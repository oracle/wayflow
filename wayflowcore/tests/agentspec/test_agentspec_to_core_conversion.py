# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import os
from pathlib import Path
from typing import Any, Dict, Union, cast

import pytest

from wayflowcore.agent import Agent as RuntimeAgent
from wayflowcore.agentspec import AgentSpecLoader
from wayflowcore.executors.executionstatus import ExecutionStatus, FinishedStatus
from wayflowcore.flow import Flow as RuntimeFlow
from wayflowcore.tools.servertools import ServerTool

from ..mcptools.conftest import sse_mcp_server_http  # isort:skip

CONFIGS_DIR = Path(os.path.dirname(__file__)) / "configs"


@pytest.mark.parametrize(
    "filename, conversation_inputs",
    [
        ("flow_1.yaml", {"user_request": "compute the n-th catalan number"}),
        (
            "flow_2.yaml",
            {"user_request": "compute the n-th catalan number"},
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
        ("mcp_agent.yaml", {}),
        ("ociagent_1.yaml", {}),
    ],
)
def test_agentspec_config_can_be_converted_to_core_then_executed(
    filename: str,
    conversation_inputs: Dict[str, str],
    mock_tool_registry: Dict[str, ServerTool],
    with_mcp_enabled,
    sse_mcp_server_http,
) -> None:
    run_example(
        filename=filename,
        conversation_inputs=conversation_inputs,
        mock_tool_registry=mock_tool_registry,
        sse_mcp_server_http=sse_mcp_server_http,
    )


@pytest.mark.parametrize(
    "filename, conversation_inputs",
    [
        ("legacy/mcp_agent.yaml", {}),
        ("legacy/input_output_message_flow.yaml", {}),
    ],
)
def test_legacy_agentspec_config_can_be_converted_to_core_then_executed(
    filename: str,
    conversation_inputs: Dict[str, str],
    with_mcp_enabled,
    sse_mcp_server_http,
) -> None:
    with pytest.warns(UserWarning, match="Missing `agentspec_version` field"):
        run_example(
            filename=filename,
            conversation_inputs=conversation_inputs,
            mock_tool_registry={},
            sse_mcp_server_http=sse_mcp_server_http,
        )


def run_example(
    filename: str,
    mock_tool_registry: Dict[str, ServerTool],
    conversation_inputs: Dict[str, Any],
    sse_mcp_server_http,
):
    loader = AgentSpecLoader(tool_registry=mock_tool_registry)

    llama70bv33_endpoint = os.environ.get("LLAMA70BV33_API_URL")
    if not llama70bv33_endpoint:
        raise Exception("LLAMA70BV33_API_URL is not set in the environment")
    oracle_process_helper_agent_endpoint_id = os.environ.get(
        "ORACLE_PROCESS_HELPER_AGENT_ENDPOINT_ID"
    )
    if not oracle_process_helper_agent_endpoint_id:
        raise Exception("ORACLE_PROCESS_HELPER_AGENT_ENDPOINT_ID is not set in the environment")

    with open(CONFIGS_DIR / filename, "r") as file:
        text = file.read()
        text = text.replace("LLAMA70BV33_API_URL", llama70bv33_endpoint)
        text = text.replace(
            "ORACLE_PROCESS_HELPER_AGENT_ENDPOINT_ID", oracle_process_helper_agent_endpoint_id
        )
        text = text.replace("MCP_SERVER_URL", sse_mcp_server_http)
        wayflowcore_assistant = cast(Union[RuntimeAgent, RuntimeFlow], loader.load_yaml(text))
    conversation = wayflowcore_assistant.start_conversation(conversation_inputs)
    status = conversation.execute()
    assert isinstance(status, ExecutionStatus)


def test_apinode_exposes_http_response_among_outputs_when_executed() -> None:
    loader = AgentSpecLoader()

    with open(CONFIGS_DIR / "flow_6.yaml", "r") as file:
        wayflowcore_assistant = cast(
            Union[RuntimeAgent, RuntimeFlow], loader.load_yaml(file.read())
        )
    conversation = wayflowcore_assistant.start_conversation()
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    assert "http_response" in status.output_values
