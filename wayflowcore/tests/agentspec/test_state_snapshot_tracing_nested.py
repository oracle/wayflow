# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from contextlib import ExitStack

from pyagentspec.tracing.events import Event as AgentSpecEvent
from pyagentspec.tracing.events import FlowExecutionStart as AgentSpecFlowExecutionStart
from pyagentspec.tracing.events import StateSnapshotEmitted as AgentSpecStateSnapshotEmitted
from pyagentspec.tracing.spanprocessor import SpanProcessor as AgentSpecSpanProcessor
from pyagentspec.tracing.spans import FlowExecutionSpan as AgentSpecFlowExecutionSpan
from pyagentspec.tracing.spans import Span as AgentSpecSpan
from pyagentspec.tracing.trace import Trace as AgentSpecTrace

from wayflowcore.agentspec.tracing import AgentSpecEventListener
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval
from wayflowcore.flow import Flow
from wayflowcore.steps import CompleteStep, FlowExecutionStep, OutputMessageStep

from ..testhelpers.statesnapshots import (
    build_state_snapshot_policy,
    snapshot_message,
    snapshot_runtime_conversation_ids,
)


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


def _execute_with_trace(conversation) -> tuple[FinishedStatus, SnapshotSpanRecorder]:
    span_recorder = SnapshotSpanRecorder()
    listener = AgentSpecEventListener()

    with ExitStack() as stack:
        stack.enter_context(AgentSpecTrace(span_processors=[span_recorder]))
        stack.enter_context(register_event_listeners([listener]))
        status = conversation.execute(
            state_snapshot_policy=build_state_snapshot_policy(
                StateSnapshotInterval.CONVERSATION_TURNS
            )
        )

    assert isinstance(status, FinishedStatus)
    return status, span_recorder


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

    _, span_recorder = _execute_with_trace(conversation)

    flow_spans = [
        span for span in span_recorder.started_spans if isinstance(span, AgentSpecFlowExecutionSpan)
    ]
    assert len(flow_spans) == 2

    flow_spans_by_name = {
        next(
            event for event in span.events if isinstance(event, AgentSpecFlowExecutionStart)
        ).flow.name: span
        for span in flow_spans
    }
    parent_span = flow_spans_by_name["parent_flow"]
    child_span = flow_spans_by_name["child_flow"]

    parent_snapshot_events = [
        event for event in parent_span.events if isinstance(event, AgentSpecStateSnapshotEmitted)
    ]
    child_snapshot_events = [
        event for event in child_span.events if isinstance(event, AgentSpecStateSnapshotEmitted)
    ]
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
