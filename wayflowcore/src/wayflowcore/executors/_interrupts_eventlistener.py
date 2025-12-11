# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import Iterator, List

from wayflowcore.conversation import Conversation
from wayflowcore.events import Event, EventListener
from wayflowcore.events.event import (
    AgentDecidedNextActionEvent,
    AgentExecutionIterationFinishedEvent,
    AgentExecutionIterationStartedEvent,
    AgentNextActionDecisionStartEvent,
    ConversationalComponentExecutionFinishedEvent,
    ConversationalComponentExecutionStartedEvent,
    FlowExecutionFinishedEvent,
    FlowExecutionIterationFinishedEvent,
    FlowExecutionIterationStartedEvent,
    LlmGenerationResponseEvent,
    StepInvocationStartEvent,
    ToolExecutionResultEvent,
    ToolExecutionStartEvent,
)
from wayflowcore.events.eventlistener import get_event_listeners, register_event_listeners
from wayflowcore.executors._events.event import Event as ExecutionEvent
from wayflowcore.executors._events.event import EventType as ExecutionEventType
from wayflowcore.executors._executor import ExecutionInterruptedException
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.tracing.span import (
    AgentExecutionSpan,
    ConversationalComponentExecutionSpan,
    get_active_span_stack,
)


def interrupts_event_listener_for_conversation_is_active(conversation: Conversation) -> bool:
    # Returns true if in the current context there's already an active InterruptsEventListener for a conversation
    return any(
        isinstance(event_listener, InterruptsEventListener)
        and event_listener.conversation.id == conversation.id
        for event_listener in get_event_listeners()
    )


@contextmanager
def get_interrupts_event_listener_context_for_conversation(
    conversation: Conversation,
) -> Iterator["InterruptsEventListener"]:
    """
    Context manager that ensures there's an active InterruptsEventListener for the given conversation.
    - If one is active for the same conversation, yield it.
    - Otherwise, temporarily register a new one, and clean up afterward.
    - Deactivates other active InterruptsEventListener for other conversations during the block.
    """
    current_event_listeners = get_event_listeners()
    current_active_for_conversation = None
    deactivated_event_listeners = []

    # Deactivate all active InterruptsEventListener except the one for the target conversation
    for event_listener in current_event_listeners:
        if isinstance(event_listener, InterruptsEventListener) and event_listener.is_active:
            if (
                event_listener.conversation.id == conversation.id
                and current_active_for_conversation is None
            ):
                current_active_for_conversation = event_listener
            elif event_listener.conversation.id != conversation.id:
                event_listener.is_active = False
                deactivated_event_listeners.append(event_listener)
            else:
                raise ValueError(
                    f"Expected only one active InterruptsEventListener for conversation {conversation.id}"
                )

    if current_active_for_conversation is not None:
        try:
            yield current_active_for_conversation
        finally:
            for event_listener in deactivated_event_listeners:
                event_listener.is_active = True
    else:
        # No active listener for this conversation: create and register one temporarily
        listener = InterruptsEventListener(conversation)
        context = (
            register_event_listeners([listener])
            if not interrupts_event_listener_for_conversation_is_active(conversation)
            else nullcontext()
        )
        with context:
            try:
                yield listener
            finally:
                for event_listener in deactivated_event_listeners:
                    event_listener.is_active = True


class InterruptsEventListener(EventListener):
    """Base Executor class. An executor is stateless, and exposes an execute method on the conversation."""

    def __init__(self, conversation: Conversation, is_active: bool = True) -> None:
        self.conversation = conversation
        self.is_active = is_active

    def _get_execution_event_from_event(self, event: Event) -> List[ExecutionEvent]:
        # We retrieve the closest active span on the stack related to the execution of a conversational component
        # to understand if we are executing a flow or an agent
        # This is needed to trigger some old events correctly (e.g., TOOL_CALL only in agents)
        closest_conversational_component_execution_span = next(
            (
                span
                for span in get_active_span_stack()[::-1]
                if isinstance(span, ConversationalComponentExecutionSpan)
            ),
            None,
        )
        event_types: List[ExecutionEventType] = []
        if isinstance(event, ConversationalComponentExecutionStartedEvent):
            event_types.append(ExecutionEventType.EXECUTION_START)
        if isinstance(event, ConversationalComponentExecutionFinishedEvent):
            if not (
                isinstance(event, FlowExecutionFinishedEvent)
                and not isinstance(event.execution_status, (FinishedStatus))
            ):
                event_types.append(ExecutionEventType.EXECUTION_END)
        if isinstance(
            event, (AgentExecutionIterationStartedEvent, FlowExecutionIterationStartedEvent)
        ):
            event_types.append(ExecutionEventType.EXECUTION_LOOP_ITERATION_START)
        if isinstance(
            event, (AgentExecutionIterationFinishedEvent, FlowExecutionIterationFinishedEvent)
        ):
            if isinstance(event, FlowExecutionIterationFinishedEvent):
                # In the old implementation of events, the step execution end coincided with the loop iteration end
                event_types.append(ExecutionEventType.STEP_EXECUTION_END)
            event_types.append(ExecutionEventType.EXECUTION_LOOP_ITERATION_END)
        if isinstance(event, StepInvocationStartEvent):
            event_types.append(ExecutionEventType.STEP_EXECUTION_START)
        if isinstance(event, AgentNextActionDecisionStartEvent):
            # GENERATION_START was referred to before the specific agent decision on what to do next
            event_types.append(ExecutionEventType.GENERATION_START)
        if isinstance(event, AgentDecidedNextActionEvent):
            # GENERATION_END was referred to after the specific agent decision on what to do next
            event_types.append(ExecutionEventType.GENERATION_END)
        if isinstance(event, LlmGenerationResponseEvent):
            # TOKEN_CONSUMPTION is covered by the LlmGenerationResponseEvent
            event_types.append(ExecutionEventType.TOKEN_CONSUMPTION)
        if isinstance(closest_conversational_component_execution_span, AgentExecutionSpan):
            if isinstance(event, ToolExecutionStartEvent):
                event_types.append(ExecutionEventType.TOOL_CALL_START)
            if isinstance(event, ToolExecutionResultEvent):
                event_types.append(ExecutionEventType.TOOL_CALL_END)
        # AGENT_CALL_START and AGENT_CALL_END were not used, we do not translate them
        return [ExecutionEvent(type=event_type) for event_type in event_types]

    def __call__(self, event: Event) -> None:
        if not self.is_active:
            return

        if not (execution_events := self._get_execution_event_from_event(event)):
            return
        conversation = self.conversation
        state = self.conversation.state
        interrupt_statuses = []
        for new_event in execution_events:
            state._register_event(new_event)
            # we collect all the statuses to be sure to run all the callbacks,
            # as they might update their internal status
            interrupt_statuses += [
                execution_interrupt.on_event(new_event, state, conversation)
                for execution_interrupt in (state._get_execution_interrupts() or [])
            ]
        try:
            # We look the first non-null interrupt status we find
            execution_status = next(
                interrupt_status
                for interrupt_status in interrupt_statuses
                if interrupt_status is not None
            )
            # If we find one, we raise an ExecutionInterruptedException containing the status
            raise ExecutionInterruptedException(execution_status=execution_status)
        except StopIteration:
            # We did not find any non-null status, we can proceed
            pass
