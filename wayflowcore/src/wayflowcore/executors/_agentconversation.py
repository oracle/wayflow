# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Dict, List, Optional, Set

from wayflowcore.agent import Agent
from wayflowcore.contextproviders import ContextProvider
from wayflowcore.conversation import Conversation
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.executors._agentexecutor import AgentConversationExecutionState
from wayflowcore.planning import ExecutionPlan


@dataclass
class AgentConversation(Conversation):
    component: Agent
    state: AgentConversationExecutionState

    @property
    def plan(self) -> Optional[ExecutionPlan]:
        return self.state.plan

    async def _get_context_provider_values(
        self,
        variable_names: Set[str],
        additional_context_providers: Optional[List["ContextProvider"]],
    ) -> Dict[str, Any]:

        context_providers_values: Dict[str, Any] = {}

        for context_provider in additional_context_providers or []:
            provider_output_descriptions = context_provider.get_output_descriptors()
            if any(
                output_description.name in variable_names
                for output_description in provider_output_descriptions
            ):
                values = await context_provider.call_async(self)
                if len(provider_output_descriptions) == 1:
                    values = [values]
                for value, value_description in zip(values, provider_output_descriptions):
                    if value_description.name in variable_names:
                        context_providers_values[value_description.name] = value

        if set(context_providers_values.keys()) != variable_names:
            raise ValueError(
                f"Missing some contextual variables in conversation, {context_providers_values}, {variable_names}"
            )

        return context_providers_values

    def _get_all_context_providers_from_parent_conversations(
        self,
    ) -> List["ContextProvider"]:
        return []

    def _get_all_sub_conversations(self) -> List["Conversation"]:
        # subconversations of an Agent are conversations from any sub-component,
        # including sub-agents and (sub-)flows.
        sub_conversations = list(self.state.current_sub_component_conversations.values())
        if self.state.current_flow_conversation is not None:
            sub_conversations += [self.state.current_flow_conversation]
        return sub_conversations

    def _get_sub_component_conversation(
        self, component: ConversationalComponent
    ) -> Optional["Conversation"]:
        return self.state.current_sub_component_conversations.get(component.id)

    def _set_sub_component_conversation(
        self, component: ConversationalComponent, conversation: Optional["Conversation"]
    ) -> None:
        identifier = component.id
        component_conversations = self.state.current_sub_component_conversations
        if not conversation and identifier in component_conversations:
            component_conversations.pop(identifier)
        elif conversation:  # otherwise we add only if the conversation is not None
            component_conversations[identifier] = conversation

    @property
    def current_step_name(self) -> str:
        return "agent"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message_list={repr(self.message_list)}, state={repr(self.state)})"

    def __str__(self) -> str:
        result = f"State: {self.state}\nList of messages:\n"

        for i, message in enumerate(self.message_list.messages):
            message_str = dedent(
                f"""
            Message #{i}
            Message type: {message.message_type}
            Message content:\n
            {message.content}\n
            tool_requests: {message.tool_requests}
            tool_results: {message.tool_result}
            """
            )

            result += message_str
        return result

    @property
    def agent(self) -> "Agent":
        return self.component
