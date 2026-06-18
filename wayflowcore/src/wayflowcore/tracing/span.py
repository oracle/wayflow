# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import sys
import time
import uuid
import warnings
from abc import ABC, abstractmethod
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import TracebackType
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, cast

from typing_extensions import Self

from wayflowcore._utils.dataclass_utils import _required_attribute
from wayflowcore.conversation import Conversation
from wayflowcore.events.event import _PII_TEXT_MASK, Event
from wayflowcore.events.eventlistener import (
    EventListener,
    _record_exception,
    _register_event_listeners,
    get_event_listeners,
    record_event,
)
from wayflowcore.messagelist import Message, MessageList
from wayflowcore.serialization import serialize_to_dict
from wayflowcore.steps.step import Step, StepResult
from wayflowcore.tools.tools import Tool, ToolRequest, ToolResult

if TYPE_CHECKING:
    from wayflowcore.agent import Agent
    from wayflowcore.contextproviders import ContextProvider
    from wayflowcore.conversationalcomponent import ConversationalComponent
    from wayflowcore.executors.executionstatus import ExecutionStatus
    from wayflowcore.flow import Flow
    from wayflowcore.models import LlmCompletion, LlmModel, Prompt
    from wayflowcore.tracing.spanprocessor import SpanProcessor
    from wayflowcore.tracing.trace import Trace


_ACTIVE_SPAN_STACK: ContextVar[List["Span"]] = ContextVar("_ACTIVE_SPAN_STACK", default=[])

# setting it will ensure it's seen by `contextvars.copy_context()`
# because this doesn't use values with default that have not been passed
# this call is used in async <-> sync transitions to ensure propagation of
# context variables updates
_ACTIVE_SPAN_STACK.set([])


def _append_span_to_active_stack(span: "Span") -> None:
    span_stack = get_active_span_stack(return_copy=True)
    span_stack.append(span)
    _ACTIVE_SPAN_STACK.set(span_stack)


def _pop_span_from_active_stack() -> None:
    span_stack = get_active_span_stack(return_copy=True)
    span_stack.pop(-1)
    _ACTIVE_SPAN_STACK.set(span_stack)


def get_active_span_stack(return_copy: bool = True) -> List["Span"]:
    """
    Retrieve the stack of active spans in this context.

    Returns
    -------
        The stack of active spans in this context
    """
    from copy import copy

    span_stack = _ACTIVE_SPAN_STACK.get()
    return copy(span_stack) if return_copy else span_stack


def get_current_span() -> Optional["Span"]:
    """
    Retrieve the currently active span in this context.

    Returns
    -------
        The active span in this context
    """
    span_stack = get_active_span_stack(return_copy=False)
    if len(span_stack) > 0:
        return span_stack[-1]
    return None


class _AddEventToSpanEventListener(EventListener):
    """Event listener used to add the event being recorded to the current span"""

    def __call__(self, event: Event) -> None:
        current_span = get_current_span()
        if current_span:
            current_span._add_event(event)


# Whenever we ask for a Span, from now on we will have the listener that adds events to spans active and running
if not any(
    isinstance(event_listener, _AddEventToSpanEventListener)
    for event_listener in get_event_listeners()
):
    _register_event_listeners([_AddEventToSpanEventListener()])


@dataclass
class Span(ABC):
    """A Span represents a single operation within a Trace."""

    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """A unique identifier for the span"""
    name: Optional[str] = None
    """The name of the span"""
    start_time: Optional[int] = None
    """The timestamp of when the span was started"""
    end_time: Optional[int] = None
    """The timestamp of when the span was closed"""
    events: List[Event] = field(default_factory=list)
    """The list of events recorded in the scope of this span"""
    _parent_span: Optional["Span"] = None
    _end_event_was_triggered: bool = False
    _span_was_appended_to_active_stack: bool = False
    _started_span_processors: List["SpanProcessor"] = field(default_factory=list)

    @property
    def _trace(self) -> Optional["Trace"]:
        """The Trace where this Span is being stored"""
        from wayflowcore.tracing.trace import get_trace

        return get_trace()

    @property
    def _span_processors(self) -> List["SpanProcessor"]:
        """The list of SpanProcessors to which this Span should be forwarded"""
        return self._trace.span_processors if self._trace else []

    def _record_start_span_event(self) -> None:
        record_event(self._create_start_span_event())

    @abstractmethod
    def _create_start_span_event(self) -> "Event":
        # The spans are supposed to override this by returning an instance of a StartSpanEvent subclass
        pass

    def _record_end_span_event(self, event: "Event") -> None:
        """
        Record the given event as the closing event for this Span.

        Note that this method is supposed to be called only once per Span instance.

        Parameters
        ----------
        event:
            The end event for this span
        """
        if self._end_event_was_triggered:
            raise RuntimeError("Cannot record two end span events for the same span")
        record_event(event)
        self._end_event_was_triggered = True

    @abstractmethod
    def record_end_span_event(self, *args: Any, **kwargs: Any) -> None:
        """
        Record the given event as the closing event for this Span.

        Note that this method is supposed to be called only once per Span instance.
        """
        # The spans are supposed to override this by adding their special end span event

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.end(exception=(cast(Exception, exc_value) if exc_value is not None else None))

    def start(self) -> None:
        """
        Start the span.

        This includes calling the ``on_start`` method of the active SpanProcessors,
        and recording the StartSpanEvent.
        """
        try:
            self._parent_span = get_current_span()
            self.start_time = time.time_ns()
            for span_processor in self._span_processors:
                span_processor.on_start(self)
                # We remember which span processors were started, so that we call on_end on them only
                # when we exit, e.g., because of an exception happening
                self._started_span_processors.append(span_processor)
            _append_span_to_active_stack(self)
            self._span_was_appended_to_active_stack = True
            self._record_start_span_event()
        except Exception as e:
            # If anything happens during the recording of the start span,
            # we still have to do the work needed to exit the context
            # including the span_processors.on_end call and removing the span from the active stack
            self.__exit__(*sys.exc_info())
            raise e

    def end(self, exception: Optional[Exception] = None) -> None:
        """
        End the span.

        This includes calling the ``on_end`` method of the active SpanProcessors,
        and recording the StartSpanEvent.

        If the ``record_end_span_event`` method was not called for this span, it is
        called automatically with a default EndSpanEvent, and a warning is raised.

        Parameters
        ----------
        exception:
            The exception that was raised during the execution of the span.
        """
        try:
            from wayflowcore.events.event import EndSpanEvent

            if exception is not None:
                _record_exception(exception)

            exceptions_list: List[Exception] = []
            self.end_time = time.time_ns()
            # We call on_end only on the span_processors that were successfully started
            for span_processor in self._started_span_processors:
                # We catch the exceptions that are raised to ensure we call on_end on all
                # the span processors on which on_start was called
                try:
                    span_processor.on_end(self)
                except Exception as e:
                    exceptions_list.append(e)
            if not self._end_event_was_triggered:
                if exception is None:
                    warnings.warn(
                        "End span event was not manually recorded, a default one will be triggered. "
                        "We recommend to record an end event manually."
                    )
                self._record_end_span_event(event=EndSpanEvent(span=self, timestamp=self.end_time))
            # If we caught exceptions before, we raise one of them here (the first we caught)
            if len(exceptions_list) > 0:
                raise exceptions_list[0]
        finally:
            # Whatever happens, we have to pop the span if it is on the active spans stack
            if self._span_was_appended_to_active_stack:
                _pop_span_from_active_stack()

    def _add_event(self, event: Event) -> None:
        """Add an event to the list of events triggered in this span."""
        self.events.append(event)

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        """
        Return a serialized version of the span's information to be used for tracing.

        Parameters
        ----------
        mask_sensitive_information
            Whether to mask potentially sensitive information from the span and its events

        Returns
        -------
            A dictionary containing the serialized information of this span
        """
        return {
            "trace_id": self._trace.trace_id if self._trace else None,
            "trace_name": self._trace.name if self._trace else None,
            "span_id": self.span_id,
            "parent_id": self._parent_span.span_id if self._parent_span else None,
            "name": self.name or self.__class__.__name__,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "span_type": self.__class__.__name__,
            "events": [
                event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)
                for event in self.events
            ],
        }


@dataclass
class LlmGenerationSpan(Span):
    """Span for the generation of an LLM"""

    llm: "LlmModel" = field(default_factory=_required_attribute("llm", "LlmModel"))
    """The LLM model that is generating"""
    prompt: "Prompt" = field(default_factory=_required_attribute("prompt", "Prompt"))
    """The prompt that was given to the LLM"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "llm.model_type": self.llm.__class__.__name__,
            "llm.model_id": self.llm.model_id,
            "llm.model_config": self.llm.config,
            "llm.generation_config": (
                self.llm.generation_config.to_dict()
                if self.llm.generation_config is not None
                else None
            ),
        }

    def _create_start_span_event(self) -> "Event":
        from wayflowcore.events.event import LlmGenerationRequestEvent

        return LlmGenerationRequestEvent(span=self, llm=self.llm, prompt=self.prompt)

    def record_end_span_event(
        self,
        completion: "LlmCompletion",
    ) -> None:
        """
        Record a LlmGenerationResponseEvent with the given information
        as the closing event for this Span.

        Note that this method is supposed to be called only once per Span instance.

        Parameters
        ----------
        completion:
            The completion returned by the LLM
        """
        from wayflowcore.events.event import LlmGenerationResponseEvent

        self._record_end_span_event(
            event=LlmGenerationResponseEvent(
                span=self,
                llm=self.llm,
                completion=completion,
            )
        )


@dataclass
class ConversationalComponentExecutionSpan(Span):
    """Span for the execution of a ConversationalComponent"""

    conversational_component: "ConversationalComponent" = field(
        default_factory=_required_attribute("conversational_component", "ConversationalComponent")
    )
    """The ConversationalComponent being executed"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "conversational_component.name": self.conversational_component.name or None,
            "conversational_component.description": self.conversational_component.description,
            # Json schema might contain sensitive information in default values
            "conversational_component.input_descriptors": [
                input_.to_json_schema() if not mask_sensitive_information else input_.name
                for input_ in self.conversational_component.input_descriptors
            ],
            "conversational_component.output_descriptors": [
                output.to_json_schema() if not mask_sensitive_information else output.name
                for output in self.conversational_component.output_descriptors
            ],
        }

    def _create_start_span_event(self) -> "Event":
        from wayflowcore.events.event import ConversationalComponentExecutionStartedEvent

        return ConversationalComponentExecutionStartedEvent(
            span=self,
            conversational_component=self.conversational_component,
        )

    def record_end_span_event(
        self,
        execution_status: "ExecutionStatus",
    ) -> None:
        """
        Record a ConversationalComponentExecutionFinishedEvent with the given information
        as the closing event for this Span.

        Note that this method is supposed to be called only once per Span instance.

        Parameters
        ----------
        execution_status:
            Indicates the status of the conversation (finished, yielding, etc.)
        """
        from wayflowcore.events.event import ConversationalComponentExecutionFinishedEvent

        self._record_end_span_event(
            event=ConversationalComponentExecutionFinishedEvent(
                span=self,
                conversational_component=self.conversational_component,
                execution_status=execution_status,
            )
        )


@dataclass
class AgentExecutionSpan(ConversationalComponentExecutionSpan):
    """Span for the execution of an Agent"""

    conversational_component: "Agent" = field(
        default_factory=_required_attribute("conversational_component", "Agent")
    )
    """The Agent being executed"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        agent = self.conversational_component
        conversational_component_id = agent.agent_id
        conversational_component_attributes = {
            "tools": [tool.name for tool in agent.tools],
            "flows": [flow.id for flow in agent.flows],
            "agents": [agent.id for agent in agent.agents],
            "context_providers": [cp.name for cp in agent.context_providers],
            "custom_instruction": (
                agent.custom_instruction if not mask_sensitive_information else _PII_TEXT_MASK
            ),
            "max_iterations": agent.max_iterations,
            "can_finish_conversation": agent.can_finish_conversation,
            "initial_message": (
                agent.initial_message if not mask_sensitive_information else _PII_TEXT_MASK
            ),
            "caller_input_mode": agent.caller_input_mode.value,
        }
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "conversational_component.id": conversational_component_id,
            "conversational_component.attributes": conversational_component_attributes,
        }

    def _create_start_span_event(self) -> "Event":
        from wayflowcore.events.event import AgentExecutionStartedEvent

        return AgentExecutionStartedEvent(
            span=self,
            conversational_component=self.conversational_component,
        )

    def record_end_span_event(
        self,
        execution_status: "ExecutionStatus",
    ) -> None:
        """
        Record an AgentExecutionFinishedEvent with the given information
        as the closing event for this Span.

        Note that this method is supposed to be called only once per Span instance.

        Parameters
        ----------
        execution_status:
            Indicates the status of the conversation (finished, yielding, etc.)
        """
        from wayflowcore.events.event import AgentExecutionFinishedEvent

        self._record_end_span_event(
            event=AgentExecutionFinishedEvent(
                span=self,
                conversational_component=self.conversational_component,
                execution_status=execution_status,
            )
        )


@dataclass
class FlowExecutionSpan(ConversationalComponentExecutionSpan):
    """Span for the execution of a Flow"""

    conversational_component: "Flow" = field(
        default_factory=_required_attribute("conversational_component", "Flow")
    )
    """The Flow being executed"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        flow = self.conversational_component
        conversational_component_id = flow.flow_id
        conversational_component_attributes = {
            "steps": [step_name for step_name in flow.steps],
            "context_providers": [cp.name for cp in flow.context_providers],
            "variables": [variable.name for variable in flow.variables],
            "control_flow_edges": [
                [
                    edge.source_step.name,
                    edge.source_branch,
                    edge.destination_step.name if edge.destination_step else None,
                ]
                for edge in flow.control_flow_edges
            ],
            "data_flow_edges": [
                (
                    edge.source_step.name,
                    edge.source_output,
                    edge.destination_step.name,
                    edge.destination_input,
                )
                for edge in flow.data_flow_edges
            ],
        }
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "conversational_component.id": conversational_component_id,
            "conversational_component.attributes": conversational_component_attributes,
        }

    def _create_start_span_event(self) -> "Event":
        from wayflowcore.events.event import FlowExecutionStartedEvent

        return FlowExecutionStartedEvent(
            span=self,
            conversational_component=self.conversational_component,
        )

    def record_end_span_event(
        self,
        execution_status: "ExecutionStatus",
    ) -> None:
        """
        Record an FlowExecutionFinishedEvent with the given information
        as the closing event for this Span.

        Note that this method is supposed to be called only once per Span instance.

        Parameters
        ----------
        execution_status:
            Indicates the status of the conversation (finished, yielding, etc.)
        """
        from wayflowcore.events.event import FlowExecutionFinishedEvent

        self._record_end_span_event(
            event=FlowExecutionFinishedEvent(
                span=self,
                conversational_component=self.conversational_component,
                execution_status=execution_status,
            )
        )


@dataclass
class ConversationSpan(Span):
    conversation: Conversation = field(
        default_factory=_required_attribute("conversation", Conversation)
    )
    """The conversation being executed"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "conversation.id": self.conversation.conversation_id,
            "conversation.name": self.conversation.name,
            "conversational_component.type": self.conversation.component.__class__.__name__,
            "conversational_component.id": self.conversation.component.id,
            "conversation.inputs": (
                self.conversation.inputs if not mask_sensitive_information else _PII_TEXT_MASK
            ),
        }

    def _create_start_span_event(self) -> "Event":
        from wayflowcore.events.event import ConversationExecutionStartedEvent

        return ConversationExecutionStartedEvent(
            span=self,
            conversation=self.conversation,
        )

    def record_end_span_event(self, execution_status: "ExecutionStatus") -> None:
        from wayflowcore.events.event import ConversationExecutionFinishedEvent

        self._record_end_span_event(
            event=ConversationExecutionFinishedEvent(
                span=self,
                conversation=self.conversation,
                execution_status=execution_status,
            )
        )


@dataclass
class ToolExecutionSpan(Span):
    tool: Tool = field(default_factory=_required_attribute("tool", Tool))
    """The tool being executed"""
    tool_request: ToolRequest = field(
        default_factory=_required_attribute("tool_request", ToolRequest)
    )
    """The tool request (ID and arguments) with which the tool is being executed"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "tool.name": self.tool.name,
            "tool.description": self.tool.description,
            "tool.type": self.tool.__class__.__name__,
            "tool.input_descriptors": [
                input_.to_json_schema() if not mask_sensitive_information else input_.name
                for input_ in self.tool.input_descriptors
            ],
            "tool.output_descriptors": [
                output.to_json_schema() if not mask_sensitive_information else output.name
                for output in self.tool.output_descriptors
            ],
        }

    def _create_start_span_event(self) -> "Event":
        from wayflowcore.events.event import ToolExecutionStartEvent

        return ToolExecutionStartEvent(
            span=self,
            tool=self.tool,
            tool_request=self.tool_request,
        )

    def record_end_span_event(self, output: Any) -> None:
        from wayflowcore.events.event import ToolExecutionResultEvent

        self._record_end_span_event(
            event=ToolExecutionResultEvent(
                span=self,
                tool=self.tool,
                tool_result=ToolResult(
                    content=output, tool_request_id=self.tool_request.tool_request_id
                ),
            )
        )


@dataclass
class StepInvocationSpan(Span):
    step: Step = field(default_factory=_required_attribute("step", Step))
    """The step being executed"""
    inputs: Dict[str, Any] = field(default_factory=_required_attribute("inputs", Dict[str, Any]))
    """The inputs with which the step is being executed"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "step.name": self.step.name,
            "step.static_configuration": (
                self.step._step_static_configuration
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
            "step.input_mapping": self.step.input_mapping,
            "step.output_mapping": self.step.output_mapping,
            "step.input_descriptors": [
                input_.to_json_schema() if not mask_sensitive_information else input_.name
                for input_ in self.step.input_descriptors
            ],
            "step.output_descriptors": [
                output.to_json_schema() if not mask_sensitive_information else output.name
                for output in self.step.output_descriptors
            ],
        }

    def _create_start_span_event(self) -> "Event":
        from wayflowcore.events.event import StepInvocationStartEvent

        return StepInvocationStartEvent(
            span=self,
            step=self.step,
            inputs=self.inputs,
        )

    def record_end_span_event(self, step_result: StepResult) -> None:
        from wayflowcore.events.event import StepInvocationResultEvent

        self._record_end_span_event(
            event=StepInvocationResultEvent(
                span=self,
                step=self.step,
                step_result=step_result,
            )
        )


@dataclass
class ContextProviderExecutionSpan(Span):
    context_provider: "ContextProvider" = field(
        default_factory=_required_attribute("context_provider", "ContextProvider")
    )
    """The context provider being executed"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "context_provider.name": self.context_provider.name,
            "context_provider.type": self.context_provider.__class__.__name__,
        }

    def _create_start_span_event(self) -> "Event":
        from wayflowcore.events.event import ContextProviderExecutionRequestEvent

        return ContextProviderExecutionRequestEvent(
            span=self,
            context_provider=self.context_provider,
        )

    def record_end_span_event(self, output: Any) -> None:
        from wayflowcore.events.event import ContextProviderExecutionResultEvent

        self._record_end_span_event(
            event=ContextProviderExecutionResultEvent(
                span=self,
                context_provider=self.context_provider,
                output=output,
            )
        )


@dataclass
class ConversationMessageStreamSpan(Span):
    message_list: MessageList = field(
        default_factory=_required_attribute("message_list", MessageList)
    )
    """The message list where a message is streamed"""
    initial_message: Message = field(
        default_factory=_required_attribute("initial_message", Message)
    )
    """The first chunk streamed, with the role and initial content of the message being streamed"""

    def to_tracing_info(self, mask_sensitive_information: bool = True) -> Dict[str, Any]:
        return {
            **super().to_tracing_info(mask_sensitive_information=mask_sensitive_information),
            "messages.id": self.message_list.id,
            "initial_message": (
                serialize_to_dict(self.initial_message)
                if not mask_sensitive_information
                else _PII_TEXT_MASK
            ),
        }

    def _create_start_span_event(self) -> "Event":
        from wayflowcore.events.event import ConversationMessageStreamStartedEvent

        return ConversationMessageStreamStartedEvent(
            message=self.initial_message,
        )

    def record_end_span_event(self, message: Any) -> None:
        from wayflowcore.events.event import ConversationMessageStreamEndedEvent

        self._record_end_span_event(
            event=ConversationMessageStreamEndedEvent(
                message=message,
            )
        )
