# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, cast

from wayflowcore._utils.formatting import stringify
from wayflowcore.executors.executionstatus import (
    AuthChallengeRequestStatus,
    ExecutionStatus,
    FinishedStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.messagelist import ImageContent, Message, MessageContent, TextContent
from wayflowcore.serialization.context import SerializationContext
from wayflowcore.serialization.serializer import serialize_any_to_dict_or_stringify
from wayflowcore.tools.tools import ToolRequest, ToolResult

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.executors._agentconversation import AgentConversation
    from wayflowcore.executors._flowconversation import FlowConversation


def _dump_json_compatible_value(value: Any) -> Any:
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
        dumped_value = {
            "conversation_id": value.conversation_id,
            "conversation_type": value.__class__.__name__,
        }
    elif isinstance(value, Component):
        dumped_value = {
            "component_id": value.id,
            "component_type": value.__class__.__name__,
        }
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


def _dump_variable_value(variable_name: str, value: Any) -> Any:
    try:
        serialized_value = json.dumps(value, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as e:
        raise TypeError(
            f"Variable '{variable_name}' contains a non-JSON-serializable value of type {type(value).__name__}"
        ) from e
    return cast(Any, json.loads(serialized_value))


def _dump_string_keyed_mapping(values: dict[Any, Any]) -> dict[str, Any]:
    return {str(key): _dump_json_compatible_value(value) for key, value in values.items()}


def _dump_flow_input_output_key_values(values: dict[Any, Any]) -> dict[str, Any]:
    return {
        f"{step_name}.{value_name}": _dump_json_compatible_value(value)
        for (step_name, value_name), value in values.items()
    }


def _dump_variable_store(variable_store: dict[str, Any]) -> dict[str, Any]:
    return {
        variable_name: _dump_variable_value(variable_name, variable_value)
        for variable_name, variable_value in variable_store.items()
    }


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


def _dump_message_content(content: MessageContent) -> dict[str, Any]:
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

    tool_requests = [
        _dump_tool_request(tool_request) for tool_request in message.tool_requests or []
    ]
    dumped_tool_result = _dump_tool_result(message.tool_result)

    if tool_requests:
        dumped_message["tool_requests"] = tool_requests
    if dumped_tool_result is not None:
        dumped_message["tool_result"] = dumped_tool_result
    return dumped_message


def _dump_execution_status(execution_status: Optional[ExecutionStatus]) -> Optional[dict[str, Any]]:
    dumped_status: dict[str, Any] | None
    if execution_status is None:
        dumped_status = None
    else:
        dumped_status = {
            "type": execution_status.__class__.__name__,
            "conversation_id": execution_status._conversation_id,
        }

        if isinstance(execution_status, FinishedStatus):
            dumped_status["output_values"] = _dump_json_compatible_value(
                execution_status.output_values
            )
            dumped_status["complete_step_name"] = execution_status.complete_step_name
        elif isinstance(execution_status, UserMessageRequestStatus):
            dumped_status["message"] = _dump_message(execution_status.message)
        elif isinstance(execution_status, ToolRequestStatus):
            dumped_status["tool_requests"] = [
                _dump_tool_request(tool_request) for tool_request in execution_status.tool_requests
            ]
            dumped_status["tool_results"] = [
                _dump_tool_result(tool_result)
                for tool_result in execution_status._tool_results or []
            ]
        elif isinstance(execution_status, ToolExecutionConfirmationStatus):
            dumped_status["tool_requests"] = [
                _dump_tool_request(tool_request) for tool_request in execution_status.tool_requests
            ]
        elif isinstance(execution_status, AuthChallengeRequestStatus):
            dumped_status["client_transport_id"] = execution_status.client_transport_id
    return dumped_status


def _dump_conversation_info(conversation: "Conversation") -> dict[str, Any]:
    return {
        "conversation_id": conversation.conversation_id,
        "conversation_type": conversation.__class__.__name__,
        "component_type": conversation.component.__class__.__name__,
        "name": conversation.name,
        "inputs": _dump_json_compatible_value(conversation.inputs),
        "messages": [_dump_message(message) for message in conversation.get_messages()],
    }


def _dump_execution_info(conversation: "Conversation") -> dict[str, Any]:
    return {
        "current_step_name": conversation.current_step_name,
        "status": _dump_execution_status(conversation.status),
        "status_handled": conversation.status_handled,
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
        "tool_call_queue": [
            _dump_tool_request(tool_request) for tool_request in conversation.state.tool_call_queue
        ],
        "current_tool_request": _dump_tool_request(conversation.state.current_tool_request),
        "current_flow_conversation": _dump_json_compatible_value(
            conversation.state.current_flow_conversation
        ),
        "current_sub_component_conversations": _dump_string_keyed_mapping(
            conversation.state.current_sub_component_conversations
        ),
    }


def dump_conversation_state(conversation: "Conversation") -> dict[str, Any]:
    from wayflowcore.executors._agentconversation import AgentConversation
    from wayflowcore.executors._flowconversation import FlowConversation

    if isinstance(conversation, FlowConversation):
        execution_info = {
            **_dump_execution_info(conversation),
            **_dump_flow_execution_info(conversation),
        }
    elif isinstance(conversation, AgentConversation):
        execution_info = {
            **_dump_execution_info(conversation),
            **_dump_agent_execution_info(conversation),
        }
    else:
        execution_info = _dump_execution_info(conversation)

    return {
        "conversation": _dump_conversation_info(conversation),
        "execution": execution_info,
    }


def serialize_conversation_state(conversation: "Conversation") -> str:
    return json.dumps(dump_conversation_state(conversation), sort_keys=True)


def deserialize_conversation_state(state: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(state))


def dump_variable_state(conversation: "Conversation") -> Optional[dict[str, Any]]:
    from wayflowcore.executors._flowconversation import FlowConversation

    if not isinstance(conversation, FlowConversation):
        variable_state = None
    else:
        variable_state = _dump_variable_store(conversation.state.variable_store)
    return variable_state


__all__ = [
    "deserialize_conversation_state",
    "dump_conversation_state",
    "dump_variable_state",
    "serialize_conversation_state",
]
