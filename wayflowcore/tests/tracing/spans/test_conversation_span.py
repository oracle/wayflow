# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict, Type

import pytest

from wayflowcore.conversation import Conversation
from wayflowcore.events.event import (
    ConversationExecutionFinishedEvent,
    ConversationExecutionStartedEvent,
)
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors._agentconversation import AgentConversation
from wayflowcore.executors.executionstatus import (
    ExecutionStatus,
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.steps.inputmessagestep import InputMessageStep
from wayflowcore.steps.outputmessagestep import OutputMessageStep
from wayflowcore.steps.toolexecutionstep import ToolExecutionStep
from wayflowcore.tools.tools import ToolResult
from wayflowcore.tracing.span import _MASKING_TOKEN, ConversationSpan
from wayflowcore.tracing.spanprocessor import SpanProcessor
from wayflowcore.tracing.trace import Trace

from ...events.conftest import DUMMY_AGENT_WITH_GET_LOCATION_TOOL, GET_LOCATION_CLIENT_TOOL
from ..conftest import InMemorySpanExporter
from .conftest import DUMMY_SERVER_TOOL


def test_span_creation_with_missing_arguments_fails() -> None:
    with pytest.raises(ValueError, match=f"An attribute named `conversation`"):
        ConversationSpan()


@pytest.mark.parametrize(
    "span_info",
    [
        {
            "name": "My span test",
            "start_time": 12,
            "end_time": 13,
            "span_id": "abc123",
            "conversation": DUMMY_AGENT_WITH_GET_LOCATION_TOOL.start_conversation(),
        },
        {
            "name": "My other span test",
            "start_time": 12,
            "end_time": 13,
            "span_id": "abc123",
            "conversation": create_single_step_flow(
                step=ToolExecutionStep(
                    tool=DUMMY_SERVER_TOOL,
                )
            ).start_conversation(),
        },
        {
            "name": "My other span test",
            "start_time": 12,
            "end_time": 13,
            "span_id": "abc123",
            "conversation": create_single_step_flow(
                step=OutputMessageStep("Hello, how are you doing?"),
            ).start_conversation(),
        },
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_span_serialization_format(
    span_info: Dict[str, Any], mask_sensitive_information: bool
) -> None:
    attributes_to_check = [
        attribute
        for attribute in ("name", "span_id", "start_time", "end_time")
        if attribute in span_info
    ]
    with Trace(name="abc") as trace:
        span = ConversationSpan(**span_info)
        serialized_span = span.to_tracing_info(
            mask_sensitive_information=mask_sensitive_information
        )
        assert serialized_span["trace_id"] == trace.trace_id
        assert serialized_span["trace_name"] == trace.name
        assert serialized_span["span_type"] == str(span.__class__.__name__)
        for attribute_name in attributes_to_check:
            assert getattr(span, attribute_name) == serialized_span[attribute_name]
        assert serialized_span["conversation.id"] == span.conversation.conversation_id
        assert serialized_span["conversation.name"] == span.conversation.name
        assert (
            serialized_span["conversational_component.type"] == "Agent"
            if isinstance(span.conversation, AgentConversation)
            else "Flow"
        )
        conversational_component_id = span.conversation.component.id
        assert serialized_span["conversational_component.id"] == conversational_component_id
        if mask_sensitive_information:
            assert serialized_span["conversation.inputs"] == _MASKING_TOKEN
        else:
            assert serialized_span["conversation.inputs"] == span.conversation.inputs


@pytest.mark.parametrize(
    "conversation",
    [
        create_single_step_flow(
            step=OutputMessageStep("Hello, how are you doing?"),
        ).start_conversation(),
        DUMMY_AGENT_WITH_GET_LOCATION_TOOL.start_conversation(),
    ],
)
def test_correct_start_and_end_events_are_caught_by_eventlisteners(
    conversation: Conversation,
) -> None:

    from ...events.event_listeners import (
        ConversationExecutionFinishedEventListener,
        ConversationExecutionStartedEventListener,
    )

    start_listener = ConversationExecutionStartedEventListener()
    end_listener = ConversationExecutionFinishedEventListener()

    with register_event_listeners([start_listener, end_listener]):
        with ConversationSpan(
            conversation=conversation,
        ) as span:
            assert len(start_listener.triggered_events) == 1
            assert isinstance(
                start_listener.triggered_events[0],
                ConversationExecutionStartedEvent,
            )
            assert len(end_listener.triggered_events) == 0
            span.record_end_span_event(
                execution_status=FinishedStatus({}),
            )
        assert len(start_listener.triggered_events) == 1
        assert isinstance(start_listener.triggered_events[0], ConversationExecutionStartedEvent)
        assert len(end_listener.triggered_events) == 1
        assert isinstance(end_listener.triggered_events[0], ConversationExecutionFinishedEvent)


@pytest.mark.parametrize(
    "conversation",
    [
        create_single_step_flow(
            step=OutputMessageStep("Hello, how are you doing?"),
        ).start_conversation(),
        create_single_step_flow(
            step=ToolExecutionStep(
                DUMMY_SERVER_TOOL,
            )
        ).start_conversation(),
    ],
)
def test_event_is_triggered_with_flow(
    conversation: Conversation,
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
) -> None:
    with Trace(span_processors=[default_span_processor]):
        with ConversationSpan(conversation=conversation) as span:
            execution_status = conversation.execute()
            span.record_end_span_event(
                execution_status=execution_status,
            )
    exported_spans = default_span_exporter.get_exported_spans("ConversationSpan")
    assert len(exported_spans) == 1
    span = exported_spans[0]
    assert len(span["events"]) >= 2
    assert span["events"][0]["event_type"] == "ConversationExecutionStartedEvent"
    assert span["events"][-1]["event_type"] == "ConversationExecutionFinishedEvent"

    execution_status = span["events"][-1]["execution_status"]
    assert execution_status == FinishedStatus.__name__


@pytest.mark.parametrize(
    "conversation, expected_execution_status",
    [
        (
            DUMMY_AGENT_WITH_GET_LOCATION_TOOL.start_conversation(),
            UserMessageRequestStatus,
        ),
        (
            create_single_step_flow(
                step=InputMessageStep("Hello, what's your name?")
            ).start_conversation(),
            UserMessageRequestStatus,
        ),
        (
            create_single_step_flow(
                step=ToolExecutionStep(
                    GET_LOCATION_CLIENT_TOOL,
                )
            ).start_conversation(),
            ToolRequestStatus,
        ),
    ],
)
def test_event_is_triggered_with_yielding_conversations(
    conversation: Conversation,
    expected_execution_status: Type[ExecutionStatus],
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
) -> None:
    with Trace(span_processors=[default_span_processor]):
        with ConversationSpan(conversation=conversation) as span:
            execution_status = conversation.execute()
            span.record_end_span_event(
                execution_status=execution_status,
            )
    exported_spans = default_span_exporter.get_exported_spans("ConversationSpan")
    assert len(exported_spans) == 1
    span = exported_spans[0]
    assert len(span["events"]) >= 2
    assert span["events"][0]["event_type"] == "ConversationExecutionStartedEvent"
    assert span["events"][-1]["event_type"] == "ConversationExecutionFinishedEvent"

    execution_status = span["events"][-1]["execution_status"]
    assert execution_status == expected_execution_status.__name__


@pytest.mark.parametrize(
    "conversation, additional_message",
    [
        (
            create_single_step_flow(
                step=InputMessageStep("Hello, what's your name?")
            ).start_conversation(),
            Message(
                content="My name is <redacted>",
                message_type=MessageType.USER,
            ),
        ),
        (
            create_single_step_flow(
                step=ToolExecutionStep(
                    GET_LOCATION_CLIENT_TOOL,
                )
            ).start_conversation(),
            Message(
                tool_result=ToolResult(
                    content="Location is Shore X",
                    tool_request_id="test",
                ),
                message_type=MessageType.TOOL_RESULT,
            ),
        ),
    ],
)
def test_event_is_triggered_once_with_multiple_execute_calls(
    conversation: Conversation,
    additional_message: Message,
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
) -> None:
    with Trace(span_processors=[default_span_processor]):
        with ConversationSpan(conversation=conversation) as span:
            conversation.execute()

            # Making sure the tool result id matches the tool request id for testing purposes
            last_message = conversation.get_last_message()
            if last_message is not None and last_message.message_type == MessageType.TOOL_REQUEST:
                assert additional_message.tool_result is not None
                assert last_message.tool_requests is not None
                additional_message.tool_result = ToolResult(
                    content=additional_message.tool_result.content,
                    tool_request_id=last_message.tool_requests[-1].tool_request_id,
                )

            conversation.append_message(additional_message)
            execution_status = conversation.execute()
            span.record_end_span_event(
                execution_status=execution_status,
            )
    exported_spans = default_span_exporter.get_exported_spans("ConversationSpan")
    assert len(exported_spans) == 1
    span = exported_spans[0]
    assert len(span["events"]) >= 2
    assert span["events"][0]["event_type"] == "ConversationExecutionStartedEvent"
    assert span["events"][-1]["event_type"] == "ConversationExecutionFinishedEvent"

    execution_status = span["events"][-1]["execution_status"]
    assert execution_status == FinishedStatus.__name__
