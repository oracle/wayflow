# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import Any, Dict, List

import pytest

from wayflowcore.agent import Agent
from wayflowcore.events.event import _MASKING_TOKEN, ToolExecutionResultEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors.executionstatus import ToolRequestStatus
from wayflowcore.flowhelpers import (
    _run_flow_and_return_status,
    create_single_step_flow,
    run_single_step,
)
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.steps.toolexecutionstep import ToolExecutionStep
from wayflowcore.tools import DescribedFlow
from wayflowcore.tools.tools import ToolRequest, ToolResult

from ..testhelpers.dummy import DummyModel
from .conftest import GET_LOCATION_CLIENT_TOOL, create_dummy_llm_with_next_output
from .event_listeners import ToolExecutionResultEventListener

TEST_STEP = ToolExecutionStep(tool=GET_LOCATION_CLIENT_TOOL)


@pytest.mark.parametrize("missing_attribute", ["tool", "tool_result"])
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes = {
        "tool": GET_LOCATION_CLIENT_TOOL,
        "tool_result": ToolResult(
            content="example tool call output",
            tool_request_id="abc123",
        ),
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        ToolExecutionResultEvent(**all_attributes)


@pytest.mark.parametrize(
    "event_info",
    [
        {
            "name": "My event test",
            "event_id": "abc123",
            "timestamp": 12,
            "tool_result": ToolResult(
                content="example tool call output",
                tool_request_id="abc123",
            ),
        },
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_correct_event_serialization_to_tracing_format(
    event_info: Dict[str, Any], mask_sensitive_information: bool
) -> None:
    event = ToolExecutionResultEvent(tool=GET_LOCATION_CLIENT_TOOL, **event_info)
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    assert serialized_event["event_type"] == str(event.__class__.__name__)
    for attribute_name in event_info.keys():
        if attribute_name == "tool_result":
            assert (
                event.tool_result.tool_request_id == serialized_event["tool_result.tool_request_id"]
            )
            if mask_sensitive_information:
                assert _MASKING_TOKEN == serialized_event["tool_result.output"]
            else:
                assert event.tool_result.content == serialized_event["tool_result.output"]
        else:
            assert getattr(event, attribute_name) == serialized_event[attribute_name]


def test_event_is_not_triggered_after_client_tool_call_with_tool_execution_step():
    event_listener = ToolExecutionResultEventListener()
    with register_event_listeners([event_listener]):
        run_single_step(step=ToolExecutionStep(tool=GET_LOCATION_CLIENT_TOOL))

    # The step yields if it's a client tool
    assert len(event_listener.triggered_events) == 0


@pytest.mark.parametrize(
    "agent, user_messages, client_tool_results",
    [
        (
            Agent(custom_instruction="Be polite", llm=DummyModel()),
            [],
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
                                    name=GET_LOCATION_CLIENT_TOOL.name,
                                    args={"company_name": "Oracle Labs"},
                                    tool_request_id="tool_request_id_1",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        ),
                        "Shore X": Message(
                            content="You are in Shore x", message_type=MessageType.AGENT
                        ),
                    },
                ),
                tools=[GET_LOCATION_CLIENT_TOOL],
            ),
            ["Please use the tool"],
            [ToolResult(content="Shore X", tool_request_id="tool_request_id_1")],
        ),
    ],
)
def test_event_is_triggered_with_agent(
    agent: Agent,
    user_messages: List[str],
    client_tool_results: List[ToolResult],
) -> None:
    event_listener = ToolExecutionResultEventListener()
    conversation = agent.start_conversation()

    with register_event_listeners([event_listener]):
        conversation.execute()
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            conversation.execute()
        for result in client_tool_results:
            conversation.append_tool_result(result)
            conversation.execute()
    assert len(event_listener.triggered_events) == len(user_messages)
    if len(user_messages) > 0:
        assert isinstance(event_listener.triggered_events[-1], ToolExecutionResultEvent)


@pytest.mark.parametrize(
    "agent, user_messages, tool_result",
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
                                    name=GET_LOCATION_CLIENT_TOOL.name,
                                    args={"company_name": "Oracle Labs"},
                                    tool_request_id="tool_request_id_1",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        ),
                        "Shore X": Message(
                            content="You are in Shore x", message_type=MessageType.AGENT
                        ),
                    },
                ),
                flows=[
                    DescribedFlow(
                        flow=create_single_step_flow(
                            step=TEST_STEP,
                        ),
                        name=GET_LOCATION_CLIENT_TOOL.name,
                        description=GET_LOCATION_CLIENT_TOOL.description,
                    )
                ],
            ),
            ["Please use the tool"],
            ToolResult(content="Shore X", tool_request_id="tool_request_id_1"),
        ),
    ],
)
def test_event_is_triggered_with_agent_and_flow(
    agent: Agent,
    user_messages: List[str],
    tool_result: ToolResult,
) -> None:
    event_listener = ToolExecutionResultEventListener()
    conversation = agent.start_conversation()

    with register_event_listeners([event_listener]):
        tool_request_id = None
        conversation.execute()
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            execution_status = conversation.execute()
            if isinstance(execution_status, ToolRequestStatus):
                tool_request_id = execution_status.tool_requests[-1].tool_request_id
        assert tool_request_id is not None
        conversation.append_tool_result(
            ToolResult(content=tool_result.content, tool_request_id=tool_request_id)
        )
        conversation.execute()
    assert len(event_listener.triggered_events) == len(user_messages)
    if len(user_messages) > 0:
        assert isinstance(event_listener.triggered_events[-1], ToolExecutionResultEvent)


def test_event_is_not_triggered_after_first_client_tool_call_with_flow():
    event_listener = ToolExecutionResultEventListener()
    flow = create_single_step_flow(
        step=ToolExecutionStep(tool=GET_LOCATION_CLIENT_TOOL),
    )
    with register_event_listeners([event_listener]):
        _run_flow_and_return_status(flow)

    # The step yields if it's a client tool
    assert len(event_listener.triggered_events) == 0
