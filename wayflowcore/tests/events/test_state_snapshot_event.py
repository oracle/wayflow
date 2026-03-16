# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest

from wayflowcore.events.event import _PII_TEXT_MASK, StateSnapshotEvent


def test_state_snapshot_event_requires_conversation_id() -> None:
    with pytest.raises(ValueError, match="conversation_id"):
        StateSnapshotEvent()


@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_state_snapshot_event_serialization(
    mask_sensitive_information: bool,
) -> None:
    event = StateSnapshotEvent(
        conversation_id="conversation-123",
        state_snapshot={"conversation": {"messages": []}},
        extra_state={"ui": {"active_tab": "plan"}},
        variable_state={"count": 2},
        name="snapshot",
        event_id="evt-1",
        timestamp=12,
    )

    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)

    assert serialized_event["event_type"] == "StateSnapshotEvent"
    assert serialized_event["conversation_id"] == "conversation-123"
    assert serialized_event["name"] == "snapshot"
    assert serialized_event["event_id"] == "evt-1"
    assert serialized_event["timestamp"] == 12

    if mask_sensitive_information:
        assert serialized_event["state_snapshot"] == _PII_TEXT_MASK
        assert serialized_event["extra_state"] == _PII_TEXT_MASK
        assert serialized_event["variable_state"] == _PII_TEXT_MASK
    else:
        assert serialized_event["state_snapshot"] == {"conversation": {"messages": []}}
        assert serialized_event["extra_state"] == {"ui": {"active_tab": "plan"}}
        assert serialized_event["variable_state"] == {"count": 2}
