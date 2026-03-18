# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from wayflowcore.conversation import Conversation
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval

from ..testhelpers.statesnapshots import (
    build_policy,
    create_output_flow_conversation,
    create_unserializable_variable_conversation,
    execute_with_state_snapshots,
    snapshot_message,
)


def test_state_snapshot_emission_survives_broken_extra_state_builder() -> None:
    def broken_builder(_conversation: Conversation) -> dict[str, object]:
        raise RuntimeError("boom")

    conversation = create_output_flow_conversation()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=build_policy(
            StateSnapshotInterval.CONVERSATION_TURNS,
            extra_state_builder=broken_builder,
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 2
    assert all(snapshot_event.extra_state is None for snapshot_event in state_snapshot_events)


def test_state_snapshot_emission_survives_unserializable_variable_state() -> None:
    conversation = create_unserializable_variable_conversation()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=build_policy(
            StateSnapshotInterval.CONVERSATION_TURNS,
            include_variable_state=True,
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 2
    assert state_snapshot_events[0].variable_state == {"custom": None}
    assert state_snapshot_events[-1].variable_state is None
    assert snapshot_message(state_snapshot_events[-1]) == "done"
