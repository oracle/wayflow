# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import Any, Dict, List

import pytest

from wayflowcore.agent import Agent
from wayflowcore.events.event import _PII_TEXT_MASK, ToolExecutionStartEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors.executionstatus import UserMessageRequestStatus
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
    DUMMY_AGENT_WITH_GET_LOCATION_TOOL,
    GET_LOCATION_CLIENT_TOOL,
    create_dummy_llm_with_next_output,
)
from .event_listeners import ToolExecutionStartEventListener


@pytest.mark.parametrize("missing_attribute", ["tool", "tool_request"])
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes = {
        "tool": GET_LOCATION_CLIENT_TOOL,
        "tool_request": ToolRequest(
            name=GET_LOCATION_CLIENT_TOOL.name,
            tool_request_id="abc123",
            args={},
        ),
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        ToolExecutionStartEvent(**all_attributes)


@pytest.mark.parametrize(
    "event_info",
    [
        {
            "name": "My event test",
            "event_id": "abc123",
            "timestamp": 12,
            "tool_request": ToolRequest(
                name=GET_LOCATION_CLIENT_TOOL.name,
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
    event = ToolExecutionStartEvent(tool=GET_LOCATION_CLIENT_TOOL, **event_info)
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


def test_event_is_triggered_on_tool_call_with_tool_execution_step():
    event_listener = ToolExecutionStartEventListener()
    with register_event_listeners([event_listener]):
        run_single_step(step=ToolExecutionStep(tool=GET_LOCATION_CLIENT_TOOL))
    assert len(event_listener.triggered_events) == 1
    assert isinstance(event_listener.triggered_events[0], ToolExecutionStartEvent)


@pytest.mark.parametrize(
    "agent, user_messages",
    [
        (
            Agent(custom_instruction="Be polite", llm=DummyModel()),
            [],
        ),
        (
            DUMMY_AGENT_WITH_GET_LOCATION_TOOL,
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
                                    name=GET_LOCATION_CLIENT_TOOL.name,
                                    args={"company_name": "Oracle Labs"},
                                    tool_request_id="tool_request_id_1",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        )
                    },
                ),
                flows=[
                    DescribedFlow(
                        flow=create_single_step_flow(
                            step=ToolExecutionStep(tool=GET_LOCATION_CLIENT_TOOL)
                        ),
                        name=GET_LOCATION_CLIENT_TOOL.name,
                        description=GET_LOCATION_CLIENT_TOOL.description,
                    )
                ],
            ),
            ["Please use the tool"],
        ),
    ],
)
def test_event_is_triggered_with_agent(
    agent: Agent,
    user_messages: List[str],
) -> None:
    event_listener = ToolExecutionStartEventListener()
    conversation = agent.start_conversation()

    with register_event_listeners([event_listener]):
        conversation.execute()
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            conversation.execute()
    assert len(event_listener.triggered_events) == len(user_messages)
    if len(user_messages) > 0:
        assert isinstance(event_listener.triggered_events[-1], ToolExecutionStartEvent)


def test_event_is_triggered_on_tool_call_with_flow():
    event_listener = ToolExecutionStartEventListener()
    flow = create_single_step_flow(
        step=ToolExecutionStep(tool=GET_LOCATION_CLIENT_TOOL),
    )
    with register_event_listeners([event_listener]):
        _run_flow_and_return_status(flow)
    assert len(event_listener.triggered_events) == 1
    assert isinstance(event_listener.triggered_events[0], ToolExecutionStartEvent)


@pytest.mark.parametrize("with_tools", [False, True], ids=["without_tools", "with_tools"])
def test_event_is_not_triggered_on_talk_to_user_tool_calls(agent_with_useless_tool):
    event_listener = ToolExecutionStartEventListener()
    with register_event_listeners([event_listener]):
        conversation_with_interrupts = agent_with_useless_tool.start_conversation()
        conversation_with_interrupts.append_user_message("What model are you?")
        execution_status = conversation_with_interrupts.execute()

    assert len(event_listener.triggered_events) == 0
    assert isinstance(execution_status, UserMessageRequestStatus)
