# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Tests for the local Python execution backend."""

import time

from wayflowcore.codeserver.backend import (
    BackendExecutionResult,
    BackendHostCallbackRequest,
)
from wayflowcore.codeserver.backends.local_python import LocalPythonBackend
from wayflowcore.codeserver.models import (
    TASK_STATUS_CANCELLED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_INPUT_REQUIRED,
    TASK_STATUS_TIMED_OUT,
    HostCallbackResponse,
    HostInteractions,
)
from wayflowcore.codeserver.sessions import BackendSession


class _JavascriptSession(BackendSession):
    """Minimal non-Python session used to test backend language validation."""

    session_id = "session-1"
    language_id = "javascript"
    host_interactions = None

    @property
    def is_active(self) -> bool:
        """Return whether this test session is active."""
        return True

    def close(self) -> None:
        """Implement the backend session resource interface for this test."""


def test_local_python_backend_runs_script(python_backend: LocalPythonBackend) -> None:
    """Runs a script and returns its normalized backend result."""
    execution = python_backend.start_script("print('hello from the backend')")

    result = execution.wait()

    assert result == BackendExecutionResult(
        status=TASK_STATUS_COMPLETED,
        stdout="hello from the backend\n",
    )


def test_local_python_backend_runs_function(python_backend: LocalPythonBackend) -> None:
    """Runs a named function with JSON-compatible arguments."""
    execution = python_backend.start_function(
        "def multiply(a, b):\n    return a * b",
        "multiply",
        {"a": 6, "b": 7},
    )

    assert execution.wait() == BackendExecutionResult(
        status=TASK_STATUS_COMPLETED,
        structured_content=42,
    )


def test_local_python_backend_captures_stdout_and_stderr(
    python_backend: LocalPythonBackend,
) -> None:
    """Captures standard output and standard error independently."""
    execution = python_backend.start_script(
        "import sys\nprint('out')\nprint('err', file=sys.stderr)"
    )

    assert execution.wait() == BackendExecutionResult(
        status=TASK_STATUS_COMPLETED,
        stdout="out\n",
        stderr="err\n",
    )


def test_local_python_backend_preserves_json_null_function_result(
    python_backend: LocalPythonBackend,
) -> None:
    """Preserves ``None`` as a structured JSON null result."""
    execution = python_backend.start_function(
        "def produce_null():\n    return None",
        "produce_null",
        {},
    )

    result = execution.wait()

    assert result.status == TASK_STATUS_COMPLETED
    assert result.structured_content is None


def test_local_python_backend_isolates_stateless_executions(
    python_backend: LocalPythonBackend,
) -> None:
    """Does not share variables between stateless executions."""
    first = python_backend.start_script("secret = 42")
    assert first.wait().status == TASK_STATUS_COMPLETED

    second = python_backend.start_script("print(secret)")

    assert second.wait().status == TASK_STATUS_FAILED


def test_local_python_backend_rejects_unknown_function(
    python_backend: LocalPythonBackend,
) -> None:
    """Reports failure when the requested function is not defined."""
    execution = python_backend.start_function("value = 1", "missing", {})

    assert execution.wait().status == TASK_STATUS_FAILED


def test_local_python_backend_returns_failed_result_for_exception(
    python_backend: LocalPythonBackend,
) -> None:
    """Reports a function exception as a failed result."""
    execution = python_backend.start_function(
        "def fail():\n    raise ValueError('boom')",
        "fail",
        {},
    )

    result = execution.wait()

    assert result.status == TASK_STATUS_FAILED
    assert result.error is not None


def test_local_python_backend_returns_failed_result_for_non_json_result(
    python_backend: LocalPythonBackend,
) -> None:
    """Rejects a function result that cannot be represented as JSON."""
    execution = python_backend.start_function(
        "def produce_object():\n    return object()",
        "produce_object",
        {},
    )

    assert execution.wait().status == TASK_STATUS_FAILED


def test_local_python_backend_returns_timed_out_result(
    python_backend: LocalPythonBackend,
) -> None:
    """Stops an execution exceeding the configured timeout."""
    python_backend.execution_timeout_seconds = 0.05
    execution = python_backend.start_script("while True: pass")

    assert execution.wait().status == TASK_STATUS_TIMED_OUT


def test_local_python_backend_cancels_execution(python_backend: LocalPythonBackend) -> None:
    """Terminates an active execution when cancellation is requested."""
    execution = python_backend.start_script("while True: pass")
    time.sleep(0.01)

    assert execution.cancel().status == TASK_STATUS_CANCELLED


def test_local_python_backend_terminates_worker_after_timeout(
    python_backend: LocalPythonBackend,
) -> None:
    """Terminates the worker instead of leaving timed-out code running."""
    python_backend.execution_timeout_seconds = 0.05
    execution = python_backend.start_script("while True: pass")

    assert execution.wait().status == TASK_STATUS_TIMED_OUT
    assert execution.is_alive() is False


def test_local_python_backend_terminates_worker_after_cancellation(
    python_backend: LocalPythonBackend,
) -> None:
    """Terminates the worker process after cancellation."""
    execution = python_backend.start_script("while True: pass")
    time.sleep(0.01)

    assert execution.cancel().status == TASK_STATUS_CANCELLED
    assert execution.is_alive() is False


def test_local_python_backend_reuses_session_namespace(
    python_backend: LocalPythonBackend,
) -> None:
    """Preserves state across executions in one session."""
    session = python_backend.create_session("session-1", "python")
    assert (
        python_backend.start_script("value = 42", session=session).wait().status
        == TASK_STATUS_COMPLETED
    )

    result = python_backend.start_script("print(value)", session=session).wait()

    assert result.stdout == "42\n"


def test_local_python_backend_does_not_share_state_between_sessions(
    python_backend: LocalPythonBackend,
) -> None:
    """Keeps namespaces isolated between sessions."""
    first = python_backend.create_session("session-1", "python")
    second = python_backend.create_session("session-2", "python")
    python_backend.start_script("value = 42", session=first).wait()

    result = python_backend.start_script("print(value)", session=second).wait()

    assert result.status == TASK_STATUS_FAILED


def test_local_python_backend_rejects_language_mismatch(
    python_backend: LocalPythonBackend,
) -> None:
    """Rejects a session whose language does not match the backend request."""
    session = _JavascriptSession()

    execution = python_backend.start_script("print('hello')", session=session)

    assert execution.wait().status == TASK_STATUS_FAILED


def test_local_python_backend_returns_callback_host_request(
    python_backend: LocalPythonBackend,
) -> None:
    """Returns a host callback when Python invokes a host function.

    The syntax used to create a callback request may be backend-dependent.
    """
    session = python_backend.create_session(
        "session-1",
        "python",
        host_interactions=HostInteractions(
            enabled=True,
            allowed_request_types=["tool_execution"],
        ),
    )
    execution = python_backend.start_script(
        "result = host.tool_execution('lookup_weather', city='Paris')\nprint(result)",
        session=session,
    )

    result = execution.wait()

    assert result.status == TASK_STATUS_INPUT_REQUIRED
    assert result.host_callback_request == BackendHostCallbackRequest(
        request_id=result.host_callback_request.request_id,  # type: ignore[union-attr]
        request_type="tool_execution",
        name="lookup_weather",
        arguments={"city": "Paris"},
    )


def test_local_python_backend_resumes_after_callback_response(
    python_backend: LocalPythonBackend,
) -> None:
    """Resumes a paused session execution after a host callback response."""
    session = python_backend.create_session(
        "session-1",
        "python",
        host_interactions=HostInteractions(
            enabled=True,
            allowed_request_types=["tool_execution"],
        ),
    )
    execution = python_backend.start_script(
        "result = host.tool_execution('lookup_weather', city='Paris')\nprint(result)",
        session=session,
    )
    request = execution.wait()
    callback_request = request.host_callback_request
    assert callback_request is not None

    response = HostCallbackResponse(
        type="host_response",
        request_id=callback_request.request_id,
        result={"temperature": 21},
    )

    assert python_backend.resume_callback(session, response).wait().status == TASK_STATUS_COMPLETED


def test_local_python_backend_rejects_unknown_callback_request_id(
    python_backend: LocalPythonBackend,
) -> None:
    """Rejects a callback response that does not match a pending request."""
    session = python_backend.create_session(
        "session-1",
        "python",
        host_interactions=HostInteractions(
            enabled=True,
            allowed_request_types=["tool_execution"],
        ),
    )

    execution = python_backend.resume_callback(
        session,
        HostCallbackResponse(
            type="host_response",
            request_id="unknown",
            result={"temperature": 21},
        ),
    )

    assert execution.wait().status == TASK_STATUS_FAILED
