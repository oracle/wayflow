# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from wayflowcore._utils.dataclass_utils import _required_attribute
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableDataclass, SerializableObject


@dataclass
class AuthChallengeRequest(SerializableDataclass):
    """Dataclass to store auth challenge request data to
    present to the client/app to complete an auth flow."""

    resource_uri: Optional[str]
    """The protected resource being accessed (e.g., MCP server URL or API base URL).
        May be omitted if not known or not applicable."""
    issuer: Optional[list[str]]
    """The OAuth/OIDC authorization server issuer identifier (typically a URL).
        May be omitted if discovery is not used or issuer is unknown."""
    authorization_url: str
    """The authorization endpoint URL to which the user agent should be directed
        to authenticate and grant consent."""

    _conversation_id: Optional[str] = None


@dataclass
class AuthChallengeResult(SerializableDataclass):
    """Dataclass to store OAuth challenge result information.

    The auth ``code`` and ``state`` are then exchanged with the OAuth tokens.
    """

    code: Optional[str] = None
    """OAuth 2.0 authorization code returned to the redirect URI, if the user
        successfully authenticated/consented."""
    state: Optional[str] = None
    """Opaque value originally provided in the authorization request and returned
        in the callback. Used to correlate/validate the response."""
    error: Optional[Exception] = None
    """Exception describing failure to complete the challenge (e.g., user
        cancelled, redirect contained an error parameter, network/timeout)."""


class AuthConfig(SerializableObject, ABC):
    """Base class for Auth configurations."""


@dataclass
class OAuthEndpoints(SerializableDataclass):
    """
    Explicit OAuth endpoint configuration.

    Use this component when endpoint discovery is not available or not desired.
    This groups the relevant endpoints required to execute OAuth authorization
    code flows and token refresh.
    """

    authorization_endpoint: str
    """Authorization endpoint where the user agent is redirected for login and consent."""
    token_endpoint: str
    """Token endpoint where authorization codes are exchanged for access tokens."""
    refresh_endpoint: Optional[str] = None
    """Optional endpoint for refresh token requests."""
    revocation_endpoint: Optional[str] = None
    """Optional endpoint for token revocation."""
    userinfo_endpoint: Optional[str] = None
    """Optional OIDC UserInfo endpoint."""


class PKCEMethod(str, Enum):
    PLAIN = "plain"
    """Code challenge is equal to code verifier."""
    S256 = "S256"
    """Code verifier is hashed using SHA-256. Recommended over the ``plain`` method"""


@dataclass
class PKCEPolicy(SerializableDataclass):
    """
    Policy configuration for Proof Key for Code Exchange (PKCE).

    PKCE mitigates authorization code interception and injection attacks in
    authorization code flows. Some protocols (such as MCP OAuth) require PKCE.
    """

    required: bool = True
    """If True, the connection must be refused if PKCE cannot be used or
        cannot be validated as supported by the authorization server.
        Defaults to ``True``."""
    method: PKCEMethod = PKCEMethod.S256
    """PKCE challenge method (e.g., ``"S256"``). Defaults to ``"S256"``."""


@dataclass
class OAuthClientConfig(SerializableDataclass):
    """
    OAuth client identity / registration configuration.

    This configuration describes the OAuth client identity to use
    with the authorization server. It supports:
    - Pre-registered clients (static client_id/client_secret)
    - Client ID Metadata Documents (URL-formatted client_id)
    - Dynamic client registration (RFC 7591)

    """

    type: Literal["pre_registered", "client_id_metadata_document", "dynamic_registration"]
    """Strategy used to obtain client identity."""

    # Pre-registered client fields
    client_id: Optional[str] = None
    """OAuth client identifier (used for pre-registered clients)."""
    client_secret: Optional[str] = None
    """OAuth client secret (used for confidential pre-registered clients)."""
    token_endpoint_auth_method: Optional[str] = None
    """Token endpoint authentication method (e.g., ``"client_secret_basic"``,
        ``"client_secret_post"``, ``"private_key_jwt"``, or ``"none"``)."""

    # Client ID Metadata Document field
    client_id_metadata_url: Optional[str] = None
    """HTTPS URL used as the OAuth ``client_id`` for Client ID Metadata Documents."""

    # Dynamic registration field
    registration_endpoint: Optional[str] = None
    """Optional dynamic registration endpoint. If omitted, may be obtained
        from authorization server discovery metadata when available."""

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return {
            "type": self.type,
            "token_endpoint_auth_method": self.token_endpoint_auth_method,
        }

    @classmethod
    def _deserialize_from_dict(
        cls,
        input_dict: Dict[str, Any],
        deserialization_context: "DeserializationContext",
    ) -> "SerializableObject":
        # Only restore what we serialized; ignore any extra fields if present.
        return cls(
            type=input_dict["type"],
            token_endpoint_auth_method=input_dict["token_endpoint_auth_method"],
            client_id=None,
            client_secret=None,
            client_id_metadata_url=None,
            registration_endpoint=None,
            id=input_dict.get("id") or IdGenerator.get_or_generate_id(),
        )


@dataclass
class OAuthConfig(SerializableDataclass, AuthConfig):
    """
    Configure OAuth-based authentication for a tool or transport.

    OAuthConfig is a generic configuration that can be used for both MCP servers
    and non-MCP remote API tools. It supports discovery-based configuration (via
    ``issuer``) and explicit endpoints (via ``endpoints``).

    """

    issuer: Optional[str] = None
    """Authorization server issuer URL used for discovery (e.g., OIDC discovery
        or RFC 8414)."""
    endpoints: Optional[OAuthEndpoints] = None
    """Explicit OAuth endpoints. When provided, these endpoints should be used
        directly instead of discovery."""
    client: OAuthClientConfig = field(
        default_factory=_required_attribute("client", OAuthClientConfig)
    )
    """OAuth client identity / registration configuration."""

    redirect_uri: str = field(default_factory=_required_attribute("redirect_uri", str))
    """Redirect (callback) URI registered with the authorization server."""
    scopes: Optional[Union[str, List[str]]] = None
    """Requested scopes, either as a space-delimited string or a list of scope
        strings."""
    scope_policy: Optional[Literal["use_challenge_or_supported", "fixed"]] = None
    """
    How the scopes are selected.

    * ``"use_challenge_or_supported"``: may prefer scopes indicated by
        challenges/metadata.
    * ``"fixed"``: requests exactly the provided scopes.
    """

    pkce: Optional[PKCEPolicy] = None
    """PKCE policy. For authorization code flows, this should typically be set
        to required with method ``S256``."""
    resource: Optional[str] = None
    """Optional resource indicator value (RFC 8707). If set, this should be
        includeed with relevant authorization and token requests when applicable."""

    callback_timeout_seconds: float = 300.0
    """Maximum time to wait for the OAuth callback/challenge results to be received before timing out."""
