# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wayflowcore.executors.executionstatus import AuthChallengeRequestStatus


class WayFlowException(Exception):
    """Base exception for wayflowcore-related errors."""


class StructuredOutputValidationError(WayFlowException, ValueError):
    """Raised when locally validated structured LLM output is invalid."""

    def __init__(self, violations: list[str]):
        self.violations = violations
        super().__init__("Structured output validation failed: " + ";\n".join(violations))


class SecurityException(WayFlowException):
    """Exception raised for security-related issues."""


class InvalidToolRequestException(WayFlowException):
    """Base exception for invalid tool requests."""


class InvalidToolRequestValueError(InvalidToolRequestException, ValueError):
    """Exception raised for invalid value in tool requests."""


class InvalidToolRequestKeyError(InvalidToolRequestException, KeyError):
    """Exception raised for missing key in tool requests."""


class InvalidToolRequestTypeError(InvalidToolRequestException, TypeError):
    """Exception raised for type mismatch in tool requests."""


class DatastoreError(Exception):
    """Generic subclass for all errors raised by ``Datastores``."""


class DatastoreConstraintViolationError(DatastoreError, ValueError):
    """Exception raised when a constraint violation occurs in the ``Datastore``."""


class DatastoreEntityError(DatastoreError, ValueError):
    """Exception raised when an entity dictionary passed to a ``Datastore`` is invalid."""


class DatastoreTypeError(DatastoreError, TypeError):
    """Exception raised when a type passed to a ``Datastore`` is invalid."""


class DatastoreValueError(DatastoreError, ValueError):
    """Exception raised for invalid value in ``Datastore`` operations."""


class DatastoreKeyError(DatastoreError, KeyError):
    """Exception raised for missing key in ``Datastore`` operations."""


class DatastoreNotImplementedError(DatastoreError, NotImplementedError):
    """Exception raised for not implemented functionality in ``Datastore`` operations."""


class MaxNumTrialsExceededException(ValueError):
    """Exception raised by the RetryStep in case it exceeds the max number of failures and no
    failure_next_step is configured"""


class NoSuchToolFoundOnMCPServerError(ValueError):
    """Error thrown when MCP server returns no tools with a given signature"""

    def __init__(
        self,
        message: str,
        missing_tool_names: list[str] | None = None,
        expected_tool_names: list[str] | None = None,
        exposed_tool_names: list[str] | None = None,
        attempts: int | None = None,
    ) -> None:
        super().__init__(message)
        self.missing_tool_names = missing_tool_names or []
        self.expected_tool_names = expected_tool_names or []
        self.exposed_tool_names = exposed_tool_names or []
        self.attempts = attempts


class DataclassFieldDeserializationError(ValueError):
    """Error thrown when the deserialization of a field of a dataclass fails"""


class _AssistantInterrupt(WayFlowException):
    """Raised when an assistant is interrupted."""


class AuthInterrupt(_AssistantInterrupt):
    """Raised when a component requires an auth challenge to be completed.
    Never raised directly, or surfaced to the user."""

    def __init__(self, status: "AuthChallengeRequestStatus") -> None:
        self.status = status

    def __str__(self) -> str:
        return "AuthInterrupt: Requesting auth challenge to be completed."
