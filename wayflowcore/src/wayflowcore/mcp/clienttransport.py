# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import datetime
import logging
import ssl
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Dict, List, Literal, Optional

import httpx
from mcp.client.auth import OAuthClientProvider
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client
from typing_extensions import TypeAlias

from wayflowcore.serialization.serializer import (
    SerializableDataclass,
    SerializableDataclassMixin,
    SerializableObject,
)

if TYPE_CHECKING:
    from wayflowcore.serialization.context import SerializationContext

ClientTransportContextManagerType: TypeAlias = Any
logger = logging.getLogger(__name__)


@dataclass
class SessionParameters(SerializableDataclassMixin, SerializableObject):
    """Keyword arguments for the MCP ClientSession constructor."""

    _can_be_referenced: ClassVar[bool] = False

    read_timeout_seconds: float = 60
    """How long, in seconds, to wait for a network read before
    aborting the operation. Adjust this to suit your network latency,
    slow clients or servers, or to enforce stricter timeouts for
    high-throughput scenarios."""

    def to_dict(self) -> Dict[str, Any]:
        self_as_dict = asdict(self)
        self_as_dict["read_timeout_seconds"] = datetime.timedelta(
            seconds=self_as_dict["read_timeout_seconds"]
        )
        return self_as_dict


class ClientTransport(SerializableObject, ABC):
    """
    Base class for different MCP client transport mechanisms.

    A Transport is responsible for establishing and managing connections
    to an MCP server, and providing a ClientSession within an async context.
    """

    session_parameters: SessionParameters = field(default_factory=SessionParameters)
    """Arguments for the MCP session."""

    @abstractmethod
    def _get_client_transport_cm(self) -> ClientTransportContextManagerType:
        """Return the client transport context manager"""


class ClientTransportWithAuth(ClientTransport, ABC):
    """
    Base class for different MCP client transport mechanisms with Oauth

    A Transport is responsible for establishing and managing connections
    to an MCP server, and providing a ClientSession within an async context.
    """

    @property
    @abstractmethod
    def auth(self) -> Optional[OAuthClientProvider]:
        """httpx Auth. Defaults to None."""


def _raise_if_missing(name: str) -> Callable[[], str]:
    def _raise_function() -> str:
        raise ValueError(f"Field '{name}' is a required argument")

    return _raise_function


@dataclass
class StdioTransport(SerializableDataclass, ClientTransport):
    """
    Base transport for connecting to an MCP server via subprocess with stdio.

    This is a base class that can be subclassed for specific command-based
    transports like Python, Node, Uvx, etc.

    .. note::
        The **stdio** transport is the recommended mechanism when the MCP server is launched as a local
        subprocess by the client application. This approach is ideal for scenarios where the server runs
        on the same machine as the client.

        For more information, visit https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#stdio
    """

    command: str = field(default_factory=_raise_if_missing("command"))
    """The executable to run to start the server."""

    args: List[str] = field(default_factory=list)
    """Command line arguments to pass to the executable."""

    env: Optional[Dict[str, str]] = None
    """
    The environment to use when spawning the process.

    If not specified, the result of get_default_environment() will be used.
    """

    cwd: Optional[str] = None
    """The working directory to use when spawning the process."""

    encoding: str = "utf-8"
    """
    The text encoding used when sending/receiving messages to the server. Defaults to utf-8.
    """

    encoding_error_handler: Literal["strict", "ignore", "replace"] = "strict"
    """
    The text encoding error handler.

    See https://docs.python.org/3/library/codecs.html#codec-base-classes for
    explanations of possible values.
    """

    session_parameters: SessionParameters = field(default_factory=SessionParameters)
    """Arguments for the MCP session."""

    def _get_client_transport_cm(self) -> ClientTransportContextManagerType:
        return stdio_client(
            server=StdioServerParameters(
                command=self.command,
                args=self.args,
                env=self.env,
                cwd=self.cwd,
                encoding=self.encoding,
                encoding_error_handler=self.encoding_error_handler,
            )
        )


@dataclass
class RemoteBaseTransport(SerializableDataclass, ClientTransport, ABC):
    """Base transport class for transport with all remotely hosted servers."""

    url: str = field(default_factory=_raise_if_missing("url"))
    """The URL of the server."""

    headers: Optional[Dict[str, str]] = None
    """The headers to send to the server. Keys of ``sensitive_headers`` and ``headers`` dictionaries cannot overlap."""

    sensitive_headers: Optional[Dict[str, str]] = None
    """The sensitive headers to send to the server, joined with the ones defined in the ``headers``.
    They will be excluded from any serialization for security reasons.
    Keys of ``sensitive_headers`` and ``headers`` dictionaries cannot overlap."""

    timeout: float = 5
    """The timeout for the HTTP request. Defaults to 5 seconds."""

    sse_read_timeout: float = 60 * 5
    """The timeout for the SSE connection, in seconds. Defaults to 5 minutes."""

    auth: Optional[OAuthClientProvider] = None
    """httpx Auth. Defaults to None."""

    follow_redirects: bool = True
    """Whether to automatically follow HTTP redirects (e.g., 301, 302) during requests.
    If True, the client will transparently handle and follow redirects.
    Defaults to True."""

    session_parameters: SessionParameters = field(default_factory=SessionParameters)
    """Arguments for the MCP session."""

    def __post_init__(self) -> None:
        repeated_headers = set(self.headers or {}).intersection(set(self.sensitive_headers or {}))
        if repeated_headers:
            raise ValueError(
                f"Some headers have been specified in both `headers` and "
                f"`sensitive_headers`: {repeated_headers}. This is not allowed."
            )

    @property
    def _merged_headers(self) -> Optional[Dict[str, str]]:
        # Merge sensitive and non-sensitive headers (if any) in a single dictionary
        merged_headers: Dict[str, str] = {}
        if self.headers:
            merged_headers.update(self.headers)
        if self.sensitive_headers:
            merged_headers.update(self.sensitive_headers)
        return merged_headers if merged_headers else None

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        if self.sensitive_headers is not None:
            logger.warning(
                f"Sensitive headers were configured in `{self.__class__.__name__}`, "
                f"but they will not be serialized in the config"
            )
        serialized_transport = super()._serialize_to_dict(serialization_context)
        serialized_transport.pop("sensitive_headers", None)
        return serialized_transport


class _HttpxClientFactory:
    def __init__(
        self,
        verify: bool = True,
        key_file: Optional[str] = None,
        cert_file: Optional[str] = None,
        ssl_ca_cert: Optional[str] = None,
        check_hostname: bool = True,
        follow_redirects: bool = True,
    ):
        self.verify: bool | ssl.SSLContext
        if verify:
            # Default behaviour: Client verification
            if not (key_file and cert_file and ssl_ca_cert):
                raise ValueError(
                    "When verify=True, all `key_file`, `cert_file` and `ssl_ca_cert` "
                    "must be defined."
                )
            ssl_ctx = ssl.create_default_context(cafile=ssl_ca_cert)
            ssl_ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
            ssl_ctx.check_hostname = check_hostname
            self.verify = ssl_ctx
        else:
            # If verify=False the cert/key files should not be specified
            if key_file or cert_file or ssl_ca_cert:
                raise ValueError(
                    "Either specify (`key_file`, `cert_file`, `ssl_ca_cert`) "
                    "or `verify=False`, not both."
                )
            self.verify = verify

        self.follow_redirects = follow_redirects

    def __call__(
        self,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        # Set MCP defaults
        kwargs: dict[str, Any] = {
            "follow_redirects": self.follow_redirects,
            "verify": self.verify,
        }
        # Handle timeout
        if timeout is None:
            kwargs["timeout"] = httpx.Timeout(30.0)
        else:
            kwargs["timeout"] = timeout
        # Handle headers
        if headers is not None:
            kwargs["headers"] = headers
        # Handle authentication
        if auth is not None:
            kwargs["auth"] = auth
        return httpx.AsyncClient(**kwargs)


@dataclass
class SSETransport(RemoteBaseTransport, ClientTransportWithAuth, SerializableObject):
    """
    Transport implementation that connects to an MCP server via Server-Sent Events.

    .. warning::
        This transport should be used for prototyping only. For production, please use
        a transport that supports mTLS.

    Examples
    --------
    >>> from wayflowcore.mcp import SSETransport
    >>> transport = SSETransport(url="https://server/sse")

    """

    def _get_client_transport_cm(self) -> ClientTransportContextManagerType:
        return sse_client(
            url=self.url,
            headers=self._merged_headers,
            timeout=self.timeout,
            sse_read_timeout=self.sse_read_timeout,
            auth=self.auth,
            httpx_client_factory=_HttpxClientFactory(
                verify=False, follow_redirects=self.follow_redirects
            ),
        )


@dataclass
class HTTPmTLSBaseTransport(RemoteBaseTransport):
    """
    Base implementation for all transports with mTLS (mutual Transport Layer Security).
    """

    key_file: str = field(default_factory=_raise_if_missing("key_file"))
    """The path to the client's private key file (PEM format). If None, mTLS cannot be performed."""

    cert_file: str = field(default_factory=_raise_if_missing("cert_file"))
    """The path to the client's certificate chain file (PEM format). If None, mTLS cannot be performed."""

    ssl_ca_cert: str = field(default_factory=_raise_if_missing("ssl_ca_cert"))
    """The path to the trusted CA certificate file (PEM format) to verify the server. If None, system cert store is used."""

    check_hostname: bool = False
    """Whether to verify that the server's hostname matches the certificate.
    If True, the client will reject connections where the server's certificate hostname does not match the expected hostname.
    Defaults to False."""


@dataclass
class SSEmTLSTransport(HTTPmTLSBaseTransport, ClientTransportWithAuth, SerializableObject):
    """
    Transport layer for SSE with mTLS (mutual Transport Layer Security).

    This transport establishes a secure, mutually authenticated TLS connection to the MCP server using client
    certificates. Production deployments MUST use this transport to ensure both client and server identities
    are verified.

    Notes
    -----
    - Users MUST provide a valid client certificate (PEM format) and private key.
    - Users MUST provide (or trust) the correct certificate authority (CA) for the server they're connecting to.
    - The client certificate/key and CA certificate paths can be managed via secrets, config files, or secure
      environment variables in any production system.
    - Executors should ensure that these files are rotated and managed securely.

    Examples
    --------
    >>> from wayflowcore.mcp import SSEmTLSTransport
    >>> mtls = SSEmTLSTransport(
    ...   url="https://server/sse",
    ...   key_file="/etc/certs/client.key",
    ...   cert_file="/etc/certs/client.pem",
    ...   ssl_ca_cert="/etc/certs/ca.pem"
    ... )
    >>> # To pass a Bearer token, use the headers argument:
    >>> mtls_2 = SSEmTLSTransport(
    ...   url="https://server/sse",
    ...   key_file="...",
    ...   cert_file="...",
    ...   ssl_ca_cert="...",
    ...   sensitive_headers={"Authorization": "Bearer <token>"}
    ... )

    """

    def _get_client_transport_cm(self) -> ClientTransportContextManagerType:
        return sse_client(
            self.url,
            headers=self._merged_headers,
            timeout=self.timeout,
            sse_read_timeout=self.sse_read_timeout,
            auth=self.auth,
            httpx_client_factory=_HttpxClientFactory(
                key_file=self.key_file,
                cert_file=self.cert_file,
                ssl_ca_cert=self.ssl_ca_cert,
                check_hostname=self.check_hostname,
                follow_redirects=self.follow_redirects,
            ),
        )


@dataclass
class StreamableHTTPTransport(RemoteBaseTransport, ClientTransportWithAuth, SerializableObject):
    """
    Transport implementation that connects to an MCP server via Streamable HTTP.
    This transport is the recommended option when connecting to a remote MCP server.

    .. warning::
        This transport should be used for prototyping only. For production, please use
        a transport that supports mTLS.

    Examples
    --------
    >>> from wayflowcore.mcp import StreamableHTTPTransport
    >>> transport = StreamableHTTPTransport(url="https://server/mcp")

    """

    def _get_client_transport_cm(self) -> ClientTransportContextManagerType:
        return streamablehttp_client(
            url=self.url,
            headers=self._merged_headers,
            timeout=datetime.timedelta(seconds=self.timeout),
            sse_read_timeout=datetime.timedelta(seconds=self.sse_read_timeout),
            auth=self.auth,
            httpx_client_factory=_HttpxClientFactory(
                verify=False, follow_redirects=self.follow_redirects
            ),
        )


@dataclass
class StreamableHTTPmTLSTransport(
    HTTPmTLSBaseTransport, ClientTransportWithAuth, SerializableObject
):
    """
    Transport layer for streamable HTTP with mTLS (mutual Transport Layer Security).

    This transport establishes a secure, mutually authenticated TLS connection to the MCP server using client
    certificates. Production deployments MUST use this transport to ensure both client and server identities
    are verified.

    Notes
    -----
    - Users MUST provide a valid client certificate (PEM format) and private key.
    - Users MUST provide (or trust) the correct certificate authority (CA) for the server they're connecting to.
    - The client certificate/key and CA certificate paths can be managed via secrets, config files, or secure
      environment variables in any production system.
    - Executors should ensure that these files are rotated and managed securely.

    Examples
    --------
    >>> from wayflowcore.mcp import StreamableHTTPmTLSTransport
    >>> mtls = StreamableHTTPmTLSTransport(
    ...   url="https://server/mcp",
    ...   key_file="/etc/certs/client.key",
    ...   cert_file="/etc/certs/client.pem",
    ...   ssl_ca_cert="/etc/certs/ca.pem"
    ... )
    >>> # To pass a Bearer token, use the headers argument:
    >>> mtls_2 = StreamableHTTPmTLSTransport(
    ...   url="https://server/mcp",
    ...   key_file="...",
    ...   cert_file="...",
    ...   ssl_ca_cert="...",
    ...   sensitive_headers={"Authorization": "Bearer <token>"}
    ... )

    """

    def _get_client_transport_cm(self) -> ClientTransportContextManagerType:
        return streamablehttp_client(
            url=self.url,
            headers=self._merged_headers,
            timeout=datetime.timedelta(seconds=self.timeout),
            sse_read_timeout=datetime.timedelta(seconds=self.sse_read_timeout),
            auth=self.auth,
            httpx_client_factory=_HttpxClientFactory(
                key_file=self.key_file,
                cert_file=self.cert_file,
                ssl_ca_cert=self.ssl_ca_cert,
                check_hostname=self.check_hostname,
                follow_redirects=self.follow_redirects,
            ),
        )
