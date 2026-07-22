# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import hashlib
import json
import time
from textwrap import dedent
from typing import Any, Dict, List, Optional, Sequence

from wayflowcore.datastore import (
    Datastore,
    InMemoryDatastore,
    OracleDatabaseConnectionConfig,
    OracleDatabaseDatastore,
    PostgresDatabaseConnectionConfig,
    PostgresDatabaseDatastore,
)
from wayflowcore.datastore._relational import RelationalDatastore
from wayflowcore.datastore.oracle import _execute_query_on_oracle_db
from wayflowcore.datastore.postgres import _execute_query_on_postgres_db

from .checkpointer import Checkpointer, CheckpointingInterval, ConversationCheckpoint, StorageConfig


def _build_checkpoint_create_table_columns(
    storage_config: StorageConfig,
    is_oracle: bool,
) -> List[str]:
    text_type = "CLOB" if is_oracle else "TEXT"
    varchar_type = "VARCHAR2(255)" if is_oracle else "VARCHAR(255)"

    columns = [
        f"{storage_config.turn_id_column_name} {varchar_type} PRIMARY KEY",
        f"{storage_config.agent_id_column_name} {varchar_type} NOT NULL",
        f"{storage_config.conversation_id_column_name} {varchar_type} NOT NULL",
        f"{storage_config.created_at_column_name} INTEGER NOT NULL",
        f"{storage_config.conversation_turn_state_column_name} {text_type} NOT NULL",
        f"{storage_config.is_last_turn_column_name} INTEGER NOT NULL",
        f"{storage_config.extra_metadata_column_name} {text_type} NOT NULL",
    ]
    if storage_config.max_retention is not None:
        columns.append(f"{storage_config.remove_by_column_name} INTEGER")
    return columns


def _build_checkpoint_latest_index_name(storage_config: StorageConfig) -> str:
    # Keep generated index names portable across supported relational backends.
    # Oracle identifiers are limited to 30 bytes, so long custom table names are
    # shortened with a stable suffix instead of being passed through directly.
    raw_index_name = f"{storage_config.table_name}_conv_latest_idx"
    safe_index_name = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in raw_index_name
    )
    if len(safe_index_name) <= 30:
        return safe_index_name

    digest = hashlib.sha256(raw_index_name.encode("utf-8")).hexdigest()[:8]
    prefix = safe_index_name[:21].rstrip("_") or "wf_checkpoint"
    return f"{prefix}_{digest}"


def _build_checkpoint_latest_index_query(storage_config: StorageConfig) -> str:
    # Composite index for the two durable read paths:
    # load_latest() filters by conversation_id + is_last_turn, while list_checkpoints()
    # filters by conversation_id. Keeping conversation_id first supports both.
    return dedent(
        f"""
        CREATE INDEX {_build_checkpoint_latest_index_name(storage_config)}
        ON {storage_config.table_name} (
            {storage_config.conversation_id_column_name},
            {storage_config.is_last_turn_column_name}
        );
        """
    )


def _prepare_postgres_checkpoint_datastore(
    connection_config: PostgresDatabaseConnectionConfig,
    storage_config: StorageConfig,
) -> None:
    from sqlalchemy.exc import ProgrammingError

    create_table_query = dedent(
        f"""
        CREATE TABLE {storage_config.table_name} (
            {", ".join(_build_checkpoint_create_table_columns(storage_config, is_oracle=False))}
        );
        """
    )
    try:
        _execute_query_on_postgres_db(connection_config, create_table_query)
        _execute_query_on_postgres_db(
            connection_config,
            _build_checkpoint_latest_index_query(storage_config),
        )
    except ProgrammingError as e:
        if f'relation "{storage_config.table_name}" already exists' in str(e):
            raise ValueError(
                f'The datastore is already setup. Either delete the existing "{storage_config.table_name}" table or start the server with `--setup-datastore=no`.'
            ) from e
        raise


def _prepare_oracle_checkpoint_datastore(
    connection_config: OracleDatabaseConnectionConfig,
    storage_config: StorageConfig,
) -> None:
    create_table_query = dedent(
        f"""
        CREATE TABLE {storage_config.table_name} (
            {", ".join(_build_checkpoint_create_table_columns(storage_config, is_oracle=True))}
        );
        """
    )
    try:
        _execute_query_on_oracle_db(connection_config, query=create_table_query)
        _execute_query_on_oracle_db(
            connection_config,
            query=_build_checkpoint_latest_index_query(storage_config),
        )
    except Exception as e:
        if "already exists" in str(e):
            raise ValueError(
                f'The datastore is already setup. Either delete the existing "{storage_config.table_name}" table or start the server with `--setup-datastore=no`.'
            ) from e
        raise


class DatastoreCheckpointer(Checkpointer):
    """Checkpointer backed by a WayFlow datastore."""

    def __init__(
        self,
        datastore: Datastore,
        storage_config: Optional[StorageConfig] = None,
        checkpointing_interval: CheckpointingInterval = CheckpointingInterval.CONVERSATION_TURNS,
    ) -> None:
        super().__init__(checkpointing_interval=checkpointing_interval)
        self.datastore = datastore
        self.storage_config = storage_config or StorageConfig()

    def _entity_to_checkpoint(self, entity: Dict[str, Any]) -> ConversationCheckpoint:
        raw_metadata = entity.get(self.storage_config.extra_metadata_column_name, "{}")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else json.loads(raw_metadata)
        return ConversationCheckpoint(
            checkpoint_id=str(entity[self.storage_config.turn_id_column_name]),
            conversation_id=str(entity[self.storage_config.conversation_id_column_name]),
            component_id=str(entity[self.storage_config.agent_id_column_name]),
            created_at=int(entity[self.storage_config.created_at_column_name]),
            state=str(entity[self.storage_config.conversation_turn_state_column_name]),
            metadata=metadata,
        )

    def _checkpoint_to_entity(self, checkpoint: ConversationCheckpoint) -> Dict[str, Any]:
        entity = {
            self.storage_config.agent_id_column_name: checkpoint.component_id,
            self.storage_config.conversation_id_column_name: checkpoint.conversation_id,
            self.storage_config.turn_id_column_name: checkpoint.checkpoint_id,
            self.storage_config.created_at_column_name: checkpoint.created_at,
            self.storage_config.conversation_turn_state_column_name: checkpoint.state,
            self.storage_config.is_last_turn_column_name: 1,
            self.storage_config.extra_metadata_column_name: json.dumps(checkpoint.metadata),
        }
        if self.storage_config.max_retention is not None:
            # Retention is represented as metadata for backend/external cleanup. Reads do
            # not filter by this value, so callers should not treat it as enforced expiry.
            entity[self.storage_config.remove_by_column_name] = (
                checkpoint.created_at + self.storage_config.max_retention
            )
        return entity

    @staticmethod
    def _sort_checkpoints(
        checkpoints: Sequence[ConversationCheckpoint],
    ) -> List[ConversationCheckpoint]:
        # `created_at` is second-resolution for schema compatibility. Prefer the
        # nanosecond timestamp and save sequence when available so same-second saves
        # have stable ordering in list/load_latest/delete promotion paths.
        return sorted(
            checkpoints,
            key=lambda checkpoint: (
                checkpoint.created_at,
                checkpoint.metadata.get("created_at_ns", checkpoint.created_at * 1_000_000_000),
                checkpoint.metadata.get("save_sequence", -1),
                checkpoint.id,
            ),
        )

    def _find_checkpoint(
        self,
        conversation_id: str,
        checkpoint_id: str,
    ) -> Optional[ConversationCheckpoint]:
        entities = self.datastore.list(
            collection_name=self.storage_config.table_name,
            where={
                self.storage_config.conversation_id_column_name: conversation_id,
                self.storage_config.turn_id_column_name: checkpoint_id,
            },
            limit=1,
        )
        if len(entities) == 0:
            return None
        return self._entity_to_checkpoint(entities[0])

    def _find_checkpoint_by_id(self, checkpoint_id: str) -> Optional[ConversationCheckpoint]:
        entities = self.datastore.list(
            collection_name=self.storage_config.table_name,
            where={self.storage_config.turn_id_column_name: checkpoint_id},
            limit=1,
        )
        if len(entities) == 0:
            return None
        return self._entity_to_checkpoint(entities[0])

    def load_latest(self, conversation_id: str) -> Optional[ConversationCheckpoint]:
        entities = self.datastore.list(
            collection_name=self.storage_config.table_name,
            where={
                self.storage_config.conversation_id_column_name: conversation_id,
                self.storage_config.is_last_turn_column_name: 1,
            },
        )
        if len(entities) == 0:
            return None
        if len(entities) > 1:
            raise ValueError(
                f"Multiple latest checkpoints found for conversation `{conversation_id}`. "
                "This can happen if multiple writers checkpoint the same conversation "
                "concurrently or if the checkpoint datastore was modified manually. Use a "
                "single writer per conversation or load a specific checkpoint by checkpoint_id."
            )
        checkpoints = self._sort_checkpoints(
            [self._entity_to_checkpoint(entity) for entity in entities]
        )
        return checkpoints[-1]

    def load(self, conversation_id: str, checkpoint_id: str) -> ConversationCheckpoint:
        checkpoint = self._find_checkpoint(
            conversation_id=conversation_id, checkpoint_id=checkpoint_id
        )
        if checkpoint is None:
            raise ValueError(
                f"Checkpoint `{checkpoint_id}` was not found for conversation `{conversation_id}`."
            )
        return checkpoint

    def save(self, checkpoint: ConversationCheckpoint) -> None:
        created_at_ns = time.time_ns()
        next_save_sequence = (
            self._save_sequence_by_conversation.get(checkpoint.conversation_id, 0) + 1
        )
        self._save_sequence_by_conversation[checkpoint.conversation_id] = next_save_sequence
        checkpoint = ConversationCheckpoint(
            checkpoint_id=checkpoint.checkpoint_id,
            conversation_id=checkpoint.conversation_id,
            component_id=checkpoint.component_id,
            created_at=checkpoint.created_at,
            state=checkpoint.state,
            metadata=checkpoint.metadata
            | {
                "created_at_ns": created_at_ns,
                "save_sequence": next_save_sequence,
            },
        )
        existing_checkpoint = self._find_checkpoint(
            conversation_id=checkpoint.conversation_id,
            checkpoint_id=checkpoint.checkpoint_id,
        )
        if existing_checkpoint is not None:
            checkpoint = ConversationCheckpoint(
                checkpoint_id=checkpoint.checkpoint_id,
                conversation_id=checkpoint.conversation_id,
                component_id=checkpoint.component_id,
                created_at=checkpoint.created_at,
                state=checkpoint.state,
                metadata=existing_checkpoint.metadata | checkpoint.metadata,
            )

        update_latest_where = {
            self.storage_config.conversation_id_column_name: checkpoint.conversation_id,
            self.storage_config.is_last_turn_column_name: 1,
        }
        update_latest_values = {self.storage_config.is_last_turn_column_name: 0}
        entity = self._checkpoint_to_entity(checkpoint)

        if isinstance(self.datastore, RelationalDatastore):
            data_table = self.datastore.data_tables[self.storage_config.table_name]
            with data_table.engine.connect() as connection:
                # Latest promotion is transactional for one writer, but the table does
                # not define a uniqueness constraint on (conversation_id, is_last_turn).
                # Shared relational deployments should use a single writer per conversation.
                connection.execute(
                    data_table._update_query(
                        where=update_latest_where,
                        update=update_latest_values,
                    )
                )
                if existing_checkpoint is None:
                    sql_create_stmt, new_entities = data_table._create_query([entity])
                    connection.execute(sql_create_stmt, new_entities)
                else:
                    update_checkpoint_where = {
                        self.storage_config.conversation_id_column_name: checkpoint.conversation_id,
                        self.storage_config.turn_id_column_name: checkpoint.checkpoint_id,
                    }
                    update_checkpoint_values = {
                        self.storage_config.agent_id_column_name: checkpoint.component_id,
                        self.storage_config.created_at_column_name: checkpoint.created_at,
                        self.storage_config.conversation_turn_state_column_name: checkpoint.state,
                        self.storage_config.is_last_turn_column_name: 1,
                        self.storage_config.extra_metadata_column_name: json.dumps(
                            checkpoint.metadata
                        ),
                    }
                    if self.storage_config.max_retention is not None:
                        update_checkpoint_values[self.storage_config.remove_by_column_name] = (
                            checkpoint.created_at + self.storage_config.max_retention
                        )
                    connection.execute(
                        data_table._update_query(
                            where=update_checkpoint_where,
                            update=update_checkpoint_values,
                        )
                    )
                connection.commit()
            return

        # Non-relational datastores follow the same logical promotion sequence.
        # They generally do not provide stronger concurrency guarantees than the
        # backing datastore implementation.
        self.datastore.update(
            collection_name=self.storage_config.table_name,
            where=update_latest_where,
            update=update_latest_values,
        )
        if existing_checkpoint is None:
            self.datastore.create(
                collection_name=self.storage_config.table_name,
                entities=[entity],
            )
        else:
            update_checkpoint_values = {
                self.storage_config.agent_id_column_name: checkpoint.component_id,
                self.storage_config.created_at_column_name: checkpoint.created_at,
                self.storage_config.conversation_turn_state_column_name: checkpoint.state,
                self.storage_config.is_last_turn_column_name: 1,
                self.storage_config.extra_metadata_column_name: json.dumps(checkpoint.metadata),
            }
            if self.storage_config.max_retention is not None:
                update_checkpoint_values[self.storage_config.remove_by_column_name] = (
                    checkpoint.created_at + self.storage_config.max_retention
                )
            self.datastore.update(
                collection_name=self.storage_config.table_name,
                where={
                    self.storage_config.conversation_id_column_name: checkpoint.conversation_id,
                    self.storage_config.turn_id_column_name: checkpoint.checkpoint_id,
                },
                update=update_checkpoint_values,
            )

    def list_checkpoints(
        self, conversation_id: str, limit: Optional[int] = 50
    ) -> List[ConversationCheckpoint]:
        checkpoints = self._sort_checkpoints(
            [
                self._entity_to_checkpoint(entity)
                for entity in self.datastore.list(
                    collection_name=self.storage_config.table_name,
                    where={self.storage_config.conversation_id_column_name: conversation_id},
                )
            ]
        )
        if limit is not None:
            should_apply_limit = len(checkpoints) > limit
            if should_apply_limit:
                checkpoints = checkpoints[-limit:]
        return checkpoints

    def delete(self, conversation_id: str, checkpoint_id: str) -> None:
        latest_checkpoint = self.load_latest(conversation_id)
        checkpoints = self.list_checkpoints(conversation_id, limit=None)
        checkpoint_to_promote: Optional[ConversationCheckpoint] = None
        is_deleting_latest_checkpoint = (
            latest_checkpoint is not None and latest_checkpoint.checkpoint_id == checkpoint_id
        )
        if is_deleting_latest_checkpoint:
            # Deleting the current latest checkpoint should leave the conversation
            # resumable from the next-newest checkpoint when one exists.
            remaining_checkpoints = [
                checkpoint
                for checkpoint in checkpoints
                if checkpoint.checkpoint_id != checkpoint_id
            ]
            checkpoint_to_promote = remaining_checkpoints[-1] if remaining_checkpoints else None

        delete_where = {
            self.storage_config.conversation_id_column_name: conversation_id,
            self.storage_config.turn_id_column_name: checkpoint_id,
        }

        if isinstance(self.datastore, RelationalDatastore):
            data_table = self.datastore.data_tables[self.storage_config.table_name]
            with data_table.engine.connect() as connection:
                # Keep deletion of the latest checkpoint and promotion of the previous
                # checkpoint atomic. Otherwise a crash between datastore.delete() and
                # datastore.update() could leave the conversation with no latest row.
                # This bypasses datatable.delete() because that helper executes and
                # commits immediately; here we need the DELETE and possible UPDATE to
                # share the same transaction.
                connection.execute(data_table._delete_query(where=delete_where))
                if checkpoint_to_promote is not None:
                    connection.execute(
                        data_table._update_query(
                            where={
                                self.storage_config.conversation_id_column_name: (
                                    checkpoint_to_promote.conversation_id
                                ),
                                self.storage_config.turn_id_column_name: (
                                    checkpoint_to_promote.checkpoint_id
                                ),
                            },
                            update={self.storage_config.is_last_turn_column_name: 1},
                        )
                    )
                connection.commit()
            return

        self.datastore.delete(
            collection_name=self.storage_config.table_name,
            where=delete_where,
        )

        if checkpoint_to_promote is not None:
            self.datastore.update(
                collection_name=self.storage_config.table_name,
                where={
                    self.storage_config.conversation_id_column_name: conversation_id,
                    self.storage_config.turn_id_column_name: checkpoint_to_promote.checkpoint_id,
                },
                update={self.storage_config.is_last_turn_column_name: 1},
            )


class InMemoryCheckpointer(DatastoreCheckpointer):
    """Checkpointer backed by an in-memory datastore."""

    def __init__(
        self,
        storage_config: Optional[StorageConfig] = None,
        checkpointing_interval: CheckpointingInterval = CheckpointingInterval.CONVERSATION_TURNS,
    ) -> None:
        resolved_storage_config = storage_config or StorageConfig()
        datastore = InMemoryDatastore(schema=resolved_storage_config.to_schema())
        super().__init__(
            datastore=datastore,
            storage_config=resolved_storage_config,
            checkpointing_interval=checkpointing_interval,
        )


class PostgresCheckpointer(DatastoreCheckpointer):
    """Checkpointer backed by PostgreSQL."""

    def __init__(
        self,
        connection_config: PostgresDatabaseConnectionConfig,
        storage_config: Optional[StorageConfig] = None,
        checkpointing_interval: CheckpointingInterval = CheckpointingInterval.CONVERSATION_TURNS,
    ) -> None:
        resolved_storage_config = storage_config or StorageConfig()
        datastore = PostgresDatabaseDatastore(
            schema=resolved_storage_config.to_schema(),
            connection_config=connection_config,
        )
        super().__init__(
            datastore=datastore,
            storage_config=resolved_storage_config,
            checkpointing_interval=checkpointing_interval,
        )
        self.connection_config = connection_config


class OracleDatabaseCheckpointer(DatastoreCheckpointer):
    """Checkpointer backed by Oracle Database."""

    def __init__(
        self,
        connection_config: OracleDatabaseConnectionConfig,
        storage_config: Optional[StorageConfig] = None,
        checkpointing_interval: CheckpointingInterval = CheckpointingInterval.CONVERSATION_TURNS,
    ) -> None:
        resolved_storage_config = storage_config or StorageConfig()
        datastore = OracleDatabaseDatastore(
            schema=resolved_storage_config.to_schema(),
            connection_config=connection_config,
        )
        super().__init__(
            datastore=datastore,
            storage_config=resolved_storage_config,
            checkpointing_interval=checkpointing_interval,
        )
        self.connection_config = connection_config
