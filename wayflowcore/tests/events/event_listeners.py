# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import List

from wayflowcore.events.event import (
    AgentExecutionFinishedEvent,
    AgentExecutionIterationFinishedEvent,
    AgentExecutionIterationStartedEvent,
    AgentExecutionStartedEvent,
    ContextProviderExecutionRequestEvent,
    ContextProviderExecutionResultEvent,
    ConversationalComponentExecutionFinishedEvent,
    ConversationalComponentExecutionStartedEvent,
    ConversationCreatedEvent,
    ConversationExecutionFinishedEvent,
    ConversationExecutionStartedEvent,
    ConversationMessageAddedEvent,
    ConversationMessageStreamChunkEvent,
    ConversationMessageStreamEndedEvent,
    ConversationMessageStreamStartedEvent,
    Event,
    ExceptionRaisedEvent,
    FlowExecutionFinishedEvent,
    FlowExecutionIterationFinishedEvent,
    FlowExecutionIterationStartedEvent,
    FlowExecutionStartedEvent,
    LlmGenerationRequestEvent,
    LlmGenerationResponseEvent,
    StepInvocationResultEvent,
    StepInvocationStartEvent,
    ToolExecutionResultEvent,
    ToolExecutionStartEvent,
)
from wayflowcore.events.eventlistener import EventListener


class AgentExecutionIterationFinishedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[AgentExecutionIterationFinishedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, AgentExecutionIterationFinishedEvent):
            self.triggered_events.append(event)


class AgentExecutionIterationStartedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[AgentExecutionIterationStartedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, AgentExecutionIterationStartedEvent):
            self.triggered_events.append(event)


class ContextProviderExecutionRequestEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[ContextProviderExecutionRequestEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ContextProviderExecutionRequestEvent):
            self.triggered_events.append(event)


class ContextProviderExecutionResultEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[ContextProviderExecutionResultEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ContextProviderExecutionResultEvent):
            self.triggered_events.append(event)


class ConversationCreatedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[ConversationCreatedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ConversationCreatedEvent):
            self.triggered_events.append(event)


class ConversationMessageAddedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[ConversationMessageAddedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ConversationMessageAddedEvent):
            self.triggered_events.append(event)


class ConversationMessageStreamChunkEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[ConversationMessageStreamChunkEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ConversationMessageStreamChunkEvent):
            self.triggered_events.append(event)


class ConversationMessageStreamStartedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[ConversationMessageStreamStartedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ConversationMessageStreamStartedEvent):
            self.triggered_events.append(event)


class ConversationMessageStreamEndedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[ConversationMessageStreamEndedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ConversationMessageStreamEndedEvent):
            self.triggered_events.append(event)


class ConversationalComponentExecutionFinishedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[ConversationalComponentExecutionFinishedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ConversationalComponentExecutionFinishedEvent):
            self.triggered_events.append(event)


class AgentExecutionFinishedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[AgentExecutionFinishedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, AgentExecutionFinishedEvent):
            self.triggered_events.append(event)


class FlowExecutionFinishedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[FlowExecutionFinishedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, FlowExecutionFinishedEvent):
            self.triggered_events.append(event)


class ConversationalComponentExecutionStartedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[ConversationalComponentExecutionStartedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ConversationalComponentExecutionStartedEvent):
            self.triggered_events.append(event)


class AgentExecutionStartedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[AgentExecutionStartedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, AgentExecutionStartedEvent):
            self.triggered_events.append(event)


class FlowExecutionStartedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[FlowExecutionStartedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, FlowExecutionStartedEvent):
            self.triggered_events.append(event)


class ExceptionRaisedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[ExceptionRaisedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ExceptionRaisedEvent):
            self.triggered_events.append(event)


class FlowExecutionIterationFinishedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[FlowExecutionIterationFinishedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, FlowExecutionIterationFinishedEvent):
            self.triggered_events.append(event)


class FlowExecutionIterationStartedEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[FlowExecutionIterationStartedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, FlowExecutionIterationStartedEvent):
            self.triggered_events.append(event)


class LlmGenerationRequestEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[LlmGenerationRequestEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, LlmGenerationRequestEvent):
            self.triggered_events.append(event)


class LlmGenerationResponseEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[LlmGenerationResponseEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, LlmGenerationResponseEvent):
            self.triggered_events.append(event)


class StepInvocationResultEventListener(EventListener):
    def __init__(self) -> None:
        self.triggered_events: List[StepInvocationResultEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, StepInvocationResultEvent):
            self.triggered_events.append(event)


class StepInvocationStartEventListener(EventListener):
    def __init__(self) -> None:
        self.triggered_events: List[StepInvocationStartEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, StepInvocationStartEvent):
            self.triggered_events.append(event)


class ToolExecutionResultEventListener(EventListener):
    def __init__(self) -> None:
        self.triggered_events: List[ToolExecutionResultEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ToolExecutionResultEvent):
            self.triggered_events.append(event)


class ToolExecutionStartEventListener(EventListener):
    def __init__(self) -> None:
        self.triggered_events: List[ToolExecutionStartEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ToolExecutionStartEvent):
            self.triggered_events.append(event)


class ConversationExecutionStartedEventListener(EventListener):
    def __init__(self) -> None:
        self.triggered_events: List[ConversationExecutionStartedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ConversationExecutionStartedEvent):
            self.triggered_events.append(event)


class ConversationExecutionFinishedEventListener(EventListener):
    def __init__(self) -> None:
        self.triggered_events: List[ConversationExecutionFinishedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ConversationExecutionFinishedEvent):
            self.triggered_events.append(event)
