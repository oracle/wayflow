# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


import pytest

from wayflowcore.agent import Agent
from wayflowcore.tools import ServerTool, ToolBox

from ..testhelpers.testhelpers import retry_test
from .conftest import find_search_tool


def test_get_search_tools_returns_toolbox(inmemory_motorcycle_datastore):
    """Test that get_search_tools returns a ToolBox instance."""
    toolbox = inmemory_motorcycle_datastore.get_search_toolbox()

    assert isinstance(toolbox, ToolBox), f"Expected ToolBox, got {type(toolbox)}"

    tools = toolbox.get_tools()
    assert all(isinstance(toolbox._get_concrete_tool(t.name), ServerTool) for t in tools)


def test_get_search_tools_functionality(inmemory_motorcycle_datastore):
    """Test that get_search_tools generates working search tools."""
    toolbox = inmemory_motorcycle_datastore.get_search_toolbox()

    tools = toolbox.get_tools()

    assert len(tools) > 0, f"Expected at least one tool, got {len(tools)}"

    search_tool = next(
        iter(tool for tool in tools if tool.name == "search_motorcycles_search_motorcycles"), None
    )

    assert (
        search_tool is not None
    ), "Should have created a search_motorcycles_search_motorcycles tool"
    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)

    results = search_tool.run(query="adventure touring BMW", columns_to_exclude=["_embedding"])

    assert isinstance(results, list), f"Expected list, got {type(results)}"

    assert len(results) > 0
    # Verify results have expected fields (if any results returned)
    for result in results:
        assert "model_name" in result, f"Missing model_name in result: {result.keys()}"
        assert "owner_name" in result, f"Missing owner_name in result: {result.keys()}"
        assert "description" in result, f"Missing description in result: {result.keys()}"
        assert "_score" in result, f"Missing _score in result: {result.keys()}"

        internal_fields = [k for k in result.keys() if k.startswith("_") and k != "_score"]
        assert len(internal_fields) == 0, f"Internal fields {internal_fields} should be filtered"


@retry_test(max_attempts=3)
def test_search_tool_returns_relevant_results(inmemory_motorcycle_datastore):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-10-17
    Average success time:  0.96 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    """Test that search tool returns relevant results for specific queries."""
    toolbox = inmemory_motorcycle_datastore.get_search_toolbox()
    tools = toolbox.get_tools()

    search_tool = next(
        iter(tool for tool in tools if tool.name == "search_motorcycles_search_motorcycles"), None
    )
    assert search_tool is not None
    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)

    # Test BMW search
    bmw_results = search_tool.run(query="BMW adventure motorcycle")
    assert len(bmw_results) > 0

    assert "BMW" in bmw_results[0].get("model_name", "")

    harley_results = search_tool.run(query="Harley Davidson touring")
    assert len(harley_results) > 0

    assert "Harley-Davidson" in harley_results[0].get("model_name", "")


@pytest.mark.parametrize("k", [1, 3, 5])
def test_search_toolbox_with_k_parameter(inmemory_motorcycle_datastore, k):
    """Test that the search toolbox respects the k parameter."""
    toolbox = inmemory_motorcycle_datastore.get_search_toolbox(k=k)

    tools = toolbox.get_tools()
    search_func = next(
        (
            tool.toolbox._get_concrete_tool(tool.name).run
            for tool in tools
            if tool.name and "search_motorcycles" in tool.name
        ),
        None,
    )

    assert search_func is not None

    results = search_func(query="motorcycle")
    assert len(results) == k, f"Expected at most {k} result(s) with k={k}, got {len(results)}"


def test_search_tool_handles_low_score_gracefully(inmemory_motorcycle_datastore):
    """Test that search tool handles queries with no results gracefully."""
    toolbox = inmemory_motorcycle_datastore.get_search_toolbox()
    tools = toolbox.get_tools()

    search_func = next(
        (
            tool.toolbox._get_concrete_tool(tool.name).run
            for tool in tools
            if tool.name and "search_motorcycles" in tool.name
        ),
        None,
    )

    assert search_func is not None

    results = search_func(query="submarine aircraft carrier spaceship")

    # Should return a list (possibly empty or with low-scoring results)
    assert isinstance(results, list)

    # Even if results are returned, they should have low scores (scores are strings now)
    for result in results:
        score_str = result.get("_score", 0)
        score = float(score_str)
        assert score < 0.8  # Low score to be expected for non-relevant queries


def test_search_toolbox_dynamic_behavior(inmemory_motorcycle_datastore):
    """Test that the toolbox dynamically generates tools on each get_tools() call."""
    toolbox = inmemory_motorcycle_datastore.get_search_toolbox()

    tools1 = toolbox.get_tools()
    tools2 = toolbox.get_tools()

    assert len(tools1) > 0
    assert len(tools2) > 0

    assert set(t.name for t in tools1) == set(t.name for t in tools2)


def test_search_toolbox_with_non_existent_collections(inmemory_motorcycle_datastore):
    """Test that toolbox can be created for specific collections."""
    toolbox = inmemory_motorcycle_datastore.get_search_toolbox(collection_names=["motorcycles"])
    tools = toolbox.get_tools()

    assert len(tools) == 1, "Should create exactly one tool for one collection"

    invalid_toolbox = inmemory_motorcycle_datastore.get_search_toolbox(
        collection_names=["nonexistent"]
    )
    invalid_tools = invalid_toolbox.get_tools()
    assert len(invalid_tools) == 0, "Should create no tools for non-existent collection"


@retry_test(max_attempts=3)
def test_agent_tool_execution(
    inmemory_motorcycle_datastore,
    remotely_hosted_llm,
):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-16
    Average success time:  1.49 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    """Test that agent actually executes search tools during conversation."""
    search_toolbox = inmemory_motorcycle_datastore.get_search_toolbox()

    agent = Agent(
        tools=[search_toolbox],
        llm=remotely_hosted_llm,
        custom_instruction="You are a motorcycle expert. Always use the search tool to find accurate information before answering.",
        max_iterations=5,
    )
    assert len(agent._toolboxes) > 0

    conversation = agent.start_conversation()

    conversation.append_user_message("What is the exact horsepower of the BMW motorcycle?")
    conversation.execute()

    final_response = conversation.get_last_message().content
    assert any(
        term in final_response for term in ["136", "BMW"]
    ), f"Response should mention BMW motorcycle info. Got: {final_response}"


@retry_test(max_attempts=3)
def test_rag_workflow_complete(
    inmemory_motorcycle_datastore,
    remotely_hosted_llm,
):
    """
    Failure rate:          1 out of 50
    Observed on:           2025-09-16
    Average success time:  2.50 seconds per successful attempt
    Average failure time:  1.51 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000
    """
    """Complete RAG workflow test."""
    results = inmemory_motorcycle_datastore.search(
        collection_name="motorcycles", query="high performance sport bike", k=2
    )
    assert len(results) > 0

    toolbox = inmemory_motorcycle_datastore.get_search_toolbox()
    tools = toolbox.get_tools()
    search_tool = find_search_tool(tools)
    assert search_tool is not None
    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)
    tool_results = search_tool.run(query="sport bike")
    assert len(tool_results) > 0


# Default Search is for both cars and motorcyles
# Otherwise, the configs mention the collection name
@pytest.mark.parametrize(
    "search_configs, collection_names, expected_tools",
    [
        (
            [
                "default_search",
                "specific_search_motor",
                "specific_search_car_cosine",
                "specific_search_car_l2",
            ],
            ["motorcycles", "cars"],
            5,
        ),
        (
            [
                "default_search",
                "specific_search_motor",
                "specific_search_car_cosine",
                "specific_search_car_l2",
            ],
            None,
            5,
        ),
        (None, ["motorcycles"], 1),
        (["default_search", "specific_search_motor"], ["motorcycles"], 2),
        (["default_search", "specific_search_motor"], ["motorcycles", "cars"], 3),
        (["specific_search_motor"], ["motorcycles", "cars"], 2),
        (None, ["motorcycles", "cars"], 2),
        (None, None, 2),  # One default search config for each collection in Datastore
    ],
)
def test_multiple_search_configurations_with_search_tools(
    populated_inmemory_vehicle_datastore,
    search_configs,
    collection_names,
    expected_tools,
):
    toolbox = populated_inmemory_vehicle_datastore.get_search_toolbox(
        search_configs=search_configs, collection_names=collection_names
    )
    search_tools = toolbox.get_tools()
    assert len(search_tools) == expected_tools
