# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import os
from pathlib import Path
from typing import Dict, Union, cast

import pytest
import yaml

from wayflowcore.a2a.a2aagent import A2AAgent as RuntimeA2AAgent
from wayflowcore.agent import Agent as RuntimeAgent
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.flow import Flow as RuntimeFlow
from wayflowcore.ociagent import OciAgent as RuntimeOciAgent
from wayflowcore.tools.servertools import ServerTool

from ..testhelpers.testhelpers import assert_agents_are_copies, assert_flows_are_copies

CONFIGS_DIR = Path(os.path.dirname(__file__)) / "configs"


@pytest.mark.parametrize(
    "filename, conversation_inputs",
    [
        ("flow_1.yaml", {"user_request": "compute the n-th catalan number"}),
        (
            "flow_2.yaml",
            {"user_request": "compute the n-th catalan number", "review": "", "code": ""},
        ),
        (
            "flow_3.yaml",
            {"user_request": "compute the n-th catalan number", "review": "", "code": ""},
        ),
        ("flow_4.yaml", {"x_list": [1.1, 2.2, 3.3, 4.4]}),
        ("flow_5.yaml", {"x_list": [1.1, 2.2, 3.3, 4.4]}),
        ("flow_6.yaml", {}),
        (
            "flow_7.yaml",  # Flow uses Variable, VariableReadStep, VariableWriteStep
            {
                "feedback_1": "Very good!",
                "feedback_2": "Need to improve!",
            },
        ),
        ("agent_1.yaml", {}),
        ("agent_2.yaml", {}),
        ("agent_3.yaml", {}),
        ("agent_4.yaml", {}),
        ("agent_5.yaml", {}),  # Agent using OCI Llm
        (
            "hr_benefits.yaml",
            {
                "context": "today is the 1st january 1970",
                "agent_title": "Benefits Advisor",
                "agent_description": "",
                "format_instructions": "use any format you want",
                "tools": "see below the instructions for tools",
                "workflow_title": "Incident Mitigation workflow",
                "topics": "cloud operations",
                "workflow_description": "A workflow for helping operators mitigate incidents",
                "special_instructions": "no special instructions",
            },
        ),
        ("ociagent_1.yaml", {}),
        ("a2aagent_1.yaml", {}),
        ("swarm.yaml", {}),
        ("managerworkers.yaml", {}),
    ],
)
def test_agentspec_config_can_be_converted_to_core_then_back_to_agentspec(
    filename: str, conversation_inputs: Dict[str, str], mock_tool_registry: Dict[str, ServerTool]
) -> None:
    loader = AgentSpecLoader(tool_registry=mock_tool_registry)
    with open(CONFIGS_DIR / filename, "r") as file:
        assistant = cast(Union[RuntimeAgent, RuntimeFlow], loader.load_yaml(file.read()))
    # Test both yaml and json
    agentspec_yaml = AgentSpecExporter().to_yaml(assistant)
    assert (
        "component_type: Agent" in agentspec_yaml
        or "component_type: Flow" in agentspec_yaml
        or "component_type: ExtendedFlow" in agentspec_yaml
        or "component_type: OciAgent" in agentspec_yaml
        or "component_type: A2AAgent" in agentspec_yaml
    )
    assert "inputs:" in agentspec_yaml
    assert "outputs:" in agentspec_yaml

    agentspec_json = AgentSpecExporter().to_json(assistant)
    assert (
        '"component_type": "Agent"' in agentspec_json
        or '"component_type": "Flow"' in agentspec_json
        or '"component_type": "ExtendedFlow"' in agentspec_json
        or '"component_type": "OciAgent"' in agentspec_json
        or '"component_type": "A2AAgent"' in agentspec_json
    )
    assert '"inputs":' in agentspec_json
    assert '"outputs":' in agentspec_json


@pytest.mark.parametrize(
    "filename, conversation_inputs",
    [
        ("flow_1.yaml", {"user_request": "compute the n-th catalan number"}),
        (
            "flow_2.yaml",
            {"user_request": "compute the n-th catalan number", "review": "", "code": ""},
        ),
        (
            "flow_3.yaml",
            {"user_request": "compute the n-th catalan number", "review": "", "code": ""},
        ),
        ("flow_4.yaml", {"x_list": [1.1, 2.2, 3.3, 4.4]}),
        ("flow_5.yaml", {"x_list": [1.1, 2.2, 3.3, 4.4]}),
        ("agent_1.yaml", {}),
        ("agent_2.yaml", {}),
        ("agent_3.yaml", {}),
        ("agent_4.yaml", {}),
        ("agent_5.yaml", {}),  # Agent using OCI Llm
        (
            "hr_benefits.yaml",
            {
                "context": "today is the 1st january 1970",
                "agent_title": "Benefits Advisor",
                "agent_description": "",
                "format_instructions": "use any format you want",
                "tools": "see below the instructions for tools",
                "workflow_title": "Incident Mitigation workflow",
                "topics": "cloud operations",
                "workflow_description": "A workflow for helping operators mitigate incidents",
                "special_instructions": "no special instructions",
            },
        ),
        ("ociagent_1.yaml", {}),
        ("a2aagent_1.yaml", {}),
        ("swarm.yaml", {}),
    ],
)
def test_agentspec_json_and_yaml_import_are_equal(
    filename: str, conversation_inputs: Dict[str, str], mock_tool_registry: Dict[str, ServerTool]
) -> None:
    agentspec_loader = AgentSpecLoader(tool_registry=mock_tool_registry)
    with open(CONFIGS_DIR / filename, "r") as file:
        assistant_yaml = file.read()
        assistant_json = json.dumps(yaml.safe_load(assistant_yaml))
        assistant = cast(
            Union[RuntimeAgent, RuntimeFlow], agentspec_loader.load_yaml(assistant_yaml)
        )
    deserialized_yaml_assistant = agentspec_loader.load_yaml(assistant_yaml)
    deserialized_json_assistant = agentspec_loader.load_json(assistant_json)
    if isinstance(assistant, RuntimeOciAgent):
        assert (
            deserialized_yaml_assistant.agent_endpoint_id
            == deserialized_json_assistant.agent_endpoint_id
        )
        assert (
            deserialized_yaml_assistant.initial_message
            == deserialized_json_assistant.initial_message
        )
        assert deserialized_yaml_assistant.agent_id == deserialized_json_assistant.agent_id
        assert deserialized_yaml_assistant.name == deserialized_json_assistant.name
        assert deserialized_yaml_assistant.description == deserialized_json_assistant.description
        assert isinstance(
            deserialized_yaml_assistant.client_config,
            type(deserialized_json_assistant.client_config),
        )
    elif isinstance(assistant, RuntimeA2AAgent):
        assert deserialized_yaml_assistant.id == deserialized_json_assistant.id
        assert deserialized_yaml_assistant.name == deserialized_json_assistant.name
        assert deserialized_yaml_assistant.description == deserialized_json_assistant.description
        assert deserialized_yaml_assistant.agent_url == deserialized_json_assistant.agent_url
        assert (
            deserialized_yaml_assistant.connection_config
            == deserialized_json_assistant.connection_config
        )
        assert (
            deserialized_yaml_assistant.session_parameters
            == deserialized_json_assistant.session_parameters
        )
    elif isinstance(assistant, RuntimeFlow):
        assert_flows_are_copies(deserialized_yaml_assistant, deserialized_json_assistant)
    elif isinstance(assistant, RuntimeAgent):
        assert_agents_are_copies(deserialized_yaml_assistant, deserialized_json_assistant)
    else:  # RuntimeSwarm
        assert deserialized_yaml_assistant.name == deserialized_json_assistant.name
        assert deserialized_yaml_assistant.description == deserialized_json_assistant.description
        assert_agents_are_copies(
            deserialized_yaml_assistant.first_agent, deserialized_json_assistant.first_agent
        )
        assert len(deserialized_yaml_assistant.relationships) == len(
            deserialized_json_assistant.relationships
        )
        for i in range(len(deserialized_yaml_assistant.relationships)):
            yaml_agent_1, yaml_agent_2 = deserialized_yaml_assistant.relationships[i]
            json_agent_1, json_agent_2 = deserialized_json_assistant.relationships[i]
            assert_agents_are_copies(yaml_agent_1, json_agent_1)
            assert_agents_are_copies(yaml_agent_2, json_agent_2)
        assert deserialized_yaml_assistant.handoff == deserialized_json_assistant.handoff
