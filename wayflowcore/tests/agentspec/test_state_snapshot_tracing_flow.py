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
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval
from wayflowcore.flow import Flow
from wayflowcore.steps import CompleteStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.tools import ServerTool

from ..testhelpers.statesnapshots import (
    build_state_snapshot_policy,
    snapshot_message,
    snapshot_step_histories,
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


async def _execute_with_trace_async(
    conversation,
    *,
    state_snapshot_policy,
    span_processors: Sequence[AgentSpecSpanProcessor] = (),
    contexts: Sequence[AbstractContextManager[Any]] = (),
):
    span_recorder = SnapshotSpanRecorder()
    listener = AgentSpecEventListener()

    async with AgentSpecTrace(span_processors=[span_recorder, *span_processors]):
        with ExitStack() as stack:
            for context in contexts:
                stack.enter_context(context)
            stack.enter_context(register_event_listeners([listener]))
            status = await conversation.execute_async(state_snapshot_policy=state_snapshot_policy)

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


def _build_tool_state_snapshot_flow() -> Flow:
    return Flow.from_steps(
        [
            ToolExecutionStep(
                tool=ServerTool(
                    name="say_hi",
                    description="Say hi",
                    func=lambda: "hi",
                    input_descriptors=[],
                )
            ),
            CompleteStep(name="end"),
        ]
    )


def test_flow_state_snapshots_are_mapped_into_the_flow_span_before_flow_end() -> None:
    flow = Flow.from_steps(
        [OutputMessageStep(message_template="Hello"), CompleteStep(name="end")],
        step_names=["single_step", "end"],
    )
    conversation = flow.start_conversation()
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=_policy(
            StateSnapshotInterval.CONVERSATION_TURNS,
            extra_state_builder=lambda _conversation: {"ui": {"active_tab": "plan"}},
        ),
    )

    assert isinstance(status, FinishedStatus)

    flow_span = _single_span(span_recorder, AgentSpecFlowExecutionSpan)
    assert _events(flow_span, AgentSpecFlowExecutionStart)
    state_snapshot_events = _events(flow_span, AgentSpecStateSnapshotEmitted)

    assert len(state_snapshot_events) == 2
    final_snapshot_event = state_snapshot_events[-1]
    assert final_snapshot_event.conversation_id == conversation.conversation_id
    assert snapshot_message(final_snapshot_event) == "Hello"
    assert final_snapshot_event.extra_state == {"ui": {"active_tab": "plan"}}
    assert flow_span.end_time is not None
    assert "variable_state" not in final_snapshot_event.model_dump(mask_sensitive_information=False)
    assert flow_span in span_recorder.ended_spans


@pytest.mark.anyio
async def test_flow_state_snapshots_are_mapped_into_the_flow_span_before_flow_end_async() -> None:
    flow = Flow.from_steps(
        [OutputMessageStep(message_template="Hello"), CompleteStep(name="end")],
        step_names=["single_step", "end"],
    )
    conversation = flow.start_conversation()
    status, span_recorder = await _execute_with_trace_async(
        conversation,
        state_snapshot_policy=_policy(
            StateSnapshotInterval.CONVERSATION_TURNS,
            extra_state_builder=lambda _conversation: {"ui": {"active_tab": "plan"}},
        ),
    )

    assert isinstance(status, FinishedStatus)

    flow_span = _single_span(span_recorder, AgentSpecFlowExecutionSpan)
    state_snapshot_events = _events(flow_span, AgentSpecStateSnapshotEmitted)

    assert len(state_snapshot_events) == 2
    final_snapshot_event = state_snapshot_events[-1]
    assert final_snapshot_event.conversation_id == conversation.conversation_id
    assert snapshot_message(final_snapshot_event) == "Hello"
    assert final_snapshot_event.extra_state == {"ui": {"active_tab": "plan"}}
    assert flow_span.end_time is not None
    assert "variable_state" not in final_snapshot_event.model_dump(mask_sensitive_information=False)
    assert flow_span in span_recorder.ended_spans


def test_node_turn_state_snapshots_are_mapped_into_the_flow_span_not_node_spans() -> None:
    flow = Flow.from_steps(
        [OutputMessageStep(message_template="Hello"), CompleteStep(name="end")],
        step_names=["single_step", "end"],
    )
    conversation = flow.start_conversation()
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=_policy(StateSnapshotInterval.NODE_TURNS),
    )

    assert isinstance(status, FinishedStatus)

    flow_span = _single_span(span_recorder, AgentSpecFlowExecutionSpan)
    flow_snapshot_events = _events(flow_span, AgentSpecStateSnapshotEmitted)

    assert len(flow_snapshot_events) == 6
    assert snapshot_step_histories(flow_snapshot_events) == [
        [],
        ["__StartStep__"],
        ["__StartStep__"],
        ["__StartStep__", "single_step"],
        ["__StartStep__", "single_step"],
        ["__StartStep__", "single_step", "end"],
    ]
    node_spans = _spans(span_recorder, AgentSpecNodeExecutionSpan)
    assert node_spans
    assert not any(
        isinstance(event, AgentSpecStateSnapshotEmitted)
        for span in node_spans
        for event in span.events
    )


@pytest.mark.parametrize(
    ("interval", "expected_step_histories"),
    [
        pytest.param(
            StateSnapshotInterval.TOOL_TURNS,
            [
                ["__StartStep__", "step_0"],
                ["__StartStep__", "step_0"],
            ],
            id="tool_turns",
        ),
        pytest.param(
            StateSnapshotInterval.ALL_INTERNAL_TURNS,
            [
                [],
                ["__StartStep__"],
                ["__StartStep__"],
                ["__StartStep__", "step_0"],
                ["__StartStep__", "step_0"],
                ["__StartStep__", "step_0"],
                ["__StartStep__", "step_0"],
                ["__StartStep__", "step_0", "end"],
            ],
            id="all_internal_turns",
        ),
    ],
)
def test_internal_flow_state_snapshots_follow_conversation_ownership_for_agent_spec(
    interval: StateSnapshotInterval,
    expected_step_histories: list[list[str]],
) -> None:
    flow = _build_tool_state_snapshot_flow()
    conversation = flow.start_conversation()
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=_policy(interval),
    )

    assert isinstance(status, FinishedStatus)

    flow_span = _single_span(span_recorder, AgentSpecFlowExecutionSpan)
    flow_snapshot_events = _events(flow_span, AgentSpecStateSnapshotEmitted)
    assert snapshot_step_histories(flow_snapshot_events) == expected_step_histories

    tool_spans = _spans(span_recorder, AgentSpecToolExecutionSpan)
    node_spans = _spans(span_recorder, AgentSpecNodeExecutionSpan)
    assert tool_spans
    assert node_spans
    assert not any(
        isinstance(event, AgentSpecStateSnapshotEmitted)
        for span in [*tool_spans, *node_spans]
        for event in span.events
    )


def test_off_policy_does_not_bridge_state_snapshots_into_agent_spec_spans() -> None:
    flow = Flow.from_steps(
        [OutputMessageStep(message_template="Hello"), CompleteStep(name="end")],
        step_names=["single_step", "end"],
    )
    conversation = flow.start_conversation()
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=_policy(StateSnapshotInterval.OFF),
    )

    assert isinstance(status, FinishedStatus)

    flow_span = _single_span(span_recorder, AgentSpecFlowExecutionSpan)
    assert _events(flow_span, AgentSpecFlowExecutionStart)
    assert _events(flow_span, AgentSpecFlowExecutionEnd)
    assert not _events(flow_span, AgentSpecStateSnapshotEmitted)


def test_only_the_opening_state_snapshot_is_exported_when_a_turn_raises() -> None:
    flow = Flow.from_steps(
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
    )
    conversation = flow.start_conversation()
    span_recorder = SnapshotSpanRecorder()

    with AgentSpecTrace(span_processors=[span_recorder]):
        with register_event_listeners([AgentSpecEventListener()]):
            with pytest.raises(RuntimeError, match="boom"):
                conversation.execute(
                    state_snapshot_policy=_policy(StateSnapshotInterval.CONVERSATION_TURNS)
                )

    flow_span = _single_span(span_recorder, AgentSpecFlowExecutionSpan)
    state_snapshot_events = _events(flow_span, AgentSpecStateSnapshotEmitted)

    assert len(state_snapshot_events) == 1
    assert state_snapshot_events[0].state_snapshot["execution"]["status"] is None
    assert flow_span in span_recorder.ended_spans
