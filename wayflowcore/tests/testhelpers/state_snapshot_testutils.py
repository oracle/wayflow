# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from contextlib import AbstractContextManager, nullcontext
from typing import Any, Sequence

from wayflowcore.conversation import Conversation
from wayflowcore.events.event import Event, StateSnapshotEvent
from wayflowcore.events.eventlistener import EventListener, register_event_listeners
from wayflowcore.executors.interrupts.executioninterrupt import ExecutionInterrupt
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotPolicy
from wayflowcore.serialization import deserialize_conversation, dump_conversation_state


class SnapshotCollector(EventListener):
    def __init__(self) -> None:
        self.state_snapshot_events: list[StateSnapshotEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, StateSnapshotEvent):
            self.state_snapshot_events.append(event)


def snapshot_status_types(snapshot_events: Sequence[StateSnapshotEvent]) -> list[str | None]:
    return [
        status["type"] if (status := snapshot_event.state_snapshot["execution"]["status"]) else None
        for snapshot_event in snapshot_events
    ]


def execute_with_state_snapshots(
    conversation: Conversation,
    *,
    state_snapshot_policy: StateSnapshotPolicy,
    execution_interrupts: Sequence[ExecutionInterrupt] | None = None,
    execution_context: AbstractContextManager[Any] | None = None,
) -> tuple[object, list[StateSnapshotEvent]]:
    collector = SnapshotCollector()

    with execution_context or nullcontext():
        with register_event_listeners([collector]):
            status = conversation.execute(
                execution_interrupts=execution_interrupts,
                state_snapshot_policy=state_snapshot_policy,
            )

    return status, collector.state_snapshot_events


async def execute_with_state_snapshots_async(
    conversation: Conversation,
    *,
    state_snapshot_policy: StateSnapshotPolicy,
    execution_interrupts: Sequence[ExecutionInterrupt] | None = None,
    execution_context: AbstractContextManager[Any] | None = None,
) -> tuple[object, list[StateSnapshotEvent]]:
    collector = SnapshotCollector()

    with execution_context or nullcontext():
        with register_event_listeners([collector]):
            status = await conversation.execute_async(
                execution_interrupts=execution_interrupts,
                state_snapshot_policy=state_snapshot_policy,
            )

    return status, collector.state_snapshot_events


def restore_conversation_from_snapshot_payload(
    snapshot_payload: dict[str, Any],
) -> Conversation:
    assert snapshot_payload["runtime"] == "wayflow"
    assert snapshot_payload["schema_version"] == 1
    assert isinstance(snapshot_payload["conversation_state"], str)

    restored_conversation = deserialize_conversation(snapshot_payload["conversation_state"])
    assert dump_conversation_state(restored_conversation) == {
        "conversation": snapshot_payload["conversation"],
        "execution": snapshot_payload["execution"],
    }
    return restored_conversation
