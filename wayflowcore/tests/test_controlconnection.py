# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Optional

import pytest

from wayflowcore import Flow, Step
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.steps import BranchingStep, OutputMessageStep


def check_edge_can_be_instantiated(
    source_step: Step,
    destination_step: Optional[Step],
    source_branch: Optional[str] = None,
):
    kwargs = dict(
        source_step=source_step,
        destination_step=destination_step,
    )
    if source_branch is not None:
        kwargs["source_branch"] = source_branch
    return ControlFlowEdge(**kwargs)


def test_control_flow_edge_can_be_created_between_two_steps():
    check_edge_can_be_instantiated(OutputMessageStep(""), OutputMessageStep(""))


def test_control_flow_edge_can_be_created_between_one_single_step():
    step1 = OutputMessageStep("")
    check_edge_can_be_instantiated(step1, step1)


def test_control_flow_edge_can_be_created_between_one_step_and_none():
    check_edge_can_be_instantiated(OutputMessageStep(""), None)


def test_control_flow_edge_can_be_instantiated_with_source_branch():
    check_edge_can_be_instantiated(OutputMessageStep(""), None, OutputMessageStep.BRANCH_NEXT)


def test_control_flow_edge_can_be_instantiated_with_several_source_branch():
    step = BranchingStep(branch_name_mapping={"res1": "branch1"})
    check_edge_can_be_instantiated(step, None, step.BRANCH_DEFAULT)
    check_edge_can_be_instantiated(step, None, "branch1")


def test_control_flow_edge_raises_when_source_branch_doesnt_exist_on_source_step():
    with pytest.raises(ValueError, match="does not have a branch named"):
        check_edge_can_be_instantiated(OutputMessageStep(""), None, "unknown_branch")


def test_control_flow_edge_raises_when_source_or_destination_are_step_names():
    with pytest.raises(TypeError, match="a control flow edge must be a `Step`"):
        check_edge_can_be_instantiated("step1", None, "wrong_branch")

    with pytest.raises(TypeError, match="a control flow edge must be a `Step`"):
        check_edge_can_be_instantiated(OutputMessageStep(""), "step2", "wrong_branch")


def test_missing_all_control_flow_edges_of_step_raises():
    step_1 = OutputMessageStep()
    step_2 = OutputMessageStep()

    with pytest.raises(ValueError, match="Transition is not specified for step `step_2`"):
        flow = Flow(
            begin_step_name="step_1",
            steps={
                "step_1": step_1,
                "step_2": step_2,
            },
            control_flow_edges=[ControlFlowEdge(source_step=step_1, destination_step=step_2)],
        )


def test_duplicate_control_flow_edge_raises():
    step_1 = OutputMessageStep()

    with pytest.raises(
        ValueError, match="Found duplicate control flow edges with same `source_branch`"
    ):
        flow = Flow(
            begin_step_name="step_1",
            steps={
                "step_1": step_1,
            },
            control_flow_edges=[
                ControlFlowEdge(source_step=step_1, destination_step=None),
                ControlFlowEdge(source_step=step_1, destination_step=None),
            ],
        )


def test_missing_one_control_flow_edge_raises():
    step_1 = BranchingStep(branch_name_mapping={"o1": "o1", "o2": "o2"})

    with pytest.warns(UserWarning, match="Missing edge for branch `default` of step"):
        flow = Flow(
            begin_step_name="step_1",
            steps={
                "step_1": step_1,
            },
            control_flow_edges=[
                ControlFlowEdge(source_step=step_1, source_branch="o1", destination_step=None),
                ControlFlowEdge(source_step=step_1, source_branch="o2", destination_step=None),
            ],
        )
