# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Service interfaces for Code Executor Protocol execution."""

from __future__ import annotations

from wayflowcore.codeserver.backend import CodeExecutorBackend
from wayflowcore.codeserver.models import (
    CodeExecutionRequest,
    CreateSessionRequest,
    ExecutionResponse,
    SessionSnapshot,
)


class CodeExecutionService:
    """Coordinates execution requests, storage, sessions, and a backend."""

    def __init__(self, backend: CodeExecutorBackend) -> None:
        """Initialize the service with an execution backend.

        Parameters
        ----------
        backend:
            Backend responsible for running code.
        """
        self.backend = backend

    def execute(self, request: CodeExecutionRequest) -> ExecutionResponse:
        """Create an execution and optionally wait for its completion.

        Parameters
        ----------
        request:
            Execution request to submit.

        Returns
        -------
        ExecutionResponse
            Current execution snapshot.
        """
        raise NotImplementedError

    def create_execution(self, request: CodeExecutionRequest) -> ExecutionResponse:
        """Create an execution without waiting for completion.

        Parameters
        ----------
        request:
            Execution request to submit.

        Returns
        -------
        ExecutionResponse
            Initial execution snapshot.
        """
        raise NotImplementedError

    def get_execution(self, execution_id: str) -> ExecutionResponse:
        """Return the latest snapshot for an execution.

        Parameters
        ----------
        execution_id:
            Identifier of the execution to retrieve.

        Returns
        -------
        ExecutionResponse
            Latest execution snapshot.
        """
        raise NotImplementedError

    def cancel_execution(self, execution_id: str) -> ExecutionResponse:
        """Request cancellation of an execution.

        Parameters
        ----------
        execution_id:
            Identifier of the execution to cancel.

        Returns
        -------
        ExecutionResponse
            Execution snapshot after cancellation is requested.
        """
        raise NotImplementedError

    def create_session(self, request: CreateSessionRequest) -> SessionSnapshot:
        """Create a stateful execution session.

        Parameters
        ----------
        request:
            Session configuration, including the session language.

        Returns
        -------
        SessionSnapshot
            Initial active session snapshot.
        """
        raise NotImplementedError

    def get_session(self, session_id: str) -> SessionSnapshot:
        """Return the latest snapshot for a session.

        Parameters
        ----------
        session_id:
            Identifier of the session to retrieve.

        Returns
        -------
        SessionSnapshot
            Latest session snapshot.
        """
        raise NotImplementedError

    def close_session(self, session_id: str) -> SessionSnapshot:
        """Close a stateful execution session.

        Parameters
        ----------
        session_id:
            Identifier of the session to close.

        Returns
        -------
        SessionSnapshot
            Session snapshot after closure is requested.
        """
        raise NotImplementedError
