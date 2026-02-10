# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import re
from typing import List, Tuple, cast

import anyio
import pytest
from anyio import to_thread

from wayflowcore import Agent, Flow
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import (
    ToolExecutionConfirmationStatus,
    UserMessageRequestStatus,
)
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
from wayflowcore.property import (
    AnyProperty,
    BooleanProperty,
    DictProperty,
    IntegerProperty,
    ListProperty,
    NullProperty,
    StringProperty,
    UnionProperty,
)
from wayflowcore.serialization import autodeserialize, serialize
from wayflowcore.steps import MapStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.tools import Tool
from wayflowcore.tools.tools import ToolRequest

from ..testhelpers.patching import patch_llm
from ..testhelpers.testhelpers import retry_test


def test_mcp_without_auth_raises_without_explicit_user_confirmation() -> None:
    with pytest.raises(
        ValueError,
        match="Using MCP servers without proper authentication is highly discouraged",
    ):
        _ = MCPToolBox(client_transport=SSETransport(url="anything"))


def test_mcp_client_transport_headers_and_sensitive_headers_cannot_overlap(sse_mcp_server_http):
    with pytest.raises(
        ValueError,
        match="Some headers have been specified in both `headers` and `sensitive_headers`",
    ):
        _ = SSETransport(
            url=sse_mcp_server_http,
            headers={"exclusive_key_1": "value", "shared_key": 1},
            sensitive_headers={"exclusive_key_2": "value", "shared_key": 1},
        )


@pytest.fixture
def sse_client_transport(sse_mcp_server_http):
    return SSETransport(url=sse_mcp_server_http)


@pytest.fixture
def sse_client_transport_with_headers(sse_mcp_server_http):
    return SSETransport(
        url=sse_mcp_server_http,
        headers={"custom-header": "value"},
        sensitive_headers={"sensitive-header": "abc123"},
    )


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
    assert len(tools) == 13
    mcp_tool = next(t for t in tools if t.name == "fooza_tool")
    assert mcp_tool.run(a=1, b=2) == "7"
    assert mcp_tool.input_descriptors == [IntegerProperty(name="a"), IntegerProperty(name="b")]


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


@pytest.fixture
def mcp_fooza_tool_with_client_with_headers(sse_client_transport_with_headers, with_mcp_enabled):
    return MCPTool(
        name="fooza_tool",
        description="custom description",
        client_transport=sse_client_transport_with_headers,
    )


@pytest.fixture
def mcp_fooza_tool_confirm(sse_client_transport, with_mcp_enabled):
    return MCPTool(
        name="fooza_tool",
        description="custom description",
        client_transport=sse_client_transport,
        requires_confirmation=True,
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


@retry_test(max_attempts=3)
def test_agent_can_use_mcp_tool_with_confirmation(mcp_fooza_tool_confirm, remotely_hosted_llm):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-23
    Average success time:  1.01 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    agent = Agent(llm=remotely_hosted_llm, tools=[mcp_fooza_tool_confirm])
    conv = agent.start_conversation()
    conv.append_user_message("What is the result of fooza of 1 and 2?")
    status = conv.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    status.confirm_tool_execution(tool_request=status.tool_requests[0])
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


def _get_agent_with_mcp_toolboxes(llm, tool_boxes: List["MCPToolBox"]):
    return Agent(
        custom_instruction="You are an helpful assistant. Use the tools at your disposal to answer the user requests.",
        llm=llm,
        tools=tool_boxes,
        agent_id="general_agent",
        name="general_agent",
        description="General agent that can call tools to answer some user requests",
    )


@retry_test(max_attempts=3)
@pytest.mark.parametrize(
    "tool_name, requires_confirmation, answer",
    [
        ("ggwp_tool", True, "6"),
        ("ggwp_tool", False, "6"),
        ("ggwp_tool", None, "6"),
        ("zbuk_tool", True, "14"),
    ],
)
def test_agent_can_call_tool_with_confirmation_from_mcptoolboxes(
    tool_name,
    requires_confirmation,
    answer,
    sse_client_transport,
    with_mcp_enabled,
    remotely_hosted_llm,
):
    """
    Failure rate:          0 out of 30
    Observed on:           2026-01-13
    Average success time:  1.06 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000
    """
    if tool_name == "ggwp_tool":
        filter_entry = Tool(
            name="ggwp_tool",
            description="Return the result of the ggwp operation between numbers a and b. Do not use for anything else than computing a ggwp operation.",
            input_descriptors=[IntegerProperty(name="a"), IntegerProperty(name="b")],
            requires_confirmation=True,
        )
    else:
        filter_entry = tool_name

    toolbox = MCPToolBox(
        client_transport=sse_client_transport,
        tool_filter=[filter_entry],
        requires_confirmation=requires_confirmation,
    )

    agent = _get_agent_with_mcp_toolboxes(remotely_hosted_llm, [toolbox])

    conv = agent.start_conversation()
    conv.append_user_message(f"compute the result the {tool_name} operation of 4 and 5")
    status = conv.execute()

    assert isinstance(status, ToolExecutionConfirmationStatus)
    status.confirm_tool_execution(status.tool_requests[0])
    status = conv.execute()
    assert not isinstance(status, ToolExecutionConfirmationStatus)

    last_message = conv.get_last_message()
    assert last_message is not None
    assert answer in last_message.content


@retry_test(max_attempts=3)
@pytest.mark.parametrize(
    "tool_name, requires_confirmation, answer",
    [("zbuk_tool", False, "14"), ("zbuk_tool", None, "14")],
)
def test_agent_can_call_tool_without_confirmation_from_mcptoolboxes(
    tool_name,
    requires_confirmation,
    answer,
    sse_client_transport,
    with_mcp_enabled,
    remotely_hosted_llm,
):
    """
    Failure rate:          0 out of 30
    Observed on:           2026-01-13
    Average success time:  1.05 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000
    """

    ggwp_tool_entry = Tool(
        name="ggwp_tool",
        description="Return the result of the ggwp operation between numbers a and b. Do not use for anything else than computing a ggwp operation.",
        input_descriptors=[IntegerProperty(name="a"), IntegerProperty(name="b")],
        requires_confirmation=True,
    )

    # ggwp_tool requires confirmation, zbuk_tool does not
    toolbox = MCPToolBox(
        client_transport=sse_client_transport,
        tool_filter=[tool_name, ggwp_tool_entry],
        requires_confirmation=requires_confirmation,
    )  # Should only call tool and not ggwp

    agent = _get_agent_with_mcp_toolboxes(remotely_hosted_llm, [toolbox])

    conv = agent.start_conversation()
    conv.append_user_message(f"compute the result the {tool_name} operation of 4 and 5")
    status = conv.execute()
    assert not isinstance(status, ToolExecutionConfirmationStatus)

    last_message = conv.get_last_message()
    assert last_message is not None
    assert answer in last_message.content


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


def test_serde_mcp_tool_with_client_with_headers(mcp_fooza_tool_with_client_with_headers):
    serialized_tool = serialize(mcp_fooza_tool_with_client_with_headers)
    assert "headers" in serialized_tool
    assert "sensitive_headers" not in serialized_tool
    deserialized_tool = autodeserialize(serialized_tool)
    assert isinstance(deserialized_tool, MCPTool)
    assert isinstance(deserialized_tool.client_transport, SSETransport)
    assert type(mcp_fooza_tool_with_client_with_headers.client_transport) is type(
        deserialized_tool.client_transport
    )
    assert (
        deserialized_tool.client_transport.headers
        == mcp_fooza_tool_with_client_with_headers.client_transport.headers
    )
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


def get_simple_mcp_agent_and_message_pattern(
    mcp_fooza_toolbox: MCPToolBox, remotely_hosted_llm
) -> Tuple[Agent, str]:
    agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction=(
            "Use the tool to generate a random string and return its result along "
            "with the list of available tools."
        ),
        initial_message=None,
        tools=[mcp_fooza_toolbox],
    )
    short_url = re.findall(
        r"(https?://.*?)/sse", cast(SSETransport, mcp_fooza_toolbox.client_transport).url
    )[0]
    message_pattern = short_url + r'/messages/\?session_id=(.*?) "HTTP'
    return agent, message_pattern


def test_connection_persistence_with_agent_and_mcp_toolbox(
    caplog: pytest.LogCaptureFixture, mcp_fooza_toolbox, remotely_hosted_llm
) -> None:
    agent, message_pattern = get_simple_mcp_agent_and_message_pattern(
        mcp_fooza_toolbox, remotely_hosted_llm
    )
    logger = logging.getLogger("httpx")
    logger.propagate = True  # necessary so that the caplog handler can capture logging messages
    logger.setLevel(logging.INFO)
    caplog.set_level(logging.INFO)
    # ^ setting pytest to capture log messages of level INFO or above

    with patch_llm(
        llm=remotely_hosted_llm,
        outputs=[
            [ToolRequest(name="generate_random_string", args={})],
            [ToolRequest(name="generate_random_string", args={})],
            "random string is ...",
        ],
    ):
        conv = agent.start_conversation()
        _ = conv.execute()

    all_session_ids = re.findall(message_pattern, caplog.text)
    assert len(set(all_session_ids)) == 1


@pytest.mark.anyio
async def test_connection_persistence_with_agent_and_mcp_toolbox_async(
    caplog: pytest.LogCaptureFixture, mcp_fooza_toolbox, remotely_hosted_llm
) -> None:
    agent, message_pattern = get_simple_mcp_agent_and_message_pattern(
        mcp_fooza_toolbox, remotely_hosted_llm
    )
    logger = logging.getLogger("httpx")
    logger.propagate = True  # necessary so that the caplog handler can capture logging messages
    logger.setLevel(logging.INFO)
    caplog.set_level(logging.INFO)
    # ^ setting pytest to capture log messages of level INFO or above

    with patch_llm(
        llm=remotely_hosted_llm,
        outputs=[
            [ToolRequest(name="generate_random_string", args={})],
            [ToolRequest(name="generate_random_string", args={})],
            "random string is ...",
        ],
    ):
        conv = agent.start_conversation()
        _ = await conv.execute_async()

    all_session_ids = re.findall(message_pattern, caplog.text)
    assert len(set(all_session_ids)) == 1


def get_simple_mcp_flow_and_message_pattern(mcp_fooza_tool: MCPTool) -> Tuple[Flow, str]:
    flow = Flow.from_steps(
        [
            ToolExecutionStep(
                name=f"tool_step_{i}",
                tool=mcp_fooza_tool,
                raise_exceptions=True,
            )
            for i in range(2)
        ]
    )
    short_url = re.findall(
        r"(https?://.*?)/sse", cast(SSETransport, mcp_fooza_tool.client_transport).url
    )[0]
    message_pattern = short_url + r'/messages/\?session_id=(.*?) "HTTP'
    return flow, message_pattern


def test_connection_persistence_with_flow_and_mcp_tool(
    caplog: pytest.LogCaptureFixture, mcp_fooza_tool
) -> None:
    flow, message_pattern = get_simple_mcp_flow_and_message_pattern(mcp_fooza_tool)
    logger = logging.getLogger("httpx")
    logger.propagate = True  # necessary so that the caplog handler can capture logging messages
    logger.setLevel(logging.INFO)
    caplog.set_level(logging.INFO)
    # ^ setting pytest to capture log messages of level INFO or above

    conv = flow.start_conversation(inputs={"a": 1, "b": 1})
    _ = conv.execute()

    all_session_ids = re.findall(message_pattern, caplog.text)
    assert len(set(all_session_ids)) == 1
    # ^ note: There is actually one more for the initial fetch (no conversation) but it is not captured here


@pytest.mark.anyio
async def test_connection_persistence_with_flow_and_mcp_tool_async(
    caplog: pytest.LogCaptureFixture,
    mcp_fooza_tool,
) -> None:
    flow, message_pattern = get_simple_mcp_flow_and_message_pattern(mcp_fooza_tool)
    logger = logging.getLogger("httpx")
    logger.propagate = True  # necessary so that the caplog handler can capture logging messages
    logger.setLevel(logging.INFO)
    caplog.set_level(logging.INFO)
    # ^ setting pytest to capture log messages of level INFO or above

    conv = flow.start_conversation(inputs={"a": 1, "b": 1})
    _ = await conv.execute_async()

    all_session_ids = re.findall(message_pattern, caplog.text)
    assert len(set(all_session_ids)) == 1
    # ^ note: There is actually one more for the initial fetch (no conversation) but it is not captured here


def test_mcp_tool_works_with_complex_output_type(sse_client_transport, with_mcp_enabled):
    tool = MCPTool(
        name="generate_complex_type",
        description="description",
        client_transport=sse_client_transport,
    )
    TOOL_OUTPUT_NAME = "generate_complex_typeOutput"
    assert tool.output_descriptors == [ListProperty(name=TOOL_OUTPUT_NAME)]
    step = ToolExecutionStep(tool=tool)
    outputs = run_step_and_return_outputs(step)
    assert TOOL_OUTPUT_NAME in outputs and outputs[TOOL_OUTPUT_NAME] == ["value1", "value2"]


def test_mcp_tool_works_with_dict_output(sse_client_transport, with_mcp_enabled):
    tool = MCPTool(
        name="generate_dict",
        description="description",
        client_transport=sse_client_transport,
        output_descriptors=[DictProperty(name="tool_output")],
    )
    step = ToolExecutionStep(tool=tool)
    outputs = run_step_and_return_outputs(step)
    assert "tool_output" in outputs and outputs["tool_output"] == {"key": "value"}


def test_mcp_tool_works_with_list_output(sse_client_transport, with_mcp_enabled):
    tool = MCPTool(
        name="generate_list",
        description="description",
        client_transport=sse_client_transport,
        output_descriptors=[ListProperty(name="tool_output")],
    )
    step = ToolExecutionStep(tool=tool)
    outputs = run_step_and_return_outputs(step)
    assert "tool_output" in outputs and outputs["tool_output"] == ["value1", "value2"]


def test_mcp_tool_works_with_tuple_output(sse_client_transport, with_mcp_enabled):
    tool = MCPTool(
        name="generate_tuple",
        description="description",
        client_transport=sse_client_transport,
        output_descriptors=[StringProperty(name="str_output"), BooleanProperty(name="bool_output")],
    )
    step = ToolExecutionStep(tool=tool)
    outputs = run_step_and_return_outputs(step)

    assert (
        "str_output" in outputs
        and outputs["str_output"] == "value"
        and "bool_output" in outputs
        and outputs["bool_output"] is True
    )


def test_mcp_tool_works_with_nested_inputs(sse_client_transport, with_mcp_enabled):
    tool = MCPTool(
        name="consumes_list_and_dict",
        description="description",
        client_transport=sse_client_transport,
        input_descriptors=[ListProperty(name="vals"), DictProperty(name="props")],
        output_descriptors=[StringProperty(name="tool_output")],
    )
    step = ToolExecutionStep(tool=tool)
    outputs = run_step_and_return_outputs(
        step, inputs={"vals": ["value1", "value2"], "props": {"key": "value"}}
    )
    assert (
        "tool_output" in outputs
        and outputs["tool_output"] == "vals=['value1', 'value2'], props={'key': 'value'}"
    )


def test_mcp_tool_works_resource_output(sse_client_transport, with_mcp_enabled):
    tool = MCPTool(
        name="get_resource",
        description="description",
        client_transport=sse_client_transport,
    )
    assert len(tool.output_descriptors) == 1
    assert isinstance(tool.output_descriptors[0], StringProperty)
    assert "user_34_response" in tool.run(user="user_34")


def test_mcp_tool_works_with_optional_output(sse_client_transport, with_mcp_enabled):
    tool = MCPTool(
        name="generate_optional",
        description="description",
        client_transport=sse_client_transport,
    )
    # The output descriptor should be a union string|null named after the tool title
    TOOL_OUTPUT_NAME = "tool_output"

    assert len(tool.output_descriptors) == 1
    desc0 = tool.output_descriptors[0]
    assert desc0.name == TOOL_OUTPUT_NAME
    assert isinstance(desc0, UnionProperty)
    assert len(desc0.any_of) == 2
    # Union must include string and null
    assert {type(p) for p in desc0.any_of} == {StringProperty, NullProperty}
    # Execute and ensure the result is surfaced
    step = ToolExecutionStep(tool=tool)
    outputs = run_step_and_return_outputs(step)
    assert TOOL_OUTPUT_NAME in outputs and outputs[TOOL_OUTPUT_NAME] == "maybe"


def test_mcp_tool_works_with_union_output(sse_client_transport, with_mcp_enabled):
    tool = MCPTool(
        name="generate_union",
        description="description",
        client_transport=sse_client_transport,
    )
    TOOL_OUTPUT_NAME = "tool_output"

    assert len(tool.output_descriptors) == 1
    desc0 = tool.output_descriptors[0]
    assert desc0.name == TOOL_OUTPUT_NAME
    assert isinstance(desc0, UnionProperty)
    assert len(desc0.any_of) == 2
    assert {type(p) for p in desc0.any_of} == {StringProperty, IntegerProperty}

    step = ToolExecutionStep(tool=tool)
    outputs = run_step_and_return_outputs(step)
    assert TOOL_OUTPUT_NAME in outputs and outputs[TOOL_OUTPUT_NAME] == "maybe"


def test_mcp_output_schema_supports_optional_string_union():
    from wayflowcore.mcp.mcphelpers import _try_convert_mcp_output_schema_to_properties
    from wayflowcore.property import NullProperty, StringProperty, UnionProperty

    # Simulate an MCP tool output schema where the `result` is Optional[str]
    schema = {
        "type": "object",
        "properties": {
            "result": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "null"},
                ]
            }
        },
        "required": ["result"],
        # some servers add this hint when wrapping primitives in {"result": ...}
        "x-fastmcp-wrap-result": True,
    }

    props = _try_convert_mcp_output_schema_to_properties(
        schema=schema, tool_title="OptionalStringOutput"
    )

    # Expect proper parsing into a single Union[String, Null] property
    assert props is not None and len(props) == 1
    assert isinstance(props[0], UnionProperty)
    any_of = props[0].any_of
    assert any(isinstance(p, StringProperty) for p in any_of)
    assert any(isinstance(p, NullProperty) for p in any_of)
