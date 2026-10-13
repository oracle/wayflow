# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Tests for failed code execution service requests."""

import pytest

from wayflowcore.codeserver.models import (
    TASK_STATUS_FAILED,
    CodeExecutionRequest,
    ExecutionResult,
    FunctionInput,
    ScriptInput,
)
from wayflowcore.codeserver.service import CodeExecutionService


def test_service_raises_on_unsupported_language(
    python_service: CodeExecutionService,
) -> None:
    """Raises when the requested language is not supported by the backend."""
    request = CodeExecutionRequest(
        language_id="ruby",
        input=[ScriptInput(type="script", source_code="puts 'hello'")],
        wait=True,
    )

    with pytest.raises(ValueError, match="Unsupported language"):
        python_service.execute(request)


def test_service_returns_failed_response_on_missing_function(
    python_service: CodeExecutionService,
) -> None:
    """Returns a failed response when the requested function is not defined."""
    request = CodeExecutionRequest(
        language_id="python",
        input=[
            FunctionInput(
                type="function",
                source_code="def multiply(a, b): return a * b",
                function_name="does_not_exist",
                arguments={"a": 1, "b": 2},
            )
        ],
        wait=True,
    )

    response = python_service.execute(request)

    assert response.status == TASK_STATUS_FAILED
    assert isinstance(response.output[0], ExecutionResult)
    assert response.output[0].is_error is True


def test_service_returns_failed_response_on_function_exception(
    python_service: CodeExecutionService,
) -> None:
    """Returns a failed response when the invoked function raises."""
    request = CodeExecutionRequest(
        language_id="python",
        input=[
            FunctionInput(
                type="function",
                source_code="def fail(): raise RuntimeError('boom')",
                function_name="fail",
                arguments={},
            )
        ],
        wait=True,
    )

    response = python_service.execute(request)

    assert response.status == TASK_STATUS_FAILED
    assert isinstance(response.output[0], ExecutionResult)
    assert response.output[0].is_error is True


def test_service_returns_failed_response_on_non_json_function_result(
    python_service: CodeExecutionService,
) -> None:
    """Returns a failed response when a function result is not JSON-compatible."""
    request = CodeExecutionRequest(
        language_id="python",
        input=[
            FunctionInput(
                type="function",
                source_code="def create_object(): return object()",
                function_name="create_object",
                arguments={},
            )
        ],
        wait=True,
    )

    response = python_service.execute(request)

    assert response.status == TASK_STATUS_FAILED
    assert isinstance(response.output[0], ExecutionResult)
    assert response.output[0].is_error is True
