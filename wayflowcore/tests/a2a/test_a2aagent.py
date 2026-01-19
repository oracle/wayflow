# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import warnings

import httpx
import pytest

from wayflowcore.a2a.a2aagent import A2AAgent, A2AConnectionConfig, A2ASessionParameters
from wayflowcore.executors._a2aagentconversation import A2AAgentConversation
from wayflowcore.executors._a2aagentexecutor import DEFAULT_RESPONSE
from wayflowcore.messagelist import Message

from ..testhelpers.testhelpers import retry_test

####### Fixtures #######


@pytest.fixture(scope="session")
def connection_config_no_verify():
    with pytest.warns(
        UserWarning,
        match="SSL verification is disabled. This is not recommended for production environments.",
    ):
        return A2AConnectionConfig(verify=False)


@pytest.fixture(scope="session")
def a2a_agent(a2a_server, connection_config_no_verify):
    return A2AAgent(
        name="A2A Agent",
        agent_url=a2a_server,
        connection_config=connection_config_no_verify,
    )


####### Tests checking inputs to `A2AAgent` #######


def test_a2aagent_accepts_valid_url(a2a_server, connection_config_no_verify):
    A2AAgent(agent_url=a2a_server, connection_config=connection_config_no_verify)


def test_a2aagent_rejects_invalid_string_url(connection_config_no_verify):
    incorrect_url = "1234"
    with pytest.raises(ValueError, match="Invalid URL provided for agent_url: 1234"):
        A2AAgent(agent_url=incorrect_url, connection_config=connection_config_no_verify)


def test_a2aconnectionconfig_rejects_negative_connection_timeout():
    with pytest.raises(ValueError, match="timeout must be positive, got -1"):
        invalid_config = A2AConnectionConfig(timeout=-1, verify=False)


def test_a2aconnectionconfig_rejects_nonexistent_key_file():
    with pytest.raises(ValueError, match="key_file path does not exist: /nonexistent/path/key.pem"):
        invalid_config = A2AConnectionConfig(key_file="/nonexistent/path/key.pem", verify=True)


def test_a2aconnectionconfig_rejects_nonexistent_cert_file():
    with pytest.raises(
        ValueError, match="cert_file path does not exist: /nonexistent/path/cert.pem"
    ):
        invalid_config = A2AConnectionConfig(cert_file="/nonexistent/path/cert.pem", verify=True)


def test_a2aconnectionconfig_rejects_nonexistent_ssl_ca_cert():
    with pytest.raises(
        ValueError, match="ssl_ca_cert path does not exist: /nonexistent/path/ca.pem"
    ):
        invalid_config = A2AConnectionConfig(ssl_ca_cert="/nonexistent/path/ca.pem", verify=True)


def test_a2asessionparameters_rejects_negative_session_timeout():
    with pytest.raises(ValueError, match="timeout must be positive, got -1"):
        invalid_params = A2ASessionParameters(timeout=-1)


def testa2asessionparameters_rejects_negative_poll_interval():
    with pytest.raises(ValueError, match="poll_interval must be positive, got -1"):
        invalid_params = A2ASessionParameters(poll_interval=-1)


def test_a2asessionparameters_rejects_negative_max_retries():
    with pytest.raises(ValueError, match="max_retries must be non-negative, got -1"):
        invalid_params = A2ASessionParameters(max_retries=-1)


####### Tests related to conversations using `A2AAgent` #######


def test_a2aagent_creates_conversation_instance(a2a_agent):
    conversation = a2a_agent.start_conversation()
    assert isinstance(conversation, A2AAgentConversation)


def test_a2aagent_no_message_conversation(a2a_agent):
    conversation = a2a_agent.start_conversation()
    status = conversation.execute()
    assert status.message.contents[0].content == DEFAULT_RESPONSE


@retry_test(max_attempts=4)
def test_a2aagent_handles_single_message_conversation(a2a_agent):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-11-18
    Average success time:  2.03 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    conversation = a2a_agent.start_conversation()
    conversation.append_user_message("What is 20*8? Just output the answer.")
    status = conversation.execute()
    assert "160" in conversation.get_last_message().content


@retry_test(max_attempts=4)
def test_a2aagent_passing_single_message_in_conversation_directly(a2a_agent):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-11-18
    Average success time:  2.03 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    message = Message("What is 20*8? Just output the answer.")
    conversation = a2a_agent.start_conversation(messages=[message])
    status = conversation.execute()
    assert "160" in conversation.get_last_message().content


@retry_test(max_attempts=4)
def test_a2aagent_handles_multiple_messages_conversation(a2a_agent):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-11-18
    Average success time:  4.23 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    conversation = a2a_agent.start_conversation()
    conversation.append_user_message("What is 2+2?")
    conversation.append_user_message("What is 3+3?")
    conversation.append_user_message(
        "Can you add the previous two results? Just output the answer.",
    )
    status = conversation.execute()
    assert "10" in conversation.get_last_message().content


@retry_test(max_attempts=4)
def test_a2aagent_passing_multiple_messages_in_conversation_directly(a2a_agent):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-11-18
    Average success time:  4.34 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    messages = [
        Message("What is 2+2?"),
        Message("What is 3+3?"),
        Message("Can you add the previous two results? Just output the answer."),
    ]
    conversation = a2a_agent.start_conversation(messages=messages)
    status = conversation.execute()
    assert "10" in conversation.get_last_message().content


@retry_test(max_attempts=4)
def test_a2aagent_continues_conversation_after_execution(a2a_agent):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-11-18
    Average success time:  6.07 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    conversation = a2a_agent.start_conversation()
    conversation.append_user_message("What is 2+2?")
    status = conversation.execute()
    conversation.append_user_message("What is 3+3?")
    status = conversation.execute()
    conversation.append_user_message(
        "Can you add the previous two results? Just output the answer.",
    )
    status = conversation.execute()
    assert "10" in conversation.get_last_message().content


@retry_test(max_attempts=4)
def test_a2aagent_manages_multiple_independent_conversations(a2a_agent):
    """
    Failure rate:          0 out of 10
    Observed on:           2025-11-18
    Average success time:  6.00 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    conversation = a2a_agent.start_conversation()
    conversation.append_user_message("What is 2+2?")
    conversation.append_user_message("What is 3+3?")
    conversation.append_user_message(
        "Can you add the previous two results? Just output the answer.",
    )
    status = conversation.execute()
    assert "10" in conversation.get_last_message().content
    conversation2 = a2a_agent.start_conversation()
    conversation2.append_user_message(
        "Can you add the previous two results? Just output the answer."
    )
    status = conversation2.execute()
    assert "10" not in conversation2.get_last_message().content


@retry_test(max_attempts=5)
def test_a2aagent_with_multiple_agents_with_separate_conversations(
    a2a_server, connection_config_no_verify
):
    """
    Failure rate:          0 out of 8
    Observed on:           2025-11-18
    Average success time:  8.12 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           5
    Justification:         (0.10 ** 5) ~= 1.0 / 100'000
    """
    a2aagent_1 = A2AAgent(agent_url=a2a_server, connection_config=connection_config_no_verify)
    a2aagent_2 = A2AAgent(agent_url=a2a_server, connection_config=connection_config_no_verify)
    conversation_1 = a2aagent_1.start_conversation()
    conversation_1.append_user_message("What is 2+2?")
    conversation_1.append_user_message("What is 3+3?")
    conversation_1.append_user_message(
        "Can you add the previous two results? Just output the answer.",
    )
    conversation_2 = a2aagent_2.start_conversation()
    conversation_2.append_user_message("What is 1+1?")
    conversation_2.append_user_message("What is 5+5?")
    conversation_2.append_user_message(
        "Can you add the previous two results? Just output the answer.",
    )
    status = conversation_1.execute()
    assert "10" in conversation_1.get_last_message().content
    status = conversation_2.execute()
    assert "12" in conversation_2.get_last_message().content


####### Tests causing timeouts with `A2AAgent` #######


def test_a2aagent_causes_timeout_with_custom_session_parameters(
    a2a_server, connection_config_no_verify
):
    session_parameters = A2ASessionParameters(timeout=0.1, poll_interval=1, max_retries=1)
    a2a_agent = A2AAgent(
        agent_url=a2a_server,
        connection_config=connection_config_no_verify,
        session_parameters=session_parameters,
    )
    conversation = a2a_agent.start_conversation()
    conversation.append_user_message("What is 5*5? Just output the answer.")
    with pytest.raises(
        TimeoutError, match=r"Task ([A-Za-z0-9_%-]+) did not complete within 0.1 seconds"
    ):
        status = conversation.execute()


def test_a2aagent_causes_timeout_with_custom_connection_config(a2a_server):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        config = A2AConnectionConfig(timeout=0.0001, verify=False)
    a2a_agent = A2AAgent(agent_url=a2a_server, connection_config=config)
    conversation = a2a_agent.start_conversation()
    conversation.append_user_message("What is 3*3? Just output the answer.")
    # This timeout is raised by httpx, hence using `httpx.ConnectTimeout`
    with pytest.raises(httpx.ConnectTimeout):
        status = conversation.execute()


@pytest.mark.skip("Server does not start reliably in CI (issue #33)")
@retry_test(max_attempts=3)
def test_adk_a2aagent_replies_with_a_message(adk_a2a_server, connection_config_no_verify):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-12-03
    Average success time:  0.66 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    a2a_agent = A2AAgent(
        name="ADK A2A Agent",
        agent_url=adk_a2a_server,
        connection_config=connection_config_no_verify,
    )
    conversation = a2a_agent.start_conversation()
    conversation.append_user_message("What is 4*4? Use the tools to compute it.")
    status = conversation.execute()
    assert "16" in conversation.get_last_message().content
