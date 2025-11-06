# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


import pytest
from pyagentspec import AgentSpecDeserializer, AgentSpecSerializer
from pyagentspec.agent import Agent
from pyagentspec.llms.vllmconfig import VllmConfig
from pyagentspec.mcp import MCPToolBox, SSETransport

from wayflowcore.agentspec import AgentSpecLoader
from wayflowcore.agentspec.components import (
    ExtendedAgent,
    PluginMCPToolBox,
    PluginSSETransport,
    all_deserialization_plugin,
    all_serialization_plugin,
)


@pytest.fixture
def agent_with_toolbox_plugin_old() -> ExtendedAgent:
    client_transport = PluginSSETransport(
        name="sse_client_transport", url=f"http://0.0.0.0:8001/sse"
    )

    mcp_toolbox = PluginMCPToolBox(
        name="MCPToolBox", client_transport=client_transport, tool_filter=["some_tool"]
    )
    llm_config = VllmConfig(
        name="meta/maverick",
        url="'llama_4_maverick_api_url'",
        model_id="Llama-4-Maverick",
    )

    agent = ExtendedAgent(
        name="payslip_advisor_agent",
        description="An advisor that helps employees Retrieve information about payslips issued to the employee.",
        llm_config=llm_config,
        system_prompt="""You are a helpful assistant ...""",
        toolboxes=[mcp_toolbox],
    )

    return agent


@pytest.fixture
def agent_with_toolbox() -> Agent:
    client_transport = SSETransport(name="sse_client_transport", url=f"http://0.0.0.0:8001/sse")

    mcp_toolbox = MCPToolBox(
        name="MCPToolBox", client_transport=client_transport, tool_filter=["some_tool"]
    )
    llm_config = VllmConfig(
        name="meta/maverick",
        url="llama_4_maverick_api_url",
        model_id="Llama-4-Maverick",
    )
    agent = Agent(
        name="payslip_advisor_agent",
        description="An advisor that helps employees Retrieve information about payslips issued to the employee.",
        llm_config=llm_config,
        system_prompt="""You are a helpful assistant ...""",
        toolboxes=[mcp_toolbox],
    )
    return agent


@pytest.mark.parametrize(
    "agent_fixture_name",
    argvalues=["agent_with_toolbox_plugin_old", "agent_with_toolbox"],
    ids=["agent_with_toolbox_plugin_old", "agent_with_toolbox_native"],
)
def test_agent_with_toolbox_serializes(request: pytest.FixtureRequest, agent_fixture_name: str):
    agent = request.getfixturevalue(agent_fixture_name)
    serialized_assistant = AgentSpecSerializer(all_serialization_plugin).to_yaml(agent)
    deserialized_assistant = AgentSpecDeserializer(all_deserialization_plugin).from_yaml(
        serialized_assistant
    )
    if (
        agent_fixture_name == "agent_with_toolbox"
    ):  # native toolbox should not serialize with plugin
        assert "component_plugin_name: " not in serialized_assistant
    # when deserializing a component, the min_agentspec_version of child components may
    # be bumped by propagation from the root component -> equality is tested except on this field.
    assert agent._is_equal(deserialized_assistant, fields_to_exclude=["min_agentspec_version"])


@pytest.mark.parametrize(
    "agent_fixture_name",
    argvalues=["agent_with_toolbox_plugin_old", "agent_with_toolbox"],
    ids=["agent_with_toolbox_plugin_old", "agent_with_toolbox_native"],
)
def test_agent_with_toolbox_convertion_to_wayflowcore(
    request: pytest.FixtureRequest, agent_fixture_name: str, with_mcp_enabled
):
    agent = request.getfixturevalue(agent_fixture_name)
    _ = AgentSpecLoader().load_component(agent)
