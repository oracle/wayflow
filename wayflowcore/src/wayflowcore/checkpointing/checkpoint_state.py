# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import time
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


_COMPONENT_ID_ERROR_HINT = "Restart-safe checkpoint restore requires stable component ids."


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
    serialization_context._register_external_component_references(conversation.component)

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
    the current component tree.
    """
    deserialization_context = DeserializationContext()
    deserialization_context.registered_tools = tool_registry.copy() if tool_registry else {}
    deserialization_context._register_external_component_references(component)
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


# Checkpoint eligibility


def _supports_checkpointing(component: "ConversationalComponent") -> bool:
    from wayflowcore.ociagent import OciAgent

    return not any(
        isinstance(nested_component, OciAgent)
        for nested_component in _iter_nested_components(component)
    )
