# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import List

from pyagentspec.agent import Agent
from pyagentspec.component import ComponentWithIO
from pyagentspec.validation_helpers import model_validator_with_error_accumulation
from pydantic import Field, SerializeAsAny
from typing_extensions import Self

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)


class PluginSwarm(ComponentWithIO):
    """Defines a ``Swarm`` conversational component.

    A ``Swarm`` is a multi-agent conversational component in which each agent determines
    the next agent to be executed, based on a list of pre-defined relationships."""

    first_agent: SerializeAsAny[Agent]
    """What is the first ``Agent`` to interact with the human user."""
    relationships: List[List[SerializeAsAny[Agent]]] = Field(default_factory=list)
    """Determine the list of allowed interactions in the ``Swarm``.
    Each element in the list is a tuple ``(caller_agent, recipient_agent)``
    specifying that the ``caller_agent`` can query the ``recipient_agent``."""
    handoff: bool = True
    """* When ``False``, agent can only talk to each other, the ``first_agent`` is fixed for the entire conversation;
    * When ``True``, agents can handoff the conversation to each other, i.e. transferring the list of messages between
      an agent and the user to another agent in the Swarm. They can also talk to each other as when ``handoff=False``"""

    @model_validator_with_error_accumulation
    def _validate_one_or_more_relations(self) -> Self:
        if len(self.relationships) == 0:
            raise ValueError(
                "Cannot define a `Swarm` with no relationships between the agents. "
                "Use an `Agent` instead."
            )

        return self


SWARM_PLUGIN_NAME = "SwarmPlugin"

swarm_serialization_plugin = PydanticComponentSerializationPlugin(
    name=SWARM_PLUGIN_NAME, component_types_and_models={PluginSwarm.__name__: PluginSwarm}
)
swarm_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=SWARM_PLUGIN_NAME, component_types_and_models={PluginSwarm.__name__: PluginSwarm}
)
