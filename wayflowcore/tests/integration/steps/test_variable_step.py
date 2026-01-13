# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, List

import pytest
from _pytest.fixtures import FixtureRequest

from wayflowcore.executors._flowexecutor import FlowConversationExecutionState
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.property import DictProperty, FloatProperty, ListProperty, StringProperty
from wayflowcore.steps import ToolExecutionStep, VariableStep
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
def string_variable_with_default() -> Variable:
    return Variable(
        name="string variable",
        type=StringProperty(),
        description="my string variable",
        default_value="default",
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
    "variable_name",
    [
        "float_variable",
        "string_variable",
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
def test_can_init_flow_with_variable_and_step_with_read(
    variable_name: str, request: FixtureRequest
) -> None:
    variable = request.getfixturevalue(variable_name)

    Flow.from_steps(
        [VariableStep(read_variables=[variable])],
        variables=[variable],
    )


@pytest.mark.parametrize(
    "variable_name",
    [
        "float_variable",
        "string_variable",
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
def test_can_init_flow_with_variable_and_step_with_write(
    variable_name: str, request: FixtureRequest
) -> None:
    variable = request.getfixturevalue(variable_name)

    Flow.from_steps(
        [
            VariableStep(
                write_variables=[variable],
                write_operations=VariableWriteOperation.OVERWRITE,
            )
        ],
        variables=[variable],
    )


@pytest.mark.parametrize(
    "variable_name",
    [
        "float_variable",
        "string_variable",
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
def test_can_init_flow_with_variable_and_step_with_read_and_write(
    variable_name: str, request: FixtureRequest
) -> None:
    variable = request.getfixturevalue(variable_name)

    Flow.from_steps(
        [
            VariableStep(
                read_variables=[variable],
                write_variables=[variable],
                write_operations=VariableWriteOperation.OVERWRITE,
            )
        ],
        variables=[variable],
    )


@pytest.mark.parametrize(
    "variable_name",
    [
        "float_variable",
        "string_variable",
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
def test_can_init_flow_with_variable_and_step_with_two_read_and_write(
    variable_name: str,
    request: FixtureRequest,
) -> None:
    variable = request.getfixturevalue(variable_name)

    Flow.from_steps(
        [
            VariableStep(
                read_variables=[variable],
                write_variables=[variable],
                write_operations=VariableWriteOperation.OVERWRITE,
            ),
            VariableStep(
                read_variables=[variable],
                write_variables=[variable],
                write_operations=VariableWriteOperation.OVERWRITE,
            ),
        ],
        variables=[variable],
    )


def test_void_variable_step_rejects() -> None:
    with pytest.raises(ValueError, match="Invalid `VariableStep`"):
        VariableStep()

    with pytest.raises(ValueError, match="Invalid `VariableStep`"):
        VariableStep(read_variables=[])

    with pytest.raises(ValueError, match="Invalid `VariableStep`"):
        VariableStep(write_variables=[])

    with pytest.raises(ValueError, match="Invalid `VariableStep`"):
        VariableStep(read_variables=[], write_variables=[])


def test_non_unique_variables_reject(float_variable: Variable) -> None:
    with pytest.raises(ValueError, match="Duplicate names are not allowed"):
        VariableStep(write_variables=[float_variable, float_variable])
    with pytest.raises(ValueError, match="Duplicate names are not allowed"):
        VariableStep(read_variables=[float_variable, float_variable])


def test_unique_variables_with_overlap_are_accepted(
    float_variable: Variable,
    string_variable: Variable,
) -> None:
    VariableStep(
        write_variables=[float_variable, string_variable],
        read_variables=[string_variable],
        write_operations=VariableWriteOperation.OVERWRITE,
    )
    VariableStep(
        read_variables=[string_variable, float_variable],
        write_variables=[float_variable],
        write_operations=VariableWriteOperation.OVERWRITE,
    )
    VariableStep(
        write_variables=[float_variable, string_variable],
        read_variables=[float_variable, string_variable],
        write_operations=VariableWriteOperation.OVERWRITE,
    )


@pytest.mark.parametrize(
    "variable_name",
    [
        "float_variable",
        "string_variable",
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
def test_requires_operations_dictionary_with_no_write_var_and_no_operations(
    variable_name: str, request: FixtureRequest
) -> None:
    variable: Variable = request.getfixturevalue(variable_name)

    step = VariableStep(read_variables=[variable])
    assert isinstance(step.write_operations, dict) and len(step.write_operations) == 0

    step = VariableStep(read_variables=[variable], write_operations=None)
    assert isinstance(step.write_operations, dict) and len(step.write_operations) == 0

    step = VariableStep(read_variables=[variable], write_operations={})
    assert isinstance(step.write_operations, dict) and len(step.write_operations) == 0


@pytest.mark.parametrize(
    "variable_name",
    [
        "float_variable",
        "string_variable",
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
@pytest.mark.parametrize("operation", [o for o in VariableWriteOperation])
def test_requires_operations_dictionary_with_no_write_var(
    variable_name: str, operation: VariableWriteOperation, request: FixtureRequest
) -> None:
    variable: Variable = request.getfixturevalue(variable_name)

    with pytest.raises(
        ValueError,
        match="The VariableStep was configured with a set of write operations to perform",
    ):
        VariableStep(read_variables=[variable], write_operations=operation)

    with pytest.raises(
        ValueError,
        match="The VariableStep was configured with a set of write operations to perform",
    ):
        VariableStep(read_variables=[variable], write_operations={variable.name: operation})

    with pytest.raises(
        ValueError,
        match="The VariableStep was configured with a set of write operations to perform",
    ):
        VariableStep(read_variables=[variable], write_operations={"out of scope name": operation})


@pytest.mark.parametrize(
    "variable_name",
    [
        "float_variable",
        "string_variable",
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
@pytest.mark.parametrize(
    "void_write_operations",
    [
        "leave-as-default",
        None,
        dict(),
    ],
)
def test_requires_operations_dictionary_with_no_operation(
    variable_name: str, void_write_operations: Any, request: FixtureRequest
) -> None:
    variable: Variable = request.getfixturevalue(variable_name)

    with pytest.raises(ValueError, match="Argument `write_operations` cannot be `None` or empty"):
        if void_write_operations == "leave-as-default":
            VariableStep(write_variables=[variable])
        else:
            VariableStep(write_variables=[variable], write_operations=void_write_operations)


@pytest.mark.parametrize(
    "write_variables_names",
    [
        ["list_of_floats_variable"],
        ["list_of_dicts_of_strings_variable"],
        ["list_of_floats_variable", "list_of_dicts_of_strings_variable"],
    ],
)
@pytest.mark.parametrize("write_operations", [o for o in VariableWriteOperation])
def test_requires_operations_dictionary_with_general_operation(
    write_variables_names: List[str],
    write_operations: VariableWriteOperation,
    request: FixtureRequest,
) -> None:
    write_variables = [
        request.getfixturevalue(write_variable_name)
        for write_variable_name in write_variables_names
    ]

    step = VariableStep(write_variables=write_variables, write_operations=write_operations)
    assert isinstance(step.write_operations, dict)
    assert len(step.write_operations) == len(write_variables)
    assert all(write_variable.name in step.write_operations for write_variable in write_variables)
    assert all(write_operations == o for _, o in step.write_operations.items())


@pytest.mark.parametrize("operation", [o for o in VariableWriteOperation])
def test_requires_operations_dictionary_with_variables_without_associated_operations(
    float_variable: Variable,
    string_variable: Variable,
    operation: VariableWriteOperation,
) -> None:
    with pytest.raises(
        ValueError,
        match="All of the variables in `write_variables` must have an associated operation.",
    ):
        VariableStep(
            write_variables=[float_variable, string_variable],
            write_operations={float_variable.name: operation},
        )


@pytest.mark.parametrize("operation", [o for o in VariableWriteOperation])
def test_requires_operations_dictionary_with_operations_without_associated_variables(
    float_variable: Variable,
    string_variable: Variable,
    operation: VariableWriteOperation,
) -> None:
    with pytest.raises(
        ValueError,
        match="All of the variable name in `write_operations` must be associated with a variable in `write_variables`",
    ):
        VariableStep(
            write_variables=[float_variable],
            write_operations={
                float_variable.name: operation,
                string_variable.name: operation,
            },
        )


@pytest.mark.parametrize("operation", [o for o in VariableWriteOperation])
def test_requires_operations_dictionary_with_invalid_operation_in_dict(
    float_variable: Variable,
    string_variable: Variable,
    operation: VariableWriteOperation,
) -> None:
    with pytest.raises(
        ValueError,
        match="Invalid operation 'append'",
    ):
        VariableStep(
            write_variables=[float_variable, string_variable],
            write_operations={
                float_variable.name: "append",  # type: ignore
                string_variable.name: operation,
            },
        )


def test_requires_operations_dictionary_with_specific_operations(
    float_variable: Variable,
    string_variable: Variable,
    dict_of_floats_variable: Variable,
    list_of_floats_variable: Variable,
) -> None:
    step = VariableStep(
        write_variables=[float_variable, dict_of_floats_variable, list_of_floats_variable],
        write_operations={
            float_variable.name: VariableWriteOperation.OVERWRITE,
            dict_of_floats_variable.name: VariableWriteOperation.MERGE,
            list_of_floats_variable.name: VariableWriteOperation.INSERT,
        },
    )
    assert isinstance(step.write_operations, dict)
    assert len(step.write_operations) == 3
    assert step._requires_operation_of_write_var(float_variable) == VariableWriteOperation.OVERWRITE
    assert (
        step._requires_operation_of_write_var(dict_of_floats_variable)
        == VariableWriteOperation.MERGE
    )
    assert (
        step._requires_operation_of_write_var(list_of_floats_variable)
        == VariableWriteOperation.INSERT
    )
    with pytest.raises(
        RuntimeError,
        match=f"No operation found associated with variable {string_variable.name}.",
    ):
        step._requires_operation_of_write_var(string_variable)


def test_variable_step_with_str_operation(float_variable: Variable) -> None:
    with pytest.raises(
        ValueError,
        match="Argument `write_operations` must be a VariableWriteOperation or a dictionary of str -> VariableWriteOperation.",
    ):
        VariableStep(write_variables=[float_variable], write_operations="append")  # type: ignore


@pytest.mark.parametrize(
    "variable_name",
    [
        "float_variable",
        "string_variable",
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
def test_variable_step_constructor_rejects_invalid_operation(
    variable_name: str, request: FixtureRequest
) -> None:
    variable: Variable = request.getfixturevalue(variable_name)

    with pytest.raises(ValueError, match="Invalid operation"):
        VariableStep(write_variables=[variable], write_operations={variable.name: "append"})  # type: ignore


@pytest.mark.parametrize(
    "variable_name",
    [
        "float_variable",
        "string_variable",
        "dict_of_floats_variable",
    ],
)
def test_variable_step_constructor_rejects_insert_on_incompatible_type(
    variable_name: str, request: FixtureRequest
) -> None:
    variable = request.getfixturevalue(variable_name)

    with pytest.raises(ValueError, match=f"If using INSERT, the variable's type must be list, *"):
        VariableStep(write_variables=[variable], write_operations=VariableWriteOperation.INSERT)


@pytest.mark.parametrize(
    "variable_name",
    [
        "list_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
def test_variable_step_constructor_accept_insert_on_compatible_type(
    variable_name: str, request: FixtureRequest
) -> None:
    variable = request.getfixturevalue(variable_name)

    VariableStep(write_variables=[variable], write_operations=VariableWriteOperation.INSERT)


@pytest.mark.parametrize(
    "variable_name",
    [
        "float_variable",
        "string_variable",
    ],
)
def test_variable_step_constructor_rejects_merge_on_incompatible_type(
    variable_name: str, request: FixtureRequest
) -> None:
    variable = request.getfixturevalue(variable_name)

    with pytest.raises(
        ValueError, match=f"If using MERGE, the variable's type must be list or dict, *"
    ):
        VariableStep(write_variables=[variable], write_operations=VariableWriteOperation.MERGE)


@pytest.mark.parametrize(
    "variable_name",
    [
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
def test_variable_step_constructor_accept_merge_on_compatible_type(
    variable_name: str, request: FixtureRequest
) -> None:
    variable = request.getfixturevalue(variable_name)

    VariableStep(write_variables=[variable], write_operations=VariableWriteOperation.MERGE)


def test_flow_constructor_rejects_duplicated_variable_names(float_variable: Variable) -> None:
    # var1 has the same name as float_variable, but everything else is different
    var1 = Variable(
        name="float_variable",
        type=ListProperty(),
        description="list of floats variable",
        default_value=[1.0, 2.0, 3.0, 4.0],
    )

    with pytest.raises(ValueError, match="The list of Variables contain duplicated names"):
        create_single_step_flow(
            step=VariableStep(
                read_variables=[float_variable],
                write_variables=[float_variable],
                write_operations=VariableWriteOperation.OVERWRITE,
            ),
            variables=[var1, float_variable],
        )


def test_flow_constructor_rejects_step_referring_unknown_variable(
    float_variable: Variable,
    string_variable: Variable,
) -> None:
    with pytest.raises(
        ValueError,
        match=r"The VariableStep 'read_step' refers to the variable\(s\) float_variable but this/these variable\(s\) was/were not passed into the flow constructor.",
    ):
        create_single_step_flow(VariableStep(read_variables=[float_variable]), "read_step")

    with pytest.raises(
        ValueError,
        match=r"The VariableStep 'read_step' refers to the variable\(s\) float_variable but this/these variable\(s\) was/were not passed into the flow constructor.",
    ):
        create_single_step_flow(
            VariableStep(
                write_variables=[float_variable], write_operations=VariableWriteOperation.OVERWRITE
            ),
            "read_step",
        )

    with pytest.raises(
        ValueError,
        match=r"The VariableStep 'read_step' refers to the variable\(s\) float_variable but this/these variable\(s\) was/were not passed into the flow constructor.",
    ):
        create_single_step_flow(
            VariableStep(
                read_variables=[float_variable],
                write_variables=[float_variable],
                write_operations=VariableWriteOperation.OVERWRITE,
            ),
            "read_step",
        )

    with pytest.raises(
        ValueError,
        match=r"The VariableStep 'read_step' refers to the variable\(s\) .+ but this/these variable\(s\) was/were not passed into the flow constructor.",
    ):
        create_single_step_flow(
            VariableStep(
                read_variables=[float_variable],
                write_variables=[string_variable],
                write_operations=VariableWriteOperation.OVERWRITE,
            ),
            "read_step",
        )


def test_variable_step_cannot_read_variable_without_default_value(
    string_variable: Variable,
) -> None:
    flow_assistant = create_single_step_flow(
        step=VariableStep(read_variables=[string_variable]),
        variables=[string_variable],
    )
    with pytest.raises(
        ValueError,
        match="Attempted to read from the Variable 'string variable' but the value was None.",
    ):
        flow_assistant.start_conversation().execute()


@pytest.mark.parametrize(
    "variable_name",
    [
        "float_variable",
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
def test_variable_step_can_read_default_value(variable_name: str, request: FixtureRequest) -> None:
    variable: Variable = request.getfixturevalue(variable_name)

    flow_assistant = create_single_step_flow(
        step=VariableStep(read_variables=[variable]),
        variables=[variable],
    )

    status = flow_assistant.start_conversation().execute()

    assert isinstance(status, FinishedStatus)
    assert variable.name in status.output_values
    assert status.output_values[variable.name] == variable.default_value


@pytest.mark.parametrize(
    "variable_name",
    [
        "float_variable",
        "list_of_floats_variable",
        "dict_of_floats_variable",
    ],
)
def test_variable_step_cannot_write_different_type(
    variable_name: str, request: FixtureRequest
) -> None:
    variable: Variable = request.getfixturevalue(variable_name)

    flow_assistant = create_single_step_flow(
        step=VariableStep(
            write_variables=[variable], write_operations=VariableWriteOperation.OVERWRITE
        ),
        variables=[variable],
    )
    with pytest.raises(
        TypeError, match="The input passed: .+ of type .+ is not of the expected type"
    ):
        flow_assistant.start_conversation({variable.name: "clearly different type"}).execute()


def test_variable_step_cannot_write_if_value_not_in_io_dict(
    string_variable: Variable,
) -> None:
    io_dict_key = "write_io"

    flow_assistant = create_single_step_flow(
        step=VariableStep(
            write_variables=[string_variable],
            write_operations=VariableWriteOperation.OVERWRITE,
            input_mapping={string_variable.name: io_dict_key},
        ),
        variables=[string_variable],
    )

    with pytest.raises(
        ValueError, match='Cannot start conversation because of missing inputs "write_io"'
    ):
        status = flow_assistant.start_conversation().execute()


@pytest.mark.parametrize(
    "variable_name",
    [
        "list_of_floats_variable",
        "dict_of_floats_variable",
        "list_of_dicts_of_strings_variable",
    ],
)
def test_flow_can_write_own_reads(variable_name: str, request: FixtureRequest) -> None:
    variable: Variable = request.getfixturevalue(variable_name)

    assistant = Flow.from_steps(
        [
            VariableStep(read_variables=[variable], output_mapping={variable.name: "spluuk"}),
            VariableStep(
                write_variables=[variable],
                write_operations=VariableWriteOperation.MERGE,
                input_mapping={variable.name: "spluuk"},
            ),
        ],
        variables=[variable],
    )

    status = assistant.start_conversation().execute()

    assert isinstance(status, FinishedStatus)

    outputs = status.output_values["spluuk"]

    if "list" in variable.name:  # the same list is concatenated again
        assert outputs == variable.default_value + variable.default_value
    elif "dict" in variable.name:  # same key, so no new elements
        assert outputs == variable.default_value
    else:
        raise ValueError("Something wrong with the fixture setup")


def test_variable_readwrite_steps_work_in_flow(string_variable_with_default: Variable) -> None:
    @tool
    def dummy_tool() -> str:
        "dummy tool"
        return "my string value"

    assistant = Flow.from_steps(
        steps=[
            ToolExecutionStep(tool=dummy_tool),  # type: ignore
            VariableStep(
                write_variables=[string_variable_with_default],
                read_variables=[string_variable_with_default],
                write_operations=VariableWriteOperation.OVERWRITE,
                input_mapping={string_variable_with_default.name: ToolExecutionStep.TOOL_OUTPUT},
            ),
        ],
        variables=[string_variable_with_default],
    )
    status = assistant.start_conversation().execute()

    assert isinstance(status, FinishedStatus)
    assert status.output_values[string_variable_with_default.name] == "my string value"


def test_multiple_reads(float_variable: Variable, list_of_floats_variable: Variable) -> None:
    assistant = Flow.from_steps(
        steps=[
            VariableStep(
                read_variables=[float_variable], output_mapping={float_variable.name: "read1-io"}
            ),
            VariableStep(
                read_variables=[list_of_floats_variable],
                output_mapping={list_of_floats_variable.name: "read2-io"},
            ),
        ],
        variables=[float_variable, list_of_floats_variable],
    )

    conversation = assistant.start_conversation()
    assert isinstance(conversation.state, FlowConversationExecutionState)
    assert len(conversation.state.input_output_key_values) == 0

    status = conversation.execute()

    assert isinstance(status, FinishedStatus)
    assert status.output_values["read1-io"] == float_variable.default_value
    assert status.output_values["read2-io"] == list_of_floats_variable.default_value


def test_multiple_reads_in_single_step(
    float_variable: Variable, list_of_floats_variable: Variable
) -> None:
    assistant = Flow.from_steps(
        steps=[
            VariableStep(
                read_variables=[float_variable, list_of_floats_variable],
                output_mapping={
                    float_variable.name: "read1-io",
                    list_of_floats_variable.name: "read2-io",
                },
            ),
        ],
        variables=[float_variable, list_of_floats_variable],
    )

    conversation = assistant.start_conversation()
    assert isinstance(conversation.state, FlowConversationExecutionState)
    assert len(conversation.state.input_output_key_values) == 0

    status = conversation.execute()

    assert isinstance(status, FinishedStatus)
    assert status.output_values["read1-io"] == float_variable.default_value
    assert status.output_values["read2-io"] == list_of_floats_variable.default_value


def test_multiple_writes(float_variable: Variable, string_variable: Variable) -> None:
    assistant = Flow.from_steps(
        steps=[
            VariableStep(
                write_variables=[float_variable],
                write_operations=VariableWriteOperation.OVERWRITE,
                input_mapping={float_variable.name: "write-float-io"},
            ),
            VariableStep(
                write_variables=[string_variable],
                write_operations=VariableWriteOperation.OVERWRITE,
                input_mapping={string_variable.name: "write-string-io"},
            ),
        ],
        variables=[float_variable, string_variable],
    )

    conversation = assistant.start_conversation(
        {"write-string-io": "my-string", "write-float-io": 3.14}
    )
    conversation.execute()

    assert conversation.state.variable_store[float_variable.name] == 3.14
    assert conversation.state.variable_store[string_variable.name] == "my-string"


def test_multiple_writes_in_single_step(
    float_variable: Variable, string_variable: Variable
) -> None:
    assistant = Flow.from_steps(
        steps=[
            VariableStep(
                write_variables=[float_variable, string_variable],
                write_operations=VariableWriteOperation.OVERWRITE,
                input_mapping={
                    float_variable.name: "write-float-io",
                    string_variable.name: "write-string-io",
                },
            ),
        ],
        variables=[float_variable, string_variable],
    )

    conversation = assistant.start_conversation(
        {"write-string-io": "my-string", "write-float-io": 3.14}
    )
    conversation.execute()

    assert conversation.state.variable_store[float_variable.name] == 3.14
    assert conversation.state.variable_store[string_variable.name] == "my-string"


def test_can_read_own_writes(float_variable: Variable, string_variable: Variable) -> None:
    assistant = Flow.from_steps(
        steps=[
            VariableStep(
                write_variables=[float_variable],
                write_operations=VariableWriteOperation.OVERWRITE,
                input_mapping={float_variable.name: "write-float-io"},
            ),
            VariableStep(
                write_variables=[string_variable],
                write_operations=VariableWriteOperation.OVERWRITE,
                input_mapping={string_variable.name: "write-string-io"},
            ),
            VariableStep(
                read_variables=[float_variable],
                output_mapping={float_variable.name: "read-float-io"},
            ),
            VariableStep(
                read_variables=[string_variable],
                output_mapping={string_variable.name: "read-string-io"},
            ),
        ],
        variables=[float_variable, string_variable],
    )

    conversation = assistant.start_conversation(
        {"write-string-io": "my-string", "write-float-io": 3.14}
    )

    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    assert (
        conversation.state.variable_store[string_variable.name]
        == status.output_values["read-string-io"]
    )
    assert (
        conversation.state.variable_store[float_variable.name]
        == status.output_values["read-float-io"]
    )


def test_can_read_own_writes_grouped_by_variable(
    float_variable: Variable, string_variable: Variable
) -> None:
    assistant = Flow.from_steps(
        steps=[
            VariableStep(
                write_variables=[float_variable],
                read_variables=[float_variable],
                write_operations=VariableWriteOperation.OVERWRITE,
                input_mapping={float_variable.name: "write-float-io"},
                output_mapping={float_variable.name: "read-float-io"},
            ),
            VariableStep(
                write_variables=[string_variable],
                read_variables=[string_variable],
                write_operations=VariableWriteOperation.OVERWRITE,
                input_mapping={string_variable.name: "write-string-io"},
                output_mapping={string_variable.name: "read-string-io"},
            ),
        ],
        variables=[float_variable, string_variable],
    )

    conversation = assistant.start_conversation(
        {"write-string-io": "my-string", "write-float-io": 3.14}
    )

    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    assert (
        conversation.state.variable_store[string_variable.name]
        == status.output_values["read-string-io"]
        == "my-string"
    )
    assert (
        conversation.state.variable_store[float_variable.name]
        == status.output_values["read-float-io"]
        == 3.14
    )


def test_can_read_own_writes_grouped_by_variable_2(
    float_variable: Variable,
    string_variable_with_default: Variable,
) -> None:
    assistant = Flow.from_steps(
        steps=[
            VariableStep(
                write_variables=[float_variable],
                read_variables=[float_variable],
                write_operations=VariableWriteOperation.OVERWRITE,
                input_mapping={float_variable.name: "write-float-io"},
                output_mapping={float_variable.name: "read-float-io"},
            ),
            VariableStep(
                write_variables=[string_variable_with_default],
                read_variables=[string_variable_with_default],
                write_operations=VariableWriteOperation.OVERWRITE,
                input_mapping={string_variable_with_default.name: "write-string-io"},
                output_mapping={string_variable_with_default.name: "read-string-io"},
            ),
        ],
        variables=[float_variable, string_variable_with_default],
    )

    conversation = assistant.start_conversation(
        {"write-string-io": "my-string", "write-float-io": 3.14}
    )

    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    assert conversation.state.variable_store[string_variable_with_default.name] == "my-string"
    assert conversation.state.variable_store[float_variable.name] == 3.14

    assert status.output_values["read-string-io"] == "my-string"
    assert status.output_values["read-float-io"] == 3.14


def test_can_read_own_writes_grouped_by_action(
    float_variable: Variable, string_variable: Variable
) -> None:
    assistant = Flow.from_steps(
        steps=[
            VariableStep(
                write_variables=[float_variable, string_variable],
                write_operations=VariableWriteOperation.OVERWRITE,
                input_mapping={
                    float_variable.name: "write-float-io",
                    string_variable.name: "write-string-io",
                },
            ),
            VariableStep(
                read_variables=[float_variable, string_variable],
                output_mapping={
                    float_variable.name: "read-float-io",
                    string_variable.name: "read-string-io",
                },
            ),
        ],
        variables=[float_variable, string_variable],
    )

    conversation = assistant.start_conversation(
        {"write-string-io": "my-string", "write-float-io": 3.14}
    )

    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    assert (
        conversation.state.variable_store[string_variable.name]
        == status.output_values["read-string-io"]
    )
    assert (
        conversation.state.variable_store[float_variable.name]
        == status.output_values["read-float-io"]
    )


def test_can_read_own_writes_in_single_step(
    float_variable: Variable,
    string_variable_with_default: Variable,
) -> None:
    assistant = Flow.from_steps(
        steps=[
            VariableStep(
                write_variables=[float_variable, string_variable_with_default],
                read_variables=[float_variable, string_variable_with_default],
                write_operations=VariableWriteOperation.OVERWRITE,
                input_mapping={
                    float_variable.name: "write-float-io",
                    string_variable_with_default.name: "write-string-io",
                },
                output_mapping={
                    float_variable.name: "read-float-io",
                    string_variable_with_default.name: "read-string-io",
                },
            ),
        ],
        variables=[float_variable, string_variable_with_default],
    )

    conversation = assistant.start_conversation(
        {"write-string-io": "my-string", "write-float-io": 3.14}
    )

    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    assert conversation.state.variable_store[string_variable_with_default.name] == "my-string"
    assert conversation.state.variable_store[float_variable.name] == 3.14

    assert status.output_values["read-string-io"] == "my-string"
    assert status.output_values["read-float-io"] == 3.14


def test_insert_into_list(list_of_floats_variable):
    assistant = Flow.from_steps(
        steps=[
            VariableStep(
                write_variables=[list_of_floats_variable],
                write_operations=VariableWriteOperation.INSERT,
                input_mapping={list_of_floats_variable.name: "write-float-io"},
            )
        ],
        variables=[list_of_floats_variable],
    )

    conversation = assistant.start_conversation({"write-float-io": 0.1})
    conversation.execute()

    expected = [4.0, 4.0, 3.0, 2.1423, 0.1]
    assert conversation.state.variable_store[list_of_floats_variable.name] == expected


def test_variable_is_reused_when_flow_loops_onto_itself(list_of_floats_variable: Variable):
    assistant = Flow.from_steps(
        steps=[
            VariableStep(
                write_variables=[list_of_floats_variable],
                write_operations=VariableWriteOperation.INSERT,
                input_mapping={list_of_floats_variable.name: "write-float-io"},
            ),
            VariableStep(
                write_variables=[list_of_floats_variable],
                write_operations=VariableWriteOperation.INSERT,
                input_mapping={list_of_floats_variable.name: "write-another-float-io"},
            ),
            VariableStep(
                read_variables=[list_of_floats_variable],
                output_mapping={list_of_floats_variable.name: "read-list-of-float-io"},
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
    conversation.execute()

    expected = [4.0, 4.0, 3.0, 2.1423, 0.1, 3.14]
    assert conversation.state.variable_store[list_of_floats_variable.name] == expected

    conversation.append_user_message("")
    conversation.execute()

    expected += [0.1, 3.14]
    assert conversation.state.variable_store[list_of_floats_variable.name] == expected


def test_variable_is_reused_when_flow_loops_onto_itself_in_itegrated_call(
    list_of_floats_variable: Variable,
):
    assistant = Flow.from_steps(
        steps=[
            VariableStep(
                write_variables=[list_of_floats_variable],
                read_variables=[list_of_floats_variable],
                write_operations=VariableWriteOperation.INSERT,
                input_mapping={list_of_floats_variable.name: "write-float-io"},
            ),
            VariableStep(
                write_variables=[list_of_floats_variable],
                read_variables=[list_of_floats_variable],
                write_operations=VariableWriteOperation.INSERT,
                input_mapping={list_of_floats_variable.name: "write-another-float-io"},
                output_mapping={list_of_floats_variable.name: "read-list-of-float-io"},
            ),
            InputMessageStep(""),
        ],
        step_names=["append-float", "append-float-again_and_read-list-of-floats", "yield"],
        loop=True,
        variables=[list_of_floats_variable],
    )

    conversation = assistant.start_conversation(
        {"write-float-io": 0.1, "write-another-float-io": 3.14}
    )
    conversation.execute()

    expected = [4.0, 4.0, 3.0, 2.1423, 0.1, 3.14]
    assert conversation.state.variable_store[list_of_floats_variable.name] == expected

    conversation.append_user_message("")
    conversation.execute()

    expected += [0.1, 3.14]
    assert conversation.state.variable_store[list_of_floats_variable.name] == expected


def test_error_on_insert_into_incompatible_variable_type(float_variable: Variable):
    # First validation happens on output value type description creation.
    with pytest.raises(ValueError, match="If using INSERT, the variable's type must be list"):
        create_single_step_flow(
            step=VariableStep(
                write_variables=[float_variable],
                write_operations=VariableWriteOperation.INSERT,
                input_mapping={float_variable.name: "write-float-io"},
            ),
            variables=[float_variable],
        )
