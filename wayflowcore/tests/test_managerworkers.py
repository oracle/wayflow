# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import json
from typing import Annotated, Any, Optional, Tuple

import pytest

from wayflowcore._utils._templating_helpers import render_template
from wayflowcore.agent import DEFAULT_INITIAL_MESSAGE, Agent
from wayflowcore.executors._agenticpattern_helpers import _SEND_MESSAGE_TOOL_NAME
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.property import IntegerProperty, StringProperty
from wayflowcore.tools import ClientTool, ToolRequest, ToolResult, tool

from .testhelpers.dummy import DummyModel
from .testhelpers.testhelpers import retry_test

_MANAGER_TOOL_CALL_TEMPLATE = """
{{thoughts}}

{"name": {{tool_name}}, "parameters": {{tool_params}}}
""".strip()


def _send_message(
    recipient_agent: Agent, message: Optional[str] = None, thoughts: Optional[str] = None
) -> Message:
    return Message(
        render_template(
            _MANAGER_TOOL_CALL_TEMPLATE,
            inputs=dict(
                thoughts=thoughts or "THOUGHTS",
                tool_name=_SEND_MESSAGE_TOOL_NAME,
                tool_params=json.dumps(
                    dict(message=message or "MESSAGE", recipient=recipient_agent.name)
                ),
            ),
        ),
        message_type=MessageType.AGENT,
    )


def test_managerworkers_raises_on_same_name_for_manager_and_worker(simple_math_agents_example):
    addition_agent, _ = simple_math_agents_example

    with pytest.raises(ValueError, match="Found agents with duplicated names"):
        ManagerWorkers(group_manager=addition_agent, workers=[addition_agent])


def test_managerworkers_raise_error_when_duplicate_names():
    llm = DummyModel()

    worker1 = Agent(llm, name="worker1", description="worker 1")
    worker2 = Agent(llm, name="worker2", description="worker 2")

    worker1.name = worker2.name

    with pytest.raises(ValueError, match="Found agents with duplicated names"):
        ManagerWorkers(workers=[worker1, worker2], group_manager=llm)


def test_managerworkers_raise_error_when_worker_list_is_empty():
    llm = DummyModel()

    with pytest.raises(ValueError, match="Cannot define a group with no worker agent"):
        ManagerWorkers(workers=[], group_manager=llm)


def test_manager_can_be_initialized_with_an_agent():
    llm = DummyModel()

    worker1 = Agent(llm, name="worker1", description="worker 1")
    worker2 = Agent(llm, name="worker2", description="worker 2")

    manager = Agent(llm, name="manager", description="manager")

    ManagerWorkers(workers=[worker1, worker2], group_manager=manager)


def test_manager_can_send_message_to_worker_and_worker_can_reply():
    llm = DummyModel()

    worker1 = Agent(llm, name="worker1", description="worker 1")
    worker2 = Agent(llm, name="worker2", description="worker 2")

    group = ManagerWorkers(workers=[worker1, worker2], group_manager=llm)

    llm.set_next_output(
        [
            _send_message(worker1, message="Hey worker 1", thoughts="sending message to worker 1"),
            "Hello manager!",
        ]
    )

    conversation = group.start_conversation()
    conversation.append_user_message("dummy")
    with pytest.raises(ValueError, match="Did you forget to set the output of the Dummy model"):
        conversation.execute()

    # subconversation of worker should contain the message from manager
    worker1_sub_conv = conversation.subconversations[worker1.name]
    worker1_first_message = worker1_sub_conv.message_list.messages[0]
    assert worker1_first_message.content == "Hey worker 1" and worker1_first_message.role == "user"

    # subconversation of worker should contain its own response
    worker1_last_message = worker1_sub_conv.get_last_message()
    assert (
        worker1_last_message.content == "Hello manager!"
        and worker1_last_message.role == "assistant"
    )

    # main conversation should contain worker's response as tool result
    last_message = conversation.get_last_message()
    assert last_message.tool_result.content == "Hello manager!" and last_message.role == "assistant"


@pytest.fixture
def simple_math_agents_example(remote_gemma_llm) -> Tuple[Agent, Agent, Agent]:
    llm = remote_gemma_llm
    addition_agent = Agent(
        name="addition_agent",
        description="Agent that can do additions",
        llm=llm,
        custom_instruction="You can do additions. Please use your tools if available",
    )
    multiplication_agent = Agent(
        name="multiplication_agent",
        description="Agent that can do multiplication",
        llm=llm,
        custom_instruction="You can do multiplication.Please use your tools if available.",
    )

    return (addition_agent, multiplication_agent)


def test_managerworkers_can_execute_with_initial_params_passed_in_start_conversation(
    remotely_hosted_llm, simple_math_agents_example
):
    """
    Failure rate:          1 out of 50
    Observed on:           2025-09-11
    Average success time:  2.22 seconds per successful attempt
    Average failure time:  1.95 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000
    """
    addition_agent, multiplication_agent = simple_math_agents_example

    manager_agent = Agent(
        llm=remotely_hosted_llm,
        description="Manager agent",
        custom_instruction=(
            "You are a group manager. You are communicating with {{ USER }}"
            "Remember to say hi with the user name when the conversation first starts."
        ),
        name="manager_agent",
    )
    group = ManagerWorkers(
        workers=[addition_agent, multiplication_agent],
        group_manager=manager_agent,
    )

    conversation = group.start_conversation(
        messages=[Message(content="Please compute 3*4 + 2", message_type=MessageType.USER)],
        inputs={"USER": "Iris"},
        conversation_id="12345",
    )

    conversation.execute()

    # The first message must be not the default message as the init messages are passed.
    assert conversation.get_last_message().content != DEFAULT_INITIAL_MESSAGE
    assert conversation.conversation_id == "12345"


def test_worker_with_client_tool_works_as_expected(remotely_hosted_llm) -> None:
    llm = remotely_hosted_llm
    dummy_llm = DummyModel()

    def _multiply_impl(a: int, b: int) -> int:
        return a * b

    def execute_client_tool_from_tool_request(tool_request: ToolRequest) -> Any:
        if tool_request.name == "multiply":
            return _multiply_impl(**tool_request.args)
        else:
            raise ValueError(f"Tool name {tool_request.name} is not recognized")

    multiply_tool = ClientTool(
        name="multiply",
        description="Return the result of multiplication between number a and b.",
        input_descriptors=[
            IntegerProperty("a", description="first required integer"),
            IntegerProperty("b", description="second required integer"),
        ],
    )

    multiplication_agent = Agent(
        name="multiplication_agent",
        description="Agent that can do multiplication",
        llm=llm,
        tools=[multiply_tool],
        custom_instruction="You can do multiplication.",
    )

    group = ManagerWorkers(group_manager=dummy_llm, workers=[multiplication_agent])

    dummy_llm.set_next_output(
        [_send_message(multiplication_agent, message="Please compute 2145 * 123")]
    )

    conversation = group.start_conversation()
    conversation.append_user_message("Dummy")

    status = conversation.execute()

    assert isinstance(status, ToolRequestStatus)

    tool_request = status.tool_requests[0]
    tool_result = execute_client_tool_from_tool_request(tool_request)
    conversation.append_tool_result(ToolResult(tool_result, tool_request.tool_request_id))

    with pytest.raises(ValueError, match="Did you forget to set the output of the Dummy model"):
        status = conversation.execute()


def test_worker_with_server_tool_execution_does_not_raise_errors(remotely_hosted_llm) -> None:
    dummy_llm = DummyModel()

    @tool
    def multiply(
        a: Annotated[int, "first required integer"], b: Annotated[int, "second required integer"]
    ) -> int:
        "Return the result of multiplication between number a and b."
        return a * b

    multiplication_agent = Agent(
        name="multiplication_agent",
        description="Agent that can do multiplication",
        llm=remotely_hosted_llm,
        tools=[multiply],
        custom_instruction="You can do multiplication.",
    )

    group = ManagerWorkers(group_manager=dummy_llm, workers=[multiplication_agent])

    dummy_llm.set_next_output(
        [_send_message(multiplication_agent, message="Please compute 2145 * 123")]
    )
    conversation = group.start_conversation()
    conversation.append_user_message("dummy")

    with pytest.raises(ValueError, match="Did you forget to set the output of the Dummy model"):
        conversation.execute()

    # Check tool request `multiply` existing in the message list of multiplication_agent
    subconversation = conversation.state.subconversations[multiplication_agent.name]

    assert any(
        message.tool_requests is not None for message in subconversation.message_list.messages
    )


def test_manager_with_server_tool_execution_does_not_raise_errors():
    llm = DummyModel()

    @tool
    def say_hello(user_name: Annotated[str, "Name of user"]) -> str:
        "Return a hello message including user name"
        return f"Hello {user_name}!"

    manager_agent = Agent(name="manager", description="manager agent", tools=[say_hello], llm=llm)
    worker = Agent(name="worker", description="worker", llm=llm)

    group = ManagerWorkers(workers=[worker], group_manager=manager_agent)

    llm.set_next_output(
        [
            Message(
                render_template(
                    _MANAGER_TOOL_CALL_TEMPLATE,
                    inputs=dict(
                        thoughts="",
                        tool_name="say_hello",
                        tool_params={"user_name": "Iris"},
                    ),
                ),
                message_type=MessageType.AGENT,
            ),
            "Dummy",
        ]
    )

    conversation = group.start_conversation()
    conversation.append_user_message("Dummy")
    status = conversation.execute()

    assert isinstance(status, UserMessageRequestStatus)


def test_manager_with_client_tool_execution_works_as_expected():
    llm = DummyModel()

    def _say_hello(user_name: str) -> str:
        return f"Hello {user_name}!"

    def execute_client_tool_from_tool_request(tool_request: ToolRequest) -> Any:
        if tool_request.name == "say_hello":
            return _say_hello(**tool_request.args)
        else:
            raise ValueError(f"Tool name {tool_request.name} is not recognized")

    hello_tool = ClientTool(
        name="say_hello",
        description="Return a hello message including user name",
        input_descriptors=[
            StringProperty("user_name", description="user name"),
        ],
    )

    manager_agent = Agent(
        name="manager_agent",
        description="manager_agent",
        llm=llm,
        tools=[hello_tool],
    )
    worker = Agent(name="worker", description="worker", llm=llm)

    group = ManagerWorkers(group_manager=manager_agent, workers=[worker])

    llm.set_next_output(
        [
            Message(
                render_template(
                    _MANAGER_TOOL_CALL_TEMPLATE,
                    inputs=dict(
                        thoughts="",
                        tool_name="say_hello",
                        tool_params={"user_name": "Iris"},
                    ),
                ),
                message_type=MessageType.AGENT,
            ),
        ]
    )

    conversation = group.start_conversation()
    conversation.append_user_message("Dummy")

    status = conversation.execute()

    assert isinstance(status, ToolRequestStatus)

    tool_request = status.tool_requests[0]
    tool_result = execute_client_tool_from_tool_request(tool_request)
    conversation.append_tool_result(ToolResult(tool_result, tool_request.tool_request_id))

    with pytest.raises(ValueError, match="Did you forget to set the output of the Dummy model"):
        status = conversation.execute()


def test_managerworkers_execution_does_not_raise_errors(
    simple_math_agents_example, remotely_hosted_llm
):
    llm = remotely_hosted_llm
    addition_agent, multiplication_agent = simple_math_agents_example

    group = ManagerWorkers(group_manager=llm, workers=[addition_agent, multiplication_agent])

    conversation = group.start_conversation()
    conversation.append_user_message("Please compute 2*2 + 1")
    conversation.execute()


@tool(requires_confirmation=True, description_mode="only_docstring")
def check_name_in_db_tool(name: str) -> str:
    """Check if a name is present in the database"""
    return "This name is present in the database"


@retry_test(max_attempts=3)
def test_managerworkers_execution_works_with_servertool_confirmation(big_llama):
    """
    Failure rate:          1 out of 50
    Observed on:           2025-09-23
    Average success time:  14.08 seconds per successful attempt
    Average failure time:  17.05 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000
    """
    llm = big_llama
    agent = Agent(
        llm=llm,
        tools=[check_name_in_db_tool],
        name="check_name_in_db_agent",
        description="A helpful agent that has access to a tool which check if a given name is present in database.",
        custom_instruction="You should only use one tool at a time. Only use the talk_to_user tool to ask the user questions, not to inform them about your next action. Don't talk to the user unless reporting on the requested tasks.",
    )

    group = ManagerWorkers(group_manager=llm, workers=[agent])

    conversation = group.start_conversation()
    conversation.append_user_message(
        "Is the name Bob present in the database? Ask your agents if needed"
    )
    status = conversation.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    assert len(status.tool_requests) == 1
    req = status.tool_requests[0]
    assert req.name == "check_name_in_db_tool"
    # Confirm the tool execution
    status.confirm_tool_execution(tool_request=req)
    status2 = conversation.execute()
    # Should result in a user message request or final status
    assert isinstance(status2, UserMessageRequestStatus) or isinstance(status2, FinishedStatus)

    conversation = group.start_conversation()
    conversation.append_user_message(
        "Is the name Alice present in the database? Ask your agents if needed"
    )
    status = conversation.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    assert len(status.tool_requests) == 1
    status.reject_tool_execution(
        tool_request=status.tool_requests[0], reason="Access Denied, Do not try again"
    )
    status2 = conversation.execute()
    # Should result in a user message request or final status
    assert isinstance(status2, UserMessageRequestStatus) or isinstance(status2, FinishedStatus)
