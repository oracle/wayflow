# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from decimal import DivisionByZero
from typing import Any, Dict, List

import pytest

from wayflowcore.agent import Agent
from wayflowcore.events.event import _PII_TEXT_MASK, ExceptionRaisedEvent
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep
from wayflowcore.steps.flowexecutionstep import FlowExecutionStep
from wayflowcore.steps.toolexecutionstep import ToolExecutionStep
from wayflowcore.tools.flowbasedtools import DescribedFlow
from wayflowcore.tools.servertools import ServerTool
from wayflowcore.tools.tools import ToolRequest

from .conftest import create_dummy_llm_with_next_output
from .event_listeners import ExceptionRaisedEventListener


@pytest.mark.parametrize("missing_attribute", ["exception"])
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes: Dict[str, Any] = {
        "exception": RuntimeError("Test exception"),
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        ExceptionRaisedEvent(**all_attributes)


@pytest.mark.parametrize(
    "event_info",
    [
        {
            "name": "My event test",
            "timestamp": 12,
            "event_id": "abc123",
            "exception": Exception(
                "Test exception",
            ),
        },
        {
            "name": "My other test",
            "exception": RuntimeError(
                "Other exception",
            ),
        },
        {
            "name": "Yet another test",
            "event_id": "123abc",
            "exception": DivisionByZero(),
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
    event = ExceptionRaisedEvent(**event_info)
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
    assert serialized_event["event_type"] == str(event.__class__.__name__)
    for attribute_name in attributes_to_check:
        if attribute_name == "exception":
            assert str(event.exception) == serialized_event["exception.message"]
            if mask_sensitive_information:
                assert _PII_TEXT_MASK == serialized_event["exception.message"]
                assert _PII_TEXT_MASK == serialized_event["exception.traceback"]
            else:
                assert str(event.exception) == serialized_event["exception.message"]
                assert event.exception.__traceback__ == serialized_event["exception.traceback"]
        else:
            assert getattr(event, attribute_name) == serialized_event[attribute_name]


def _raises_runtime_error():
    raise RuntimeError()


def _raises_io_error():
    raise IOError()


@pytest.mark.parametrize(
    "tool",
    [
        ServerTool(
            name="do_random_logic",
            description="This tool does some very complicated logic, and can fail",
            func=_raises_runtime_error,
            input_descriptors=[],
        ),
        ServerTool(
            name="create_code_file",
            description="This tool tries to create a file and fails",
            func=_raises_io_error,
            input_descriptors=[],
        ),
    ],
)
def test_event_is_not_triggered_with_tool_execution_raises_exception_false(
    tool: ServerTool,
) -> None:
    event_listener = ExceptionRaisedEventListener()
    flow = create_single_step_flow(
        step=ToolExecutionStep(
            tool=tool,
            raise_exceptions=False,
        )
    )
    conversation = flow.start_conversation()

    with register_event_listeners([event_listener]):
        conversation.execute()

    assert len(event_listener.triggered_events) == 0


@pytest.mark.parametrize(
    "tool",
    [
        ServerTool(
            name="do_random_logic",
            description="This tool does some very complicated logic, and can fail",
            func=_raises_runtime_error,
            input_descriptors=[],
        ),
        ServerTool(
            name="create_code_file",
            description="This tool tries to create a file and fails",
            func=_raises_io_error,
            input_descriptors=[],
        ),
    ],
)
def test_event_is_triggered_with_tool_execution_and_reraises(
    tool: ServerTool,
) -> None:
    event_listener = ExceptionRaisedEventListener()
    flow = create_single_step_flow(
        step=ToolExecutionStep(
            tool=tool,
            raise_exceptions=True,
        )
    )
    conversation = flow.start_conversation()

    with pytest.raises(Exception):
        with register_event_listeners([event_listener]):
            conversation.execute()

    assert len(event_listener.triggered_events) == 1
    assert isinstance(event_listener.triggered_events[0], ExceptionRaisedEvent)


SERVER_TOOL = ServerTool(
    name="create_file",
    description="This tool attempts to create a file",
    func=_raises_io_error,
    input_descriptors=[],
)


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
                                    name=SERVER_TOOL.name,
                                    args={},
                                    tool_request_id="tool_request_id_1",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        ),
                    },
                ),
                flows=[
                    DescribedFlow(
                        name=SERVER_TOOL.name,
                        description="Create file",
                        flow=create_single_step_flow(
                            step=FlowExecutionStep(
                                flow=create_single_step_flow(
                                    step=FlowExecutionStep(
                                        flow=create_single_step_flow(
                                            step=ToolExecutionStep(
                                                tool=SERVER_TOOL,
                                            ),
                                        )
                                    )
                                )
                            )
                        ),
                    )
                ],
            ),
            ["Please use the tool"],
        ),
    ],
)
def test_event_is_triggered_with_agent_using_flow(
    agent: Agent,
    user_messages: List[str],
) -> None:
    event_listener = ExceptionRaisedEventListener()
    conversation = agent.start_conversation()

    with pytest.raises(Exception):
        with register_event_listeners([event_listener]):
            conversation.execute()
            for user_message in user_messages:
                conversation.append_user_message(user_message)
                conversation.execute()

    assert len(event_listener.triggered_events) == 1
    assert isinstance(event_listener.triggered_events[0], ExceptionRaisedEvent)


EXCEPTION_RAISING_STEP = ToolExecutionStep(
    tool=ServerTool(
        name="raise_exception",
        description="this tool tries to do something but miserably fails",
        func=_raises_runtime_error,
        input_descriptors=[],
    ),
    raise_exceptions=True,
)


@pytest.mark.parametrize(
    "flow",
    [
        create_single_step_flow(step=EXCEPTION_RAISING_STEP),
        create_single_step_flow(
            step=FlowExecutionStep(flow=create_single_step_flow(step=EXCEPTION_RAISING_STEP))
        ),
        create_single_step_flow(
            step=FlowExecutionStep(
                flow=create_single_step_flow(
                    step=FlowExecutionStep(
                        flow=create_single_step_flow(
                            step=EXCEPTION_RAISING_STEP,
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
                                    step=EXCEPTION_RAISING_STEP,
                                )
                            )
                        )
                    )
                )
            )
        ),
    ],
)
def test_event_is_triggered_only_once(
    flow: Flow,
) -> None:
    event_listener = ExceptionRaisedEventListener()
    conversation = flow.start_conversation()

    with pytest.raises(Exception):
        with register_event_listeners([event_listener]):
            conversation.execute()

    assert len(event_listener.triggered_events) == 1
    assert all(isinstance(event, ExceptionRaisedEvent) for event in event_listener.triggered_events)


@pytest.mark.parametrize(
    "flow",
    [
        create_single_step_flow(
            step=FlowExecutionStep(
                flow=create_single_step_flow(
                    step=FlowExecutionStep(
                        flow=create_single_step_flow(
                            step=AgentExecutionStep(
                                agent=Agent(
                                    agent_id="a123",
                                    custom_instruction="Be polite",
                                    raise_exceptions=True,
                                    llm=create_dummy_llm_with_next_output(
                                        {
                                            "Please use the tool": Message(
                                                tool_requests=[
                                                    ToolRequest(
                                                        name=SERVER_TOOL.name,
                                                        args={},
                                                        tool_request_id="tool_request_id_1",
                                                    )
                                                ],
                                                message_type=MessageType.TOOL_REQUEST,
                                                sender="a123",
                                                recipients={"a123"},
                                            ),
                                        },
                                    ),
                                    flows=[
                                        DescribedFlow(
                                            name=SERVER_TOOL.name,
                                            description="Create file",
                                            flow=create_single_step_flow(
                                                step=FlowExecutionStep(
                                                    flow=create_single_step_flow(
                                                        step=FlowExecutionStep(
                                                            flow=create_single_step_flow(
                                                                step=EXCEPTION_RAISING_STEP,
                                                            )
                                                        )
                                                    )
                                                )
                                            ),
                                        )
                                    ],
                                )
                            )
                        )
                    )
                )
            )
        ),
    ],
)
def test_event_is_triggered_once_with_nested_agent(
    flow: Flow,
) -> None:
    event_listener = ExceptionRaisedEventListener()
    conversation = flow.start_conversation()

    with pytest.raises(Exception):
        with register_event_listeners([event_listener]):
            conversation.execute()
            conversation.append_user_message("Please use the tool")
            conversation.execute()

    assert len(event_listener.triggered_events) == 1
    assert isinstance(event_listener.triggered_events[-1], ExceptionRaisedEvent)
