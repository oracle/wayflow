# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging

from wayflowcore.agentserver.serverstorageconfig import ServerStorageConfig
from wayflowcore.checkpointing.datastorecheckpointer import (
    _prepare_oracle_checkpoint_datastore,
    _prepare_postgres_checkpoint_datastore,
)
from wayflowcore.datastore.oracle import OracleDatabaseConnectionConfig
from wayflowcore.datastore.postgres import PostgresDatabaseConnectionConfig

logger = logging.getLogger(__name__)


def _prepare_postgres_datastore(
    connection_config: PostgresDatabaseConnectionConfig, storage_config: ServerStorageConfig
) -> None:
    _prepare_postgres_checkpoint_datastore(connection_config, storage_config)


def _prepare_oracle_datastore(
    connection_config: OracleDatabaseConnectionConfig, storage_config: ServerStorageConfig
) -> None:
    _prepare_oracle_checkpoint_datastore(connection_config, storage_config)
