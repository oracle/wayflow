# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, cast

from exceptiongroup import ExceptionGroup
from httpx import ConnectError
from mcp import ClientSession
from mcp import types as types

from wayflowcore.exceptions import NoSuchToolFoundOnMCPServerError
from wayflowcore.mcp.clienttransport import ClientTransport, ClientTransportWithAuth
from wayflowcore.property import (
    DictProperty,
    JsonSchemaParam,
    ListProperty,
    ObjectProperty,
    Property,
)
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


def _extract_text_content_from_tool_result(result: types.CallToolResult) -> str:
    if len(result.content) == 0:
        raise ValueError(f"No content was returned")

    text_content = ""
    for content in result.content:
        if content.type == "text":
            text_content += content.text
        elif content.type == "resource" and isinstance(
            content.resource, types.TextResourceContents
        ):
            resource = content.resource
            content_as_json = {
                "uri": str(resource.uri),
                "mimeType": resource.mimeType,
                "text": resource.text,
            }
            text_content += json.dumps(content_as_json)
        else:
            raise ValueError(
                f"Only `text` and text `resource` content type is supported, was {content.type}"
            )
    return text_content


def _try_handle_structured_content_from_tool_result(
    result: types.CallToolResult, output_descriptors: List[Property]
) -> Optional[Any]:
    structured_output = result.structuredContent
    if structured_output is None:
        return None

    try:
        # 1. If there are several expected outputs, we return the wrapped structuredContent
        if len(output_descriptors) > 1 and len(structured_output["result"]) == len(
            output_descriptors
        ):
            # MCP only supports objects so tuples are wrapped into a "result" field
            wrapped_outputs = structured_output["result"]
            return {
                property_.name: value
                for property_, value in zip(output_descriptors, wrapped_outputs)
            }  # required for multi-output tools

        # 2. If the tool output is expected to be a dict, we return the structuredContent
        elif (
            len(output_descriptors) == 1
            and isinstance(output_descriptors[0], (DictProperty, ObjectProperty))
            and structured_output
        ):
            return structured_output

        # 3. If the tool output is expected to be a list, we return the wrapped structuredContent
        elif (
            len(output_descriptors) == 1
            and isinstance(output_descriptors[0], ListProperty)
            and structured_output
        ):
            # MCP only supports objects so lists are wrapped into a "result" field
            return structured_output["result"]

        else:
            return None

    except KeyError:
        logger.debug(
            "Encountered error while parsing structured content in MCP tool result, will default to text content"
        )
        return None


async def _invoke_mcp_tool_call_async(
    session: ClientSession,
    tool_name: str,
    tool_args: Dict[str, Any],
    output_descriptors: List[Property],
) -> Any:
    with _catch_and_raise_mcp_connection_errors():
        result: types.CallToolResult = await session.call_tool(tool_name, tool_args)

        output = _try_handle_structured_content_from_tool_result(result, output_descriptors)
        if output is not None:
            return output

        return _extract_text_content_from_tool_result(result)


async def _get_server_signatures_from_mcp_server(session: ClientSession) -> types.ListToolsResult:
    with _catch_and_raise_mcp_connection_errors():
        return await session.list_tools()


def _try_convert_mcp_output_schema_to_properties(
    schema: Optional[Dict[str, Any]],
    tool_title: str,
) -> Optional[List[Property]]:
    """Best effort attempt to convert the output schema from a MCP Tool"""
    if schema is None:
        return None

    if "properties" not in schema:
        logger.debug("Missing `properties` from schema: %s", schema)
        return None

    output_schema_title = schema.get("title", tool_title)

    try:
        # Detect Dict Property
        if "additionalProperties" in schema:
            return [Property.from_json_schema(cast(JsonSchemaParam, schema))]

        if not "result" in schema["properties"]:
            logger.warning(
                "Output schema of MCP tool is not compliant with the MCP spec (missing "
                "'result' field in 'properties')"
            )
            return None

        result_property = schema["properties"]["result"]

        # Detect List Property
        if result_property["type"] == "array" and "items" in result_property:
            item_property = Property.from_json_schema(result_property["items"])
            return [ListProperty(name=output_schema_title, item_type=item_property)]

        # Detect Tuple Properties
        if result_property["type"] == "array" and "prefixItems" in result_property:
            return [Property.from_json_schema(p) for p in result_property["prefixItems"]]

        return None  # No compatible complex type was detected -> use default type
    except Exception as e:
        logger.error(
            "Failed to parse remote MCP output schema, will default to `None` "
            "MCP tool output descriptors. Tool title: %s, schema: %s",
            tool_title,
            schema,
            exc_info=True,
        )
        return None


async def get_server_tools_from_mcp_server(
    session: ClientSession,
    expected_signatures_by_name: Dict[str, Optional[Tool]],
    client_transport: ClientTransport,
) -> List[ServerTool]:
    from wayflowcore.mcp.tools import MCPTool

    processed_tool_signatures: List[ServerTool] = []
    remote_mcp_signature = await _get_server_signatures_from_mcp_server(session)

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
        remote_output_descriptors = _try_convert_mcp_output_schema_to_properties(
            exposed_tool.outputSchema,
            tool_title=(exposed_tool.title or exposed_tool.name) + "Output",
        )
        remote_description = exposed_tool.description or ""

        output_descriptors: Optional[List[Property]]
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

            output_descriptors = expected_tool_signature.output_descriptors
            if remote_output_descriptors is None and output_descriptors is not None:
                logger.warning(
                    "MCP Tool '%s' expects output descriptors %s but failed to parse remote output descriptors. Check the debug logs to see why the parsing failed.",
                    expected_tool_signature.name,
                    output_descriptors,
                )
            elif output_descriptors != remote_output_descriptors:
                logger.warning(
                    "The output descriptors exposed by the remote MCP server do not match the locally defined output descriptors for tool `%s`:/nLocal ouptut descriptors: %s\nRemote output descriptors: %s",
                    expected_tool_signature.name,
                    expected_tool_signature,
                    remote_output_descriptors,
                )
            description = expected_tool_signature.description
            requires_confirmation = expected_tool_signature.requires_confirmation
        else:
            # we use the ones exposed by the MCP server
            input_descriptors = remote_input_descriptors
            output_descriptors = remote_output_descriptors
            description = remote_description
            requires_confirmation = False

        processed_tool_signatures.append(
            MCPTool(
                name=exposed_tool.name,
                description=description,
                input_descriptors=input_descriptors,
                output_descriptors=output_descriptors,
                client_transport=client_transport,
                _validate_tool_exist_on_server=False,
                requires_confirmation=requires_confirmation,
            )
        )
    return processed_tool_signatures


async def _get_tool_on_server(
    session: ClientSession, name: str, client_transport: ClientTransport
) -> Tool:
    try:
        tools = await get_server_tools_from_mcp_server(session, {name: None}, client_transport)
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
