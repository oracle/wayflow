# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List, Optional, Tuple, Type

import pytest

from wayflowcore import Flow
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import BranchingStep, CompleteStep, ToolExecutionStep
from wayflowcore.steps.catchexceptionstep import CatchExceptionStep
from wayflowcore.tools import ClientTool, ServerTool

from ..test_agentcomposability import fooza_tool, zinimo_tool


def _create_tool_that_throws(exception: Type[Exception]):
    def raise_func():
        raise exception()

    return ServerTool(
        name=f"throws_{exception.__name__}",
        description=f"Will throw a {exception.__name__} exception",
        parameters={},
        output={"type": "string"},
        func=raise_func,
    )


def throw_if_needed_tool(caught_exceptions: list[Type[Exception]]):

    def throw_if_needed(exception: Exception):
        if isinstance(exception, tuple(caught_exceptions)):
            return "success"
        raise exception

    return ServerTool(
        name="throw_if_needed",
        description="throw if not caught",
        parameters={"exception": {}},
        output={"type": "string"},
        func=throw_if_needed,
    )


def create_inside_flow(
    exception_tools: List[Type[Exception]], except_on: List[str], catch_all_exceptions: bool = False
) -> Flow:
    tools = [_create_tool_that_throws(e) for e in exception_tools] + [fooza_tool, zinimo_tool]
    inner_flow = Flow.from_steps(
        [
            ToolExecutionStep(
                tool=t,
                raise_exceptions=True,
                output_mapping={ToolExecutionStep.TOOL_OUTPUT: t.name + "_output"},
            )
            for i, t in enumerate(tools)
        ]
    )
    catch_exception_step = CatchExceptionStep(
        flow=inner_flow,
        except_on={e: e for e in except_on},
        catch_all_exceptions=catch_all_exceptions,
    )
    steps = {
        "catch_exception_step": catch_exception_step,
        **{e: CompleteStep() for e in except_on},
    }
    control_flow_edges = [
        ControlFlowEdge(
            source_step=catch_exception_step, source_branch=e, destination_step=steps[e]
        )
        for e in except_on
    ] + [
        ControlFlowEdge(
            source_step=catch_exception_step,
            source_branch=CatchExceptionStep.BRANCH_NEXT,
            destination_step=None,
        )
    ]
    if catch_all_exceptions:
        control_flow_edges += [
            ControlFlowEdge(
                source_step=catch_exception_step,
                source_branch=CatchExceptionStep.DEFAULT_EXCEPTION_BRANCH,
                destination_step=None,
            )
        ]
    outer_flow = Flow(
        begin_step=catch_exception_step, steps=steps, control_flow_edges=control_flow_edges
    )
    return outer_flow


def runs_to_the_end(flow: Flow) -> Tuple[Dict[str, Any], Optional[str]]:
    conv = flow.start_conversation(inputs={"a": 5, "b": 6})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    return status.output_values, status.complete_step_name


def test_catch_exception_runs_without_exception():
    flow = create_inside_flow(exception_tools=[], except_on=[], catch_all_exceptions=False)
    outputs, last_step = runs_to_the_end(flow)
    assert outputs["zinimo_tool_output"] == 0
    assert outputs["fooza_tool_output"] == 27
    assert last_step == None


class MyCustomError(Exception):
    pass


@pytest.mark.parametrize(
    "exception",
    [
        ValueError,
        NotImplementedError,
        MyCustomError,
    ],
)
def test_catch_any_exception_runs(exception):
    flow = create_inside_flow(exception_tools=[exception], except_on=[], catch_all_exceptions=True)
    outputs, last_step = runs_to_the_end(flow)
    assert outputs[CatchExceptionStep.EXCEPTION_NAME_OUTPUT_NAME] == exception.__name__
    assert last_step is None


@pytest.mark.parametrize(
    "exception",
    [
        ValueError,
        NotImplementedError,
        MyCustomError,
    ],
)
def test_catch_step_throws_exceptions(exception):
    with pytest.raises(exception):
        flow = create_inside_flow(
            exception_tools=[exception], except_on=[], catch_all_exceptions=False
        )
        outputs, last_step = runs_to_the_end(flow)


@pytest.mark.parametrize(
    "exception",
    [
        ValueError,
        NotImplementedError,
        MyCustomError,
    ],
)
def test_catch_exception_runs_and_raises_expected_exception(exception):
    except_on = [
        ValueError.__name__,
        NotImplementedError.__name__,
        MyCustomError.__name__,
    ]
    flow = create_inside_flow(
        exception_tools=[exception], except_on=except_on, catch_all_exceptions=False
    )
    outputs, last_step = runs_to_the_end(flow)
    assert outputs[CatchExceptionStep.EXCEPTION_NAME_OUTPUT_NAME] == exception.__name__
    assert last_step == exception.__name__


def create_conditional_flow() -> Flow:
    branching_step = BranchingStep(branch_name_mapping={"1": "1", "2": "2"})
    step_ten = CompleteStep()
    step_twenty = CompleteStep()
    return Flow(
        begin_step=branching_step,
        steps={
            "0": branching_step,
            "10": step_ten,
            "20": step_twenty,
        },
        control_flow_edges=[
            ControlFlowEdge(
                source_step=branching_step, source_branch="1", destination_step=step_ten
            ),
            ControlFlowEdge(
                source_step=branching_step, source_branch="2", destination_step=step_twenty
            ),
            ControlFlowEdge(
                source_step=branching_step, source_branch="default", destination_step=None
            ),
        ],
    )


@pytest.mark.parametrize("branch", ["1", "2", "unknown"])
def test_catch_exception_step_with_conditional_branching_inside_works(branch):
    catch_step = CatchExceptionStep(
        flow=create_conditional_flow(),
    )
    step1 = CompleteStep()
    step2 = CompleteStep()
    unknown = CompleteStep()
    flow = Flow(
        begin_step=catch_step,
        steps={
            "catch": catch_step,
            "1": step1,
            "2": step2,
            "unknown": unknown,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=catch_step, source_branch="10", destination_step=step1),
            ControlFlowEdge(source_step=catch_step, source_branch="20", destination_step=step2),
            ControlFlowEdge(
                source_step=catch_step,
                source_branch=CatchExceptionStep.BRANCH_NEXT,
                destination_step=unknown,
            ),
        ],
    )
    conv = flow.start_conversation(inputs={BranchingStep.NEXT_BRANCH_NAME: branch})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.complete_step_name == branch


@pytest.mark.parametrize(
    "flow, except_on, catch_all_exceptions, expected_branches",
    [
        (
            create_single_step_flow(ToolExecutionStep(fooza_tool)),
            [ValueError.__name__],
            True,
            {
                CatchExceptionStep.BRANCH_NEXT,
                ValueError.__name__,
                CatchExceptionStep.DEFAULT_EXCEPTION_BRANCH,
            },
        ),
        (
            create_single_step_flow(ToolExecutionStep(fooza_tool)),
            [ValueError.__name__],
            False,
            {CatchExceptionStep.BRANCH_NEXT, ValueError.__name__},
        ),
        (
            create_single_step_flow(ToolExecutionStep(fooza_tool)),
            [ValueError.__name__, MyCustomError.__name__],
            True,
            {
                CatchExceptionStep.BRANCH_NEXT,
                MyCustomError.__name__,
                ValueError.__name__,
                CatchExceptionStep.DEFAULT_EXCEPTION_BRANCH,
            },
        ),
        (
            create_conditional_flow(),
            [ValueError.__name__, MyCustomError.__name__],
            True,
            {
                "10",
                "20",
                "next",
                MyCustomError.__name__,
                ValueError.__name__,
                CatchExceptionStep.DEFAULT_EXCEPTION_BRANCH,
            },
        ),
    ],
)
def test_catch_step_has_correct_branches(flow, except_on, catch_all_exceptions, expected_branches):
    step = CatchExceptionStep(
        flow=flow, except_on={e: e for e in except_on}, catch_all_exceptions=catch_all_exceptions
    )
    assert set(step.get_branches()) == expected_branches


@pytest.mark.parametrize(
    "flow,except_on,catch_all_exceptions,expected_inputs,expected_outputs,expected_branches",
    [
        (
            create_conditional_flow(),
            {ValueError.__name__: "value_error", MyCustomError.__name__: "my_custom_error"},
            True,
            {"next_step_name"},
            {"exception_name", "exception_payload_name"},
            {"default_exception_branch", "10", "20", "my_custom_error", "value_error", "next"},
        ),
        (
            create_single_step_flow(
                ToolExecutionStep(
                    tool=ClientTool(
                        name="tool", description="", parameters={"i1": {}, "i2": {}, "i3": {}}
                    ),
                    output_mapping={ToolExecutionStep.TOOL_OUTPUT: "my_output"},
                ),
            ),
            {ValueError.__name__: "value_error"},
            False,
            {"i1", "i2", "i3"},
            {"exception_name", "exception_payload_name", "my_output"},
            {
                "next",
                "value_error",
            },
        ),
        (
            create_single_step_flow(
                ToolExecutionStep(
                    tool=ClientTool(name="tool", description="", parameters={}),
                )
            ),
            None,
            False,
            set(),
            {"exception_name", "exception_payload_name", "tool_output"},
            {"next"},
        ),
    ],
)
def test_step_has_correct_input_and_output_descriptors(
    flow, except_on, catch_all_exceptions, expected_inputs, expected_outputs, expected_branches
) -> None:
    # Check that the configuration description looks like what we need
    configuration = {
        "input_mapping": None,
        "output_mapping": None,
        "input_descriptors": None,
        "output_descriptors": None,
        "flow": flow,
        "except_on": except_on,
        "catch_all_exceptions": catch_all_exceptions,
    }

    step = CatchExceptionStep(**configuration)
    assert isinstance(step, CatchExceptionStep)

    # check that input descriptors can be created
    input_descriptors = step.input_descriptors
    assert {i.name for i in input_descriptors} == expected_inputs

    # check that output descriptors can be created
    output_descriptors = step.output_descriptors
    assert {o.name for o in output_descriptors} == expected_outputs

    # check that next steps can be retrieved
    next_step_names = step.get_branches()
    assert set(next_step_names) == expected_branches
