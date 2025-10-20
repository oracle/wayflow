# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.property import Property
from wayflowcore.steps.step import Step, StepResult
from wayflowcore.variable import Variable

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation


class VariableReadStep(Step):
    """
    Step to perform a read on a Variable.
    This step has no input, and a single output "value".
    These variables are stored in a key-value store distinct from the I/O system.
    """

    VALUE = "value"
    """str: Output key for the read value from the ``VariableReadStep``."""

    def __init__(
        self,
        variable: Variable,
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

        This step has no input descriptor.

        **Output descriptors**

        This step has a single output descriptor:

        * ``VariableReadStep.VALUE``: ``variable type``, the value read from the variable store.

        Parameters
        ----------
        variable:
            ``Variable`` to read from.
            If the variable refers to a non-existent ``Variable`` (not passed into the flow), the flow constructor will throw an error.
            An exception is raised if the read returns a ``None`` value.
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
        >>> from wayflowcore.steps import VariableReadStep, OutputMessageStep
        >>> from wayflowcore.variable import Variable
        >>> from wayflowcore.property import ListProperty, FloatProperty
        >>>
        >>> float_variable = Variable(
        ...     name="float_variable",
        ...     type=ListProperty(item_type=FloatProperty()),
        ...     description="list of floats variable",
        ...     default_value=[1.0, 2.0, 3.0, 4.0],
        ... )
        >>>
        >>> read_step = VariableReadStep(variable=float_variable)
        >>> output_step = OutputMessageStep("The variable is {{ variable }}")
        >>>
        >>> flow = Flow(
        ...     begin_step=read_step,
        ...     control_flow_edges=[
        ...         ControlFlowEdge(read_step, output_step),
        ...         ControlFlowEdge(output_step, None),
        ...     ],
        ...     data_flow_edges=[
        ...         DataFlowEdge(read_step, VariableReadStep.VALUE, output_step, "variable"),
        ...     ],
        ...     variables=[float_variable],
        ... )
        >>> conv = flow.start_conversation()
        >>> status = conv.execute()
        >>> last_message = conv.get_last_message()
        >>> last_message.content
        'The variable is [1.0, 2.0, 3.0, 4.0]'

        """
        super().__init__(
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            step_static_configuration=dict(
                variable=variable,
            ),
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )
        self.variable = variable

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        return {"variable": Variable}

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls, variable: Variable
    ) -> List[Property]:
        return []

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls, variable: Variable
    ) -> List[Property]:
        return [variable.to_property().copy(name=cls.VALUE)]

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        variable_value = conversation._get_variable_value(self.variable)
        if variable_value is None:
            raise ValueError(
                f"Attempted to read from the Variable '{self.variable.name}' but the value was None."
            )
        return StepResult(
            outputs={self.VALUE: variable_value},
        )
