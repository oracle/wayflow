# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Tests for code execution service and backend behavior."""

from wayflowcore.codeserver.models import (
    TASK_STATUS_COMPLETED,
    CodeExecutionRequest,
    ExecutionResponse,
    ExecutionResult,
    FunctionInput,
    ScriptInput,
    TextContent,
)
from wayflowcore.codeserver.service import CodeExecutionService


def test_service_runs_script_to_completion(python_service: CodeExecutionService) -> None:
    """Runs a script through the local Python backend and captures stdout."""
    request = CodeExecutionRequest(
        language_id="python",
        input=[
            ScriptInput(
                type="script",
                source_code="print('hello from the backend')",
            )
        ],
        wait=True,
    )

    response = python_service.execute(request)

    expected_response = ExecutionResponse(
        id=response.id,
        object="response",
        created_at=response.created_at,
        status=TASK_STATUS_COMPLETED,
        completed_at=response.completed_at,
        language_id="python",
        output=[
            ExecutionResult(
                type="output",
                content=[
                    TextContent(
                        type="text",
                        stream="stdout",
                        text="hello from the backend\n",
                    )
                ],
            )
        ],
        metadata=response.metadata,
    )

    assert response == expected_response


def test_service_runs_function_to_completion(python_service: CodeExecutionService) -> None:
    """Invokes a named function with JSON arguments and returns structured content."""
    request = CodeExecutionRequest(
        language_id="python",
        input=[
            FunctionInput(
                type="function",
                source_code="def multiply(a, b): return a * b",
                function_name="multiply",
                arguments={"a": 6, "b": 7},
            )
        ],
        wait=True,
    )

    response = python_service.execute(request)

    assert response.status == TASK_STATUS_COMPLETED
    assert response.output == [ExecutionResult(type="output", structured_content=42)]


def test_service_returns_empty_structured_content_for_script_without_result(
    python_service: CodeExecutionService,
) -> None:
    """Distinguishes no structured result from JSON null."""
    request = CodeExecutionRequest(
        language_id="python",
        input=[ScriptInput(type="script", source_code="print('done')")],
        wait=True,
    )

    response = python_service.execute(request)

    output = response.output[0]
    assert isinstance(output, ExecutionResult)
    assert "structured_content" not in output.model_fields_set


def test_service_preserves_json_null_function_result(python_service: CodeExecutionService) -> None:
    """Preserves a function result of None as JSON null."""
    request = CodeExecutionRequest(
        language_id="python",
        input=[
            FunctionInput(
                type="function",
                source_code="def produce_null(): return None",
                function_name="produce_null",
                arguments={},
            )
        ],
        wait=True,
    )

    response = python_service.execute(request)

    output = response.output[0]
    assert isinstance(output, ExecutionResult)
    assert output.structured_content is None
    assert "structured_content" in output.model_fields_set


def test_service_captures_stdout_and_stderr(python_service: CodeExecutionService) -> None:
    """Captures both standard output and standard error output."""
    request = CodeExecutionRequest(
        language_id="python",
        input=[
            ScriptInput(
                type="script",
                source_code=("import sys\n" "print('stdout')\n" "print('stderr', file=sys.stderr)"),
            )
        ],
        wait=True,
    )

    response = python_service.execute(request)

    assert response.output == [
        ExecutionResult(
            type="output",
            content=[
                TextContent(type="text", stream="stdout", text="stdout\n"),
                TextContent(type="text", stream="stderr", text="stderr\n"),
            ],
        )
    ]
