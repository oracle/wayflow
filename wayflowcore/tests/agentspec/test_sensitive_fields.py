# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from pathlib import Path

import pytest
from pyagentspec import Component

from wayflowcore.agent import Agent
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.mcp import (
    MCPToolBox,
    SSEmTLSTransport,
    StreamableHTTPmTLSTransport,
)
from wayflowcore.models import OCIGenAIModel, OpenAICompatibleModel
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey
from wayflowcore.steps import ApiCallStep
from wayflowcore.tools import RemoteTool, ServerTool


@pytest.fixture
def agent_with_sensitive_fields_filepath() -> str:
    return str(Path(__file__).parent / "configs" / "agent_with_sensitive_fields.json")


# All components used as test case have the string 'abcdexyz' added on a sensitive field.
# This string should be excluded when serializing.
@pytest.mark.parametrize(
    "component",
    [
        Agent(
            name="name",
            custom_instruction="Hi",
            llm=OpenAICompatibleModel(
                name="openai-compatible-config",
                base_url="https://api.closedai.com/v2",
                model_id="gpt-7",
                api_key="abcdexyz",
            ),
            tools=[
                RemoteTool(
                    name="tool_name1",
                    description="description",
                    url="https://some.url",
                    method="GET",
                    sensitive_headers={"Authorization": "Bearer abcdexyz"},
                ),
                MCPToolBox(
                    name="tool_name2",
                    description="description",
                    client_transport=StreamableHTTPmTLSTransport(
                        url="https://some.url",
                        cert_file="path/to/abcdexyz.json",
                        key_file="path/to/abcdexyz.pem",
                        ssl_ca_cert="path/to/abcdexyz.pem",
                    ),
                ),
            ],
        ),
        Agent(
            name="name",
            custom_instruction="Hi",
            llm=OCIGenAIModel(
                name="oci-genai-config",
                model_id="gpt-7",
                compartment_id="id-7",
                client_config=OCIClientConfigWithApiKey(
                    _auth_file_location="path/to/abcdexyz.json",
                    auth_profile="default",
                    service_endpoint="https://some.url",
                ),
            ),
            tools=[
                ServerTool.from_step(
                    step=ApiCallStep(
                        name="step_name",
                        url="https://some.url",
                        method="GET",
                        sensitive_headers={"Authorization": "Bearer abcdexyz"},
                    ),
                    step_name="tool_name1",
                    step_description="description",
                ),
                MCPToolBox(
                    name="tool_name2",
                    description="description",
                    client_transport=SSEmTLSTransport(
                        url="https://some.url",
                        cert_file="path/to/abcdexyz.json",
                        key_file="path/to/abcdexyz.pem",
                        ssl_ca_cert="path/to/abcdexyz.pem",
                    ),
                ),
            ],
        ),
    ],
)
def test_exported_component_does_not_contain_sensitive_field(
    with_mcp_enabled, component: Component
) -> None:
    serialized_component = AgentSpecExporter().to_json(component)
    assert "abcdexyz" not in serialized_component
    assert "$component_ref" in serialized_component


def test_can_import_component_with_missing_sensitive_fields(
    with_mcp_enabled,
    agent_with_sensitive_fields_filepath: str,
) -> None:
    components_registry = {
        "oci-client-config.auth_file_location": "path/to/abcdexyz.json",
        "remote-tool-id.sensitive_headers": {"Authorization": "Bearer abcdexyz"},
        "mcp-toolbox-client-transport-id.key_file": "path/to/abcdexyz.json",
        "mcp-toolbox-client-transport-id.cert_file": "path/to/abcdexyz.pem",
        "mcp-toolbox-client-transport-id.ca_file": "path/to/abcdexyz.pem",
    }
    with open(agent_with_sensitive_fields_filepath, "r") as f:
        component = AgentSpecLoader().load_json(f.read(), components_registry=components_registry)
    assert isinstance(component, Agent)
    assert isinstance(component.llm, OCIGenAIModel)
    assert isinstance(component.llm.client_config, OCIClientConfigWithApiKey)
    assert component.llm.client_config.auth_file_location == "path/to/abcdexyz.json"
    remote_tool = next((tool for tool in component.tools if isinstance(tool, RemoteTool)), None)
    assert isinstance(remote_tool, RemoteTool)
    assert remote_tool.sensitive_headers == {"Authorization": "Bearer abcdexyz"}
    mcp_toolbox = next(
        (toolbox for toolbox in component.tools if isinstance(toolbox, MCPToolBox)), None
    )
    assert isinstance(mcp_toolbox, MCPToolBox)
    assert isinstance(mcp_toolbox.client_transport, SSEmTLSTransport)
    assert mcp_toolbox.client_transport.key_file == "path/to/abcdexyz.json"
    assert mcp_toolbox.client_transport.cert_file == "path/to/abcdexyz.pem"
    assert mcp_toolbox.client_transport.ssl_ca_cert == "path/to/abcdexyz.pem"


def test_import_component_with_incomplete_missing_sensitive_fields_fails(
    with_mcp_enabled,
    agent_with_sensitive_fields_filepath: str,
) -> None:
    incomplete_components_registry = {
        "oci-client-config.auth_file_location": "path/to/abcdexyz.json",
        "remote-tool-id.sensitive_headers": {"Authorization": "Bearer abcdexyz"},
        # We remove from the registry the following expected field values to make deserialization fail
        # "mcp-toolbox-client-transport-id.key_file": "path/to/abcdexyz.json",
        # "mcp-toolbox-client-transport-id.cert_file": "path/to/abcdexyz.pem",
        "mcp-toolbox-client-transport-id.ca_file": "path/to/abcdexyz.pem",
    }
    with pytest.raises(
        ValueError, match="The following references to fields or components are missing"
    ):
        with open(agent_with_sensitive_fields_filepath, "r") as f:
            _ = AgentSpecLoader().load_json(
                f.read(), components_registry=incomplete_components_registry
            )
