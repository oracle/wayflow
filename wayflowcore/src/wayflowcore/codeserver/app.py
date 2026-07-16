# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""FastAPI application for the Code Executor Protocol routes."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status

from wayflowcore.codeserver.models import (
    CodeExecutionRequest,
    CodeExecutorCapabilities,
    ExecutionResponse,
)
from wayflowcore.codeserver.service import CodeExecutionService


def create_code_executor_app(
    service: CodeExecutionService,
    *,
    server_name: str = "wayflow-code-server",
    protocol_version: str = "26.1.3",
) -> FastAPI:
    """Create a FastAPI application backed by one code execution service."""
    app = FastAPI(
        title=server_name,
        version=protocol_version,
        description="Code Executor Protocol server.",
    )

    @app.get(
        "/v1/code-executor",
        response_model=CodeExecutorCapabilities,
    )
    def get_capabilities() -> CodeExecutorCapabilities:
        """Return the server and backend capabilities."""
        return CodeExecutorCapabilities(
            protocol_version=protocol_version,
            server_name=server_name,
            capabilities=service.backend.get_capabilities(),
        )

    @app.post("/v1/executions", response_model=ExecutionResponse)
    def create_execution(request: CodeExecutionRequest) -> ExecutionResponse:
        """Create an execution and optionally wait for completion."""
        try:
            return service.execute(request)
        except NotImplementedError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @app.get("/v1/executions/{execution_id}", response_model=ExecutionResponse)
    def get_execution(execution_id: str) -> ExecutionResponse:
        """Return the latest execution snapshot."""
        try:
            return service.get_execution(execution_id)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @app.post("/v1/executions/{execution_id}/cancel", response_model=ExecutionResponse)
    def cancel_execution(execution_id: str) -> ExecutionResponse:
        """Cancel an active execution."""
        try:
            return service.cancel_execution(execution_id)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return app
