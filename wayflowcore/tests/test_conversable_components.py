# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from wayflowcore import Agent, Flow
from wayflowcore.contextproviders import FlowContextProvider, ToolContextProvider
from wayflowcore.ociagent import OciAgent
from wayflowcore.steps import (
    AgentExecutionStep,
    CatchExceptionStep,
    FlowExecutionStep,
    InputMessageStep,
    MapStep,
    PromptExecutionStep,
    RetryStep,
    ToolExecutionStep,
)
from wayflowcore.swarm import Swarm
from wayflowcore.templates import LLAMA_AGENT_TEMPLATE
from wayflowcore.tools import ServerTool


def create_tool(name: str):
    return ServerTool(name=name, description="", input_descriptors=[], func=lambda: "")


def test_get_referenced_tools_in_agent(remotely_hosted_llm):
    agent = Agent(
        llm=remotely_hosted_llm,
        tools=[
            create_tool("agent_tool_1"),
            create_tool("agent_tool_2"),
        ],
        flows=[
            Flow.from_steps(
                name="flow_1",
                description="flow 1",
                steps=[
                    ToolExecutionStep(create_tool("tool_in_flow_11")),
                    ToolExecutionStep(create_tool("tool_in_flow_12")),
                ],
            ),
            Flow.from_steps(
                name="flow_2",
                description="flow 2",
                steps=[
                    ToolExecutionStep(create_tool("tool_in_flow_21")),
                ],
            ),
        ],
        agents=[
            Agent(
                name="sub_agent_1",
                description="sub agent 1",
                llm=remotely_hosted_llm,
                tools=[create_tool("tool_in_agent_in_agent_1")],
            ),
            Agent(
                name="sub_agent_2",
                description="sub agent 2",
                llm=remotely_hosted_llm,
                tools=[create_tool("tool_in_agent_in_agent_2")],
            ),
        ],
    )
    expected_tool_names = {
        "agent_tool_1",
        "agent_tool_2",
        "tool_in_flow_11",
        "tool_in_flow_12",
        "tool_in_flow_21",
        "tool_in_agent_in_agent_1",
        "tool_in_agent_in_agent_2",
    }
    all_tools = agent._referenced_tools()
    assert len(all_tools) == len(expected_tool_names)
    assert set(t.name for t in all_tools) == expected_tool_names


def test_get_referenced_tools_in_flow(remotely_hosted_llm):
    flow = Flow.from_steps(
        steps=[
            ToolExecutionStep(tool=create_tool("tool_from_step")),
            InputMessageStep(message_template="hello"),
            AgentExecutionStep(
                agent=Agent(llm=remotely_hosted_llm, tools=[create_tool("tool_agent_in_flow")])
            ),
            MapStep(
                flow=Flow.from_steps(
                    steps=[
                        ToolExecutionStep(tool=create_tool("tool_in_mapstep")),
                    ]
                )
            ),
            FlowExecutionStep(
                flow=Flow.from_steps(
                    steps=[ToolExecutionStep(create_tool("tool_in_flow_execution_step"))]
                )
            ),
            CatchExceptionStep(
                flow=Flow.from_steps(
                    steps=[
                        ToolExecutionStep(tool=create_tool("tool_in_catch_exception_step")),
                    ]
                )
            ),
            RetryStep(
                flow=Flow.from_steps(
                    steps=[
                        ToolExecutionStep(tool=create_tool("tool_in_retry_step")),
                    ]
                ),
                success_condition="tool_output",
            ),
            PromptExecutionStep(
                llm=remotely_hosted_llm,
                prompt_template=LLAMA_AGENT_TEMPLATE.with_tools([create_tool("tool_in_template")]),
            ),
        ],
        context_providers=[
            FlowContextProvider(
                flow=Flow.from_steps(
                    steps=[ToolExecutionStep(tool=create_tool("tool_in_flow_context_provider"))]
                )
            ),
            ToolContextProvider(tool=create_tool("tool_in_tool_context_provider")),
        ],
    )
    expected_tool_names = {
        "tool_from_step",
        "tool_agent_in_flow",
        "tool_in_mapstep",
        "tool_in_flow_execution_step",
        "tool_in_catch_exception_step",
        "tool_in_retry_step",
        "tool_in_template",
        "tool_in_flow_context_provider",
        "tool_in_tool_context_provider",
    }
    all_tools = flow._referenced_tools()
    assert len(all_tools) == len(expected_tool_names)
    assert set(t.name for t in all_tools) == expected_tool_names


def test_get_referenced_tools_in_ociagent(remotely_hosted_llm, oci_agent_client_config):
    agent = OciAgent(client_config=oci_agent_client_config, agent_endpoint_id="some_endpoint")
    all_tools = set(t.name for t in agent._referenced_tools())
    assert all_tools == set()


def test_get_referenced_tools_in_swarm(remotely_hosted_llm):
    first_agent = Agent(llm=remotely_hosted_llm, tools=[create_tool("tool_in_first_agent")])

    swarm = Swarm(
        first_agent=first_agent,
        relationships=[
            (
                first_agent,
                Agent(
                    llm=remotely_hosted_llm,
                    tools=[create_tool("tool_in_first_sub_agent")],
                    description="sub agent 1",
                ),
            ),
            (
                first_agent,
                Agent(
                    llm=remotely_hosted_llm,
                    tools=[create_tool("tool_in_second_sub_agent")],
                    description="sub agent 2",
                ),
            ),
            (
                first_agent,
                Agent(
                    llm=remotely_hosted_llm,
                    tools=[create_tool("tool_in_third_sub_agent")],
                    description="sub agent 3",
                ),
            ),
        ],
    )
    expected_tool_names = {
        "tool_in_first_agent",
        "tool_in_first_sub_agent",
        "tool_in_second_sub_agent",
        "tool_in_third_sub_agent",
    }
    all_tools = swarm._referenced_tools()
    assert len(all_tools) == len(expected_tool_names)
    assert set(t.name for t in all_tools) == expected_tool_names


def test_referenced_tools_are_deduplicated(remotely_hosted_llm):
    tool_1 = create_tool("tool_1")
    tool_2 = create_tool("tool_1")  # has the same name as tool_1
    tool_3 = create_tool("tool_3")
    flow = Flow.from_steps(
        steps=[
            AgentExecutionStep(
                agent=Agent(
                    llm=remotely_hosted_llm,
                    tools=[tool_1, tool_3],
                    flows=[
                        Flow.from_steps(
                            steps=[ToolExecutionStep(tool_1)],
                            name="subflow",
                            description="sub flow",
                        )
                    ],
                )
            ),
            ToolExecutionStep(tool_1),
            FlowExecutionStep(flow=Flow.from_steps(steps=[ToolExecutionStep(tool_2)])),
        ]
    )
    all_tools = flow._referenced_tools()
    assert len(all_tools) == 3
    assert {t.name for t in all_tools} == {"tool_1", "tool_3"}
