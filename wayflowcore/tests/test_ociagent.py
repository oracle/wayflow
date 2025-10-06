# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
import os

import pytest

from wayflowcore import Agent, Flow
from wayflowcore.ociagent import OciAgent
from wayflowcore.serialization.serializer import deserialize_from_dict, serialize_to_dict
from wayflowcore.steps import AgentExecutionStep
from wayflowcore.tools import ToolResult

from .testhelpers.testhelpers import retry_test


@pytest.fixture
def agent(oci_agent_client_config):
    oracle_process_helper_agent_endpoint_id = os.environ.get(
        "ORACLE_PROCESS_HELPER_AGENT_ENDPOINT_ID"
    )
    if not oracle_process_helper_agent_endpoint_id:
        raise Exception("ORACLE_PROCESS_HELPER_AGENT_ENDPOINT_ID is not set in the environment")
    pytest.skip("Skip since Agent does not work")
    return OciAgent(
        agent_endpoint_id=oracle_process_helper_agent_endpoint_id,
        client_config=oci_agent_client_config,
        name="oci_agent",
        description="agent that can help with question around Oracle processes and LTs",
    )


@retry_test(max_attempts=6)
def test_oci_knowledge_agent_simple_rag_question(agent):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-06-02
    Average success time:  3.95 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    conv = agent.start_conversation()
    conv.append_user_message("What does LT stand for?")
    conv.execute()

    last_message = conv.get_last_message().content
    assert "licensed" in last_message.lower()
    assert "technology" in last_message.lower()


# oci agent performance seems to fluctuate, we increase max_attempts to ensure CI reliability
@retry_test(max_attempts=6)
def test_oci_knowledge_agent_continue_conversation(agent):
    """
    Failure rate:          1 out of 20
    Observed on:           2025-06-02
    Average success time:  8.58 seconds per successful attempt
    Average failure time:  10.63 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 6.8 / 100'000
    """
    conv = agent.start_conversation()
    conv.append_user_message("What does LT stand for?")
    conv.execute()
    conv.append_user_message("What was my previous question again?")
    conv.execute()
    last_message = conv.get_last_message().content
    assert "lt" in last_message.lower()


# oci agent performance seems to fluctuate, we increase max_attempts to ensure CI reliability
@retry_test(max_attempts=10)
def test_oci_knowledge_agent_in_agent_execution_step(agent):
    """
    Failure rate:          4 out of 20
    Observed on:           2025-06-02
    Average success time:  8.60 seconds per successful attempt
    Average failure time:  10.90 seconds per failed attempt
    Max attempt:           7
    Justification:         (0.23 ** 7) ~= 3.1 / 100'000
    """
    step = AgentExecutionStep(agent=agent)
    flow = Flow.from_steps([step])
    conv = flow.start_conversation()
    conv.append_user_message("What does LT stand for?")
    conv.execute()
    conv.append_user_message("What was my previous question again?")
    conv.execute()
    last_message = conv.get_last_message().content
    assert "lt" in last_message.lower()


# oci agent performance seems to fluctuate, we increase max_attempts to ensure CI reliability
@retry_test(max_attempts=9)
def test_oci_knowledge_agent_as_a_subagent(agent, remotely_hosted_llm):
    """
    Failure rate:          1 out of 20
    Observed on:           2025-06-02
    Average success time:  5.95 seconds per successful attempt
    Average failure time:  4.95 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 6.8 / 100'000
    """
    master_agent = Agent(
        custom_instruction="You are a helpful assistant. Always call your sub-agents to get correct information before answering to the user",
        agents=[agent],
        llm=remotely_hosted_llm,
    )
    conv = master_agent.start_conversation()
    conv.append_user_message("What does LT stand for?")
    conv.execute()
    conv.append_user_message("What was my previous question again?")
    conv.execute()
    last_message = conv.get_last_message().content
    assert "lt" in last_message.lower()


@pytest.mark.skip("failure rate can vary from 2/20 to 12/20")
@retry_test(max_attempts=16)
def test_oci_knowledge_agent_with_previous_message(agent):
    """
    Failure rate:          12 out of 20
    Observed on:           2025-06-02
    Average success time:  14.50 seconds per successful attempt
    Average failure time:  14.82 seconds per failed attempt
    Max attempt:           18
    Justification:         (0.59 ** 18) ~= 7.7 / 100'000

    Failure rate:          2 out of 20
    Observed on:           2025-06-02
    Average success time:  13.22 seconds per successful attempt
    Average failure time:  17.74 seconds per failed attempt
    Max attempt:           5
    Justification:         (0.14 ** 5) ~= 4.7 / 100'000
    """
    conv = agent.start_conversation()
    conv.append_user_message("What is MySQL?")
    conv.append_agent_message("MySQL is some database technology")
    conv.append_user_message("What does LT stand for?")
    conv.execute()
    last_message = conv.get_last_message().content
    assert "lt" in last_message.lower()

    conv.append_user_message("Can you summarize the answers of the two previous questions?")
    conv.execute()
    last_message = conv.get_last_message().content
    assert "mysql" in last_message.lower()
    assert "lt" in last_message.lower()


def test_oci_agent_serde(agent):
    ser_agent = serialize_to_dict(agent, None)
    deser_agent = deserialize_from_dict(OciAgent, ser_agent, None)
    assert agent.initial_message == deser_agent.initial_message
    assert agent.agent_endpoint_id == deser_agent.agent_endpoint_id
    assert agent.client_config.to_dict() == deser_agent.client_config.to_dict()
    assert agent.name == deser_agent.name
    assert agent.description == deser_agent.description


@pytest.fixture
def agent_with_tools(oci_agent_client_config) -> OciAgent:
    weather_agent_endpoint_id = os.environ.get("WEATHER_AGENT_ENDPOINT_ID")
    if not weather_agent_endpoint_id:
        raise Exception("WEATHER_AGENT_ENDPOINT_ID is not set in the environment")
    return OciAgent(
        agent_endpoint_id=weather_agent_endpoint_id,
        client_config=oci_agent_client_config,
        name="oci_agent",
        description="agent that can help with requests regarding the weather.",
    )


@pytest.mark.skip("OCI Agent is making a lot of errors when parsing tool requests")
@retry_test(max_attempts=6)
def test_oci_agent_with_client_tools_can_generate_tool_requests_and_process_tool_results(
    agent_with_tools,
):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-06-11
    Average success time:  3.47 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    conv = agent_with_tools.start_conversation()
    conv.append_user_message("What is the weather in Zurich and in Paris?")
    agent_with_tools.execute(conv)
    last_message = conv.get_last_message()
    tool_requests = last_message.tool_requests
    assert tool_requests is not None and len(tool_requests) == 1
    assert tool_requests[0].name == "get_weather" and tool_requests[0].args == {"city": "Zurich"}
    conv.append_tool_result(
        ToolResult(tool_request_id=tool_requests[0].tool_request_id, content="windy")
    )
    agent_with_tools.execute(conv)
    last_message = conv.get_last_message()
    tool_requests = last_message.tool_requests
    assert tool_requests is not None and len(tool_requests) == 1
    assert tool_requests[0].name == "get_weather" and tool_requests[0].args == {"city": "Paris"}
    conv.append_tool_result(
        ToolResult(tool_request_id=tool_requests[0].tool_request_id, content="sunny")
    )
    agent_with_tools.execute(conv)
    last_message = conv.get_last_message()
    assert "windy" in last_message.content
    assert "sunny" in last_message.content
