# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import cast

from pyagentspec.flows.edges import ControlFlowEdge
from pyagentspec.flows.flow import Flow
from pyagentspec.flows.nodes import EndNode, OutputMessageNode, StartNode
from pyagentspec.llms import VllmConfig

from wayflowcore import Flow as WayflowFlow
from wayflowcore import MessageType
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.agentspec.components.messagelist import PluginMessageType
from wayflowcore.agentspec.components.nodes import PluginOutputMessageNode
from wayflowcore.models import VllmModel
from wayflowcore.steps import OutputMessageStep


def test_output_message_node_is_deserialized_correctly() -> None:
    start_node = StartNode(name="start")
    end_node = EndNode(name="end")
    output_node = OutputMessageNode(name="output_node", message="Hello!")
    flow = Flow(
        name="flow",
        start_node=start_node,
        nodes=[start_node, end_node, output_node],
        control_flow_connections=[
            ControlFlowEdge(name="c1", from_node=start_node, to_node=output_node),
            ControlFlowEdge(name="c2", from_node=output_node, to_node=end_node),
        ],
        data_flow_connections=[],
    )
    wayflow_flow = cast(WayflowFlow, AgentSpecLoader().load_component(flow))
    output_step = wayflow_flow.steps["output_node"]
    assert isinstance(output_step, OutputMessageStep)
    assert output_step.message_template == "Hello!"
    assert not output_step.rephrase


def test_extended_output_message_node_is_deserialized_correctly() -> None:
    start_node = StartNode(name="start")
    end_node = EndNode(name="end")
    output_node = PluginOutputMessageNode(
        name="output_node",
        message="Hello!",
        message_type=PluginMessageType.SYSTEM,
        rephrase=True,
        llm_config=VllmConfig(name="llm", url="http://my.url", model_id="my.llm"),
    )
    flow = Flow(
        name="flow",
        start_node=start_node,
        nodes=[start_node, end_node, output_node],
        control_flow_connections=[
            ControlFlowEdge(name="c1", from_node=start_node, to_node=output_node),
            ControlFlowEdge(name="c2", from_node=output_node, to_node=end_node),
        ],
        data_flow_connections=[],
    )
    wayflow_flow = cast(WayflowFlow, AgentSpecLoader().load_component(flow))
    output_step = wayflow_flow.steps["output_node"]
    assert isinstance(output_step, OutputMessageStep)
    assert output_step.message_template == output_node.message
    assert output_step.rephrase
    assert isinstance(output_step.llm, VllmModel)


def test_output_message_step_is_serialized_correctly() -> None:
    output_step = OutputMessageStep(
        name="output_node", message_template="Hello!", expose_message_as_output=False
    )
    wayflow_flow = WayflowFlow.from_steps([output_step])
    agentspec_flow = AgentSpecExporter().to_component(wayflow_flow)
    output_node = next(
        (node for node in agentspec_flow.nodes if isinstance(node, OutputMessageNode)),
        None,
    )
    assert output_node is not None
    assert not isinstance(output_node, PluginOutputMessageNode)

    output_step = OutputMessageStep(
        name="output_node",
        message_template="Hello!",
        message_type=PluginMessageType.SYSTEM,
        rephrase=True,
        llm=VllmModel(host_port="http://my.url", model_id="my.llm"),
    )
    wayflow_flow = WayflowFlow.from_steps([output_step])
    agentspec_flow = AgentSpecExporter().to_component(wayflow_flow)
    output_node = next(
        (node for node in agentspec_flow.nodes if isinstance(node, PluginOutputMessageNode)),
        None,
    )
    assert output_node is not None
    assert output_node.message == output_step.message_template
    assert output_node.message_type == MessageType.SYSTEM
    assert output_node.rephrase == output_step.rephrase
    assert isinstance(output_node.llm_config, VllmConfig)
