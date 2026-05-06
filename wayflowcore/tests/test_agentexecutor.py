# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest

from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.executors._agentexecutor import (
    AgentConversationExecutor,
    _normalize_tool_request_args,
)
from wayflowcore.executors.executionstatus import FinishedStatus, ToolRequestStatus
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.property import IntegerProperty, ListProperty, StringProperty
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import ClientTool, ServerTool, ToolRequest

from .testhelpers.dummy import DummyModel


def test_normalize_tool_request_args_coerces_and_drops_unknown_values() -> None:
    tool_request = ToolRequest(
        name="create_dashboard",
        args={
            "name": "my_dash",
            "forecasted_data": "[27, 28, 24, 21, 25]",
            "wrong_arg_name": "",
        },
        tool_request_id="request_id",
    )

    _normalize_tool_request_args(
        tool_request,
        {
            "name": {"type": "string"},
            "forecasted_data": {"type": "array", "items": {"type": "integer"}},
        },
    )

    assert tool_request.args == {
        "name": "my_dash",
        "forecasted_data": [27, 28, 24, 21, 25],
    }


@pytest.mark.anyio
async def test_execute_next_subcall_normalizes_zero_arg_client_tool_before_yielding() -> None:
    tool = ClientTool(
        name="measure_room_temp",
        description="Return the value of the temperature in the room",
        parameters={},
    )
    agent = Agent(
        llm=DummyModel(),
        tools=[tool],
        custom_instruction="You are a helpful assistant.",
    )
    conversation = agent.start_conversation()
    tool_request = ToolRequest(
        name="measure_room_temp",
        args={"wrong_arg_name": ""},
        tool_request_id="request_id",
    )
    conversation.append_message(
        Message(message_type=MessageType.TOOL_REQUEST, tool_requests=[tool_request])
    )
    conversation.state.current_retrieved_tools = [tool]

    status = await AgentConversationExecutor._execute_next_subcall(
        config=agent,
        conversation=conversation,
        state=conversation.state,
        tool_request=tool_request,
        messages=conversation.message_list,
    )

    assert isinstance(status, ToolRequestStatus)
    assert status.tool_requests[0].args == {}


@pytest.mark.anyio
async def test_execute_next_subcall_coerces_numeric_tool_args_before_execution() -> None:
    tool = ServerTool(
        name="multiply",
        description="Return the result of multiplication between number a and b.",
        input_descriptors=[
            IntegerProperty("a", description="first required integer"),
            IntegerProperty("b", description="second required integer"),
        ],
        func=lambda a, b: a * b,
    )
    agent = Agent(
        llm=DummyModel(),
        tools=[tool],
        custom_instruction="You are a helpful assistant.",
    )
    conversation = agent.start_conversation()
    tool_request = ToolRequest(
        name="multiply",
        args={"a": "2145", "b": "123"},
        tool_request_id="request_id",
    )
    conversation.append_message(
        Message(message_type=MessageType.TOOL_REQUEST, tool_requests=[tool_request])
    )
    conversation.state.current_retrieved_tools = [tool]

    status = await AgentConversationExecutor._execute_next_subcall(
        config=agent,
        conversation=conversation,
        state=conversation.state,
        tool_request=tool_request,
        messages=conversation.message_list,
    )

    assert status is None
    assert tool_request.args == {"a": 2145, "b": 123}
    assert conversation.get_last_message().tool_result.content == 263835


@pytest.mark.anyio
async def test_execute_next_subcall_coerces_stringified_array_tool_args_before_execution() -> None:
    tool = ServerTool(
        name="create_dashboard",
        description="Create a dashboard.",
        input_descriptors=[
            StringProperty("name", description="name of the dashboard"),
            ListProperty(
                "forecasted_data",
                description="forecasted data. Cannot be an empty list",
                item_type=IntegerProperty(),
            ),
        ],
        func=lambda name, forecasted_data: {"name": name, "forecasted_data": forecasted_data},
    )
    agent = Agent(
        llm=DummyModel(),
        tools=[tool],
        custom_instruction="You are a helpful assistant.",
    )
    conversation = agent.start_conversation()
    tool_request = ToolRequest(
        name="create_dashboard",
        args={"name": "my_dash", "forecasted_data": "[27, 28, 24, 21, 25]"},
        tool_request_id="request_id",
    )
    conversation.append_message(
        Message(message_type=MessageType.TOOL_REQUEST, tool_requests=[tool_request])
    )
    conversation.state.current_retrieved_tools = [tool]

    status = await AgentConversationExecutor._execute_next_subcall(
        config=agent,
        conversation=conversation,
        state=conversation.state,
        tool_request=tool_request,
        messages=conversation.message_list,
    )

    assert status is None
    assert tool_request.args == {
        "name": "my_dash",
        "forecasted_data": [27, 28, 24, 21, 25],
    }
    assert conversation.get_last_message().tool_result.content == {
        "name": "my_dash",
        "forecasted_data": [27, 28, 24, 21, 25],
    }


@pytest.mark.anyio
async def test_execute_next_subcall_normalizes_zero_arg_flow_before_starting_flow() -> None:
    inner_tool = ServerTool(
        name="_inner_measure_room_temp",
        description="Return the value of the temperature in the room",
        parameters={},
        func=lambda: "22C",
    )
    flow = create_single_step_flow(
        ToolExecutionStep(tool=inner_tool),
        flow_name="measure_room_temp",
        flow_description="Return the value of the temperature in the room",
    )
    agent = Agent(
        llm=DummyModel(),
        flows=[flow],
        custom_instruction="You are a helpful assistant.",
    )
    conversation = agent.start_conversation()
    tool_request = ToolRequest(
        name="measure_room_temp",
        args={"wrong_arg_name": ""},
        tool_request_id="request_id",
    )

    status = await AgentConversationExecutor._execute_next_subcall(
        config=agent,
        conversation=conversation,
        state=conversation.state,
        tool_request=tool_request,
        messages=conversation.message_list,
    )

    assert status is None
    assert tool_request.args == {}
    assert conversation.get_last_message().tool_result.content == "22C"


@pytest.mark.anyio
async def test_process_tool_call_normalizes_submit_result_arguments_before_finishing() -> None:
    agent = Agent(
        llm=DummyModel(),
        caller_input_mode=CallerInputMode.NEVER,
        custom_instruction="Submit the outputs using the submit_result tool.",
        output_descriptors=[
            IntegerProperty(
                "zinimo_result",
                description="result of the zinimo operation of the two provided integers",
            )
        ],
    )
    conversation = agent.start_conversation()
    tool_request = ToolRequest(
        name="submit_result",
        args={"zinimo_result": "-2", "wrong_arg_name": ""},
        tool_request_id="request_id",
    )

    status, should_yield = await AgentConversationExecutor._process_tool_call(
        agent_config=agent,
        tool_request=tool_request,
        agent_state=conversation.state,
        conversation=conversation,
    )

    assert should_yield is True
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {"zinimo_result": -2}
    assert tool_request.args == {"zinimo_result": -2}
    assert conversation.get_last_message().tool_result.content == "The submission was successful"
