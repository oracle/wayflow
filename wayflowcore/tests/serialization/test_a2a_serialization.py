# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import warnings

import pytest

from wayflowcore.a2a.a2aagent import A2AAgent, A2AConnectionConfig
from wayflowcore.executors._a2aagentconversation import A2AAgentConversation
from wayflowcore.serialization import deserialize, serialize

from ..testhelpers.testhelpers import retry_test


@pytest.fixture(scope="session")
def connection_config_no_verify():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return A2AConnectionConfig(verify=False)


@pytest.fixture(scope="session")
def a2a_agent(a2a_server, connection_config_no_verify):
    return A2AAgent(
        name="A2A Agent",
        agent_url=a2a_server,
        connection_config=connection_config_no_verify,
    )


def assert_a2aagents_are_equal(old_agent: A2AAgent, new_agent: A2AAgent):
    assert old_agent.name == new_agent.name
    assert old_agent.description == new_agent.description
    assert old_agent.id == new_agent.id
    assert old_agent.__metadata_info__ == new_agent.__metadata_info__
    assert old_agent.agent_url == new_agent.agent_url
    assert old_agent.connection_config.timeout == new_agent.connection_config.timeout
    assert old_agent.connection_config.verify == new_agent.connection_config.verify
    assert old_agent.session_parameters.timeout == new_agent.session_parameters.timeout
    assert old_agent.session_parameters.poll_interval == new_agent.session_parameters.poll_interval
    assert old_agent.session_parameters.max_retries == new_agent.session_parameters.max_retries


def test_can_serialize_a2aagent(a2a_agent) -> None:
    serialized_a2aagent = serialize(a2a_agent)
    assert isinstance(serialized_a2aagent, str)


def test_can_deserialize_a_serialized_a2aagent(a2a_agent) -> None:
    serialized_a2aagent = serialize(a2a_agent)
    with pytest.warns(
        UserWarning,
        match="SSL verification is disabled. This is not recommended for production environments.",
    ):
        deserialized_a2aagent = deserialize(A2AAgent, serialized_a2aagent)
        assert_a2aagents_are_equal(a2a_agent, deserialized_a2aagent)


def test_can_serialize_a2aconversation(a2a_agent) -> None:
    conversation = a2a_agent.start_conversation()
    serialized_conversation = serialize(conversation)
    assert isinstance(serialized_conversation, str)


def test_can_deserialize_a_serialized_a2aconversation(a2a_agent) -> None:
    conversation = a2a_agent.start_conversation()
    conversation.append_user_message("What is 1+1?")
    conversation.append_user_message("What is 2+2?")
    serialized_conversation = serialize(conversation)
    with pytest.warns(
        UserWarning,
        match="SSL verification is disabled. This is not recommended for production environments.",
    ):
        deserialized_conversation = deserialize(A2AAgentConversation, serialized_conversation)
        assert_a2aagents_are_equal(conversation.component, deserialized_conversation.component)
        assert isinstance(deserialized_conversation, A2AAgentConversation)
        assert len(deserialized_conversation.message_list) == len(conversation.message_list)
        assert deserialized_conversation.message_list == conversation.message_list


@retry_test(max_attempts=4)
def test_can_continue_a_deserialized_a2aconversation(a2a_agent) -> None:
    """
    Failure rate:          0 out of 15
    Observed on:           2025-11-19
    Average success time:  4.41 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    conversation = a2a_agent.start_conversation()
    conversation.append_user_message("What is 5+5? Just output the answer.")
    conversation.execute()
    conv_length_before_serialization = len(conversation.message_list)
    serialized_conversation = serialize(conversation)
    with pytest.warns(
        UserWarning,
        match="SSL verification is disabled. This is not recommended for production environments.",
    ):
        deserialized_conversation = deserialize(A2AAgentConversation, serialized_conversation)
        assert_a2aagents_are_equal(conversation.component, deserialized_conversation.component)
        assert len(deserialized_conversation.message_list) == conv_length_before_serialization
        deserialized_conversation.append_user_message(
            "What if you replace 5 by 10? Just output the answer."
        )
        status = deserialized_conversation.execute()
        assert len(deserialized_conversation.message_list) > conv_length_before_serialization
        assert "20" in deserialized_conversation.get_last_message().content
