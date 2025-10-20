# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import os

import pytest
from pyagentspec import AgentSpecDeserializer, AgentSpecSerializer
from pyagentspec.llms.vllmconfig import VllmConfig

from wayflowcore.agentspec import AgentSpecLoader
from wayflowcore.agentspec.components import (
    ExtendedAgent,
    PluginMCPToolBox,
    PluginSSETransport,
    all_deserialization_plugin,
    all_serialization_plugin,
)


@pytest.fixture
def agent_with_toolbox() -> ExtendedAgent:
    client_transport = PluginSSETransport(
        name="sse_client_transport", url=f"http://0.0.0.0:8001/sse"
    )

    mcp_toolbox = PluginMCPToolBox(
        name="MCPToolBox", client_transport=client_transport, tool_filter=["some_tool"]
    )
    llama_4_maverick_api_url = os.environ.get("LLAMA_4_Maverick_API_URL")
    if not llama_4_maverick_api_url:
        raise Exception("LLAMA_4_Maverick_API_URL is not set in the environment")
    llm_config = VllmConfig(
        name="meta/maverick",
        url=llama_4_maverick_api_url,
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


def test_agent_with_toolbox_serde(agent_with_toolbox):
    serialized_assistant = AgentSpecSerializer(plugins=all_serialization_plugin).to_yaml(
        agent_with_toolbox
    )
    deserialized_assistant = AgentSpecDeserializer(plugins=all_deserialization_plugin).from_yaml(
        serialized_assistant
    )
    assert agent_with_toolbox == deserialized_assistant


def test_agent_with_toolbox_convertion_to_wayflowcore(agent_with_toolbox, with_mcp_enabled):
    wayflowcore_agent_with_toolbox = AgentSpecLoader().load_component(agent_with_toolbox)
