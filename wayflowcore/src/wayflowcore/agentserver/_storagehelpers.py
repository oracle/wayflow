# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging
from textwrap import dedent
from typing import Dict, Optional, cast

from wayflowcore.agentserver.serverstorageconfig import ServerStorageConfig
from wayflowcore.component import Component
from wayflowcore.conversation import Conversation
from wayflowcore.datastore.oracle import OracleDatabaseConnectionConfig, _execute_query_on_oracle_db
from wayflowcore.datastore.postgres import (
    PostgresDatabaseConnectionConfig,
    _execute_query_on_postgres_db,
)
from wayflowcore.serialization import autodeserialize
from wayflowcore.serialization.context import DeserializationContext
from wayflowcore.tools import Tool

logger = logging.getLogger(__name__)


def _prepare_postgres_datastore(
    connection_config: PostgresDatabaseConnectionConfig, storage_config: ServerStorageConfig
) -> None:
    from sqlalchemy.exc import ProgrammingError

    create_table_query = dedent(
        f"""
        CREATE TABLE {storage_config.table_name} (
            {storage_config.turn_id_column_name} VARCHAR(255) PRIMARY KEY,
            {storage_config.agent_id_column_name} VARCHAR(255) NOT NULL,
            {storage_config.conversation_id_column_name} VARCHAR(255) NOT NULL,
            {storage_config.created_at_column_name} INTEGER NOT NULL,
            {storage_config.conversation_turn_state_column_name} TEXT NOT NULL,
            {storage_config.is_last_turn_column_name} INTEGER NOT NULL,
            {storage_config.extra_metadata_column_name} TEXT NOT NULL
        );
        """
    )
    try:
        _execute_query_on_postgres_db(connection_config, create_table_query)
    except ProgrammingError as e:
        if f'relation "{storage_config.table_name}" already exists' in str(e):
            raise ValueError(
                f'The datastore is already setup. Either delete the existing "{storage_config.table_name}" table or start the server with `--setup-datastore=no`.'
            ) from e
        else:
            raise e


def _prepare_oracle_datastore(
    connection_config: OracleDatabaseConnectionConfig, storage_config: ServerStorageConfig
) -> None:
    create_table_query = dedent(
        f"""
        CREATE TABLE {storage_config.table_name} (
            {storage_config.turn_id_column_name} VARCHAR2(255) PRIMARY KEY,
            {storage_config.agent_id_column_name} VARCHAR2(255) NOT NULL,
            {storage_config.conversation_id_column_name} VARCHAR2(255) NOT NULL,
            {storage_config.created_at_column_name} INTEGER NOT NULL,
            {storage_config.conversation_turn_state_column_name} CLOB NOT NULL,
            {storage_config.is_last_turn_column_name} INTEGER NOT NULL,
            {storage_config.extra_metadata_column_name} CLOB NOT NULL
        );
        """
    )
    try:
        _execute_query_on_oracle_db(connection_config, query=create_table_query)
    except Exception as e:
        if "already exists" in str(e):
            raise ValueError(
                f'The datastore is already setup. Either delete the existing "{storage_config.table_name}" table or start the server with `--setup-datastore=no`.'
            ) from e
        else:
            raise e


def _deserialize_conversation_safely(
    serialized_state: str,
    tool_registry: Optional[Dict[str, Tool]] = None,
    component: Optional[Component] = None,
) -> Conversation:
    """
    Tries to deserialize the conversation. If it does not work, try to deserialize it by considering
    the component as a disaggregated component, and will use the already instantiated agent instead of deserializing
    it from scratch.
    """
    deserialization_context = DeserializationContext()
    deserialization_context.registered_tools = tool_registry.copy() if tool_registry else {}
    try:
        conversation = autodeserialize(
            serialized_state, deserialization_context=deserialization_context
        )
    except (TypeError, ValueError) as e:
        if component is None:
            raise e
        # we try adding the ref to the agent itself, so that we fall back if
        # something went wrong during agent deserialization
        logger.warning(
            "Failed to deserialize conversation by itself: %s. Using a fallback approach that leverages the provided agent as a disaggregated one to deserialize the conversation.",
            e,
        )
        deserialization_context = DeserializationContext()
        deserialization_context.registered_tools = tool_registry.copy() if tool_registry else {}
        deserialization_context._add_component_to_context(component)

        conversation = autodeserialize(
            serialized_state, deserialization_context=deserialization_context
        )
    return cast(Conversation, conversation)
