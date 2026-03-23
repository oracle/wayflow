# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
from typing import Any

import pytest

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.conversation import Conversation
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval, StateSnapshotPolicy
from wayflowcore.flow import Flow
from wayflowcore.property import AnyProperty, StringProperty
from wayflowcore.serialization import (
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
    VariableReadStep,
    VariableWriteStep,
)
from wayflowcore.tools import ClientTool, ServerTool, ToolResult, register_server_tool
from wayflowcore.variable import Variable

from ..testhelpers.state_snapshot_testutils import (
    execute_with_state_snapshots,
    restore_conversation_from_snapshot_payload,
)


class _UnserializableValue:
    def __str__(self) -> str:
        return "custom-value"


def _build_snapshot_flow(custom_variable: Variable) -> Flow:
    return Flow.from_steps(
        [
            VariableWriteStep(
                variable=custom_variable,
                input_mapping={VariableWriteStep.VALUE: custom_variable.name},
            ),
            OutputMessageStep(message_template="Hello there"),
        ],
        variables=[custom_variable],
        name="snapshot_flow",
    )


def _build_non_finite_input_snapshot_flow() -> Flow:
    return Flow.from_steps(
        [
            ToolExecutionStep(
                tool=ServerTool(
                    name="echo",
                    description="Echo input",
                    func=lambda bad: str(bad),
                    input_descriptors=[AnyProperty(name="bad")],
                )
            ),
            CompleteStep(name="end"),
        ],
        name="non_finite_snapshot_flow",
    )


def _make_snapshot_flow_conversation(
    *,
    variable_type: StringProperty | AnyProperty,
    input_value: Any,
) -> tuple[Variable, Conversation]:
    custom_variable = Variable(
        name="custom",
        type=variable_type,
        description="Custom variable used for snapshot serialization tests",
    )
    conversation = _build_snapshot_flow(custom_variable).start_conversation(
        inputs={custom_variable.name: input_value}
    )
    conversation.execute()
    return custom_variable, conversation


def _build_user_input_resume_flow() -> Flow:
    return Flow.from_steps(
        [InputMessageStep("Please answer"), OutputMessageStep("done")],
        name="resume_flow",
    )


def _conversation_turn_snapshot_payload(
    conversation: Conversation,
) -> tuple[object, dict[str, Any]]:
    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert state_snapshot_events[-1].state_snapshot is not None
    return status, state_snapshot_events[-1].state_snapshot


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


def test_dump_conversation_state_is_strict_json_serializable_and_lightweight() -> None:
    _, conversation = _make_snapshot_flow_conversation(
        variable_type=StringProperty(),
        input_value="custom-value",
    )

    snapshot = dump_conversation_state(conversation)

    assert json.loads(json.dumps(snapshot, allow_nan=False)) == snapshot
    assert dump_variable_state(conversation) == {"custom": "custom-value"}
    assert snapshot["conversation"]["component_type"] == "Flow"
    assert snapshot["conversation"]["messages"][-1]["content"] == "Hello there"
    assert all(
        not isinstance(scalar, (Conversation, Flow, OutputMessageStep))
        for scalar in _walk_scalars(snapshot)
    )


def test_dump_conversation_state_includes_runtime_conversation_ids() -> None:
    _, conversation = _make_snapshot_flow_conversation(
        variable_type=StringProperty(),
        input_value="custom-value",
    )

    snapshot = dump_conversation_state(conversation)

    assert snapshot["conversation"]["id"] == conversation.id
    assert snapshot["conversation"]["conversation_id"] == conversation.conversation_id


def test_dump_conversation_state_status_overrides_do_not_mutate_live_conversation() -> None:
    _, conversation = _make_snapshot_flow_conversation(
        variable_type=StringProperty(),
        input_value="custom-value",
    )

    previous_status = conversation.status
    previous_status_handled = conversation.status_handled

    snapshot = dump_conversation_state(conversation, status=None, status_handled=True)

    assert snapshot["execution"]["status"] is None
    assert snapshot["execution"]["status_handled"] is True
    assert conversation.status is previous_status
    assert conversation.status_handled is previous_status_handled


def test_dump_variable_state_rejects_non_json_serializable_values() -> None:
    _, conversation = _make_snapshot_flow_conversation(
        variable_type=AnyProperty(),
        input_value=_UnserializableValue(),
    )

    with pytest.raises(TypeError, match="Variable 'custom' contains a non-JSON-serializable"):
        dump_variable_state(conversation)


@pytest.mark.parametrize(
    ("value", "expected_dumped_value"),
    [
        pytest.param(float("nan"), "NaN", id="nan"),
        pytest.param(float("inf"), "Infinity", id="infinity"),
        pytest.param(float("-inf"), "-Infinity", id="negative-infinity"),
    ],
)
def test_dump_conversation_state_normalizes_non_finite_floats_for_strict_json(
    value: float,
    expected_dumped_value: str,
) -> None:
    conversation = _build_non_finite_input_snapshot_flow().start_conversation(inputs={"bad": value})

    snapshot = dump_conversation_state(conversation)

    assert json.loads(json.dumps(snapshot, allow_nan=False)) == snapshot
    assert snapshot["conversation"]["inputs"]["bad"] == expected_dumped_value


def test_serialized_conversation_roundtrip_preserves_pending_tool_results() -> None:
    client_tool = ClientTool(
        name="client_lookup",
        description="Look up some data on the client side",
        parameters={},
    )
    conversation = Flow.from_steps(
        [
            ToolExecutionStep(tool=client_tool),
            CompleteStep(name="end"),
        ],
        name="tool_resume_flow",
    ).start_conversation()

    status = conversation.execute()
    assert isinstance(status, ToolRequestStatus)

    tool_request = status.tool_requests[0]
    conversation.append_tool_result(
        ToolResult(tool_request_id=tool_request.tool_request_id, content="client-result")
    )

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


def test_emitted_snapshot_payload_restores_waiting_for_user_input() -> None:
    status, snapshot_payload = _conversation_turn_snapshot_payload(
        _build_user_input_resume_flow().start_conversation()
    )

    assert isinstance(status, UserMessageRequestStatus)

    restored_conversation = restore_conversation_from_snapshot_payload(
        json.loads(json.dumps(snapshot_payload, allow_nan=False))
    )
    restored_conversation.append_user_message("hello")
    resumed_status = restored_conversation.execute()

    assert isinstance(resumed_status, FinishedStatus)
    assert [message.content for message in restored_conversation.get_messages()] == [
        "Please answer",
        "hello",
        "done",
    ]


def test_emitted_snapshot_payload_restores_waiting_for_client_tool_result() -> None:
    client_tool = ClientTool(
        name="client_lookup",
        description="Look up some data on the client side",
        parameters={},
    )
    conversation = Flow.from_steps(
        [
            ToolExecutionStep(tool=client_tool),
            CompleteStep(name="end"),
        ],
        name="snapshot_client_tool_resume_flow",
    ).start_conversation()

    status, snapshot_payload = _conversation_turn_snapshot_payload(conversation)

    assert isinstance(status, ToolRequestStatus)

    restored_conversation = restore_conversation_from_snapshot_payload(snapshot_payload)
    assert isinstance(restored_conversation.status, ToolRequestStatus)

    tool_request = restored_conversation.status.tool_requests[0]
    restored_conversation.append_tool_result(
        ToolResult(tool_request_id=tool_request.tool_request_id, content="client-result")
    )
    resumed_status = restored_conversation.execute()

    assert isinstance(resumed_status, FinishedStatus)
    tool_result_messages = [
        message.tool_result
        for message in restored_conversation.get_messages()
        if message.tool_result
    ]
    assert len(tool_result_messages) == 1
    assert tool_result_messages[0].tool_request_id == tool_request.tool_request_id
    assert tool_result_messages[0].content == "client-result"


def test_emitted_snapshot_payload_restores_variable_dependent_continuation() -> None:
    customer_name = Variable(
        name="customer_name",
        type=StringProperty(),
        description="Customer name persisted across resumable snapshots",
    )
    capture_name = VariableWriteStep(
        variable=customer_name,
        input_mapping={VariableWriteStep.VALUE: customer_name.name},
        name="capture_name",
    )
    ask_follow_up = InputMessageStep(
        message_template="How can I help {{customer_name}}?",
        name="ask_follow_up",
    )
    read_name = VariableReadStep(variable=customer_name, name="read_name")
    final_message = OutputMessageStep(
        message_template="Stored {{stored_name}}. Reply: {{reply}}",
        name="final_message",
    )
    flow = Flow(
        begin_step=capture_name,
        steps={
            "capture_name": capture_name,
            "ask_follow_up": ask_follow_up,
            "read_name": read_name,
            "final_message": final_message,
        },
        control_flow_edges=[
            ControlFlowEdge(capture_name, ask_follow_up),
            ControlFlowEdge(ask_follow_up, read_name),
            ControlFlowEdge(read_name, final_message),
            ControlFlowEdge(final_message, None),
        ],
        data_flow_edges=[
            DataFlowEdge(
                ask_follow_up,
                InputMessageStep.USER_PROVIDED_INPUT,
                final_message,
                "reply",
            ),
            DataFlowEdge(read_name, VariableReadStep.VALUE, final_message, "stored_name"),
        ],
        variables=[customer_name],
        name="snapshot_variable_resume_flow",
    )
    conversation = flow.start_conversation(inputs={customer_name.name: "Alice"})

    status, snapshot_payload = _conversation_turn_snapshot_payload(conversation)

    assert isinstance(status, UserMessageRequestStatus)

    restored_conversation = restore_conversation_from_snapshot_payload(snapshot_payload)
    assert dump_variable_state(restored_conversation) == {"customer_name": "Alice"}

    restored_conversation.append_user_message("Need pricing")
    resumed_status = restored_conversation.execute()

    assert isinstance(resumed_status, FinishedStatus)
    assert [message.content for message in restored_conversation.get_messages()] == [
        "How can I help Alice?",
        "Need pricing",
        "Stored Alice. Reply: Need pricing",
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

    assert isinstance(conversation.execute(), FinishedStatus)
