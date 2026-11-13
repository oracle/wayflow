# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


from dataclasses import dataclass, field
from typing import Any

from wayflowcore._utils.notgiven import NOT_GIVEN, NotGiven


@dataclass(frozen=True, kw_only=True)
class CodeExecutionStatus:
    """Status returned by a code executor."""

    status: str
    """Execution status reported by the server."""
    execution_id: str
    """Identifier of the execution reported by the configured server."""
    metadata: dict[str, Any] = field(default_factory=dict)
    """Caller data and server-specific execution details."""


@dataclass(frozen=True, kw_only=True)
class CodeExecutionSucceeded(CodeExecutionStatus):
    """A completed execution with accepted output."""

    status: str = "succeeded"
    """Execution status reported by the server."""

    stdout: str = ""
    """Captured standard output."""
    stderr: str = ""
    """Captured standard error output."""
    result: Any | NotGiven = NOT_GIVEN
    """Structured result, or ``NOT_GIVEN`` when no structured result exists."""


@dataclass(frozen=True, kw_only=True)
class CodeExecutionRejected(CodeExecutionStatus):
    """An execution rejected before user code started."""

    status: str = "rejected"
    """Execution status reported by the server."""

    message: str | None = None
    """Optional explanation of the rejection."""


@dataclass(frozen=True, kw_only=True)
class CodeExecutionFailed(CodeExecutionStatus):
    """An execution that started and then failed."""

    status: str = "failed"
    """Execution status reported by the server."""

    message: str | None = None
    """Optional explanation of the failure."""
    stdout: str = ""
    """Captured standard output produced before the failure."""
    stderr: str = ""
    """Captured standard error output produced before the failure."""


@dataclass(frozen=True, kw_only=True)
class CodeExecutionTimedOut(CodeExecutionStatus):
    """An execution stopped after a timeout."""

    status: str = "timed_out"
    """Execution status reported by the server."""

    message: str | None = None
    """Optional explanation of the timeout."""
    stdout: str = ""
    """Captured standard output produced before the timeout."""
    stderr: str = ""
    """Captured standard error output produced before the timeout."""


@dataclass(frozen=True, kw_only=True)
class CodeExecutionCancelled(CodeExecutionStatus):
    """An execution cancelled before it produced an accepted result."""

    status: str = "cancelled"
    """Execution status reported by the server."""

    message: str | None = None
    """Optional explanation of the cancellation."""
    stdout: str = ""
    """Captured standard output produced before cancellation."""
    stderr: str = ""
    """Captured standard error output produced before cancellation."""
