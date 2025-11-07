# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Set, Tuple

from wayflowcore import Conversation
from wayflowcore._utils._templating_helpers import render_template
from wayflowcore.agent import Agent
from wayflowcore.executors._agenticpattern_helpers import (
    _HANDOFF_TOOL_NAME,
    _SEND_MESSAGE_TOOL_NAME,
    _close_parallel_tool_requests_if_necessary,
    _get_last_tool_request_message_from_agent_response,
    _get_tool_request_from_message,
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
from wayflowcore.messagelist import MessageType
from wayflowcore.swarm import Swarm
from wayflowcore.templates._swarmtemplate import _HANDOFF_CONFIRMATION_MESSAGE_TEMPLATE
from wayflowcore.tools import ToolResult

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
    return [
        recipient_agent for sender_agent, recipient_agent in relationships if sender_agent == agent
    ]


class SwarmRunner(ConversationExecutor):
    @staticmethod
    async def execute_async(
        conversation: Conversation,
        execution_interrupts: Optional[Sequence[ExecutionInterrupt]] = None,
    ) -> ExecutionStatus:
        from wayflowcore.executors._swarmconversation import SwarmConversation

        if not isinstance(conversation, SwarmConversation):
            raise ValueError(
                f"Conversation should be of type SwarmConversation, but got {type(conversation)}"
            )

        from wayflowcore.agent import _MutatedAgent
        from wayflowcore.executors._agentexecutor import (
            _TALK_TO_USER_TOOL_NAME,
            _make_talk_to_user_tool,
        )

        swarm_config = conversation.component

        current_thread = conversation.state.current_thread
        if current_thread is None:
            raise ValueError(
                f"Cannot execute Swarm as current thread is `None`. Conversation was {conversation}"
            )

        while True:
            logger.info(
                "\n%s\nNew execution round. Current thread is %s\n%s\n",
                "-" * 30,
                current_thread.identifier,
                "-" * 30,
            )
            current_agent = current_thread.recipient_agent

            # get sub conversation for current agent
            agent_sub_conversation = conversation._get_subconversation_for_thread(current_thread)
            if agent_sub_conversation is None:
                agent_sub_conversation = conversation.state._create_subconversation_for_thread(
                    current_thread
                )

            mutated_agent_tools = (
                list(current_agent.tools) + swarm_config._communication_tools[current_agent.name]
            )
            has_talk_to_user_tool = any(
                tool_.name == _TALK_TO_USER_TOOL_NAME for tool_ in mutated_agent_tools
            )
            if not has_talk_to_user_tool:
                # Manager agent should have tool to talk to user
                mutated_agent_tools.append(_make_talk_to_user_tool())

            mutated_agent_template = swarm_config.swarm_template.with_partial(
                {
                    "name": current_agent.name,
                    "description": current_agent.description,
                    "caller_name": current_thread.caller.name,
                    "other_agents": _get_all_recipients_for_agent(
                        swarm_config.relationships, current_agent
                    ),
                }
            )
            with _MutatedAgent(
                current_agent,
                {
                    "tools": mutated_agent_tools,
                    "agent_template": mutated_agent_template,
                    "_add_talk_to_user_tool": has_talk_to_user_tool,
                },
            ):
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

            if isinstance(status, ToolRequestStatus) and any(
                t.name == _SEND_MESSAGE_TOOL_NAME for t in status.tool_requests
            ):
                # 1. agent is sending a message to another agent
                current_thread = SwarmRunner._post_agent_message_to_next_thread(
                    swarm_conversation=conversation,
                    current_thread=current_thread,
                    current_agent=current_agent,
                )
                # we will handle the conversation manually
                agent_sub_conversation.status = None
            elif isinstance(status, ToolRequestStatus) and any(
                t.name == _HANDOFF_TOOL_NAME for t in status.tool_requests
            ):
                # 2. agent is handing off the conversation to another agent
                current_thread = SwarmRunner._handoff_conversation_to_agent(
                    swarm_config=swarm_config,
                    swarm_conversation=conversation,
                    current_thread=current_thread,
                    current_agent=current_agent,
                )
                # we will handle the conversation manually
                agent_sub_conversation.status = None
            elif isinstance(status, UserMessageRequestStatus) and current_thread.is_main_thread:
                # 3. agent posted to main conversation, back to the user/caller
                _last_message = conversation.get_last_message()
                if _last_message is None:
                    raise ValueError("Internal error: Empty message list after executing agent")
                logger.info(
                    "From main thread: Answering to user with content `%s`",
                    _last_message.content,
                )
                return status
            elif isinstance(status, UserMessageRequestStatus):
                # 4. agent is answering to another agent
                current_thread = SwarmRunner._post_agent_answer_to_previous_thread(
                    swarm_conversation=conversation,
                    current_agent_subconversation=agent_sub_conversation,
                )
                # we will handle the conversation manually
                agent_sub_conversation.status = None
            elif isinstance(status, (ToolRequestStatus, ToolExecutionConfirmationStatus)):
                # 5. usual client/server tool requests
                return status
            else:
                # 6. illegal agent finishing the conversation
                raise ValueError("Should not happen")

            # Set state's current thread to current_thread
            conversation.state.current_thread = current_thread

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
        )  # fix
        if len(unanswered_tool_requests) != 1:
            raise ValueError(
                f"Internal error, should have exactly one unanswered tool request, has {len(unanswered_tool_requests)}"
            )

        last_tool_request_id = unanswered_tool_requests[0].tool_request_id

        current_thread.message_list.append_tool_result(
            ToolResult(agent_result_message.content, tool_request_id=last_tool_request_id)
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
        current_thread: "SwarmThread",
        current_agent: "Agent",
    ) -> "SwarmThread":
        from wayflowcore.executors._agentexecutor import _TALK_TO_USER_TOOL_NAME

        # if there is a send message tool request:
        #   -> current_thread pushed to the stack
        #   -> current_thread = thread between caller and recipient
        #   -> add message as user message in the current thread
        last_tool_request_message = _get_last_tool_request_message_from_agent_response(
            current_thread.message_list
        )
        tool_request = _get_tool_request_from_message(
            message=last_tool_request_message,
            tool_name=_SEND_MESSAGE_TOOL_NAME,
        )
        _close_parallel_tool_requests_if_necessary(current_thread.message_list, tool_request)
        # ^ We disable parallel client tool calling in Swarm

        # validation
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
            current_thread.message_list.append_user_message(message)
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
        current_thread: "SwarmThread",
        current_agent: "Agent",
    ) -> "SwarmThread":
        # if there is a handoff conversation tool request:
        #   -> previous_thread = current_thread
        #   -> current_thread = thread between caller and recipient
        #   -> current_thread.message_list = previous_thread_message_list
        #   -> add indication that conversation was handed off as user message in the current thread
        last_tool_request_message = _get_last_tool_request_message_from_agent_response(
            current_thread.message_list
        )
        tool_request = _get_tool_request_from_message(
            message=last_tool_request_message,
            tool_name=_HANDOFF_TOOL_NAME,
        )
        _close_parallel_tool_requests_if_necessary(current_thread.message_list, tool_request)

        # validation
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
                # We move to another thread
                previous_caller_name = previous_thread.caller.name
                try:
                    current_thread = swarm_conversation.state.agents_and_threads[
                        previous_caller_name
                    ][recipient_agent_name]
                except KeyError:  # TODO Move to init
                    raise KeyError(
                        f"Cannot handoff conversation from (caller='{current_thread.caller.name}', "
                        f"recipient='{current_agent.name}') to (caller='{previous_caller_name}', "
                        f"recipient='{recipient_agent_name}') because of missing relationship ('{previous_caller_name}', "
                        f"'{recipient_agent_name}'). Please make sure to add this relationship when defining the Swarm."
                    )
                current_thread.message_list.messages[:] = (
                    previous_thread.message_list.get_messages()
                )  # it IS overriding the thread messagelist
                # ^ Was overriding the MessageList object
            logger.info(
                "Conversation was handed off to a new agent (thread %s)",
                current_thread.identifier,
            )

        return current_thread
