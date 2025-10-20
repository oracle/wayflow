# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Union

import pytest

from wayflowcore.agent import Agent
from wayflowcore.executors._swarmconversation import (
    SwarmConversation,
    SwarmConversationExecutionState,
    SwarmThread,
    SwarmUser,
)
from wayflowcore.serialization import deserialize, serialize, serialize_to_dict
from wayflowcore.swarm import Swarm

from ..conftest import _assert_config_are_equal
from ..test_swarm import example_medical_agents  # noqa
from .test_conversation_serialization import assert_agent_conversations_are_equal


@pytest.fixture
def simple_thread(example_medical_agents) -> SwarmThread:
    gp_doctor, neurologist_doctor, oncologist_doctor = example_medical_agents
    return SwarmThread(
        gp_doctor,
        recipient_agent=neurologist_doctor,
    )


@pytest.fixture
def simple_swarm(example_medical_agents) -> Swarm:
    gp_doctor, neurologist_doctor, oncologist_doctor = example_medical_agents
    return Swarm(
        first_agent=gp_doctor,
        relationships=[
            (gp_doctor, neurologist_doctor),
            (gp_doctor, oncologist_doctor),
            (neurologist_doctor, oncologist_doctor),
        ],
    )


@pytest.fixture
def simple_conversation(simple_swarm: Swarm) -> SwarmConversation:
    return simple_swarm.start_conversation()


@pytest.fixture
def simple_state(simple_conversation: SwarmConversation) -> SwarmConversationExecutionState:
    return simple_conversation.state


def assert_swarm_agents_are_equal(
    old_agent: Union[Agent, SwarmUser],
    new_agent: Union[Agent, SwarmUser],
):
    if isinstance(old_agent, SwarmUser) and isinstance(new_agent, SwarmUser):
        return

    assert old_agent.name == new_agent.name
    assert old_agent.description == new_agent.description
    assert old_agent.__metadata_info__ == new_agent.__metadata_info__
    assert old_agent.id == new_agent.id


def assert_swarm_threads_are_equal(old_thread: SwarmThread, new_thread: SwarmThread):
    assert_swarm_agents_are_equal(old_thread.caller, new_thread.caller)
    assert_swarm_agents_are_equal(old_thread.recipient_agent, new_thread.recipient_agent)
    assert len(old_thread.message_list) == len(new_thread.message_list)
    assert old_thread.is_main_thread == new_thread.is_main_thread
    assert old_thread.__metadata_info__ == new_thread.__metadata_info__
    assert old_thread.id == new_thread.id


def assert_swarm_states_are_equal(
    old_state: SwarmConversationExecutionState, new_state: SwarmConversationExecutionState
):
    assert_swarm_threads_are_equal(old_state.main_thread, new_state.main_thread)

    assert old_state.agents_and_threads.keys() == new_state.agents_and_threads.keys()
    for caller_agent_name in old_state.agents_and_threads:
        old_recipients_and_threads = old_state.agents_and_threads[caller_agent_name]
        new_recipients_and_threads = new_state.agents_and_threads[caller_agent_name]
        assert old_recipients_and_threads.keys() == new_recipients_and_threads.keys()
        for recipient_agent_name in old_recipients_and_threads:
            assert_swarm_threads_are_equal(
                old_recipients_and_threads[recipient_agent_name],
                new_recipients_and_threads[recipient_agent_name],
            )

    assert_swarm_threads_are_equal(old_state.current_thread, new_state.current_thread)
    assert len(old_state.thread_stack) == len(new_state.thread_stack)
    for old_thread, new_thread in zip(old_state.thread_stack, new_state.thread_stack):
        assert_swarm_threads_are_equal(old_thread, new_thread)

    assert old_state.__metadata_info__ == new_state.__metadata_info__
    assert old_state.id == new_state.id


def assert_swarms_are_equal(old_swarm: Swarm, new_swarm: Swarm):
    assert_swarm_agents_are_equal(old_swarm.first_agent, new_swarm.first_agent)
    assert len(old_swarm.relationships) == len(new_swarm.relationships)
    for (old_caller_agent, old_recipient_agent), (new_caller_agent, new_recipient_agent) in zip(
        old_swarm.relationships, new_swarm.relationships
    ):
        assert_swarm_agents_are_equal(old_caller_agent, new_caller_agent)
        assert_swarm_agents_are_equal(old_recipient_agent, new_recipient_agent)

    assert old_swarm.__metadata_info__ == new_swarm.__metadata_info__
    assert old_swarm.id == new_swarm.id


def assert_swarm_conversations_are_equal(
    old_conversation: SwarmConversation, new_conversation: SwarmConversation
):
    assert_swarms_are_equal(old_conversation.swarm, new_conversation.swarm)
    assert_swarm_states_are_equal(old_conversation.state, new_conversation.state)
    assert old_conversation.inputs == new_conversation.inputs
    assert len(old_conversation.thread_subconversations) == len(
        new_conversation.thread_subconversations
    )
    assert (
        old_conversation.thread_subconversations.keys()
        == new_conversation.thread_subconversations.keys()
    )
    for thread_id in old_conversation.thread_subconversations:
        old_agent_conv = old_conversation.thread_subconversations[thread_id]
        new_agent_conv = new_conversation.thread_subconversations[thread_id]

        assert_agent_conversations_are_equal(old_agent_conv, new_agent_conv)

    assert (
        new_conversation.state.main_thread.message_list
        is new_conversation._get_subconversation_for_thread(
            new_conversation.state.main_thread
        ).message_list
    )

    assert old_conversation.__metadata_info__ == new_conversation.__metadata_info__
    assert old_conversation.id == new_conversation.id


def test_can_serialize_simple_thread(simple_thread: SwarmThread) -> None:
    serialized_thread = serialize(simple_thread)
    assert isinstance(serialized_thread, str)

    assert serialized_thread.count(" agent/") == 4  # 2 references, 1 caller, 1 recipient
    assert "GeneralistDoctor" in serialized_thread
    assert "NeurologistDoctor" in serialized_thread


def test_can_deserialize_a_serialized_thread(simple_thread: SwarmThread) -> None:
    new_thread = deserialize(SwarmThread, serialize(simple_thread))

    _assert_config_are_equal(
        serialize_to_dict(simple_thread),
        serialize_to_dict(new_thread),
    )
    assert_swarm_threads_are_equal(simple_thread, new_thread)


def test_can_serialize_simple_state(simple_state: SwarmConversationExecutionState) -> None:
    serialized_state = serialize(simple_state)
    assert isinstance(serialized_state, str)


def test_can_deserialize_a_serialized_state(simple_state: SwarmConversationExecutionState) -> None:
    new_state = deserialize(SwarmConversationExecutionState, serialize(simple_state))

    _assert_config_are_equal(
        serialize_to_dict(simple_state),
        serialize_to_dict(new_state),
    )


def test_can_serialize_simple_swarm(simple_swarm: Swarm) -> None:
    serialized_swarm = serialize(simple_swarm)
    assert isinstance(serialized_swarm, str)


def test_can_deserialize_a_serialized_swarm(simple_swarm: Swarm) -> None:
    serialized_swarm = serialize(simple_swarm)
    new_swarm = deserialize(Swarm, serialized_swarm)

    _assert_config_are_equal(
        serialize_to_dict(simple_swarm),
        serialize_to_dict(new_swarm),
    )
    assert_swarms_are_equal(simple_swarm, new_swarm)


def test_can_serialize_simple_conversation(simple_conversation: SwarmConversation) -> None:
    serialized_conversation = serialize(simple_conversation)
    assert isinstance(serialized_conversation, str)


def test_can_deserialize_a_serialized_conversation(simple_conversation: SwarmConversation) -> None:
    new_conversation = deserialize(SwarmConversation, serialize(simple_conversation))
    s1 = serialize_to_dict(simple_conversation)
    s2 = serialize_to_dict(new_conversation)
    _assert_config_are_equal(s1, s2)
    assert_swarm_conversations_are_equal(simple_conversation, new_conversation)


def test_can_continue_a_deserialized_swarm_conversation(simple_swarm: Swarm) -> None:
    conv = simple_swarm.start_conversation()
    conv.append_user_message(
        "I've been having very bad back pain for a few weeks, what should I do?"
    )
    conv.execute()
    conv_length_before_serialization = len(conv.get_messages())

    ser_conv = serialize(conv)
    deser_conv = deserialize(SwarmConversation, ser_conv)

    assert (
        deser_conv.state.main_thread.message_list
        is deser_conv._get_subconversation_for_thread(deser_conv.state.main_thread).message_list
    )

    deser_conv.append_user_message("Actually it's better now")
    assert len(deser_conv.get_messages()) == conv_length_before_serialization + 1
    deser_conv.execute()
