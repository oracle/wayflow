# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Dict, Optional

import pytest

from wayflowcore import Flow
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flowhelpers import _run_flow_and_return_status
from wayflowcore.steps import BranchingStep, CompleteStep


def run_navigation_assistant(
    navigation_step: BranchingStep,
    next_step: str,
    expected_step: str,
    default_next_step: Optional[str] = None,
) -> None:
    BRANCHING_STEP = "branching_step"

    other_steps = [
        step_name
        for step_name in navigation_step.get_branches()
        if step_name != BranchingStep.BRANCH_DEFAULT
    ]

    other_steps_dict = {step_name: CompleteStep() for step_name in other_steps}
    default_step = CompleteStep()
    flow = Flow(
        begin_step_name=BRANCHING_STEP,
        steps={
            BRANCHING_STEP: navigation_step,
            **other_steps_dict,
            default_next_step: default_step,
        },
        control_flow_edges=[
            ControlFlowEdge(
                source_step=navigation_step, source_branch=step_name, destination_step=step
            )
            for step_name, step in other_steps_dict.items()
        ]
        + [
            ControlFlowEdge(
                source_step=navigation_step,
                source_branch=BranchingStep.BRANCH_DEFAULT,
                destination_step=default_step,
            )
        ],
    )

    status = _run_flow_and_return_status(flow, inputs={BranchingStep.NEXT_BRANCH_NAME: next_step})
    assert isinstance(status, FinishedStatus)
    assert status.complete_step_name == expected_step


@pytest.mark.parametrize(
    "branch_name_mapping,input_next_step,expected_step_ran",
    [
        ({"wrong_fake_step": "fake_step_3"}, "wrong_fake_step", "fake_step_3"),
    ],
)
def test_navigation_step_returns_correct_next_step_with_remapping(
    branch_name_mapping: Dict[str, str], input_next_step: str, expected_step_ran: str
) -> None:
    run_navigation_assistant(
        navigation_step=BranchingStep(branch_name_mapping=branch_name_mapping),
        next_step=input_next_step,
        expected_step=expected_step_ran,
        default_next_step="fake_step_4",
    )


def test_navigation_step_returns_correct_next_step_with_default() -> None:
    run_navigation_assistant(
        navigation_step=BranchingStep(branch_name_mapping={}),
        next_step="wrong_fake_step",
        expected_step="fake_step_4",
        default_next_step="fake_step_4",
    )


def test_branching_step_might_not_yield() -> None:
    step = BranchingStep(branch_name_mapping={})
    assert not step.might_yield


def get_branching_flow(
    success_branch_name: Optional[str] = None,
    failure_branch_name: Optional[str] = None,
    default_branch_name: Optional[str] = None,
):
    start_step = BranchingStep(
        branch_name_mapping={
            "success": "success_branch",
            "failure": "failure_branch",
        },
    )
    external_success_step = CompleteStep(branch_name=success_branch_name)
    failure_branch = CompleteStep(branch_name=failure_branch_name)
    default_next_step = CompleteStep(branch_name=default_branch_name)
    return Flow(
        begin_step_name="start",
        steps={
            "start": start_step,
            "external_success_step": external_success_step,
            "failure_branch": failure_branch,
            "default_next_step": default_next_step,
        },
        control_flow_edges=[
            ControlFlowEdge(
                source_step=start_step,
                source_branch="success_branch",
                destination_step=external_success_step,
            ),
            ControlFlowEdge(
                source_step=start_step,
                source_branch="failure_branch",
                destination_step=failure_branch,
            ),
            ControlFlowEdge(
                source_step=start_step,
                source_branch=BranchingStep.BRANCH_DEFAULT,
                destination_step=default_next_step,
            ),
        ],
    )


@pytest.mark.parametrize(
    "branching_input,expected_last_step",
    [
        ("success", "external_success_step"),
        ("unknown", "default_next_step"),
        ("success_branch", "default_next_step"),
        ("failure", "failure_branch"),
    ],
)
def test_can_use_branches_mapping(branching_input, expected_last_step):
    flow = get_branching_flow()
    conv = flow.start_conversation(inputs={BranchingStep.NEXT_BRANCH_NAME: branching_input})
    status = flow.execute(conv)
    assert isinstance(status, FinishedStatus)
    assert status.complete_step_name == expected_last_step
