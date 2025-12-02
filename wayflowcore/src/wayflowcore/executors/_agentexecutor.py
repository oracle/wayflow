# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import os
import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple, Union

from wayflowcore import Flow
from wayflowcore._utils._templating_helpers import (
    _DEFAULT_VARIABLE_DESCRIPTION_TEMPLATE,
    render_template,
)
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.conversation import Conversation
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.events import record_event
from wayflowcore.events.event import (
    AgentExecutionIterationFinishedEvent,
    AgentExecutionIterationStartedEvent,
    ToolConfirmationRequestEndEvent,
    ToolConfirmationRequestStartEvent,
    ToolExecutionResultEvent,
    ToolExecutionStartEvent,
)
from wayflowcore.executors._events.event import EventType
from wayflowcore.executors._executionstate import ConversationExecutionState
from wayflowcore.executors._executor import ConversationExecutor, ExecutionInterruptedException
from wayflowcore.executors.executionstatus import (
    ExecutionStatus,
    FinishedStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.executors.interrupts.executioninterrupt import (
    ExecutionInterrupt,
    FlowExecutionInterrupt,
)
from wayflowcore.messagelist import Message, MessageList, MessageType
from wayflowcore.ociagent import OciAgent
from wayflowcore.planning import ExecutionPlan
from wayflowcore.property import JsonSchemaParam, Property, StringProperty
from wayflowcore.tools import ClientTool, ServerTool, Tool, ToolRequest, ToolResult
from wayflowcore.tools.tools import _sanitize_tool_name
from wayflowcore.tracing.span import AgentExecutionSpan, ToolExecutionSpan

if TYPE_CHECKING:
    from wayflowcore.executors._agentconversation import AgentConversation


logger = logging.getLogger(__name__)


_SUBMIT_TOOL_NAME = "submit_result"

_TALK_TO_USER_TOOL_NAME = "talk_to_user"
_TALK_TO_USER_INPUT_PARAM = "text"

EXIT_CONVERSATION_TOOL_NAME = "end_conversation"
EXIT_CONVERSATION_TOOL_MESSAGE = "Conversation has been ended by the agent."
EXIT_CONVERSATION_CONFIRMATION_MESSAGE = "You attempted to end the conversation. If the user indeed asked to exit, please call this tool again and do not reply anything else. You are a helpful assistant; do not annoy the user; do not ask them to confirm."
_TOOL_REJECTION_REASON = "Tool Request for tool {tool} denied due to reason: {reason}"


def _is_running_in_notebook() -> bool:
    try:
        from IPython.core.getipython import get_ipython

        return get_ipython().__class__.__name__ == "ZMQInteractiveShell"  # type: ignore
    except ImportError:
        return False


_DISABLE_STREAMING = "WAYFLOW_EXP_DISABLE_STREAMING"


def _can_use_streaming() -> bool:
    if _DISABLE_STREAMING in os.environ:
        return False
    return not _is_running_in_notebook()


def _log_messages_for_debug(messages: List[Message]) -> None:
    txt = "\n---\n".join([str(msg) for msg in messages])
    logger.debug("Current conversation messages:\n%s\n\n%s", txt, "-" * 20)


@dataclass
class AgentConversationExecutionState(ConversationExecutionState):
    """Contains the states for a flexible conversation"""

    memory: Optional[Any] = None
    plan: Optional[ExecutionPlan] = None
    tool_call_queue: List[ToolRequest] = field(default_factory=list)
    current_tool_request: Optional[ToolRequest] = None
    current_flow_conversation: Optional["Conversation"] = None
    current_sub_component_conversations: Dict[str, "Conversation"] = field(default_factory=dict)
    has_confirmed_conversation_exit: bool = False

    curr_iter: int = 0

    # just used in the executor, should not be serialized
    current_retrieved_tools: Optional[List[Tool]] = field(default=None, init=False)


def _agent_as_client_tool(agent: Union[Agent, OciAgent]) -> ClientTool:
    agent_input_parameters: Dict[str, JsonSchemaParam] = {}
    if isinstance(agent, Agent):
        resolved_agent_input_names = [property_.name for property_ in agent.input_descriptors]
        resolved_agent_inputs = [
            property_
            for property_ in agent.input_descriptors
            if property_.name in resolved_agent_input_names
        ]
        # list of resolved inputs (i.e. not including context providers). TODO: Remove `inputs` in favor of using `input_descriptors`.
        for input_descriptor in resolved_agent_inputs:
            if not input_descriptor.name:
                raise ValueError(
                    f"Cannot use agent '{agent.name}' as a sub-agent because of missing "
                    f"name for input {input_descriptor}. Please ensure that all input descriptors "
                    f"of a sub-agent have a name."
                )
            if input_descriptor.name == "context":
                raise ValueError(
                    f"Cannot use agent '{agent.name}' as a sub-agent because of use of reserved "
                    f"name in the agent inputs. The input name 'context' is a reserved name, please "
                    f"do not use this variable name in the `custom_instruction` of a sub-agent."
                )
            if input_descriptor.description == _DEFAULT_VARIABLE_DESCRIPTION_TEMPLATE.format(
                var_name=input_descriptor.name
            ):
                warnings.warn(
                    f"Input with name '{input_descriptor.name}' for agent '{agent.name}' uses a "
                    "default description. Please add a description to the input by specifying "
                    "the `input_descriptors` parameter of the Agent",
                    category=UserWarning,
                )
            input_json_schema = input_descriptor.to_json_schema()
            input_description = input_json_schema.get("description", "")
            if not input_description:
                raise ValueError(
                    f"Cannot use agent '{agent.name}' as a sub-agent because of missing description "
                    f"for input {input_descriptor}. Please ensure that all input descriptors "
                    f"of a sub-agent have a description."
                )
            input_json_schema["description"] = "(part of the sub-agent inputs) " + input_description
            agent_input_parameters[input_descriptor.name] = input_json_schema

    agent_parameters: Dict[str, JsonSchemaParam] = {
        "context": {
            "description": "Context to pass the expert. Make sure to state the question, and any relevant information the expert might need to answer the request",
            "type": "string",
        },
        **agent_input_parameters,
    }
    return ClientTool(
        name=_sanitize_tool_name(agent.name),
        description=agent.description or "",
        parameters=agent_parameters,
    )


def _get_end_conversation_tool() -> Tool:
    return ClientTool(
        name=EXIT_CONVERSATION_TOOL_NAME,
        description="Use this tool to end a conversation upon user request.",
        parameters={},
        output={},
    )


def _get_submit_tool_description(caller_input_mode: "CallerInputMode") -> str:
    from wayflowcore.agent import CallerInputMode

    description = """Function to finish the conversation when you found all required outputs. Never make up outputs, """
    if caller_input_mode == CallerInputMode.ALWAYS:
        description += "before calling this function, first ask the user for any missing information, to gather all the required values, and then call this function"
    elif caller_input_mode == CallerInputMode.NEVER:
        description += (
            "never ask the user but use all your tools and knowledge to fill the expected outputs"
        )
    else:
        raise ValueError("Unknown caller input mode")
    return description


def _make_submit_output_tool(
    caller_input_mode: "CallerInputMode", outputs: List[Property]
) -> ClientTool:
    return ClientTool(
        name=_SUBMIT_TOOL_NAME,
        description=_get_submit_tool_description(caller_input_mode),
        parameters={s.name: s.to_json_schema() for s in outputs},
        output={},
    )


def _make_talk_to_user_tool() -> ClientTool:
    return ClientTool(
        name=_TALK_TO_USER_TOOL_NAME,
        description=(
            "Send a message to the user. This can be used either to help the user with their "
            "request or to ask them for additional information you are missing. Prioritize "
            "answering their requests when possible."
        ),
        parameters={
            _TALK_TO_USER_INPUT_PARAM: StringProperty(
                name=_TALK_TO_USER_INPUT_PARAM, description="The message to send to the user."
            ).to_json_schema()
        },
        output={},
    )


class AgentConversationExecutor(ConversationExecutor):
    @staticmethod
    def _register_event(
        state: ConversationExecutionState,
        conversation: Conversation,
        event_type: EventType,
        tool_request: Optional[ToolRequest] = None,
    ) -> None:

        # Do not register talk_to_user_tool as an event
        if event_type in (EventType.TOOL_CALL_START, EventType.TOOL_CALL_END) and tool_request:
            if tool_request.name == _TALK_TO_USER_TOOL_NAME:
                return

        return ConversationExecutor._register_event(state, conversation, event_type)

    @staticmethod
    async def _collect_custom_instruction_variables(
        config: Agent,
        conversation: "AgentConversation",
    ) -> Dict[str, Any]:
        prompt_variables = {}
        custom_instruction_variable_names = {*config._all_variables}

        # 1. Check in the conversation inputs
        for input_descriptor in config.input_descriptors:  # See `_configure_agent_inputs`
            variable_name = input_descriptor.name
            if variable_name in conversation.inputs:
                prompt_variables[variable_name] = conversation.inputs[variable_name]
                custom_instruction_variable_names.remove(variable_name)

        # 2. Check in the context providers
        prompt_variables.update(
            await conversation._get_context_provider_values(
                variable_names=custom_instruction_variable_names,
                additional_context_providers=config.context_providers,
            )
        )
        return prompt_variables

    @staticmethod
    async def _generate_next_agent_message(
        config: Agent,
        conversation: "AgentConversation",
        state: AgentConversationExecutionState,
        messages: MessageList,
        tools: Optional[List[Tool]],
        plan: Optional[ExecutionPlan],
    ) -> Message:
        logger.debug("%s::generate_next_agent_message: building prompt", config.agent_id)

        prompt_template = config.agent_template.with_tools(tools or None)

        prompt_variables = await AgentConversationExecutor._collect_custom_instruction_variables(
            config=config, conversation=conversation
        )
        custom_instruction: Optional[str] = None
        if config.custom_instruction is not None and config.custom_instruction != "":
            custom_instruction = render_template(config.custom_instruction, inputs=prompt_variables)

        chat_history = _filter_messages_by_delimiter_type(messages, state, config.agent_id)

        prompt = await prompt_template.format_async(
            inputs={
                **prompt_variables,
                "custom_instruction": custom_instruction,
                prompt_template.CHAT_HISTORY_PLACEHOLDER_NAME: chat_history,
                "__PLAN__": plan.to_str() if plan else "",
            }
        )

        logger.debug("%s::generate_next_agent_message: built prompt:\n%s", config.agent_id, prompt)
        if _can_use_streaming():
            iterator = config.llm.stream_generate_async(prompt, _conversation=conversation)
            new_message = await messages._append_streaming_message(stream=iterator)
            # new_message is a copy of messages.messages[-1] so we must specify its sender
            # on top of specifying the sender of messages.messages[-1]
            new_message.sender = config.agent_id
        else:
            completion = await config.llm.generate_async(
                prompt=prompt,
                _conversation=conversation,
            )
            messages.append_message(completion.message)

        messages.messages[-1].sender = config.agent_id
        logger.debug("Agent generated %s", messages.messages[-1])
        return messages.messages[-1]

    @staticmethod
    async def _decide_next_action(
        config: Agent,
        conversation: "AgentConversation",
        state: AgentConversationExecutionState,
        messages: MessageList,
        tools: Optional[List[Tool]],
        plan: Optional[ExecutionPlan],
    ) -> bool:

        if (
            not _conversation_contains_user_messages(conversation)
            and config.initial_message is not None
        ):
            new_message = Message(
                content=config.initial_message,
                message_type=MessageType.AGENT,
                sender=config.agent_id,
            )
            conversation.append_message(new_message)
        else:
            new_message = await AgentConversationExecutor._generate_next_agent_message(
                config=config,
                conversation=conversation,
                state=state,
                messages=messages,
                tools=tools,
                plan=plan,
            )
        logger.debug(f"Agent executor answered: %s", str(new_message))

        # if no tool_requests, we simply yield to the user
        if new_message.tool_requests is None or len(new_message.tool_requests) == 0:
            return True

        # fix
        talk_to_user_request = next(
            (tr for tr in new_message.tool_requests if tr.name == _TALK_TO_USER_TOOL_NAME), None
        )
        if talk_to_user_request:
            logger.debug(
                "Parallel tool calling is disabled when using %s tool", _TALK_TO_USER_TOOL_NAME
            )
            new_message.tool_requests = [talk_to_user_request]

        state.tool_call_queue.extend(new_message.tool_requests)
        return False

    @staticmethod
    def _should_recreate_called_component_conversation(
        caller_conv: "AgentConversation",
        caller_config: Agent,
        called_component: ConversationalComponent,
        inputs: Dict[str, Any],
    ) -> bool:
        """Advanced users can override this method."""
        if isinstance(called_component, (Agent, OciAgent)):
            # Agent calls Agent: sub-conversation lifetime is unlimited
            return False
        elif isinstance(called_component, Flow):
            # Agent calls Flow: sub-conversation lifetime is unlimited
            # TODO: update to single-use
            return False
        else:
            raise ValueError(f"Unsupported called component: {called_component.__class__.__name__}")

    @staticmethod
    def _should_share_messages_with_called_component(
        caller_conv: "AgentConversation",
        caller_config: Agent,
        called_component: ConversationalComponent,
        inputs: Dict[str, Any],
    ) -> bool:
        """Advanced users can override this method."""
        if isinstance(called_component, (Agent, OciAgent)):
            # Agent calls Agent: messages are not shared
            return False
        elif isinstance(called_component, Flow):
            # Agent calls Flow: messages are shared
            return True
        else:
            raise ValueError(f"Unsupported called component: {called_component.__class__.__name__}")

    @staticmethod
    def _get_or_create_expert_agent_subconversation(
        caller_config: Agent,
        caller_conv: "AgentConversation",
        caller_messages: MessageList,
        expert_agent: Union[Agent, OciAgent],
        inputs: Dict[str, Any],
        caller_request_message: Message,
    ) -> "Conversation":
        sub_agent_conversation = caller_conv._get_sub_component_conversation(expert_agent)
        should_recreate_subconversation = (
            AgentConversationExecutor._should_recreate_called_component_conversation(
                caller_conv=caller_conv,
                caller_config=caller_config,
                called_component=expert_agent,
                inputs=inputs,
            )
        )
        # Case 1: No need to (re)create sub-conversation
        if sub_agent_conversation and not should_recreate_subconversation:
            # re-using the same conversation: we should not add the caller request
            # if are resuming from a client-tool execution (ToolRequestStatus/ToolExecutionConfirmationStatus)
            if not isinstance(
                sub_agent_conversation.status, (ToolRequestStatus, ToolExecutionConfirmationStatus)
            ):
                sub_agent_conversation.message_list.append_message(caller_request_message)
            return sub_agent_conversation

        # Case 2: Need to (re)create sub-conversation
        should_share_messages_with_caller = (
            AgentConversationExecutor._should_share_messages_with_called_component(
                caller_conv=caller_conv,
                caller_config=caller_config,
                called_component=expert_agent,
                inputs=inputs,
            )
        )
        init_messages: Optional[MessageList]
        if should_share_messages_with_caller:
            init_messages = caller_messages  # using the message list from the caller
        else:
            init_messages = MessageList.from_messages([])

        init_messages.append_message(caller_request_message)
        sub_agent_conversation = expert_agent.start_conversation(
            messages=init_messages, inputs=inputs
        )
        return sub_agent_conversation

    @staticmethod
    async def _execute_as_expert_agent(
        config: Agent,
        caller_conv: "AgentConversation",
        messages: MessageList,
        expert_agent: Union[Agent, OciAgent],
        agent_inputs: Dict[str, Any],
        caller_request_message: Message,
    ) -> Tuple[Any, str, ExecutionStatus]:
        agent_output: Any = None
        try:
            sub_agent_conversation = (
                AgentConversationExecutor._get_or_create_expert_agent_subconversation(
                    caller_config=config,
                    caller_conv=caller_conv,
                    caller_messages=messages,
                    expert_agent=expert_agent,
                    inputs=agent_inputs,
                    caller_request_message=caller_request_message,
                )
            )
            caller_conv._set_sub_component_conversation(expert_agent, sub_agent_conversation)
            subagent_execution_status = await sub_agent_conversation.execute_async()

            last_message = sub_agent_conversation.get_last_message()
            agent_output = last_message.content if last_message is not None else ""
            serialized_output = _serialize_output(agent_output)
        except Exception as e:
            agent_output = e
            serialized_output = str(e)
            subagent_execution_status = FinishedStatus(output_values={})

        if isinstance(subagent_execution_status, FinishedStatus):
            # reset state if agent finishes
            caller_conv._set_sub_component_conversation(expert_agent, None)

        return agent_output, serialized_output, subagent_execution_status

    @staticmethod
    async def _execute_flow(
        state: AgentConversationExecutionState,
        messages: MessageList,
        flow: Flow,
        inputs: Dict[str, Any],
    ) -> Tuple[Any, str, ExecutionStatus]:
        """
        Execute a flow and return its outputs and its execution status.
        The outputs will always be None, unless the execution status is
        FinishedStatus.
        """
        outputs: Any = None
        try:
            if state.current_flow_conversation is None:
                state.current_flow_conversation = flow.start_conversation(
                    inputs=inputs,
                    messages=messages,
                )
                messages.append_message(
                    Message(
                        content=_get_start_filtering_delimiter(state=state),
                        message_type=MessageType.INTERNAL,
                    )
                )
            flow_conversation = state.current_flow_conversation
            # We propagate the interrupts that work on flows, e.g., time limit and token limit
            interrupts = [
                interrupt
                for interrupt in (state._get_execution_interrupts() or [])
                if isinstance(interrupt, FlowExecutionInterrupt)
            ]
            status = await flow_conversation.execute_async(execution_interrupts=interrupts)

            if not isinstance(status, FinishedStatus):
                return None, "None", status

            outputs = status.output_values
            if len(outputs) == 1:
                # if single output, just unwrap it
                outputs = next(iter(outputs.values()))
        except Exception as e:
            outputs = e
            status = FinishedStatus(output_values={})

        state.current_flow_conversation = None
        messages.append_message(
            Message(
                content=_get_end_filtering_delimiter(state=state),
                message_type=MessageType.INTERNAL,
            )
        )
        serialized_output = _serialize_output(outputs)
        return outputs, serialized_output, status

    @staticmethod
    async def _execute_tool(
        tool: ServerTool, conversation: Conversation, inputs: Dict[str, Any]
    ) -> Tuple[Any, str]:
        try:
            tool._bind_parent_conversation_if_applicable(conversation)
            tool_output = await tool.run_async(**inputs)
            # serialize as part of the try/catch so that if there is a serialization error, it is caught
            serialized_output = _serialize_output(tool_output)
            return tool_output, serialized_output
        except Exception as e:
            return e, str(e)

    @staticmethod
    async def _execute_next_subcall(
        config: Agent,
        conversation: "AgentConversation",
        state: AgentConversationExecutionState,
        tool_request: ToolRequest,
        messages: MessageList,
    ) -> Optional[ExecutionStatus]:
        for agent in config.agents:
            if tool_request.name == _sanitize_tool_name(agent.name):
                return await AgentConversationExecutor._handle_agent_call(
                    config=config,
                    state=state,
                    agent_to_execute=agent,
                    tool_request=tool_request,
                    messages=messages,
                    conversation=conversation,
                )
        for flow in config.flows:
            if tool_request.name == _sanitize_tool_name(flow.name):
                return await AgentConversationExecutor._handle_flow_call(
                    config, state, flow, tool_request, messages
                )

        if state.current_retrieved_tools is None:
            # need to reload the tools if when reloading they are not present anymore
            state.current_retrieved_tools = await AgentConversationExecutor._collect_tools(
                config=config, curr_iter=state.curr_iter
            )
        for tool in state.current_retrieved_tools or []:
            if tool_request.name == tool.name:
                return await AgentConversationExecutor._handle_tool_call(
                    config, tool, conversation, tool_request, messages
                )
        else:
            # Did not find a valid tool, flow or sub-agent with the name `tool_request.name`
            return AgentConversationExecutor._handle_unknown_call(
                config, state, tool_request, messages
            )

    @staticmethod
    def _handle_unknown_call(
        config: Agent,
        state: AgentConversationExecutionState,
        tool_request: ToolRequest,
        messages: MessageList,
    ) -> Optional[ExecutionStatus]:
        currently_available_tool_names = [
            tool.name for tool in (state.current_retrieved_tools or [])
        ]
        messages.append_message(
            AgentConversationExecutor._get_tool_response_message(
                content=(
                    f"Tool named {tool_request.name} is not in the list of available tools. "
                    f"Remember that you ONLY have access to "
                    f"{len(currently_available_tool_names)} 'tools'.\n"
                    f"Available tools:\n{currently_available_tool_names}."
                ),
                tool_request_id=tool_request.tool_request_id,
                agent_id=config.agent_id,
            )
        )
        return None

    @staticmethod
    def _get_tool_response_message(content: str, tool_request_id: str, agent_id: str) -> Message:
        return Message(
            tool_result=ToolResult(
                content=content,
                tool_request_id=tool_request_id,
            ),
            message_type=MessageType.TOOL_RESULT,
            sender=agent_id,
            recipients={agent_id},
        )

    @staticmethod
    def _get_expert_agent_inputs_from_tool_call(
        caller_config: Agent,
        tool_request: ToolRequest,
        caller_messages: MessageList,
    ) -> Tuple[Dict[str, Any], Message]:
        """Advanced users can override this method."""
        REQUEST_KEY = "context"
        inputs = {
            k: v
            for k, v in tool_request.args.items()
            if k != REQUEST_KEY  # context is a reserved parameter name
        }
        last_message = caller_messages.get_last_message(strict=True)
        request_content = tool_request.args.get(REQUEST_KEY, last_message.content)
        request_message = Message(
            content=request_content,
            message_type=MessageType.USER,
            sender=caller_config.agent_id,
        )
        return inputs, request_message

    @staticmethod
    async def _handle_agent_call(
        config: Agent,
        state: AgentConversationExecutionState,
        agent_to_execute: Union[Agent, OciAgent],
        tool_request: ToolRequest,
        messages: MessageList,
        conversation: "AgentConversation",
    ) -> Optional[ExecutionStatus]:
        # 1. Extract inputs and caller request to provide to the Expert Agent
        agent_inputs, request_message = (
            AgentConversationExecutor._get_expert_agent_inputs_from_tool_call(
                caller_config=config,
                tool_request=tool_request,
                caller_messages=messages,
            )
        )
        # 2. Call expert Agent
        output, serialized_output, agent_execution_status = (
            await AgentConversationExecutor._execute_as_expert_agent(
                config=config,
                caller_conv=conversation,
                messages=messages,
                expert_agent=agent_to_execute,
                agent_inputs=agent_inputs,
                caller_request_message=request_message,
            )
        )
        logger.debug(
            'Agent "%s" (id=%s) returned: %s, status: %s',
            tool_request.name,
            tool_request.tool_request_id,
            serialized_output,
            agent_execution_status,
        )

        if isinstance(output, Exception) and config.raise_exceptions:
            # Raise error in sub-agent execution
            raise output

        if isinstance(agent_execution_status, (FinishedStatus, UserMessageRequestStatus)):
            messages.append_message(
                AgentConversationExecutor._get_tool_response_message(
                    content=output,
                    tool_request_id=tool_request.tool_request_id,
                    agent_id=config.agent_id,
                )
            )
            return None
        else:
            return agent_execution_status

    @staticmethod
    async def _handle_flow_call(
        config: Agent,
        state: AgentConversationExecutionState,
        flow: Flow,
        tool_request: ToolRequest,
        messages: MessageList,
    ) -> Optional[ExecutionStatus]:
        logger.debug(
            'Agent executing flow "%s" (id=%s) with arguments: %s',
            tool_request.name,
            tool_request.tool_request_id,
            tool_request.args,
        )
        output, serialized_output, flow_execution_status = (
            await AgentConversationExecutor._execute_flow(state, messages, flow, tool_request.args)
        )

        logger.debug(
            'Flow "%s" (id=%s) returned: %s',
            tool_request.name,
            tool_request.tool_request_id,
            serialized_output,
        )

        if isinstance(output, Exception) and config.raise_exceptions:
            # Raise error in sub-flow execution
            raise output

        if isinstance(flow_execution_status, FinishedStatus):
            messages.append_message(
                AgentConversationExecutor._get_tool_response_message(
                    output, tool_request.tool_request_id, config.agent_id
                )
            )
            return None
        else:
            return flow_execution_status

    @staticmethod
    async def _handle_tool_call(
        config: Agent,
        tool: Tool,
        conversation: "AgentConversation",
        tool_request: ToolRequest,
        messages: MessageList,
    ) -> Optional[ExecutionStatus]:
        logger.debug(
            'Agent executing tool "%s" (id=%s) with arguments: %s',
            tool_request.name,
            tool_request.tool_request_id,
            tool_request.args,
        )

        if tool.requires_confirmation:
            if not tool_request._requires_confirmation:
                record_event(
                    ToolConfirmationRequestStartEvent(
                        tool=tool,
                        tool_request=tool_request,
                    )
                )
                tool_request._requires_confirmation = True
                return ToolExecutionConfirmationStatus(
                    tool_requests=[tool_request], _conversation_id=conversation.id
                )

            record_event(
                ToolConfirmationRequestEndEvent(
                    tool=tool,
                    tool_request=tool_request,
                )
            )
            if tool_request._tool_execution_confirmed is None:
                raise ValueError(
                    "Missing tool confirmation, "
                    "please make sure to either confirm or reject the tool execution before resuming the conversation."
                )
            if not tool_request._tool_execution_confirmed:

                output_message = _TOOL_REJECTION_REASON.format(
                    tool=tool, reason=tool_request._tool_rejection_reason
                )
                messages.append_message(
                    AgentConversationExecutor._get_tool_response_message(
                        output_message,
                        tool_request.tool_request_id,
                        config.agent_id,
                    )
                )

                return None

        if isinstance(tool, ClientTool):
            try:
                tool_result_client_answer = next(
                    m.tool_result
                    for m in reversed(messages.messages)
                    if m.tool_result is not None
                    and m.tool_result.tool_request_id == tool_request.tool_request_id
                )
                tool._add_defaults_to_tool_outputs(tool_result_client_answer.content)
                record_event(
                    ToolExecutionResultEvent(
                        tool=tool,
                        tool_result=tool_result_client_answer,
                    )
                )
                logger.debug(
                    'Found the tool result message for tool "%s" (id=%s)',
                    tool_request.name,
                    tool_request.tool_request_id,
                )
                return None
            except StopIteration:
                # client hasn't answered tool request yet
                record_event(
                    ToolExecutionStartEvent(
                        tool=tool,
                        tool_request=tool_request,
                    )
                )
                logger.debug(
                    'Did not find the tool result message for tool "%s" (id=%s). Returning the execution status ToolRequestStatus',
                    tool_request.name,
                    tool_request.tool_request_id,
                )
                # Even though we are executing one tool, which happens to be a client tool, we
                # choose here retrieve all the open client tool requests, such that we minimize the
                # number of times the agent needs to yield. In particular, yielding for a tool
                # request typically requires a web response to a client and a new request from them,
                # so this optimization minimizes the number of required requests between the client
                # and the agent.
                all_open_client_tool_requests = (
                    AgentConversationExecutor._get_all_open_client_tool_requests(
                        config, conversation.state, messages
                    )
                )

                return ToolRequestStatus(
                    tool_requests=all_open_client_tool_requests, _conversation_id=conversation.id
                )
        elif isinstance(tool, ServerTool):
            with ToolExecutionSpan(
                tool=tool,
                tool_request=tool_request,
            ) as span:
                output, serialized_output = await AgentConversationExecutor._execute_tool(
                    tool, conversation, tool_request.args
                )
                span.record_end_span_event(
                    output=output,
                )

            logger.debug(
                'Tool "%s" (id=%s) returned: %s',
                tool_request.name,
                tool_request.tool_request_id,
                serialized_output,
            )

            if isinstance(output, Exception) and config.raise_exceptions:
                # Raise error in tool execution
                raise output

            # Check if tool output is copyable
            output = tool._check_tool_outputs_copyable(
                output, raise_exceptions=config.raise_exceptions
            )

            messages.append_message(
                AgentConversationExecutor._get_tool_response_message(
                    output, tool_request.tool_request_id, config.agent_id
                )
            )
            return None
        else:
            raise ValueError(f"Illegal: unsupported tool type: {tool}")

    @staticmethod
    def _get_all_open_client_tool_requests(
        config: Agent,
        state: AgentConversationExecutionState,
        messages: MessageList,
    ) -> List[ToolRequest]:
        if not state.current_retrieved_tools:
            return []

        completed_tool_calls = {
            m.tool_result.tool_request_id for m in messages.get_messages() if m.tool_result
        }
        all_tools = {tool.name: tool for tool in state.current_retrieved_tools}
        open_client_tool_requests = [
            tr
            for m in messages.get_messages()
            for tr in m.tool_requests or []
            if tr.tool_request_id not in completed_tool_calls
            and isinstance(all_tools.get(tr.name), ClientTool)
        ]
        return open_client_tool_requests

    @staticmethod
    async def execute_async(
        conversation: Conversation,
        execution_interrupts: Optional[Sequence[ExecutionInterrupt]] = None,
    ) -> ExecutionStatus:
        from ._agentconversation import AgentConversation

        if not isinstance(conversation, AgentConversation):
            raise ValueError(
                f"the provided conversation to an agent must be of type AgentConversation but was {conversation.__class__.__name__}"
            )
        with AgentExecutionSpan(conversational_component=conversation.component) as span:
            execution_status = await AgentConversationExecutor._execute_agent(
                conversation, execution_interrupts
            )
            span.record_end_span_event(execution_status=execution_status)
        return execution_status

    @staticmethod
    async def _process_tool_call(
        agent_config: Agent,
        tool_request: ToolRequest,
        agent_state: AgentConversationExecutionState,
        conversation: "AgentConversation",
    ) -> Tuple[Optional[ExecutionStatus], bool]:
        should_yield = False
        if tool_request.name == _SUBMIT_TOOL_NAME:
            outputs = AgentConversationExecutor._collect_submit_tool_outputs(
                config=agent_config,
                submit_tool_call=tool_request,
                conversation=conversation,
            )
            if outputs is not None:
                return FinishedStatus(output_values=outputs, _conversation_id=conversation.id), True
        elif tool_request.name == _TALK_TO_USER_TOOL_NAME:
            successful_tool_use = _convert_talk_to_user_tool_call_into_agent_message(
                agent_config=agent_config,
                tool_request=tool_request,
                conversation=conversation,
            )
            should_yield = successful_tool_use
            # ^ If something went wrong and the message is converted to USER message, we should NOT yield!
        elif tool_request.name == EXIT_CONVERSATION_TOOL_NAME:
            if not agent_state.has_confirmed_conversation_exit:
                # we will ask for confirmation
                agent_state.has_confirmed_conversation_exit = True
                conversation.append_message(
                    AgentConversationExecutor._get_tool_response_message(
                        EXIT_CONVERSATION_CONFIRMATION_MESSAGE,
                        tool_request.tool_request_id,
                        agent_config.agent_id,
                    )
                )
            else:
                conversation.append_message(
                    AgentConversationExecutor._get_tool_response_message(
                        EXIT_CONVERSATION_TOOL_MESSAGE,
                        tool_request.tool_request_id,
                        agent_config.agent_id,
                    )
                )
                return FinishedStatus(output_values={}, _conversation_id=conversation.id), True
        else:
            tool_execution_status = await AgentConversationExecutor._execute_next_subcall(
                config=agent_config,
                conversation=conversation,
                state=agent_state,
                tool_request=tool_request,
                messages=conversation.message_list,
            )
            if tool_execution_status and tool_execution_status._requires_yielding:
                return tool_execution_status, True

            should_yield = False
        return None, should_yield

    @staticmethod
    async def _execute_agent(
        conversation: "AgentConversation",
        execution_interrupts: Optional[Sequence[ExecutionInterrupt]] = None,
    ) -> ExecutionStatus:
        agent_config = conversation.component

        logger.debug("%s::execute: start of execution", agent_config.agent_id)
        logger.debug("Interrupts received: %s", execution_interrupts)

        agent_state = conversation.state
        agent_state._set_execution_interrupts(execution_interrupts)

        try:
            AgentConversationExecutor._register_event(
                state=agent_state,
                conversation=conversation,
                event_type=EventType.EXECUTION_START,
            )

            messages = conversation.message_list
            agent_state.curr_iter = 0
            should_yield = False

            while not should_yield:

                AgentConversationExecutor._register_event(
                    state=agent_state,
                    conversation=conversation,
                    event_type=EventType.EXECUTION_LOOP_ITERATION_START,
                )
                record_event(
                    AgentExecutionIterationStartedEvent(
                        execution_state=conversation.state,
                    )
                )

                if agent_state.current_tool_request is not None:
                    tool_request = agent_state.current_tool_request
                    AgentConversationExecutor._register_event(
                        state=agent_state,
                        conversation=conversation,
                        event_type=EventType.TOOL_CALL_START,
                        tool_request=tool_request,
                    )
                    execution_status, should_yield = (
                        await AgentConversationExecutor._process_tool_call(
                            agent_config=agent_config,
                            tool_request=tool_request,
                            agent_state=agent_state,
                            conversation=conversation,
                        )
                    )
                    if execution_status is not None:
                        return execution_status

                    agent_state.current_tool_request = None

                    AgentConversationExecutor._register_event(
                        state=agent_state,
                        conversation=conversation,
                        event_type=EventType.TOOL_CALL_END,
                        tool_request=tool_request,
                    )

                elif len(agent_state.tool_call_queue) > 0:
                    agent_state.current_tool_request = agent_state.tool_call_queue.pop(0)
                elif agent_state.curr_iter >= agent_config.max_iterations:
                    if len(agent_config.output_descriptors) > 0:
                        # need to generate some outputs
                        default_outputs = {
                            o.name: o.default_value for o in agent_config.output_descriptors
                        }
                        return FinishedStatus(
                            output_values=default_outputs, _conversation_id=conversation.id
                        )
                    break
                else:
                    logger.debug("No open tool call, will decide next action by prompting the llm")
                    agent_state.current_retrieved_tools = (
                        await AgentConversationExecutor._collect_tools(
                            config=agent_config, curr_iter=agent_state.curr_iter
                        )
                    )

                    agent_state.curr_iter += 1

                    AgentConversationExecutor._register_event(
                        state=agent_state,
                        conversation=conversation,
                        event_type=EventType.GENERATION_START,
                    )

                    should_yield = await AgentConversationExecutor._decide_next_action(
                        config=agent_config,
                        conversation=conversation,
                        state=agent_state,
                        messages=messages,
                        tools=agent_state.current_retrieved_tools,
                        plan=agent_state.plan,
                    )

                    AgentConversationExecutor._register_event(
                        state=agent_state,
                        conversation=conversation,
                        event_type=EventType.GENERATION_END,
                    )

                    if should_yield and agent_config.caller_input_mode == CallerInputMode.NEVER:
                        conversation.append_message(
                            _caller_input_mode_never_reminder(
                                caller_input_mode=agent_config.caller_input_mode,
                                sender=agent_config.agent_id,
                            )
                        )
                        should_yield = False

                AgentConversationExecutor._register_event(
                    state=agent_state,
                    conversation=conversation,
                    event_type=EventType.EXECUTION_LOOP_ITERATION_END,
                )
                record_event(
                    AgentExecutionIterationFinishedEvent(
                        execution_state=conversation.state,
                    )
                )

            AgentConversationExecutor._register_event(
                state=agent_state,
                conversation=conversation,
                event_type=EventType.EXECUTION_END,
            )
        except ExecutionInterruptedException as e:
            return e.execution_status

        if agent_config.caller_input_mode == CallerInputMode.ALWAYS:
            last_message = conversation.get_last_message()
            if last_message is None:
                raise ValueError("Something went wrong, should not happen")
            return UserMessageRequestStatus(
                message=last_message,
                _conversation_id=conversation.id,
            )
        return FinishedStatus(output_values={}, _conversation_id=conversation.id)

    @staticmethod
    async def _collect_tools(config: Agent, curr_iter: int) -> Optional[List[Tool]]:
        tools: Optional[List[Tool]]

        # last possible llm generation
        if curr_iter == config.max_iterations - 1:
            if (
                config.caller_input_mode == CallerInputMode.NEVER
                and len(config.output_descriptors) > 0
            ):
                # we only allow the LLM to submit
                tools = [
                    tool for tool in config._all_static_tools if tool.name == _SUBMIT_TOOL_NAME
                ]
            else:
                # we don't want the model to output a tool call for the last iteration
                tools = [
                    tool
                    for tool in config._all_static_tools
                    if tool.name
                    in {_SUBMIT_TOOL_NAME, _TALK_TO_USER_TOOL_NAME, EXIT_CONVERSATION_TOOL_NAME}
                ]
        else:
            # The list of tools passed to the Agent includes the list of static tools
            # as well as the tools fetch from the ToolBoxes
            tools = [
                *config._all_static_tools,
                *[
                    tool
                    for toolbox in config._toolboxes
                    for tool in await toolbox.get_tools_async()
                ],
            ]
        return tools

    @staticmethod
    def _collect_submit_tool_outputs(
        config: Agent, submit_tool_call: ToolRequest, conversation: Conversation
    ) -> Optional[Dict[str, Any]]:
        """
        We check if the submit tool arguments are the expected outputs. If yes, we return, if not, we loop
        back to ask the agent to correct itself.
        """
        if len(config.output_descriptors) == 0:
            raise ValueError("Internal error, the agent should not have the submit tool")

        tool_inputs = submit_tool_call.args
        missing_inputs = [
            o.name
            for o in config.output_descriptors
            if o.name not in tool_inputs and not o.has_default
        ]
        successful_submission = len(missing_inputs) == 0
        if successful_submission:
            tool_output_content = "The submission was successful"
        else:
            tool_output_content = f"The submission: {tool_inputs}\n is missing some inputs: {missing_inputs}. Please resubmit with the correct inputs."
            logger.debug(
                f"The agent made an incomplete output submission.\nSubmission: {tool_inputs}\nMissing: {missing_inputs}"
            )

        conversation.append_message(
            Message(
                role="user",
                sender=config.id,
                tool_result=ToolResult(
                    content=tool_output_content,
                    tool_request_id=submit_tool_call.tool_request_id,
                ),
            )
        )

        if not successful_submission:
            return None

        agent_outputs = {
            o.name: tool_inputs.get(o.name, o.default_value) for o in config.output_descriptors
        }
        logger.debug(f"The agent successfully returned the outputs: {agent_outputs}")
        return agent_outputs


def _convert_talk_to_user_tool_call_into_agent_message(
    agent_config: Agent, tool_request: ToolRequest, conversation: "AgentConversation"
) -> bool:
    question_is_present = _TALK_TO_USER_INPUT_PARAM in tool_request.args
    last_message = conversation.message_list.get_last_message()
    if not last_message or last_message.tool_result is not None:
        raise ValueError(
            f"Internal error: Expected {_TALK_TO_USER_TOOL_NAME} tool request message, "
            "received a message with a tool result."
        )
    # we need to remove the tool call and replace by a question
    conversation.message_list._update_last_message_fields(
        fields=dict(
            content=(
                tool_request.args[_TALK_TO_USER_INPUT_PARAM]
                if question_is_present
                else str(tool_request.args)
            ),
            role="assistant",
            tool_requests=None,
        ),
    )
    message_to_update = conversation.get_last_message()
    if message_to_update is None:
        raise RuntimeError("Last message was None, this should not be the case")
    if question_is_present:
        return question_is_present  # True
    # else we need to remind the agent to use the talk to user tool properly
    conversation.append_user_message(
        f"{_TALK_TO_USER_TOOL_NAME} tool used improperly (missing field {_TALK_TO_USER_INPUT_PARAM}"
    )
    return question_is_present  # False


def _caller_input_mode_never_reminder(caller_input_mode: CallerInputMode, sender: str) -> Message:
    content = f"I'm not available. Please achieve the task by yourself"
    if caller_input_mode:
        content += f" and submit using the {_SUBMIT_TOOL_NAME} function"
    content += ". DO NOT generate pure text."
    return Message(role="user", content=content, sender=sender)


def _serialize_output(output: Any) -> str:
    if not isinstance(output, str):
        logger.debug("Output is not str, make sure it is serializable with `str()`.")
    return str(output)


def _filter_messages_by_delimiter_type(
    messages: MessageList,
    state: AgentConversationExecutionState,
    agent_id: str,
) -> List[Message]:
    filtered_messages = messages.get_messages()
    logger.debug("%s::Messages before filtering", agent_id)
    _log_messages_for_debug(filtered_messages)

    filtered_messages = _filter_messages_by_delimiter(filtered_messages, state=state)
    filtered_messages = MessageList._filter_messages_by_type(
        messages=filtered_messages,
        types_to_include=[
            MessageType.TOOL_RESULT,
            MessageType.USER,
            MessageType.AGENT,
            MessageType.TOOL_REQUEST,
        ],
    )
    logger.debug("%s::Messages after filtering", agent_id)
    _log_messages_for_debug(filtered_messages)
    return filtered_messages


def _filter_messages_by_delimiter(
    messages: List[Message], state: AgentConversationExecutionState
) -> List[Message]:
    filtered_messages = []
    filter_out = False
    for message in messages:
        if message.message_type == MessageType.INTERNAL:
            if message.content == _get_start_filtering_delimiter(state=state):
                filter_out = True
            elif message.content == _get_end_filtering_delimiter(state=state):
                filter_out = False
        if filter_out:
            continue

        filtered_messages.append(message)
    return filtered_messages


def _get_start_filtering_delimiter(state: AgentConversationExecutionState) -> str:
    return f"START_FILTERING_FLOW_MESSAGES_{id(state)}"


def _get_end_filtering_delimiter(state: AgentConversationExecutionState) -> str:
    return f"END_FILTERING_FLOW_MESSAGES_{id(state)}"


def _conversation_contains_user_messages(conversation: Conversation) -> bool:
    return any(m.message_type == MessageType.USER for m in conversation.get_messages())
