# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging
import warnings
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterable, Callable, Dict, List, Optional, Sequence

from wayflowcore._utils.async_helpers import run_async_in_sync
from wayflowcore.component import DataclassComponent
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.executors._events.event import Event
from wayflowcore.executors.executionstatus import (
    ExecutionStatus,
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
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


logger = logging.getLogger(__name__)

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
        if self.status is not None and self._status_applies_to_this_conversation(self.status):
            self._update_conversation_with_status(self.status)

        # reset status
        self.status = None

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
        if self.status is None:
            self.message_list.append_message(message)
        elif isinstance(self.status, UserMessageRequestStatus):
            self.append_user_message(message.content)
        elif isinstance(self.status, ToolRequestStatus) and message.tool_result is not None:
            self.append_tool_result(message.tool_result)
        else:
            self.message_list.append_message(message)

    def append_agent_message(self, agent_input: str, is_error: bool = False) -> None:
        """Append a new message object of type ``MessageType.AGENT`` to the messages list.

        Parameters
        ----------
        agent_input:
            message to append.
        """
        self.message_list.append_agent_message(agent_input=agent_input, is_error=is_error)

    def append_user_message(self, user_input: str) -> None:
        """Append a new message object of type ``MessageType.USER`` to the messages list.

        Parameters
        ----------
        user_input:
            message to append.
        """

        from wayflowcore.executors.interrupts.executioninterrupt import InterruptedExecutionStatus

        if self.status is None:
            self.message_list.append_user_message(user_input)
        elif isinstance(self.status, UserMessageRequestStatus):
            self.status.submit_user_response(user_input)
        elif isinstance(self.status, InterruptedExecutionStatus):
            self.message_list.append_user_message(user_input)
        elif isinstance(self.status, FinishedStatus):
            warnings.warn(
                "Conversation was finished but a new user message was appended.", UserWarning
            )
            self.message_list.append_user_message(user_input)
        else:
            raise ValueError(
                f"Should not append tool results to the current conversation ({user_input}, {self.status})"
            )

    def append_tool_result(self, tool_result: "ToolResult") -> None:
        """Append a new message object of type ``MessageType.TOOL_RESULT`` to the messages list.

        Parameters
        ----------
        tool_result:
            message to append.
        """
        if self.status is None or not isinstance(self.status, ToolRequestStatus):
            raise ValueError("internal error")

        self.status.submit_tool_result(tool_result)

    async def _append_streaming_message(
        self,
        stream: AsyncIterable["TaggedMessageChunkType"],
        extract_func: Optional[Callable[[Any], "TaggedMessageChunkType"]] = None,
    ) -> Message:
        return await self.message_list._append_streaming_message(stream, extract_func)

    def _status_applies_to_this_conversation(self, status: ExecutionStatus) -> bool:
        return status is not None and status._conversation_id == self.id

    def _update_conversation_with_status(self, status: ExecutionStatus) -> None:
        if isinstance(status, UserMessageRequestStatus):
            user_response = status._user_response
            if user_response is None:
                s = "\n".join([str(m) for m in self.get_messages()])
                logger.info(
                    f"Should have submitted a user response before updating the conversation: {s}"
                )
            else:
                self.message_list.append_message(user_response)
        elif isinstance(status, ToolRequestStatus):
            tool_results = status._tool_results
            if tool_results is None:
                # return
                raise ValueError(
                    "Should have submitted a tool results before updating the conversation\n"
                    f"The status was: {status}\n"
                    f"The conversation was: {self.get_messages()}\n"
                )
            for tool_result in tool_results:
                self.message_list.append_message(Message(tool_result=tool_result, role="assistant"))
