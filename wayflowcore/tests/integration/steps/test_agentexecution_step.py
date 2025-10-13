# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.from unittest.mock import patch
from unittest.mock import patch

import pytest
from pytest import fixture

from wayflowcore import Message, MessageType
from wayflowcore.agent import Agent, _MutatedAgent
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow, run_flow_and_return_outputs
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.property import IntegerProperty, Property
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep, CallerInputMode
from wayflowcore.steps.outputmessagestep import OutputMessageStep
from wayflowcore.tools import ClientTool, ToolRequest

from ...testhelpers.dummy import DummyModel
from ...testhelpers.testhelpers import retry_test
from ..test_agent import (  # noqa
    agent_with_yielding_subflow,
    run_test_agent_can_call_client_tool_with_no_parameter,
)
from ..test_agentcomposability import zinimo_tool
from ..test_assistanttester import make_sequential_assistant_with_context_provider


@fixture
def zinimo_agent(remotely_hosted_llm):
    return Agent(
        llm=remotely_hosted_llm,
        custom_instruction=(
            "You should ask the user for 2 numbers, compute their zinimo operation, "
            "and submit the tool result to the user using the `submit_result` function (and not as a agent message). "
            "IMPORTANT: Never make up arguments, ask the user if you have a question. "
            "Only output a single function call at a time if needed."
        ),
        tools=[zinimo_tool],
        initial_message=None,
    )


zinimo_result_description = IntegerProperty(
    name="zinimo_result",
    description="result of the zinimo operation of the two provided integers",
    default_value=0,
)


@pytest.mark.parametrize(
    "outputs",
    [
        None,
        [],
    ],
)
def test_agent_step_raises_when_outputs_are_not_properly_configured(outputs, zinimo_agent):
    with pytest.raises(ValueError):
        AgentExecutionStep(
            agent=zinimo_agent, caller_input_mode=CallerInputMode.NEVER, output_descriptors=outputs
        )


def run_zinimo(agent: Agent, output: Property):
    # hack to only enable a single round
    with _MutatedAgent(agent=agent, attributes=dict(max_iterations=2)) as agent:

        step = AgentExecutionStep(
            agent=agent,
            output_descriptors=[output],
            caller_input_mode=CallerInputMode.NEVER,
        )
        flow = create_single_step_flow(step)
        outputs = run_flow_and_return_outputs(flow)
        assert "zinimo_result" in outputs
        assert outputs["zinimo_result"] == 10


@retry_test(max_attempts=3)
def test_basic_agent_execution_step_without_user_input(zinimo_agent):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-01-15
    Average success time:  2.93 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    step = AgentExecutionStep(
        agent=zinimo_agent,
        output_descriptors=[zinimo_result_description],
        caller_input_mode=CallerInputMode.NEVER,
    )
    flow = create_single_step_flow(step)
    conv = flow.start_conversation()
    conv.append_user_message("between 2 and 5")
    status = flow.execute(conv)
    assert isinstance(status, FinishedStatus)
    assert "zinimo_result" in status.output_values
    assert status.output_values["zinimo_result"] == -2


@retry_test(max_attempts=3)
def test_basic_agent_execution_step_with_step_inputs(remotely_hosted_llm):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-01-28
    Average success time:  3.06 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    zinimo_agent_with_inputs = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="Compute the result of zinimo({{a}}, {{b}}) and submit it to the user using the `submit_result` function. IMPORTANT: Never make up arguments, ask the user if you have a question. Only output a single function call at a time if needed",
        tools=[zinimo_tool],
        initial_message=None,
    )
    step = AgentExecutionStep(
        agent=zinimo_agent_with_inputs,
        output_descriptors=[zinimo_result_description],
        caller_input_mode=CallerInputMode.NEVER,
    )
    flow = create_single_step_flow(step)
    outputs = run_flow_and_return_outputs(flow, inputs={"a": "2", "b": "5"})
    assert outputs["zinimo_result"] == -2


@retry_test(max_attempts=3)
def test_basic_agent_execution_step_with_user_input(zinimo_agent):
    """
    Failure rate:          0 out of 40
    Observed on:           2025-04-17
    Average success time:  5.22 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 1.3 / 100'000
    """
    step = AgentExecutionStep(
        agent=zinimo_agent,
        output_descriptors=[zinimo_result_description],
        caller_input_mode=CallerInputMode.ALWAYS,
    )

    flow = create_single_step_flow(step)
    conv = flow.start_conversation()
    conv.append_user_message("hi, can you help me compute the result of the zinimo operation?")
    status = flow.execute(conv)
    assert isinstance(status, UserMessageRequestStatus)
    conv.append_user_message("2")
    status = flow.execute(conv)
    assert isinstance(status, UserMessageRequestStatus)
    conv.append_user_message("5")
    status = flow.execute(conv)
    assert isinstance(status, FinishedStatus)
    assert "zinimo_result" in status.output_values
    assert status.output_values["zinimo_result"] == -2


@retry_test(max_attempts=4)
@pytest.mark.parametrize(
    "message_with_secret, user_question, expected_secret",
    [
        ("The secret code is GL0B4L", "Please repeat the secret code again", "GL0B4L"),
        ("The robot's name is Wall33", "Please repeat the robot's name again", "Wall33"),
        ("The CEO's nickname is Jack", "Please repeat the CEO's nickname again", "Jack"),
        ("The secret code is X-TERMINATE", "Please repeat the secret code again", "X-TERMINATE"),
        ("The chosen game is Chess", "Tell me again what is the chosen game", "Chess"),
    ],
)
@pytest.mark.parametrize("display_mode_only", [True, False])
def test_agent_executor_step_can_read_previous_messages(
    remotely_hosted_llm, message_with_secret, user_question, expected_secret, display_mode_only
):
    """
    (Test case 1)
            Failure rate:          0 out of 10
            Observed on:           2025-03-03
            Average success time:  1.59 seconds per successful attempt
            Average failure time:  No time measurement
            Max attempt:           4
            Justification:         (0.08 ** 4) ~= 4.8 / 100'000

    (Test case 2)
            Failure rate:          0 out of 10
            Observed on:           2025-03-03
            Average success time:  1.60 seconds per successful attempt
            Average failure time:  No time measurement
            Max attempt:           4
            Justification:         (0.08 ** 4) ~= 4.8 / 100'000

    (Test case 3)
            Failure rate:          0 out of 10
            Observed on:           2025-03-03
            Average success time:  1.57 seconds per successful attempt
            Average failure time:  No time measurement
            Max attempt:           4
            Justification:         (0.08 ** 4) ~= 4.8 / 100'000

    (Test case 4)
            Failure rate:          0 out of 10
            Observed on:           2025-03-03
            Average success time:  1.57 seconds per successful attempt
            Average failure time:  No time measurement
            Max attempt:           4
            Justification:         (0.08 ** 4) ~= 4.8 / 100'000

    (Test case 5)
            Failure rate:          0 out of 10
            Observed on:           2025-03-03
            Average success time:  1.82 seconds per successful attempt
            Average failure time:  No time measurement
            Max attempt:           4
            Justification:         (0.08 ** 4) ~= 4.8 / 100'000

    (Test case 6)
            Failure rate:          0 out of 10
            Observed on:           2025-03-03
            Average success time:  1.23 seconds per successful attempt
            Average failure time:  No time measurement
            Max attempt:           4
            Justification:         (0.08 ** 4) ~= 4.8 / 100'000

    (Test case 7)
            Failure rate:          0 out of 10
            Observed on:           2025-03-03
            Average success time:  1.31 seconds per successful attempt
            Average failure time:  No time measurement
            Max attempt:           4
            Justification:         (0.08 ** 4) ~= 4.8 / 100'000

    (Test case 8)
            Failure rate:          1 out of 10
            Observed on:           2025-03-03
            Average success time:  1.63 seconds per successful attempt
            Average failure time:  1.66 seconds per failed attempt
            Max attempt:           6
            Justification:         (0.17 ** 6) ~= 2.1 / 100'000

    (Test case 9)
            Failure rate:          0 out of 10
            Observed on:           2025-03-03
            Average success time:  1.29 seconds per successful attempt
            Average failure time:  No time measurement
            Max attempt:           4
            Justification:         (0.08 ** 4) ~= 4.8 / 100'000

    (Test case 10)
            Failure rate:          0 out of 10
            Observed on:           2025-03-03
            Average success time:  1.26 seconds per successful attempt
            Average failure time:  No time measurement
            Max attempt:           4
            Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    agent = Agent(
        llm=remotely_hosted_llm,
        caller_input_mode=CallerInputMode.ALWAYS,
        custom_instruction="Please help me with my tasks.",
        initial_message=None,
    )
    output_step = OutputMessageStep(
        message_with_secret,
        message_type=MessageType.DISPLAY_ONLY if display_mode_only else MessageType.AGENT,
    )
    flow = Flow.from_steps([output_step, AgentExecutionStep(agent)])
    conv = flow.start_conversation()
    conv.append_user_message(user_question)
    with patch(
        "wayflowcore.models.llmmodel.LlmModel.stream_generate_async",
        side_effect=remotely_hosted_llm.stream_generate_async,
    ) as mock:
        status = conv.execute()
        args, kwargs = mock.call_args
        if display_mode_only:
            assert message_with_secret not in str(args)
        else:
            assert message_with_secret in str(args)


def test_agent_only_uses_max_iterations_in_total_during_agent_execution_step(remotely_hosted_llm):

    agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="Your goal is to 1. compute some zinimo operation 2. submit the result to the user using the `submit_result` function. IMPORTANT: Only output a single function call at a time",
        tools=[zinimo_tool],
        max_iterations=4,
        initial_message=None,
    )
    step = AgentExecutionStep(
        agent=agent,
        output_descriptors=[zinimo_result_description],
        caller_input_mode=CallerInputMode.NEVER,
    )

    dummy_llm = DummyModel()
    dummy_llm.set_next_output(
        [
            "what are numbers a and b?",
            Message(
                message_type=MessageType.TOOL_REQUEST,
                tool_requests=[
                    ToolRequest(
                        name="zinimo_tool",
                        args={"a": 1, "b": 2},
                        tool_request_id="some_id_whatever",
                    )
                ],
            ),
            "what are numbers a and b?",
            "what are numbers a and b?",
        ]
    )
    step.agent.llm = dummy_llm

    flow = create_single_step_flow(step)
    conv = flow.start_conversation()
    status = flow.execute(conv)
    assert isinstance(status, FinishedStatus)
    assert dummy_llm.output is None  # all generations used
    assert len([m for m in conv.get_messages() if "I'm not available" in m.content]) == 3


@retry_test(max_attempts=7)
@pytest.mark.parametrize(
    "user_question, expected_answer",
    [
        ("What is the result of the multiplication 13 x 4?", "52"),
        ("What is a regular polygon with 6 equal sides called?", "hexagon"),
        ("How much is a right angle in degrees?", "90"),
        ("What are all the countries around Switzerland?", "germany"),
    ],
)
def test_agentexecutionstep_without_tool_helpfully_answers_basic_questions(
    remotely_hosted_llm, user_question, expected_answer
):
    """
    (Test case 1)
    Failure rate:          24 out of 100
    Observed on:           2025-05-09
    Average success time:  0.33 seconds per successful attempt
    Average failure time:  0.46 seconds per failed attempt
    Max attempt:           7
    Justification:         (0.25 ** 7) ~= 5.3 / 100'000

    (Test case 2)
    Failure rate:          1 out of 100
    Observed on:           2025-05-09
    Average success time:  0.35 seconds per successful attempt
    Average failure time:  0.52 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.8 / 100'000

    (Test case 3)
    Failure rate:          2 out of 100
    Observed on:           2025-05-09
    Average success time:  0.28 seconds per successful attempt
    Average failure time:  0.31 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 2.5 / 100'000

    (Test case 4)
    Failure rate:          4 out of 100
    Observed on:           2025-05-09
    Average success time:  0.34 seconds per successful attempt
    Average failure time:  0.44 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.05 ** 4) ~= 0.6 / 100'000

    (Test case 5)
    Failure rate:          1 out of 100
    Observed on:           2025-05-09
    Average success time:  0.46 seconds per successful attempt
    Average failure time:  1.36 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.8 / 100'000
    """
    agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="As an expert in the sciences, you concisely and directly answer the user questions about maths and geography.",
        can_finish_conversation=True,
    )
    agent_execution_step = AgentExecutionStep(agent)
    flow = create_single_step_flow(agent_execution_step)
    conversation = flow.start_conversation()
    conversation.append_user_message(user_question)
    flow.execute(conversation)
    assert expected_answer in conversation.get_last_message().content.lower()


@retry_test(max_attempts=3)
def test_flow_as_tool_calling_with_user_response_inside_agent_execution_step(
    agent_with_yielding_subflow,
):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-04-16
    Average success time:  2.83 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    Verifies that:
    - The inner flow is not re-executed a second time after it yields the first time.
    - The execution is interrupted by a user input step, leading to the following error:
    ValueError: Expected TOOL_RESULT or USER message after TOOL_REQUEST...

    """

    agent = agent_with_yielding_subflow
    agent_execution_step = AgentExecutionStep(agent=agent)
    flow = create_single_step_flow(agent_execution_step)
    conversation = flow.start_conversation()
    conversation.append_user_message("How is the weather in Morocco?")
    flow.execute(conversation)
    conversation.append_user_message("windy")
    flow.execute(conversation)

    messages = [m for m in conversation.get_messages() if m.message_type != MessageType.INTERNAL]

    assert messages[0].content == "How is the weather in Morocco?"
    assert messages[0].message_type == MessageType.USER

    assert messages[1].message_type == MessageType.TOOL_REQUEST

    assert messages[2].content == "What is the weather in Morocco"
    assert messages[2].message_type == MessageType.AGENT

    assert messages[3].content == "windy"
    assert messages[3].message_type == MessageType.USER

    assert messages[4].content == "The weather in Morocco windy"
    assert messages[4].message_type == MessageType.AGENT

    assert messages[5].message_type == MessageType.TOOL_RESULT
    assert messages[6].message_type == MessageType.AGENT


@pytest.fixture
def measure_room_temp_tool():
    tool = ClientTool(
        name="measure_room_temp",
        description="Return the value of the temperature in the room",
        parameters={},
    )
    return tool


@retry_test(max_attempts=3, wait_between_tries=1)
def test_agentexecution_step_can_call_client_tool_with_no_parameter(
    remotely_hosted_llm: VllmModel,
    measure_room_temp_tool: ClientTool,
) -> None:
    """
    Failure rate:          3 out of 50
    Observed on:           2025-08-20
    Average success time:  0.48 seconds per successful attempt
    Average failure time:  0.56 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 3.5 / 100'000
    """

    agent_execution_step = AgentExecutionStep(
        Agent(
            tools=[measure_room_temp_tool],
            llm=remotely_hosted_llm,
            custom_instruction="You are a helpful assistant that has access to some tools.",
        )
    )

    assistant = make_sequential_assistant_with_context_provider([agent_execution_step])

    run_test_agent_can_call_client_tool_with_no_parameter(assistant)


def test_agent_step_uses_default_caller_input_mode_of_agent(remotely_hosted_llm):
    agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="Ask a question to the user",
        max_iterations=2,
        caller_input_mode=CallerInputMode.NEVER,
    )

    agent_step = AgentExecutionStep(
        agent=agent,
    )

    flow = Flow.from_steps(steps=[agent_step])

    conv = flow.start_conversation()
    conv.append_user_message("What is the capital of Switzerland?")
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
