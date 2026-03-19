# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest

from wayflowcore.agent import Agent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors._events.event import EventType
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.executors.interrupts.executioninterrupt import InterruptedExecutionStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval, StateSnapshotPolicy

from ..conftest import disable_streaming
from ..test_interrupts import OnEventExecutionInterrupt
from ..testhelpers.dummy import DummyModel
from ..testhelpers.statesnapshots import (
    SnapshotCollector,
    create_agent_conversation,
    create_output_flow_conversation,
    create_tool_calling_agent_conversation,
    create_tool_flow_conversation,
    execute_with_state_snapshots,
    execute_with_state_snapshots_async,
    snapshot_status_types,
    snapshot_step_histories,
)


class _SerializableDummyModel(DummyModel):
    @property
    def config(self) -> dict[str, object]:
        return {"model_id": self.model_id}


@pytest.mark.parametrize(
    (
        "conversation_factory",
        "expected_status_class",
        "expected_status_types",
        "expected_snapshot_count",
        "expected_curr_iters",
    ),
    [
        pytest.param(
            create_output_flow_conversation,
            FinishedStatus,
            [None, None, None, None, None, None, None, "FinishedStatus"],
            8,
            None,
            id="flow",
        ),
        pytest.param(
            create_agent_conversation,
            UserMessageRequestStatus,
            [None, None, None, "UserMessageRequestStatus"],
            4,
            [0, 1],
            id="agent",
        ),
    ],
)
def test_node_turn_policy_tracks_flow_steps_and_agent_iterations(
    conversation_factory,
    expected_status_class,
    expected_status_types: list[str | None],
    expected_snapshot_count: int,
    expected_curr_iters: list[int] | None,
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.NODE_TURNS
        ),
    )

    assert isinstance(status, expected_status_class)
    assert len(state_snapshot_events) == expected_snapshot_count
    assert snapshot_status_types(state_snapshot_events) == expected_status_types
    if expected_curr_iters is not None:
        assert [
            state_snapshot_events[1].state_snapshot["execution"]["curr_iter"],
            state_snapshot_events[2].state_snapshot["execution"]["curr_iter"],
        ] == expected_curr_iters


@pytest.mark.anyio
@pytest.mark.parametrize(
    (
        "conversation_factory",
        "expected_status_class",
        "expected_status_types",
        "expected_snapshot_count",
        "expected_curr_iters",
    ),
    [
        pytest.param(
            create_output_flow_conversation,
            FinishedStatus,
            [None, None, None, None, None, None, None, "FinishedStatus"],
            8,
            None,
            id="flow",
        ),
        pytest.param(
            create_agent_conversation,
            UserMessageRequestStatus,
            [None, None, None, "UserMessageRequestStatus"],
            4,
            [0, 1],
            id="agent",
        ),
    ],
)
async def test_node_turn_policy_tracks_flow_steps_and_agent_iterations_async(
    conversation_factory,
    expected_status_class,
    expected_status_types: list[str | None],
    expected_snapshot_count: int,
    expected_curr_iters: list[int] | None,
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = await execute_with_state_snapshots_async(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.NODE_TURNS
        ),
    )

    assert isinstance(status, expected_status_class)
    assert len(state_snapshot_events) == expected_snapshot_count
    assert snapshot_status_types(state_snapshot_events) == expected_status_types
    if expected_curr_iters is not None:
        assert [
            state_snapshot_events[1].state_snapshot["execution"]["curr_iter"],
            state_snapshot_events[2].state_snapshot["execution"]["curr_iter"],
        ] == expected_curr_iters


@pytest.mark.parametrize(
    ("conversation_factory", "interrupt_event"),
    [
        pytest.param(create_output_flow_conversation, EventType.STEP_EXECUTION_START, id="flow"),
        pytest.param(create_agent_conversation, EventType.GENERATION_START, id="agent"),
    ],
)
def test_node_turn_policy_keeps_partial_progress_when_interrupted_mid_turn(
    conversation_factory,
    interrupt_event: EventType,
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        execution_interrupts=[OnEventExecutionInterrupt(interrupt_event)],
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.NODE_TURNS
        ),
    )

    assert isinstance(status, InterruptedExecutionStatus)
    assert snapshot_status_types(state_snapshot_events) == [None, None]


def test_flow_node_turn_policy_uses_iteration_start_and_end_boundaries() -> None:
    conversation = create_output_flow_conversation()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.NODE_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert snapshot_step_histories(state_snapshot_events) == [
        [],
        [],
        ["__StartStep__"],
        ["__StartStep__"],
        ["__StartStep__", "step_0"],
        ["__StartStep__", "step_0"],
        ["__StartStep__", "step_0", "end"],
        ["__StartStep__", "step_0", "end"],
    ]


def test_internal_snapshots_do_not_reuse_the_previous_turn_status() -> None:
    llm = _SerializableDummyModel()
    llm.set_next_output(["Hello from agent", "Hello again"])
    conversation = Agent(llm=llm).start_conversation()
    conversation.append_user_message("Hi")
    collector = SnapshotCollector()
    policy = StateSnapshotPolicy(state_snapshot_interval=StateSnapshotInterval.NODE_TURNS)

    with register_event_listeners([collector]):
        first_status = conversation.execute(state_snapshot_policy=policy)
        assert isinstance(first_status, UserMessageRequestStatus)

        first_status.submit_user_response("Continue")
        second_status = conversation.execute(state_snapshot_policy=policy)

    assert isinstance(second_status, UserMessageRequestStatus)
    assert len(collector.state_snapshot_events) == 8

    second_turn_internal_snapshots = collector.state_snapshot_events[5:7]
    assert snapshot_status_types(second_turn_internal_snapshots) == [None, None]
    assert all(
        snapshot_event.state_snapshot["execution"]["status_handled"] is False
        for snapshot_event in second_turn_internal_snapshots
    )


@pytest.mark.parametrize(
    (
        "conversation_factory",
        "execution_interrupts",
        "execution_context",
        "expected_status_class",
        "expected_status_types",
    ),
    [
        pytest.param(
            lambda: create_tool_flow_conversation(lambda: "hi"),
            None,
            None,
            FinishedStatus,
            [None, None, None, "FinishedStatus"],
            id="flow-success",
        ),
        pytest.param(
            create_tool_calling_agent_conversation,
            [OnEventExecutionInterrupt(EventType.TOOL_CALL_END)],
            disable_streaming(),
            InterruptedExecutionStatus,
            [None, None, None],
            id="agent-tool-end-interrupt",
        ),
    ],
)
def test_tool_turn_policy_records_real_tool_boundaries(
    conversation_factory,
    execution_interrupts,
    execution_context,
    expected_status_class,
    expected_status_types: list[str | None],
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        execution_interrupts=execution_interrupts,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.TOOL_TURNS
        ),
        execution_context=execution_context,
    )

    assert isinstance(status, expected_status_class)
    assert snapshot_status_types(state_snapshot_events) == expected_status_types


@pytest.mark.anyio
@pytest.mark.parametrize(
    (
        "conversation_factory",
        "execution_interrupts",
        "execution_context",
        "expected_status_class",
        "expected_status_types",
    ),
    [
        pytest.param(
            lambda: create_tool_flow_conversation(lambda: "hi"),
            None,
            None,
            FinishedStatus,
            [None, None, None, "FinishedStatus"],
            id="flow-success",
        ),
        pytest.param(
            create_tool_calling_agent_conversation,
            [OnEventExecutionInterrupt(EventType.TOOL_CALL_END)],
            disable_streaming(),
            InterruptedExecutionStatus,
            [None, None, None],
            id="agent-tool-end-interrupt",
        ),
    ],
)
async def test_tool_turn_policy_records_real_tool_boundaries_async(
    conversation_factory,
    execution_interrupts,
    execution_context,
    expected_status_class,
    expected_status_types: list[str | None],
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = await execute_with_state_snapshots_async(
        conversation,
        execution_interrupts=execution_interrupts,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.TOOL_TURNS
        ),
        execution_context=execution_context,
    )

    assert isinstance(status, expected_status_class)
    assert snapshot_status_types(state_snapshot_events) == expected_status_types


def test_all_internal_turn_policy_combines_node_and_tool_boundaries() -> None:
    conversation = create_tool_flow_conversation(lambda: "hi")

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.ALL_INTERNAL_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 10
    assert snapshot_status_types(state_snapshot_events) == [None] * 9 + ["FinishedStatus"]


@pytest.mark.anyio
async def test_all_internal_turn_policy_combines_node_and_tool_boundaries_async() -> None:
    conversation = create_tool_flow_conversation(lambda: "hi")

    status, state_snapshot_events = await execute_with_state_snapshots_async(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.ALL_INTERNAL_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 10
    assert snapshot_status_types(state_snapshot_events) == [None] * 9 + ["FinishedStatus"]


@pytest.mark.parametrize(
    ("interval", "expected_status_types"),
    [
        pytest.param(
            StateSnapshotInterval.CONVERSATION_TURNS,
            [None, "FinishedStatus"],
            id="conversation_turns",
        ),
        pytest.param(
            StateSnapshotInterval.TOOL_TURNS,
            [None, None, None, "FinishedStatus"],
            id="tool_turns",
        ),
        pytest.param(
            StateSnapshotInterval.NODE_TURNS,
            [None, None, None, None, None, None, None, "FinishedStatus"],
            id="node_turns",
        ),
        pytest.param(
            StateSnapshotInterval.ALL_INTERNAL_TURNS,
            [None, None, None, None, None, None, None, None, None, "FinishedStatus"],
            id="all_internal_turns",
        ),
    ],
)
def test_snapshot_interval_policies_include_conversation_turns_cumulatively(
    interval: StateSnapshotInterval,
    expected_status_types: list[str | None],
) -> None:
    conversation = create_tool_flow_conversation(lambda: "hi")

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(state_snapshot_interval=interval),
    )

    assert isinstance(status, FinishedStatus)
    assert snapshot_status_types(state_snapshot_events) == expected_status_types
