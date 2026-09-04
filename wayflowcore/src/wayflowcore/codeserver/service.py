# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Service interfaces for Code Executor Protocol execution."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from wayflowcore._utils.notgiven import NOT_GIVEN
from wayflowcore.codeserver.backend import (
    BackendExecutionContext,
    BackendExecutionResult,
    CodeExecutorBackend,
)
from wayflowcore.codeserver.models import (
    TASK_STATUS_CANCELLED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_INPUT_REQUIRED,
    TASK_STATUS_TIMED_OUT,
    TASK_STATUS_WORKING,
    CodeExecutionRequest,
    CreateSessionRequest,
    ExecutionResponse,
    ExecutionResult,
    FunctionInput,
    HostCallbackRequest,
    HostCallbackResponse,
    JsonValue,
    ScriptInput,
    SessionSnapshot,
    TextContent,
)
from wayflowcore.codeserver.sessions import BackendSession
from wayflowcore.codeserver.storage import CodeExecutorStorage


class CodeExecutionService:
    """Coordinates execution requests, storage, sessions, and a backend."""

    def __init__(
        self,
        backend: CodeExecutorBackend,
        storage: CodeExecutorStorage | None = None,
    ) -> None:
        """Initialize the service with an execution backend.

        Parameters
        ----------
        backend:
            Backend responsible for running code.
        """
        self.backend = backend
        self.storage = storage or CodeExecutorStorage()
        self._execution_contexts: dict[str, BackendExecutionContext] = {}
        self._sessions: dict[str, BackendSession] = {}

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
        if not request.wait:
            return self.create_execution(request)

        initial_response = self.create_execution(request)
        context = self._execution_contexts[initial_response.id]
        result = context.wait()
        if isinstance(request.input[0], HostCallbackResponse) and result.error is not None:
            raise ValueError(f"host request rejected: {result.error}")
        return self._update_execution(initial_response, result)

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
        context = self._start_execution(request)
        response = ExecutionResponse(
            id=self._create_execution_id(),
            object="response",
            created_at=datetime.now(timezone.utc),
            status=TASK_STATUS_WORKING,
            language_id=request.language_id,
            metadata=request.metadata,
        )
        self.storage.create_execution(response)
        self._execution_contexts[response.id] = context
        return response

    def _start_execution(self, request: CodeExecutionRequest) -> BackendExecutionContext:
        """Start one stateless script or function request on the backend."""
        self.backend.validate_language(request.language_id)
        session = None
        if request.session_id is not None:
            session = self._get_backend_session(request.session_id)
            if request.language_id != session.language_id:
                raise ValueError("Execution language does not match session language.")
            if not session.is_active:
                raise ValueError("Session is closed.")

        input_item = request.input[0]
        if isinstance(input_item, ScriptInput):
            return self.backend.start_script(input_item.source_code, session=session)
        if isinstance(input_item, FunctionInput):
            return self.backend.start_function(
                input_item.source_code,
                input_item.function_name,
                input_item.arguments,
                session=session,
            )
        if isinstance(input_item, HostCallbackResponse):
            if session is None:
                raise ValueError("Host callback responses require a session.")
            return self.backend.resume_callback(session, input_item)
        raise TypeError(f"Unsupported execution input: {type(input_item).__name__}")

    def _update_execution(
        self,
        previous_response: ExecutionResponse,
        result: BackendExecutionResult,
    ) -> ExecutionResponse:
        """Update one stored response from its latest backend result."""
        response = self._result_to_response(
            execution_id=previous_response.id,
            created_at=previous_response.created_at,
            language_id=previous_response.language_id,
            result=result,
            request_metadata=previous_response.metadata,
            completed_at=previous_response.completed_at,
        )
        self.storage.update_execution(response)
        return response

    @staticmethod
    def _create_execution_id() -> str:
        """Create one public execution identifier."""
        return f"exec_{uuid4().hex}"

    def _result_to_response(
        self,
        *,
        execution_id: str,
        created_at: datetime,
        language_id: str,
        result: BackendExecutionResult,
        request_metadata: dict[str, JsonValue],
        completed_at: datetime | None = None,
    ) -> ExecutionResponse:
        """Convert one backend result into a protocol execution snapshot."""
        output = [] if result.status == TASK_STATUS_WORKING else [self._result_to_output(result)]
        if completed_at is None and result.status in {
            TASK_STATUS_COMPLETED,
            TASK_STATUS_FAILED,
            TASK_STATUS_TIMED_OUT,
            TASK_STATUS_CANCELLED,
        }:
            completed_at = datetime.now(timezone.utc)
        metadata = dict(request_metadata)
        if result.metadata:
            metadata.update(result.metadata)
        if result.error is not None:
            metadata["error"] = result.error
        return ExecutionResponse(
            id=execution_id,
            object="response",
            created_at=created_at,
            status=result.status,
            completed_at=completed_at,
            language_id=language_id,
            output=output,
            metadata=metadata,
        )

    @staticmethod
    def _result_to_output(
        result: BackendExecutionResult,
    ) -> ExecutionResult | HostCallbackRequest:
        """Convert backend output and callback data into a protocol output item."""
        if result.status == TASK_STATUS_INPUT_REQUIRED:
            if result.host_callback_request is None:
                raise ValueError("Backend requested input without a callback request.")
            callback = result.host_callback_request
            return HostCallbackRequest(
                type="host_request",
                request_id=callback.request_id,
                request_type=callback.request_type,
                name=callback.name,
                arguments=callback.arguments,
            )

        content: list[TextContent] = []
        if result.stdout:
            content.append(TextContent(type="text", stream="stdout", text=result.stdout))
        if result.stderr:
            content.append(TextContent(type="text", stream="stderr", text=result.stderr))
        structured_fields = (
            {"structured_content": result.structured_content}
            if result.structured_content is not NOT_GIVEN
            else {}
        )
        return ExecutionResult(
            type="output",
            content=content,
            is_error=result.status != TASK_STATUS_COMPLETED,
            **structured_fields,
        )

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
        response = self.storage.get_execution(execution_id)
        context = self._execution_contexts.get(execution_id)
        if context is None or response.status not in {
            TASK_STATUS_WORKING,
            TASK_STATUS_INPUT_REQUIRED,
        }:
            return response
        return self._update_execution(response, context.get_result())

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
        response = self.storage.get_execution(execution_id)
        context = self._execution_contexts.get(execution_id)
        if context is None or response.status not in {"working", TASK_STATUS_INPUT_REQUIRED}:
            return response
        return self._update_execution(response, context.cancel())

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
        self.backend.validate_language(request.language_id)
        session_id = self._create_session_id()
        backend_session = self.backend.create_session(
            session_id,
            request.language_id,
            host_interactions=request.host_interactions,
        )
        self._sessions[session_id] = backend_session
        snapshot = SessionSnapshot(
            id=session_id,
            object="session",
            status="active",
            language_id=request.language_id,
            host_interactions=request.host_interactions,
            metadata=request.metadata,
        )
        return self.storage.create_session(snapshot)

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
        return self.storage.get_session(session_id)

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
        snapshot = self.storage.get_session(session_id)
        if snapshot.status == "closed":
            return snapshot
        backend_session = self._get_backend_session(session_id)
        self.backend.close_session(backend_session)
        self._sessions.pop(session_id, None)
        closed = snapshot.model_copy(update={"status": "closed"})
        return self.storage.update_session(closed)

    @staticmethod
    def _create_session_id() -> str:
        """Create one public session identifier."""
        return f"sess_{uuid4().hex}"

    def _get_backend_session(self, session_id: str) -> BackendSession:
        """Return the backend session associated with a public identifier."""
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            try:
                snapshot = self.storage.get_session(session_id)
            except KeyError:
                raise ValueError(f"Unknown session id: {session_id}") from exc
            if snapshot.status == "closed":
                raise ValueError("Session is closed.") from exc
            raise ValueError(f"Unknown session id: {session_id}") from exc
