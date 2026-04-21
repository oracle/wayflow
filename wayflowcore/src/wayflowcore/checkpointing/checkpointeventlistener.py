# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from contextlib import contextmanager, nullcontext
from typing import TYPE_CHECKING, Any, Dict, Iterator, Optional

from ..events import EventListener
from .checkpointer import CheckpointingInterval

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation


def _build_checkpoint_metadata(
    conversation: "Conversation",
    *,
    save_reason: str,
    event: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    checkpoint_metadata: Dict[str, Any] = {
        "save_reason": save_reason,
        "current_step_name": conversation.current_step_name,
        "message_count": len(conversation.message_list.messages),
    }
    if conversation.status is not None:
        checkpoint_metadata["status_type"] = type(conversation.status).__name__
    if event is not None:
        checkpoint_metadata["event_type"] = event.__class__.__name__
        execution_state = getattr(event, "execution_state", None)
        if execution_state is not None:
            if hasattr(execution_state, "curr_iter"):
                checkpoint_metadata["agent_iteration"] = execution_state.curr_iter
            if hasattr(execution_state, "current_step_name"):
                checkpoint_metadata["flow_step_name"] = execution_state.current_step_name
            if hasattr(execution_state, "nesting_level"):
                checkpoint_metadata["nesting_level"] = execution_state.nesting_level
    if metadata:
        checkpoint_metadata.update(metadata)
    return checkpoint_metadata


def _save_conversation_checkpoint(
    conversation: "Conversation",
    *,
    save_reason: str,
    event: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
    checkpoint_id: Optional[str] = None,
) -> None:
    checkpointer = conversation.checkpointer
    if checkpointer is None:
        return

    checkpoint_metadata = _build_checkpoint_metadata(
        conversation,
        save_reason=save_reason,
        event=event,
        metadata=metadata,
    )

    checkpointer.save_conversation(
        conversation,
        checkpoint_id=checkpoint_id,
        metadata=checkpoint_metadata,
    )


class _ConversationCheckpointEventListener(EventListener):
    def __init__(self, conversation: "Conversation") -> None:
        self.conversation = conversation
        self._llm_was_used_since_last_internal_turn = False
        self._last_internal_turn_start_event: Optional[Any] = None

    def __call__(self, event: Any) -> None:
        from wayflowcore.events.event import (
            AgentExecutionIterationStartedEvent,
            FlowExecutionIterationStartedEvent,
            LlmGenerationResponseEvent,
        )

        checkpointer = self.conversation.checkpointer
        if checkpointer is None:
            return

        if isinstance(event, LlmGenerationResponseEvent):
            self._llm_was_used_since_last_internal_turn = True
            return

        if not isinstance(
            event, (AgentExecutionIterationStartedEvent, FlowExecutionIterationStartedEvent)
        ):
            return

        checkpointing_interval = checkpointer.checkpointing_interval

        if checkpointing_interval == CheckpointingInterval.CONVERSATION_TURNS:
            self._last_internal_turn_start_event = event
            return

        if checkpointing_interval == CheckpointingInterval.ALL_INTERNAL_TURNS:
            _save_conversation_checkpoint(
                self.conversation,
                save_reason="internal_turn_boundary",
                event=event,
                metadata={
                    "llm_used_in_previous_turn": self._llm_was_used_since_last_internal_turn,
                },
            )
            self._llm_was_used_since_last_internal_turn = False
            self._last_internal_turn_start_event = event
            return

        if self._llm_was_used_since_last_internal_turn:
            _save_conversation_checkpoint(
                self.conversation,
                save_reason="internal_turn_boundary",
                event=event,
                metadata={
                    "llm_used_in_previous_turn": self._llm_was_used_since_last_internal_turn,
                },
            )
            self._llm_was_used_since_last_internal_turn = False

        self._last_internal_turn_start_event = event

    def flush_pending_checkpoint(self) -> None:
        checkpointer = self.conversation.checkpointer
        if checkpointer is None:
            return
        if checkpointer.checkpointing_interval != CheckpointingInterval.LLM_TURNS:
            return
        if not self._llm_was_used_since_last_internal_turn:
            return

        _save_conversation_checkpoint(
            self.conversation,
            save_reason="internal_turn_boundary",
            event=self._last_internal_turn_start_event,
            metadata={
                "llm_used_in_previous_turn": True,
            },
        )
        self._llm_was_used_since_last_internal_turn = False


@contextmanager
def get_conversation_checkpoint_execution_context(
    conversation: "Conversation",
    *,
    is_outermost_execution: bool,
    final_checkpoint_id: Optional[str] = None,
    final_checkpoint_metadata: Optional[Dict[str, Any]] = None,
) -> Iterator[None]:
    if conversation.checkpointer is None or not is_outermost_execution:
        with nullcontext():
            yield
        return

    from wayflowcore.events.eventlistener import register_event_listeners

    listener = _ConversationCheckpointEventListener(conversation)
    with register_event_listeners([listener]):
        try:
            yield
        except Exception:
            raise
        else:
            listener.flush_pending_checkpoint()
            _save_conversation_checkpoint(
                conversation,
                save_reason="conversation_turn",
                checkpoint_id=final_checkpoint_id,
                metadata=final_checkpoint_metadata,
            )
