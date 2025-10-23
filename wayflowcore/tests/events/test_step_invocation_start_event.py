# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import Any, Dict, List

import pytest

from wayflowcore.agent import Agent
from wayflowcore.events.event import _MASKING_TOKEN, StepInvocationStartEvent
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

from .conftest import GET_LOCATION_CLIENT_TOOL, create_dummy_llm_with_next_output
from .event_listeners import StepInvocationStartEventListener

TEST_GET_LOCATION_STEP = ToolExecutionStep(tool=GET_LOCATION_CLIENT_TOOL)


@pytest.mark.parametrize("missing_attribute", ["step", "inputs"])
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes = {
        "step": TEST_GET_LOCATION_STEP,
        "inputs": {},
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        StepInvocationStartEvent(**all_attributes)


@pytest.mark.parametrize(
    "event_info",
    [
        {
            "name": "My event test",
            "event_id": "abc123",
            "timestamp": 12,
            "inputs": {"a": 12},
        },
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_correct_event_serialization_to_tracing_format(
    event_info: Dict[str, Any], mask_sensitive_information: bool
) -> None:
    event = StepInvocationStartEvent(step=TEST_GET_LOCATION_STEP, **event_info)
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    assert serialized_event["event_type"] == str(event.__class__.__name__)
    for attribute_name, _ in event_info.items():
        if attribute_name == "inputs":
            if mask_sensitive_information:
                assert _MASKING_TOKEN == serialized_event[attribute_name]
            else:
                for key, value in event.inputs.items():
                    assert str(value) == serialized_event[attribute_name][key]
        else:
            assert getattr(event, attribute_name) == serialized_event[attribute_name]


def test_event_is_triggered_step_invocation_with_tool_execution_step():
    event_listener = StepInvocationStartEventListener()
    with register_event_listeners([event_listener]):
        run_single_step(step=TEST_GET_LOCATION_STEP)

    # The first event is the StartStep event
    assert len(event_listener.triggered_events) == 2
    assert isinstance(event_listener.triggered_events[1], StepInvocationStartEvent)


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
                            content="The company is in Shore X",
                            message_type=MessageType.AGENT,
                        ),
                    },
                ),
                flows=[
                    DescribedFlow(
                        flow=create_single_step_flow(
                            step=TEST_GET_LOCATION_STEP,
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
def test_event_is_triggered_step_invocation_with_agent_and_flow(
    agent: Agent,
    user_messages: List[str],
    tool_result: ToolResult,
):
    event_listener = StepInvocationStartEventListener()
    conversation = agent.start_conversation()
    tool_request_id = None

    with register_event_listeners([event_listener]):
        conversation.execute()
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            execution_status = conversation.execute()
            if isinstance(execution_status, ToolRequestStatus):
                assert len(execution_status.tool_requests) == 1
                tool_request_id = execution_status.tool_requests[-1].tool_request_id
        assert tool_request_id is not None
        conversation.append_tool_result(
            ToolResult(tool_request_id=tool_request_id, content=tool_result.content)
        )
        conversation.execute()

    # StartStep + ToolExecutionStep(Yielding call) + ToolExecutionStep(call after ToolResult)
    assert len(event_listener.triggered_events) == 3
    for event in event_listener.triggered_events:
        assert isinstance(event, StepInvocationStartEvent)


def test_event_is_triggered_step_invocation_with_flow():
    event_listener = StepInvocationStartEventListener()
    flow = create_single_step_flow(
        step=TEST_GET_LOCATION_STEP,
    )
    with register_event_listeners([event_listener]):
        _run_flow_and_return_status(flow)

    # The first event is the StartStep event
    assert len(event_listener.triggered_events) == 2
    assert isinstance(event_listener.triggered_events[1], StepInvocationStartEvent)
