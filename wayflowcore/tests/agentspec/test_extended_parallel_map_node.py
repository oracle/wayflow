# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import cast

from pyagentspec.flows.edges import ControlFlowEdge
from pyagentspec.flows.flow import Flow
from pyagentspec.flows.nodes import EndNode, StartNode, ToolNode
from pyagentspec.property import ListProperty, StringProperty
from pyagentspec.tools import ServerTool

from wayflowcore import Flow as WayflowFlow
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.agentspec.components import ExtendedParallelMapNode
from wayflowcore.steps import ParallelMapStep


def test_extended_parallel_map_node_is_serde_correctly() -> None:
    start_node = StartNode(name="start", inputs=[StringProperty(title="in")])
    end_node = EndNode(name="end", outputs=[StringProperty(title="out")])
    tool = ServerTool(
        name="tool", inputs=[StringProperty(title="in")], outputs=[StringProperty(title="out")]
    )
    tool_node = ToolNode(name="tool_node", tool=tool)
    subflow = Flow(
        name="subflow",
        start_node=start_node,
        nodes=[start_node, end_node, tool_node],
        control_flow_connections=[
            ControlFlowEdge(name="c1", from_node=start_node, to_node=tool_node),
            ControlFlowEdge(name="c2", from_node=tool_node, to_node=end_node),
        ],
        data_flow_connections=None,
    )

    start_node = StartNode(
        name="start",
        inputs=[
            ListProperty(title=ExtendedParallelMapNode.ITERATED_INPUT, item_type=StringProperty())
        ],
    )
    end_node = EndNode(name="end")
    parallel_map_node = ExtendedParallelMapNode(
        name="parallel_map_node",
        flow=subflow,
        unpack_input={"in": "."},
        max_workers=3,
    )
    flow = Flow(
        name="flow",
        start_node=start_node,
        nodes=[start_node, end_node, parallel_map_node],
        control_flow_connections=[
            ControlFlowEdge(name="c1", from_node=start_node, to_node=parallel_map_node),
            ControlFlowEdge(name="c2", from_node=parallel_map_node, to_node=end_node),
        ],
        data_flow_connections=None,
    )
    wayflow_flow = cast(
        WayflowFlow, AgentSpecLoader(tool_registry={"tool": lambda x: x}).load_component(flow)
    )
    parallel_map_node = wayflow_flow.steps["parallel_map_node"]
    assert isinstance(parallel_map_node, ParallelMapStep)
    assert parallel_map_node.unpack_input == {"in": "."}
    assert parallel_map_node.max_workers == 3
    assert isinstance(parallel_map_node.flow, WayflowFlow)

    serialized_flow = AgentSpecExporter().to_yaml(wayflow_flow)
    assert "component_type: ExtendedParallelMapNode" in serialized_flow
    assert "component_type: ParallelMapNode" not in serialized_flow
    assert "tool_node" in serialized_flow
    assert "unpack_input:" in serialized_flow
    assert "max_workers: 3" in serialized_flow
