# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.from typing import Any, Dict
from typing import Any, Dict

import pytest

from wayflowcore import Flow
from wayflowcore.agent import Agent
from wayflowcore.events.event import _MASKING_TOKEN, ConversationMessageStreamChunkEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.steps import PromptExecutionStep

from .event_listeners import ConversationMessageStreamChunkEventListener


@pytest.mark.parametrize("missing_attribute", ["chunk"])
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes = {"chunk": " content"}
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        ConversationMessageStreamChunkEvent(**all_attributes)


@pytest.mark.parametrize(
    "event_info",
    [
        {
            "chunk": " content",
        },
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_correct_event_serialization_to_tracing_format(
    event_info: Dict[str, Any], mask_sensitive_information: bool
) -> None:
    event = ConversationMessageStreamChunkEvent(**event_info)
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    assert serialized_event["event_type"] == str(event.__class__.__name__)
    assert (
        serialized_event["chunk"] == event.chunk
        if not mask_sensitive_information
        else _MASKING_TOKEN
    )


def test_event_is_triggered_with_agent(remotely_hosted_llm):
    event_listener = ConversationMessageStreamChunkEventListener()
    agent = Agent(llm=remotely_hosted_llm)
    conv = agent.start_conversation()
    conv.append_user_message("what is the capital of Switzerland?")
    with register_event_listeners([event_listener]):
        conv.execute()
    assert len(event_listener.triggered_events) > 0
    assert all(
        isinstance(t, ConversationMessageStreamChunkEvent) for t in event_listener.triggered_events
    )


def test_event_is_triggered_with_flow(remotely_hosted_llm):
    event_listener = ConversationMessageStreamChunkEventListener()
    step = PromptExecutionStep(
        prompt_template="what is the capital of Switzerland?",
        llm=remotely_hosted_llm,
        send_message=True,  # should therefore stream
    )
    flow = Flow.from_steps([step])
    conv = flow.start_conversation()
    with register_event_listeners([event_listener]):
        conv.execute()
    assert len(event_listener.triggered_events) > 0
    assert all(
        isinstance(t, ConversationMessageStreamChunkEvent) for t in event_listener.triggered_events
    )
