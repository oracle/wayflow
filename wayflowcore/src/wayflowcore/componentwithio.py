# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
import logging
from abc import ABC
from typing import Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.component import Component
from wayflowcore.property import Property

logger = logging.getLogger(__name__)


class ComponentWithInputsOutputs(Component, ABC):
    """Class for all wayflowcore components with input and output descriptors"""

    def __init__(
        self,
        input_descriptors: List["Property"],
        output_descriptors: List["Property"],
        name: str,
        description: Optional[str],
        id: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        super().__init__(
            name=name, description=description, id=id, __metadata_info__=__metadata_info__
        )

        if len(set(property_.name for property_ in input_descriptors)) < len(input_descriptors):
            raise ValueError(
                f"Found several input descriptors with the same names: {input_descriptors}"
            )
        self.input_descriptors = input_descriptors

        if len(set(property_.name for property_ in output_descriptors)) < len(output_descriptors):
            raise ValueError(
                f"Found several output descriptors with the same names: {output_descriptors}"
            )
        self.output_descriptors = output_descriptors

    @staticmethod
    def _resolve_input_descriptors(
        specified_descriptors: Optional[List["Property"]],
        default_descriptors: List["Property"],
    ) -> List["Property"]:
        """
        Function to resolve the input descriptors of a component. The final input descriptors of the component will
        be:
        - the specified descriptors which names can be mapped to the default descriptors
        - the default descriptors for which no specified descriptors were found. This is so the step is guaranteed
          to have the all the inputs to work correctly.

        If some specified descriptors are found with names not matching the default descriptors, an error will be raised
        to avoid misspellings.
        If ``specified_descriptors`` is ``None``, will just use the default descriptors.
        """
        if specified_descriptors is None:
            return default_descriptors

        if len(set(descriptor.name for descriptor in specified_descriptors)) < len(
            specified_descriptors
        ):
            raise ValueError(
                f"Detected name conflicts in descriptors. Please ensure names are unique: {specified_descriptors}"
            )

        specified_descriptors_dict = {
            descriptor.name: descriptor for descriptor in specified_descriptors
        }

        final_descriptors = [
            specified_descriptors_dict.get(default_descriptor.name, default_descriptor)
            for default_descriptor in default_descriptors
        ]

        if len(set(descriptor.name for descriptor in final_descriptors)) < len(final_descriptors):
            final_descriptors = ComponentWithInputsOutputs._remove_properties_with_duplicate_names(
                final_descriptors
            )

        expected_input_names = [descriptor.name for descriptor in final_descriptors]
        for specified_descriptor in specified_descriptors:
            if specified_descriptor.name not in expected_input_names:
                raise ValueError(
                    f"Unknown input descriptor specified: {specified_descriptor}. Make sure there is no misspelling.\n"
                    f"Expected input descriptors are: {final_descriptors}"
                )

        return final_descriptors

    @staticmethod
    def _resolve_output_descriptors(
        specified_descriptors: Optional[List["Property"]],
        default_descriptors: List["Property"],
    ) -> List["Property"]:
        """
        Function to resolve the output descriptors of a component. The final output descriptors of the component will
        be:
        - the specified descriptors which names can be mapped to the default descriptors

        By default, if some specified descriptors are found with names not matching the default descriptors, an
        error will be raised to avoid misspellings.
        If ``specified_descriptors`` is ``None``, will just use the default descriptors.

        If the specified descriptors should change this component's behaviour, they should be taken into account
        in the default descriptors.
        """
        if specified_descriptors is None:
            return default_descriptors

        if len(set(descriptor.name for descriptor in specified_descriptors)) < len(
            specified_descriptors
        ):
            raise ValueError(
                f"Detected name conflicts in descriptors. Please ensure names are unique: {specified_descriptors}"
            )

        expected_output_names = {descriptor.name for descriptor in default_descriptors}
        for specified_descriptor in specified_descriptors:
            if specified_descriptor.name not in expected_output_names:
                raise ValueError(
                    f"Unknown output descriptor specified: {specified_descriptor}. Make sure there is no misspelling.\n"
                    f"Possible output descriptors are: {default_descriptors}"
                )
        final_output_descriptors = [
            default_descriptor
            for default_descriptor in specified_descriptors
            if default_descriptor.name in expected_output_names
        ]
        if len(set(descriptor.name for descriptor in final_output_descriptors)) < len(
            final_output_descriptors
        ):
            final_output_descriptors = (
                ComponentWithInputsOutputs._remove_properties_with_duplicate_names(
                    final_output_descriptors
                )
            )

        return final_output_descriptors

    @staticmethod
    def _remove_properties_with_duplicate_names(properties: List[Property]) -> List[Property]:
        selected_properties = []

        descriptors_per_name_groups: Dict[str, List[Property]] = {}
        for descriptor in properties:
            if descriptor.name not in descriptors_per_name_groups:
                descriptors_per_name_groups[descriptor.name] = []
            descriptors_per_name_groups[descriptor.name].append(descriptor)

        for descriptor_name, all_descriptors in descriptors_per_name_groups.items():
            if len(all_descriptors) > 1:
                logger.warning(
                    f"Detected name conflicts in resolved descriptors. Only this descriptor will be used for name `%s`: %s.\nAll descriptors: %s",
                    descriptor_name,
                    all_descriptors[-1],
                    all_descriptors,
                )
                selected_properties.append(all_descriptors[-1])
            else:
                selected_properties.append(all_descriptors[0])
        return selected_properties
