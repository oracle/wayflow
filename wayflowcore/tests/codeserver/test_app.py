# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""HTTP tests for the Code Executor Protocol application."""

import time

import pytest
from fastapi.testclient import TestClient

from wayflowcore.codeserver.backends.local_python import LocalPythonBackend
from wayflowcore.codeserver.server import CodeExecutorServer


@pytest.fixture
def client() -> TestClient:
    """Create an HTTP client backed by a local Python server."""
    backend = LocalPythonBackend()
    with TestClient(CodeExecutorServer(backend=backend).get_app()) as test_client:
        yield test_client
    backend.close_all_sessions()


def test_code_executor_capabilities(client: TestClient) -> None:
    """Returns server and local-backend capabilities."""
    response = client.get("/v1/code-executor")

    assert response.status_code == 200
    assert response.json()["view"] == "public"
    assert response.json()["server_name"] == "wayflow-code-server"
    assert response.json()["capabilities"]["supported_languages"] == ["python"]


def test_code_executor_runs_script_to_completion(client: TestClient) -> None:
    """Runs a script through the HTTP endpoint."""
    response = client.post(
        "/v1/executions",
        json={
            "language_id": "python",
            "input": [{"type": "script", "source_code": "print('hello')"}],
            "wait": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["output"][0]["content"][0]["text"] == "hello\n"


def test_code_executor_serializes_script_response_exactly(client: TestClient) -> None:
    """Serializes captured script output with the protocol field names."""
    response = client.post(
        "/v1/executions",
        json={
            "language_id": "python",
            "input": [{"type": "script", "source_code": "print('hello')"}],
            "wait": True,
        },
    )

    body = response.json()
    assert set(body) == {
        "id",
        "object",
        "created_at",
        "status",
        "completed_at",
        "language_id",
        "output",
        "metadata",
    }
    assert body["object"] == "response"
    assert body["output"] == [
        {
            "type": "output",
            "content": [{"type": "text", "stream": "stdout", "text": "hello\n"}],
            "isError": False,
        }
    ]


def test_code_executor_serializes_explicit_json_null_result(client: TestClient) -> None:
    """Preserves an explicit null structured function result on the wire."""
    response = client.post(
        "/v1/executions",
        json={
            "language_id": "python",
            "input": [
                {
                    "type": "function",
                    "source_code": "def make_none():\n    return None",
                    "function_name": "make_none",
                    "arguments": {},
                }
            ],
            "wait": True,
        },
    )

    output = response.json()["output"][0]
    assert "structuredContent" in output
    assert output["structuredContent"] is None


def test_code_executor_runs_function_to_completion(client: TestClient) -> None:
    """Runs a named function and returns its structured result."""
    response = client.post(
        "/v1/executions",
        json={
            "language_id": "python",
            "input": [
                {
                    "type": "function",
                    "source_code": "def multiply(a, b):\n    return a * b",
                    "function_name": "multiply",
                    "arguments": {"a": 6, "b": 7},
                }
            ],
            "wait": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["output"][0]["structuredContent"] == 42


def test_code_executor_returns_failed_execution(client: TestClient) -> None:
    """Returns a failed response when user code raises an exception."""
    response = client.post(
        "/v1/executions",
        json={
            "language_id": "python",
            "input": [{"type": "script", "source_code": "raise ValueError('boom')"}],
            "wait": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["output"][0]["isError"] is True


def test_code_executor_supports_polling(client: TestClient) -> None:
    """Creates an execution without waiting and retrieves its snapshot."""
    response = client.post(
        "/v1/executions",
        json={
            "language_id": "python",
            "input": [
                {
                    "type": "script",
                    "source_code": "import time\ntime.sleep(0.1)\nprint('done')",
                }
            ],
            "wait": False,
        },
    )
    execution_id = response.json()["id"]

    assert response.status_code == 200
    assert response.json()["status"] == "working"
    for _ in range(100):
        snapshot = client.get(f"/v1/executions/{execution_id}")
        if snapshot.json()["status"] == "completed":
            break
        time.sleep(0.05)

    assert snapshot.status_code == 200
    assert snapshot.json()["status"] == "completed"


def test_code_executor_supports_cancellation(client: TestClient) -> None:
    """Cancels a running execution through HTTP."""
    response = client.post(
        "/v1/executions",
        json={
            "language_id": "python",
            "input": [{"type": "script", "source_code": "while True: pass"}],
            "wait": False,
        },
    )
    execution_id = response.json()["id"]
    cancellation = client.post(f"/v1/executions/{execution_id}/cancel")

    assert cancellation.status_code == 200
    assert cancellation.json()["status"] == "cancelled"


def test_code_executor_returns_not_found_for_unknown_execution(client: TestClient) -> None:
    """Returns HTTP 404 for an unknown execution identifier."""
    response = client.get("/v1/executions/exec_unknown")

    assert response.status_code == 404


def test_code_executor_returns_not_found_when_cancelling_unknown_execution(
    client: TestClient,
) -> None:
    """Returns HTTP 404 when cancelling an unknown execution identifier."""
    response = client.post("/v1/executions/exec_unknown/cancel")

    assert response.status_code == 404


def test_code_executor_rejects_malformed_request(client: TestClient) -> None:
    """Returns HTTP 422 when the request does not match the protocol model."""
    response = client.post(
        "/v1/executions",
        json={"language_id": "python", "input": [{"type": "script"}]},
    )

    assert response.status_code == 422


def test_code_executor_rejects_unknown_request_fields(client: TestClient) -> None:
    """Rejects fields that are not part of the execution request model."""
    response = client.post(
        "/v1/executions",
        json={
            "language_id": "python",
            "input": [{"type": "script", "source_code": "pass"}],
            "unexpected": True,
        },
    )

    assert response.status_code == 422


def test_code_executor_rejects_unsupported_language(client: TestClient) -> None:
    """Returns a client error when the backend cannot run the language."""
    response = client.post(
        "/v1/executions",
        json={
            "language_id": "javascript",
            "input": [{"type": "script", "source_code": "console.log('hello')"}],
        },
    )

    assert response.status_code == 400
    assert isinstance(response.json()["detail"], str)


def test_code_executor_creates_session(client: TestClient) -> None:
    """Creates a stateful session through HTTP."""
    response = client.post("/v1/sessions", json={"language_id": "python"})

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "session"
    assert body["status"] == "active"
    assert body["language_id"] == "python"


def test_code_executor_closes_session(client: TestClient) -> None:
    """Closes a stateful session through HTTP."""
    created = client.post("/v1/sessions", json={"language_id": "python"})
    session_id = created.json()["id"]

    response = client.delete(f"/v1/sessions/{session_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_code_executor_returns_not_found_for_unknown_session(client: TestClient) -> None:
    """Returns HTTP 404 when closing an unknown session identifier."""
    response = client.delete("/v1/sessions/sess_unknown")

    assert response.status_code == 404


def test_code_executor_rejects_malformed_session_request(client: TestClient) -> None:
    """Returns HTTP 422 when a session request is missing its language."""
    response = client.post("/v1/sessions", json={})

    assert response.status_code == 422
