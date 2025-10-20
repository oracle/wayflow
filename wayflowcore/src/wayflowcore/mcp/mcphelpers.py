# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

from exceptiongroup import ExceptionGroup
from httpx import ConnectError
from mcp import types as types

from wayflowcore.exceptions import NoSuchToolFoundOnMCPServerError
from wayflowcore.mcp.clienttransport import ClientTransport, ClientTransportWithAuth
from wayflowcore.property import Property
from wayflowcore.tools.servertools import ServerTool
from wayflowcore.tools.tools import Tool

logger = logging.getLogger(__name__)

# Whether the developer enables the use of MCP without authentication
_GLOBAL_ENABLED_MCP_WITHOUT_AUTH: ContextVar[bool] = ContextVar(
    "_GLOBAL_ENABLED_MCP_WITHOUT_AUTH", default=False
)


def enable_mcp_without_auth() -> None:
    """Helper function to enable the use of client transport without authentication.

    .. warning::
        This method should only be used in prototyping.

    Example
    -------
    >>> from wayflowcore.mcp import enable_mcp_without_auth, MCPToolBox, SSETransport
    >>> enable_mcp_without_auth()
    >>> transport = SSETransport(
    ...     url="https://localhost:8443/sse",
    ... )
    >>> mcp_toolbox = MCPToolBox(client_transport=transport)

    """
    _GLOBAL_ENABLED_MCP_WITHOUT_AUTH.set(True)


def _reset_mcp_contextvar() -> None:
    _GLOBAL_ENABLED_MCP_WITHOUT_AUTH.set(False)


def _is_mcp_without_auth_enabled() -> bool:
    return _GLOBAL_ENABLED_MCP_WITHOUT_AUTH.get()


def _validate_auth(client_transport: ClientTransport) -> None:
    if (
        not (isinstance(client_transport, ClientTransportWithAuth) and client_transport.auth)
        and not _is_mcp_without_auth_enabled()
    ):
        raise ValueError(
            "Using MCP servers without proper authentication is highly discouraged. "
            "If you still want to use it, please call `enable_mcp_without_auth` before "
            "instantiating the MCPToolBox."
        )


@contextmanager
def _catch_and_raise_mcp_connection_errors() -> Any:
    """Context manager to catch MCP connection exceptions and throw a meaningful error message"""
    try:
        yield
    except ExceptionGroup as e:
        # in case the error is just about connect, we raise a meaningful error instead
        for sub_exception in e.exceptions:
            if isinstance(sub_exception, ConnectError) and "All connection attempts failed" in str(
                sub_exception
            ):
                raise ConnectionError(
                    "Could not connect to the remote MCP server. Make sure it is running and reachable."
                ) from sub_exception
        raise e


async def _invoke_mcp_tool_call_async(
    client_transport: ClientTransport,
    tool_name: str,
    tool_args: Dict[str, Any],
) -> str:
    with _catch_and_raise_mcp_connection_errors():
        async with client_transport._connect_session() as session:
            result: types.CallToolResult = await session.call_tool(tool_name, tool_args)

            if len(result.content) == 0:
                raise ValueError(f"No content was returned")

            text_content = ""
            for content in result.content:
                if content.type == "text":
                    text_content += content.text
                else:
                    raise ValueError(f"Only `text` content type is supported, was {content.type}")
            return text_content


async def _get_server_signatures_from_mcp_server(
    client_transport: ClientTransport,
) -> types.ListToolsResult:
    with _catch_and_raise_mcp_connection_errors():
        async with client_transport._connect_session() as session:
            return await session.list_tools()


async def get_server_tools_from_mcp_server(
    client_transport: ClientTransport,
    expected_signatures_by_name: Dict[str, Optional[Tool]],
) -> List[ServerTool]:
    from wayflowcore.mcp.tools import MCPTool

    processed_tool_signatures: List[ServerTool] = []
    remote_mcp_signature = await _get_server_signatures_from_mcp_server(
        client_transport=client_transport
    )

    if missing_tool_name := next(
        (
            expected_tool_name
            for expected_tool_name in expected_signatures_by_name or {}
            if expected_tool_name
            not in (
                exposed_tool_names := {
                    exposed_tool.name for exposed_tool in remote_mcp_signature.tools
                }
            )
        ),
        None,
    ):
        raise NoSuchToolFoundOnMCPServerError(
            f"Expected tool '{missing_tool_name}' but tool was missing from the list of exposed tools. "
            f"Exposed tools: {exposed_tool_names}"
        )

    for exposed_tool in remote_mcp_signature.tools:
        exposed_tool_name = exposed_tool.name
        if (
            len(expected_signatures_by_name) != 0
            and exposed_tool_name not in expected_signatures_by_name
        ):
            # Specified tools are passed and this `exposed_tool` was not expected, thus is skipped.
            continue

        remote_input_descriptors = [
            Property.from_json_schema(json_property, name=input_name)
            for input_name, json_property in exposed_tool.inputSchema["properties"].items()
        ]
        remote_description = exposed_tool.description or ""

        if (
            expected_signatures_by_name
            and expected_signatures_by_name[exposed_tool_name] is not None
        ):
            expected_tool_signature: Tool = expected_signatures_by_name[exposed_tool_name]  # type: ignore

            # use the local input_descriptors and description as overrides of the remote MCP tool
            input_descriptors = expected_tool_signature.input_descriptors
            if input_descriptors != remote_input_descriptors:
                logger.warning(
                    "The input descriptors exposed by the remote MCP server do not match the locally defined input descriptors for tool `%s`:/nLocal input descriptors: %s\nRemote input descriptors: %s",
                    expected_tool_signature.name,
                    expected_tool_signature,
                    remote_input_descriptors,
                )
            description = expected_tool_signature.description
        else:
            # we use the ones exposed by the MCP server
            input_descriptors = remote_input_descriptors
            description = remote_description

        processed_tool_signatures.append(
            MCPTool(
                name=exposed_tool.name,
                description=description,
                input_descriptors=input_descriptors,
                client_transport=client_transport,
                _validate_tool_exist_on_server=False,
            )
        )
    return processed_tool_signatures


async def _get_tool_on_server(name: str, client_transport: ClientTransport) -> Tool:

    try:
        tools = await get_server_tools_from_mcp_server(client_transport, {name: None})
    except NoSuchToolFoundOnMCPServerError as e:
        tools = []
    except Exception as e:
        raise ConnectionError(f"Cannot connect to the MCP server {client_transport}") from e

    if tools is None or len(tools) != 1:
        raise ValueError(f"Cannot find a tool named {name} on the MCP server: {tools}")
    tool = tools[0]
    if not isinstance(tool, Tool):
        raise ValueError("Could not retrieve tool")
    return tool
