# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import time
from itertools import chain
from typing import TYPE_CHECKING, Any, Dict, Optional, Type

from wayflowcore.exceptions import DataclassFieldDeserializationError
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.serialization import autodeserialize, serialize
from wayflowcore.serialization.context import (
    DeserializationContext,
    MissingDeserializationReferenceError,
    SerializationContext,
    _iter_nested_components,
)

if TYPE_CHECKING:
    from wayflowcore.checkpointing import Checkpointer
    from wayflowcore.checkpointing.checkpointer import ConversationCheckpoint
    from wayflowcore.conversation import Conversation
    from wayflowcore.conversationalcomponent import ConversationalComponent
    from wayflowcore.executors._agentexecutor import AgentConversationExecutionState
    from wayflowcore.executors._flowexecutor import FlowConversationExecutionState
    from wayflowcore.executors._managerworkersconversation import (
        ManagerWorkersConversationExecutionState,
    )
    from wayflowcore.executors._swarmconversation import SwarmConversationExecutionState


_COMPONENT_ID_ERROR_HINT = "Restart-safe checkpoint restore requires stable component ids."
_STEP_NAME_ERROR_HINT = "Restart-safe checkpoint restore requires stable step names."
_AGENT_NAME_ERROR_HINT = "Restart-safe checkpoint restore requires stable agent names."


class _CheckpointRestoreCompatibilityError(ValueError):
    """Raised when a checkpoint cannot be resumed against the current live graph."""


def _save_live_conversation_checkpoint(
    checkpointer: "Checkpointer",
    conversation: "Conversation",
    checkpoint_id: Optional[str] = None,
    component_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> "ConversationCheckpoint":
    from wayflowcore.checkpointing.checkpointer import ConversationCheckpoint

    if not _supports_checkpointing(conversation.component):
        raise NotImplementedError(
            "Checkpointing conversations that contain `OciAgent` is not supported yet."
        )
    serialization_context = SerializationContext(root=conversation)
    serialization_context._add_component_to_context(conversation.component)

    checkpoint = ConversationCheckpoint(
        checkpoint_id=checkpoint_id or IdGenerator.get_or_generate_id(),
        conversation_id=conversation.conversation_id,
        component_id=component_id or conversation.component.id,
        created_at=int(time.time()),
        state=serialize(conversation, serialization_context=serialization_context),
        metadata=dict(metadata or {}),
    )
    checkpointer.save(checkpoint)
    conversation.checkpoint_id = checkpoint.checkpoint_id
    return checkpoint


def _load_checkpointed_conversation(
    checkpoint: "ConversationCheckpoint",
    component: "ConversationalComponent",
    expected_conversation_type: Type["Conversation"],
    tool_registry: Optional[Dict[str, Any]] = None,
    checkpointer: Optional["Checkpointer"] = None,
    attach_checkpointer: bool = True,
) -> "Conversation":
    """Restore a Conversation object from stored checkpoint state.

    The serialized conversation omits live component/tool objects and rebuilds them from
    the current component tree. After deserialization, the helper also repairs
    derived runtime-only state that is not stored directly in the checkpoint.
    """
    deserialization_context = DeserializationContext()
    deserialization_context.registered_tools = tool_registry.copy() if tool_registry else {}
    deserialization_context._add_component_to_context(component)
    try:
        conversation = autodeserialize(
            checkpoint.state,
            deserialization_context=deserialization_context,
        )
    except (MissingDeserializationReferenceError, DataclassFieldDeserializationError) as exc:
        if not _contains_missing_reference_error(exc):
            raise
        raise _CheckpointRestoreCompatibilityError(
            "Cannot restore this checkpoint because the current component tree does not "
            "match the serialized component ids. "
            f"{_COMPONENT_ID_ERROR_HINT}"
        ) from exc
    if not isinstance(conversation, expected_conversation_type):
        raise _CheckpointRestoreCompatibilityError(
            "Cannot restore this checkpoint because this conversation was started with another "
            f"component. Expected `{expected_conversation_type.__name__}`, got `{type(conversation).__name__}`."
        )
    _prepare_restored_conversation_states(conversation)
    conversation.checkpoint_id = checkpoint.checkpoint_id

    if attach_checkpointer:
        conversation.checkpointer = checkpointer
    return conversation


def _contains_missing_reference_error(error: Exception) -> bool:
    """Return whether the exception chain contains a missing component/tool reference."""
    while error is not None:
        if isinstance(error, MissingDeserializationReferenceError):
            return True
        error = error.__cause__  # type: ignore[assignment]
    return False


def _prepare_restored_conversation_states(root_conversation: "Conversation") -> None:
    """Repair executor-specific state after a conversation is restored."""
    from wayflowcore.executors._agentexecutor import AgentConversationExecutionState
    from wayflowcore.executors._flowexecutor import FlowConversationExecutionState
    from wayflowcore.executors._managerworkersconversation import (
        ManagerWorkersConversationExecutionState,
    )
    from wayflowcore.executors._swarmconversation import SwarmConversationExecutionState

    for conversation in chain(
        (root_conversation,),
        root_conversation._get_all_sub_conversations_recursive(),
    ):
        state = conversation.state
        match state:
            case AgentConversationExecutionState():
                _prepare_restored_agent_conversation_state(state)
            case FlowConversationExecutionState():
                _validate_restored_flow_conversation_state(state)
            case SwarmConversationExecutionState():
                _prepare_restored_swarm_conversation_state(state)
            case ManagerWorkersConversationExecutionState():
                _prepare_restored_managerworkers_conversation_state(state)


def _prepare_restored_agent_conversation_state(state: "AgentConversationExecutionState") -> None:
    """Re-key Agent subconversations by the canonical runtime slot key."""
    from wayflowcore.executors._agentconversation import AgentConversation

    state.current_sub_component_conversations = {
        AgentConversation._sub_component_conversation_key(
            subconversation.component
        ): subconversation
        for subconversation in state.current_sub_component_conversations.values()
    }


def _validate_restored_flow_conversation_state(state: "FlowConversationExecutionState") -> None:
    """Fail fast if restored Flow state names steps that no longer exist live."""
    valid_step_names = set(state.flow.steps)
    if state.flow.begin_step_name is not None:
        valid_step_names.add(state.flow.begin_step_name)

    for step_name in chain(
        (state.current_step_name,),
        state.step_history,
        (step_name for step_name, _output_name in state.input_output_key_values),
    ):
        if step_name is None or step_name in valid_step_names:
            continue
        raise _CheckpointRestoreCompatibilityError(
            "Cannot restore this checkpoint because flow conversation state refers to "
            f"step `{step_name}` which is not present in the current Flow. "
            f"{_STEP_NAME_ERROR_HINT}"
        )


def _prepare_restored_swarm_conversation_state(state: "SwarmConversationExecutionState") -> None:
    """Rebuild Swarm's derived indexes, then assert the active thread is still valid."""
    threads = [state.main_thread] + [
        thread
        for recipients_and_threads in state.agents_and_threads.values()
        for thread in recipients_and_threads.values()
    ]
    # Rebuild the recipient lookup from the live thread objects. The serialized
    # dict keys may no longer line up after deserialization.
    state.agents_and_threads = {}
    for thread in threads:
        if not thread.is_main_thread:
            state.agents_and_threads.setdefault(thread.caller.name, {})[
                thread.recipient_agent.name
            ] = thread
    # Thread subconversations are matched by sharing the same message list object.
    # The thread identifiers are the stable keys; message-list object identity lets
    # us reconnect them after deserialization rebuilt the in-memory objects.
    thread_ids_by_message_list = {id(thread.message_list): thread.identifier for thread in threads}
    state.thread_subconversations = {
        thread_id: subconversation
        for subconversation in state.thread_subconversations.values()
        if (thread_id := thread_ids_by_message_list.get(id(subconversation.message_list)))
        is not None
    }
    if state.current_thread is None:
        raise _CheckpointRestoreCompatibilityError(
            "Cannot restore this checkpoint because Swarm conversation state does not "
            f"have an active thread. {_AGENT_NAME_ERROR_HINT}"
        )

    valid_thread_ids = {thread.identifier for thread in threads}
    if state.current_thread.identifier not in valid_thread_ids:
        raise _CheckpointRestoreCompatibilityError(
            "Cannot restore this checkpoint because Swarm conversation state refers to "
            f"thread `{state.current_thread.identifier}` which is not present in the current "
            f"Swarm topology. {_AGENT_NAME_ERROR_HINT}"
        )


def _prepare_restored_managerworkers_conversation_state(
    state: "ManagerWorkersConversationExecutionState",
) -> None:
    """Re-key ManagerWorkers subconversations, then assert the active agent is still valid."""
    # Subconversations are restored as objects first; rebuild the name-keyed lookup
    # used by the runtime from those live conversation objects.
    state.subconversations = {
        subconversation.component.name: subconversation
        for subconversation in state.subconversations.values()
    }
    if (
        state.current_agent_name is not None
        and state.current_agent_name not in state.subconversations
    ):
        raise _CheckpointRestoreCompatibilityError(
            "Cannot restore this checkpoint because ManagerWorkers conversation state "
            f"refers to agent `{state.current_agent_name}` which is not present "
            f"in the current component tree. {_AGENT_NAME_ERROR_HINT}"
        )


# Checkpoint eligibility


def _supports_checkpointing(component: "ConversationalComponent") -> bool:
    from wayflowcore.ociagent import OciAgent

    return not any(
        isinstance(nested_component, OciAgent)
        for nested_component in _iter_nested_components(component)
    )
