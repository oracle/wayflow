# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List

import pytest

from wayflowcore.agent import Agent
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.events.event import _MASKING_TOKEN, ConversationCreatedEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.messagelist import Message, MessageList, MessageType
from wayflowcore.serialization import serialize_to_dict
from wayflowcore.steps import InputMessageStep, OutputMessageStep
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep
from wayflowcore.steps.flowexecutionstep import FlowExecutionStep
from wayflowcore.tools import DescribedFlow
from wayflowcore.tools.tools import ToolRequest

from ..testhelpers.dummy import DummyModel
from .conftest import (
    DUMMY_AGENT_WITH_GET_LOCATION_FLOW_AS_TOOL,
    GET_LOCATION_CLIENT_TOOL,
    count_agents_and_flows_in_agent,
    count_agents_and_flows_in_flow,
    create_dummy_llm_with_next_output,
)
from .event_listeners import ConversationCreatedEventListener


@pytest.mark.parametrize(
    "missing_attribute",
    [
        "conversational_component",
        "inputs",
        "messages",
        "conversation_id",
        "nesting_level",
    ],
)
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes = {
        "conversational_component": create_single_step_flow(
            InputMessageStep(message_template="How are you?")
        ),
        "inputs": {},
        "messages": MessageList([Message("How are you?")]),
        "conversation_id": "abc123",
        "nesting_level": 1,
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        ConversationCreatedEvent(**all_attributes)


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
            "inputs": {},
            "messages": MessageList([Message("How are you?")]),
            "conversation_id": "abc123",
            "nesting_level": 1,
        },
        {
            "name": "My other test",
            "conversational_component": create_single_step_flow(
                OutputMessageStep(message_template="How are you?")
            ),
            "inputs": {},
            "messages": [Message("How are you?")],
            "conversation_id": "efg456",
            "nesting_level": 1,
        },
        {
            "name": "Another test?",
            "conversational_component": Agent(llm=DummyModel(), tools=[GET_LOCATION_CLIENT_TOOL]),
            "inputs": {
                "v": 1234,
                "v1234": "value",
            },
            "messages": MessageList([]),
            "conversation_id": "efg456",
            "nesting_level": 1,
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
            "inputs": {
                "when": "will",
                "it": "end",
            },
            "messages": MessageList([]),
            "conversation_id": "hij789",
            "nesting_level": 1,
        },
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_correct_event_serialization_to_tracing_format(
    event_info: Dict[str, Any], mask_sensitive_information: bool
) -> None:
    attributes_to_check = [
        attribute
        for attribute in (
            "name",
            "event_id",
            "timestamp",
            "inputs",
            "messages",
            "conversation_id",
        )
        if attribute in event_info
    ]
    event = ConversationCreatedEvent(**event_info)
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    assert serialized_event["event_type"] == str(event.__class__.__name__)
    for attribute_name in attributes_to_check:
        attr = getattr(event, attribute_name)
        if attribute_name == "messages":
            if mask_sensitive_information:
                assert _MASKING_TOKEN == serialized_event[attribute_name]
            else:
                if isinstance(event_info[attribute_name], MessageList):
                    for i, message in enumerate(event_info[attribute_name].get_messages()):
                        assert serialize_to_dict(message) == serialized_event[attribute_name][i]
                elif isinstance(event_info[attribute_name], list):
                    for i, message in enumerate(event_info[attribute_name]):
                        assert serialize_to_dict(message) == serialized_event[attribute_name][i]
                else:
                    assert serialized_event[attribute_name] is None
        elif mask_sensitive_information and attribute_name == "inputs":
            assert _MASKING_TOKEN == serialized_event[attribute_name]
        elif isinstance(attr, dict):
            for key, value in attr.items():
                assert str(value) == serialized_event[attribute_name][key]
        else:
            assert attr == serialized_event[attribute_name]


@pytest.mark.parametrize(
    "conversational_component",
    [
        Agent(custom_instruction="Be polite", llm=DummyModel()),
        create_single_step_flow(OutputMessageStep("Hello")),
    ],
)
def test_event_is_triggered_with_direct_call_to_start_conversation(
    conversational_component: ConversationalComponent,
) -> None:
    event_listener = ConversationCreatedEventListener()

    with register_event_listeners([event_listener]):
        conversational_component.start_conversation()

    assert len(event_listener.triggered_events) == 1
    assert isinstance(event_listener.triggered_events[0], ConversationCreatedEvent)


@pytest.mark.parametrize(
    "agent, user_messages",
    [
        (
            Agent(custom_instruction="Be polite", llm=DummyModel()),
            [],
        ),
        (
            Agent(
                agent_id="123",
                llm=create_dummy_llm_with_next_output(
                    {
                        "Please use the agent": Message(
                            tool_requests=[
                                ToolRequest(
                                    name="Location agent",
                                    args={},
                                    tool_request_id="tool_request_id_1",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        ),
                        "Hi, location is X": Message(
                            content="From my expert sub agents, I've pinpointed that location is X",
                            message_type=MessageType.AGENT,
                        ),
                    }
                ),
                initial_message="Hey!",
                agents=[
                    Agent(
                        name="Location agent",
                        description="This agent knows how to pinpoint locations",
                        custom_instruction="Be polite",
                        llm=create_dummy_llm_with_next_output("Hi, location is X"),
                    )
                ],
            ),
            ["Please use the agent"],
        ),
        (
            DUMMY_AGENT_WITH_GET_LOCATION_FLOW_AS_TOOL,
            ["Please use the tool"],
        ),
    ],
)
def test_event_is_triggered_with_agent_subagents_subflows(
    agent: Agent,
    user_messages: List[str],
) -> None:
    event_listener = ConversationCreatedEventListener()
    additional_conversations = count_agents_and_flows_in_agent(agent)

    with register_event_listeners([event_listener]):
        conversation = agent.start_conversation()
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            conversation.execute()

    assert len(event_listener.triggered_events) == 1 + additional_conversations
    assert isinstance(event_listener.triggered_events[0], ConversationCreatedEvent)


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
            step=AgentExecutionStep(
                agent=Agent(custom_instruction="Be polite", llm=DummyModel()),
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
def test_event_is_triggered_with_flow_subagents_subflows(
    flow: Flow,
) -> None:
    event_listener = ConversationCreatedEventListener()
    additional_conversations = count_agents_and_flows_in_flow(flow)

    with register_event_listeners([event_listener]):
        conversation = flow.start_conversation()
        conversation.execute()

    assert len(event_listener.triggered_events) == 1 + additional_conversations
    assert isinstance(event_listener.triggered_events[0], ConversationCreatedEvent)
