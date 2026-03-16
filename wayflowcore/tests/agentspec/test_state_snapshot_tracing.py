# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from typing import Any, cast

import pytest
from pyagentspec.adapters.wayflow import AgentSpecLoader
from pyagentspec.agent import Agent as AgentSpecAgent
from pyagentspec.llms import VllmConfig
from pyagentspec.tracing.events import AgentExecutionEnd as AgentSpecAgentExecutionEnd
from pyagentspec.tracing.events import AgentExecutionStart as AgentSpecAgentExecutionStart
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
from wayflowcore.executors.statesnapshotpolicy import (
    StateSnapshotInterval,
    StateSnapshotPolicy,
)
from wayflowcore.flow import Flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.serialization import dump_conversation_state
from wayflowcore.steps import AgentExecutionStep, CompleteStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.swarm import Swarm
from wayflowcore.tools import ServerTool, ToolRequest

from ..testhelpers.patching import patch_llm

pytestmark = pytest.mark.skipif(
    AgentSpecStateSnapshotEmitted is None,
    reason="Installed pyagentspec does not expose StateSnapshotEmitted",
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


@dataclass(frozen=True)
class ExportedAGUIStateSnapshot:
    conversation_id: str
    snapshot: dict[str, Any]


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


_RETRIEVAL_INPUTS = {
    "input": "How many orders last week?",
    "thread_id": "thread-123",
    "agent_type": "planner",
    "llm_model_name": "gpt-5-mini",
    "default_schema": "sales",
    "input_document": "Only use the sales schema and weekly order metrics.",
}

_RETRIEVAL_UI_STATE = {
    "preplan": {
        "summary": "Inspect weekly sales orders and answer concisely.",
        "entries": [
            "Inspect the active schema",
            "Aggregate last week's orders",
            "Return the final answer",
        ],
        "ready_to_proceed": True,
    },
    "assumptions": [
        {"text": "Use the sales schema only", "status": "approved"},
        {"text": "Week boundaries follow UTC", "status": "auto_approved"},
    ],
}


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
) -> dict[str, Any]:
    return {
        "thread_id": conversation_inputs["thread_id"],
        "agent_type": conversation_inputs["agent_type"],
        "llm_model_name": conversation_inputs["llm_model_name"],
        "default_schema": conversation_inputs["default_schema"],
        "input_document": conversation_inputs["input_document"],
        "message_count": message_count,
        "last_response": last_response,
        "ui": _RETRIEVAL_UI_STATE,
    }


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
        "agent_state": _build_retrieval_agent_state(
            conversation_inputs=conversation.inputs,
            message_count=len(messages),
            last_response=last_response,
        )
    }


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


def _build_swarm_state_snapshot_flow() -> tuple[
    Flow,
    VllmModel,
    list[Message | str],
    VllmModel,
    list[Message | str],
    type[AgentSpecSpan],
    str,
    str,
    type[AgentSpecEvent],
]:
    first_agent_llm = _create_mock_vllm_model("agent1")
    second_agent_llm = _create_mock_vllm_model("agent2")
    first_agent = WayflowAgent(llm=first_agent_llm, name="agent1", description="agent1")
    second_agent = WayflowAgent(llm=second_agent_llm, name="agent2", description="agent2")
    swarm = Swarm(
        first_agent=first_agent,
        relationships=[(first_agent, second_agent), (second_agent, first_agent)],
        name="swarm",
    )

    return (
        Flow.from_steps([AgentExecutionStep(agent=swarm), CompleteStep(name="end")]),
        first_agent_llm,
        [_create_send_message_request("agent2", "Do it"), "agent1 final answer"],
        second_agent_llm,
        ["agent2 answer"],
        AgentSpecSwarmExecutionSpan,
        "agent2 answer",
        "agent1 final answer",
        AgentSpecSwarmExecutionEnd,
    )


def test_flow_state_snapshots_are_mapped_into_the_flow_span_before_flow_end() -> None:
    flow = Flow.from_steps(
        [OutputMessageStep(message_template="Hello"), CompleteStep(name="end")],
        step_names=["single_step", "end"],
    )
    conversation = flow.start_conversation()
    listener = AgentSpecEventListener()
    span_recorder = SnapshotSpanRecorder()

    with AgentSpecTrace(span_processors=[span_recorder]):
        with register_event_listeners([listener]):
            status = conversation.execute(
                state_snapshot_policy=StateSnapshotPolicy(
                    state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS,
                    extra_state_builder=lambda _conversation: {"ui": {"active_tab": "plan"}},
                )
            )

    assert isinstance(status, FinishedStatus)

    flow_spans = [
        span for span in span_recorder.started_spans if isinstance(span, AgentSpecFlowExecutionSpan)
    ]
    assert len(flow_spans) == 1
    flow_span = flow_spans[0]
    flow_events = flow_span.events

    assert any(isinstance(event, AgentSpecFlowExecutionStart) for event in flow_events)
    flow_end_event = next(
        event for event in flow_events if isinstance(event, AgentSpecFlowExecutionEnd)
    )
    state_snapshot_events = [
        event for event in flow_events if isinstance(event, AgentSpecStateSnapshotEmitted)
    ]

    # From an Agent Spec consumer point of view, the flow span should expose the
    # opening and closing checkpoints, and the closing checkpoint must still
    # appear before the terminal flow-end event.
    assert len(state_snapshot_events) == 2
    final_snapshot_event = state_snapshot_events[-1]
    assert final_snapshot_event.conversation_id == conversation.conversation_id
    assert final_snapshot_event.state_snapshot["conversation"]["messages"][-1]["content"] == "Hello"
    assert final_snapshot_event.extra_state == {"ui": {"active_tab": "plan"}}
    assert flow_events.index(final_snapshot_event) < flow_events.index(flow_end_event)
    assert flow_span.end_time is not None
    assert final_snapshot_event.timestamp <= flow_span.end_time
    assert "variable_state" not in final_snapshot_event.model_dump(mask_sensitive_information=False)
    assert flow_span in span_recorder.ended_spans


def test_off_policy_does_not_bridge_state_snapshots_into_agent_spec_spans() -> None:
    flow = Flow.from_steps(
        [OutputMessageStep(message_template="Hello"), CompleteStep(name="end")],
        step_names=["single_step", "end"],
    )
    conversation = flow.start_conversation()
    listener = AgentSpecEventListener()
    span_recorder = SnapshotSpanRecorder()

    with AgentSpecTrace(span_processors=[span_recorder]):
        with register_event_listeners([listener]):
            status = conversation.execute(
                state_snapshot_policy=StateSnapshotPolicy(
                    state_snapshot_interval=StateSnapshotInterval.OFF
                )
            )

    assert isinstance(status, FinishedStatus)

    flow_spans = [
        span for span in span_recorder.started_spans if isinstance(span, AgentSpecFlowExecutionSpan)
    ]
    assert len(flow_spans) == 1
    flow_events = flow_spans[0].events

    assert any(isinstance(event, AgentSpecFlowExecutionStart) for event in flow_events)
    assert any(isinstance(event, AgentSpecFlowExecutionEnd) for event in flow_events)
    assert not any(isinstance(event, AgentSpecStateSnapshotEmitted) for event in flow_events)


def test_agent_state_snapshots_support_the_agui_retrieval_export_flow() -> None:
    assistant_message = "I checked the warehouse and found 42 orders last week."
    wayflow_agent = _create_retrieval_like_wayflow_agent()
    conversation = wayflow_agent.start_conversation(inputs=_RETRIEVAL_INPUTS)
    conversation.append_user_message(_RETRIEVAL_INPUTS["input"])

    listener = AgentSpecEventListener()
    span_recorder = SnapshotSpanRecorder()
    agui_exporter = AGUIStateSnapshotExporter()

    with patch_llm(wayflow_agent.llm, [assistant_message], patch_internal=True):
        with AgentSpecTrace(span_processors=[span_recorder, agui_exporter]):
            with register_event_listeners([listener]):
                status = conversation.execute(
                    state_snapshot_policy=StateSnapshotPolicy(
                        state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS,
                        extra_state_builder=_build_retrieval_like_extra_state,
                    )
                )

    assert isinstance(status, UserMessageRequestStatus)

    agent_spans = [
        span
        for span in span_recorder.started_spans
        if isinstance(span, AgentSpecAgentExecutionSpan)
    ]
    assert len(agent_spans) == 1
    agent_span = agent_spans[0]
    agent_events = agent_span.events

    assert any(isinstance(event, AgentSpecAgentExecutionStart) for event in agent_events)
    agent_end_event = next(
        event for event in agent_events if isinstance(event, AgentSpecAgentExecutionEnd)
    )
    state_snapshot_events = [
        event for event in agent_events if isinstance(event, AgentSpecStateSnapshotEmitted)
    ]
    assert len(state_snapshot_events) == 2

    final_snapshot_event = state_snapshot_events[-1]
    runtime_messages = final_snapshot_event.state_snapshot["conversation"]["messages"]
    expected_agent_state = _build_retrieval_agent_state(
        conversation_inputs=_RETRIEVAL_INPUTS,
        message_count=len(runtime_messages),
        last_response=assistant_message,
    )

    # This retrieval example is the main product use-case: a downstream AG-UI
    # style exporter should be able to reconstruct the latest UI-facing state
    # directly from the final snapshot event on the agent execution span.
    assert final_snapshot_event.conversation_id == conversation.conversation_id
    assert (
        final_snapshot_event.state_snapshot["conversation"]["inputs"]["input"]
        == _RETRIEVAL_INPUTS["input"]
    )
    assert runtime_messages[-1]["content"] == assistant_message
    assert final_snapshot_event.extra_state == {"agent_state": expected_agent_state}
    assert agent_events.index(final_snapshot_event) < agent_events.index(agent_end_event)

    assert len(agui_exporter.exported_snapshots) == 2
    assert agui_exporter.exported_snapshots[-1] == ExportedAGUIStateSnapshot(
        conversation_id=conversation.conversation_id,
        snapshot={
            "messages": runtime_messages,
            "input": _RETRIEVAL_INPUTS["input"],
            "agent_state": expected_agent_state,
        },
    )


@pytest.mark.parametrize(
    "flow_builder",
    [
        pytest.param(_build_swarm_state_snapshot_flow, id="swarm"),
    ],
)
def test_nested_multi_agent_state_snapshots_follow_conversation_ownership_boundaries(
    flow_builder,
) -> None:
    (
        flow,
        primary_llm,
        primary_outputs,
        secondary_llm,
        secondary_outputs,
        expected_multi_agent_span_class,
        expected_child_message,
        expected_parent_message,
        expected_multi_agent_end_event_class,
    ) = flow_builder()
    conversation = flow.start_conversation()
    conversation.append_user_message("dummy")

    listener = AgentSpecEventListener()
    span_recorder = SnapshotSpanRecorder()

    with patch_llm(primary_llm, primary_outputs, patch_internal=True):
        with patch_llm(secondary_llm, secondary_outputs, patch_internal=True):
            with AgentSpecTrace(span_processors=[span_recorder]):
                with register_event_listeners([listener]):
                    status = conversation.execute(
                        state_snapshot_policy=StateSnapshotPolicy(
                            state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
                        )
                    )

    assert isinstance(status, UserMessageRequestStatus)

    flow_spans = [
        span for span in span_recorder.started_spans if isinstance(span, AgentSpecFlowExecutionSpan)
    ]
    assert len(flow_spans) == 1
    flow_span = flow_spans[0]
    flow_snapshot_events = [
        event for event in flow_span.events if isinstance(event, AgentSpecStateSnapshotEmitted)
    ]
    assert len(flow_snapshot_events) == 2
    assert [event.conversation_id for event in flow_snapshot_events] == [
        conversation.conversation_id,
        conversation.conversation_id,
    ]
    assert (
        flow_snapshot_events[-1].state_snapshot["conversation"]["messages"][-1]["content"]
        == expected_parent_message
    )

    multi_agent_spans = [
        span
        for span in span_recorder.started_spans
        if isinstance(span, expected_multi_agent_span_class)
    ]
    assert len(multi_agent_spans) == 1
    multi_agent_span = multi_agent_spans[0]
    multi_agent_snapshot_events = [
        event
        for event in multi_agent_span.events
        if isinstance(event, AgentSpecStateSnapshotEmitted)
    ]
    multi_agent_end_event = next(
        event
        for event in multi_agent_span.events
        if isinstance(event, expected_multi_agent_end_event_class)
    )
    parent_multi_agent_conversation_id = multi_agent_snapshot_events[0].conversation_id

    # The parent multi-agent conversation brackets both child turns. It keeps a
    # single conversation id while the manager/main-thread agent and the
    # delegated child each emit snapshots on their own agent execution spans.
    assert [event.conversation_id for event in multi_agent_snapshot_events] == [
        parent_multi_agent_conversation_id,
        parent_multi_agent_conversation_id,
        parent_multi_agent_conversation_id,
        parent_multi_agent_conversation_id,
        parent_multi_agent_conversation_id,
        parent_multi_agent_conversation_id,
    ]
    assert [
        (
            event.state_snapshot["execution"]["status"]["type"]
            if event.state_snapshot["execution"]["status"] is not None
            else None
        )
        for event in multi_agent_snapshot_events
    ] == [
        None,
        "ToolRequestStatus",
        None,
        "UserMessageRequestStatus",
        None,
        "UserMessageRequestStatus",
    ]
    assert (
        multi_agent_snapshot_events[4].state_snapshot["conversation"]["messages"][-1]["content"]
        == expected_child_message
    )
    assert (
        multi_agent_snapshot_events[-1].state_snapshot["conversation"]["messages"][-1]["content"]
        == expected_parent_message
    )
    assert multi_agent_span.events.index(
        multi_agent_snapshot_events[-1]
    ) < multi_agent_span.events.index(multi_agent_end_event)

    agent_snapshot_spans = [
        span
        for span in span_recorder.started_spans
        if isinstance(span, AgentSpecAgentExecutionSpan)
        and any(isinstance(event, AgentSpecStateSnapshotEmitted) for event in span.events)
    ]
    assert len(agent_snapshot_spans) == 3
    agent_snapshot_events_by_conversation_id: dict[str, list[AgentSpecStateSnapshotEmitted]] = {}
    for agent_span in agent_snapshot_spans:
        snapshot_events = [
            event for event in agent_span.events if isinstance(event, AgentSpecStateSnapshotEmitted)
        ]
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
    assert [
        (
            event.state_snapshot["execution"]["status"]["type"]
            if event.state_snapshot["execution"]["status"] is not None
            else None
        )
        for event in manager_thread_snapshot_events
    ] == [
        None,
        "ToolRequestStatus",
        None,
        "UserMessageRequestStatus",
    ]
    assert (
        manager_thread_snapshot_events[2].state_snapshot["conversation"]["messages"][-1]["content"]
        == expected_child_message
    )
    assert (
        manager_thread_snapshot_events[-1].state_snapshot["conversation"]["messages"][-1]["content"]
        == expected_parent_message
    )
    assert [
        (
            event.state_snapshot["execution"]["status"]["type"]
            if event.state_snapshot["execution"]["status"] is not None
            else None
        )
        for event in delegated_agent_snapshot_events
    ] == [None, "UserMessageRequestStatus"]
    assert (
        delegated_agent_snapshot_events[-1].state_snapshot["conversation"]["messages"][-1][
            "content"
        ]
        == expected_child_message
    )

    tool_spans = [
        span for span in span_recorder.started_spans if isinstance(span, AgentSpecToolExecutionSpan)
    ]
    assert tool_spans
    assert not any(
        isinstance(event, AgentSpecStateSnapshotEmitted)
        for span in tool_spans
        for event in span.events
    )

    assert flow_span in span_recorder.ended_spans
    assert multi_agent_span in span_recorder.ended_spans


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
    listener = AgentSpecEventListener()
    span_recorder = SnapshotSpanRecorder()

    with AgentSpecTrace(span_processors=[span_recorder]):
        with register_event_listeners([listener]):
            with pytest.raises(RuntimeError, match="boom"):
                conversation.execute(
                    state_snapshot_policy=StateSnapshotPolicy(
                        state_snapshot_interval=StateSnapshotInterval.CONVERSATION_TURNS
                    )
                )

    flow_spans = [
        span for span in span_recorder.started_spans if isinstance(span, AgentSpecFlowExecutionSpan)
    ]
    assert len(flow_spans) == 1
    flow_span = flow_spans[0]
    state_snapshot_events = [
        event for event in flow_span.events if isinstance(event, AgentSpecStateSnapshotEmitted)
    ]

    assert len(state_snapshot_events) == 1
    assert state_snapshot_events[0].state_snapshot["execution"]["status"] is None
    assert flow_span in span_recorder.ended_spans
