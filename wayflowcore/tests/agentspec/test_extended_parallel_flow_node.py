# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Callable, Dict, cast

import pytest
from pyagentspec.flows.edges import ControlFlowEdge
from pyagentspec.flows.flow import Flow
from pyagentspec.flows.node import Node
from pyagentspec.flows.nodes import EndNode, ParallelFlowNode, StartNode, ToolNode
from pyagentspec.property import IntegerProperty
from pyagentspec.tools import ServerTool

from wayflowcore import Flow as WayflowFlow
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.agentspec.components import ExtendedParallelFlowNode
from wayflowcore.steps import ParallelFlowExecutionStep


def create_one_node_flow(node: Node) -> Flow:
    start_node = StartNode(name="start", inputs=node.inputs)
    end_node = EndNode(name="end", outputs=node.outputs)
    return Flow(
        name="flow",
        start_node=start_node,
        nodes=[start_node, end_node, node],
        control_flow_connections=[
            ControlFlowEdge(name="c1", from_node=start_node, to_node=node),
            ControlFlowEdge(name="c2", from_node=node, to_node=end_node),
        ],
        data_flow_connections=None,
    )


def create_flow_with_parallel_flow_node(extended: bool = False) -> Flow:

    add_tool = ServerTool(
        name="add",
        inputs=[IntegerProperty(title="a"), IntegerProperty(title="b")],
        outputs=[IntegerProperty(title="sum")],
    )

    subtract_tool = ServerTool(
        name="subtract",
        inputs=[IntegerProperty(title="a"), IntegerProperty(title="b")],
        outputs=[IntegerProperty(title="difference")],
    )

    multiply_tool = ServerTool(
        name="multiply",
        inputs=[IntegerProperty(title="a"), IntegerProperty(title="b")],
        outputs=[IntegerProperty(title="product")],
    )

    divide_tool = ServerTool(
        name="divide",
        inputs=[IntegerProperty(title="a"), IntegerProperty(title="b")],
        outputs=[IntegerProperty(title="quotient")],
    )

    sum_flow = create_one_node_flow(ToolNode(name="sum_step", tool=add_tool))
    subtract_flow = create_one_node_flow(ToolNode(name="subtract_step", tool=subtract_tool))
    multiply_flow = create_one_node_flow(ToolNode(name="multiply_step", tool=multiply_tool))
    divide_flow = create_one_node_flow(ToolNode(name="divide_step", tool=divide_tool))

    if extended:
        parallel_flow_node = ExtendedParallelFlowNode(
            name="parallel_flow_node",
            flows=[sum_flow, subtract_flow, multiply_flow, divide_flow],
            max_workers=3,
        )
    else:
        parallel_flow_node = ParallelFlowNode(
            name="parallel_flow_node",
            subflows=[sum_flow, subtract_flow, multiply_flow, divide_flow],
        )

    return create_one_node_flow(parallel_flow_node)


@pytest.fixture
def default_flow_with_parallel_flow_node() -> Flow:
    return create_flow_with_parallel_flow_node(extended=False)


@pytest.fixture
def default_flow_with_extended_parallel_flow_node() -> Flow:
    return create_flow_with_parallel_flow_node(extended=True)


@pytest.fixture
def tool_registry() -> Dict[str, Callable]:

    def add(a: int, b: int) -> int:
        """Sum two numbers"""
        return a + b

    def subtract(a: int, b: int) -> int:
        """Subtract two numbers"""
        return a - b

    def multiply(a: int, b: int) -> int:
        """Multiply two numbers"""
        return a * b

    def divide(a: int, b: int) -> int:
        """Divide two numbers"""
        return a // b

    return {
        "add": add,
        "subtract": subtract,
        "multiply": multiply,
        "divide": divide,
    }


def test_parallel_flow_node_is_serde_correctly(
    default_flow_with_parallel_flow_node: Flow,
    tool_registry: Dict[str, Callable],
) -> None:

    wayflow_flow = cast(
        WayflowFlow,
        AgentSpecLoader(tool_registry=tool_registry).load_component(
            default_flow_with_parallel_flow_node
        ),
    )
    parallel_flow_step = wayflow_flow.steps["parallel_flow_node"]
    assert isinstance(parallel_flow_step, ParallelFlowExecutionStep)
    assert parallel_flow_step.max_workers is None
    assert isinstance(parallel_flow_step.flows, list)
    assert all(isinstance(subflow, WayflowFlow) for subflow in parallel_flow_step.flows)

    serialized_flow = AgentSpecExporter().to_yaml(wayflow_flow)
    assert "component_type: ParallelFlowNode" in serialized_flow
    assert "component_type: ExtendedParallelFlowNode" not in serialized_flow
    assert "add" in serialized_flow
    assert "product" in serialized_flow
    assert "max_workers" not in serialized_flow


def test_extended_parallel_flow_node_is_serde_correctly(
    default_flow_with_extended_parallel_flow_node: Flow,
    tool_registry: Dict[str, Callable],
) -> None:

    wayflow_flow = cast(
        WayflowFlow,
        AgentSpecLoader(tool_registry=tool_registry).load_component(
            default_flow_with_extended_parallel_flow_node
        ),
    )
    parallel_flow_step = wayflow_flow.steps["parallel_flow_node"]
    assert isinstance(parallel_flow_step, ParallelFlowExecutionStep)
    assert parallel_flow_step.max_workers == 3
    assert isinstance(parallel_flow_step.flows, list)
    assert all(isinstance(subflow, WayflowFlow) for subflow in parallel_flow_step.flows)

    serialized_flow = AgentSpecExporter().to_yaml(wayflow_flow)
    assert "component_type: ExtendedParallelFlowNode" in serialized_flow
    assert "component_type: ParallelFlowNode" not in serialized_flow
    assert "add" in serialized_flow
    assert "product" in serialized_flow
    assert "max_workers: 3" in serialized_flow
