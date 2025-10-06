# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import anyio
import pytest
from anyio import to_thread

from wayflowcore import Agent, Flow
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import UserMessageRequestStatus
from wayflowcore.flowhelpers import create_single_step_flow, run_step_and_return_outputs
from wayflowcore.mcp import (
    ClientTransport,
    MCPTool,
    MCPToolBox,
    SSEmTLSTransport,
    SSETransport,
    StreamableHTTPmTLSTransport,
    StreamableHTTPTransport,
)
from wayflowcore.property import AnyProperty, IntegerProperty
from wayflowcore.serialization import autodeserialize, serialize
from wayflowcore.steps import MapStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.tools import Tool

from ..testhelpers.testhelpers import retry_test


def test_mcp_without_auth_raises_without_explicit_user_confirmation() -> None:
    with pytest.raises(
        ValueError,
        match="Using MCP servers without proper authentication is highly discouraged",
    ):
        _ = MCPToolBox(client_transport=SSETransport(url="anything"))


@pytest.fixture
def sse_client_transport(sse_mcp_server_http):
    return SSETransport(url=sse_mcp_server_http)


@pytest.fixture
def sse_client_transport_https(sse_mcp_server_https):
    return SSETransport(url=sse_mcp_server_https)


@pytest.fixture
def sse_client_transport_mtls(sse_mcp_server_mtls, client_cert_path, client_key_path, ca_cert_path):
    return SSEmTLSTransport(
        url=sse_mcp_server_mtls,
        key_file=client_key_path,
        cert_file=client_cert_path,
        ssl_ca_cert=ca_cert_path,
    )


@pytest.fixture
def streamablehttp_client_transport(streamablehttp_mcp_server_http):
    return StreamableHTTPTransport(url=streamablehttp_mcp_server_http)


@pytest.fixture
def streamablehttp_client_transport_https(streamablehttp_mcp_server_https):
    return StreamableHTTPTransport(url=streamablehttp_mcp_server_https)


@pytest.fixture
def streamablehttp_client_transport_mtls(
    streamablehttp_mcp_server_mtls, client_cert_path, client_key_path, ca_cert_path
):
    return StreamableHTTPmTLSTransport(
        url=streamablehttp_mcp_server_mtls,
        key_file=client_key_path,
        cert_file=client_cert_path,
        ssl_ca_cert=ca_cert_path,
    )


def run_toolbox_test(transport: ClientTransport) -> None:
    toolbox = MCPToolBox(client_transport=transport)
    tools = toolbox.get_tools()  # need
    assert len(tools) == 4
    assert tools[0].run(a=1, b=2) == "7"
    assert tools[0].input_descriptors == [IntegerProperty(name="a"), IntegerProperty(name="b")]


@pytest.mark.parametrize(
    "client_transport_name",
    [
        "sse_client_transport",
        "sse_client_transport_https",
        "sse_client_transport_mtls",
        "streamablehttp_client_transport",
        "streamablehttp_client_transport_https",
        "streamablehttp_client_transport_mtls",
    ],
)
def test_mcp_toolbox_exposes_proper_tools(client_transport_name, with_mcp_enabled, request):
    client_transport = request.getfixturevalue(client_transport_name)
    run_toolbox_test(client_transport)


async def run_toolbox_test_from_thread_async(transport: ClientTransport) -> None:
    await to_thread.run_sync(run_tool_can_be_executed, transport)


def run_toolbox_test_from_thread(transport: ClientTransport) -> None:
    anyio.run(run_toolbox_test_from_thread_async, transport)


@pytest.mark.parametrize(
    "client_transport_name",
    [
        "sse_client_transport",
        "sse_client_transport_https",
        "sse_client_transport_mtls",
        "streamablehttp_client_transport",
        "streamablehttp_client_transport_https",
        "streamablehttp_client_transport_mtls",
    ],
)
def test_mcp_toolbox_exposes_proper_tools_from_thread(
    client_transport_name, with_mcp_enabled, request
):
    client_transport = request.getfixturevalue(client_transport_name)
    run_toolbox_test_from_thread(client_transport)


def run_tool_can_be_executed(transport: ClientTransport) -> None:
    tool = MCPTool(
        name="fooza_tool",
        client_transport=transport,
    )
    assert tool.run(a=1, b=2) == "7"


@pytest.mark.parametrize(
    "client_transport_name",
    [
        "sse_client_transport",
        "sse_client_transport_https",
        "sse_client_transport_mtls",
        "streamablehttp_client_transport",
        "streamablehttp_client_transport_https",
        "streamablehttp_client_transport_mtls",
    ],
)
def test_mcp_tool_can_be_executed(client_transport_name, with_mcp_enabled, request):
    client_transport = request.getfixturevalue(client_transport_name)
    run_tool_can_be_executed(client_transport)


async def run_tool_can_be_executed_from_thread_async(transport: ClientTransport) -> None:
    await to_thread.run_sync(run_tool_can_be_executed, transport)


def run_tool_can_be_executed_from_thread(transport: ClientTransport) -> None:
    anyio.run(run_tool_can_be_executed_from_thread_async, transport)


@pytest.mark.parametrize(
    "client_transport_name",
    [
        "sse_client_transport",
        "sse_client_transport_https",
        "sse_client_transport_mtls",
        "streamablehttp_client_transport",
        "streamablehttp_client_transport_https",
        "streamablehttp_client_transport_mtls",
    ],
)
def test_mcp_tool_can_be_executed_from_thread(client_transport_name, with_mcp_enabled, request):
    client_transport = request.getfixturevalue(client_transport_name)
    run_tool_can_be_executed_from_thread(client_transport)


def test_mcp_toolbox_properly_filters_tools(sse_client_transport, with_mcp_enabled):
    toolbox = MCPToolBox(
        client_transport=sse_client_transport,
        tool_filter=[
            "bwip_tool",
            Tool(
                name="zbuk_tool",
                description="something",
                input_descriptors=[
                    IntegerProperty(name="a"),
                    IntegerProperty(name="b"),
                ],
            ),
        ],
    )
    tools = toolbox.get_tools()  # need
    assert len(tools) == 2
    assert set(t.name for t in tools) == {"bwip_tool", "zbuk_tool"}


def test_unknown_tool_on_mcp_server(sse_client_transport, with_mcp_enabled):
    with pytest.raises(ValueError, match="Cannot find a tool named fooza on the MCP server"):
        tool = MCPTool(name="fooza", client_transport=sse_client_transport)


def test_auto_resolution_of_a_tool_description_and_output_descriptors(
    sse_client_transport, with_mcp_enabled
):
    tool = MCPTool(name="fooza_tool", client_transport=sse_client_transport)
    assert (
        tool.description
        == "Return the result of the fooza operation between numbers a and b. Do not use for anything else than computing a fooza operation."
    )
    assert tool.input_descriptors == [IntegerProperty(name="a"), IntegerProperty(name="b")]


def test_can_override_description_of_mcp_tool(sse_client_transport, with_mcp_enabled):
    tool = MCPTool(
        name="fooza_tool", description="custom description", client_transport=sse_client_transport
    )
    assert tool.description == "custom description"


def test_non_matching_input_descriptors_of_mcp_tools_log_it(
    sse_client_transport, with_mcp_enabled, caplog
):
    tool = MCPTool(
        name="fooza_tool",
        description="custom description",
        client_transport=sse_client_transport,
        input_descriptors=[],  # not the same input descriptors as the MCP server ones
    )
    assert (
        "The input descriptors exposed by the remote MCP server do not match the locally defined input descriptors"
        in caplog.text
    )


@pytest.fixture
def mcp_fooza_tool(sse_client_transport, with_mcp_enabled):
    return MCPTool(
        name="fooza_tool", description="custom description", client_transport=sse_client_transport
    )


def test_tool_execution_step_can_use_mcp_tool(mcp_fooza_tool):
    step = ToolExecutionStep(tool=mcp_fooza_tool)
    outputs = run_step_and_return_outputs(step, inputs={"a": 1, "b": 2})
    assert outputs == {"tool_output": "7"}


@retry_test(max_attempts=3)
def test_agent_can_use_mcp_tool(mcp_fooza_tool, remotely_hosted_llm):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-06-20
    Average success time:  1.03 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    agent = Agent(llm=remotely_hosted_llm, tools=[mcp_fooza_tool])
    conv = agent.start_conversation()
    conv.append_user_message("What is the result of fooza of 1 and 2?")
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    assert "7" in conv.get_last_message().content


@pytest.fixture
def mcp_fooza_toolbox(sse_client_transport, with_mcp_enabled):
    return MCPToolBox(client_transport=sse_client_transport)


MCP_USER_QUERY = "What is the result of fooza of 1 and 2?"


@retry_test(max_attempts=3)
def test_agent_can_use_mcp_toolbox(mcp_fooza_toolbox, remotely_hosted_llm):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-06-20
    Average success time:  1.09 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    agent = Agent(llm=remotely_hosted_llm, tools=[mcp_fooza_toolbox])
    conv = agent.start_conversation()
    conv.append_user_message(MCP_USER_QUERY)
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    assert "7" in conv.get_last_message().content


def test_mcp_tools_work_with_parallel_mapstep(mcp_fooza_toolbox):
    tools = mcp_fooza_toolbox.get_tools()

    mcp_tool_step = ToolExecutionStep(
        name="mcp_tool_step",
        tool=tools[0],
    )
    output_step = OutputMessageStep(
        name="output_step",
        message_template="Here is the answer:\n{{fooza_ans}}",
        input_mapping={"fooza_ans": ToolExecutionStep.TOOL_OUTPUT},
    )
    flow = Flow(
        begin_step=mcp_tool_step,
        control_flow_edges=[
            ControlFlowEdge(source_step=mcp_tool_step, destination_step=output_step),
            ControlFlowEdge(source_step=output_step, destination_step=None),
        ],
    )

    map_step = MapStep(
        name="map_step",
        flow=flow,
        unpack_input={
            "a": ".a",
            "b": ".b",
        },
        output_descriptors=[AnyProperty(name=OutputMessageStep.OUTPUT)],
        parallel_execution=True,
    )

    inputs = [{"a": 2, "b": 3}, {"a": 5, "b": 10}, {"a": 3, "b": 1}]
    assistant = create_single_step_flow(map_step, "step")
    conversation = assistant.start_conversation(inputs={MapStep.ITERATED_INPUT: inputs})
    status = conversation.execute()
    results = status.output_values["output_message"]
    assert len(results) == 3


def test_serde_mcp_tool(mcp_fooza_tool):
    serialized_tool = serialize(mcp_fooza_tool)
    deserialized_tool = autodeserialize(serialized_tool)
    assert isinstance(deserialized_tool, MCPTool)
    assert deserialized_tool.run(a=1, b=2) == "7"


def test_serde_mcp_toolbox(mcp_fooza_toolbox):
    serialized_toolbox = serialize(mcp_fooza_toolbox)
    deserialized_toolbox = autodeserialize(serialized_toolbox)
    assert isinstance(deserialized_toolbox, MCPToolBox)
    assert mcp_fooza_toolbox.get_tools() == deserialized_toolbox.get_tools()


def test_serde_agent_with_mcp_tool_and_toolbox(
    mcp_fooza_tool, mcp_fooza_toolbox, remotely_hosted_llm
):
    agent = Agent(llm=remotely_hosted_llm, tools=[mcp_fooza_tool, mcp_fooza_toolbox])
    serialized_agent = serialize(agent)
    deserialized_agent = autodeserialize(serialized_agent)
    assert isinstance(deserialized_agent, Agent)
    assert len(deserialized_agent.tools) == 2
    assert len(deserialized_agent._tools) == 1
    assert len(deserialized_agent._toolboxes) == 1
