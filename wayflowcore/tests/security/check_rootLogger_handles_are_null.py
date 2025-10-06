# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

"""
If somewhere our code initializes a StreamHandler this test will alert you to it.
It could be due to a dependency or your own code in the wayflowcore package.
The test will also catch all import failures due to syntax errors.

The implications are that applications that import wayflowcore cannot send logging info anymore.
As the resident RootLogger suppresses all downstream logging initialization via logging.basicConfig.
"""

import logging
import os

# Must not import packages outside the Python Standard Library here


def listloggers():
    rootlogger = logging.getLogger()
    print(rootlogger)
    for h in rootlogger.handlers:
        print("     %s" % h)

    for nm, lgr in logging.Logger.manager.loggerDict.items():
        print("+ [%-20s] %s " % (nm, lgr))
        if not isinstance(lgr, logging.PlaceHolder):
            for h in lgr.handlers:
                print("     %s" % h)


def import_all_of_wayflowcore():
    from wayflowcore.agent import Agent
    from wayflowcore.models import LlmModelFactory
    from wayflowcore.property import StringProperty
    from wayflowcore.serialization import deserialize, serialize
    from wayflowcore.tools import ClientTool

    llama_api_url = os.environ.get("LLAMA_API_URL")
    if not llama_api_url:
        raise Exception("LLAMA_API_URL is not set in the environment")
    # Run and serialize/deserialize a simple agent
    llm = LlmModelFactory.from_config(
        {
            "model_type": "vllm",
            "host_port": llama_api_url,
            "model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "generation_config": {"max_tokens": 512},
        }
    )
    agent = Agent(
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
    conversation = agent.start_conversation(inputs={"username": "test_user"})
    conversation.execute()
    conversation.append_user_message("This is a message to the agent")
    conversation.execute()
    serialized_agent = serialize(agent)
    _ = deserialize(Agent, serialized_agent)

    from wayflowcore.controlconnection import ControlFlowEdge
    from wayflowcore.dataconnection import DataFlowEdge
    from wayflowcore.flow import Flow
    from wayflowcore.flowhelpers import create_single_step_flow
    from wayflowcore.steps import (
        CompleteStep,
        FlowExecutionStep,
        InputMessageStep,
        OutputMessageStep,
        PromptExecutionStep,
        StartStep,
    )

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
    flow = Flow(
        begin_step=steps["start_step"],
        steps=steps,
        control_flow_edges=control_flow_edges,
        data_flow_edges=data_flow_edges,
        name="default_flow",
        flow_id="321cba",
    )
    conversation = flow.start_conversation(inputs={"username": "test_user"})
    conversation.execute()
    conversation.append_user_message("Good, thanks!")
    conversation.execute()
    serialized_flow = serialize(flow)
    _ = deserialize(Flow, serialized_flow)


def test_for_empty_rootlogger():

    rootlogger = logging.getLogger()
    if len(rootlogger.handlers) != 0:
        raise Exception(
            "rootLoggers must be empty. This file should only have PSL packages in its header."
            f"{rootlogger.handlers}"
        )
    import_all_of_wayflowcore()
    if len(rootlogger.handlers) != 0:
        listloggers()
        raise Exception(
            "Following rootLoggers have been initialized on import of wayflowcore package:\n"
            f"{rootlogger.handlers}"
        )


if __name__ == "__main__":
    test_for_empty_rootlogger()
