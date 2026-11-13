# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Tests for stateful code execution sessions."""

import pytest

from wayflowcore.codeserver.models import (
    TASK_STATUS_COMPLETED,
    CodeExecutionRequest,
    CreateSessionRequest,
    ExecutionResult,
    ScriptInput,
    TextContent,
)
from wayflowcore.codeserver.service import CodeExecutionService


def test_service_creates_session(python_service: CodeExecutionService) -> None:
    """Creates an active Python execution session."""
    session = python_service.create_session(CreateSessionRequest(language_id="python"))

    assert session.id
    assert session.object == "session"
    assert session.status == "active"
    assert session.language_id == "python"


def test_service_runs_code_in_session(python_service: CodeExecutionService) -> None:
    """Runs an execution against a created session."""
    session = python_service.create_session(CreateSessionRequest(language_id="python"))
    request = CodeExecutionRequest(
        language_id="python",
        session_id=session.id,
        input=[ScriptInput(type="script", source_code="print('hello')")],
    )

    response = python_service.execute(request)

    assert response.status == TASK_STATUS_COMPLETED
    assert response.language_id == "python"


def test_service_reuses_state_within_session(python_service: CodeExecutionService) -> None:
    """Reuses runtime state across executions in one session."""
    session = python_service.create_session(CreateSessionRequest(language_id="python"))
    python_service.execute(
        CodeExecutionRequest(
            language_id="python",
            session_id=session.id,
            input=[ScriptInput(type="script", source_code="value = 42")],
        )
    )

    response = python_service.execute(
        CodeExecutionRequest(
            language_id="python",
            session_id=session.id,
            input=[ScriptInput(type="script", source_code="print(value)")],
        )
    )

    assert response.output == [
        ExecutionResult(
            type="output",
            content=[TextContent(type="text", stream="stdout", text="42\n")],
        )
    ]


def test_service_does_not_share_state_between_sessions(
    python_service: CodeExecutionService,
) -> None:
    """Keeps runtime state isolated between sessions."""
    session_a = python_service.create_session(CreateSessionRequest(language_id="python"))
    session_b = python_service.create_session(CreateSessionRequest(language_id="python"))
    python_service.execute(
        CodeExecutionRequest(
            language_id="python",
            session_id=session_a.id,
            input=[ScriptInput(type="script", source_code="value = 42")],
        )
    )

    response = python_service.execute(
        CodeExecutionRequest(
            language_id="python",
            session_id=session_b.id,
            input=[ScriptInput(type="script", source_code="print(value)")],
        )
    )

    assert response.status == "failed"


def test_service_rejects_language_mismatch_in_session(
    python_service: CodeExecutionService,
) -> None:
    """Raises when an execution language differs from its session language."""
    session = python_service.create_session(CreateSessionRequest(language_id="python"))
    request = CodeExecutionRequest(
        language_id="javascript",
        session_id=session.id,
        input=[ScriptInput(type="script", source_code="console.log('hello')")],
    )

    with pytest.raises(ValueError, match="language"):
        python_service.execute(request)


def test_service_closes_session(python_service: CodeExecutionService) -> None:
    """Closes a session and prevents further executions in it."""
    session = python_service.create_session(CreateSessionRequest(language_id="python"))

    closed = python_service.close_session(session.id)

    assert closed.id == session.id
    assert closed.status == "closed"

    with pytest.raises(ValueError, match="closed"):
        python_service.execute(
            CodeExecutionRequest(
                language_id="python",
                session_id=session.id,
                input=[ScriptInput(type="script", source_code="print('hello')")],
            )
        )
