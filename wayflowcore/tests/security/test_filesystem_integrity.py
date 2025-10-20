# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""
The purpose of these tests is to show that the filesystem is not accessed (read/write)
unexpectedly by the main wayflowcore functionalities.
"""

from wayflowcore.agent import Agent
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.models import LlmModel, LlmModelFactory
from wayflowcore.property import StringProperty
from wayflowcore.serialization import deserialize, serialize
from wayflowcore.steps import (
    CompleteStep,
    FlowExecutionStep,
    InputMessageStep,
    OutputMessageStep,
    PromptExecutionStep,
    StartStep,
)
from wayflowcore.tools import ClientTool

from ..conftest import VLLM_MODEL_CONFIG
from ..testhelpers.dummy import DummyModel


def create_default_llm(serializable: bool = False) -> LlmModel:
    # The dummy model just returns "..." at every generation
    return (
        LlmModelFactory.from_config(VLLM_MODEL_CONFIG)
        if serializable
        else DummyModel(fails_if_not_set=False)
    )


def create_default_agent(llm: LlmModel) -> Agent:
    return Agent(
        agent_id="abc123",
        name="default_agent",
        llm=llm,
        custom_instruction="You are a great agent. You are talking to {{username}}. Be kind.",
        tools=[
            ClientTool(
                name="do_nothing",
                description="do nothing",
                input_descriptors=[StringProperty("x")],
                output_descriptors=[StringProperty("x")],
            )
        ],
    )


def create_default_flow(llm: LlmModel) -> Flow:
    steps = {
        "start_step": StartStep(input_descriptors=[StringProperty(name="username")]),
        "input_step": InputMessageStep("How are you, {{username}}?"),
        "prompt_step": FlowExecutionStep(
            create_single_step_flow(
                step=PromptExecutionStep(
                    llm=llm, prompt_template="{{" + InputMessageStep.USER_PROVIDED_INPUT + "}}"
                ),
                step_name="inner_prompt_step",
                flow_name="subflow_1",
            )
        ),
        "output_step": OutputMessageStep(
            "{{"
            + InputMessageStep.USER_PROVIDED_INPUT
            + "}}, {{"
            + PromptExecutionStep.OUTPUT
            + "}}"
        ),
        "end_step": CompleteStep(),
    }
    control_flow_edges = [
        ControlFlowEdge(
            source_step=steps["start_step"],
            destination_step=steps["input_step"],
        ),
        ControlFlowEdge(
            source_step=steps["input_step"],
            destination_step=steps["prompt_step"],
        ),
        ControlFlowEdge(
            source_step=steps["prompt_step"],
            destination_step=steps["output_step"],
        ),
        ControlFlowEdge(
            source_step=steps["output_step"],
            destination_step=steps["end_step"],
        ),
    ]
    data_flow_edges = [
        DataFlowEdge(
            source_step=steps["input_step"],
            source_output=InputMessageStep.USER_PROVIDED_INPUT,
            destination_step=steps["prompt_step"],
            destination_input=InputMessageStep.USER_PROVIDED_INPUT,
        ),
        DataFlowEdge(
            source_step=steps["input_step"],
            source_output=InputMessageStep.USER_PROVIDED_INPUT,
            destination_step=steps["output_step"],
            destination_input=InputMessageStep.USER_PROVIDED_INPUT,
        ),
        DataFlowEdge(
            source_step=steps["prompt_step"],
            source_output=PromptExecutionStep.OUTPUT,
            destination_step=steps["output_step"],
            destination_input=PromptExecutionStep.OUTPUT,
        ),
    ]
    return Flow(
        begin_step=steps["start_step"],
        steps=steps,
        control_flow_edges=control_flow_edges,
        data_flow_edges=data_flow_edges,
        name="default_flow",
        flow_id="321cba",
    )


def test_serialize_and_deserialize_agent(guard_all_filewrites, guard_all_network_access) -> None:
    agent = create_default_agent(create_default_llm(serializable=True))
    serialized_agent = serialize(agent)
    _ = deserialize(Agent, serialized_agent)


def test_serialize_and_deserialize_flow(guard_all_filewrites, guard_all_network_access) -> None:
    flow = create_default_flow(create_default_llm(serializable=True))
    serialized_flow = serialize(flow)
    _ = deserialize(Flow, serialized_flow)


def test_run_agent(guard_all_filewrites, guard_all_network_access) -> None:
    agent = create_default_agent(create_default_llm(serializable=False))
    conversation = agent.start_conversation(inputs={"username": "test_user"})
    conversation.execute()
    conversation.append_user_message("This is a message to the agent")
    conversation.execute()


def test_run_flow(guard_all_filewrites, guard_all_network_access) -> None:
    flow = create_default_flow(create_default_llm(serializable=False))
    conversation = flow.start_conversation(inputs={"username": "test_user"})
    conversation.execute()
    conversation.append_user_message("Good, thanks!")
    conversation.execute()
