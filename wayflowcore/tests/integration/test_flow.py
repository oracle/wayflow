# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import anyio
import pytest

from wayflowcore import Flow
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.property import StringProperty
from wayflowcore.steps import (
    BranchingStep,
    InputMessageStep,
    OutputMessageStep,
    StartStep,
    ToolExecutionStep,
)
from wayflowcore.tools import tool

STEP_1 = OutputMessageStep(
    "{{step_name}}",
    input_descriptors=[StringProperty("step_name", default_value="step_1")],
    name="step_1",
    output_mapping={OutputMessageStep.OUTPUT: "output_1"},
)
STEP_2 = OutputMessageStep(
    "{{step_name}}",
    input_descriptors=[StringProperty("step_name", default_value="step_2")],
    name="step_2",
    output_mapping={OutputMessageStep.OUTPUT: "output_2"},
)
STEP_3 = OutputMessageStep(
    "{{step_name}}",
    input_descriptors=[StringProperty("step_name", default_value="step_3")],
    name="step_3",
    output_mapping={OutputMessageStep.OUTPUT: "output_3"},
)


def test_flow_without_input_descriptors_correctly_raises_an_exception_on_conflicting_names():
    with pytest.raises(
        ValueError, match="Some input descriptors have the same name but are different"
    ):
        flow = Flow.from_steps(steps=[STEP_1, STEP_2, STEP_3], input_descriptors=None)


def test_flow_with_no_input_descriptors_correctly_does_not_group_inputs_and_leverages_different_default_values():
    flow = Flow.from_steps(steps=[STEP_1, STEP_2, STEP_3], input_descriptors=[])
    conv = flow.start_conversation(inputs={})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {
        "output_1": "step_1",
        "output_2": "step_2",
        "output_3": "step_3",
    }


def test_flow_with_conflicting_input_names_still_works_with_start_step():
    start_step = StartStep(
        input_descriptors=[StringProperty(name="step_name", default_value="ohoh")]
    )
    flow = Flow.from_steps(
        steps=[start_step, STEP_1, STEP_2, STEP_3],
        input_descriptors=None,
        data_flow_edges=[
            DataFlowEdge(
                source_step=start_step,
                source_output="step_name",
                destination_step=step,
                destination_input="step_name",
            )
            for step in [STEP_1, STEP_2, STEP_3]
        ],
    )
    conv = flow.start_conversation(inputs={})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {
        "output_1": "ohoh",
        "output_2": "ohoh",
        "output_3": "ohoh",
    }


def test_flow_with_conflicting_input_names_still_works_with_specified_inputs():
    flow = Flow.from_steps(
        steps=[STEP_1, STEP_2, STEP_3],
        input_descriptors=[StringProperty(name="step_name", default_value="ohoh")],
    )
    conv = flow.start_conversation(inputs={})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {
        "output_1": "ohoh",
        "output_2": "ohoh",
        "output_3": "ohoh",
    }


def test_shared_variable_works():
    @tool(description_mode="only_docstring")
    def tool_1(experiment: str) -> str:
        """tool 1"""
        return experiment + "+1"

    @tool(description_mode="only_docstring", output_descriptors=[StringProperty(name="experiment")])
    def tool_2(experiment: str, consensus: str = "yes") -> str:
        """tool 2"""
        return experiment + "+2"

    step_1 = ToolExecutionStep(tool_1, name="tool1step")
    step_2 = ToolExecutionStep(tool_2, name="tool2step")
    step_3 = BranchingStep(
        branch_name_mapping={"hello+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2": "end"},
        name="branching",
        input_mapping={BranchingStep.NEXT_BRANCH_NAME: "experiment"},
    )

    flow = Flow(
        begin_step=step_1,
        control_flow_edges=[
            ControlFlowEdge(source_step=step_1, destination_step=step_2),
            ControlFlowEdge(source_step=step_2, destination_step=step_3),
            ControlFlowEdge(
                source_step=step_3,
                destination_step=step_1,
                source_branch=BranchingStep.BRANCH_DEFAULT,
            ),
            ControlFlowEdge(source_step=step_3, destination_step=None, source_branch="end"),
        ],
        input_descriptors=[
            StringProperty(name="experiment"),
            StringProperty(name="consensus", default_value="yes"),
        ],
    )
    conversation = flow.start_conversation(inputs={"experiment": "hello"})
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values["experiment"] == "hello+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2+2"


def test_shared_variable_works_if_overwritten_several_times():
    @tool(description_mode="only_docstring", output_descriptors=[StringProperty(name="experiment")])
    def tool_1(experiment: str) -> str:
        """tool 1"""
        return experiment + "+1"

    @tool(description_mode="only_docstring", output_descriptors=[StringProperty(name="experiment")])
    def tool_2(experiment: str, consensus: str = "yes") -> str:
        """tool 2"""
        return experiment + "+2"

    step_1 = ToolExecutionStep(tool_1, name="tool1step")
    step_2 = ToolExecutionStep(tool_2, name="tool2step")
    step_3 = BranchingStep(
        branch_name_mapping={"hello+1+2+1+2+1+2+1+2+1+2+1+2": "end"},
        name="branching",
        input_mapping={BranchingStep.NEXT_BRANCH_NAME: "experiment"},
    )

    flow = Flow(
        begin_step=step_1,
        control_flow_edges=[
            ControlFlowEdge(source_step=step_1, destination_step=step_2),
            ControlFlowEdge(source_step=step_2, destination_step=step_3),
            ControlFlowEdge(
                source_step=step_3,
                destination_step=step_1,
                source_branch=BranchingStep.BRANCH_DEFAULT,
            ),
            ControlFlowEdge(source_step=step_3, destination_step=None, source_branch="end"),
        ],
    )
    conversation = flow.start_conversation(inputs={"experiment": "hello"})
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values["experiment"] == "hello+1+2+1+2+1+2+1+2+1+2+1+2"


@pytest.mark.anyio
async def test_flow_run_async():
    flow = Flow.from_steps(
        steps=[
            InputMessageStep(message_template="what is 2+2"),
        ]
    )
    conversation = flow.start_conversation()
    status = await conversation.execute_async()
    assert isinstance(status, UserMessageRequestStatus)
    conversation.append_user_message("4")
    status = await conversation.execute_async()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {InputMessageStep.USER_PROVIDED_INPUT: "4"}


@tool(description_mode="only_docstring")
def my_tool() -> str:
    """Hello"""
    i = -1
    for i in range(10000):
        i += 3
    return ""


@pytest.mark.anyio
async def test_flow_with_many_steps():
    flow = Flow.from_steps(steps=[ToolExecutionStep(tool=my_tool) for _ in range(100)])

    async def _target():
        conversation = flow.start_conversation()
        await conversation.execute_async()

    async with anyio.create_task_group() as tg:
        for _ in range(50):
            tg.start_soon(_target)
