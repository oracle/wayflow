# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict, List

import pytest

from wayflowcore.events import register_event_listeners
from wayflowcore.events.event import LlmGenerationRequestEvent, LlmGenerationResponseEvent
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import LlmCompletion, LlmModelFactory, Prompt
from wayflowcore.tracing.span import LlmGenerationSpan, get_current_span
from wayflowcore.tracing.spanprocessor import SpanProcessor
from wayflowcore.tracing.trace import Trace

from ...conftest import VLLM_MODEL_CONFIG
from ...models.test_models import initialize_model, with_all_llm_configs, with_all_prompts
from ..conftest import InMemorySpanExporter


@pytest.mark.parametrize(
    "missing_attribute",
    [
        "llm",
        "prompt",
    ],
)
def test_span_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes = {
        "llm": LlmModelFactory.from_config(VLLM_MODEL_CONFIG),
        "prompt": [Message("How are you?")],
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        LlmGenerationSpan(**all_attributes)


@pytest.mark.parametrize(
    "span_info",
    [
        {
            "name": "My span test",
            "start_time": 12,
            "end_time": 13,
            "span_id": "abc123",
            "llm": LlmModelFactory.from_config(VLLM_MODEL_CONFIG),
            "prompt": [Message("How are you?")],
        },
        {
            "name": "My other span test",
            "llm": LlmModelFactory.from_config(VLLM_MODEL_CONFIG),
            "prompt": [Message("How are you now?")],
        },
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_span_serialization_format(
    span_info: Dict[str, Any], mask_sensitive_information: bool
) -> None:
    attributes_to_check = [
        attribute
        for attribute in (
            "name",
            "span_id",
            "start_time",
            "end_time",
        )
        if attribute in span_info
    ]
    with Trace(name="abc") as trace:
        span = LlmGenerationSpan(**span_info)
        serialized_span = span.to_tracing_info(
            mask_sensitive_information=mask_sensitive_information
        )
        assert serialized_span["trace_id"] == trace.trace_id
        assert serialized_span["trace_name"] == trace.name
        assert serialized_span["span_type"] == str(span.__class__.__name__)
        for attribute_name in attributes_to_check:
            attr = getattr(span, attribute_name)
            assert attr == serialized_span[attribute_name]
        assert serialized_span["llm.model_id"] == span.llm.model_id
        assert serialized_span["llm.model_type"] == span.llm.__class__.__name__
        assert serialized_span["llm.model_config"] == span.llm.config
        assert serialized_span["llm.generation_config"] == span.llm.generation_config.to_dict()


def test_correct_start_and_end_events_are_catched_by_eventlisteners() -> None:
    from ...events.event_listeners import (
        LlmGenerationRequestEventListener,
        LlmGenerationResponseEventListener,
    )

    request_eventlistener = LlmGenerationRequestEventListener()
    response_eventlistener = LlmGenerationResponseEventListener()
    llm = LlmModelFactory.from_config(VLLM_MODEL_CONFIG)
    with register_event_listeners([request_eventlistener, response_eventlistener]):
        with LlmGenerationSpan(llm=llm, prompt=Prompt(messages=[Message("How are you?")])) as span:
            assert len(request_eventlistener.triggered_events) == 1
            assert isinstance(request_eventlistener.triggered_events[0], LlmGenerationRequestEvent)
            assert len(response_eventlistener.triggered_events) == 0
            span.record_end_span_event(
                completion=LlmCompletion(
                    message=Message(content="Done", message_type=MessageType.AGENT),
                    token_usage=None,
                )
            )
        assert len(request_eventlistener.triggered_events) == 1
        assert len(response_eventlistener.triggered_events) == 1
        assert isinstance(response_eventlistener.triggered_events[0], LlmGenerationResponseEvent)


@with_all_llm_configs
@with_all_prompts
def test_event_is_triggered_on_generate(
    llm_config: Dict[str, str],
    prompt: List[Message],
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
) -> None:
    llm = initialize_model(llm_config)
    with Trace(span_processors=[default_span_processor]):
        _ = llm.generate(prompt=Prompt(prompt))
    exported_spans = default_span_exporter.get_exported_spans("LlmGenerationSpan")
    assert len(exported_spans) == 1
    span = exported_spans[0]
    assert len(span["events"]) == 2
    assert span["events"][0]["event_type"] == "LlmGenerationRequestEvent"
    assert span["events"][1]["event_type"] == "LlmGenerationResponseEvent"


@with_all_llm_configs
@with_all_prompts
def test_event_is_triggered_on_stream_generate(
    llm_config: Dict[str, str],
    prompt: List[Message],
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
) -> None:
    llm = initialize_model(llm_config)
    with Trace(span_processors=[default_span_processor]):
        llm_iter = llm.stream_generate(prompt=Prompt(prompt))
        for _ in llm_iter:
            pass
    exported_spans = default_span_exporter.get_exported_spans("LlmGenerationSpan")
    assert len(exported_spans) == 1
    span = exported_spans[0]
    assert len(span["events"]) == 2
    assert span["events"][0]["event_type"] == "LlmGenerationRequestEvent"
    assert span["events"][1]["event_type"] == "LlmGenerationResponseEvent"
    assert get_current_span() is None
