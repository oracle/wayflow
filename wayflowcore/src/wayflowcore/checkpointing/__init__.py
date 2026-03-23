# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .base import Checkpointer
    from .datastore import (
        DatastoreCheckpointer,
        InMemoryCheckpointer,
        OracleDatabaseCheckpointer,
        PostgresCheckpointer,
    )
    from .models import CheckpointingInterval, ConversationCheckpoint, StorageConfig

__all__ = [
    "CheckpointingInterval",
    "Checkpointer",
    "ConversationCheckpoint",
    "DatastoreCheckpointer",
    "InMemoryCheckpointer",
    "OracleDatabaseCheckpointer",
    "PostgresCheckpointer",
    "StorageConfig",
]


def __getattr__(name: str) -> Any:
    if name in {"CheckpointingInterval", "ConversationCheckpoint", "StorageConfig"}:
        return getattr(import_module("wayflowcore.checkpointing.models"), name)
    if name == "Checkpointer":
        return getattr(import_module("wayflowcore.checkpointing.base"), name)
    if name in {
        "DatastoreCheckpointer",
        "InMemoryCheckpointer",
        "OracleDatabaseCheckpointer",
        "PostgresCheckpointer",
    }:
        return getattr(import_module("wayflowcore.checkpointing.datastore"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
