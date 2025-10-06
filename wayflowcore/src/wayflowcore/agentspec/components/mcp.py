# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import List, Literal, Optional, Union

from pyagentspec.mcp.clienttransport import ClientTransport, RemoteTransport, StdioTransport
from pyagentspec.tools import ServerTool
from pyagentspec.tools.tool import Tool
from pydantic import ConfigDict, Field, SerializeAsAny

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)
from wayflowcore.agentspec.components.tools import PluginToolBox


class PluginClientTransport(ClientTransport, abstract=True):
    """
    Base class for different MCP client transport mechanisms.

    A Transport is responsible for establishing and managing connections
    to an MCP server, and providing a ClientSession within an async context.
    """


class PluginRemoteBaseTransport(RemoteTransport, abstract=True):
    """Base transport class for transport with all remotely hosted servers."""

    timeout: float = 5
    """The timeout for the HTTP request. Defaults to 5 seconds."""

    sse_read_timeout: float = 60 * 5
    """The timeout for the SSE connection, in seconds. Defaults to 5 minutes."""


class PluginSSETransport(PluginRemoteBaseTransport, PluginClientTransport):
    """Transport implementation that connects to an MCP server via Server-Sent Events."""


class PluginHTTPmTLSBaseTransport(PluginRemoteBaseTransport):
    """Base implementation for all transports with mTLS (mutual Transport Layer Security)."""

    key_file: str
    """The path to the client's private key file (PEM format). If None, mTLS cannot be performed."""

    cert_file: str
    """The path to the client's certificate chain file (PEM format). If None, mTLS cannot be performed."""

    ca_file: str = Field(alias="ssl_ca_cert")
    """The path to the trusted CA certificate file (PEM format) to verify the server.
    If None, system cert store is used."""

    model_config = ConfigDict(populate_by_name=True)


class PluginSSEmTLSTransport(PluginHTTPmTLSBaseTransport, PluginClientTransport):
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

    """


class PluginStreamableHTTPTransport(PluginRemoteBaseTransport, PluginClientTransport):
    """Transport implementation that connects to an MCP server via Streamable HTTP."""


class PluginStreamableHTTPmTLSTransport(PluginHTTPmTLSBaseTransport, PluginClientTransport):
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

    """


class PluginMCPToolSpec(Tool):
    """Specification of MCP tool"""


class PluginMCPTool(ServerTool):
    """Class for tools exposed by MCP servers"""

    client_transport: SerializeAsAny[ClientTransport]
    """Transport to use for establishing and managing connections to the MCP server."""


class PluginMCPToolBox(PluginToolBox):
    """Class to dynamically expose a list of tools from a MCP Server."""

    client_transport: SerializeAsAny[ClientTransport]
    """Transport to use for establishing and managing connections to the MCP server."""

    tool_filter: Optional[List[Union[PluginMCPToolSpec, str]]] = None
    """
    Optional filter to select specific tools.

    If None, exposes all tools from the MCP server.

    * Specifying a tool name (``str``) indicates that a tool of the given name is expected from the MCP server.
    * Specifying a tool signature (``Tool``) validate the presence and signature of the specified tool in the MCP Server.
        * The name of the MCP tool should match the name of the tool from the MCP Server.
        * Specifying a non-empty description will override the remote tool description.
        * Input descriptors can be provided with description of each input. The names and types should match the remote tool schema.

    """


class PluginStdioTransport(PluginClientTransport, StdioTransport):
    """
    Base transport for connecting to an MCP server via subprocess with stdio.

    This is a base class that can be subclassed for specific command-based
    transports like Python, Node, Uvx, etc.

    .. warning::
        Stdio should be used for local prototyping only.
    """

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


MCP_PLUGIN_NAME = "MCPPlugin"

mcp_serialization_plugin = PydanticComponentSerializationPlugin(
    name=MCP_PLUGIN_NAME,
    component_types_and_models={
        PluginStdioTransport.__name__: PluginStdioTransport,
        PluginSSETransport.__name__: PluginSSETransport,
        PluginMCPToolSpec.__name__: PluginMCPToolSpec,
        PluginMCPTool.__name__: PluginMCPTool,
        PluginMCPToolBox.__name__: PluginMCPToolBox,
        PluginSSEmTLSTransport.__name__: PluginSSEmTLSTransport,
        PluginStreamableHTTPTransport.__name__: PluginStreamableHTTPTransport,
        PluginStreamableHTTPmTLSTransport.__name__: PluginStreamableHTTPmTLSTransport,
    },
)
mcp_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=MCP_PLUGIN_NAME,
    component_types_and_models={
        PluginStdioTransport.__name__: PluginStdioTransport,
        PluginSSETransport.__name__: PluginSSETransport,
        PluginMCPToolSpec.__name__: PluginMCPToolSpec,
        PluginMCPTool.__name__: PluginMCPTool,
        PluginMCPToolBox.__name__: PluginMCPToolBox,
        PluginSSEmTLSTransport.__name__: PluginSSEmTLSTransport,
        PluginStreamableHTTPTransport.__name__: PluginStreamableHTTPTransport,
        PluginStreamableHTTPmTLSTransport.__name__: PluginStreamableHTTPmTLSTransport,
    },
)
