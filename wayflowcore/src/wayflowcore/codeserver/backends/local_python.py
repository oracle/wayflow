# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Local Python execution backend and worker-process handles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from wayflowcore.codeserver.backend import (
    BackendExecutionContext,
    BackendExecutionResult,
    CodeExecutorBackend,
    PythonExecutionPolicy,
)


class LocalPythonBackend(CodeExecutorBackend):
    """Backend configuration for executing Python locally."""

    policy: PythonExecutionPolicy | None = None

    def start_script(self, source_code: str, *, session: Any = None) -> BackendExecutionContext:
        """Start a Python script in a worker process."""
        raise NotImplementedError

    def start_function(
        self,
        source_code: str,
        function_name: str,
        arguments: Mapping[str, Any],
        *,
        session: Any = None,
    ) -> BackendExecutionContext:
        """Start a Python function in a worker process."""
        raise NotImplementedError


@dataclass
class LocalPythonExecution(BackendExecutionContext):
    """Handle for one local Python worker execution."""

    execution_id: str
    result: BackendExecutionResult | None = None

    def get_result(self) -> BackendExecutionResult:
        """Return the latest worker result."""
        raise NotImplementedError

    def wait(self) -> BackendExecutionResult:
        """Wait for the worker to finish or request host input."""
        raise NotImplementedError

    def cancel(self) -> BackendExecutionResult:
        """Terminate the worker and return its cancellation result."""
        raise NotImplementedError


@dataclass
class LocalPythonSession:
    """Handle for a long-lived local Python session worker."""

    session_id: str
    process: Any = None
    lock: Any = field(default=None, repr=False)

    def close(self) -> None:
        """Terminate the session worker and release its resources."""
        raise NotImplementedError
