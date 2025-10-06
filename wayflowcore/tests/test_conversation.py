# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import List

import pytest

from wayflowcore.agent import Agent
from wayflowcore.flow import Flow
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.steps import InputMessageStep, OutputMessageStep
from wayflowcore.swarm import Swarm

from .testhelpers.dummy import DummyModel

# FOR AGENT
USER_MSG_1 = "User message 1"
USER_MSG_2 = "User message 2"
AGENT_MSG_1 = "Agent message 1"
AGENT_MSG_2 = "Agent message 2"

# FOR FLOW
INPUT_MSG = "Input message"
USER_MSG = "User message"
OUTPUT_MSG = "Output message"


@pytest.fixture()
def agent() -> Agent:
    llm = DummyModel()
    llm.set_next_output([AGENT_MSG_1, AGENT_MSG_2])
    return Agent(llm=llm)


@pytest.fixture()
def flow() -> Flow:
    return Flow.from_steps([InputMessageStep(INPUT_MSG), OutputMessageStep(OUTPUT_MSG)])


@pytest.fixture()
def swarm() -> Swarm:
    llm = DummyModel()
    llm.set_next_output([AGENT_MSG_1, AGENT_MSG_2])

    first_agent = Agent(
        name="agent1",
        description="agent 1",
        llm=llm,
    )
    recipient_agent = Agent(
        name="agent2",
        description="agent 2",
        llm=llm,
    )
    return Swarm(first_agent=first_agent, relationships=[(first_agent, recipient_agent)])


@pytest.fixture()
def managerworkers() -> ManagerWorkers:
    llm = DummyModel()
    llm.set_next_output([AGENT_MSG_1, AGENT_MSG_2])

    worker = Agent(name="worker", description="worker", llm=llm)
    return ManagerWorkers(group_manager=llm, workers=[worker])


def _assert_expected_agent_messages(messages: List[Message]):
    assert len(messages) == 4

    user_message1, agent_message1, user_message2, agent_message2 = messages

    assert user_message1.message_type == MessageType.USER and user_message1.content == USER_MSG_1
    assert (
        agent_message1.message_type == MessageType.AGENT and agent_message1.content == AGENT_MSG_1
    )
    assert user_message2.message_type == MessageType.USER and user_message2.content == USER_MSG_2
    assert (
        agent_message2.message_type == MessageType.AGENT and agent_message2.content == AGENT_MSG_2
    )


def _assert_expected_flow_messages(messages: List[Message]):
    assert len(messages) == 3
    input_message, user_message, output_message = messages

    assert input_message.content == INPUT_MSG
    assert user_message.message_type == MessageType.USER and user_message.content == USER_MSG
    assert output_message.content == OUTPUT_MSG


def test_flow_execute_produces_expected_messages(flow: Flow):
    conv = flow.start_conversation()
    flow.execute(conv)
    conv.append_user_message(USER_MSG)
    flow.execute(conv)
    _assert_expected_flow_messages(conv.get_messages())


def test_flowconversation_execute_produces_expected_messages(flow: Flow):
    conv = flow.start_conversation()
    conv.execute()
    conv.append_user_message(USER_MSG)
    conv.execute()
    _assert_expected_flow_messages(conv.get_messages())


def test_agent_execute_produces_expected_messages(agent: Agent):
    conv = agent.start_conversation()
    conv.append_user_message(USER_MSG_1)

    agent.execute(conv)
    conv.append_user_message(USER_MSG_2)
    agent.execute(conv)
    _assert_expected_agent_messages(conv.get_messages())


def test_agentconversation_execute_produces_expected_messages(agent: Agent):
    conv = agent.start_conversation()
    conv.append_user_message(USER_MSG_1)

    conv.execute()
    conv.append_user_message(USER_MSG_2)
    conv.execute()
    _assert_expected_agent_messages(conv.get_messages())


def test_swarm_execute_produces_expected_messages(swarm: Swarm):
    conv = swarm.start_conversation()
    conv.append_user_message(USER_MSG_1)

    swarm.execute(conv)
    conv.append_user_message(USER_MSG_2)
    swarm.execute(conv)
    _assert_expected_agent_messages(conv.get_messages())


def test_swarmconversation_execute_produces_expected_messages(swarm: Swarm):
    conv = swarm.start_conversation()
    conv.append_user_message(USER_MSG_1)

    conv.execute()
    conv.append_user_message(USER_MSG_2)
    conv.execute()
    _assert_expected_agent_messages(conv.get_messages())


def test_managerworkerconversation_execute_produces_expected_messages(
    managerworkers: ManagerWorkers,
):
    conv = managerworkers.start_conversation()
    conv.append_user_message(USER_MSG_1)

    conv.execute()
    conv.append_user_message(USER_MSG_2)
    conv.execute()
    _assert_expected_agent_messages(conv.get_messages())
