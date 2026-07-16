# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Datastore-backed persistence for Code Executor Protocol snapshots."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

from wayflowcore.codeserver.models import ExecutionResponse, SessionSnapshot
from wayflowcore.datastore import Datastore, Entity, InMemoryDatastore
from wayflowcore.property import StringProperty

_EXECUTIONS_COLLECTION = "code_executions"
_SESSIONS_COLLECTION = "code_sessions"
_ID_PROPERTY = "id"
_DATA_PROPERTY = "data"


def _storage_schema() -> dict[str, Entity]:
    """Build the datastore schema used for execution and session snapshots."""
    return {
        _EXECUTIONS_COLLECTION: Entity(
            properties={
                _ID_PROPERTY: StringProperty(),
                _DATA_PROPERTY: StringProperty(),
            }
        ),
        _SESSIONS_COLLECTION: Entity(
            properties={
                _ID_PROPERTY: StringProperty(),
                _DATA_PROPERTY: StringProperty(),
            }
        ),
    }


@dataclass
class CodeExecutorStorage:
    """Persist protocol snapshots through a configured :class:`Datastore`.

    Parameters
    ----------
    datastore:
        Datastore used for persistence. When omitted, an
        :class:`InMemoryDatastore` is created for local development and tests.
    """

    datastore: Datastore | None = None
    _datastore: Datastore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the configured or default datastore."""
        if self.datastore is not None:
            self._datastore = self.datastore
            return
        # The storage adapter explicitly documents this as its local default;
        # avoid repeating InMemoryDatastore's general-purpose warning here.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="InMemoryDatastore is for DEVELOPMENT",
                category=UserWarning,
            )
            self._datastore = InMemoryDatastore(_storage_schema())

    def create_execution(self, response: ExecutionResponse) -> ExecutionResponse:
        """Persist and return a new execution snapshot."""
        self._create(_EXECUTIONS_COLLECTION, response.id, response.model_dump_json(by_alias=True))
        return response

    def get_execution(self, execution_id: str) -> ExecutionResponse:
        """Retrieve an execution snapshot by identifier."""
        data = self._get_data(_EXECUTIONS_COLLECTION, execution_id)
        return ExecutionResponse.model_validate_json(data)

    def update_execution(self, response: ExecutionResponse) -> ExecutionResponse:
        """Replace an existing execution snapshot."""
        self._update(_EXECUTIONS_COLLECTION, response.id, response.model_dump_json(by_alias=True))
        return response

    def delete_execution(self, execution_id: str) -> None:
        """Delete an execution snapshot."""
        self._datastore.delete(_EXECUTIONS_COLLECTION, where={_ID_PROPERTY: execution_id})

    def create_session(self, snapshot: SessionSnapshot) -> SessionSnapshot:
        """Persist and return a new session snapshot."""
        self._create(_SESSIONS_COLLECTION, snapshot.id, snapshot.model_dump_json(by_alias=True))
        return snapshot

    def get_session(self, session_id: str) -> SessionSnapshot:
        """Retrieve a session snapshot by identifier."""
        data = self._get_data(_SESSIONS_COLLECTION, session_id)
        return SessionSnapshot.model_validate_json(data)

    def update_session(self, snapshot: SessionSnapshot) -> SessionSnapshot:
        """Replace an existing session snapshot."""
        self._update(_SESSIONS_COLLECTION, snapshot.id, snapshot.model_dump_json(by_alias=True))
        return snapshot

    def delete_session(self, session_id: str) -> None:
        """Delete a session snapshot."""
        self._datastore.delete(_SESSIONS_COLLECTION, where={_ID_PROPERTY: session_id})

    def _create(self, collection_name: str, record_id: str, data: str) -> None:
        """Create one serialized datastore record."""
        self._datastore.create(
            collection_name,
            {_ID_PROPERTY: record_id, _DATA_PROPERTY: data},
        )

    def _update(self, collection_name: str, record_id: str, data: str) -> None:
        """Update one serialized datastore record."""
        updated = self._datastore.update(
            collection_name,
            where={_ID_PROPERTY: record_id},
            update={_DATA_PROPERTY: data},
        )
        if not updated:
            raise KeyError(f"Record '{record_id}' was not found.")

    def _get_data(self, collection_name: str, record_id: str) -> str:
        """Retrieve the serialized payload for one datastore record."""
        records = self._datastore.list(
            collection_name,
            where={_ID_PROPERTY: record_id},
            limit=1,
        )
        if not records:
            raise KeyError(f"Record '{record_id}' was not found.")
        data = records[0].get(_DATA_PROPERTY)
        if not isinstance(data, str):
            raise TypeError(f"Record '{record_id}' contains invalid serialized data.")
        return data
