# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import time
from typing import Any, Dict

import pytest

from wayflowcore.events.event import Event


def test_event_creation_with_default_values() -> None:
    start_time = time.time_ns()
    event = Event()
    end_time = time.time_ns()
    assert event.name is None
    assert start_time <= event.timestamp <= end_time
    assert event.event_id is not None


def test_event_creation_with_custom_values() -> None:
    attributes = {
        "name": "My event test",
        "timestamp": 12,
        "event_id": "abc123",
    }
    event = Event(**attributes)
    for attribute_name, attribute_value in attributes.items():
        assert getattr(event, attribute_name) == attribute_value


def test_event_creation_with_partial_custom_values() -> None:
    start_time = time.time_ns()
    event = Event(event_id="123abc", name="My event test")
    end_time = time.time_ns()
    assert event.name == "My event test"
    assert start_time <= event.timestamp <= end_time
    assert event.event_id == "123abc"


@pytest.mark.parametrize(
    "event_info",
    [
        {
            "name": "My event test",
            "timestamp": 12,
            "event_id": "abc123",
        },
        {
            "name": "My test",
        },
        {
            "event_id": "abc123",
        },
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_correct_event_serialization_to_tracing_format(
    event_info: Dict[str, Any], mask_sensitive_information: bool
) -> None:
    event = Event(**event_info)
    serialized_json = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    assert serialized_json["event_type"] == str(event.__class__.__name__)
    for attribute_name, _ in event_info.items():
        assert getattr(event, attribute_name) == serialized_json[attribute_name]
