# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
from typing import Annotated, Any, Optional, Tuple

import pytest

from wayflowcore._utils._templating_helpers import render_template
from wayflowcore.agent import DEFAULT_INITIAL_MESSAGE, Agent, CallerInputMode
from wayflowcore.executors._agentexecutor import _TALK_TO_USER_TOOL_NAME
from wayflowcore.executors._agenticpattern_helpers import _SEND_MESSAGE_TOOL_NAME
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import VllmModel
from wayflowcore.property import IntegerProperty, StringProperty
from wayflowcore.templates import LLAMA_AGENT_TEMPLATE, PromptTemplate
from wayflowcore.templates._managerworkerstemplate import (
    _DEFAULT_MANAGERWORKERS_CHAT_TEMPLATE,
    _DEFAULT_MANAGERWORKERS_NATIVE_CHAT_TEMPLATE,
    ManagerWorkersJsonToolOutputParser,
)
from wayflowcore.tools import ClientTool, ToolRequest, ToolResult, tool

from .test_swarm import (
    _get_agent_with_client_tool,
    _get_bwip_agent,
    _get_fooza_agent,
    _get_zbuk_agent,
    bwip_tool,
    fooza_tool,
    zbuk_tool,
)
from .testhelpers.dummy import DummyModel
from .testhelpers.patching import patch_llm
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


def _send_message_with_native_tool_call(
    recipient_agent: Agent, message: Optional[str] = None
) -> Message:
    return _native_tool_call_message(
        _SEND_MESSAGE_TOOL_NAME,
        dict(message=message or "MESSAGE", recipient=recipient_agent.name),
        tool_request_id="send_message_1",
    )


def _native_tool_call_message(
    tool_name: str, args: dict[str, Any], tool_request_id: str = "tool_request_1"
) -> Message:
    return Message(
        tool_requests=[
            ToolRequest(
                name=tool_name,
                args=args,
                tool_request_id=tool_request_id,
            )
        ],
        message_type=MessageType.AGENT,
    )


def _get_multiplication_agent_with_client_tool(
    llm: DummyModel, requires_confirmation: bool = False
) -> Agent:
    multiply_tool = ClientTool(
        name="multiply",
        description="Return the result of multiplication between number a and b.",
        input_descriptors=[
            IntegerProperty("a", description="first required integer"),
            IntegerProperty("b", description="second required integer"),
        ],
        requires_confirmation=requires_confirmation,
    )
    return Agent(
        name="multiplication_agent",
        description="Agent that can do multiplication",
        llm=llm,
        tools=[multiply_tool],
        custom_instruction="You can do multiplication.",
    )


def _set_multiplication_agent_client_tool_outputs(llm: DummyModel) -> None:
    llm.set_next_output(
        [
            Message(
                tool_requests=[
                    ToolRequest(
                        name="multiply",
                        args={"a": 2145, "b": 123},
                        tool_request_id="multiply_1",
                    )
                ],
                message_type=MessageType.AGENT,
            ),
            "worker answer",
        ]
    )


def _execute_multiply_tool_from_tool_request(tool_request: ToolRequest) -> int:
    if tool_request.name != "multiply":
        raise ValueError(f"Tool name {tool_request.name} is not recognized")
    return tool_request.args["a"] * tool_request.args["b"]


def _get_managerworkers_group_and_message(
    manager_llm: DummyModel, worker: Agent, message: str, use_native_managerworkers_template: bool
) -> tuple[ManagerWorkers, Message]:
    if use_native_managerworkers_template:
        managerworkers = (
            ManagerWorkers(
                group_manager=manager_llm,
                workers=[worker],
                managerworkers_template=_DEFAULT_MANAGERWORKERS_NATIVE_CHAT_TEMPLATE,
            ),
            _send_message_with_native_tool_call(worker, message),
        )
    else:
        managerworkers = (
            ManagerWorkers(
                group_manager=manager_llm,
                workers=[worker],
                managerworkers_template=_DEFAULT_MANAGERWORKERS_CHAT_TEMPLATE,
            ),
            _send_message(worker, message=message),
        )
    return managerworkers


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


def test_managerworkers_uses_native_tool_calling_template_by_default_when_manager_llm_supports_it():
    llm = DummyModel()
    worker = Agent(llm, name="worker", description="worker")

    group = ManagerWorkers(workers=[worker], group_manager=llm)

    assert group.managerworkers_template.native_tool_calling is True
    assert group.managerworkers_template.output_parser is None
    assert group.managerworkers_template.generation_config is None


def test_managerworkers_uses_non_native_tool_calling_template_when_manager_llm_does_not_support_it():
    llm = DummyModel(supports_tool_calling=False)
    worker = Agent(llm, name="worker", description="worker")

    group = ManagerWorkers(workers=[worker], group_manager=llm)

    assert group.managerworkers_template.native_tool_calling is False
    assert isinstance(
        group.managerworkers_template.output_parser, ManagerWorkersJsonToolOutputParser
    )


def test_managerworkers_uses_non_native_template_when_manager_llm_defaults_to_non_native_tools():
    manager_llm = VllmModel(
        model_id="meta-llama/Meta-Llama-3.1-8B-Instruct",
        host_port="http://example.test",
    )
    worker_llm = DummyModel()
    worker = Agent(worker_llm, name="worker", description="worker")

    group = ManagerWorkers(workers=[worker], group_manager=manager_llm)

    assert manager_llm.supports_tool_calling is True
    assert manager_llm.agent_template.native_tool_calling is False
    assert group.managerworkers_template.native_tool_calling is False
    assert isinstance(
        group.managerworkers_template.output_parser, ManagerWorkersJsonToolOutputParser
    )


def test_managerworkers_can_use_non_native_tool_calling_template_when_explicitly_requested():
    llm = DummyModel()
    worker = Agent(llm, name="worker", description="worker")

    group = ManagerWorkers(
        workers=[worker],
        group_manager=llm,
        managerworkers_template=_DEFAULT_MANAGERWORKERS_CHAT_TEMPLATE,
    )

    assert group.managerworkers_template.native_tool_calling is False
    assert isinstance(
        group.managerworkers_template.output_parser, ManagerWorkersJsonToolOutputParser
    )


def test_managerworkers_can_use_native_tool_calling_template_when_explicitly_requested():
    llm = DummyModel(supports_tool_calling=False)
    worker = Agent(llm, name="worker", description="worker")

    group = ManagerWorkers(
        workers=[worker],
        group_manager=llm,
        managerworkers_template=_DEFAULT_MANAGERWORKERS_NATIVE_CHAT_TEMPLATE,
    )

    assert group.managerworkers_template.native_tool_calling is True
    assert group.managerworkers_template.output_parser is None
    assert group.managerworkers_template.generation_config is None


def test_managerworkers_default_depends_on_manager_llm_not_manager_agent_template():
    llm = DummyModel()
    worker = Agent(llm, name="worker", description="worker")
    manager = Agent(
        llm,
        name="manager",
        description="manager",
        agent_template=LLAMA_AGENT_TEMPLATE,
    )

    group = ManagerWorkers(workers=[worker], group_manager=manager)

    assert group.managerworkers_template.native_tool_calling is True
    assert group.managerworkers_template.output_parser is None


def test_native_managerworkers_template_omits_talk_to_user_when_disabled():
    prompt = _DEFAULT_MANAGERWORKERS_NATIVE_CHAT_TEMPLATE.format(
        inputs={
            "name": "manager",
            "description": "manager",
            "caller_name": "HUMAN USER",
            "other_agents": [{"name": "worker", "description": "worker"}],
            "_add_talk_to_user_tool": False,
            "custom_instruction": "",
            PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME: [],
        },
    )
    rendered_prompt = "\n".join(message.content for message in prompt.messages)

    assert "talk_to_user" not in rendered_prompt
    assert "Answer your caller directly" in rendered_prompt


def test_non_native_managerworkers_template_allows_direct_answer_when_talk_to_user_disabled():
    prompt = _DEFAULT_MANAGERWORKERS_CHAT_TEMPLATE.format(
        inputs={
            "name": "manager",
            "description": "manager",
            "caller_name": "HUMAN USER",
            "other_agents": [{"name": "worker", "description": "worker"}],
            "_add_talk_to_user_tool": False,
            "custom_instruction": "",
            PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME: [],
        },
    )
    rendered_prompt = "\n".join(message.content for message in prompt.messages)

    assert "talk_to_user" not in rendered_prompt
    assert "When no tool call is needed, return only the visible answer text." in rendered_prompt
    assert "Always structure your response as a thought" not in rendered_prompt


def test_managerworkers_private_add_talk_to_user_tool_false_removes_tool_schema():
    class CapturingDummyModel(DummyModel):
        def __init__(self):
            super().__init__()
            self.captured_tool_names: list[str] = []

        async def _generate_impl(self, prompt):
            self.captured_tool_names = [tool.name for tool in prompt.tools or []]
            return await super()._generate_impl(prompt)

    llm = CapturingDummyModel()
    llm.set_next_output("done")
    worker = Agent(llm, name="worker", description="worker")

    group = ManagerWorkers(
        workers=[worker],
        group_manager=llm,
        _add_talk_to_user_tool=False,
    )
    status = group.start_conversation(messages="hello").execute()

    assert isinstance(status, UserMessageRequestStatus)
    assert _SEND_MESSAGE_TOOL_NAME in llm.captured_tool_names
    assert _TALK_TO_USER_TOOL_NAME not in llm.captured_tool_names


def test_managerworkers_private_add_talk_to_user_tool_false_applies_to_workers():
    class CapturingDummyModel(DummyModel):
        def __init__(self):
            super().__init__()
            self.captured_tool_names: list[str] = []

        async def _generate_impl(self, prompt):
            self.captured_tool_names = [tool.name for tool in prompt.tools or []]
            return await super()._generate_impl(prompt)

    manager_llm = DummyModel()
    worker_llm = CapturingDummyModel()
    worker = Agent(
        worker_llm,
        name="worker",
        description="worker",
        tools=[fooza_tool],
    )
    manager_llm.set_next_output(
        [
            _send_message_with_native_tool_call(worker, message="do work"),
            "manager done",
        ]
    )
    worker_llm.set_next_output("worker done")

    group = ManagerWorkers(
        workers=[worker],
        group_manager=manager_llm,
        _add_talk_to_user_tool=False,
    )
    status = group.start_conversation(messages="hello").execute()

    assert isinstance(status, UserMessageRequestStatus)
    assert "fooza_tool" in worker_llm.captured_tool_names
    assert _TALK_TO_USER_TOOL_NAME not in worker_llm.captured_tool_names


def test_managerworkers_private_add_talk_to_user_tool_false_keeps_nested_llm_manager_synced():
    llm = DummyModel()
    fooza_agent = _get_fooza_agent(llm)
    nested_group = ManagerWorkers(
        group_manager=llm,
        workers=[fooza_agent],
        name="nested_group",
        description="Nested group",
    )
    outer_manager = Agent(
        llm=llm,
        name="outer_manager",
        description="Outer manager",
        custom_instruction="Delegate fooza work to nested_group.",
    )
    outer_group = ManagerWorkers(
        group_manager=outer_manager,
        workers=[nested_group],
        _add_talk_to_user_tool=False,
    )
    conv = outer_group.start_conversation(messages="Compute fooza(4, 2).")

    with patch_llm(
        llm,
        outputs=[
            [
                ToolRequest(
                    name="send_message",
                    args={"recipient": "nested_group", "message": "calculate fooza(4,2)"},
                )
            ],
            [
                ToolRequest(
                    name="send_message",
                    args={"recipient": "fooza_agent", "message": "calculate fooza(4,2)"},
                )
            ],
            [ToolRequest(name="fooza_tool", args={"a": 4, "b": 2})],
            "fooza agent answers nested manager",
            "nested manager answers outer manager",
            "outer manager answers user",
        ],
    ):
        status = conv.execute()

    assert isinstance(status, UserMessageRequestStatus)
    assert conv.get_last_message().content == "outer manager answers user"
    nested_conv = conv.state.subconversations["nested_group"]
    assert nested_conv._get_main_subconversation().component is nested_group.manager_agent


def test_manager_can_send_message_to_worker_and_worker_can_reply():
    llm = DummyModel()

    worker1 = Agent(llm, name="worker1", description="worker 1")
    worker2 = Agent(llm, name="worker2", description="worker 2")

    group = ManagerWorkers(workers=[worker1, worker2], group_manager=llm)

    llm.set_next_output(
        [
            _send_message_with_native_tool_call(worker1, message="Hey worker 1"),
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


@pytest.mark.parametrize(
    "use_native_managerworkers_template",
    [
        pytest.param(False, id="non_native_managerworkers_template"),
        pytest.param(True, id="native_managerworkers_template"),
    ],
)
def test_worker_with_client_tool_works_as_expected(
    use_native_managerworkers_template: bool,
) -> None:
    manager_llm = DummyModel()
    worker_llm = DummyModel()

    multiplication_agent = _get_multiplication_agent_with_client_tool(worker_llm)
    _set_multiplication_agent_client_tool_outputs(worker_llm)

    group, initial_manager_message = _get_managerworkers_group_and_message(
        manager_llm,
        multiplication_agent,
        "Please compute 2145 * 123",
        use_native_managerworkers_template,
    )

    manager_llm.set_next_output([initial_manager_message])

    conversation = group.start_conversation()
    conversation.append_user_message("Dummy")

    status = conversation.execute()

    assert isinstance(status, ToolRequestStatus)

    tool_request = status.tool_requests[0]
    assert tool_request.args == {"a": 2145, "b": 123}
    tool_result = _execute_multiply_tool_from_tool_request(tool_request)
    conversation.append_tool_result(ToolResult(tool_result, tool_request.tool_request_id))

    with pytest.raises(ValueError, match="Did you forget to set the output of the Dummy model"):
        status = conversation.execute()


@pytest.mark.parametrize(
    "use_native_managerworkers_template",
    [
        pytest.param(False, id="non_native_managerworkers_template"),
        pytest.param(True, id="native_managerworkers_template"),
    ],
)
def test_worker_with_client_tool_with_confirmation_works_as_expected(
    use_native_managerworkers_template: bool,
) -> None:
    manager_llm = DummyModel()
    worker_llm = DummyModel()

    multiplication_agent = _get_multiplication_agent_with_client_tool(
        worker_llm, requires_confirmation=True
    )
    _set_multiplication_agent_client_tool_outputs(worker_llm)

    group, initial_manager_message = _get_managerworkers_group_and_message(
        manager_llm,
        multiplication_agent,
        "Please compute 2145 * 123",
        use_native_managerworkers_template,
    )

    manager_llm.set_next_output([initial_manager_message])

    conversation = group.start_conversation()
    conversation.append_user_message("Dummy")

    status = conversation.execute()

    assert isinstance(status, ToolExecutionConfirmationStatus)
    status.confirm_tool_execution(tool_request=status.tool_requests[0])
    status = conversation.execute()
    assert isinstance(status, ToolRequestStatus)

    tool_request = status.tool_requests[0]
    tool_result = _execute_multiply_tool_from_tool_request(tool_request)
    conversation.append_tool_result(ToolResult(tool_result, tool_request.tool_request_id))

    manager_llm.set_next_output(["dummy assistant output"])
    status = conversation.execute()
    assert isinstance(status, UserMessageRequestStatus)


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
        [
            _send_message_with_native_tool_call(
                multiplication_agent, message="Please compute 2145 * 123"
            )
        ]
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
            _native_tool_call_message("say_hello", {"user_name": "Iris"}),
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
            _native_tool_call_message("say_hello", {"user_name": "Iris"}),
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


def test_manager_with_client_tool_with_confirmation_execution_works_as_expected():
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
        requires_confirmation=True,
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
            _native_tool_call_message("say_hello", {"user_name": "Iris"}),
        ]
    )

    conversation = group.start_conversation()
    conversation.append_user_message("Dummy")

    status = conversation.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    status.confirm_tool_execution(tool_request=status.tool_requests[0])
    status = conversation.execute()
    assert isinstance(status, ToolRequestStatus)

    tool_request = status.tool_requests[0]
    tool_result = execute_client_tool_from_tool_request(tool_request)
    conversation.append_tool_result(ToolResult(tool_result, tool_request.tool_request_id))

    llm.set_next_output(["dummy assistant output"])
    status = conversation.execute()
    assert isinstance(status, UserMessageRequestStatus)


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
    Failure rate:          0 out of 50
    Observed on:           2026-05-15
    Average success time:  8.41 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
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


def test_multiple_tool_calling_with_nested_client_tool_request_does_not_raise_error(
    vllm_responses_llm,
):
    llm = vllm_responses_llm

    agent_with_client_tool = _get_agent_with_client_tool(llm)
    fooza_agent = _get_fooza_agent(llm)

    group = ManagerWorkers(group_manager=llm, workers=[agent_with_client_tool, fooza_agent])

    conv = group.start_conversation(
        messages="Check if the name Alice is present in the database and compute the result of fooza(4, 2)"
    )

    multiple_tool_requests = [
        ToolRequest(
            name="send_message",
            args={
                "recipient": "check_name_in_db_agent",
                "message": "Check if the name Alice is present in the database",
            },
            tool_request_id="send_message_1",
        ),
        ToolRequest(
            name="send_message",
            args={"recipient": "fooza_agent", "message": "Compute fooza(4,2)"},
            tool_request_id="send_message_2",
        ),
    ]
    client_tool_request = [
        ToolRequest(
            name="check_name_in_db_tool",
            args={"name": "Alice"},
            tool_request_id="client_tool",
        )
    ]

    with patch_llm(
        llm,
        outputs=[
            multiple_tool_requests,  # output from manager
            client_tool_request,  # output from agent_with_client_tool
            "agent_with_client_tool_answers",
            "fooza_agent_answers",
            "manager_answers",
        ],
    ):
        status = conv.execute()
        assert isinstance(status, ToolRequestStatus)  # yielding from agent_with_client_tool
        assert len(status.tool_requests) == 1
        assert status.tool_requests[0].name == "check_name_in_db_tool"

        status.submit_tool_result(
            ToolResult(
                content="The name Alice is present in the database", tool_request_id="client_tool"
            )
        )
        status_2 = conv.execute()
        assert isinstance(status_2, UserMessageRequestStatus)  # yielding from manager
        assert conv.get_last_message().content == "manager_answers"


def test_multiple_tool_calls_including_client_tool_can_be_executed(vllm_responses_llm):
    llm = vllm_responses_llm

    agent_with_client_tool = _get_agent_with_client_tool(llm)
    fooza_agent = _get_fooza_agent(llm)

    group = ManagerWorkers(
        group_manager=agent_with_client_tool,
        workers=[fooza_agent],
    )

    conv = group.start_conversation(
        messages="Check if the name Alice is present in the database and compute the result of fooza(4, 2)"
    )

    multiple_tool_requests = [
        ToolRequest(
            name="check_name_in_db_tool",
            args={"name": "Alice"},
            tool_request_id="client_tool",
        ),
        ToolRequest(
            name="send_message",
            args={"recipient": "fooza_agent", "message": "Compute fooza(4,2)"},
            tool_request_id="send_message",
        ),
    ]

    with patch_llm(
        llm,
        outputs=[
            multiple_tool_requests,  # output from manager agent (i.e. agent_with_client_tool)
            "fooza_answers_to_main_agent",
            "manager_answers_to_user",
        ],
    ):
        status = conv.execute()
        assert isinstance(status, ToolRequestStatus)  # yielding from manager
        assert len(status.tool_requests) == 1  # the send_message should not appear in the status
        assert status.tool_requests[0].name == "check_name_in_db_tool"
        status.submit_tool_result(
            ToolResult(
                content="The name Alice is present in the database", tool_request_id="client_tool"
            )
        )

        status_2 = conv.execute()
        assert isinstance(status_2, UserMessageRequestStatus)
        assert conv.get_last_message().content == "manager_answers_to_user"


def test_multiple_tool_calls_including_server_tool_can_be_executed(vllm_responses_llm):
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)

    group = ManagerWorkers(
        group_manager=fooza_agent,
        workers=[bwip_agent],
    )
    prompt = "Compute bwip(4,2) fooza(4,3) and bwip(4,5)"
    conv = group.start_conversation(messages=prompt)

    multiple_tool_requests = [
        ToolRequest(
            name="send_message",
            args={
                "recipient": "bwip_agent",
                "message": "calculate bwip(4,2)",
            },
        ),
        ToolRequest(
            name="fooza_tool",
            args={"a": 4, "b": 3},
        ),
        ToolRequest(
            name="send_message",
            args={
                "recipient": "bwip_agent",
                "message": "calculate bwip(4,5)",
            },
        ),
    ]
    with patch_llm(
        llm,
        outputs=[
            multiple_tool_requests,  # fooza's output
            "bwip answers to fooza",
            "bwip answers to second fooza call",
            "fooza answers to user",
        ],
    ):
        status = conv.execute()
        assert isinstance(status, UserMessageRequestStatus)
        messages = conv.get_messages()
        assert messages[0].content == prompt
        assert messages[1].tool_requests[0].name == "send_message"
        assert messages[1].tool_requests[0].args["recipient"] == "bwip_agent"
        assert messages[1].tool_requests[1].name == "fooza_tool"
        assert messages[1].tool_requests[2].name == "send_message"
        assert messages[1].tool_requests[2].args["recipient"] == "bwip_agent"
        assert messages[2].content == "bwip answers to fooza"
        assert messages[3].content == "16"  # Fooza tool
        assert messages[4].content == "bwip answers to second fooza call"
        assert messages[5].content == "fooza answers to user"


def test_multiple_tool_calls_including_with_nonexistent_tools(vllm_responses_llm):
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)

    group = ManagerWorkers(
        group_manager=fooza_agent,
        workers=[bwip_agent],
    )

    conv = group.start_conversation(messages="Compute bwip(4,2), fooza(4,3)")

    fooza_tool_requests = [
        ToolRequest(
            name="send_message",
            args={
                "recipient": "bwip_agent",
                "message": "calculate bwip(4,2)",
            },
        ),
        ToolRequest(
            name="fooza_tool",
            args={"a": 4, "b": 3},
        ),
    ]

    bwip_tool_requests = [
        ToolRequest(
            name="bwip_tool",
            args={"a": 4, "b": 2},
        ),
        ToolRequest(
            name="non_existent_tool",
            args={"a": 4, "b": 3},
        ),
    ]

    with patch_llm(
        llm,
        outputs=[
            fooza_tool_requests,
            bwip_tool_requests,
            "bwip answers to fooza",
            "fooza answers to user",
        ],
    ):
        status = conv.execute()
        assert isinstance(status, UserMessageRequestStatus)
        assert conv.get_last_message().content == "fooza answers to user"
        tool_result_messages = [
            m
            for m in conv.state.subconversations["bwip_agent"].get_messages()
            if m.tool_result is not None
        ]
        assert (
            "Tool named non_existent_tool is not in the list of available tools."
            in tool_result_messages[-1].tool_result.content
        )


@retry_test(max_attempts=5)
def test_managerworkers_can_do_multiple_tool_calling_when_appropriate(vllm_responses_llm):
    """
    Failure rate:          6 out of 50
    Observed on:           2026-05-17
    Average success time:  7.83 seconds per successful attempt
    Average failure time:  7.26 seconds per failed attempt
    Max attempt:           5
    Justification:         (0.13 ** 5) ~= 4.4 / 100'000
    """
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)

    # openai/gpt-oss-120b does not support native parallel tool calling,
    # so this test forces the legacy non-native manager prompt to exercise multiple tool-calling behavior.
    # See https://github.com/openai/harmony/issues/68
    group = ManagerWorkers(
        group_manager=llm,
        workers=[fooza_agent, bwip_agent, zbuk_agent],
        managerworkers_template=_DEFAULT_MANAGERWORKERS_CHAT_TEMPLATE,
        _add_talk_to_user_tool=False,
    )

    conv = group.start_conversation(
        messages="Compute the result of fooza(4, 2) + bwip(4, 5) + zbuk(5, 6). You should call multiple tools at once for this task."
    )

    conv.execute()

    expected_tool_requests = [
        ("send_message", {"recipient": "fooza_agent"}),
        ("send_message", {"recipient": "bwip_agent"}),
        ("send_message", {"recipient": "zbuk_agent"}),
    ]

    second_message = conv.get_messages()[1]

    assert len(second_message.tool_requests) == 3

    for tool_request, (expected_tool_name, expected_params) in zip(
        second_message.tool_requests,
        expected_tool_requests,
        strict=True,
    ):
        assert tool_request.name == expected_tool_name
        for k, v in expected_params.items():
            assert tool_request.args[k] == v

    assert "30" in conv.get_last_message().content


def _setup_managerworkers_for_multiple_tool_calling(vllm_responses_llm, raise_exceptions):
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(
        llm, raise_exception_tool=True, raise_exceptions=raise_exceptions
    )
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)

    group = ManagerWorkers(
        group_manager=fooza_agent,
        workers=[bwip_agent, zbuk_agent],
        _add_talk_to_user_tool=False,
    )

    conv = group.start_conversation(
        messages="Compute the result of fooza(4, 2) + bwip(4, 5) + zbuk(5, 6). You should call multiple tools at once for this task. If you are unable to obtain a complete result, return the partial result instead."
    )

    return conv


@retry_test(max_attempts=3)
def test_managerworkers_can_do_multiple_tool_calling_with_tool_raising_exception_raises_error(
    vllm_responses_llm,
):
    """
    Failure rate:          0 out of 50
    Observed on:           2026-05-17
    Average success time:  2.09 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    conv = _setup_managerworkers_for_multiple_tool_calling(
        vllm_responses_llm, raise_exceptions=True
    )
    with pytest.raises(ValueError, match="Cannot compute result using fooza tool."):
        conv.execute()


@retry_test(max_attempts=4)
def test_managerworkers_can_do_multiple_tool_calling_with_tool_raising_exception_does_not_raise_error(
    vllm_responses_llm,
):
    """
    Failure rate:          4 out of 50
    Observed on:           2026-05-17
    Average success time:  8.78 seconds per successful attempt
    Average failure time:  5.05 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.10 ** 4) ~= 8.5 / 100'000
    """
    conv = _setup_managerworkers_for_multiple_tool_calling(
        vllm_responses_llm, raise_exceptions=False
    )
    conv.execute()
    result = bwip_tool.func(4, 5) + zbuk_tool.func(5, 6)
    assert str(result) in conv.get_last_message().content


@retry_test(max_attempts=3)
def test_managerworkers_without_user_input_can_execute_as_expected(vllm_responses_llm):
    """
    Failure rate:          0 out of 50
    Observed on:           2026-05-15
    Average success time:  9.36 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)

    group = ManagerWorkers(
        group_manager=llm,
        workers=[fooza_agent, bwip_agent],
        output_descriptors=[
            IntegerProperty("result", description="The result of the user request")
        ],
        caller_input_mode=CallerInputMode.NEVER,
    )

    conv = group.start_conversation(messages="Compute the result of fooza(4, 2) + bwip(4, 5)")
    status = conv.execute()
    assert isinstance(status, FinishedStatus)

    assert status.output_values["result"] == 13


def test_two_level_managerworkers_with_mock_outputs(vllm_responses_llm):
    llm = vllm_responses_llm
    worker_1 = _get_bwip_agent(llm)
    sub_worker = _get_fooza_agent(llm)
    worker_2 = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a second-level manager. Use your worker fooza for related work.",
        ),
        workers=[sub_worker],
        name="worker_2",
        description="worker 2",
        _add_talk_to_user_tool=False,
    )
    group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a first-level manager. Use your workers for related computations.",
        ),
        workers=[worker_1, worker_2],
        name="first_level_group",
        description="First level group",
    )
    conv = group.start_conversation(messages="Compute the result of fooza(4, 2) and bwip(4,5)")
    ###
    ###
    ###          manager
    ###         |      |
    ###  worker_1     worker_2
    ###                   |
    ###               sub_worker
    ###
    with patch_llm(
        llm,
        outputs=[
            [
                ToolRequest(
                    name="send_message",
                    args={"recipient": "worker_2", "message": "calculate fooza(4,2)"},
                ),
                ToolRequest(
                    name="send_message",
                    args={"recipient": "bwip_agent", "message": "calculate bwip(4,5)"},
                ),
            ],  # multiple tool requests of first-level manager
            [
                ToolRequest(
                    name="send_message",
                    args={"recipient": "fooza_agent", "message": "calculate fooza(4,2)"},
                )
            ],  # tool request of the second-level manager
            [
                ToolRequest(name="fooza_tool", args={"a": 4, "b": 2})
            ],  # tool request of the subworker
            "fooza agent answers to second-level manager",
            "worker 2 (second-level manager) answers to first-level manager",
            [ToolRequest(name="bwip_tool", args={"a": 4, "b": 5})],
            "bwip agent answers to first-level manager",
            "first-level manager answers to user",
        ],
    ):
        status = conv.execute()
        assert isinstance(status, UserMessageRequestStatus)
        assert conv.get_last_message().content == "first-level manager answers to user"


@retry_test(max_attempts=3)
def test_two_level_managerworkers_with_llms(vllm_responses_llm):
    """
    Failure rate:          0 out of 50
    Observed on:           2026-05-17
    Average success time:  9.41 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    llm = vllm_responses_llm

    worker_1 = _get_bwip_agent(llm)

    sub_worker = _get_fooza_agent(llm)
    worker_2 = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a second-level manager. Use your worker fooza for related work.",
        ),
        workers=[sub_worker],
        name="worker_2",
        description="worker 2",
        _add_talk_to_user_tool=False,
    )

    group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a first-level manager. Use your workers for fooza and bwip for related computations.",
        ),
        workers=[worker_1, worker_2],
        name="first_level_group",
        description="First level group",
        _add_talk_to_user_tool=False,
    )

    conv = group.start_conversation(
        messages="Compute the result of fooza(4, 2) and add it with bwip(4,5)"
    )
    ###
    ###
    ###          manager
    ###         |      |
    ###  worker_1     worker_2
    ###                   |
    ###               sub_worker
    ###
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    ans = fooza_tool.func(4, 2) + bwip_tool.func(4, 5)
    assert str(ans) in conv.get_last_message().content


def test_three_level_managerworkers_with_mock_outputs(vllm_responses_llm):
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)

    third_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a third-level manager. Use your worker fooza for related work.",
        ),
        workers=[fooza_agent],
        name="third_level_group",
        description="Third level group",
    )
    second_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a second-level manager. Use your third-level group for related work.",
        ),
        workers=[third_level_group],
        name="second_level_group",
        description="Second level group",
    )
    first_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a first-level manager. Use your workers for related computations.",
        ),
        workers=[second_level_group, bwip_agent, zbuk_agent],
        name="first_level_group",
        description="First level group",
    )

    conv = first_level_group.start_conversation(
        messages="Compute the result of fooza(4, 2), bwip(4,5), and zbuk(5,6)"
    )
    ###
    ###
    ###              manager
    ###             |         |      |
    ### second_level_group  worker_1  worker_2
    ###        |
    ### third_level_group
    ###        |
    ###    sub_worker
    ###
    with patch_llm(
        llm,
        outputs=[
            [
                ToolRequest(
                    name="send_message",
                    args={"recipient": "second_level_group", "message": "calculate fooza(4,2)"},
                ),
                ToolRequest(
                    name="send_message",
                    args={"recipient": "bwip_agent", "message": "calculate bwip(4,5)"},
                ),
                ToolRequest(
                    name="send_message",
                    args={"recipient": "zbuk_agent", "message": "calculate zbuk(5,6)"},
                ),
            ],  # multiple tool requests of first-level manager
            [
                ToolRequest(
                    name="send_message",
                    args={"recipient": "third_level_group", "message": "calculate fooza(4,2)"},
                )
            ],  # tool request of the second-level manager
            [
                ToolRequest(
                    name="send_message",
                    args={"recipient": "fooza_agent", "message": "calculate fooza(4,2)"},
                )
            ],  # tool request of the third-level manager
            [ToolRequest(name="fooza_tool", args={"a": 4, "b": 2})],
            "fooza agent answers to third-level manager",
            "third-level manager answers to second-level manager",
            "second-level manager answers to first-level manager",
            [ToolRequest(name="bwip_tool", args={"a": 4, "b": 5})],
            "bwip agent answers to first-level manager",
            [ToolRequest(name="zbuk_tool", args={"a": 5, "b": 6})],
            "zbuk agent answers to first-level manager",
            "first-level manager answers to user",
        ],
    ):
        status = conv.execute()
        assert isinstance(status, UserMessageRequestStatus)
        assert conv.get_last_message().content == "first-level manager answers to user"


@retry_test(max_attempts=3)
def test_three_level_managerworkers_with_llms(vllm_responses_llm):
    """
    Failure rate:          0 out of 50
    Observed on:           2026-05-17
    Average success time:  14.77 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)

    third_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a third-level manager. Use your worker fooza for related work.",
        ),
        workers=[fooza_agent],
        name="third_level_group",
        description="Third level group",
        _add_talk_to_user_tool=False,
    )
    second_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a second-level manager. Use your third-level group for fooza related work.",
        ),
        workers=[third_level_group],
        name="second_level_group",
        description="Second level group",
        _add_talk_to_user_tool=False,
    )
    first_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a first-level manager. Use your workers for fooza, bwip, zbuk related computations.",
        ),
        workers=[second_level_group, bwip_agent, zbuk_agent],
        name="first_level_group",
        description="First level group",
        _add_talk_to_user_tool=False,
    )

    conv = first_level_group.start_conversation(
        messages="Compute the result of fooza(4, 2) and add it with bwip(4,5) and zbuk(5,6)"
    )
    ###
    ###
    ###              manager
    ###             |         |      |
    ### second_level_group  worker_1  worker_2
    ###        |
    ### third_level_group
    ###        |
    ###    sub_worker
    ###
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    ans = fooza_tool.func(4, 2) + bwip_tool.func(4, 5) + zbuk_tool.func(5, 6)
    assert str(ans) in conv.get_last_message().content


def test_linear_chain_managerworkers_with_mock_outputs(vllm_responses_llm):
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)

    # Linear chain: each level delegates to the next in a strict hierarchy
    third_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a third-level manager. Use your worker fooza for related work.",
        ),
        workers=[fooza_agent],
        name="third_level_group",
        description="Third level group",
    )
    second_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a second-level manager. Use your workers for related computations.",
        ),
        workers=[third_level_group, zbuk_agent],
        name="second_level_group",
        description="Second level group",
    )
    first_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a first-level manager. Use your workers for related computations.",
        ),
        workers=[second_level_group, bwip_agent],
        name="first_level_group",
        description="First level group",
    )

    conv = first_level_group.start_conversation(
        messages="Compute the result of fooza(4, 2), bwip(4,5), and zbuk(5,6)"
    )
    ###
    ###
    ###          manager
    ###             |
    ### second_level_group
    ###        |          |
    ### third_level_group  worker_2
    ###        |
    ###    worker_1
    ###
    with patch_llm(
        llm,
        outputs=[
            [
                ToolRequest(
                    name="send_message",
                    args={
                        "recipient": "second_level_group",
                        "message": "calculate fooza(4,2) and zbuk(5,6)",
                    },
                ),
                ToolRequest(
                    name="send_message",
                    args={"recipient": "bwip_agent", "message": "calculate bwip(4,5)"},
                ),
            ],  # tool requests of first-level manager
            [
                ToolRequest(
                    name="send_message",
                    args={"recipient": "third_level_group", "message": "calculate fooza(4,2)"},
                ),
                ToolRequest(
                    name="send_message",
                    args={"recipient": "zbuk_agent", "message": "calculate zbuk(5,6)"},
                ),
            ],  # tool requests of second-level manager
            [
                ToolRequest(
                    name="send_message",
                    args={"recipient": "fooza_agent", "message": "calculate fooza(4,2)"},
                )
            ],  # tool request of third-level manager
            [ToolRequest(name="fooza_tool", args={"a": 4, "b": 2})],
            "fooza agent answers to third-level manager",
            "third-level manager answers to second-level manager",
            [ToolRequest(name="zbuk_tool", args={"a": 5, "b": 6})],
            "zbuk agent answers to second-level manager",
            "second-level manager answers to first-level manager",
            [ToolRequest(name="bwip_tool", args={"a": 4, "b": 5})],
            "bwip agent answers to first-level manager",
            "first-level manager answers to user",
        ],
    ):
        status = conv.execute()
        assert isinstance(status, UserMessageRequestStatus)
        assert conv.get_last_message().content == "first-level manager answers to user"


@retry_test(max_attempts=3)
def test_linear_chain_managerworkers_with_llms(vllm_responses_llm):
    """
    Failure rate:          1 out of 50
    Observed on:           2026-05-17
    Average success time:  16.47 seconds per successful attempt
    Average failure time:  13.34 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000
    """
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)

    # Linear chain: each level delegates to the next in a strict hierarchy
    third_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a third-level manager. Use your worker fooza for related work.",
        ),
        workers=[fooza_agent],
        name="third_level_group",
        description="Third level group",
        _add_talk_to_user_tool=False,
    )
    second_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a second-level manager. Use your workers for fooza and zbuk related computations.",
        ),
        workers=[third_level_group, zbuk_agent],
        name="second_level_group",
        description="Second level group",
        _add_talk_to_user_tool=False,
    )
    first_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are a first-level manager. Use your workers for fooza, bwip, zbuk related computations.",
        ),
        workers=[second_level_group, bwip_agent],
        name="first_level_group",
        description="First level group",
        _add_talk_to_user_tool=False,
    )

    conv = first_level_group.start_conversation(
        messages="Compute the result of fooza(4, 2) and add it with bwip(4,5) and zbuk(5,6)"
    )
    ###
    ###
    ###          manager
    ###             |
    ### second_level_group
    ###        |          |
    ### third_level_group  worker_2
    ###        |
    ###    worker_1
    ###
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    ans = fooza_tool.func(4, 2) + bwip_tool.func(4, 5) + zbuk_tool.func(5, 6)
    assert str(ans) in conv.get_last_message().content


def test_multi_managers_with_mock_outputs(vllm_responses_llm):
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)

    # Two second-level managers, each with their own workers
    second_level_group_1 = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are second level group 1 manager. Use your worker fooza for related work.",
        ),
        workers=[fooza_agent],
        name="second_level_group_1",
        description="Second level group 1",
    )
    second_level_group_2 = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are second level group 2 manager. Use your workers bwip and zbuk for related work.",
        ),
        workers=[bwip_agent, zbuk_agent],
        name="second_level_group_2",
        description="Second level group 2",
    )
    first_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are first level group manager. Use your workers second level group 1 and group 2 managers for related work.",
        ),
        workers=[second_level_group_1, second_level_group_2],
        name="first_level_group",
        description="First level group",
    )

    conv = first_level_group.start_conversation(
        messages="Compute the result of fooza(4, 2), bwip(4,5), and zbuk(5,6)"
    )
    ###
    ###
    ###                manager
    ###                |        |
    ### second_level_group_1  second_level_group_2
    ###         |                  |        |
    ###     worker_1             worker_2  worker_3
    ###
    with patch_llm(
        llm,
        outputs=[
            [
                ToolRequest(
                    name="send_message",
                    args={"recipient": "second_level_group_1", "message": "calculate fooza(4,2)"},
                ),
                ToolRequest(
                    name="send_message",
                    args={
                        "recipient": "second_level_group_2",
                        "message": "calculate bwip(4,5) and zbuk(5,6)",
                    },
                ),
            ],  # multiple tool requests of first-level manager
            [
                ToolRequest(
                    name="send_message",
                    args={"recipient": "fooza_agent", "message": "calculate fooza(4,2)"},
                )
            ],  # tool request of second-level manager 1
            [ToolRequest(name="fooza_tool", args={"a": 4, "b": 2})],
            "fooza agent answers to second-level manager 1",
            "second-level manager 1 answers to first-level manager",
            [
                ToolRequest(
                    name="send_message",
                    args={"recipient": "bwip_agent", "message": "calculate bwip(4,5)"},
                ),
                ToolRequest(
                    name="send_message",
                    args={"recipient": "zbuk_agent", "message": "calculate zbuk(5,6)"},
                ),
            ],  # tool requests of second-level manager 2
            [ToolRequest(name="bwip_tool", args={"a": 4, "b": 5})],
            "bwip agent answers to second-level manager 2",
            [ToolRequest(name="zbuk_tool", args={"a": 5, "b": 6})],
            "zbuk agent answers to second-level manager 2",
            "second-level manager 2 answers to first-level manager",
            "first-level manager answers to user",
        ],
    ):
        status = conv.execute()
        assert isinstance(status, UserMessageRequestStatus)
        assert conv.get_last_message().content == "first-level manager answers to user"


@retry_test(max_attempts=3)
def test_multi_managers_with_llms(vllm_responses_llm):
    """
    Failure rate:          1 out of 50
    Observed on:           2026-05-17
    Average success time:  15.03 seconds per successful attempt
    Average failure time:  2.31 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000
    """
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)

    # Two second-level managers, each with their own workers
    second_level_group_1 = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are second level group 1 manager. Use your worker fooza for related work.",
        ),
        workers=[fooza_agent],
        name="second_level_group_1",
        description="Second level group 1",
        _add_talk_to_user_tool=False,
    )
    second_level_group_2 = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are second level group 2 manager. Use your workers bwip and zbuk for related work.",
        ),
        workers=[bwip_agent, zbuk_agent],
        name="second_level_group_2",
        description="Second level group 2",
        _add_talk_to_user_tool=False,
    )
    first_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction="You are first level group manager. Use your workers second level group 1 for fooza and group 2 managers for bwip and zbuk related work.",
        ),
        workers=[second_level_group_1, second_level_group_2],
        name="first_level_group",
        description="First level group",
        _add_talk_to_user_tool=False,
    )

    conv = first_level_group.start_conversation(
        messages="Compute the result of fooza(4, 2) and add it with bwip(4,5) and zbuk(5,6)"
    )
    ###
    ###
    ###                manager
    ###                |        |
    ### second_level_group_1  second_level_group_2
    ###         |                  |        |
    ###     worker_1             worker_2  worker_3
    ###
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    ans = fooza_tool.func(4, 2) + bwip_tool.func(4, 5) + zbuk_tool.func(5, 6)
    assert str(ans) in conv.get_last_message().content
