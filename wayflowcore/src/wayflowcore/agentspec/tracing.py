# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
from typing import Dict, Optional, Union, cast

from pyagentspec import Component as AgentSpecComponent
from pyagentspec.agent import Agent as AgentSpecAgent
from pyagentspec.flows.flow import Flow as AgentSpecFlow
from pyagentspec.flows.node import Node as AgentSpecNode
from pyagentspec.llms import LlmConfig as AgentSpecLlmConfig
from pyagentspec.llms import LlmGenerationConfig
from pyagentspec.tools import Tool as AgentSpecTool
from pyagentspec.tracing.events import AgentExecutionEnd as AgentSpecAgentExecutionEnd
from pyagentspec.tracing.events import AgentExecutionStart as AgentSpecAgentExecutionStart
from pyagentspec.tracing.events import ExceptionRaised as AgentSpecExceptionRaised
from pyagentspec.tracing.events import FlowExecutionEnd as AgentSpecFlowExecutionEnd
from pyagentspec.tracing.events import FlowExecutionStart as AgentSpecFlowExecutionStart
from pyagentspec.tracing.events import (
    LlmGenerationChunkReceived as AgentSpecLlmGenerationChunkReceived,
)
from pyagentspec.tracing.events import LlmGenerationRequest as AgentSpecLlmGenerationRequest
from pyagentspec.tracing.events import LlmGenerationResponse as AgentSpecLlmGenerationResponse
from pyagentspec.tracing.events import NodeExecutionEnd as AgentSpecNodeExecutionEnd
from pyagentspec.tracing.events import NodeExecutionStart as AgentSpecNodeExecutionStart
from pyagentspec.tracing.events import ToolExecutionRequest as AgentSpecToolExecutionRequest
from pyagentspec.tracing.events import ToolExecutionResponse as AgentSpecToolExecutionResponse
from pyagentspec.tracing.events.llmgeneration import ToolCall as AgentSpecToolCall
from pyagentspec.tracing.messages.message import Message as AgentSpecMessage
from pyagentspec.tracing.spans import AgentExecutionSpan as AgentSpecAgentExecutionSpan
from pyagentspec.tracing.spans import FlowExecutionSpan as AgentSpecFlowExecutionSpan
from pyagentspec.tracing.spans import LlmGenerationSpan as AgentSpecLlmGenerationSpan
from pyagentspec.tracing.spans import NodeExecutionSpan as AgentSpecNodeExecutionSpan
from pyagentspec.tracing.spans import Span as AgentSpecSpan
from pyagentspec.tracing.spans import ToolExecutionSpan as AgentSpecToolExecutionSpan

from wayflowcore._utils.formatting import stringify
from wayflowcore.agentspec import AgentSpecExporter
from wayflowcore.component import Component
from wayflowcore.events.event import (
    AgentExecutionFinishedEvent,
    AgentExecutionStartedEvent,
    ConversationMessageStreamChunkEvent,
    Event,
    ExceptionRaisedEvent,
    FlowExecutionFinishedEvent,
    FlowExecutionStartedEvent,
    LlmGenerationRequestEvent,
    LlmGenerationResponseEvent,
    StepInvocationResultEvent,
    StepInvocationStartEvent,
    ToolExecutionResultEvent,
    ToolExecutionStartEvent,
)
from wayflowcore.events.eventlistener import EventListener
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.tracing.span import LlmGenerationSpan, get_active_span_stack, get_current_span


class AgentSpecEventListener(EventListener):
    """Event listener that emits traces according to the Open Agent Spec Tracing standard"""

    def __init__(self) -> None:
        super().__init__()
        # We keep track of the mapping between the wayflow span (id) and the corresponding agent spec span
        self.agentspec_spans_registry: Dict[str, AgentSpecSpan] = {}
        # As we need to store agent spec objects in the agent spec spans and events, we need to perform conversions
        self.agentspec_exporter: AgentSpecExporter = AgentSpecExporter()
        # We keep a registry of conversions, so that we do not repeat the conversion for the same object twice
        self.agentspec_components_registry: Dict[str, AgentSpecComponent] = {}
        # Track last assistant message id and a robust mapping tool_request_id -> assistant message id.
        # Some providers may emit tool events before final assistant message id is known; we allow
        # temporarily missing ids and backfill on LLM response.
        self._last_assistant_message_id: Union[str, None] = None
        self._tool_to_message: Dict[str, Optional[str]] = {}

    def _convert_to_agentspec(self, component: Component) -> AgentSpecComponent:
        if component.id not in self.agentspec_components_registry:
            self.agentspec_components_registry[component.id] = self.agentspec_exporter.to_component(
                component
            )
        return self.agentspec_components_registry[component.id]

    def __call__(self, event: Event) -> None:
        # We intercept the wayflow events, and based on the type of event:
        # - if it corresponds to a span start event, we create the corresponding agent spec span, and we start it
        # - we map the wayflow event to the corresponding agent spec one, and we emit that
        # - if it corresponds to a span end event, we retrieve the corresponding agent spec span, and we close it
        current_span = get_current_span()
        if not current_span:
            return
        current_agentspec_span = self.agentspec_spans_registry.get(current_span.span_id, None)
        current_span_name = current_span.name or ""
        event_name = event.name or ""
        match event:
            case LlmGenerationRequestEvent():
                # LLM Generation starts. Create the new agent spec span, start it, add the event
                llm_config = cast(AgentSpecLlmConfig, self._convert_to_agentspec(event.llm))
                if event.prompt.generation_config:
                    agentspec_generation_config = LlmGenerationConfig(
                        top_p=event.prompt.generation_config.top_p,
                        temperature=event.prompt.generation_config.temperature,
                        max_tokens=event.prompt.generation_config.max_tokens,
                    )
                else:
                    agentspec_generation_config = LlmGenerationConfig()
                current_agentspec_span = AgentSpecLlmGenerationSpan(
                    id=current_span.span_id,
                    name=current_span_name,
                    llm_config=llm_config,
                )
                self.agentspec_spans_registry[current_span.span_id] = current_agentspec_span
                current_agentspec_span.start()
                current_agentspec_span.add_event(
                    AgentSpecLlmGenerationRequest(
                        id=event.event_id,
                        name=event_name,
                        llm_config=llm_config,
                        llm_generation_config=agentspec_generation_config,
                        prompt=[
                            AgentSpecMessage(
                                id=message.id,
                                content=message.content,
                                sender=message.sender or "",
                                role=message.role,
                            )
                            for message in event.prompt.messages
                        ],
                        tools=[
                            cast(AgentSpecTool, self._convert_to_agentspec(tool))
                            for tool in event.prompt.tools or []
                        ],
                        request_id=current_agentspec_span.id,
                    )
                )
            case LlmGenerationResponseEvent():
                # LLM Generation ends. Add the event to the agent spec span and close the span
                if not current_agentspec_span:
                    return
                message = event.completion.message
                # Ensure assistant message id is populated.
                # Prefer provider/message id; fall back to the Wayflow span id for stability.
                message_id = message.id or current_span.span_id
                self._last_assistant_message_id = message_id
                # Backfill any pending tool-call mappings with the now-known assistant message id
                for tc_id, mid in list(self._tool_to_message.items()):
                    if mid is None:
                        self._tool_to_message[tc_id] = message_id
                llm_config = cast(AgentSpecLlmConfig, self._convert_to_agentspec(event.llm))
                current_agentspec_span.add_event(
                    AgentSpecLlmGenerationResponse(
                        id=event.event_id,
                        name=event_name,
                        llm_config=llm_config,
                        request_id=current_agentspec_span.id,
                        completion_id=message_id,
                        content=message.content,
                        tool_calls=[
                            AgentSpecToolCall(
                                call_id=request.tool_request_id,
                                tool_name=request.name,
                                arguments=json.dumps(request.args),
                            )
                            for request in message.tool_requests or []
                        ],
                        input_tokens=(
                            event.completion.token_usage.input_tokens
                            if event.completion.token_usage
                            else None
                        ),
                        output_tokens=(
                            event.completion.token_usage.output_tokens
                            if event.completion.token_usage
                            else None
                        ),
                    )
                )
                current_agentspec_span.end()
            case ConversationMessageStreamChunkEvent():
                # We are in a ConversationMessageStreamSpan, we need to find the closest llm generation span,
                # so that we can retrieve the corresponding agent spec span
                llm_generation_span = next(
                    (
                        span
                        for span in get_active_span_stack()[::-1]
                        if isinstance(span, LlmGenerationSpan)
                    ),
                    None,
                )
                # Llm Generation Span not found, we don't emit any chunk event
                if not llm_generation_span:
                    return
                # No corresponding Agent Spec span found, we don't emit any chunk event
                if not (
                    current_agentspec_span := self.agentspec_spans_registry.get(
                        llm_generation_span.span_id, None
                    )
                ):
                    return
                current_agentspec_span.add_event(
                    AgentSpecLlmGenerationChunkReceived(
                        id=event.event_id,
                        name=event_name,
                        llm_config=cast(
                            AgentSpecLlmGenerationSpan, current_agentspec_span
                        ).llm_config,
                        request_id=current_agentspec_span.id,
                        content=event.chunk,
                        tool_calls=[],
                    )
                )
            case ToolExecutionStartEvent():
                # Tool execution starts. Create the new agent spec span, start it, add the event
                agentspec_tool = cast(AgentSpecTool, self._convert_to_agentspec(event.tool))
                current_agentspec_span = AgentSpecToolExecutionSpan(
                    id=current_span.span_id,
                    name=current_span_name,
                    tool=agentspec_tool,
                )
                self.agentspec_spans_registry[current_span.span_id] = current_agentspec_span
                current_agentspec_span.start()
                # Seed correlation mapping; may be pending until LLM response provides message id
                tc_id = event.tool_request.tool_request_id
                if tc_id not in self._tool_to_message:
                    self._tool_to_message[tc_id] = self._last_assistant_message_id
                current_agentspec_span.add_event(
                    AgentSpecToolExecutionRequest(
                        id=event.event_id,
                        name=event_name,
                        tool=agentspec_tool,
                        request_id=tc_id,
                        inputs={
                            input_name: input_value
                            for input_name, input_value in event.tool_request.args.items()
                        },
                    )
                )
            case ToolExecutionResultEvent():
                # Tool execution ends. Add the event to the agent spec span and close the span
                if not current_agentspec_span:
                    return
                agentspec_tool = cast(AgentSpecTool, self._convert_to_agentspec(event.tool))
                tool_result_content = event.tool_result.content
                if agentspec_tool.outputs and len(agentspec_tool.outputs) == 1:
                    tool_result_content = {agentspec_tool.outputs[0].title: tool_result_content}
                tc_id = event.tool_result.tool_request_id
                if tc_id is None:
                    raise RuntimeError(
                        "`tool_request_id` should not be None in ToolExecutionResultEvent"
                    )
                # Ensure a mapping exists; attach message id lazily if still pending
                if tc_id not in self._tool_to_message:
                    self._tool_to_message[tc_id] = self._last_assistant_message_id
                msg_id = self._tool_to_message.get(tc_id)
                if msg_id is None:
                    # Last-resort fallback to current known assistant id
                    msg_id = self._last_assistant_message_id or current_span.span_id
                    self._tool_to_message[tc_id] = msg_id
                current_agentspec_span.add_event(
                    AgentSpecToolExecutionResponse(
                        id=event.event_id,
                        name=event_name,
                        request_id=tc_id,
                        tool=agentspec_tool,
                        outputs={
                            output.title: tool_result_content[output.title]
                            for output in agentspec_tool.outputs or []
                        },
                    )
                )
                # Clear mapping for this tool call
                self._tool_to_message.pop(tc_id, None)
                current_agentspec_span.end()
            case StepInvocationStartEvent():
                # Step (node) execution starts. Create the new agent spec span, start it, add the event
                agentspec_node = cast(AgentSpecNode, self._convert_to_agentspec(event.step))
                current_agentspec_span = AgentSpecNodeExecutionSpan(
                    id=current_span.span_id,
                    name=current_span_name,
                    node=agentspec_node,
                )
                self.agentspec_spans_registry[current_span.span_id] = current_agentspec_span
                current_agentspec_span.start()
                current_agentspec_span.add_event(
                    AgentSpecNodeExecutionStart(
                        id=event.event_id,
                        name=event_name,
                        node=agentspec_node,
                        inputs={
                            input_name: input_value
                            for input_name, input_value in event.inputs.items()
                        },
                    )
                )
            case StepInvocationResultEvent():
                # Step execution ends. Add the event to the agent spec span and close the span
                if not current_agentspec_span:
                    return
                agentspec_node = cast(AgentSpecNode, self._convert_to_agentspec(event.step))
                current_agentspec_span.add_event(
                    AgentSpecNodeExecutionEnd(
                        id=event.event_id,
                        name=event_name,
                        node=agentspec_node,
                        outputs={
                            output_name: output_value
                            for output_name, output_value in event.step_result.outputs.items()
                        },
                        branch_selected=event.step_result.branch_name,
                    )
                )
                current_agentspec_span.end()
            case FlowExecutionStartedEvent():
                # Flow execution starts. Create the new agent spec span, start it, add the event
                agentspec_flow = cast(
                    AgentSpecFlow, self._convert_to_agentspec(event.conversational_component)
                )
                current_agentspec_span = AgentSpecFlowExecutionSpan(
                    id=current_span.span_id,
                    name=current_span_name,
                    flow=agentspec_flow,
                )
                self.agentspec_spans_registry[current_span.span_id] = current_agentspec_span
                current_agentspec_span.start()
                current_agentspec_span.add_event(
                    AgentSpecFlowExecutionStart(
                        id=event.event_id,
                        name=event_name,
                        flow=agentspec_flow,
                        inputs={},
                    )
                )
            case FlowExecutionFinishedEvent():
                # Flow execution ends. Add the event to the agent spec span and close the span
                if not current_agentspec_span:
                    return
                agentspec_flow = cast(
                    AgentSpecFlow, self._convert_to_agentspec(event.conversational_component)
                )
                if isinstance(event.execution_status, FinishedStatus):
                    branch_selected = event.execution_status.complete_step_name
                    outputs = event.execution_status.output_values
                else:
                    branch_selected = ""
                    outputs = {}
                current_agentspec_span.add_event(
                    AgentSpecFlowExecutionEnd(
                        id=event.event_id,
                        name=event_name,
                        flow=agentspec_flow,
                        outputs=outputs,
                        branch_selected=branch_selected,
                    )
                )
                current_agentspec_span.end()
            case AgentExecutionStartedEvent():
                # Agent execution starts. Create the new agent spec span, start it, add the event
                agentspec_agent = cast(
                    AgentSpecAgent, self._convert_to_agentspec(event.conversational_component)
                )
                current_agentspec_span = AgentSpecAgentExecutionSpan(
                    id=current_span.span_id,
                    name=current_span_name,
                    agent=agentspec_agent,
                )
                self.agentspec_spans_registry[current_span.span_id] = current_agentspec_span
                current_agentspec_span.start()
                current_agentspec_span.add_event(
                    AgentSpecAgentExecutionStart(
                        id=event.event_id,
                        name=event_name,
                        agent=agentspec_agent,
                        inputs={},
                    )
                )
            case AgentExecutionFinishedEvent():
                # Agent execution ends. Add the event to the agent spec span and close the span
                if not current_agentspec_span:
                    return
                agentspec_agent = cast(
                    AgentSpecAgent, self._convert_to_agentspec(event.conversational_component)
                )
                outputs = (
                    event.execution_status.output_values
                    if isinstance(event.execution_status, FinishedStatus)
                    else {}
                )
                current_agentspec_span.add_event(
                    AgentSpecAgentExecutionEnd(
                        id=event.event_id,
                        name=event_name,
                        agent=agentspec_agent,
                        outputs=outputs,
                    )
                )
                current_agentspec_span.end()
            case ExceptionRaisedEvent():
                if not current_agentspec_span:
                    return
                current_agentspec_span.add_event(
                    AgentSpecExceptionRaised(
                        id=event.event_id,
                        name=event_name,
                        exception_type=event.exception.__class__.__name__,
                        exception_message=stringify(event.exception),
                        exception_stacktrace=str(event.exception.__traceback__),
                    )
                )
