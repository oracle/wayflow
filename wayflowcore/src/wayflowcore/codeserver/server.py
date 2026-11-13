# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Server composition and process entry point for Code Executor Protocol."""

from __future__ import annotations

import secrets
import warnings
from ipaddress import ip_address
from typing import Any, Optional, Sequence

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from wayflowcore.codeserver.app import create_code_executor_app
from wayflowcore.codeserver.backend import CodeExecutorBackend
from wayflowcore.codeserver.backends.local_python import LocalPythonBackend
from wayflowcore.codeserver.serverstorageconfig import CodeExecutorServerStorageConfig
from wayflowcore.codeserver.service import CodeExecutionService
from wayflowcore.codeserver.storage import CodeExecutorStorage
from wayflowcore.datastore import Datastore


class CodeExecutorServer:
    """Compose a Code Executor service and expose it as a FastAPI application."""

    def __init__(
        self,
        backend: CodeExecutorBackend | None = None,
        storage: Datastore | None = None,
        storage_config: CodeExecutorServerStorageConfig | None = None,
        allowed_origins: Optional[Sequence[str]] = None,
        allow_credentials: bool = True,
        allowed_methods: Optional[Sequence[str]] = None,
        allowed_headers: Optional[Sequence[str]] = None,
        server_name: str = "wayflow-code-server",
        protocol_version: str = "26.1.3",
    ) -> None:
        """Initialize a server with a backend and optional snapshot storage.

        Parameters
        ----------
        storage:
            Datastore for server persistence. When omitted, an in-memory datastore is used.
        storage_config:
            Configuration for the collections and serialized snapshot fields.
        allowed_origins:
            Origins allowed to make browser cross-origin requests to the server through
            CORS (Cross-Origin Resource Sharing). CORS is a browser access-control
            mechanism that decides whether JavaScript loaded from one origin, such as
            ``https://app.example.com``, may call this server on another origin.
            An origin is the scheme, host, and port, for example
            ``https://app.example.com`` or ``http://localhost:3000``.
            If not provided, CORS middleware is not enabled and browsers deny
            cross-origin requests by default.
            Examples:
            ``["https://app.example.com"]`` allows one browser application origin.
            ``["*"]`` allows any origin, but only when ``allow_credentials`` is false.
            Wildcard subdomain patterns such as ``["*.example.com"]`` are not
            supported here; list each allowed origin explicitly.
        allow_credentials:
            Whether CORS requests may include credentials.
        allowed_methods:
            HTTP methods accepted by CORS preflight requests.
        allowed_headers:
            HTTP headers accepted by CORS preflight requests.
        """
        self.backend = backend or LocalPythonBackend()
        effective_storage_config = storage_config or CodeExecutorServerStorageConfig()
        self.service = CodeExecutionService(
            backend=self.backend,
            storage=CodeExecutorStorage(
                datastore=storage or effective_storage_config.datastore,
                storage_config=effective_storage_config,
            ),
        )
        self.server_name = server_name
        self.protocol_version = protocol_version
        self.allowed_origins = allowed_origins
        self.allow_credentials = allow_credentials
        self.allowed_methods = allowed_methods
        self.allowed_headers = allowed_headers

    def _setup_middleware(
        self,
        app: FastAPI,
        allowed_origins: Optional[Sequence[str]],
        allow_credentials: bool,
        allowed_methods: Optional[Sequence[str]],
        allowed_headers: Optional[Sequence[str]],
    ) -> None:
        """Set up CORS and other middleware."""
        if not allowed_origins:
            # allowed_methods and allowed_headers are only meaningful once CORS is enabled
            # with an origin allow-list. Without allowed_origins, keep CORS disabled so
            # browser cross-origin access is denied by default.
            return
        if allow_credentials and "*" in allowed_origins:
            raise ValueError("Wildcard CORS origins cannot be used with credentials enabled.")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(allowed_origins),
            allow_credentials=allow_credentials,
            allow_methods=list(allowed_methods or ["*"]),
            allow_headers=list(allowed_headers or ["*"]),
        )

    def get_app(self) -> FastAPI:
        """Return the FastAPI application for deployment by an ASGI server."""
        app = create_code_executor_app(
            self.service,
            server_name=self.server_name,
            protocol_version=self.protocol_version,
        )
        self._setup_middleware(
            app,
            allowed_origins=self.allowed_origins,
            allow_credentials=self.allow_credentials,
            allowed_methods=self.allowed_methods,
            allowed_headers=self.allowed_headers,
        )
        return app

    def run(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        api_key: str | None = None,
    ) -> None:
        """Run the Code Executor server with Uvicorn."""
        import uvicorn

        _validate_server_auth_configuration(host=host, api_key=api_key)
        if api_key is None:
            warn_server_is_not_secured()
        app = self.get_app()
        if api_key is not None:
            _add_token_authentication(app, api_key)
        uvicorn.run(app, host=host, port=port, reload=False)


def _add_token_authentication(app: FastAPI, api_key: str) -> None:
    """Add bearer-token authentication middleware to an application."""

    @app.middleware("http")
    async def require_bearer_token(request: Request, call_next: Any) -> Any:
        auth_header = request.headers.get("authorization", "")
        if not secrets.compare_digest(auth_header, f"Bearer {api_key}"):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid bearer token"},
            )
        return await call_next(request)


def _validate_server_auth_configuration(host: str, api_key: str | None) -> None:
    """Require authentication when binding outside the loopback interface."""
    if api_key is None and not _is_loopback_host(host):
        raise ValueError(
            "An api_key is required when binding to a non-loopback host. "
            "Use host='127.0.0.1' for local unauthenticated development."
        )


def _is_loopback_host(host: str) -> bool:
    normalized_host = host.strip("[]").lower()
    if normalized_host == "localhost":
        return True
    try:
        return ip_address(normalized_host).is_loopback
    except ValueError:
        return False


_WARNING_MESSAGE = r"""

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                                ⚠️  SECURITY WARNING                                            ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                                                                ┃
┃   This server has NO built-in authentication or encryption.                                    ┃
┃   Anyone with network access can invoke this CodeExecutor server.                              ┃
┃                                                                                                ┃
┃   For production, either:                                                                      ┃
┃     • Deploy behind an authenticated gateway                                                   ┃
┃     • Add auth middleware via `CodeExecutorServer.get_app()`                                   ┃
┃                                                                                                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
"""


def warn_server_is_not_secured() -> None:
    warnings.warn(_WARNING_MESSAGE)


_CURL_EXAMPLES = r"""


curl http://127.0.0.1:8010/v1/code-executor



curl -X POST http://127.0.0.1:8010/v1/executions \
    -H "Content-Type: application/json" \
    -d '{
        "language_id": "python",
        "input": [
        {
            "type": "script",
            "source_code": "print(\"hello from curl\")"
        }
        ],
        "wait": true
    }'

curl -X POST http://127.0.0.1:8010/v1/executions \
    -H "Content-Type: application/json" \
    -d '{
        "language_id": "python",
        "input": [
        {
            "type": "function",
            "source_code": "def multiply(a, b):\n    return a * b",
            "function_name": "multiply",
            "arguments": {
            "a": 6,
            "b": 7
            }
        }
        ],
        "wait": true
    }'
"""
