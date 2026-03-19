# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
from typing import Any

import pytest

from wayflowcore.conversation import Conversation
from wayflowcore.executors._flowconversation import FlowConversation
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.flow import Flow
from wayflowcore.property import AnyProperty, StringProperty
from wayflowcore.serialization import (
    deserialize_conversation,
    deserialize_conversation_state,
    dump_conversation_state,
    dump_variable_state,
    load_conversation_state,
    serialize_conversation_state,
)
from wayflowcore.serialization.context import DeserializationContext
from wayflowcore.steps import (
    CompleteStep,
    InputMessageStep,
    OutputMessageStep,
    ToolExecutionStep,
    VariableWriteStep,
)
from wayflowcore.tools import ClientTool, ServerTool, ToolResult, register_server_tool
from wayflowcore.variable import Variable


class _UnserializableValue:
    def __str__(self) -> str:
        return "custom-value"


def _build_snapshot_flow(custom_variable: Variable) -> Flow:
    return Flow.from_steps(
        steps=[
            VariableWriteStep(
                variable=custom_variable,
                input_mapping={VariableWriteStep.VALUE: custom_variable.name},
            ),
            OutputMessageStep(message_template="Hello there"),
        ],
        variables=[custom_variable],
        name="snapshot_flow",
    )


def _walk_scalars(value: Any):
    if isinstance(value, dict):
        for inner_value in value.values():
            yield from _walk_scalars(inner_value)
        return
    if isinstance(value, list):
        for inner_value in value:
            yield from _walk_scalars(inner_value)
        return
    yield value


def test_dump_conversation_state_is_json_serializable_and_lightweight() -> None:
    custom_variable = Variable(
        name="custom",
        type=StringProperty(),
        description="Custom variable used for snapshot serialization tests",
    )
    flow = _build_snapshot_flow(custom_variable)
    conversation = flow.start_conversation(inputs={custom_variable.name: "custom-value"})
    conversation.execute()

    snapshot = dump_conversation_state(conversation)
    variable_state = dump_variable_state(conversation)
    serialized_conversation_state = serialize_conversation_state(conversation)
    deserialized_conversation_state = deserialize_conversation_state(serialized_conversation_state)

    assert json.loads(json.dumps(snapshot)) == snapshot
    assert deserialized_conversation_state["_component_type"] == conversation.__class__.__name__
    assert variable_state == {"custom": "custom-value"}
    assert snapshot["conversation"]["component_type"] == "Flow"
    assert snapshot["conversation"]["messages"][-1]["content"] == "Hello there"

    assert all(
        not isinstance(scalar, (Conversation, Flow, OutputMessageStep))
        for scalar in _walk_scalars(snapshot)
    )


def test_dump_conversation_state_overrides_execution_fields_without_mutating_conversation() -> None:
    custom_variable = Variable(
        name="custom",
        type=StringProperty(),
        description="Custom variable used for snapshot serialization tests",
    )
    flow = _build_snapshot_flow(custom_variable)
    conversation = flow.start_conversation(inputs={custom_variable.name: "custom-value"})
    conversation.execute()

    previous_status = conversation.status
    previous_status_handled = conversation.status_handled

    snapshot = dump_conversation_state(
        conversation,
        status=None,
        status_handled=True,
    )

    assert snapshot["execution"]["status"] is None
    assert snapshot["execution"]["status_handled"] is True
    assert conversation.status is previous_status
    assert conversation.status_handled is previous_status_handled


def test_dump_conversation_state_includes_runtime_conversation_id() -> None:
    custom_variable = Variable(
        name="custom",
        type=StringProperty(),
        description="Custom variable used for snapshot serialization tests",
    )
    flow = _build_snapshot_flow(custom_variable)
    conversation = flow.start_conversation(inputs={custom_variable.name: "custom-value"})
    conversation.execute()

    snapshot = dump_conversation_state(conversation)

    assert snapshot["conversation"]["id"] == conversation.id
    assert snapshot["conversation"]["conversation_id"] == conversation.conversation_id


def test_dump_conversation_state_does_not_overload_status_conversation_identity() -> None:
    custom_variable = Variable(
        name="custom",
        type=StringProperty(),
        description="Custom variable used for snapshot serialization tests",
    )
    flow = _build_snapshot_flow(custom_variable)
    conversation = flow.start_conversation(inputs={custom_variable.name: "custom-value"})
    conversation.execute()

    snapshot = dump_conversation_state(conversation)

    assert snapshot["execution"]["status"]["type"] == "FinishedStatus"
    assert "conversation_id" not in snapshot["execution"]["status"]


def test_dump_variable_state_rejects_non_json_serializable_values() -> None:
    custom_variable = Variable(
        name="custom",
        type=AnyProperty(),
        description="Custom variable used for snapshot serialization tests",
    )
    flow = _build_snapshot_flow(custom_variable)
    conversation = flow.start_conversation(inputs={custom_variable.name: _UnserializableValue()})
    conversation.execute()

    with pytest.raises(TypeError, match="Variable 'custom' contains a non-JSON-serializable"):
        dump_variable_state(conversation)


def test_conversation_state_roundtrip_preserves_pending_tool_results() -> None:
    client_tool = ClientTool(
        name="client_lookup",
        description="Look up some data on the client side",
        parameters={},
    )
    flow = Flow.from_steps(
        [
            ToolExecutionStep(tool=client_tool),
            CompleteStep(name="end"),
        ],
        name="tool_resume_flow",
    )
    conversation = flow.start_conversation()

    status = conversation.execute()
    assert isinstance(status, ToolRequestStatus)

    tool_request = status.tool_requests[0]
    conversation.append_tool_result(
        ToolResult(tool_request_id=tool_request.tool_request_id, content="client-result")
    )

    snapshot = dump_conversation_state(conversation)
    assert snapshot["execution"]["status"]["type"] == "ToolRequestStatus"
    assert snapshot["execution"]["status"]["tool_results"] == [
        {
            "tool_request_id": tool_request.tool_request_id,
            "content": "client-result",
        }
    ]
    assert all(message.tool_result is None for message in conversation.get_messages())

    loaded_conversation = load_conversation_state(
        deserialize_conversation_state(serialize_conversation_state(conversation))
    )
    loaded_snapshot = dump_conversation_state(loaded_conversation)

    assert loaded_snapshot["execution"]["status"]["tool_results"] == [
        {
            "tool_request_id": tool_request.tool_request_id,
            "content": "client-result",
        }
    ]

    resumed_status = loaded_conversation.execute()
    assert isinstance(resumed_status, FinishedStatus)

    tool_result_messages = [
        message.tool_result for message in loaded_conversation.get_messages() if message.tool_result
    ]
    assert len(tool_result_messages) == 1
    assert tool_result_messages[0].tool_request_id == tool_request.tool_request_id
    assert tool_result_messages[0].content == "client-result"


def test_load_conversation_state_restores_a_runnable_conversation() -> None:
    flow = Flow.from_steps(
        [InputMessageStep("Please answer"), OutputMessageStep("done")],
        name="resume_flow",
    )
    conversation = flow.start_conversation()

    status = conversation.execute()
    assert isinstance(status, UserMessageRequestStatus)

    loaded_conversation = load_conversation_state(
        deserialize_conversation_state(serialize_conversation_state(conversation))
    )

    assert isinstance(loaded_conversation, FlowConversation)
    loaded_conversation.append_user_message("hello")
    resumed_status = loaded_conversation.execute()

    assert isinstance(resumed_status, FinishedStatus)
    assert [message.content for message in loaded_conversation.get_messages()] == [
        "Please answer",
        "hello",
        "done",
    ]


def test_deserialize_conversation_restores_a_runnable_conversation() -> None:
    flow = Flow.from_steps(
        [InputMessageStep("Please answer"), OutputMessageStep("done")],
        name="resume_flow",
    )
    conversation = flow.start_conversation()

    status = conversation.execute()
    assert isinstance(status, UserMessageRequestStatus)

    deserialized_conversation = deserialize_conversation(serialize_conversation_state(conversation))

    assert isinstance(deserialized_conversation, FlowConversation)
    deserialized_conversation.append_user_message("hello")
    resumed_status = deserialized_conversation.execute()

    assert isinstance(resumed_status, FinishedStatus)
    assert [message.content for message in deserialized_conversation.get_messages()] == [
        "Please answer",
        "hello",
        "done",
    ]


def test_load_conversation_state_uses_the_given_deserialization_context() -> None:
    tool = ServerTool(
        name="say_hi",
        description="Say hi",
        func=lambda: "hi",
        input_descriptors=[],
    )
    flow = Flow.from_steps(
        [
            ToolExecutionStep(tool=tool),
            CompleteStep(name="end"),
        ],
        name="tool_flow",
    )

    deserialization_context = DeserializationContext()
    register_server_tool(tool, deserialization_context.registered_tools)

    conversation = load_conversation_state(
        deserialize_conversation_state(serialize_conversation_state(flow.start_conversation())),
        deserialization_context=deserialization_context,
    )

    assert isinstance(conversation, FlowConversation)
    assert isinstance(conversation.execute(), FinishedStatus)
