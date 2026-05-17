# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List, Optional

import pytest

from wayflowcore import Tool
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import run_step_and_return_outputs
from wayflowcore.property import IntegerProperty, ListProperty, Property, StringProperty
from wayflowcore.steps import InputMessageStep, OutputMessageStep, StartStep, ToolExecutionStep
from wayflowcore.steps.parallelflowexecutionstep import ParallelFlowExecutionStep
from wayflowcore.steps.step import Step, StepResult
from wayflowcore.tools import ServerTool


class _EchoValueStep(Step):
    def __init__(self, output_name: str, name: Optional[str] = None) -> None:
        self.output_name = output_name
        self.seen_values: List[str] = []
        super().__init__(
            step_static_configuration={"output_name": output_name},
            name=name,
        )

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: Any,
    ) -> StepResult:
        value = inputs["value"]
        self.seen_values.append(value)
        return StepResult(outputs={self.output_name: value})

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        return {"output_name": str}

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls, output_name: str
    ) -> List[Property]:
        return [StringProperty(name="value")]

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls, output_name: str
    ) -> List[Property]:
        return [StringProperty(name=output_name)]


class _LoopParallelResultStep(Step):
    BRANCH_REPEAT = "repeat"
    BRANCH_DONE = "done"
    _COUNT_KEY = "loop_parallel_result_step_count"

    def __init__(self, next_value: str, name: Optional[str] = None) -> None:
        self.next_value = next_value
        self.seen_outputs: List[Dict[str, Any]] = []
        super().__init__(
            step_static_configuration={"next_value": next_value},
            name=name,
        )

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: Any,
    ) -> StepResult:
        count = (
            conversation._get_internal_context_value_for_step(
                self,
                self._COUNT_KEY,
            )
            or 0
        )
        conversation._put_internal_context_key_value_for_step(
            self,
            self._COUNT_KEY,
            count + 1,
        )
        self.seen_outputs.append(dict(inputs))
        return StepResult(
            outputs={"value": self.next_value},
            branch_name=self.BRANCH_REPEAT if count == 0 else self.BRANCH_DONE,
        )

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        return {"next_value": str}

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls, next_value: str
    ) -> List[Property]:
        return [StringProperty(name="out_a"), StringProperty(name="out_b")]

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls, next_value: str
    ) -> List[Property]:
        return [StringProperty(name="value")]

    @classmethod
    def _compute_internal_branches_from_static_config(
        cls,
        next_value: str,
    ) -> List[str]:
        return [cls.BRANCH_REPEAT, cls.BRANCH_DONE]


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


def test_parallel_subflow_reentry_recreates_finished_sub_conversations() -> None:
    start_step = StartStep(
        input_descriptors=[StringProperty(name="value")],
        name="start",
    )
    subflow_a_step = _EchoValueStep(output_name="out_a", name="echo_a")
    subflow_b_step = _EchoValueStep(output_name="out_b", name="echo_b")
    parallel_step = ParallelFlowExecutionStep(
        flows=[
            Flow.from_steps([subflow_a_step], name="echo_a_flow"),
            Flow.from_steps([subflow_b_step], name="echo_b_flow"),
        ],
        max_workers=1,
        name="parallel",
    )
    loop_step = _LoopParallelResultStep(next_value="second", name="loop")
    flow = Flow(
        begin_step=start_step,
        control_flow_edges=[
            ControlFlowEdge(source_step=start_step, destination_step=parallel_step),
            ControlFlowEdge(source_step=parallel_step, destination_step=loop_step),
            ControlFlowEdge(
                source_step=loop_step,
                source_branch=_LoopParallelResultStep.BRANCH_REPEAT,
                destination_step=parallel_step,
            ),
            ControlFlowEdge(
                source_step=loop_step,
                source_branch=_LoopParallelResultStep.BRANCH_DONE,
                destination_step=None,
            ),
        ],
        data_flow_edges=[
            DataFlowEdge(start_step, "value", parallel_step, "value"),
            DataFlowEdge(loop_step, "value", parallel_step, "value"),
            DataFlowEdge(parallel_step, "out_a", loop_step, "out_a"),
            DataFlowEdge(parallel_step, "out_b", loop_step, "out_b"),
        ],
    )

    status = flow.start_conversation(inputs={"value": "first"}).execute()

    assert isinstance(status, FinishedStatus)
    assert subflow_a_step.seen_values == ["first", "second"]
    assert subflow_b_step.seen_values == ["first", "second"]
    assert loop_step.seen_outputs == [
        {"out_a": "first", "out_b": "first"},
        {"out_a": "second", "out_b": "second"},
    ]


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
