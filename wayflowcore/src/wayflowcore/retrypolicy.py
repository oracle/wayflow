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
from typing import Any, ClassVar, Dict, List, Literal, Optional

from wayflowcore.serialization.serializer import SerializableDataclassMixin, SerializableObject


@dataclass
class RetryPolicy(SerializableDataclassMixin, SerializableObject):
    """Provider-agnostic retry policy.

    Notes
    -----
    - ``max_attempts`` is the maximum number of retries (does not include the initial attempt).
    - ``initial_retry_delay``/``max_retry_delay`` apply to the sleep between attempts.
    """

    id: str = field(default_factory=lambda: "retry_policy")
    _can_be_referenced: ClassVar[bool] = False

    max_attempts: int = 2

    request_timeout: Optional[float] = None
    """Maximum allowed time (in seconds) for a single request attempt.

    This is a per-attempt timeout. When set, runtimes should pass this value to the
    underlying HTTP client / SDK timeout configuration. Values are expressed in
    seconds and may be fractional (e.g., ``0.5`` means 500 milliseconds).
    """

    initial_retry_delay: float = 1.0
    max_retry_delay: float = 8.0
    backoff_factor: float = 2.0
    jitter: Optional[
        Literal[
            "equal",
            "full",
            "full_and_equal_for_throttle",
            "decorrelated",
        ]
    ] = "full_and_equal_for_throttle"
    service_error_retry_on_any_5xx: bool = True

    recoverable_statuses: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "409": [],
            "429": [],
        }
    )

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return SerializableDataclassMixin._serialize_to_dict(self, serialization_context)

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        input_dict = dict(input_dict)
        input_dict.pop("_component_type", None)
        return cls(**input_dict)


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wayflowcore.serialization.context import DeserializationContext, SerializationContext
