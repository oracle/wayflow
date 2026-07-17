# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from typing import Any, Dict, Optional

from wayflowcore.codeserver.models import CodeExecutionRequest, ExecutionResponse
from wayflowcore.retrypolicy import RetryPolicy

from ._http import CodeExecutorHttpClient
from .executor import CodeExecutor


@dataclass(kw_only=True)
class EndpointCodeExecutor(CodeExecutor):
    """Run code through a Code Executor endpoint."""

    url: str
    """Code Executor base URL."""

    headers: dict[str, str] | None = None
    """Non-sensitive transport headers."""

    sensitive_headers: Optional[Dict[str, str]] = None
    """Sensitive transport headers."""

    retry_policy: RetryPolicy | None = None
    """Transport retry policy."""

    request_timeout_seconds: float = 30.0
    """Maximum time allowed for one HTTP request."""

    def __post_init__(self) -> None:
        """Initialize the private HTTP client lazily."""
        self._client: CodeExecutorHttpClient | None = None

    def _get_http_client(self) -> CodeExecutorHttpClient:
        """Return the cached private HTTP client."""
        if self._client is None:
            request_headers = dict(self.headers or {})
            request_headers.update(self.sensitive_headers or {})
            timeout = (
                self.retry_policy.request_timeout
                if self.retry_policy is not None
                else self.request_timeout_seconds
            )
            self._client = CodeExecutorHttpClient(
                self.url,
                headers=request_headers,
                timeout_seconds=timeout,
            )
        return self._client

    def _create_execution(self, request: CodeExecutionRequest) -> ExecutionResponse:
        """Submit an execution through HTTP."""
        return self._get_http_client().create_execution(request)

    def _get_execution(self, execution_id: str) -> ExecutionResponse:
        """Retrieve an execution snapshot through HTTP."""
        return self._get_http_client().get_execution(execution_id)

    def _cancel_execution(self, execution_id: str) -> ExecutionResponse:
        """Cancel an execution through HTTP."""
        return self._get_http_client().cancel_execution(execution_id)

    def _get_capabilities(self) -> dict[str, Any]:
        """Retrieve capabilities through HTTP."""
        return self._get_http_client().get_capabilities()

    def close(self) -> None:
        """Close the private HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None
