# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import Any, Dict, List, Set

import pytest

from wayflowcore._utils.formatting import stringify
from wayflowcore.contextproviders import ContextProvider
from wayflowcore.contextproviders.constantcontextprovider import ConstantContextProvider
from wayflowcore.contextproviders.flowcontextprovider import FlowContextProvider
from wayflowcore.contextproviders.toolcontextprovider import ToolContextProvider
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.events.event import _MASKING_TOKEN, ContextProviderExecutionResultEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.property import DictProperty, IntegerProperty, StringProperty
from wayflowcore.steps.outputmessagestep import OutputMessageStep
from wayflowcore.steps.step import Step
from wayflowcore.tools.servertools import ServerTool

from .event_listeners import ContextProviderExecutionResultEventListener


@pytest.mark.parametrize("missing_attribute", ["context_provider", "output"])
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes: Dict[str, Any] = {
        "context_provider": ConstantContextProvider(
            value=1,
            output_description=IntegerProperty(),
        ),
        "output": 1,
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        ContextProviderExecutionResultEvent(**all_attributes)


@pytest.mark.parametrize(
    "event_info",
    [
        {
            "name": "My event test",
            "timestamp": 12,
            "event_id": "abc123",
            "context_provider": ConstantContextProvider(
                value=1,
                output_description=IntegerProperty(name="value"),
            ),
            "output": 1,
        },
        {
            "name": "My other test",
            "context_provider": ConstantContextProvider(
                value="abc123",
                output_description=StringProperty(name="value"),
            ),
            "output": "abc123",
        },
        {
            "name": "Yet another test",
            "event_id": "123abc",
            "context_provider": ConstantContextProvider(
                value={"x": "y"}, output_description=DictProperty()
            ),
            "output": {"x": "y"},
        },
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_correct_event_serialization_to_tracing_format(
    event_info: Dict[str, Any], mask_sensitive_information: bool
) -> None:
    attributes_to_check = [
        attribute
        for attribute in ("name", "event_id", "timestamp", "output")
        if attribute in event_info
    ]
    event = ContextProviderExecutionResultEvent(**event_info)
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    assert serialized_event["event_type"] == str(event.__class__.__name__)
    for attribute_name in attributes_to_check:
        attr = getattr(event, attribute_name)
        if attribute_name == "output":
            if mask_sensitive_information:
                assert _MASKING_TOKEN == serialized_event[attribute_name]
            else:
                assert stringify(attr) == serialized_event[attribute_name]
        else:
            assert attr == serialized_event[attribute_name]


@pytest.mark.parametrize(
    "context_provider, expected_output",
    [
        (
            FlowContextProvider(
                flow=create_single_step_flow(
                    step=OutputMessageStep(
                        message_template="Shore X",
                        output_mapping={OutputMessageStep.OUTPUT: "location_output"},
                    ),
                ),
                flow_output_names=["location_output"],
            ),
            "Shore X",
        ),
        (
            ConstantContextProvider(
                value=2025,
                output_description=IntegerProperty("Year"),
            ),
            2025,
        ),
        (
            ToolContextProvider(
                tool=ServerTool(
                    name="get_weather",
                    description="Returns current weather",
                    func=lambda: "The weather is currently sunny",
                    input_descriptors=[],
                )
            ),
            "The weather is currently sunny",
        ),
    ],
)
def test_event_is_triggered_with_direct_call(
    context_provider: ContextProvider,
    expected_output: Any,
) -> None:
    event_listener = ContextProviderExecutionResultEventListener()
    flow = create_single_step_flow(step=OutputMessageStep("simple flow test"))
    conversation = flow.start_conversation()

    with register_event_listeners([event_listener]):
        context_provider(conversation)

    assert len(event_listener.triggered_events) == 1
    assert isinstance(event_listener.triggered_events[0], ContextProviderExecutionResultEvent)
    assert event_listener.triggered_events[0].output == expected_output


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
) -> None:
    expected_output = "Shore X"
    test_output_step = OutputMessageStep(
        message_template="Location of the company is at {{location_output_io}}",
    )
    flow = Flow(
        begin_step_name="output_step",
        steps={"output_step": test_output_step},
        control_flow_edges=[ControlFlowEdge(test_output_step, None)],
        data_flow_edges=[
            DataFlowEdge(
                context_provider, "location_output", test_output_step, "location_output_io"
            )
        ],
        context_providers=[context_provider],
    )
    conversation = flow.start_conversation()
    event_listener = ContextProviderExecutionResultEventListener()

    with register_event_listeners([event_listener]):
        flow.execute(conversation)

    assert len(event_listener.triggered_events) == 1
    assert isinstance(event_listener.triggered_events[0], ContextProviderExecutionResultEvent)
    assert event_listener.triggered_events[0].output == expected_output


@pytest.mark.parametrize(
    "context_providers, expected_outputs, test_step",
    [
        (
            [
                ConstantContextProvider(
                    value="Shore X",
                    output_description=StringProperty("location_output"),
                ),
                ConstantContextProvider(
                    value="Y inc",
                    output_description=StringProperty("company_name"),
                ),
            ],
            {
                "Shore X",
                "Y inc",
            },
            OutputMessageStep(
                message_template="Location of the company {{company_name_io}} is at {{location_output_io}}.",
            ),
        ),
        (
            [
                ToolContextProvider(
                    tool=ServerTool(
                        name="get_weather",
                        description="Returns current weather",
                        func=lambda: "sunny",
                        input_descriptors=[],
                    ),
                    output_name="weather_info",
                ),
                ConstantContextProvider(
                    value="Shore X",
                    output_description=StringProperty("location_output"),
                ),
            ],
            {
                "sunny",
                "Shore X",
            },
            OutputMessageStep(
                message_template="The weather at location {{location_output_io}} is {{weather_info_io}}.",
            ),
        ),
    ],
)
def test_multiple_events_are_triggered(
    context_providers: List[ContextProvider],
    expected_outputs: Set[Any],
    test_step: Step,
) -> None:
    data_flow_edges: List[DataFlowEdge] = []
    for ctx in context_providers:
        source_output = ctx.get_output_descriptors()[0].name
        destination_input = f"{source_output}_io"
        data_flow_edges.append(DataFlowEdge(ctx, source_output, test_step, destination_input))
    flow = Flow(
        begin_step_name="output_step",
        steps={"output_step": test_step},
        control_flow_edges=[ControlFlowEdge(test_step, None)],
        data_flow_edges=data_flow_edges,
        context_providers=context_providers,
    )
    conversation = flow.start_conversation()
    event_listener = ContextProviderExecutionResultEventListener()

    with register_event_listeners([event_listener]):
        flow.execute(conversation)

    assert len(event_listener.triggered_events) == len(context_providers)
    assert len(event_listener.triggered_events) == len(expected_outputs)
    assert all(
        isinstance(event, ContextProviderExecutionResultEvent)
        for event in event_listener.triggered_events
    )
    outputs = set(event.output for event in event_listener.triggered_events)
    assert outputs == expected_outputs
