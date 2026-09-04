# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Backend-owned session abstractions for stateful execution."""

from __future__ import annotations

from abc import ABC, abstractmethod

from wayflowcore.codeserver.models import HostInteractions


class BackendSession(ABC):
    """Resource handle for one backend-owned execution session."""

    session_id: str
    """Identifier assigned to this session by the service."""

    language_id: str
    """Language accepted by this session."""

    host_interactions: HostInteractions | None
    """Host callback configuration selected when the session was created."""

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Return whether the session can accept another execution."""

    @abstractmethod
    def close(self) -> None:
        """Release resources owned by this session."""


class SessionRegistry:
    """Registry storing backend-owned execution sessions by identifier."""

    def add(self, session: BackendSession) -> None:
        """Register one backend-created session."""
        raise NotImplementedError

    def get(self, session_id: str) -> BackendSession:
        """Return a registered backend session."""
        raise NotImplementedError

    def remove(self, session_id: str) -> BackendSession:
        """Remove and return one registered backend session."""
        raise NotImplementedError
