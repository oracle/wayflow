# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Backend session abstractions for stateful execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BackendSessionState:
    """Runtime state owned by one stateful backend session."""

    session_id: str
    language_id: str
    runtime: Any = None
    closed: bool = False
    failed: bool = False


class SessionRegistry:
    """Registry for backend-owned stateful sessions."""

    def create(self, session_id: str, language_id: str) -> BackendSessionState:
        """Create and register a backend session."""
        raise NotImplementedError

    def get(self, session_id: str) -> BackendSessionState:
        """Return a registered backend session."""
        raise NotImplementedError

    def close(self, session_id: str) -> None:
        """Close and remove a backend session."""
        raise NotImplementedError
