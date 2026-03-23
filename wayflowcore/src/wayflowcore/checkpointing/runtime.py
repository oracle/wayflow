# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

import weakref
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from wayflowcore.events.eventlistener import EventListener

from .models import CheckpointingInterval

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation

    from .base import Checkpointer


@dataclass
class _ConversationCheckpointRuntimeState:
    checkpointer: Optional["Checkpointer"] = None
    checkpoint_id: Optional[str] = None
    final_checkpoint_id_override: Optional[str] = None
    final_checkpoint_metadata_override: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _ConversationCheckpointExecutionState:
    listener_context: Any
    listener: Optional["_ConversationCheckpointEventListener"]


_CONVERSATION_CHECKPOINT_RUNTIME_STATE: Dict[int, _ConversationCheckpointRuntimeState] = {}
_CONVERSATION_CHECKPOINT_RUNTIME_REFS: Dict[int, weakref.ReferenceType[Any]] = {}


def _clear_conversation_checkpoint_runtime_state(conversation_key: int) -> None:
    _CONVERSATION_CHECKPOINT_RUNTIME_STATE.pop(conversation_key, None)
    _CONVERSATION_CHECKPOINT_RUNTIME_REFS.pop(conversation_key, None)


def _make_runtime_state_finalizer(
    conversation_key: int,
) -> Callable[[weakref.ReferenceType[Any]], None]:
    def _finalize_runtime_state(_ref: weakref.ReferenceType[Any]) -> None:
        _clear_conversation_checkpoint_runtime_state(conversation_key)

    return _finalize_runtime_state


def _get_conversation_checkpoint_runtime_state(
    conversation: "Conversation",
) -> _ConversationCheckpointRuntimeState:
    conversation_key = id(conversation)
    runtime_state = _CONVERSATION_CHECKPOINT_RUNTIME_STATE.get(conversation_key)
    if runtime_state is None:
        runtime_state = _ConversationCheckpointRuntimeState()
        _CONVERSATION_CHECKPOINT_RUNTIME_STATE[conversation_key] = runtime_state
        try:
            _CONVERSATION_CHECKPOINT_RUNTIME_REFS[conversation_key] = weakref.ref(
                conversation,
                _make_runtime_state_finalizer(conversation_key),
            )
        except TypeError:
            pass
    return runtime_state


def _get_conversation_checkpointer(conversation: "Conversation") -> Optional["Checkpointer"]:
    return _get_conversation_checkpoint_runtime_state(conversation).checkpointer


def _set_conversation_checkpointer(
    conversation: "Conversation", checkpointer: Optional["Checkpointer"]
) -> None:
    _get_conversation_checkpoint_runtime_state(conversation).checkpointer = checkpointer


def _get_conversation_checkpoint_id(conversation: "Conversation") -> Optional[str]:
    return _get_conversation_checkpoint_runtime_state(conversation).checkpoint_id


def _set_conversation_checkpoint_id(
    conversation: "Conversation", checkpoint_id: Optional[str]
) -> None:
    _get_conversation_checkpoint_runtime_state(conversation).checkpoint_id = checkpoint_id


def _clear_conversation_final_checkpoint_overrides(conversation: "Conversation") -> None:
    runtime_state = _get_conversation_checkpoint_runtime_state(conversation)
    runtime_state.final_checkpoint_id_override = None
    runtime_state.final_checkpoint_metadata_override = {}


def _set_conversation_final_checkpoint_overrides(
    conversation: "Conversation",
    *,
    checkpoint_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    runtime_state = _get_conversation_checkpoint_runtime_state(conversation)
    runtime_state.final_checkpoint_id_override = checkpoint_id
    runtime_state.final_checkpoint_metadata_override = dict(metadata or {})


def _attach_checkpointer_to_conversation(
    conversation: "Conversation",
    checkpointer: Optional["Checkpointer"],
    checkpoint_id: Optional[str] = None,
) -> "Conversation":
    _set_conversation_checkpointer(conversation, checkpointer)
    _set_conversation_checkpoint_id(conversation, checkpoint_id)
    _clear_conversation_final_checkpoint_overrides(conversation)
    return conversation


def _detach_checkpointer_from_conversation(conversation: "Conversation") -> None:
    _set_conversation_checkpointer(conversation, None)
    _set_conversation_checkpoint_id(conversation, None)
    _clear_conversation_final_checkpoint_overrides(conversation)


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
    use_final_save_overrides: bool = False,
) -> None:
    checkpointer = _get_conversation_checkpointer(conversation)
    if checkpointer is None:
        return

    runtime_state = _get_conversation_checkpoint_runtime_state(conversation)
    checkpoint_id = None
    checkpoint_metadata = _build_checkpoint_metadata(
        conversation,
        save_reason=save_reason,
        event=event,
        metadata=metadata,
    )
    if use_final_save_overrides:
        checkpoint_id = runtime_state.final_checkpoint_id_override
        if runtime_state.final_checkpoint_metadata_override:
            checkpoint_metadata.update(runtime_state.final_checkpoint_metadata_override)

    checkpointer.save_conversation(
        conversation,
        checkpoint_id=checkpoint_id,
        metadata=checkpoint_metadata,
    )
    if use_final_save_overrides:
        _clear_conversation_final_checkpoint_overrides(conversation)


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

        checkpointer = _get_conversation_checkpointer(self.conversation)
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
        checkpointer = _get_conversation_checkpointer(self.conversation)
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


def _prepare_conversation_checkpoint_execution(
    conversation: "Conversation",
    *,
    is_outermost_execution: bool,
) -> _ConversationCheckpointExecutionState:
    if _get_conversation_checkpointer(conversation) is None or not is_outermost_execution:
        return _ConversationCheckpointExecutionState(
            listener_context=nullcontext(),
            listener=None,
        )

    from wayflowcore.events.eventlistener import register_event_listeners

    listener = _ConversationCheckpointEventListener(conversation)
    return _ConversationCheckpointExecutionState(
        listener_context=register_event_listeners([listener]),
        listener=listener,
    )


def _finalize_conversation_checkpoint_execution(
    conversation: "Conversation",
    *,
    is_outermost_execution: bool,
    execution_state: _ConversationCheckpointExecutionState,
) -> None:
    if _get_conversation_checkpointer(conversation) is None or not is_outermost_execution:
        return

    if execution_state.listener is not None:
        execution_state.listener.flush_pending_checkpoint()
    _save_conversation_checkpoint(
        conversation,
        save_reason="conversation_turn",
        use_final_save_overrides=True,
    )
