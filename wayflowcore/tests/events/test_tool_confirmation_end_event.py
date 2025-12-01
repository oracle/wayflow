# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List

import pytest

from wayflowcore.agent import Agent
from wayflowcore.events.event import _PII_TEXT_MASK, ToolConfirmationRequestEndEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors.executionstatus import ToolExecutionConfirmationStatus
from wayflowcore.flowhelpers import (
    _run_flow_and_return_status,
    create_single_step_flow,
    run_single_step,
)
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.steps.toolexecutionstep import ToolExecutionStep
from wayflowcore.tools import DescribedFlow
from wayflowcore.tools.tools import ToolRequest

from ..testhelpers.dummy import DummyModel
from .conftest import (
    GET_LOCATION_CLIENT_TOOL_WITH_CONFIRMATION,
    GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION,
    create_dummy_llm_with_next_output,
)
from .event_listeners import ToolConfirmationRequestEndEventListener


@pytest.mark.parametrize("missing_attribute", ["tool", "tool_request"])
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes = {
        "tool": GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION,
        "tool_request": ToolRequest(
            name=GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION.name,
            tool_request_id="abc123",
            args={},
        ),
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        ToolConfirmationRequestEndEvent(**all_attributes)


@pytest.mark.parametrize(
    "event_info",
    [
        {
            "name": "My event test",
            "event_id": "abc123",
            "timestamp": 12,
            "tool_request": ToolRequest(
                name=GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION.name,
                tool_request_id="abc123",
                args={},
            ),
        },
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_correct_event_serialization_to_tracing_format(
    event_info: Dict[str, Any], mask_sensitive_information: bool
) -> None:
    event = ToolConfirmationRequestEndEvent(
        tool=GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION, **event_info
    )
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    assert serialized_event["event_type"] == str(event.__class__.__name__)
    for attribute_name in event_info.keys():
        if attribute_name == "tool_request":
            assert event.tool_request.tool_request_id == serialized_event["tool_request.id"]
            if mask_sensitive_information:
                assert _PII_TEXT_MASK == serialized_event["tool_request.inputs"]
            else:
                assert event.tool_request.args == serialized_event["tool_request.inputs"]
        else:
            assert getattr(event, attribute_name) == serialized_event[attribute_name]


@pytest.mark.parametrize(
    "location_tool",
    [GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION, GET_LOCATION_CLIENT_TOOL_WITH_CONFIRMATION],
)
def test_event_is_not_triggered_after_server_tool_call_with_tool_execution_step(location_tool):
    event_listener = ToolConfirmationRequestEndEventListener()
    with register_event_listeners([event_listener]):
        run_single_step(step=ToolExecutionStep(tool=location_tool))

    # The step yields if it's a client tool
    assert len(event_listener.triggered_events) == 0


@pytest.mark.parametrize(
    "agent, user_messages",
    [
        (
            Agent(custom_instruction="Be polite", llm=DummyModel()),
            [],
        ),
        (
            Agent(
                agent_id="a123",
                custom_instruction="Be polite",
                llm=create_dummy_llm_with_next_output(
                    {
                        "Please use the tool": Message(
                            tool_requests=[
                                ToolRequest(
                                    name=GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION.name,
                                    args={"company_name": "Oracle Labs"},
                                    tool_request_id="tool_request_id_1",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        ),
                        "Oracle Labs": Message(
                            content="You are in Oracle Labs", message_type=MessageType.AGENT
                        ),
                    },
                ),
                tools=[GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION],
            ),
            ["Please use the tool"],
        ),
        (
            Agent(
                agent_id="a123",
                custom_instruction="Be polite",
                llm=create_dummy_llm_with_next_output(
                    {
                        "Please use the tool": Message(
                            tool_requests=[
                                ToolRequest(
                                    name=GET_LOCATION_CLIENT_TOOL_WITH_CONFIRMATION.name,
                                    args={"company_name": "Oracle Labs"},
                                    tool_request_id="tool_request_id_1",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        ),
                        "Oracle Labs": Message(
                            content="You are in Oracle Labs", message_type=MessageType.AGENT
                        ),
                    },
                ),
                tools=[GET_LOCATION_CLIENT_TOOL_WITH_CONFIRMATION],
            ),
            ["Please use the tool"],
        ),
    ],
)
def test_event_is_triggered_with_agent(
    agent: Agent,
    user_messages: List[str],
) -> None:
    event_listener = ToolConfirmationRequestEndEventListener()
    conversation = agent.start_conversation()

    with register_event_listeners([event_listener]):
        conversation.execute()
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            execution_status = conversation.execute()
            if isinstance(execution_status, ToolExecutionConfirmationStatus):
                execution_status.confirm_tool_execution(
                    tool_request=execution_status.tool_requests[-1]
                )
                execution_status = conversation.execute()

    assert len(event_listener.triggered_events) == len(user_messages)
    if len(user_messages) > 0:
        assert isinstance(event_listener.triggered_events[-1], ToolConfirmationRequestEndEvent)


@pytest.mark.parametrize(
    "agent, user_messages",
    [
        (
            Agent(
                agent_id="a123",
                custom_instruction="Be polite",
                llm=create_dummy_llm_with_next_output(
                    {
                        "Please use the tool": Message(
                            tool_requests=[
                                ToolRequest(
                                    name=GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION.name,
                                    args={"company_name": "Oracle Labs"},
                                    tool_request_id="tool_request_id_1",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        ),
                        "Oracle Labs": Message(
                            content="You are in Oracle Labs", message_type=MessageType.AGENT
                        ),
                    },
                ),
                flows=[
                    DescribedFlow(
                        flow=create_single_step_flow(
                            step=ToolExecutionStep(tool=GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION),
                        ),
                        name=GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION.name,
                        description=GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION.description,
                    )
                ],
            ),
            ["Please use the tool"],
        ),
        (
            Agent(
                agent_id="a123",
                custom_instruction="Be polite",
                llm=create_dummy_llm_with_next_output(
                    {
                        "Please use the tool": Message(
                            tool_requests=[
                                ToolRequest(
                                    name=GET_LOCATION_CLIENT_TOOL_WITH_CONFIRMATION.name,
                                    args={"company_name": "Oracle Labs"},
                                    tool_request_id="tool_request_id_1",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        ),
                        "Oracle Labs": Message(
                            content="You are in Oracle Labs", message_type=MessageType.AGENT
                        ),
                    },
                ),
                flows=[
                    DescribedFlow(
                        flow=create_single_step_flow(
                            step=ToolExecutionStep(tool=GET_LOCATION_CLIENT_TOOL_WITH_CONFIRMATION),
                        ),
                        name=GET_LOCATION_CLIENT_TOOL_WITH_CONFIRMATION.name,
                        description=GET_LOCATION_CLIENT_TOOL_WITH_CONFIRMATION.description,
                    )
                ],
            ),
            ["Please use the tool"],
        ),
    ],
)
def test_event_is_triggered_with_agent_and_flow(
    agent: Agent,
    user_messages: List[str],
) -> None:
    event_listener = ToolConfirmationRequestEndEventListener()
    conversation = agent.start_conversation()

    with register_event_listeners([event_listener]):
        tool_request_id = None
        conversation.execute()
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            execution_status = conversation.execute()
            if isinstance(execution_status, ToolExecutionConfirmationStatus):
                tool_request_id = execution_status.tool_requests[-1].tool_request_id
                execution_status.confirm_tool_execution(
                    tool_request=execution_status.tool_requests[-1]
                )
                execution_status = conversation.execute()

        assert tool_request_id is not None
    assert len(event_listener.triggered_events) == len(user_messages)
    if len(user_messages) > 0:
        assert isinstance(event_listener.triggered_events[-1], ToolConfirmationRequestEndEvent)


@pytest.mark.parametrize(
    "location_tool",
    [GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION, GET_LOCATION_CLIENT_TOOL_WITH_CONFIRMATION],
)
def test_event_is_triggered_after_confirming_tool_call_with_flow(location_tool):
    event_listener_1 = ToolConfirmationRequestEndEventListener()
    event_listener_2 = ToolConfirmationRequestEndEventListener()
    flow = create_single_step_flow(
        step=ToolExecutionStep(tool=location_tool, raise_exceptions=False),
    )
    with register_event_listeners([event_listener_1]):
        conv = flow.start_conversation({}, messages=None)
        status = conv.execute()
        status.reject_tool_execution(tool_request=status.tool_requests[0])
        status = conv.execute()

    with register_event_listeners([event_listener_2]):
        conv = flow.start_conversation({}, messages=None)
        status = conv.execute()
        status.confirm_tool_execution(tool_request=status.tool_requests[0])
        status = conv.execute()

    # The end event is captured after confirming tool confirmation and executing
    assert len(event_listener_1.triggered_events) == 1
    assert isinstance(event_listener_1.triggered_events[-1], ToolConfirmationRequestEndEvent)
    assert len(event_listener_2.triggered_events) == 1
    assert isinstance(event_listener_2.triggered_events[-1], ToolConfirmationRequestEndEvent)


@pytest.mark.parametrize(
    "location_tool",
    [GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION, GET_LOCATION_CLIENT_TOOL_WITH_CONFIRMATION],
)
def test_event_is_not_triggered_after_first_server_tool_call_with_flow(location_tool):
    event_listener = ToolConfirmationRequestEndEventListener()
    flow = create_single_step_flow(
        step=ToolExecutionStep(tool=location_tool),
    )
    with register_event_listeners([event_listener]):
        status = _run_flow_and_return_status(flow)

    # The step yields if it's a server tool with confirmation
    assert len(event_listener.triggered_events) == 0
