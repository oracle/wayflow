# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Server composition and process entry point for Code Executor Protocol."""

from __future__ import annotations

from fastapi import FastAPI

from wayflowcore.codeserver.app import create_code_executor_app
from wayflowcore.codeserver.backend import CodeExecutorBackend
from wayflowcore.codeserver.backends.local_python import LocalPythonBackend
from wayflowcore.codeserver.service import CodeExecutionService
from wayflowcore.codeserver.storage import CodeExecutorStorage


class CodeExecutorServer:
    """Compose a Code Executor service and expose it as a FastAPI application."""

    def __init__(
        self,
        backend: CodeExecutorBackend | None = None,
        storage: CodeExecutorStorage | None = None,
        *,
        server_name: str = "wayflow-code-server",
        protocol_version: str = "26.1.3",
    ) -> None:
        """Initialize a server with a backend and optional snapshot storage."""
        self.backend = backend or LocalPythonBackend()
        self.service = CodeExecutionService(backend=self.backend, storage=storage)
        self.server_name = server_name
        self.protocol_version = protocol_version

    def get_app(self) -> FastAPI:
        """Return the FastAPI application for deployment by an ASGI server."""
        return create_code_executor_app(
            self.service,
            server_name=self.server_name,
            protocol_version=self.protocol_version,
        )

    def run(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        """Run the Code Executor server with Uvicorn."""
        import uvicorn

        uvicorn.run(self.get_app(), host=host, port=port, reload=False)
