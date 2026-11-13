# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Storage configuration for the Code Executor server."""

from __future__ import annotations

from dataclasses import dataclass

from wayflowcore.datastore import Datastore


@dataclass
class CodeExecutorServerStorageConfig:
    """Configuration for Code Executor execution and session snapshots."""

    datastore: Datastore | None = None
    """Datastore used for persistence."""

    executions_table_name: str = "code_executions"
    """Collection containing execution snapshots."""

    sessions_table_name: str = "code_sessions"
    """Collection containing session snapshots."""

    id_column_name: str = "id"
    """Column containing the public snapshot identifier."""

    data_column_name: str = "data"
    """Column containing the serialized snapshot."""
