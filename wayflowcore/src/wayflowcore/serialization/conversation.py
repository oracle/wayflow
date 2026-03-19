# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

import json
import warnings
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, cast

import yaml

from wayflowcore.executors.executionstatus import (
    AuthChallengeRequestStatus,
    ExecutionStatus,
    FinishedStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import (
    autodeserialize_from_dict,
    serialize,
    serialize_any_to_dict_or_stringify,
)
from wayflowcore.tools.tools import ToolRequest, ToolResult

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.executors._agentconversation import AgentConversation
    from wayflowcore.executors._flowconversation import FlowConversation
    from wayflowcore.messagelist import Message, MessageContent
    from wayflowcore.serialization.plugins import (
        WayflowDeserializationPlugin,
        WayflowSerializationPlugin,
    )

_UNSET = object()


def _dump_conversation_reference(conversation: "Conversation") -> dict[str, Any]:
    return {
        "id": conversation.id,
        "conversation_id": conversation.conversation_id,
        "conversation_type": conversation.__class__.__name__,
    }


def _dump_component_reference(component: Any) -> dict[str, Any]:
    return {
        "component_id": component.id,
        "component_type": component.__class__.__name__,
    }


def _dump_json_compatible_value(value: Any) -> Any:
    from wayflowcore._utils.formatting import stringify
    from wayflowcore.component import Component
    from wayflowcore.conversation import Conversation

    dumped_value: Any
    if value is None or isinstance(value, (bool, int, float, str)):
        dumped_value = value
    elif isinstance(value, bytes):
        dumped_value = value.decode("utf-8", errors="replace")
    elif isinstance(value, datetime):
        dumped_value = value.isoformat()
    elif isinstance(value, Enum):
        dumped_value = _dump_json_compatible_value(value.value)
    elif isinstance(value, Conversation):
        dumped_value = _dump_conversation_reference(value)
    elif isinstance(value, Component):
        dumped_value = _dump_component_reference(value)
    elif isinstance(value, dict):
        dumped_value = {
            str(key): _dump_json_compatible_value(inner_value) for key, inner_value in value.items()
        }
    elif isinstance(value, (list, tuple, set)):
        dumped_value = [_dump_json_compatible_value(inner_value) for inner_value in value]
    else:
        serialized_value = serialize_any_to_dict_or_stringify(
            value, SerializationContext(root=value)
        )
        if serialized_value is value:
            dumped_value = stringify(value)
        else:
            dumped_value = _dump_json_compatible_value(serialized_value)
    return dumped_value


def _dump_string_keyed_mapping(values: dict[Any, Any]) -> dict[str, Any]:
    return {str(key): _dump_json_compatible_value(value) for key, value in values.items()}


def _dump_flow_input_output_key_values(values: dict[Any, Any]) -> dict[str, Any]:
    return {
        f"{step_name}.{value_name}": _dump_json_compatible_value(value)
        for (step_name, value_name), value in values.items()
    }


def _dump_tool_requests(
    tool_requests: Optional[list[ToolRequest]],
) -> list[Optional[dict[str, Any]]]:
    return [_dump_tool_request(tool_request) for tool_request in tool_requests or []]


def _dump_tool_request(tool_request: Optional[ToolRequest]) -> Optional[dict[str, Any]]:
    if tool_request is None:
        dumped_tool_request = None
    else:
        dumped_tool_request = {
            "name": tool_request.name,
            "tool_request_id": tool_request.tool_request_id,
            "args": _dump_json_compatible_value(tool_request.args),
            "requires_confirmation": tool_request._requires_confirmation,
            "tool_execution_confirmed": tool_request._tool_execution_confirmed,
            "tool_rejection_reason": tool_request._tool_rejection_reason,
        }
    return dumped_tool_request


def _dump_tool_result(tool_result: Optional[ToolResult]) -> Optional[dict[str, Any]]:
    if tool_result is None:
        dumped_tool_result = None
    else:
        dumped_tool_result = {
            "tool_request_id": tool_result.tool_request_id,
            "content": _dump_json_compatible_value(tool_result.content),
        }
    return dumped_tool_result


def _dump_tool_related_execution_status(
    execution_status: ToolRequestStatus | ToolExecutionConfirmationStatus,
) -> dict[str, Any]:
    dumped_status = {
        "tool_requests": _dump_tool_requests(execution_status.tool_requests),
    }
    if isinstance(execution_status, ToolRequestStatus):
        dumped_status["tool_results"] = [
            _dump_tool_result(tool_result) for tool_result in execution_status._tool_results or []
        ]
    return dumped_status


def _dump_message_content(content: MessageContent) -> dict[str, Any]:
    from wayflowcore.messagelist import ImageContent, TextContent

    content_type = getattr(content, "type", content.__class__.__name__)

    if isinstance(content, TextContent):
        dumped_content = {
            "type": content.type,
            "content": content.content,
        }
    elif isinstance(content, ImageContent):
        dumped_content = {
            "type": content.type,
            "base64_content": content.base64_content,
        }
    else:
        serialized_content = _dump_json_compatible_value(content)
        if isinstance(serialized_content, dict):
            if "type" in serialized_content:
                dumped_content = serialized_content
            else:
                dumped_content = {"type": content_type, **serialized_content}
        else:
            dumped_content = {
                "type": content_type,
                "content": serialized_content,
            }
    return dumped_content


def _dump_message(message: Message) -> dict[str, Any]:
    dumped_message: dict[str, Any] = {
        "role": message.role,
        "message_type": message.message_type.value if message.message_type else None,
        "sender": message.sender,
        "recipients": sorted(message.recipients),
        "time_created": message.time_created.isoformat(),
        "time_updated": message.time_updated.isoformat(),
        "content": message.content,
        "contents": [_dump_message_content(content) for content in message.contents],
    }

    tool_requests = _dump_tool_requests(message.tool_requests)
    dumped_tool_result = _dump_tool_result(message.tool_result)

    if tool_requests:
        dumped_message["tool_requests"] = tool_requests
    if dumped_tool_result is not None:
        dumped_message["tool_result"] = dumped_tool_result
    return dumped_message


def _dump_execution_status(execution_status: Optional[ExecutionStatus]) -> Optional[dict[str, Any]]:
    if execution_status is None:
        return None

    dumped_status: dict[str, Any] = {"type": execution_status.__class__.__name__}
    if isinstance(execution_status, FinishedStatus):
        dumped_status["output_values"] = _dump_json_compatible_value(execution_status.output_values)
        dumped_status["complete_step_name"] = execution_status.complete_step_name
    elif isinstance(execution_status, UserMessageRequestStatus):
        dumped_status["message"] = _dump_message(execution_status.message)
    elif isinstance(execution_status, (ToolRequestStatus, ToolExecutionConfirmationStatus)):
        dumped_status.update(_dump_tool_related_execution_status(execution_status))
    elif isinstance(execution_status, AuthChallengeRequestStatus):
        dumped_status["client_transport_id"] = execution_status.client_transport_id
    return dumped_status


def _dump_conversation_info(conversation: "Conversation") -> dict[str, Any]:
    return {
        **_dump_conversation_reference(conversation),
        "component_type": conversation.component.__class__.__name__,
        "name": conversation.name,
        "inputs": _dump_json_compatible_value(conversation.inputs),
        "messages": [_dump_message(message) for message in conversation.get_messages()],
    }


def _dump_common_execution_info(
    conversation: "Conversation",
    *,
    status: object = _UNSET,
    status_handled: object = _UNSET,
) -> dict[str, Any]:
    return {
        "current_step_name": conversation.current_step_name,
        "status": _dump_execution_status(
            conversation.status if status is _UNSET else cast(Optional[ExecutionStatus], status)
        ),
        "status_handled": (
            conversation.status_handled if status_handled is _UNSET else cast(bool, status_handled)
        ),
        "token_usage": _dump_json_compatible_value(conversation.token_usage),
    }


def _dump_flow_execution_info(conversation: "FlowConversation") -> dict[str, Any]:
    return {
        "step_history": list(conversation.state.step_history),
        "nesting_level": conversation.state.nesting_level,
        "input_output_key_values": _dump_flow_input_output_key_values(
            conversation.state.input_output_key_values
        ),
        "flow_output_values": _dump_json_compatible_value(
            conversation.state._flow_output_value_dict
        ),
        "context_key_values": _dump_json_compatible_value(conversation.state.context_key_values),
        "internal_context_key_values": _dump_string_keyed_mapping(
            conversation.state.internal_context_key_values
        ),
    }


def _dump_agent_execution_info(conversation: "AgentConversation") -> dict[str, Any]:
    return {
        "curr_iter": conversation.state.curr_iter,
        "has_confirmed_conversation_exit": conversation.state.has_confirmed_conversation_exit,
        "tool_call_queue": _dump_tool_requests(conversation.state.tool_call_queue),
        "current_tool_request": _dump_tool_request(conversation.state.current_tool_request),
        "current_flow_conversation": _dump_json_compatible_value(
            conversation.state.current_flow_conversation
        ),
        "current_sub_component_conversations": _dump_string_keyed_mapping(
            conversation.state.current_sub_component_conversations
        ),
    }


def _dump_component_execution_info(conversation: "Conversation") -> dict[str, Any]:
    from wayflowcore.executors._agentconversation import AgentConversation
    from wayflowcore.executors._flowconversation import FlowConversation

    if isinstance(conversation, FlowConversation):
        return _dump_flow_execution_info(conversation)
    if isinstance(conversation, AgentConversation):
        return _dump_agent_execution_info(conversation)
    return {}


def dump_conversation_state(
    conversation: "Conversation",
    *,
    status: object = _UNSET,
    status_handled: object = _UNSET,
) -> dict[str, Any]:
    """
    Return a JSON-serializable runtime snapshot of a conversation.

    The returned dictionary is intended for inspection, tracing, and state snapshot
    emission. It captures the user-visible conversation state and the runtime
    execution state without embedding live component objects. Optional ``status``
    and ``status_handled`` overrides are available so callers can snapshot a
    slightly adjusted view of the current runtime state without mutating the
    conversation itself.

    Parameters
    ----------
    conversation:
        Conversation instance to snapshot.
    status:
        Optional execution status override to include in the dumped state instead
        of ``conversation.status``.
    status_handled:
        Optional ``status_handled`` override to include in the dumped state
        instead of ``conversation.status_handled``.

    Returns
    -------
    dict[str, Any]
        JSON-compatible conversation snapshot containing ``conversation`` and
        ``execution`` sections.
    """
    return {
        "conversation": _dump_conversation_info(conversation),
        "execution": {
            **_dump_common_execution_info(
                conversation,
                status=status,
                status_handled=status_handled,
            ),
            **_dump_component_execution_info(conversation),
        },
    }


def serialize_conversation_state(
    conversation: "Conversation",
    serialization_context: Optional[SerializationContext] = None,
    plugins: Optional[list["WayflowSerializationPlugin"]] = None,
) -> str:
    """
    Serialize a conversation into its stable textual state representation.

    This is the string form meant for storage or transport when the full runtime
    conversation needs to be preserved for later loading. Unlike
    ``dump_conversation_state()``, this serializes the actual conversation object
    graph using WayFlow serialization.

    Parameters
    ----------
    conversation:
        Conversation instance to serialize.
    serialization_context:
        Optional serialization context to use.
    plugins:
        Optional serialization plugins to use.

    Returns
    -------
    str
        Serialized conversation state string.
    """
    return serialize(
        conversation,
        serialization_context=serialization_context,
        plugins=plugins,
    )


def deserialize_conversation_state(state: str) -> dict[str, Any]:
    """
    Parse a serialized conversation state string into a dictionary.

    This is the dictionary-level counterpart of
    ``serialize_conversation_state()``. It is useful when callers need to inspect
    or adjust the serialized payload before loading it back into a live
    ``Conversation`` object.

    Parameters
    ----------
    state:
        Serialized conversation state string.

    Returns
    -------
    dict[str, Any]
        Parsed serialized state.

    Raises
    ------
    TypeError
        If the serialized payload does not deserialize into a dictionary.
    """
    loaded_state = yaml.safe_load(state)
    if not isinstance(loaded_state, dict):
        raise TypeError("Serialized conversation state must deserialize into a dictionary.")
    return cast(dict[str, Any], loaded_state)


def load_conversation_state(
    state: dict[str, Any],
    deserialization_context: Optional[DeserializationContext] = None,
    plugins: Optional[list["WayflowDeserializationPlugin"]] = None,
) -> "Conversation":
    """
    Reconstruct a live conversation from a serialized state dictionary.

    The input dictionary is expected to come from
    ``deserialize_conversation_state()`` or another equivalent WayFlow
    serialization source.

    Parameters
    ----------
    state:
        Serialized conversation state as a dictionary.
    deserialization_context:
        Optional deserialization context to use. This is the preferred way to
        provide tool registries or plugins.
    plugins:
        Optional deserialization plugins. When a deserialization context is
        already provided, plugins should be attached to that context instead.

    Returns
    -------
    Conversation
        Reconstructed live conversation instance.

    Raises
    ------
    TypeError
        If the deserialized object is not a ``Conversation``.
    """
    from wayflowcore.conversation import Conversation

    deserialization_context = _resolve_deserialization_context(
        deserialization_context=deserialization_context,
        plugins=plugins,
    )

    conversation = autodeserialize_from_dict(state, deserialization_context)
    if not isinstance(conversation, Conversation):
        raise TypeError(
            f"Loaded object is of type {conversation.__class__.__name__}, not Conversation."
        )
    return conversation


def deserialize_conversation(
    conversation_state: str,
    deserialization_context: Optional[DeserializationContext] = None,
    plugins: Optional[list["WayflowDeserializationPlugin"]] = None,
) -> "Conversation":
    """
    Reconstruct a conversation directly from its serialized string form.

    This is a convenience wrapper around
    ``deserialize_conversation_state()`` followed by ``load_conversation_state()``.

    Parameters
    ----------
    conversation_state:
        Serialized conversation state string.
    deserialization_context:
        Optional deserialization context to use.
    plugins:
        Optional deserialization plugins.

    Returns
    -------
    Conversation
        Reconstructed live conversation instance.
    """
    return load_conversation_state(
        deserialize_conversation_state(conversation_state),
        deserialization_context=deserialization_context,
        plugins=plugins,
    )


def dump_variable_state(conversation: "Conversation") -> Optional[dict[str, Any]]:
    """
    Return the JSON-serializable runtime-owned variable state for a conversation.

    Only flow conversations expose runtime variable storage. For other
    conversation types, this returns ``None``.

    Parameters
    ----------
    conversation:
        Conversation whose runtime-owned variable values should be dumped.

    Returns
    -------
    dict[str, Any] | None
        JSON-compatible mapping of variable names to values for flow
        conversations, otherwise ``None``.

    Raises
    ------
    TypeError
        If a variable contains a value that cannot be represented as JSON.
    """
    from wayflowcore.executors._flowconversation import FlowConversation

    if not isinstance(conversation, FlowConversation):
        return None

    variable_state: dict[str, Any] = {}
    for variable_name, variable_value in conversation.state.variable_store.items():
        try:
            serialized_value = json.dumps(variable_value, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError) as e:
            raise TypeError(
                f"Variable '{variable_name}' contains a non-JSON-serializable value of type {type(variable_value).__name__}"
            ) from e
        variable_state[variable_name] = cast(Any, json.loads(serialized_value))
    return variable_state


def _resolve_deserialization_context(
    *,
    deserialization_context: Optional[DeserializationContext],
    plugins: Optional[list["WayflowDeserializationPlugin"]],
) -> DeserializationContext:
    if deserialization_context is None:
        return DeserializationContext(plugins=plugins)
    if plugins is not None:
        warnings.warn(
            "A list of plugins was provided together with a deserialization context instance in `load_conversation_state`. "
            "Do not pass the plugins to `load_conversation_state`, but create the context instance passing the list of plugins instead.",
            UserWarning,
        )
    return deserialization_context


__all__ = [
    "deserialize_conversation",
    "deserialize_conversation_state",
    "dump_conversation_state",
    "dump_variable_state",
    "load_conversation_state",
    "serialize_conversation_state",
]
