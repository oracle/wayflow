# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from wayflowcore.agent import Agent
from wayflowcore.conversation import Conversation
from wayflowcore.executors._executionstate import ConversationExecutionState
from wayflowcore.messagelist import Message, MessageList
from wayflowcore.serialization.serializer import SerializableDataclass
from wayflowcore.tools import ToolResult

if TYPE_CHECKING:
    from wayflowcore.agentconversation import AgentConversation
    from wayflowcore.contextproviders import ContextProvider
    from wayflowcore.swarm import Swarm
from wayflowcore.swarm import Swarm

if TYPE_CHECKING:
    from wayflowcore.executors._agentconversation import AgentConversation


logger = logging.getLogger(__name__)


@dataclass
class SwarmUser(SerializableDataclass):
    name: str = field(default="Human User", init=False)


@dataclass
class SwarmThread(SerializableDataclass):
    caller: Union[Agent, SwarmUser]
    recipient_agent: Agent
    message_list: MessageList = field(default_factory=lambda: MessageList())
    is_main_thread: bool = False

    @property
    def identifier(self) -> str:
        if self.is_main_thread:
            return "MAIN"
        return f"{self.caller.name}#{self.recipient_agent.name}"


@dataclass
class SwarmConversationExecutionState(ConversationExecutionState):
    inputs: Any
    messages: Any
    main_thread: SwarmThread
    agents_and_threads: Dict[str, Dict[str, SwarmThread]]
    context_providers: List["ContextProvider"]
    current_thread: Optional["SwarmThread"] = None
    thread_stack: List["SwarmThread"] = field(default_factory=list)

    thread_subconversations: Dict[str, "AgentConversation"] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.current_thread = self.current_thread or self.main_thread

        if not self.thread_subconversations:
            self._create_subconversation_for_thread(
                self.main_thread, inputs=self.inputs, message_list=self.messages
            )

    def _create_subconversation_for_thread(
        self,
        thread: "SwarmThread",
        inputs: Optional[Dict[str, Any]] = None,
        message_list: Optional[Union[MessageList, List[Message]]] = None,
    ) -> "AgentConversation":
        thread_id = thread.identifier
        if thread_id in self.thread_subconversations:
            raise KeyError(
                f"Trying to create a new subconversation for thread {thread_id} but a conversation already exists"
            )

        if message_list is not None:
            thread.message_list = (
                MessageList(message_list) if isinstance(message_list, list) else message_list
            )
        conversation = thread.recipient_agent.start_conversation(
            inputs=inputs,
            messages=thread.message_list,
        )
        self.thread_subconversations[thread_id] = conversation

        return conversation


@dataclass
class SwarmConversation(Conversation):
    component: Swarm
    state: SwarmConversationExecutionState

    @property
    def swarm(self) -> "Swarm":
        return self.component

    @property
    def thread_subconversations(self) -> dict[str, "AgentConversation"]:
        return self.state.thread_subconversations

    @property
    def current_step_name(self) -> str:
        return "Swarm"

    def _get_all_context_providers_from_parent_conversations(
        self,
    ) -> List["ContextProvider"]:
        return []

    def _get_all_sub_conversations(self) -> List["Conversation"]:
        return []

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(state={self.state!r}, thread_subconversations={self.thread_subconversations!r})"

    def __str__(self) -> str:
        return repr(self)

    def _get_main_thread_conversation(self) -> "AgentConversation":
        agent_conv = self._get_subconversation_for_thread(self.state.main_thread)
        if not agent_conv:
            raise ValueError("Agent conversation for main thread is None")
        return agent_conv

    def get_messages(self) -> List[Message]:
        """Return all ``Message`` objects of the messages list in a python list."""
        return self._get_main_thread_conversation().get_messages()

    def get_last_message(self) -> Optional[Message]:
        return self._get_main_thread_conversation().get_last_message()

    def append_tool_result(self, tool_result: ToolResult) -> None:
        current_thread = self.state.current_thread
        if current_thread is None:
            raise ValueError(f"Internal error: Current thread is None")

        current_conv = self._get_subconversation_for_thread(current_thread)
        if current_conv is None:
            raise ValueError(f"Internal error: Current subconversation is None")

        current_conv.append_tool_result(tool_result)

    def append_user_message(self, user_input: str) -> None:
        """Append a new message object of type ``MessageType.USER`` to the main thread.

        Parameters
        ----------
        user_input:
            message to append.
        """
        self._get_main_thread_conversation().append_user_message(user_input)

    def _get_subconversation_for_thread(
        self, thread: "SwarmThread"
    ) -> Optional["AgentConversation"]:
        return self.thread_subconversations.get(thread.identifier)

    def _get_recipient_names_for_agent(self, agent: Agent) -> List[str]:
        if agent.name not in self.state.agents_and_threads:
            raise ValueError(f"Agent {agent} is not a sender of any thread")
        return list(self.state.agents_and_threads[agent.name].keys())
