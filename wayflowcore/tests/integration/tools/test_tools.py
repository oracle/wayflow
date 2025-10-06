# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict, List, Literal, Optional, Union

import pytest

from wayflowcore.agent import Agent, _convert_described_flow_into_named_flow
from wayflowcore.executors.executionstatus import UserMessageRequestStatus
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.property import (
    AnyProperty,
    BooleanProperty,
    DictProperty,
    FloatProperty,
    IntegerProperty,
    ListProperty,
    NullProperty,
    StringProperty,
    UnionProperty,
)
from wayflowcore.steps import PromptExecutionStep, ToolExecutionStep
from wayflowcore.tools import ClientTool, DescribedFlow, ServerTool, Tool, tool
from wayflowcore.tools.toolhelpers import _to_react_template_dict

from ...testhelpers.testhelpers import retry_test


def _described_flow_to_tool(described_flow: DescribedFlow) -> Tool:
    flow = _convert_described_flow_into_named_flow(described_flow)

    return flow.as_client_tool()


def get_location(
    company_name: str,
    useless1: int = 0,
    useless2: float = 0.0,
    useless3: bool = False,
    useless4: List[str] = [],
    useless5: Dict[str, str] = {},
    useless6: Optional[
        str
    ] = None,  # BUG ON LANGCHAIN, Optional is not recognized as anyOf. TODO remove
    useless7: Union[int, float] = 0,
    useless8: Any = "no_default_langchain",  # BUG ON LANGCHAIN, langchain tool confuses no-default with none-default
) -> str:
    """
    Search the location of a given company
    """
    return "bern"


CLIENT_TOOL = ClientTool(
    name="get_location",
    description="Search the location of a given company",
    parameters={
        "company_name": {
            "type": "string",
            "description": "Name of the company to search the location for",
        },
        "useless1": {"type": "integer", "default": 0, "description": "this argument is unused"},
        "useless2": {"type": "number", "default": 0.0, "description": "this argument is unused"},
        "useless3": {"type": "boolean", "default": False, "description": "this argument is unused"},
        "useless4": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
            "description": "this argument is unused",
        },
        "useless5": {
            "type": "object",
            "default": {},
            "description": "this argument is unused",
            "additionalProperties": {"type": "string"},
        },
        "useless6": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None,
            "description": "this argument is unused",
        },
        "useless7": {
            "anyOf": [{"type": "integer"}, {"type": "number"}],
            "default": 0,
            "description": "this argument is unused",
        },
        "useless8": {"default": None, "description": "this argument is unused"},
    },
)


SERVER_SIDE_TOOL = ServerTool(
    name="get_location",
    description="Search the location of a given company",
    parameters={
        "company_name": {
            "type": "string",
            "description": "Name of the company to search the location for",
        },
        "useless1": {"type": "integer", "default": 0, "description": "this argument is unused"},
        "useless2": {"type": "number", "default": 0.0, "description": "this argument is unused"},
        "useless3": {"type": "boolean", "default": False, "description": "this argument is unused"},
        "useless4": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
            "description": "this argument is unused",
        },
        "useless5": {
            "type": "object",
            "default": {},
            "description": "this argument is unused",
            "additionalProperties": {"type": "string"},
        },
        "useless6": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None,
            "description": "this argument is unused",
        },
        "useless7": {
            "anyOf": [{"type": "integer"}, {"type": "number"}],
            "default": 0,
            "description": "this argument is unused",
        },
        "useless8": {"default": None, "description": "this argument is unused"},
    },
    func=lambda *args, **kwargs: "bern",
    output={"type": "string"},
)

SERVER_SIDE_TOOL_WITH_DESCRIPTORS = ServerTool(
    name="get_location",
    description="Search the location of a given company",
    input_descriptors=[
        StringProperty(
            name="company_name", description="Name of the company to search the location for"
        ),
        IntegerProperty(name="useless1", description="this argument is unused", default_value=0),
        FloatProperty(name="useless2", description="this argument is unused", default_value=0.0),
        BooleanProperty(
            name="useless3", description="this argument is unused", default_value=False
        ),
        ListProperty(
            name="useless4",
            description="this argument is unused",
            default_value=[],
            item_type=StringProperty(),
        ),
        DictProperty(
            name="useless5",
            description="this argument is unused",
            default_value={},
            value_type=StringProperty(),
        ),
        UnionProperty(
            name="useless6",
            description="this argument is unused",
            default_value=None,
            any_of=[StringProperty(), NullProperty()],
        ),
        UnionProperty(
            name="useless7",
            description="this argument is unused",
            default_value=0,
            any_of=[IntegerProperty(), FloatProperty()],
        ),
        AnyProperty(name="useless8", description="this argument is unused", default_value=None),
    ],
    output_descriptors=[StringProperty(name="tool_output")],
    func=lambda *args, **kwargs: "bern",
)


def check_get_location_tool_is_properly_formatted(
    tool: Tool, expected_num_args: int, expect_arg_description: bool = True
) -> None:
    assert tool.name == "get_location"
    assert tool.description == "Search the location of a given company"
    assert isinstance(tool.parameters, dict)
    assert len(tool.parameters) == expected_num_args
    for param_name, param in tool.parameters.items():
        assert "title" in param
        assert "type" not in param or param["type"] in [
            "boolean",
            "number",
            "integer",
            "string",
            "array",
            "object",
        ]
    assert "type" in tool.output and tool.output["type"] == "string"

    tool_openai_dict = tool.to_openai_format()
    assert "function" in tool_openai_dict

    tool_description_as_str = _to_react_template_dict(tool)["description"]
    assert "Search the location of a given company" in tool_description_as_str
    assert "- useless2: number (Optional, default=0.0)" in tool_description_as_str
    assert "- useless3: boolean (Optional, default=False)" in tool_description_as_str
    assert "- useless4: array (Optional, default=[])" in tool_description_as_str
    assert "- useless5: object (Optional, default={})" in tool_description_as_str
    assert (
        "- useless6: string | null (Optional, default=None)" in tool_description_as_str
        or "- useless6: string (Optional, default=None)"
        in tool_description_as_str  # due to bug in langchain, see above
    )
    assert "- useless7: integer | number (Optional, default=0)" in tool_description_as_str
    assert (
        "- useless8: Any (Optional, default=None)" in tool_description_as_str
        or "- useless8: Any (Optional, default=no_default_langchain)" in tool_description_as_str
        # due to bug in langchain, see above
    )
    if expect_arg_description:
        assert (
            "- company_name: string (Required) Name of the company to search the location for"
            in tool_description_as_str
        )
        assert (
            "- useless1: integer (Optional, default=0) this argument is unused"
            in tool_description_as_str
        )
    else:
        assert "- useless1: integer (Optional, default=0)" in tool_description_as_str
        assert "company_name: string (Required)" in tool_description_as_str


def test_server_tool_returns_proper_dicts() -> None:
    check_get_location_tool_is_properly_formatted(SERVER_SIDE_TOOL, expected_num_args=9)


def test_client_tool_returns_proper_dicts() -> None:
    check_get_location_tool_is_properly_formatted(CLIENT_TOOL, expected_num_args=9)


def test_server_tool_from_descriptors_returns_proper_dicts() -> None:
    check_get_location_tool_is_properly_formatted(
        SERVER_SIDE_TOOL_WITH_DESCRIPTORS, expected_num_args=9
    )


def test_tool_raises_if_several_input_descriptors_have_same_name():
    with pytest.raises(ValueError):
        ClientTool(
            name="",
            description="",
            input_descriptors=[
                StringProperty("input_1"),
                StringProperty("input_1"),
            ],
        )


def test_tool_doesnt_raise_if_several_output_descriptors_have_same_name():
    with pytest.raises(ValueError):
        ClientTool(
            name="",
            description="",
            input_descriptors=[],
            output_descriptors=[
                StringProperty("input_1"),
                StringProperty("input_1"),
            ],
        )


def test_invalid_param_type_raises_exception() -> None:
    with pytest.raises(TypeError):
        ClientTool(
            name="tool_with_invalid_param_type",
            description="tool with an invalid param type",
            parameters={"a": {"title": "A", "type": "not_a_real_type"}},
        )


def test_server_tool_cannot_be_defined_without_func() -> None:
    with pytest.raises(ValueError):
        ServerTool(
            name="name",
            description="description",
            parameters={},
            output={"type": "string"},
            func={},
        )


def test_flow_as_tool_input_without_default_value_is_required(
    remotely_hosted_llm: "VllmModel",
) -> None:
    # PromptExecutionStep's inputs are required

    flow = DescribedFlow(
        create_single_step_flow(PromptExecutionStep("{{my_flow_input}}", llm=remotely_hosted_llm)),
        name="my_flow",
        description="my description",
    )
    client_tool = _described_flow_to_tool(flow)

    assert len(client_tool.parameters) == 1
    assert "default" not in client_tool.parameters["my_flow_input"]


def test_flow_as_tool_input_with_default_value_is_not_required() -> None:
    # ToolExecutionStep's inputs depend on the tool's inputs

    @tool(description_mode="only_docstring")
    def my_tool(my_flow_input: str = "not required") -> str:
        """filler"""
        return my_flow_input

    flow = DescribedFlow(
        create_single_step_flow(ToolExecutionStep(my_tool)),
        name="my_flow",
        description="my description",
    )
    client_tool = _described_flow_to_tool(flow)

    assert len(client_tool.parameters) == 1
    assert "default" in client_tool.parameters["my_flow_input"]
    assert client_tool.parameters["my_flow_input"]["default"] == "not required"


def test_flow_as_tool_input_with_optional_default_value_is_not_required() -> None:
    @tool(description_mode="only_docstring")
    def my_tool(my_flow_input: Optional[str] = "") -> str:
        """filler"""
        return "dummy fake string"

    flow = DescribedFlow(
        create_single_step_flow(ToolExecutionStep(my_tool)),
        name="my_flow",
        description="my description",
    )
    client_tool = _described_flow_to_tool(flow)

    assert len(client_tool.parameters) == 1
    assert "default" in client_tool.parameters["my_flow_input"]
    assert client_tool.parameters["my_flow_input"]["default"] == ""


def test_flow_as_tool_inputs_are_typed(remotely_hosted_llm: "VllmModel") -> None:
    from typing import List

    from wayflowcore.flow import Flow

    @tool(description_mode="only_docstring")
    def my_tool(my_non_str_input: List[int]) -> str:
        """filler"""
        return "dummy fake string"

    flow = DescribedFlow(
        flow=Flow.from_steps(
            steps=[
                PromptExecutionStep(
                    "{{my_flow_input_0}} {{my_flow_input_1}}", llm=remotely_hosted_llm
                ),
                ToolExecutionStep(my_tool),
            ],
            step_names=["prompt_step", "tool_step"],
        ),
        name="my_flow",
        description="my description",
    )
    client_tool = _described_flow_to_tool(flow)

    assert len(client_tool.parameters) == 3
    for i in range(2):
        input_name = f"my_flow_input_{i}"
        assert "type" in client_tool.parameters[input_name]
        assert client_tool.parameters[input_name]["type"] == "string"

    input_name = "my_non_str_input"
    assert "type" in client_tool.parameters[input_name]
    assert client_tool.parameters[input_name]["type"] == "array"


@retry_test(max_attempts=3)
def test_llm_can_use_tool_with_enum_param(remotely_hosted_llm):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-09-17
    Average success time:  0.97 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """

    @tool(description_mode="only_docstring")
    def generate_name(size: Literal["SHORT", "LONG"]) -> str:
        """generate a name"""
        if size == "SHORT":
            return "Jo"
        elif size == "LONG":
            return "Bartholomew"
        raise ValueError(f"Not supported")

    agent = Agent(llm=remotely_hosted_llm, tools=[generate_name])
    conv = agent.start_conversation()
    conv.append_user_message("generate a name with few letters using your tool")
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    assert "jo" in conv.get_last_message().content.lower()
