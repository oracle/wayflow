# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict, List

import pytest

from wayflowcore.agent import Agent
from wayflowcore.events.event import _MASKING_TOKEN, FlowExecutionIterationStartedEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors._flowexecutor import FlowConversationExecutionState
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.serialization.context import SerializationContext
from wayflowcore.serialization.serializer import serialize_any_to_dict
from wayflowcore.steps import (
    FlowExecutionStep,
    InputMessageStep,
    OutputMessageStep,
    ToolExecutionStep,
)
from wayflowcore.tools import ServerTool

from .conftest import (
    DUMMY_AGENT_WITH_GET_LOCATION_FLOW_AS_TOOL,
    GET_LOCATION_CLIENT_TOOL,
    count_agents_and_flows_in_flow,
)
from .event_listeners import FlowExecutionIterationStartedEventListener


@pytest.mark.parametrize("missing_attribute", ["execution_state"])
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes: Dict[str, Any] = {
        "execution_state": FlowConversationExecutionState(
            flow=create_single_step_flow(step=OutputMessageStep("Hello")),
            current_step_name="output_hello_message_step",
            input_output_key_values={},
        ),
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        FlowExecutionIterationStartedEvent(**all_attributes)


@pytest.mark.parametrize(
    "event_info, execution_state",
    [
        (
            {
                "name": "My event test",
                "timestamp": 12,
                "event_id": "abc123",
            },
            FlowConversationExecutionState(
                flow=create_single_step_flow(step=OutputMessageStep("Hello")),
                current_step_name="output_hello_message_step",
                input_output_key_values={},
            ),
        ),
        (
            {
                "name": "My other test",
            },
            FlowConversationExecutionState(
                flow=create_single_step_flow(step=InputMessageStep("What's your name")),
                current_step_name="input_name_message_step",
                input_output_key_values={},
            ),
        ),
        (
            {
                "name": "Yet another test",
                "event_id": "123abc",
            },
            FlowConversationExecutionState(
                flow=create_single_step_flow(
                    step=ToolExecutionStep(
                        tool=GET_LOCATION_CLIENT_TOOL,
                    )
                ),
                current_step_name="input_name_message_step",
                input_output_key_values={},
            ),
        ),
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_correct_event_serialization_to_tracing_format(
    event_info: Dict[str, Any],
    execution_state: FlowConversationExecutionState,
    mask_sensitive_information: bool,
) -> None:
    attributes_to_check = [
        attribute
        for attribute in (
            "name",
            "event_id",
            "timestamp",
            "current_step_name",
            "input_output_key_values",
            "variable_store",
            "step_history",
            "internal_context_key_values",
        )
        if attribute in event_info or hasattr(execution_state, attribute)
    ]
    event = FlowExecutionIterationStartedEvent(**event_info, execution_state=execution_state)
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    serialization_context = SerializationContext(root=execution_state)
    assert serialized_event["event_type"] == str(event.__class__.__name__)
    for attribute_name in attributes_to_check:
        try:
            assert getattr(event, attribute_name) == serialized_event[attribute_name]
        except AttributeError:
            if attribute_name in {
                "input_output_key_values",
                "internal_context_key_values",
                "variable_store",
            }:
                if mask_sensitive_information:
                    assert _MASKING_TOKEN == serialized_event[f"execution_state.{attribute_name}"]
                else:
                    assert (
                        serialize_any_to_dict(
                            getattr(event.execution_state, attribute_name), serialization_context
                        )
                        == serialized_event[f"execution_state.{attribute_name}"]
                    )
            else:
                assert (
                    getattr(event.execution_state, attribute_name)
                    == serialized_event[f"execution_state.{attribute_name}"]
                )


@pytest.mark.parametrize(
    "flow",
    [
        create_single_step_flow(
            step=OutputMessageStep("Hello"),
        ),
        create_single_step_flow(
            step=ToolExecutionStep(
                tool=ServerTool(
                    name="get_location",
                    description="This tool gets the current location",
                    func=lambda: print("Getting location..") or "Location is X",
                    input_descriptors=[],
                ),
            ),
        ),
        create_single_step_flow(step=InputMessageStep("What's your question?")),
    ],
)
def test_event_is_triggered_with_direct_call_flow_execute(
    flow: Flow,
) -> None:
    event_listener = FlowExecutionIterationStartedEventListener()

    with register_event_listeners([event_listener]):
        conversation = flow.start_conversation()
        flow.execute(conversation)

    assert len(event_listener.triggered_events) == 2
    assert isinstance(event_listener.triggered_events[0], FlowExecutionIterationStartedEvent)


@pytest.mark.parametrize(
    "flow",
    [
        create_single_step_flow(step=OutputMessageStep("Hello from flow")),
        create_single_step_flow(
            step=FlowExecutionStep(
                flow=create_single_step_flow(step=OutputMessageStep("Hello from subflow"))
            )
        ),
        create_single_step_flow(
            step=FlowExecutionStep(
                flow=create_single_step_flow(
                    step=FlowExecutionStep(
                        flow=create_single_step_flow(
                            step=OutputMessageStep(
                                "Hello from the depth of subflows",
                            )
                        )
                    )
                )
            )
        ),
        create_single_step_flow(
            step=FlowExecutionStep(
                flow=create_single_step_flow(
                    step=FlowExecutionStep(
                        flow=create_single_step_flow(
                            step=FlowExecutionStep(
                                flow=create_single_step_flow(
                                    step=OutputMessageStep(
                                        "Hello from the depth of subflows",
                                    )
                                )
                            )
                        )
                    )
                )
            )
        ),
        create_single_step_flow(
            step=FlowExecutionStep(
                flow=create_single_step_flow(
                    step=FlowExecutionStep(
                        flow=create_single_step_flow(
                            step=FlowExecutionStep(
                                flow=create_single_step_flow(
                                    step=FlowExecutionStep(
                                        flow=create_single_step_flow(
                                            step=OutputMessageStep(
                                                "Hello from the depth of subflows",
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
        ),
    ],
)
def test_events_are_triggered_with_nested_flows(
    flow: Flow,
) -> None:
    event_listener = FlowExecutionIterationStartedEventListener()
    conversation = flow.start_conversation()

    with register_event_listeners([event_listener]):
        flow.execute(conversation)

    # In this case each step has a flow iteration as well
    assert len(event_listener.triggered_events) == 2 + count_agents_and_flows_in_flow(flow) * 2
    assert all(
        isinstance(event, FlowExecutionIterationStartedEvent)
        for event in event_listener.triggered_events
    )


@pytest.mark.parametrize(
    "agent, user_messages",
    [
        (
            DUMMY_AGENT_WITH_GET_LOCATION_FLOW_AS_TOOL,
            ["Please use the tool"],
        ),
    ],
)
def test_event_is_triggered_with_agent_subflows(
    agent: Agent,
    user_messages: List[str],
) -> None:
    event_listener = FlowExecutionIterationStartedEventListener()
    conversation = agent.start_conversation()

    with register_event_listeners([event_listener]):
        agent.execute(conversation)
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            agent.execute(conversation)

    assert len(event_listener.triggered_events) == 2
    assert isinstance(event_listener.triggered_events[0], FlowExecutionIterationStartedEvent)
