# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import threading
from contextlib import AbstractContextManager, nullcontext
from typing import Any, Callable, Sequence

from wayflowcore.agent import Agent
from wayflowcore.conversation import Conversation
from wayflowcore.events.event import Event, StateSnapshotEvent
from wayflowcore.events.eventlistener import EventListener, register_event_listeners
from wayflowcore.executors._executionstate import ConversationExecutionState
from wayflowcore.executors.interrupts.executioninterrupt import (
    ExecutionInterrupt,
    InterruptedExecutionStatus,
    _NullExecutionInterrupt,
)
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval, StateSnapshotPolicy
from wayflowcore.flow import Flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.property import AnyProperty, StringProperty
from wayflowcore.serialization.serializer import SerializableNeedToBeImplementedMixin
from wayflowcore.steps import (
    AgentExecutionStep,
    CompleteStep,
    OutputMessageStep,
    ToolExecutionStep,
    VariableWriteStep,
)
from wayflowcore.tools import ServerTool, ToolRequest, tool
from wayflowcore.variable import Variable

from .dummy import DummyModel


class SnapshotCollector(EventListener):
    def __init__(self) -> None:
        self.state_snapshot_events: list[StateSnapshotEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, StateSnapshotEvent):
            self.state_snapshot_events.append(event)


def snapshot_status_types(snapshot_events: Sequence[Any]) -> list[str | None]:
    return [
        status["type"] if (status := snapshot_event.state_snapshot["execution"]["status"]) else None
        for snapshot_event in snapshot_events
    ]


def snapshot_message(snapshot_event: Any) -> str | None:
    messages = snapshot_event.state_snapshot["conversation"]["messages"]
    if not messages:
        return None
    return messages[-1].get("content")


def snapshot_runtime_conversation_ids(snapshot_events: Sequence[Any]) -> list[str]:
    return [
        snapshot_event.state_snapshot["conversation"]["id"] for snapshot_event in snapshot_events
    ]


def snapshot_step_histories(snapshot_events: Sequence[Any]) -> list[list[str]]:
    return [
        snapshot_event.state_snapshot["execution"]["step_history"]
        for snapshot_event in snapshot_events
    ]


def execute_with_state_snapshots(
    conversation: Conversation,
    *,
    state_snapshot_policy: StateSnapshotPolicy,
    execution_interrupts: Sequence[ExecutionInterrupt] | None = None,
    execution_context: AbstractContextManager[Any] | None = None,
) -> tuple[object, list[StateSnapshotEvent]]:
    collector = SnapshotCollector()

    with execution_context or nullcontext():
        with register_event_listeners([collector]):
            status = conversation.execute(
                execution_interrupts=execution_interrupts,
                state_snapshot_policy=state_snapshot_policy,
            )

    return status, collector.state_snapshot_events


async def execute_with_state_snapshots_async(
    conversation: Conversation,
    *,
    state_snapshot_policy: StateSnapshotPolicy,
    execution_interrupts: Sequence[ExecutionInterrupt] | None = None,
    execution_context: AbstractContextManager[Any] | None = None,
) -> tuple[object, list[StateSnapshotEvent]]:
    collector = SnapshotCollector()

    with execution_context or nullcontext():
        with register_event_listeners([collector]):
            status = await conversation.execute_async(
                execution_interrupts=execution_interrupts,
                state_snapshot_policy=state_snapshot_policy,
            )

    return status, collector.state_snapshot_events


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


class _UnserializableVariableValue:
    pass


def create_tool_flow_conversation(
    func: Callable[[], object],
    *,
    name: str = "say_hi",
    description: str = "Say hi",
) -> Conversation:
    return Flow.from_steps(
        [
            ToolExecutionStep(
                tool=ServerTool(
                    name=name,
                    description=description,
                    func=func,
                    input_descriptors=[],
                )
            ),
            CompleteStep(name="end"),
        ]
    ).start_conversation()


def create_output_flow_conversation(message: str = "Hello") -> Conversation:
    return Flow.from_steps(
        [
            OutputMessageStep(message_template=message),
            CompleteStep(name="end"),
        ]
    ).start_conversation()


def create_agent_conversation(message: str = "Hello from agent") -> Conversation:
    llm = DummyModel()
    llm.set_next_output(message)
    conversation = Agent(llm=llm).start_conversation()
    conversation.append_user_message("Hi")
    return conversation


def create_tool_calling_agent_conversation() -> Conversation:
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


def create_nested_agent_step_flow_conversation() -> Conversation:
    llm = DummyModel()
    llm.set_next_output("agent answer")
    child_agent = Agent(llm=llm)
    conversation = Flow.from_steps(
        [AgentExecutionStep(agent=child_agent), CompleteStep(name="end")]
    ).start_conversation()
    conversation.append_user_message("dummy")
    return conversation


def create_parallel_child_flow(output_name: str, output_value: str) -> Flow:
    return Flow.from_steps(
        [
            ToolExecutionStep(
                tool=ServerTool(
                    name=f"tool_{output_name}",
                    description=f"Return {output_name}",
                    input_descriptors=[],
                    output_descriptors=[StringProperty(name=output_name)],
                    func=lambda: output_value,
                )
            ),
            CompleteStep(name="end"),
        ]
    )


def create_unserializable_variable_conversation() -> Conversation:
    custom_variable = Variable(name="custom", type=AnyProperty())
    return Flow.from_steps(
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


def build_policy(
    interval: StateSnapshotInterval,
    **kwargs: object,
) -> StateSnapshotPolicy:
    return StateSnapshotPolicy(state_snapshot_interval=interval, **kwargs)


def assert_terminal_snapshot(
    snapshot_events: Sequence[object],
    *,
    expected_status_type: str,
    expected_message: str,
) -> None:
    assert snapshot_status_types(snapshot_events)[-1] == expected_status_type
    assert snapshot_message(snapshot_events[-1]) == expected_message
    assert snapshot_events[-1].state_snapshot["execution"]["status_handled"] is False
