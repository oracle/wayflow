# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from wayflowcore.datastore import Datastore


@dataclass(frozen=True)
class ConversationCheckpoint:
    """Durable snapshot of a conversation at a checkpoint boundary."""

    checkpoint_id: str
    """External identifier of this saved checkpoint."""
    conversation_id: str
    """Durable conversation id that this checkpoint belongs to."""
    component_id: str
    """Best-effort root component id stored for diagnostics and storage queries."""
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
    # Save after completed internal turns that actually used an LLM.
    LLM_TURNS = "llm_turns"
    # Save after every completed internal agent/flow turn boundary.
    ALL_INTERNAL_TURNS = "all_internal_turns"


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

    @abstractmethod
    def save(self, checkpoint: ConversationCheckpoint) -> None:
        raise NotImplementedError()

    async def save_async(self, checkpoint: ConversationCheckpoint) -> None:
        # Async persistence is not implemented yet; this preserves the async API
        # contract while delegating to the synchronous backend implementation.
        self.save(checkpoint)

    @abstractmethod
    def list_checkpoints(
        self, conversation_id: str, limit: Optional[int] = 50
    ) -> List[ConversationCheckpoint]:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, conversation_id: str, checkpoint_id: str) -> None:
        raise NotImplementedError()
