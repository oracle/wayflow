# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import contextlib
from dataclasses import dataclass
from typing import Annotated, Any, List
from unittest.mock import patch

import pytest

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import (
    run_flow_and_return_outputs,
    run_single_step,
    run_step_and_return_outputs,
)
from wayflowcore.property import (
    AnyProperty,
    BooleanProperty,
    DictProperty,
    FloatProperty,
    IntegerProperty,
    ListProperty,
    NullProperty,
    ObjectProperty,
    Property,
    StringProperty,
    UnionProperty,
    _cast_value_into,
)
from wayflowcore.steps import FlowExecutionStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.steps.step import StepResult
from wayflowcore.tools import tool

from ..testhelpers.teststeps import FakeStep, _InputOutputSpecifiedStep


def test_missing_2_input_values() -> None:
    with pytest.raises(ValueError):
        run_single_step(FakeStep())


def test_missing_input_value() -> None:
    with pytest.raises(ValueError):
        run_single_step(FakeStep(), {"input_1": ""})


def test_input_default_value() -> None:
    input_dict = {"input_1": "", "input_2": ""}
    conv, messages = run_single_step(FakeStep(), input_dict)
    input_dict.update({"input_3": "default_value"})
    assert messages[-1].content == str(input_dict)


def test_input_values() -> None:
    input_dict = {"input_1": "", "input_2": "", "input_3": ""}
    conv, messages = run_single_step(FakeStep(), input_dict)
    assert messages[-1].content == str(input_dict)


def test_unused_input_value() -> None:
    conv, messages = run_single_step(FakeStep(), {"input_1": "", "input_2": "", "input_3": ""})
    assert messages[-1].content == str({"input_1": "", "input_2": "", "input_3": ""})


def test_renamed_input_value() -> None:
    conv, messages = run_single_step(
        FakeStep(input_mapping={"input_2": "INPUT2"}),
        {"input_1": "", "INPUT2": "ahah", "input_3": ""},
    )
    assert messages[-1].content == str({"input_1": "", "input_2": "ahah", "input_3": ""})


def test_missing_output() -> None:
    step = OutputMessageStep("some message")
    with patch.object(
        step,
        "invoke_async",
        return_value=StepResult(
            outputs={},
        ),
    ):
        with pytest.raises(ValueError):
            run_single_step(step)


def test_additional_output() -> None:
    step = OutputMessageStep("some message")
    with patch.object(
        step,
        "invoke_async",
        return_value=StepResult(
            outputs={OutputMessageStep.OUTPUT: "some message", "additional_value": "something"},
        ),
    ):
        with pytest.warns(UserWarning):
            run_single_step(step)


# hard case, see design page
def test_check_input_and_outputs() -> None:
    STEP_B = "step_b"
    STEP_C = "step_c"
    STEP_D = "step_d"

    step_b = _InputOutputSpecifiedStep(inputs=["i1"], outputs=["o1"], branch_out=[STEP_C, STEP_D])
    step_c = _InputOutputSpecifiedStep(inputs=["o1", "i2"], outputs=["o2"])
    step_d = _InputOutputSpecifiedStep(inputs=["o1"], outputs=["o2", "o3"])

    flow = Flow(
        begin_step=step_b,
        steps={
            STEP_B: step_b,
            STEP_C: step_c,
            STEP_D: step_d,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=step_b, source_branch=STEP_C, destination_step=step_c),
            ControlFlowEdge(source_step=step_b, source_branch=STEP_D, destination_step=step_d),
            ControlFlowEdge(source_step=step_c, destination_step=None),
            ControlFlowEdge(source_step=step_d, destination_step=None),
        ],
    )
    assert set(descriptor.name for descriptor in flow.input_descriptors) == {"i1", "i2"}
    assert set(descriptor.name for descriptor in flow.output_descriptors) == {"o1", "o2"}


# edge case, see design page
def test_check_input_and_outputs_edge_case() -> None:
    STEP_A = "step_a"
    STEP_B = "step_b"
    STEP_C = "step_c"
    STEP_D = "step_d"
    STEP_E = "step_e"

    step_a = _InputOutputSpecifiedStep(outputs=["o1"], branch_out=[STEP_B, STEP_C])
    step_b = _InputOutputSpecifiedStep(inputs=["o1"], outputs=["o1", "o2", "o3", "o4"])
    step_c = _InputOutputSpecifiedStep(inputs=["o1"], outputs=["o2", "o5"])
    step_d = _InputOutputSpecifiedStep(outputs=["o4"])
    step_e = _InputOutputSpecifiedStep()

    flow = Flow(
        begin_step_name=STEP_A,
        steps={
            STEP_A: step_a,
            STEP_B: step_b,
            STEP_C: step_c,
            STEP_D: step_d,
            STEP_E: step_e,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=step_a, source_branch=STEP_B, destination_step=step_b),
            ControlFlowEdge(source_step=step_a, source_branch=STEP_C, destination_step=step_c),
            ControlFlowEdge(source_step=step_b, destination_step=step_e),
            ControlFlowEdge(source_step=step_c, destination_step=step_d),
            ControlFlowEdge(source_step=step_d, destination_step=step_e),
            ControlFlowEdge(source_step=step_e, destination_step=None),
        ],
    )
    assert len(set(descriptor.name for descriptor in flow.input_descriptors)) == 0
    assert set(flow.output_descriptors_dict.keys()) == {"o1", "o2", "o4"}


@pytest.fixture
def flow_with_inputs():
    return Flow.from_steps(
        [
            _InputOutputSpecifiedStep(outputs=["o1"]),
            _InputOutputSpecifiedStep(inputs=["o1", "o2"], outputs=["o3"]),
        ]
    )


def test_missing_input_when_instantiating_flow(flow_with_inputs: Flow) -> None:
    with pytest.raises(ValueError):
        conversation = flow_with_inputs.start_conversation()


def test_instantiating_flow_with_inputs(flow_with_inputs: Flow) -> None:
    conversation = flow_with_inputs.start_conversation({"o2": "ahah"})


@pytest.fixture
def flow_with_inputs_and_mapping():
    return Flow.from_steps(
        [
            _InputOutputSpecifiedStep(outputs=["o1"]),
            _InputOutputSpecifiedStep(
                inputs=["o1", "o2"], outputs=["o3"], input_mapping={"o2": "O2"}
            ),
        ]
    )


def test_missing_input_when_instantiating_flow_with_mapping(
    flow_with_inputs_and_mapping: Flow,
) -> None:
    with pytest.raises(ValueError):
        conversation = flow_with_inputs_and_mapping.start_conversation()


def test_instantiating_flow_with_inputs_with_mapping(
    flow_with_inputs_and_mapping: Flow,
) -> None:
    conversation = flow_with_inputs_and_mapping.start_conversation({"O2": "ahah"})


def test_flow_without_inputs() -> None:
    flow_without_inputs = Flow.from_steps([_InputOutputSpecifiedStep(outputs=["o1"])])
    conversation = flow_without_inputs.start_conversation()


def test_flow_raises_when_conversation_started_with_incorrect_type() -> None:
    flow_without_outputs = Flow.from_steps(
        [_InputOutputSpecifiedStep(inputs=[BooleanProperty(name="i1")])]
    )
    with pytest.raises(TypeError):
        conversation = flow_without_outputs.start_conversation({"i1": "something"})


def test_flow_without_outputs() -> None:
    flow_without_outputs = Flow.from_steps([_InputOutputSpecifiedStep(inputs=["i1"])])
    conversation = flow_without_outputs.start_conversation({"i1": ""})


def test_flow_without_inputs_and_outputs() -> None:
    flow_without_outputs = Flow.from_steps([_InputOutputSpecifiedStep()])
    conversation = flow_without_outputs.start_conversation()


@pytest.mark.parametrize(
    "output_value_type,output_value,input_value_type,should_fail",
    [
        (StringProperty(), "nah", StringProperty(), False),  # 0
        (  # 1
            ListProperty(item_type=StringProperty()),
            ["nah"],
            ListProperty(item_type=StringProperty()),
            False,
        ),
        (  # 2
            DictProperty(value_type=StringProperty()),
            {"nah": "nah"},
            DictProperty(value_type=StringProperty()),
            False,
        ),
        (  # 3
            ListProperty(item_type=ListProperty(item_type=StringProperty())),
            [["nah"]],
            ListProperty(item_type=ListProperty(item_type=StringProperty())),
            False,
        ),
        (StringProperty(), "nah", ListProperty(item_type=StringProperty()), True),  # 4
        (StringProperty(), ["nah"], ListProperty(item_type=StringProperty()), True),  # 5
        (ListProperty(item_type=StringProperty()), ["nah"], StringProperty(), False),  # 6
        (DictProperty(value_type=StringProperty()), {"nah": "nah"}, StringProperty(), False),  # 7
        # any can only be converted to any
        (AnyProperty(), ["nah"], ListProperty(item_type=StringProperty()), True),  # 8
        (ListProperty(item_type=StringProperty()), ["nah"], AnyProperty(), False),  # 9
        (AnyProperty(), ["nah"], AnyProperty(), False),  # 10
        (AnyProperty(), "nah", AnyProperty(), False),  # 11
        (
            StringProperty(),
            "nah",
            UnionProperty(any_of=[StringProperty(), IntegerProperty()]),
            False,
        ),  # 12
        (
            BooleanProperty(),
            True,
            UnionProperty(any_of=[IntegerProperty(), FloatProperty()]),
            False,
        ),  # 13
        (
            StringProperty(),
            "nah",
            UnionProperty(any_of=[IntegerProperty(), FloatProperty()]),
            True,
        ),  # 14
    ],
)
def test_flow_io_types(
    output_value_type: Property,
    output_value: Any,
    input_value_type: Property,
    should_fail: bool,
) -> None:
    with pytest.raises(TypeError) if should_fail else contextlib.nullcontext():
        input_var_name = "input_var_name"
        assistant = Flow.from_steps(
            [
                _InputOutputSpecifiedStep(
                    outputs=[output_value_type.copy(name=input_var_name)],
                    output_values={input_var_name: output_value},
                ),
                _InputOutputSpecifiedStep(
                    inputs=[input_value_type.copy(name=input_var_name)],
                ),
            ]
        )
        conversation = assistant.start_conversation({})
        assistant.execute(conversation)


@pytest.mark.parametrize(
    "template,input_mapping,output_mapping,inputs,expected_outputs",
    [
        (
            "{{var1}}{{var2}}",
            {"var1": "VAR1", "var2": "VAR2"},
            {OutputMessageStep.OUTPUT: "output1"},
            {"VAR1": "v1", "VAR2": "v2"},
            {"output1": "v1v2"},
        ),
        (
            "{{var1}}",
            {"var1": "VAR1"},
            {},
            {"VAR1": "v1"},
            {"output_message": "v1"},
        ),
        (
            "{{var1}}",
            {},
            {},
            {"var1": "v1"},
            {"output_message": "v1"},
        ),
    ],
)
def test_finished_status_contains_proper_outputs(
    template, input_mapping, output_mapping, inputs, expected_outputs
):
    assistant = Flow.from_steps(
        [
            OutputMessageStep(
                message_template=template,
                input_mapping=input_mapping,
                output_mapping=output_mapping,
            ),
        ]
    )
    output_values = run_flow_and_return_outputs(assistant, inputs=inputs)
    assert output_values == expected_outputs


@pytest.mark.parametrize(
    "template,input_mapping,output_mapping,subflow_input_mapping,subflow_output_mapping,inputs,expected_outputs",
    [
        (
            "{{var1}}{{var2}}",
            {"var1": "VAR1", "var2": "VAR2"},
            {OutputMessageStep.OUTPUT: "output1"},
            {},
            {},
            {"VAR1": "v1", "VAR2": "v2"},
            {"output1": "v1v2"},
        ),
        (
            "{{var1}}",
            {"var1": "VAR1"},
            {},
            {"VAR1": "SUB_VAR1"},
            {},
            {"SUB_VAR1": "v1"},
            {"output_message": "v1"},
        ),
        (
            "{{var1}}",
            {},
            {OutputMessageStep.OUTPUT: "some_output"},
            {"var1": "SUB_VAR1"},
            {"some_output": "SUB_OUTPUT"},
            {"SUB_VAR1": "v1"},
            {"SUB_OUTPUT": "v1"},
        ),
    ],
)
def test_finished_status_contains_proper_outputs_with_sub_flows(
    template,
    input_mapping,
    output_mapping,
    subflow_input_mapping,
    subflow_output_mapping,
    inputs,
    expected_outputs,
):
    assistant = Flow.from_steps(
        [
            FlowExecutionStep(
                flow=Flow.from_steps(
                    [
                        OutputMessageStep(
                            message_template=template,
                            input_mapping=input_mapping,
                            output_mapping=output_mapping,
                        ),
                    ]
                ),
                input_mapping=subflow_input_mapping,
                output_mapping=subflow_output_mapping,
            ),
        ]
    )
    output_values = run_flow_and_return_outputs(assistant, inputs=inputs)
    assert output_values == expected_outputs


def test_flow_has_default_name():
    auto_named_flow = Flow.from_steps([OutputMessageStep("")])
    assert "flow_" in auto_named_flow.name and len(auto_named_flow.name) == 19
    assert auto_named_flow.description == ""


def test_flow_name_and_description_can_be_changed():
    flow = Flow.from_steps([OutputMessageStep("")], name="flow_1", description="description_1")
    assert flow.name == "flow_1"
    assert flow.description == "description_1"
    flow_2 = flow.clone(
        name="flow_2",
        description="description_2",
    )
    assert flow.name == "flow_1"
    assert flow.description == "description_1"
    assert flow_2.name == "flow_2"
    assert flow_2.description == "description_2"


def test_flow_with_named_steps():
    step1 = OutputMessageStep("step1", name="step1")
    step2 = OutputMessageStep("step2", name="step2")
    step2bis = OutputMessageStep("{{input}}", name="step2bis")
    flow = Flow(
        begin_step=step1,
        control_flow_edges=[
            ControlFlowEdge(source_step=step1, destination_step=step2),
            ControlFlowEdge(source_step=step2, destination_step=step2bis),
            ControlFlowEdge(source_step=step2bis, destination_step=None),
        ],
        data_flow_edges=[
            DataFlowEdge(
                source_step=step2,
                source_output=step2.OUTPUT,
                destination_step=step2bis,
                destination_input="input",
            )
        ],
    )
    outputs = run_flow_and_return_outputs(flow)
    assert len(outputs)


def test_flow_raises_if_non_unique_step_names():
    step1 = OutputMessageStep("step1", name="step1")
    step2 = OutputMessageStep("step2", name="step1")
    with pytest.raises(ValueError):
        flow = Flow(
            begin_step=step1,
            control_flow_edges=[
                ControlFlowEdge(source_step=step1, destination_step=step2),
                ControlFlowEdge(source_step=step2, destination_step=None),
            ],
        )


@pytest.fixture
def step_returns_list_of_booleans():
    @tool
    def custom_tool() -> List[int]:
        """Tool to return a list"""
        return [1, 2, 3, 4, 5]

    return ToolExecutionStep(tool=custom_tool)


def test_flow_can_cast_inputs_to_expected_types(step_returns_list_of_booleans):
    output_step = OutputMessageStep(
        message_template="{{tool_output}}"
    )  # descriptor is by default str
    flow = Flow.from_steps([step_returns_list_of_booleans, output_step])
    outputs = run_flow_and_return_outputs(flow)
    assert outputs["output_message"] == "[1, 2, 3, 4, 5]"


def test_flow_raises_when_types_cannot_be_casted(step_returns_list_of_booleans):
    with pytest.raises(TypeError):
        output_step = OutputMessageStep(
            message_template="{{tool_output}}",
            input_descriptors=[BooleanProperty(name="tool_output")],
        )  # descriptor is by default str
        flow = Flow.from_steps([step_returns_list_of_booleans, output_step])


def test_flow_works_when_input_can_be_casted_to_proper_type():
    output_step = OutputMessageStep(
        message_template="{{tool_output}}"
    )  # descriptor is by default str
    flow = Flow.from_steps([output_step])
    outputs = run_flow_and_return_outputs(flow, inputs={"tool_output": [1, 2, 3, 4, 5]})
    assert outputs["output_message"] == "[1, 2, 3, 4, 5]"


def test_flow_raises_when_input_cannot_be_casted_to_proper_type():
    with pytest.raises(TypeError):
        output_step = OutputMessageStep(
            message_template="{{tool_output}}",
            input_descriptors=[BooleanProperty(name="tool_output")],
        )  # descriptor is by default str
        flow = Flow.from_steps([output_step])
        outputs = run_flow_and_return_outputs(flow, inputs={"tool_output": [1, 2, 3, 4, 5]})
        assert outputs["output_message"] == "[1, 2, 3, 4, 5]"


@dataclass
class CustomClass:
    field_1: int
    field_2: int


@pytest.mark.parametrize(
    "value, destination_type, expected_casted_value",
    [
        (True, BooleanProperty(), True),
        (True, IntegerProperty(), 1),
        (True, FloatProperty(), 1.0),
        (42, BooleanProperty(), True),
        (42, IntegerProperty(), 42),
        (42, FloatProperty(), 42.0),
        (42, StringProperty(), "42"),
        (14.4, BooleanProperty(), True),
        (14.4, IntegerProperty(), 14),
        (14.4, FloatProperty(), 14.4),
        (14.4, StringProperty(), "14.4"),
        ("hello", StringProperty(), "hello"),
        ([1, 2, 3], StringProperty(), "[1, 2, 3]"),
        ([1, 2, 3], ListProperty(item_type=IntegerProperty()), [1, 2, 3]),
        ([0, 1, 2], ListProperty(item_type=BooleanProperty()), [False, True, True]),
        ({True: "ahah"}, StringProperty(), '{"true": "ahah"}'),
        ({True: "ahah"}, DictProperty(key_type=BooleanProperty()), {True: "ahah"}),
        (
            {True: 1},
            DictProperty(key_type=BooleanProperty(), value_type=StringProperty()),
            {True: "1"},
        ),
        (
            {"field_1": "value_1", "field_2": 2},
            StringProperty(),
            '{"field_1": "value_1", "field_2": 2}',
        ),
        (
            {"field_1": 2, "field_2": 2},
            ObjectProperty(properties={"field_1": FloatProperty(), "field_2": StringProperty()}),
            {"field_1": 2.0, "field_2": "2"},
        ),
        (
            CustomClass(2, 2),
            ObjectProperty(properties={"field_1": FloatProperty(), "field_2": StringProperty()}),
            {"field_1": 2.0, "field_2": "2"},
        ),  # no changes
        ({2: [1, 2, "4", "5"]}, AnyProperty(), {2: [1, 2, "4", "5"]}),
        (True, UnionProperty(any_of=[IntegerProperty(), FloatProperty(), BooleanProperty()]), True),
        (True, UnionProperty(any_of=[IntegerProperty(), FloatProperty()]), 1),
    ],
)
def test_values_can_be_casted(
    value: Property, destination_type: Property, expected_casted_value: Any
):
    casted_value = _cast_value_into(value, destination_type)
    assert casted_value == expected_casted_value


def test_step_output_is_casted_to_proper_type_if_needed():
    @tool
    def some_tool() -> Annotated[bool, "some output"]:
        """Does something"""
        return 0  # type: ignore

    outputs = run_step_and_return_outputs(ToolExecutionStep(tool=some_tool))
    assert outputs["tool_output"] == False


def test_step_output_raises_when_output_cannot_be_casted_to_proper_type():
    @tool
    def some_tool() -> Annotated[bool, "some output"]:
        """Does something"""
        return "something"  # type: ignore

    with pytest.raises(ValueError):
        outputs = run_step_and_return_outputs(ToolExecutionStep(tool=some_tool))


def test_tool_with_none_default():
    @tool(description_mode="only_docstring")
    def some_tool(optional_arg: str = None) -> bool:
        """Does something"""
        return "something"  # type: ignore

    assert some_tool.input_descriptors == [
        UnionProperty(
            name="optional_arg",
            default_value=None,
            any_of=[
                StringProperty(),
                NullProperty(),
            ],
        )
    ]
