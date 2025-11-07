# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List, Type

import pytest

from wayflowcore.agent import Agent
from wayflowcore.events.event import (
    AgentExecutionFinishedEvent,
    ConversationalComponentExecutionFinishedEvent,
    FlowExecutionFinishedEvent,
)
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors.executionstatus import (
    ExecutionStatus,
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import _run_flow_and_return_status, create_single_step_flow
from wayflowcore.messagelist import Message
from wayflowcore.steps import InputMessageStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep
from wayflowcore.steps.flowexecutionstep import FlowExecutionStep
from wayflowcore.tools import DescribedFlow, ToolRequest

from ..testhelpers.dummy import DummyModel
from .conftest import (
    DUMMY_AGENT_WITH_CONVERSATION_EXIT,
    DUMMY_AGENT_WITH_GET_LOCATION_FLOW_AS_TOOL,
    DUMMY_AGENT_WITH_GET_LOCATION_TOOL,
    GET_LOCATION_CLIENT_TOOL,
    count_agents_and_flows_in_flow,
)
from .event_listeners import (
    AgentExecutionFinishedEventListener,
    ConversationalComponentExecutionFinishedEventListener,
    FlowExecutionFinishedEventListener,
)


@pytest.mark.parametrize("missing_attribute", ["conversational_component", "execution_status"])
@pytest.mark.parametrize(
    "event_class",
    [
        ConversationalComponentExecutionFinishedEvent,
        FlowExecutionFinishedEvent,
        AgentExecutionFinishedEvent,
    ],
)
def test_event_creation_with_missing_arguments_fails(
    missing_attribute: str, event_class: Type[ConversationalComponentExecutionFinishedEvent]
) -> None:
    all_attributes = {
        "conversational_component": (
            create_single_step_flow(InputMessageStep(message_template="How are you?"))
            if event_class == FlowExecutionFinishedEvent
            else Agent(llm=DummyModel())
        ),
        "execution_status": UserMessageRequestStatus(
            message=Message(content=""), _conversation_id=""
        ),
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        event_class(**all_attributes)


@pytest.mark.parametrize(
    "event_info",
    [
        {
            "name": "My event test",
            "timestamp": 12,
            "event_id": "abc123",
            "conversational_component": create_single_step_flow(
                InputMessageStep(message_template="How are you?")
            ),
            "execution_status": UserMessageRequestStatus(
                message=Message(content=""), _conversation_id=""
            ),
        },
        {
            "name": "My other test",
            "conversational_component": create_single_step_flow(
                OutputMessageStep(message_template="How are you?")
            ),
            "execution_status": FinishedStatus(
                output_values={}, complete_step_name="step_1", _conversation_id=None
            ),
        },
        {
            "name": "Yet another test",
            "event_id": "123abc",
            "conversational_component": create_single_step_flow(
                InputMessageStep(message_template="How are you?")
            ),
            "execution_status": ToolRequestStatus(
                tool_requests=[
                    ToolRequest(name="a", args={"a": 1, "b": "v"}, tool_request_id="a_id")
                ],
                _conversation_id=None,
            ),
        },
        {
            "name": "Another test?",
            "conversational_component": Agent(llm=DummyModel(), tools=[GET_LOCATION_CLIENT_TOOL]),
            "execution_status": ToolRequestStatus(
                tool_requests=[
                    ToolRequest(name="a", args={"a": 1, "b": "v"}, tool_request_id="a_id")
                ],
                _conversation_id=None,
            ),
        },
        {
            "name": "Wow, another test!",
            "conversational_component": Agent(
                agent_id="123",
                llm=DummyModel(),
                initial_message="Hey!",
                agents=[
                    Agent(
                        name="subagent",
                        description="subagent desc",
                        llm=DummyModel(),
                        tools=[GET_LOCATION_CLIENT_TOOL],
                    )
                ],
                flows=[
                    DescribedFlow(
                        name="subflow",
                        description="subflow desc",
                        flow=create_single_step_flow(
                            InputMessageStep(message_template="How are you?")
                        ),
                    )
                ],
            ),
            "execution_status": UserMessageRequestStatus(
                message=Message(content=""), _conversation_id=""
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
        for attribute in ("name", "event_id", "timestamp", "execution_status")
        if attribute in event_info
    ]
    if isinstance(event_info["conversational_component"], Agent):
        event = AgentExecutionFinishedEvent(**event_info)
    elif isinstance(event_info["conversational_component"], Flow):
        event = FlowExecutionFinishedEvent(**event_info)
    else:
        raise ValueError(
            f"Unexpected conversational component type {type(event_info['conversational_component'])}"
        )
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    assert serialized_event["event_type"] == str(event.__class__.__name__)
    for attribute_name in attributes_to_check:
        if attribute_name == "execution_status":
            assert (
                getattr(event, attribute_name).__class__.__name__
                == serialized_event[attribute_name]
            )
        else:
            assert getattr(event, attribute_name) == serialized_event[attribute_name]


@pytest.mark.parametrize(
    "flow, execution_status_type",
    [
        (
            create_single_step_flow(InputMessageStep(message_template="How are you?")),
            UserMessageRequestStatus,
        ),
        (
            create_single_step_flow(OutputMessageStep(message_template="How are you?")),
            FinishedStatus,
        ),
        (
            create_single_step_flow(ToolExecutionStep(tool=GET_LOCATION_CLIENT_TOOL)),
            ToolRequestStatus,
        ),
    ],
)
def test_event_is_triggered_with_flow(
    flow: Flow, execution_status_type: Type[ExecutionStatus]
) -> None:
    agent_event_listener = AgentExecutionFinishedEventListener()
    flow_event_listener = FlowExecutionFinishedEventListener()
    event_listener = ConversationalComponentExecutionFinishedEventListener()
    with register_event_listeners([event_listener, flow_event_listener, agent_event_listener]):
        _run_flow_and_return_status(flow=flow, inputs={})
    assert len(event_listener.triggered_events) == 1
    assert isinstance(
        event_listener.triggered_events[0], ConversationalComponentExecutionFinishedEvent
    )
    assert isinstance(event_listener.triggered_events[0].execution_status, execution_status_type)
    assert isinstance(event_listener.triggered_events[-1], FlowExecutionFinishedEvent)
    assert len(flow_event_listener.triggered_events) == len(event_listener.triggered_events)
    assert len(agent_event_listener.triggered_events) == 0


@pytest.mark.parametrize(
    "agent, user_messages, execution_status_type",
    [
        (
            Agent(custom_instruction="Be polite", llm=DummyModel()),
            [],
            UserMessageRequestStatus,
        ),
        (
            DUMMY_AGENT_WITH_CONVERSATION_EXIT,
            ["I'm done, you can exit"],
            FinishedStatus,
        ),
        (
            DUMMY_AGENT_WITH_GET_LOCATION_TOOL,
            ["Please use the tool"],
            ToolRequestStatus,
        ),
    ],
)
def test_event_is_triggered_with_agent(
    agent: Agent,
    user_messages: List[str],
    execution_status_type: Type[ExecutionStatus],
) -> None:
    agent_event_listener = AgentExecutionFinishedEventListener()
    flow_event_listener = FlowExecutionFinishedEventListener()
    event_listener = ConversationalComponentExecutionFinishedEventListener()
    conversation = agent.start_conversation()
    with register_event_listeners([event_listener, agent_event_listener, flow_event_listener]):
        conversation.execute()
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            conversation.execute()
    assert len(event_listener.triggered_events) == 1 + len(user_messages)
    assert all(
        isinstance(event, ConversationalComponentExecutionFinishedEvent)
        for event in event_listener.triggered_events
    )
    assert isinstance(event_listener.triggered_events[-1].execution_status, execution_status_type)
    assert isinstance(event_listener.triggered_events[-1], AgentExecutionFinishedEvent)
    assert len(event_listener.triggered_events) == len(agent_event_listener.triggered_events)
    assert len(flow_event_listener.triggered_events) == 0


@pytest.mark.parametrize(
    "agent, user_messages",
    [
        (
            DUMMY_AGENT_WITH_GET_LOCATION_FLOW_AS_TOOL,
            ["Please use the tool"],
        ),
    ],
)
def test_event_is_triggered_with_nested_agents_flows(
    agent: Agent,
    user_messages: List[str],
) -> None:
    event_listener = ConversationalComponentExecutionFinishedEventListener()
    conversation = agent.start_conversation()
    with register_event_listeners([event_listener]):
        conversation.execute()
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            conversation.execute()

    # initial execute + one execute per user message + an execution of the flow as tool
    assert len(event_listener.triggered_events) == 1 + len(user_messages) + 1
    assert all(
        isinstance(event, ConversationalComponentExecutionFinishedEvent)
        for event in event_listener.triggered_events
    )
    assert isinstance(event_listener.triggered_events[-1], AgentExecutionFinishedEvent)


@pytest.mark.parametrize(
    "flow",
    [
        create_single_step_flow(
            step=AgentExecutionStep(
                agent=Agent(custom_instruction="Be polite", llm=DummyModel()),
            )
        ),
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
                            step=AgentExecutionStep(
                                agent=Agent(custom_instruction="Be polite", llm=DummyModel())
                            )
                        )
                    )
                )
            )
        ),
    ],
)
def test_event_is_triggered_with_nested_flows_agents(
    flow: Flow,
) -> None:
    event_listener = ConversationalComponentExecutionFinishedEventListener()
    conversation = flow.start_conversation()

    with register_event_listeners([event_listener]):
        conversation.execute()

    assert len(event_listener.triggered_events) == 1 + count_agents_and_flows_in_flow(flow)
    assert isinstance(
        event_listener.triggered_events[-1], ConversationalComponentExecutionFinishedEvent
    )
    assert isinstance(event_listener.triggered_events[-1], FlowExecutionFinishedEvent)
