# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import pytest

from wayflowcore import Agent
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.mcp import (
    MCPTool,
    MCPToolBox,
    SSEmTLSTransport,
    SSETransport,
    StdioTransport,
    StreamableHTTPmTLSTransport,
    StreamableHTTPTransport,
)
from wayflowcore.property import StringProperty


@pytest.mark.parametrize(
    "client_transport",
    [
        SSETransport(url="http://url-to/server"),
        SSETransport(url="http://url-to/server", timeout=100),
        SSEmTLSTransport(
            url="http://url-to/server",
            cert_file="cert_file",
            ssl_ca_cert="ssl_ca_cert",
            key_file="key_fil",
        ),
        SSEmTLSTransport(
            url="http://url-to/server",
            cert_file="cert_file",
            ssl_ca_cert="ssl_ca_cert",
            key_file="key_fil",
            timeout=100,
        ),
        StreamableHTTPTransport(url="http://url-to/server"),
        StreamableHTTPTransport(url="http://url-to/server", timeout=100),
        StreamableHTTPmTLSTransport(
            url="http://url-to/server",
            cert_file="cert_file",
            ssl_ca_cert="ssl_ca_cert",
            key_file="key_fil",
        ),
        StreamableHTTPmTLSTransport(
            url="http://url-to/server",
            cert_file="cert_file",
            ssl_ca_cert="ssl_ca_cert",
            key_file="key_fil",
            timeout=100,
        ),
        StdioTransport(command="command", cwd=".."),
    ],
)
def test_mcp_tool_can_be_converted_to_agentspec_and_back(
    client_transport, remotely_hosted_llm, with_mcp_enabled
):
    mcp_tool = MCPTool(
        name="fooza_tool",
        client_transport=client_transport,
        _validate_server_exists=False,  # should not be done, but avoids requiring the server here
        description="some description",
        input_descriptors=[StringProperty(name="a"), StringProperty(name="b")],
    )
    mcp_toolbox = MCPToolBox(client_transport=client_transport)
    agent = Agent(llm=remotely_hosted_llm, tools=[mcp_tool, mcp_toolbox])

    components_registry = {
        f"{client_transport.id}.cert_file": getattr(client_transport, "cert_file", None),
        f"{client_transport.id}.ca_file": getattr(client_transport, "ssl_ca_cert", None),
        f"{client_transport.id}.key_file": getattr(client_transport, "key_file", None),
    }

    agentspec_agent = AgentSpecExporter().to_json(agent)
    reloaded_agent = AgentSpecLoader().load_json(
        agentspec_agent, components_registry=components_registry
    )

    assert isinstance(reloaded_agent, Agent)
    assert reloaded_agent.llm.id == agent.llm.id
    all_agent_tools = {t.name: t for t in agent.tools}
    all_reloaded_agent_tools = {t.name: t for t in reloaded_agent.tools}
    assert len(all_agent_tools) == len(all_reloaded_agent_tools)
    for key, value in all_agent_tools.items():
        assert value == all_reloaded_agent_tools[key]
