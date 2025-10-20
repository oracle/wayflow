# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict

import pytest

from wayflowcore import Agent, Flow, Message, MessageList
from wayflowcore.events.event import (
    ConversationMessageStreamChunkEvent,
    ConversationMessageStreamEndedEvent,
    ConversationMessageStreamStartedEvent,
)
from wayflowcore.events.eventlistener import record_event, register_event_listeners
from wayflowcore.flowhelpers import _run_flow_and_return_status
from wayflowcore.serialization import serialize_to_dict
from wayflowcore.steps import PromptExecutionStep
from wayflowcore.tracing.span import _MASKING_TOKEN, ConversationMessageStreamSpan
from wayflowcore.tracing.spanprocessor import SpanProcessor
from wayflowcore.tracing.trace import Trace

from ..conftest import InMemorySpanExporter


@pytest.mark.parametrize("missing_attribute", ["message_list", "initial_message"])
def test_span_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes: Dict[str, Any] = {
        "message_list": MessageList(),
        "initial_message": Message(content=""),
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        ConversationMessageStreamSpan(**all_attributes)


@pytest.mark.parametrize(
    "span_info",
    [
        {
            "name": "My span test",
            "start_time": 12,
            "end_time": 13,
            "span_id": "abc123",
            "message_list": MessageList(
                messages=[Message(content="1"), Message(content="2")],
            ),
            "initial_message": Message(content="some initial_message"),
        },
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_span_serialization_format(
    span_info: Dict[str, Any], mask_sensitive_information: bool
) -> None:
    attributes_to_check = [
        attribute
        for attribute in ("name", "span_id", "start_time", "end_time")
        if attribute in span_info
    ]
    with Trace(name="abc") as trace:
        span = ConversationMessageStreamSpan(**span_info)
        serialized_span = span.to_tracing_info(
            mask_sensitive_information=mask_sensitive_information
        )
        assert serialized_span["trace_id"] == trace.trace_id
        assert serialized_span["trace_name"] == trace.name
        assert serialized_span["span_type"] == str(span.__class__.__name__)
        for attribute_name in attributes_to_check:
            assert getattr(span, attribute_name) == serialized_span[attribute_name]
        assert serialized_span["initial_message"] == (
            serialize_to_dict(span_info["initial_message"])
            if not mask_sensitive_information
            else _MASKING_TOKEN
        )
        assert serialized_span["messages.id"] == span_info["message_list"].id


def test_correct_start_and_end_events_are_caught_by_eventlisteners() -> None:
    from ...events.event_listeners import (
        ConversationMessageStreamChunkEventListener,
        ConversationMessageStreamEndedEventListener,
        ConversationMessageStreamStartedEventListener,
    )

    start_listener = ConversationMessageStreamStartedEventListener()
    chunk_listener = ConversationMessageStreamChunkEventListener()
    end_listener = ConversationMessageStreamEndedEventListener()

    message_list = MessageList()

    with register_event_listeners([start_listener, chunk_listener, end_listener]):
        with ConversationMessageStreamSpan(
            message_list=message_list,
            initial_message=Message(content="hi"),
        ) as span:
            assert len(start_listener.triggered_events) == 1
            assert isinstance(
                start_listener.triggered_events[0], ConversationMessageStreamStartedEvent
            )
            assert len(end_listener.triggered_events) == 0
            for chunk in [", how", " are you ", "doing?"]:
                record_event(ConversationMessageStreamChunkEvent(chunk=chunk))
            span.record_end_span_event(message=Message(content="hi, how are you doing?"))
        assert len(start_listener.triggered_events) == 1
        assert isinstance(start_listener.triggered_events[0], ConversationMessageStreamStartedEvent)
        assert len(chunk_listener.triggered_events) == 3
        assert all(
            isinstance(e, ConversationMessageStreamChunkEvent)
            for e in chunk_listener.triggered_events
        )
        assert len(end_listener.triggered_events) == 1
        assert isinstance(end_listener.triggered_events[0], ConversationMessageStreamEndedEvent)


def test_event_is_triggered_with_agent(
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
    remotely_hosted_llm,
) -> None:
    agent = Agent(llm=remotely_hosted_llm)
    conv = agent.start_conversation()
    conv.append_user_message("what is the capital of Switzerland?")

    with Trace(span_processors=[default_span_processor]):
        conv.execute()
    exported_spans = default_span_exporter.get_exported_spans("ConversationMessageStreamSpan")
    assert len(exported_spans) == 1
    span = exported_spans[0]
    assert len(span["events"]) >= 2
    assert span["events"][0]["event_type"] == "ConversationMessageStreamStartedEvent"
    assert all(
        e["event_type"] == "ConversationMessageStreamChunkEvent" for e in span["events"][1:-1]
    )
    assert span["events"][-1]["event_type"] == "ConversationMessageStreamEndedEvent"


def test_event_is_triggered_with_flow(
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
    remotely_hosted_llm,
) -> None:
    step = PromptExecutionStep(
        prompt_template="what is the capital of Switzerland?",
        llm=remotely_hosted_llm,
        send_message=True,  # should therefore stream
    )
    flow = Flow.from_steps([step])

    with Trace(span_processors=[default_span_processor]):
        _run_flow_and_return_status(flow=flow, inputs={})
    exported_spans = default_span_exporter.get_exported_spans("ConversationMessageStreamSpan")
    assert len(exported_spans) == 1
    span = exported_spans[0]
    assert len(span["events"]) >= 2
    assert span["events"][0]["event_type"] == "ConversationMessageStreamStartedEvent"
    assert all(
        e["event_type"] == "ConversationMessageStreamChunkEvent" for e in span["events"][1:-1]
    )
    assert span["events"][-1]["event_type"] == "ConversationMessageStreamEndedEvent"
