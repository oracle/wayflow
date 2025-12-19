# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict, List, Type

import pytest

from wayflowcore import Message, MessageType
from wayflowcore.agent import Agent
from wayflowcore.events.event import (
    ConversationalComponentExecutionFinishedEvent,
    ConversationalComponentExecutionStartedEvent,
)
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors._agentexecutor import (
    EXIT_CONVERSATION_CONFIRMATION_MESSAGE,
    EXIT_CONVERSATION_TOOL_NAME,
)
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import _run_flow_and_return_status, create_single_step_flow
from wayflowcore.steps import InputMessageStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep
from wayflowcore.steps.flowexecutionstep import FlowExecutionStep
from wayflowcore.tools import ToolRequest
from wayflowcore.tracing.span import (
    _PII_TEXT_MASK,
    AgentExecutionSpan,
    ConversationalComponentExecutionSpan,
    FlowExecutionSpan,
)
from wayflowcore.tracing.spanprocessor import SpanProcessor
from wayflowcore.tracing.trace import Trace

from ...events.conftest import count_agents_and_flows_in_flow
from ..conftest import (
    InMemorySpanExporter,
    SerializableDummyModel,
    create_serializable_dummy_llm_with_next_output,
)
from .conftest import GET_LOCATION_CLIENT_TOOL


@pytest.mark.parametrize("missing_attribute", ["conversational_component"])
@pytest.mark.parametrize(
    "span_class", [ConversationalComponentExecutionSpan, AgentExecutionSpan, FlowExecutionSpan]
)
def test_span_creation_with_missing_arguments_fails(
    missing_attribute: str, span_class: Type[ConversationalComponentExecutionSpan]
) -> None:
    all_attributes: Dict[str, Any] = {
        "conversational_component": (
            create_single_step_flow(InputMessageStep(message_template="How are you?"))
            if span_class == FlowExecutionSpan
            else Agent(llm=SerializableDummyModel())
        ),
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        span_class(**all_attributes)


@pytest.mark.parametrize(
    "span_info",
    [
        {
            "name": "My span test",
            "start_time": 12,
            "end_time": 13,
            "span_id": "abc123",
            "conversational_component": create_single_step_flow(
                InputMessageStep(message_template="How are you?")
            ),
        },
        {
            "name": "My other test",
            "conversational_component": create_single_step_flow(
                OutputMessageStep(message_template="How are you?")
            ),
        },
        {
            "name": "Yet another test",
            "span_id": "123abc",
            "start_time": 12,
            "conversational_component": create_single_step_flow(
                InputMessageStep(message_template="How are you?")
            ),
        },
        {
            "name": "Another test?",
            "conversational_component": Agent(
                llm=SerializableDummyModel(), tools=[GET_LOCATION_CLIENT_TOOL]
            ),
        },
        {
            "name": "Wow, another test!",
            "conversational_component": Agent(
                agent_id="123",
                llm=SerializableDummyModel(),
                initial_message="Hey!",
                agents=[
                    Agent(
                        name="subagent",
                        description="subagent desc",
                        llm=SerializableDummyModel(),
                        tools=[GET_LOCATION_CLIENT_TOOL],
                    )
                ],
                flows=[
                    create_single_step_flow(
                        InputMessageStep(message_template="How are you?"),
                        flow_name="subflow",
                        flow_description="subflow desc",
                    )
                ],
            ),
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
        if isinstance(span_info["conversational_component"], Agent):
            span = AgentExecutionSpan(**span_info)
        elif isinstance(span_info["conversational_component"], Flow):
            span = FlowExecutionSpan(**span_info)
        else:
            raise ValueError(
                f"Unexpected conversational component type {type(span_info['conversational_component'])}"
            )
        serialized_span = span.to_tracing_info(
            mask_sensitive_information=mask_sensitive_information
        )
        assert serialized_span["trace_id"] == trace.trace_id
        assert serialized_span["trace_name"] == trace.name
        assert serialized_span["span_type"] == str(span.__class__.__name__)
        for attribute_name in attributes_to_check:
            attr = getattr(span, attribute_name)
            assert attr == serialized_span[attribute_name]
        assert (
            serialized_span["conversational_component.name"] == span.conversational_component.name
        )
        assert (
            serialized_span["conversational_component.description"]
            == span.conversational_component.description
        )
        for attribute_name in ["input_descriptors", "output_descriptors"]:
            if mask_sensitive_information:
                assert serialized_span[f"conversational_component.{attribute_name}"] == [
                    descriptor.name
                    for descriptor in getattr(span.conversational_component, attribute_name)
                ]
            else:
                assert serialized_span[f"conversational_component.{attribute_name}"] == [
                    descriptor.to_json_schema()
                    for descriptor in getattr(span.conversational_component, attribute_name)
                ]

        conversational_component_attributes = serialized_span["conversational_component.attributes"]
        if isinstance(span_info["conversational_component"], Agent):
            agent = span.conversational_component
            assert "steps" not in conversational_component_attributes
            for parameter in (
                "max_iterations",
                "custom_instruction",
                "initial_message",
                "can_finish_conversation",
            ):
                assert parameter in conversational_component_attributes
                if mask_sensitive_information and parameter in {
                    "custom_instruction",
                    "initial_message",
                }:
                    assert conversational_component_attributes[parameter] == _PII_TEXT_MASK
                else:
                    assert conversational_component_attributes[parameter] == getattr(
                        agent, parameter
                    )
            for parameter in ("tools", "agents", "flows", "context_providers"):
                assert parameter in conversational_component_attributes
                assert len(conversational_component_attributes[parameter]) == len(
                    getattr(agent, parameter)
                )
        else:
            flow = span.conversational_component
            assert "tools" not in conversational_component_attributes
            for parameter in (
                "steps",
                "context_providers",
                "variables",
                "control_flow_edges",
                "data_flow_edges",
            ):
                assert parameter in conversational_component_attributes
                assert len(conversational_component_attributes[parameter]) == len(
                    getattr(flow, parameter)
                )


def test_correct_start_and_end_events_are_catched_by_eventlisteners() -> None:
    from wayflowcore.executors.executionstatus import FinishedStatus

    from ...events.event_listeners import (
        ConversationalComponentExecutionFinishedEventListener,
        ConversationalComponentExecutionStartedEventListener,
    )

    started_eventlistener = ConversationalComponentExecutionStartedEventListener()
    finished_eventlistener = ConversationalComponentExecutionFinishedEventListener()
    flow = create_single_step_flow(InputMessageStep(message_template="How are you?"))
    with register_event_listeners([started_eventlistener, finished_eventlistener]):
        with ConversationalComponentExecutionSpan(conversational_component=flow) as span:
            assert len(started_eventlistener.triggered_events) == 1
            assert isinstance(
                started_eventlistener.triggered_events[0],
                ConversationalComponentExecutionStartedEvent,
            )
            assert len(finished_eventlistener.triggered_events) == 0
            span.record_end_span_event(execution_status=FinishedStatus({}))
        assert len(started_eventlistener.triggered_events) == 1
        assert len(finished_eventlistener.triggered_events) == 1
        assert isinstance(
            finished_eventlistener.triggered_events[0],
            ConversationalComponentExecutionFinishedEvent,
        )


@pytest.mark.parametrize(
    "flow",
    [
        create_single_step_flow(InputMessageStep(message_template="How are you?")),
        create_single_step_flow(ToolExecutionStep(tool=GET_LOCATION_CLIENT_TOOL)),
    ],
)
def test_event_is_triggered_with_flow(
    flow: Flow,
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
) -> None:
    with Trace(span_processors=[default_span_processor]):
        _run_flow_and_return_status(flow=flow, inputs={})
    exported_spans = default_span_exporter.get_exported_spans(
        "AgentExecutionSpan"
    ) + default_span_exporter.get_exported_spans("FlowExecutionSpan")
    assert len(exported_spans) == 1
    span = exported_spans[0]
    assert len(span["events"]) >= 2
    assert span["events"][0]["event_type"] == "FlowExecutionStartedEvent"
    assert span["events"][-1]["event_type"] == "FlowExecutionFinishedEvent"


@pytest.mark.parametrize(
    "agent, user_messages",
    [
        (
            Agent(custom_instruction="Be polite", llm=SerializableDummyModel()),
            [],
        ),
        (
            Agent(
                agent_id="a123",
                custom_instruction="Be polite",
                llm=create_serializable_dummy_llm_with_next_output(
                    {
                        "I'm done, you can exit": Message(
                            tool_requests=[
                                ToolRequest(
                                    name=EXIT_CONVERSATION_TOOL_NAME,
                                    args={},
                                    tool_request_id="tool_request_id_1",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        ),
                        EXIT_CONVERSATION_CONFIRMATION_MESSAGE: Message(
                            tool_requests=[
                                ToolRequest(
                                    name=EXIT_CONVERSATION_TOOL_NAME,
                                    args={},
                                    tool_request_id="tool_request_id_2",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        ),
                    }
                ),
                can_finish_conversation=True,
            ),
            ["I'm done, you can exit"],
        ),
        (
            Agent(
                agent_id="a123",
                custom_instruction="Be polite",
                llm=create_serializable_dummy_llm_with_next_output(
                    {
                        "Please use the tool": Message(
                            tool_requests=[
                                ToolRequest(
                                    name=GET_LOCATION_CLIENT_TOOL.name,
                                    args={"company_name": "Oracle Labs"},
                                    tool_request_id="tool_request_id_1",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        )
                    }
                ),
                tools=[GET_LOCATION_CLIENT_TOOL],
            ),
            ["Please use the tool"],
        ),
    ],
)
def test_event_is_triggered_with_agent(
    agent: Agent,
    user_messages: List[str],
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
) -> None:
    conversation = agent.start_conversation()
    with Trace(span_processors=[default_span_processor]):
        agent.execute(conversation)
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            agent.execute(conversation)
    exported_spans = default_span_exporter.get_exported_spans(
        "AgentExecutionSpan"
    ) + default_span_exporter.get_exported_spans("FlowExecutionSpan")
    assert len(exported_spans) == 1 + len(user_messages)
    for span in exported_spans:
        assert len(span["events"]) >= 2
        assert span["events"][0]["event_type"] == "AgentExecutionStartedEvent"
        assert span["events"][-1]["event_type"] == "AgentExecutionFinishedEvent"


@pytest.mark.parametrize(
    "agent, user_messages",
    [
        (
            Agent(
                agent_id="a123",
                custom_instruction="Be polite",
                llm=create_serializable_dummy_llm_with_next_output(
                    {
                        "Please use the tool": Message(
                            tool_requests=[
                                ToolRequest(
                                    name="tool",
                                    args={},
                                    tool_request_id="tool_request_id_1",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        ),
                        "In shore X": Message(
                            content="The company is in shore X",
                            message_type=MessageType.AGENT,
                        ),
                    }
                ),
                flows=[
                    create_single_step_flow(
                        flow_name="tool",
                        flow_description="flow as tool",
                        step=OutputMessageStep("In shore X"),
                    ),
                ],
            ),
            ["Please use the tool"],
        ),
        (
            Agent(
                agent_id="a123",
                custom_instruction="Be polite",
                llm=create_serializable_dummy_llm_with_next_output(
                    {
                        "Please use the tool": Message(
                            tool_requests=[
                                ToolRequest(
                                    name="tool",
                                    args={},
                                    tool_request_id="tool_request_id_1",
                                )
                            ],
                            message_type=MessageType.TOOL_REQUEST,
                            sender="a123",
                            recipients={"a123"},
                        ),
                        "In shore X": Message(
                            content="The company is in shore X",
                            message_type=MessageType.AGENT,
                        ),
                    }
                ),
                agents=[
                    Agent(
                        agent_id="a123",
                        name="tool",
                        description="agent as tool",
                        custom_instruction="Be polite",
                        llm=create_serializable_dummy_llm_with_next_output("In shore X"),
                    )
                ],
            ),
            ["Please use the tool"],
        ),
    ],
)
def test_event_is_triggered_with_flows_and_agents_in_agent(
    agent: Agent,
    user_messages: List[str],
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
) -> None:
    conversation = agent.start_conversation()
    with Trace(span_processors=[default_span_processor]):
        agent.execute(conversation)
        for user_message in user_messages:
            conversation.append_user_message(user_message)
            agent.execute(conversation)
    exported_spans = default_span_exporter.get_exported_spans(
        "AgentExecutionSpan"
    ) + default_span_exporter.get_exported_spans("FlowExecutionSpan")
    # initial execute + one execute per user message + an execution of the agent/flow as tool
    assert len(exported_spans) == 1 + len(user_messages) + 1
    for span in exported_spans:
        assert len(span["events"]) >= 2
        assert span["events"][0]["event_type"] in (
            "AgentExecutionStartedEvent",
            "FlowExecutionStartedEvent",
        )
        assert span["events"][-1]["event_type"] in (
            "AgentExecutionFinishedEvent",
            "FlowExecutionFinishedEvent",
        )


@pytest.mark.parametrize(
    "flow",
    [
        create_single_step_flow(
            step=AgentExecutionStep(
                agent=Agent(custom_instruction="Be polite", llm=SerializableDummyModel()),
            )
        ),
        create_single_step_flow(step=OutputMessageStep("Hello from flow")),
        create_single_step_flow(
            step=FlowExecutionStep(
                flow=create_single_step_flow(step=OutputMessageStep("Hello from subflow"))
            )
        ),
        create_single_step_flow(
            step=FlowExecutionStep(
                flow=create_single_step_flow(
                    step=FlowExecutionStep(
                        flow=create_single_step_flow(
                            step=AgentExecutionStep(
                                agent=Agent(
                                    custom_instruction="Be polite", llm=SerializableDummyModel()
                                )
                            )
                        )
                    )
                )
            )
        ),
    ],
)
def test_event_is_triggered_with_flows_and_agents_in_flows(
    flow: Flow,
    default_span_processor: SpanProcessor,
    default_span_exporter: InMemorySpanExporter,
) -> None:
    conversation = flow.start_conversation()
    with Trace(span_processors=[default_span_processor]):
        flow.execute(conversation)
    exported_spans = default_span_exporter.get_exported_spans(
        "AgentExecutionSpan"
    ) + default_span_exporter.get_exported_spans("FlowExecutionSpan")
    # initial execute + one execute per flow or agent execution step
    assert len(exported_spans) == 1 + count_agents_and_flows_in_flow(flow)
    for span in exported_spans:
        assert len(span["events"]) >= 2
        assert span["events"][0]["event_type"] in (
            "AgentExecutionStartedEvent",
            "FlowExecutionStartedEvent",
        )
        assert span["events"][-1]["event_type"] in (
            "AgentExecutionFinishedEvent",
            "FlowExecutionFinishedEvent",
        )
