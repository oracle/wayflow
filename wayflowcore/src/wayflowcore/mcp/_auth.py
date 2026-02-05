# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import ssl
from collections.abc import AsyncGenerator
from typing import Optional, TypeAlias
from urllib.parse import parse_qs, parse_qsl, urlparse

import anyio
import httpx
from exceptiongroup import ExceptionGroup
from mcp.client.auth import OAuthClientProvider, OAuthFlowError, OAuthTokenError, TokenStorage
from mcp.client.auth.utils import (
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
    create_client_info_from_metadata_url,
    create_client_registration_request,
    create_oauth_metadata_request,
    extract_field_from_www_auth,
    extract_resource_metadata_from_www_auth,
    extract_scope_from_www_auth,
    get_client_metadata_scopes,
    handle_auth_metadata_response,
    handle_protected_resource_response,
    handle_registration_response,
    should_use_client_metadata_url,
)
from mcp.client.streamable_http import MCP_PROTOCOL_VERSION
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from pydantic import ValidationError

from wayflowcore.auth.auth import AuthChallengeRequest, AuthChallengeResult, OAuthConfig
from wayflowcore.mcp._session_persistence import AsyncRuntime, MemoryStreamTypeT

AuthCodeT: TypeAlias = str
AuthStateT: TypeAlias = str

logger = logging.getLogger(__name__)


class OAuthCancelledStatus:
    """Marker used when an OAuth flow is cancelled."""


class OAuthCancelledError(OAuthFlowError):
    """Raised when OAuth flow is cancelled."""


class InMemoryTokenStorage(TokenStorage):
    def __init__(self, server_url: str) -> None:
        self._server_url = server_url
        self._storage_oauth_token: dict[str, OAuthToken] = {}
        self._storage_client_info: dict[str, OAuthClientInformationFull] = {}

    def _get_token_cache_key(self) -> str:
        return f"{self._server_url}/tokens"

    def _get_client_info_cache_key(self) -> str:
        return f"{self._server_url}/client_info"

    async def get_tokens(self) -> OAuthToken | None:
        return self._storage_oauth_token.get(self._get_token_cache_key())

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._storage_oauth_token[self._get_token_cache_key()] = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self._storage_client_info.get(self._get_client_info_cache_key())

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._storage_client_info[self._get_client_info_cache_key()] = client_info


HANDLER_NOT_INIT_MSG = "OAuth flow handler not bound to portal or event not initialized."


class OAuthFlowHandler(OAuthClientProvider):
    def __init__(
        self,
        mcp_url: str,
        oauth_config: "OAuthConfig",
    ) -> None:
        # MCP runtime state
        self._send_chan = None
        self._portal: Optional[AsyncRuntime] = None
        self.callbackresult_submitted_event: Optional[anyio.Event] = None
        self.oauth_flow_completed_event: Optional[anyio.Event] = None
        self._callback_result: AuthChallengeResult | OAuthCancelledStatus | None = None
        self._transport_id: str | None = None
        self._conversation_id: str | None = None

        # Normalize server base URL
        parsed_url = urlparse(mcp_url)
        server_base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        token_storage = InMemoryTokenStorage(server_url=server_base_url)

        # Validate required config
        if not oauth_config.redirect_uri:
            raise ValueError("OAuthConfig.redirect_uri is required for MCP OAuth flows.")

        # Build scopes string for MCP client's OAuthClientMetadata
        scopes_str: str = ""
        if isinstance(oauth_config.scopes, list):
            scopes_str = " ".join(oauth_config.scopes)
        elif oauth_config.scopes is not None:
            scopes_str = str(oauth_config.scopes)

        # Build minimal OAuth client metadata
        client_metadata = OAuthClientMetadata(
            client_name="WayFlow MCP Client",
            redirect_uris=[oauth_config.redirect_uri],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope=scopes_str or None,
            token_endpoint_auth_method=oauth_config.client.token_endpoint_auth_method,
        )

        # Optional URL-based client id (CIMD)
        client_metadata_url: Optional[str] = None
        if oauth_config.client.type == "client_id_metadata_document":
            client_metadata_url = oauth_config.client.client_id_metadata_url
            if not client_metadata_url:
                raise ValueError(
                    "OAuthClientConfig.type='client_id_metadata_document' requires client_id_metadata_url."
                )

        # Optional seed client_info for pre-registered clients
        client_info: Optional[OAuthClientInformationFull] = None
        if oauth_config.client.type == "pre_registered":
            if not oauth_config.client.client_id:
                raise ValueError("OAuthClientConfig.type='pre_registered' requires client_id.")

            client_info = OAuthClientInformationFull(
                redirect_uris=client_metadata.redirect_uris,
                token_endpoint_auth_method=oauth_config.client.token_endpoint_auth_method,
                grant_types=client_metadata.grant_types,
                response_types=client_metadata.response_types,
                scope=client_metadata.scope,
                client_name=client_metadata.client_name,
                # Client identity
                client_id=oauth_config.client.client_id,
                client_secret=oauth_config.client.client_secret,
            )

        super().__init__(
            server_url=server_base_url,
            client_metadata=client_metadata,
            storage=token_storage,
            redirect_handler=self.redirect_handler,
            callback_handler=self.callback_handler,
        )

        self.context.client_info = client_info  # sets pre-registered client info
        if oauth_config.issuer:
            self.context.auth_server_url = oauth_config.issuer

        self._initialized = True  # important otherwise client info is reset.

    @property
    def portal(self) -> AsyncRuntime:
        if self._portal is None:
            raise ValueError(HANDLER_NOT_INIT_MSG)
        return self._portal

    def bind_runtime(
        self,
        portal: AsyncRuntime,
        memory_stream: MemoryStreamTypeT,
        transport_id: str,
        conversation_id: str,
    ) -> None:
        """This method is called by the MCP Runtime when creating a new long-lived MCP client session."""
        send_chan, _ = memory_stream
        self._send_chan = send_chan
        self._portal = portal
        self._transport_id = transport_id
        self._conversation_id = conversation_id

        async def _create_event() -> None:
            self.callbackresult_submitted_event = anyio.Event()
            self.oauth_flow_completed_event = anyio.Event()

        # the events need to be created in the same thread
        # -> we instantiate through the portal
        self.portal.call(_create_event)

    def _cancel_oauth_flow(self) -> None:
        self._callback_result = OAuthCancelledStatus()

        async def _set() -> None:
            """Indicates to the callback_handler that the auth flow should be
            continued. The `OAuthCancelledStatus` will indicate that cancellation
            is required."""
            if self.callbackresult_submitted_event is None:
                raise RuntimeError(HANDLER_NOT_INIT_MSG)
            self.callbackresult_submitted_event.set()

        self.portal.call(_set)
        logger.debug(
            "Submitted Empty OAuth callback results for transport id '%s', conversation id '%s'",
            self._transport_id,
            self._conversation_id,
        )

    def _submit_oauth_callbackresult(
        self,
        result: AuthChallengeResult,
        oauth_completion_timeout: float,
    ) -> None:
        self._callback_result = result

        async def _set() -> None:
            """Indicates to the callback_handler that the auth challenge
            has been submitted and that the OAuth flow can be continued."""
            if self.callbackresult_submitted_event is None:
                raise RuntimeError(HANDLER_NOT_INIT_MSG)
            self.callbackresult_submitted_event.set()

        self.portal.call(_set)
        logger.debug(
            "Submitted OAuth callback results for transport id '%s', conversation id '%s'",
            self._transport_id,
            self._conversation_id,
        )

        async def _wait_for_oauth_completion() -> None:
            flow_completed = anyio.Event()

            async def _wait() -> None:
                if self.oauth_flow_completed_event is None:
                    raise RuntimeError(HANDLER_NOT_INIT_MSG)
                await self.oauth_flow_completed_event.wait()
                flow_completed.set()

            async with anyio.create_task_group() as tg:
                tg.start_soon(_wait)
                try:
                    with anyio.fail_after(oauth_completion_timeout):
                        await flow_completed.wait()
                        return
                except TimeoutError as e:
                    raise TimeoutError(
                        f"OAuth flow did not complete after {oauth_completion_timeout} seconds"
                    ) from e
                finally:
                    await anyio.sleep(0.1)
                    tg.cancel_scope.cancel()

            raise RuntimeError("OAuth flow could not be completed")

        self.portal.call(_wait_for_oauth_completion)
        logger.debug(
            "Completed OAuth flow for transport id '%s', conversation id '%s'",
            self._transport_id,
            self._conversation_id,
        )

    async def redirect_handler(self, authorization_url: str) -> None:
        if self._send_chan is None:
            raise ValueError(HANDLER_NOT_INIT_MSG)
        auth_request = AuthChallengeRequest(
            authorization_url, _conversation_id=self._conversation_id
        )
        await self._send_chan.send(auth_request)

    async def callback_handler(self) -> tuple[AuthCodeT, AuthStateT | None]:
        logger.debug(
            "Calling OAuth callback handler for transport id '%s', conversation id '%s'",
            self._transport_id,
            self._conversation_id,
        )

        result = AuthChallengeResult()
        result_ready = anyio.Event()

        async def callback_runner() -> None:
            if self.callbackresult_submitted_event is None:
                raise RuntimeError("Result event not initialized")

            await self.callbackresult_submitted_event.wait()

            if self._callback_result is None:
                raise ValueError("None callback response")
            elif isinstance(self._callback_result, OAuthCancelledStatus):
                raise OAuthCancelledError()

            cb_res = self._callback_result
            result.code = cb_res.code
            result.state = cb_res.state
            result.error = cb_res.error
            result_ready.set()

        async with anyio.create_task_group() as tg:
            TIMEOUT = 300.0
            # ^ 5 minute timeout for client to complete any auth
            # challenge and submit the results back.
            tg.start_soon(callback_runner)
            try:
                with anyio.fail_after(TIMEOUT):
                    await result_ready.wait()
                    if result.error:
                        raise result.error
                    return result.code, result.state  # type: ignore
            except TimeoutError as e:
                raise TimeoutError(f"OAuth callback timed out after {TIMEOUT} seconds") from e
            finally:
                await anyio.sleep(0.1)
                tg.cancel_scope.cancel()

        raise RuntimeError("OAuth callback handler could not be completed")

    async def _handle_token_response(self, response: httpx.Response) -> None:
        """Handle token exchange response."""
        # overriding OAuthClientProvider._handle_token_response
        # to use modified `handle_token_response_scopes` function
        if response.status_code != 200:
            body = await response.aread()
            body_text = body.decode("utf-8")
            raise OAuthTokenError(f"Token exchange failed ({response.status_code}): {body_text}")

        # Parse and validate response with scope validation
        token_response = await handle_token_response_scopes(response)

        # Store tokens in context
        self.context.current_tokens = token_response
        self.context.update_token_expiry(token_response)
        await self.context.storage.set_tokens(token_response)

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        """HTTPX auth flow integration."""
        async with self.context.lock:
            if not self._initialized:
                await self._initialize()

            # Capture protocol version from request headers
            self.context.protocol_version = request.headers.get(MCP_PROTOCOL_VERSION)

            if not self.context.is_token_valid() and self.context.can_refresh_token():
                # Try to refresh token
                refresh_request = await self._refresh_token()
                refresh_response = yield refresh_request

                if not await self._handle_refresh_response(refresh_response):
                    # Refresh failed, need full re-authentication
                    self._initialized = False

            if self.context.is_token_valid():
                self._add_auth_header(request)

            # need to add something when failing to
            try:
                response = yield request
            except GeneratorExit as e:
                raise ValueError("Error when sending first request. Maybe due to VPN.")

            if response.status_code == 401:
                # Perform full OAuth flow
                try:
                    # OAuth flow must be inline due to generator constraints
                    www_auth_resource_metadata_url = extract_resource_metadata_from_www_auth(
                        response
                    )
                    # Step 1: Discover protected resource metadata (SEP-985 with fallback support)
                    prm_discovery_urls = build_protected_resource_metadata_discovery_urls(
                        www_auth_resource_metadata_url, self.context.server_url
                    )

                    for url in prm_discovery_urls:  # pragma: no branch
                        discovery_request = create_oauth_metadata_request(url)

                        discovery_response = yield discovery_request  # sending request

                        prm = await handle_protected_resource_response(discovery_response)
                        if prm:
                            self.context.protected_resource_metadata = prm

                            # todo: try all authorization_servers to find the OASM
                            assert (
                                len(prm.authorization_servers) > 0
                            )  # this is always true as authorization_servers has a min length of 1

                            self.context.auth_server_url = str(prm.authorization_servers[0])
                            break
                        else:
                            logger.debug(f"Protected resource metadata discovery failed: {url}")

                    asm_discovery_urls = build_oauth_authorization_server_metadata_discovery_urls(
                        self.context.auth_server_url, self.context.server_url
                    )

                    # Step 2: Discover OAuth Authorization Server Metadata (OASM) (with fallback for legacy servers)
                    for url in asm_discovery_urls:
                        oauth_metadata_request = create_oauth_metadata_request(url)
                        oauth_metadata_response = yield oauth_metadata_request

                        ok, asm = await handle_auth_metadata_response(oauth_metadata_response)
                        if not ok:
                            break
                        if ok and asm:
                            self.context.oauth_metadata = asm
                            break
                        else:
                            logger.debug(f"OAuth metadata discovery failed: {url}")

                    # Step 3: Apply scope selection strategy
                    self.context.client_metadata.scope = get_client_metadata_scopes(
                        extract_scope_from_www_auth(response),
                        self.context.protected_resource_metadata,
                        self.context.oauth_metadata,
                    )

                    # Step 4: Register client or use URL-based client ID (CIMD)
                    if not self.context.client_info:
                        if should_use_client_metadata_url(
                            self.context.oauth_metadata, self.context.client_metadata_url
                        ):
                            # Use URL-based client ID (CIMD)
                            logger.debug(
                                f"Using URL-based client ID (CIMD): {self.context.client_metadata_url}"
                            )
                            client_information = create_client_info_from_metadata_url(
                                self.context.client_metadata_url,  # type: ignore[arg-type]
                                redirect_uris=self.context.client_metadata.redirect_uris,
                            )
                            self.context.client_info = client_information
                            await self.context.storage.set_client_info(client_information)
                        else:
                            # Fallback to Dynamic Client Registration
                            registration_request = create_client_registration_request(
                                self.context.oauth_metadata,
                                self.context.client_metadata,
                                self.context.get_authorization_base_url(self.context.server_url),
                            )
                            registration_response = yield registration_request
                            client_information = await handle_registration_response(
                                registration_response
                            )
                            self.context.client_info = client_information
                            await self.context.storage.set_client_info(client_information)

                    # Step 5: continued after lock release below
                except Exception:
                    self._signal_oauth_completion_with_error()
                    raise

        # modified section - requires releasing lock
        if response.status_code == 401:
            try:
                # Step 5.a: Perform authorization
                auth_code, code_verifier = await self._perform_authorization_code_grant()
            except ExceptionGroup as e:
                if any(isinstance(sub_exc, OAuthCancelledError) for sub_exc in e.exceptions):
                    raise e  # raise the error to catch it in the session runner
                else:
                    self._signal_oauth_completion_with_error()
                    raise
            except Exception:
                self._signal_oauth_completion_with_error()
                raise

        # finishing exchange when status code was 401
        async with self.context.lock:
            if response.status_code == 401:
                try:
                    # Step 5.b: Complete token exchange
                    token_response = yield await self._exchange_token_authorization_code(
                        auth_code, code_verifier
                    )
                    # ^ modification from https://github.com/modelcontextprotocol/python-sdk/blob/d3133ae6ce7333a501e38046aff4275c44326f90/src/mcp/client/auth/oauth2.py#L583C50-L583C79
                    # broken self._perform_authorization() into its 2 calls
                    await self._handle_token_response(token_response)
                except Exception:
                    self._signal_oauth_completion_with_error()
                    raise

                # Retry with new tokens
                self._add_auth_header(request)
                yield request
            elif response.status_code == 403:
                # Step 1: Extract error field from WWW-Authenticate header
                error = extract_field_from_www_auth(response, "error")

                # Step 2: Check if we need to step-up authorization
                if error == "insufficient_scope":  # pragma: no branch
                    try:
                        # Step 2a: Update the required scopes
                        self.context.client_metadata.scope = get_client_metadata_scopes(
                            extract_scope_from_www_auth(response),
                            self.context.protected_resource_metadata,
                        )

                        # Step 2b: Perform (re-)authorization and token exchange
                        token_response = yield await self._perform_authorization()
                        await self._handle_token_response(token_response)
                    except Exception:
                        self._signal_oauth_completion_with_error()
                        raise

                # Retry with new tokens
                self._add_auth_header(request)
                yield request

    def _signal_oauth_completion_with_error(self) -> None:
        logger.exception("OAuth flow error")
        if self.oauth_flow_completed_event is None:
            raise RuntimeError("OAuth flow handler not bound to portal or event not initialized")
        self.oauth_flow_completed_event.set()


def headless_auth_flow_handler(
    authorization_url: str, verify: ssl.SSLContext | bool = True
) -> tuple[str, str | None]:
    """Helper function to get the auth code and state from an authorization url,
    for auth flows compatible with headless completion (for prototyping only)."""
    with httpx.Client(verify=verify) as client:
        response = client.get(authorization_url, follow_redirects=False)

    if response.status_code == 302:
        redirect_url = response.headers["location"]
        parsed = urlparse(redirect_url)
        query_params = parse_qs(parsed.query)

        if "error" in query_params:
            error = query_params["error"][0]
            error_desc = query_params.get("error_description", ["Unknown error"])[0]
            raise RuntimeError(f"OAuth authorization failed: {error} - {error_desc}")

        auth_code = query_params["code"][0]
        state = query_params.get("state", [None])[0]
        return auth_code, state
    else:
        raise RuntimeError(f"Authorization failed: {response.status_code}")


async def handle_token_response_scopes(response: httpx.Response) -> OAuthToken:
    """Parse and validate token response with optional scope validation."""
    try:
        content = await response.aread()
        try:
            return OAuthToken.model_validate_json(content)
        except ValidationError:
            # fallback (fix for some MCP servers): try with query parsing
            parsed_content = parse_qsl(content.decode("utf-8"), keep_blank_values=True)
            return OAuthToken.model_validate(parsed_content)
    except ValidationError as e:
        raise OAuthTokenError(f"Invalid token response: {e}")
