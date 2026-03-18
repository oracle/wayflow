# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest

from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors._events.event import EventType
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.executors.interrupts.executioninterrupt import InterruptedExecutionStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval

from ..conftest import disable_streaming
from ..test_interrupts import OnEventExecutionInterrupt
from ..testhelpers.statesnapshots import (
    MutatingExecutionEndInterrupt,
    SnapshotCollector,
    WorkerExecutionEndInterrupt,
    assert_terminal_snapshot,
    build_policy,
    create_agent_conversation,
    create_managerworkers_conversation,
    create_output_flow_conversation,
    create_tool_flow_conversation,
    execute_with_state_snapshots,
    execute_with_state_snapshots_async,
    find_snapshot_events_by_component_type,
    snapshot_status_types,
)


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


def test_parent_multi_agent_does_not_emit_turn_end_snapshot_when_child_turn_is_interrupted() -> (
    None
):
    conversation = create_managerworkers_conversation()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        execution_interrupts=[WorkerExecutionEndInterrupt()],
        state_snapshot_policy=build_policy(StateSnapshotInterval.CONVERSATION_TURNS),
        execution_context=disable_streaming(),
    )

    assert isinstance(status, InterruptedExecutionStatus)
    parent_multi_agent_snapshot_events = find_snapshot_events_by_component_type(
        state_snapshot_events,
        "ManagerWorkers",
    )
    assert "InterruptedExecutionStatus" not in snapshot_status_types(
        parent_multi_agent_snapshot_events
    )
