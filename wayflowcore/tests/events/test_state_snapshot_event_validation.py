# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest

from wayflowcore.events.event import StateSnapshotEvent


def test_state_snapshot_event_requires_conversation_id() -> None:
    with pytest.raises(ValueError, match="conversation_id"):
        StateSnapshotEvent()


def test_state_snapshot_event_allows_missing_state_snapshot() -> None:
    event = StateSnapshotEvent(conversation_id="conversation-123")

    assert event.state_snapshot is None


def test_state_snapshot_event_requires_state_snapshot_to_be_a_dictionary() -> None:
    with pytest.raises(ValueError, match="state_snapshot must be a dictionary"):
        StateSnapshotEvent(
            conversation_id="conversation-123",
            state_snapshot="not-a-dictionary",
        )


def test_state_snapshot_event_requires_runtime_conversation_id() -> None:
    with pytest.raises(ValueError, match=r"state_snapshot\['conversation'\]\['id'\]"):
        StateSnapshotEvent(
            conversation_id="conversation-123",
            state_snapshot={"conversation": {"messages": []}},
        )
