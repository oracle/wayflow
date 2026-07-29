# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union


class CheckpointRestoreCompatibilityError(ValueError):
    """Raised when a checkpoint cannot be resumed against the current live graph."""


if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.datastore import Datastore


@dataclass(frozen=True)
class ConversationCheckpoint:
    """Durable snapshot of a conversation at a checkpoint boundary."""

    checkpoint_id: str
    """ID of the checkpoint"""
    conversation_id: str
    """ID of the stored conversation"""
    component_id: str
    """ID of the component that created the conversation"""
    created_at: int
    """Checkpoint creation time in seconds since the Unix epoch."""
    state: str
    """Serialized conversation state."""
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Auxiliary checkpoint metadata used for ordering and inspection."""

    @property
    def id(self) -> str:
        return self.checkpoint_id


class CheckpointingInterval(Enum):
    """Configure which completed execution boundary triggers a checkpoint save."""

    # Save only after the outermost `Conversation.execute()` returns.
    CONVERSATION_TURNS = "conversation_turns"
    """Saves the state at the end of a component turn (before returning from conversation.execute()"""
    # Save after completed internal turns that actually used an LLM.
    LLM_TURNS = "llm_turns"
    """Saves the state at the end of a turn that uses a LLM (agent llm turn, PromptExecutionNode, ...)"""
    # Save after every completed internal agent/flow turn boundary.
    ALL_INTERNAL_TURNS = "all_internal_turns"
    """Saves the state at every internal turn (every step of a flow, every iteration of an agent, ...) recursively in all sub-components"""


@dataclass
class StorageConfig:
    """Configuration for checkpoint storage."""

    datastore: Optional["Datastore"] = None
    """Datastore to use for persistence"""
    table_name: str = "conversations"
    """Name of the table in which the states are stored"""
    agent_id_column_name: str = "agent_id"
    """Name of the column where the agent id of the state is stored"""
    conversation_id_column_name: str = "conversation_id"
    """Name of the column where the id of the conversation is stored"""
    turn_id_column_name: str = "turn_id"
    """Name of the column where the turn id / response id is stored"""
    created_at_column_name: str = "created_at"
    """Name of the column where the creation timestamp is stored"""
    remove_by_column_name: str = "remove_by"
    """Name of the column where the retention deadline timestamp is stored"""
    conversation_turn_state_column_name: str = "conversation_turn_state"
    """Name of the column where the serialized state of turn is store"""
    is_last_turn_column_name: str = "is_last_turn"
    """Name of the column where the marker for the most recent turn of a given conversation is stored"""
    extra_metadata_column_name: str = "extra_metadata"
    """Name of the column where the server stores its own attributes"""
    max_retention: Optional[int] = None
    """Number of seconds for which to retain a conversation before discarding it"""

    def to_schema(self) -> Dict[str, Any]:
        from wayflowcore.datastore import Entity, nullable
        from wayflowcore.property import IntegerProperty, StringProperty

        properties = {
            self.agent_id_column_name: StringProperty(),
            self.conversation_id_column_name: StringProperty(),
            self.turn_id_column_name: StringProperty(),
            self.is_last_turn_column_name: IntegerProperty(),
            self.conversation_turn_state_column_name: StringProperty(),
            self.created_at_column_name: IntegerProperty(),
            self.extra_metadata_column_name: StringProperty(),
        }
        if self.max_retention is not None:
            properties[self.remove_by_column_name] = nullable(IntegerProperty())
        return {
            self.table_name: Entity(
                properties=properties,
            ),
        }


class Checkpointer(ABC):
    """Backend that can persist and restore checkpoints for conversations."""

    def __init__(
        self,
        checkpointing_interval: CheckpointingInterval = CheckpointingInterval.CONVERSATION_TURNS,
    ) -> None:
        self.checkpointing_interval = checkpointing_interval
        self._save_sequence_by_conversation: Dict[str, int] = {}

    @abstractmethod
    def load_latest(self, conversation_id: str) -> Optional[ConversationCheckpoint]:
        raise NotImplementedError()

    @abstractmethod
    def load(self, conversation_id: str, checkpoint_id: str) -> ConversationCheckpoint:
        raise NotImplementedError()

    def save(
        self,
        checkpoint: Union["Conversation", ConversationCheckpoint],
        *,
        checkpoint_id: Optional[str] = None,
        component_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ConversationCheckpoint]:
        """Persist a checkpoint or snapshot a live conversation before persisting it.

        Checkpoint identifiers, component identifiers, and metadata are only valid
        when saving a live conversation.
        """
        from wayflowcore.conversation import Conversation

        if isinstance(checkpoint, Conversation):
            return self._save_conversation(
                checkpoint,
                checkpoint_id=checkpoint_id,
                component_id=component_id,
                metadata=metadata,
            )
        if checkpoint_id is not None or component_id is not None or metadata is not None:
            raise ValueError(
                "`checkpoint_id`, `component_id`, and `metadata` can only be provided "
                "when saving a live Conversation."
            )
        self._save_checkpoint(checkpoint)
        return None

    def _save_conversation(
        self,
        conversation: "Conversation",
        *,
        checkpoint_id: Optional[str] = None,
        component_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationCheckpoint:
        """Create and persist a checkpoint for a live conversation."""
        import time

        from wayflowcore.idgeneration import IdGenerator
        from wayflowcore.serialization import serialize
        from wayflowcore.serialization.context import SerializationContext

        if not conversation.component._supports_checkpointing:
            raise NotImplementedError("Checkpointing this component is not supported yet.")
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
        self._save_checkpoint(checkpoint)
        conversation.checkpoint_id = checkpoint.checkpoint_id
        return checkpoint

    @abstractmethod
    def _save_checkpoint(self, checkpoint: ConversationCheckpoint) -> None:
        """Persist an already-materialized checkpoint in the backend."""
        raise NotImplementedError()

    async def save_async(
        self,
        checkpoint: Union["Conversation", ConversationCheckpoint],
        *,
        checkpoint_id: Optional[str] = None,
        component_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ConversationCheckpoint]:
        # Async persistence is not implemented yet; this preserves the async API
        # contract while delegating to the synchronous backend implementation.
        return self.save(
            checkpoint,
            checkpoint_id=checkpoint_id,
            component_id=component_id,
            metadata=metadata,
        )

    @abstractmethod
    def list_checkpoints(
        self, conversation_id: str, limit: Optional[int] = 50
    ) -> List[ConversationCheckpoint]:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, conversation_id: str, checkpoint_id: str) -> None:
        raise NotImplementedError()
