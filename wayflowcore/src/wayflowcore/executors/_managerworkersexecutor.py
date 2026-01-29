# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from enum import Enum, auto
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Union

from wayflowcore import Conversation
from wayflowcore.a2a.a2aagent import A2AAgent
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.executors._agenticpattern_helpers import (
    _SEND_MESSAGE_TOOL_NAME,
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
from wayflowcore.tools import ClientTool, ToolResult

if TYPE_CHECKING:
    from wayflowcore.agentconversation import AgentConversation
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


def _validate_agent_unicity(
    worker_agents: List[Union[Agent, ManagerWorkers]], manager_agent: Agent) -> Dict[str, Union[Agent, ManagerWorkers]]:
    agent_by_name: Dict[str, Union["Agent", "ManagerWorkers"]] = {}
    all_agents = worker_agents + [manager_agent]
    for agent in all_agents:
        if agent.name != manager_agent.name:
            if not isinstance(agent, (Agent, ManagerWorkers, A2AAgent)):
                raise TypeError(
                    f"Only Agent, ManagerWorker and A2AAgent types are supported as workers for ManagerWorkers, got component of type '{agent.__class__.__name__}'"
                )
        else:
            if not isinstance(agent, Agent):
                raise TypeError(
                    f"Only Agents are supported as managers for ManagerWorkers, got component of type '{agent.__class__.__name__}'"
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


class _ToolProcessSignal(Enum):
    RETURN = auto()  # Break the while loop and return the status to user
    START_NEW_LOOP = auto()  # Equivalent to `continue` in the while loop
    EXECUTE_AGENT = auto()  # Go to the agent execution


class ManagerWorkersRunner(ConversationExecutor):
    @staticmethod
    async def _run_manager_round(
        current_agent: Agent,
        managerworkers_config: "ManagerWorkers",
        current_conversation: "AgentConversation",
        execution_interrupts: Optional[Sequence[ExecutionInterrupt]] = None,
    ) -> ExecutionStatus:
        from wayflowcore.conversationalcomponent import _MutatedConversationalComponent
        from wayflowcore.executors._agentexecutor import (
            _TALK_TO_USER_TOOL_NAME,
            _make_talk_to_user_tool,
        )

        mutated_agent_tools = (
            list(current_agent.tools) + managerworkers_config._manager_communication_tools
        )

        has_talk_to_user_tool = any(
            tool_.name == _TALK_TO_USER_TOOL_NAME for tool_ in mutated_agent_tools
        )
        if managerworkers_config.caller_input_mode == CallerInputMode.NEVER:
            if has_talk_to_user_tool:
                # Manager agent should not have tool to talk to user
                mutated_agent_tools = [
                    t for t in mutated_agent_tools if t.name != _TALK_TO_USER_TOOL_NAME
                ]
        else:
            if not has_talk_to_user_tool:
                # Manager agent should have tool to talk to user
                mutated_agent_tools.append(_make_talk_to_user_tool())

        mutated_agent_template = managerworkers_config.managerworkers_template.with_partial(
            {
                "name": current_agent.name,
                "description": current_agent.description,
                "other_agents": [
                    {"name": worker.name, "description": worker.description}
                    for worker in managerworkers_config.workers
                ],
                "caller_name": "HUMAN USER",
            }
        )

        with _MutatedConversationalComponent(
            current_agent,
            {
                "tools": mutated_agent_tools,
                "agent_template": mutated_agent_template,
                "output_descriptors": managerworkers_config.output_descriptors,
                "caller_input_mode": managerworkers_config.caller_input_mode,
                "_add_talk_to_user_tool": has_talk_to_user_tool,
            },
        ):
            return await current_conversation.execute_async(
                execution_interrupts=execution_interrupts,
            )

    @staticmethod
    async def _run_worker_round(
        current_conversation: Union["AgentConversation", "ManagerWorkersConversation"],
        execution_interrupts: Optional[Sequence[ExecutionInterrupt]] = None,
    ) -> ExecutionStatus:
        return await current_conversation.execute_async(
            execution_interrupts=execution_interrupts,
        )

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

                if isinstance(current_conversation, ManagerWorkersConversation):
                    raise ValueError(
                        "Manager Conversation cannot be of type `ManagerWorkersConversation`."
                    )

                # Handle pending tool requests of manager
                if isinstance(current_conversation.status, ToolRequestStatus):
                    signal = ManagerWorkersRunner._handle_pending_tool_requests_of_manager(
                        manager=current_agent,
                        manager_conversation=current_conversation,
                        managerworkers_conversation=conversation,
                    )

                    if signal == _ToolProcessSignal.RETURN:
                        return current_conversation.status
                    elif signal == _ToolProcessSignal.START_NEW_LOOP:
                        continue
                    else:
                        # _ToolProcessSignal.EXECUTE_AGENT -> we continue this loop with a new call to the current agent
                        pass

                status = await ManagerWorkersRunner._run_manager_round(
                    current_agent=current_agent,
                    managerworkers_config=managerworkers_config,
                    current_conversation=current_conversation,
                    execution_interrupts=execution_interrupts,
                )
            else:
                status = await ManagerWorkersRunner._run_worker_round(
                    current_conversation=current_conversation,
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

            if (
                isinstance(status, ToolRequestStatus)
                and current_agent_name == managerworkers_config.manager_agent.name
            ):
                # 1. current agent is the manager agent and is calling tools
                # These tool(s) will be handled in the next loop by checking the pending tools of the manager
                continue
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
                # 4. usual client tool requests of a worker
                # or tools that need confirmations of either the manager or a worker
                return status
            else:
                # 5. finish status: happening when caller_input_mode == NEVER
                return status

    @staticmethod
    def _handle_pending_tool_requests_of_manager(
        manager: Agent,
        manager_conversation: "AgentConversation",
        managerworkers_conversation: "ManagerWorkersConversation",
    ) -> _ToolProcessSignal:
        if not isinstance(manager_conversation.status, ToolRequestStatus):
            raise ValueError("Internal error: the status should be ToolRequestStatus")

        if manager_conversation.status._tool_results:
            manager_conversation._update_conversation_with_status()

        manager_conv_state = manager_conversation.state
        manager_conv_state._get_current_tool_request()
        tool_request = manager_conv_state.current_tool_request

        if not tool_request:
            # no tool left to execute, resume current agent execution
            manager_conversation.status = None
            return _ToolProcessSignal.EXECUTE_AGENT

        # Case 1: send_message tool
        if tool_request.name == _SEND_MESSAGE_TOOL_NAME:
            ManagerWorkersRunner._send_message_to_worker(
                managerworkers_conversation=managerworkers_conversation,
                managerworkers_config=managerworkers_conversation.component,
            )

            manager_conv_state.current_tool_request = None

            return (
                _ToolProcessSignal.START_NEW_LOOP
            )  # start a new loop to handle other pending tools if any

        tool = next((t for t in manager.tools if t.name == tool_request.name), None)

        # Case 2: standard client tool
        if tool and isinstance(tool, ClientTool):
            # Only one tool request is surfaced to the user at a time, other tool calls are still in the queue
            manager_conversation.status.tool_requests = [tool_request]
            # This is done here instead of the agent executor as tool handling for manager agent is done here
            manager_conv_state.current_tool_request = None

            return _ToolProcessSignal.RETURN

        # Case 3: Server tool or other internal tool
        # -> Let agent handle it (agent will check the current_tool_request)
        manager_conversation.status = None
        return _ToolProcessSignal.EXECUTE_AGENT

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

        # Get the oldest unanswered tool requests since the tool requests are processed sequentially
        tool_request_id = unanswered_tool_requests[0].tool_request_id

        manager_subconversation.append_tool_result(
            ToolResult(message.content, tool_request_id=tool_request_id)
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

        unanswered_tool_requests = _get_unanswered_tool_requests_from_agent_response(
            manager_subconversation.message_list
        )

        # Get the oldest unanswered tool requests since the tool requests are processed sequentially
        tool_request = unanswered_tool_requests[0]

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
