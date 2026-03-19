# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any

import pytest

from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors._events.event import EventType
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.executors.interrupts.executioninterrupt import InterruptedExecutionStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval
from wayflowcore.flow import Flow
from wayflowcore.serialization import deserialize_conversation, dump_conversation_state
from wayflowcore.steps import CompleteStep, InputMessageStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.tools import ClientTool, ToolResult

from ..test_interrupts import OnEventExecutionInterrupt
from ..testhelpers.statesnapshots import (
    MutatingExecutionEndInterrupt,
    SnapshotCollector,
    assert_terminal_snapshot,
    build_policy,
    create_agent_conversation,
    create_output_flow_conversation,
    create_tool_flow_conversation,
    execute_with_state_snapshots,
    execute_with_state_snapshots_async,
    snapshot_status_types,
)


def _restore_conversation_from_snapshot_payload(snapshot_payload: dict[str, Any]):
    assert snapshot_payload["runtime"] == "wayflow"
    assert snapshot_payload["schema_version"] == 1
    assert isinstance(snapshot_payload["conversation_state"], str)

    restored_conversation = deserialize_conversation(snapshot_payload["conversation_state"])
    assert dump_conversation_state(restored_conversation) == {
        "conversation": snapshot_payload["conversation"],
        "execution": snapshot_payload["execution"],
    }
    return restored_conversation


@pytest.mark.parametrize(
    (
        "conversation_factory",
        "expected_status_class",
        "expected_status_type",
        "expected_message",
    ),
    [
        pytest.param(
            create_output_flow_conversation,
            FinishedStatus,
            "FinishedStatus",
            "Hello",
            id="flow",
        ),
        pytest.param(
            create_agent_conversation,
            UserMessageRequestStatus,
            "UserMessageRequestStatus",
            "Hello from agent",
            id="agent",
        ),
    ],
)
def test_conversation_turn_policy_records_opening_and_closing_checkpoints(
    conversation_factory,
    expected_status_class,
    expected_status_type: str,
    expected_message: str,
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=build_policy(StateSnapshotInterval.CONVERSATION_TURNS),
    )

    assert isinstance(status, expected_status_class)
    assert snapshot_status_types(state_snapshot_events) == [None, expected_status_type]
    assert_terminal_snapshot(
        state_snapshot_events,
        expected_status_type=expected_status_type,
        expected_message=expected_message,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    (
        "conversation_factory",
        "expected_status_class",
        "expected_status_type",
        "expected_message",
    ),
    [
        pytest.param(
            create_output_flow_conversation,
            FinishedStatus,
            "FinishedStatus",
            "Hello",
            id="flow",
        ),
        pytest.param(
            create_agent_conversation,
            UserMessageRequestStatus,
            "UserMessageRequestStatus",
            "Hello from agent",
            id="agent",
        ),
    ],
)
async def test_conversation_turn_policy_records_opening_and_closing_checkpoints_async(
    conversation_factory,
    expected_status_class,
    expected_status_type: str,
    expected_message: str,
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = await execute_with_state_snapshots_async(
        conversation,
        state_snapshot_policy=build_policy(StateSnapshotInterval.CONVERSATION_TURNS),
    )

    assert isinstance(status, expected_status_class)
    assert snapshot_status_types(state_snapshot_events) == [None, expected_status_type]
    assert_terminal_snapshot(
        state_snapshot_events,
        expected_status_type=expected_status_type,
        expected_message=expected_message,
    )


@pytest.mark.parametrize(
    ("conversation_factory", "expected_status_class"),
    [
        pytest.param(create_output_flow_conversation, FinishedStatus, id="flow"),
        pytest.param(create_agent_conversation, UserMessageRequestStatus, id="agent"),
    ],
)
def test_off_policy_disables_state_snapshot_emission(
    conversation_factory,
    expected_status_class,
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=build_policy(StateSnapshotInterval.OFF),
    )

    assert isinstance(status, expected_status_class)
    assert state_snapshot_events == []


@pytest.mark.parametrize(
    ("conversation_factory", "expected_message"),
    [
        pytest.param(create_output_flow_conversation, "Hello", id="flow"),
        pytest.param(create_agent_conversation, "Hello from agent", id="agent"),
    ],
)
def test_conversation_turn_policy_records_interrupted_turn_end_checkpoints(
    conversation_factory,
    expected_message: str,
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        execution_interrupts=[OnEventExecutionInterrupt(EventType.EXECUTION_END)],
        state_snapshot_policy=build_policy(StateSnapshotInterval.CONVERSATION_TURNS),
    )

    assert isinstance(status, InterruptedExecutionStatus)
    assert snapshot_status_types(state_snapshot_events) == [None, "InterruptedExecutionStatus"]
    assert_terminal_snapshot(
        state_snapshot_events,
        expected_status_type="InterruptedExecutionStatus",
        expected_message=expected_message,
    )


def test_conversation_turn_policy_keeps_only_the_opening_checkpoint_when_turn_raises() -> None:
    def explode() -> str:
        raise RuntimeError("boom")

    conversation = create_tool_flow_conversation(
        explode,
        name="explode",
        description="Raise an error",
    )
    collector = SnapshotCollector()

    with register_event_listeners([collector]):
        with pytest.raises(RuntimeError, match="boom"):
            conversation.execute(
                state_snapshot_policy=build_policy(StateSnapshotInterval.CONVERSATION_TURNS)
            )

    assert len(collector.state_snapshot_events) == 1
    assert collector.state_snapshot_events[0].state_snapshot["execution"]["status"] is None


def test_conversation_turn_policy_reflects_real_interrupt_side_effects_once() -> None:
    conversation = create_output_flow_conversation()
    interrupt = MutatingExecutionEndInterrupt()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        execution_interrupts=[interrupt],
        state_snapshot_policy=build_policy(StateSnapshotInterval.CONVERSATION_TURNS),
    )

    assert isinstance(status, FinishedStatus)
    assert interrupt.count == 1
    assert conversation.inputs["preview_count"] == 1
    assert snapshot_status_types(state_snapshot_events) == [None, "FinishedStatus"]
    assert state_snapshot_events[-1].state_snapshot["conversation"]["inputs"]["preview_count"] == 1


def test_conversation_turn_snapshot_payload_can_resume_waiting_for_client_tool_result() -> None:
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

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=build_policy(StateSnapshotInterval.CONVERSATION_TURNS),
    )

    assert isinstance(status, ToolRequestStatus)
    assert state_snapshot_events[-1].state_snapshot is not None
    restored_conversation = _restore_conversation_from_snapshot_payload(
        state_snapshot_events[-1].state_snapshot
    )
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


@pytest.mark.anyio
async def test_conversation_turn_snapshot_payload_can_resume_waiting_for_user_input_async() -> None:
    conversation = Flow.from_steps(
        [
            InputMessageStep("Please answer"),
            OutputMessageStep("done"),
        ],
        name="snapshot_user_resume_flow",
    ).start_conversation()

    status, state_snapshot_events = await execute_with_state_snapshots_async(
        conversation,
        state_snapshot_policy=build_policy(StateSnapshotInterval.CONVERSATION_TURNS),
    )

    assert isinstance(status, UserMessageRequestStatus)
    assert state_snapshot_events[-1].state_snapshot is not None
    restored_conversation = _restore_conversation_from_snapshot_payload(
        state_snapshot_events[-1].state_snapshot
    )
    restored_conversation.append_user_message("hello")
    resumed_status = await restored_conversation.execute_async()

    assert isinstance(resumed_status, FinishedStatus)
    assert [message.content for message in restored_conversation.get_messages()] == [
        "Please answer",
        "hello",
        "done",
    ]
