# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Backend interfaces for Code Executor Protocol execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass

from wayflowcore._utils.notgiven import NOT_GIVEN, NotGiven
from wayflowcore.codeserver.models import (
    HostCallbackResponse,
    HostInteractions,
    JsonValue,
    TaskStatus,
)
from wayflowcore.codeserver.sessions import BackendSession


@dataclass
class CodeExecutorBackend(ABC):
    """Interface used by :class:`CodeExecutionService` to run code."""

    execution_timeout_seconds: float = 30.0
    """Maximum wall-clock time allowed for one execution."""

    @abstractmethod
    def get_capabilities(self) -> dict[str, JsonValue]:
        """Return capabilities supported by this backend."""
        raise NotImplementedError

    @abstractmethod
    def validate_language(self, language_id: str) -> None:
        """Validate that this backend supports the requested language."""
        raise NotImplementedError

    @abstractmethod
    def start_script(
        self,
        source_code: str,
        *,
        session: BackendSession | None = None,
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

    @abstractmethod
    def start_function(
        self,
        source_code: str,
        function_name: str,
        arguments: Mapping[str, JsonValue],
        *,
        session: BackendSession | None = None,
    ) -> "BackendExecutionContext":
        """Start a named function execution."""
        raise NotImplementedError

    @abstractmethod
    def create_session(
        self,
        session_id: str,
        language_id: str,
        *,
        host_interactions: HostInteractions | None = None,
    ) -> BackendSession:
        """Create backend state for a retained execution session."""
        raise NotImplementedError

    @abstractmethod
    def resume_callback(
        self,
        session: BackendSession,
        response: HostCallbackResponse,
    ) -> "BackendExecutionContext":
        """Resume a session execution with one host callback response."""
        raise NotImplementedError

    @abstractmethod
    def close_session(self, session: BackendSession) -> None:
        """Release resources owned by a retained execution session."""
        raise NotImplementedError


@dataclass(frozen=True)
class BackendHostCallbackRequest:
    """Internal representation of a callback requested by executing code."""

    request_id: str
    request_type: str
    name: str
    arguments: dict[str, JsonValue]


@dataclass
class BackendExecutionResult:
    """Normalized result produced by an execution backend."""

    status: TaskStatus
    stdout: str = ""
    stderr: str = ""
    structured_content: JsonValue | NotGiven = NOT_GIVEN
    """Structured function result, or ``NOT_GIVEN`` when no result exists."""
    error: str | None = None
    host_callback_request: BackendHostCallbackRequest | None = None
    """Pending host callback request when status is ``input_required``."""
    metadata: dict[str, JsonValue] | None = None


class BackendExecutionContext(ABC):
    """Handle for one active or completed backend execution."""

    @abstractmethod
    def get_result(self) -> BackendExecutionResult:
        """Return the latest normalized result for this execution."""
        raise NotImplementedError

    @abstractmethod
    def wait(self) -> BackendExecutionResult:
        """Wait until the execution reaches a terminal or waiting state."""
        raise NotImplementedError

    @abstractmethod
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

    def build_namespace(self) -> dict[str, object]:
        """Build the initial namespace for a worker execution."""
        raise NotImplementedError
