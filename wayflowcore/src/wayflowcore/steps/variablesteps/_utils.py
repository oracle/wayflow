# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from collections import Counter
from typing import TYPE_CHECKING, Any, Iterable, List, Optional

from wayflowcore.property import DictProperty, ListProperty, Property
from wayflowcore.variable import Variable, VariableWriteOperation

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation


def _get_non_unique_elements(iterable: Iterable[Any]) -> List[str]:
    return [element for element, count in Counter(iterable).items() if count > 1]


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
