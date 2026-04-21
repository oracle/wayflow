# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from wayflowcore.idgeneration import IdGenerator

from .serialization import _serialize_conversation_checkpoint_state

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.datastore import Datastore


@dataclass(frozen=True)
class ConversationCheckpoint:
    """Durable snapshot of a conversation at a checkpoint boundary."""

    checkpoint_id: str
    conversation_id: str
    component_id: str
    created_at: int
    state: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.checkpoint_id


class CheckpointingInterval(Enum):
    """
    Configure when the conversation is saved during execution.
    """

    CONVERSATION_TURNS = "conversation_turns"
    LLM_TURNS = "llm_turns"
    ALL_INTERNAL_TURNS = "all_internal_turns"


@dataclass
class StorageConfig:
    """Configuration for checkpoint storage."""

    datastore: Optional["Datastore"] = None
    table_name: str = "conversations"
    agent_id_column_name: str = "agent_id"
    conversation_id_column_name: str = "conversation_id"
    turn_id_column_name: str = "turn_id"
    created_at_column_name: str = "created_at"
    remove_by_column_name: str = "remove_by"
    conversation_turn_state_column_name: str = "conversation_turn_state"
    is_last_turn_column_name: str = "is_last_turn"
    extra_metadata_column_name: str = "extra_metadata"
    max_retention: Optional[int] = None

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

    def save(self, checkpoint: Any) -> None:
        from wayflowcore.conversation import Conversation

        if isinstance(checkpoint, Conversation):
            self.save_conversation(checkpoint)
            return
        if not isinstance(checkpoint, ConversationCheckpoint):
            raise TypeError(
                f"Expected a Conversation or ConversationCheckpoint, got {type(checkpoint).__name__}."
            )
        self._save_checkpoint(checkpoint)

    async def save_async(self, checkpoint: Any) -> None:
        self.save(checkpoint)

    def save_conversation(
        self,
        conversation: "Conversation",
        *,
        checkpoint_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationCheckpoint:
        next_save_sequence = self._save_sequence_by_conversation.get(conversation.id, 0) + 1
        self._save_sequence_by_conversation[conversation.id] = next_save_sequence
        checkpoint_metadata = {"save_sequence": next_save_sequence}
        if metadata:
            checkpoint_metadata.update(metadata)
        checkpoint = ConversationCheckpoint(
            checkpoint_id=checkpoint_id or IdGenerator.get_or_generate_id(),
            conversation_id=conversation.id,
            component_id=conversation.component.id,
            created_at=int(time.time()),
            state=_serialize_conversation_checkpoint_state(conversation),
            metadata=checkpoint_metadata,
        )
        self._save_checkpoint(checkpoint)
        conversation.checkpoint_id = checkpoint.checkpoint_id
        return checkpoint

    @abstractmethod
    def _save_checkpoint(self, checkpoint: ConversationCheckpoint) -> None:
        raise NotImplementedError()

    @abstractmethod
    def list_checkpoints(
        self, conversation_id: str, limit: Optional[int] = 50
    ) -> List[ConversationCheckpoint]:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, conversation_id: str, checkpoint_id: str) -> None:
        raise NotImplementedError()
