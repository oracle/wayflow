# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import List, Optional, Tuple, Union

import pytest

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import (
    _run_flow_and_return_status,
    create_single_step_flow,
    run_flow_and_return_outputs,
)
from wayflowcore.models.llmmodel import LlmModel
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.steps import ChoiceSelectionStep, CompleteStep, InputMessageStep, OutputMessageStep

from ...testhelpers.dummy import DummyModel
from ...testhelpers.flowscriptrunner import (
    AnswerCheck,
    FlowScript,
    FlowScriptInteraction,
    FlowScriptRunner,
)
from ...testhelpers.testhelpers import retry_test


def create_choiceselectionstep_assistant(
    llm: LlmModel,
    next_steps: List[Union[Tuple[str, str], Tuple[str, str, str]]],
    default_step: Optional[str] = None,
) -> Flow:

    begin_step_name = "begin"
    choice_step = "choice"

    next_step_names = {v[0]: v[0] for v in next_steps}
    next_step_names[ChoiceSelectionStep.BRANCH_DEFAULT] = default_step

    steps = {
        begin_step_name: InputMessageStep(
            "What do you want to do?",
            output_mapping={InputMessageStep.USER_PROVIDED_INPUT: ChoiceSelectionStep.INPUT},
        ),
        choice_step: ChoiceSelectionStep(
            llm=llm,
            next_steps=next_steps,
            num_tokens=7,
        ),
    }
    transitions = {begin_step_name: [choice_step, begin_step_name], choice_step: next_step_names}
    for step_name in next_step_names.values():
        steps[step_name] = OutputMessageStep(message_template=str(step_name))
        transitions[step_name] = [None]

    return Flow(begin_step_name=begin_step_name, steps=steps, transitions=transitions)


def run_choice_selection(
    possible_next_steps: List[Union[Tuple[str, str, str], Tuple[str, str]]],
    default_step: Optional[str],
    llm_output: str,
    expected_next_step: str,
) -> None:
    llm = DummyModel()
    llm.set_next_output(llm_output)
    # assistant = create_choiceselectionstep_assistant(llm, possible_next_steps, default_step)
    next_step_names = [p[0] for p in possible_next_steps]

    choice_step = ChoiceSelectionStep(
        llm=llm,
        next_steps=possible_next_steps,
        num_tokens=7,
    )

    steps = {
        "choice": choice_step,
        **{step_name: CompleteStep() for step_name in next_step_names},
        **({default_step: CompleteStep()} if default_step is not None else {}),
    }
    flow = Flow(
        begin_step_name="choice",
        steps=steps,
        control_flow_edges=[
            ControlFlowEdge(
                source_step=choice_step, destination_step=steps[step_name], source_branch=step_name
            )
            for step_name in next_step_names
        ]
        + [
            ControlFlowEdge(
                source_step=choice_step,
                source_branch=ChoiceSelectionStep.BRANCH_DEFAULT,
                destination_step=steps.get(default_step, None),
            )
        ],
    )
    status = _run_flow_and_return_status(flow, inputs={ChoiceSelectionStep.INPUT: ""})
    assert isinstance(status, FinishedStatus)
    assert status.complete_step_name == expected_next_step


POSSIBLE_NEXT_STEPS = [("step1", "STEP1_DESCR"), ("step2", "STEP2_DESCR")]


@pytest.mark.parametrize(
    "llm_output,expected_next_step",
    [
        ("step1", "step1"),
        ("step2", "step2"),
    ],
)
def test_choice_selection_works(llm_output: str, expected_next_step: str) -> None:
    run_choice_selection(
        possible_next_steps=POSSIBLE_NEXT_STEPS,
        default_step=None,
        llm_output=llm_output,
        expected_next_step=expected_next_step,
    )


@pytest.mark.parametrize(
    "default_step,llm_output,expected_next_step",
    [
        ("step1", "unknown_step", "step1"),
        ("step2", "unknown_step", "step2"),
        ("step1", "step2", "step2"),
    ],
)
def test_choice_selection_uses_default_step(
    default_step: str, llm_output: str, expected_next_step: str
) -> None:
    run_choice_selection(
        possible_next_steps=POSSIBLE_NEXT_STEPS,
        default_step=default_step,
        llm_output=llm_output,
        expected_next_step=expected_next_step,
    )


@pytest.mark.parametrize(
    "llm_output,expected_next_step",
    [
        ("STEP1", "step1"),
        ("step1", "default_test_step"),
        ("step2", "step2"),
    ],
)
def test_choice_selection_uses_displayed_names(llm_output: str, expected_next_step: str) -> None:
    next_steps = [
        ("step1", "STEP1_DESCR", "STEP1"),
        ("step2", "STEP2_DESCR"),
        ("some_default", "default_descr"),
    ]
    run_choice_selection(
        possible_next_steps=next_steps,
        default_step="default_test_step",
        llm_output=llm_output,
        expected_next_step=expected_next_step,
    )


@pytest.mark.parametrize(
    "llm_output,expected_next_step",
    [
        ("choice1", "choice1"),
        ("default", "something"),
        ("unknown", "something"),
    ],
)
def test_choice_selection_step_works_when_some_next_step_has_default_name(
    llm_output, expected_next_step
):
    next_steps = [
        ("choice1", "descr choice 1"),
        ("default", "if nothing found"),
    ]

    llm = DummyModel()
    llm.set_next_output(llm_output)
    choice_step = ChoiceSelectionStep(
        llm=llm,
        next_steps=next_steps,
        num_tokens=7,
    )
    choice1_step = CompleteStep()
    default_step = CompleteStep()

    flow = Flow(
        begin_step_name="step",
        steps={
            "step": choice_step,
            "choice1": choice1_step,
            "something": default_step,
        },
        control_flow_edges=[
            ControlFlowEdge(
                source_step=choice_step, source_branch="choice1", destination_step=choice1_step
            ),
            ControlFlowEdge(
                source_step=choice_step, source_branch="default", destination_step=default_step
            ),
        ],
    )
    status = _run_flow_and_return_status(flow, inputs={ChoiceSelectionStep.INPUT: ""})
    assert isinstance(status, FinishedStatus)
    assert status.complete_step_name == expected_next_step


@pytest.mark.parametrize(
    "llm_output,expected_next_step",
    [
        (".*", ".*"),
        ("$?/", "step3"),
        ("step1", "step1"),
    ],
)
def test_choice_selection_works_with_step_names_containing_special_characters(
    llm_output: str, expected_next_step: str
) -> None:
    next_steps = [("step1", "descr1"), (".*", "descr2"), ("step3", "descr3", "$?/")]
    run_choice_selection(
        possible_next_steps=next_steps,
        default_step=None,
        llm_output=llm_output,
        expected_next_step=expected_next_step,
    )


def test_choice_selection_step_works_with_custom_template() -> None:
    llm = DummyModel()
    llm.set_next_output("choice_1")
    step = ChoiceSelectionStep(
        llm=llm,
        prompt_template=(
            "Instruction: {{customer_weird_variable}}\n"
            "Steps:\n"
            "{% for desc in next_steps -%}"
            "- {{ desc.displayed_step_name }}: {{ desc.description }}\n"
            "{% endfor -%}"
        ),
        next_steps=[("exit", "", "choice_1")],
    )
    choice_step = "choice_step"
    flow = create_single_step_flow(step, step_name=choice_step)
    run_flow_and_return_outputs(flow=flow, inputs={"customer_weird_variable": "something"})


def test_choice_selection_step_might_not_yield() -> None:
    step = ChoiceSelectionStep(
        llm=DummyModel(),
        next_steps=POSSIBLE_NEXT_STEPS,
    )
    assert not step.might_yield


@retry_test(max_attempts=5)
def test_looping_with_choice_selection_step(remotely_hosted_llm: VllmModel) -> None:
    """
    Failure rate:          5 out of 50
    Observed on:           2025-08-18
    Average success time:  1.09 seconds per successful attempt
    Average failure time:  0.90 seconds per failed attempt
    Max attempt:           5
    Justification:         (0.12 ** 5) ~= 2.0 / 100'000
    """

    USER_INPUT_STEP = "user_input_step"
    CHOICE_SELECTION_STEP = "choice_selection_step"
    COMPLETE_STEP = "end_step"

    user_input_step = InputMessageStep(
        "Is this content correct?",
        output_mapping={InputMessageStep.USER_PROVIDED_INPUT: "input"},
    )
    choice_selection_step = ChoiceSelectionStep(
        llm=remotely_hosted_llm,
        next_steps=[
            (COMPLETE_STEP, "the content is correct", "confirm"),
            (USER_INPUT_STEP, "the content is not correct, need to retry", "retry"),
        ],
    )
    complete_step = OutputMessageStep("Content successfully confirmed!")

    assistant = Flow(
        begin_step_name=USER_INPUT_STEP,
        steps={
            USER_INPUT_STEP: user_input_step,
            CHOICE_SELECTION_STEP: choice_selection_step,
            COMPLETE_STEP: complete_step,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=user_input_step, destination_step=choice_selection_step),
            ControlFlowEdge(
                source_step=choice_selection_step,
                destination_step=complete_step,
                source_branch=COMPLETE_STEP,
            ),
            ControlFlowEdge(
                source_step=choice_selection_step,
                destination_step=user_input_step,
                source_branch=USER_INPUT_STEP,
            ),
            ControlFlowEdge(
                source_step=choice_selection_step,
                destination_step=None,
                source_branch=ChoiceSelectionStep.BRANCH_DEFAULT,
            ),
            ControlFlowEdge(source_step=complete_step, destination_step=None),
        ],
    )

    flow_script = FlowScript(
        interactions=[
            FlowScriptInteraction(user_input=None),
            FlowScriptInteraction(user_input="NO, the content is not correct"),
            FlowScriptInteraction(user_input="NO, the content is not correct"),
            FlowScriptInteraction(
                user_input="YES, the content is correct",
                checks=[AnswerCheck("Content successfully confirmed!")],
                is_last=True,
            ),
        ]
    )

    runner = FlowScriptRunner(assistants=[assistant], flow_scripts=[flow_script])
    runner.execute(raise_exceptions=True)
