# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import List, Optional

import pytest

from wayflowcore import Tool
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import run_step_and_return_outputs
from wayflowcore.property import IntegerProperty, ListProperty, StringProperty
from wayflowcore.steps import InputMessageStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.steps.parallelflowexecutionstep import ParallelFlowExecutionStep
from wayflowcore.tools import ServerTool


def get_tool(arg_names: Optional[List[str]] = None, output_name: str = "output") -> Tool:
    return ServerTool(
        name="some_tool",
        description="description",
        input_descriptors=[StringProperty(name=arg_name) for arg_name in arg_names or []],
        output_descriptors=[StringProperty(name=output_name)],
        func=lambda **kwargs: str(kwargs) + f"_from_{output_name}",
    )


def get_flow_from_tools(tools: List[Tool]) -> Flow:
    return Flow.from_steps(steps=[ToolExecutionStep(tool=t) for t in tools])


def test_simple_parallel_subflow_has_correct_outputs() -> None:
    step = ParallelFlowExecutionStep(
        flows=[
            get_flow_from_tools(
                tools=[
                    get_tool(output_name="subflow_11_output"),
                    get_tool(output_name="subflow_12_output"),
                ]
            ),
            get_flow_from_tools(
                tools=[get_tool(output_name="subflow_2_output")],
            ),
        ]
    )
    assert step.input_descriptors == []
    assert set(step.output_descriptors) == {
        StringProperty(name="subflow_11_output"),
        StringProperty(name="subflow_12_output"),
        StringProperty(name="subflow_2_output"),
    }
    outputs = run_step_and_return_outputs(step)
    assert outputs == {
        "subflow_11_output": "{}_from_subflow_11_output",
        "subflow_12_output": "{}_from_subflow_12_output",
        "subflow_2_output": "{}_from_subflow_2_output",
    }


def test_simple_parallel_subflow_has_correct_inputs() -> None:
    step = ParallelFlowExecutionStep(
        flows=[
            get_flow_from_tools(
                tools=[
                    get_tool(arg_names=["input1"], output_name="o1"),
                    get_tool(arg_names=["input2"], output_name="o2"),
                ]
            ),
            get_flow_from_tools(
                tools=[
                    get_tool(arg_names=["input3"], output_name="o3"),
                ]
            ),
        ]
    )
    assert set(step.input_descriptors) == {
        StringProperty(name="input1"),
        StringProperty(name="input2"),
        StringProperty(name="input3"),
    }
    assert set(step.output_descriptors) == {
        StringProperty(name="o1"),
        StringProperty(name="o2"),
        StringProperty(name="o3"),
    }
    outputs = run_step_and_return_outputs(
        step,
        inputs={
            "input1": "i1",
            "input2": "i2",
            "input3": "i3",
        },
    )
    assert outputs == {
        "o1": "{'input1': 'i1'}_from_o1",
        "o2": "{'input2': 'i2'}_from_o2",
        "o3": "{'input3': 'i3'}_from_o3",
    }


def test_simple_parallel_subflow_has_correct_inputs_when_collision_occurs() -> None:
    step = ParallelFlowExecutionStep(
        flows=[
            get_flow_from_tools(
                tools=[
                    get_tool(arg_names=["input1"], output_name="o1"),
                    get_tool(arg_names=["input2"], output_name="o2"),
                ]
            ),
            get_flow_from_tools(
                tools=[
                    get_tool(arg_names=["input1"], output_name="o3"),
                    get_tool(arg_names=["input3"], output_name="o4"),
                ]
            ),
        ]
    )
    assert set(step.input_descriptors) == {
        StringProperty(name="input1"),
        StringProperty(name="input2"),
        StringProperty(name="input3"),
    }
    assert set(step.output_descriptors) == {
        StringProperty(name="o1"),
        StringProperty(name="o2"),
        StringProperty(name="o3"),
        StringProperty(name="o4"),
    }
    outputs = run_step_and_return_outputs(
        step,
        inputs={
            "input1": "i1",
            "input2": "i2",
            "input3": "i3",
        },
    )
    assert outputs == {
        "o1": "{'input1': 'i1'}_from_o1",
        "o2": "{'input2': 'i2'}_from_o2",
        "o3": "{'input1': 'i1'}_from_o3",
        "o4": "{'input3': 'i3'}_from_o4",
    }


def test_parallel_flow_step_raises_when_output_name_collisions_occur():
    with pytest.raises(
        ValueError,
        match="Output descriptors of subflows inside ParallelFlowExecutionStep cannot have the same name",
    ):
        _ = ParallelFlowExecutionStep(
            flows=[
                get_flow_from_tools(
                    tools=[
                        get_tool(arg_names=["input1"], output_name="o1"),
                        get_tool(arg_names=["input2"], output_name="o2"),
                    ]
                ),
                get_flow_from_tools(tools=[get_tool(arg_names=["input3"], output_name="o2")]),
            ]
        )


def test_nested_parallel_subflow_execution() -> None:
    step_1 = ParallelFlowExecutionStep(
        flows=[
            get_flow_from_tools(tools=[get_tool(arg_names=["input1"], output_name="o1")]),
            get_flow_from_tools(tools=[get_tool(arg_names=["input2"], output_name="o2")]),
        ]
    )
    step_2 = ParallelFlowExecutionStep(
        flows=[
            get_flow_from_tools(tools=[get_tool(arg_names=["input3"], output_name="o3")]),
            get_flow_from_tools(tools=[get_tool(arg_names=["input4"], output_name="o4")]),
        ]
    )
    step = ParallelFlowExecutionStep(
        flows=[
            Flow.from_steps(steps=[step_1]),
            Flow.from_steps(steps=[step_2]),
        ]
    )
    assert set(step.input_descriptors) == {
        StringProperty(name="input1"),
        StringProperty(name="input2"),
        StringProperty(name="input3"),
        StringProperty(name="input4"),
    }
    assert set(step.output_descriptors) == {
        StringProperty(name="o1"),
        StringProperty(name="o2"),
        StringProperty(name="o3"),
        StringProperty(name="o4"),
    }
    outputs = run_step_and_return_outputs(
        step,
        inputs={
            "input1": "i1",
            "input2": "i2",
            "input3": "i3",
            "input4": "i4",
        },
    )
    assert outputs == {
        "o1": "{'input1': 'i1'}_from_o1",
        "o2": "{'input2': 'i2'}_from_o2",
        "o3": "{'input3': 'i3'}_from_o3",
        "o4": "{'input4': 'i4'}_from_o4",
    }


def test_parallel_subflow_execution_raises_when_flow_contains_yielding_steps() -> None:
    with pytest.raises(ValueError, match="Flows ran in `ParallelFlowExecutionStep` cannot yield"):
        step = ParallelFlowExecutionStep(
            flows=[
                Flow.from_steps(steps=[InputMessageStep("hello")]),
                Flow.from_steps(steps=[OutputMessageStep("bye")]),
            ]
        )


def test_parallel_subflow_execution_cannot_yield():
    step = ParallelFlowExecutionStep(flows=[Flow.from_steps([OutputMessageStep("")])])
    assert step.might_yield is False


def test_step_raises_when_two_flows_have_inputs_with_same_name_but_different_types():
    tool_1 = ServerTool(
        name="n", description="d", input_descriptors=[ListProperty(name="i")], func=lambda: ""
    )
    tool_2 = ServerTool(
        name="n", description="d", input_descriptors=[IntegerProperty(name="i")], func=lambda: ""
    )
    with pytest.raises(
        ValueError,
        match="Two subflows in ParallelFlowExecutionStep have an input descriptor with the same name but different types:",
    ):
        ParallelFlowExecutionStep(
            flows=[
                Flow.from_steps([ToolExecutionStep(tool_1)]),
                Flow.from_steps([ToolExecutionStep(tool_2)]),
            ]
        )
