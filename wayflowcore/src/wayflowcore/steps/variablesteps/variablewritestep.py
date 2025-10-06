# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.property import DictProperty, ListProperty, Property
from wayflowcore.steps.step import Step, StepResult
from wayflowcore.variable import Variable, VariableWriteOperation

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation


class VariableWriteStep(Step):
    """
    Step to perform a write on a Variable.
    This step has no output and a single input, called "value".
    These variables are stored in a key-value store distinct from the I/O system.
    """

    VALUE = "value"
    """str: Input key for the value to write for the ``VariableWriteStep``."""

    def __init__(
        self,
        variable: Variable,
        operation: VariableWriteOperation = VariableWriteOperation.OVERWRITE,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Note
        ----

        A step has input and output descriptors, describing what values the step requires to run and what values it produces.

        **Input descriptors**

        This step has a single input descriptor:

        * ``VariableWriteStep.VALUE``: ``??``, the value to write in the variable store. Type will be resolved depending on the variable type and the type of variable write operation.

        **Output descriptors**

        This step has no output descriptor.

        Parameters
        ----------
        variable:
            ``Variable`` to write to.
            If the variable refers to a non-existent Variable (not passed into the flow), the flow construction will throw an error.
        operation:
            The type of write operation to perform.

            .. note::
                ``VariableWriteOperation.OVERWRITE`` (or ``'overwrite'``) works on any type of variable to replace its value with the incoming value.
                ``VariableWriteOperation.MERGE`` (or ``'merge'``) updates a ``Variable`` of type dict (resp. list),
                so that the variable will contain both the existing data stored in the variable along with the new values in the incoming dict (resp. list).
                If the operation is ``MERGE`` but the variable's value is ``None``, it will throw an error,
                as a default value should have been provided when constructing the ``Variable``.
                The ``VariableWriteOperation.INSERT`` (or ``'insert'``) operation can be used to append a single element at the end of a list.
        input_descriptors:
            Input descriptors of the step. ``None`` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.

        output_descriptors:
            Output descriptors of the step. ``None`` means the step will resolve them automatically using its static
            configuration in a best effort manner.

        name:
            Name of the step.

        input_mapping:
            Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.

        output_mapping:
            Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.


        Examples
        --------
        >>> from wayflowcore.flow import Flow
        >>> from wayflowcore.controlconnection import ControlFlowEdge
        >>> from wayflowcore.steps import VariableWriteStep
        >>> from wayflowcore.variable import Variable
        >>> from wayflowcore.property import ListProperty, FloatProperty
        >>>
        >>> VARIABLE_IO = "$variable"
        >>> # ^ how the variable value is stored in the I/O dict
        >>>
        >>> float_variable = Variable(
        ...     name="float_variable",
        ...     type=ListProperty(item_type=FloatProperty()),
        ...     description="list of floats variable",
        ...     default_value=[],
        ... )
        >>>
        >>> write_step = VariableWriteStep(
        ...     variable=float_variable,
        ...     input_mapping={VariableWriteStep.VALUE: VARIABLE_IO}
        ... )
        >>>
        >>> flow = Flow(
        ...     begin_step=write_step,
        ...     control_flow_edges=[
        ...         ControlFlowEdge(write_step, None),
        ...     ],
        ...     variables=[float_variable],
        ... )
        >>> conv = flow.start_conversation(inputs={VARIABLE_IO: [1.0, 2.0, 3.0, 4.0]})
        >>> status = conv.execute()
        >>> new_variable_value = conv._get_variable_value(float_variable)
        >>> # In practice, the value can be accessed with a VariableReadStep in the flow
        >>> new_variable_value
        [1.0, 2.0, 3.0, 4.0]

        """
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
        if operation == VariableWriteOperation.INSERT and not isinstance(
            variable.type, (ListProperty)
        ):
            raise ValueError(
                f"If using INSERT, the variable's type must be list, but got {variable.type}"
            )

        super().__init__(
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            step_static_configuration=dict(variable=variable, operation=operation),
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )
        self.variable = variable
        self.operation = operation

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        return {
            "variable": Variable,
            "operation": VariableWriteOperation,
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls, variable: Variable, operation: VariableWriteOperation
    ) -> List[Property]:
        value_type_description = variable.to_property()
        if operation == VariableWriteOperation.INSERT:
            if isinstance(value_type_description, ListProperty):
                return [
                    value_type_description.item_type.copy(
                        name=cls.VALUE,
                        description=value_type_description.item_type.description
                        or f"{value_type_description.description} (single element)",
                    )
                ]
            elif isinstance(value_type_description, DictProperty):
                return [
                    value_type_description.value_type.copy(
                        name=cls.VALUE,
                        description=value_type_description.value_type.description
                        or f"{value_type_description.description} (single element)",
                    )
                ]
            else:
                raise TypeError(
                    f"Can only apply insert write operation to lists, not {value_type_description.__class__}"
                )
        else:
            return [value_type_description.copy(name=cls.VALUE)]

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls, variable: Variable, operation: VariableWriteOperation
    ) -> List[Property]:
        return []

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        _put_variable_value_in_conversation_store(
            conversation=conversation,
            variable=self.variable,
            value=inputs[self.VALUE],
            operation=self.operation,
        )
        return StepResult(
            outputs={},
        )


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
