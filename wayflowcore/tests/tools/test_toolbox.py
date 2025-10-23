# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass, field
from typing import Annotated, Any, Dict, List

from wayflowcore.agent import Agent
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.tools import Tool, ToolBox, tool

from ..testhelpers.testhelpers import retry_test


@tool
def fooza_tool(
    a: Annotated[int, "first required integer"], b: Annotated[int, "second required integer"]
) -> int:
    """Return the result of the fooza operation between numbers a and b. Do not use for anything else than computing a fooza operation."""
    return a * 2 + b * 3 - 1


@tool
def bwip_tool(
    a: Annotated[int, "first required integer"], b: Annotated[int, "second required integer"]
) -> int:
    """Return the result of the bwip operation between numbers a and b. Do not use for anything else than computing a bwip operation."""
    return a - b + 1


@tool
def zbuk_tool(
    a: Annotated[int, "first required integer"], b: Annotated[int, "second required integer"]
) -> int:
    """Return the result of the zbuk operation between numbers a and b. Do not use for anything else than computing a zbuk operation."""
    return a + b * 2


@dataclass
class BasicToolBox(ToolBox):
    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        raise NotImplementedError()

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        raise NotImplementedError()

    tools: List[Tool] = field(default_factory=list)

    def get_tools(self) -> List[Tool]:
        """Return the list of tools exposed by the ``ToolBox``"""
        return self.tools

    async def get_tools_async(self) -> List["Tool"]:
        return self.tools


def test_toolbox_can_be_instantiated_with_tools():
    BasicToolBox(tools=[fooza_tool, bwip_tool])


def _get_agent_with_tool_and_toolboxes(llm, tool_boxes: List[ToolBox]):
    return Agent(
        custom_instruction="You are an helpful assistant. Use the tools at your disposal to answer the user requests.",
        llm=llm,
        tools=[fooza_tool, *tool_boxes],
        agent_id="general_agent",
        name="general_agent",
        description="General agent that can call tools to answer some user requests",
    )


def test_toolboxes_can_be_passed_to_agents(remotely_hosted_llm):
    toolbox1 = BasicToolBox(tools=[zbuk_tool])
    toolbox2 = BasicToolBox(tools=[bwip_tool])

    _get_agent_with_tool_and_toolboxes(remotely_hosted_llm, [toolbox1, toolbox2])


@retry_test(max_attempts=3)
def test_agent_can_call_tool_from_toolboxes(remotely_hosted_llm):
    """
    Failure rate:          0 out of 30
    Observed on:           2025-06-16
    Average success time:  1.06 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000
    """
    toolbox1 = BasicToolBox(tools=[zbuk_tool])
    toolbox2 = BasicToolBox(tools=[bwip_tool])

    agent = _get_agent_with_tool_and_toolboxes(remotely_hosted_llm, [toolbox1, toolbox2])

    conv = agent.start_conversation()
    conv.append_user_message("compute the result the zbuk operation of 4 and 5")
    conv.execute()

    last_message = conv.get_last_message()
    assert last_message is not None
    assert "14" in last_message.content
