# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from textwrap import dedent

import pytest

from wayflowcore.agent import Agent
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.datastore.inmemory import _INMEMORY_USER_WARNING, InMemoryDatastore
from wayflowcore.flow import Flow
from wayflowcore.search import SearchConfig, VectorConfig, VectorRetrieverConfig
from wayflowcore.steps import CompleteStep, InputMessageStep, PromptExecutionStep, StartStep
from wayflowcore.steps.searchstep import SearchStep
from wayflowcore.tools import ToolBox

from ..testhelpers.testhelpers import retry_test
from .conftest import find_search_tool


@retry_test(max_attempts=3)
def test_agent_rag_with_search_tools(inmemory_motorcycle_datastore, remotely_hosted_llm):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-12
    Average success time:  2.03 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    """Test that an Agent can use search tools for RAG."""
    search_toolbox = inmemory_motorcycle_datastore.get_search_toolbox()

    # Verify we got a ToolBox
    assert isinstance(search_toolbox, ToolBox)

    agent = Agent(
        tools=[search_toolbox],
        llm=remotely_hosted_llm,
        custom_instruction="You are a helpful motorcycle garage assistant. Use the search tools to find information about motorcycles in our garage before answering questions.",
        initial_message="Hello! I'm your motorcycle garage assistant. I can help you find information about the motorcycles in our garage.",
    )

    conversation = agent.start_conversation()

    result = conversation.execute()
    assert len(conversation.get_messages()) > 0

    conversation.append_user_message("Who owns the Yamaha motorcycle in our garage?")
    result = conversation.execute()

    agent_messages = [
        msg for msg in conversation.get_messages() if msg.message_type.name == "AGENT"
    ]
    assert len(agent_messages) > 0

    last_response = agent_messages[-1].content

    # Verify the response mentions Sarah Johnson (owner of Yamaha YZF-R6)
    assert (
        "Sarah Johnson" in last_response or "Yamaha" in last_response
    ), f"Agent should mention Sarah Johnson or Yamaha. Got: {last_response}"

    # Verify agent has toolboxes (not tools)
    assert len(agent._toolboxes) > 0


@retry_test(max_attempts=3)
def test_flow_rag_with_search_step(
    inmemory_motorcycle_datastore,
    remotely_hosted_llm,
):
    """
    Failure rate:          1 out of 50
    Observed on:           2025-09-12
    Average success time:  1.76 seconds per successful attempt
    Average failure time:  0.71 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000
    """
    """Test that a Flow can use SearchStep for RAG."""
    start_step = StartStep()

    user_input_step = InputMessageStep(
        message_template="Hello! I'm your motorcycle garage assistant. What would you like to know about the motorcycles in our garage?"
    )

    search_step = SearchStep(
        datastore=inmemory_motorcycle_datastore, collection_name="motorcycles", k=3
    )

    llm_response_step = PromptExecutionStep(
        prompt_template=dedent(
            """
            You are a helpful motorcycle garage assistant. Based on the following search results:

            {{ retrieved_documents }}

            Answer the user's question: {{ user_query }}

            Be specific and mention details from the search results.
        """
        ),
        llm=remotely_hosted_llm,
    )

    destination_step = CompleteStep()

    steps = {
        "start": start_step,
        "input": user_input_step,
        "search": search_step,
        "respond": llm_response_step,
        "last_step": destination_step,
    }

    control_edges = [
        ControlFlowEdge(start_step, user_input_step),
        ControlFlowEdge(user_input_step, search_step),
        ControlFlowEdge(search_step, llm_response_step),
        ControlFlowEdge(llm_response_step, destination_step),
    ]

    data_edges = [
        DataFlowEdge(
            user_input_step, InputMessageStep.USER_PROVIDED_INPUT, search_step, SearchStep.QUERY
        ),
        DataFlowEdge(
            user_input_step, InputMessageStep.USER_PROVIDED_INPUT, llm_response_step, "user_query"
        ),
        DataFlowEdge(search_step, SearchStep.DOCUMENTS, llm_response_step, "retrieved_documents"),
    ]

    flow = Flow(
        begin_step=start_step,
        steps=steps,
        control_flow_edges=control_edges,
        data_flow_edges=data_edges,
    )

    conversation = flow.start_conversation()
    conversation.execute()
    conversation.append_user_message("Tell me about the dirt bike in the garage")
    result = conversation.execute()

    # Verify flow executed
    assert result.output_values is not None
    assert PromptExecutionStep.OUTPUT in result.output_values

    response = result.output_values[PromptExecutionStep.OUTPUT]
    assert isinstance(response, str)
    assert len(response) > 0

    # Response should mention Honda CRF450L or Emily Davis (dirt bike details)
    assert any(
        term in response for term in ["Honda", "CRF450L", "Emily Davis", "dirt", "off-road"]
    ), f"Response should mention dirt bike details. Got: {response}"


def test_search_on_empty_datastore_raises(embedding_model, entity_motorcycle_schema):
    """Test handling of search on empty datastore."""
    # Create empty datastore
    search_config = SearchConfig(retriever=VectorRetrieverConfig(model=embedding_model))

    with pytest.warns(UserWarning, match=_INMEMORY_USER_WARNING):
        datastore = InMemoryDatastore(
            schema={"motorcycles": entity_motorcycle_schema}, search_configs=[search_config]
        )

    # Verify datastore is actually empty
    entities = datastore.list("motorcycles")
    assert len(entities) == 0, "Datastore should be empty"

    # We expect an error to be raised for an empty datastore, because we infer the dimensionality of the Vector Index by checking the dimension of the entries in the Datatable.
    # This behaviour will be different in OracleDatabaseDatastore, because the VECTOR column will already have a pre-defined dimension, and we assume the Vector Index is already built
    with pytest.raises(ValueError, match="No vector index found for config"):
        direct_results = datastore.search(
            collection_name="motorcycles", query="any motorcycle", k=3
        )


def test_search_with_filters(inmemory_motorcycle_datastore):
    """Test search with where filters for RAG use cases."""
    # Search with owner filter - John Smith owns 2 motorcycles
    results = inmemory_motorcycle_datastore.search(
        collection_name="motorcycles", query="motorcycle", k=10, where={"owner_name": "John Smith"}
    )

    # Should only return John Smith's motorcycles
    assert all(r["owner_name"] == "John Smith" for r in results)
    assert len(results) == 2  # John owns Harley-Davidson Street Glide and Road King


@pytest.mark.parametrize(
    "k_arg, k_actual",
    [(1, 1), (3, 3), (5, 5), (100, 5)],
)
def test_search_with_different_k_values(inmemory_motorcycle_datastore, k_arg, k_actual):
    """Test search with different k values for RAG flexibility."""
    results_k = inmemory_motorcycle_datastore.search(
        collection_name="motorcycles", query="adventure touring", k=k_arg
    )
    assert len(results_k) == k_actual


def test_search_tools_with_custom_k(inmemory_motorcycle_datastore):
    """Test that search tools respect custom k parameter."""
    toolbox = inmemory_motorcycle_datastore.get_search_toolbox(k=1)
    tools = toolbox.get_tools()

    search_tool = find_search_tool(tools)
    assert search_tool is not None, "Should find search tool"
    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)

    # Should use k=1 as configured in toolbox
    results = search_tool.run(query="Harley")
    assert len(results) <= 1

    # Create another toolbox with different k
    toolbox_k5 = inmemory_motorcycle_datastore.get_search_toolbox(k=5)
    tools_k5 = toolbox_k5.get_tools()
    search_tool_k5 = find_search_tool(tools_k5)
    assert search_tool_k5 is not None
    search_tool_k5 = search_tool_k5.toolbox._get_concrete_tool(search_tool_k5.name)
    results_k5 = search_tool_k5.run(query="Harley")
    assert len(results_k5) <= 5


@retry_test(max_attempts=3)
def test_search_semantic_similarity(inmemory_motorcycle_datastore):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-12
    Average success time:  1.24 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    """Test that search uses semantic similarity for RAG."""
    # Search for "dirt bike" should find Honda CRF450L even without exact match
    results = inmemory_motorcycle_datastore.search(
        collection_name="motorcycles", query="dirt bike off-road trail riding", k=1
    )

    assert len(results) == 1
    assert results[0]["model_name"] == "Honda CRF450L"

    # Search for "touring" should find touring motorcycles (Harleys and BMW)
    touring_results = inmemory_motorcycle_datastore.search(
        collection_name="motorcycles", query="long distance touring comfort highway", k=3
    )

    # Should include Harley and/or BMW touring bikes
    touring_models = [r["model_name"] for r in touring_results]
    assert any("Harley" in model or "BMW" in model for model in touring_models)


@retry_test(max_attempts=3)
def test_multiple_search_configurations(
    embedding_model, entity_motorcycle_schema, motorcycle_json_data
):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-12
    Average success time:  2.22 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    """Test datastore with multiple search configurations."""
    # Create multiple search configs
    search_config_1 = SearchConfig(
        name="default_search", retriever=VectorRetrieverConfig(model=embedding_model)
    )

    search_config_2 = SearchConfig(
        name="specific_search",
        retriever=VectorRetrieverConfig(model=embedding_model, collection_name="motorcycles"),
    )

    with pytest.warns(UserWarning, match=_INMEMORY_USER_WARNING):
        datastore = InMemoryDatastore(
            schema={"motorcycles": entity_motorcycle_schema},
            search_configs=[search_config_1, search_config_2],
        )

    datastore.create("motorcycles", motorcycle_json_data)

    # Test search with different configs
    results_1 = datastore.search("BMW", "motorcycles", search_config="default_search", k=2)
    results_2 = datastore.search("BMW", "motorcycles", search_config="specific_search", k=2)

    assert len(results_1) > 0
    assert len(results_2) > 0

    # Both should find BMW R 1250 GS Adventure
    assert any("BMW" in r.get("model_name", "") for r in results_1)
    assert any("BMW" in r.get("model_name", "") for r in results_2)


def test_error_handling_in_search_tools(inmemory_motorcycle_datastore):
    """Test that search tools handle errors gracefully."""
    toolbox = inmemory_motorcycle_datastore.get_search_toolbox()
    tools = toolbox.get_tools()
    search_tool = find_search_tool(tools)
    assert search_tool is not None
    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)
    # Test with empty query
    parsed_result = search_tool.run(query="")
    assert isinstance(parsed_result, list)  # Should return list, not error

    # Test normal query (k is fixed in toolbox)
    parsed_result = search_tool.run(query="motorcycle")
    assert isinstance(parsed_result, list)
    assert len(parsed_result) <= 5  # Can't return more than we have


@pytest.mark.parametrize("collection_name", ["bikes", "vehicles", "inventory"])
def test_search_tools_different_collections(
    embedding_model, entity_motorcycle_schema, motorcycle_json_data, collection_name
):
    """Test search tools with different collection names."""
    search_config = SearchConfig(retriever=VectorRetrieverConfig(model=embedding_model))

    with pytest.warns(UserWarning, match=_INMEMORY_USER_WARNING):
        datastore = InMemoryDatastore(
            schema={collection_name: entity_motorcycle_schema}, search_configs=[search_config]
        )

    datastore.create(collection_name, motorcycle_json_data)

    # Get search tools
    toolbox = datastore.get_search_toolbox()
    tools = toolbox.get_tools()
    assert len(tools) > 0

    # Find tool for this collection
    search_tool = find_search_tool(tools, collection_name)
    assert search_tool is not None, f"Should create search tool for {collection_name}"
    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)

    # Test the tool
    results = search_tool.run(query="BMW")
    assert len(results) > 0


@retry_test(max_attempts=3)
def test_search_toolbox_dynamic_updates(inmemory_motorcycle_datastore):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-12
    Average success time:  1.26 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    """Test that search toolbox reflects dynamic datastore changes."""
    toolbox = inmemory_motorcycle_datastore.get_search_toolbox()

    # Get initial tools
    tools_before = toolbox.get_tools()
    assert len(tools_before) > 0

    # Add a new motorcycle
    new_motorcycle = {
        "id": 6,
        "owner_name": "Test Owner",
        "model_name": "Test Motorcycle",
        "description": "A test motorcycle for dynamic updates",
        "hp": 100,
    }
    inmemory_motorcycle_datastore.create("motorcycles", new_motorcycle)

    # Get tools again - should still work with updated data
    tools_after = toolbox.get_tools()
    assert len(tools_after) == len(tools_before)  # Same number of tools

    # Test that search finds the new motorcycle
    search_tool = find_search_tool(tools_after)
    assert search_tool is not None
    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)

    results = search_tool.run(query="Test Motorcycle")

    # Should find the new motorcycle
    assert any("Test Motorcycle" in r.get("model_name", "") for r in results)


@retry_test(max_attempts=3)
def test_search_toolbox_works_for_specific_collection(inmemory_motorcycle_datastore):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-12
    Average success time:  0.63 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    """Test search toolbox created for specific collections."""
    # Create toolbox for specific collection
    toolbox = inmemory_motorcycle_datastore.get_search_toolbox(collection_names=["motorcycles"])
    tools = toolbox.get_tools()

    assert len(tools) == 1  # Should have exactly one tool

    # Test the tool works
    search_tool = find_search_tool(tools)
    assert search_tool is not None
    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)

    results = search_tool.run(query="Yamaha")
    assert len(results) > 0
    # Should find Sarah Johnson's Yamaha YZF-R6
    assert any("Yamaha" in r.get("model_name", "") for r in results)


@retry_test(max_attempts=3)
@pytest.mark.parametrize(
    "vector_config",
    [
        (
            VectorConfig(
                name="Vector config 123",
                collection_name="motorcycles",
                vector_property="_embedding",
            )
        ),
        (
            VectorConfig(
                collection_name="motorcycles",
            )
        ),
    ],
)
def test_vector_config_works(
    embedding_model, entity_motorcycle_schema, motorcycle_json_data, vector_config
):
    """
    (VectorConfig(name = "Vector config 123", collection_name = "motorcycles", vector_property = "_embedding"))
    Failure rate:          0 out of 50
    Observed on:           2025-11-04
    Average success time:  1.65 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000

    (VectorConfig(collection_name = "motorcycles",))
    Failure rate:          0 out of 50
    Observed on:           2025-11-04
    Average success time:  1.68 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """

    search_config_1 = SearchConfig(
        name="default_search",
        retriever=VectorRetrieverConfig(model=embedding_model, vectors=vector_config),
    )

    if vector_config.vector_property:
        with pytest.warns(UserWarning, match=_INMEMORY_USER_WARNING):
            datastore = InMemoryDatastore(
                schema={"motorcycles": entity_motorcycle_schema},
                search_configs=[search_config_1],
                vector_configs=[vector_config],
            )
    else:
        with pytest.warns(UserWarning, match=_INMEMORY_USER_WARNING):
            with pytest.raises(ValueError, match="No Vector Property found for collection name"):
                datastore = InMemoryDatastore(
                    schema={"motorcycles": entity_motorcycle_schema},
                    search_configs=[search_config_1],
                    vector_configs=[vector_config],
                )
        return
    datastore.create("motorcycles", motorcycle_json_data)

    # Test search with different configs
    results = datastore.search("BMW", "motorcycles", search_config="default_search", k=2)

    assert len(results) > 0

    assert any("BMW" in r.get("model_name", "") for r in results)
