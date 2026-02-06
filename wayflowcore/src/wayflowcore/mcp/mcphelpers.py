# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import inspect
import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
    TypeVar,
    cast,
    get_args,
    get_origin,
)

from exceptiongroup import ExceptionGroup
from httpx import ConnectError
from mcp import ClientSession
from mcp import types as types
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSessionT
from mcp.shared.context import LifespanContextT, RequestT

from wayflowcore.events.event import ToolExecutionStreamingChunkReceived
from wayflowcore.events.eventlistener import record_event
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
from wayflowcore.tracing.span import ToolExecutionSpan, get_current_span

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


MCPProgressMessage = TypedDict(
    "MCPProgressMessage",
    {
        "type": Literal["tool/stream"],
        "content": Any,
    },
    total=False,
)


async def _mcp_progress_handler(progress: float, total: float | None, message: str | None) -> None:
    if not message:
        return

    current_span = get_current_span()
    if not (current_span and isinstance(current_span, ToolExecutionSpan)):
        logger.debug(
            "Skipping streaming chunk emission for MCP tool (no parent ToolExecutionSpan found)",
        )
        return

    message_dict: MCPProgressMessage = json.loads(message)
    message_type = message_dict["type"]
    content = message_dict["content"]
    if message_type == "tool/stream":
        record_event(
            ToolExecutionStreamingChunkReceived(
                tool=current_span.tool,
                tool_request=current_span.tool_request,
                content=content,
            )
        )
    else:
        logger.warning("MCP progress type %s is not supported", message_type)


async def _invoke_mcp_tool_call_async(
    session: ClientSession,
    tool_name: str,
    tool_args: Dict[str, Any],
    output_descriptors: List[Property],
) -> Any:
    with _catch_and_raise_mcp_connection_errors():
        result: types.CallToolResult = await session.call_tool(
            tool_name, tool_args, progress_callback=_mcp_progress_handler
        )

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


ToolOutuptTypeT = TypeVar("ToolOutuptTypeT")


def _extract_yield_type(func: Callable[..., Any]) -> Any:
    """
    If func is annotated as AsyncGenerator[T, None], return T; else return Any.
    """
    ann = getattr(func, "__annotations__", {}).get("return", Any)
    origin = get_origin(ann)
    if origin in (AsyncGenerator,):
        args = get_args(ann)
        if args:
            return args[0]
    return Any


async def _stream_tool_output_chunk(
    ctx: Context[ServerSessionT, LifespanContextT, RequestT], progress: int, payload: Any
) -> None:
    message: MCPProgressMessage = {"type": "tool/stream", "content": payload}
    msg_str = json.dumps(message, default=str)  # would need to improve type validation
    await ctx.report_progress(progress, message=msg_str)


def mcp_streaming_tool(
    func: Callable[..., AsyncGenerator[ToolOutuptTypeT, None]],
) -> Callable[..., Any]:
    """
    Decorator that adapts an async-generator tool into an MCP tool:
      - all yielded items except the last are sent via ctx.report_progress(...)
      - the last yielded item is returned as the tool result
    """
    if not inspect.isasyncgenfunction(func):
        raise TypeError("@tool_streaming_adapter can only be applied to async generator functions")

    sig = inspect.signature(func)
    params = list(sig.parameters.values())

    func_return_t = _extract_yield_type(func)

    # Decide whether to pass ctx into the underlying generator
    has_ctx_param = "ctx" in sig.parameters
    has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)

    @wraps(func)
    async def wrapped(
        ctx: Context[ServerSessionT, LifespanContextT, RequestT], *args: Any, **kwargs: Any
    ) -> Any:
        if has_ctx_param and "ctx" not in kwargs:
            kwargs["ctx"] = ctx
        elif (not has_ctx_param) and has_varkw:
            # If user declared **kwargs, allow ctx to be consumed optionally.
            kwargs.setdefault("ctx", ctx)

        agen = func(*args, **kwargs)

        try:
            # Pull first item
            try:
                first = await agen.__anext__()
            except StopAsyncIteration:
                raise ValueError("Tool generator produced no items; expected at least one yield")

            # Try to pull second item to determine whether `first` is final.
            try:
                second = await agen.__anext__()
            except StopAsyncIteration:
                # Single-yield generator: treat that item as the final result (no progress)
                return first

            progress_idx = 0
            # We now know there is more than one item, so report `first` as progress.
            await _stream_tool_output_chunk(ctx, progress_idx, first)

            prev = second
            while True:
                progress_idx += 1
                try:
                    nxt = await agen.__anext__()
                except StopAsyncIteration:
                    # prev is the last element -> return as main result
                    return prev

                await _stream_tool_output_chunk(ctx, progress_idx, prev)
                prev = nxt

        finally:
            try:
                await agen.aclose()
            except Exception:
                # Best-effort close; don't hide original exceptions.
                pass

    # --- Make wrapped function “look like” a normal MCP tool signature ---

    # If the original function already had ctx, keep signature; else add ctx first.
    if has_ctx_param:
        wrapped.__signature__ = sig  # type: ignore[attr-defined]
    else:
        new_params = [
            inspect.Parameter(
                "ctx",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Context,
            ),
            *params,
        ]
        wrapped.__signature__ = sig.replace(parameters=new_params, return_annotation=func_return_t)  # type: ignore[attr-defined]

    # Fix annotations so tool frameworks see a normal return type.
    wrapped.__annotations__ = dict(getattr(func, "__annotations__", {}))
    wrapped.__annotations__["return"] = func_return_t
    if not has_ctx_param:
        wrapped.__annotations__.setdefault("ctx", Context)

    return wrapped
