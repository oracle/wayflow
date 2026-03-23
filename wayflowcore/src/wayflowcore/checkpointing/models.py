# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
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

    datastore: Optional[Datastore] = None
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
