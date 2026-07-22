# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Generator, Optional

from ..events import Event, EventListener
from ..events.event import (
    AgentExecutionIterationStartedEvent,
    FlowExecutionIterationStartedEvent,
    LlmGenerationResponseEvent,
)
from .checkpoint_state import _save_live_conversation_checkpoint
from .checkpointer import Checkpointer, CheckpointingInterval

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation

_CHECKPOINT_SAVE_REASON_CONVERSATION_TURN = "conversation_turn"
_CHECKPOINT_SAVE_REASON_INTERNAL_TURN_BOUNDARY = "internal_turn_boundary"
_IterationStartedEvent = AgentExecutionIterationStartedEvent | FlowExecutionIterationStartedEvent
_ITERATION_STARTED_EVENTS = (
    AgentExecutionIterationStartedEvent,
    FlowExecutionIterationStartedEvent,
)


def _find_checkpointed_conversation(
    conversation: "Conversation",
    execution_state: object,
) -> Optional["Conversation"]:
    if conversation.state is execution_state:
        return conversation

    # Events can be emitted by temporary helper conversations that are not part of
    # the root conversation and its nested subconversations. Only save boundaries whose execution state belongs
    # to a conversation that will actually be serialized.
    for checkpoint_conversation in conversation._get_all_sub_conversations_recursive():
        if checkpoint_conversation.state is execution_state:
            return checkpoint_conversation
    return None


def _is_agent_iteration_start_that_exits_immediately(
    checkpointed_conversation: "Conversation",
    event: _IterationStartedEvent,
) -> bool:
    from wayflowcore.agent import Agent

    # The agent executor emits an iteration-start event at the top of every loop,
    # including the final loop that immediately exits because there is no work left.
    if not isinstance(event, AgentExecutionIterationStartedEvent):
        return False

    checkpointed_agent = checkpointed_conversation.component
    if not isinstance(checkpointed_agent, Agent):
        return False
    execution_state = event.execution_state
    if execution_state.curr_iter < checkpointed_agent.max_iterations:
        return False
    has_no_pending_tool_requests = (
        execution_state.current_tool_request is None and not execution_state.tool_call_queue
    )
    return has_no_pending_tool_requests


def _build_listener_checkpoint_metadata(
    conversation: "Conversation",
    save_reason: str,
    event: Optional[_IterationStartedEvent] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build listener metadata describing why this checkpoint was saved."""
    checkpoint_metadata: Dict[str, Any] = {
        "save_reason": save_reason,
        "current_step_name": conversation.current_step_name,
        "message_count": len(conversation.message_list.messages),
    }
    if conversation.status is not None:
        checkpoint_metadata["status_type"] = type(conversation.status).__name__
    if event is not None:
        checkpoint_metadata["event_type"] = event.__class__.__name__

    if isinstance(event, AgentExecutionIterationStartedEvent):
        checkpoint_metadata["agent_iteration"] = event.execution_state.curr_iter
    elif isinstance(event, FlowExecutionIterationStartedEvent):
        checkpoint_metadata["flow_step_name"] = event.execution_state.current_step_name
        checkpoint_metadata["nesting_level"] = event.execution_state.nesting_level
    if metadata:
        checkpoint_metadata.update(metadata)
    return checkpoint_metadata


class _ConversationCheckpointEventListener(EventListener):
    """Translate execution events into checkpoint saves for one root conversation.

    The listener is intentionally attached only around the outermost execute()
    call. Nested conversations contribute to the same root snapshot through the
    serialized root conversation and its nested subconversations rather than
    writing independent checkpoints.
    """

    def __init__(self, conversation: "Conversation", checkpointer: Checkpointer) -> None:
        self.conversation = conversation
        self.checkpointer = checkpointer
        self._pending_llm_checkpoint = False
        self._latest_checkpoint_boundary_event: Optional[_IterationStartedEvent] = None

    def __call__(self, event: Event) -> None:
        # LLM_TURNS checkpoints are delayed until the next safe agent/flow boundary.
        # This avoids saving in the middle of a model/tool iteration.
        if isinstance(event, LlmGenerationResponseEvent):
            self._pending_llm_checkpoint = True
            return

        if not isinstance(event, _ITERATION_STARTED_EVENTS):
            return

        self._latest_checkpoint_boundary_event = event

        checkpointed_conversation = _find_checkpointed_conversation(
            self.conversation, event.execution_state
        )
        if checkpointed_conversation is None:
            return

        match self.checkpointer.checkpointing_interval:
            case CheckpointingInterval.CONVERSATION_TURNS:
                # Conversation-turn checkpoints are written once after execute() returns.
                return
            case CheckpointingInterval.ALL_INTERNAL_TURNS:
                self._save_internal_turn_checkpoint(event)
            case CheckpointingInterval.LLM_TURNS if self._pending_llm_checkpoint:
                # Skip the synthetic "next loop started, then exited immediately" event.
                # The final conversation-turn checkpoint will capture the same state.
                if _is_agent_iteration_start_that_exits_immediately(
                    checkpointed_conversation, event
                ):
                    self._pending_llm_checkpoint = False
                    return
                self._save_internal_turn_checkpoint(event)

    def save_pending_llm_checkpoint(self) -> None:
        if self.checkpointer.checkpointing_interval != CheckpointingInterval.LLM_TURNS:
            return
        if not self._pending_llm_checkpoint:
            return
        event = self._latest_checkpoint_boundary_event
        if event is None:
            return
        if _find_checkpointed_conversation(self.conversation, event.execution_state) is None:
            return

        # If execution returns immediately after an LLM turn, there may be no following
        # iteration-start event. Flush that last completed LLM boundary before final save.
        self._save_internal_turn_checkpoint(event)

    def _save_internal_turn_checkpoint(self, event: _IterationStartedEvent) -> None:
        _save_live_conversation_checkpoint(
            self.checkpointer,
            self.conversation,
            metadata=_build_listener_checkpoint_metadata(
                self.conversation,
                save_reason=_CHECKPOINT_SAVE_REASON_INTERNAL_TURN_BOUNDARY,
                event=event,
            ),
        )
        self._pending_llm_checkpoint = False


@contextmanager
def get_conversation_checkpoint_execution_context(
    conversation: "Conversation",
    is_outermost_execution: bool,
) -> Generator[None, None, None]:
    """Context manager that wraps one outermost execute() with checkpointing.

    The ordering is deliberate:
    - listen to internal execution events while the execute() call runs
    - flush any pending LLM-turn checkpoint before the final save
    - write the conversation-turn checkpoint only if execution returned normally
    """
    checkpointer = conversation.checkpointer
    if checkpointer is None or not is_outermost_execution:
        # Nested executes are captured through the root conversation snapshot. Saving each
        # nested execute separately would create duplicate/incomplete root checkpoints.
        yield
        return

    from wayflowcore.events.eventlistener import register_event_listeners

    listener = _ConversationCheckpointEventListener(conversation, checkpointer)
    with register_event_listeners([listener]):
        yield
        listener.save_pending_llm_checkpoint()
        _save_live_conversation_checkpoint(
            checkpointer,
            conversation,
            metadata=_build_listener_checkpoint_metadata(
                conversation,
                save_reason=_CHECKPOINT_SAVE_REASON_CONVERSATION_TURN,
            ),
        )
