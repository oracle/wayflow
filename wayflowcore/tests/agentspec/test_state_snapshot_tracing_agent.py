# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from contextlib import AbstractContextManager, ExitStack
from dataclasses import asdict, dataclass
from typing import Any, Sequence, cast

from pyagentspec.adapters.wayflow import AgentSpecLoader
from pyagentspec.agent import Agent as AgentSpecAgent
from pyagentspec.llms import VllmConfig
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
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.serialization import dump_conversation_state

from ..testhelpers.patching import patch_llm
from ..testhelpers.statesnapshots import (
    build_state_snapshot_policy,
    snapshot_message,
    snapshot_status_types,
)


@dataclass(frozen=True)
class ExportedAGUIStateSnapshot:
    conversation_id: str
    snapshot: dict[str, Any]


@dataclass(frozen=True)
class RetrievalPreplan:
    summary: str
    entries: list[str]
    ready_to_proceed: bool


@dataclass(frozen=True)
class RetrievalAssumption:
    text: str
    status: str


@dataclass(frozen=True)
class RetrievalUIState:
    preplan: RetrievalPreplan
    assumptions: list[RetrievalAssumption]


@dataclass(frozen=True)
class RetrievalAgentState:
    thread_id: str
    agent_type: str
    llm_model_name: str
    default_schema: str
    input_document: str
    message_count: int
    last_response: str
    ui: RetrievalUIState


class AGUIStateSnapshotExporter(AgentSpecSpanProcessor):
    def __init__(self) -> None:
        super().__init__()
        self.exported_snapshots: list[ExportedAGUIStateSnapshot] = []

    def on_start(self, span: AgentSpecSpan) -> None:
        return None

    async def on_start_async(self, span: AgentSpecSpan) -> None:
        return None

    def on_end(self, span: AgentSpecSpan) -> None:
        return None

    async def on_end_async(self, span: AgentSpecSpan) -> None:
        return None

    def on_event(self, event: AgentSpecEvent, span: AgentSpecSpan) -> None:
        if not isinstance(event, AgentSpecStateSnapshotEmitted):
            return

        conversation_snapshot = (event.state_snapshot or {}).get("conversation", {})
        self.exported_snapshots.append(
            ExportedAGUIStateSnapshot(
                conversation_id=event.conversation_id,
                snapshot={
                    "messages": conversation_snapshot.get("messages", []),
                    "input": conversation_snapshot.get("inputs", {}).get("input"),
                    "agent_state": (event.extra_state or {}).get("agent_state", {}),
                },
            )
        )

    async def on_event_async(self, event: AgentSpecEvent, span: AgentSpecSpan) -> None:
        self.on_event(event, span)

    def startup(self) -> None:
        return None

    def shutdown(self) -> None:
        return None

    async def startup_async(self) -> None:
        return None

    async def shutdown_async(self) -> None:
        return None


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


_RETRIEVAL_INPUTS = {
    "input": "How many orders last week?",
    "thread_id": "thread-123",
    "agent_type": "planner",
    "llm_model_name": "gpt-5-mini",
    "default_schema": "sales",
    "input_document": "Only use the sales schema and weekly order metrics.",
}

_RETRIEVAL_UI_STATE = RetrievalUIState(
    preplan=RetrievalPreplan(
        summary="Inspect weekly sales orders and answer concisely.",
        entries=[
            "Inspect the active schema",
            "Aggregate last week's orders",
            "Return the final answer",
        ],
        ready_to_proceed=True,
    ),
    assumptions=[
        RetrievalAssumption(text="Use the sales schema only", status="approved"),
        RetrievalAssumption(text="Week boundaries follow UTC", status="auto_approved"),
    ],
)


def _create_retrieval_like_wayflow_agent() -> WayflowAgent:
    agentspec_agent = AgentSpecAgent(
        name="retrieval_agent",
        llm_config=VllmConfig(name="llm", url="http://mock.url", model_id="mock.model"),
        system_prompt="You are a helpful retrieval agent.",
    )
    return cast(WayflowAgent, AgentSpecLoader().load_component(agentspec_agent))


def _build_retrieval_agent_state(
    *,
    conversation_inputs: dict[str, Any],
    message_count: int,
    last_response: str,
) -> RetrievalAgentState:
    return RetrievalAgentState(
        thread_id=conversation_inputs["thread_id"],
        agent_type=conversation_inputs["agent_type"],
        llm_model_name=conversation_inputs["llm_model_name"],
        default_schema=conversation_inputs["default_schema"],
        input_document=conversation_inputs["input_document"],
        message_count=message_count,
        last_response=last_response,
        ui=_RETRIEVAL_UI_STATE,
    )


def _build_retrieval_like_extra_state(conversation) -> dict[str, Any]:
    conversation_snapshot = dump_conversation_state(conversation)["conversation"]
    messages = conversation_snapshot["messages"]
    last_response = next(
        (
            message.get("content")
            for message in reversed(messages)
            if message.get("role") == "assistant" and message.get("content")
        ),
        "",
    )
    return {
        "agent_state": asdict(
            _build_retrieval_agent_state(
                conversation_inputs=conversation.inputs,
                message_count=len(messages),
                last_response=last_response,
            )
        )
    }


def _create_mock_vllm_model(name: str) -> VllmModel:
    return VllmModel(model_id="mock.model", host_port="http://mock.url", name=name)


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


def test_agent_state_snapshots_support_the_agui_retrieval_export_flow() -> None:
    assistant_message = "I checked the warehouse and found 42 orders last week."
    wayflow_agent = _create_retrieval_like_wayflow_agent()
    conversation = wayflow_agent.start_conversation(inputs=_RETRIEVAL_INPUTS)
    conversation.append_user_message(_RETRIEVAL_INPUTS["input"])

    agui_exporter = AGUIStateSnapshotExporter()

    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=_policy(
            StateSnapshotInterval.CONVERSATION_TURNS,
            extra_state_builder=_build_retrieval_like_extra_state,
        ),
        span_processors=[agui_exporter],
        contexts=[patch_llm(wayflow_agent.llm, [assistant_message], patch_internal=True)],
    )

    assert isinstance(status, UserMessageRequestStatus)

    agent_span = _single_span(span_recorder, AgentSpecAgentExecutionSpan)
    assert _events(agent_span, AgentSpecAgentExecutionStart)
    state_snapshot_events = _events(agent_span, AgentSpecStateSnapshotEmitted)
    assert len(state_snapshot_events) == 2

    final_snapshot_event = state_snapshot_events[-1]
    runtime_messages = final_snapshot_event.state_snapshot["conversation"]["messages"]
    expected_agent_state = asdict(
        _build_retrieval_agent_state(
            conversation_inputs=_RETRIEVAL_INPUTS,
            message_count=len(runtime_messages),
            last_response=assistant_message,
        )
    )

    assert final_snapshot_event.conversation_id == conversation.conversation_id
    assert (
        final_snapshot_event.state_snapshot["conversation"]["inputs"]["input"]
        == _RETRIEVAL_INPUTS["input"]
    )
    assert runtime_messages[-1]["content"] == assistant_message
    assert final_snapshot_event.extra_state == {"agent_state": expected_agent_state}

    assert len(agui_exporter.exported_snapshots) == 2
    assert agui_exporter.exported_snapshots[-1] == ExportedAGUIStateSnapshot(
        conversation_id=conversation.conversation_id,
        snapshot={
            "messages": runtime_messages,
            "input": _RETRIEVAL_INPUTS["input"],
            "agent_state": expected_agent_state,
        },
    )


def test_agent_node_turn_state_snapshots_are_mapped_into_the_agent_span_not_llm_spans() -> None:
    assistant_message = "Hello from agent"
    llm = _create_mock_vllm_model("agent")
    agent = WayflowAgent(llm=llm)
    conversation = agent.start_conversation()
    conversation.append_user_message("Hi")
    status, span_recorder = _execute_with_trace(
        conversation,
        state_snapshot_policy=_policy(StateSnapshotInterval.NODE_TURNS),
        contexts=[patch_llm(llm, [assistant_message], patch_internal=True)],
    )

    assert isinstance(status, UserMessageRequestStatus)

    agent_span = _single_span(span_recorder, AgentSpecAgentExecutionSpan)
    state_snapshot_events = _events(agent_span, AgentSpecStateSnapshotEmitted)

    assert len(state_snapshot_events) == 2
    assert [event.state_snapshot["execution"]["curr_iter"] for event in state_snapshot_events] == [
        0,
        1,
    ]
    assert snapshot_status_types(state_snapshot_events) == [None, None]
    assert snapshot_message(state_snapshot_events[-1]) == assistant_message

    llm_spans = _spans(span_recorder, AgentSpecLlmGenerationSpan)
    assert llm_spans
    assert not any(
        isinstance(event, AgentSpecStateSnapshotEmitted)
        for span in llm_spans
        for event in span.events
    )
