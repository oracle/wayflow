# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import json
from textwrap import dedent
from typing import Annotated, Optional, Tuple

import pytest

from wayflowcore._utils._templating_helpers import render_template
from wayflowcore.agent import Agent
from wayflowcore.executors._agentexecutor import _TALK_TO_USER_TOOL_NAME
from wayflowcore.executors._swarmexecutor import _HANDOFF_TOOL_NAME, _SEND_MESSAGE_TOOL_NAME
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolExecutionConfirmationStatus,
    UserMessageRequestStatus,
)
from wayflowcore.flow import Flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.steps import OutputMessageStep
from wayflowcore.swarm import Swarm
from wayflowcore.tools import tool

from .testhelpers.dummy import DummyModel
from .testhelpers.testhelpers import retry_test


@tool
def fooza_tool(
    a: Annotated[int, "first required integer"], b: Annotated[int, "second required integer"]
) -> int:
    """Return the result of the fooza operation between numbers a and b. Do not use for anything else than computing a fooza operation."""
    return a * 2 + b * 3 - 1


@tool
def bwip_tool(
    a: Annotated[int, "first required integer"], b: Annotated[int, "second required integer"]
) -> int:
    """Return the result of the bwip operation between numbers a and b. Do not use for anything else than computing a bwip operation."""
    return a - b + 1


@tool
def zbuk_tool(
    a: Annotated[int, "first required integer"], b: Annotated[int, "second required integer"]
) -> int:
    """Return the result of the zbuk operation between numbers a and b. Do not use for anything else than computing a zbuk operation."""
    return a + b * 2


def _get_fooza_agent(llm):
    return Agent(
        custom_instruction=(
            "You are a fooza operation specialist. The fooza operation is a linear transformation, "
            "designed by Mr. Fooza. Tackle the requests you are specialized to tackle, and let other agents take care of the rest."
        ),
        llm=llm,
        tools=[fooza_tool],
        agent_id="fooza_agent",
        name="fooza_agent",
        description="An specialized AI Assistant that can answer any question/request related to the fooza operation.",
    )


def _get_bwip_agent(llm):
    return Agent(
        custom_instruction=(
            "You are a bwip operation specialist. Answer the user/caller requests about the bwip operation, "
            "and their request only (do not attempt to solve unrelated tasks). The bwip operation is a linear transformation, "
            "designed by Mr. Bwip. Only tackle the requests you are specialized to tackle, and let other agents take care of the rest."
        ),
        llm=llm,
        tools=[bwip_tool],
        agent_id="bwip_agent",
        name="bwip_agent",
        description="An specialized AI Assistant that can answer any question/request related to the bwip operation.",
    )


def _get_zbuk_agent(llm):
    return Agent(
        custom_instruction=(
            "You are a zbuk operation specialist. Answer the user/caller requests about the zbuk operation, "
            "and their request only (do not attempt to solve unrelated tasks). The zbuk operation is a linear transformation, "
            "designed by Mr. Zbuk. Only tackle the requests you are specialized to tackle, and let other agents take care of the rest."
        ),
        llm=llm,
        tools=[zbuk_tool],
        agent_id="zbuk_agent",
        name="zbuk_agent",
        description="An specialized AI Assistant that can answer any question/request related to the zbuk operation.",
    )


@pytest.fixture
def example_math_agents(remote_gemma_llm) -> Tuple[Agent, Agent, Agent]:
    llm = remote_gemma_llm
    return (
        _get_bwip_agent(llm),
        _get_zbuk_agent(llm),
        _get_fooza_agent(llm),
    )


def _get_math_swarm(bwip_agent, zbuk_agent, fooza_agent, handoff: bool):
    all_agents = (bwip_agent, zbuk_agent, fooza_agent)
    return Swarm(
        first_agent=fooza_agent,
        relationships=[  # all-to-all topology
            (ag1, ag2) for ag1 in all_agents for ag2 in all_agents if ag1 is not ag2
        ],
        handoff=handoff,
    )


@pytest.fixture
def example_medical_agents(remotely_hosted_llm) -> Tuple[Agent, Agent, Agent]:
    llm = remotely_hosted_llm
    gp_doctor = Agent(
        llm=llm,
        custom_instruction=(
            "You are a general practitioner doctor."
            "Patients might come to you for common issues like flu etc. For these, just prescribe something directly "
            "For more complicated cases, refer to a specialist."
        ),
        name="GeneralistDoctor",
        description="Generalist practitioner doctor",
    )

    neurologist_doctor = Agent(
        llm=llm,
        custom_instruction=dedent(
            "You are a neurologist. If a patient has cancer, refer them to the oncologist."
        ),
        name="NeurologistDoctor",
        description="Neurologist doctor",
    )

    oncologist_doctor = Agent(
        llm=llm,
        custom_instruction=dedent(
            "You are an oncologist. "
            "You should help patients with cancer, prescribing treatments and giving them precise information"
        ),
        name="OncologistDoctor",
        description="Oncologist doctor",
    )

    return gp_doctor, neurologist_doctor, oncologist_doctor


def test_can_execute_swarm_with_initial_params_passed_in_start_conversation(
    example_medical_agents, remotely_hosted_llm
):
    _, neurologist_doctor, oncologist_doctor = example_medical_agents

    llm = remotely_hosted_llm
    gp_doctor = Agent(
        llm=llm,
        custom_instruction=(
            "You are a general practitioner doctor for a patient names {{ USER }}."
            "This patient might come to you for common issues like flu etc. For these, just prescribe something directly "
            "For more complicated cases, refer to a specialist."
            "Remember to say hi to this patient when first answering."
        ),
        name="GeneralistDoctor",
        description="Generalist practitioner doctor",
    )

    swarm = Swarm(
        first_agent=gp_doctor,
        relationships=[
            (gp_doctor, neurologist_doctor),
            (gp_doctor, oncologist_doctor),
            (neurologist_doctor, oncologist_doctor),
        ],
    )

    conversation = swarm.start_conversation(
        messages=[
            Message(
                content="My skin has been itching for some about a week, can you help me understand what is going on?",
                message_type=MessageType.USER,
            )
        ],
        inputs={"USER": "Iris"},
        conversation_id="12345",
    )

    conversation.execute()

    # The first message must be not the default message as the init messages are passed.
    assert conversation.get_last_message().content != "Hi! How can I help you?"
    assert conversation.conversation_id == "12345"


def test_can_create_swarm(example_medical_agents):
    gp_doctor, neurologist_doctor, oncologist_doctor = example_medical_agents

    Swarm(
        first_agent=gp_doctor,
        relationships=[
            (gp_doctor, neurologist_doctor),
            (gp_doctor, oncologist_doctor),
            (neurologist_doctor, oncologist_doctor),
        ],
    )


def test_swarm_raises_with_empty_relationship_list(example_medical_agents):
    gp_doctor, neurologist_doctor, oncologist_doctor = example_medical_agents

    with pytest.raises(
        ValueError,
        match="Cannot define an `Swarm` with no relationships between the agents. Use an `Agent` instead.",
    ):
        Swarm(
            first_agent=gp_doctor,
            relationships=[],
        )


def test_swarm_raises_when_agent_have_no_name(example_medical_agents):
    gp_doctor, neurologist_doctor, oncologist_doctor = example_medical_agents
    gp_doctor.name = ""

    with pytest.raises(ValueError, match="Agent .* has no name."):
        Swarm(
            first_agent=gp_doctor,
            relationships=[
                (gp_doctor, neurologist_doctor),
                (gp_doctor, oncologist_doctor),
                (neurologist_doctor, oncologist_doctor),
            ],
        )


def test_swarm_raises_warning_when_duplicate_names(example_medical_agents):
    gp_doctor, neurologist_doctor, oncologist_doctor = example_medical_agents
    neurologist_doctor.name = oncologist_doctor.name

    with pytest.raises(ValueError, match="Found agents with duplicated names"):
        Swarm(
            first_agent=gp_doctor,
            relationships=[
                (gp_doctor, neurologist_doctor),
                (gp_doctor, oncologist_doctor),
                (neurologist_doctor, oncologist_doctor),
            ],
        )


def test_swarm_raises_when_duplicated_relationships(example_medical_agents):
    gp_doctor, neurologist_doctor, oncologist_doctor = example_medical_agents

    with pytest.raises(
        ValueError,
        match="Found duplicated relationship involving agents 'GeneralistDoctor' and 'NeurologistDoctor'",
    ):
        Swarm(
            first_agent=gp_doctor,
            relationships=[
                (gp_doctor, neurologist_doctor),
                (gp_doctor, oncologist_doctor),
                (neurologist_doctor, oncologist_doctor),
                (gp_doctor, neurologist_doctor),  # DUPLICATED
            ],
        )


def test_swarm_raises_when_using_flows(example_medical_agents):
    gp_doctor, neurologist_doctor, oncologist_doctor = example_medical_agents

    flow = Flow.from_steps([OutputMessageStep()], name="my_flow", description="my_flow_description")

    with pytest.raises(
        TypeError,
        match="Only Agents are supported in Swarm, got component of type 'Flow'",
    ):
        Swarm(
            first_agent=gp_doctor,
            relationships=[
                (gp_doctor, flow),
                (gp_doctor, oncologist_doctor),
                (neurologist_doctor, oncologist_doctor),
            ],
        )


@retry_test(max_attempts=3)
@pytest.mark.parametrize(
    argnames="handoff",
    argvalues=[False, True],
    ids=["no_handoff", "with_handoff"],
)
def test_swarm_can_complete_task_without_specialist(example_math_agents, handoff: bool):
    """
    The only two configurations used are:
     * [gemma-3-27b-it][no_handoff]
     * [gemma-3-27b-it][with_handoff]

    The other results are for indicative purposes

    # NO HANDOFF
    [Llama-3.1-8B-Instruct][no_handoff]
    Failure rate:          5 out of 30
    Observed on:           2025-05-12
    Average success time:  1.24 seconds per successful attempt
    Average failure time:  1.09 seconds per failed attempt
    Max attempt:           6
    Justification:         (0.19 ** 6) ~= 4.3 / 100'000

    [Llama-4-Maverick][no_handoff]
    Failure rate:          0 out of 30
    Observed on:           2025-05-12
    Average success time:  1.98 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000

    [gemma-3-27b-it][no_handoff]
    Failure rate:          0 out of 30
    Observed on:           2025-05-12
    Average success time:  1.84 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000

    [gpt-4.1-nano][no_handoff]
    Failure rate:          0 out of 30
    Observed on:           2025-05-12
    Average success time:  1.49 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000

    # WITH HANDOFF
    [Llama-3.1-8B-Instruct][with_handoff]
    Failure rate:          3 out of 30
    Observed on:           2025-05-12
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  0.75 seconds per failed attempt
    Max attempt:           5
    Justification:         (0.12 ** 5) ~= 3.1 / 100'000

    [Llama-4-Maverick][with_handoff]
    Failure rate:          0 out of 30
    Observed on:           2025-05-12
    Average success time:  2.28 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000

    [gemma-3-27b-it][with_handoff]
    Failure rate:          0 out of 30
    Observed on:           2025-05-12
    Average success time:  1.81 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000

    [gpt-4.1-nano][with_handoff]
    Failure rate:          1 out of 30
    Observed on:           2025-05-12
    Average success time:  1.44 seconds per successful attempt
    Average failure time:  0.51 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.5 / 100'000
    """
    math_swarm = _get_math_swarm(*example_math_agents, handoff=handoff)
    conv = math_swarm.start_conversation()  # first agent is fooza
    conv.append_user_message("compute the result the fooza operation of 4 and 5")
    math_swarm.execute(conv)

    last_message = conv.get_last_message()
    assert last_message is not None
    assert "22" in last_message.content


@retry_test(max_attempts=3)
@pytest.mark.parametrize(
    argnames="handoff",
    argvalues=[False, True],
    ids=["no_handoff", "with_handoff"],
)
def test_swarm_can_complete_routing_task(example_math_agents, handoff: bool):
    """
    The only two configurations used are:
     * [gemma-3-27b-it][no_handoff]
     * [gemma-3-27b-it][with_handoff]

    The other results are for indicative purposes.

    # NO HANDOFF
    [Llama-3.1-8B-Instruct][no_handoff]
    Failure rate:          12 out of 30
    Observed on:           2025-05-12
    Average success time:  2.72 seconds per successful attempt
    Average failure time:  2.70 seconds per failed attempt
    Max attempt:           11
    Justification:         (0.41 ** 11) ~= 5.0 / 100'000

    [Llama-4-Maverick][no_handoff]
    Failure rate:          0 out of 30
    Observed on:           2025-05-12
    Average success time:  4.08 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000

    [gemma-3-27b-it][no_handoff]
    Failure rate:          0 out of 30
    Observed on:           2025-05-12
    Average success time:  4.25 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000

    [gpt-4.1-nano][no_handoff]
    Failure rate:          0 out of 30
    Observed on:           2025-05-12
    Average success time:  3.63 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000

    # WITH HANDOFF
    [Llama-3.1-8B-Instruct][with_handoff]
    Failure rate:          5 out of 30
    Observed on:           2025-05-12
    Average success time:  3.40 seconds per successful attempt
    Average failure time:  1.86 seconds per failed attempt
    Max attempt:           6
    Justification:         (0.19 ** 6) ~= 4.3 / 100'000

    [Llama-4-Maverick][with_handoff]
    Failure rate:          0 out of 30
    Observed on:           2025-05-12
    Average success time:  4.45 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000

    [gemma-3-27b-it][with_handoff]
    Failure rate:          0 out of 30
    Observed on:           2025-05-12
    Average success time:  3.88 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000

    [gpt-4.1-nano][with_handoff]
    Failure rate:          1 out of 30
    Observed on:           2025-05-12
    Average success time:  3.10 seconds per successful attempt
    Average failure time:  4.83 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.5 / 100'000
    """
    math_swarm = _get_math_swarm(*example_math_agents, handoff=handoff)
    conv = math_swarm.start_conversation()  # first agent is fooza
    conv.append_user_message("compute the result the zbuk operation of 4 and 5")
    conv.execute()

    last_message = conv.get_last_message()
    assert last_message is not None
    assert "14" in last_message.content


@pytest.mark.skip(
    "just to show task ref perf"
)  # Just to show the task with reference performance results
def test_swarm_can_complete_composition_task(math_swarm_no_handoff: Swarm):
    """
    # NO HANDOFF
    [Llama-3.1-8B-Instruct][no_handoff]
    Failure rate:          15 out of 30
    Observed on:           2025-05-12
    Average success time:  6.73 seconds per successful attempt
    Average failure time:  4.30 seconds per failed attempt
    Max attempt:           14
    Justification:         (0.50 ** 14) ~= 6.1 / 100'000

    [Llama-4-Maverick][no_handoff]
    Failure rate:          2 out of 30
    Observed on:           2025-05-12
    Average success time:  8.37 seconds per successful attempt
    Average failure time:  13.19 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 7.7 / 100'000

    [gemma-3-27b-it][no_handoff]
    Failure rate:          3 out of 30
    Observed on:           2025-05-12
    Average success time:  8.13 seconds per successful attempt
    Average failure time:  8.12 seconds per failed attempt
    Max attempt:           5
    Justification:         (0.12 ** 5) ~= 3.1 / 100'000

    [gpt-4.1-nano][no_handoff]
    Failure rate:          25 out of 30
    Observed on:           2025-05-12
    Average success time:  6.30 seconds per successful attempt
    Average failure time:  3.94 seconds per failed attempt
    Max attempt:           45
    Justification:         (0.81 ** 45) ~= 8.8 / 100'000

    [gpt-4.1-mini][no_handoff]
    Failure rate:          5 out of 30
    Observed on:           2025-05-12
    Average success time:  11.99 seconds per successful attempt
    Average failure time:  9.07 seconds per failed attempt
    Max attempt:           6
    Justification:         (0.19 ** 6) ~= 4.3 / 100'000

    [gpt4.1][no_handoff]
    Failure rate:          0 out of 10
    Observed on:           2025-05-08
    Average success time:  1.06 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000

    # WITH HANDOFF
    [Llama-3.1-8B-Instruct][with_handoff]
    Failure rate:          19 out of 30
    Observed on:           2025-05-12
    Average success time:  6.84 seconds per successful attempt
    Average failure time:  5.66 seconds per failed attempt
    Max attempt:           20
    Justification:         (0.62 ** 20) ~= 8.3 / 100'000

    [Llama-4-Maverick][with_handoff]
    Failure rate:          1 out of 30
    Observed on:           2025-05-12
    Average success time:  8.87 seconds per successful attempt
    Average failure time:  11.15 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.5 / 100'000

    [gemma-3-27b-it][with_handoff]
    Failure rate:          3 out of 30
    Observed on:           2025-05-12
    Average success time:  8.17 seconds per successful attempt
    Average failure time:  8.06 seconds per failed attempt
    Max attempt:           5
    Justification:         (0.12 ** 5) ~= 3.1 / 100'000

    [gpt-4.1-nano][with_handoff]
    Failure rate:          23 out of 30
    Observed on:           2025-05-12
    Average success time:  6.24 seconds per successful attempt
    Average failure time:  4.67 seconds per failed attempt
    Max attempt:           33
    Justification:         (0.75 ** 33) ~= 7.5 / 100'000

    [gpt-4.1-mini][with_handoff]
    Failure rate:          4 out of 30
    Observed on:           2025-05-12
    Average success time:  10.89 seconds per successful attempt
    Average failure time:  7.21 seconds per failed attempt
    Max attempt:           5
    Justification:         (0.16 ** 5) ~= 9.3 / 100'000
    """
    math_swarm = math_swarm_no_handoff
    conv = math_swarm.start_conversation()  # first agent is fooza
    conv.append_user_message("compute the result of the bwip(4, zbuk(5, 6))")
    math_swarm.execute(conv)

    last_message = conv.get_last_message()
    assert last_message is not None
    assert "-12" in last_message.content


_SWARM_TOOL_CALL_TEMPLATE = """
{{thoughts}}

{"name": {{tool_name}}, "parameters": {{tool_params}}}
""".strip()


def _send_message(
    recipient_agent: Agent, message: Optional[str] = None, thoughts: Optional[str] = None
) -> Message:
    return Message(
        render_template(
            _SWARM_TOOL_CALL_TEMPLATE,
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


def _handoff_message(recipient_agent: Agent, thoughts: Optional[str] = None) -> Message:
    return Message(
        render_template(
            _SWARM_TOOL_CALL_TEMPLATE,
            inputs=dict(
                thoughts=thoughts or "THOUGHTS",
                tool_name=_HANDOFF_TOOL_NAME,
                tool_params=json.dumps(dict(recipient=recipient_agent.name)),
            ),
        ),
        message_type=MessageType.AGENT,
    )


def test_swarm_warns_agent_on_sending_message_to_caller_instead_of_using_talk_to_user_tool():
    llm = DummyModel()

    agent1 = Agent(llm, name="agent1", description="agent 1")
    agent2 = Agent(llm, name="agent2", description="agent 2")

    swarm = Swarm(first_agent=agent1, relationships=[(agent1, agent2), (agent2, agent1)])
    llm.set_next_output(
        [
            _send_message(
                agent2, message="hey agent 2, can you do ...", thoughts="sending message to agent2"
            ),
            _send_message(
                agent1, message="hey agent 1, can you do ...", thoughts="sending message to agent1"
            ),
        ]
    )

    conv = swarm.start_conversation()
    conv.append_user_message("dummy")
    with pytest.raises(ValueError, match="Did you forget to set the output of the Dummy model"):
        # controlled execution
        swarm.execute(conv)

    agent1_agent2_message_list = conv.state.agents_and_threads[agent1.name][
        agent2.name
    ].message_list
    last_message = (
        agent1_agent2_message_list.get_last_message()
    )  # Message warning the `agent2` about what it is doing wrong
    assert (
        f"Circular calling warning: Cannot use {_SEND_MESSAGE_TOOL_NAME} on a caller/user. Please use {_TALK_TO_USER_TOOL_NAME} instead"
        in last_message.content
    )


def test_swarm_raises_on_missing_relationship_when_using_handoff():
    llm = DummyModel()

    agent1 = Agent(llm, name="agent1", description="agent 1")
    agent2 = Agent(llm, name="agent2", description="agent 2")
    agent3 = Agent(llm, name="agent3", description="agent 3")

    swarm = Swarm(
        first_agent=agent1,
        relationships=[
            (agent1, agent2),
            # (agent1, agent3), # required to support handoff
            (agent2, agent3),
            (agent3, agent1),
        ],
    )

    llm.set_next_output(
        [
            _send_message(
                agent2, message="hey agent 2, can you do ...", thoughts="sending message to agent2"
            ),
            _handoff_message(agent3, thoughts="handing off conversation to agent3"),
            _send_message(
                agent1, message="hey agent 1, can you do ...", thoughts="sending message to agent1"
            ),
        ]
    )

    conv = swarm.start_conversation()
    conv.append_user_message("dummy")
    with pytest.raises(
        KeyError,
        match=f"Cannot handoff conversation from .*'{agent1.name}', recipient='{agent2.name}'.*'{agent1.name}', recipient='{agent3.name}'.*'{agent1.name}', '{agent3.name}'",
    ):
        swarm.execute(conv)


def test_circular_calling_warning_with_handoff():
    llm = DummyModel()

    agent1 = Agent(llm, name="agent1", description="agent 1")
    agent2 = Agent(llm, name="agent2", description="agent 2")
    agent3 = Agent(llm, name="agent3", description="agent 3")

    swarm = Swarm(
        first_agent=agent1,
        relationships=[
            (agent1, agent2),
            (agent1, agent3),  # required to support handoff
            (agent2, agent3),
            (agent3, agent1),
        ],
    )

    llm.set_next_output(
        [
            _send_message(
                agent2, message="hey agent 2, can you do ...", thoughts="sending message to agent2"
            ),
            _handoff_message(agent3, thoughts="handing off conversation to agent3"),
            _send_message(
                agent1, message="hey agent 1, can you do ...", thoughts="sending message to agent1"
            ),
        ]
    )

    conv = swarm.start_conversation()
    conv.append_user_message("dummy")

    with pytest.raises(ValueError, match="Did you forget to set the output of the Dummy model"):
        # controlled execution
        swarm.execute(conv)

    agent1_agent3_message_list = conv.state.agents_and_threads[agent1.name][
        agent3.name
    ].message_list
    last_message = (
        agent1_agent3_message_list.get_last_message()
    )  # Message warning the `agent3` about what it is doing wrong
    assert (
        f"Circular calling warning: Cannot use {_SEND_MESSAGE_TOOL_NAME} on a caller/user. Please use {_TALK_TO_USER_TOOL_NAME} instead"
        in last_message.content
    )


@retry_test(max_attempts=3)
def test_swarm_execution_does_not_raise_errors(remotely_hosted_llm) -> None:
    """
    IMPORTANT: THIS TEST SHOULD ALWAYS HAVE A FAILURE RATE OF 0%
    If any flakiness is detected please contact the core team.

    Failure rate:          0 out of 50
    Observed on:           2025-06-02
    Average success time:  3.58 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """

    llm = remotely_hosted_llm
    addition_agent = Agent(
        name="addition_agent",
        description="Agent that can do additions",
        llm=llm,
        custom_instruction="You can do additions.",
    )
    multiplication_agent = Agent(
        name="multiplication_agent",
        description="Agent that can do multiplication",
        llm=llm,
        custom_instruction="You can do multiplication.",
    )
    division_agent = Agent(
        name="division_agent",
        description="Agent that can do division",
        llm=llm,
        custom_instruction="You can do division.",
    )

    swarm = Swarm(
        first_agent=addition_agent,
        relationships=[
            (addition_agent, multiplication_agent),
            (addition_agent, division_agent),
            (multiplication_agent, division_agent),
        ],
    )
    conversation = swarm.start_conversation()
    conversation.append_user_message("Please compute 2*2+1")
    swarm.execute(conversation)


def test_execute_swarm_on_wrong_conversation_raises(remotely_hosted_llm):
    agent = Agent(llm=remotely_hosted_llm)
    agent_2 = Agent(llm=remotely_hosted_llm, description="sub agent")
    swarm_1 = Swarm(first_agent=agent, relationships=[(agent, agent_2)])
    swarm_2 = Swarm(first_agent=agent, relationships=[(agent, agent_2)])

    conv = swarm_1.start_conversation()
    with pytest.raises(ValueError, match="You are trying to call"):
        swarm_2.execute(conv)


@tool(requires_confirmation=True, description_mode="only_docstring")
def check_name_in_db_tool(name: str) -> str:
    """Check if a name is present in the database"""
    return "This name is present in the database"


@retry_test(max_attempts=3, wait_between_tries=1)
def test_swarm_can_handle_server_tool_with_confirmation(big_llama):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-22
    Average success time:  21.96 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    # Plug the tool into an agent
    llm = big_llama
    main_agent = Agent(
        llm=llm,
        description="general agent which will route queries to your agents",
        custom_instruction="You are a general agent which will always route queries to your agents and collect tool outputs",
    )
    agent = Agent(
        llm=llm,
        tools=[check_name_in_db_tool],
        name="check_name_in_db_agent",
        description="A helpful agent that has access to a tool which check if a given name is present in database.",
        custom_instruction="You should only use one tool at a time. Only use the talk_to_user tool to ask the user questions, not to inform them about your next action. Don't talk to the user unless reporting on the requested tasks.",
    )
    swarm = Swarm(
        first_agent=main_agent,
        relationships=[(main_agent, agent)],
    )

    conv = swarm.start_conversation()
    conv.append_user_message("Is the name Alice present in the database? Ask your agents if needed")
    status = swarm.execute(conv)
    assert isinstance(status, ToolExecutionConfirmationStatus)
    assert len(status.tool_requests) == 1
    req = status.tool_requests[0]
    assert req.name == "check_name_in_db_tool"

    # Confirm the tool execution
    status.confirm_tool_execution(tool_request=req)
    status2 = swarm.execute(conv)
    # Should result in a user message request or final status
    assert isinstance(status2, UserMessageRequestStatus) or isinstance(status2, FinishedStatus)

    # Now test rejection path
    conv = swarm.start_conversation()
    conv.append_user_message("Is the name Bob present in the database? Ask your agents if needed")
    status = swarm.execute(conv)
    assert isinstance(status, ToolExecutionConfirmationStatus)
    # Reject with a reason
    status.reject_tool_execution(
        tool_request=status.tool_requests[0], reason="Invalid request. Do not try again"
    )
    status2 = swarm.execute(conv)
    loop_count = 1
    while isinstance(status2, ToolExecutionConfirmationStatus):
        status2.reject_tool_execution(
            tool_request=status2.tool_requests[0],
            reason="Permission Denied, Do not try to use this tool.",
        )
        status2 = swarm.execute(conv)
        loop_count += 1
        if loop_count > 3:
            break
    # Should result in a user message request or a graceful finish
    assert isinstance(status2, UserMessageRequestStatus) or isinstance(status2, FinishedStatus)
