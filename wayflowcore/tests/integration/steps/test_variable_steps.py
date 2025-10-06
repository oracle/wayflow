# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import pytest
from _pytest.fixtures import FixtureRequest

from wayflowcore.executors._flowexecutor import FlowConversationExecutionState
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.property import DictProperty, FloatProperty, ListProperty, StringProperty
from wayflowcore.steps import ToolExecutionStep, VariableReadStep, VariableWriteStep
from wayflowcore.steps.inputmessagestep import InputMessageStep
from wayflowcore.tools import tool
from wayflowcore.variable import Variable, VariableWriteOperation


@pytest.fixture
def float_variable() -> Variable:
    return Variable(
        name="float_variable",
        type=FloatProperty(),
        description="a float variable",
        default_value=1.1,
    )


@pytest.fixture
def string_variable() -> Variable:
    return Variable(
        name="string variable",
        type=StringProperty(),
        description="my string variable",
    )


@pytest.fixture
def list_of_floats_variable() -> Variable:
    return Variable(
        name="list_of_floats_variable",
        type=ListProperty(item_type=FloatProperty()),
        description="list of floats variable",
        default_value=[4.0, 4.0, 3.0, 2.1423],
    )


@pytest.fixture
def dict_of_floats_variable() -> Variable:
    return Variable(
        name="dict_of_floats_variable",
        type=DictProperty(value_type=FloatProperty()),
        description="dict of floats variable",
        default_value={"my_str": 22.14},
    )


@pytest.fixture
def list_of_dicts_of_strings_variable() -> Variable:
    return Variable(
        name="list_of_dict_of_strings_variable",
        type=ListProperty(item_type=DictProperty(value_type=StringProperty())),
        description="list of dict of strings variable",
        default_value=[{"my_str": "my value"}],
    )


@pytest.mark.parametrize(
    "variable",
    [
        "float_variable",
        "string_variable",
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
def test_can_init_flow_with_variable_and_steps(variable: str, request: FixtureRequest) -> None:
    variable = request.getfixturevalue(variable)

    Flow.from_steps(
        [VariableReadStep(variable=variable), VariableReadStep(variable=variable)],
        variables=[variable],
    )


def test_variable_write_step_constructor_rejects_merge_on_incompatible_type(
    float_variable: Variable,
) -> None:
    with pytest.raises(ValueError):
        VariableWriteStep(float_variable, operation="append")
    with pytest.raises(ValueError):
        VariableWriteStep(float_variable, operation="merge")


def test_flow_constructor_rejects_duplicated_variable_names(float_variable: Variable) -> None:
    # var1 has the same name as float_variable, but everything else is different
    var1 = Variable(
        name="float_variable",
        type=ListProperty(FloatProperty()),
        description="list of floats variable",
        default_value=[1.0, 2.0, 3.0, 4.0],
    )

    with pytest.raises(ValueError):
        create_single_step_flow(
            step=VariableReadStep(variable=float_variable), variables=[var1, float_variable]
        )


def test_flow_constructor_rejects_read_step_referring_unknown_variable(
    float_variable: Variable,
) -> None:
    with pytest.raises(ValueError):
        create_single_step_flow(VariableReadStep(variable=float_variable), "read_step")


def test_flow_constructor_rejects_write_step_referring_unknown_variable(
    float_variable: Variable,
) -> None:
    with pytest.raises(ValueError):
        create_single_step_flow(VariableWriteStep(variable=float_variable), "write_step")


def test_variable_read_step_cannot_read_variable_without_default_value(
    string_variable: Variable,
) -> None:
    flow_assistant = create_single_step_flow(
        step=VariableReadStep(variable=string_variable),
        variables=[string_variable],
    )
    with pytest.raises(ValueError):
        flow_assistant.execute(flow_assistant.start_conversation())


@pytest.mark.parametrize(
    "variable",
    [
        "float_variable",
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
def test_variable_read_step_can_read_default_value(variable: str, request: FixtureRequest) -> None:
    variable = request.getfixturevalue(variable)

    flow_assistant = create_single_step_flow(
        step=VariableReadStep(variable=variable),
        variables=[variable],
    )

    status = flow_assistant.execute(flow_assistant.start_conversation())

    assert isinstance(status, FinishedStatus)
    assert VariableReadStep.VALUE in status.output_values
    assert status.output_values[VariableReadStep.VALUE] == variable.default_value


@pytest.mark.parametrize(
    "variable", ["float_variable", "list_of_floats_variable", "dict_of_floats_variable"]
)
def test_variable_write_step_cannot_write_different_type(
    variable: str, request: FixtureRequest
) -> None:
    variable = request.getfixturevalue(variable)

    flow_assistant = create_single_step_flow(
        step=VariableWriteStep(variable=variable), variables=[variable]
    )
    with pytest.raises(TypeError):
        flow_assistant.execute(
            flow_assistant.start_conversation({VariableWriteStep.VALUE: "clearly different type"})
        )


def test_variable_write_step_cannot_write_if_value_not_in_io_dict(
    string_variable: Variable,
) -> None:
    io_dict_key = "write_io"

    flow_assistant = create_single_step_flow(
        step=VariableWriteStep(variable=string_variable, input_mapping={"value": io_dict_key}),
        variables=[string_variable],
    )

    with pytest.raises(ValueError):
        flow_assistant.execute(flow_assistant.start_conversation())


@pytest.mark.parametrize(
    "variable",
    [
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
def test_flow_can_write_own_reads(variable: str, request: FixtureRequest) -> None:
    variable = request.getfixturevalue(variable)

    assistant = Flow.from_steps(
        [
            VariableReadStep(variable=variable, output_mapping={"value": "spluuk"}),
            VariableWriteStep(
                variable=variable, operation="merge", input_mapping={"value": "spluuk"}
            ),
        ],
        variables=[variable],
    )

    conversation = assistant.start_conversation()
    status = assistant.execute(conversation)

    assert isinstance(status, FinishedStatus)

    outputs = status.output_values["spluuk"]

    if "list" in variable.name:  # the same list is concatenated again
        assert outputs == variable.default_value + variable.default_value
    elif "dict" in variable.name:  # same key, so no new elements
        assert outputs == variable.default_value
    else:
        raise ValueError("Something wrong with the fixture setup")


def test_variable_readwrite_steps_work_in_flow(string_variable: Variable) -> None:
    @tool
    def dummy_tool() -> str:
        "dummy tool"
        return "my string value"

    assistant = Flow.from_steps(
        steps=[
            ToolExecutionStep(tool=dummy_tool),
            VariableWriteStep(
                string_variable,
                input_mapping={VariableWriteStep.VALUE: ToolExecutionStep.TOOL_OUTPUT},
            ),
            VariableReadStep(string_variable),
        ],
        variables=[string_variable],
    )
    conversation = assistant.start_conversation()
    status = assistant.execute(conversation)

    assert isinstance(status, FinishedStatus)
    assert status.output_values[VariableReadStep.VALUE] == "my string value"


def test_multiple_reads(float_variable: Variable, list_of_floats_variable: Variable) -> None:
    assistant = Flow.from_steps(
        steps=[
            VariableReadStep(variable=float_variable, output_mapping={"value": "read1-io"}),
            VariableReadStep(
                variable=list_of_floats_variable, output_mapping={"value": "read2-io"}
            ),
        ],
        variables=[float_variable, list_of_floats_variable],
    )

    conversation = assistant.start_conversation()
    assert isinstance(conversation.state, FlowConversationExecutionState)
    assert len(conversation.state.input_output_key_values) == 0

    status = assistant.execute(conversation)

    assert isinstance(status, FinishedStatus)
    assert status.output_values["read1-io"] == float_variable.default_value
    assert status.output_values["read2-io"] == list_of_floats_variable.default_value


def test_multiple_writes(float_variable: Variable, string_variable: Variable) -> None:
    assistant = Flow.from_steps(
        steps=[
            VariableWriteStep(variable=float_variable, input_mapping={"value": "write-float-io"}),
            VariableWriteStep(variable=string_variable, input_mapping={"value": "write-string-io"}),
        ],
        variables=[float_variable, string_variable],
    )

    conversation = assistant.start_conversation(
        {"write-string-io": "my-string", "write-float-io": 3.14}
    )
    assistant.execute(conversation)

    assert conversation.state.variable_store[float_variable.name] == 3.14
    assert conversation.state.variable_store[string_variable.name] == "my-string"


def test_can_read_own_writes(float_variable: Variable, string_variable: Variable) -> None:
    assistant = Flow.from_steps(
        steps=[
            VariableWriteStep(variable=float_variable, input_mapping={"value": "write-float-io"}),
            VariableWriteStep(variable=string_variable, input_mapping={"value": "write-string-io"}),
            VariableReadStep(variable=float_variable, output_mapping={"value": "read-float-io"}),
            VariableReadStep(variable=string_variable, output_mapping={"value": "read-string-io"}),
        ],
        variables=[float_variable, string_variable],
    )

    conversation = assistant.start_conversation(
        {"write-string-io": "my-string", "write-float-io": 3.14}
    )

    status = assistant.execute(conversation)
    assert isinstance(status, FinishedStatus)

    assert (
        conversation.state.variable_store[string_variable.name]
        == status.output_values["read-string-io"]
    )
    assert (
        conversation.state.variable_store[float_variable.name]
        == status.output_values["read-float-io"]
    )


def test_insert_into_list(list_of_floats_variable):
    assistant = Flow.from_steps(
        steps=[
            VariableWriteStep(
                variable=list_of_floats_variable,
                operation=VariableWriteOperation.INSERT,
                input_mapping={"value": "write-float-io"},
            )
        ],
        variables=[list_of_floats_variable],
    )

    conversation = assistant.start_conversation({"write-float-io": 0.1})
    assistant.execute(conversation)

    expected = [4.0, 4.0, 3.0, 2.1423, 0.1]
    assert conversation.state.variable_store[list_of_floats_variable.name] == expected


def test_variable_is_reused_when_flow_loops_onto_itself(list_of_floats_variable):
    assistant = Flow.from_steps(
        steps=[
            VariableWriteStep(
                variable=list_of_floats_variable,
                operation=VariableWriteOperation.INSERT,
                input_mapping={"value": "write-float-io"},
            ),
            VariableWriteStep(
                variable=list_of_floats_variable,
                operation=VariableWriteOperation.INSERT,
                input_mapping={"value": "write-another-float-io"},
            ),
            VariableReadStep(
                variable=list_of_floats_variable, output_mapping={"value": "read-list-of-float-io"}
            ),
            InputMessageStep(""),
        ],
        step_names=["append-float", "append-float-again", "read-list-of-floats", "yield"],
        loop=True,
        variables=[list_of_floats_variable],
    )

    conversation = assistant.start_conversation(
        {"write-float-io": 0.1, "write-another-float-io": 3.14}
    )
    assistant.execute(conversation)

    expected = [4.0, 4.0, 3.0, 2.1423, 0.1, 3.14]
    assert conversation.state.variable_store[list_of_floats_variable.name] == expected

    conversation.append_user_message("")
    assistant.execute(conversation)

    expected += [0.1, 3.14]
    assert conversation.state.variable_store[list_of_floats_variable.name] == expected


def test_error_on_insert_into_incompatible_variable_type(float_variable):
    # First validation happens on output value type description creation.
    with pytest.raises(ValueError):
        create_single_step_flow(
            step=VariableWriteStep(
                variable=float_variable,
                operation=VariableWriteOperation.INSERT,
                input_mapping={"value": "write-float-io"},
            ),
            variables=[float_variable],
        )
