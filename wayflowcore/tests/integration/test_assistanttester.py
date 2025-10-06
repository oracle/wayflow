# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import random
from typing import Any, Callable, Dict, List, Optional

import pytest

from wayflowcore import Agent
from wayflowcore.contextproviders.constantcontextprovider import ConstantContextProvider
from wayflowcore.evaluation import HumanProxyAssistant
from wayflowcore.evaluation.assistantevaluator import (
    _SCRIPTED_TOOL_CRASH_MESSAGE,
    _get_agent_messages,
    _get_last_agent_message,
)
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.property import Property, StringProperty
from wayflowcore.steps import AgentExecutionStep
from wayflowcore.steps.step import Step
from wayflowcore.tools import ToolRequest, ToolResult, tool

from ..testhelpers.assistanttester import AssistantTester
from ..testhelpers.dummy import DummyModel


def make_sequential_assistant_with_context_provider(
    steps: List[Step], verbose: bool = False, loop: bool = False
) -> Flow:
    context_provider = ConstantContextProvider(
        value="",
        output_description=StringProperty(
            "context",
            "The context about files, the data models, ui and authentication",
        ),
    )
    return Flow.from_steps(steps=steps, loop=loop, context_providers=[context_provider])


def get_weather_assistant(
    llm: DummyModel,
    trigger: bool = False,
    with_tools: bool = True,
    system_prompt: None = None,
    context_prompt: None = None,
    current_task_prompt: None = None,
) -> Flow:
    @tool(description_mode="only_docstring")
    def get_weather(location: Optional[str] = None) -> str:
        """Get the weather for the given specified location"""
        if location and "zurich" in location.lower():
            return "wintry"
        return random.choice(["sunny", "cloudy", "windy"])  # nosec

    @tool(description_mode="only_docstring")
    def get_largest_city(country: str) -> str:
        """Get the largest city of the specified country"""
        country = country.lower()
        if country == "switzerland":
            return "zurich"
        if country == "france":
            return "paris"
        if country == "china":
            return "beijing"
        if country == "algeria":
            return "algiers"
        return "unknown"

    agent = Agent(
        llm=llm,
        tools=[get_weather, get_largest_city] if with_tools else None,
        custom_instruction=system_prompt,
    )
    step = AgentExecutionStep(
        agent=agent,
    )

    context_providers = {}
    if current_task_prompt is not None:
        context_providers[StringProperty("current_task", "The current task about the weather")] = (
            lambda conversation: current_task_prompt
        )
    if context_prompt is not None:
        context_providers[StringProperty("context", "The context about the weather")] = (
            lambda conversation: context_prompt
        )
    return create_single_step_flow(
        step, step_name="single_step", context_providers=context_providers
    )


DUMMY_MODEL = DummyModel()
DUMMY_MODEL.output = "Weather in Zurich"


def test_assistant_tester_throws_with_invalid_pass_threshold() -> None:
    assistant = get_weather_assistant(DUMMY_MODEL)

    tester = AssistantTester(
        assistant_under_test=assistant,
        human_proxy=None,
        init_human_messages=[],
        required_checks=None,
        max_rounds=0,  # max_rounds=0 means only init_human_messages are used and human_proxy is not used
    )

    with pytest.raises(ValueError):
        tester.run_test(N=1, pass_threshold=1.1)

    with pytest.raises(ValueError):
        tester.run_test(N=1, pass_threshold=-0.1)


def test_weather_script_can_run_without_human_proxy() -> None:
    assistant = get_weather_assistant(DUMMY_MODEL)

    scripted_messages = [
        "Tell me the weather in the largest city in Switzerland.",
    ]

    def outcome_check(assistant, agent_conv, proxy_conv):
        """Checks that the agent generated "Zurich" and that the proxy was not called"""
        return (
            "Zurich" in _get_last_agent_message(agent_conv).content
            and proxy_conv is None  # since we do not pass a human_proxy
        )

    tester = AssistantTester(
        assistant_under_test=assistant,
        human_proxy=None,
        init_human_messages=scripted_messages,
        required_checks=[outcome_check],
        max_rounds=0,  # max_rounds=0 means only init_human_messages are used and human_proxy is not used
    )
    accuracy, report = tester.run_test(N=3, pass_threshold=0.6)

    assert all(
        report["is_scripted_round"].tolist()[:-1]
    )  # :-1 because the last row is nan (it's not a round)


def get_weather_human_proxy(llm: DummyModel) -> HumanProxyAssistant:
    return HumanProxyAssistant(
        llm=llm,
        system_prompt="""You are pretending to be a Human, and your goal is to interact with an AI chatbot to try to complete a task.
The AI only has only *one* attempt to give you the answer. That is, you *must not* allow it to try again.
As an expert, you know that the AI completes the task if its answer contains the word 'wintry'. That's it, nothing else matters. \
In this case, you must write '<ENDED>' to finish the conversation.
Otherwise, if its first response does not contain the word 'wintry', \
you must write '<FAILED>' to indicate that the chatbot failed to complete the task.""",
    )


def get_weather_tester(
    assistant: Flow,
    human_proxy: HumanProxyAssistant,
    checks: List[Callable],
    max_rounds: int = 5,
) -> AssistantTester:
    return AssistantTester(
        assistant_under_test=assistant,
        human_proxy=human_proxy,
        init_human_messages=[
            (
                "Tell me the weather in the largest city in Switzerland. "
                "You only have one attempt to give me the correct answer, otherwise you fail this task. "
                "Your attempt begins now."
            ),
        ],
        required_checks=checks,
        max_rounds=max_rounds,
    )


def test_assistanttester_correctly_returns_success_when_outcome_checks_succeed(
    success_rate: float = 0.4,
) -> None:
    human_proxy = get_weather_human_proxy(DUMMY_MODEL)
    assistant = get_weather_assistant(DUMMY_MODEL, with_tools=True)

    outcome_check = lambda assistant, agent_conv, proxy_conv: True

    tester = get_weather_tester(assistant, human_proxy, [outcome_check], max_rounds=0)

    accuracy, report = tester.run_test(N=2, pass_threshold=success_rate)


def test_assistanttester_correctly_returns_failure_when_outcome_checks_fail() -> None:
    human_proxy = get_weather_human_proxy(DUMMY_MODEL)
    assistant = get_weather_assistant(DUMMY_MODEL, with_tools=False)

    outcome_check = lambda assistant, agent_conv, proxy_conv: False

    tester = get_weather_tester(assistant, human_proxy, [outcome_check])

    # set threshold = 0.0 so that it does not raise the low accuracy error
    accuracy, report = tester.run_test(N=2, pass_threshold=0.0)

    assert (
        accuracy == 0.0
    ), f"test should not pass since outcome checks failed but got non-zero {accuracy=}"

    # set threshold=1.0 to check that the run_test raises an error if accuracy is lower than threshold
    with pytest.raises(ValueError):
        accuracy, report = tester.run_test(N=2, pass_threshold=1.0)


class NonStringableObject:
    msg = "Intentional error: This object cannot be converted to a string."

    def __str__(self):
        raise TypeError(self.msg)

    def __repr__(self) -> str:
        raise TypeError(self.msg)


class _AssistantTesterExceptionStep(Step):
    def __init__(self) -> None:
        super().__init__(step_static_configuration={})

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls, *args: Any, **kwargs: Any
    ) -> List[Property]:
        return []

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls, *args: Any, **kwargs: Any
    ) -> List[Property]:
        return []

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls, *args: Any, **kwargs: Any
    ) -> Dict[str, type]:
        return {}

    def _invoke_step(self, *args: Any, **kwargs: Any):
        raise ValueError("Exception!!!")


def test_assistanttester_can_handle_assistant_tool_crash(remotely_hosted_llm: VllmModel) -> None:
    """Tests the looping logic of AgentExecutionStep and AssistantTester.
    If this test fails, the looping logic has been changed.
    """

    step = _AssistantTesterExceptionStep()

    assistant = make_sequential_assistant_with_context_provider([step])

    tester = AssistantTester(
        assistant_under_test=assistant,
        human_proxy=None,
        init_human_messages=[
            "Get me the weather of Paris. Let's think step by step.",
        ],
        required_checks=None,
    )
    accuracy, report = tester.run_test(N=2, pass_threshold=0.0, only_agent_msg_type=False)

    assert (
        accuracy == 0.0
    ), f"test should not pass since exceptions were encountered but got non-zero {accuracy=}"

    # if an exception was encountered, the row with the error message is always -2
    # i.e. second-to-last, as the last row only contains outcome check results
    errors = [e[-2] for e in report.groupby("seed")["error"].apply(list).tolist()]
    for e in errors:
        assert e is not None and ("Exception!!!" in e)


def test_get_agent_messages() -> None:
    fake_messages = [
        Message(content="Please get the current temperature", message_type=MessageType.USER),
        Message(content="Sure, I can do that", message_type=MessageType.AGENT),
        Message(
            content="I will call get_temp to get the temperature",
            message_type=MessageType.TOOL_REQUEST,
            tool_requests=[ToolRequest("get_temp", {"location": "Zug"}, "tc1")],
        ),
        Message(
            message_type=MessageType.TOOL_RESULT,
            tool_result=ToolResult(
                tool_request_id="tc1",
                content="23C",
            ),
        ),
    ]

    # Test 1: only extract AGENT messages
    new_agent_messages, current_len = _get_agent_messages(
        chat_history=fake_messages,
        prev_len=1,  # length before invoking agent
        only_agent_msg_type=True,
    )
    assert len(new_agent_messages) == 2 and current_len == 4
    assert new_agent_messages[0] == fake_messages[1].content

    # Test 2: extract AGENT and TOOL_REQUEST but not TOOL_RESULT messages
    new_agent_messages, current_len = _get_agent_messages(
        chat_history=fake_messages, prev_len=1, only_agent_msg_type=False
    )
    assert len(new_agent_messages) == 3 and current_len == 4
    assert (
        new_agent_messages[0] == fake_messages[1].content
        and new_agent_messages[1] == fake_messages[2].content
    )


def test_get_agent_messages_throws_error_when_no_new_agent_messages() -> None:
    fake_messages = [
        Message(content="Please get the current temperature", message_type=MessageType.USER),
        Message(content="Sure, I can do that", message_type=MessageType.AGENT),
        Message(content="Do it now", message_type=MessageType.USER),
        # _get_agent_messages is called after calling assistant.execute(assistant_conv)
        # so it should always have new messages from the agent, including thoughts and tool calls
    ]

    with pytest.raises(ValueError):
        new_agent_messages, current_len = _get_agent_messages(
            chat_history=fake_messages, prev_len=3, only_agent_msg_type=True
        )


def test_get_agent_messages_returns_scripted_message_when_no_new_agent_message() -> None:
    fake_messages = [
        Message(content="Please get the current temperature", message_type=MessageType.USER),
        Message(content="Sure, I can do that", message_type=MessageType.AGENT),
        Message(content="Do it now", message_type=MessageType.USER),
        Message(content="I have no idea what I should do", message_type=MessageType.THOUGHT),
    ]
    new_agent_messages, current_len = _get_agent_messages(
        chat_history=fake_messages, prev_len=3, only_agent_msg_type=True
    )
    assert len(new_agent_messages) == 1 and current_len == 4
    assert new_agent_messages[0] == _SCRIPTED_TOOL_CRASH_MESSAGE


def test_get_agent_messages_returns_scripted_message_when_tool_request_is_empty() -> None:
    fake_messages = [
        Message(content="Please get the current temperature", message_type=MessageType.USER),
        Message(content="Sure, I can do that", message_type=MessageType.AGENT),
        Message(content="Do it now", message_type=MessageType.USER),
        Message(
            content="",
            message_type=MessageType.TOOL_REQUEST,
            tool_requests=[ToolRequest("get_temp", {"location": "Zug"}, "tc1")],
        ),
    ]
    new_agent_messages, current_len = _get_agent_messages(
        chat_history=fake_messages, prev_len=3, only_agent_msg_type=False
    )
    assert len(new_agent_messages) == 1 and current_len == 4
    assert new_agent_messages[0] == _SCRIPTED_TOOL_CRASH_MESSAGE
