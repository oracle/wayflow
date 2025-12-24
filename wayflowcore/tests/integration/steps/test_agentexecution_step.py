# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.from unittest.mock import patch
from unittest.mock import patch

import pytest
from pytest import fixture

from wayflowcore import Message, MessageType
from wayflowcore.agent import Agent
from wayflowcore.conversationalcomponent import _MutatedConversationalComponent
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow, run_flow_and_return_outputs
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.property import IntegerProperty, Property, StringProperty
from wayflowcore.steps import OutputMessageStep
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep, CallerInputMode
from wayflowcore.steps.outputmessagestep import OutputMessageStep
from wayflowcore.swarm import Swarm
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
def zinimo_agent(vllm_responses_llm):
    return Agent(
        llm=vllm_responses_llm,
        custom_instruction=(
            "You need to compute the zinimo operation of 2 provided numbers (if not provided, you should ask the user)"
            "and submit the tool result to the user using the `submit_result` function (and not as a agent message). "
            "IMPORTANT: Never make up arguments, ask the user if you have a question. "
            "Only output a single function call at a time if needed."
        ),
        tools=[zinimo_tool],
        description="Agent that can compute the zinimo operation of 2 provided numbers.",
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
    with _MutatedConversationalComponent(agent=agent, attributes=dict(max_iterations=2)) as agent:

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
    status = conv.execute()
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
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    conv.append_user_message("2")
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    conv.append_user_message("5")
    status = conv.execute()
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
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert dummy_llm.output is None  # all generations used
    assert len([m for m in conv.get_messages() if "The user is not available" in m.content]) == 3


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
    conversation.execute()
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
    conversation.execute()
    conversation.append_user_message("windy")
    conversation.execute()

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


@retry_test(max_attempts=3)
def test_agent_step_that_uses_agent_with_default_input_values_works(big_llama):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-19
    Average success time:  2.94 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    agent = Agent(
        llm=big_llama,
        custom_instruction="You are a helpful agent. Here's what you know: {{context}}. Answer the user `{{username}}`.",
        input_descriptors=[
            StringProperty(name="context", default_value="Videogames"),
            StringProperty(name="username"),
        ],
    )

    agent_step = AgentExecutionStep(
        agent=agent,
    )

    flow = Flow.from_steps(steps=[agent_step])
    assert len(flow.input_descriptors) == 2
    assert {"context", "username"} == set(descriptor.name for descriptor in flow.input_descriptors)
    context_input = next(
        descriptor for descriptor in flow.input_descriptors if descriptor.name == "context"
    )
    assert context_input.default_value == "Videogames"

    conv = flow.start_conversation({"username": "john"})
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    status.submit_user_response("Who is the user?")
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    last_message = status.message
    assert "john" in last_message.content.lower()
    status.submit_user_response("What do you know?")
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    last_message = status.message
    assert "videogame" in last_message.content.lower()


@retry_test(max_attempts=3)
def test_agent_step_with_swarm_can_execute_when_first_agent_handles_task(
    zinimo_agent,
    vllm_responses_llm,
):
    """
    Failure rate:          0 out of 20
    Observed on:           2026-01-27
    Average success time:  2.33 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    first_agent = zinimo_agent

    second_agent = Agent(
        llm=vllm_responses_llm,
        name="second_agent",
        description="second agent",
        custom_instruction="You are a helpful agent",
    )

    swarm = Swarm(first_agent=first_agent, relationships=[(first_agent, second_agent)])
    step = AgentExecutionStep(
        agent=swarm,
        output_descriptors=[zinimo_result_description],
        caller_input_mode=CallerInputMode.NEVER,
    )
    flow = create_single_step_flow(step)
    conv = flow.start_conversation()
    conv.append_user_message("Calculate zinimo operation between 2 and 5")
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values["zinimo_result"] == -2


@retry_test(max_attempts=3)
def test_agent_step_with_swarm_can_execute_when_sub_agent_handles_task(
    zinimo_agent,
    vllm_responses_llm,
):
    """
    Failure rate:          0 out of 20
    Observed on:           2026-01-27
    Average success time:  6.33 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    first_agent = Agent(
        llm=vllm_responses_llm,
        name="master_agent",
        description="Redirects the user requests to the sub agents, or handles the subagents communication. Do not solve the task on your own.",
        custom_instruction="You are the main agent",
    )
    second_agent = zinimo_agent

    swarm = Swarm(first_agent=first_agent, relationships=[(first_agent, second_agent)])
    step = AgentExecutionStep(
        agent=swarm,
        output_descriptors=[zinimo_result_description],
        caller_input_mode=CallerInputMode.NEVER,
    )
    flow = create_single_step_flow(step)
    conv = flow.start_conversation()
    conv.append_user_message("Calculate zinimo operation between 2 and 5")
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values["zinimo_result"] == -2


@retry_test(max_attempts=3)
def test_agent_step_with_swarm_in_conversational_mode(vllm_responses_llm):
    """
    Failure rate:          0 out of 20
    Observed on:           2026-01-27
    Average success time:  1.83 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    first_agent = Agent(
        llm=vllm_responses_llm,
        name="first_agent",
        custom_instruction="You are a helpful agent",
    )
    second_agent = Agent(
        llm=vllm_responses_llm,
        name="second_agent",
        description="Agent that can do math",
        custom_instruction="You are an agent that can do math",
    )
    swarm = Swarm(first_agent=first_agent, relationships=[(first_agent, second_agent)])
    agent_step = AgentExecutionStep(agent=swarm)

    flow = Flow.from_steps(steps=[agent_step])

    conv = flow.start_conversation()
    status = conv.execute()

    assert isinstance(status, UserMessageRequestStatus)
    status.submit_user_response("Hello, my name is John")
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    status.submit_user_response("What is my name?")
    status = conv.execute()
    assert "john" in conv.get_last_message().content.lower()


@retry_test(max_attempts=3)
def test_swarm_can_run_in_non_conversational_mode(vllm_responses_llm):
    """
    Failure rate:          0 out of 20
    Observed on:           2026-01-27
    Average success time:  2.06 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    first_agent = Agent(
        llm=vllm_responses_llm,
        name="first_agent",
        custom_instruction="You are a helpful agent",
    )
    second_agent = Agent(
        llm=vllm_responses_llm,
        name="second_agent",
        description="Agent that can do math",
        custom_instruction="You are an agent that can do math",
    )
    swarm = Swarm(first_agent=first_agent, relationships=[(first_agent, second_agent)])

    response = StringProperty(name="response", default_value="")

    agent_step = AgentExecutionStep(
        name="agent_step",
        agent=swarm,
        output_descriptors=[response],
        caller_input_mode=CallerInputMode.NEVER,
    )

    output_step = OutputMessageStep(name="output_step", message_template="""{{response}}""")

    flow = Flow.from_steps([agent_step, output_step])

    conversation = flow.start_conversation()
    conversation.append_user_message("What is 10+10?")
    status = conversation.execute()
    assert "20" in status.output_values["output_message"]


@retry_test(max_attempts=3)
def test_swarm_can_run_in_non_conversational_mode_with_output_descriptors_in_swarm(
    vllm_responses_llm,
):
    """
    Failure rate:          0 out of 20
    Observed on:           2026-01-27
    Average success time:  3.28 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    first_agent = Agent(
        llm=vllm_responses_llm,
        name="first_agent",
        custom_instruction="You are a helpful agent",
    )
    second_agent = Agent(
        llm=vllm_responses_llm,
        name="second_agent",
        description="Agent that can do math",
        custom_instruction="You are an agent that can do math",
    )
    response = StringProperty(name="response", default_value="")
    swarm = Swarm(
        first_agent=first_agent,
        relationships=[(first_agent, second_agent)],
        output_descriptors=[response],
        caller_input_mode=CallerInputMode.NEVER,
    )

    agent_step = AgentExecutionStep(
        name="agent_step",
        agent=swarm,
    )

    output_step = OutputMessageStep(name="output_step", message_template="""{{response}}""")

    flow = Flow.from_steps([agent_step, output_step])

    conversation = flow.start_conversation()
    conversation.append_user_message("What is 10+10?")
    status = conversation.execute()
    assert "20" in status.output_values["output_message"]


@retry_test(max_attempts=3)
def test_swarm_can_run_in_non_conversational_mode_with_input_and_output_descriptors_in_swarm(
    vllm_responses_llm,
):
    """
    Failure rate:          0 out of 20
    Observed on:           2026-01-27
    Average success time:  1.91 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    input_message = StringProperty(name="input_message", default_value="")
    response = StringProperty(name="response", default_value="")
    first_agent = Agent(
        llm=vllm_responses_llm,
        name="first_agent",
        custom_instruction="You are a helpful agent. Look at the message in {{input_message}}",
    )
    second_agent = Agent(
        llm=vllm_responses_llm,
        name="second_agent",
        description="Agent that can do math",
        custom_instruction="You are an agent that can do math.",
    )

    swarm = Swarm(
        first_agent=first_agent,
        relationships=[(first_agent, second_agent)],
        input_descriptors=[input_message],
        output_descriptors=[response],
        caller_input_mode=CallerInputMode.NEVER,
    )

    agent_step = AgentExecutionStep(
        name="agent_step",
        agent=swarm,
    )

    output_step = OutputMessageStep(name="output_step", message_template="""{{response}}""")

    flow = Flow.from_steps([agent_step, output_step])

    conversation = flow.start_conversation(inputs={"input_message": "What is 10+10?"})
    conversation.execute()
    status = conversation.execute()
    assert "20" in status.output_values["output_message"]


@retry_test(max_attempts=3)
def test_agent_step_with_managerworkers_with_input_descriptors_can_execute(vllm_responses_llm):
    """
    Failure rate:          1 out of 50
    Observed on:           2025-12-24
    Average success time:  2.64 seconds per successful attempt
    Average failure time:  1.14 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000
    """
    llm = vllm_responses_llm

    first_agent = Agent(
        llm=llm,
        name="first_agent",
        description="first agent",
        custom_instruction="You are a helpful agent. Here's what you know: {{context_1}}. You are answering an user with the name: `{{username}}`.",
    )

    second_agent = Agent(
        llm=llm,
        name="second_agent",
        description="second agent",
    )

    group = ManagerWorkers(
        group_manager=first_agent,
        workers=[second_agent],
        input_descriptors=[
            StringProperty(name="context_1", default_value="Video games"),
            StringProperty(name="username"),
        ],  # can declare input descriptors of the manager using ManagerWorkers's input_descriptors,
        # users can also define it within the manager agent.
    )

    agent_step = AgentExecutionStep(
        agent=group,
    )

    flow = Flow.from_steps(steps=[agent_step])

    assert len(flow.input_descriptors) == 2
    assert {"context_1", "username"} == set(
        descriptor.name for descriptor in flow.input_descriptors
    )
    context_input = next(
        descriptor for descriptor in flow.input_descriptors if descriptor.name == "context_1"
    )
    assert context_input.default_value == "Video games"

    conv = flow.start_conversation({"username": "John"})

    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    status.submit_user_response("What is the name of the user you are interacting?")

    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    last_message = status.message
    assert "john" in last_message.content.lower()
    status.submit_user_response("What do you know?")

    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    last_message = status.message
    assert "video" in last_message.content.lower() or "game" in last_message.content.lower()
