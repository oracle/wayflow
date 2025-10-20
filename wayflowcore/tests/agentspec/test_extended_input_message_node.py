# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import cast

from pyagentspec.flows.edges import ControlFlowEdge
from pyagentspec.flows.flow import Flow
from pyagentspec.flows.nodes import EndNode, InputMessageNode, StartNode
from pyagentspec.llms import VllmConfig

from wayflowcore import Flow as WayflowFlow
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.agentspec.components.nodes import PluginInputMessageNode
from wayflowcore.models import VllmModel
from wayflowcore.steps import InputMessageStep


def test_input_message_node_is_deserialized_correctly() -> None:
    start_node = StartNode(name="start")
    end_node = EndNode(name="end")
    input_node = InputMessageNode(name="input_node")
    flow = Flow(
        name="flow",
        start_node=start_node,
        nodes=[start_node, end_node, input_node],
        control_flow_connections=[
            ControlFlowEdge(name="c1", from_node=start_node, to_node=input_node),
            ControlFlowEdge(name="c2", from_node=input_node, to_node=end_node),
        ],
        data_flow_connections=[],
    )
    wayflow_flow = cast(WayflowFlow, AgentSpecLoader().load_component(flow))
    input_step = wayflow_flow.steps["input_node"]
    assert isinstance(input_step, InputMessageStep)
    assert input_step.message_template is None
    assert not input_step.rephrase


def test_extended_input_message_node_is_deserialized_correctly() -> None:
    start_node = StartNode(name="start")
    end_node = EndNode(name="end")
    input_node = PluginInputMessageNode(
        name="input_node",
        message_template="Hello!",
        rephrase=True,
        llm_config=VllmConfig(name="llm", url="http://my.url", model_id="my.llm"),
    )
    flow = Flow(
        name="flow",
        start_node=start_node,
        nodes=[start_node, end_node, input_node],
        control_flow_connections=[
            ControlFlowEdge(name="c1", from_node=start_node, to_node=input_node),
            ControlFlowEdge(name="c2", from_node=input_node, to_node=end_node),
        ],
        data_flow_connections=[],
    )
    wayflow_flow = cast(WayflowFlow, AgentSpecLoader().load_component(flow))
    input_step = wayflow_flow.steps["input_node"]
    assert isinstance(input_step, InputMessageStep)
    assert input_step.message_template == input_node.message_template
    assert input_step.rephrase
    assert isinstance(input_step.llm, VllmModel)


def test_input_message_step_is_serialized_correctly() -> None:
    input_step = InputMessageStep(name="input_node", message_template=None)
    wayflow_flow = WayflowFlow.from_steps([input_step])
    agentspec_flow = AgentSpecExporter().to_component(wayflow_flow)
    input_node = next(
        (node for node in agentspec_flow.nodes if isinstance(node, InputMessageNode)),
        None,
    )
    assert input_node is not None
    assert not isinstance(input_node, PluginInputMessageNode)

    input_step = InputMessageStep(
        name="input_node",
        message_template="Hello!",
        rephrase=True,
        llm=VllmModel(host_port="http://my.url", model_id="my.llm"),
    )
    wayflow_flow = WayflowFlow.from_steps([input_step])
    agentspec_flow = AgentSpecExporter().to_component(wayflow_flow)
    input_node = next(
        (node for node in agentspec_flow.nodes if isinstance(node, PluginInputMessageNode)),
        None,
    )
    assert input_node is not None
    assert input_node.message_template == input_step.message_template
    assert input_node.rephrase == input_step.rephrase
    assert isinstance(input_node.llm_config, VllmConfig)
