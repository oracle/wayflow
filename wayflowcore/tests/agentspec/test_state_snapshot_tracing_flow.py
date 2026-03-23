# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from contextlib import AbstractContextManager, ExitStack
from typing import Any, Sequence

import pytest
from pyagentspec.tracing.events import Event as AgentSpecEvent
from pyagentspec.tracing.events import FlowExecutionEnd as AgentSpecFlowExecutionEnd
from pyagentspec.tracing.events import FlowExecutionStart as AgentSpecFlowExecutionStart
from pyagentspec.tracing.events import StateSnapshotEmitted as AgentSpecStateSnapshotEmitted
from pyagentspec.tracing.spanprocessor import SpanProcessor as AgentSpecSpanProcessor
from pyagentspec.tracing.spans import FlowExecutionSpan as AgentSpecFlowExecutionSpan
from pyagentspec.tracing.spans import NodeExecutionSpan as AgentSpecNodeExecutionSpan
from pyagentspec.tracing.spans import Span as AgentSpecSpan
from pyagentspec.tracing.spans import ToolExecutionSpan as AgentSpecToolExecutionSpan
from pyagentspec.tracing.trace import Trace as AgentSpecTrace

from wayflowcore.agentspec.tracing import AgentSpecEventListener
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval, StateSnapshotPolicy
from wayflowcore.flow import Flow
from wayflowcore.steps import CompleteStep, FlowExecutionStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.tools import ServerTool


class _PassiveSpanProcessor(AgentSpecSpanProcessor):
    def on_start(self, span: AgentSpecSpan) -> None:
        return None

    async def on_start_async(self, span: AgentSpecSpan) -> None:
        return None

    def on_end(self, span: AgentSpecSpan) -> None:
        return None

    async def on_end_async(self, span: AgentSpecSpan) -> None:
        return None

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


class _SnapshotSpanRecorder(_PassiveSpanProcessor):
    def __init__(self) -> None:
        super().__init__()
        self.started_spans: list[AgentSpecSpan] = []

    def on_start(self, span: AgentSpecSpan) -> None:
        self.started_spans.append(span)

    async def on_start_async(self, span: AgentSpecSpan) -> None:
        self.started_spans.append(span)


class _EventsSeenAtSpanEndRecorder(_PassiveSpanProcessor):
    def __init__(self) -> None:
        super().__init__()
        self.events_by_span_id: dict[str, list[AgentSpecEvent]] = {}

    def on_end(self, span: AgentSpecSpan) -> None:
        self.events_by_span_id[span.id] = list(span.events)

    async def on_end_async(self, span: AgentSpecSpan) -> None:
        self.events_by_span_id[span.id] = list(span.events)


def _recorded_spans(
    span_recorder: _SnapshotSpanRecorder,
    span_type: type[AgentSpecSpan],
) -> list[AgentSpecSpan]:
    return [span for span in span_recorder.started_spans if isinstance(span, span_type)]


def _single_span(
    span_recorder: _SnapshotSpanRecorder,
    span_type: type[AgentSpecSpan],
) -> AgentSpecSpan:
    matching_spans = _recorded_spans(span_recorder, span_type)
    assert len(matching_spans) == 1
    return matching_spans[0]


def _span_events(
    span: AgentSpecSpan,
    event_type: type[AgentSpecEvent],
) -> list[AgentSpecEvent]:
    return [event for event in span.events if isinstance(event, event_type)]


def _execute_with_trace(
    conversation,
    *,
    state_snapshot_policy,
    span_processors: Sequence[AgentSpecSpanProcessor] = (),
    contexts: Sequence[AbstractContextManager[Any]] = (),
) -> tuple[Any, _SnapshotSpanRecorder]:
    span_recorder = _SnapshotSpanRecorder()
    listener = AgentSpecEventListener()

    with ExitStack() as stack:
        for context in contexts:
            stack.enter_context(context)
        stack.enter_context(AgentSpecTrace(span_processors=[span_recorder, *span_processors]))
        stack.enter_context(register_event_listeners([listener]))
        status = conversation.execute(state_snapshot_policy=state_snapshot_policy)

    return status, span_recorder


def _make_output_flow() -> Flow:
    return Flow.from_steps(
        [
            OutputMessageStep(message_template="Hello", name="single_step"),
            CompleteStep(name="end"),
        ],
        name="simple_output_flow",
    )


def _make_tool_flow() -> Flow:
    return Flow.from_steps(
        [
            ToolExecutionStep(
                tool=ServerTool(
                    name="say_hi",
                    description="Say hi",
                    func=lambda: "hi",
                    input_descriptors=[],
                ),
                name="tool_step",
            ),
            CompleteStep(name="end"),
        ],
        name="tool_flow",
    )


def _make_nested_parent_flow_conversation():
    child_flow = Flow.from_steps(
        [
            OutputMessageStep(message_template="child", name="child_message"),
            CompleteStep(name="end"),
        ],
        name="child_flow",
    )
    parent_flow = Flow.from_steps(
        [
            FlowExecutionStep(flow=child_flow, name="child_flow_step"),
            OutputMessageStep(message_template="parent", name="parent_message"),
            CompleteStep(name="end"),
        ],
        name="parent_flow",
    )
    return parent_flow.start_conversation()


def _snapshot_message(snapshot_event: AgentSpecStateSnapshotEmitted) -> str | None:
    messages = (snapshot_event.state_snapshot or {}).get("conversation", {}).get("messages", [])
    if not messages:
        return None
    return messages[-1].get("content")


def test_conversation_turn_snapshots_attach_to_the_flow_span() -> None:
    conversation = _make_output_flow().start_conversation()
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)

    flow_span = _single_span(span_recorder, AgentSpecFlowExecutionSpan)
    state_snapshot_events = _span_events(flow_span, AgentSpecStateSnapshotEmitted)

    assert _span_events(flow_span, AgentSpecFlowExecutionStart)
    assert len(state_snapshot_events) == 2
    assert state_snapshot_events[-1].conversation_id == conversation.conversation_id
    assert _snapshot_message(state_snapshot_events[-1]) == "Hello"


def test_final_flow_snapshot_is_visible_to_span_processors_inside_on_end() -> None:
    conversation = _make_output_flow().start_conversation()
    events_seen_at_end_recorder = _EventsSeenAtSpanEndRecorder()
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
        span_processors=[events_seen_at_end_recorder],
    )

    assert isinstance(status, FinishedStatus)

    flow_span = _single_span(span_recorder, AgentSpecFlowExecutionSpan)
    events_seen_at_end = events_seen_at_end_recorder.events_by_span_id[flow_span.id]

    assert any(isinstance(event, AgentSpecFlowExecutionEnd) for event in events_seen_at_end)
    assert isinstance(events_seen_at_end[-1], AgentSpecStateSnapshotEmitted)
    assert _snapshot_message(events_seen_at_end[-1]) == "Hello"


def test_node_turn_snapshots_attach_to_the_flow_span_not_node_or_tool_spans() -> None:
    conversation = _make_tool_flow().start_conversation()
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.NODE_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)

    flow_span = _single_span(span_recorder, AgentSpecFlowExecutionSpan)
    flow_snapshot_events = _span_events(flow_span, AgentSpecStateSnapshotEmitted)

    assert len(flow_snapshot_events) > 2
    assert not any(
        isinstance(event, AgentSpecStateSnapshotEmitted)
        for span in _recorded_spans(span_recorder, AgentSpecNodeExecutionSpan)
        for event in span.events
    )
    assert not any(
        isinstance(event, AgentSpecStateSnapshotEmitted)
        for span in _recorded_spans(span_recorder, AgentSpecToolExecutionSpan)
        for event in span.events
    )


def test_nested_flow_execution_exports_snapshots_only_on_the_root_flow_span() -> None:
    conversation = _make_nested_parent_flow_conversation()
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)

    flow_spans = _recorded_spans(span_recorder, AgentSpecFlowExecutionSpan)
    assert len(flow_spans) == 2

    flow_spans_by_name = {
        next(
            event for event in span.events if isinstance(event, AgentSpecFlowExecutionStart)
        ).flow.name: span
        for span in flow_spans
    }
    parent_span = flow_spans_by_name["parent_flow"]
    child_span = flow_spans_by_name["child_flow"]

    parent_snapshot_events = _span_events(parent_span, AgentSpecStateSnapshotEmitted)
    child_snapshot_events = _span_events(child_span, AgentSpecStateSnapshotEmitted)

    assert len(parent_snapshot_events) == 2
    assert [event.conversation_id for event in parent_snapshot_events] == [
        conversation.conversation_id,
        conversation.conversation_id,
    ]
    assert _snapshot_message(parent_snapshot_events[-1]) == "parent"
    assert child_snapshot_events == []


def test_off_policy_disables_flow_state_snapshot_export() -> None:
    conversation = _make_output_flow().start_conversation()
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.OFF
        ),
    )

    assert isinstance(status, FinishedStatus)

    flow_span = _single_span(span_recorder, AgentSpecFlowExecutionSpan)
    assert _span_events(flow_span, AgentSpecStateSnapshotEmitted) == []


def test_raised_turn_exports_only_the_opening_flow_snapshot() -> None:
    conversation = Flow.from_steps(
        [
            ToolExecutionStep(
                tool=ServerTool(
                    name="explode",
                    description="Raise an error",
                    func=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
                    input_descriptors=[],
                )
            ),
            CompleteStep(name="end"),
        ]
    ).start_conversation()

    span_recorder = _SnapshotSpanRecorder()
    listener = AgentSpecEventListener()
    with AgentSpecTrace(span_processors=[span_recorder]):
        with register_event_listeners([listener]):
            with pytest.raises(RuntimeError, match="boom"):
                conversation.execute(
                    state_snapshot_policy=StateSnapshotPolicy(
                        state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
                    )
                )

    flow_span = _single_span(span_recorder, AgentSpecFlowExecutionSpan)
    state_snapshot_events = _span_events(flow_span, AgentSpecStateSnapshotEmitted)

    assert len(state_snapshot_events) == 1
    assert state_snapshot_events[0].state_snapshot["execution"]["status"] is None
