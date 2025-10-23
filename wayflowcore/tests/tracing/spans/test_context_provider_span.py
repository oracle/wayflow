# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict

import pytest

from wayflowcore.contextproviders import ContextProvider
from wayflowcore.contextproviders.constantcontextprovider import ConstantContextProvider
from wayflowcore.contextproviders.flowcontextprovider import FlowContextProvider
from wayflowcore.contextproviders.toolcontextprovider import ToolContextProvider
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.events.event import (
    ContextProviderExecutionRequestEvent,
    ContextProviderExecutionResultEvent,
)
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.property import DictProperty, IntegerProperty, StringProperty
from wayflowcore.steps.outputmessagestep import OutputMessageStep
from wayflowcore.tools.servertools import ServerTool
from wayflowcore.tracing.span import ContextProviderExecutionSpan
from wayflowcore.tracing.spanprocessor import SpanProcessor
from wayflowcore.tracing.trace import Trace

from ..conftest import InMemorySpanExporter


def test_span_creation_with_missing_arguments_fails() -> None:
    with pytest.raises(ValueError, match=f"An attribute named `context_provider`"):
        ContextProviderExecutionSpan()


@pytest.mark.parametrize(
    "span_info",
    [
        {
            "name": "My span test",
            "start_time": 12,
            "end_time": 13,
            "span_id": "abc123",
            "context_provider": ConstantContextProvider(
                value=1,
                output_description=IntegerProperty(name="value"),
            ),
        },
        {
            "name": "My other span test",
            "start_time": 12,
            "end_time": 13,
            "span_id": "abc123",
            "context_provider": ConstantContextProvider(
                value="abc123",
                output_description=StringProperty(name="value"),
            ),
        },
        {
            "name": "My other span test",
            "start_time": 12,
            "end_time": 13,
            "span_id": "abc123",
            "context_provider": ConstantContextProvider(
                value={"x": "y"}, output_description=DictProperty()
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
        span = ContextProviderExecutionSpan(**span_info)
        serialized_span = span.to_tracing_info(
            mask_sensitive_information=mask_sensitive_information
        )
        assert serialized_span["trace_id"] == trace.trace_id
        assert serialized_span["trace_name"] == trace.name
        assert serialized_span["span_type"] == str(span.__class__.__name__)
        for attribute_name in attributes_to_check:
            assert getattr(span, attribute_name) == serialized_span[attribute_name]
        assert serialized_span["context_provider.name"] == span.context_provider.name
        assert serialized_span["context_provider.type"] == span.context_provider.__class__.__name__


def test_correct_start_and_end_events_are_caught_by_eventlisteners() -> None:
    context_provider = ConstantContextProvider(
        value="Shore X",
        output_description=StringProperty("location_output"),
    )

    from ...events.event_listeners import (
        ContextProviderExecutionRequestEventListener,
        ContextProviderExecutionResultEventListener,
    )

    start_listener = ContextProviderExecutionRequestEventListener()
    end_listener = ContextProviderExecutionResultEventListener()

    with register_event_listeners([start_listener, end_listener]):
        with ContextProviderExecutionSpan(
            context_provider=context_provider,
        ) as span:
            assert len(start_listener.triggered_events) == 1
            assert isinstance(
                start_listener.triggered_events[0], ContextProviderExecutionRequestEvent
            )
            assert len(end_listener.triggered_events) == 0
            span.record_end_span_event(
                output="something",
            )
        assert len(start_listener.triggered_events) == 1
        assert isinstance(start_listener.triggered_events[0], ContextProviderExecutionRequestEvent)
        assert len(end_listener.triggered_events) == 1
        assert isinstance(end_listener.triggered_events[0], ContextProviderExecutionResultEvent)


@pytest.mark.parametrize(
    "context_provider",
    [
        FlowContextProvider(
            flow=create_single_step_flow(
                step=OutputMessageStep(
                    message_template="Shore X",
                    output_mapping={OutputMessageStep.OUTPUT: "location_output"},
                ),
            ),
            flow_output_names=["location_output"],
        ),
        ConstantContextProvider(
            value="Shore X",
            output_description=StringProperty("location_output"),
        ),
        ToolContextProvider(
            tool=ServerTool(
                name="get_location",
                description="Returns current location",
                func=lambda: "Shore X",
                input_descriptors=[],
            ),
            output_name="location_output",
        ),
    ],
)
def test_event_is_triggered_with_flow(
    context_provider: ContextProvider,
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
) -> None:
    output_step = OutputMessageStep(
        message_template="Location of the company is at {{location_output_io}}",
    )
    flow = Flow(
        begin_step=output_step,
        steps={"output_step": output_step},
        control_flow_edges=[ControlFlowEdge(output_step, None)],
        data_flow_edges=[
            DataFlowEdge(context_provider, "location_output", output_step, "location_output_io")
        ],
        context_providers=[context_provider],
    )
    conversation = flow.start_conversation()

    with Trace(span_processors=[default_span_processor]):
        conversation.execute()
    exported_spans = default_span_exporter.get_exported_spans("ContextProviderExecutionSpan")
    assert len(exported_spans) == 1
    span = exported_spans[0]
    assert len(span["events"]) >= 2
    assert span["events"][0]["event_type"] == "ContextProviderExecutionRequestEvent"
    assert span["events"][-1]["event_type"] == "ContextProviderExecutionResultEvent"
