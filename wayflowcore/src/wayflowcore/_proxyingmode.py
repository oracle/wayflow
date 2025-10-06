# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import os
from contextvars import ContextVar, Token
from copy import copy
from enum import Enum
from types import TracebackType
from typing import Dict, List, Optional, Union

from wayflowcore.agent import Agent
from wayflowcore.conversation import Conversation
from wayflowcore.conversationalcomponent import _HUMAN_ENTITY_ID
from wayflowcore.messagelist import Message, MessageList, MessageType
from wayflowcore.tools import ToolRequest

logger = logging.getLogger(__name__)


class _ProxyMode(Enum):
    """Enumeration of the types of proxying modes"""

    NO_PROXY = "NO_PROXY"
    FULL_PROXY = "FULL_PROXY"

    def __str__(self) -> str:
        return f"{self.name}"


_DEV_COMPOSABILITY_MODE = "WAYFLOW_EXP_PROXYING_MODE"


def _get_proxying_mode() -> _ProxyMode:
    proxy_mode = _ProxyMode.FULL_PROXY
    if _DEV_COMPOSABILITY_MODE in os.environ:
        logger.warning(
            "Proxy mode is an advanced feature for multi-agent WayFlow agents and should be used for dev only."
        )
        proxy_mode = _ProxyMode[os.environ[_DEV_COMPOSABILITY_MODE]]
    return proxy_mode


def _mark_message_if_needed(messages: MessageList, agent_id: str) -> None:
    """Automatically adds the proper message sender and recipients if needed.
    For instance, when a user answers with a USER message or when we add a
    TOOL_RESULT message"""
    # we always make the tool result recipient match the tool request sender
    _associate_tool_results_recipients_to_their_tool_request_sender(messages)

    last_message = messages.get_last_message()
    logger.debug(
        "%s::execute: last message: %s\n",
        agent_id,
        last_message,
    )
    if last_message is None:
        return
    elif last_message.message_type in {MessageType.USER, MessageType.ERROR}:
        messages.messages[-1].sender = _HUMAN_ENTITY_ID
        messages._add_recipients_to_message({_HUMAN_ENTITY_ID, agent_id}, index=-1)


def _associate_tool_results_recipients_to_their_tool_request_sender(messages: MessageList) -> None:
    sender_by_tool_request_id: Dict[str, str] = {}
    for msg in messages.messages:
        if msg.sender is not None and msg.tool_requests is not None:
            for tr in msg.tool_requests:
                sender_by_tool_request_id[tr.tool_request_id] = msg.sender

        if msg.message_type == MessageType.TOOL_RESULT and len(msg.recipients) == 0:
            if msg.tool_result is not None:
                tool_result_id = msg.tool_result.tool_request_id
                if tool_result_id in sender_by_tool_request_id:
                    msg._add_recipients({sender_by_tool_request_id[tool_result_id]})


# this is a context variable holding a communication context for each conversation id
_GLOBAL_PROXY_COMMUNICATION_CONTEXT: ContextVar[Dict[str, "ProxyCommunicationContext"]] = (
    ContextVar("_GLOBAL_PROXY_COMMUNICATION_CONTEXT", default={})
)


class ProxyCommunicationContext:
    def __init__(
        self,
        conversation: Conversation,
        sender: str,
    ) -> None:
        self.prev_contexts_dict: Dict[str, ProxyCommunicationContext] = {}
        self.conversation_id = conversation.conversation_id

        self.sender_id = sender

    @staticmethod
    def _get_current_communication_context(
        conversation: Conversation,
    ) -> Optional["ProxyCommunicationContext"]:
        return _GLOBAL_PROXY_COMMUNICATION_CONTEXT.get().get(conversation.conversation_id)

    def __enter__(self) -> "ProxyCommunicationContext":
        current_value = copy(_GLOBAL_PROXY_COMMUNICATION_CONTEXT.get())

        # install ourselves as current communication context
        current_value[self.conversation_id] = self
        prev_contexts_dict = _GLOBAL_PROXY_COMMUNICATION_CONTEXT.set(current_value).old_value

        if prev_contexts_dict != Token.MISSING:
            # save the previous communication context
            self.prev_contexts_dict = prev_contexts_dict

        return self

    def __exit__(
        self,
        exc_type: Union[type[BaseException], None],
        exc_val: Union[BaseException, None],
        exc_tb: Union[TracebackType, None],
    ) -> None:
        # reinstate the previous communication context
        _GLOBAL_PROXY_COMMUNICATION_CONTEXT.set(self.prev_contexts_dict)

    @staticmethod
    def get_parent_id_from_conversation(conversation: Conversation) -> str:
        current_context = ProxyCommunicationContext._get_current_communication_context(
            conversation=conversation
        )
        if current_context is None:
            return _HUMAN_ENTITY_ID
        return current_context.sender_id


class ActionType(Enum):
    NONE = "none"
    PARENT_USER_MESSAGE = "parent.usermessage"
    PARENT_AGENT_MESSAGE = "parent.agentmessage"
    CURRENT_AGENT_MESSAGE = "current.agentmessage"
    CURRENT_TOOL_RESULT = "current.tool_toolresult"
    CURRENT_SUBAGENT_RESULT = "current.agent_toolresult"
    CURRENT_TOOL_REQUEST = "current.tool_toolrequest"
    CURRENT_SUBAGENT_REQUEST = "current.agent_toolrequest"


def _find_tool_name_from_tool_request_id(tool_request_id: str, conversation: Conversation) -> str:
    try:
        return next(
            tool_request.name
            for message in conversation.get_messages()
            if (
                message.message_type == MessageType.TOOL_REQUEST
                and message.tool_requests is not None
            )
            for tool_request in message.tool_requests
            if tool_request.tool_request_id == tool_request_id
        )
    except StopIteration:
        raise ValueError(f"Did not find a ToolRequest with id={tool_request_id}")


def _determine_last_action_type(
    config: "Agent",
    last_message: Optional[Message],
    conversation: Conversation,
    parent_entity_id: str,
) -> ActionType:
    if last_message is None:
        # beginning of the conversation, there is no last message
        return ActionType.NONE
    elif last_message.sender == parent_entity_id and last_message.message_type in {
        MessageType.USER,
        MessageType.ERROR,
    }:
        # the agent received a message from the user
        return ActionType.PARENT_USER_MESSAGE
    elif last_message.sender == parent_entity_id and last_message.message_type == MessageType.AGENT:
        # the agent received a message from its parent agent
        return ActionType.PARENT_AGENT_MESSAGE
    elif (
        last_message.sender == config.agent_id
        and (
            last_message.message_type == MessageType.TOOL_RESULT
            and last_message.tool_result is not None
        )
        and _find_tool_name_from_tool_request_id(
            tool_request_id=last_message.tool_result.tool_request_id, conversation=conversation
        )
        in {agent.name for agent in config.agents}
    ):
        # the agent receveived a result from a child agent
        return ActionType.CURRENT_SUBAGENT_RESULT
    elif (
        last_message.sender == config.agent_id
        and last_message.message_type == MessageType.TOOL_RESULT
    ):
        # the agent receveived a result from a flow, tool or hallucinated tool.
        return ActionType.CURRENT_TOOL_RESULT
    else:
        raise ValueError(
            f"Illegal last message type, this should not happen. {parent_entity_id=}. The message was:\n{last_message!r}"
        )


def _validate_single_agent_call_or_defaults_to_tool_calls(
    config: "Agent",
    tool_requests: List[ToolRequest],
    conversation: Conversation,
) -> ActionType:
    tool_name_list = [
        _find_tool_name_from_tool_request_id(
            tool_request_id=tool_request.tool_request_id, conversation=conversation
        )
        for tool_request in tool_requests
    ]
    agent_names = {agent.name for agent in config.agents}
    if any(tool_name in agent_names for tool_name in tool_name_list):
        if len(tool_name_list) == 1:
            return ActionType.CURRENT_SUBAGENT_REQUEST
        logger.warning(
            "Found a subagent call + other tool requests, will default to the communication mode for non-subagents tools"
        )
    # we do not check for the correctness of the other names, they will be caught later in the agent execution
    return ActionType.CURRENT_TOOL_REQUEST


def _determine_new_action_type(
    config: "Agent",
    new_message: Message,
    conversation: Conversation,
) -> ActionType:
    if (
        new_message.sender == config.agent_id
        and new_message.message_type == MessageType.TOOL_REQUEST
        and new_message.tool_requests is not None
    ):
        # The agent is requesting a tool/flow/agent call
        new_action_type = _validate_single_agent_call_or_defaults_to_tool_calls(
            config=config,
            tool_requests=new_message.tool_requests,
            conversation=conversation,
        )
        return new_action_type
    elif new_message.sender == config.agent_id and new_message.message_type == MessageType.AGENT:
        # The agent is answering to the user/parent agent
        return ActionType.CURRENT_AGENT_MESSAGE
    else:
        raise ValueError(
            f"Illegal new message type, this should not happen. The message was:\n{new_message!r}\nFull conversation: {conversation.get_messages()}\nCurrent agent: {config.agent_id}"
        )


def _communicate_information_fullproxying_mode(
    config: "Agent",
    new_message: Message,
    conversation: Conversation,
    messages: MessageList,
    parent_entity_id: str,
) -> None:
    """
    In the full-proxy communication mode, information is rephrased between the entities when needed.
    """
    new_action_type = _determine_new_action_type(
        config=config,
        new_message=new_message,
        conversation=conversation,
    )
    logger.debug("New message (of action_type %s) is %s", new_action_type, new_message)

    if new_action_type == ActionType.CURRENT_AGENT_MESSAGE:
        # We need to differentiate between the case where the parent entity is a user (in which case we do need to add
        # the parent entity to the set of recipients) and the case in which the parent entity is an agent for which we
        # DO NOT want to add the message (because the result information will already be contained in the ToolResult)
        agent_message_recipients = {config.agent_id}
        if parent_entity_id == _HUMAN_ENTITY_ID:
            agent_message_recipients.add(parent_entity_id)
        messages._add_recipients_to_message(agent_message_recipients, index=-1)
    elif new_action_type == ActionType.CURRENT_TOOL_REQUEST:
        # The current agent generated a tool request, it needs to see it
        messages._add_recipients_to_message({config.agent_id}, index=-1)
    elif (
        new_action_type == ActionType.CURRENT_SUBAGENT_REQUEST
        and new_message.tool_requests is not None
    ):
        sub_assistant_name = new_message.tool_requests[0].name
        sub_agents_by_name = {agent.name: agent for agent in config.agents}
        sub_agent_id = sub_agents_by_name[sub_assistant_name].id
        # The current agent generated a sub-agent request, it needs to see it
        messages._add_recipients_to_message({config.agent_id}, index=-1)
        # The context information needs to be forwarded from the current agent to the sub-agent
        messages.append_message(
            Message(
                content=new_message.tool_requests[0].args.get(
                    "context", new_message.content
                ),  # extracting the information, defaulting on content
                message_type=MessageType.AGENT,
                sender=config.agent_id,
                recipients={sub_agent_id},
            )
        )
    else:
        raise NotImplementedError(f"New message type {new_message} is not supported")


def _communicate_information_noproxying_mode(
    config: "Agent",
    last_message: Optional[Message],
    new_message: Message,
    conversation: Conversation,
    messages: MessageList,
    parent_entity_id: str,
) -> None:
    """
    In the no-proxy communication mode, information is forwarded between the entities when needed.
    ⚠ EXPERIMENTAL FEATURE: The "no-proxy" communication mode is an experimental feature. This should
    only be used by advanced users for prototyping purposes.
    """
    last_action_type = _determine_last_action_type(
        config=config,
        last_message=last_message,
        conversation=conversation,
        parent_entity_id=parent_entity_id,
    )
    new_action_type = _determine_new_action_type(
        config=config,
        new_message=new_message,
        conversation=conversation,
    )
    if (
        last_action_type
        in [
            ActionType.PARENT_USER_MESSAGE,
            ActionType.PARENT_AGENT_MESSAGE,
            ActionType.CURRENT_TOOL_RESULT,
        ]
        and new_action_type == ActionType.CURRENT_AGENT_MESSAGE
    ):
        # We need to differentiate between the case where the parent entity is a user (in which case we do need to add
        # the parent entity to the set of recipients) and the case in which the parent entity is an agent for which we
        # DO NOT want to add the message (because the result information will already be contained in the ToolResult)
        agent_message_recipients = {config.agent_id}
        if parent_entity_id == _HUMAN_ENTITY_ID:
            agent_message_recipients.add(parent_entity_id)
        messages._add_recipients_to_message(agent_message_recipients, index=-1)
    elif (
        last_action_type in [ActionType.CURRENT_SUBAGENT_RESULT]
        and last_message is not None
        and last_message.tool_result is not None
        and new_action_type == ActionType.CURRENT_AGENT_MESSAGE
    ):
        # Forwarding response from a sub-agent directly to a parent user if needed
        # The current agent/parent agent will see the result with a ToolResult message
        if parent_entity_id == _HUMAN_ENTITY_ID:
            messages.append_message(
                Message(
                    content=last_message.tool_result.content,
                    message_type=MessageType.AGENT,
                    sender=config.agent_id,
                    recipients={parent_entity_id},
                )
            )
    elif (
        last_action_type
        in [
            ActionType.PARENT_USER_MESSAGE,
            ActionType.PARENT_AGENT_MESSAGE,
            ActionType.CURRENT_TOOL_RESULT,
            ActionType.CURRENT_SUBAGENT_RESULT,
        ]
        and new_action_type == ActionType.CURRENT_TOOL_REQUEST
    ):
        # The current agent generated a tool request, it needs to see it
        messages._add_recipients_to_message({config.agent_id}, index=-1)
    elif (
        last_action_type
        in [
            ActionType.PARENT_USER_MESSAGE,
            ActionType.PARENT_AGENT_MESSAGE,
            ActionType.CURRENT_SUBAGENT_RESULT,
        ]
        and last_message is not None
        and new_action_type == ActionType.CURRENT_SUBAGENT_REQUEST
        and new_message.tool_requests is not None
    ):
        # The current agent generated a sub-agent request, it needs to see it
        # + context information needs to be forwarded from the parent entity to the sub-agent
        sub_agent_name = new_message.tool_requests[0].name
        sub_agents_by_name = {agent.name: agent for agent in config.agents}
        sub_agent_id = sub_agents_by_name[sub_agent_name].id

        messages._add_recipients_to_message({config.agent_id}, index=-1)
        messages.append_message(
            Message(
                content=last_message.content,  # forwarding info
                message_type=MessageType.AGENT,
                sender=config.agent_id,  # Must be `self.agent_id` since `last_message.sender` is not a parent entity of the sub agent
                recipients={sub_agent_id},
            )
        )
    elif (
        last_action_type in [ActionType.CURRENT_TOOL_RESULT]
        and new_action_type == ActionType.CURRENT_SUBAGENT_REQUEST
        and new_message.tool_requests is not None
    ):
        # Weird case. Only place were we use content information from the current agent
        # instead of forwarding (as it is very unlikely to have the correct context info
        # from the output of a non-agent tool)
        sub_agent_name = new_message.tool_requests[0].name
        sub_agents_by_names = {agent.name: agent for agent in config.agents}
        sub_agent_id = sub_agents_by_names[sub_agent_name].id
        messages._add_recipients_to_message({config.agent_id}, index=-1)
        messages.append_message(
            Message(
                content=new_message.tool_requests[0].args.get(
                    "context", new_message.content
                ),  # extracting the information, defaulting on content (no forwarding here)
                message_type=MessageType.AGENT,
                sender=config.agent_id,
                recipients={sub_agent_id},
            )
        )
    else:
        raise ValueError(
            f"Illegal last/new message type pair, this should not happen. {last_action_type=}, {new_action_type=}"
        )


def _set_new_message_recipients_depending_on_communication_mode(
    config: "Agent",
    last_message: Optional[Message],
    new_message: Message,
    conversation: Conversation,
    messages: MessageList,
) -> None:
    # The proxy mode is completely separated from the AgentConversationExecutor and is thus
    # neither bound to an agent nor a conversation
    proxy_mode = _get_proxying_mode()
    parent_entity_id = ProxyCommunicationContext.get_parent_id_from_conversation(
        conversation=conversation
    )
    logger.debug("Using proxy mode %s", proxy_mode)
    if proxy_mode == _ProxyMode.FULL_PROXY:
        # "Full proxy" mode: the current agent rephrases information if needed
        _communicate_information_fullproxying_mode(
            config=config,
            new_message=new_message,
            conversation=conversation,
            messages=messages,
            parent_entity_id=parent_entity_id,
        )
    elif proxy_mode == _ProxyMode.NO_PROXY:
        # "No proxy" mode (developer mode only): the current agent forwards information if needed
        _communicate_information_noproxying_mode(
            config=config,
            last_message=last_message,
            new_message=new_message,
            conversation=conversation,
            messages=messages,
            parent_entity_id=parent_entity_id,
        )
    else:
        raise ValueError(f"Proxying mode {proxy_mode} is not supported")
