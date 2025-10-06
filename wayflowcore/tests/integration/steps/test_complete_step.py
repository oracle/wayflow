# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import pytest

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.property import StringProperty
from wayflowcore.steps import (
    BranchingStep,
    CompleteStep,
    FlowExecutionStep,
    OutputMessageStep,
    StartStep,
)

from ...testhelpers.teststeps import _InputOutputSpecifiedStep

STEP_A = "step_a"
STEP_B = "step_b"
STEP_C = "step_c"
COMPLETE_STEP = "complete_step"


def test_single_complete_step_in_a_flow():
    with pytest.raises(ValueError):
        flow = create_single_step_flow(CompleteStep())


def test_flow_starts_with_a_complete_step():
    with pytest.raises(ValueError):
        flow = Flow.from_steps(
            [CompleteStep(), _InputOutputSpecifiedStep(inputs=["i1"], outputs=["o1"])]
        )


def test_flat_flow_can_exit_with_none():
    flow = create_single_step_flow(_InputOutputSpecifiedStep(inputs=["i1"], outputs=["o1"]))
    conversation = flow.start_conversation(inputs={"i1": "i1"})
    execution_status = flow.execute(conversation)
    assert isinstance(execution_status, FinishedStatus)
    assert "o1" in execution_status.output_values


def test_flat_flow_can_exit_with_single_complete_step():
    step_a = _InputOutputSpecifiedStep(inputs=["i1"], outputs=["o1"])
    complete_step = CompleteStep()
    assistant = Flow(
        begin_step_name=STEP_A,
        steps={
            STEP_A: step_a,
            COMPLETE_STEP: complete_step,
        },
        control_flow_edges=[ControlFlowEdge(source_step=step_a, destination_step=complete_step)],
    )
    conversation = assistant.start_conversation(inputs={"i1": "i1"})
    execution_status = assistant.execute(conversation)
    assert isinstance(execution_status, FinishedStatus)
    assert "o1" in execution_status.output_values


def test_flat_flow_can_exit_with_several_complete_steps():
    step_a = BranchingStep(branch_name_mapping={"c1": "case1", "c2": "case2"})
    step_b = OutputMessageStep(message_template="hello")
    exit_1 = CompleteStep()
    exit_2 = CompleteStep()
    assistant = Flow(
        begin_step_name=STEP_A,
        steps={
            STEP_A: step_a,
            STEP_B: step_b,
            "exit1": exit_1,
            "exit2": exit_2,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=step_a, source_branch="case1", destination_step=step_b),
            ControlFlowEdge(source_step=step_a, source_branch="case2", destination_step=exit_2),
            ControlFlowEdge(
                source_step=step_a,
                source_branch=BranchingStep.BRANCH_DEFAULT,
                destination_step=exit_2,
            ),
            ControlFlowEdge(source_step=step_b, destination_step=exit_1),
        ],
    )
    conversation = assistant.start_conversation(inputs={"next_step_name": "c1"})
    execution_status = assistant.execute(conversation)
    assert isinstance(execution_status, FinishedStatus)
    assert conversation.get_last_message().content == "hello"


def test_nested_flow_can_exit_with_outer_steps_transitions():
    assistant = Flow.from_steps(
        [
            FlowExecutionStep(
                flow=Flow.from_steps(
                    steps=[
                        _InputOutputSpecifiedStep(inputs=["i1"], outputs=["o1"]),
                        CompleteStep(),
                    ],
                    step_names=[STEP_B, COMPLETE_STEP],
                ),
            ),
            _InputOutputSpecifiedStep(inputs=["o1"], outputs=["o2"]),
        ],
        step_names=[STEP_A, STEP_C],
    )
    conversation = assistant.start_conversation(inputs={"i1": "i1"})
    execution_status = assistant.execute(conversation)
    assert isinstance(execution_status, FinishedStatus)
    assert "o2" in execution_status.output_values


def test_complete_step_remaps_output_names() -> None:
    start_step = StartStep(name="start", input_descriptors=[StringProperty("input_1")])
    end_step = CompleteStep(name="end", input_descriptors=[StringProperty("renamed_input_1")])
    assistant = Flow.from_steps(
        steps=[start_step, end_step],
        data_flow_edges=[
            DataFlowEdge(
                source_step=start_step,
                source_output="input_1",
                destination_step=end_step,
                destination_input="renamed_input_1",
            )
        ],
    )
    conversation = assistant.start_conversation(inputs={"input_1": "abcdefg"})
    execution_status = assistant.execute(conversation)
    assert isinstance(execution_status, FinishedStatus)
    assert "renamed_input_1" in execution_status.output_values
    assert execution_status.output_values["renamed_input_1"] == "abcdefg"
