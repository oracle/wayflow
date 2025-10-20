# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterable, Callable, Dict, List, Optional, Sequence

from wayflowcore._utils.async_helpers import run_async_in_sync
from wayflowcore.component import DataclassComponent
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.executors._events.event import Event
from wayflowcore.executors.executionstatus import (
    ExecutionStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
)
from wayflowcore.messagelist import Message, MessageList
from wayflowcore.planning import ExecutionPlan
from wayflowcore.tokenusage import TokenUsage

if TYPE_CHECKING:
    from wayflowcore.contextproviders import ContextProvider
    from wayflowcore.executors._executionstate import ConversationExecutionState
    from wayflowcore.executors.interrupts.executioninterrupt import ExecutionInterrupt
    from wayflowcore.models._requesthelpers import TaggedMessageChunkType
    from wayflowcore.tools import ToolResult


ContextProviderType = Callable[["Conversation"], Any]


@dataclass
class Conversation(DataclassComponent):

    component: ConversationalComponent
    state: "ConversationExecutionState"
    inputs: Dict[str, Any]
    message_list: MessageList
    status: Optional[ExecutionStatus]
    token_usage: TokenUsage = field(default_factory=TokenUsage, init=False)
    conversation_id: str = ""  # deprecated

    def __post_init__(self) -> None:
        if self.inputs is None:
            self.inputs = {}

    @property
    def plan(self) -> Optional[ExecutionPlan]:
        return None

    def _get_interrupts(self) -> Optional[List["ExecutionInterrupt"]]:
        return self.state.interrupts

    def _register_event(self, event: Event) -> None:
        self.state._register_event(event)

    def execute(
        self,
        execution_interrupts: Optional[Sequence["ExecutionInterrupt"]] = None,
    ) -> "ExecutionStatus":
        """
        Execute the conversation and get its ``ExecutionStatus`` based on the outcome.

        The ``Execution`` status is returned by the Assistant and indicates if the assistant yielded,
        finished the conversation.
        """
        return run_async_in_sync(
            self.execute_async, execution_interrupts, method_name="execute_async"
        )

    async def execute_async(
        self,
        execution_interrupts: Optional[Sequence["ExecutionInterrupt"]] = None,
    ) -> "ExecutionStatus":
        """
        Execute the conversation and get its ``ExecutionStatus`` based on the outcome.

        The ``Execution`` status is returned by the Assistant and indicates if the assistant yielded,
        finished the conversation.
        """
        self.status = await self.component.runner.execute_async(self, execution_interrupts)
        return self.status

    @property
    @abstractmethod
    def current_step_name(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    def _get_all_context_providers_from_parent_conversations(
        self,
    ) -> List["ContextProvider"]:
        """Gathers all context providers from this conversation and all parent conversations"""
        raise NotImplementedError()

    @abstractmethod
    def _get_all_sub_conversations(self) -> List["Conversation"]:
        """Gathers all sub conversations"""
        raise NotImplementedError()

    @abstractmethod
    def __repr__(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    def __str__(self) -> str:
        raise NotImplementedError()

    def get_messages(self) -> List[Message]:
        """Return all ``Message`` objects of the messages list in a python list."""
        return self.message_list.get_messages()

    def get_last_message(self) -> Optional[Message]:
        """Get the last message from the messages List."""
        return self.message_list.get_last_message()

    def append_message(self, message: Message) -> None:
        """Append a message to the messages list of this ``Conversation`` object.

        Parameters
        ----------
        message:
            message to append.
        """
        self.message_list.append_message(message)

    def append_agent_message(self, agent_input: str, is_error: bool = False) -> None:
        """Append a new message object of type ``MessageType.AGENT`` to the messages list.

        Parameters
        ----------
        agent_input:
            message to append.
        """
        self.message_list.append_agent_message(agent_input, is_error)

    def append_user_message(self, user_input: str) -> None:
        """Append a new message object of type ``MessageType.USER`` to the messages list.

        Parameters
        ----------
        user_input:
            message to append.
        """
        self.message_list.append_user_message(user_input)

    def append_tool_result(self, tool_result: "ToolResult") -> None:
        """Append a new message object of type ``MessageType.TOOL_RESULT`` to the messages list.

        Parameters
        ----------
        tool_result:
            message to append.
        """
        if (
            isinstance(self.status, (ToolRequestStatus, ToolExecutionConfirmationStatus))
            and self.status._conversation_id == self.id
        ):
            # we should append to this conversation message list only if
            # it is the conversation the ToolRequestStatus/ToolExecutionConfirmationStatus originated from.
            self.message_list.append_tool_result(tool_result)
        else:
            # otherwise, we need to propagate the tool_result to sub conversations
            # to append the message to the conversation bound to the ToolRequestStatus/ToolExecutionConfirmationStatus
            for conv in self._get_all_sub_conversations():
                conv.append_tool_result(tool_result)

    async def _append_streaming_message(
        self,
        stream: AsyncIterable["TaggedMessageChunkType"],
        extract_func: Optional[Callable[[Any], "TaggedMessageChunkType"]] = None,
    ) -> Message:
        return await self.message_list._append_streaming_message(stream, extract_func)
