# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from textwrap import dedent
from typing import TYPE_CHECKING, List

from wayflowcore.a2a.a2aagent import A2AAgent
from wayflowcore.conversation import Conversation
from wayflowcore.executors._a2aagentexecutor import A2AAgentState

if TYPE_CHECKING:
    from wayflowcore.contextproviders import ContextProvider
    from wayflowcore.conversation import Conversation


@dataclass
class A2AAgentConversation(Conversation):
    component: A2AAgent
    state: A2AAgentState

    @property
    def current_step_name(self) -> str:
        return "a2a_agent"

    def _get_all_context_providers_from_parent_conversations(self) -> List["ContextProvider"]:
        return []

    def _get_all_sub_conversations(self) -> List["Conversation"]:
        return []

    def __repr__(self) -> str:
        return f"A2AAgentConversation({self.get_messages()})"

    def __str__(self) -> str:
        result = f"State: {self.state}\nList of messages:\n"

        for i, message in enumerate(self.message_list.messages):
            message_str = dedent(
                """
                    Message #{}
                    Message type: {}
                    Message content:\n
                    {}\n
                """
            ).format(i, message.message_type, message.content)

            result += message_str
        return result
