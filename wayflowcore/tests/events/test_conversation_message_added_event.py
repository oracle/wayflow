# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict, List

import pytest

from wayflowcore import Message, MessageType
from wayflowcore.agent import Agent
from wayflowcore.events.event import _MASKING_TOKEN, ConversationMessageAddedEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors._agentexecutor import EXIT_CONVERSATION_TOOL_NAME
from wayflowcore.executors.executionstatus import UserMessageRequestStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import _run_flow_and_return_status, create_single_step_flow
from wayflowcore.steps import InputMessageStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep
from wayflowcore.steps.flowexecutionstep import FlowExecutionStep
from wayflowcore.tools import ToolRequest

from ..testhelpers.dummy import DummyModel
from .conftest import (
    DUMMY_AGENT_WITH_CONVERSATION_EXIT,
    DUMMY_AGENT_WITH_GET_LOCATION_FLOW_AS_TOOL,
    DUMMY_AGENT_WITH_GET_LOCATION_TOOL,
    GET_LOCATION_CLIENT_TOOL,
    create_dummy_llm_with_next_output,
)
from .event_listeners import ConversationMessageAddedEventListener


@pytest.mark.parametrize("missing_attribute", ["message", "streamed"])
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes: Dict[str, Any] = {"message": Message(), "streamed": True}
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        ConversationMessageAddedEvent(**all_attributes)


@pytest.mark.parametrize(
    "event_info",
    [
        {
            "name": "My event test",
            "timestamp": 12,
            "event_id": "abc123",
            "message": Message(
                message_type=MessageType.AGENT,
            ),
            "streamed": True,
        },
        {
            "name": "My other test",
            "message": Message(
                message_type=MessageType.USER,
            ),
            "streamed": False,
        },
        {
            "name": "Yet another test",
            "event_id": "123abc",
            "message": Message(
                message_type=MessageType.TOOL_REQUEST,
                tool_requests=[ToolRequest("get_weather", {}, "abc123")],
            ),
            "streamed": True,
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
    event = ConversationMessageAddedEvent(**event_info)
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    assert serialized_event["event_type"] == str(event.__class__.__name__)
    for attribute_name in attributes_to_check:
        if mask_sensitive_information and attribute_name == "message":
            assert _MASKING_TOKEN == serialized_event[attribute_name]
        else:
            assert getattr(event, attribute_name) == serialized_event[attribute_name]


@pytest.mark.parametrize(
    "flow, message_type",
    [
        (
            create_single_step_flow(InputMessageStep(message_template="How are you?")),
            MessageType.AGENT,
        ),
        (
            create_single_step_flow(OutputMessageStep(message_template="How are you?")),
            MessageType.AGENT,
        ),
        (
            create_single_step_flow(ToolExecutionStep(tool=GET_LOCATION_CLIENT_TOOL)),
            MessageType.TOOL_REQUEST,
        ),
    ],
)
def test_event_is_triggered_with_flow(flow: Flow, message_type: MessageType) -> None:
    event_listener = ConversationMessageAddedEventListener()
    with register_event_listeners([event_listener]):
        _run_flow_and_return_status(flow=flow, inputs={})
    assert len(event_listener.triggered_events) == 1
    assert isinstance(event_listener.triggered_events[0], ConversationMessageAddedEvent)
    assert event_listener.triggered_events[0].message.message_type is message_type


@pytest.mark.parametrize(
    "agent, user_messages, message_type",
    [
        (
            Agent(custom_instruction="Be polite", llm=DummyModel()),
            [],
            MessageType.AGENT,
        ),
        (
            DUMMY_AGENT_WITH_CONVERSATION_EXIT,
            ["I'm done, you can exit"],
            MessageType.TOOL_RESULT,
        ),
        (
            DUMMY_AGENT_WITH_GET_LOCATION_TOOL,
            ["Please use the tool"],
            MessageType.TOOL_REQUEST,
        ),
    ],
)
def test_event_is_triggered_with_agent(
    agent: Agent,
    user_messages: List[str],
    message_type: MessageType,
) -> None:
    event_listener = ConversationMessageAddedEventListener()
    conversation = agent.start_conversation()
    with register_event_listeners([event_listener]):
        agent.execute(conversation)
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            agent.execute(conversation)
    end_tool_verification_messages = 0
    for event in event_listener.triggered_events:
        message = event.message
        if message.tool_requests is not None and any(
            tool_request.name == EXIT_CONVERSATION_TOOL_NAME
            for tool_request in message.tool_requests
        ):
            end_tool_verification_messages = 2
    assert (
        len(event_listener.triggered_events)
        == 1
        + len(user_messages)
        + len(getattr(agent.llm, "output", []) or [])
        + end_tool_verification_messages
    )
    assert all(
        isinstance(event, ConversationMessageAddedEvent)
        for event in event_listener.triggered_events
    )
    assert event_listener.triggered_events[-1].message.message_type is message_type


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
                agent=Agent(
                    custom_instruction="You are a helpful assistant",
                    llm=create_dummy_llm_with_next_output("Hi, location is X"),
                ),
            )
        ),
        create_single_step_flow(
            step=FlowExecutionStep(
                flow=create_single_step_flow(
                    step=FlowExecutionStep(
                        flow=create_single_step_flow(
                            step=AgentExecutionStep(
                                agent=Agent(
                                    custom_instruction="Be polite",
                                    llm=create_dummy_llm_with_next_output("Hi, location is X"),
                                ),
                            )
                        )
                    )
                )
            )
        ),
    ],
)
def test_event_is_triggered_with_agents_in_flows(flow: Flow) -> None:
    event_listener = ConversationMessageAddedEventListener()
    additional_messages = 0

    with register_event_listeners([event_listener]):
        conversation = flow.start_conversation()
        status = flow.execute(conversation)
        if isinstance(status, UserMessageRequestStatus):
            conversation.append_user_message("Hello, what is location for company?")
            additional_messages += 1

            status = flow.execute(conversation)
            additional_messages += 1

    assert len(event_listener.triggered_events) == 1 + additional_messages
    assert all(
        isinstance(event, ConversationMessageAddedEvent)
        for event in event_listener.triggered_events
    )


@pytest.mark.parametrize(
    "agent, user_messages, message_type",
    [
        (
            DUMMY_AGENT_WITH_GET_LOCATION_FLOW_AS_TOOL,
            ["Please use the tool"],
            MessageType.AGENT,
        ),
    ],
)
def test_event_is_triggered_with_flows_in_agents(
    agent: Agent,
    user_messages: List[str],
    message_type: MessageType,
) -> None:
    event_listener = ConversationMessageAddedEventListener()
    conversation = agent.start_conversation()

    with register_event_listeners([event_listener]):
        agent.execute(conversation)
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            agent.execute(conversation)

    assert (
        len(
            [
                event
                for event in event_listener.triggered_events
                if event.message.message_type is not MessageType.INTERNAL
            ]
        )
        == 1 + len(user_messages) + len(getattr(agent.llm, "output", []) or []) + 2
    )
    assert all(
        isinstance(event, ConversationMessageAddedEvent)
        for event in event_listener.triggered_events
    )
    assert event_listener.triggered_events[-1].message.message_type == message_type
