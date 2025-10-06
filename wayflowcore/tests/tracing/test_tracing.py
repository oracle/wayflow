# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
import pytest

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.events.event import EndSpanEvent
from wayflowcore.flow import Flow
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import MapStep, PromptExecutionStep, StartStep
from wayflowcore.tracing.span import ConversationSpan
from wayflowcore.tracing.spanprocessor import SimpleSpanProcessor
from wayflowcore.tracing.trace import Trace, get_trace

from .conftest import InMemorySpanExporter, MyCustomSpan


def test_span_creation_with_default_values() -> None:
    trace = Trace()
    assert trace.trace_id is not None
    assert trace.name is None
    assert trace.span_processors == []


def test_trace_creation_with_custom_values() -> None:
    attributes = {
        "name": "My trace test",
        "trace_id": "abc123",
        "span_processors": [
            InMemorySpanExporter(),
            InMemorySpanExporter(),
        ],
    }
    trace = Trace(**attributes)
    for attribute_name, attribute_value in attributes.items():
        assert getattr(trace, attribute_name) == attribute_value


def test_global_trace_is_set_correctly(default_span_processor) -> None:
    assert get_trace() is None
    with Trace(name="my-trace", span_processors=[default_span_processor]) as trace:
        assert trace == get_trace()
    assert get_trace() is None


def test_start_multiple_traces_raise_exception(default_span_processor) -> None:
    with Trace(name="my-trace", span_processors=[default_span_processor]) as trace:
        with pytest.raises(
            RuntimeError, match="A Trace already exists. Cannot create two nested Traces."
        ):
            with Trace(name="my-trace", span_processors=[default_span_processor]):
                pass


@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_span_processor_methods_are_called_at_right_time(mask_sensitive_information: bool) -> None:
    span_exporters = [InMemorySpanExporter() for _ in range(3)]
    assert all(not span_exporter.startup_called for span_exporter in span_exporters)
    assert all(not span_exporter.shutdown_called for span_exporter in span_exporters)
    assert all(not span_exporter.force_flush_called for span_exporter in span_exporters)
    with Trace(
        span_processors=[
            SimpleSpanProcessor(
                span_exporter, mask_sensitive_information=mask_sensitive_information
            )
            for span_exporter in span_exporters
        ]
    ):
        assert all(span_exporter.startup_called for span_exporter in span_exporters)
        assert all(not span_exporter.shutdown_called for span_exporter in span_exporters)
        assert all(span_exporter.exported_spans == [] for span_exporter in span_exporters)
        with MyCustomSpan(custom_attribute=2) as span_1:
            assert all(span_exporter.exported_spans == [] for span_exporter in span_exporters)
            with MyCustomSpan() as span_2:
                assert all(span_exporter.exported_spans == [] for span_exporter in span_exporters)
                span_3 = MyCustomSpan(custom_attribute=100)
                span_3.start()
                assert all(span_exporter.exported_spans == [] for span_exporter in span_exporters)
                span_3.record_end_span_event(EndSpanEvent(span=span_3))
                assert all(span_exporter.exported_spans == [] for span_exporter in span_exporters)
                span_3.end()
                assert all(
                    span_exporter.exported_spans
                    == [
                        span_3.to_tracing_info(
                            mask_sensitive_information=mask_sensitive_information
                        )
                    ]
                    for span_exporter in span_exporters
                )
                span_2.record_end_span_event(EndSpanEvent(span=span_2))
                assert all(
                    span_exporter.exported_spans
                    == [
                        span_3.to_tracing_info(
                            mask_sensitive_information=mask_sensitive_information
                        )
                    ]
                    for span_exporter in span_exporters
                )
            assert all(
                span_exporter.exported_spans
                == [
                    span_3.to_tracing_info(mask_sensitive_information=mask_sensitive_information),
                    span_2.to_tracing_info(mask_sensitive_information=mask_sensitive_information),
                ]
                for span_exporter in span_exporters
            )
            span_1.record_end_span_event(EndSpanEvent(span=span_1))
            assert all(
                span_exporter.exported_spans
                == [
                    span_3.to_tracing_info(mask_sensitive_information=mask_sensitive_information),
                    span_2.to_tracing_info(mask_sensitive_information=mask_sensitive_information),
                ]
                for span_exporter in span_exporters
            )
        assert all(
            span_exporter.exported_spans
            == [
                span_3.to_tracing_info(mask_sensitive_information=mask_sensitive_information),
                span_2.to_tracing_info(mask_sensitive_information=mask_sensitive_information),
                span_1.to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            ]
            for span_exporter in span_exporters
        )
    assert all(span_exporter.shutdown_called for span_exporter in span_exporters)
    assert all(not span_exporter.force_flush_called for span_exporter in span_exporters)


def test_tracing_works_with_parallel_execution(
    llm,
) -> None:  # Tests if tracing works properly while using parallel execution.
    articles = [
        "Sea turtles are ancient reptiles that have been around for over 100 million years. They play crucial roles in marine ecosystems, such as maintaining healthy seagrass beds and coral reefs. Unfortunately, they are under threat due to poaching, habitat loss, and pollution. Conservation efforts worldwide aim to protect nesting sites and reduce bycatch in fishing gear.",
        "Dolphins are highly intelligent marine mammals known for their playfulness and curiosity. They live in social groups called pods, which can consist of hundreds of individuals depending on the species. Dolphins communicate using a variety of clicks, whistles, and other sounds. They face threats from habitat loss, marine pollution, and bycatch in fishing operations.",
        "Manatees, often referred to as 'sea cows', are gentle aquatic giants found in shallow coastal areas and rivers. These herbivorous mammals spend most of their time eating, resting, and traveling. They are particularly known for their slow movement and inability to survive in cold waters. Manatee populations are vulnerable to boat collisions, loss of warm-water habitats, and environmental pollutants.",
    ]

    start_step_1 = StartStep(name="start_step", input_descriptors=[StringProperty("article")])
    summarize_step = PromptExecutionStep(
        name="summarize_step",
        llm=llm,
        prompt_template="""Summarize this article in 10 words:
    {{article}}""",
        output_mapping={PromptExecutionStep.OUTPUT: "summary"},
    )
    summarize_flow = Flow(
        begin_step=start_step_1,
        control_flow_edges=[
            ControlFlowEdge(source_step=start_step_1, destination_step=summarize_step),
            ControlFlowEdge(source_step=summarize_step, destination_step=None),
        ],
        data_flow_edges=[
            DataFlowEdge(start_step_1, "article", summarize_step, "article"),
        ],
    )

    start_step = StartStep(input_descriptors=[ListProperty("articles", item_type=StringProperty())])
    map_step = MapStep(
        flow=summarize_flow,
        unpack_input={"article": "."},
        output_descriptors=[ListProperty(name="summary", item_type=StringProperty())],
        input_descriptors=[ListProperty(MapStep.ITERATED_INPUT, item_type=StringProperty())],
        parallel_execution=True,
    )
    map_step_name = "map_step"
    flow = Flow(
        begin_step_name="start_step",
        steps={
            "start_step": start_step,
            map_step_name: map_step,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=start_step, destination_step=map_step),
            ControlFlowEdge(source_step=map_step, destination_step=None),
        ],
        data_flow_edges=[
            DataFlowEdge(start_step, "articles", map_step, MapStep.ITERATED_INPUT),
        ],
    )

    conversation = flow.start_conversation(inputs={"articles": articles})
    span_exporter = InMemorySpanExporter()

    with Trace(span_processors=[SimpleSpanProcessor(span_exporter)]):
        with ConversationSpan(conversation=conversation) as conversation_span:
            status = conversation.execute()
            conversation_span.record_end_span_event(status)

    exported_spans = span_exporter.get_exported_spans()
    span_types = [exp_span["span_type"] for exp_span in exported_spans]

    assert (
        len(exported_spans) == 16
    )  # Expected number of total Spans. Previous iteration was outputting only 4 spans with parallel execution and 16 without.
    assert (
        len(set(span_types)) == 4
    )  # Expected Span types: ConversationSpan, FlowExecutionSpan, StepExecutionSpan, LlmGenerationSpan
    assert "LlmGenerationSpan" in span_types
