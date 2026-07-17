# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Local Python execution backend and queue-worker process handles."""

from __future__ import annotations

import multiprocessing
import os
import queue
import signal
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from multiprocessing.process import BaseProcess
from multiprocessing.queues import Queue
from threading import Lock
from typing import cast

from wayflowcore.codeserver.backend import (
    BackendExecutionContext,
    BackendExecutionResult,
    BackendHostCallbackRequest,
    CodeExecutorBackend,
)
from wayflowcore.codeserver.backends.pythonexecutionpolicy import PythonExecutionPolicy
from wayflowcore.codeserver.backends.pythonworker import worker_main
from wayflowcore.codeserver.models import (
    TASK_STATUS_CANCELLED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_INPUT_REQUIRED,
    TASK_STATUS_TIMED_OUT,
    HostCallbackResponse,
    HostInteractions,
    JsonValue,
)
from wayflowcore.codeserver.sessions import BackendSession

WorkerCommand = dict[str, object]
WorkerMessage = dict[str, object]


@dataclass
class LocalPythonBackend(CodeExecutorBackend):
    """Backend configuration for executing Python locally."""

    policy: PythonExecutionPolicy | None = None
    cancel_grace_seconds: float = 0.5
    """Time allowed for a worker to exit after a termination request."""

    max_stdout_chars: int = 50_000
    """Maximum captured standard-output characters per execution."""

    max_stderr_chars: int = 50_000
    """Maximum captured standard-error characters per execution."""

    _sessions: dict[str, LocalPythonSession] = field(default_factory=dict, init=False, repr=False)

    def get_capabilities(self) -> dict[str, JsonValue]:
        """Return capabilities supported by the local Python backend."""
        return {
            "supported_languages": ["python"],
            "execution_modes": ["script", "function"],
            "supports_sessions": True,
            "supports_host_interactions": True,
        }

    def validate_language(self, language_id: str) -> None:
        """Validate that the local backend supports Python."""
        if language_id != "python":
            raise ValueError(f"Unsupported language: {language_id}")

    def start_script(
        self,
        source_code: str,
        *,
        session: BackendSession | None = None,
    ) -> LocalPythonExecution:
        """Start a Python script in a worker process."""
        if self.policy is not None:
            self.policy.validate_script(source_code)
        return self._start_execution(
            {
                "type": "run",
                "mode": "script",
                "source_code": source_code,
            },
            session=session,
        )

    def start_function(
        self,
        source_code: str,
        function_name: str,
        arguments: Mapping[str, JsonValue],
        *,
        session: BackendSession | None = None,
    ) -> LocalPythonExecution:
        """Start a Python function in a worker process."""
        if self.policy is not None:
            self.policy.validate_function(source_code, function_name)
        return self._start_execution(
            {
                "type": "run",
                "mode": "function",
                "source_code": source_code,
                "function_name": function_name,
                "arguments": dict(arguments),
            },
            session=session,
        )

    def create_session(
        self,
        session_id: str,
        language_id: str,
        *,
        host_interactions: HostInteractions | None = None,
    ) -> LocalPythonSession:
        """Create one retained local Python worker session."""
        self.validate_language(language_id)
        command_queue, result_queue, process = self._spawn_worker(session_mode=True)
        session = LocalPythonSession(
            session_id=session_id,
            language_id=language_id,
            process=process,
            command_queue=command_queue,
            result_queue=result_queue,
            host_interactions=host_interactions,
        )
        self._sessions[session_id] = session
        return session

    def resume_callback(
        self,
        session: BackendSession,
        response: HostCallbackResponse,
    ) -> LocalPythonExecution:
        """Resume a paused local Python session from a host response."""
        local_session = self._require_local_python_session(session)
        with local_session.lock:
            if local_session.pending_callback_request_id != response.request_id:
                return self._failed_execution("Unknown host callback request id.")
            if not local_session.is_active:
                return self._failed_execution("Session is no longer active.")
            local_session.pending_callback_request_id = None
            execution_id = self._create_new_execution_id()
            local_session.active_execution_id = execution_id
            local_session.command_queue.put(
                {
                    "type": "callback_response",
                    "request_id": response.request_id,
                    "result": response.result,
                }
            )
        return LocalPythonExecution(
            execution_id=execution_id,
            backend=self,
            process=local_session.process,
            command_queue=local_session.command_queue,
            result_queue=local_session.result_queue,
            session=local_session,
            deadline=time.monotonic() + self.execution_timeout_seconds,
        )

    def close_session(self, session: BackendSession) -> None:
        """Close a retained local Python worker session."""
        local_session = self._require_local_python_session(session)
        with local_session.lock:
            if local_session.closed:
                return
            local_session.close()
            local_session.process.join(self.cancel_grace_seconds)
            if local_session.process.is_alive():
                self._terminate_process(local_session.process)
            _close_queue(local_session.command_queue)
            _close_queue(local_session.result_queue)
            self._sessions.pop(session.session_id, None)

    def close_all_sessions(self) -> None:
        """Close every session still owned by this backend instance."""
        for session in list(self._sessions.values()):
            self.close_session(session)

    def _start_execution(
        self,
        command: WorkerCommand,
        *,
        session: BackendSession | None,
    ) -> LocalPythonExecution:
        """Start one worker command statelessly or in a retained session."""
        command.update(
            {
                "max_stdout_chars": self.max_stdout_chars,
                "max_stderr_chars": self.max_stderr_chars,
            }
        )
        if session is None:
            command["host_interactions_enabled"] = False  # only sessions can use host interactions
            command_queue, result_queue, process = self._spawn_worker(session_mode=False)
            command_queue.put(command)
            return LocalPythonExecution(
                execution_id=self._create_new_execution_id(),
                backend=self,
                process=process,
                command_queue=command_queue,
                result_queue=result_queue,
                deadline=time.monotonic() + self.execution_timeout_seconds,
            )

        if session.language_id != "python":
            return self._failed_execution("Session language does not match the Python backend.")
        local_session = self._require_local_python_session(session)
        with local_session.lock:
            if not local_session.is_active:
                return self._failed_execution("Session is no longer active.")
            if local_session.active_execution_id is not None:
                return self._failed_execution("Session already has an active execution.")
            if not local_session.process.is_alive():
                local_session.failed = True
                return self._failed_execution("Session worker exited unexpectedly.")
            execution_id = self._create_new_execution_id()
            local_session.active_execution_id = execution_id
            command["host_interactions_enabled"] = _host_interactions_enabled(
                local_session.host_interactions
            )
            local_session.command_queue.put(command)
        return LocalPythonExecution(
            execution_id=execution_id,
            backend=self,
            process=local_session.process,
            command_queue=local_session.command_queue,
            result_queue=local_session.result_queue,
            session=local_session,
            deadline=time.monotonic() + self.execution_timeout_seconds,
        )

    def _spawn_worker(
        self, *, session_mode: bool
    ) -> tuple[Queue[object], Queue[object], BaseProcess]:
        """Create and start one local Python worker process."""
        context = multiprocessing.get_context("spawn")
        # multiprocessing.queues.Queue is not subscriptable at runtime on
        # Python 3.11, so keep the generic form in annotations only.
        command_queue = context.Queue()
        result_queue = context.Queue()
        process = context.Process(
            target=worker_main,
            args=(command_queue, result_queue, self.policy),
            kwargs={"session_mode": session_mode},
        )
        process.daemon = True
        process.start()
        return command_queue, result_queue, process

    def _terminate_process(self, process: BaseProcess) -> None:
        """Terminate a worker process and its descendants when supported."""
        if not process.is_alive():
            return
        if os.name == "posix" and process.pid is not None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                process.terminate()
        else:
            process.terminate()
        process.join(self.cancel_grace_seconds)
        if not process.is_alive():
            return
        if os.name == "posix" and process.pid is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                process.kill()
        else:
            process.kill()
        process.join()

    def _require_local_python_session(self, session: BackendSession) -> LocalPythonSession:
        """Require a session owned by this local Python backend."""
        if not isinstance(session, LocalPythonSession):
            raise ValueError("Session does not belong to the local Python backend.")
        return session

    def _failed_execution(self, error: str) -> LocalPythonExecution:
        """Create an execution handle already resolved to failure."""
        return LocalPythonExecution(
            execution_id=self._create_new_execution_id(),
            backend=self,
            result=BackendExecutionResult(status=TASK_STATUS_FAILED, error=error),
        )

    @staticmethod
    def _create_new_execution_id() -> str:
        """Create one backend-local execution identifier."""
        return f"exec_{uuid.uuid4().hex}"


@dataclass
class LocalPythonExecution(BackendExecutionContext):
    """Handle for one local Python worker execution."""

    execution_id: str
    backend: LocalPythonBackend = field(repr=False)
    process: BaseProcess | None = field(default=None, repr=False)
    command_queue: Queue[object] | None = field(default=None, repr=False)
    result_queue: Queue[object] | None = field(default=None, repr=False)
    session: LocalPythonSession | None = field(default=None, repr=False)
    deadline: float | None = field(default=None, repr=False)
    result: BackendExecutionResult | None = None

    def get_result(self) -> BackendExecutionResult:
        """Return the latest worker result without blocking."""
        if self.result is None:
            self._consume_available_messages()
            self._check_timeout()
            self._check_worker_exit()
        return self.result or BackendExecutionResult(status="working")

    def wait(self) -> BackendExecutionResult:
        """Wait for the worker to finish or request host input."""
        while self.result is None:
            self._check_timeout()
            if self.result is not None:
                break
            self._wait_for_message(self._remaining_timeout())
            self._check_worker_exit()
        if self.result is None:
            raise RuntimeError("Execution worker exited without producing a result.")
        return self.result

    def cancel(self) -> BackendExecutionResult:
        """Terminate the worker and return its cancellation result."""
        if self.result is not None:
            return self.result
        if self.process is not None:
            self.backend._terminate_process(self.process)
        if self.session is not None:
            self.session.failed = True
        self._set_terminal_result(BackendExecutionResult(status=TASK_STATUS_CANCELLED))
        if self.result is None:
            raise RuntimeError("Execution cancellation did not produce a result.")
        return self.result

    def is_alive(self) -> bool:
        """Return whether the backing worker process is still alive."""
        return self.process is not None and self.process.is_alive()

    def _consume_available_messages(self) -> None:
        """Update the current result from messages already sent by the worker."""
        if self.result_queue is None:
            return
        while self.result is None:
            try:
                message = self.result_queue.get_nowait()
            except queue.Empty:
                return
            self._handle_message(message)

    def _wait_for_message(self, timeout_seconds: float | None) -> None:
        """Wait for one worker message and update the current result."""
        if self.result_queue is None:
            self._set_terminal_result(
                BackendExecutionResult(
                    status=TASK_STATUS_FAILED, error="Execution has no worker queue."
                )
            )
            return
        try:
            message = self.result_queue.get(timeout=timeout_seconds)
        except queue.Empty:
            self._check_timeout()
            return
        self._handle_message(message)

    def _handle_message(self, raw_message: object) -> None:
        """Convert one worker message into a normalized backend result."""
        if not isinstance(raw_message, dict) or not all(
            isinstance(key, str) for key in raw_message
        ):
            self._set_terminal_result(
                BackendExecutionResult(
                    status=TASK_STATUS_FAILED, error="Worker returned an invalid message."
                )
            )
            return
        message = cast(WorkerMessage, raw_message)
        message_type = message.get("type")
        stdout = _optional_str(message.get("stdout"))
        stderr = _optional_str(message.get("stderr"))
        metadata = _truncation_metadata(message)
        if message_type == "completed":
            if "structured_content" in message:
                structured_content = _json_value(message["structured_content"])
                self._set_terminal_result(
                    BackendExecutionResult(
                        status=TASK_STATUS_COMPLETED,
                        stdout=stdout,
                        stderr=stderr,
                        structured_content=structured_content,
                        metadata=metadata,
                    )
                )
            else:
                self._set_terminal_result(
                    BackendExecutionResult(
                        status=TASK_STATUS_COMPLETED,
                        stdout=stdout,
                        stderr=stderr,
                        metadata=metadata,
                    )
                )
            return
        if message_type == "failed":
            self._set_terminal_result(
                BackendExecutionResult(
                    status=TASK_STATUS_FAILED,
                    stdout=stdout,
                    stderr=stderr,
                    error=_optional_str(message.get("error")) or "Python execution failed.",
                    metadata=metadata,
                )
            )
            return
        if message_type == "host_request":
            request = BackendHostCallbackRequest(
                request_id=_required_str(message, "request_id"),
                request_type=_required_str(message, "request_type"),
                name=_required_str(message, "name"),
                arguments=_json_object(message.get("arguments")),
            )
            if self.session is None:
                self._set_terminal_result(
                    BackendExecutionResult(
                        status=TASK_STATUS_FAILED,
                        error="Host callbacks require a retained session.",
                    )
                )
                return
            self.session.pending_callback_request_id = request.request_id
            self.result = BackendExecutionResult(
                status=TASK_STATUS_INPUT_REQUIRED,
                stdout=stdout,
                stderr=stderr,
                host_callback_request=request,
                metadata=metadata,
            )
            return
        self._set_terminal_result(
            BackendExecutionResult(
                status=TASK_STATUS_FAILED, error="Worker returned an unknown message."
            )
        )

    def _check_timeout(self) -> None:
        """Terminate an execution whose parent-side deadline has elapsed."""
        if self.result is not None or self.deadline is None or time.monotonic() < self.deadline:
            return
        if self.process is not None:
            self.backend._terminate_process(self.process)
        if self.session is not None:
            self.session.failed = True
        self._set_terminal_result(BackendExecutionResult(status=TASK_STATUS_TIMED_OUT))

    def _check_worker_exit(self) -> None:
        """Report unexpected worker exit when no result has been received."""
        if self.result is None and self.process is not None and not self.process.is_alive():
            self._set_terminal_result(
                BackendExecutionResult(
                    status=TASK_STATUS_FAILED, error="Python worker exited unexpectedly."
                )
            )

    def _remaining_timeout(self) -> float | None:
        """Return time remaining until this execution reaches its deadline."""
        if self.deadline is None:
            return None
        return max(0.0, self.deadline - time.monotonic())

    def _set_terminal_result(self, result: BackendExecutionResult) -> None:
        """Store a terminal result and release a session for later commands."""
        self.result = result
        if self.session is not None and result.status != TASK_STATUS_INPUT_REQUIRED:
            with self.session.lock:
                if self.session.active_execution_id == self.execution_id:
                    self.session.active_execution_id = None
        if self.session is None and result.status != TASK_STATUS_INPUT_REQUIRED:
            if self.process is not None:
                self.process.join(self.backend.cancel_grace_seconds)
            if self.command_queue is not None:
                _close_queue(self.command_queue)
            if self.result_queue is not None:
                _close_queue(self.result_queue)


@dataclass
class LocalPythonSession(BackendSession):
    """Handle for a long-lived local Python session worker."""

    session_id: str
    language_id: str
    process: BaseProcess
    command_queue: Queue[object]
    result_queue: Queue[object]
    host_interactions: HostInteractions | None = None
    lock: Lock = field(default_factory=Lock, repr=False)
    pending_callback_request_id: str | None = None
    active_execution_id: str | None = None
    closed: bool = False
    failed: bool = False

    @property
    def is_active(self) -> bool:
        """Return whether this session can accept another worker command."""
        return not self.closed and not self.failed

    def close(self) -> None:
        """Request graceful closure of the retained worker."""
        if not self.closed and self.process.is_alive():
            self.command_queue.put({"type": "close"})
        self.closed = True


def _host_interactions_enabled(host_interactions: HostInteractions | None) -> bool:
    """Return whether tool-execution callbacks are allowed for a session."""
    return (
        host_interactions is not None
        and host_interactions.enabled
        and "tool_execution" in host_interactions.allowed_request_types
    )


def _optional_str(value: object) -> str:
    """Return a string value or an empty string for an absent invalid field."""
    return value if isinstance(value, str) else ""


def _required_str(message: Mapping[str, object], name: str) -> str:
    """Return one required string worker-message field."""
    value = message.get(name)
    if not isinstance(value, str):
        raise ValueError(f"Worker message field '{name}' must be a string.")
    return value


def _json_object(value: object) -> dict[str, JsonValue]:
    """Return one JSON object value or raise for invalid worker data."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("Worker callback arguments must be a JSON object.")
    return {key: _json_value(item) for key, item in value.items()}


def _json_value(value: object) -> JsonValue:
    """Validate a value recursively as JSON-compatible worker data."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {key: _json_value(item) for key, item in value.items()}
    raise ValueError("Worker returned a non-JSON-compatible value.")


def _truncation_metadata(message: Mapping[str, object]) -> dict[str, JsonValue] | None:
    """Return output-truncation metadata when the worker reported it."""
    metadata: dict[str, JsonValue] = {}
    if message.get("stdout_truncated") is True:
        metadata["stdout_truncated"] = True
    if message.get("stderr_truncated") is True:
        metadata["stderr_truncated"] = True
    return metadata or None


def _close_queue(worker_queue: Queue[object]) -> None:
    """Close one parent-owned multiprocessing queue and its feeder thread."""
    worker_queue.close()
    worker_queue.join_thread()
