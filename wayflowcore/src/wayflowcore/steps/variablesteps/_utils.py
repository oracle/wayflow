# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from collections import Counter
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Union

from wayflowcore.property import DictProperty, ListProperty, Property
from wayflowcore.variable import Variable, VariableWriteOperation

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation


def _require_variable_value_from_conversation_store(
    variable: Variable,
    conversation: "FlowConversation",
) -> Any:
    return conversation._get_variable_value(variable)


def _validate_write_step_configurations(
    variable: Variable, operation: VariableWriteOperation
) -> None:
    if operation not in list(VariableWriteOperation):
        raise ValueError(
            f"Invalid operation '{operation}', expected one of {list(VariableWriteOperation)}"
        )
    if operation == VariableWriteOperation.MERGE and not isinstance(
        variable.type, (ListProperty, DictProperty)
    ):
        raise ValueError(
            f"If using MERGE, the variable's type must be list or dict, but got {variable.type}"
        )
    if operation == VariableWriteOperation.INSERT and not isinstance(variable.type, (ListProperty)):
        raise ValueError(
            f"If using INSERT, the variable's type must be list, but got {variable.type}"
        )


def _compute_variable_input_descriptor(
    variable: Variable,
    operation: VariableWriteOperation,
    name: Optional[str] = None,
) -> Property:
    if name is None:
        name = variable.name

    value_type_description = variable.to_property()

    if operation == VariableWriteOperation.INSERT:
        if isinstance(value_type_description, ListProperty):
            return value_type_description.item_type.copy(
                name=name,
                description=value_type_description.item_type.description
                or f"{value_type_description.description} (single element)",
            )

        raise TypeError(
            f"Can only apply insert write operation to lists, not {value_type_description.__class__}"
        )

    return value_type_description.copy(name=name)


def _put_variable_value_in_conversation_store(
    conversation: "FlowConversation",
    variable: Variable,
    value: Any,
    operation: "VariableWriteOperation" = VariableWriteOperation.OVERWRITE,
) -> None:
    current_value = conversation._get_variable_value(variable)
    if current_value is not None and type(current_value) != type(value):
        if operation == VariableWriteOperation.INSERT:
            var_type = variable.type
            if not isinstance(var_type, ListProperty):
                raise TypeError(
                    f"Can only insert into list variables, but {variable.name} has type {variable.type}"
                )

            if not var_type.item_type.is_value_of_expected_type(value):
                raise TypeError(
                    f"Expected inserted value in variable {variable.name} to be of type {var_type.item_type}, got {type(value)} instead."
                )
        else:
            raise ValueError(
                f"The new value type '{type(value)}' is different from the current value type '{type(current_value)}'. "
                "This error should have been caught by the flow executor when resolving inputs for the write step."
            )
    if operation == VariableWriteOperation.OVERWRITE:
        conversation.state.variable_store[variable.name] = value
    elif operation == VariableWriteOperation.MERGE:
        if isinstance(current_value, list):
            current_value.extend(value)
        elif isinstance(current_value, dict):
            current_value.update(value)
        else:
            raise ValueError(
                f"MERGE operation only supports list and dicts, but the value is {value} of type {type(value)}"
            )
    elif operation == VariableWriteOperation.INSERT:
        if isinstance(current_value, list):
            current_value.append(value)
        else:
            raise ValueError(
                f"INSERT operation only supports list, but the value is {value} of type {type(value)}"
            )
    else:
        raise ValueError(
            f"Invalid operation '{operation}', expected one of {list(VariableWriteOperation)}"
        )


def _get_non_unique_elements(iterable: Iterable[Any]) -> List[str]:
    return [element for element, count in Counter(iterable).items() if count > 1]


def _require_unique_variable_names(variables: List[Variable]) -> None:
    non_unique_var_names = _get_non_unique_elements(map(lambda v: v.name, variables))
    if len(non_unique_var_names) != 0:
        non_unique_var_names_str = ", ".join(non_unique_var_names)
        raise ValueError(
            "Duplicate names are not allowed in `write_variables` or `read_variables`. "
            f"{non_unique_var_names_str} appears more than once. "
            "A variable may appear in both `read_variables` and `write_variables`, but not more than once in any of them. "
            "Each of `read_variables` and `write_variables` must contain unique variables."
        )


def _require_write_operations_dictionary(
    write_variables: List[Variable],
    write_operations: Optional[
        Union[
            VariableWriteOperation,
            Dict[str, VariableWriteOperation],
        ]
    ],
) -> Dict[str, VariableWriteOperation]:

    no_operations = write_operations is None or (
        isinstance(write_operations, dict) and len(write_operations) == 0
    )
    no_write_variable = len(write_variables) == 0

    if no_write_variable and no_operations:
        return {}

    if no_write_variable:
        raise ValueError(
            f"The VariableStep was configured with a set of write operations to perform ({write_operations}, type: {type(write_operations)}), but no variables to write."
            "This is seemingly a misuse of `VariableStep`, as the `write_operations` specify the kind of write operations that must apply to the variables in `write_variables`. "
            "If there is no intention of writing a variable in this step, you should omit passing a value to the argument `write_operations`. "
            "Otherwise, you should also declare the intended variable in `write_variables`."
        )

    if no_operations:
        raise ValueError(
            f"Argument `write_operations` cannot be `None` or empty while `write_variables` is non-empty."
        )

    if isinstance(write_operations, VariableWriteOperation):
        return {var.name: write_operations for var in write_variables}

    if isinstance(write_operations, dict):
        operations_vars_names = set(write_operations.keys())

        write_vars_names = {var.name for var in write_variables}

        write_variable_with_no_operation = write_vars_names - operations_vars_names
        if len(write_variable_with_no_operation) != 0:
            write_variable_with_no_operation_str = ", ".join(write_variable_with_no_operation)
            raise ValueError(
                "All of the variables in `write_variables` must have an associated operation. "
                f"Variable(s) {write_variable_with_no_operation_str} is/are defined in `write_variables`, but there is no operation associated with them in the `write_operations` dictionary."
            )

        operations_with_no_declared_variables = operations_vars_names - write_vars_names
        if len(operations_with_no_declared_variables) != 0:
            operations_with_no_declared_variables_str = ", ".join(
                operations_with_no_declared_variables
            )
            raise ValueError(
                "All of the variable name in `write_operations` must be associated with a variable in `write_variables`, "
                f"but operations dictionary additionally specifies {operations_with_no_declared_variables_str}. "
                f"There is/are operation(s) specified for variable(s) {operations_with_no_declared_variables_str} in the dictionary passed as `write_operations`, while these variables are not declared in `write_variables`. "
                "If you want to perform a write operation on a variable, the variable must be present in `write_variables`."
            )

        return write_operations

    raise ValueError(
        "Argument `write_operations` must be a VariableWriteOperation or a dictionary of str -> VariableWriteOperation. "
        f"Found {write_operations} with type {type(write_operations)} instead."
    )
