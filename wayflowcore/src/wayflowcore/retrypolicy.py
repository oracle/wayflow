# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Retry configuration shared across networked WayFlow components.

This module defines the public ``RetryPolicy`` aligned with Agent Spec and the
design document ``retry-configuration-on-agent-spec-components.pdf``.

Agent Spec represents ``recoverable_statuses`` as ``Dict[str, List[str]]``
(JSON object keys must be strings). WayFlow uses the same shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar, Dict, List, Optional

from wayflowcore.serialization.serializer import SerializableDataclassMixin, SerializableObject

_MIN_REQUEST_TIMEOUT_SECONDS = 0.0
_MIN_RETRY_DELAY_SECONDS = 0.001
_MAX_RETRY_DELAY_SECONDS = 600.0
_MIN_BACKOFF_FACTOR = 0.001
_MAX_ATTEMPTS = 20


class RetryJitter(str, Enum):
    """Supported jitter strategies for retry backoff."""

    EQUAL = "equal"
    FULL = "full"
    FULL_AND_EQUAL_FOR_THROTTLE = "full_and_equal_for_throttle"
    DECORRELATED = "decorrelated"


@dataclass
class RetryPolicy(SerializableDataclassMixin, SerializableObject):
    """Provider-agnostic retry policy.

    Notes
    -----
    - ``max_attempts`` is the maximum number of retries (does not include the initial attempt).
    - ``initial_retry_delay``/``max_retry_delay`` apply to the sleep between attempts.
    """

    _can_be_referenced: ClassVar[bool] = False

    max_attempts: int = 2
    """Maximum number of retry attempts after the initial request."""

    request_timeout: float = 600.0
    """Maximum allowed time (in seconds) for a single request attempt.

    This is a per-attempt timeout. When set, runtimes should pass this value to the
    underlying HTTP client / SDK timeout configuration. Values are expressed in
    seconds and may be fractional (e.g., ``0.5`` means 500 milliseconds).
    """

    initial_retry_delay: float = 1.0
    """Base delay in seconds used to compute exponential backoff."""

    max_retry_delay: float = 8.0
    """Upper bound in seconds for the delay between two retry attempts."""

    backoff_factor: float = 2.0
    """Multiplier applied between retry delays during exponential backoff."""

    jitter: Optional[RetryJitter] = RetryJitter.FULL_AND_EQUAL_FOR_THROTTLE
    """Randomization strategy applied to the computed backoff delay."""

    service_error_retry_on_any_5xx: bool = True
    """Whether retryable 5xx responses except 501 should be retried."""

    recoverable_statuses: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "409": [],
            "429": [],
        }
    )
    """Additional HTTP statuses to treat as retryable.

    The dictionary key is the numeric HTTP status code encoded as a string.
    The value is a list of textual service error codes to match for that status.
    An empty list means the numeric status code alone is enough to retry.
    A non-empty list means both the numeric status code and one of the textual
    codes must match before the request is retried.
    """

    def __post_init__(self) -> None:
        if self.request_timeout is None:
            self.request_timeout = 600.0
        if isinstance(self.jitter, str):
            self.jitter = RetryJitter(self.jitter)
        if self.max_attempts < 0:
            raise ValueError(f"max_attempts must be non-negative, got {self.max_attempts}")
        if self.max_attempts > _MAX_ATTEMPTS:
            raise ValueError(
                f"max_attempts must not exceed {_MAX_ATTEMPTS}, got {self.max_attempts}"
            )
        if self.request_timeout <= _MIN_REQUEST_TIMEOUT_SECONDS:
            raise ValueError(f"request_timeout must be positive, got {self.request_timeout}")
        if self.initial_retry_delay < _MIN_RETRY_DELAY_SECONDS:
            raise ValueError(
                "initial_retry_delay must be positive, " f"got {self.initial_retry_delay}"
            )
        if self.max_retry_delay < _MIN_RETRY_DELAY_SECONDS:
            raise ValueError(f"max_retry_delay must be positive, got {self.max_retry_delay}")
        if self.max_retry_delay > _MAX_RETRY_DELAY_SECONDS:
            raise ValueError(
                f"max_retry_delay must not exceed {_MAX_RETRY_DELAY_SECONDS}, got {self.max_retry_delay}"
            )
        if self.backoff_factor < _MIN_BACKOFF_FACTOR:
            raise ValueError(f"backoff_factor must be positive, got {self.backoff_factor}")

        normalized_recoverable_statuses: Dict[str, List[str]] = {}
        for status_code, textual_codes in self.recoverable_statuses.items():
            normalized_status = str(status_code)
            if not normalized_status.isdigit():
                raise ValueError(
                    "recoverable_statuses keys must be numeric HTTP status codes, "
                    f"got {status_code!r}"
                )
            normalized_recoverable_statuses[normalized_status] = [
                str(code) for code in textual_codes
            ]
        self.recoverable_statuses = normalized_recoverable_statuses

    @property
    def total_attempts(self) -> int:
        return self.max_attempts + 1
