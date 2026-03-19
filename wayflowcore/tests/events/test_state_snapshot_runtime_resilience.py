# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass

import pytest

from wayflowcore.conversation import Conversation
from wayflowcore.events import Event, EventListener
from wayflowcore.events.event import StateSnapshotEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval, StateSnapshotPolicy
from wayflowcore.flow import Flow
from wayflowcore.property import AnyProperty
from wayflowcore.serialization.serializer import FrozenSerializableDataclass
from wayflowcore.steps import CompleteStep, OutputMessageStep, VariableWriteStep
from wayflowcore.variable import Variable

from ..testhelpers.statesnapshots import (
    create_output_flow_conversation,
    execute_with_state_snapshots,
    snapshot_message,
)


@dataclass(frozen=True)
class _SerializableButNotJson(FrozenSerializableDataclass):
    value: str


def _create_non_json_variable_state_conversation() -> Conversation:
    custom_variable = Variable(name="custom", type=AnyProperty())
    return Flow.from_steps(
        [
            VariableWriteStep(
                variable=custom_variable,
                input_mapping={VariableWriteStep.VALUE: custom_variable.name},
            ),
            OutputMessageStep(message_template="done"),
            CompleteStep(name="end"),
        ],
        variables=[custom_variable],
    ).start_conversation(inputs={custom_variable.name: _SerializableButNotJson(value="x")})


def test_state_snapshot_emission_survives_broken_extra_state_builder() -> None:
    def broken_builder(_conversation: Conversation) -> dict[str, object]:
        raise RuntimeError("boom")

    conversation = create_output_flow_conversation()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS,
            extra_state_builder=broken_builder,
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 2
    assert all(snapshot_event.extra_state is None for snapshot_event in state_snapshot_events)


def test_state_snapshot_emission_survives_unserializable_variable_state() -> None:
    conversation = _create_non_json_variable_state_conversation()

    status, state_snapshot_events = execute_with_state_snapshots(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS,
            include_variable_state=True,
        ),
    )

    assert isinstance(status, FinishedStatus)
    assert len(state_snapshot_events) == 2
    assert state_snapshot_events[0].variable_state == {"custom": None}
    assert state_snapshot_events[-1].variable_state is None
    assert snapshot_message(state_snapshot_events[-1]) == "done"


class _FailOnTerminalSnapshot(EventListener):
    def __call__(self, event: Event) -> None:
        if not isinstance(event, StateSnapshotEvent):
            return

        execution_status = (event.state_snapshot or {}).get("execution", {}).get("status")
        if execution_status is not None:
            raise RuntimeError("snapshot sink failed")


def test_state_snapshot_listener_failures_propagate_to_the_caller() -> None:
    conversation = create_output_flow_conversation()

    with register_event_listeners([_FailOnTerminalSnapshot()]):
        with pytest.raises(RuntimeError, match="snapshot sink failed"):
            conversation.execute(
                state_snapshot_policy=StateSnapshotPolicy(
                    state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
                )
            )

    assert conversation.get_last_message() is not None
    assert conversation.get_last_message().content == "Hello"
