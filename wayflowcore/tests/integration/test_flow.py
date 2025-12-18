# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging

import anyio
import pytest

from wayflowcore import Flow
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.property import AnyProperty, DictProperty, StringProperty
from wayflowcore.steps import (
    BranchingStep,
    InputMessageStep,
    OutputMessageStep,
    StartStep,
    ToolExecutionStep,
)
from wayflowcore.tools import ServerTool, tool

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
        ValueError, match="Some flow input descriptors have the same name but are different"
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


def test_flow_with_subset_of_inputs_outputs_exposes_only_selected_inputs_and_outputs():
    map_tool = ServerTool(
        name="tool",
        description="tool",
        input_descriptors=[
            StringProperty(name="input_a"),
            StringProperty(name="input_b", default_value="hello"),
        ],
        output_descriptors=[StringProperty(name="output_a"), StringProperty(name="output_b")],
        func=lambda input_a, input_b: {"output_a": input_a, "output_b": input_b},
    )
    tool_step = ToolExecutionStep(name="tool_node", tool=map_tool)
    flow = Flow(
        name="flow",
        begin_step=tool_step,
        control_flow_edges=[ControlFlowEdge(source_step=tool_step, destination_step=None)],
        input_descriptors=[StringProperty(name="input_a")],
        output_descriptors=[StringProperty(name="output_a")],
    )

    assert len(flow.input_descriptors) == 1
    assert flow.input_descriptors[0].name == "input_a"
    assert len(flow.input_descriptors_dict) == 1
    assert "input_a" in flow.input_descriptors_dict

    assert len(flow.output_descriptors) == 1
    assert flow.output_descriptors[0].name == "output_a"
    assert len(flow.output_descriptors_dict) == 1
    assert "output_a" in flow.output_descriptors_dict

    conversation = flow.start_conversation(inputs={"input_a": "a"})
    state = conversation.execute()

    assert isinstance(state, FinishedStatus)
    assert len(state.output_values) == 1
    assert state.output_values["output_a"] == "a"


def test_flow_with_missing_input_without_default_raises_exception():
    output_step = OutputMessageStep(
        name="output_step",
        message_template="{{user_input}} {{missing_input}}",
    )
    with pytest.raises(
        ValueError,
        match="Step named `output_step` requires an input",
        # match="Step named `output_step` requires an input called `missing_input`, but no input with",
    ):
        _ = Flow(
            begin_step=output_step,
            control_flow_edges=[ControlFlowEdge(source_step=output_step, destination_step=None)],
            input_descriptors=[StringProperty(name="user_input")],
        )


def test_flow_with_missing_input_with_default_value_works():
    output_step = OutputMessageStep(
        name="output_step",
        message_template="{{user_input}} {{default_input}}",
        input_descriptors=[
            StringProperty(name="user_input"),
            StringProperty(name="default_input", default_value="hello"),
        ],
    )
    flow = Flow(
        begin_step=output_step,
        control_flow_edges=[ControlFlowEdge(source_step=output_step, destination_step=None)],
        input_descriptors=[StringProperty(name="user_input")],
    )

    assert len(flow.input_descriptors) == 1
    assert flow.input_descriptors[0].name == "user_input"
    assert len(flow.input_descriptors_dict) == 1
    assert "user_input" in flow.input_descriptors_dict


def test_steps_with_input_names_conflicts_raises_warning(caplog):
    caplog.set_level(logging.WARNING)

    step_1 = OutputMessageStep(message_template="{{i1}}")
    step_2 = OutputMessageStep(message_template="{{i1}}")
    flow = Flow.from_steps([step_1, step_2])

    assert "Make sure that these refer to the same input" in caplog.text


def test_steps_with_input_names_conflicts_with_different_types_raises_error():
    step_1 = OutputMessageStep(
        message_template="{{i1}}", input_descriptors=[AnyProperty(name="i1")]
    )
    step_2 = OutputMessageStep(
        message_template="{{i1}}", input_descriptors=[DictProperty(name="i1")]
    )

    with pytest.raises(ValueError, match="Their types are not compatible"):
        flow = Flow.from_steps([step_1, step_2])


def test_steps_with_input_names_conflicts_does_not_raises_warning_with_data_edges(caplog):
    caplog.set_level(logging.WARNING)

    step_1 = OutputMessageStep(message_template="{{i1}}")
    step_2 = OutputMessageStep(message_template="{{i1}}")
    start_step = StartStep(input_descriptors=[StringProperty(name="i1")])

    data_edges = [
        DataFlowEdge(
            source_step=start_step,
            source_output="i1",
            destination_step=step_1,
            destination_input="i1",
        ),
        DataFlowEdge(
            source_step=start_step,
            source_output="i1",
            destination_step=step_2,
            destination_input="i1",
        ),
    ]

    flow = Flow.from_steps([start_step, step_1, step_2], data_flow_edges=data_edges)
    assert "Make sure that these refer to the same input" not in caplog.text


def test_step_in_data_flow_edge_destination_is_not_mentioned_in_the_control_flow_edges():
    step_1 = OutputMessageStep(message_template="{{i1}}", name="step1")
    step_2 = OutputMessageStep(message_template="{{i2}}", name="step2")
    step_3 = OutputMessageStep(message_template="{{i3}}", name="step3")

    with pytest.raises(ValueError, match="The destination step `step3`"):
        flow = Flow(
            begin_step=step_1,
            control_flow_edges=[
                ControlFlowEdge(source_step=step_1, destination_step=step_2),
                ControlFlowEdge(source_step=step_2, destination_step=None),
            ],
            data_flow_edges=[
                DataFlowEdge(
                    source_step=step_1,
                    source_output=step_1.OUTPUT,
                    destination_step=step_3,
                    destination_input="i3",
                ),
                DataFlowEdge(
                    source_step=step_1,
                    source_output=step_1.OUTPUT,
                    destination_step=step_2,
                    destination_input="i2",
                ),
            ],
        )


def test_step_in_data_flow_edge_source_is_not_mentioned_in_the_control_flow_edges():
    step_1 = OutputMessageStep(message_template="{{i1}}", name="step1")
    step_2 = OutputMessageStep(message_template="{{i2}}", name="step2")
    step_3 = OutputMessageStep(message_template="{{i3}}", name="step3")

    with pytest.raises(ValueError, match="The source step `step3`"):
        flow = Flow(
            begin_step=step_1,
            control_flow_edges=[
                ControlFlowEdge(source_step=step_1, destination_step=step_2),
                ControlFlowEdge(source_step=step_2, destination_step=None),
            ],
            data_flow_edges=[
                DataFlowEdge(
                    source_step=step_3,
                    source_output=step_3.OUTPUT,
                    destination_step=step_1,
                    destination_input="i1",
                ),
                DataFlowEdge(
                    source_step=step_1,
                    source_output=step_1.OUTPUT,
                    destination_step=step_2,
                    destination_input="i2",
                ),
            ],
        )


def test_missing_step_input_needs_to_be_added_to_start_step_raises():
    start_step = StartStep(input_descriptors=[])
    step_1 = OutputMessageStep(message_template="{{i1}}", name="step1")
    step_2 = OutputMessageStep(message_template="{{i2}}", name="step2")

    with pytest.raises(ValueError, match="The flow requires the input descriptor"):
        flow = Flow(
            begin_step=start_step,
            control_flow_edges=[
                ControlFlowEdge(source_step=start_step, destination_step=step_1),
                ControlFlowEdge(source_step=step_1, destination_step=step_2),
                ControlFlowEdge(source_step=step_2, destination_step=None),
            ],
            data_flow_edges=[
                DataFlowEdge(
                    source_step=step_1,
                    source_output=step_1.OUTPUT,
                    destination_step=step_2,
                    destination_input="i2",
                )
            ],
        )


def test_node_in_control_flow_edge_not_in_steps_list():
    step_1 = OutputMessageStep(message_template="{{i1}}", name="step1")
    step_2 = OutputMessageStep(message_template="{{i2}}", name="step2")

    with pytest.raises(ValueError, match="The destination step in control flow edge"):
        flow = Flow(
            begin_step=step_1,
            steps=[step_1],
            control_flow_edges=[
                ControlFlowEdge(source_step=step_1, destination_step=step_2),
                ControlFlowEdge(source_step=step_2, destination_step=None),
            ],
        )


def test_node_in_data_flow_edge_not_in_steps_list():
    step_1 = OutputMessageStep(message_template="{{i1}}", name="step1")
    step_2 = OutputMessageStep(message_template="{{i2}}", name="step2")

    with pytest.raises(
        ValueError, match="The destination step `step2` present in the data flow edge"
    ):
        flow = Flow(
            begin_step=step_1,
            steps=[step_1],
            control_flow_edges=[
                ControlFlowEdge(source_step=step_1, destination_step=None),
            ],
            data_flow_edges=[
                DataFlowEdge(
                    source_step=step_1,
                    source_output=step_1.OUTPUT,
                    destination_step=step_2,
                    destination_input="i2",
                ),
            ],
        )


def test_node_does_not_have_incoming_edges():
    step_1 = OutputMessageStep(message_template="{{i1}}", name="step1")
    step_2 = OutputMessageStep(message_template="{{i2}}", name="step2")

    with pytest.raises(ValueError, match="No step is transitioning to step `step2`"):
        flow = Flow(
            begin_step=step_1,
            steps=[step_1, step_2],
            control_flow_edges=[
                ControlFlowEdge(source_step=step_1, destination_step=None),
            ],
        )


def test_node_does_not_have_outgoing_edges():
    step_1 = OutputMessageStep(message_template="{{i1}}", name="step1")
    step_2 = OutputMessageStep(message_template="{{i2}}", name="step2")

    with pytest.raises(ValueError, match="Transition is not specified for step"):
        flow = Flow(
            begin_step=step_1,
            steps=[step_1, step_2],
            control_flow_edges=[
                ControlFlowEdge(source_step=step_1, destination_step=step_2),
            ],
        )
