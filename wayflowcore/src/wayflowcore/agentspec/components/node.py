# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
from abc import abstractmethod
from typing import Dict, List

from pyagentspec import Property
from pyagentspec.flows.node import Node as AgentSpecNode
from pydantic import Field


class ExtendedNode(AgentSpecNode, abstract=True):
    """Extended version of the Agent Spec node, supports input and output name mappings"""

    input_mapping: Dict[str, str] = Field(default_factory=dict)
    """Mapping between the name of the inputs this step expects and the name
       to get it from in the conversation input/output dictionary."""

    output_mapping: Dict[str, str] = Field(default_factory=dict)
    """Mapping between the name of the outputs this step expects and the name
       to get it from in the conversation input/output dictionary."""

    def _get_inferred_inputs(self) -> List[Property]:
        non_mapped_inputs = self._get_non_mapped_inferred_inputs()
        mapped_inputs = [
            Property(
                json_schema={
                    **input_property.json_schema,
                    "title": self.input_mapping.get(input_property.title, input_property.title),
                }
            )
            for input_property in non_mapped_inputs
        ]
        return mapped_inputs

    def _get_inferred_outputs(self) -> List[Property]:
        non_mapped_outputs = self._get_non_mapped_inferred_outputs()
        mapped_outputs = [
            Property(
                json_schema={
                    **output_property.json_schema,
                    "title": self.output_mapping.get(output_property.title, output_property.title),
                }
            )
            for output_property in non_mapped_outputs
        ]
        return mapped_outputs

    @abstractmethod
    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        raise NotImplementedError("Not implemented abstract method")

    @abstractmethod
    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        raise NotImplementedError("Not implemented abstract method")
