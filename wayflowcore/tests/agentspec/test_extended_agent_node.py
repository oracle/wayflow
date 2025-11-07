# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import cast

from pyagentspec.agent import Agent
from pyagentspec.flows.edges import ControlFlowEdge
from pyagentspec.flows.flow import Flow
from pyagentspec.flows.nodes import AgentNode, EndNode, StartNode
from pyagentspec.llms import VllmConfig

from wayflowcore import Agent as WayflowAgent
from wayflowcore import Flow as WayflowFlow
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.agentspec.components.nodes import ExtendedAgentNode
from wayflowcore.models import VllmModel
from wayflowcore.steps import AgentExecutionStep


def test_agent_node_is_converted_correctly() -> None:

    from pyagentspec.property import IntegerProperty, StringProperty

    start_node = StartNode(name="start")
    end_node = EndNode(name="end")
    agent = Agent(
        name="agent",
        llm_config=VllmConfig(name="llm", url="http://my.url", model_id="my.llm"),
        system_prompt="What is the fastest italian car?",
        outputs=[
            StringProperty(title="brand", description="The brand of the car"),
            StringProperty(title="model", description="The name of the car's model"),
            IntegerProperty(
                title="hp", description="The horsepower amount, which expresses the car's power"
            ),
        ],
    )
    agent_node = AgentNode(name="agent_node", agent=agent)
    flow = Flow(
        name="flow",
        start_node=start_node,
        nodes=[start_node, end_node, agent_node],
        control_flow_connections=[
            ControlFlowEdge(name="c1", from_node=start_node, to_node=agent_node),
            ControlFlowEdge(name="c2", from_node=agent_node, to_node=end_node),
        ],
        data_flow_connections=[],
    )
    wayflow_flow = cast(WayflowFlow, AgentSpecLoader().load_component(flow))
    agent_step = wayflow_flow.steps["agent_node"]
    assert isinstance(agent_step, AgentExecutionStep)
    assert len(agent_step.output_descriptors) == 3


def test_agent_execution_step_is_serialized_correctly() -> None:

    from wayflowcore.property import IntegerProperty, StringProperty

    agent = WayflowAgent(
        llm=VllmModel(model_id="my.llm", host_port="http://my.url"),
        custom_instruction="What is the fastest italian car?",
        output_descriptors=[
            StringProperty(name="brand", description="The brand of the car"),
            StringProperty(name="model", description="The name of the car's model"),
            IntegerProperty(
                name="hp", description="The horsepower amount, which expresses the car's power"
            ),
        ],
    )

    agent_step = AgentExecutionStep(name="agent_node", agent=agent)
    wayflow_flow = WayflowFlow.from_steps([agent_step])
    agentspec_flow = AgentSpecExporter().to_component(wayflow_flow)
    agent_node = next(
        (node for node in agentspec_flow.nodes if isinstance(node, AgentNode)),
        None,
    )
    assert agent_node is not None
    assert not isinstance(agent_node, ExtendedAgentNode)
    assert isinstance(agent_node.agent, Agent)

    agent = WayflowAgent(
        llm=VllmModel(model_id="my.llm", host_port="http://my.url"),
        custom_instruction="What is the fastest italian car?",
    )

    agent_step = AgentExecutionStep(
        name="agent_node",
        agent=agent,
        output_descriptors=[
            StringProperty(name="brand", description="The brand of the car"),
            StringProperty(name="model", description="The name of the car's model"),
            IntegerProperty(
                name="hp", description="The horsepower amount, which expresses the car's power"
            ),
        ],
    )
    wayflow_flow = WayflowFlow.from_steps([agent_step])
    agentspec_flow = AgentSpecExporter().to_component(wayflow_flow)
    agent_node = next(
        (node for node in agentspec_flow.nodes if isinstance(node, ExtendedAgentNode)),
        None,
    )
    assert agent_node is not None
    assert len(agent_node.outputs or []) == 3
    assert isinstance(agent_node.agent, Agent)
