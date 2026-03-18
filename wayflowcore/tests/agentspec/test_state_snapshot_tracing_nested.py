# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from contextlib import AbstractContextManager, ExitStack
from dataclasses import dataclass
from typing import Any, Sequence

import pytest
from pyagentspec.tracing.events import Event as AgentSpecEvent
from pyagentspec.tracing.events import FlowExecutionEnd as AgentSpecFlowExecutionEnd
from pyagentspec.tracing.events import FlowExecutionStart as AgentSpecFlowExecutionStart
from pyagentspec.tracing.events import StateSnapshotEmitted as AgentSpecStateSnapshotEmitted
from pyagentspec.tracing.events import SwarmExecutionEnd as AgentSpecSwarmExecutionEnd
from pyagentspec.tracing.spanprocessor import SpanProcessor as AgentSpecSpanProcessor
from pyagentspec.tracing.spans import AgentExecutionSpan as AgentSpecAgentExecutionSpan
from pyagentspec.tracing.spans import FlowExecutionSpan as AgentSpecFlowExecutionSpan
from pyagentspec.tracing.spans import Span as AgentSpecSpan
from pyagentspec.tracing.spans import SwarmExecutionSpan as AgentSpecSwarmExecutionSpan
from pyagentspec.tracing.spans import ToolExecutionSpan as AgentSpecToolExecutionSpan
from pyagentspec.tracing.trace import Trace as AgentSpecTrace

from wayflowcore import Agent as WayflowAgent
from wayflowcore.agentspec.tracing import AgentSpecEventListener
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval
from wayflowcore.flow import Flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.steps import AgentExecutionStep, CompleteStep, FlowExecutionStep, OutputMessageStep
from wayflowcore.swarm import Swarm
from wayflowcore.tools import ToolRequest

from ..testhelpers.patching import patch_llm
from ..testhelpers.statesnapshots import (
    build_state_snapshot_policy,
    snapshot_message,
    snapshot_runtime_conversation_ids,
    snapshot_status_types,
)


@dataclass(frozen=True)
class SwarmStateSnapshotScenario:
    flow: Flow
    primary_llm: VllmModel
    primary_outputs: list[Message | str]
    secondary_llm: VllmModel
    secondary_outputs: list[Message | str]
    multi_agent_span_class: type[AgentSpecSpan]
    child_message: str
    parent_message: str
    multi_agent_end_event_class: type[AgentSpecEvent]


class SnapshotSpanRecorder(AgentSpecSpanProcessor):
    def __init__(self) -> None:
        super().__init__()
        self.started_spans: list[AgentSpecSpan] = []
        self.ended_spans: list[AgentSpecSpan] = []

    def on_start(self, span: AgentSpecSpan) -> None:
        self.started_spans.append(span)

    async def on_start_async(self, span: AgentSpecSpan) -> None:
        self.started_spans.append(span)

    def on_end(self, span: AgentSpecSpan) -> None:
        self.ended_spans.append(span)

    async def on_end_async(self, span: AgentSpecSpan) -> None:
        self.ended_spans.append(span)

    def on_event(self, event: AgentSpecEvent, span: AgentSpecSpan) -> None:
        return None

    async def on_event_async(self, event: AgentSpecEvent, span: AgentSpecSpan) -> None:
        return None

    def startup(self) -> None:
        return None

    def shutdown(self) -> None:
        return None

    async def startup_async(self) -> None:
        return None

    async def shutdown_async(self) -> None:
        return None


def _create_mock_vllm_model(name: str) -> VllmModel:
    return VllmModel(model_id="mock.model", host_port="http://mock.url", name=name)


def _create_send_message_request(recipient_name: str, message: str) -> Message:
    return Message(
        content="",
        message_type=MessageType.TOOL_REQUEST,
        tool_requests=[
            ToolRequest(
                name="send_message",
                args={"recipient": recipient_name, "message": message},
            )
        ],
    )


def _build_swarm_state_snapshot_flow() -> SwarmStateSnapshotScenario:
    first_agent_llm = _create_mock_vllm_model("agent1")
    second_agent_llm = _create_mock_vllm_model("agent2")
    first_agent = WayflowAgent(llm=first_agent_llm, name="agent1", description="agent1")
    second_agent = WayflowAgent(llm=second_agent_llm, name="agent2", description="agent2")
    swarm = Swarm(
        first_agent=first_agent,
        relationships=[(first_agent, second_agent), (second_agent, first_agent)],
        name="swarm",
    )

    return SwarmStateSnapshotScenario(
        flow=Flow.from_steps([AgentExecutionStep(agent=swarm), CompleteStep(name="end")]),
        primary_llm=first_agent_llm,
        primary_outputs=[
            _create_send_message_request("agent2", "Do it"),
            "agent1 final answer",
        ],
        secondary_llm=second_agent_llm,
        secondary_outputs=["agent2 answer"],
        multi_agent_span_class=AgentSpecSwarmExecutionSpan,
        child_message="agent2 answer",
        parent_message="agent1 final answer",
        multi_agent_end_event_class=AgentSpecSwarmExecutionEnd,
    )


def _policy(
    interval: StateSnapshotInterval,
    **kwargs: Any,
):
    return build_state_snapshot_policy(interval, **kwargs)


def _execute_with_trace(
    conversation,
    *,
    state_snapshot_policy,
    span_processors: Sequence[AgentSpecSpanProcessor] = (),
    contexts: Sequence[AbstractContextManager[Any]] = (),
):
    span_recorder = SnapshotSpanRecorder()
    listener = AgentSpecEventListener()

    with ExitStack() as stack:
        for context in contexts:
            stack.enter_context(context)
        stack.enter_context(AgentSpecTrace(span_processors=[span_recorder, *span_processors]))
        stack.enter_context(register_event_listeners([listener]))
        status = conversation.execute(state_snapshot_policy=state_snapshot_policy)

    return status, span_recorder


def _spans(
    span_recorder: SnapshotSpanRecorder,
    span_type: type[AgentSpecSpan],
) -> list[AgentSpecSpan]:
    return [span for span in span_recorder.started_spans if isinstance(span, span_type)]


def _single_span(
    span_recorder: SnapshotSpanRecorder,
    span_type: type[AgentSpecSpan],
) -> AgentSpecSpan:
    matching_spans = _spans(span_recorder, span_type)
    assert len(matching_spans) == 1
    return matching_spans[0]


def _events(
    span: AgentSpecSpan,
    event_type: type[AgentSpecEvent],
) -> list[AgentSpecEvent]:
    return [event for event in span.events if isinstance(event, event_type)]


def _single_event(
    span: AgentSpecSpan,
    event_type: type[AgentSpecEvent],
) -> AgentSpecEvent:
    return next(event for event in span.events if isinstance(event, event_type))


def _assert_snapshot_precedes_terminal_event(
    span: AgentSpecSpan,
    snapshot_events: Sequence[AgentSpecStateSnapshotEmitted],
    terminal_event: AgentSpecEvent,
) -> None:
    assert span.events.index(snapshot_events[-1]) < span.events.index(terminal_event)


@pytest.mark.parametrize(
    "flow_builder",
    [
        pytest.param(_build_swarm_state_snapshot_flow, id="swarm"),
    ],
)
def test_nested_multi_agent_state_snapshots_follow_conversation_ownership_boundaries(
    flow_builder,
) -> None:
    scenario = flow_builder()
    conversation = scenario.flow.start_conversation()
    conversation.append_user_message("dummy")

    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=_policy(StateSnapshotInterval.CONVERSATION_TURNS),
        contexts=[
            patch_llm(scenario.primary_llm, scenario.primary_outputs, patch_internal=True),
            patch_llm(scenario.secondary_llm, scenario.secondary_outputs, patch_internal=True),
        ],
    )

    assert isinstance(status, UserMessageRequestStatus)

    flow_span = _single_span(span_recorder, AgentSpecFlowExecutionSpan)
    flow_snapshot_events = _events(flow_span, AgentSpecStateSnapshotEmitted)
    assert len(flow_snapshot_events) == 2
    assert [event.conversation_id for event in flow_snapshot_events] == [
        conversation.conversation_id,
        conversation.conversation_id,
    ]
    assert snapshot_message(flow_snapshot_events[-1]) == scenario.parent_message

    multi_agent_span = _single_span(span_recorder, scenario.multi_agent_span_class)
    multi_agent_snapshot_events = _events(multi_agent_span, AgentSpecStateSnapshotEmitted)
    multi_agent_end_event = _single_event(multi_agent_span, scenario.multi_agent_end_event_class)
    parent_multi_agent_conversation_id = multi_agent_snapshot_events[0].conversation_id

    assert [event.conversation_id for event in multi_agent_snapshot_events] == [
        parent_multi_agent_conversation_id,
        parent_multi_agent_conversation_id,
        parent_multi_agent_conversation_id,
        parent_multi_agent_conversation_id,
        parent_multi_agent_conversation_id,
        parent_multi_agent_conversation_id,
    ]
    assert snapshot_status_types(multi_agent_snapshot_events) == [
        None,
        "ToolRequestStatus",
        None,
        "UserMessageRequestStatus",
        None,
        "UserMessageRequestStatus",
    ]
    assert snapshot_message(multi_agent_snapshot_events[4]) == scenario.child_message
    assert snapshot_message(multi_agent_snapshot_events[-1]) == scenario.parent_message
    _assert_snapshot_precedes_terminal_event(
        multi_agent_span,
        multi_agent_snapshot_events,
        multi_agent_end_event,
    )

    agent_snapshot_spans = [
        span
        for span in span_recorder.started_spans
        if isinstance(span, AgentSpecAgentExecutionSpan)
        and any(isinstance(event, AgentSpecStateSnapshotEmitted) for event in span.events)
    ]
    assert len(agent_snapshot_spans) == 3
    agent_snapshot_events_by_conversation_id: dict[str, list] = {}
    for agent_span in agent_snapshot_spans:
        snapshot_events = _events(agent_span, AgentSpecStateSnapshotEmitted)
        agent_snapshot_events_by_conversation_id.setdefault(
            snapshot_events[0].conversation_id,
            [],
        ).extend(snapshot_events)

    assert len(agent_snapshot_events_by_conversation_id) == 2
    manager_thread_snapshot_events = next(
        snapshot_events
        for snapshot_events in agent_snapshot_events_by_conversation_id.values()
        if len(snapshot_events) == 4
    )
    delegated_agent_snapshot_events = next(
        snapshot_events
        for snapshot_events in agent_snapshot_events_by_conversation_id.values()
        if len(snapshot_events) == 2
    )

    assert manager_thread_snapshot_events[0].conversation_id != conversation.conversation_id
    assert manager_thread_snapshot_events[0].conversation_id != parent_multi_agent_conversation_id
    assert delegated_agent_snapshot_events[0].conversation_id not in {
        conversation.conversation_id,
        parent_multi_agent_conversation_id,
        manager_thread_snapshot_events[0].conversation_id,
    }
    assert snapshot_status_types(manager_thread_snapshot_events) == [
        None,
        "ToolRequestStatus",
        None,
        "UserMessageRequestStatus",
    ]
    assert snapshot_message(manager_thread_snapshot_events[2]) == scenario.child_message
    assert snapshot_message(manager_thread_snapshot_events[-1]) == scenario.parent_message
    assert snapshot_status_types(delegated_agent_snapshot_events) == [
        None,
        "UserMessageRequestStatus",
    ]
    assert snapshot_message(delegated_agent_snapshot_events[-1]) == scenario.child_message

    tool_spans = _spans(span_recorder, AgentSpecToolExecutionSpan)
    assert tool_spans
    assert not any(
        isinstance(event, AgentSpecStateSnapshotEmitted)
        for span in tool_spans
        for event in span.events
    )

    assert flow_span in span_recorder.ended_spans
    assert multi_agent_span in span_recorder.ended_spans


def test_nested_flow_state_snapshots_stay_on_the_root_flow_span_for_shared_conversations() -> None:
    child_flow = Flow.from_steps(
        [OutputMessageStep(message_template="child"), CompleteStep(name="end")],
        step_names=["child_message", "end"],
        name="child_flow",
    )
    parent_flow = Flow.from_steps(
        [
            FlowExecutionStep(flow=child_flow),
            OutputMessageStep(message_template="parent"),
            CompleteStep(name="end"),
        ],
        step_names=["child_flow_step", "parent_message", "end"],
        name="parent_flow",
    )
    conversation = parent_flow.start_conversation()

    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=_policy(StateSnapshotInterval.CONVERSATION_TURNS),
    )

    assert isinstance(status, FinishedStatus)

    flow_spans = _spans(span_recorder, AgentSpecFlowExecutionSpan)
    assert len(flow_spans) == 2

    flow_spans_by_name = {
        _single_event(span, AgentSpecFlowExecutionStart).flow.name: span for span in flow_spans
    }
    parent_span = flow_spans_by_name["parent_flow"]
    child_span = flow_spans_by_name["child_flow"]

    parent_snapshot_events = _events(parent_span, AgentSpecStateSnapshotEmitted)
    child_snapshot_events = _events(child_span, AgentSpecStateSnapshotEmitted)
    parent_end_event = _single_event(parent_span, AgentSpecFlowExecutionEnd)

    assert [event.conversation_id for event in parent_snapshot_events] == [
        conversation.conversation_id,
        conversation.conversation_id,
        conversation.conversation_id,
        conversation.conversation_id,
    ]
    child_runtime_conversation_id = parent_snapshot_events[1].state_snapshot["conversation"]["id"]
    assert snapshot_runtime_conversation_ids(parent_snapshot_events) == [
        conversation.id,
        child_runtime_conversation_id,
        child_runtime_conversation_id,
        conversation.id,
    ]
    assert child_runtime_conversation_id != conversation.id
    assert snapshot_message(parent_snapshot_events[2]) == "child"
    assert snapshot_message(parent_snapshot_events[-1]) == "parent"
    assert not child_snapshot_events
    _assert_snapshot_precedes_terminal_event(parent_span, parent_snapshot_events, parent_end_event)
