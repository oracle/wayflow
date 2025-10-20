# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
import time
from dataclasses import dataclass

import pytest

from wayflowcore.agent import Agent
from wayflowcore.contextproviders.constantcontextprovider import ConstantContextProvider
from wayflowcore.events.event import EndSpanEvent, Event, StartSpanEvent
from wayflowcore.events.eventlistener import (
    GenericEventListener,
    record_event,
    register_event_listeners,
)
from wayflowcore.flow import Flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import LlmGenerationConfig, Prompt, VllmModel
from wayflowcore.outputparser import RegexOutputParser
from wayflowcore.property import IntegerProperty, ObjectProperty, StringProperty
from wayflowcore.steps import StartStep
from wayflowcore.tools import Tool, ToolRequest
from wayflowcore.tracing.span import (
    AgentExecutionSpan,
    ContextProviderExecutionSpan,
    ConversationalComponentExecutionSpan,
    ConversationSpan,
    FlowExecutionSpan,
    LlmGenerationSpan,
    Span,
    StepInvocationSpan,
    ToolExecutionSpan,
    get_active_span_stack,
    get_current_span,
)
from wayflowcore.tracing.spanprocessor import SpanProcessor
from wayflowcore.tracing.trace import Trace

from .conftest import MyCustomEvent, MyCustomSpan


def test_span_creation_with_default_values() -> None:
    span = MyCustomSpan()
    assert span.span_id is not None
    assert span.name is None
    assert span.start_time is None
    assert span.end_time is None
    assert span.events == []
    assert span._parent_span is None
    assert span._trace is None
    assert span._span_processors == []


def test_span_creation_with_custom_values() -> None:
    attributes = {
        "name": "My span test",
        "start_time": 12,
        "end_time": 13,
        "span_id": "abc123",
        "events": [
            StartSpanEvent(event_id="1", name="start event"),
            EndSpanEvent(event_id="2", name="start event"),
        ],
    }
    span = MyCustomSpan(**attributes)
    for attribute_name, attribute_value in attributes.items():
        assert getattr(span, attribute_name) == attribute_value


def test_span_stack_is_registered_correctly() -> None:
    assert get_current_span() is None
    assert get_active_span_stack() == []
    with MyCustomSpan(custom_attribute=2) as span_1:
        assert span_1.custom_attribute == 2
        assert get_current_span() == span_1
        assert get_active_span_stack() == [span_1]
        with MyCustomSpan() as span_2:
            assert get_current_span() == span_2
            assert get_active_span_stack() == [span_1, span_2]
            span_3 = MyCustomSpan(custom_attribute=100)
            assert span_3.custom_attribute == 100
            # Check that we did not put the span in the stack yet
            assert get_current_span() == span_2
            assert get_active_span_stack() == [span_1, span_2]
            span_3.start()
            assert get_current_span() == span_3
            assert get_active_span_stack() == [span_1, span_2, span_3]
            span_3.record_end_span_event(EndSpanEvent(span=span_3))
            span_3.end()
            # Check that the span was correctly removed from the stack
            assert get_current_span() == span_2
            assert get_active_span_stack() == [span_1, span_2]
            span_2.record_end_span_event(EndSpanEvent(span=span_2))
        assert get_current_span() == span_1
        assert get_active_span_stack() == [span_1]
        span_1.record_end_span_event(EndSpanEvent(span=span_1))
    assert get_current_span() is None
    assert get_active_span_stack() == []


def test_parent_span_is_set_correctly():
    with MyCustomSpan() as span_1:
        assert span_1._parent_span is None
        with MyCustomSpan() as span_2:
            assert span_1._parent_span is None
            assert span_2._parent_span == span_1
            span_3 = MyCustomSpan(custom_attribute=100)
            assert span_3._parent_span is None
            span_3.start()
            assert span_1._parent_span is None
            assert span_2._parent_span == span_1
            assert span_3._parent_span == span_2
            span_3.record_end_span_event(EndSpanEvent(span=span_3))
            span_3.end()
            span_2.record_end_span_event(EndSpanEvent(span=span_2))
        span_1.record_end_span_event(EndSpanEvent(span=span_1))


def test_span_start_end_timestamps_are_set_correctly() -> None:
    time_split_1 = time.time_ns()
    with MyCustomSpan() as span_1:
        time_split_2 = time.time_ns()
        assert time_split_1 <= span_1.start_time <= time_split_2
        assert span_1.end_time is None
        with MyCustomSpan() as span_2:
            time_split_3 = time.time_ns()
            assert time_split_2 <= span_2.start_time <= time_split_3
            assert span_2.end_time is None
            span_3 = MyCustomSpan(custom_attribute=100)
            span_3.start()
            time_split_4 = time.time_ns()
            assert time_split_3 <= span_3.start_time <= time_split_4
            assert span_3.end_time is None
            span_3.record_end_span_event(EndSpanEvent(span=span_3))
            span_3.end()
            time_split_5 = time.time_ns()
            assert time_split_3 <= span_3.start_time <= time_split_4
            assert span_3.end_time is not None
            assert time_split_4 <= span_3.end_time <= time_split_5
            span_2.record_end_span_event(EndSpanEvent(span=span_2))
        time_split_6 = time.time_ns()
        assert time_split_2 <= span_2.start_time <= time_split_3
        assert span_2.end_time is not None
        assert time_split_5 <= span_2.end_time <= time_split_6
        span_1.record_end_span_event(EndSpanEvent(span=span_1))
    time_split_7 = time.time_ns()
    assert time_split_1 <= span_1.start_time <= time_split_2
    assert span_1.end_time is not None
    assert time_split_6 <= span_1.end_time <= time_split_7


def test_recording_span_end_event_twice_raises_exception() -> None:
    with MyCustomSpan() as span:
        span.record_end_span_event(EndSpanEvent(span=span))
        with pytest.raises(
            RuntimeError, match="Cannot record two end span events for the same span"
        ):
            span.record_end_span_event(EndSpanEvent(span=span))


def test_closing_span_without_calling_record_end_span_event_method_raises_warning() -> None:
    with pytest.warns(UserWarning):
        with MyCustomSpan():
            pass

    span = MyCustomSpan()
    span.start()
    with pytest.warns(UserWarning):
        span.end()


def test_recorded_events_are_added_to_correct_span() -> None:
    event_0 = MyCustomEvent(name="no-span-event", custom_attribute={"a": 1})
    record_event(event_0)
    with MyCustomSpan(custom_attribute=-12) as span_1:
        event_1 = MyCustomEvent(name="event_1", custom_attribute={"b": 1, "c": "a"})
        record_event(event_1)
        assert event_0 not in span_1.events
        assert event_1 in span_1.events
        with MyCustomSpan() as span_2:
            event_2 = MyCustomEvent(name="event_2")
            record_event(event_2)
            assert event_0 not in span_2.events
            assert event_1 not in span_2.events
            assert event_2 in span_2.events
            assert event_2 not in span_1.events
            span_3 = MyCustomSpan(custom_attribute=100)
            span_3.start()
            event_3 = MyCustomEvent(name="event_3", custom_attribute={"o": {"p": [1]}, "p": [0]})
            record_event(event_3)
            assert event_0 not in span_3.events
            assert event_1 not in span_3.events
            assert event_2 not in span_3.events
            assert event_3 in span_3.events
            assert event_3 not in span_1.events
            assert event_3 not in span_2.events
            span_3.record_end_span_event(EndSpanEvent(span=span_3))
            span_3.end()
            span_2.record_end_span_event(EndSpanEvent(span=span_2))
        span_1.record_end_span_event(EndSpanEvent(span=span_1))
    # Ensure after span closure that nothing changed
    assert event_0 not in span_1.events
    assert event_0 not in span_2.events
    assert event_0 not in span_3.events
    assert event_1 in span_1.events
    assert event_1 not in span_2.events
    assert event_1 not in span_3.events
    assert event_2 not in span_1.events
    assert event_2 in span_2.events
    assert event_2 not in span_3.events
    assert event_3 not in span_1.events
    assert event_3 not in span_2.events
    assert event_3 in span_3.events


def test_span_is_deregistered_when_an_exception_is_raised_in_context() -> None:
    assert get_current_span() is None
    try:
        with MyCustomSpan() as span_1:
            try:
                with MyCustomSpan() as span_2:
                    assert get_current_span() is span_2
                    assert len(get_active_span_stack()) == 2
                    with MyCustomSpan() as span_3:
                        assert get_current_span() is span_3
                        assert len(get_active_span_stack()) == 3
                        raise ValueError("Exception!")
            except ValueError:
                pass
            # We ensure that both spans are removed from stack
            assert get_current_span() is span_1
            assert len(get_active_span_stack()) == 1
            span_1.record_end_span_event(event=EndSpanEvent(span=span_1))
    except ValueError:
        pass
    assert get_current_span() is None
    assert len(get_active_span_stack()) == 0


def test_span_is_deregistered_when_an_exception_is_raised_in_span_processor() -> None:

    class SpanProcessorThatMightRaiseExceptions(SpanProcessor):

        def __init__(self, raise_on_start: bool = False, raise_on_end: bool = False):
            self.on_start_called = False
            self.on_end_called = False
            self.raise_on_start = raise_on_start
            self.raise_on_end = raise_on_end

        def on_start(self, span: "Span") -> None:
            self.on_start_called = True
            if self.raise_on_start:
                raise ValueError("Exception in on_start")

        def on_end(self, span: "Span") -> None:
            self.on_end_called = True
            if self.raise_on_end:
                raise ValueError("Exception in on_end")

        def startup(self) -> None:
            return

        def shutdown(self) -> None:
            return

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            return True

    assert get_current_span() is None
    span_processor_that_does_not_raise = SpanProcessorThatMightRaiseExceptions(
        raise_on_start=False, raise_on_end=False
    )
    span_processor_that_raises_at_start = SpanProcessorThatMightRaiseExceptions(
        raise_on_start=True, raise_on_end=False
    )
    # Note that the order in which we provide span processors matters, as the first one that raises blocks the process
    with Trace(
        span_processors=[span_processor_that_does_not_raise, span_processor_that_raises_at_start]
    ):
        try:
            with MyCustomSpan() as span_1:
                # Ensure we never end up in here, as we raise at start
                assert False
        except ValueError:
            pass
    assert span_processor_that_raises_at_start.on_start_called
    assert span_processor_that_does_not_raise.on_start_called
    assert not span_processor_that_raises_at_start.on_end_called
    assert span_processor_that_does_not_raise.on_end_called
    assert get_current_span() is None
    assert len(get_active_span_stack()) == 0

    span_processor_that_does_not_raise = SpanProcessorThatMightRaiseExceptions(
        raise_on_start=False, raise_on_end=False
    )
    span_processor_that_raises_at_end = SpanProcessorThatMightRaiseExceptions(
        raise_on_start=False, raise_on_end=True
    )
    with Trace(
        span_processors=[span_processor_that_does_not_raise, span_processor_that_raises_at_end]
    ):
        try:
            with MyCustomSpan() as span_1:
                with MyCustomSpan() as span_2:
                    assert get_current_span() is span_2
                    assert len(get_active_span_stack()) == 2
                    span_2.record_end_span_event(event=EndSpanEvent(span=span_2))
                span_1.record_end_span_event(event=EndSpanEvent(span=span_1))
        except ValueError:
            pass
    assert span_processor_that_raises_at_end.on_start_called
    assert span_processor_that_does_not_raise.on_start_called
    assert span_processor_that_raises_at_end.on_end_called
    assert span_processor_that_does_not_raise.on_end_called
    assert get_current_span() is None
    assert len(get_active_span_stack()) == 0


def test_span_is_deregistered_when_an_exception_is_raised_in_end_event() -> None:

    def _raises_exception(event: "Event"):
        raise ValueError("ruins your day as well")

    assert get_current_span() is None
    try:
        with register_event_listeners(
            [
                GenericEventListener(
                    event_classes=[EndSpanEvent],
                    function=_raises_exception,
                )
            ]
        ):
            with MyCustomSpan() as span_1:
                try:
                    with MyCustomSpan() as span_2:
                        assert get_current_span() is span_2
                        assert len(get_active_span_stack()) == 2
                        with MyCustomSpan() as span_3:
                            assert get_current_span() is span_3
                            assert len(get_active_span_stack()) == 3
                            span_3.record_end_span_event(EndSpanEvent(span=span_3))
                except ValueError:
                    pass
                # We ensure that both spans are removed from stack
                assert get_current_span() is span_1
                assert len(get_active_span_stack()) == 1
    except ValueError:
        pass
    assert get_current_span() is None
    assert len(get_active_span_stack()) == 0


def test_span_is_deregistered_when_an_exception_is_raised_in_start_event() -> None:

    @dataclass
    class SpanThatMightRaiseInStartSpanEvent(Span):

        raise_exception_at_start: bool = True

        def _create_start_span_event(self) -> "Event":
            if self.raise_exception_at_start:
                raise ValueError("Error in start span event")
            return StartSpanEvent(span=self)

        def record_end_span_event(self) -> None:
            self._record_end_span_event(event=EndSpanEvent(span=self))

    assert get_current_span() is None
    with SpanThatMightRaiseInStartSpanEvent(raise_exception_at_start=False) as span_1:
        try:
            with SpanThatMightRaiseInStartSpanEvent(raise_exception_at_start=False) as span_2:
                assert get_current_span() is span_2
                assert len(get_active_span_stack()) == 2
                with SpanThatMightRaiseInStartSpanEvent(raise_exception_at_start=True):
                    # Ensure we never get in here
                    assert False
        except ValueError:
            pass
        # We ensure that both spans are removed from stack
        assert get_current_span() is span_1
        assert len(get_active_span_stack()) == 1
        span_1.record_end_span_event()
    assert get_current_span() is None
    assert len(get_active_span_stack()) == 0


class ShouldNotBeSerialized:
    def __str__(self):
        raise ValueError("Should not be serialized")

    def __repr__(self):
        raise ValueError("Should not be serialized")


@pytest.mark.parametrize(
    "span",
    [
        ContextProviderExecutionSpan(
            context_provider=ConstantContextProvider(
                value=ShouldNotBeSerialized(), output_description=IntegerProperty(name="1")
            )
        ),
        StepInvocationSpan(
            step=StartStep(name="start_step"), inputs={"some": ShouldNotBeSerialized()}
        ),
        ToolExecutionSpan(
            tool=Tool(
                name="some_tool",
                description="some descr",
                input_descriptors=[StringProperty(name="arg1")],
            ),
            tool_request=ToolRequest(name="some_tool", args={"arg1": "hello"}, tool_request_id="1"),
        ),
        ConversationSpan(
            conversation=Flow.from_steps([StartStep(name="start_step")]).start_conversation()
        ),
        FlowExecutionSpan(conversational_component=Flow.from_steps([StartStep(name="start_step")])),
        AgentExecutionSpan(
            conversational_component=Agent(
                llm=VllmModel(model_id="llama", host_port="my_host"),
                custom_instruction="you are a helpful agent",
            )
        ),
        ConversationalComponentExecutionSpan(
            conversational_component=Agent(
                llm=VllmModel(model_id="llama", host_port="my_host"),
                custom_instruction="you are a helpful agent",
            )
        ),
        LlmGenerationSpan(
            llm=VllmModel(
                model_id="llama",
                host_port="my_host",
                generation_config=LlmGenerationConfig(max_tokens=100, top_p=0.9),
            ),
            prompt=Prompt(
                messages=[
                    Message(message_type=MessageType.SYSTEM, content="system prompt"),
                    Message(message_type=MessageType.USER, content="user query"),
                ],
                tools=[
                    Tool(
                        name="some_tool_1",
                        input_descriptors=[StringProperty(name="arg1")],
                        description="some descr",
                    ),
                    Tool(
                        name="some_tool_2",
                        input_descriptors=[StringProperty(name="arg1")],
                        description="some descr",
                    ),
                ],
                response_format=ObjectProperty(name="obj", properties={"attr1": StringProperty()}),
                output_parser=RegexOutputParser(regex_pattern=r".*"),
                generation_config=LlmGenerationConfig(max_tokens=100, top_p=0.9),
            ),
        ),
    ],
)
def test_span_can_be_serialized_to_tracing_info(span):
    tracing_info = span.to_tracing_info(mask_sensitive_information=False)
    serialized_tracing_info = json.dumps(tracing_info)
    deserialized_tracing_info = json.loads(serialized_tracing_info)
    assert deserialized_tracing_info == tracing_info
