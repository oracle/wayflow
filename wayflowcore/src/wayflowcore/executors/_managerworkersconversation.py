# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional

from wayflowcore.agent import Agent
from wayflowcore.conversation import Conversation
from wayflowcore.executors._executionstate import ConversationExecutionState
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.messagelist import Message, MessageContent
from wayflowcore.tools import ToolResult

if TYPE_CHECKING:
    from wayflowcore.contextproviders import ContextProvider
    from wayflowcore.executors._agentconversation import AgentConversation

logger = logging.getLogger(__name__)


@dataclass
class ManagerWorkersConversationExecutionState(ConversationExecutionState):
    current_agent_name: str
    subconversations: Dict[str, "AgentConversation"]

    def _create_subconversation_for_agent(self, agent: Agent) -> "AgentConversation":
        subconv = agent.start_conversation()
        self.subconversations[agent.name] = subconv

        return subconv


@dataclass
class ManagerWorkersConversation(Conversation):
    component: ManagerWorkers
    state: ManagerWorkersConversationExecutionState

    @property
    def managerworkers(self) -> "ManagerWorkers":
        return self.component

    @property
    def subconversations(self) -> Dict[str, "AgentConversation"]:
        return self.state.subconversations

    @property
    def current_step_name(self) -> str:
        return "ManagerWorkers"

    def _get_all_context_providers_from_parent_conversations(
        self,
    ) -> List["ContextProvider"]:
        return []

    def _get_all_sub_conversations(self) -> List["Conversation"]:
        return list(self.state.subconversations.values())

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(state={self.state!r}, subconversations={self.subconversations!r})"

    def __str__(self) -> str:
        return repr(self)

    def _get_agent_subconversation(self, agent_name: str) -> Optional["AgentConversation"]:
        return self.state.subconversations.get(agent_name)

    def _get_main_subconversation(
        self,
    ) -> "AgentConversation":
        "Return subconversation between the manger agent and the user"
        main_subconv = self._get_agent_subconversation(self.component.manager_agent.name)
        if main_subconv is None:
            raise (ValueError(f"Internal error: Main subconversation is None"))
        return main_subconv

    def append_tool_result(self, tool_result: ToolResult) -> None:
        current_conv = self._get_agent_subconversation(self.state.current_agent_name)
        if current_conv is None:
            raise (ValueError(f"Internal error: Current subconversation is None"))
        current_conv.append_tool_result(tool_result)

    def append_user_message(self, user_input: str | list[MessageContent]) -> None:
        """Append a new message object of type ``MessageType.USER`` to the main thread.

        Parameters
        ----------
        user_input:
            message to append.
        """
        self._get_main_subconversation().append_user_message(user_input)

    def get_messages(self) -> List[Message]:
        return self._get_main_subconversation().get_messages()

    def get_last_message(self) -> Optional[Message]:
        return self._get_main_subconversation().get_last_message()
