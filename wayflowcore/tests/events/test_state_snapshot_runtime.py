# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import threading
from contextlib import nullcontext
from typing import Sequence

import pytest

from wayflowcore.agent import Agent
from wayflowcore.conversation import Conversation
from wayflowcore.events.event import Event, StateSnapshotEvent
from wayflowcore.events.eventlistener import EventListener, register_event_listeners
from wayflowcore.executors._events.event import EventType
from wayflowcore.executors._executionstate import ConversationExecutionState
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.executors.interrupts.executioninterrupt import (
    ExecutionInterrupt,
    InterruptedExecutionStatus,
    _NullExecutionInterrupt,
)
from wayflowcore.executors.statesnapshotpolicy import (
    StateSnapshotInterval,
    StateSnapshotPolicy,
)
from wayflowcore.flow import Flow
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.property import AnyProperty
from wayflowcore.serialization.serializer import SerializableNeedToBeImplementedMixin
from wayflowcore.steps import (
    AgentExecutionStep,
    CompleteStep,
    FlowExecutionStep,
    OutputMessageStep,
    ToolExecutionStep,
    VariableWriteStep,
)
from wayflowcore.swarm import Swarm
from wayflowcore.tools import ServerTool, ToolRequest, tool
from wayflowcore.variable import Variable

from ..conftest import disable_streaming
from ..test_interrupts import OnEventExecutionInterrupt
from ..testhelpers.dummy import DummyModel

# Runtime snapshot tests stay focused on emission semantics. Event payload
# mapping and serialization details live in dedicated tracing/serialization
# suites.


class SnapshotCollector(EventListener):
    def __init__(self) -> None:
        self.state_snapshot_events: list[StateSnapshotEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, StateSnapshotEvent):
            self.state_snapshot_events.append(event)


class MutatingExecutionEndInterrupt(SerializableNeedToBeImplementedMixin, _NullExecutionInterrupt):
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.count = 0
        super().__init__()

    def _on_execution_end(
        self,
        state: ConversationExecutionState,
        conversation: Conversation,
    ) -> InterruptedExecutionStatus | None:
        conversation.inputs["preview_count"] = conversation.inputs.get("preview_count", 0) + 1
        self.count += 1
        return None


class WorkerExecutionEndInterrupt(SerializableNeedToBeImplementedMixin, _NullExecutionInterrupt):
    def __init__(self) -> None:
        self.triggered = False
        super().__init__()

    def _on_execution_end(
        self,
        state: ConversationExecutionState,
        conversation: Conversation,
    ) -> InterruptedExecutionStatus | None:
        if self.triggered:
            return None
        if getattr(conversation.component, "name", None) != "worker":
            return None

        self.triggered = True
        return InterruptedExecutionStatus(
            interrupter=self,
            reason="worker execution end",
            _conversation_id=conversation.id,
        )


class _UnserializableVariableValue:
    pass


def _create_output_flow_conversation(message: str = "Hello") -> Conversation:
    flow = Flow.from_steps(
        [
            OutputMessageStep(message_template=message),
            CompleteStep(name="end"),
        ]
    )
    return flow.start_conversation()


def _create_agent_conversation(message: str = "Hello from agent") -> Conversation:
    llm = DummyModel()
    llm.set_next_output(message)
    conversation = Agent(llm=llm).start_conversation()
    conversation.append_user_message("Hi")
    return conversation


def _create_tool_calling_agent_conversation() -> Conversation:
    @tool
    def do_nothing_tool() -> str:
        """Do nothing tool."""
        return "Tool called successfully"

    llm = DummyModel()
    llm.set_next_output(
        {
            "Please use the do_nothing_tool": Message(
                message_type=MessageType.TOOL_REQUEST,
                content="I am calling the do nothing tool",
                tool_requests=[ToolRequest("do_nothing_tool", {}, "tc1")],
            )
        }
    )
    conversation = Agent(llm=llm, tools=[do_nothing_tool], max_iterations=10).start_conversation()
    conversation.append_user_message("Please use the do_nothing_tool")
    return conversation


def _create_send_message_request(recipient_name: str, message: str) -> Message:
    return Message(
        content="",
        message_type=MessageType.TOOL_REQUEST,
        tool_requests=[
            ToolRequest(
                name="send_message",
                args={"recipient": recipient_name, "message": message},
            )
        ],
    )


def _create_nested_agent_step_flow_conversation() -> Conversation:
    llm = DummyModel()
    llm.set_next_output("agent answer")
    child_agent = Agent(llm=llm)
    conversation = Flow.from_steps(
        [AgentExecutionStep(agent=child_agent), CompleteStep(name="end")]
    ).start_conversation()
    conversation.append_user_message("dummy")
    return conversation


def _create_nested_managerworkers_flow_conversation() -> Conversation:
    llm = DummyModel()
    worker = Agent(llm=llm, name="worker", description="worker")
    group = ManagerWorkers(group_manager=llm, workers=[worker])
    llm.set_next_output(
        [
            _create_send_message_request("worker", "Do it"),
            "worker answer",
            "manager final answer",
        ]
    )

    conversation = Flow.from_steps(
        [AgentExecutionStep(agent=group), CompleteStep(name="end")]
    ).start_conversation()
    conversation.append_user_message("dummy")
    return conversation


def _create_managerworkers_conversation() -> Conversation:
    llm = DummyModel()
    worker = Agent(llm=llm, name="worker", description="worker")
    group = ManagerWorkers(group_manager=llm, workers=[worker])
    llm.set_next_output(
        [
            _create_send_message_request("worker", "Do it"),
            "worker answer",
            "manager final answer",
        ]
    )

    conversation = group.start_conversation()
    conversation.append_user_message("dummy")
    return conversation


def _create_nested_swarm_flow_conversation() -> Conversation:
    llm = DummyModel()
    first_agent = Agent(llm=llm, name="agent1", description="agent1")
    second_agent = Agent(llm=llm, name="agent2", description="agent2")
    swarm = Swarm(
        first_agent=first_agent,
        relationships=[(first_agent, second_agent), (second_agent, first_agent)],
    )
    llm.set_next_output(
        [
            _create_send_message_request("agent2", "Do it"),
            "agent2 answer",
            "agent1 final answer",
        ]
    )

    conversation = Flow.from_steps(
        [AgentExecutionStep(agent=swarm), CompleteStep(name="end")]
    ).start_conversation()
    conversation.append_user_message("dummy")
    return conversation


def _snapshot_status_types(snapshot_events: Sequence[StateSnapshotEvent]) -> list[str | None]:
    return [
        (
            snapshot_event.state_snapshot["execution"]["status"]["type"]
            if snapshot_event.state_snapshot["execution"]["status"] is not None
            else None
        )
        for snapshot_event in snapshot_events
    ]


def _execute_with_state_snapshots(
    conversation: Conversation,
    *,
    state_snapshot_policy: StateSnapshotPolicy,
    execution_interrupts: Sequence[ExecutionInterrupt] | None = None,
    use_disable_streaming: bool = False,
) -> tuple[object, list[StateSnapshotEvent]]:
    collector = SnapshotCollector()
    streaming_context = disable_streaming() if use_disable_streaming else nullcontext()

    with streaming_context:
        with register_event_listeners([collector]):
            status = conversation.execute(
                execution_interrupts=execution_interrupts,
                state_snapshot_policy=state_snapshot_policy,
            )

    return status, collector.state_snapshot_events


@pytest.mark.parametrize(
    (
        "conversation_factory",
        "expected_status_class",
        "expected_status_type",
        "expected_message",
    ),
    [
        pytest.param(
            _create_output_flow_conversation,
            FinishedStatus,
            "FinishedStatus",
            "Hello",
            id="flow",
        ),
        pytest.param(
            _create_agent_conversation,
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

    status, state_snapshot_events = _execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, expected_status_class)
    assert _snapshot_status_types(state_snapshot_events) == [None, expected_status_type]
    assert (
        state_snapshot_events[-1].state_snapshot["conversation"]["messages"][-1]["content"]
        == expected_message
    )
    assert state_snapshot_events[-1].state_snapshot["execution"]["status_handled"] is False


@pytest.mark.parametrize(
    ("conversation_factory", "expected_status_class"),
    [
        pytest.param(_create_output_flow_conversation, FinishedStatus, id="flow"),
        pytest.param(_create_agent_conversation, UserMessageRequestStatus, id="agent"),
    ],
)
def test_off_policy_disables_state_snapshot_emission(
    conversation_factory,
    expected_status_class,
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = _execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.OFF
        ),
    )

    assert isinstance(status, expected_status_class)
    assert state_snapshot_events == []


@pytest.mark.parametrize(
    ("conversation_factory", "expected_message"),
    [
        pytest.param(_create_output_flow_conversation, "Hello", id="flow"),
        pytest.param(_create_agent_conversation, "Hello from agent", id="agent"),
    ],
)
def test_conversation_turn_policy_records_interrupted_turn_end_checkpoints(
    conversation_factory,
    expected_message: str,
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = _execute_with_state_snapshots(
        conversation,
        execution_interrupts=[OnEventExecutionInterrupt(EventType.EXECUTION_END)],
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, InterruptedExecutionStatus)
    assert _snapshot_status_types(state_snapshot_events) == [None, "InterruptedExecutionStatus"]
    assert (
        state_snapshot_events[-1].state_snapshot["conversation"]["messages"][-1]["content"]
        == expected_message
    )
    assert state_snapshot_events[-1].state_snapshot["execution"]["status_handled"] is False


def test_conversation_turn_policy_keeps_only_the_opening_checkpoint_when_turn_raises() -> None:
    def explode() -> str:
        raise RuntimeError("boom")

    conversation = Flow.from_steps(
        [
            ToolExecutionStep(
                tool=ServerTool(
                    name="explode",
                    description="Raise an error",
                    func=explode,
                    input_descriptors=[],
                )
            ),
            CompleteStep(name="end"),
        ]
    ).start_conversation()
    collector = SnapshotCollector()

    with register_event_listeners([collector]):
        with pytest.raises(RuntimeError, match="boom"):
            conversation.execute(
                state_snapshot_policy=StateSnapshotPolicy(
                    state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
                )
            )

    assert len(collector.state_snapshot_events) == 1
    assert collector.state_snapshot_events[0].state_snapshot["execution"]["status"] is None


def test_conversation_turn_policy_reflects_real_interrupt_side_effects_once() -> None:
    conversation = _create_output_flow_conversation()
    interrupt = MutatingExecutionEndInterrupt()

    status, state_snapshot_events = _execute_with_state_snapshots(
        conversation,
        execution_interrupts=[interrupt],
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert interrupt.count == 1
    assert conversation.inputs["preview_count"] == 1
    assert _snapshot_status_types(state_snapshot_events) == [None, "FinishedStatus"]
    assert state_snapshot_events[-1].state_snapshot["conversation"]["inputs"]["preview_count"] == 1


def test_parent_multi_agent_does_not_emit_turn_end_snapshot_when_child_turn_is_interrupted() -> (
    None
):
    conversation = _create_managerworkers_conversation()

    status, state_snapshot_events = _execute_with_state_snapshots(
        conversation,
        execution_interrupts=[WorkerExecutionEndInterrupt()],
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
        use_disable_streaming=True,
    )

    assert isinstance(status, InterruptedExecutionStatus)

    snapshot_events_by_conversation_id: dict[str, list[StateSnapshotEvent]] = {}
    for snapshot_event in state_snapshot_events:
        snapshot_events_by_conversation_id.setdefault(
            snapshot_event.conversation_id,
            [],
        ).append(snapshot_event)

    parent_multi_agent_snapshot_events = next(
        snapshot_events
        for snapshot_events in snapshot_events_by_conversation_id.values()
        if snapshot_events[0].state_snapshot["conversation"]["component_type"] == "ManagerWorkers"
    )

    assert "InterruptedExecutionStatus" not in _snapshot_status_types(
        parent_multi_agent_snapshot_events
    )


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
            _create_output_flow_conversation,
            FinishedStatus,
            [None, None, None, None, None, None, "FinishedStatus"],
            7,
            None,
            id="flow",
        ),
        pytest.param(
            _create_agent_conversation,
            UserMessageRequestStatus,
            [None, None, "UserMessageRequestStatus"],
            3,
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

    status, state_snapshot_events = _execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.NODE_TURNS
        ),
    )

    # NODE_TURNS means step start/end checkpoints for flows and iteration
    # start/end checkpoints for agents, plus the final turn-end checkpoint.
    # Flow.from_steps(...) also inserts an internal StartStep, so the flow case
    # includes start/end checkpoints for that step too.
    assert isinstance(status, expected_status_class)
    assert len(state_snapshot_events) == expected_snapshot_count
    assert _snapshot_status_types(state_snapshot_events) == expected_status_types
    if expected_curr_iters is not None:
        assert [
            state_snapshot_events[0].state_snapshot["execution"]["curr_iter"],
            state_snapshot_events[1].state_snapshot["execution"]["curr_iter"],
        ] == expected_curr_iters


@pytest.mark.parametrize(
    ("conversation_factory", "interrupt_event"),
    [
        pytest.param(_create_output_flow_conversation, EventType.STEP_EXECUTION_START, id="flow"),
        pytest.param(_create_agent_conversation, EventType.GENERATION_START, id="agent"),
    ],
)
def test_node_turn_policy_keeps_partial_progress_when_interrupted_mid_turn(
    conversation_factory,
    interrupt_event: EventType,
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = _execute_with_state_snapshots(
        conversation,
        execution_interrupts=[OnEventExecutionInterrupt(interrupt_event)],
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.NODE_TURNS
        ),
    )

    assert isinstance(status, InterruptedExecutionStatus)
    assert _snapshot_status_types(state_snapshot_events) == [None]


def test_internal_snapshots_do_not_reuse_the_previous_turn_status() -> None:
    llm = DummyModel()
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
    assert len(collector.state_snapshot_events) == 6

    second_turn_internal_snapshots = collector.state_snapshot_events[3:5]
    assert _snapshot_status_types(second_turn_internal_snapshots) == [None, None]
    assert all(
        snapshot_event.state_snapshot["execution"]["status_handled"] is False
        for snapshot_event in second_turn_internal_snapshots
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

    status, state_snapshot_events = _execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 4
    assert {snapshot_event.conversation_id for snapshot_event in state_snapshot_events} == {
        conversation.conversation_id
    }


def test_state_snapshot_policy_is_inherited_by_nested_agent_steps() -> None:
    conversation = _create_nested_agent_step_flow_conversation()

    status, state_snapshot_events = _execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    nested_conversation_id = state_snapshot_events[1].conversation_id

    # A parent flow keeps its own opening/closing checkpoints, while the nested
    # agent contributes its own opening/closing pair under the child
    # conversation id.
    assert isinstance(status, UserMessageRequestStatus)
    assert _snapshot_status_types(state_snapshot_events) == [
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
    assert (
        state_snapshot_events[-1].state_snapshot["conversation"]["messages"][-1]["content"]
        == "agent answer"
    )


@pytest.mark.parametrize(
    (
        "conversation_factory",
        "expected_multi_agent_component_type",
        "expected_child_message",
        "expected_parent_message",
    ),
    [
        pytest.param(
            _create_nested_managerworkers_flow_conversation,
            "ManagerWorkers",
            "worker answer",
            "manager final answer",
            id="managerworkers",
        ),
        pytest.param(
            _create_nested_swarm_flow_conversation,
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

    status, state_snapshot_events = _execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, UserMessageRequestStatus)
    assert len(state_snapshot_events) == 14

    snapshot_events_by_conversation_id: dict[str, list[StateSnapshotEvent]] = {}
    for snapshot_event in state_snapshot_events:
        snapshot_events_by_conversation_id.setdefault(
            snapshot_event.conversation_id,
            [],
        ).append(snapshot_event)

    # A nested multi-agent turn has four independent snapshot streams:
    # the outer flow, the parent multi-agent conversation, the manager/main
    # thread agent conversation (which runs twice), and the delegated child.
    assert len(snapshot_events_by_conversation_id) == 4

    flow_snapshot_events = snapshot_events_by_conversation_id[conversation.conversation_id]
    parent_multi_agent_snapshot_events = next(
        snapshot_events
        for snapshot_events in snapshot_events_by_conversation_id.values()
        if snapshot_events[0].state_snapshot["conversation"]["component_type"]
        == expected_multi_agent_component_type
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

    assert _snapshot_status_types(flow_snapshot_events) == [None, "UserMessageRequestStatus"]
    assert (
        flow_snapshot_events[-1].state_snapshot["conversation"]["messages"][-1]["content"]
        == expected_parent_message
    )

    # The parent multi-agent conversation records checkpoints each time control
    # enters or returns from a child turn, which is what lets a UI reconstruct
    # the parent-level progress independently from the child conversations.
    assert _snapshot_status_types(parent_multi_agent_snapshot_events) == [
        None,
        "ToolRequestStatus",
        None,
        "UserMessageRequestStatus",
        None,
        "UserMessageRequestStatus",
    ]
    assert (
        parent_multi_agent_snapshot_events[4].state_snapshot["conversation"]["messages"][-1][
            "content"
        ]
        == expected_child_message
    )
    assert (
        parent_multi_agent_snapshot_events[-1].state_snapshot["conversation"]["messages"][-1][
            "content"
        ]
        == expected_parent_message
    )

    # The manager/main thread agent conversation spans two execution turns:
    # one that delegates and one that resumes after the child reply.
    assert _snapshot_status_types(manager_thread_snapshot_events) == [
        None,
        "ToolRequestStatus",
        None,
        "UserMessageRequestStatus",
    ]
    assert (
        manager_thread_snapshot_events[2].state_snapshot["conversation"]["messages"][-1]["content"]
        == expected_child_message
    )
    assert (
        manager_thread_snapshot_events[-1].state_snapshot["conversation"]["messages"][-1]["content"]
        == expected_parent_message
    )

    assert _snapshot_status_types(delegated_agent_snapshot_events) == [
        None,
        "UserMessageRequestStatus",
    ]
    assert (
        delegated_agent_snapshot_events[-1].state_snapshot["conversation"]["messages"][-1][
            "content"
        ]
        == expected_child_message
    )


def test_state_snapshot_emission_survives_broken_extra_state_builder() -> None:
    def broken_builder(_conversation: Conversation) -> dict[str, object]:
        raise RuntimeError("boom")

    conversation = _create_output_flow_conversation()

    status, state_snapshot_events = _execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS,
            extra_state_builder=broken_builder,
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 2
    assert all(snapshot_event.extra_state is None for snapshot_event in state_snapshot_events)


def test_state_snapshot_emission_survives_unserializable_variable_state() -> None:
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
    ).start_conversation(inputs={custom_variable.name: _UnserializableVariableValue()})

    status, state_snapshot_events = _execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS,
            include_variable_state=True,
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 2
    assert state_snapshot_events[0].variable_state == {"custom": None}
    assert state_snapshot_events[-1].variable_state is None
    assert (
        state_snapshot_events[-1].state_snapshot["conversation"]["messages"][-1]["content"]
        == "done"
    )


@pytest.mark.parametrize(
    (
        "conversation_factory",
        "execution_interrupts",
        "use_disable_streaming",
        "expected_status_class",
        "expected_status_types",
    ),
    [
        pytest.param(
            lambda: Flow.from_steps(
                [
                    ToolExecutionStep(
                        tool=ServerTool(
                            name="say_hi",
                            description="Say hi",
                            func=lambda: "hi",
                            input_descriptors=[],
                        )
                    ),
                    CompleteStep(name="end"),
                ]
            ).start_conversation(),
            None,
            False,
            FinishedStatus,
            [None, None, "FinishedStatus"],
            id="flow-success",
        ),
        pytest.param(
            lambda: _create_tool_calling_agent_conversation(),
            [OnEventExecutionInterrupt(EventType.TOOL_CALL_END)],
            True,
            InterruptedExecutionStatus,
            [None, None],
            id="agent-tool-end-interrupt",
        ),
    ],
)
def test_tool_turn_policy_records_real_tool_boundaries(
    conversation_factory,
    execution_interrupts: Sequence[ExecutionInterrupt] | None,
    use_disable_streaming: bool,
    expected_status_class,
    expected_status_types: list[str | None],
) -> None:
    conversation = conversation_factory()

    status, state_snapshot_events = _execute_with_state_snapshots(
        conversation,
        execution_interrupts=execution_interrupts,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.TOOL_TURNS
        ),
        use_disable_streaming=use_disable_streaming,
    )

    assert isinstance(status, expected_status_class)
    assert _snapshot_status_types(state_snapshot_events) == expected_status_types
