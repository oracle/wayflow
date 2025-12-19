# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import time
import uuid
from abc import ABC
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Optional, TypeVar, Union

from wayflowcore._utils.dataclass_utils import _required_attribute
from wayflowcore._utils.formatting import stringify
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.serialization.context import SerializationContext
from wayflowcore.serialization.serializer import serialize_any_to_dict, serialize_to_dict
from wayflowcore.steps.step import Step, StepResult
from wayflowcore.tools.tools import Tool, ToolRequest, ToolResult

if TYPE_CHECKING:
    from wayflowcore.contextproviders import ContextProvider
    from wayflowcore.conversation import Conversation
    from wayflowcore.executors._agentexecutor import AgentConversationExecutionState
    from wayflowcore.executors._flowexecutor import FlowConversationExecutionState
    from wayflowcore.executors.executionstatus import ExecutionStatus
    from wayflowcore.messagelist import Message, MessageList
    from wayflowcore.models import LlmCompletion, LlmModel, Prompt

    # autoflake keeps removing the imports of the derived Span classes, causing mypy to fail
    from wayflowcore.tracing.span import (  # noqa
        ContextProviderExecutionSpan,
        ConversationalComponentExecutionSpan,
        ConversationSpan,
        LlmGenerationSpan,
        Span,
        StepInvocationSpan,
        ToolExecutionSpan,
    )

_PII_TEXT_MASK = "** MASKED **"
SpanType = TypeVar("SpanType", bound="Span")


def _get_current_span_factory() -> Optional["Span"]:
    from wayflowcore.tracing.span import get_current_span

    return get_current_span()


def _serialize_tool_request(
    tool_request: Optional[ToolRequest], mask_sensitive_information: bool
) -> Dict[str, Any]:
    if tool_request is None:
        return {}
    # We build the serialization manually instead of calling `serialize_to_dict`
    # to avoid that adding new fields with sensitive information added to the tool request
    # end up unmasked in the serialization by mistake
    serialization: Dict[str, Any] = {
        "name": tool_request.name,
        "tool_request_id": tool_request.tool_request_id,
    }
    if not mask_sensitive_information:
        serialization["args"] = tool_request.args
    return serialization


@dataclass(frozen=True)
class Event(ABC):
    """Base Event class. It contains information relevant to all events."""

    name: Optional[str] = None
    """The optional name of the event"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """A unique identifier for the event"""
    timestamp: int = field(default_factory=time.time_ns)
    """The timestamp of when the event occurred"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        """
        Return a serialized version of the event's information to be used for tracing.

        Parameters
        ----------
        mask_sensitive_information
            Whether to mask potentially sensitive information from the span and its events

        Returns
        -------
            A dictionary containing the serialized information of this event
        """
        return {
            "event_id": self.event_id,
            "name": self.name or self.__class__.__name__,
            "timestamp": self.timestamp,
            "event_type": self.__class__.__name__,
        }


@dataclass(frozen=True)
class StartSpanEvent(Generic[SpanType], Event):
    """
    This event is recorded at the beginning of a span.
    """

    span: Optional["Span"] = field(default_factory=_get_current_span_factory)
    """The span that is starting"""


@dataclass(frozen=True)
class EndSpanEvent(Generic[SpanType], Event):
    """
    This event is recorded at the end of a span.
    """

    span: Optional["Span"] = field(default_factory=_get_current_span_factory)
    """The span that is ending"""


@dataclass(frozen=True)
class LlmGenerationRequestEvent(StartSpanEvent["LlmGenerationSpan"]):
    """
    This event is recorded when the llm receives a generation request.
    """

    llm: "LlmModel" = field(default_factory=_required_attribute("llm", "LlmModel"))
    """The model that receives the generation request"""
    prompt: "Prompt" = field(default_factory=_required_attribute("prompt", "Prompt"))
    """The prompt for the generation request"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "prompt": (
                serialize_to_dict(self.prompt) if not mask_sensitive_information else _PII_TEXT_MASK
            ),
        }


@dataclass(frozen=True)
class LlmGenerationResponseEvent(EndSpanEvent["LlmGenerationSpan"]):
    """
    This event is recorded when the llm generates a response.
    """

    llm: "LlmModel" = field(default_factory=_required_attribute("llm", "LlmModel"))
    """The model that was used for generating the response"""
    completion: "LlmCompletion" = field(
        default_factory=_required_attribute("completion", "LlmCompletion")
    )
    """The completion generated by the llm model"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "completion": (
                serialize_to_dict(self.completion)
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
        }


@dataclass(frozen=True)
class ConversationalComponentExecutionStartedEvent(
    StartSpanEvent["ConversationalComponentExecutionSpan"]
):
    """
    This event is recorded when the agent/flow execution has started.
    """

    conversational_component: "ConversationalComponent" = field(
        default_factory=_required_attribute("conversational_component", "ConversationalComponent")
    )
    """Agent/flow that started the execution of the conversation"""


@dataclass(frozen=True)
class AgentExecutionStartedEvent(ConversationalComponentExecutionStartedEvent):
    pass


@dataclass(frozen=True)
class FlowExecutionStartedEvent(ConversationalComponentExecutionStartedEvent):
    pass


@dataclass(frozen=True)
class ConversationalComponentExecutionFinishedEvent(
    EndSpanEvent["ConversationalComponentExecutionSpan"]
):
    """
    This event is recorded when the agent/flow execution has ended.
    """

    conversational_component: "ConversationalComponent" = field(
        default_factory=_required_attribute("conversational_component", "ConversationalComponent")
    )
    """Agent/flow that started the execution of the conversation"""
    execution_status: "ExecutionStatus" = field(
        default_factory=_required_attribute("execution_status", "ExecutionStatus")
    )
    """Indicates the status of the conversation (finished, yielding, etc.)"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "execution_status": self.execution_status.__class__.__name__,
        }


@dataclass(frozen=True)
class FlowExecutionFinishedEvent(ConversationalComponentExecutionFinishedEvent):
    pass


@dataclass(frozen=True)
class AgentExecutionFinishedEvent(ConversationalComponentExecutionFinishedEvent):
    pass


@dataclass(frozen=True)
class ConversationCreatedEvent(Event):
    """
    This event is recorded whenever a new conversation with an agent or a flow was created.
    """

    conversational_component: "ConversationalComponent" = field(
        default_factory=_required_attribute("conversational_component", "ConversationalComponent")
    )
    """Agent/flow from which the conversation was created"""
    inputs: Optional[Dict[str, Any]] = field(
        default_factory=_required_attribute("inputs", Optional[Dict[str, Any]])
    )
    """A dictionary of inputs where the keys are the input names and the values
    are the actual inputs of the conversation."""
    messages: Optional[Union["MessageList", List["Message"]]] = field(
        default_factory=_required_attribute(
            "messages", Optional[Union["MessageList", List["Message"]]]
        )
    )
    """List of messages to populate the conversation"""
    conversation_id: Optional[str] = field(
        default_factory=_required_attribute("conversation_id", Optional[str])
    )
    """Unique id of the conversation"""
    nesting_level: Optional[int] = field(
        default_factory=_required_attribute("nesting_level", Optional[int])
    )
    """The level of nested sub-conversations or tasks within the main conversation."""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        from wayflowcore.messagelist import MessageList

        messages = (
            self.messages.get_messages()
            if isinstance(self.messages, MessageList)
            else self.messages
        )
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "conversational_component.type": self.conversational_component.__class__.__name__,
            "conversational_component.id": self.conversational_component.id,
            "inputs": (
                {key: stringify(value) for key, value in (self.inputs or {}).items()}
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "messages": (
                [serialize_to_dict(message) for message in (messages or [])]
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "conversation_id": self.conversation_id,
            "nesting_level": self.nesting_level,
        }


@dataclass(frozen=True)
class ConversationMessageAddedEvent(Event):
    """
    This event is recorded whenever a new message was added to the conversation.
    """

    message: "Message" = field(default_factory=_required_attribute("message", "Message"))
    """The message that is being appended to the conversation"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "message": (
                serialize_to_dict(self.message)
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
        }


@dataclass(frozen=True)
class ToolExecutionStartEvent(StartSpanEvent["ToolExecutionSpan"]):
    """
    This event is recorded whenever a tool is executed.
    """

    tool: Tool = field(default_factory=_required_attribute("tool", Tool))
    """Tool that triggered this event"""
    tool_request: ToolRequest = field(
        default_factory=_required_attribute("tool_request", ToolRequest)
    )
    """ToolRequest object containing the id of the tool request made as well as the tool call's inputs"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "tool_request.inputs": (
                {key: stringify(value) for key, value in self.tool_request.args.items()}
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "tool_request.id": self.tool_request.tool_request_id,
        }


@dataclass(frozen=True)
class ToolExecutionResultEvent(EndSpanEvent["ToolExecutionSpan"]):
    """
    This event is recorded whenever a tool has finished execution.
    """

    tool: Tool = field(default_factory=_required_attribute("tool", Tool))
    """Tool that triggered this event"""
    tool_result: ToolResult = field(default_factory=_required_attribute("tool_result", ToolResult))
    """ToolResult object containing the id of the tool request made and the tool call's output """

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "tool_result.output": (
                stringify(self.tool_result.content)
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "tool_result.tool_request_id": self.tool_result.tool_request_id,
        }


@dataclass(frozen=True)
class StepInvocationStartEvent(StartSpanEvent["StepInvocationSpan"]):
    """
    This event is recorded whenever a step is invoked.
    """

    step: Step = field(default_factory=_required_attribute("step", Step))
    """Step that triggered the event"""
    inputs: Dict[str, Any] = field(default_factory=_required_attribute("inputs", Dict[str, Any]))
    """Inputs to the step invocation"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "inputs": (
                {key: stringify(value) for key, value in self.inputs.items()}
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
        }


@dataclass(frozen=True)
class StepInvocationResultEvent(EndSpanEvent["StepInvocationSpan"]):
    """
    This event is recorded whenever a step invocation has finished.
    """

    step: Step = field(default_factory=_required_attribute("step", Step))
    """Step that triggered the event"""
    step_result: StepResult = field(default_factory=_required_attribute("step_result", StepResult))
    """Result of the step invocation"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:

        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "step_result.outputs": (
                {key: stringify(value) for key, value in self.step_result.outputs.items()}
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "step_result.branch_name": self.step_result.branch_name,
            "step_result.step_type": self.step_result.step_type,
        }


@dataclass(frozen=True)
class ContextProviderExecutionRequestEvent(StartSpanEvent["ContextProviderExecutionSpan"]):
    """
    This event is recorded whenever a context provider is called.
    """

    context_provider: "ContextProvider" = field(
        default_factory=_required_attribute("context_provider", "ContextProvider")
    )
    """Used to pass contextual information to assistants"""


@dataclass(frozen=True)
class ContextProviderExecutionResultEvent(EndSpanEvent["ContextProviderExecutionSpan"]):
    """
    This event is recorded whenever a context provider has returned a result.
    """

    context_provider: "ContextProvider" = field(
        default_factory=_required_attribute("context_provider", "ContextProvider")
    )
    """Used to pass contextual information to assistants"""
    output: Any = field(default_factory=_required_attribute("output", Any))
    """Result of the context provider call"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "output": stringify(self.output) if not mask_sensitive_information else _PII_TEXT_MASK,
        }


@dataclass(frozen=True)
class FlowExecutionIterationStartedEvent(Event):
    """
    This event is recorded whenever an iteration of a flow has started executing.
    """

    execution_state: "FlowConversationExecutionState" = field(
        default_factory=_required_attribute("execution_state", "FlowConversationExecutionState")
    )
    """State of a flow (doesn't contain messages)"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        serialization_context = SerializationContext(root=self.execution_state)
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "execution_state.current_step_name": self.execution_state.current_step_name,
            "execution_state.input_output_key_values": (
                serialize_any_to_dict(
                    self.execution_state.input_output_key_values, serialization_context
                )
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "execution_state.variable_store": (
                serialize_any_to_dict(self.execution_state.variable_store, serialization_context)
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "execution_state.step_history": self.execution_state.step_history,
            "execution_state.nesting_level": self.execution_state.nesting_level,
            "execution_state.internal_context_key_values": (
                serialize_any_to_dict(
                    self.execution_state.internal_context_key_values, serialization_context
                )
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
        }


@dataclass(frozen=True)
class FlowExecutionIterationFinishedEvent(Event):
    """
    This event is recorded whenever an iteration of a flow has finished executing.
    """

    execution_state: "FlowConversationExecutionState" = field(
        default_factory=_required_attribute("execution_state", "FlowConversationExecutionState")
    )
    """State of a flow (doesn't contain messages)"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        serialization_context = SerializationContext(root=self.execution_state)
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "execution_state.current_step_name": self.execution_state.current_step_name,
            "execution_state.input_output_key_values": (
                serialize_any_to_dict(
                    self.execution_state.input_output_key_values, serialization_context
                )
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "execution_state.variable_store": (
                serialize_any_to_dict(self.execution_state.variable_store, serialization_context)
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "execution_state.step_history": self.execution_state.step_history,
            "execution_state.nesting_level": self.execution_state.nesting_level,
            "execution_state.internal_context_key_values": (
                serialize_any_to_dict(
                    self.execution_state.internal_context_key_values, serialization_context
                )
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
        }


@dataclass(frozen=True)
class AgentExecutionIterationStartedEvent(Event):
    """
    This event is recorded whenever an iteration of an agent has started executing.
    """

    execution_state: "AgentConversationExecutionState" = field(
        default_factory=_required_attribute("execution_state", "AgentConversationExecutionState")
    )
    """State of an agent (doesn't contain messages)"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "execution_state.memory": (
                (
                    serialize_to_dict(self.execution_state.memory)
                    if self.execution_state.memory
                    else {}
                )
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "execution_state.plan": (
                stringify(self.execution_state.plan)
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "execution_state.tool_call_queue": [
                _serialize_tool_request(tool_request, mask_sensitive_information)
                for tool_request in self.execution_state.tool_call_queue
            ],
            "execution_state.current_tool_request": _serialize_tool_request(
                self.execution_state.current_tool_request, mask_sensitive_information
            ),
            "execution_state.current_flow_conversation": (
                (
                    serialize_to_dict(self.execution_state.current_flow_conversation)
                    if self.execution_state.current_flow_conversation
                    else None
                )
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "execution_state.has_confirmed_conversation_exit": self.execution_state.has_confirmed_conversation_exit,
            "execution_state.current_retrieved_tools": [
                tool.name for tool in self.execution_state.current_retrieved_tools or []
            ],
            "execution_state.curr_iter": self.execution_state.curr_iter,
        }


@dataclass(frozen=True)
class AgentExecutionIterationFinishedEvent(Event):
    """
    This event is recorded whenever an iteration of an agent has finished executing.
    """

    execution_state: "AgentConversationExecutionState" = field(
        default_factory=_required_attribute("execution_state", "AgentConversationExecutionState")
    )
    """State of an agent (doesn't contain messages)"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "execution_state.memory": (
                (
                    serialize_to_dict(self.execution_state.memory)
                    if self.execution_state.memory
                    else {}
                )
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "execution_state.plan": (
                stringify(self.execution_state.plan)
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "execution_state.tool_call_queue": [
                _serialize_tool_request(tool_request, mask_sensitive_information)
                for tool_request in self.execution_state.tool_call_queue
            ],
            "execution_state.current_tool_request": _serialize_tool_request(
                self.execution_state.current_tool_request, mask_sensitive_information
            ),
            "execution_state.current_flow_conversation": (
                (
                    serialize_to_dict(self.execution_state.current_flow_conversation)
                    if self.execution_state.current_flow_conversation
                    else None
                )
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "execution_state.has_confirmed_conversation_exit": self.execution_state.has_confirmed_conversation_exit,
            "execution_state.current_retrieved_tools": [
                tool.name for tool in self.execution_state.current_retrieved_tools or []
            ],
            "execution_state.curr_iter": self.execution_state.curr_iter,
        }


@dataclass(frozen=True)
class ExceptionRaisedEvent(Event):
    """
    This event is recorded whenever an exception occurs.
    """

    exception: Exception = field(default_factory=_required_attribute("exception", Exception))
    """Exception that was thrown during execution"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "exception.type": self.exception.__class__.__name__,
            "exception.message": (
                stringify(self.exception) if not mask_sensitive_information else _PII_TEXT_MASK
            ),
            "exception.traceback": (
                self.exception.__traceback__ if not mask_sensitive_information else _PII_TEXT_MASK
            ),
        }


@dataclass(frozen=True)
class ConversationExecutionStartedEvent(StartSpanEvent["ConversationSpan"]):
    """
    This event is recorded whenever a conversation is started.
    """

    conversation: "Conversation" = field(
        default_factory=_required_attribute("conversation", "Conversation")
    )

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "conversation.id": self.conversation.conversation_id,
            "conversation.name": self.conversation.name,
        }


@dataclass(frozen=True)
class ConversationExecutionFinishedEvent(EndSpanEvent["ConversationSpan"]):
    """
    This event is recorded whenever a conversation is started.
    """

    conversation: "Conversation" = field(
        default_factory=_required_attribute("conversation", "Conversation")
    )
    execution_status: "ExecutionStatus" = field(
        default_factory=_required_attribute("execution_status", "ExecutionStatus")
    )

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "conversation.id": self.conversation.conversation_id,
            "conversation.name": self.conversation.name,
            "execution_status": self.execution_status.__class__.__name__,
        }
