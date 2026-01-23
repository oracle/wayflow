# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
# mypy: ignore-errors
# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import pytest
from pyagentspec.datastores.datastore import InMemoryCollectionDatastore
from pyagentspec.llms import VllmConfig
from pyagentspec.transforms import (
    ConversationSummarizationTransform as AgentSpecConversationSummarizationTransform,
)
from pyagentspec.transforms import (
    MessageSummarizationTransform as AgentSpecMessageSummarizationTransform,
)

from wayflowcore.agentspec.agentspecexporter import AgentSpecExporter
from wayflowcore.agentspec.runtimeloader import AgentSpecLoader
from wayflowcore.datastore import InMemoryDatastore
from wayflowcore.datastore.inmemory import _INMEMORY_USER_WARNING
from wayflowcore.transforms import (
    ConversationSummarizationTransform as WayflowConversationSummarizationTransform,
)
from wayflowcore.transforms import (
    MessageSummarizationTransform as WayflowMessageSummarizationTransform,
)

from ..conftest import MOCK_LLM_CONFIG, mock_llm

filter_inmemds_warnings = pytest.mark.filterwarnings(f"ignore:{_INMEMORY_USER_WARNING}:UserWarning")


def _testing_message_summarization_transforms():
    """Create both wayflow and agent-spec transforms with non-default values."""
    # Non-default values for comprehensive testing
    custom_max_message_size = 15000
    custom_summarization_instructions = "Custom summarization instructions for testing"
    custom_summarized_message_template = "Custom summary: {{summary}}"
    custom_cache_collection_name = "custom_summarized_messages_cache"
    custom_max_cache_size = 5000
    custom_max_cache_lifetime = 2 * 3600

    # Create datastore for wayflow transform
    datastore = InMemoryDatastore(
        {custom_cache_collection_name: WayflowMessageSummarizationTransform.get_entity_definition()}
    )

    # Create wayflow transform with custom values
    wayflow_transform = WayflowMessageSummarizationTransform(
        llm=mock_llm(),
        datastore=datastore,
        max_message_size=custom_max_message_size,
        summarization_instructions=custom_summarization_instructions,
        summarized_message_template=custom_summarized_message_template,
        cache_collection_name=custom_cache_collection_name,
        max_cache_size=custom_max_cache_size,
        max_cache_lifetime=custom_max_cache_lifetime,
    )

    # Create agent-spec transform with matching custom values
    llm_config = VllmConfig(
        name="vllm", model_id=MOCK_LLM_CONFIG["model_id"], url=MOCK_LLM_CONFIG["host_port"]
    )
    agent_spec_datastore = InMemoryCollectionDatastore(
        name="custom-inmemory-datastore",
        datastore_schema={
            custom_cache_collection_name: AgentSpecMessageSummarizationTransform.get_entity_definition()
        },
    )
    agent_spec_transform = AgentSpecMessageSummarizationTransform(
        name="custom-message-summarizer",
        llm=llm_config,
        datastore=agent_spec_datastore,
        max_message_size=custom_max_message_size,
        summarization_instructions=custom_summarization_instructions,
        summarized_message_template=custom_summarized_message_template,
        cache_collection_name=custom_cache_collection_name,
        max_cache_size=custom_max_cache_size,
        max_cache_lifetime=custom_max_cache_lifetime,
    )

    return wayflow_transform, agent_spec_transform


def _testing_conversation_summarization_transforms():
    """Create both wayflow and agent-spec conversation transforms with non-default values."""
    # Non-default values for comprehensive testing
    custom_max_num_messages = 60
    custom_min_num_messages = 15
    custom_summarization_instructions = "Custom conversation summarization instructions for testing"
    custom_summarized_conversation_template = "Custom conversation summary: {{summary}}"
    custom_cache_collection_name = "custom_summarized_conversations_cache"
    custom_max_cache_size = 6000
    custom_max_cache_lifetime = 3 * 3600

    # Create datastore for wayflow transform
    datastore = InMemoryDatastore(
        {
            custom_cache_collection_name: WayflowConversationSummarizationTransform.get_entity_definition()
        }
    )

    # Create wayflow transform with custom values
    wayflow_transform = WayflowConversationSummarizationTransform(
        llm=mock_llm(),
        datastore=datastore,
        max_num_messages=custom_max_num_messages,
        min_num_messages=custom_min_num_messages,
        summarization_instructions=custom_summarization_instructions,
        summarized_conversation_template=custom_summarized_conversation_template,
        cache_collection_name=custom_cache_collection_name,
        max_cache_size=custom_max_cache_size,
        max_cache_lifetime=custom_max_cache_lifetime,
    )

    # Create agent-spec transform with matching custom values
    llm_config = VllmConfig(
        name="vllm", model_id=MOCK_LLM_CONFIG["model_id"], url=MOCK_LLM_CONFIG["host_port"]
    )
    agent_spec_datastore = InMemoryCollectionDatastore(
        name="custom-inmemory-datastore-conversations",
        datastore_schema={
            custom_cache_collection_name: AgentSpecConversationSummarizationTransform.get_entity_definition()
        },
    )
    agent_spec_transform = AgentSpecConversationSummarizationTransform(
        name="custom-conversation-summarizer",
        llm=llm_config,
        datastore=agent_spec_datastore,
        max_num_messages=custom_max_num_messages,
        min_num_messages=custom_min_num_messages,
        summarization_instructions=custom_summarization_instructions,
        summarized_conversation_template=custom_summarized_conversation_template,
        cache_collection_name=custom_cache_collection_name,
        max_cache_size=custom_max_cache_size,
        max_cache_lifetime=custom_max_cache_lifetime,
    )

    return wayflow_transform, agent_spec_transform


@filter_inmemds_warnings
def test_wayflow_summarization_message_transform_can_be_converted_to_agentspec():
    # Create both transforms with matching custom values
    wayflow_transform, expected_agent_spec_transform = _testing_message_summarization_transforms()

    # Export to agent spec.
    converted_transform = AgentSpecExporter().to_component(wayflow_transform)

    assert_message_summarization_transforms_are_equal(
        converted_transform, expected_agent_spec_transform
    )


@filter_inmemds_warnings
def test_agentspec_summarization_message_transform_can_be_converted_to_wayflow():
    # Create both transforms with matching custom values
    expected_wayflow_transform, agent_spec_transform = _testing_message_summarization_transforms()

    converted_transform = AgentSpecLoader().load_component(agent_spec_transform)
    assert_message_summarization_transforms_are_equal(
        converted_transform, expected_wayflow_transform
    )


@filter_inmemds_warnings
def test_wayflow_summarization_conversation_transform_can_be_converted_to_agentspec():
    # Create both transforms with matching custom values
    wayflow_transform, expected_agent_spec_transform = (
        _testing_conversation_summarization_transforms()
    )

    # Export to agent spec.
    converted_transform = AgentSpecExporter().to_component(wayflow_transform)

    assert_conversation_summarization_transforms_are_equal(
        converted_transform, expected_agent_spec_transform
    )


@filter_inmemds_warnings
def test_agentspec_summarization_conversation_transform_can_be_converted_to_wayflow():
    # Create both transforms with matching custom values
    expected_wayflow_transform, agent_spec_transform = (
        _testing_conversation_summarization_transforms()
    )

    converted_transform = AgentSpecLoader().load_component(agent_spec_transform)
    assert_conversation_summarization_transforms_are_equal(
        converted_transform, expected_wayflow_transform
    )


def assert_message_summarization_transforms_are_equal(converted_transform, expected_transform):
    # Check that the parameters match the ground truth from agent-spec
    assert converted_transform.max_message_size == expected_transform.max_message_size
    assert (
        converted_transform.summarization_instructions
        == expected_transform.summarization_instructions
    )
    assert (
        converted_transform.summarized_message_template
        == expected_transform.summarized_message_template
    )
    assert converted_transform.max_cache_size == expected_transform.max_cache_size
    assert converted_transform.max_cache_lifetime == expected_transform.max_cache_lifetime
    assert converted_transform.cache_collection_name == expected_transform.cache_collection_name
    # For llm, check equivalent fields
    if isinstance(expected_transform, AgentSpecMessageSummarizationTransform):
        assert converted_transform.llm.url == expected_transform.llm.url
        assert converted_transform.llm.model_id == expected_transform.llm.model_id
    if isinstance(expected_transform, WayflowMessageSummarizationTransform):
        assert (
            converted_transform.llm.config["host_port"]
            == expected_transform.llm.config["host_port"]
        )
        assert converted_transform.llm.model_id == expected_transform.llm.model_id


def assert_conversation_summarization_transforms_are_equal(converted_transform, expected_transform):
    # Check that the parameters match the ground truth from agent-spec
    assert converted_transform.max_num_messages == expected_transform.max_num_messages
    assert converted_transform.min_num_messages == expected_transform.min_num_messages
    assert (
        converted_transform.summarization_instructions
        == expected_transform.summarization_instructions
    )
    assert (
        converted_transform.summarized_conversation_template
        == expected_transform.summarized_conversation_template
    )
    assert converted_transform.max_cache_size == expected_transform.max_cache_size
    assert converted_transform.max_cache_lifetime == expected_transform.max_cache_lifetime
    assert converted_transform.cache_collection_name == expected_transform.cache_collection_name
    # For llm, check equivalent fields
    if isinstance(expected_transform, AgentSpecConversationSummarizationTransform):
        assert converted_transform.llm.url == expected_transform.llm.url
        assert converted_transform.llm.model_id == expected_transform.llm.model_id
    if isinstance(expected_transform, WayflowConversationSummarizationTransform):
        assert (
            converted_transform.llm.config["host_port"]
            == expected_transform.llm.config["host_port"]
        )
        assert converted_transform.llm.model_id == expected_transform.llm.model_id
