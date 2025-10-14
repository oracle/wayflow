# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Union

from wayflowcore import Conversation
from wayflowcore.agent import Agent
from wayflowcore.executors._agenticpattern_helpers import (
    _SEND_MESSAGE_TOOL_NAME,
    _close_parallel_tool_requests_if_nessary,
    _get_last_tool_request_message_from_agent_response,
    _get_tool_request_from_message,
    _get_unanswered_tool_requests_from_agent_response,
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
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import LlmModel
from wayflowcore.tools import ToolResult

if TYPE_CHECKING:
    from wayflowcore.executors._managerworkersconversation import ManagerWorkersConversation

logger = logging.getLogger(__name__)

GROUP_MANAGER_CUSTOM_INSTRUCTION = """
You are a group manager. You are responsible to communicate with the human user and \
assign tasks to the available agents in your group.
"""


def _create_manager_agent(group_manager: Union[Agent, LlmModel]) -> Agent:
    if isinstance(group_manager, LlmModel):
        manager_agent = Agent(
            name="manager_agent",
            description="Agent that can assign tasks to other agents.",
            llm=group_manager,
            custom_instruction=GROUP_MANAGER_CUSTOM_INSTRUCTION,
        )
    else:
        manager_agent = group_manager
    return manager_agent


def _validate_agent_unicity(agents: List[Agent]) -> Dict[str, "Agent"]:
    agent_by_name: Dict[str, "Agent"] = {}

    for agent in agents:
        if not isinstance(agent, Agent):
            raise TypeError(
                f"Only Agents are supported in ManagerWorkers, got component of type '{agent.__class__.__name__}'"
            )

        # Checking for missing name
        if not agent.name:
            raise ValueError(f"There is an Agent with no name. Please assign one.")

        # Checking for name uniqueness (compulsory since routing depends on the name)
        agent_name = agent.name
        if agent_name in agent_by_name:
            raise ValueError(
                f"Found agents with duplicated names: {agent_name}. All agents (manager and workers) in ManagerWorkers should have unique names."
            )
        else:
            agent_by_name[agent_name] = agent

    return agent_by_name


class ManagerWorkersRunner(ConversationExecutor):
    @staticmethod
    async def execute_async(
        conversation: Conversation,
        execution_interrupts: Optional[Sequence[ExecutionInterrupt]] = None,
    ) -> ExecutionStatus:
        from wayflowcore.executors._managerworkersconversation import ManagerWorkersConversation

        if not isinstance(conversation, ManagerWorkersConversation):
            raise ValueError(
                f"Conversation should be of type ManagerWorkersConversation, but got {type(conversation)}"
            )

        from wayflowcore.agent import _MutatedAgent
        from wayflowcore.executors._agentexecutor import (
            _TALK_TO_USER_TOOL_NAME,
            _make_talk_to_user_tool,
        )

        managerworkers_config = conversation.component

        while True:
            current_agent_name = conversation.state.current_agent_name
            current_conversation = conversation._get_agent_subconversation(current_agent_name)

            if current_conversation is None:
                raise ValueError("Current conversation is None")

            logger.info(
                "\n%s\nNew execution round. Current agent is %s\n%s\n",
                "-" * 30,
                current_agent_name,
                "-" * 30,
            )

            if current_agent_name == managerworkers_config.manager_agent.name:
                current_agent = managerworkers_config.manager_agent
                mutated_agent_tools = (
                    list(current_agent.tools) + managerworkers_config._manager_communication_tools
                )

                if not any(tool_.name == _TALK_TO_USER_TOOL_NAME for tool_ in mutated_agent_tools):
                    # Manager agent should have tool to talk to user
                    mutated_agent_tools.append(_make_talk_to_user_tool())

                mutated_agent_template = managerworkers_config.managerworkers_template.with_partial(
                    {
                        "name": current_agent.name,
                        "description": current_agent.description,
                        "other_agents": managerworkers_config.workers,
                        "caller_name": "HUMAN USER",
                    }
                )

                with _MutatedAgent(
                    current_agent,
                    {
                        "tools": mutated_agent_tools,
                        "agent_template": mutated_agent_template,
                    },
                ):
                    status = await current_conversation.execute_async(
                        execution_interrupts=execution_interrupts,
                    )

            else:  # Current agent is a worker
                current_agent = managerworkers_config._agent_by_name[current_agent_name]
                status = await current_conversation.execute_async(
                    execution_interrupts=execution_interrupts,
                )

            _last_message = current_conversation.get_last_message()
            if (
                not _last_message
                or _last_message.message_type == MessageType.TOOL_REQUEST
                and not isinstance(status, (ToolRequestStatus, ToolExecutionConfirmationStatus))
            ):
                raise TypeError(
                    "Internal error: Last agent message is a tool request but execution status "
                    f"is not of type {ToolRequestStatus}, {ToolExecutionConfirmationStatus} (is '{type(status)}')"
                )

            if isinstance(status, ToolRequestStatus) and any(
                t.name == _SEND_MESSAGE_TOOL_NAME for t in status.tool_requests
            ):
                # 1. current agent is the manager agent and is sending a message to a worker
                ManagerWorkersRunner._send_message_to_worker(
                    managerworkers_conversation=conversation,
                    managerworkers_config=managerworkers_config,
                )
            elif (
                isinstance(status, UserMessageRequestStatus)
                and current_agent_name == managerworkers_config.manager_agent.name
            ):
                # 2. current agent is the manager agent and is sending a message to the user
                logger.info(
                    "Answering to user with content `%s`",
                    _last_message.content,
                )
                return status
            elif isinstance(status, UserMessageRequestStatus):
                # 3. current agent is a worker and is sending a message to the manager
                ManagerWorkersRunner._send_message_to_manager(
                    message=_last_message,
                    manager_agent_name=managerworkers_config.manager_agent.name,
                    managerworkers_conversation=conversation,
                )
            elif isinstance(status, (ToolRequestStatus, ToolExecutionConfirmationStatus)):
                # 4. usual client/server tool requests of either manager agent or the worker
                return status
            else:
                # 5. illegal agent finishing the conversation
                raise ValueError("Conversation is finished unexpectedly.")

    @staticmethod
    def _send_message_to_manager(
        message: "Message",
        manager_agent_name: str,
        managerworkers_conversation: "ManagerWorkersConversation",
    ) -> None:
        manager_subconversation = managerworkers_conversation._get_main_subconversation()

        if message.message_type != MessageType.AGENT:
            raise ValueError(f"Message should be of type agent, is {message.message_type}")

        unanswered_tool_requests = _get_unanswered_tool_requests_from_agent_response(
            manager_subconversation.message_list
        )

        # There should be exactly one unanswered tool request in the manager's conversation
        # as the manager uses `send_message` tool to send messages to the worker.
        # For parallel tool calling that might be implemented later, we will allow more than 1 unanswered tool request.
        if len(unanswered_tool_requests) != 1:
            raise ValueError(
                f"Internal error, should have exactly one unanswered tool request, has {len(unanswered_tool_requests)}"
            )

        last_tool_request_id = unanswered_tool_requests[0].tool_request_id

        manager_subconversation.message_list.append_tool_result(
            ToolResult(message.content, tool_request_id=last_tool_request_id)
        )

        logger.info(
            "Answering back to manager agent with tool result `%s`",
            message.content,
        )

        # Change current agent back to manager
        managerworkers_conversation.state.current_agent_name = manager_agent_name

    @staticmethod
    def _send_message_to_worker(
        managerworkers_conversation: "ManagerWorkersConversation",
        managerworkers_config: "ManagerWorkers",
    ) -> None:
        manager_subconversation = managerworkers_conversation._get_main_subconversation()

        last_tool_request_message = _get_last_tool_request_message_from_agent_response(
            manager_subconversation.message_list
        )

        tool_request = _get_tool_request_from_message(
            message=last_tool_request_message,
            tool_name=_SEND_MESSAGE_TOOL_NAME,
        )

        _close_parallel_tool_requests_if_nessary(manager_subconversation.message_list, tool_request)
        # ^ We currently do not support parallel tool calling --> need to cancel other tool requests if existing.

        recipient_agent_name, message, error_message = _parse_send_message_tool_request(
            tool_request,
            possible_recipient_names=[agent.name for agent in managerworkers_config.workers],
        )

        if error_message:
            manager_subconversation.message_list.append_tool_result(
                ToolResult(error_message, tool_request_id=tool_request.tool_request_id)
            )
            logger.debug("Failure when trying to call new agent: `%s`", error_message)
        else:
            worker_subconversation = managerworkers_conversation._get_agent_subconversation(
                recipient_agent_name
            )

            if worker_subconversation is None:
                worker_subconversation = (
                    managerworkers_conversation.state._create_subconversation_for_agent(
                        managerworkers_config._agent_by_name[recipient_agent_name]
                    )
                )
                logger.info(
                    f"Sub-conversation is created for {recipient_agent_name} agent",
                )
            worker_subconversation.append_user_message(message)

            logger.info("Calling agent %s with request `%s`", recipient_agent_name, message)

            # Change current agent for the next iteration
            managerworkers_conversation.state.current_agent_name = recipient_agent_name
