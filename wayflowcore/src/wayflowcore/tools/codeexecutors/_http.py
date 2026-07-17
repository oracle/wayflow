# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Private synchronous HTTP client for Code Executor Protocol endpoints."""

from __future__ import annotations

from typing import Any

import httpx

from wayflowcore.codeserver.models import (
    CodeExecutionRequest,
    CodeExecutorCapabilities,
    ExecutionResponse,
)


class CodeExecutorHttpClient:
    """Small HTTP client for the Code Executor Protocol routes."""

    def __init__(
        self,
        base_url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize the client with a base URL and per-request timeout."""
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            headers=headers,
            timeout=timeout_seconds,
        )

    def get_capabilities(self) -> dict[str, Any]:
        """Fetch the server capabilities document."""
        response = self._client.get(f"{self.base_url}/v1/code-executor")
        response.raise_for_status()
        return CodeExecutorCapabilities.model_validate(response.json()).capabilities

    def create_execution(self, request: CodeExecutionRequest) -> ExecutionResponse:
        """Submit an execution request."""
        response = self._client.post(
            f"{self.base_url}/v1/executions",
            json=request.model_dump(by_alias=True, exclude_none=True),
        )
        response.raise_for_status()
        return ExecutionResponse.model_validate(response.json())

    def get_execution(self, execution_id: str) -> ExecutionResponse:
        """Fetch an execution snapshot."""
        response = self._client.get(f"{self.base_url}/v1/executions/{execution_id}")
        response.raise_for_status()
        return ExecutionResponse.model_validate(response.json())

    def cancel_execution(self, execution_id: str) -> ExecutionResponse:
        """Cancel an execution."""
        response = self._client.post(f"{self.base_url}/v1/executions/{execution_id}/cancel")
        response.raise_for_status()
        return ExecutionResponse.model_validate(response.json())

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
