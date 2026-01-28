# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
# mypy: ignore-errors

import pytest
from pyagentspec.agent import Agent as AgentSpecAgent
from pyagentspec.llms import VllmConfig

from wayflowcore.agent import Agent as WayflowAgent
from wayflowcore.agentspec.agentspecexporter import AgentSpecExporter
from wayflowcore.agentspec.runtimeloader import AgentSpecLoader
from wayflowcore.datastore.inmemory import _INMEMORY_USER_WARNING
from wayflowcore.models import VllmModel

from ..conftest import MOCK_LLM_CONFIG
from .test_transforms import (
    _testing_conversation_summarization_transforms,
    _testing_message_summarization_transforms,
    assert_conversation_summarization_transforms_are_equal,
    assert_message_summarization_transforms_are_equal,
)

filter_in_memory_datastore_warnings = pytest.mark.filterwarnings(
    f"ignore:{_INMEMORY_USER_WARNING}:UserWarning"
)


@pytest.fixture
def _testing_agents_with_summarization_transforms():
    """Create both wayflow and agent-spec agents with summarization transforms."""
    wayflow_message_transform, agent_spec_message_transform = (
        _testing_message_summarization_transforms()
    )
    wayflow_conversation_transform, agent_spec_conversation_transform = (
        _testing_conversation_summarization_transforms()
    )

    # Create wayflow agent with both transforms
    wayflow_agent = WayflowAgent(
        llm=VllmModel(model_id=MOCK_LLM_CONFIG["model_id"], host_port=MOCK_LLM_CONFIG["host_port"]),
        custom_instruction="Test agent with transforms",
        transforms=[wayflow_message_transform, wayflow_conversation_transform],
    )

    # Create agent-spec agent with matching transforms
    llm_config = VllmConfig(
        name="vllm", model_id=MOCK_LLM_CONFIG["model_id"], url=MOCK_LLM_CONFIG["host_port"]
    )
    agent_spec_agent = AgentSpecAgent(
        name="test-agent-with-transforms",
        system_prompt="Test agent with transforms",
        llm_config=llm_config,
        transforms=[agent_spec_message_transform, agent_spec_conversation_transform],
    )

    return wayflow_agent, agent_spec_agent


@filter_in_memory_datastore_warnings
def test_wayflow_agent_with_summarization_transforms_can_be_converted_to_agentspec(
    _testing_agents_with_summarization_transforms,
):
    # Create both agents with matching transforms
    wayflow_agent, expected_agent_spec_agent = _testing_agents_with_summarization_transforms

    # Export to agent spec.
    converted_agent = AgentSpecExporter().to_component(wayflow_agent)

    assert_agents_with_summarization_transforms_are_equal(
        converted_agent, expected_agent_spec_agent
    )


@filter_in_memory_datastore_warnings
def test_agentspec_agent_with_summarization_transforms_can_be_converted_to_wayflow(
    _testing_agents_with_summarization_transforms,
):
    # Create both agents with matching transforms
    expected_wayflow_agent, agent_spec_agent = _testing_agents_with_summarization_transforms

    converted_agent = AgentSpecLoader().load_component(agent_spec_agent)
    assert_agents_with_summarization_transforms_are_equal(converted_agent, expected_wayflow_agent)


def assert_agents_with_summarization_transforms_are_equal(converted_agent, expected_agent):
    # Check that the agents have the same number of transforms
    assert len(converted_agent.transforms) == len(expected_agent.transforms)
    assert_message_summarization_transforms_are_equal(
        converted_agent.transforms[0], expected_agent.transforms[0]
    )
    assert_conversation_summarization_transforms_are_equal(
        converted_agent.transforms[1], expected_agent.transforms[1]
    )
