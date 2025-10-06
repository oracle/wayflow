# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

from wayflowcore.serialization.serializer import SerializableObject

if TYPE_CHECKING:
    from wayflowcore.flow import Flow
    from wayflowcore.serialization.context import DeserializationContext, SerializationContext


@dataclass
class DescribedFlow(SerializableObject):
    """
    DescribedFlow are used to store additional information about Flow
    to enable flow as tool support in the AgentExecutionStep.

    The name and description of the flow should represent the purpose of the
    flow when used as a tool.

    Parameters
    ----------
    flow:
        Flow object.
    name:
        Name of the flow.
    description:
        Description of the purpose of the flow when used as a tool.
    output:
        Description of the output of the flow.
    """

    flow: "Flow"
    name: str
    description: str
    output: Optional[str] = None

    def __post_init__(self) -> None:
        if self.output is not None and self.output not in self.flow.output_descriptors_dict:
            raise ValueError(
                f"'{self.output}' is not present in the outputs of the flow: {self.flow.output_descriptors_dict}"
            )
        from wayflowcore.flow import Flow

        if not isinstance(self.flow, Flow):
            raise ValueError(
                f"Attempting to create a `DescribedFlow` but `flow` is not of type `Flow`, is: {type(self.agent)}"
            )

    def to_config(
        self, serialization_context: Optional["SerializationContext"] = None
    ) -> Dict[str, Any]:
        """
        Converts the described flow to a configuration dictionary.

        Parameters
        ----------
        serialization_context:
            Serialization context for the object.

        Returns
        -------
        config:
            A dictionary representing the configuration of the described flow.
        """
        from wayflowcore.serialization.serializer import serialize_to_dict

        return {
            "name": self.name,
            "description": self.description,
            "output": self.output,
            "flow": serialize_to_dict(self.flow, serialization_context),
        }

    @staticmethod
    def from_config(
        config: Dict[str, Any], deserialization_context: Optional["DeserializationContext"] = None
    ) -> "DescribedFlow":
        """
        Creates a DescribedFlow object from a configuration dictionary.

        Parameters
        ----------
        config:
            Dictionary representing the configuration of the described flow.
        serialization_context:
            Serialization context for the object.

        Returns
        -------
            A DescribedFlow object created from the configuration.
        """
        from wayflowcore.flow import Flow
        from wayflowcore.serialization.serializer import deserialize_from_dict

        flow = deserialize_from_dict(Flow, config["flow"], deserialization_context)
        if not isinstance(flow, Flow):
            raise ValueError(
                f"During deserialization, expected an object of type Flow, but found: " f"{flow}"
            )
        return DescribedFlow(
            name=config["name"],
            description=config["description"],
            output=config.get("output"),
            flow=flow,
        )

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return self.to_config(serialization_context=serialization_context)

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        return cls.from_config(config=input_dict, deserialization_context=deserialization_context)
