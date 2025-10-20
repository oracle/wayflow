# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


from typing import Any, Dict, List, Optional, Type

from wayflowcore._metadata import MetadataType
from wayflowcore.conversation import Conversation
from wayflowcore.property import (
    BooleanProperty,
    FloatProperty,
    IntegerProperty,
    Property,
    StringProperty,
)
from wayflowcore.steps.step import Step, StepResult


class ConstantValuesStep(Step):
    _output_descriptors_change_step_behavior = True

    def __init__(
        self,
        constant_values: Dict[str, Any],
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Step to provide constant values.


        Note
        ----

        **Output descriptors**

        The output descriptors of this step are automatically inferred and
        generated based on the values and names provided in the configuration.
        The supported types are integer, float, boolean and string.

        Parameters
        ----------
        constant_values:
            Dictionary mapping names to constant values.

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
        >>> from wayflowcore.steps import ConstantValuesStep
        >>> from wayflowcore.flowhelpers import create_single_step_flow
        >>> assistant = create_single_step_flow(ConstantValuesStep(constant_values={"PI":3.14, "PI_string": "3.14"}))
        >>> conversation = assistant.start_conversation()
        >>> status = conversation.execute()
        >>> status.output_values["PI"] == 3.14
        True
        >>> status.output_values["PI_string"] == "3.14"
        True


        """
        self.constant_values = constant_values
        super().__init__(
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            step_static_configuration=dict(constant_values=constant_values),
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            __metadata_info__=__metadata_info__,
            name=name,
        )

    @staticmethod
    def _infer_type(value: str) -> Type[Property]:
        """Infer the type of the configuration value."""
        if isinstance(value, bool):
            # isinstance(True, int) will return true, so we need to have bool at the top
            return BooleanProperty
        elif isinstance(value, int):
            return IntegerProperty
        elif isinstance(value, float):
            return FloatProperty
        elif isinstance(value, str):
            return StringProperty
        else:
            raise ValueError(f"Value of type {type(value)} not supported in ConstantValuesStep.")

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        return {"constant_values": Dict[str, Any]}

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        constant_values: Dict[str, Any],
        output_descriptors: Optional[List[Property]],
    ) -> List[Property]:
        return []

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        constant_values: Dict[str, Any],
        output_descriptors: Optional[List[Property]],
    ) -> List[Property]:

        if output_descriptors is None:
            output_descriptors = []
            for name, constant in constant_values.items():
                if not isinstance(name, str):
                    raise ValueError(
                        f"Name of values in the ConstantValuesStep must be string, "
                        f"received value with name {name} of type {type(name)}"
                    )
                property_class = cls._infer_type(constant)
                output_descriptors.append(
                    property_class(
                        name=name,
                        description=f"constant value with name {name}",
                    )
                )
        else:
            for descriptor in output_descriptors:
                if descriptor.name not in constant_values:
                    raise ValueError(
                        f"Provided output descriptor name {descriptor.name} does not exist in the constant values."
                    )
                value = constant_values[descriptor.name]
                if not descriptor.is_value_of_expected_type(value):
                    raise ValueError(
                        f"The value {value} with name {descriptor.name} does not have an appropriate type according to the provided output descriptor."
                    )

        return output_descriptors

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: Conversation,
    ) -> StepResult:
        return StepResult(
            outputs=self.constant_values,
        )
