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
from wayflowcore.flow import Flow
from wayflowcore.steps import CompleteStep, InputMessageStep, PromptExecutionStep, StartStep
from wayflowcore.steps.searchstep import SearchStep
from wayflowcore.tools import ToolBox

from ..testhelpers.testhelpers import retry_test
from .conftest import find_search_tool


@retry_test(max_attempts=3)
def test_agent_rag_with_search_tools(populated_oracle_vehicle_datastore, remotely_hosted_llm):
    """
    Failure rate:          1 out of 50
    Observed on:           2025-09-10
    Average success time:  2.21 seconds per successful attempt
    Average failure time:  2.22 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000
    """

    """Test that an Agent can use search tools for RAG."""
    search_toolbox = populated_oracle_vehicle_datastore.get_search_toolbox(
        collection_names=["motorcycles"]
    )

    # Verify we got a ToolBox
    assert isinstance(search_toolbox, ToolBox)

    agent = Agent(
        tools=[search_toolbox],
        llm=remotely_hosted_llm,
        custom_instruction="You are a helpful motorcycle garage assistant. Use the search tools to find information about motorcycles in our garage before answering questions.",
        initial_message="Hello! I'm your motorcycle garage assistant. I can help you find information about the motorcycles in our garage.",
    )

    conversation = agent.start_conversation()

    conversation.execute()
    assert len(conversation.get_messages()) > 0

    conversation.append_user_message("Who owns the Yamaha motorcycle in our garage?")
    conversation.execute()

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
    populated_oracle_vehicle_datastore,
    remotely_hosted_llm,
):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-10
    Average success time:  2.05 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """

    """Test that a Flow can use SearchStep for RAG."""
    start_step = StartStep()

    user_input_step = InputMessageStep(
        message_template="Hello! I'm your motorcycle garage assistant. What would you like to know about the motorcycles in our garage?"
    )

    search_step = SearchStep(
        datastore=populated_oracle_vehicle_datastore, collection_name="motorcycles", k=3
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
        "destination_step": destination_step,
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
    with pytest.warns(UserWarning, match="No vector config found for collection"):
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


def test_search_on_empty_datastore_does_not_raise(oracle_empty_table_datastore):
    """Test handling of search on empty datastore."""
    # Create empty datastore

    # Verify datastore is actually empty
    entities = oracle_empty_table_datastore.list("empty_table")
    assert len(entities) == 0, "Datastore should be empty"

    # Test direct search on empty datastore
    with pytest.warns(UserWarning, match="No vector config found for collection"):
        direct_results = oracle_empty_table_datastore.search(
            collection_name="empty_table", query="any motorcycle", k=3
        )
    # If direct search succeeds, it should return empty list
    assert isinstance(direct_results, list)
    assert len(direct_results) == 0, "Empty datastore should return empty search results"

    # Test search tools if direct search works
    toolbox = oracle_empty_table_datastore.get_search_toolbox()
    tools = toolbox.get_tools()
    assert len(tools) > 0

    search_tool = find_search_tool(tools, collection_name="empty_table")
    assert search_tool is not None

    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)
    with pytest.warns(UserWarning, match="No vector config found for collection"):
        result = search_tool.run(query="any motorcycle")
    assert isinstance(result, list)
    assert len(result) == 0, "Search tool should return empty results for empty datastore"


@retry_test(max_attempts=3)
def test_oracledb_search_returns_results_in_relevance_order(populated_oracle_vehicle_datastore):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-10
    Average success time:  0.98 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    """Test that search results return relevant information."""

    with pytest.warns(UserWarning, match="No vector config found for collection"):
        results = populated_oracle_vehicle_datastore.search(
            collection_name="motorcycles",
            query="Italian superbike",
            k=3,
            search_config="search_motorcycles",
        )

    # Verify we got results
    assert len(results) > 0
    assert len(results) <= 3

    assert (
        results[0]["owner_name"] == "Carlos Rodriguez"
    ), "Italian Superbike should rank first for sport query"


@retry_test(max_attempts=3)
def test_oracledb_search_raises_warning_if_no_config(populated_oracle_vehicle_datastore):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-10
    Average success time:  0.98 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    """Test that search results return relevant information."""

    with pytest.warns(UserWarning, match="No vector config found for collection"):
        results = populated_oracle_vehicle_datastore.search(
            collection_name="motorcycles",
            query="Italian superbike",
            k=3,
            search_config="search_motorcycles",
        )


@pytest.mark.parametrize(
    "k_arg, k_actual",
    [(1, 1), (3, 3), (5, 5), (100, 5)],
)
def test_search_with_different_k_values(populated_oracle_vehicle_datastore, k_arg, k_actual):
    """Test search with different k values for RAG flexibility."""
    with pytest.warns(UserWarning, match="No vector config found for collection"):
        results_k = populated_oracle_vehicle_datastore.search(
            collection_name="motorcycles", query="adventure touring", k=k_arg
        )
    assert len(results_k) == k_actual


def test_search_with_filters(populated_oracle_vehicle_datastore):
    """Test search with where filters for RAG use cases."""
    # Search with owner filter - John Smith owns 1 motorcycle
    with pytest.warns(UserWarning, match="No vector config found for collection"):
        results = populated_oracle_vehicle_datastore.search(
            collection_name="motorcycles",
            query="motorcycle",
            k=10,
            where={"owner_name": "John Smith"},
        )
    # Should only return John Smith's motorcycles
    assert all(r["owner_name"] == "John Smith" for r in results)
    assert len(results) == 1  # John owns Harley-Davidson Road King

    with pytest.warns(UserWarning, match="No vector config found for collection"):
        results = populated_oracle_vehicle_datastore.search(
            collection_name="motorcycles",
            query="motorcycle",
            k=10,
            where={"owner_name": "Jane Doe"},
        )

    assert (
        len(results) == 0
    )  # No results should be returned, because Jane Doe does not exist in the database


def test_search_tools_with_custom_k(populated_oracle_vehicle_datastore):
    """Test that search tools respect custom k parameter."""
    toolbox = populated_oracle_vehicle_datastore.get_search_toolbox(
        k=1, collection_names=["motorcycles"]
    )
    tools = toolbox.get_tools()

    search_tool = find_search_tool(tools)
    assert search_tool is not None, "Should find search tool"
    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)

    # Should use k=1 as configured in toolbox
    with pytest.warns(UserWarning, match="No vector config found for collection"):
        results = search_tool.run(query="Harley")
    assert len(results) <= 1

    # Create another toolbox with different k
    toolbox_k5 = populated_oracle_vehicle_datastore.get_search_toolbox(
        k=5, collection_names=["motorcycles"]
    )
    tools_k5 = toolbox_k5.get_tools()
    search_tool_k5 = find_search_tool(tools_k5)
    assert search_tool_k5 is not None
    search_tool_k5 = search_tool_k5.toolbox._get_concrete_tool(search_tool_k5.name)
    with pytest.warns(UserWarning, match="No vector config found for collection"):
        results_k5 = search_tool_k5.run(query="Harley")
    assert len(results_k5) <= 5


@retry_test(max_attempts=3)
@pytest.mark.parametrize(
    "collection_name, model_name, search_config, model_name_test",
    [
        ("motorcycles", "BMW", "default_search", "model_name"),
        ("motorcycles", "BMW", "specific_search_motor", "model_name"),
        ("cars", "Tesla", "specific_search_car_cosine", "car_model"),
        ("cars", "Audi", "specific_search_car_l2", "car_model"),
    ],
)
def test_multiple_search_configurations(
    populated_oracle_vehicle_multi_search_config_datastore,
    collection_name,
    model_name,
    search_config,
    model_name_test,
):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-10
    Average success time:  4.00 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    """Test datastore with multiple search configurations."""

    # Test search with different configs
    with pytest.warns(UserWarning, match="No vector config found for collection"):
        results = populated_oracle_vehicle_multi_search_config_datastore.search(
            model_name, collection_name, search_config=search_config, k=2
        )

    assert len(results) > 0

    # All results should find the relevant model names
    assert any(model_name in r.get(model_name_test, "") for r in results)


@retry_test(max_attempts=3)
@pytest.mark.parametrize(
    "collection_name, model_name, search_config, model_name_test",
    [
        ("motorcycles", "BMW", "default_search", "model_name"),
        ("motorcycles", "BMW", None, "model_name"),
        ("cars", "Tesla", None, "car_model"),
        ("cars", "Tesla", "default_search", "car_model"),
    ],
)
def test_vector_config_works_as_expected(
    populated_oracle_vehicle_vector_config_datastore,
    collection_name,
    model_name,
    search_config,
    model_name_test,
):
    """
    ("motorcycles", "BMW", "default_search", "model_name")
    Failure rate:          0 out of 50
    Observed on:           2025-11-04
    Average success time:  1.23 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000

    ("motorcycles", "BMW", None, "model_name")
    Failure rate:          0 out of 50
    Observed on:           2025-11-04
    Average success time:  1.02 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000

    ("cars", "Tesla", None, "car_model")
    Failure rate:          0 out of 50
    Observed on:           2025-11-04
    Average success time:  1.03 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000

    ("cars", "Tesla", "default_search", "car_model")
    Failure rate:          0 out of 50
    Observed on:           2025-11-04
    Average success time:  0.97 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """

    results = populated_oracle_vehicle_vector_config_datastore.search(
        model_name, collection_name, search_config=search_config, k=2
    )

    assert len(results) > 0
    assert any(model_name in r.get(model_name_test, "") for r in results)


@retry_test(max_attempts=3)
@pytest.mark.parametrize(
    "collection_name, model_name, search_config, model_name_test",
    [
        ("motorcycles", "BMW", "specific_search_motor_embeddings_2", "model_name"),
        ("cars", "Tesla", "specific_search_cars_embeddings_2", "car_model"),
        ("cars", "Tesla", "specific_search_car_l2", "car_model"),
        (
            "cars",
            "Tesla",
            None,
            "car_model",
        ),  # Should be able to infer a default search_config for a collection_name
        (
            "motorcycles",
            "BMW",
            None,
            "model_name",
        ),  # Should be able to infer a default search_config for a collection_name
        (None, "Tesla", "specific_search_cars_embeddings_2", "car_model"),
        (None, "BMW", "specific_search_motor_embeddings_2", "model_name"),
    ],
)
def test_complex_datastore_works_with_different_combinations(
    populated_oracle_vehicle_multi_search_and_vector_config_datastore,
    collection_name,
    model_name,
    search_config,
    model_name_test,
):
    """
    ("motorcycles", "BMW", "specific_search_motor_embeddings_2", "model_name")
    Failure rate:          0 out of 20
    Observed on:           2025-12-17
    Average success time:  1.20 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    ("cars", "Tesla", "specific_search_cars_embeddings_2", "car_model")
    Failure rate:          0 out of 20
    Observed on:           2025-12-17
    Average success time:  1.25 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    ("cars", "Tesla", "specific_search_car_l2", "car_model")
    Failure rate:          0 out of 20
    Observed on:           2025-12-17
    Average success time:  1.18 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    ("cars", "Tesla", None, "car_model")
    Failure rate:          0 out of 20
    Observed on:           2025-12-17
    Average success time:  1.23 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    ("motorcycles", "BMW", None, "model_name")
    Failure rate:          0 out of 20
    Observed on:           2025-12-17
    Average success time:  1.24 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    (None, "Tesla", "specific_search_cars_embeddings_2", "car_model")
    Failure rate:          0 out of 20
    Observed on:           2025-12-17
    Average success time:  1.23 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    (None, "BMW", "specific_search_motor_embeddings_2", "model_name")
    Failure rate:          0 out of 20
    Observed on:           2025-12-17
    Average success time:  1.23 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """

    results = populated_oracle_vehicle_multi_search_and_vector_config_datastore.search(
        model_name,
        collection_name,
        search_config=search_config,
        k=2,
    )

    assert len(results) > 0
    assert any(model_name in r.get(model_name_test, "") for r in results)


@pytest.mark.parametrize(
    "collection_name, model_name, search_config",
    [
        ("motorcycles", "BMW", "default_search"),
        ("motorcycles", "BMW", "specific_search_motor"),
        ("cars", "Tesla", "specific_search_car_embeddings"),
    ],
)
def test_complex_datastore_raises_with_incorrect_search_config(
    populated_oracle_vehicle_multi_search_and_vector_config_datastore,
    collection_name,
    model_name,
    search_config,
):
    # For collection motorcycles, the search should raise an error for SearchConfigs which do not specify a VectorConfig in the vectors argument.
    # This is because multiple VectorConfigs exist for motorcycles.
    # For example, specific_search_car_embeddings can have either vector_config3 and vector_config4 for property `embeddings`
    with pytest.raises(ValueError, match="Multiple vector configs found for collection"):
        populated_oracle_vehicle_multi_search_and_vector_config_datastore.search(
            model_name,
            collection_name,
            search_config=search_config,
            k=2,
        )
