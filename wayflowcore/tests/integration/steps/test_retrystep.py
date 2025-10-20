# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import Any, Dict, Optional

import pytest

from wayflowcore import Flow, Step
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import (
    _run_flow_and_return_status,
    _run_single_step_to_finish,
    create_single_step_flow,
    run_flow_and_return_outputs,
)
from wayflowcore.steps import CompleteStep, PromptExecutionStep, RetryStep, ToolExecutionStep
from wayflowcore.tools import ServerTool, tool

from ...testhelpers.testhelpers import retry_test
from ...testhelpers.teststeps import _AddCustomValuesToContextStep

SUCCESS_CONDITION_NAME = "success"


def create_inside_flow(
    success_condition: str,
    succeeds_on_nth_trial: int,
) -> Flow:

    class Counter:
        def __init__(self):
            self.counter = 0

        def increment(self):
            self.counter += 1
            return self.counter == succeeds_on_nth_trial

    return create_single_step_flow(
        ToolExecutionStep(
            tool=ServerTool(
                name="tool", description="tool", parameters={}, output={}, func=Counter().increment
            ),
            output_mapping={ToolExecutionStep.TOOL_OUTPUT: success_condition},
        )
    )


BRANCH_TAKEN = "branch_taken"


def create_retry_flow(
    flow: Flow,
    success_condition: str,
    success_next_step: Optional[str],
    failure_next_step: Optional[str],
    max_num_trials: int,
):
    retry_step_name = "retry_step_name"
    retry_step = RetryStep(
        flow=flow,
        success_condition=success_condition,
        max_num_trials=max_num_trials,
    )
    success_step = CompleteStep()
    failure_step = CompleteStep()
    steps = {
        retry_step_name: retry_step,
        success_next_step: success_step,
        failure_next_step: failure_step,
    }
    control_flow_edges = [
        ControlFlowEdge(
            source_step=retry_step,
            source_branch=RetryStep.BRANCH_NEXT,
            destination_step=success_step,
        ),
        ControlFlowEdge(
            source_step=retry_step,
            source_branch=RetryStep.BRANCH_FAILURE,
            destination_step=failure_step,
        ),
    ]

    return Flow(begin_step_name=retry_step_name, steps=steps, control_flow_edges=control_flow_edges)


@pytest.fixture
def default_flow():
    return create_inside_flow(success_condition=SUCCESS_CONDITION_NAME, succeeds_on_nth_trial=1)


def test_max_num_trials_negative_value(default_flow):
    with pytest.raises(ValueError):
        RetryStep(
            flow=default_flow,
            success_condition=SUCCESS_CONDITION_NAME,
            max_num_trials=-1,
        )


def test_max_num_trials_is_too_high(default_flow):
    with pytest.raises(ValueError):
        RetryStep(
            flow=default_flow,
            success_condition=SUCCESS_CONDITION_NAME,
            max_num_trials=100,
        )


def _run_single_step_to_finish(
    step: Step,
    success_step: str = RetryStep.BRANCH_NEXT,
    failure_step: str = RetryStep.BRANCH_FAILURE,
) -> Dict[str, Any]:
    branching_step = "branching_step"
    success_step_instance = CompleteStep()
    failure_step_instance = CompleteStep()
    flow = Flow(
        begin_step_name=branching_step,
        steps={
            branching_step: step,
            success_step: success_step_instance,
            failure_step: failure_step_instance,
        },
        control_flow_edges=[
            ControlFlowEdge(
                source_step=step,
                source_branch=RetryStep.BRANCH_NEXT,
                destination_step=success_step_instance,
            ),
            ControlFlowEdge(
                source_step=step,
                source_branch=RetryStep.BRANCH_FAILURE,
                destination_step=failure_step_instance,
            ),
        ],
    )
    return run_flow_and_return_outputs(flow)


def test_only_allow_single_trial():
    outputs = _run_single_step_to_finish(
        step=RetryStep(
            flow=create_inside_flow(SUCCESS_CONDITION_NAME, 1),
            success_condition=SUCCESS_CONDITION_NAME,
            max_num_trials=1,
        )
    )
    assert outputs[RetryStep.SUCCESS_VAR]
    assert outputs[RetryStep.NUM_RETRIES_VAR] == 1


@pytest.mark.parametrize(
    "n,max_num_trials,expected_success",
    [
        (0, 0, False),
        (0, 1, False),
        (0, 10, False),
        (1, 1, True),
        (2, 1, False),
        (3, 4, True),
        (4, 4, True),
        (5, 4, False),
    ],
)
def test_retry_step_behaves_as_expected_without_exception(n, max_num_trials, expected_success):
    success_step_name = "my_success_step"
    failure_step_name = "failure_next_step"
    flow = create_retry_flow(
        flow=create_inside_flow(SUCCESS_CONDITION_NAME, n),
        success_condition=SUCCESS_CONDITION_NAME,
        success_next_step=success_step_name,
        failure_next_step=failure_step_name,
        max_num_trials=max_num_trials,
    )
    status = _run_flow_and_return_status(flow=flow)
    assert isinstance(status, FinishedStatus)
    assert status.complete_step_name == (
        success_step_name if expected_success else failure_step_name
    )


def test_inside_flow_do_not_return_success_condition():
    with pytest.raises(ValueError):
        RetryStep(
            flow=create_inside_flow("unknown_condition", 10),
            success_condition=SUCCESS_CONDITION_NAME,
        )


@pytest.mark.parametrize(
    "condition_value,expected_success",
    [
        (True, True),
        (False, False),
        ("", False),
        ("False", True),
        ([], False),
        (["something"], True),
        (0, False),
        (1, True),
    ],
)
def test_retry_step_with_success_conditions(condition_value, expected_success):
    success_step_name = "my_success_step"
    failure_step_name = "failure_next_step"
    flow = create_retry_flow(
        flow=create_single_step_flow(
            step=_AddCustomValuesToContextStep(
                expected_outputs={SUCCESS_CONDITION_NAME: condition_value}
            )
        ),
        success_condition=SUCCESS_CONDITION_NAME,
        success_next_step=success_step_name,
        failure_next_step=failure_step_name,
        max_num_trials=1,
    )
    status = _run_flow_and_return_status(flow=flow)
    assert isinstance(status, FinishedStatus)
    assert status.complete_step_name == (
        success_step_name if expected_success else failure_step_name
    )


@retry_test(max_attempts=2)  # should not fail it's an LLM so retry should be mandatory
def test_feedback_loop(remotely_hosted_llm):
    """
    Failure rate:          0 out of 100
    Observed on:           2024-11-26
    Average success time:  0.40 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           2
    Justification:         (0.01 ** 2) ~= 9.6 / 100'000
    """

    class NumberGuesser:
        def __init__(self, number: int):
            self.number = number
            self.tried_numbers = []

        def check(self, n: str) -> bool:
            """Check if it is the right number"""
            result = n == str(self.number)
            if not result:
                self.tried_numbers += n
            return result

        def give_hint(self) -> str:
            """Returns hints about what number were tried"""
            return "\n".join(f"It is not {n}" for n in self.tried_numbers)

    guesser = NumberGuesser(2)

    guess_one_round = Flow.from_steps(
        steps=[
            PromptExecutionStep(
                llm=remotely_hosted_llm,
                prompt_template="""\
        Guess a number inside [0,3]. Just return the number.

        {% if hint %}{{hint}}{% endif %}
        """,
                output_mapping={PromptExecutionStep.OUTPUT: "n"},
            ),
            ToolExecutionStep(
                tool=tool(guesser.check, description_mode="only_docstring"),
                output_mapping={ToolExecutionStep.TOOL_OUTPUT: "correct"},
            ),
            ToolExecutionStep(
                tool=tool(guesser.give_hint, description_mode="only_docstring"),
                output_mapping={ToolExecutionStep.TOOL_OUTPUT: "hint"},
            ),
        ]
    )

    retry_step = RetryStep(flow=guess_one_round, success_condition="correct", max_num_trials=5)

    outputs = _run_single_step_to_finish(retry_step)
    assert outputs[RetryStep.SUCCESS_VAR] == True


@pytest.mark.parametrize(
    "succeeds_on_x,expected_last_step",
    [
        (3, "failure"),
        (2, "failure"),
        (1, "success"),
    ],
)
def test_can_use_branches_mapping(succeeds_on_x, expected_last_step):
    next_step_names = ["failure", "success"]
    retry_step = RetryStep(
        success_condition="cond",
        flow=create_inside_flow("cond", succeeds_on_nth_trial=succeeds_on_x),
        max_num_trials=1,
    )
    success_step = CompleteStep()
    failure_step = CompleteStep()
    flow = Flow(
        begin_step_name="start",
        steps={
            "start": retry_step,
            "success": success_step,
            "failure": failure_step,
        },
        control_flow_edges=[
            ControlFlowEdge(
                source_step=retry_step,
                source_branch=retry_step.BRANCH_NEXT,
                destination_step=success_step,
            ),
            ControlFlowEdge(
                source_step=retry_step,
                source_branch=retry_step.BRANCH_FAILURE,
                destination_step=failure_step,
            ),
        ],
    )
    conv = flow.start_conversation()
    status = flow.execute(conv)
    assert isinstance(status, FinishedStatus)
    assert status.complete_step_name == expected_last_step
