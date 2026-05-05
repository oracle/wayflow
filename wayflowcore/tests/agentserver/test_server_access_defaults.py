# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import warnings
from typing import Any, TypeVar

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from wayflowcore.agentserver.server import A2AServer, OpenAIResponsesServer

ServerT = TypeVar("ServerT", A2AServer, OpenAIResponsesServer)


def _capture_uvicorn_app(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_run(**kwargs: Any) -> None:
        captured.update(kwargs)

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", fake_run)
    return captured


def _ok_app() -> FastAPI:
    app = FastAPI()

    @app.get("/")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _make_server(server_cls: type[ServerT], **kwargs: Any) -> ServerT:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="InMemoryDatastore is for DEVELOPMENT")
        return server_cls(**kwargs)


@pytest.mark.parametrize("server_cls", [A2AServer, OpenAIResponsesServer])
def test_server_run_rejects_non_loopback_without_api_key(server_cls: type[Any]) -> None:
    server = _make_server(server_cls)

    with pytest.raises(ValueError, match="api_key is required"):
        server.run(host="0.0.0.0", api_key=None)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
@pytest.mark.parametrize("server_cls", [A2AServer, OpenAIResponsesServer])
def test_server_allows_loopback_without_api_key(
    server_cls: type[Any], host: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _capture_uvicorn_app(monkeypatch)
    server = _make_server(server_cls)
    if isinstance(server, A2AServer):
        monkeypatch.setattr(server, "get_app", lambda host, port: _ok_app())

    with pytest.warns(UserWarning):
        server.run(host=host, api_key=None)

    assert captured["host"] == host


@pytest.mark.parametrize(
    "server_cls,path", [(A2AServer, "/"), (OpenAIResponsesServer, "/v1/models")]
)
def test_server_requires_bearer_when_api_key_is_set(
    server_cls: type[Any], path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _capture_uvicorn_app(monkeypatch)
    server = _make_server(server_cls)
    if isinstance(server, A2AServer):
        monkeypatch.setattr(server, "get_app", lambda host, port: _ok_app())

    server.run(host="0.0.0.0", api_key="secret")

    client = TestClient(captured["app"])
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"authorization": "Bearer secret"}).status_code == 200


def test_openai_responses_server_does_not_enable_cors_by_default() -> None:
    client = TestClient(_make_server(OpenAIResponsesServer).get_app())

    response = client.options(
        "/v1/responses",
        headers={
            "origin": "https://example.com",
            "access-control-request-method": "POST",
        },
    )

    assert response.status_code == 405
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers
    assert "access-control-allow-methods" not in response.headers


def test_openai_responses_server_allows_configured_cors_origin() -> None:
    client = TestClient(
        _make_server(OpenAIResponsesServer, allowed_origins=["https://app.example.com"]).get_app()
    )

    response = client.options(
        "/v1/responses",
        headers={
            "origin": "https://app.example.com",
            "access-control-request-method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.example.com"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_openai_responses_server_rejects_wildcard_cors_with_credentials() -> None:
    with pytest.raises(ValueError, match="Wildcard CORS origins"):
        _make_server(OpenAIResponsesServer, allowed_origins=["*"], allow_credentials=True)
