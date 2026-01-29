# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import re
from typing import Annotated, Optional

import pytest

from wayflowcore.agent import Agent
from wayflowcore.flow import Flow
from wayflowcore.property import IntegerProperty, NullProperty, StringProperty, UnionProperty
from wayflowcore.serialization import autodeserialize, deserialize, serialize
from wayflowcore.serialization.context import DeserializationContext
from wayflowcore.steps.toolexecutionstep import ToolExecutionStep
from wayflowcore.tools import ClientTool, RemoteTool, ServerTool, Tool, tool


@pytest.fixture
def example_client_tool() -> ClientTool:
    return ClientTool(
        name="get_weather",
        description="Return the weather of the day for a given city",
        parameters={
            "city": {
                "description": "The city to request the weather for",
                "type": "string",
                "default": "Zurich",
            }
        },
        output={"type": "array"},
    )


def test_client_tool_can_be_serialized(example_client_tool) -> None:
    serialized_client_tool = serialize(example_client_tool)
    assert "tool_type: client" in serialized_client_tool
    assert "name: get_weather" in serialized_client_tool
    assert "title: city" in serialized_client_tool
    assert "description: The city to request the weather for" in serialized_client_tool
    assert "type: array" in serialized_client_tool


def test_client_tool_with_no_parameters_can_be_serialized() -> None:
    client_tool = ClientTool(
        name="get_weather_def",
        description="none",
        parameters={},
    )
    serialized_client_tool = serialize(client_tool)
    assert "tool_type: client" in serialized_client_tool
    assert "name: get_weather_def" in serialized_client_tool
    assert "input_descriptors: []" in serialized_client_tool


def test_client_tool_can_be_ser_deser_then_ser(example_client_tool) -> None:
    first_serialized_client_tool = serialize(example_client_tool)
    second_serialized_client_tool = serialize(deserialize(Tool, first_serialized_client_tool))
    assert first_serialized_client_tool == second_serialized_client_tool


def test_client_tool_can_be_ser_autodeser_then_ser(example_client_tool) -> None:
    first_serialized_client_tool = serialize(example_client_tool)
    second_serialized_client_tool = serialize(autodeserialize(first_serialized_client_tool))
    assert first_serialized_client_tool == second_serialized_client_tool


@pytest.fixture
def example_server_tool() -> ServerTool:
    @tool(description_mode="only_docstring")
    def qwerz_operation() -> str:
        "computes and return the result of the qwerz operation"
        return "Result: qqwweerrzz"

    return qwerz_operation


@pytest.fixture
def deserialization_context_with_server_tool(example_server_tool) -> DeserializationContext:
    deserialization_context = DeserializationContext()
    deserialization_context.registered_tools[example_server_tool.name] = example_server_tool
    return deserialization_context


@pytest.fixture
def example_agent(example_server_tool, example_client_tool, remotely_hosted_llm) -> Agent:
    return Agent(
        llm=remotely_hosted_llm,
        tools=[example_server_tool, example_client_tool],
    )


def test_client_tools_are_properly_serialized_in_a_agent(
    example_agent,
) -> None:
    serialized_assistant = serialize(example_agent)
    assert "tool_type: client" in serialized_assistant
    assert "name: get_weather" in serialized_assistant
    assert "qwerz_operation" in serialized_assistant


def test_agent_with_client_tools_can_be_ser_deser_then_ser(
    example_server_tool, example_agent, deserialization_context_with_server_tool
) -> None:
    first_serialized_assistant = serialize(example_agent)
    second_serialized_assistant = serialize(
        deserialize(Agent, first_serialized_assistant, deserialization_context_with_server_tool)
    )

    # We remove digits for this assertion because id of python object appearing h=in the references
    # of the serialization will have changed between the two serializations.
    assert re.sub(r"[0-9]+", "", first_serialized_assistant) == re.sub(
        r"[0-9]+", "", second_serialized_assistant
    )


def test_serialization_of_client_tools_in_flow(
    example_client_tool, example_server_tool, deserialization_context_with_server_tool
) -> None:
    flow = Flow.from_steps(
        steps=[
            ToolExecutionStep(example_client_tool),
            ToolExecutionStep(example_server_tool),
        ],
        step_names=["client_tool_execution", "server_tool_execution"],
    )
    new_flow = deserialize(Flow, serialize(flow), deserialization_context_with_server_tool)
    assert (
        new_flow.steps["client_tool_execution"].tool is not flow.steps["client_tool_execution"].tool
    )
    assert new_flow.steps["client_tool_execution"].tool == flow.steps["client_tool_execution"].tool
    assert new_flow.steps["client_tool_execution"].id == flow.steps["client_tool_execution"].id


def test_server_tool_serialization_contain_metadata_info():
    server_tool = ServerTool(
        name="read_wiki_page",
        description="Allows to read a page on Wikipedia",
        parameters={
            "title": {"type": "string", "description": "The title of the page to be read."}
        },
        output={"type": "string", "description": "The content of a wikipedia page as a string"},
        __metadata_info__={"x": 1357, "y": 2468},
        func=lambda title: f"Page {title} does not exist.",
    )
    serialized_server_tool = serialize(server_tool)
    assert "1357" in serialized_server_tool and "2468" in serialized_server_tool


@pytest.mark.parametrize(
    "override_tool_args",
    [
        {"name": "wrong_name"},
        {"description": "wrong description"},
        {"parameters": {"wrong_param": {"type": "string", "description": ""}}},
        {
            "parameters": {
                "title": {"type": "number", "description": "The title of the page to be read."}
            }
        },
        {"output": {"type": "number", "description": ""}},
    ],
)
def test_server_tool_deserialization_fails_on_wrong_registration(override_tool_args):
    tool_args = dict(
        name="read_wiki_page",
        description="Allows to read a page on Wikipedia",
        parameters={
            "title": {"type": "string", "description": "The title of the page to be read."}
        },
        output={"type": "string", "description": "The content of a wikipedia page as a string"},
        __metadata_info__={"x": 1357, "y": 2468},
        func=lambda title: f"Page {title} does not exist.",
    )
    server_tool = ServerTool(**tool_args)
    serialized_server_tool = serialize(server_tool)
    registered_tool = ServerTool(**{**tool_args, **override_tool_args})
    deserialization_context = DeserializationContext()
    deserialization_context.registered_tools["read_wiki_page"] = registered_tool
    with pytest.raises(
        ValueError, match="Information of the registered tool does not match the serialization"
    ):
        deserialize(Tool, serialized_server_tool, deserialization_context)


def test_server_tool_deserialization_succeeds_on_correct_registration():
    tool_args = dict(
        name="read_wiki_page",
        description="Allows to read a page on Wikipedia",
        parameters={
            "title": {"type": "string", "description": "The title of the page to be read."}
        },
        output={"type": "string", "description": "The content of a wikipedia page as a string"},
        __metadata_info__={"x": 1357, "y": 2468},
        func=lambda title: f"Page {title} does not exist.",
    )
    server_tool = ServerTool(**tool_args)
    serialized_server_tool = serialize(server_tool)
    registered_tool = ServerTool(**tool_args)
    deserialization_context = DeserializationContext()
    deserialization_context.registered_tools["read_wiki_page"] = registered_tool
    deserialized_tool = deserialize(Tool, serialized_server_tool, deserialization_context)
    assert isinstance(deserialized_tool, ServerTool)


@pytest.fixture
def remote_tool() -> Tool:
    return RemoteTool(
        name="my_api",
        description="some endpoint",
        url="http://my-remote-api",
        method="POST",
        data="something".encode("utf-8"),
        params=[("what", "is")],
        headers={
            "Content-type": "application/json",
            "Custom-header": "{{hello}}",
        },
        sensitive_headers={"Authentication": "Bearer: abc123"},
        ignore_bad_http_requests=True,
        num_retry_on_bad_http_request=4,
        input_descriptors=[StringProperty(name="hello")],
        output_descriptors=[StringProperty(name="output")],
        allow_insecure_http=True,
        url_allow_list=["http://fishy-endpoint.com"],
    )


def test_remote_tool_can_be_serialized(remote_tool):
    serialized_tool = serialize(remote_tool)
    assert "my_api" in serialized_tool
    assert "POST" in serialized_tool
    assert "sensitive_headers" not in serialized_tool


def test_remote_tool_can_be_serialized_and_deserialized(remote_tool):
    serialized_tool = serialize(remote_tool)
    deserialized_tool = autodeserialize(serialized_tool)
    assert isinstance(deserialized_tool, RemoteTool)
    # Need to reset sensitive_headers before comparison, as those are not exported
    remote_tool.sensitive_headers = None
    assert remote_tool == deserialized_tool


def test_serialize_agent_with_remote_tools(remotely_hosted_llm, remote_tool):
    agent = Agent(llm=remotely_hosted_llm, tools=[remote_tool])
    serialize_agent = serialize(agent)
    deserialized_agent = autodeserialize(serialize_agent)
    assert isinstance(deserialized_agent, Agent)
    assert len(deserialized_agent.tools) == 1
    assert isinstance(deserialized_agent.tools[0], RemoteTool)


def test_deserialize_tool_with_none_default():
    @tool
    def my_tool(param1: Annotated[Optional[int], "param desc"] = None) -> str:
        """Tool desc"""
        return ""

    assistant = Flow.from_steps([ToolExecutionStep(my_tool)], step_names=["tool_step"])
    serialized_assistant = serialize(assistant)
    deserialization_context = DeserializationContext()
    deserialization_context.registered_tools[my_tool.name] = my_tool
    deserialized_assistant = autodeserialize(serialized_assistant, deserialization_context)
    t = deserialized_assistant.steps["tool_step"].tool
    assert t.name == "my_tool"
    assert t.input_descriptors[0] == UnionProperty(
        any_of=[IntegerProperty(), NullProperty()],
        name="param1",
        description="param desc",
        default_value=None,
    )
