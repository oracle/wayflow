# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Backend interfaces for Code Executor Protocol execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from wayflowcore.codeserver.models import TaskStatus
from wayflowcore.codeserver.sessions import BackendSessionState


@dataclass
class CodeExecutorBackend:
    """Interface used by :class:`CodeExecutionService` to run code."""

    execution_timeout_seconds: float = 30.0
    """Maximum wall-clock time allowed for one execution."""

    def start_script(
        self,
        source_code: str,
        *,
        session: BackendSessionState | None = None,
    ) -> "BackendExecutionContext":
        """Start a script execution.

        Parameters
        ----------
        source_code:
            Python source code to execute.
        session:
            Optional retained backend session in which to execute the code.

        Returns
        -------
            BackendExecutionContext
            Handle for observing and controlling the execution.
        """
        raise NotImplementedError

    def start_function(
        self,
        source_code: str,
        function_name: str,
        arguments: Mapping[str, Any],
        *,
        session: BackendSessionState | None = None,
    ) -> "BackendExecutionContext":
        """Start a named function execution."""
        raise NotImplementedError


@dataclass
class BackendExecutionResult:
    """Normalized result produced by an execution backend."""

    status: TaskStatus
    stdout: str = ""
    stderr: str = ""
    structured_content: Any = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


class BackendExecutionContext:
    """Handle for one active or completed backend execution."""

    def get_result(self) -> BackendExecutionResult:
        """Return the latest normalized result for this execution."""
        raise NotImplementedError

    def wait(self) -> BackendExecutionResult:
        """Wait until the execution reaches a terminal or waiting state."""
        raise NotImplementedError

    def cancel(self) -> BackendExecutionResult:
        """Request cancellation and return the resulting backend state."""
        raise NotImplementedError


class PythonExecutionPolicy:
    """Policy controlling Python source execution inside a worker."""

    def validate_script(self, source_code: str) -> None:
        """Validate source code intended for script execution."""
        raise NotImplementedError

    def validate_function(self, source_code: str, function_name: str) -> None:
        """Validate source code and entry point for function execution."""
        raise NotImplementedError

    def build_namespace(self) -> dict[str, Any]:
        """Build the initial namespace for a worker execution."""
        raise NotImplementedError
