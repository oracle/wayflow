# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

from wayflowcore.serialization.serializer import SerializableObject

if TYPE_CHECKING:
    from wayflowcore.agent import Agent
    from wayflowcore.serialization.context import DeserializationContext, SerializationContext


@dataclass
class DescribedAgent(SerializableObject):
    """
    DescribedAgent are used to store additional information about agents
    to enable their use as tool support in the AgentExecutionStep.

    The name and description of the agent should represent the purpose of the
    agent when used as a tool.

    Parameters
    ----------
    agent:
        Agent object.
    name:
        Name of the agent.
    description:
        Description of the purpose of the agent when used as a tool.
    """

    agent: "Agent"
    name: str
    description: str

    def __post_init__(self) -> None:
        from wayflowcore.agent import Agent

        if not isinstance(self.agent, Agent):
            raise ValueError(
                f"Attempting to create a `DescribedAgent` but `agent` is not of type `Agent`, is: {type(self.agent)}"
            )

    def to_config(self, serialization_context: Optional["SerializationContext"]) -> Dict[str, Any]:
        """
        Converts the described agent to a configuration dictionary.

        Parameters
        ----------
        serialization_context:
            Serialization context for the object.

        Returns
        -------
        Dict:
            A dictionary representing the configuration of the described agent.
        """
        from wayflowcore.serialization.serializer import serialize_to_dict

        return {
            "name": self.name,
            "description": self.description,
            "agent": serialize_to_dict(self.agent, serialization_context),
        }

    @staticmethod
    def from_config(
        config: Dict[str, Any], deserialization_context: Optional["DeserializationContext"]
    ) -> "DescribedAgent":
        """
        Creates a DescribedAgent object from a configuration dictionary.

        Parameters
        ----------
        config:
            Dictionary representing the configuration of the described agent.
        deserialization_context:
            Deserialization context for the object.

        Returns
        -------
        DescribedAgent:
            A DescribedAgent object created from the configuration.
        """
        from wayflowcore.agent import Agent
        from wayflowcore.serialization.serializer import deserialize_from_dict

        # backward compatibility
        if "agent" not in config.keys() and "assistant" in config.keys():
            config["agent"] = config.pop("assistant")

        agent = deserialize_from_dict(Agent, config["agent"], deserialization_context)

        return DescribedAgent(
            name=config["name"],
            description=config["description"],
            agent=agent,
        )

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return self.to_config(serialization_context=serialization_context)

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        return cls.from_config(config=input_dict, deserialization_context=deserialization_context)
