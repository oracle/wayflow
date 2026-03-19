# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest

from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval, StateSnapshotPolicy
from wayflowcore.flow import Flow
from wayflowcore.steps import (
    CompleteStep,
    FlowExecutionStep,
    OutputMessageStep,
    ParallelFlowExecutionStep,
    ParallelMapStep,
)

from ..testhelpers.statesnapshots import (
    create_nested_agent_step_flow_conversation,
    create_parallel_child_flow,
    execute_with_state_snapshots,
    execute_with_state_snapshots_async,
    restore_conversation_from_snapshot_payload,
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
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 2
    assert {snapshot_event.conversation_id for snapshot_event in state_snapshot_events} == {
        conversation.conversation_id
    }
    assert snapshot_runtime_conversation_ids(state_snapshot_events) == [
        conversation.id,
        conversation.id,
    ]


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
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 2
    assert {snapshot_event.conversation_id for snapshot_event in state_snapshot_events} == {
        conversation.conversation_id
    }
    assert snapshot_runtime_conversation_ids(state_snapshot_events) == [
        conversation.id,
        conversation.id,
    ]


def test_nested_root_turn_snapshot_payload_can_resume_the_logical_parent_conversation() -> None:
    child_flow = Flow.from_steps(
        [
            OutputMessageStep(message_template="child"),
            CompleteStep(name="child_end"),
        ],
        name="child_flow",
    )
    parent_flow = Flow.from_steps(
        [
            FlowExecutionStep(flow=child_flow),
            OutputMessageStep(message_template="parent"),
            CompleteStep(name="parent_end"),
        ],
        name="parent_flow",
    )
    conversation = parent_flow.start_conversation()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    root_turn_snapshot_event = state_snapshot_events[-1]
    root_turn_snapshot = root_turn_snapshot_event.state_snapshot
    assert root_turn_snapshot is not None
    assert root_turn_snapshot_event.conversation_id == conversation.conversation_id
    assert root_turn_snapshot["conversation"]["id"] == conversation.id

    restored_conversation = restore_conversation_from_snapshot_payload(root_turn_snapshot)
    assert restored_conversation.id == conversation.id
    assert restored_conversation.conversation_id == conversation.conversation_id

    resumed_status = restored_conversation.execute()

    assert isinstance(resumed_status, FinishedStatus)
    assert [message.content for message in restored_conversation.get_messages()] == [
        "child",
        "parent",
    ]


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
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 2
    assert {snapshot_event.conversation_id for snapshot_event in state_snapshot_events} == {
        conversation.conversation_id
    }
    assert snapshot_runtime_conversation_ids(state_snapshot_events) == [
        conversation.id,
        conversation.id,
    ]
    assert snapshot_status_types(state_snapshot_events) == [None, "FinishedStatus"]


def test_parallel_root_turn_snapshot_payloads_can_resume_the_logical_parent_conversation() -> None:
    left_child_flow = Flow.from_steps(
        [
            OutputMessageStep(
                message_template="left",
                output_mapping={OutputMessageStep.OUTPUT: "left_message"},
            ),
            CompleteStep(name="left_end"),
        ],
        name="left_child_flow",
    )
    right_child_flow = Flow.from_steps(
        [
            OutputMessageStep(
                message_template="right",
                output_mapping={OutputMessageStep.OUTPUT: "right_message"},
            ),
            CompleteStep(name="right_end"),
        ],
        name="right_child_flow",
    )
    conversation = Flow.from_steps(
        [
            ParallelFlowExecutionStep(
                flows=[
                    left_child_flow,
                    right_child_flow,
                ]
            ),
            CompleteStep(name="end"),
        ]
    ).start_conversation()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)

    for snapshot_event in state_snapshot_events:
        snapshot_payload = snapshot_event.state_snapshot
        assert snapshot_payload is not None

        restored_conversation = restore_conversation_from_snapshot_payload(snapshot_payload)
        resumed_status = restored_conversation.execute()

        assert isinstance(resumed_status, FinishedStatus)
        assert sorted(message.content for message in restored_conversation.get_messages()) == [
            "left",
            "right",
        ]


def test_parallel_map_emits_only_resumable_parent_turn_snapshots() -> None:
    child_flow = Flow.from_steps(
        [
            OutputMessageStep(message_template="item={{item}}"),
            CompleteStep(name="child_end"),
        ],
        name="parallel_map_child",
    )
    conversation = Flow.from_steps(
        [
            ParallelMapStep(
                flow=child_flow,
                unpack_input={"item": "."},
                name="parallel_map",
            ),
            CompleteStep(name="end"),
        ],
        name="parallel_map_parent",
    ).start_conversation(inputs={ParallelMapStep.ITERATED_INPUT: ["a", "b"]})

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert snapshot_status_types(state_snapshot_events) == [None, "FinishedStatus"]

    for snapshot_event in state_snapshot_events:
        snapshot_payload = snapshot_event.state_snapshot
        assert snapshot_payload is not None

        restored_conversation = restore_conversation_from_snapshot_payload(snapshot_payload)
        resumed_status = restored_conversation.execute()

        assert isinstance(resumed_status, FinishedStatus)
        assert sorted(message.content for message in restored_conversation.get_messages()) == [
            "item=a",
            "item=b",
        ]


def test_nested_node_turn_snapshots_keep_child_runtime_conversation_identity() -> None:
    child_flow = Flow.from_steps(
        [
            OutputMessageStep(message_template="child"),
            CompleteStep(name="child_end"),
        ],
        name="child_flow",
    )
    parent_flow = Flow.from_steps(
        [
            FlowExecutionStep(flow=child_flow),
            OutputMessageStep(message_template="parent"),
            CompleteStep(name="parent_end"),
        ],
        name="parent_flow",
    )
    conversation = parent_flow.start_conversation()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.NODE_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert {snapshot_event.conversation_id for snapshot_event in state_snapshot_events} == {
        conversation.conversation_id
    }
    assert any(
        snapshot_event.state_snapshot["conversation"]["id"] != conversation.id
        for snapshot_event in state_snapshot_events
    )


def test_state_snapshot_policy_is_inherited_by_nested_agent_steps() -> None:
    conversation = create_nested_agent_step_flow_conversation()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, UserMessageRequestStatus)
    assert snapshot_status_types(state_snapshot_events) == [None, "UserMessageRequestStatus"]
    assert [snapshot_event.conversation_id for snapshot_event in state_snapshot_events] == [
        conversation.conversation_id,
        conversation.conversation_id,
    ]
    assert snapshot_runtime_conversation_ids(state_snapshot_events) == [
        conversation.id,
        conversation.id,
    ]
    assert snapshot_message(state_snapshot_events[-1]) == "agent answer"
