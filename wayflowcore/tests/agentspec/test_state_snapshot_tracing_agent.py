# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from contextlib import AbstractContextManager, ExitStack
from typing import Any, Sequence

from pyagentspec.tracing.events import AgentExecutionEnd as AgentSpecAgentExecutionEnd
from pyagentspec.tracing.events import AgentExecutionStart as AgentSpecAgentExecutionStart
from pyagentspec.tracing.events import Event as AgentSpecEvent
from pyagentspec.tracing.events import StateSnapshotEmitted as AgentSpecStateSnapshotEmitted
from pyagentspec.tracing.spanprocessor import SpanProcessor as AgentSpecSpanProcessor
from pyagentspec.tracing.spans import AgentExecutionSpan as AgentSpecAgentExecutionSpan
from pyagentspec.tracing.spans import LlmGenerationSpan as AgentSpecLlmGenerationSpan
from pyagentspec.tracing.spans import Span as AgentSpecSpan
from pyagentspec.tracing.trace import Trace as AgentSpecTrace

from wayflowcore import Agent as WayflowAgent
from wayflowcore.agentspec.tracing import AgentSpecEventListener
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors.executionstatus import UserMessageRequestStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval, StateSnapshotPolicy
from wayflowcore.models.vllmmodel import VllmModel

from ..testhelpers.patching import patch_llm


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


def _make_single_turn_agent_conversation() -> tuple[str, VllmModel, Any]:
    assistant_message = "Hello from agent"
    llm = VllmModel(model_id="mock.model", host_port="http://mock.url", name="agent")
    conversation = WayflowAgent(llm=llm).start_conversation()
    conversation.append_user_message("Hi")
    return assistant_message, llm, conversation


def _snapshot_message(snapshot_event: AgentSpecStateSnapshotEmitted) -> str | None:
    messages = (snapshot_event.state_snapshot or {}).get("conversation", {}).get("messages", [])
    if not messages:
        return None
    return messages[-1].get("content")


def test_conversation_turn_snapshots_attach_to_the_agent_span() -> None:
    assistant_message, llm, conversation = _make_single_turn_agent_conversation()
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
        contexts=[patch_llm(llm, [assistant_message], patch_internal=True)],
    )

    assert isinstance(status, UserMessageRequestStatus)

    agent_span = _single_span(span_recorder, AgentSpecAgentExecutionSpan)
    state_snapshot_events = _span_events(agent_span, AgentSpecStateSnapshotEmitted)

    assert _span_events(agent_span, AgentSpecAgentExecutionStart)
    assert len(state_snapshot_events) == 2
    assert state_snapshot_events[-1].conversation_id == conversation.conversation_id
    assert _snapshot_message(state_snapshot_events[-1]) == assistant_message


def test_node_turn_snapshots_attach_to_the_agent_span_not_llm_spans() -> None:
    assistant_message, llm, conversation = _make_single_turn_agent_conversation()
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.NODE_TURNS
        ),
        contexts=[patch_llm(llm, [assistant_message], patch_internal=True)],
    )

    assert isinstance(status, UserMessageRequestStatus)

    agent_span = _single_span(span_recorder, AgentSpecAgentExecutionSpan)
    state_snapshot_events = _span_events(agent_span, AgentSpecStateSnapshotEmitted)

    assert len(state_snapshot_events) == 4
    assert state_snapshot_events[-1].state_snapshot["execution"]["status"]["type"] == (
        "UserMessageRequestStatus"
    )
    assert _snapshot_message(state_snapshot_events[-1]) == assistant_message
    assert not any(
        isinstance(event, AgentSpecStateSnapshotEmitted)
        for span in _recorded_spans(span_recorder, AgentSpecLlmGenerationSpan)
        for event in span.events
    )


def test_final_agent_snapshot_is_visible_to_span_processors_inside_on_end() -> None:
    assistant_message, llm, conversation = _make_single_turn_agent_conversation()
    events_seen_at_end_recorder = _EventsSeenAtSpanEndRecorder()
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
        ),
        span_processors=[events_seen_at_end_recorder],
        contexts=[patch_llm(llm, [assistant_message], patch_internal=True)],
    )

    assert isinstance(status, UserMessageRequestStatus)

    agent_span = _single_span(span_recorder, AgentSpecAgentExecutionSpan)
    events_seen_at_end = events_seen_at_end_recorder.events_by_span_id[agent_span.id]

    assert any(isinstance(event, AgentSpecAgentExecutionEnd) for event in events_seen_at_end)
    assert isinstance(events_seen_at_end[-1], AgentSpecStateSnapshotEmitted)
    assert _snapshot_message(events_seen_at_end[-1]) == assistant_message


def test_agent_snapshot_extra_state_is_passed_through_verbatim() -> None:
    assistant_message, llm, conversation = _make_single_turn_agent_conversation()
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=StateSnapshotPolicy(
            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS,
            extra_state_builder=lambda _conversation: {"ui": {"active_tab": "plan"}},
        ),
        contexts=[patch_llm(llm, [assistant_message], patch_internal=True)],
    )

    assert isinstance(status, UserMessageRequestStatus)

    agent_span = _single_span(span_recorder, AgentSpecAgentExecutionSpan)
    state_snapshot_events = _span_events(agent_span, AgentSpecStateSnapshotEmitted)

    assert state_snapshot_events[-1].extra_state == {"ui": {"active_tab": "plan"}}
