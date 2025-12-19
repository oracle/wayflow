# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
from typing import Any, Dict, List

import pytest

from wayflowcore.events.event import _PII_TEXT_MASK, LlmGenerationRequestEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import Prompt
from wayflowcore.serialization import serialize_to_dict
from wayflowcore.tools.tools import ToolRequest, ToolResult

from ..models.test_models import initialize_model, with_all_llm_configs_and_dummy, with_all_prompts
from ..testhelpers.dummy import DummyModel
from ..testhelpers.patching import patch_llm
from .event_listeners import LlmGenerationRequestEventListener


@pytest.mark.parametrize("missing_attribute", ["llm", "prompt"])
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes = {
        "llm": DummyModel(),
        "prompt": "Hey, how are you?",
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        LlmGenerationRequestEvent(**all_attributes)


@pytest.mark.parametrize(
    "event_info",
    [
        {
            "name": "My event test",
            "timestamp": 12,
            "event_id": "abc123",
            "prompt": Prompt(messages=[Message("Hello, how are you doing?")]),
        },
        {
            "prompt": Prompt(
                messages=[
                    Message(
                        content="How can I help you?",
                        message_type=MessageType.AGENT,
                        sender="agent",
                        recipients={"me", "abc", "bcd"},
                    ),
                    Message(
                        content="What's the weather like today?",
                        message_type=MessageType.USER,
                        sender="me",
                        recipients={"agent", "abc", "bcd"},
                    ),
                ]
            ),
        },
        {
            "name": "My complicated test",
            "prompt": Prompt(
                messages=[
                    Message(
                        content="Tool requests",
                        message_type=MessageType.TOOL_REQUEST,
                        tool_requests=[
                            ToolRequest(
                                name="tool_request_1",
                                args={"param1": 1, "param2": "a"},
                                tool_request_id="tr_id_1",
                            ),
                            ToolRequest(
                                name="tool_request_2",
                                args={"param3": "1", "param4": 3},
                                tool_request_id="tr_id_2",
                            ),
                        ],
                        tool_result=None,
                        sender="agent",
                        recipients={"me"},
                    ),
                    Message(
                        message_type=MessageType.TOOL_RESULT,
                        tool_requests=None,
                        tool_result=ToolResult(content="result", tool_request_id="tr_id_1"),
                        sender="agent",
                        recipients={"me"},
                    ),
                ]
            ),
        },
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_correct_event_serialization_to_tracing_format(
    event_info: Dict[str, Any], mask_sensitive_information: bool
) -> None:
    attributes_to_check = [
        attribute
        for attribute in ("name", "event_id", "timestamp", "prompt")
        if attribute in event_info
    ]
    event = LlmGenerationRequestEvent(llm=DummyModel(), **event_info)
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    assert serialized_event["event_type"] == str(event.__class__.__name__)
    for attribute_name in attributes_to_check:
        if attribute_name == "prompt":
            if mask_sensitive_information:
                assert _PII_TEXT_MASK == serialized_event[attribute_name]
            else:
                assert (
                    serialize_to_dict(event_info[attribute_name])
                    == serialized_event[attribute_name]
                )
        else:
            assert getattr(event, attribute_name) == serialized_event[attribute_name]


@with_all_llm_configs_and_dummy
@with_all_prompts
def test_event_is_triggered_on_generate(llm_config: Dict[str, str], prompt: List[Message]) -> None:
    event_listener = LlmGenerationRequestEventListener()
    llm = initialize_model(llm_config)
    # need to patch the internal method, because the event is registered in the external one
    with patch_llm(llm, ["whatever"], patch_internal=True):
        with register_event_listeners([event_listener]):
            _ = llm.generate(prompt=Prompt(prompt))
    assert len(event_listener.triggered_events) == 1
    assert isinstance(event_listener.triggered_events[0], LlmGenerationRequestEvent)


@with_all_llm_configs_and_dummy
@with_all_prompts
def test_event_is_triggered_on_stream_generate(
    llm_config: Dict[str, str], prompt: List[Message]
) -> None:
    event_listener = LlmGenerationRequestEventListener()
    llm = initialize_model(llm_config)
    # need to patch the internal method, because the event is registered in the external one
    with patch_llm(llm, ["whatever"], patch_internal=True):
        with register_event_listeners([event_listener]):
            llm_iter = llm.stream_generate(Prompt(messages=prompt))
            for _ in llm_iter:
                pass
    assert len(event_listener.triggered_events) == 1
    assert isinstance(event_listener.triggered_events[0], LlmGenerationRequestEvent)
