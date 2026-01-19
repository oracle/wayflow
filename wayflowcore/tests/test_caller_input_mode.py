# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from typing import List, Optional, Tuple

import pytest

from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors._agentexecutor import (
    _TALK_TO_USER_TOOL_NAME,
    EXIT_CONVERSATION_CONFIRMATION_MESSAGE,
)
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.steps import AgentExecutionStep
from wayflowcore.tools import ClientTool, ServerTool, Tool

from .testhelpers.testhelpers import retry_test

logging.basicConfig(level=logging.INFO)

NO_CALLER_REMINDER_MESSAGE = (
    "The user is busy... continue if needed or exit the conversation if the task is completed."
)


def get_increment_counter_tool() -> ServerTool:

    class IncrementCounterTool:
        def __init__(self, desired_number: int = 2):
            self.counter = 0
            self.desired_number = desired_number

        def is_completed(self) -> bool:
            return self.counter >= self.desired_number

        def __call__(self) -> str:
            self.counter += 1
            if self.counter >= self.desired_number:
                return f"Reached the desired number!"
            return f"Counter is now {self.counter}. Desired number not reached yet."

    return ServerTool(
        name="increment_counter",
        description="increment the counter and notify if desired number is reached or not. No input parameters",
        parameters={},
        output={"type": "string"},
        func=IncrementCounterTool(),
    )


def _get_creative_assistant(
    llm: VllmModel,
    custom_instructions: str,
    tools: List[Tool],
    max_no_caller_mode_reminders: int,
    caller_input_mode: CallerInputMode,
    no_caller_reminder_message: Optional[str] = None,
) -> Flow:

    agent = Agent(
        llm=llm,
        tools=tools,
        custom_instruction=custom_instructions,
        max_iterations=5,
        caller_input_mode=caller_input_mode,
        can_finish_conversation=True,
    )
    agent_execution_step = AgentExecutionStep(agent=agent)

    return Flow(
        begin_step=agent_execution_step,
        steps={"creative_step": agent_execution_step},
        control_flow_edges=[
            ControlFlowEdge(source_step=agent_execution_step, destination_step=None),
        ],
    )


def _get_test_iterator_assistant(
    llm: VllmModel,
    caller_input_mode: CallerInputMode,
) -> Tuple[ServerTool, Flow]:
    increment_tool = get_increment_counter_tool()
    assistant = _get_creative_assistant(
        llm=llm,
        custom_instructions="""You are a helpful iterator Assistant, tasked with \
incrementing numbers until a desired number is reached. The desired number is hidden \
to you, but you will be notified when you reach it.
To solve the task, you must increment the counter using the tool increment_counter.
Once you have reached this number, you can end the conversation.""",
        tools=[increment_tool],
        caller_input_mode=caller_input_mode,
        max_no_caller_mode_reminders=2,
        no_caller_reminder_message=NO_CALLER_REMINDER_MESSAGE,
    )
    return increment_tool, assistant


@retry_test(max_attempts=6, wait_between_tries=1)
def test_assistant_in_caller_mode_never(remotely_hosted_llm: VllmModel) -> None:
    """
    Failure rate:          8 out of 50
    Observed on:           2025-05-06
    Average success time:  5.25 seconds per successful attempt
    Average failure time:  5.94 seconds per failed attempt
    Max attempt:           6
    Justification:         (0.16 ** 6) ~= 1.1 / 100'000
    """
    increment_tool, assistant = _get_test_iterator_assistant(
        remotely_hosted_llm, caller_input_mode=CallerInputMode.NEVER
    )

    conversation = assistant.start_conversation()
    conversation.append_user_message(
        "Iterate the counter until task completion. Exit as soon as you reach the number"
    )

    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    messages = conversation.get_messages()
    assert increment_tool.func.is_completed()  # reached the final number
    assert any(
        EXIT_CONVERSATION_CONFIRMATION_MESSAGE in msg.content for msg in messages
    )  # at least tried to exit the conversation


@retry_test(max_attempts=3, wait_between_tries=1)
def test_assistant_in_caller_mode_always(remotely_hosted_llm: VllmModel) -> None:
    """
    Failure rate:          0 out of 50
    Observed on:           2024-12-17
    Average success time:  7.14 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    increment_tool, assistant = _get_test_iterator_assistant(
        remotely_hosted_llm, caller_input_mode=CallerInputMode.ALWAYS
    )

    conversation = assistant.start_conversation()
    conversation.append_user_message(
        "The initial counter value is 0, please iterate the counter until the desired number is reached."
    )

    max_turns = 3
    current_turn = 0
    while current_turn < max_turns:
        status = conversation.execute()
        if isinstance(status, FinishedStatus):
            break
        conversation.append_user_message(
            "continue until task is completed, then use the tool to exit the conversation"
        )
        current_turn += 1
    status = conversation.execute()

    messages = conversation.get_messages()

    assert increment_tool.func.is_completed()  # reached the final number
    assert (
        any(NO_CALLER_REMINDER_MESSAGE in msg.content for msg in messages) == False
    )  # should NOT have triggered the NO_CALLER_REMINDER_MESSAGE message
    assert any(
        EXIT_CONVERSATION_CONFIRMATION_MESSAGE in msg.content for msg in messages
    )  # at least tried to exit the conversation


def test_agent_raises_when_passing_talk_to_user_tool_when_callerinputmode_is_set_to_never(
    remotely_hosted_llm: VllmModel,
) -> None:
    llm = remotely_hosted_llm
    talk_to_user_tool = ClientTool(
        name=_TALK_TO_USER_TOOL_NAME,
        description="desc",
        input_descriptors=[],
    )

    with pytest.raises(
        ValueError,
        match=f"Caller input mode is set to 'NEVER' but found a tool with name {_TALK_TO_USER_TOOL_NAME}. Make sure to not pass any tool with this name.",
    ):
        _ = Agent(
            llm=llm,
            tools=[talk_to_user_tool],
            caller_input_mode=CallerInputMode.NEVER,
            custom_instruction="A random custom instruction. If custom instruction is not provided, an earlier exception will appear.",
        )
