# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation


class StateSnapshotInterval(str, Enum):
    """
    Configure which execution boundaries emit state snapshots.

    `CONVERSATION_TURNS`
        Emit an opening turn snapshot before execution starts and a closing
        turn snapshot at the end of the turn. The closing payload is emitted
        before the live conversation commits the new status, but the payload is
        synthesized so it matches the post-return conversation state. This is
        the default policy because it gives a stable turn-level checkpoint
        without emitting snapshots for every internal step.

    `TOOL_TURNS`
        Emit the `CONVERSATION_TURNS` snapshots plus snapshots around each tool
        invocation (`TOOL_START` and `TOOL_END`).

    `NODE_TURNS`
        Emit the `CONVERSATION_TURNS` snapshots plus snapshots around each
        internal node boundary. For flows this means per-step snapshots; for
        agents it maps to decision-loop iteration boundaries.

    `ALL_INTERNAL_TURNS`
        Emit the `CONVERSATION_TURNS`, `TOOL_TURNS`, and `NODE_TURNS`
        snapshots.

    `OFF`
        Disable state snapshot emission entirely.
    """

    CONVERSATION_TURNS = "conversation_turns"
    TOOL_TURNS = "tool_turns"
    NODE_TURNS = "node_turns"
    ALL_INTERNAL_TURNS = "all_internal_turns"
    OFF = "off"


@dataclass(frozen=True)
class StateSnapshotPolicy:
    """Execution-time policy controlling WayFlow state snapshot emission."""

    state_snapshot_interval: StateSnapshotInterval = StateSnapshotInterval.CONVERSATION_TURNS
    include_variable_state: bool = True
    extra_state_builder: Optional[Callable[["Conversation"], Optional[Dict[str, Any]]]] = None
