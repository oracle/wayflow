# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import inspect
import json
import logging
from collections.abc import AsyncGenerator as cAsyncGenerator
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
    Protocol,
    Type,
    TypedDict,
    TypeVar,
    cast,
    get_args,
    get_origin,
)

import httpx
from exceptiongroup import ExceptionGroup
from httpx import ConnectError
from mcp import ClientSession
from mcp import types as types
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSessionT
from mcp.shared.context import LifespanContextT, RequestT

from wayflowcore.events.event import ToolExecutionStreamingChunkReceivedEvent
from wayflowcore.events.eventlistener import record_event
from wayflowcore.exceptions import NoSuchToolFoundOnMCPServerError
from wayflowcore.mcp._session_persistence import get_mcp_async_runtime
from wayflowcore.mcp.clienttransport import ClientTransport, ClientTransportWithAuth
from wayflowcore.property import (
    DictProperty,
    JsonSchemaParam,
    ListProperty,
    ObjectProperty,
    Property,
    UnionProperty,
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
            elif isinstance(sub_exception, httpx.HTTPStatusError) and "401 Unauthorized" in str(
                sub_exception
            ):
                request = sub_exception.request
                raise httpx.HTTPStatusError(
                    (
                        f"Could not connect to the remote MCP server with url '{request.url}' because of "
                        f"error '401 Unauthorized'. Full error: {str(sub_exception)}"
                    ),
                    request=request,
                    response=sub_exception.response,
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

        # 4. For single-output tools expecting a union/optional, unwrap `result`
        elif (
            len(output_descriptors) == 1
            and isinstance(output_descriptors[0], UnionProperty)
            and structured_output
            and "result" in structured_output
        ):
            return structured_output["result"]

        else:
            return None

    except KeyError:
        logger.debug(
            "Encountered error while parsing structured content in MCP tool result, will default to text content"
        )
        return None


class MCPProgressMessage(TypedDict):
    type: Literal["tool/stream"]
    content: Any


async def _mcp_progress_handler(progress: float, total: float | None, message: str | None) -> None:
    if not message:
        return

    current_span = get_current_span()
    # Progress callbacks can run in the MCP portal thread under a context that
    # does not include the active tool span/listeners. Fall back to the runtime's
    # last known caller context.
    if not (current_span and isinstance(current_span, ToolExecutionSpan)):
        # When running on the MCP async runtime portal thread, the tracing stack
        # can be decoupled from the tool execution stack in the caller thread.
        # AsyncRuntime.call() stores the caller's span stack in a contextvar so we
        # can still resolve the correct ToolExecutionSpan here.
        runtime = get_mcp_async_runtime()
        parent_span_task = runtime.get_parent_span_stack()
        tool_span = next(
            (span for span in reversed(parent_span_task) if isinstance(span, ToolExecutionSpan)),
            None,
        )
        if tool_span is None:
            logger.debug(
                "Skipping streaming chunk emission for MCP tool (no parent ToolExecutionSpan found)",
            )
            return
        current_span = tool_span

    if not isinstance(current_span, ToolExecutionSpan):
        logger.debug(
            "Skipping streaming chunk emission for MCP tool (no parent ToolExecutionSpan found)",
        )
        return

    message_dict: MCPProgressMessage = json.loads(message)
    message_type = message_dict["type"]
    content = message_dict["content"]
    if message_type == "tool/stream":
        record_event(
            ToolExecutionStreamingChunkReceivedEvent(
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

        # Handle unions/optionals (e.g., anyOf including null) first
        if "anyOf" in result_property:
            property_from_schema = Property.from_json_schema(
                result_property, name=output_schema_title
            )
            return [property_from_schema]

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
        print(
            f"CONVERTING OUTPUT SCHEMA for '{exposed_tool.title}', '{exposed_tool.name}': {exposed_tool.outputSchema}"
        )
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


def _extract_async_generator_inner_return_type(func: Callable[..., Any]) -> Any:
    """
    If func is annotated as AsyncGenerator[T, None], return T; else return Any.
    """
    annotations = getattr(func, "__annotations__", {}).get("return", Any)
    origin = get_origin(annotations) or annotations

    if origin in (cAsyncGenerator, AsyncGenerator):
        # typing.AsyncGenerator is an alias of collections.abc.AsyncGenerator
        # but they are not equal, so we need both.
        args = get_args(annotations)
        return args[0] if args else Any

    return Any


async def _stream_tool_output_chunk(
    ctx: Context[ServerSessionT, LifespanContextT, RequestT], progress: int, payload: Any
) -> None:
    message: MCPProgressMessage = {"type": "tool/stream", "content": payload}
    msg_str = json.dumps(message, default=str)
    await ctx.report_progress(progress, message=msg_str)


class ContextType(Protocol):
    """Protocol for MCP Context object to interface to MCP's RequestContext."""

    async def report_progress(
        self, progress: float, total: float | None = None, message: str | None = None
    ) -> None:
        """Report progress for the current operation."""
        ...


def mcp_streaming_tool(
    func: Callable[..., AsyncGenerator[ToolOutuptTypeT, None]],
    context_cls: Optional[Type[ContextType]] = None,
) -> Callable[..., Any]:
    """
    Decorate an MCP tool callable to enable streaming tool outputs.

    This decorator adapts a server-side async generator tool implementation so
    that intermediate yielded values are streamed to the client as tool output
    events, while the final yielded value is treated as the tool's final result.

    Parameters
    ----------
    func:
        An async callable that returns an async generator. Each ``yield`` emits
        a tool output chunk to be streamed. The generator should eventually
        complete, and the last yielded value is typically interpreted as the final
        tool result.
    context_cls:
        Context class used to access MCP request/response context.
        If ``None``, the decorator uses the ``Context`` type from the official
        MCP SDK. When using third-party MCP libraries, provide the appropriate
        context class so the decorator can correctly locate and use the context.


    Note
    ----

    .. important::

        The wrapper primes the async generator by pulling the first (and, if available, second) item up
        front to distinguish single-yield generators (treated as a final result with no streamed progress)
        from multi-yield generators (where earlier yields are streamed as progress and only the last yield
        is returned). As a result, a generator that errors after its first yield may appear to have emitted
        progress chunks server-side even if a client only consumes/observes the final result.

    Example
    -------

    >>> import anyio
    >>> from typing import AsyncGenerator
    >>> from mcp.server.fastmcp import FastMCP
    >>> from wayflowcore.mcp.mcphelpers import mcp_streaming_tool
    >>> server = FastMCP(
    ...     name="Example MCP Server",
    ...     instructions="A MCP Server.",
    ... )
    >>> @server.tool(description="Stream intermediate outputs, then yield the final result.")
    ... @mcp_streaming_tool
    ... async def my_streaming_tool(topic: str) -> AsyncGenerator[str, None]:
    ...     all_sentences = [f"{topic} part {i}" for i in range(2)]
    ...     for i in range(2):
    ...         await anyio.sleep(0.2)  # simulate work
    ...         yield all_sentences[i]
    ...     yield ". ".join(all_sentences)
    >>>
    >>> # server.run(transport="streamable-http")

    """
    if not inspect.isasyncgenfunction(func):
        raise TypeError("@mcp_streaming_tool can only be applied to async generator functions")

    context_cls_ = context_cls or Context

    callable_signature = inspect.signature(func)
    callable_parameters = list(callable_signature.parameters.values())
    func_return_type = _extract_async_generator_inner_return_type(func)

    # Decide whether to pass ctx into the underlying generator
    has_ctx_parameter = "ctx" in callable_signature.parameters
    has_kwargs_parameter = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in callable_parameters)

    @wraps(func)
    async def wrapped(
        ctx: Context[ServerSessionT, LifespanContextT, RequestT], *args: Any, **kwargs: Any
    ) -> Any:
        if has_ctx_parameter and "ctx" not in kwargs:
            kwargs["ctx"] = ctx
        elif (not has_ctx_parameter) and has_kwargs_parameter:
            # If user declared **kwargs, allow ctx to be consumed optionally.
            kwargs.setdefault("ctx", ctx)

        agenerator = func(*args, **kwargs)
        try:
            # Pull first item
            try:
                first = await agenerator.__anext__()
            except StopAsyncIteration:
                raise ValueError("Tool generator produced no items; expected at least one yield")

            # Try to pull second item to determine whether `first` is final.
            try:
                second = await agenerator.__anext__()
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
                    nxt = await agenerator.__anext__()
                except StopAsyncIteration:
                    # prev is the last element -> return as main result
                    return prev

                await _stream_tool_output_chunk(ctx, progress_idx, prev)
                prev = nxt
        finally:
            try:
                await agenerator.aclose()
            except Exception:
                logger.error("Encountered error while closing async generator '%s'", agenerator)

    if has_ctx_parameter:
        wrapped.__signature__ = callable_signature.replace(return_annotation=func_return_type)  # type: ignore
    else:
        new_params = [
            inspect.Parameter(
                "ctx",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=context_cls_,
            ),
            *callable_parameters,
        ]
        wrapped.__signature__ = callable_signature.replace(  # type: ignore
            parameters=new_params, return_annotation=func_return_type
        )

    # Fix annotations so tool frameworks see a normal return type.
    wrapped.__annotations__ = dict(getattr(func, "__annotations__", {}))
    wrapped.__annotations__["return"] = func_return_type
    if not has_ctx_parameter:
        wrapped.__annotations__.setdefault("ctx", context_cls_)

    return wrapped
