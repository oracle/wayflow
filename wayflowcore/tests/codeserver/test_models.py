# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Tests for the Code Executor Protocol wire models."""

import pytest

from wayflowcore.codeserver.models import (
    CodeExecutionRequest,
    CreateSessionRequest,
    ExecutionResponse,
    ExecutionResult,
    FunctionInput,
    HostCallbackRequest,
    HostCallbackResponse,
    ScriptInput,
    SessionSnapshot,
    TextContent,
)


def test_script_execution_request_accepts_protocol_shape() -> None:
    """Validates a script request."""
    request = CodeExecutionRequest.model_validate(
        {
            "language_id": "python",
            "input": [
                {
                    "type": "script",
                    "source_code": "print('hello')",
                }
            ],
            "dependencies": [],
            "session_id": "sess_123",
            "metadata": {"caller": "test"},
            "wait": True,
        }
    )

    assert request.language_id == "python"
    assert len(request.input) == 1
    assert request.input[0].type == "script"
    assert request.input[0].source_code == "print('hello')"
    assert request.dependencies == []
    assert request.session_id == "sess_123"
    assert request.metadata == {"caller": "test"}
    assert request.wait is True


def test_function_execution_request_accepts_protocol_shape() -> None:
    """Validates a function request with named JSON arguments."""
    request = CodeExecutionRequest.model_validate(
        {
            "language_id": "python",
            "input": [
                {
                    "type": "function",
                    "source_code": "def multiply(a, b): return a * b",
                    "function_name": "multiply",
                    "arguments": {"a": 6, "b": 7},
                }
            ],
            "wait": True,
        }
    )

    assert isinstance(request.input[0], FunctionInput)
    assert request.input[0].function_name == "multiply"
    assert request.input[0].arguments == {"a": 6, "b": 7}


def test_execution_request_raises_on_unknown_input_type() -> None:
    """Raises when an input item type is not supported by the protocol."""
    with pytest.raises(ValueError):
        CodeExecutionRequest.model_validate(
            {
                "language_id": "python",
                "input": [{"type": "unknown", "source_code": "pass"}],
                "wait": True,
            }
        )


def test_execution_request_raises_on_multiple_input_items() -> None:
    """Raises when more than one executable input item is supplied."""
    with pytest.raises(ValueError):
        CodeExecutionRequest.model_validate(
            {
                "language_id": "python",
                "input": [
                    {"type": "script", "source_code": "pass"},
                    {"type": "script", "source_code": "pass"},
                ],
                "wait": True,
            }
        )


def test_script_input_raises_on_function_fields() -> None:
    """Raises when function-only fields are supplied on a script input item."""
    with pytest.raises(ValueError):
        ScriptInput.model_validate(
            {
                "type": "script",
                "source_code": "print('hello')",
                "function_name": "main",
            }
        )


def test_function_input_raises_on_missing_function_name() -> None:
    """Raises when a function name is missing from a function input item."""
    with pytest.raises(ValueError):
        FunctionInput.model_validate(
            {
                "type": "function",
                "source_code": "def main(): return 1",
                "arguments": {},
            }
        )


def test_function_input_raises_on_non_object_arguments() -> None:
    """Raises when named arguments are not represented by a JSON object."""
    with pytest.raises(ValueError):
        FunctionInput.model_validate(
            {
                "type": "function",
                "source_code": "def main(): return 1",
                "function_name": "main",
                "arguments": [1, 2],  # should be {"a": 1, "b": 1}
            }
        )


@pytest.mark.parametrize("value", [{"answer": 42}, [1, 2], "done", 42, True, None])
def test_structured_content_accepts_any_json_value(value: object) -> None:
    """Accepts any JSON value as structured execution content."""
    output = ExecutionResult.model_validate(
        {
            "type": "output",
            "content": [{"type": "text", "text": "done"}],
            "structuredContent": value,
            "isError": False,
        }
    )

    assert output.structured_content == value
    assert isinstance(output.content[0], TextContent)


def test_execution_response_accepts_terminal_snapshot() -> None:
    """Validates the Pydantic response model returned by the service."""
    response = ExecutionResponse.model_validate(
        {
            "id": "exec_123",
            "object": "response",
            "created_at": "2026-06-04T12:00:00Z",
            "status": "completed",
            "completed_at": "2026-06-04T12:00:02Z",
            "language_id": "python",
            "output": [
                {
                    "type": "output",
                    "content": [{"type": "text", "text": "done\n"}],
                }
            ],
        }
    )

    assert response.id == "exec_123"
    assert response.status == "completed"
    assert response.output[0].content[0].text == "done\n"


def test_host_request_and_host_response_models() -> None:
    """Validates the retained host interaction vocabulary."""
    request = HostCallbackRequest.model_validate(
        {
            "type": "host_request",
            "request_id": "req_123",
            "request_type": "tool_execution",
            "name": "lookup_weather",
            "arguments": {"city": "Paris"},
        }
    )
    response = HostCallbackResponse.model_validate(
        {
            "type": "host_response",
            "request_id": "req_123",
            "result": {"temperature": 21},
        }
    )

    assert request.request_type == "tool_execution"
    assert request.arguments == {"city": "Paris"}
    assert response.request_id == request.request_id
    assert response.result == {"temperature": 21}


def test_session_request_and_snapshot_models() -> None:
    """Validates session creation and lifecycle snapshot models."""
    request = CreateSessionRequest.model_validate(
        {
            "language_id": "python",
            "host_interactions": {
                "enabled": True,
                "allowed_request_types": ["tool_execution"],
            },
            "metadata": {"owner": "test"},
        }
    )
    snapshot = SessionSnapshot.model_validate(
        {
            "id": "sess_123",
            "object": "session",
            "status": "active",
            "language_id": "python",
            "host_interactions": {
                "enabled": True,
                "allowed_request_types": ["tool_execution"],
            },
            "metadata": {"owner": "test"},
        }
    )

    assert request.language_id == snapshot.language_id
    assert snapshot.id == "sess_123"
    assert snapshot.status == "active"
