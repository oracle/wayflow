# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict

import pytest

from wayflowcore.events.event import ToolExecutionResultEvent, ToolExecutionStartEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.flowhelpers import _run_flow_and_return_status, create_single_step_flow
from wayflowcore.property import StringProperty
from wayflowcore.steps.toolexecutionstep import ToolExecutionStep
from wayflowcore.tools.clienttools import ClientTool
from wayflowcore.tools.servertools import ServerTool
from wayflowcore.tools.tools import ToolRequest
from wayflowcore.tracing.span import ToolExecutionSpan
from wayflowcore.tracing.spanprocessor import SpanProcessor
from wayflowcore.tracing.trace import Trace

from ..conftest import InMemorySpanExporter
from .conftest import DUMMY_SERVER_TOOL


@pytest.mark.parametrize("missing_attribute", ["tool", "tool_request"])
def test_span_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes: Dict[str, Any] = {
        "tool": DUMMY_SERVER_TOOL,
        "tool_request": ToolRequest(
            name=DUMMY_SERVER_TOOL.name,
            args={},
            tool_request_id="abc123",
        ),
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        ToolExecutionSpan(**all_attributes)


@pytest.mark.parametrize(
    "span_info",
    [
        {
            "name": "My span test",
            "start_time": 12,
            "end_time": 13,
            "span_id": "abc123",
            "tool": ServerTool(
                name="simple_function",
                description="This is a simple function",
                func=lambda: print("This is a simple function"),
                input_descriptors=[],
            ),
            "tool_request": ToolRequest(
                name="simple_function",
                args={},
                tool_request_id="abc123",
            ),
        },
        {
            "name": "My other span test",
            "start_time": 12,
            "end_time": 13,
            "span_id": "abc123",
            "tool": ClientTool(
                name="simple_function",
                description="This is a simple function",
                input_descriptors=[StringProperty("location")],
            ),
            "tool_request": ToolRequest(
                name="simple_function",
                args={"location": "Oracle"},
                tool_request_id="abc123",
            ),
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
        span = ToolExecutionSpan(**span_info)
        serialized_span = span.to_tracing_info(
            mask_sensitive_information=mask_sensitive_information
        )
        assert serialized_span["trace_id"] == trace.trace_id
        assert serialized_span["trace_name"] == trace.name
        assert serialized_span["span_type"] == str(span.__class__.__name__)
        for attribute_name in attributes_to_check:
            assert getattr(span, attribute_name) == serialized_span[attribute_name]
        assert serialized_span["tool.name"] == span.tool.name
        assert serialized_span["tool.description"] == span.tool.description
        assert serialized_span["tool.type"] == span.tool.__class__.__name__
        for attribute_name in ["input_descriptors", "output_descriptors"]:
            if mask_sensitive_information:
                assert serialized_span[f"tool.{attribute_name}"] == [
                    descriptor.name for descriptor in getattr(span.tool, attribute_name)
                ]
            else:
                assert serialized_span[f"tool.{attribute_name}"] == [
                    descriptor.to_json_schema() for descriptor in getattr(span.tool, attribute_name)
                ]


def test_correct_start_and_end_events_are_caught_by_eventlisteners() -> None:
    from ...events.event_listeners import (
        ToolExecutionResultEventListener,
        ToolExecutionStartEventListener,
    )

    tool = ServerTool(
        name="say_hi",
        description="This tool allows you to say hi to someone",
        func=lambda someone: f"Hi {someone}",
        input_descriptors=[StringProperty("someone")],
    )
    tool_request = ToolRequest(
        name=tool.name, args={"someone": "someone_like_you"}, tool_request_id="test123"
    )

    start_listener = ToolExecutionStartEventListener()
    end_listener = ToolExecutionResultEventListener()

    with register_event_listeners([start_listener, end_listener]):
        with ToolExecutionSpan(
            tool=tool,
            tool_request=tool_request,
        ) as span:
            assert len(start_listener.triggered_events) == 1
            assert isinstance(start_listener.triggered_events[0], ToolExecutionStartEvent)
            assert len(end_listener.triggered_events) == 0
            output = tool.run("someone_like_you")
            span.record_end_span_event(
                output=output,
            )
        assert len(start_listener.triggered_events) == 1
        assert isinstance(start_listener.triggered_events[0], ToolExecutionStartEvent)
        assert len(end_listener.triggered_events) == 1
        assert isinstance(end_listener.triggered_events[0], ToolExecutionResultEvent)


def test_event_is_triggered_with_flow(
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
) -> None:
    flow = create_single_step_flow(ToolExecutionStep(tool=DUMMY_SERVER_TOOL))

    with Trace(span_processors=[default_span_processor]):
        _run_flow_and_return_status(flow=flow, inputs={})
    exported_spans = default_span_exporter.get_exported_spans("ToolExecutionSpan")
    assert len(exported_spans) == 1
    span = exported_spans[0]
    assert len(span["events"]) >= 2
    assert span["events"][0]["event_type"] == "ToolExecutionStartEvent"
    assert span["events"][-1]["event_type"] == "ToolExecutionResultEvent"
