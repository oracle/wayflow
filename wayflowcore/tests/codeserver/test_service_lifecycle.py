# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Tests for code execution lifecycle operations."""

from wayflowcore.codeserver.models import (
    TASK_STATUS_CANCELLED,
    TASK_STATUS_TIMED_OUT,
    TASK_STATUS_WORKING,
    CodeExecutionRequest,
    ScriptInput,
)
from wayflowcore.codeserver.service import CodeExecutionService


def test_service_creates_pending_execution_when_wait_is_false(
    python_service: CodeExecutionService,
) -> None:
    """Creates a pollable execution when waiting is disabled."""
    request = CodeExecutionRequest(
        language_id="python",
        input=[ScriptInput(type="script", source_code="print('hello')")],
        wait=False,
    )

    response = python_service.create_execution(request)

    assert response.id
    assert response.status == TASK_STATUS_WORKING


def test_service_returns_execution_snapshot(
    python_service: CodeExecutionService,
) -> None:
    """Returns the latest snapshot for a created execution."""
    request = CodeExecutionRequest(
        language_id="python",
        input=[ScriptInput(type="script", source_code="print('hello')")],
        wait=False,
    )
    execution = python_service.create_execution(request)

    snapshot = python_service.get_execution(execution.id)

    assert snapshot.id == execution.id


def test_service_cancellation(python_service: CodeExecutionService) -> None:
    """Cancels an execution that has not completed."""
    request = CodeExecutionRequest(
        language_id="python",
        input=[ScriptInput(type="script", source_code="print('hello')")],
        wait=False,
    )
    execution = python_service.create_execution(request)

    response = python_service.cancel_execution(execution.id)

    assert response.id == execution.id
    assert response.status == TASK_STATUS_CANCELLED


def test_service_execution_timeout(python_service: CodeExecutionService) -> None:
    """Reports a timed-out execution using the backend timeout configuration."""
    request = CodeExecutionRequest(
        language_id="python",
        input=[ScriptInput(type="script", source_code="while True: pass")],
        wait=True,
    )

    response = python_service.execute(request)

    assert response.status == TASK_STATUS_TIMED_OUT
