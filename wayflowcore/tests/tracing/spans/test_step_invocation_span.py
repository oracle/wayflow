# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict

import pytest

from wayflowcore.events.event import StepInvocationResultEvent, StepInvocationStartEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps.inputmessagestep import InputMessageStep
from wayflowcore.steps.outputmessagestep import OutputMessageStep
from wayflowcore.steps.step import StepResult
from wayflowcore.steps.toolexecutionstep import ToolExecutionStep
from wayflowcore.tracing.span import _MASKING_TOKEN, StepInvocationSpan
from wayflowcore.tracing.spanprocessor import SpanProcessor
from wayflowcore.tracing.trace import Trace

from ..conftest import InMemorySpanExporter
from .conftest import DUMMY_SERVER_TOOL


@pytest.mark.parametrize("missing_attribute", ["step", "inputs"])
def test_span_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes: Dict[str, Any] = {
        "step": OutputMessageStep("Hello world"),
        "inputs": {},
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        StepInvocationSpan(**all_attributes)


@pytest.mark.parametrize(
    "span_info",
    [
        {
            "name": "My span test",
            "start_time": 12,
            "end_time": 13,
            "span_id": "abc123",
            "step": OutputMessageStep(
                message_template="Hi, location is here.",
                input_descriptors=[],
                output_descriptors=[],
                name="Formats location message nicely",
                input_mapping={},
            ),
            "inputs": {},
        },
        {
            "name": "My other span test",
            "start_time": 12,
            "end_time": 13,
            "span_id": "abc123",
            "step": InputMessageStep(
                message_template="Hi, location is here.",
                input_descriptors=[],
                output_descriptors=[],
                name="Formats location message nicely",
                input_mapping={},
            ),
            "inputs": {},
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
        span = StepInvocationSpan(**span_info)
        serialized_span = span.to_tracing_info(
            mask_sensitive_information=mask_sensitive_information
        )
        assert serialized_span["trace_id"] == trace.trace_id
        assert serialized_span["trace_name"] == trace.name
        assert serialized_span["span_type"] == str(span.__class__.__name__)
        for attribute_name in attributes_to_check:
            assert getattr(span, attribute_name) == serialized_span[attribute_name]
        assert serialized_span["step.name"] == span.step.name
        if mask_sensitive_information:
            assert serialized_span["step.static_configuration"] == _MASKING_TOKEN
        else:
            assert (
                serialized_span["step.static_configuration"] == span.step._step_static_configuration
            )
        assert serialized_span["step.input_mapping"] == span.step.input_mapping
        assert serialized_span["step.output_mapping"] == span.step.output_mapping
        for attribute_name in ["input_descriptors", "output_descriptors"]:
            if mask_sensitive_information:
                assert serialized_span[f"step.{attribute_name}"] == [
                    descriptor.name for descriptor in getattr(span.step, attribute_name)
                ]
            else:
                assert serialized_span[f"step.{attribute_name}"] == [
                    descriptor.to_json_schema() for descriptor in getattr(span.step, attribute_name)
                ]


def test_correct_start_and_end_events_are_caught_by_eventlisteners() -> None:
    from ...events.event_listeners import (
        StepInvocationResultEventListener,
        StepInvocationStartEventListener,
    )

    start_listener = StepInvocationStartEventListener()
    end_listener = StepInvocationResultEventListener()

    step = OutputMessageStep("Hello")
    inputs = {}

    with register_event_listeners([start_listener, end_listener]):
        with StepInvocationSpan(step=step, inputs=inputs) as span:
            assert len(start_listener.triggered_events) == 1
            assert isinstance(start_listener.triggered_events[0], StepInvocationStartEvent)
            assert len(end_listener.triggered_events) == 0
            span.record_end_span_event(
                step_result=StepResult({"output": "Hello"}),
            )
        assert len(start_listener.triggered_events) == 1
        assert isinstance(start_listener.triggered_events[0], StepInvocationStartEvent)
        assert len(end_listener.triggered_events) == 1
        assert isinstance(end_listener.triggered_events[0], StepInvocationResultEvent)


@pytest.mark.parametrize(
    "flow",
    [
        create_single_step_flow(OutputMessageStep("Hello")),
        create_single_step_flow(InputMessageStep("Hello")),
        create_single_step_flow(ToolExecutionStep(tool=DUMMY_SERVER_TOOL)),
    ],
)
def test_event_is_triggered_with_flow(
    flow: Flow,
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
) -> None:
    with Trace(span_processors=[default_span_processor]):
        flow.start_conversation().execute()
    exported_spans = default_span_exporter.get_exported_spans("StepInvocationSpan")

    # Has a start step, so two spans are created
    assert len(exported_spans) == 2
    span = exported_spans[0]
    assert len(span["events"]) >= 2
    assert span["events"][0]["event_type"] == "StepInvocationStartEvent"
    assert span["events"][-1]["event_type"] == "StepInvocationResultEvent"
