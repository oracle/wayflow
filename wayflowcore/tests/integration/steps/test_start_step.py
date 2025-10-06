# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import pytest

from wayflowcore import Agent
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty
from wayflowcore.steps import AgentExecutionStep, CompleteStep, OutputMessageStep, StartStep

from ...testhelpers.dummy import DummyModel
from ...testhelpers.teststeps import _InputOutputSpecifiedStep


def test_start_step_is_added_to_a_flow_if_missing():
    input_names = ["i1", "i2"]
    flow = Flow.from_steps(
        [_InputOutputSpecifiedStep(inputs=input_names, outputs=["o1"]), CompleteStep()]
    )
    assert len(flow.steps) == 3
    assert Flow._DEFAULT_STARTSTEP_NAME in flow.steps
    assert flow.begin_step_name == Flow._DEFAULT_STARTSTEP_NAME
    assert isinstance(flow.steps[flow.begin_step_name], StartStep)
    start_step_input_descriptors = flow.steps[flow.begin_step_name].input_descriptors
    assert input_names == [
        input_descriptor.name for input_descriptor in start_step_input_descriptors
    ]


def test_start_step_is_added_to_a_flow_if_missing_with_mapped_input_names():
    flow = Flow.from_steps(
        [
            OutputMessageStep(
                message_template="{{input_1_renamed}} {{input_2}}",
                input_mapping={"input_1_renamed": "input_1"},
            ),
            OutputMessageStep(
                message_template="{{input_2_renamed}} {{input_1}}",
                input_mapping={"input_2_renamed": "input_2"},
            ),
            CompleteStep(),
        ]
    )
    assert len(flow.steps) == 4
    assert Flow._DEFAULT_STARTSTEP_NAME in flow.steps
    assert flow.begin_step_name == Flow._DEFAULT_STARTSTEP_NAME
    assert isinstance(flow.steps[flow.begin_step_name], StartStep)
    start_step_input_descriptors = flow.steps[flow.begin_step_name].input_descriptors
    assert {"input_1", "input_2"} == {
        input_descriptor.name for input_descriptor in start_step_input_descriptors
    }


def test_start_step_with_subset_of_available_inputs():
    start_step = StartStep(input_descriptors=[StringProperty(name="i1"), StringProperty(name="i2")])
    flow = Flow.from_steps(
        [start_step, _InputOutputSpecifiedStep(inputs=["i1"], outputs=["o1"]), CompleteStep()]
    )
    assert len(flow.input_descriptors_dict) == 2
    assert all(input_ in flow.input_descriptors_dict for input_ in ("i1", "i2"))


def test_inputs_are_passed_correctly_when_start_step_has_io_mapping():
    steps = {
        "start_step": StartStep(
            input_descriptors=[StringProperty("i1")],
            input_mapping={"internal_useless_name": "i1"},
            output_mapping={"internal_useless_name": "renamed_i1"},
        ),
        "output_step": OutputMessageStep(message_template="{{renamed_i1}}"),
        "end_step": CompleteStep(),
    }
    control_flow_edges = [
        ControlFlowEdge(source_step=steps["start_step"], destination_step=steps["output_step"]),
        ControlFlowEdge(source_step=steps["output_step"], destination_step=steps["end_step"]),
    ]
    flow = Flow(
        steps=steps,
        begin_step_name="start_step",
        control_flow_edges=control_flow_edges,
    )
    assert len(flow.input_descriptors_dict) == 1
    assert "i1" in flow.input_descriptors_dict

    conversation = flow.start_conversation({"i1": "This is the output message!"})
    status = flow.execute(conversation=conversation)
    assert isinstance(status, FinishedStatus)
    assert conversation.get_last_message().content == "This is the output message!"


def test_inputs_are_passed_correctly_when_start_step_has_io_mapping_with_data_edges():
    steps = {
        "start_step": StartStep(
            input_descriptors=[StringProperty("i1")],
            input_mapping={"internal_name": "i1"},
            output_mapping={"internal_name": "renamed_i1"},
        ),
        "output_step": OutputMessageStep(message_template="{{renamed_i1}}"),
        "end_step": CompleteStep(),
    }
    control_flow_edges = [
        ControlFlowEdge(source_step=steps["start_step"], destination_step=steps["output_step"]),
        ControlFlowEdge(source_step=steps["output_step"], destination_step=steps["end_step"]),
    ]
    data_flow_edges = [
        DataFlowEdge(
            source_step=steps["start_step"],
            source_output="renamed_i1",
            destination_step=steps["output_step"],
            destination_input="renamed_i1",
        )
    ]
    flow = Flow(
        steps=steps,
        begin_step_name="start_step",
        control_flow_edges=control_flow_edges,
        data_flow_edges=data_flow_edges,
    )
    assert len(flow.input_descriptors_dict) == 1
    assert "i1" in flow.input_descriptors_dict

    conversation = flow.start_conversation({"i1": "This is the output message!"})
    status = flow.execute(conversation=conversation)
    assert isinstance(status, FinishedStatus)
    assert conversation.get_last_message().content == "This is the output message!"


def test_start_step_with_unavailable_input_raises():
    start_step = StartStep(input_descriptors=[StringProperty(name="i1"), StringProperty(name="i3")])
    with pytest.raises(ValueError):
        _ = Flow.from_steps(
            [
                start_step,
                _InputOutputSpecifiedStep(inputs=["i1", "nonexisting_input", "i3"], outputs=["o1"]),
                CompleteStep(),
            ]
        )


def test_start_step_works_with_default_input():
    start_step = StartStep(input_descriptors=[StringProperty(name="i1"), StringProperty(name="i3")])
    flow = Flow.from_steps(
        [
            start_step,
            _InputOutputSpecifiedStep(
                inputs=[
                    "i1",
                    StringProperty(name="default_input", default_value="default_value"),
                    "i3",
                ],
                outputs=["o1"],
            ),
            CompleteStep(),
        ]
    )
    assert len(flow.input_descriptors_dict) == 2
    assert all(input_ in flow.input_descriptors_dict for input_ in ("i1", "i3"))
    conversation = flow.start_conversation({"i1": "input value 1", "i3": "input value 3"})
    status = flow.execute(conversation=conversation)
    assert isinstance(status, FinishedStatus)


def test_start_step_with_complete_step_default_inputs():
    start_step = StartStep(input_descriptors=[])
    flow = Flow.from_steps(
        [
            start_step,
            AgentExecutionStep(Agent(llm=DummyModel())),
            CompleteStep(),
        ]
    )
    assert len(flow.input_descriptors_dict) == 0


def test_flow_with_multiple_start_steps_raises():
    with pytest.raises(ValueError):
        _ = Flow.from_steps([StartStep(), StartStep(), CompleteStep()])


def test_flow_with_control_flow_edge_destination_connected_to_start_steps_raises():
    with pytest.raises(ValueError):
        start_step = StartStep()
        io_step = _InputOutputSpecifiedStep(inputs=["i1"], outputs=["o1"])
        _ = Flow(
            begin_step_name="start_step",
            steps={
                "start_step": start_step,
                "io_step": io_step,
            },
            control_flow_edges=[
                ControlFlowEdge(source_step=start_step, destination_step=io_step),
                ControlFlowEdge(source_step=io_step, destination_step=start_step),
            ],
        )


def test_flow_with_start_step_not_set_as_begin_step_name_raises():
    with pytest.raises(ValueError):
        _ = Flow.from_steps(
            [_InputOutputSpecifiedStep(inputs=["i1"], outputs=["o1"]), StartStep(), CompleteStep()]
        )
