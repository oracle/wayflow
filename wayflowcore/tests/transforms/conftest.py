# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import List, Optional
from unittest.mock import AsyncMock, patch

import pytest
from pyagentspec.agent import Agent as AgentSpecAgent
from pyagentspec.datastores.datastore import (
    InMemoryCollectionDatastore as AgentSpecInMemoryCollection,
)
from pyagentspec.llms import VllmConfig as AgentSpecVllmConfig
from pyagentspec.transforms import (
    ConversationSummarizationTransform as AgentSpecConversationSummarizationTransform,
)
from pyagentspec.transforms import (
    MessageSummarizationTransform as AgentSpecMessageSummarizationTransform,
)

from wayflowcore.agentspec.runtimeloader import AgentSpecLoader
from wayflowcore.conversation import Conversation
from wayflowcore.datastore.entity import Entity
from wayflowcore.datastore.inmemory import InMemoryDatastore
from wayflowcore.messagelist import Message
from wayflowcore.models.llmmodel import LlmCompletion, LlmModel
from wayflowcore.property import FloatProperty, IntegerProperty, StringProperty
from wayflowcore.transforms import ConversationSummarizationTransform, MessageSummarizationTransform

from ..conftest import GEMMA_CONFIG, MOCK_LLM_CONFIG, patch_streaming_llm
from ..datastores.conftest import (
    cleanup_oracle_datastore,
    get_oracle_connection_config,
    get_oracle_datastore_with_schema,
)

_CachedSummarizationTransform = MessageSummarizationTransform | ConversationSummarizationTransform


@pytest.fixture(scope="session")
def oracle_database_connection():
    connection_config = get_oracle_connection_config()
    conn = connection_config.get_connection()
    try:
        yield conn
    finally:
        conn.close()


def create_entities_inside_oracle_database(oracle_database_connection, schema):
    ddl = _get_dll_for_creation_of_one_entity_schema(schema)
    for stmt in ddl:
        oracle_database_connection.cursor().execute(stmt)


def delete_entities_inside_oracle_database(oracle_database_connection, schema):
    ddl = _get_dll_for_deletion_of_one_entity_schema(schema)
    for stmt in ddl:
        oracle_database_connection.cursor().execute(stmt)


def find_datastore_by_schema(pool, schema):
    for s, datastore in pool:
        if s == schema:
            return datastore
    return None


MESSAGE_SUMMARIZATION_CACHE_COLLECTION_NAME = "messages_cache"
CONVERSATION_SUMMARIZATION_CACHE_COLLECTION_NAME = "conversations_cache"


@pytest.fixture(scope="session")
def oracle_database_datastores_pool():
    pool = []
    try:
        testing_schemas = get_testing_schemas()
        for schema in testing_schemas:
            datastore = get_oracle_datastore_with_schema(
                _get_dll_for_creation_of_one_entity_schema(schema), schema
            )
            pool.append((schema, datastore))
        yield pool
    finally:
        for schema in testing_schemas:
            cleanup_oracle_datastore(_get_dll_for_deletion_of_one_entity_schema(schema))


def get_testing_schemas():
    return [
        {
            MESSAGE_SUMMARIZATION_CACHE_COLLECTION_NAME: MessageSummarizationTransform.get_entity_definition()
        },
        {
            MessageSummarizationTransform.DEFAULT_CACHE_COLLECTION_NAME: MessageSummarizationTransform.get_entity_definition()
        },
        {
            CONVERSATION_SUMMARIZATION_CACHE_COLLECTION_NAME: ConversationSummarizationTransform.get_entity_definition()
        },
        {
            ConversationSummarizationTransform.DEFAULT_CACHE_COLLECTION_NAME: ConversationSummarizationTransform.get_entity_definition()
        },
    ] + get_incorrect_schemas()


def get_incorrect_schemas():
    entity = MessageSummarizationTransform.get_entity_definition()
    prop_keys = list(entity.properties.keys())

    wrong_entities = []
    for i in range(len(prop_keys)):
        keys_to_include = prop_keys[:i] + prop_keys[i + 1 :]
        new_properties = {k: entity.properties[k] for k in keys_to_include}
        wrong_entity = Entity(properties=new_properties)
        wrong_entities.append(wrong_entity)
    wrong_entities.append(Entity(properties={"conversation_id": StringProperty()}))
    correct_collection_name = MESSAGE_SUMMARIZATION_CACHE_COLLECTION_NAME

    wrong_entity_but_correct_collection_name = [
        {correct_collection_name: entity} for entity in wrong_entities
    ]
    correct_entity_but_wrong_collection_name = [
        {"wrong_table_name": MessageSummarizationTransform.get_entity_definition()}
    ]
    return wrong_entity_but_correct_collection_name + correct_entity_but_wrong_collection_name


@pytest.fixture(
    scope="function",
    params=["testing_inmemory_data_store", "testing_oracle_data_store"],
)
def testing_data_store(request: pytest.FixtureRequest):
    # https://stackoverflow.com/questions/42014484/pytest-using-fixtures-as-arguments-in-parametrize
    return request.getfixturevalue(request.param)


@pytest.fixture
def testing_inmemory_data_store(
    collection_name: Optional[str], transform_type: _CachedSummarizationTransform
):
    # if collection name is none, the default one is chosen.
    if not collection_name:
        collection_name = transform_type.DEFAULT_CACHE_COLLECTION_NAME
    return InMemoryDatastore({collection_name: transform_type.get_entity_definition()})


@pytest.fixture
def testing_oracle_data_store(
    oracle_database_datastores_pool,
    oracle_database_connection,
    collection_name: Optional[str],
    transform_type: _CachedSummarizationTransform,
):
    # if collection name is none, the user needs to choose the default
    if not collection_name:
        collection_name = transform_type.DEFAULT_CACHE_COLLECTION_NAME
    schema = {collection_name: transform_type.get_entity_definition()}
    try:
        pool = oracle_database_datastores_pool
        correct_datastore = find_datastore_by_schema(pool, schema)
        if correct_datastore:
            create_entities_inside_oracle_database(oracle_database_connection, schema)
            yield correct_datastore
        else:
            raise ValueError(f"Schema {schema} not found in pool")
    finally:
        delete_entities_inside_oracle_database(oracle_database_connection, schema)


# Executes the conversation and Checks if the summarization LLM ran or not.
def execute_conversation_check_summarizer_ran(
    conversation: Conversation, summarization_llm: LlmModel, agent_llm: LlmModel
) -> bool:
    mock_generate_summary = AsyncMock(
        side_effect=lambda prompt: LlmCompletion(Message("Summary: Dolphins are amazing."), None)
    )
    with patch.object(summarization_llm, "generate_async", mock_generate_summary):
        with patch_streaming_llm(agent_llm, "This is a mock generation"):
            # We expect the transform to do summarization
            conversation.execute()
            return mock_generate_summary.call_count > 0


@pytest.fixture
def datastore_with_incorrect_schemas(
    oracle_database_datastores_pool, oracle_database_connection, request
):
    schema = request.param
    try:
        pool = oracle_database_datastores_pool
        ds = find_datastore_by_schema(pool, schema)
        create_entities_inside_oracle_database(oracle_database_connection, schema)
        yield ds
    finally:
        delete_entities_inside_oracle_database(oracle_database_connection, schema)


@pytest.fixture
def inmemory_datastore_with_incorrect_schemas(request: pytest.FixtureRequest):
    schema = request.param
    return InMemoryDatastore(schema)


# We do this check to ensure that some information from the long message is kept. Otherwise
# returning "" would pass the tests.
def at_least_one_keyword_present(keywords: List[str], message: str) -> bool:
    return any([keyword.lower() in message.lower() for keyword in keywords])


def _get_dll_for_creation_of_one_entity_schema(schema: dict[str, "Entity"]) -> list[str]:
    entity_name = next(iter(schema.keys()), None)
    if not entity_name:
        return [""]

    entity = schema[entity_name]
    prop_lines = []
    for prop_name, prop_type in entity.properties.items():
        if isinstance(prop_type, StringProperty):
            sql_type = "VARCHAR(200)"
        elif isinstance(prop_type, IntegerProperty) or isinstance(prop_type, FloatProperty):
            sql_type = "NUMBER"
        else:
            sql_type = "CLOB"
        prop_lines.append(f"    {prop_name} {sql_type}")
    props_str = ",\n".join(prop_lines)
    ddl = f"CREATE TABLE {entity_name} (\n{props_str}\n)"

    drop = f"DROP TABLE IF EXISTS {entity_name}"
    return [drop, ddl]


def _get_dll_for_deletion_of_one_entity_schema(schema: dict[str, "Entity"]) -> list[str]:
    entity_name = next(iter(schema.keys()), None)
    if not entity_name:
        return [""]
    return [f"DROP TABLE IF EXISTS {entity_name}"]


@pytest.fixture
def converted_wayflow_agent_with_message_summarization_transform_from_agentspec():
    collection_name = MESSAGE_SUMMARIZATION_CACHE_COLLECTION_NAME
    agent_spec_datastore = AgentSpecInMemoryCollection(
        name="test-inmemory-datastore",
        datastore_schema={
            collection_name: AgentSpecMessageSummarizationTransform.get_entity_definition()
        },
    )
    summarization_llm_config = AgentSpecVllmConfig(
        name="vllm", model_id=GEMMA_CONFIG["model_id"], url=GEMMA_CONFIG["host_port"]
    )
    agent_spec_transform = AgentSpecMessageSummarizationTransform(
        name="message-summarizer",
        llm=summarization_llm_config,
        datastore=agent_spec_datastore,
        max_message_size=500,
        cache_collection_name=collection_name,
    )
    agent_llm_config = AgentSpecVllmConfig(
        name="vllm", model_id=MOCK_LLM_CONFIG["model_id"], url=MOCK_LLM_CONFIG["host_port"]
    )
    agent_spec_agent = AgentSpecAgent(
        name="test-agent",
        system_prompt="",
        llm_config=agent_llm_config,
        transforms=[agent_spec_transform],
    )
    loader = AgentSpecLoader()
    wayflow_agent = loader.load_component(agent_spec_agent)
    return wayflow_agent


@pytest.fixture
def converted_wayflow_agent_with_conversation_summarization_transform_from_agentspec():
    collection_name = CONVERSATION_SUMMARIZATION_CACHE_COLLECTION_NAME
    agent_spec_datastore = AgentSpecInMemoryCollection(
        name="test-inmemory-datastore",
        datastore_schema={
            collection_name: AgentSpecConversationSummarizationTransform.get_entity_definition()
        },
    )
    summarization_llm_config = AgentSpecVllmConfig(
        name="vllm", model_id=GEMMA_CONFIG["model_id"], url=GEMMA_CONFIG["host_port"]
    )
    agent_spec_transform = AgentSpecConversationSummarizationTransform(
        name="conversation-summarizer",
        llm=summarization_llm_config,
        datastore=agent_spec_datastore,
        max_num_messages=10,
        min_num_messages=5,
        cache_collection_name=collection_name,
    )
    agent_llm_config = AgentSpecVllmConfig(
        name="vllm", model_id=MOCK_LLM_CONFIG["model_id"], url=MOCK_LLM_CONFIG["host_port"]
    )
    agent_spec_agent = AgentSpecAgent(
        name="test-agent",
        system_prompt="",
        llm_config=agent_llm_config,
        transforms=[agent_spec_transform],
    )
    wayflow_agent = AgentSpecLoader().load_component(agent_spec_agent)
    return wayflow_agent
