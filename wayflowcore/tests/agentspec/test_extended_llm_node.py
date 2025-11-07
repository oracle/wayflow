# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import cast

from pyagentspec.flows.edges import ControlFlowEdge
from pyagentspec.flows.flow import Flow
from pyagentspec.flows.nodes import EndNode, LlmNode, StartNode
from pyagentspec.llms import VllmConfig

from wayflowcore import Flow as WayflowFlow
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.agentspec.components.nodes import ExtendedLlmNode
from wayflowcore.models import VllmModel
from wayflowcore.steps import PromptExecutionStep


def test_llm_node_is_converted_correctly() -> None:

    from pyagentspec.property import IntegerProperty, StringProperty

    start_node = StartNode(name="start")
    end_node = EndNode(name="end")
    llm_node = LlmNode(
        name="llm_node",
        llm_config=VllmConfig(name="llm", url="http://my.url", model_id="my.llm"),
        prompt_template="What is the fastest italian car?",
        outputs=[
            StringProperty(title="brand", description="The brand of the car"),
            StringProperty(title="model", description="The name of the car's model"),
            IntegerProperty(
                title="hp", description="The horsepower amount, which expresses the car's power"
            ),
        ],
    )
    flow = Flow(
        name="flow",
        start_node=start_node,
        nodes=[start_node, end_node, llm_node],
        control_flow_connections=[
            ControlFlowEdge(name="c1", from_node=start_node, to_node=llm_node),
            ControlFlowEdge(name="c2", from_node=llm_node, to_node=end_node),
        ],
        data_flow_connections=[],
    )
    wayflow_flow = cast(WayflowFlow, AgentSpecLoader().load_component(flow))
    llm_step = wayflow_flow.steps["llm_node"]
    assert isinstance(llm_step, PromptExecutionStep)
    assert not llm_step.send_message
    assert len(llm_step.output_descriptors) == 3


def test_prompt_execution_step_is_serialized_correctly() -> None:

    from wayflowcore.property import IntegerProperty, StringProperty

    llm_step = PromptExecutionStep(
        name="llm_node",
        llm=VllmModel(model_id="my.llm", host_port="http://my.url"),
        prompt_template="What is the fastest italian car?",
        output_descriptors=[
            StringProperty(name="brand", description="The brand of the car"),
            StringProperty(name="model", description="The name of the car's model"),
            IntegerProperty(
                name="hp", description="The horsepower amount, which expresses the car's power"
            ),
        ],
    )
    wayflow_flow = WayflowFlow.from_steps([llm_step])
    agentspec_flow = AgentSpecExporter().to_component(wayflow_flow)
    llm_node = next(
        (node for node in agentspec_flow.nodes if isinstance(node, LlmNode)),
        None,
    )
    assert llm_node is not None
    assert not isinstance(llm_node, ExtendedLlmNode)

    llm_step = PromptExecutionStep(
        name="llm_node",
        llm=VllmModel(model_id="my.llm", host_port="http://my.url"),
        send_message=True,
        prompt_template="What is the fastest italian car?",
    )
    wayflow_flow = WayflowFlow.from_steps([llm_step])
    agentspec_flow = AgentSpecExporter().to_component(wayflow_flow)
    llm_node = next(
        (node for node in agentspec_flow.nodes if isinstance(node, ExtendedLlmNode)),
        None,
    )
    assert llm_node is not None
    assert llm_node.send_message
    assert len(llm_node.outputs or []) == 1
    assert isinstance(llm_node.llm_config, VllmConfig)
