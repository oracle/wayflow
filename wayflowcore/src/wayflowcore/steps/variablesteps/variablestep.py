# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from collections import Counter
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Union

from wayflowcore._metadata import MetadataType
from wayflowcore.property import Property
from wayflowcore.steps.step import Step, StepResult
from wayflowcore.steps.variablesteps._utils import (
    _compute_variable_input_descriptor,
    _put_variable_value_in_conversation_store,
    _require_variable_value_from_conversation_store,
    _validate_write_step_configurations,
)
from wayflowcore.variable import Variable, VariableWriteOperation

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation


class VariableStep(Step):
    """
    Step to perform a write, read, or both of them on one or more variables.
    These variables are stored in a key-value store distinct from the I/O system.
    If both read and write is instructed for a variable, the step will perform write first, and read the updated value afterward.
    """

    def __init__(
        self,
        write_variables: Optional[List[Variable]] = None,
        read_variables: Optional[List[Variable]] = None,
        operations: Optional[
            Union[
                VariableWriteOperation,
                Dict[str, VariableWriteOperation],
            ]
        ] = None,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        A step has input and output descriptors, describing what values the step requires to run and what values it produces.

        If both read and write is instructed for a variable, the step will perform write first, and read the updated value afterward.

        **Input descriptors**

        This step has an input descriptor for each variable in ``write_variables`` as follows:

        * ``variable.name``: ``??``, the value to write in the variable store. Type will be resolved depending on the variable type and the type of variable write operation.

        **Output descriptors**

        This step has an output descriptor for each variable in `read_variables` as follows:

        * ``variable.name``: ``variable type``, the value read from the variable store.

        Parameters
        ----------
        write_variables:
            list of ``Variable``s to write to. Leave it as default (``None``) or empty (``[]``) if you don't have a write operation in this step.

        read_variables:
            list of ``Variable``s to read from. Leave it as default (``None``) or empty (``[]``) if you don't have a read operation in this step.

        operations:
            The type of operation to perform on ``write_variables``. The keys are the name of the write variables.

            If ``write_variables`` is ``None`` or an empty list, the value of this variable should also be left as default, be ``None``, or an empty dictionary (``{}``).

            If you have one or more variables in ``write_variables``, then this step will have write operations involved. You can set a single operation for all of the variables or use a dictionary to specify the operation for each variable separately. If you use a dictionary, you should specify the operation for all the variables in `write_variables`. Missing an operation for any variable in `write_variables` leads to a ValueError.

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
        >>> from wayflowcore.dataconnection import DataFlowEdge
        >>> from wayflowcore.steps import OutputMessageStep, VariableStep
        >>> from wayflowcore.variable import Variable, VariableWriteOperation
        >>> from wayflowcore.property import ListProperty, FloatProperty
        >>> variable = Variable(
        ...     name="variable",
        ...     type=ListProperty(item_type=FloatProperty()),
        ...     description="list of floats variable",
        ...     default_value=[1.0],
        ... )
        >>>
        >>> variable_step = VariableStep(
        ...     write_variables=[variable],
        ...     read_variables=[variable],
        ...     operations=VariableWriteOperation.MERGE,
        ... )
        >>>
        >>> output_step = OutputMessageStep("The variable is {{ value }}.")
        >>> flow = Flow(
        ...     begin_step=variable_step,
        ...     control_flow_edges=[
        ...         ControlFlowEdge(variable_step, output_step),
        ...         ControlFlowEdge(output_step, None),
        ...     ],
        ...     data_flow_edges=[
        ...         DataFlowEdge(variable_step, variable.name, output_step, "value"),
        ...     ],
        ...     variables=[variable],
        ... )
        >>>
        >>> conv = flow.start_conversation(inputs={variable.name: [2.0, 3.0, 4.0]})
        >>> status = conv.execute()
        >>> last_message = conv.get_last_message()
        >>> last_message.content
        'The variable is [1.0, 2.0, 3.0, 4.0].'

        """

        write_variables = write_variables or []
        read_variables = read_variables or []

        if len(write_variables) == len(read_variables) == 0:
            raise ValueError(
                "Void `VariableStep`: At least one variable must be subject to read or write. "
                "Add the variables that must be read/written by this step to `read_variables`/`write_variables`. "
                "If you don't have any variables to read/write, this step should be omitted."
            )

        _requires_unique_variable_names(write_variables)
        _requires_unique_variable_names(read_variables)

        operations = _requires_operations_dictionary(
            write_variables=write_variables,
            operations=operations,
        )

        for write_var in write_variables:
            _validate_write_step_configurations(
                write_var,
                VariableStep._requires_operation_of_a_var(write_var, operations),
            )

        super().__init__(
            step_static_configuration=dict(
                write_variables=write_variables,
                read_variables=read_variables,
                operations=operations,
            ),
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )
        self.write_variables = write_variables
        self.read_variables = read_variables
        self.operations = operations

    @classmethod
    def _requires_operation_of_a_var(
        cls,
        variable: Variable,
        operations: Dict[str, VariableWriteOperation],
    ) -> VariableWriteOperation:
        op = operations.get(variable.name, None)
        if op is None:
            raise RuntimeError(
                f"No operation found associated with variable {variable.name}. "
                "The code is guarded against this case in the class initialization checks and this should not happen in usual use cases. "
                "Please ensure you do not modify the arguments passed to the initializer of the step after initialization."
            )
        return op

    def _requires_operation_of_write_var(self, variable: Variable) -> VariableWriteOperation:
        return VariableStep._requires_operation_of_a_var(variable, self.operations)

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        return {
            "write_variables": List[Variable],
            "read_variables": List[Variable],
            "operations": Dict[str, VariableWriteOperation],
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        read_variables: List[Variable],
        write_variables: List[Variable],
        operations: Dict[str, VariableWriteOperation],
    ) -> List[Property]:
        return [
            _compute_variable_input_descriptor(
                write_var,
                cls._requires_operation_of_a_var(write_var, operations),
            )
            for write_var in write_variables
        ]

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        read_variables: List[Variable],
        write_variables: List[Variable],
        operations: Dict[str, VariableWriteOperation],
    ) -> List[Property]:
        return [read_var.to_property().copy(name=read_var.name) for read_var in read_variables]

    def _write_values(
        self,
        variables_to_write: List[Variable],
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> None:
        for write_var in variables_to_write:
            _put_variable_value_in_conversation_store(
                conversation=conversation,
                variable=write_var,
                value=inputs[write_var.name],
                operation=self._requires_operation_of_write_var(write_var),
            )

    def _read_variables(
        self, variables_to_read: List[Variable], conversation: "FlowConversation"
    ) -> Dict[str, Any]:
        return {
            read_var.name: _require_variable_value_from_conversation_store(read_var, conversation)
            for read_var in variables_to_read
        }

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        self._write_values(self.write_variables, inputs, conversation)
        reads_outputs = self._read_variables(self.read_variables, conversation)
        return StepResult(outputs=reads_outputs)


def _get_non_unique_elements(iterable: Iterable[Any]) -> List[str]:
    return [element for element, count in Counter(iterable).items() if count > 1]


def _requires_unique_variable_names(variables: List[Variable]) -> None:
    non_unique_var_names = _get_non_unique_elements(map(lambda v: v.name, variables))
    if len(non_unique_var_names) != 0:
        non_unique_var_names_str = ", ".join(non_unique_var_names)
        raise ValueError(
            "Duplicate names are not allowed in `write_variables` or `read_variables`. "
            f"Variable(s) {non_unique_var_names_str} appear(s) more than once. "
            "A variable may appear in both `read_variables` and `write_variables`, but not more than once in any of them. "
            "Each of `read_variables` and `write_variables` must contain unique variables."
        )


def _requires_operations_dictionary(
    write_variables: List[Variable],
    operations: Optional[
        Union[
            VariableWriteOperation,
            Dict[str, VariableWriteOperation],
        ]
    ],
) -> Dict[str, VariableWriteOperation]:

    no_operations = operations is None or (isinstance(operations, dict) and len(operations) == 0)
    no_write_variable = len(write_variables) == 0

    if no_write_variable and no_operations:
        return {}

    if no_write_variable:
        raise ValueError(
            f"Non-default `operations` has been specified as '{operations}' (type: {type(operations)}) while `write_variables` contains no variable. "
            "This is seemingly a misuse of `VariableStep`, as the `operations` specify the kind of write operations that must apply to the variables in `write_variables`. "
            "If there is no intention of writing a variable in this step, you should omit passing a value to the argument `operations`. "
            "Otherwise, you should also declare the intended variable in `write_variables`."
        )

    if no_operations:
        raise ValueError(
            f"Argument `operations` cannot be `None` or empty while `write_variables` is non-empty."
        )

    if isinstance(operations, VariableWriteOperation):
        return {var.name: operations for var in write_variables}

    if isinstance(operations, dict):
        operations_vars_names = set(operations.keys())

        write_vars_names = {var.name for var in write_variables}

        write_variable_with_no_operation = write_vars_names - operations_vars_names
        if len(write_variable_with_no_operation) != 0:
            write_variable_with_no_operation_str = ", ".join(write_variable_with_no_operation)
            raise ValueError(
                "All of the variables in `write_variables` must have an associated operation. "
                f"Variable(s) {write_variable_with_no_operation_str} is/are defined in `write_variables`, but there is no operation associated with them in the `operations` dictionary."
            )

        operations_with_no_declared_variables = operations_vars_names - write_vars_names
        if len(operations_with_no_declared_variables) != 0:
            operations_with_no_declared_variables_str = ", ".join(
                operations_with_no_declared_variables
            )
            raise ValueError(
                "All of the variable name in `operations` must be associated with a variable in `write_variables`, "
                f"but operations dictionary additionally specifies {operations_with_no_declared_variables_str}. "
                f"There is/are operation(s) specified for variable(s) {operations_with_no_declared_variables_str} in the dictionary passed as `operations`, while these variables are not declared in `write_variables`. "
                "If you want to perform a write operation on a variable, the variable must be present in `write_variables`."
            )

        return operations

    raise ValueError(
        "Argument `operations` must be a VariableWriteOperation or a dictionary of str -> VariableWriteOperation. "
        f"Found {operations} with type {type(operations)} instead."
    )
