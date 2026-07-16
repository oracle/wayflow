# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""HTTP tests for the Code Executor Protocol application."""

from fastapi.testclient import TestClient

from wayflowcore.codeserver.backends.local_python import LocalPythonBackend
from wayflowcore.codeserver.server import CodeExecutorServer


def _client() -> TestClient:
    """Create a test client for the local Python server."""
    return TestClient(CodeExecutorServer(backend=LocalPythonBackend()).get_app())


def test_code_executor_capabilities() -> None:
    """Returns server and local-backend capabilities."""
    response = _client().get("/v1/code-executor")

    assert response.status_code == 200
    assert response.json()["view"] == "public"
    assert response.json()["server_name"] == "wayflow-code-server"
    assert response.json()["capabilities"]["supported_languages"] == ["python"]


def test_code_executor_runs_script_to_completion() -> None:
    """Runs a script through the HTTP endpoint."""
    response = _client().post(
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


def test_code_executor_supports_polling_and_cancellation() -> None:
    """Creates a pending execution and cancels it through HTTP."""
    client = _client()
    response = client.post(
        "/v1/executions",
        json={
            "language_id": "python",
            "input": [{"type": "script", "source_code": "while True: pass"}],
            "wait": False,
        },
    )
    execution_id = response.json()["id"]

    assert response.status_code == 200
    assert response.json()["status"] == "working"
    cancellation = client.post(f"/v1/executions/{execution_id}/cancel")

    assert cancellation.status_code == 200
    assert cancellation.json()["status"] == "cancelled"


def test_code_executor_returns_not_found_for_unknown_execution() -> None:
    """Returns HTTP 404 for an unknown execution identifier."""
    response = _client().get("/v1/executions/exec_unknown")

    assert response.status_code == 404


def test_code_executor_does_not_expose_session_routes() -> None:
    """Leaves session routes unavailable while session HTTP support is deferred."""
    response = _client().post("/v1/sessions", json={"language_id": "python"})

    assert response.status_code == 404
