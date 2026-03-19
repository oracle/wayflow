# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest
from pyagentspec.tracing.events import FlowExecutionEnd as AgentSpecFlowExecutionEnd
from pyagentspec.tracing.events import FlowExecutionStart as AgentSpecFlowExecutionStart
from pyagentspec.tracing.events import StateSnapshotEmitted as AgentSpecStateSnapshotEmitted
from pyagentspec.tracing.spans import FlowExecutionSpan as AgentSpecFlowExecutionSpan
from pyagentspec.tracing.spans import NodeExecutionSpan as AgentSpecNodeExecutionSpan
from pyagentspec.tracing.spans import ToolExecutionSpan as AgentSpecToolExecutionSpan
from pyagentspec.tracing.trace import Trace as AgentSpecTrace

from wayflowcore.agentspec.tracing import AgentSpecEventListener
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval, StateSnapshotPolicy
from wayflowcore.flow import Flow
from wayflowcore.steps import CompleteStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.tools import ServerTool

from ..testhelpers.agentspec_tracing import (
    SnapshotEventsSeenAtSpanEndRecorder,
    SnapshotSpanRecorder,
    events,
    execute_with_trace,
    single_span,
    spans,
)
from ..testhelpers.statesnapshots import (
    snapshot_message,
    snapshot_step_histories,
)


def test_flow_state_snapshots_are_mapped_into_the_flow_span_before_flow_end() -> None:
    flow = Flow.from_steps(
        [OutputMessageStep(message_template="Hello"), CompleteStep(name="end")],
        step_names=["single_step", "end"],
    )
    conversation = flow.start_conversation()
    status, span_recorder = execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS,
            extra_state_builder=lambda _conversation: {"ui": {"active_tab": "plan"}},
        ),
    )

    assert isinstance(status, FinishedStatus)

    flow_span = single_span(span_recorder, AgentSpecFlowExecutionSpan)
    assert events(flow_span, AgentSpecFlowExecutionStart)
    state_snapshot_events = events(flow_span, AgentSpecStateSnapshotEmitted)

    assert len(state_snapshot_events) == 2
    final_snapshot_event = state_snapshot_events[-1]
    assert final_snapshot_event.conversation_id == conversation.conversation_id
    assert snapshot_message(final_snapshot_event) == "Hello"
    assert final_snapshot_event.extra_state == {"ui": {"active_tab": "plan"}}
    assert flow_span.end_time is not None
    assert "variable_state" not in final_snapshot_event.model_dump(mask_sensitive_information=False)
    assert flow_span in span_recorder.ended_spans


def test_flow_final_state_snapshot_is_visible_to_span_processors_inside_on_end() -> None:
    flow = Flow.from_steps(
        [OutputMessageStep(message_template="Hello"), CompleteStep(name="end")],
        step_names=["single_step", "end"],
    )
    conversation = flow.start_conversation()
    on_end_recorder = SnapshotEventsSeenAtSpanEndRecorder()

    status, span_recorder = execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
        span_processors=[on_end_recorder],
    )

    assert isinstance(status, FinishedStatus)

    flow_span = single_span(span_recorder, AgentSpecFlowExecutionSpan)
    events_seen_at_end = on_end_recorder.events_by_span_id[flow_span.id]

    assert any(isinstance(event, AgentSpecFlowExecutionEnd) for event in events_seen_at_end)
    assert (
        len(
            [
                event
                for event in events_seen_at_end
                if isinstance(event, AgentSpecStateSnapshotEmitted)
            ]
        )
        == 2
    )
    assert isinstance(events_seen_at_end[-1], AgentSpecStateSnapshotEmitted)
    assert snapshot_message(events_seen_at_end[-1]) == "Hello"


@pytest.mark.anyio
async def test_flow_state_snapshots_are_mapped_into_the_flow_span_before_flow_end_async() -> None:
    flow = Flow.from_steps(
        [OutputMessageStep(message_template="Hello"), CompleteStep(name="end")],
        step_names=["single_step", "end"],
    )
    conversation = flow.start_conversation()
    span_recorder = SnapshotSpanRecorder()

    async with AgentSpecTrace(span_processors=[span_recorder]):
        with register_event_listeners([AgentSpecEventListener()]):
            status = await conversation.execute_async(
                state_snapshot_policy=StateSnapshotPolicy(
                    state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS,
                    extra_state_builder=lambda _conversation: {"ui": {"active_tab": "plan"}},
                )
            )

    assert isinstance(status, FinishedStatus)

    flow_span = single_span(span_recorder, AgentSpecFlowExecutionSpan)
    state_snapshot_events = events(flow_span, AgentSpecStateSnapshotEmitted)

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
    status, span_recorder = execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.NODE_TURNS
        ),
    )

    assert isinstance(status, FinishedStatus)

    flow_span = single_span(span_recorder, AgentSpecFlowExecutionSpan)
    flow_snapshot_events = events(flow_span, AgentSpecStateSnapshotEmitted)

    assert len(flow_snapshot_events) == 8
    assert snapshot_step_histories(flow_snapshot_events) == [
        [],
        [],
        ["__StartStep__"],
        ["__StartStep__"],
        ["__StartStep__", "single_step"],
        ["__StartStep__", "single_step"],
        ["__StartStep__", "single_step", "end"],
        ["__StartStep__", "single_step", "end"],
    ]
    node_spans = spans(span_recorder, AgentSpecNodeExecutionSpan)
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
                [],
                ["__StartStep__", "step_0"],
                ["__StartStep__", "step_0"],
                ["__StartStep__", "step_0", "end"],
            ],
            id="tool_turns",
        ),
        pytest.param(
            StateSnapshotInterval.ALL_INTERNAL_TURNS,
            [
                [],
                [],
                ["__StartStep__"],
                ["__StartStep__"],
                ["__StartStep__", "step_0"],
                ["__StartStep__", "step_0"],
                ["__StartStep__", "step_0"],
                ["__StartStep__", "step_0"],
                ["__StartStep__", "step_0", "end"],
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
    flow = Flow.from_steps(
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
    conversation = flow.start_conversation()
    status, span_recorder = execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(state_snapshot_interval=interval),
    )

    assert isinstance(status, FinishedStatus)

    flow_span = single_span(span_recorder, AgentSpecFlowExecutionSpan)
    flow_snapshot_events = events(flow_span, AgentSpecStateSnapshotEmitted)
    assert snapshot_step_histories(flow_snapshot_events) == expected_step_histories

    tool_spans = spans(span_recorder, AgentSpecToolExecutionSpan)
    node_spans = spans(span_recorder, AgentSpecNodeExecutionSpan)
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
    status, span_recorder = execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.OFF
        ),
    )

    assert isinstance(status, FinishedStatus)

    flow_span = single_span(span_recorder, AgentSpecFlowExecutionSpan)
    assert events(flow_span, AgentSpecFlowExecutionStart)
    assert events(flow_span, AgentSpecFlowExecutionEnd)
    assert not events(flow_span, AgentSpecStateSnapshotEmitted)


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
                    state_snapshot_policy=StateSnapshotPolicy(
                        state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
                    )
                )

    flow_span = single_span(span_recorder, AgentSpecFlowExecutionSpan)
    state_snapshot_events = events(flow_span, AgentSpecStateSnapshotEmitted)

    assert len(state_snapshot_events) == 1
    assert state_snapshot_events[0].state_snapshot["execution"]["status"] is None
    assert flow_span in span_recorder.ended_spans
