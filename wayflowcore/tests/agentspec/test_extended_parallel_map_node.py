# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import cast

import pytest
from pyagentspec.flows.edges import ControlFlowEdge
from pyagentspec.flows.flow import Flow
from pyagentspec.flows.nodes import EndNode, ParallelMapNode, StartNode, ToolNode
from pyagentspec.property import ListProperty, StringProperty
from pyagentspec.tools import ServerTool

from wayflowcore import Flow as WayflowFlow
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.agentspec.components import ExtendedParallelMapNode
from wayflowcore.steps import ParallelMapStep


def create_flow_with_parallel_map_node(extended: bool = False) -> Flow:
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

    if extended:
        parallel_map_node = ExtendedParallelMapNode(
            name="parallel_map_node",
            flow=subflow,
            unpack_input={"in": "."},
            max_workers=3,
        )
        parallel_map_node_input = ListProperty(
            title=ExtendedParallelMapNode.ITERATED_INPUT, item_type=StringProperty()
        )
    else:
        parallel_map_node = ParallelMapNode(
            name="parallel_map_node",
            subflow=subflow,
        )
        parallel_map_node_input = ListProperty(title="iterated_in", item_type=StringProperty())

    start_node = StartNode(name="start", inputs=[parallel_map_node_input])
    end_node = EndNode(name="end", outputs=parallel_map_node.outputs)

    return Flow(
        name="flow",
        start_node=start_node,
        nodes=[start_node, end_node, parallel_map_node],
        control_flow_connections=[
            ControlFlowEdge(name="c1", from_node=start_node, to_node=parallel_map_node),
            ControlFlowEdge(name="c2", from_node=parallel_map_node, to_node=end_node),
        ],
        data_flow_connections=None,
    )


@pytest.fixture
def default_flow_with_parallel_map_node() -> Flow:
    return create_flow_with_parallel_map_node(extended=False)


@pytest.fixture
def default_flow_with_extended_parallel_map_node() -> Flow:
    return create_flow_with_parallel_map_node(extended=True)


def test_parallel_map_node_is_serde_correctly(default_flow_with_parallel_map_node: Flow) -> None:

    wayflow_flow = cast(
        WayflowFlow,
        AgentSpecLoader(tool_registry={"tool": lambda x: x}).load_component(
            default_flow_with_parallel_map_node
        ),
    )
    parallel_map_node = wayflow_flow.steps["parallel_map_node"]
    assert isinstance(parallel_map_node, ParallelMapStep)
    assert parallel_map_node.unpack_input == {"in": "."}
    assert parallel_map_node.max_workers is None
    assert isinstance(parallel_map_node.flow, WayflowFlow)

    serialized_flow = AgentSpecExporter().to_yaml(wayflow_flow)
    # The export of an import is going to be an extended version, since it contains input/output mappings
    assert "component_type: ExtendedParallelMapNode" in serialized_flow
    assert "tool_node" in serialized_flow
    assert "unpack_input:" in serialized_flow


def test_extended_parallel_map_node_is_serde_correctly(
    default_flow_with_extended_parallel_map_node: Flow,
) -> None:

    wayflow_flow = cast(
        WayflowFlow,
        AgentSpecLoader(tool_registry={"tool": lambda x: x}).load_component(
            default_flow_with_extended_parallel_map_node
        ),
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
