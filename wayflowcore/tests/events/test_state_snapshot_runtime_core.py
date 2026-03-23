# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass

import pytest

from wayflowcore.conversation import Conversation
from wayflowcore.events import Event, EventListener
from wayflowcore.events.event import StateSnapshotEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors._events.event import EventType
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.executors.interrupts.executioninterrupt import InterruptedExecutionStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval, StateSnapshotPolicy
from wayflowcore.flow import Flow
from wayflowcore.property import AnyProperty
from wayflowcore.serialization import dump_conversation_state
from wayflowcore.serialization.serializer import FrozenSerializableDataclass
from wayflowcore.steps import (
    CompleteStep,
    FlowExecutionStep,
    OutputMessageStep,
    ParallelFlowExecutionStep,
    ToolExecutionStep,
    VariableWriteStep,
)
from wayflowcore.tools import ServerTool
from wayflowcore.variable import Variable

from ..test_interrupts import OnEventExecutionInterrupt
from ..testhelpers.state_snapshot_testutils import (
    execute_with_state_snapshots,
    execute_with_state_snapshots_async,
    restore_conversation_from_snapshot_payload,
    snapshot_status_types,
)


class _LiveConversationSnapshotObserver(EventListener):
    def __init__(self, conversation) -> None:
        self.conversation = conversation
        self.live_snapshots: list[dict[str, Any]] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, StateSnapshotEvent):
            self.live_snapshots.append(dump_conversation_state(self.conversation))


def _make_output_conversation():
    return Flow.from_steps(
        [
            OutputMessageStep(message_template="Hello", name="single_step"),
            CompleteStep(name="end"),
        ]
    ).start_conversation()


def _make_tool_flow_conversation():
    return Flow.from_steps(
        [
            ToolExecutionStep(
                tool=ServerTool(
                    name="say_hi",
                    description="Say hi",
                    func=lambda: "hi",
                    input_descriptors=[],
                ),
                name="tool_step",
            ),
            CompleteStep(name="end"),
        ]
    ).start_conversation()


def _make_parent_child_conversation():
    child_flow = Flow.from_steps(
        [
            OutputMessageStep(message_template="child", name="child_message"),
            CompleteStep(name="child_end"),
        ],
        name="child_flow",
    )
    parent_flow = Flow.from_steps(
        [
            FlowExecutionStep(flow=child_flow, name="child_flow_step"),
            OutputMessageStep(message_template="parent", name="parent_message"),
            CompleteStep(name="end"),
        ],
        name="parent_flow",
    )
    return parent_flow.start_conversation()


def _make_parallel_parent_conversation():
    return Flow.from_steps(
        [
            ParallelFlowExecutionStep(
                flows=[
                    Flow.from_steps(
                        [
                            OutputMessageStep(
                                message_template="left",
                                output_mapping={OutputMessageStep.OUTPUT: "left_message"},
                            ),
                            CompleteStep(name="left_end"),
                        ],
                        name="left_child_flow",
                    ),
                    Flow.from_steps(
                        [
                            OutputMessageStep(
                                message_template="right",
                                output_mapping={OutputMessageStep.OUTPUT: "right_message"},
                            ),
                            CompleteStep(name="right_end"),
                        ],
                        name="right_child_flow",
                    ),
                ],
                name="parallel_children",
            ),
            CompleteStep(name="end"),
        ],
        name="parallel_parent_flow",
    ).start_conversation()


def _snapshot_message(snapshot_event: StateSnapshotEvent) -> str | None:
    messages = snapshot_event.state_snapshot["conversation"]["messages"]
    if not messages:
        return None
    return messages[-1].get("content")


def _snapshot_step_histories(snapshot_events: list[StateSnapshotEvent]) -> list[list[str]]:
    return [
        snapshot_event.state_snapshot["execution"]["step_history"]
        for snapshot_event in snapshot_events
    ]


def _execute_tool_flow_with_interval(
    interval: StateSnapshotInterval,
) -> tuple[object, list[StateSnapshotEvent]]:
    return execute_with_state_snapshots(
        _make_tool_flow_conversation(),
        state_snapshot_policy=StateSnapshotPolicy(state_snapshot_interval=interval),
    )


@dataclass(frozen=True)
class _SerializableButNotJson(FrozenSerializableDataclass):
    value: str


class _FailOnTerminalSnapshot(EventListener):
    def __call__(self, event: Event) -> None:
        if not isinstance(event, StateSnapshotEvent):
            return

        execution_status = (event.state_snapshot or {}).get("execution", {}).get("status")
        if execution_status is not None:
            raise RuntimeError("snapshot sink failed")


def test_off_policy_emits_no_state_snapshots() -> None:
    status, state_snapshot_events = execute_with_state_snapshots(
        _make_output_conversation(),
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.OFF
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert state_snapshot_events == []


def test_conversation_turns_emit_opening_and_closing_snapshots() -> None:
    status, state_snapshot_events = execute_with_state_snapshots(
        _make_output_conversation(),
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 2
    assert snapshot_status_types(state_snapshot_events) == [None, "FinishedStatus"]
    assert _snapshot_message(state_snapshot_events[-1]) == "Hello"
    assert all(
        isinstance(snapshot_event.state_snapshot.get("conversation_state"), str)
        for snapshot_event in state_snapshot_events
    )


def test_terminal_snapshot_is_synthesized_before_live_status_commit() -> None:
    conversation = _make_output_conversation()
    collector = []
    observer = _LiveConversationSnapshotObserver(conversation)

    class _Collector(EventListener):
        def __call__(self, event: Event) -> None:
            if isinstance(event, StateSnapshotEvent):
                collector.append(event)

    with register_event_listeners([_Collector(), observer]):
        status = conversation.execute(
            state_snapshot_policy=StateSnapshotPolicy(
                state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
            )
        )

    assert isinstance(status, FinishedStatus)
    assert conversation.status is status
    assert observer.live_snapshots[-1]["execution"]["status"] is None
    assert collector[-1].state_snapshot["execution"]["status"]["type"] == "FinishedStatus"
    assert collector[-1].state_snapshot["execution"]["status_handled"] is False
    assert observer.live_snapshots[-1] != {
        "conversation": collector[-1].state_snapshot["conversation"],
        "execution": collector[-1].state_snapshot["execution"],
    }


def test_interrupted_conversation_turn_emits_terminal_snapshot() -> None:
    status, state_snapshot_events = execute_with_state_snapshots(
        _make_output_conversation(),
        execution_interrupts=[OnEventExecutionInterrupt(EventType.EXECUTION_END)],
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, InterruptedExecutionStatus)
    assert snapshot_status_types(state_snapshot_events) == [None, "InterruptedExecutionStatus"]
    assert state_snapshot_events[-1].state_snapshot["execution"]["status_handled"] is False


def test_node_turns_emit_internal_step_snapshots_and_only_root_turns_are_resumable() -> None:
    status, state_snapshot_events = execute_with_state_snapshots(
        _make_output_conversation(),
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.NODE_TURNS
        ),
    )

    step_histories = [
        snapshot_event.state_snapshot["execution"]["step_history"]
        for snapshot_event in state_snapshot_events
    ]

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) > 2
    assert snapshot_status_types(state_snapshot_events)[0] is None
    assert snapshot_status_types(state_snapshot_events)[-1] == "FinishedStatus"
    assert all(
        status_type is None for status_type in snapshot_status_types(state_snapshot_events)[1:-1]
    )
    assert [] in step_histories
    assert ["__StartStep__"] in step_histories
    assert ["__StartStep__", "single_step"] in step_histories
    assert ["__StartStep__", "single_step", "end"] in step_histories
    assert isinstance(state_snapshot_events[0].state_snapshot.get("conversation_state"), str)
    assert isinstance(state_snapshot_events[-1].state_snapshot.get("conversation_state"), str)
    assert all(
        "conversation_state" not in snapshot_event.state_snapshot
        for snapshot_event in state_snapshot_events[1:-1]
    )


def test_tool_turns_emit_tool_boundary_snapshots_and_only_root_turns_are_resumable() -> None:
    status, state_snapshot_events = _execute_tool_flow_with_interval(
        StateSnapshotInterval.TOOL_TURNS
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 4
    assert snapshot_status_types(state_snapshot_events) == [None, None, None, "FinishedStatus"]
    assert isinstance(state_snapshot_events[0].state_snapshot.get("conversation_state"), str)
    assert isinstance(state_snapshot_events[-1].state_snapshot.get("conversation_state"), str)
    assert all(
        "conversation_state" not in snapshot_event.state_snapshot
        for snapshot_event in state_snapshot_events[1:-1]
    )


def test_all_internal_turns_emit_more_snapshots_than_tool_turns() -> None:
    _, tool_turn_events = _execute_tool_flow_with_interval(StateSnapshotInterval.TOOL_TURNS)
    status, all_internal_turn_events = _execute_tool_flow_with_interval(
        StateSnapshotInterval.ALL_INTERNAL_TURNS
    )

    assert isinstance(status, FinishedStatus)
    assert len(all_internal_turn_events) > len(tool_turn_events)


def test_all_internal_turns_emit_more_snapshots_than_node_turns() -> None:
    _, node_turn_events = _execute_tool_flow_with_interval(StateSnapshotInterval.NODE_TURNS)
    status, all_internal_turn_events = _execute_tool_flow_with_interval(
        StateSnapshotInterval.ALL_INTERNAL_TURNS
    )

    assert isinstance(status, FinishedStatus)
    assert len(all_internal_turn_events) > len(node_turn_events)


def test_all_internal_turns_emit_opening_and_terminal_statuses() -> None:
    status, all_internal_turn_events = _execute_tool_flow_with_interval(
        StateSnapshotInterval.ALL_INTERNAL_TURNS
    )

    assert isinstance(status, FinishedStatus)
    assert snapshot_status_types(all_internal_turn_events)[0] is None
    assert snapshot_status_types(all_internal_turn_events)[-1] == "FinishedStatus"


def test_all_internal_turns_include_node_step_boundaries() -> None:
    status, all_internal_turn_events = _execute_tool_flow_with_interval(
        StateSnapshotInterval.ALL_INTERNAL_TURNS
    )
    step_histories = _snapshot_step_histories(all_internal_turn_events)

    assert isinstance(status, FinishedStatus)
    assert ["__StartStep__"] in step_histories
    assert ["__StartStep__", "tool_step"] in step_histories
    assert ["__StartStep__", "tool_step", "end"] in step_histories


def test_all_internal_turns_keep_only_root_turns_resumable() -> None:
    status, all_internal_turn_events = _execute_tool_flow_with_interval(
        StateSnapshotInterval.ALL_INTERNAL_TURNS
    )

    assert isinstance(status, FinishedStatus)
    assert isinstance(all_internal_turn_events[0].state_snapshot.get("conversation_state"), str)
    assert isinstance(all_internal_turn_events[-1].state_snapshot.get("conversation_state"), str)
    assert all(
        "conversation_state" not in snapshot_event.state_snapshot
        for snapshot_event in all_internal_turn_events[1:-1]
    )


@pytest.mark.anyio
async def test_execute_async_emits_conversation_turn_snapshots() -> None:
    status, state_snapshot_events = await execute_with_state_snapshots_async(
        _make_output_conversation(),
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert snapshot_status_types(state_snapshot_events) == [None, "FinishedStatus"]


def test_parallel_conversation_turn_snapshots_stay_on_the_root_conversation() -> None:
    conversation = _make_parallel_parent_conversation()
    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert snapshot_status_types(state_snapshot_events) == [None, "FinishedStatus"]
    assert [snapshot_event.conversation_id for snapshot_event in state_snapshot_events] == [
        conversation.conversation_id,
        conversation.conversation_id,
    ]
    assert [
        snapshot_event.state_snapshot["conversation"]["id"]
        for snapshot_event in state_snapshot_events
    ] == [conversation.id, conversation.id]

    restored_conversation = restore_conversation_from_snapshot_payload(
        state_snapshot_events[-1].state_snapshot
    )
    resumed_status = restored_conversation.execute()

    assert isinstance(resumed_status, FinishedStatus)
    assert sorted(message.content for message in restored_conversation.get_messages()) == [
        "left",
        "right",
    ]


def test_nested_conversation_turn_snapshots_stay_on_the_root_conversation() -> None:
    conversation = _make_parent_child_conversation()
    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 2
    assert snapshot_status_types(state_snapshot_events) == [None, "FinishedStatus"]
    assert [snapshot_event.conversation_id for snapshot_event in state_snapshot_events] == [
        conversation.conversation_id,
        conversation.conversation_id,
    ]
    assert [
        snapshot_event.state_snapshot["conversation"]["id"]
        for snapshot_event in state_snapshot_events
    ] == [conversation.id, conversation.id]
    assert _snapshot_message(state_snapshot_events[-1]) == "parent"


def test_nested_node_turn_snapshots_can_capture_child_runtime_conversation_ids() -> None:
    conversation = _make_parent_child_conversation()
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
    assert isinstance(state_snapshot_events[0].state_snapshot.get("conversation_state"), str)
    assert isinstance(state_snapshot_events[-1].state_snapshot.get("conversation_state"), str)
    assert all(
        "conversation_state" not in snapshot_event.state_snapshot
        for snapshot_event in state_snapshot_events[1:-1]
    )
    assert any(
        snapshot_event.state_snapshot["conversation"]["id"] != conversation.id
        for snapshot_event in state_snapshot_events[1:-1]
    )


def test_state_snapshot_emits_variable_state_for_successful_flow_execution() -> None:
    custom_variable = Variable(name="custom", type=AnyProperty())
    conversation = Flow.from_steps(
        [
            VariableWriteStep(
                variable=custom_variable,
                input_mapping={VariableWriteStep.VALUE: custom_variable.name},
            ),
            OutputMessageStep(message_template="done"),
            CompleteStep(name="end"),
        ],
        variables=[custom_variable],
    ).start_conversation(inputs={custom_variable.name: "stored-value"})

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS,
            include_variable_state=True,
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert state_snapshot_events[0].variable_state == {"custom": None}
    assert state_snapshot_events[-1].variable_state == {"custom": "stored-value"}


def test_state_snapshot_emission_propagates_extra_state_builder_failures() -> None:
    output_conversation = _make_output_conversation()

    def broken_builder(_conversation: Conversation) -> dict[str, object]:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        output_conversation.execute(
            state_snapshot_policy=StateSnapshotPolicy(
                state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS,
                extra_state_builder=broken_builder,
            )
        )

    assert output_conversation.get_last_message() is None


def test_state_snapshot_emission_rejects_non_strict_json_extra_state() -> None:
    output_conversation = _make_output_conversation()

    with pytest.raises(TypeError, match="Extra snapshot state .* strict JSON-serializable"):
        output_conversation.execute(
            state_snapshot_policy=StateSnapshotPolicy(
                state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS,
                extra_state_builder=lambda _conversation: {"ui": {"preview_count": float("nan")}},
            )
        )

    assert output_conversation.get_last_message() is None


def test_state_snapshot_emission_propagates_unserializable_variable_state() -> None:
    custom_variable = Variable(name="custom", type=AnyProperty())
    conversation = Flow.from_steps(
        [
            VariableWriteStep(
                variable=custom_variable,
                input_mapping={VariableWriteStep.VALUE: custom_variable.name},
            ),
            OutputMessageStep(message_template="done"),
            CompleteStep(name="end"),
        ],
        variables=[custom_variable],
    ).start_conversation(inputs={custom_variable.name: _SerializableButNotJson(value="x")})

    with pytest.raises(TypeError, match="Variable 'custom' contains a non-JSON-serializable"):
        conversation.execute(
            state_snapshot_policy=StateSnapshotPolicy(
                state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS,
                include_variable_state=True,
            )
        )

    assert conversation.get_last_message() is not None
    assert conversation.get_last_message().content == "done"


def test_state_snapshot_listener_failures_propagate_to_the_caller() -> None:
    output_conversation = _make_output_conversation()

    with register_event_listeners([_FailOnTerminalSnapshot()]):
        with pytest.raises(RuntimeError, match="snapshot sink failed"):
            output_conversation.execute(
                state_snapshot_policy=StateSnapshotPolicy(
                    state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
                )
            )

    assert output_conversation.get_last_message() is not None
    assert output_conversation.get_last_message().content == "Hello"
