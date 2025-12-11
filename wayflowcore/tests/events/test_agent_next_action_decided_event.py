# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List

import pytest

from wayflowcore.agent import Agent
from wayflowcore.events.event import (
    _PII_TEXT_MASK,
    AgentDecidedNextActionEvent,
    _serialize_tool_request,
)
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors._agentexecutor import AgentConversationExecutionState
from wayflowcore.planning import ExecutionPlan, Task
from wayflowcore.tools.tools import ToolRequest

from .conftest import (
    DUMMY_AGENT_WITH_CONVERSATION_EXIT,
    DUMMY_AGENT_WITH_GET_LOCATION_FLOW_AS_TOOL,
    DUMMY_AGENT_WITH_GET_LOCATION_TOOL,
)
from .event_listeners import AgentDecidedNextActionEventListener


@pytest.mark.parametrize("missing_attribute", ["execution_state", "should_yield"])
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes: Dict[str, Any] = {
        "execution_state": AgentConversationExecutionState(),
        "should_yield": True,
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        AgentDecidedNextActionEvent(**all_attributes)


@pytest.mark.parametrize(
    "execution_state",
    [
        AgentConversationExecutionState(
            memory={},
            plan=ExecutionPlan(
                [
                    Task("1", "Think about what to do"),
                    Task("2", "Prepare things to do"),
                    Task("3", "Do the things"),
                ],
            ),
            tool_call_queue=[],
            has_confirmed_conversation_exit=False,
        ),
        AgentConversationExecutionState(
            memory={},
            plan=ExecutionPlan(
                [
                    Task("first", "Write a design page"),
                    Task("second", "Approve the design page"),
                    Task("third", "Implement the feature"),
                    Task("fourth", "Write a pull request"),
                    Task("fifth", "Review the pull request"),
                    Task("sixth-a", "Merge the pull request"),
                    Task("sixth-b", "Reject the pull request"),
                    Task("seventh", "Delete the branch"),
                ],
            ),
            tool_call_queue=[
                ToolRequest(
                    name="create_pr",
                    args={
                        "title": "Implement x",
                        "description": "Implements X based on DP",
                        "branch_name": "12345-implement-x-for-y-feature",
                    },
                    tool_request_id="abc123",
                )
            ],
            has_confirmed_conversation_exit=True,
            curr_iter=6,
        ),
        AgentConversationExecutionState(
            memory={},
            plan=ExecutionPlan(
                [
                    Task("eis", "Write a ui design"),
                    Task("zwei", "Use component library"),
                    Task("drei", "Implement the graphical user interface"),
                ],
            ),
            tool_call_queue=[
                ToolRequest(
                    name="install_component_library",
                    args={
                        "name": "Bob",
                        "version": "0.1.432",
                    },
                    tool_request_id="abc123",
                )
            ],
            has_confirmed_conversation_exit=False,
            curr_iter=8,
        ),
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
@pytest.mark.parametrize("should_yield", [True, False])
def test_correct_event_serialization_to_tracing_format(
    execution_state: AgentConversationExecutionState,
    should_yield: bool,
    mask_sensitive_information: bool,
) -> None:
    event_info = {
        "name": "My event test",
        "timestamp": 12,
        "event_id": "abc123",
    }
    attributes_to_check = [
        attribute
        for attribute in (
            "name",
            "event_id",
            "timestamp",
            "memory",
            "plan",
            "tool_call_queue",
            "current_tool_request",
            "current_flow_conversation",
            "has_confirmed_conversation_exit",
            "current_retrieved_tools",
            "curr_iter",
            "should_yield",
        )
        if attribute in event_info
        or hasattr(execution_state, attribute)
        or attribute == "should_yield"
    ]
    event = AgentDecidedNextActionEvent(
        **event_info, execution_state=execution_state, should_yield=should_yield
    )
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    assert serialized_event["event_type"] == str(event.__class__.__name__)
    for attribute_name in attributes_to_check:
        try:
            assert getattr(event, attribute_name) == serialized_event[attribute_name]
        except AttributeError:
            if attribute_name == "plan":
                if mask_sensitive_information:
                    assert _PII_TEXT_MASK == serialized_event[f"execution_state.{attribute_name}"]
                else:
                    assert (
                        str(getattr(event.execution_state, attribute_name))
                        == serialized_event[f"execution_state.{attribute_name}"]
                    )
            elif attribute_name == "tool_call_queue":
                assert [
                    _serialize_tool_request(tool_request, mask_sensitive_information)
                    for tool_request in event.execution_state.tool_call_queue
                ] == serialized_event[f"execution_state.{attribute_name}"]
            elif attribute_name == "current_tool_request":
                assert (
                    _serialize_tool_request(
                        event.execution_state.current_tool_request, mask_sensitive_information
                    )
                    == serialized_event[f"execution_state.{attribute_name}"]
                )
            elif "tools" in attribute_name:
                tool_names = [
                    tool.name for tool in getattr(event.execution_state, attribute_name) or []
                ]
                assert tool_names == serialized_event[f"execution_state.{attribute_name}"]
            elif attribute_name == "should_yield":
                assert should_yield == serialized_event["should_yield"]
            else:
                if mask_sensitive_information and attribute_name in {
                    "memory",
                    "current_flow_conversation",
                }:
                    assert _PII_TEXT_MASK == serialized_event[f"execution_state.{attribute_name}"]
                else:
                    assert (
                        getattr(event.execution_state, attribute_name)
                        == serialized_event[f"execution_state.{attribute_name}"]
                    )


def test_event_is_triggered_with_agent_execute_exit_conversation() -> None:
    agent = DUMMY_AGENT_WITH_CONVERSATION_EXIT
    user_messages = ["I'm done, you can exit"]
    event_listener = AgentDecidedNextActionEventListener()
    conversation = agent.start_conversation()
    with register_event_listeners([event_listener]):
        conversation.execute()
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            conversation.execute()

    assert len(event_listener.triggered_events) == 3
    assert all(
        isinstance(event, AgentDecidedNextActionEvent) for event in event_listener.triggered_events
    )


def test_event_is_triggered_with_agent_execute_client_tool_call() -> None:
    agent = DUMMY_AGENT_WITH_GET_LOCATION_TOOL
    user_messages = ["Please use the tool"]
    event_listener = AgentDecidedNextActionEventListener()
    conversation = agent.start_conversation()
    with register_event_listeners([event_listener]):
        conversation.execute()
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            conversation.execute()

    assert len(event_listener.triggered_events) == 2
    assert all(
        isinstance(event, AgentDecidedNextActionEvent) for event in event_listener.triggered_events
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
def test_event_is_triggered_with_agent_execute_client_tool_call_with_flow(
    agent: Agent,
    user_messages: List[str],
) -> None:
    event_listener = AgentDecidedNextActionEventListener()
    conversation = agent.start_conversation()
    with register_event_listeners([event_listener]):
        conversation.execute()
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            conversation.execute()

    assert len(event_listener.triggered_events) == 3
    assert all(
        isinstance(event, AgentDecidedNextActionEvent) for event in event_listener.triggered_events
    )
