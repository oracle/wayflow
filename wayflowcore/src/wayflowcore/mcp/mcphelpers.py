# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import base64
import inspect
import json
import logging
from collections.abc import AsyncGenerator as cAsyncGenerator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from functools import wraps
from importlib import import_module
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeAlias,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
)

from exceptiongroup import ExceptionGroup
from mcp import ClientSession
from mcp import types as types
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSessionT
from mcp.shared.context import LifespanContextT, RequestT
from typing_extensions import NotRequired, TypedDict

from wayflowcore.events.event import ToolExecutionStreamingChunkReceivedEvent
from wayflowcore.events.eventlistener import record_event
from wayflowcore.exceptions import NoSuchToolFoundOnMCPServerError
from wayflowcore.mcp._session_persistence import (
    _raise_if_translatable_mcp_error,
    get_mcp_async_runtime,
)
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
from wayflowcore.tools.toolhelpers import _unwrap_artifact_output_annotation
from wayflowcore.tools.tools import (
    TOOL_OUTPUT_TYPE_METADATA_KEY,
    Tool,
    ToolOutputArtifact,
    ToolOutputType,
)
from wayflowcore.tracing.span import ToolExecutionSpan, get_current_span

logger = logging.getLogger(__name__)

# Whether the developer enables the use of MCP without authentication
_GLOBAL_ENABLED_MCP_WITHOUT_AUTH: ContextVar[bool] = ContextVar(
    "_GLOBAL_ENABLED_MCP_WITHOUT_AUTH", default=False
)

# Reserved structured-content key used to transport WayFlow artifacts over MCP
# without exposing them as model-visible tool content.
_MCP_TOOL_ARTIFACT_ENVELOPE_KEY = "__wayflowcore_tool_artifacts__"
_MCP_TOOL_ARTIFACT_CONTENT_KEY = "content"
_MCP_TOOL_ARTIFACT_ITEMS_KEY = "artifacts"
_MCP_TOOL_ARTIFACT_DATA_ENCODING_KEY = "data_encoding"
_MCP_TOOL_ARTIFACT_TEXT_ENCODING = "text"
_MCP_TOOL_ARTIFACT_BASE64_ENCODING = "base64"
_MCP_DEFAULT_TEXT_ARTIFACT_MIME_TYPE = "text/plain"
_MCP_DEFAULT_BINARY_ARTIFACT_MIME_TYPE = "application/octet-stream"


MCPToolOutputT = TypeVar("MCPToolOutputT")


class MCPToolOutputArtifactT(TypedDict):
    """Developer-facing MCP artifact dictionary."""

    data: str | bytes
    mime_type: NotRequired[str]
    name: NotRequired[str]


MCPToolOutputArtifactTypeT: TypeAlias = Union[
    str,
    bytes,
    MCPToolOutputArtifactT,
    Tuple[MCPToolOutputArtifactT, ...],
]
"""Accepted artifact payload shapes for WayFlow's MCP streaming helper."""

ReturnArtifact: TypeAlias = Tuple[MCPToolOutputT, MCPToolOutputArtifactTypeT]
"""Convenience alias for MCP server-tool return annotations."""


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
        _raise_if_translatable_mcp_error(e)
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


def _serialize_normalized_tool_output_artifacts_for_mcp(
    artifacts: tuple[ToolOutputArtifact, ...],
) -> list[dict[str, Any]]:
    serialized_artifacts: list[dict[str, Any]] = []
    for artifact in artifacts:
        artifact_data: str
        data_encoding = _MCP_TOOL_ARTIFACT_TEXT_ENCODING
        if isinstance(artifact.data, bytes):
            artifact_data = base64.b64encode(artifact.data).decode("ascii")
            data_encoding = _MCP_TOOL_ARTIFACT_BASE64_ENCODING
        else:
            artifact_data = artifact.data

        serialized_artifacts.append(
            {
                "name": artifact.name,
                "mime_type": artifact.mime_type,
                "data": artifact_data,
                _MCP_TOOL_ARTIFACT_DATA_ENCODING_KEY: data_encoding,
            }
        )

    return serialized_artifacts


def _convert_to_mcp_content_blocks(result: Any) -> list[types.ContentBlock]:
    if result is None:
        return []

    if isinstance(
        result,
        (
            types.TextContent,
            types.ImageContent,
            types.AudioContent,
            types.ResourceLink,
            types.EmbeddedResource,
        ),
    ):
        return [result]

    if isinstance(result, (list, tuple)):
        content_blocks: list[types.ContentBlock] = []
        for item in result:
            content_blocks.extend(_convert_to_mcp_content_blocks(item))
        return content_blocks

    if not isinstance(result, str):
        result = json.dumps(result, default=str, indent=2)

    return [types.TextContent(type="text", text=result)]


def _normalize_mcp_tool_output_artifact(
    artifact: str | bytes | MCPToolOutputArtifactT,
    *,
    require_name: bool,
) -> ToolOutputArtifact:
    if isinstance(artifact, str):
        if require_name:
            raise TypeError(
                "MCP artifact tuples only accept named artifact dictionaries for each artifact item."
            )
        return ToolOutputArtifact(
            mime_type=_MCP_DEFAULT_TEXT_ARTIFACT_MIME_TYPE,
            data=artifact,
        )

    if isinstance(artifact, bytes):
        if require_name:
            raise TypeError(
                "MCP artifact tuples only accept named artifact dictionaries for each artifact item."
            )
        return ToolOutputArtifact(
            mime_type=_MCP_DEFAULT_BINARY_ARTIFACT_MIME_TYPE,
            data=artifact,
        )

    if not isinstance(artifact, dict) or "data" not in artifact:
        raise TypeError(
            "MCP artifacts should be returned as `str | bytes | MCPToolOutputArtifactT | "
            "tuple[MCPToolOutputArtifactT, ...]`."
        )

    name = artifact.get("name")
    if require_name and not name:
        raise ValueError(
            "Each MCP artifact dictionary inside a tuple should define a non-empty `name`."
        )
    if name is not None and (not isinstance(name, str) or not name):
        raise TypeError("MCP artifact dictionary field `name` should be a non-empty string")

    data = artifact["data"]
    if not isinstance(data, (str, bytes)):
        raise TypeError("MCP artifact dictionary field `data` should be `str | bytes`")

    mime_type = artifact.get(
        "mime_type",
        (
            _MCP_DEFAULT_TEXT_ARTIFACT_MIME_TYPE
            if isinstance(data, str)
            else _MCP_DEFAULT_BINARY_ARTIFACT_MIME_TYPE
        ),
    )
    if not isinstance(mime_type, str) or not mime_type:
        raise TypeError("MCP artifact dictionary field `mime_type` should be a non-empty string")

    return ToolOutputArtifact(name=name, mime_type=mime_type, data=data)


def _normalize_mcp_tool_output_artifacts(
    artifacts: MCPToolOutputArtifactTypeT,
) -> tuple[ToolOutputArtifact, ...]:
    if isinstance(artifacts, tuple):
        return tuple(
            _normalize_mcp_tool_output_artifact(artifact, require_name=True)
            for artifact in artifacts
        )

    return (_normalize_mcp_tool_output_artifact(artifacts, require_name=False),)


def _deserialize_tool_output_artifacts_from_mcp(
    artifact_payloads: Any,
) -> tuple[ToolOutputArtifact, ...]:
    if not isinstance(artifact_payloads, list):
        raise TypeError("MCP artifact payload should be a list")

    deserialized_artifacts: list[ToolOutputArtifact] = []
    for artifact_payload in artifact_payloads:
        if not isinstance(artifact_payload, dict):
            raise TypeError("Each MCP artifact payload should be a dictionary")

        name = artifact_payload.get("name")
        mime_type = artifact_payload.get("mime_type")
        data = artifact_payload.get("data")
        data_encoding = artifact_payload.get(
            _MCP_TOOL_ARTIFACT_DATA_ENCODING_KEY, _MCP_TOOL_ARTIFACT_TEXT_ENCODING
        )

        if data_encoding == _MCP_TOOL_ARTIFACT_BASE64_ENCODING:
            if not isinstance(data, str):
                raise TypeError("Base64-encoded MCP artifact payloads should be strings")
            artifact_data: str | bytes = base64.b64decode(data)
        elif data_encoding == _MCP_TOOL_ARTIFACT_TEXT_ENCODING:
            if not isinstance(data, str):
                raise TypeError("Text MCP artifact payloads should be strings")
            artifact_data = data
        else:
            raise ValueError(f"Unsupported MCP artifact payload encoding '{data_encoding}'")

        mime_type = artifact_payload.get(
            "mime_type",
            (
                _MCP_DEFAULT_TEXT_ARTIFACT_MIME_TYPE
                if isinstance(artifact_data, str)
                else _MCP_DEFAULT_BINARY_ARTIFACT_MIME_TYPE
            ),
        )
        if not isinstance(mime_type, str) or not mime_type:
            raise TypeError("MCP artifact payload field `mime_type` should be a non-empty string")

        deserialized_artifacts.append(
            ToolOutputArtifact(name=name, mime_type=mime_type, data=artifact_data)
        )

    return tuple(deserialized_artifacts)


def _extract_mcp_tool_output_and_artifacts(
    tool_output: Any,
    *,
    tool_name: str,
    warn_on_missing_artifacts_tuple: bool,
) -> tuple[Any, tuple[ToolOutputArtifact, ...]]:
    if not isinstance(tool_output, tuple) or len(tool_output) != 2:
        if warn_on_missing_artifacts_tuple:
            logger.warning(
                "Streaming MCP tool '%s' is configured with output_type='%s' but returned %s "
                "instead of a (content, artifacts) tuple. Artifacts were dropped.",
                tool_name,
                ToolOutputType.CONTENT_AND_ARTIFACT.value,
                type(tool_output).__name__,
            )
        return tool_output, ()

    content, artifacts = tool_output
    try:
        normalized_artifacts = _normalize_mcp_tool_output_artifacts(artifacts)
    except Exception as exc:
        logger.warning(
            "Streaming MCP tool '%s' returned invalid artifacts (%s). Artifacts were dropped.",
            tool_name,
            exc,
        )
        return content, ()

    return content, normalized_artifacts


def _build_mcp_tool_artifact_result(
    content: Any,
    artifacts: tuple[ToolOutputArtifact, ...],
    context_cls: type[Any],
) -> Any:
    structured_content: dict[str, Any]
    if isinstance(content, dict):
        structured_content = dict(content)
    else:
        structured_content = {"result": content}

    structured_content[_MCP_TOOL_ARTIFACT_ENVELOPE_KEY] = {
        _MCP_TOOL_ARTIFACT_CONTENT_KEY: content,
        _MCP_TOOL_ARTIFACT_ITEMS_KEY: _serialize_normalized_tool_output_artifacts_for_mcp(
            artifacts
        ),
    }

    if _is_third_party_fastmcp_context_cls(context_cls):
        tool_result_cls = getattr(import_module("fastmcp.tools.tool"), "ToolResult")
        return tool_result_cls(
            content=content,
            structured_content=structured_content,
        )

    return types.CallToolResult(
        content=_convert_to_mcp_content_blocks(content),
        structuredContent=structured_content,
    )


def _build_mcp_tool_artifact_result_or_fallback(
    final_output: Any,
    tool_name: str,
    context_cls: type[Any],
) -> Any:
    content, artifacts = _extract_mcp_tool_output_and_artifacts(
        final_output,
        tool_name=tool_name,
        warn_on_missing_artifacts_tuple=True,
    )
    if not isinstance(final_output, tuple) or len(final_output) != 2:
        return content
    return _build_mcp_tool_artifact_result(content, artifacts, context_cls)


def _unwrap_nested_mcp_structured_content_payload(structured_output: Any) -> Any:
    if (
        isinstance(structured_output, dict)
        and "structuredContent" in structured_output
        and "content" in structured_output
        and "isError" in structured_output
    ):
        return structured_output["structuredContent"]
    return structured_output


def _try_extract_artifact_output_from_mcp_result(
    result: types.CallToolResult,
    tool_name: str,
    output_type: ToolOutputType,
) -> Optional[Any]:
    structured_output = _unwrap_nested_mcp_structured_content_payload(result.structuredContent)
    if not isinstance(structured_output, dict):
        return None

    envelope = structured_output.get(_MCP_TOOL_ARTIFACT_ENVELOPE_KEY)
    if envelope is None and isinstance(structured_output.get("result"), dict):
        envelope = structured_output["result"].get(_MCP_TOOL_ARTIFACT_ENVELOPE_KEY)
    if envelope is None:
        return None

    if not isinstance(envelope, dict):
        logger.warning(
            "Encountered malformed MCP artifact envelope for tool '%s'. Artifacts were dropped.",
            tool_name,
        )
        fallback_output = _extract_text_content_from_tool_result(result)
        return (
            (fallback_output, ())
            if output_type == ToolOutputType.CONTENT_AND_ARTIFACT
            else fallback_output
        )

    content = envelope.get(_MCP_TOOL_ARTIFACT_CONTENT_KEY)
    artifact_payloads = envelope.get(_MCP_TOOL_ARTIFACT_ITEMS_KEY, [])
    try:
        artifacts = _deserialize_tool_output_artifacts_from_mcp(artifact_payloads)
    except Exception as exc:
        logger.warning(
            "Failed to decode MCP tool artifacts for tool '%s' (%s). Artifacts were dropped.",
            tool_name,
            exc,
        )
        return (content, ()) if output_type == ToolOutputType.CONTENT_AND_ARTIFACT else content

    if output_type == ToolOutputType.CONTENT_AND_ARTIFACT:
        return content, artifacts

    if len(artifacts) != 0:
        logger.warning(
            "MCP tool '%s' returned artifacts but is configured with output_type='%s'. "
            "Artifacts were dropped.",
            tool_name,
            output_type.value,
        )
    return content


def _try_handle_structured_content_from_tool_result(
    result: types.CallToolResult, output_descriptors: List[Property]
) -> Optional[Any]:
    structured_output = _unwrap_nested_mcp_structured_content_payload(result.structuredContent)
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
    artifacts: NotRequired[list[dict[str, Any]]]


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
        chunk_artifacts: tuple[ToolOutputArtifact, ...] = ()
        artifact_payloads = message_dict.get("artifacts", [])
        if artifact_payloads:
            try:
                chunk_artifacts = _deserialize_tool_output_artifacts_from_mcp(artifact_payloads)
            except Exception as exc:
                logger.warning(
                    "Failed to decode streamed MCP tool artifacts (%s). Artifacts were dropped.",
                    exc,
                )
        if (
            len(chunk_artifacts) != 0
            and current_span.tool.output_type != ToolOutputType.CONTENT_AND_ARTIFACT
        ):
            logger.warning(
                "MCP tool '%s' streamed artifacts but is configured with output_type='%s'. "
                "Artifacts were dropped.",
                current_span.tool.name,
                current_span.tool.output_type.value,
            )
            chunk_artifacts = ()
        record_event(
            ToolExecutionStreamingChunkReceivedEvent(
                tool=current_span.tool,
                tool_request=current_span.tool_request,
                content=content,
                artifacts=chunk_artifacts,
            )
        )
    else:
        logger.warning("MCP progress type %s is not supported", message_type)


async def _invoke_mcp_tool_call_async(
    session: ClientSession,
    tool_name: str,
    tool_args: Dict[str, Any],
    output_descriptors: List[Property],
    output_type: ToolOutputType,
) -> Any:
    with _catch_and_raise_mcp_connection_errors():
        result: types.CallToolResult = await session.call_tool(
            tool_name, tool_args, progress_callback=_mcp_progress_handler
        )

        artifact_output = _try_extract_artifact_output_from_mcp_result(
            result=result,
            tool_name=tool_name,
            output_type=output_type,
        )
        if artifact_output is not None:
            return artifact_output

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
    use_remote_output_type: bool = False,
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
        remote_output_type = ToolOutputType.CONTENT_ONLY
        if exposed_tool.meta and TOOL_OUTPUT_TYPE_METADATA_KEY in exposed_tool.meta:
            try:
                remote_output_type = ToolOutputType(
                    exposed_tool.meta[TOOL_OUTPUT_TYPE_METADATA_KEY]
                )
            except ValueError:
                logger.warning(
                    "Remote MCP tool '%s' exposed an invalid output_type metadata value '%s'. "
                    "Falling back to '%s'.",
                    exposed_tool_name,
                    exposed_tool.meta[TOOL_OUTPUT_TYPE_METADATA_KEY],
                    ToolOutputType.CONTENT_ONLY.value,
                )

        output_descriptors: Optional[List[Property]]
        resolved_output_type = (
            remote_output_type if use_remote_output_type else ToolOutputType.CONTENT_ONLY
        )
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
            resolved_output_type = expected_tool_signature.output_type
            if expected_tool_signature.output_type != remote_output_type:
                logger.warning(
                    "The output type exposed by the remote MCP server does not match the locally defined output type for tool `%s`: local output_type=%s, remote output_type=%s",
                    expected_tool_signature.name,
                    expected_tool_signature.output_type.value,
                    remote_output_type.value,
                )
        else:
            # we use the ones exposed by the MCP server
            input_descriptors = remote_input_descriptors
            output_descriptors = remote_output_descriptors
            description = remote_description
            requires_confirmation = False
            if remote_output_type != ToolOutputType.CONTENT_ONLY and not use_remote_output_type:
                logger.warning(
                    "Remote MCP tool '%s' exposed output_type='%s', but WayFlow defaults to "
                    "'%s' unless the local MCPTool or tool signature explicitly sets "
                    "`output_type`.",
                    exposed_tool_name,
                    remote_output_type.value,
                    ToolOutputType.CONTENT_ONLY.value,
                )

        processed_tool_signatures.append(
            MCPTool(
                name=exposed_tool.name,
                description=description,
                input_descriptors=input_descriptors,
                output_descriptors=output_descriptors,
                client_transport=client_transport,
                _validate_tool_exist_on_server=False,
                requires_confirmation=requires_confirmation,
                output_type=resolved_output_type,
            )
        )
    return processed_tool_signatures


async def _get_tool_on_server(
    session: ClientSession, name: str, client_transport: ClientTransport
) -> Tool:
    try:
        tools = await get_server_tools_from_mcp_server(
            session,
            {name: None},
            client_transport,
            use_remote_output_type=True,
        )
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


def _extract_async_generator_inner_return_type(
    func: Callable[..., Any],
    output_type: ToolOutputType = ToolOutputType.CONTENT_ONLY,
) -> Any:
    """
    If func is annotated as AsyncGenerator[T, None], return T; else return Any.
    """
    annotations = getattr(func, "__annotations__", {}).get("return", Any)
    origin = get_origin(annotations) or annotations

    if origin in (cAsyncGenerator, AsyncGenerator):
        # typing.AsyncGenerator is an alias of collections.abc.AsyncGenerator
        # but they are not equal, so we need both.
        args = get_args(annotations)
        if not args:
            return Any
        return _unwrap_artifact_output_annotation(
            args[0],
            output_type=output_type,
            tool_name=getattr(func, "__name__", "<anonymous>"),
        )

    return Any


def _is_third_party_fastmcp_context_cls(context_cls: type[Any]) -> bool:
    return getattr(context_cls, "__module__", "").startswith("fastmcp.")


def _attach_output_type_metadata_to_fastmcp_callable(
    func: Callable[..., Any],
    output_type: ToolOutputType,
    context_cls: type[Any],
) -> None:
    if output_type == ToolOutputType.CONTENT_ONLY or not _is_third_party_fastmcp_context_cls(
        context_cls
    ):
        return

    get_fastmcp_meta = getattr(import_module("fastmcp.decorators"), "get_fastmcp_meta")
    tool_meta_cls = getattr(import_module("fastmcp.tools.function_tool"), "ToolMeta")

    existing_metadata = get_fastmcp_meta(func)
    merged_meta = (
        dict(existing_metadata.meta)
        if isinstance(existing_metadata, tool_meta_cls) and existing_metadata.meta
        else {}
    )
    merged_meta[TOOL_OUTPUT_TYPE_METADATA_KEY] = output_type.value

    metadata = (
        replace(existing_metadata, meta=merged_meta)
        if isinstance(existing_metadata, tool_meta_cls)
        else tool_meta_cls(meta=merged_meta)
    )

    target = func.__func__ if hasattr(func, "__func__") else func
    target.__fastmcp__ = metadata


async def _stream_tool_output_chunk(
    ctx: Context[ServerSessionT, LifespanContextT, RequestT],
    progress: int,
    payload: Any,
    artifacts: tuple[ToolOutputArtifact, ...] = (),
) -> None:
    message: MCPProgressMessage = {"type": "tool/stream", "content": payload}
    if len(artifacts) != 0:
        message["artifacts"] = _serialize_normalized_tool_output_artifacts_for_mcp(artifacts)
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
    func: Optional[Callable[..., AsyncGenerator[ToolOutuptTypeT, None]]] = None,
    *,
    context_cls: Optional[Type[ContextType]] = None,
    output_type: ToolOutputType = ToolOutputType.CONTENT_ONLY,
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
    output_type:
        Controls the yielded value artifact contract.

        * With ``ToolOutputType.CONTENT_ONLY``, the final yielded value is returned as the
          MCP tool result.
        * With ``ToolOutputType.CONTENT_AND_ARTIFACT``, each yielded value may be either
          ``content`` or ``(content, artifacts)``.

          * A single artifact may be returned as ``str``, ``bytes``, or a dictionary with
            ``data`` and optional ``mime_type`` / ``name``.
          * Several artifacts should be returned as a tuple of named dictionaries.

        Earlier yielded artifacts are exposed on
        ``ToolExecutionStreamingChunkReceivedEvent.artifacts``.
        Only artifacts returned by the final yielded value are attached to the final
        ``ToolExecutionResultEvent`` and ``ToolResult``.

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
    >>> from wayflowcore.mcp.mcphelpers import ReturnArtifact, mcp_streaming_tool
    >>> server = FastMCP(
    ...     name="Example MCP Server",
    ...     instructions="A MCP Server.",
    ... )
    >>> @server.tool(description="Stream intermediate outputs, then yield the final result.")
    ... @mcp_streaming_tool
    ... async def my_streaming_tool(topic: str) -> AsyncGenerator[ReturnArtifact[str], None]:
    ...     all_sentences = [f"{topic} part {i}" for i in range(2)]
    ...     for i in range(2):
    ...         await anyio.sleep(0.2)  # simulate work
    ...         yield all_sentences[i], {"name": f"{i}.txt", "data": all_sentences[i]}
    ...     yield ". ".join(all_sentences), {"name": "full.txt", "data": ". ".join(all_sentences)}
    >>>
    >>> # server.run(transport="streamable-http")

    """

    def _decorate(
        target_func: Callable[..., AsyncGenerator[ToolOutuptTypeT, None]],
    ) -> Callable[..., Any]:
        if not inspect.isasyncgenfunction(target_func):
            raise TypeError("@mcp_streaming_tool can only be applied to async generator functions")

        context_cls_ = context_cls or Context
        tool_name = getattr(target_func, "__name__", "<anonymous>")

        callable_signature = inspect.signature(target_func)
        callable_parameters = list(callable_signature.parameters.values())
        func_return_type = _extract_async_generator_inner_return_type(
            target_func,
            output_type=output_type,
        )

        # Decide whether to pass ctx into the underlying generator
        has_ctx_parameter = "ctx" in callable_signature.parameters
        has_kwargs_parameter = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in callable_parameters
        )

        @wraps(target_func)
        async def wrapped(
            ctx: Context[ServerSessionT, LifespanContextT, RequestT], *args: Any, **kwargs: Any
        ) -> Any:
            if has_ctx_parameter and "ctx" not in kwargs:
                kwargs["ctx"] = ctx
            elif (not has_ctx_parameter) and has_kwargs_parameter:
                # If user declared **kwargs, allow ctx to be consumed optionally.
                kwargs.setdefault("ctx", ctx)

            agenerator = target_func(*args, **kwargs)
            try:
                # Pull first item
                try:
                    first = await agenerator.__anext__()
                except StopAsyncIteration:
                    raise ValueError(
                        "Tool generator produced no items; expected at least one yield"
                    )

                # Try to pull second item to determine whether `first` is final.
                try:
                    second = await agenerator.__anext__()
                except StopAsyncIteration:
                    # Single-yield generator: treat that item as the final result (no progress)
                    if output_type == ToolOutputType.CONTENT_AND_ARTIFACT:
                        return _build_mcp_tool_artifact_result_or_fallback(
                            first,
                            tool_name,
                            context_cls_,
                        )
                    return first

                progress_idx = 0
                # We now know there is more than one item, so report `first` as progress.
                if output_type == ToolOutputType.CONTENT_AND_ARTIFACT:
                    first_content, first_artifacts = _extract_mcp_tool_output_and_artifacts(
                        first,
                        tool_name=tool_name,
                        warn_on_missing_artifacts_tuple=False,
                    )
                    await _stream_tool_output_chunk(
                        ctx,
                        progress_idx,
                        first_content,
                        first_artifacts,
                    )
                else:
                    await _stream_tool_output_chunk(ctx, progress_idx, first)
                prev = second
                while True:
                    progress_idx += 1
                    try:
                        nxt = await agenerator.__anext__()
                    except StopAsyncIteration:
                        # prev is the last element -> return as main result
                        if output_type == ToolOutputType.CONTENT_AND_ARTIFACT:
                            return _build_mcp_tool_artifact_result_or_fallback(
                                prev,
                                tool_name,
                                context_cls_,
                            )
                        return prev

                    if output_type == ToolOutputType.CONTENT_AND_ARTIFACT:
                        prev_content, prev_artifacts = _extract_mcp_tool_output_and_artifacts(
                            prev,
                            tool_name=tool_name,
                            warn_on_missing_artifacts_tuple=False,
                        )
                        await _stream_tool_output_chunk(
                            ctx,
                            progress_idx,
                            prev_content,
                            prev_artifacts,
                        )
                    else:
                        await _stream_tool_output_chunk(ctx, progress_idx, prev)
                    prev = nxt
            finally:
                try:
                    await agenerator.aclose()
                except Exception:
                    logger.error("Encountered error while closing async generator '%s'", agenerator)

        if has_ctx_parameter:
            wrapped.__signature__ = callable_signature.replace(  # type: ignore[attr-defined]
                return_annotation=func_return_type
            )
        else:
            new_params = [
                inspect.Parameter(
                    "ctx",
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=context_cls_,
                ),
                *callable_parameters,
            ]
            wrapped.__signature__ = callable_signature.replace(  # type: ignore[attr-defined]
                parameters=new_params, return_annotation=func_return_type
            )

        # Fix annotations so tool frameworks see a normal return type.
        wrapped.__annotations__ = dict(getattr(target_func, "__annotations__", {}))
        wrapped.__annotations__["return"] = func_return_type
        if not has_ctx_parameter:
            wrapped.__annotations__.setdefault("ctx", context_cls_)

        _attach_output_type_metadata_to_fastmcp_callable(wrapped, output_type, context_cls_)
        return wrapped

    if func is None:
        return _decorate
    return _decorate(func)
