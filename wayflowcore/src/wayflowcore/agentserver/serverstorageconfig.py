# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


from dataclasses import dataclass
from typing import Dict, Optional

from wayflowcore.datastore import Datastore, Entity
from wayflowcore.property import IntegerProperty, StringProperty


@dataclass
class ServerStorageConfig:
    """Configuration for server storage management."""

    datastore: Optional[Datastore] = None
    """Datastore to use for persistence"""

    table_name: str = "conversations"
    """Name of the table in which the states are stored"""
    agent_id_column_name: str = "agent_id"
    """Name of the column where the agent id of the state is stored"""
    state_id_column_name: str = "state_id"
    """Name of the column where the id of the state is stored"""
    turn_id_column_name: str = "turn_id"
    """Name of the column where the turn id / response id is stored"""
    created_at_column_name: str = "created_at"
    """Name of the column where the creation timestamp is stored"""
    state_column_name: str = "state"
    """Name of the column where the serialized state is store"""
    is_last_turn_column_name: str = "is_last_turn"
    """Name of the column where the marker for the most recent turn of a given conversation is stored"""
    extra_metadata_column_name: str = "extra_metadata"
    """Name of the column where the server stores its own attributes"""

    max_retention: Optional[int] = None
    """Number of seconds for which to retain a conversation before discarding it"""

    def to_schema(self) -> Dict[str, Entity]:
        return {
            self.table_name: Entity(
                properties={
                    self.agent_id_column_name: StringProperty(),
                    self.state_id_column_name: StringProperty(),
                    self.turn_id_column_name: StringProperty(),
                    self.is_last_turn_column_name: IntegerProperty(),
                    self.state_column_name: StringProperty(),
                    self.created_at_column_name: IntegerProperty(),
                    self.extra_metadata_column_name: StringProperty(),
                }
            ),
        }
