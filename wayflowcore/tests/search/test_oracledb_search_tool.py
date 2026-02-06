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


def test_get_search_tools_returns_toolbox(populated_oracle_vehicle_datastore):
    """Test that get_search_tools returns a ToolBox instance."""
    toolbox = populated_oracle_vehicle_datastore.get_search_toolbox(
        collection_names=["motorcycles"]
    )

    assert isinstance(toolbox, ToolBox), f"Expected ToolBox, got {type(toolbox)}"

    tools = toolbox.get_tools()
    assert all(isinstance(toolbox._get_concrete_tool(t.name), ServerTool) for t in tools)


def test_get_search_tools_functionality(populated_oracle_vehicle_datastore):
    """Test that get_search_tools generates working search tools."""
    toolbox = populated_oracle_vehicle_datastore.get_search_toolbox(
        collection_names=["motorcycles"]
    )

    tools = toolbox.get_tools()

    assert len(tools) > 0, f"Expected at least one tool, got {len(tools)}"

    search_tool = next(
        iter(tool for tool in tools if tool.name == "search_motorcycles_search_motorcycles"), None
    )

    assert (
        search_tool is not None
    ), "Should have created a search_motorcycles_search_motorcycles tool"

    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)
    with pytest.warns(UserWarning, match="No vector config found for collection"):
        results = search_tool.run(query="adventure touring BMW")

    assert isinstance(results, list), f"Expected list, got {type(results)}"
    assert len(results) > 0
    for result in results:
        assert "model_name" in result, f"Missing model_name in result: {result.keys()}"
        assert "owner_name" in result, f"Missing owner_name in result: {result.keys()}"
        assert "description" in result, f"Missing description in result: {result.keys()}"

        internal_fields = [k for k in result.keys() if k.startswith("_")]
        assert len(internal_fields) == 0, f"Internal fields {internal_fields} should be filtered"


@retry_test(max_attempts=3)
def test_search_tool_returns_relevant_results(populated_oracle_vehicle_datastore):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-10-17
    Average success time:  2.04 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    """Test that search tool returns relevant results for specific queries."""
    toolbox = populated_oracle_vehicle_datastore.get_search_toolbox(
        collection_names=["motorcycles"]
    )
    tools = toolbox.get_tools()

    search_tool = next(
        iter(tool for tool in tools if tool.name == "search_motorcycles_search_motorcycles"), None
    )

    assert search_tool is not None
    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)

    with pytest.warns(UserWarning, match="No vector config found for collection"):
        bmw_results = search_tool.run(query="BMW adventure motorcycle")

    assert len(bmw_results) > 0

    assert "BMW" in bmw_results[0].get("model_name", "")

    with pytest.warns(UserWarning, match="No vector config found for collection"):
        harley_results = search_tool.run(query="Harley Davidson touring")
    assert len(harley_results) > 0

    assert "Harley-Davidson" in harley_results[0].get("model_name", "")


@pytest.mark.parametrize("k", [1, 3, 5])
def test_search_toolbox_with_k_parameter(populated_oracle_vehicle_datastore, k):
    """Test that the search toolbox respects the k parameter."""
    toolbox = populated_oracle_vehicle_datastore.get_search_toolbox(
        k=k, collection_names=["motorcycles"]
    )

    tools = toolbox.get_tools()

    search_func = next(
        (
            tool.toolbox._get_concrete_tool(tool.name).run
            for tool in tools
            if tool.name and "search_motorcycles_search_motorcycles" in tool.name
        ),
        None,
    )

    assert search_func is not None

    with pytest.warns(UserWarning, match="No vector config found for collection"):
        results = search_func(query="motorcycle")
    assert len(results) == k, f"Expected at most {k} result(s) with k={k}, got {len(results)}"


def test_search_toolbox_dynamic_behavior(populated_oracle_vehicle_datastore):
    """Test that the toolbox dynamically generates tools on each get_tools() call."""
    toolbox = populated_oracle_vehicle_datastore.get_search_toolbox(
        collection_names=["motorcycles"]
    )

    tools1 = toolbox.get_tools()
    tools2 = toolbox.get_tools()

    assert len(tools1) > 0
    assert len(tools2) > 0

    assert set(t.name for t in tools1) == set(t.name for t in tools2)


def test_search_toolbox_with_non_existent_collections(populated_oracle_vehicle_datastore):
    """Test that toolbox can be created for specific collections."""
    toolbox = populated_oracle_vehicle_datastore.get_search_toolbox(
        collection_names=["motorcycles"]
    )
    tools = toolbox.get_tools()

    assert len(tools) == 1, "Should create exactly one tool for one collection"

    invalid_toolbox = populated_oracle_vehicle_datastore.get_search_toolbox(
        collection_names=["nonexistent"]
    )
    invalid_tools = invalid_toolbox.get_tools()
    assert len(invalid_tools) == 0, "Should create no tools for non-existent collection"


def test_error_handling_in_search_tools(populated_oracle_vehicle_datastore):
    """Test that search tools handle errors gracefully."""
    toolbox = populated_oracle_vehicle_datastore.get_search_toolbox(
        collection_names=["motorcycles"]
    )
    tools = toolbox.get_tools()
    search_tool = find_search_tool(tools)
    assert search_tool is not None
    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)

    # Test with empty query
    with pytest.warns(UserWarning, match="No vector config found for collection"):
        parsed_result = search_tool.run(query="")
    assert isinstance(parsed_result, list)  # Should return list, not error

    with pytest.warns(UserWarning, match="No vector config found for collection"):
        parsed_result = search_tool.run(query="motorcycle")
    assert isinstance(parsed_result, list)
    assert len(parsed_result) <= 5  # Can't return more than we have


@retry_test(max_attempts=3)
def test_search_toolbox_dynamic_updates(populated_oracle_vehicle_datastore, embedding_model):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-10
    Average success time:  2.06 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    """Test that search toolbox reflects dynamic datastore changes."""
    toolbox = populated_oracle_vehicle_datastore.get_search_toolbox(
        collection_names=["motorcycles"]
    )

    tools_before = toolbox.get_tools()
    assert len(tools_before) > 0

    new_motorcycle = {
        "owner_name": "Test Owner",
        "model_name": "Test Motorcycle",
        "description": "A test motorcycle for dynamic updates",
        "hp": 100,
    }
    concat_str = []
    for key, value in new_motorcycle.items():
        concat_str.append(f"{key}: {value}")
    serial_text = ",".join(concat_str)
    new_motorcycle["serial_text_representation"] = serial_text
    new_motorcycle["embeddings"] = embedding_model.embed(
        data=[new_motorcycle["serial_text_representation"]]
    )[0]
    populated_oracle_vehicle_datastore.create("motorcycles", new_motorcycle)

    tools_after = toolbox.get_tools()
    assert len(tools_after) == len(tools_before)  # Same number of tools

    search_tool = find_search_tool(tools_after)
    assert search_tool is not None
    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)
    with pytest.warns(UserWarning, match="No vector config found for collection"):
        results = search_tool.run(query="Test Motorcycle and Test Owner")
    assert any("Test Motorcycle" in r.get("model_name", "") for r in results)


@retry_test(max_attempts=3)
def test_agent_tool_execution(
    populated_oracle_vehicle_datastore,
    remotely_hosted_llm,
):
    """
    Failure rate:          1 out of 50
    Observed on:           2025-09-16
    Average success time:  2.09 seconds per successful attempt
    Average failure time:  2.05 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000
    """
    """Test that agent actually uses search tools during conversation."""
    search_toolbox = populated_oracle_vehicle_datastore.get_search_toolbox(
        collection_names=["motorcycles"]
    )

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
    populated_oracle_vehicle_datastore,
    remotely_hosted_llm,
):
    """
    Failure rate:          1 out of 50
    Observed on:           2025-09-16
    Average success time:  3.79 seconds per successful attempt
    Average failure time:  2.74 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000
    """
    """Complete RAG workflow test."""
    with pytest.warns(UserWarning, match="No vector config found for collection"):
        results = populated_oracle_vehicle_datastore.search(
            collection_name="motorcycles", query="high performance sport bike", k=2
        )
    assert len(results) > 0

    toolbox = populated_oracle_vehicle_datastore.get_search_toolbox(
        collection_names=["motorcycles"]
    )
    tools = toolbox.get_tools()
    search_tool = find_search_tool(tools)
    assert search_tool is not None
    search_tool = search_tool.toolbox._get_concrete_tool(search_tool.name)

    with pytest.warns(UserWarning, match="No vector config found for collection"):
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
def test_search_tool_multiple_search_configurations(
    populated_oracle_vehicle_multi_search_config_datastore,
    search_configs,
    collection_names,
    expected_tools,
):
    toolbox = populated_oracle_vehicle_multi_search_config_datastore.get_search_toolbox(
        search_configs=search_configs, collection_names=collection_names
    )
    search_tools = toolbox.get_tools()
    assert len(search_tools) == expected_tools
