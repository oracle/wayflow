# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import os
from pathlib import Path
from typing import List, Optional

import pytest

from wayflowcore.agent import Agent
from wayflowcore.contextproviders import ChatHistoryContextProvider
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.flow import Flow
from wayflowcore.models import LlmModel
from wayflowcore.property import StringProperty
from wayflowcore.serialization import autodeserialize, deserialize, serialize
from wayflowcore.serialization.context import DeserializationContext
from wayflowcore.steps import InputMessageStep, OutputMessageStep
from wayflowcore.tools import DescribedFlow, Tool, register_server_tool, tool

CONFIGS_DIR = Path(os.path.dirname(__file__)).parent / "configs"


def add_numbers(a: int, b: int) -> int:
    """adds the two numbers"""
    return a + b


add_number_tool = tool(add_numbers, description_mode="only_docstring")


def create_flow():
    step_a = OutputMessageStep(message_template="Hello!")
    step_b = OutputMessageStep(message_template="How")
    step_c = OutputMessageStep(message_template="are")
    step_d = InputMessageStep(message_template="you?")
    return Flow(
        begin_step_name="STEP_A",
        steps={
            "STEP_A": step_a,
            "STEP_B": step_b,
            "STEP_C": step_c,
            "STEP_D": step_d,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=step_a, destination_step=step_b),
            ControlFlowEdge(source_step=step_b, destination_step=step_c),
            ControlFlowEdge(source_step=step_c, destination_step=step_d),
            ControlFlowEdge(source_step=step_d, destination_step=None),
        ],
    )


@pytest.fixture
def flow():
    assistant = create_flow()
    assistant.__metadata_info__ = {"ui_name": "my_custom_flow"}
    return assistant


@pytest.fixture
def agent(remotely_hosted_llm):
    return create_agent(
        remotely_hosted_llm,
        [add_number_tool],
        [DescribedFlow(name="flow1", description="some flow", flow=create_flow())],
    )


def create_agent(
    llm: LlmModel, tools: Optional[List[Tool]] = None, flows: Optional[List[DescribedFlow]] = None
) -> Agent:
    return Agent(
        llm=llm,
        tools=tools,
        flows=flows,
        agents=None,  # TODO not supported yet
        custom_instruction="Some custom instruction {{ some_context }}",
        max_iterations=99,
        context_providers=[
            ChatHistoryContextProvider(
                output_template="some random context", output_name="some_context"
            )
        ],
        can_finish_conversation=True,
        output_descriptors=[StringProperty(name="agent_output", description="d", default_value="")],
        __metadata_info__={"ui_name": "my_custom_flex_assistant"},
    )


def test_can_serialize_simple_flow(flow: Flow) -> None:
    serialized_assistant = serialize(flow)
    assert isinstance(serialized_assistant, str)
    assert serialized_assistant.count("_component_type: Flow") == 1
    assert serialized_assistant.count(" Flow") == 1
    assert serialized_assistant.count(" Step") == 5
    assert "InputMessageStep" in serialized_assistant
    assert "you?" in serialized_assistant
    assert "my_custom_flow" in serialized_assistant


def _check_deserialized_flow_validity(old_flow: Flow, new_flow: Flow):
    assert isinstance(new_flow, Flow)
    assert set(new_flow.steps) == set(old_flow.steps)
    assert new_flow.__metadata_info__ == old_flow.__metadata_info__


def test_can_deserialize_a_serialized_flow(flow: Flow) -> None:
    new_assistant = deserialize(Flow, serialize(flow))
    _check_deserialized_flow_validity(flow, new_assistant)


def test_can_autodeserialize_a_serialized_flow(flow: Flow) -> None:
    new_assistant = autodeserialize(serialize(flow))
    _check_deserialized_flow_validity(flow, new_assistant)


def test_can_serialize_simple_agent(agent: Agent) -> None:
    serialized_assistant = serialize(agent)
    assert isinstance(serialized_assistant, str)
    assert serialized_assistant.count("_component_type: Agent") == 1
    assert (
        serialized_assistant.count("tools:") == 1 + 2
    )  # 2 mentions of tool in the template serialization
    assert serialized_assistant.count(" Flow") == 1
    assert serialized_assistant.count(" Step") == 5
    assert serialized_assistant.count("max_iterations: 99") == 1
    assert "InputMessageStep" in serialized_assistant
    assert "you?" in serialized_assistant
    assert "my_custom_flex_assistant" in serialized_assistant
    assert "agent_output" in serialized_assistant


def _check_deserialized_agent_validity(old_agent: Agent, new_agent: Agent):
    assert isinstance(new_agent, Agent)
    assert set([t.name for t in new_agent.tools]) == set([t.name for t in old_agent.tools])
    assert new_agent.agents == old_agent.agents
    assert len(new_agent.flows) == len(old_agent.flows) == 1
    assert set(new_agent.flows[0].steps) == set(old_agent.flows[0].steps)
    assert set(new_agent.flows[0].description) == set(old_agent.flows[0].description)
    assert set(new_agent.flows[0].name) == set(old_agent.flows[0].name)
    assert new_agent.custom_instruction == old_agent.custom_instruction
    assert new_agent.max_iterations == old_agent.max_iterations
    assert (
        next(iter(new_agent.context_providers)).output_template
        == next(iter(old_agent.context_providers)).output_template
    )
    assert new_agent.can_finish_conversation == old_agent.can_finish_conversation
    assert new_agent.caller_input_mode == old_agent.caller_input_mode
    assert set(new_agent.output_descriptors) == set(old_agent.output_descriptors)
    assert set(new_agent.input_descriptors) == set(old_agent.input_descriptors)
    assert new_agent.__metadata_info__ == old_agent.__metadata_info__
    assert new_agent.id == old_agent.id


def test_can_deserialize_a_serialized_agent(
    agent: Agent,
) -> None:
    deserialization_context = DeserializationContext()
    register_server_tool(add_number_tool, deserialization_context.registered_tools)
    new_agent = deserialize(
        Agent, serialize(agent), deserialization_context=deserialization_context
    )
    _check_deserialized_agent_validity(agent, new_agent)


def test_can_autodeserialize_a_serialized_agent(
    agent: Agent,
) -> None:
    deserialization_context = DeserializationContext()
    register_server_tool(add_number_tool, deserialization_context.registered_tools)
    new_agent = autodeserialize(serialize(agent), deserialization_context=deserialization_context)
    _check_deserialized_agent_validity(agent, new_agent)


def test_can_deserialize_xkcd_assistant() -> None:
    with open(CONFIGS_DIR / "xkcd_tech_support_flow_chart.yaml") as config_file:
        serialized_assistant = config_file.read()
    assistant = deserialize(Flow, serialized_assistant)
    assert isinstance(assistant, Flow)
    assert len(assistant.steps) == 15


def run_branching_flow(flow: Flow, query: str, expected_message: str):
    conv = flow.start_conversation()
    status = flow.execute(conv)
    assert isinstance(status, UserMessageRequestStatus)
    conv.append_user_message(query)
    status = flow.execute(conv)
    assert isinstance(status, FinishedStatus)
    assert status.output_values["output_message"] == expected_message


def test_can_deserialize_subflow_with_branching_inside() -> None:
    with open(CONFIGS_DIR / "flow_with_subflow_branching.yaml") as config_file:
        serialized_assistant = config_file.read()
    flow = deserialize(Flow, serialized_assistant)
    assert isinstance(flow, Flow)
    assert len(flow.steps) == 5
    run_branching_flow(flow, "YES", "success!!!!")
    run_branching_flow(flow, "NO", "FAILUREEEEEE")
    run_branching_flow(flow, "BEDUBDUW", "FAILUREEEEEE")
