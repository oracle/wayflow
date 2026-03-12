# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

import logging
from contextlib import contextmanager
from enum import Enum
from typing import Iterator, Optional

from wayflowcore.conversation import Conversation, _get_active_conversations
from wayflowcore.events import Event, EventListener
from wayflowcore.events.event import (
    AgentExecutionFinishedEvent,
    AgentExecutionIterationFinishedEvent,
    AgentExecutionIterationStartedEvent,
    AgentExecutionStartedEvent,
    ExceptionRaisedEvent,
    FlowExecutionFinishedEvent,
    FlowExecutionIterationFinishedEvent,
    FlowExecutionStartedEvent,
    StateSnapshotEvent,
    StepInvocationStartEvent,
    ToolExecutionResultEvent,
    ToolExecutionStartEvent,
)
from wayflowcore.events.eventlistener import (
    get_event_listeners,
    record_event,
    register_event_listeners,
)
from wayflowcore.executors._events.event import EventType as ExecutionEventType
from wayflowcore.executors._executor import ExecutionInterruptedException
from wayflowcore.executors.executionstatus import ExecutionStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval
from wayflowcore.serialization.conversation import dump_conversation_state, dump_variable_state
from wayflowcore.tracing.span import AgentExecutionSpan, FlowExecutionSpan, get_current_span

logger = logging.getLogger(__name__)


class StateSnapshotBoundary(str, Enum):
    """
    Concrete runtime boundaries at which a state snapshot may be recorded.

    `TURN_START`
        The opening boundary of a single `conversation.execute(...)` call. This
        captures the turn's initial resume point before execution work begins.

    `TURN_END`
        The closing boundary of a single `conversation.execute(...)` call. This
        is the stable resume point after the turn's final status is known.

    `TOOL_START`
        Right before a tool invocation begins.

    `TOOL_END`
        Right after a tool invocation completes and its result is available.

    `NODE_START`
        Right before a flow step starts executing.

    `NODE_END`
        Right after a flow step finishes executing.

    `AGENT_LOOP_START`
        Right before an agent reasoning/decision-loop iteration starts.

    `AGENT_LOOP_END`
        Right after an agent reasoning/decision-loop iteration finishes.
    """

    TURN_START = "turn_start"
    TURN_END = "turn_end"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    NODE_START = "node_start"
    NODE_END = "node_end"
    AGENT_LOOP_START = "agent_loop_start"
    AGENT_LOOP_END = "agent_loop_end"


class StateSnapshotListenerPhase(str, Enum):
    PRE_INTERRUPTS = "pre_interrupts"
    POST_INTERRUPTS = "post_interrupts"


def should_emit_state_snapshot(
    conversation: Conversation,
    boundary: StateSnapshotBoundary,
) -> bool:
    state_snapshot_policy = conversation._get_state_snapshot_policy()
    if state_snapshot_policy is None:
        return False

    snapshot_interval = state_snapshot_policy.state_snapshot_interval
    if snapshot_interval == StateSnapshotInterval.OFF:
        should_emit = False
    elif boundary == StateSnapshotBoundary.TURN_START:
        should_emit = snapshot_interval == StateSnapshotInterval.CONVERSATION_TURNS
    elif boundary == StateSnapshotBoundary.TURN_END:
        should_emit = True
    elif boundary in {StateSnapshotBoundary.TOOL_START, StateSnapshotBoundary.TOOL_END}:
        should_emit = snapshot_interval in {
            StateSnapshotInterval.TOOL_TURNS,
            StateSnapshotInterval.ALL_INTERNAL_TURNS,
        }
    elif boundary in {
        StateSnapshotBoundary.NODE_START,
        StateSnapshotBoundary.NODE_END,
        StateSnapshotBoundary.AGENT_LOOP_START,
        StateSnapshotBoundary.AGENT_LOOP_END,
    }:
        # Agents do not expose node execution events, so NODE_TURNS maps to
        # per-step boundaries for flows and per-iteration boundaries for agents.
        should_emit = snapshot_interval in {
            StateSnapshotInterval.NODE_TURNS,
            StateSnapshotInterval.ALL_INTERNAL_TURNS,
        }
    else:
        should_emit = False

    return should_emit


def record_state_snapshot(
    conversation: Conversation,
    boundary: StateSnapshotBoundary,
    *,
    execution_status: ExecutionStatus | None,
    status_handled: bool,
) -> bool:
    state_snapshot_policy = conversation._get_state_snapshot_policy()
    if state_snapshot_policy is None or not should_emit_state_snapshot(conversation, boundary):
        return False

    previous_status = conversation.status
    previous_status_handled = conversation.status_handled
    conversation.status = execution_status
    conversation.status_handled = status_handled

    try:
        record_event(
            StateSnapshotEvent(
                conversation_id=conversation.conversation_id,
                state_snapshot=dump_conversation_state(conversation),
                extra_state=conversation._build_extra_state(),
                variable_state=(
                    dump_variable_state(conversation)
                    if state_snapshot_policy.include_variable_state
                    else None
                ),
            )
        )
        return True
    except Exception:
        logger.warning(
            "Failed to emit state snapshot for conversation '%s'",
            conversation.conversation_id,
            exc_info=True,
        )
        return False
    finally:
        conversation.status = previous_status
        conversation.status_handled = previous_status_handled


def _get_current_active_conversation() -> Optional[Conversation]:
    active_conversations = _get_active_conversations(return_copy=False)
    if not active_conversations:
        return None
    return active_conversations[-1]


def _is_multi_agent_conversation(conversation: Conversation) -> bool:
    from wayflowcore.executors._managerworkersconversation import ManagerWorkersConversation
    from wayflowcore.executors._swarmconversation import SwarmConversation

    return isinstance(conversation, (ManagerWorkersConversation, SwarmConversation))


def _get_nearest_parent_multi_agent_conversation() -> Optional[Conversation]:
    active_conversations = _get_active_conversations(return_copy=False)
    if len(active_conversations) < 2:
        return None

    for conversation in reversed(active_conversations[:-1]):
        if _is_multi_agent_conversation(conversation):
            return conversation

    return None


class StateSnapshotEventListener(EventListener):
    """Emit state snapshots for the active conversation."""

    def __init__(
        self,
        conversation: Conversation,
        phase: StateSnapshotListenerPhase,
    ) -> None:
        self.conversation = conversation
        self.phase = phase

    def _record_snapshot(self, boundary: StateSnapshotBoundary) -> None:
        record_state_snapshot(
            self.conversation,
            boundary,
            execution_status=None,
            status_handled=False,
        )

    def _handle_pre_interrupt_event(self, event: Event) -> None:
        match event:
            case FlowExecutionStartedEvent():
                self._record_snapshot(StateSnapshotBoundary.TURN_START)
            case AgentExecutionStartedEvent():
                self._record_snapshot(StateSnapshotBoundary.TURN_START)
            case ToolExecutionStartEvent():
                self._record_snapshot(StateSnapshotBoundary.TOOL_START)
            case ToolExecutionResultEvent():
                self._record_snapshot(StateSnapshotBoundary.TOOL_END)
            case StepInvocationStartEvent():
                self._record_snapshot(StateSnapshotBoundary.NODE_START)
            case FlowExecutionIterationFinishedEvent():
                self._record_snapshot(StateSnapshotBoundary.NODE_END)
            case AgentExecutionIterationStartedEvent():
                self._record_snapshot(StateSnapshotBoundary.AGENT_LOOP_START)
            case AgentExecutionIterationFinishedEvent():
                self._record_snapshot(StateSnapshotBoundary.AGENT_LOOP_END)

    def _handle_pre_interrupt_event_for_parent_multi_agent(self, event: Event) -> None:
        match event:
            case AgentExecutionStartedEvent() | FlowExecutionStartedEvent():
                self._record_snapshot(StateSnapshotBoundary.TURN_START)

    def _record_turn_end_snapshot(
        self,
        execution_status: ExecutionStatus | None = None,
    ) -> None:
        record_state_snapshot(
            self.conversation,
            StateSnapshotBoundary.TURN_END,
            execution_status=execution_status,
            status_handled=False,
        )

    def _latest_execution_event_is_turn_end(self) -> bool:
        if not self.conversation.state.events:
            return False
        return self.conversation.state.events[-1].type == ExecutionEventType.EXECUTION_END

    def _should_record_interrupted_turn_end_snapshot(
        self,
    ) -> bool:
        if not self._latest_execution_event_is_turn_end():
            should_record = False
        elif not isinstance(get_current_span(), (FlowExecutionSpan, AgentExecutionSpan)):
            should_record = False
        else:
            should_record = True

        return should_record

    def _handle_post_interrupt_event(self, event: Event) -> None:
        match event:
            case FlowExecutionFinishedEvent(
                execution_status=execution_status
            ) | AgentExecutionFinishedEvent(execution_status=execution_status):
                self._record_turn_end_snapshot(execution_status)
            case ExceptionRaisedEvent(exception=ExecutionInterruptedException() as exception):
                if self._should_record_interrupted_turn_end_snapshot():
                    self._record_turn_end_snapshot(exception.execution_status)

    def _handle_post_interrupt_event_for_parent_multi_agent(self, event: Event) -> None:
        match event:
            case FlowExecutionFinishedEvent(
                execution_status=execution_status
            ) | AgentExecutionFinishedEvent(execution_status=execution_status):
                self._record_turn_end_snapshot(execution_status)
            case ExceptionRaisedEvent(exception=ExecutionInterruptedException() as exception):
                self._record_turn_end_snapshot(exception.execution_status)

    def __call__(self, event: Event) -> None:
        if isinstance(event, StateSnapshotEvent):
            return

        current_conversation = _get_current_active_conversation()
        if current_conversation is None:
            return

        is_current_conversation = current_conversation.id == self.conversation.id
        parent_multi_agent_conversation = _get_nearest_parent_multi_agent_conversation()
        is_parent_multi_agent_conversation = (
            parent_multi_agent_conversation is not None
            and parent_multi_agent_conversation.id == self.conversation.id
        )

        if not is_current_conversation and not is_parent_multi_agent_conversation:
            return

        if self.phase == StateSnapshotListenerPhase.PRE_INTERRUPTS:
            if is_current_conversation:
                self._handle_pre_interrupt_event(event)
            else:
                self._handle_pre_interrupt_event_for_parent_multi_agent(event)
        else:
            if is_current_conversation:
                self._handle_post_interrupt_event(event)
            else:
                self._handle_post_interrupt_event_for_parent_multi_agent(event)


@contextmanager
def get_state_snapshot_event_listener_context_for_conversation(
    conversation: Conversation,
    *,
    phase: StateSnapshotListenerPhase,
) -> Iterator[StateSnapshotEventListener]:
    current_listener = next(
        (
            event_listener
            for event_listener in get_event_listeners()
            if isinstance(event_listener, StateSnapshotEventListener)
            and event_listener.conversation.id == conversation.id
            and event_listener.phase == phase
        ),
        None,
    )

    if current_listener is not None:
        yield current_listener
    else:
        listener = StateSnapshotEventListener(conversation, phase=phase)
        with register_event_listeners([listener]):
            yield listener
