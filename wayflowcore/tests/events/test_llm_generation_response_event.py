# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import Any, Dict, List

import pytest

from wayflowcore.events.event import _MASKING_TOKEN, LlmGenerationResponseEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.messagelist import Message
from wayflowcore.models import LlmCompletion, Prompt
from wayflowcore.serialization import serialize_to_dict
from wayflowcore.tokenusage import TokenUsage

from ..models.test_models import initialize_model, with_all_llm_configs_and_dummy, with_all_prompts
from ..testhelpers.dummy import DummyModel
from .event_listeners import LlmGenerationResponseEventListener


@pytest.mark.parametrize("missing_attribute", ["llm", "completion"])
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes = {
        "llm": DummyModel(),
        "completion": LlmCompletion(
            message=Message("Hey, how are you?"),
            token_usage=TokenUsage(input_tokens=1000, output_tokens=200),
        ),
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        LlmGenerationResponseEvent(**all_attributes)


@pytest.mark.parametrize(
    "event_info",
    [
        {
            "name": "My event test",
            "timestamp": 12,
            "event_id": "abc123",
            "completion": LlmCompletion(
                message=Message("Hey, how are you?"),
                token_usage=TokenUsage(input_tokens=1000, output_tokens=200),
            ),
        },
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_correct_event_serialization_to_tracing_format(
    event_info: Dict[str, Any], mask_sensitive_information: bool
) -> None:
    event = LlmGenerationResponseEvent(llm=DummyModel(), **event_info)
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    assert serialized_event["event_type"] == str(event.__class__.__name__)
    for attribute_name, _ in event_info.items():
        if attribute_name == "completion":
            if mask_sensitive_information:
                assert _MASKING_TOKEN == serialized_event[attribute_name]
            else:
                assert (
                    serialize_to_dict(getattr(event, attribute_name))
                    == serialized_event[attribute_name]
                )
        else:
            assert getattr(event, attribute_name) == serialized_event[attribute_name]


@with_all_llm_configs_and_dummy
@with_all_prompts
def test_event_is_triggered_on_generate(llm_config: Dict[str, str], prompt: List[Message]) -> None:
    event_listener = LlmGenerationResponseEventListener()
    llm = initialize_model(llm_config)
    with register_event_listeners([event_listener]):
        _ = llm.generate(Prompt(messages=prompt))
    assert len(event_listener.triggered_events) == 1
    assert isinstance(event_listener.triggered_events[0], LlmGenerationResponseEvent)


@with_all_llm_configs_and_dummy
@with_all_prompts
def test_event_is_triggered_on_stream_generate(
    llm_config: Dict[str, str], prompt: List[Message]
) -> None:
    event_listener = LlmGenerationResponseEventListener()
    llm = initialize_model(llm_config)
    with register_event_listeners([event_listener]):
        llm_iter = llm.stream_generate(prompt=Prompt(prompt))
        for _ in llm_iter:
            pass
    assert len(event_listener.triggered_events) == 1
    assert isinstance(event_listener.triggered_events[0], LlmGenerationResponseEvent)
