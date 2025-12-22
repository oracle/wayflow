# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from enum import Enum, auto
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Set, Tuple

from wayflowcore import Conversation
from wayflowcore._utils._templating_helpers import render_template
from wayflowcore.agent import Agent
from wayflowcore.executors._agenticpattern_helpers import (
    _HANDOFF_TOOL_NAME,
    _SEND_MESSAGE_TOOL_NAME,
    _close_parallel_tool_requests_after_handoff_tool_request,
    _get_unanswered_tool_requests_from_agent_response,
    _parse_handoff_conversation_tool_request,
    _parse_send_message_tool_request,
)
from wayflowcore.executors._executor import ConversationExecutor
from wayflowcore.executors.executionstatus import (
    ExecutionStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.executors.interrupts.executioninterrupt import ExecutionInterrupt
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.swarm import HandoffMode, Swarm
from wayflowcore.templates._swarmtemplate import _HANDOFF_CONFIRMATION_MESSAGE_TEMPLATE
from wayflowcore.tools import ClientTool, ToolRequest, ToolResult

if TYPE_CHECKING:
    from wayflowcore.executors._agentconversation import AgentConversation
    from wayflowcore.executors._swarmconversation import SwarmConversation, SwarmThread


logger = logging.getLogger(__name__)


def _validate_agent_unicity(
    first_agent: Agent,
    relationships: List[Tuple[Agent, Agent]],
) -> Dict[str, "Agent"]:
    from wayflowcore.agent import Agent

    all_agents: List["Agent"] = [first_agent]
    for sender_agent, recipient_agent in relationships:
        all_agents.extend([sender_agent, recipient_agent])

    agent_by_name: Dict[str, "Agent"] = {}
    for agent in all_agents:
        if not isinstance(agent, Agent):
            raise TypeError(
                f"Only Agents are supported in Swarm, got component of type '{agent.__class__.__name__}'"
            )
        # Checking for missing name
        if not agent.name:
            raise ValueError(f"Agent {agent} has no name.")
        agent_name = agent.name

        # Checking for name uniqueness (compulsory since routing depends on the name)
        if agent_name in agent_by_name:
            if agent_by_name[agent_name] is not agent:
                raise ValueError(
                    f"Found agents with duplicated names: {agent} != {agent_by_name[agent_name]}. "
                )
        else:
            agent_by_name[agent_name] = agent

    return agent_by_name


def _validate_relationships_unicity(
    relationships: List[Tuple[Agent, Agent]],
) -> None:
    relationship_name_set: Set[Tuple[str, str]] = set()
    for sender_agent, recipient_agent in relationships:
        name_pair = (sender_agent.name, recipient_agent.name)
        if name_pair in relationship_name_set:
            raise ValueError(
                f"Found duplicated relationship involving agents '{name_pair[0]}' and '{name_pair[1]}'. "
                "Make sure all relationships are unique."
            )
        relationship_name_set.add(name_pair)


def _get_all_recipients_for_agent(
    relationships: List[Tuple[Agent, Agent]], agent: Agent
) -> List[Agent]:
    """Get all recipients for agent and make sure that they all have descriptions"""
    recipients = []
    for sender_agent, recipient_agent in relationships:
        if sender_agent == agent:
            if not recipient_agent.description:
                raise ValueError(f"Agent '{recipient_agent.name}' is missing a description")
            recipients.append(recipient_agent)
    return recipients


class _ToolProcessSignal(Enum):
    RETURN = auto()  # Break the while loop and return the status to user
    START_NEW_LOOP = auto()  # Equivalent to `continue` in the while loop
    EXECUTE_AGENT = auto()  # Go to the agent execution


class SwarmRunner(ConversationExecutor):
    @staticmethod
    async def execute_async(
        conversation: Conversation,
        execution_interrupts: Optional[Sequence[ExecutionInterrupt]] = None,
    ) -> ExecutionStatus:
        from wayflowcore.agent import _MutatedAgent
        from wayflowcore.executors._swarmconversation import SwarmConversation

        if not isinstance(conversation, SwarmConversation):
            raise ValueError(
                f"Conversation should be of type SwarmConversation, but got {type(conversation)}"
            )

        swarm_config = conversation.component

        while True:
            # Setup context
            current_thread = conversation.state.current_thread
            if current_thread is None:
                raise ValueError(
                    f"Cannot execute Swarm as current thread is `None`. Conversation was {conversation}"
                )

            current_agent = current_thread.recipient_agent

            agent_sub_conversation = conversation._get_subconversation_for_thread(current_thread)
            if agent_sub_conversation is None:
                agent_sub_conversation = conversation.state._create_subconversation_for_thread(
                    current_thread
                )

            # Handle pending tool requests (if any)
            result = SwarmRunner._handle_pending_tool_requests(
                swarm_conversation=conversation,
                agent_sub_conversation=agent_sub_conversation,
                current_agent=current_agent,
            )

            if result == _ToolProcessSignal.RETURN:
                if not isinstance(agent_sub_conversation.status, ToolRequestStatus):
                    raise ValueError("Internal error: The status should be ToolRequestStatus")
                return agent_sub_conversation.status
            elif result == _ToolProcessSignal.START_NEW_LOOP:
                continue

            # Execute agent
            logger.info(
                "\n%s\nNew execution round. Current thread is %s\n%s\n",
                "-" * 30,
                current_thread.identifier,
                "-" * 30,
            )
            communication_tools = swarm_config._communication_tools[current_agent.name]
            if (
                conversation.component.handoff == HandoffMode.OPTIONAL
                and current_agent != conversation.state.main_thread.recipient_agent
            ):
                # when using HandoffMode.OPTIONAL (agents can both send message and handoff)
                # only the main agent is allowed to handoff
                communication_tools = [
                    t for t in communication_tools if t.name != _HANDOFF_TOOL_NAME
                ]
            mutated_agent_tools = list(current_agent.tools) + communication_tools

            mutated_agent_template = swarm_config.swarm_template.with_partial(
                {
                    "name": current_agent.name,
                    "description": current_agent.description,
                    "caller_name": current_thread.caller.name,
                    "other_agents": [
                        {"name": agent.name, "description": agent.description}
                        for agent in _get_all_recipients_for_agent(
                            swarm_config.relationships, current_agent
                        )
                    ],
                    "handoff": swarm_config.handoff.value,  # type: ignore
                }
            )
            with _MutatedAgent(
                current_agent,
                {
                    "tools": mutated_agent_tools,
                    "agent_template": mutated_agent_template,
                    "id": current_agent.name,
                    # ^Change the agent id to agent name -> message.sender = agent_id = agent_name -> easier for llm to know which agent sending the message
                    # Note: this is a workaround and should be fixed in the future
                },
            ):
                if (
                    isinstance(agent_sub_conversation.status, ToolRequestStatus)
                    and not agent_sub_conversation.status.tool_requests
                ):
                    # If the status.tool_requests is empty we need to manually reset the status to None
                    # Otherwise, it will raise error as no tool results are present.
                    agent_sub_conversation.status = None

                status = await agent_sub_conversation.execute_async(
                    execution_interrupts=execution_interrupts,
                )

            _last_message = agent_sub_conversation.get_last_message()
            if (
                not _last_message
                or _last_message.message_type == MessageType.TOOL_REQUEST
                and not isinstance(status, (ToolRequestStatus, ToolExecutionConfirmationStatus))
            ):
                raise TypeError(
                    "Internal error: Last agent message is a tool request but execution status "
                    f"is not of type {ToolRequestStatus}, {ToolExecutionConfirmationStatus} (is '{status}')"
                )
            if isinstance(status, ToolRequestStatus):
                # 1. Agent requests communication tools (send_message/handoff) or a standard client tool
                # These tool(s) will be handled in the next loop

                # Empty status.tool_requests as we will:
                # - For standard client tool: add only that client tool to status.tool_requests when handling it
                # - For server and internal tool (e.g send_message, handoff_conversation): we handle it and the tool results manually -> should not appear in the status
                status.tool_requests = []

                continue
            elif isinstance(status, UserMessageRequestStatus) and current_thread.is_main_thread:
                # 2. Agent posted to main conversation, back to the human user
                _last_message = conversation.get_last_message()
                if _last_message is None:
                    raise ValueError("Internal error: Empty message list after executing agent")
                logger.info(
                    "From main thread: Answering to user with content `%s`",
                    _last_message.content,
                )
                return status
            elif isinstance(status, UserMessageRequestStatus):
                # 3. Agent is answering to its caller which is another agent
                next_thread = SwarmRunner._post_agent_answer_to_previous_thread(
                    swarm_conversation=conversation,
                    current_agent_subconversation=agent_sub_conversation,
                )
                conversation.state.current_thread = next_thread
            elif isinstance(status, ToolExecutionConfirmationStatus):
                # 4. Agent wants to execute tool that needs confirmation
                return status
            else:
                # 5. Illegal agent finishing the conversation
                raise ValueError("Should not happen")

    @staticmethod
    def _handle_pending_tool_requests(
        swarm_conversation: "SwarmConversation",
        agent_sub_conversation: "AgentConversation",
        current_agent: Agent,
    ) -> _ToolProcessSignal:
        execute_tool = (
            isinstance(agent_sub_conversation.status, ToolRequestStatus)
            # If user submitted tool result (in case of client tool)
            # -> need to execute the agent first to append the tool result to the message list before executing next tool request
            and not agent_sub_conversation.status._tool_results
            and (
                agent_sub_conversation.state.current_tool_request
                or agent_sub_conversation.state.tool_call_queue
            )
        )

        if not execute_tool:
            return _ToolProcessSignal.EXECUTE_AGENT

        if not agent_sub_conversation.state.current_tool_request:
            agent_sub_conversation.state.current_tool_request = (
                agent_sub_conversation.state.tool_call_queue.pop(0)
            )

        tool_request = agent_sub_conversation.state.current_tool_request

        # Case 1: Communication tool (internal)
        if tool_request.name in [_SEND_MESSAGE_TOOL_NAME, _HANDOFF_TOOL_NAME]:
            SwarmRunner._handle_communication_tool_request(
                tool_request=tool_request,
                swarm_conv=swarm_conversation,
                current_agent=current_agent,
            )

            agent_sub_conversation.state.current_tool_request = None

            # Start a new loop to handle the next tool request if any
            return _ToolProcessSignal.START_NEW_LOOP

        # Case 2: Standard client tool
        tool = next((t for t in current_agent.tools if t.name == tool_request.name), None)
        if tool and isinstance(tool, ClientTool):
            # It is a standard client tool request

            # Return only the current tool request in the ToolRequestStatus
            if not isinstance(agent_sub_conversation.status, ToolRequestStatus):
                raise ValueError("Internal error: The status should be ToolRequestStatus")
            agent_sub_conversation.status.tool_requests = [tool_request]

            agent_sub_conversation.state.current_tool_request = None

            return _ToolProcessSignal.RETURN

        # Case 3: Server tool or other internal tool
        # -> Let agent handle it (agent will check the current_tool_request)
        return _ToolProcessSignal.EXECUTE_AGENT

    @staticmethod
    def _handle_communication_tool_request(
        tool_request: ToolRequest,
        swarm_conv: "SwarmConversation",
        current_agent: Agent,
    ) -> None:
        if tool_request.name == _SEND_MESSAGE_TOOL_NAME:
            swarm_conv.state.current_thread = SwarmRunner._post_agent_message_to_next_thread(
                swarm_conversation=swarm_conv,
                current_agent=current_agent,
            )
        elif tool_request.name == _HANDOFF_TOOL_NAME:
            swarm_conv.state.current_thread = SwarmRunner._handoff_conversation_to_agent(
                swarm_config=swarm_conv.component,
                swarm_conversation=swarm_conv,
                current_agent=current_agent,
            )
        return None

    @staticmethod
    def _post_agent_answer_to_previous_thread(
        swarm_conversation: "SwarmConversation",
        current_agent_subconversation: "AgentConversation",
    ) -> "SwarmThread":
        # - UserMessageRequest (and current thread != main thread)
        #     -> get agent message as result
        #     -> Current thread = stack.pop(-1)
        #     -> add tool result message to current thread
        agent_result_message = current_agent_subconversation.get_last_message()
        if agent_result_message is None:
            raise ValueError("Internal error: Message list is empty after executing an Agent")
        if agent_result_message.message_type != MessageType.AGENT:
            raise ValueError(f"Message should be of type agent, is {agent_result_message}")
        if len(swarm_conversation.state.thread_stack) == 0:
            raise ValueError(
                f"Internal error: was not in the main thread but thread_stack is empty"
            )

        current_thread = (
            swarm_conversation.state.thread_stack.pop()
        )  # get the previously running thread

        unanswered_tool_requests = _get_unanswered_tool_requests_from_agent_response(
            current_thread.message_list
        )

        # Get the oldest unanswered tool requests since the tool requests are processed sequentially
        tool_request_id = unanswered_tool_requests[0].tool_request_id

        current_thread.message_list.append_tool_result(
            ToolResult(agent_result_message.content, tool_request_id=tool_request_id)
        )
        logger.info(
            "Answering back to thread %s with tool result `%s`",
            current_thread.identifier,
            agent_result_message.content,
        )

        return current_thread

    @staticmethod
    def _post_agent_message_to_next_thread(
        swarm_conversation: "SwarmConversation",
        current_agent: "Agent",
    ) -> "SwarmThread":
        # if there is a send message tool request:
        #   -> current_thread pushed to the stack
        #   -> current_thread = thread between caller and recipient
        #   -> add message as user message in the current thread
        from wayflowcore.executors._agentexecutor import _TALK_TO_USER_TOOL_NAME

        current_thread = swarm_conversation.state.current_thread

        if not current_thread:
            raise ValueError("Internal error when executing send_message tool.")

        unanswered_tool_requests = _get_unanswered_tool_requests_from_agent_response(
            current_thread.message_list
        )

        # Get the oldest unanswered tool requests since the tool requests are processed sequentially
        tool_request = unanswered_tool_requests[0]

        # Validation
        recipient_agent_name, message, error_message = _parse_send_message_tool_request(
            tool_request,
            possible_recipient_names=swarm_conversation._get_recipient_names_for_agent(
                current_agent
            ),
        )
        if error_message:
            current_thread.message_list.append_tool_result(
                ToolResult(error_message, tool_request_id=tool_request.tool_request_id)
            )
            logger.debug("Failure when trying to call new agent: `%s`", error_message)
        elif recipient_agent_name == current_thread.caller.name:
            current_thread.message_list.append_tool_result(
                ToolResult(
                    f"Circular calling warning: Cannot use {_SEND_MESSAGE_TOOL_NAME} on a caller/user. Please use {_TALK_TO_USER_TOOL_NAME} instead",
                    tool_request_id=tool_request.tool_request_id,
                )
            )
            logger.debug(
                "Agent '%s' attempted to send a message to its caller '%s' (should use `%s` instead)",
                current_agent.name,
                recipient_agent_name,
                _TALK_TO_USER_TOOL_NAME,
            )
        else:
            swarm_conversation.state.thread_stack.append(current_thread)
            current_thread = swarm_conversation.state.agents_and_threads[current_agent.name][
                recipient_agent_name
            ]

            current_thread.message_list.append_message(
                Message(
                    role="user",
                    content=message,
                    sender=current_agent.name,
                )
            )
            logger.info(
                "Calling new agent (thread %s) with request `%s`",
                current_thread.identifier,
                message,
            )

        return current_thread

    @staticmethod
    def _handoff_conversation_to_agent(
        swarm_config: Swarm,
        swarm_conversation: "SwarmConversation",
        current_agent: "Agent",
    ) -> "SwarmThread":
        # if there is a handoff conversation tool request:
        #   -> previous_thread = current_thread
        #   -> current_thread = thread between caller and recipient
        #   -> current_thread.message_list = previous_thread_message_list
        #   -> add indication that conversation was handed off as user message in the current thread
        current_thread = swarm_conversation.state.current_thread

        if not current_thread:
            raise ValueError("Internal error when executing handoff tool.")

        unanswered_tool_requests = _get_unanswered_tool_requests_from_agent_response(
            current_thread.message_list
        )

        # Get the oldest unanswered tool requests since the tool requests are processed sequentially
        tool_request = unanswered_tool_requests[0]

        if len(unanswered_tool_requests) >= 1:
            # We do not allow tool requests after the handoff since the conversation is transfer to another agent
            # by append tool results saying that the tool requests are cancelled
            _close_parallel_tool_requests_after_handoff_tool_request(
                current_thread.message_list, tool_request
            )

            # Empty the tool call queue
            sub_conversation = swarm_conversation._get_subconversation_for_thread(current_thread)
            if not sub_conversation:
                raise ValueError("Internal error: sub conversation should not be None")
            sub_conversation.state.tool_call_queue = []

        # Validation
        recipient_agent_name, error_message = _parse_handoff_conversation_tool_request(
            tool_request,
            possible_recipient_names=swarm_conversation._get_recipient_names_for_agent(
                current_agent
            ),
        )
        if error_message:
            current_thread.message_list.append_tool_result(
                ToolResult(error_message, tool_request_id=tool_request.tool_request_id)
            )
            logger.info("Failure when trying to call new agent: `%s`", error_message)
        else:
            previous_thread = current_thread
            previous_thread.message_list.append_tool_result(
                ToolResult(
                    render_template(
                        _HANDOFF_CONFIRMATION_MESSAGE_TEMPLATE,
                        {
                            "sender_agent_name": current_agent.name,
                            "new_agent_name": recipient_agent_name,
                        },
                    ),
                    tool_request_id=tool_request.tool_request_id,
                )
            )  # Was not added to the previous thread
            if previous_thread.is_main_thread:
                recipient_agent = swarm_config._agent_by_name[recipient_agent_name]

                # We stay in the main thread but change the recipient
                current_thread.recipient_agent = recipient_agent

                # Change the thread conversation's component to recipient agent
                thread_conversation = swarm_conversation._get_main_thread_conversation()
                thread_conversation.component = recipient_agent
            else:
                raise ValueError(
                    "An Agent not being the main agent is trying to handoff the conversation. This should not happen."
                )
            logger.info(
                "Conversation was handed off to a new agent (thread %s)",
                current_thread.identifier,
            )

        return current_thread
