# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from contextvars import ContextVar
from typing import List, Optional, Tuple

from wayflowcore.agent import Agent
from wayflowcore.messagelist import Message, MessageList, MessageType
from wayflowcore.property import StringProperty
from wayflowcore.tools import ClientTool, ToolRequest, ToolResult

logger = logging.getLogger(__name__)

# Whether the developer enables "complex" Swarm features such as flows in agents
_GLOBAL_ENABLED_SWARM_BETA_FEATURES: ContextVar[bool] = ContextVar(
    "_GLOBAL_ENABLED_SWARM_BETA_FEATURES", default=False
)


def _enable_swarm_beta_features() -> None:
    _GLOBAL_ENABLED_SWARM_BETA_FEATURES.set(True)


def _are_swarm_beta_features_enabled() -> bool:
    return _GLOBAL_ENABLED_SWARM_BETA_FEATURES.get()


_SEND_MESSAGE_TOOL_NAME = "send_message"

_SEND_MESSAGE_TOOL_DESCRIPTION = """
Use this tool to facilitate direct, synchronous communication with another agent within your group.
- The recipient agent will respond only to this message, and will not continue any further tasks afterward.
- To continue the dialogue, you must invoke this tool again with the recipient agent and a follow-up message.
- You are responsible for relaying the agent's responses back to the user, as the user does not have direct access.
- Do not send more than 1 message to the same agent simultaneously.
""".strip()

_HANDOFF_TOOL_NAME = "handoff_conversation"

_HANDOFF_TOOL_DESCRIPTION = """
Use this tool to transfer the entire conversation with the user to another agent in your group.
- Use this when another agent is better suited to handle the user’s request.
- Once handed off, the receiving agent takes over the conversation entirely.
- Specify the recipient agent’s name to complete the handoff.
""".strip()


def _create_communication_tools(
    agent: Agent, recipient_agents: List[Agent], handoff: bool
) -> List[ClientTool]:
    communication_tools = [
        ClientTool(
            name=_SEND_MESSAGE_TOOL_NAME,
            description=_SEND_MESSAGE_TOOL_DESCRIPTION,
            input_descriptors=[
                StringProperty(
                    name="message",
                    description=(
                        "Specify the task required for the recipient agent to complete. Focus on clarifying "
                        "what the task entails, rather than providing exact instructions. Make sure to include "
                        "all the relevant information from the conversation needed to complete the task."
                    ),
                ),
                StringProperty(
                    name="recipient",
                    description=f"Name of the agent to send the message to. Available agents can be found in <other_entities>",
                ),
            ],
        )
    ]
    if handoff:
        communication_tools.append(
            ClientTool(
                name=_HANDOFF_TOOL_NAME,
                description=_HANDOFF_TOOL_DESCRIPTION,
                input_descriptors=[
                    StringProperty(
                        name="recipient",
                        description=f"Name of the agent to transfer the entire conversation to. Available agents can be found in <other_entities>",
                    ),
                ],
            )
        )
    return communication_tools


def _get_tool_request_from_message(message: Message, tool_name: str) -> ToolRequest:
    if message.message_type != MessageType.TOOL_REQUEST or not message.tool_requests:
        raise ValueError(
            f"Internal error: Message should be a tool request, got {message}"
        )  # for mypy compliance

    tool_request = next((tr for tr in message.tool_requests if tr.name == tool_name), None)
    if not tool_request:
        raise ValueError(f"Internal error: was expecting {tool_name} in the tool request.")
    return tool_request


def _get_last_tool_request_message_info_from_agent_response(
    message_list: MessageList,
) -> Tuple["Message", List[str]]:
    """
    Introduced as last message may not be of type tool request.
    Thus, this function is needed to iterate through the message list reversely to get the last tool request message.

    Will fail on extra messages being produced between a swarm send message
    request and the result from the recipient, which may happen when using Flow
    in Agents.

    Flow in Swarm agents is not tested currently, users need to enable this
    advanced feature if they still wish to use it.
    """
    _enabled_swarm_beta_features = _are_swarm_beta_features_enabled()
    last_tool_request_message: Optional["Message"] = None
    answered_tool_request_ids = []
    for msg in message_list.get_messages()[::-1]:
        if msg.message_type == MessageType.TOOL_REQUEST:
            last_tool_request_message = msg
            break
        elif msg.message_type != MessageType.TOOL_RESULT or msg.tool_result is None:
            # When using parallel tool calling, a tool request may be followed by tool result messages
            # When using flows in agents, the flow may produce more messages (e.g. agent message)
            # We force developer to be aware of this complexity by having them to activate "advanced" features
            if _enabled_swarm_beta_features:
                continue
            raise ValueError(
                f"Internal error: was expecting a ToolRequest or ToolResult message, received {msg}. "
                "If you are using advanced features such as flows in Swarm agents, please activate "
                f"the advanced features using the `_enable_swarm_beta_features` function."
            )
        answered_tool_request_ids.append(msg.tool_result.tool_request_id)

    if last_tool_request_message is None:
        raise ValueError("Internal error: Message list is empty after executing an Agent")

    if not last_tool_request_message.tool_requests:
        raise ValueError(
            f"Missing tool requests in tool request message {last_tool_request_message}"
        )

    if not _enabled_swarm_beta_features:
        # Check that all answered tool requests were actually part of the tool request message
        tool_request_ids = {tr.tool_request_id for tr in last_tool_request_message.tool_requests}
        for tr_id in answered_tool_request_ids:
            if tr_id not in tool_request_ids:
                raise ValueError(
                    f"Internal error: Tool request directly followed by tool results with mismatching tool request ids"
                )

    return last_tool_request_message, answered_tool_request_ids


def _get_last_tool_request_message_from_agent_response(message_list: MessageList) -> "Message":
    last_tool_request_message, _ = _get_last_tool_request_message_info_from_agent_response(
        message_list
    )
    return last_tool_request_message


def _get_unanswered_tool_requests_from_agent_response(
    message_list: MessageList,
) -> List[ToolRequest]:
    last_tool_request_message, answered_tool_request_ids = (
        _get_last_tool_request_message_info_from_agent_response(message_list)
    )

    if (
        last_tool_request_message.message_type != MessageType.TOOL_REQUEST
        or not last_tool_request_message.tool_requests
    ):
        raise ValueError(f"Message should be of type tool request, is {last_tool_request_message}")

    tool_requests = last_tool_request_message.tool_requests
    unanswered_tool_requests = [
        tr for tr in tool_requests if tr.tool_request_id not in answered_tool_request_ids
    ]
    return unanswered_tool_requests


def _close_parallel_tool_requests_if_necessary(
    message_list: MessageList, tool_request: ToolRequest
) -> None:
    """
    Close parallel tool request by marking other tool requests (that are not `tool_request`) as "cancelling"
    and appending corresponding tool results to the message list.
    Example:
    message_list = [Message(tool_requests=[TR1, TR2, TR3])]
    tool_request = TR1
    Resulting message_list after execution:
        [
            Message(tool_requests=[TR1, TR2, TR3]),
            Message(tool_result=ToolResult(content="Parallel tool calling is not supported. Cancelling call to tool 'TR2'")),
            Message(tool_result=ToolResult(content="Parallel tool calling is not supported. Cancelling call to tool 'TR3'"))
        ]
    """
    message = message_list.get_last_message()
    if (
        message is None
        or message.message_type != MessageType.TOOL_REQUEST
        or not message.tool_requests
        or not tool_request in message.tool_requests
    ):
        raise ValueError(f"Internal error: {message}")  # for mypy compliance

    if len(message.tool_requests) == 1:
        return

    logger.debug(
        "Parallel tool request in multi-agent patterns is not supported yet, will send one message/request only."
    )
    other_tool_requests = [
        other_tool_request
        for other_tool_request in message.tool_requests
        if tool_request.tool_request_id != other_tool_request.tool_request_id
    ]
    for other_tool_request in other_tool_requests:
        message_list.append_tool_result(
            ToolResult(
                content=f"Parallel tool calling is not supported. Cancelling call to tool '{other_tool_request.name}'",
                tool_request_id=other_tool_request.tool_request_id,
            )
        )


def _parse_send_message_tool_request(
    tool_request: ToolRequest, possible_recipient_names: List[str]
) -> Tuple[str, str, str]:
    recipient_agent_name = ""
    message = ""
    error_message = ""
    if "message" not in tool_request.args:
        error_message += f"Missing or malformed `message` parameter in `{_SEND_MESSAGE_TOOL_NAME}` tool request.\n"
    else:
        message = tool_request.args["message"]
    if "recipient" not in tool_request.args:
        error_message += f"Missing or malformed `recipient` parameter in `{_SEND_MESSAGE_TOOL_NAME}` tool request.\n"
    else:
        recipient_agent_name = tool_request.args["recipient"]
        if recipient_agent_name not in possible_recipient_names:
            error_message += (
                f"Recipient {recipient_agent_name} is not recognized. "
                f"Possible recipients are: {possible_recipient_names}."
            )
    return recipient_agent_name, message, error_message


def _parse_handoff_conversation_tool_request(
    tool_request: ToolRequest, possible_recipient_names: List[str]
) -> Tuple[str, str]:
    recipient_agent_name = ""
    error_message = ""
    if "recipient" not in tool_request.args:
        error_message += (
            f"Missing or malformed `recipient` parameter in `{_HANDOFF_TOOL_NAME}` tool request.\n"
        )
    else:
        recipient_agent_name = tool_request.args["recipient"]
        if recipient_agent_name not in possible_recipient_names:
            error_message += (
                f"Recipient {recipient_agent_name} is not recognized. "
                f"Possible recipients are: {possible_recipient_names}."
            )
    return recipient_agent_name, error_message
