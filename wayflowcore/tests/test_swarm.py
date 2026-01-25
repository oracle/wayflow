# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
from textwrap import dedent
from typing import Annotated, Optional, Tuple

import pytest

from wayflowcore._utils._templating_helpers import render_template
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.executors._agentexecutor import _TALK_TO_USER_TOOL_NAME
from wayflowcore.executors._swarmconversation import SwarmConversation
from wayflowcore.executors._swarmexecutor import _HANDOFF_TOOL_NAME, _SEND_MESSAGE_TOOL_NAME
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.flow import Flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import LlmModel
from wayflowcore.property import IntegerProperty, StringProperty
from wayflowcore.serialization import deserialize, serialize
from wayflowcore.steps import OutputMessageStep
from wayflowcore.swarm import HandoffMode, Swarm
from wayflowcore.tools import ClientTool, ToolRequest, ToolResult, tool

from .testhelpers.dummy import DummyModel
from .testhelpers.patching import patch_llm
from .testhelpers.testhelpers import retry_test


@tool
def fooza_tool(
    a: Annotated[int, "first required integer"], b: Annotated[int, "second required integer"]
) -> int:
    """Return the result of the fooza operation between numbers a and b. Do not use for anything else than computing a fooza operation."""
    return a * 2 + b * 3 - 1


@tool
def fooza_tool_2(
    a: Annotated[int, "first required integer"], b: Annotated[int, "second required integer"]
) -> int:
    """Return the result of the fooza operation between numbers a and b. Do not use for anything else than computing a fooza operation."""
    raise ValueError("Cannot compute result using fooza tool.")


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


def _get_fooza_agent(llm, raise_exception_tool=False, raise_exceptions=False):
    _tool = fooza_tool_2 if raise_exception_tool else fooza_tool
    return Agent(
        custom_instruction=(
            "You are a fooza operation specialist. The fooza operation is a linear transformation, "
            "designed by Mr. Fooza. Tackle the requests you are specialized to tackle, and let other agents take care of the rest."
        ),
        llm=llm,
        tools=[_tool],
        raise_exceptions=raise_exceptions,
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
def example_math_agents(vllm_responses_llm) -> Tuple[Agent, Agent, Agent]:
    llm = vllm_responses_llm
    return (
        _get_bwip_agent(llm),
        _get_zbuk_agent(llm),
        _get_fooza_agent(llm),
    )


def _get_math_swarm(bwip_agent, zbuk_agent, fooza_agent, handoff: HandoffMode):
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


def _get_check_name_in_db_client_tool() -> ClientTool:
    return ClientTool(
        name="check_name_in_db_tool",
        description="Check if a name is present in the database",
        input_descriptors=[
            StringProperty("name", description="name to check"),
        ],
    )


def _get_agent_with_client_tool(llm: LlmModel) -> Agent:
    check_name_in_db_tool = _get_check_name_in_db_client_tool()
    return Agent(
        llm=llm,
        tools=[check_name_in_db_tool],
        name="check_name_in_db_agent",
        description="A helpful agent that has access to a tool which check if a given name is present in database.",
        custom_instruction="You are an agent which checks if a name is present in the database",
    )


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
    argvalues=[HandoffMode.NEVER, HandoffMode.OPTIONAL],
    ids=["no_handoff", "with_handoff"],
)
def test_swarm_can_complete_task_without_specialist(example_math_agents, handoff: HandoffMode):
    """
    # HandoffMode.NEVER
    Failure rate:          0 out of 50
    Observed on:           2026-01-19
    Average success time:  2.59 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000

    # HandoffMode.OPTIONAL
    Failure rate:          0 out of 50
    Observed on:           2026-01-19
    Average success time:  2.74 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    math_swarm = _get_math_swarm(*example_math_agents, handoff=handoff)
    conv = math_swarm.start_conversation()  # first agent is fooza
    conv.append_user_message("compute the result the fooza operation of 4 and 5")
    conv.execute()

    last_message = conv.get_last_message()
    assert last_message is not None
    assert "22" in last_message.content


@retry_test(max_attempts=3)
@pytest.mark.parametrize(
    argnames="handoff",
    argvalues=[HandoffMode.NEVER, HandoffMode.OPTIONAL],
    ids=["no_handoff", "with_handoff"],
)
def test_swarm_can_complete_routing_task(example_math_agents, handoff: HandoffMode):
    """
    # HandoffMode.NEVER
    Failure rate:          0 out of 50
    Observed on:           2026-01-19
    Average success time:  5.57 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000

    # HandoffMode.OPTIONAL
    Failure rate:          0 out of 50
    Observed on:           2026-01-19
    Average success time:  3.87 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    math_swarm = _get_math_swarm(*example_math_agents, handoff=handoff)
    conv = math_swarm.start_conversation()  # first agent is fooza
    conv.append_user_message("compute the result the zbuk operation of 4 and 5")
    conv.execute()

    last_message = conv.get_last_message()
    assert last_message is not None
    assert "14" in last_message.content


@retry_test(max_attempts=5)
@pytest.mark.parametrize(
    argnames="handoff",
    argvalues=[HandoffMode.NEVER, HandoffMode.OPTIONAL],
    ids=["no_handoff", "with_handoff"],
)
def test_swarm_can_complete_composition_task(example_math_agents, handoff):
    """
    # HandoffMode.NEVER
    Failure rate:          2 out of 50
    Observed on:           2026-01-19
    Average success time:  11.79 seconds per successful attempt
    Average failure time:  5.62 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.1 / 100'000

    # HandoffMode.OPTIONAL
    Failure rate:          5 out of 50
    Observed on:           2026-01-19
    Average success time:  10.24 seconds per successful attempt
    Average failure time:  4.74 seconds per failed attempt
    Max attempt:           5
    Justification:         (0.12 ** 5) ~= 2.0 / 100'000
    """
    math_swarm = _get_math_swarm(*example_math_agents, handoff)
    conv = math_swarm.start_conversation()  # first agent is fooza
    conv.append_user_message("compute the result of the bwip(4, zbuk(5, 6))")
    conv.execute()

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
        conv.execute()

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
            "Yes, do this..",
            _handoff_message(agent3, thoughts="handing off conversation to agent3"),
            "Yes, User..",
        ]
    )

    conv = swarm.start_conversation()
    conv.append_user_message("dummy")
    conv.execute()
    main_message_list = conv.state.main_thread.message_list
    handoff_error_message = main_message_list.get_messages()[-2]
    assert (
        f"Recipient agent3 is not recognized. Possible recipients are: ['agent2']"
        in handoff_error_message.content
    )


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
            (agent3, agent2),
        ],
    )

    llm.set_next_output(
        [
            _handoff_message(agent3, thoughts="handing off conversation to agent3"),
            _send_message(
                agent2, message="hey agent 2, can you do ...", thoughts="sending message to agent2"
            ),
            _send_message(
                agent3, message="hey agent 3, can you do ...", thoughts="sending message to agent3"
            ),
        ]
    )

    conv = swarm.start_conversation()
    conv.append_user_message("dummy")

    with pytest.raises(ValueError, match="Did you forget to set the output of the Dummy model"):
        # controlled execution
        conv.execute()

    agent3_agent2_message_list = conv.state.agents_and_threads[agent3.name][
        agent2.name
    ].message_list
    last_message = (
        agent3_agent2_message_list.get_last_message()
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
    conversation.execute()


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
    status = conv.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    assert len(status.tool_requests) == 1
    req = status.tool_requests[0]
    assert req.name == "check_name_in_db_tool"

    # Confirm the tool execution
    status.confirm_tool_execution(tool_request=req)
    status2 = conv.execute()
    # Should result in a user message request or final status
    assert isinstance(status2, UserMessageRequestStatus) or isinstance(status2, FinishedStatus)

    # Now test rejection path
    conv = swarm.start_conversation()
    conv.append_user_message("Is the name Bob present in the database? Ask your agents if needed")
    status = conv.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    # Reject with a reason
    status.reject_tool_execution(
        tool_request=status.tool_requests[0], reason="Invalid request. Do not try again"
    )
    status2 = conv.execute()
    loop_count = 1
    while isinstance(status2, ToolExecutionConfirmationStatus):
        status2.reject_tool_execution(
            tool_request=status2.tool_requests[0],
            reason="Permission Denied, Do not try to use this tool.",
        )
        status2 = conv.execute()
        loop_count += 1
        if loop_count > 3:
            break
    # Should result in a user message request or a graceful finish
    assert isinstance(status2, UserMessageRequestStatus) or isinstance(status2, FinishedStatus)


@retry_test(max_attempts=4)
def test_swarm_can_handle_client_tool_with_confirmation(big_llama):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-10-20
    Average success time:  14.36 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    check_name_in_db_tool = ClientTool(
        name="check_name_in_db_tool",
        description="Check if a name is present in the database",
        input_descriptors=[
            StringProperty("name", description="name to check"),
        ],
        requires_confirmation=True,
    )
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
        custom_instruction="You are an agent which checks if a name is present in the database",
    )
    swarm = Swarm(
        first_agent=main_agent,
        relationships=[(main_agent, agent)],
    )

    conv = swarm.start_conversation()
    conv.append_user_message("Is the name Alice present in the database? Ask your agents if needed")
    status = conv.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    assert len(status.tool_requests) == 1
    status.confirm_tool_execution(tool_request=status.tool_requests[0])
    status = conv.execute()
    assert isinstance(status, ToolRequestStatus)
    assert len(status.tool_requests) == 1
    req = status.tool_requests[0]
    assert req.name == "check_name_in_db_tool"


@retry_test(max_attempts=4)
def test_swarm_can_handle_client_tool(big_llama):
    """
    Failure rate:          2 out of 50
    Observed on:           2025-10-09
    Average success time:  10.91 seconds per successful attempt
    Average failure time:  8.84 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.1 / 100'000
    """
    llm = big_llama
    main_agent = Agent(
        llm=llm,
        description="general agent which will route queries to your agents",
        custom_instruction="You are a general agent which will always route queries to your agents and collect tool outputs",
    )
    agent = _get_agent_with_client_tool(llm)
    swarm = Swarm(
        first_agent=main_agent,
        relationships=[(main_agent, agent)],
    )

    conv = swarm.start_conversation()
    conv.append_user_message("Is the name Alice present in the database? Ask your agents if needed")
    status = conv.execute()
    assert isinstance(status, ToolRequestStatus)
    assert len(status.tool_requests) == 1
    req = status.tool_requests[0]
    assert req.name == "check_name_in_db_tool"

    # Check conversation can be continued after being serialized and deserialized
    serialized_conv = serialize(conv)
    conv = deserialize(SwarmConversation, serialized_conv)

    # Confirm the tool execution
    tool_result = "The name Alice is present in the database"
    conv.append_tool_result(ToolResult(content=tool_result, tool_request_id=req.tool_request_id))
    status_2 = conv.execute()
    assert isinstance(status_2, UserMessageRequestStatus) or isinstance(status_2, FinishedStatus)


def test_agent_ids_in_swarm_are_the_same_after_the_conversation_execution(example_medical_agents):
    gp_doctor, neurologist_doctor, oncologist_doctor = example_medical_agents

    swarm = Swarm(
        first_agent=gp_doctor,
        relationships=[
            (gp_doctor, neurologist_doctor),
            (gp_doctor, oncologist_doctor),
            (neurologist_doctor, oncologist_doctor),
        ],
    )

    gp_doctor_id = gp_doctor.agent_id
    neurologist_doctor_id = neurologist_doctor.agent_id
    oncologist_doctor_id = oncologist_doctor.agent_id

    conv = swarm.start_conversation()
    conv.append_user_message(
        "My skin has been itching for some about a week, can you help me understand what is going on?"
    )
    conv.execute()

    assert gp_doctor_id == gp_doctor.agent_id
    assert neurologist_doctor_id == neurologist_doctor.agent_id
    assert oncologist_doctor_id == oncologist_doctor.agent_id


def get_fixer_agent(llm: LlmModel) -> Agent:
    @tool(description_mode="only_docstring")
    def fix_bug(bug: dict[str, str]) -> str:
        """Fix the the provided bug"""
        return "Successfully fixed the give bug"

    return Agent(
        llm=llm,
        custom_instruction="You are a bug-fixer. Use your tools to fix bugs",
        name="fixer_agent",
        description="can fix bugs in the code-base given a bug detail",
        tools=[fix_bug],
    )


def get_debugger_agent(llm: LlmModel) -> Agent:
    @tool(description_mode="only_docstring")
    def get_bug(product: str) -> dict[str, str]:
        """Gets the existing bugs on a given product"""
        return {"id": "fbuyeiwb", "details": "Infinite recursion bug on some function"}

    return Agent(
        llm=llm,
        custom_instruction="You are the debugger agent. Be truthful, do not make up any information. Use your tools to find information about bugs. Do not yield to user for confirmation.",
        name="debugger_agent",
        description="can investigate bugs in the code-base of a given product",
        tools=[get_bug],
    )


def get_first_agent(llm: LlmModel) -> Agent:
    return Agent(
        llm=llm,
        custom_instruction="You are the main agent",
        name="master_agent",
        description="Redirects the user requests to the sub agents, or handles the subagents communication. Do not solve the task on your own.",
    )


@retry_test(max_attempts=6)
def test_swarm_uses_handoff_tool_in_always_handoff_mode(vllm_responses_llm):
    """
    Failure rate:          18 out of 100
    Observed on:           2025-12-22
    Average success time:  8.97 seconds per successful attempt
    Average failure time:  3.65 seconds per failed attempt
    Max attempt:           6
    Justification:         (0.19 ** 6) ~= 4.2 / 100'000
    """

    llm = vllm_responses_llm

    main_agent = get_first_agent(llm)
    debugger_agent = get_debugger_agent(llm)
    fixer_agent = get_fixer_agent(llm)

    swarm = Swarm(
        first_agent=main_agent,
        relationships=[
            (main_agent, debugger_agent),
            (debugger_agent, main_agent),
            (main_agent, fixer_agent),
            (fixer_agent, main_agent),
            (debugger_agent, fixer_agent),
        ],
        handoff=HandoffMode.ALWAYS,
    )

    conv = swarm.start_conversation(
        messages="Do we have any bugs on the `amazon` product? If yes, fix them."
    )
    conv.execute()

    expected_tool_requests = [
        ("handoff_conversation", {"recipient": "debugger_agent"}),
        ("get_bug", {}),
        ("handoff_conversation", {"recipient": "fixer_agent"}),
        ("fix_bug", {}),
    ]
    all_tool_requests = [
        tq for message in conv.get_messages() for tq in (message.tool_requests or [])
    ]

    assert len(all_tool_requests) > 0

    for tool_request, (expected_tool_name, expected_params) in zip(
        all_tool_requests,
        expected_tool_requests,
        strict=False,
        # ^ sometime the agent yields to tell the user about the bug before fixing it
        # -> handoff_conversation, fix_bug might not be in the tool requests.
    ):
        assert tool_request.name == expected_tool_name
        for k, v in expected_params.items():
            assert tool_request.args[k] == v


@retry_test(max_attempts=3)
def test_swarm_uses_handoff_tool_when_sub_agent_can_take_over_in_optional_handoff_mode(
    vllm_responses_llm,
):
    """
    Failure rate:          1 out of 100
    Observed on:           2025-12-10
    Average success time:  3.50 seconds per successful attempt
    Average failure time:  606.05 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.8 / 100'000
    """

    llm = vllm_responses_llm

    main_agent = get_first_agent(llm)
    debugger_agent = get_debugger_agent(llm)
    swarm = Swarm(
        first_agent=main_agent,
        relationships=[
            (main_agent, debugger_agent),
            (debugger_agent, main_agent),
        ],
        handoff=HandoffMode.ALWAYS,
    )

    conv = swarm.start_conversation(messages="Do we have any bugs on the `amazon` product?")
    conv.execute()

    expected_tool_requests = [
        ("handoff_conversation", {"recipient": "debugger_agent"}),
        ("get_bug", {}),
    ]
    all_tool_requests = [
        tq for message in conv.get_messages() for tq in (message.tool_requests or [])
    ]
    for tool_request, (expected_tool_name, expected_params) in zip(
        all_tool_requests, expected_tool_requests, strict=True
    ):
        assert tool_request.name == expected_tool_name
        for k, v in expected_params.items():
            assert tool_request.args[k] == v


@retry_test(max_attempts=6)
def test_swarm_uses_send_message_when_collaboration_needed_in_optional_handoff_mode(
    vllm_responses_llm,
):
    """
    Failure rate:          16 out of 100
    Observed on:           2025-12-11
    Average success time:  11.60 seconds per successful attempt
    Average failure time:  13.25 seconds per failed attempt
    Max attempt:           6
    Justification:         (0.17 ** 6) ~= 2.1 / 100'000
    """

    llm = vllm_responses_llm

    main_agent = get_first_agent(llm)
    debugger_agent = get_debugger_agent(llm)
    fixer_agent = get_fixer_agent(llm)

    swarm = Swarm(
        first_agent=main_agent,
        relationships=[
            (main_agent, debugger_agent),
            (debugger_agent, main_agent),
            (main_agent, fixer_agent),
            (fixer_agent, main_agent),
            (debugger_agent, fixer_agent),
        ],
        handoff=HandoffMode.OPTIONAL,
    )

    conv = swarm.start_conversation(
        messages="Do we have any bugs on the `amazon` product? If yes, fix them."
    )
    conv.execute()

    expected_tool_requests = [
        ("send_message", {"recipient": "debugger_agent"}),
        ("send_message", {"recipient": "fixer_agent"}),
    ]

    all_tool_requests = [
        tq for message in conv.get_messages() for tq in (message.tool_requests or [])
    ]
    for tool_request, (expected_tool_name, expected_params) in zip(
        all_tool_requests, expected_tool_requests, strict=True
    ):
        assert tool_request.name == expected_tool_name
        for k, v in expected_params.items():
            assert tool_request.args[k] == v


def test_multiple_tool_calling_with_nested_client_tool_request_does_not_raise_error(
    vllm_responses_llm,
):
    llm = vllm_responses_llm

    main_agent = get_first_agent(llm)
    agent_with_client_tool = _get_agent_with_client_tool(llm)
    fooza_agent = _get_fooza_agent(llm)

    swarm = Swarm(
        first_agent=main_agent,
        relationships=[(main_agent, agent_with_client_tool), (main_agent, fooza_agent)],
    )

    conv = swarm.start_conversation(
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
            multiple_tool_requests,  # output from main_agent
            client_tool_request,  # output from agent_with_client_tool
            "agent_with_client_tool_answers",
            "fooza_agent_answers",
            "main_agent_answers",
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
        assert isinstance(status_2, UserMessageRequestStatus)  # yielding from main_agent
        assert conv.get_last_message().content == "main_agent_answers"


def test_multiple_tool_calling_with_nested_send_message_tool_request_can_be_executed(
    vllm_responses_llm,
):
    llm = vllm_responses_llm

    main_agent = get_first_agent(llm)
    agent_1 = Agent(llm=llm, description="agent 1", name="agent_1")
    agent_2 = Agent(llm=llm, description="agent 2", name="agent_2")

    swarm = Swarm(
        first_agent=main_agent,
        relationships=[
            (main_agent, agent_1),
            (main_agent, agent_2),
            (agent_1, agent_2),
        ],
    )

    conv = swarm.start_conversation(messages="Dummy message")
    multiple_tool_requests = [
        ToolRequest(
            name="send_message",
            args={"recipient": "agent_1", "message": "message to agent 1 from main agent"},
        ),
        ToolRequest(
            name="send_message",
            args={"recipient": "agent_2", "message": "message to agent 2 from main agent"},
        ),
    ]
    send_message_request = [
        ToolRequest(
            name="send_message",
            args={"recipient": "agent_2", "message": "message to agent 2 from agent 1"},
        ),
    ]

    with patch_llm(
        llm,
        outputs=[
            multiple_tool_requests,  # output from main agent
            send_message_request,  # output from agent 1
            "agent 2 answers to agent 1",
            "agent 1 answers to main agent",
            "agent 2 answers to main agent",
            "main agent answers to user",
        ],
    ):
        status = conv.execute()
        assert isinstance(status, UserMessageRequestStatus)
        assert conv.get_last_message().content == "main agent answers to user"


def test_multiple_tool_calls_including_client_tool_can_be_executed(vllm_responses_llm):
    llm = vllm_responses_llm

    agent_with_client_tool = _get_agent_with_client_tool(llm)
    fooza_agent = _get_fooza_agent(llm)

    swarm = Swarm(
        first_agent=agent_with_client_tool,
        relationships=[(agent_with_client_tool, fooza_agent)],
    )

    conv = swarm.start_conversation(
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
            multiple_tool_requests,  # output from first agent (i.e. agent_with_client_tool)
            "fooza_answers_to_main_agent",
            "main_agent_answers_to_user",
        ],
    ):
        status = conv.execute()
        assert isinstance(status, ToolRequestStatus)  # yielding from first_agent
        assert len(status.tool_requests) == 1  # The send_message should not appear in the status
        assert status.tool_requests[0].name == "check_name_in_db_tool"
        status.submit_tool_result(
            ToolResult(
                content="The name Alice is present in the database", tool_request_id="client_tool"
            )
        )

        status_2 = conv.execute()
        assert isinstance(status_2, UserMessageRequestStatus)
        assert conv.get_last_message().content == "main_agent_answers_to_user"


def test_multiple_tool_calls_including_server_tool_can_be_executed(vllm_responses_llm):
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)

    swarm = Swarm(
        first_agent=fooza_agent,
        relationships=[(fooza_agent, bwip_agent)],
    )

    conv = swarm.start_conversation(messages="Compute bwip(4,2) fooza(4,3) and bwip(4,5)")

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
            multiple_tool_requests,
            "bwip answers to fooza",
            "bwip answers to fooza",
            "fooza answers to user",
        ],
    ):
        status = conv.execute()
        assert isinstance(status, UserMessageRequestStatus)
        assert conv.get_last_message().content == "fooza answers to user"


def test_multiple_tool_calls_after_handoff_get_cancelled(vllm_responses_llm):
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    main_agent = get_first_agent(llm)

    math_swarm = Swarm(
        first_agent=main_agent,
        relationships=[(main_agent, agent) for agent in [fooza_agent, bwip_agent]],
    )

    # Multiple tool calls
    tool_requests = [
        ToolRequest(
            name="handoff_conversation",
            args={"recipient": "fooza_agent", "message": "Compute the result of fooza(4, 2)"},
            tool_request_id="handoff",
        ),
        ToolRequest(
            name="send_message",
            args={"recipient": "bwip_agent", "message": "Compute bwip(4,5)"},
            tool_request_id="send_message",
        ),
    ]
    with patch_llm(llm, outputs=[tool_requests, "dummy_test"]):
        conv = math_swarm.start_conversation(
            messages="Compute the result of fooza(4, 2) + bwip(4, 5)"
        )
        conv.execute()
        assert (
            conv.state.current_thread.recipient_agent == fooza_agent
        )  # The handoff tool is executed
        for message in conv.get_messages():
            if message.tool_result and message.tool_result.tool_request_id == "send_message":
                assert (
                    message.tool_result.content
                    == "Calling 'send_message' after the handoff is not possible. Cancelling call to tool 'send_message'"
                )


@retry_test(max_attempts=3)
def test_swarm_can_do_multiple_tool_calling_when_appropriate(vllm_responses_llm):
    """
    Failure rate:          1 out of 50
    Observed on:           2025-12-22
    Average success time:  11.72 seconds per successful attempt
    Average failure time:  3.71 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000
    """
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)
    main_agent = get_first_agent(llm)
    main_agent.custom_instruction = (
        "You are the main agent. You SHOULD output all the tool calls at once when approriate."
    )

    math_swarm = Swarm(
        first_agent=main_agent,
        relationships=[(main_agent, agent) for agent in [fooza_agent, bwip_agent, zbuk_agent]],
    )

    conv = math_swarm.start_conversation(
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
        second_message.tool_requests, expected_tool_requests
    ):
        assert tool_request.name == expected_tool_name
        for k, v in expected_params.items():
            assert tool_request.args[k] == v

    result = fooza_tool.func(4, 2) + bwip_tool.func(4, 5) + zbuk_tool.func(5, 6)
    assert str(result) in conv.get_last_message().content


def _setup_swarm_for_multiple_tool_calling(vllm_responses_llm, raise_exceptions):
    llm = vllm_responses_llm
    fooza_agent = _get_fooza_agent(
        llm, raise_exception_tool=True, raise_exceptions=raise_exceptions
    )
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)
    main_agent = get_first_agent(llm)
    main_agent.custom_instruction = "You are the main agent. You SHOULD output all the tool calls at once when approriate. If you are unable to obtain a complete result, return the partial result instead."

    math_swarm = Swarm(
        first_agent=main_agent,
        relationships=[(main_agent, agent) for agent in [fooza_agent, bwip_agent, zbuk_agent]],
    )

    conv = math_swarm.start_conversation(
        messages="Compute the result of fooza(4, 2) + bwip(4, 5) + zbuk(5, 6)"
    )

    return conv


@retry_test(max_attempts=3)
def test_swarm_can_do_multiple_tool_calling_with_tool_raising_exception_raises_error(
    vllm_responses_llm,
):
    """
    Failure rate:          0 out of 20
    Observed on:           2026-01-28
    Average success time:  5.19 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    conv = _setup_swarm_for_multiple_tool_calling(vllm_responses_llm, raise_exceptions=True)
    with pytest.raises(ValueError, match="Cannot compute result using fooza tool."):
        conv.execute()


@retry_test(max_attempts=5)
def test_swarm_can_do_multiple_tool_calling_with_tool_raising_exception_does_not_raise_error(
    vllm_responses_llm,
):
    """
    Failure rate:          2 out of 20
    Observed on:           2026-01-28
    Average success time:  14.45 seconds per successful attempt
    Average failure time:  21.04 seconds per failed attempt
    Max attempt:           5
    Justification:         (0.14 ** 5) ~= 4.7 / 100'000
    """
    conv = _setup_swarm_for_multiple_tool_calling(vllm_responses_llm, raise_exceptions=False)
    conv.execute()
    result = bwip_tool.func(4, 5) + zbuk_tool.func(5, 6)
    assert str(result) in conv.get_last_message().content


@retry_test(max_attempts=4)
def test_swarm_without_user_input_can_execute_as_expected(vllm_responses_llm):
    """
    Failure rate:          3 out of 50
    Observed on:           2025-12-24
    Average success time:  9.38 seconds per successful attempt
    Average failure time:  3.74 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 3.5 / 100'000
    """
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    main_agent = get_first_agent(llm)

    math_swarm = Swarm(
        first_agent=main_agent,
        relationships=[(main_agent, fooza_agent), (main_agent, bwip_agent)],
        output_descriptors=[
            IntegerProperty("result", description="The result of the user request")
        ],
        caller_input_mode=CallerInputMode.NEVER,
    )

    conv = math_swarm.start_conversation(messages="Compute the result of fooza(4, 2) + bwip(4, 5)")
    status = conv.execute()
    assert isinstance(status, FinishedStatus)

    result = fooza_tool.func(4, 2) + bwip_tool.func(4, 5)
    assert status.output_values["result"] == result
