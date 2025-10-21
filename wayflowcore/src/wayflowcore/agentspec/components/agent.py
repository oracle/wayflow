# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import List, Optional

from pyagentspec.agent import Agent
from pyagentspec.component import SerializeAsEnum
from pyagentspec.flows.flow import Flow
from pyagentspec.versioning import AgentSpecVersionEnum
from pydantic import Field, SerializeAsAny

from wayflowcore.agent import DEFAULT_INITIAL_MESSAGE, CallerInputMode
from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)
from wayflowcore.agentspec.components.contextprovider import PluginContextProvider
from wayflowcore.agentspec.components.template import PluginPromptTemplate


class ExtendedAgent(Agent):
    """Agent that can handle a conversation with a user, interact with external tools
    and follow interaction flows. Compared to the basic Agent Spec Agent, this
    ExtendedAgent supports composition with subflows and subagents, custom
    prompt templates, context providers, and some more customizations on the agent's execution."""

    context_providers: Optional[List[SerializeAsAny[PluginContextProvider]]] = None
    """Context providers for jinja variables in the ``system_prompt``."""
    can_finish_conversation: bool = False
    """Whether the agent can decide to end the conversation or not."""
    max_iterations: int = 10
    """Maximum number of calls to the agent executor before yielding back to the user."""
    initial_message: Optional[str] = DEFAULT_INITIAL_MESSAGE
    """Initial message the agent will post if no previous user message.
    Default to ``Agent.DEFAULT_INITIAL_MESSAGE``. If None, the LLM will generate it but the agent requires
    a custom_instruction."""
    caller_input_mode: SerializeAsEnum[CallerInputMode] = CallerInputMode.ALWAYS
    """Whether the agent is allowed to ask the user questions (CallerInputMode.ALWAYS) or not (CallerInputMode.NEVER).
    If set to NEVER, the agent won't be able to yield."""
    agents: List[Agent] = Field(default_factory=list)
    """Other agents that the agent can call (expert agents)."""
    flows: List[Flow] = Field(default_factory=list)
    agent_template: Optional[SerializeAsAny[PluginPromptTemplate]] = None
    """Specific agent template for more advanced prompting techniques. It will be overloaded with the current
    agent ``tools``, and can have placeholders:
    * ``custom_instruction`` placeholder for the ``system_prompt`` parameter"""

    def _versioned_model_fields_to_exclude(
        self, agentspec_version: AgentSpecVersionEnum
    ) -> set[str]:
        return set()

    def _infer_min_agentspec_version_from_configuration(self) -> AgentSpecVersionEnum:
        return AgentSpecVersionEnum.v25_4_1


AGENT_PLUGIN_NAME = "AgentPlugin"

agent_serialization_plugin = PydanticComponentSerializationPlugin(
    name=AGENT_PLUGIN_NAME, component_types_and_models={ExtendedAgent.__name__: ExtendedAgent}
)
agent_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=AGENT_PLUGIN_NAME, component_types_and_models={ExtendedAgent.__name__: ExtendedAgent}
)
