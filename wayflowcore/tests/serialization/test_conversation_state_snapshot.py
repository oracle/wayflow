# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
from typing import Any

import pytest

from wayflowcore.conversation import Conversation
from wayflowcore.flow import Flow
from wayflowcore.property import AnyProperty, StringProperty
from wayflowcore.serialization import (
    deserialize_conversation_state,
    dump_conversation_state,
    dump_variable_state,
    serialize_conversation_state,
)
from wayflowcore.steps import OutputMessageStep, VariableWriteStep
from wayflowcore.variable import Variable


class _UnserializableValue:
    def __str__(self) -> str:
        return "custom-value"


def _build_snapshot_flow(custom_variable: Variable) -> Flow:
    return Flow.from_steps(
        steps=[
            VariableWriteStep(
                variable=custom_variable,
                input_mapping={VariableWriteStep.VALUE: custom_variable.name},
            ),
            OutputMessageStep(message_template="Hello there"),
        ],
        variables=[custom_variable],
        name="snapshot_flow",
    )


def _walk_scalars(value: Any):
    if isinstance(value, dict):
        for inner_value in value.values():
            yield from _walk_scalars(inner_value)
        return
    if isinstance(value, list):
        for inner_value in value:
            yield from _walk_scalars(inner_value)
        return
    yield value


def test_dump_conversation_state_is_json_serializable_and_lightweight() -> None:
    custom_variable = Variable(
        name="custom",
        type=StringProperty(),
        description="Custom variable used for snapshot serialization tests",
    )
    flow = _build_snapshot_flow(custom_variable)
    conversation = flow.start_conversation(inputs={custom_variable.name: "custom-value"})
    conversation.execute()

    snapshot = dump_conversation_state(conversation)
    variable_state = dump_variable_state(conversation)
    serialized_snapshot = serialize_conversation_state(conversation)

    assert json.loads(json.dumps(snapshot)) == deserialize_conversation_state(serialized_snapshot)
    assert variable_state == {"custom": "custom-value"}
    assert snapshot["conversation"]["component_type"] == "Flow"
    assert snapshot["conversation"]["messages"][-1]["content"] == "Hello there"

    assert all(
        not isinstance(scalar, (Conversation, Flow, OutputMessageStep))
        for scalar in _walk_scalars(snapshot)
    )


def test_dump_conversation_state_overrides_execution_fields_without_mutating_conversation() -> None:
    custom_variable = Variable(
        name="custom",
        type=StringProperty(),
        description="Custom variable used for snapshot serialization tests",
    )
    flow = _build_snapshot_flow(custom_variable)
    conversation = flow.start_conversation(inputs={custom_variable.name: "custom-value"})
    conversation.execute()

    previous_status = conversation.status
    previous_status_handled = conversation.status_handled

    snapshot = dump_conversation_state(
        conversation,
        status=None,
        status_handled=True,
    )

    assert snapshot["execution"]["status"] is None
    assert snapshot["execution"]["status_handled"] is True
    assert conversation.status is previous_status
    assert conversation.status_handled is previous_status_handled


def test_dump_conversation_state_includes_runtime_conversation_id() -> None:
    custom_variable = Variable(
        name="custom",
        type=StringProperty(),
        description="Custom variable used for snapshot serialization tests",
    )
    flow = _build_snapshot_flow(custom_variable)
    conversation = flow.start_conversation(inputs={custom_variable.name: "custom-value"})
    conversation.execute()

    snapshot = dump_conversation_state(conversation)

    assert snapshot["conversation"]["id"] == conversation.id
    assert snapshot["conversation"]["conversation_id"] == conversation.conversation_id


def test_dump_conversation_state_does_not_overload_status_conversation_identity() -> None:
    custom_variable = Variable(
        name="custom",
        type=StringProperty(),
        description="Custom variable used for snapshot serialization tests",
    )
    flow = _build_snapshot_flow(custom_variable)
    conversation = flow.start_conversation(inputs={custom_variable.name: "custom-value"})
    conversation.execute()

    snapshot = dump_conversation_state(conversation)

    assert snapshot["execution"]["status"]["type"] == "FinishedStatus"
    assert "conversation_id" not in snapshot["execution"]["status"]


def test_dump_variable_state_rejects_non_json_serializable_values() -> None:
    custom_variable = Variable(
        name="custom",
        type=AnyProperty(),
        description="Custom variable used for snapshot serialization tests",
    )
    flow = _build_snapshot_flow(custom_variable)
    conversation = flow.start_conversation(inputs={custom_variable.name: _UnserializableValue()})
    conversation.execute()

    with pytest.raises(TypeError, match="Variable 'custom' contains a non-JSON-serializable"):
        dump_variable_state(conversation)
