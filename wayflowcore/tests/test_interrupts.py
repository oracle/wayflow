# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import contextlib
import os
from typing import Any, Dict, Optional, Type

import pytest

from wayflowcore.agent import Agent
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.conversation import Conversation
from wayflowcore.executors._events.event import Event, EventType
from wayflowcore.executors._executionstate import ConversationExecutionState
from wayflowcore.executors.interrupts.executioninterrupt import (
    FlexibleExecutionInterrupt,
    FlowExecutionInterrupt,
    InterruptedExecutionStatus,
    _AllEventsInterruptMixin,
)
from wayflowcore.executors.interrupts.timeoutexecutioninterrupt import SoftTimeoutExecutionInterrupt
from wayflowcore.executors.interrupts.tokenlimitexecutioninterrupt import (
    SoftTokenLimitExecutionInterrupt,
)
from wayflowcore.flow import Flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.steps import PromptExecutionStep
from wayflowcore.steps.step import Step
from wayflowcore.tools import ToolRequest, tool

from .testhelpers.dummy import DoNothingStep, DummyModel, SleepStep


@contextlib.contextmanager
def disable_streaming():
    """Temporarily disable message streaming of LLMs"""
    from wayflowcore.executors._agentexecutor import _DISABLE_STREAMING

    old_value = os.environ.get(_DISABLE_STREAMING, None)
    if old_value is None:
        os.environ[_DISABLE_STREAMING] = "true"
    try:
        yield
    finally:
        del os.environ[_DISABLE_STREAMING]


def assert_conversations_are_equivalent(
    conversation_a: Conversation,
    conversation_b: Conversation,
) -> None:
    conversation_a_messages = conversation_a.get_messages()
    conversation_b_messages = conversation_b.get_messages()
    assert len(conversation_a_messages) == len(conversation_b_messages)
    for i in range(len(conversation_a_messages)):
        assert conversation_a_messages[i].content == conversation_b_messages[i].content
        assert conversation_a_messages[i].message_type == conversation_b_messages[i].message_type
        assert conversation_a_messages[i].tool_requests == conversation_b_messages[i].tool_requests
        assert conversation_a_messages[i].tool_result == conversation_b_messages[i].tool_result


def create_basic_flow_assistant(
    num_steps: int = 3,
    step_type: Type[Step] = DoNothingStep,
    step_args: Optional[Dict[str, Any]] = None,
):
    # Returns a linear flow with `num_steps` steps of the same type
    assert num_steps > 0
    step_args = step_args or dict()
    steps = {f"step_{i}": step_type(**step_args) for i in range(num_steps)}
    return Flow(
        begin_step=steps["step_0"],
        steps=steps,
        control_flow_edges=[
            ControlFlowEdge(source_step=steps[f"step_{i}"], destination_step=steps[f"step_{i + 1}"])
            for i in range(num_steps - 1)
        ]
        + [ControlFlowEdge(source_step=steps[f"step_{num_steps - 1}"], destination_step=None)],
    )


def create_basic_flow_with_outputs() -> Flow:

    from wayflowcore.steps import OutputMessageStep

    step0 = OutputMessageStep(
        message_template="This is the agent message",
        message_type=MessageType.AGENT,
    )
    step1 = DoNothingStep()
    step2 = OutputMessageStep(
        message_template="This is the system message",
        message_type=MessageType.SYSTEM,
    )
    return Flow.from_steps([step0, step1, step2])


@pytest.fixture
def basic_flow_assistant_with_outputs() -> Flow:
    return create_basic_flow_with_outputs()


@pytest.fixture
def basic_flow_assistant_with_outputs_in_subflow() -> Flow:

    from wayflowcore.steps import FlowExecutionStep, OutputMessageStep

    outer_step_0 = FlowExecutionStep(create_basic_flow_with_outputs())
    outer_step_1 = DoNothingStep()
    outer_step_2 = OutputMessageStep(
        message_template="This is the outer agent message",
        message_type=MessageType.AGENT,
    )
    return Flow.from_steps([outer_step_0, outer_step_1, outer_step_2])


def create_basic_agent(llm: VllmModel, **kwargs) -> Agent:
    return Agent(
        llm=llm,
        **kwargs,
    )


class OnEventExecutionInterrupt(
    _AllEventsInterruptMixin, FlexibleExecutionInterrupt, FlowExecutionInterrupt
):

    def __init__(self, trigger_on_event: EventType):
        self.trigger_on_event = trigger_on_event
        self.triggered = False
        self.current_event = None
        super().__init__()

    def _return_status_if_condition_is_met(
        self, state: ConversationExecutionState, conversation: Conversation
    ) -> Optional[InterruptedExecutionStatus]:
        if (
            self.current_event is not None
            and self.current_event.type == self.trigger_on_event
            and not self.triggered
        ):
            self.triggered = True
            return InterruptedExecutionStatus(
                interrupter=self,
                reason=str(self.current_event.type),
                _conversation_id=conversation.id,
            )
        return None

    def on_event(
        self, event: Event, state: ConversationExecutionState, conversation: Conversation
    ) -> Optional[InterruptedExecutionStatus]:
        # We implement it this way to check that the logic of the parent classes is correct
        self.current_event = event
        return super().on_event(event, state, conversation)

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return {"trigger_on_event": self.trigger_on_event}

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        return OnEventExecutionInterrupt(trigger_on_event=input_dict["trigger_on_event"])


_AGENT_EVENTS = [
    EventType.EXECUTION_START,
    EventType.EXECUTION_END,
    EventType.EXECUTION_LOOP_ITERATION_START,
    EventType.EXECUTION_LOOP_ITERATION_END,
    EventType.GENERATION_START,
    EventType.GENERATION_END,
    EventType.TOOL_CALL_START,
    EventType.TOOL_CALL_END,
    # These are not yet used in the agent
    # EventType.AGENT_CALL_START,
    # EventType.AGENT_CALL_END,
]

_FLOW_EVENTS = [
    EventType.EXECUTION_START,
    EventType.EXECUTION_END,
    EventType.EXECUTION_LOOP_ITERATION_START,
    EventType.EXECUTION_LOOP_ITERATION_END,
    EventType.STEP_EXECUTION_START,
    EventType.STEP_EXECUTION_END,
]


@pytest.mark.parametrize("event_type", _AGENT_EVENTS)
def test_agent_interrupts_are_triggered_on_event_and_correctly_continues(event_type):

    @tool
    def do_nothing_tool() -> str:
        """Do nothing tool"""
        return "Do nothing tool result"

    dummy_output = {
        "Hello, how are you?": Message(
            message_type=MessageType.AGENT, content="This is the agent message"
        ),
        "Please tell me a joke": Message(
            message_type=MessageType.AGENT,
            content="What do you say to Einstein on the beach? What a physique!",
        ),
        "Do nothing tool result": Message(
            message_type=MessageType.AGENT, content="Tool called successfully"
        ),
        "Please use the do_nothing_tool": Message(
            message_type=MessageType.TOOL_REQUEST,
            content="I am calling the do nothing tool",
            tool_requests=[ToolRequest("do_nothing_tool", {}, "tc1")],
        ),
    }

    dummy_llm = DummyModel()
    dummy_llm.set_next_output(dummy_output)

    assistant = create_basic_agent(dummy_llm, tools=[do_nothing_tool], max_iterations=10)

    # We need to disable streaming as it's currently a bit broken
    with disable_streaming():
        # Do a full conversation with the assistant first, without interrupts
        conversation = assistant.start_conversation()
        conversation.append_user_message("Hello, how are you?")
        _ = conversation.execute(execution_interrupts=[])
        conversation.append_user_message("Please use the do_nothing_tool")
        _ = conversation.execute(execution_interrupts=[])

        # Then run a conversation with the interrupt
        execution_interrupts = [OnEventExecutionInterrupt(event_type)]
        conversation_with_interrupts = assistant.start_conversation()
        conversation_with_interrupts.append_user_message("Hello, how are you?")
        execution_status = conversation_with_interrupts.execute(execution_interrupts)

        # Before entering tool events in interrupts, we need to have a first round with the user
        # So we will not have interrupt execution statuses here
        if event_type not in {EventType.TOOL_CALL_START, EventType.TOOL_CALL_END}:
            assert isinstance(execution_status, InterruptedExecutionStatus)
            assert execution_status.interrupter == execution_interrupts[0]
            assert execution_status.reason == str(event_type)

        # There are interrupts that break before the first round of user input is required,
        # we should re-start them before appending a message to the conversation
        if event_type in {
            EventType.EXECUTION_START,
            EventType.EXECUTION_LOOP_ITERATION_START,
            EventType.GENERATION_START,
        }:
            execution_status = conversation_with_interrupts.execute(execution_interrupts)

        # Make the assistant use the tool
        conversation_with_interrupts.append_user_message("Please use the do_nothing_tool")
        execution_status = conversation_with_interrupts.execute(execution_interrupts)

        # We skipped the check on the returned status before for tool events,
        # now it should be correctly thrown by the interrupts
        if event_type in {EventType.TOOL_CALL_START, EventType.TOOL_CALL_END}:
            assert isinstance(execution_status, InterruptedExecutionStatus)
            assert execution_status.interrupter == execution_interrupts[0]
            assert execution_status.reason == str(event_type)
            _ = conversation_with_interrupts.execute(execution_interrupts)

    # Check that the conversations with and without interrupts are equivalent
    assert_conversations_are_equivalent(conversation, conversation_with_interrupts)


@pytest.mark.parametrize("event_type", _FLOW_EVENTS)
@pytest.mark.parametrize("wrap_in_subflow", [True, False])
def test_flow_assistant_interrupts_are_triggered_on_event_and_correctly_continues(
    basic_flow_assistant_with_outputs,
    basic_flow_assistant_with_outputs_in_subflow,
    event_type,
    wrap_in_subflow,
):
    if wrap_in_subflow:
        assistant = basic_flow_assistant_with_outputs_in_subflow
    else:
        assistant = basic_flow_assistant_with_outputs
    # Do a full conversation with the assistant first, without interrupts
    conversation = assistant.start_conversation()
    _ = conversation.execute(execution_interrupts=[])

    # Run a conversation with the interrupt
    execution_interrupts = [OnEventExecutionInterrupt(event_type)]
    conversation_with_interrupts = assistant.start_conversation()
    execution_status = conversation_with_interrupts.execute(execution_interrupts)
    assert isinstance(execution_status, InterruptedExecutionStatus)
    assert execution_status.interrupter == execution_interrupts[0]
    assert execution_status.reason == str(event_type)
    _ = conversation_with_interrupts.execute(execution_interrupts)

    # Check that the conversations with and without interrupts are equivalent
    assert_conversations_are_equivalent(conversation, conversation_with_interrupts)


@pytest.mark.parametrize("event_type", _FLOW_EVENTS)
def test_flow_assistant_interrupts_are_triggered_on_event_and_correctly_continues_in_subflow(
    basic_flow_assistant_with_outputs, event_type
):
    assistant = basic_flow_assistant_with_outputs
    # Do a full conversation with the assistant first, without interrupts
    conversation = assistant.start_conversation()
    _ = conversation.execute(execution_interrupts=[])

    # Run a conversation with the interrupt
    execution_interrupts = [OnEventExecutionInterrupt(event_type)]
    conversation_with_interrupts = assistant.start_conversation()
    execution_status = conversation_with_interrupts.execute(
        execution_interrupts=execution_interrupts
    )
    assert isinstance(execution_status, InterruptedExecutionStatus)
    assert execution_status.interrupter == execution_interrupts[0]
    assert execution_status.reason == str(event_type)
    _ = conversation_with_interrupts.execute(execution_interrupts)

    # Check that the conversations with and without interrupts are equivalent
    assert_conversations_are_equivalent(conversation, conversation_with_interrupts)


def test_conversations_have_default_timeout_execution_interrupt(remotely_hosted_llm):
    assistant = create_basic_flow_assistant()
    conversation = assistant.start_conversation()
    _ = conversation.execute()
    execution_interrupts = conversation.state._get_execution_interrupts()
    assert len(execution_interrupts) == 1
    assert isinstance(execution_interrupts[0], SoftTimeoutExecutionInterrupt)

    assistant = create_basic_agent(remotely_hosted_llm)
    conversation = assistant.start_conversation()
    conversation.append_user_message("Hello, how are you?")
    _ = conversation.execute()
    execution_interrupts = conversation.state._get_execution_interrupts()
    assert len(execution_interrupts) == 1
    assert isinstance(execution_interrupts[0], SoftTimeoutExecutionInterrupt)


def test_agent_execution_stops_with_timeout_execution_interrupt(remotely_hosted_llm):

    @tool
    def sleep_tool() -> str:
        """Tool that sleeps for 1 second"""
        import time

        time.sleep(1)
        return ""

    assistant = create_basic_agent(
        remotely_hosted_llm, tools=[sleep_tool], custom_instruction="You are a useful assistant"
    )
    execution_interrupts = [SoftTimeoutExecutionInterrupt(timeout=0.5)]
    conversation = assistant.start_conversation()
    execution_status = conversation.execute(execution_interrupts)
    conversation.append_user_message("Please, use the sleep tool")
    execution_status = conversation.execute(execution_interrupts)
    assert isinstance(execution_status, InterruptedExecutionStatus)
    assert execution_status.interrupter == execution_interrupts[0]
    assert execution_status.reason == "Execution time limit reached"


def test_flow_assistant_execution_stops_with_timeout_execution_interrupt():
    assistant = create_basic_flow_assistant(step_type=SleepStep)
    execution_interrupts = [SoftTimeoutExecutionInterrupt(timeout=0.5)]
    conversation = assistant.start_conversation()
    execution_status = conversation.execute(execution_interrupts)
    assert isinstance(execution_status, InterruptedExecutionStatus)
    assert execution_status.interrupter == execution_interrupts[0]
    assert execution_status.reason == "Execution time limit reached"


def test_agent_execution_stops_with_per_model_token_limit_execution_interrupt(
    remotely_hosted_llm,
):
    assistant = create_basic_agent(
        remotely_hosted_llm,
        custom_instruction="You are a smart assistant",
    )
    execution_interrupts = [
        SoftTokenLimitExecutionInterrupt(tokens_per_model={remotely_hosted_llm: 1})
    ]
    conversation = assistant.start_conversation()
    conversation.append_user_message("Hello, how are you?")
    execution_status = conversation.execute(execution_interrupts)
    assert isinstance(execution_status, InterruptedExecutionStatus)
    assert execution_status.interrupter == execution_interrupts[0]
    assert (
        execution_status.reason == f"Token limit reached for model {remotely_hosted_llm.model_id}"
    )


def test_agent_execution_stops_with_global_token_limit_execution_interrupt(
    remotely_hosted_llm,
):
    assistant = create_basic_agent(
        remotely_hosted_llm,
        custom_instruction="You are a smart assistant",
    )
    execution_interrupts = [
        SoftTokenLimitExecutionInterrupt(all_models=[remotely_hosted_llm], total_tokens=1)
    ]
    conversation = assistant.start_conversation()
    conversation.append_user_message("Hello, how are you?")
    execution_status = conversation.execute(execution_interrupts)
    assert isinstance(execution_status, InterruptedExecutionStatus)
    assert execution_status.interrupter == execution_interrupts[0]
    assert execution_status.reason == "Global token limit reached"


def test_flow_assistant_execution_stops_with_global_token_limit_execution_interrupt(
    remotely_hosted_llm,
):
    step_0 = PromptExecutionStep(
        prompt_template="Tell me a joke",
        llm=remotely_hosted_llm,
    )
    step_1 = PromptExecutionStep(
        prompt_template="Tell me a joke",
        llm=remotely_hosted_llm,
    )
    flow = Flow.from_steps(steps=[step_0, step_1])
    execution_interrupts = [
        SoftTokenLimitExecutionInterrupt(all_models=[remotely_hosted_llm], total_tokens=1)
    ]
    conversation = flow.start_conversation()
    execution_status = conversation.execute(execution_interrupts)
    assert isinstance(execution_status, InterruptedExecutionStatus)
    assert execution_status.interrupter == execution_interrupts[0]
    assert execution_status.reason == "Global token limit reached"
