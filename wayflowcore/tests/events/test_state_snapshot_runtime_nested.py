# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest

from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval
from wayflowcore.flow import Flow
from wayflowcore.steps import (
    CompleteStep,
    FlowExecutionStep,
    OutputMessageStep,
    ParallelFlowExecutionStep,
)

from ..testhelpers.statesnapshots import (
    build_policy,
    create_nested_agent_step_flow_conversation,
    create_nested_managerworkers_flow_conversation,
    create_nested_swarm_flow_conversation,
    create_parallel_child_flow,
    execute_with_state_snapshots,
    execute_with_state_snapshots_async,
    find_snapshot_events_by_component_type,
    group_snapshot_events_by_conversation_id,
    snapshot_message,
    snapshot_runtime_conversation_ids,
    snapshot_status_types,
)


def test_state_snapshot_policy_is_inherited_by_nested_sub_conversations() -> None:
    child_flow = Flow.from_steps(
        [
            OutputMessageStep(message_template="child"),
            CompleteStep(name="end"),
        ]
    )
    parent_flow = Flow.from_steps(
        [
            FlowExecutionStep(flow=child_flow),
            CompleteStep(name="end"),
        ]
    )
    conversation = parent_flow.start_conversation()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=build_policy(StateSnapshotInterval.CONVERSATION_TURNS),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 4
    assert {snapshot_event.conversation_id for snapshot_event in state_snapshot_events} == {
        conversation.conversation_id
    }
    child_runtime_conversation_id = state_snapshot_events[1].state_snapshot["conversation"]["id"]
    assert snapshot_runtime_conversation_ids(state_snapshot_events) == [
        conversation.id,
        child_runtime_conversation_id,
        child_runtime_conversation_id,
        conversation.id,
    ]
    assert child_runtime_conversation_id != conversation.id


@pytest.mark.anyio
async def test_state_snapshot_policy_is_inherited_by_nested_sub_conversations_async() -> None:
    child_flow = Flow.from_steps(
        [
            OutputMessageStep(message_template="child"),
            CompleteStep(name="end"),
        ]
    )
    parent_flow = Flow.from_steps(
        [
            FlowExecutionStep(flow=child_flow),
            CompleteStep(name="end"),
        ]
    )
    conversation = parent_flow.start_conversation()

    status, state_snapshot_events = await execute_with_state_snapshots_async(
        conversation,
        state_snapshot_policy=build_policy(StateSnapshotInterval.CONVERSATION_TURNS),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 4
    assert {snapshot_event.conversation_id for snapshot_event in state_snapshot_events} == {
        conversation.conversation_id
    }
    child_runtime_conversation_id = state_snapshot_events[1].state_snapshot["conversation"]["id"]
    assert snapshot_runtime_conversation_ids(state_snapshot_events) == [
        conversation.id,
        child_runtime_conversation_id,
        child_runtime_conversation_id,
        conversation.id,
    ]
    assert child_runtime_conversation_id != conversation.id


def test_state_snapshot_policy_is_inherited_by_parallel_sub_conversations() -> None:
    conversation = Flow.from_steps(
        [
            ParallelFlowExecutionStep(
                flows=[
                    create_parallel_child_flow("left_output", "left"),
                    create_parallel_child_flow("right_output", "right"),
                ]
            ),
            CompleteStep(name="end"),
        ]
    ).start_conversation()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=build_policy(StateSnapshotInterval.CONVERSATION_TURNS),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 6
    assert {snapshot_event.conversation_id for snapshot_event in state_snapshot_events} == {
        conversation.conversation_id
    }
    assert snapshot_status_types(state_snapshot_events).count(None) == 3
    assert snapshot_status_types(state_snapshot_events).count("FinishedStatus") == 3


def test_state_snapshot_policy_is_inherited_by_nested_agent_steps() -> None:
    conversation = create_nested_agent_step_flow_conversation()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=build_policy(StateSnapshotInterval.CONVERSATION_TURNS),
    )

    nested_conversation_id = state_snapshot_events[1].conversation_id

    assert isinstance(status, UserMessageRequestStatus)
    assert snapshot_status_types(state_snapshot_events) == [
        None,
        None,
        "UserMessageRequestStatus",
        "UserMessageRequestStatus",
    ]
    assert [snapshot_event.conversation_id for snapshot_event in state_snapshot_events] == [
        conversation.conversation_id,
        nested_conversation_id,
        nested_conversation_id,
        conversation.conversation_id,
    ]
    assert nested_conversation_id != conversation.conversation_id
    assert snapshot_message(state_snapshot_events[-1]) == "agent answer"


@pytest.mark.parametrize(
    (
        "conversation_factory",
        "expected_multi_agent_component_type",
        "expected_child_message",
        "expected_parent_message",
    ),
    [
        pytest.param(
            create_nested_managerworkers_flow_conversation,
            "ManagerWorkers",
            "worker answer",
            "manager final answer",
            id="managerworkers",
        ),
        pytest.param(
            create_nested_swarm_flow_conversation,
            "Swarm",
            "agent2 answer",
            "agent1 final answer",
            id="swarm",
        ),
    ],
)
def test_nested_multi_agent_components_emit_snapshots_for_the_active_conversation(
    conversation_factory,
    expected_multi_agent_component_type: str,
    expected_child_message: str,
    expected_parent_message: str,
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=build_policy(StateSnapshotInterval.CONVERSATION_TURNS),
    )

    assert isinstance(status, UserMessageRequestStatus)
    assert len(state_snapshot_events) == 14

    snapshot_events_by_conversation_id = group_snapshot_events_by_conversation_id(
        state_snapshot_events
    )

    assert len(snapshot_events_by_conversation_id) == 4

    flow_snapshot_events = snapshot_events_by_conversation_id[conversation.conversation_id]
    parent_multi_agent_snapshot_events = find_snapshot_events_by_component_type(
        state_snapshot_events,
        expected_multi_agent_component_type,
    )
    agent_snapshot_event_groups = [
        snapshot_events
        for conversation_id, snapshot_events in snapshot_events_by_conversation_id.items()
        if conversation_id
        not in {
            conversation.conversation_id,
            parent_multi_agent_snapshot_events[0].conversation_id,
        }
    ]
    manager_thread_snapshot_events = next(
        snapshot_events
        for snapshot_events in agent_snapshot_event_groups
        if len(snapshot_events) == 4
    )
    delegated_agent_snapshot_events = next(
        snapshot_events
        for snapshot_events in agent_snapshot_event_groups
        if len(snapshot_events) == 2
    )

    assert snapshot_status_types(flow_snapshot_events) == [None, "UserMessageRequestStatus"]
    assert snapshot_message(flow_snapshot_events[-1]) == expected_parent_message

    assert snapshot_status_types(parent_multi_agent_snapshot_events) == [
        None,
        "ToolRequestStatus",
        None,
        "UserMessageRequestStatus",
        None,
        "UserMessageRequestStatus",
    ]
    assert snapshot_message(parent_multi_agent_snapshot_events[4]) == expected_child_message
    assert snapshot_message(parent_multi_agent_snapshot_events[-1]) == expected_parent_message

    assert snapshot_status_types(manager_thread_snapshot_events) == [
        None,
        "ToolRequestStatus",
        None,
        "UserMessageRequestStatus",
    ]
    assert snapshot_message(manager_thread_snapshot_events[2]) == expected_child_message
    assert snapshot_message(manager_thread_snapshot_events[-1]) == expected_parent_message

    assert snapshot_status_types(delegated_agent_snapshot_events) == [
        None,
        "UserMessageRequestStatus",
    ]
    assert snapshot_message(delegated_agent_snapshot_events[-1]) == expected_child_message
