# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import asyncio
from typing import Annotated, List, Tuple, cast

import pytest
from pyagentspec.agent import Agent as AgentSpecAgent
from pyagentspec.flows.edges import ControlFlowEdge
from pyagentspec.flows.flow import Flow as AgentSpecFlow
from pyagentspec.flows.nodes import EndNode, LlmNode, StartNode, ToolNode
from pyagentspec.llms import VllmConfig
from pyagentspec.property import StringProperty as AgentSpecStringProperty
from pyagentspec.tools import ServerTool as AgentSpecServerTool
from pyagentspec.tracing.events import AgentExecutionEnd as AgentSpecAgentExecutionEnd
from pyagentspec.tracing.events import AgentExecutionStart as AgentSpecAgentExecutionStart
from pyagentspec.tracing.events import Event as AgentSpecEvent
from pyagentspec.tracing.events import FlowExecutionEnd as AgentSpecFlowExecutionEnd
from pyagentspec.tracing.events import FlowExecutionStart as AgentSpecFlowExecutionStart
from pyagentspec.tracing.events import (
    LlmGenerationChunkReceived as AgentSpecLlmGenerationChunkReceived,
)
from pyagentspec.tracing.events import LlmGenerationRequest as AgentSpecLlmGenerationRequest
from pyagentspec.tracing.events import LlmGenerationResponse as AgentSpecLlmGenerationResponse
from pyagentspec.tracing.events import NodeExecutionEnd as AgentSpecNodeExecutionEnd
from pyagentspec.tracing.events import NodeExecutionStart as AgentSpecNodeExecutionStart
from pyagentspec.tracing.events import ToolExecutionRequest as AgentSpecToolExecutionRequest
from pyagentspec.tracing.events import ToolExecutionResponse as AgentSpecToolExecutionResponse
from pyagentspec.tracing.spanprocessor import SpanProcessor as AgentSpecSpanProcessor
from pyagentspec.tracing.spans import AgentExecutionSpan as AgentSpecAgentExecutionSpan
from pyagentspec.tracing.spans import FlowExecutionSpan as AgentSpecFlowExecutionSpan
from pyagentspec.tracing.spans import LlmGenerationSpan as AgentSpecLlmGenerationSpan
from pyagentspec.tracing.spans import NodeExecutionSpan as AgentSpecNodeExecutionSpan
from pyagentspec.tracing.spans import Span as AgentSpecSpan
from pyagentspec.tracing.spans import ToolExecutionSpan as AgentSpecToolExecutionSpan
from pyagentspec.tracing.trace import Trace as AgentSpecTrace

from wayflowcore import Agent, Flow
from wayflowcore._utils._templating_helpers import render_template
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.agentspec.tracing import AgentSpecEventListener, dump_tracing_model
from wayflowcore.events.eventlistener import register_event_listeners
from wayflowcore.executors.executionstatus import (
    ExecutionStatus,
    FinishedStatus,
    UserMessageRequestStatus,
)
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.serialization import deserialize, serialize
from wayflowcore.steps import CompleteStep, ConstantValuesStep, InputMessageStep, StartStep
from wayflowcore.tools import tool

from ..conftest import mock_llm
from ..testhelpers.patching import patch_llm


class DummyAgentSpecSpanProcessor(AgentSpecSpanProcessor):

    def __init__(self) -> None:
        super().__init__()
        self.started_up_async = False
        self.shut_down_async = False
        self.started_up = False
        self.shut_down = False
        self.starts: List[AgentSpecSpan] = []
        self.ends: List[AgentSpecSpan] = []
        self.events: List[Tuple[AgentSpecEvent, AgentSpecSpan]] = []
        self.starts_async: List[AgentSpecSpan] = []
        self.ends_async: List[AgentSpecSpan] = []
        self.events_async: List[Tuple[AgentSpecEvent, AgentSpecSpan]] = []

    def on_start(self, span: AgentSpecSpan) -> None:
        self.starts.append(span)

    async def on_start_async(self, span: AgentSpecSpan) -> None:
        self.starts_async.append(span)

    def on_end(self, span: AgentSpecSpan) -> None:
        self.ends.append(span)

    async def on_end_async(self, span: AgentSpecSpan) -> None:
        self.ends_async.append(span)

    def on_event(self, event: AgentSpecEvent, span: AgentSpecSpan) -> None:
        self.events.append((event, span))

    async def on_event_async(self, event: AgentSpecEvent, span: AgentSpecSpan) -> None:
        self.events_async.append((event, span))

    def startup(self) -> None:
        self.started_up = True

    def shutdown(self) -> None:
        self.shut_down = True

    async def startup_async(self) -> None:
        self.started_up_async = True

    async def shutdown_async(self) -> None:
        self.shut_down_async = True


@pytest.fixture
def wayflow_flow() -> Flow:
    start_node = StartNode(name="start")
    end_node = EndNode(name="end")
    llm_node = LlmNode(
        name="llm_node",
        llm_config=VllmConfig(name="llm", url="http://mock.url", model_id="mock.model"),
        prompt_template="Answer with a single brand of a fast Italian car.",
    )

    tool_node = ToolNode(
        name="tool_node",
        tool=AgentSpecServerTool(
            name="tool",
            description="tool desc",
            inputs=[AgentSpecStringProperty(title="tool_input", default="input")],
            outputs=[AgentSpecStringProperty(title="tool_output")],
        ),
    )
    ps_flow = AgentSpecFlow(
        name="flow",
        start_node=start_node,
        nodes=[start_node, end_node, llm_node, tool_node],
        control_flow_connections=[
            ControlFlowEdge(name="c1", from_node=start_node, to_node=llm_node),
            ControlFlowEdge(name="c2", from_node=llm_node, to_node=tool_node),
            ControlFlowEdge(name="c3", from_node=tool_node, to_node=end_node),
        ],
    )
    return cast(
        Flow,
        AgentSpecLoader(tool_registry={"tool": lambda tool_input: "output"}).load_component(
            ps_flow
        ),
    )


@pytest.fixture
def wayflow_agent() -> Agent:
    ps_agent = AgentSpecAgent(
        name="agent",
        llm_config=VllmConfig(name="llm", url="http://mock.url", model_id="mock.model"),
        system_prompt="You are a helpful assistant.",
    )
    return cast(Agent, AgentSpecLoader().load_component(ps_agent))


def test_agentspec_agent_raises_correct_events(wayflow_agent: Agent):

    # Run the agent attaching an AgentSpecEventListener as context manager
    listener = AgentSpecEventListener()
    span_processor = DummyAgentSpecSpanProcessor()
    conv = wayflow_agent.start_conversation()
    with patch_llm(wayflow_agent.llm, ["Hello from agent"], patch_internal=True):
        with AgentSpecTrace(span_processors=[span_processor]) as trace:
            with register_event_listeners([listener]):
                status = conv.execute()

    # Sanity check on execution
    assert isinstance(status, UserMessageRequestStatus)
    assert span_processor.started_up and span_processor.shut_down

    # Ensure that the right PyAgentSpec Events and Spans are activated and emitted
    assert all(any(start is end for end in span_processor.ends) for start in span_processor.starts)
    spans = span_processor.starts

    # Agent span with start/end events
    agent_spans = [s for s in spans if isinstance(s, AgentSpecAgentExecutionSpan)]
    assert agent_spans, "Expected at least one AgentExecutionSpan"
    agent_events = agent_spans[0].events
    assert any(isinstance(e, AgentSpecAgentExecutionStart) for e in agent_events)
    assert any(isinstance(e, AgentSpecAgentExecutionEnd) for e in agent_events)

    # LLM generation span with request/response events
    llm_spans = [s for s in spans if isinstance(s, AgentSpecLlmGenerationSpan)]
    assert llm_spans, "Expected at least one LlmGenerationSpan"
    llm_events = llm_spans[0].events
    assert any(isinstance(e, AgentSpecLlmGenerationRequest) for e in llm_events)
    assert any(isinstance(e, AgentSpecLlmGenerationResponse) for e in llm_events)
    assert any(isinstance(e, AgentSpecLlmGenerationChunkReceived) for e in llm_events)
    response_event = next(e for e in llm_events if isinstance(e, AgentSpecLlmGenerationResponse))
    assert response_event.content == "Hello from agent"
    assert all(e.request_id == response_event.request_id for e in llm_events)


def test_agentspec_agent_async_raises_correct_events(wayflow_agent: Agent):

    # Run the agent attaching an AgentSpecEventListener as context manager
    listener = AgentSpecEventListener()
    span_processor = DummyAgentSpecSpanProcessor()

    async def run() -> ExecutionStatus:
        conv = wayflow_agent.start_conversation()
        with patch_llm(wayflow_agent.llm, ["Hello from agent"], patch_internal=True):
            async with AgentSpecTrace(span_processors=[span_processor]) as trace:
                with register_event_listeners([listener]):
                    status_ = await conv.execute_async()
        return status_

    status = asyncio.run(run())
    # Sanity check on execution
    assert isinstance(status, UserMessageRequestStatus)
    assert span_processor.started_up_async and span_processor.shut_down_async

    # Ensure that the right PyAgentSpec Events and Spans are activated and emitted
    assert all(any(start is end for end in span_processor.ends) for start in span_processor.starts)
    spans = span_processor.starts

    # Agent span with start/end events
    agent_spans = [s for s in spans if isinstance(s, AgentSpecAgentExecutionSpan)]
    assert agent_spans, "Expected at least one AgentExecutionSpan"
    agent_events = agent_spans[0].events
    assert any(isinstance(e, AgentSpecAgentExecutionStart) for e in agent_events)
    assert any(isinstance(e, AgentSpecAgentExecutionEnd) for e in agent_events)

    # LLM generation span with request/response events
    llm_spans = [s for s in spans if isinstance(s, AgentSpecLlmGenerationSpan)]
    assert llm_spans, "Expected at least one LlmGenerationSpan"
    llm_events = llm_spans[0].events
    assert any(isinstance(e, AgentSpecLlmGenerationRequest) for e in llm_events)
    assert any(isinstance(e, AgentSpecLlmGenerationResponse) for e in llm_events)
    assert any(isinstance(e, AgentSpecLlmGenerationChunkReceived) for e in llm_events)
    response_event = next(e for e in llm_events if isinstance(e, AgentSpecLlmGenerationResponse))
    assert response_event.content == "Hello from agent"
    assert all(e.request_id == response_event.request_id for e in llm_events)


def test_agentspec_flow_raises_correct_events(wayflow_flow: Flow):

    # Retrieve the wayflow LLM step to patch its LLM calls
    llm_step = wayflow_flow.steps["llm_node"]

    # Run the flow attaching an AgentSpecEventListener as context manager
    listener = AgentSpecEventListener()
    span_processor = DummyAgentSpecSpanProcessor()
    conv = wayflow_flow.start_conversation()

    with patch_llm(llm_step.llm, ["Ferrari"], patch_internal=True):
        with AgentSpecTrace(span_processors=[span_processor]) as trace:
            with register_event_listeners([listener]):
                status = conv.execute()

    # Sanity check on execution
    assert isinstance(status, FinishedStatus)
    assert span_processor.started_up and span_processor.shut_down

    # - Ensure that the right PyAgentSpec Events and Spans are activated and emitted
    assert all(any(start is end for end in span_processor.ends) for start in span_processor.starts)
    spans = span_processor.starts

    # Flow span with start/end events
    flow_spans = [s for s in spans if isinstance(s, AgentSpecFlowExecutionSpan)]
    assert flow_spans, "Expected at least one FlowExecutionSpan"
    flow_events = flow_spans[0].events
    assert any(isinstance(e, AgentSpecFlowExecutionStart) for e in flow_events)
    assert any(isinstance(e, AgentSpecFlowExecutionEnd) for e in flow_events)

    # Node (step) span with start/end events
    node_spans = [s for s in spans if isinstance(s, AgentSpecNodeExecutionSpan)]
    assert node_spans, "Expected at least one NodeExecutionSpan"
    node_events = node_spans[0].events
    assert any(isinstance(e, AgentSpecNodeExecutionStart) for e in node_events)
    assert any(isinstance(e, AgentSpecNodeExecutionEnd) for e in node_events)

    # Tool span with start/end events
    node_spans = [s for s in spans if isinstance(s, AgentSpecToolExecutionSpan)]
    assert node_spans, "Expected at least one ToolExecutionSpan"
    tool_events = node_spans[0].events
    assert any(isinstance(e, AgentSpecToolExecutionRequest) for e in tool_events)
    assert any(isinstance(e, AgentSpecToolExecutionResponse) for e in tool_events)
    request_event = next(e for e in tool_events if isinstance(e, AgentSpecToolExecutionRequest))
    assert request_event.inputs == {"tool_input": "input"}
    response_event = next(e for e in tool_events if isinstance(e, AgentSpecToolExecutionResponse))
    assert response_event.outputs == {"tool_output": "output"}
    assert request_event.request_id == response_event.request_id

    # LLM generation span with request/response events
    llm_spans = [s for s in spans if isinstance(s, AgentSpecLlmGenerationSpan)]
    assert llm_spans, "Expected at least one LlmGenerationSpan"
    llm_events = llm_spans[0].events
    assert any(isinstance(e, AgentSpecLlmGenerationRequest) for e in llm_events)
    assert any(isinstance(e, AgentSpecLlmGenerationResponse) for e in llm_events)
    response_event = next(e for e in llm_events if isinstance(e, AgentSpecLlmGenerationResponse))
    assert response_event.content == "Ferrari"
    assert all(e.request_id == response_event.request_id for e in llm_events)


def test_agentspec_flow_end_uses_last_executed_step_when_flow_ends_on_none_transition():
    flow = Flow.from_steps(
        [
            StartStep(name="start"),
            ConstantValuesStep(name="finish", constant_values={}),
        ]
    )

    listener = AgentSpecEventListener()
    span_processor = DummyAgentSpecSpanProcessor()

    with AgentSpecTrace(span_processors=[span_processor]):
        with register_event_listeners([listener]):
            status = flow.start_conversation().execute()

    assert isinstance(status, FinishedStatus)
    assert status.complete_step_name is None
    assert status.final_step_name == "finish"

    flow_span = next(s for s in span_processor.starts if isinstance(s, AgentSpecFlowExecutionSpan))
    end_event = next(e for e in flow_span.events if isinstance(e, AgentSpecFlowExecutionEnd))
    assert end_event.branch_selected == "finish"


def test_finished_status_serialization_round_trip_keeps_final_step_name():
    status = FinishedStatus(
        output_values={"value": "ok"},
        complete_step_name=None,
        _final_step_name="finish",
        _conversation_id="conv-id",
    )

    round_tripped_status = deserialize(FinishedStatus, serialize(status))

    assert isinstance(round_tripped_status, FinishedStatus)
    assert round_tripped_status.complete_step_name is None
    assert round_tripped_status.final_step_name == "finish"
    assert round_tripped_status.output_values == {"value": "ok"}


def test_finished_status_deserialization_supports_legacy_final_step_name():
    status = FinishedStatus(
        output_values={"value": "ok"},
        complete_step_name=None,
        _final_step_name="finish",
        _conversation_id="conv-id",
    )

    legacy_serialized_status = serialize(status).replace("_final_step_name", "final_step_name")

    round_tripped_status = deserialize(FinishedStatus, legacy_serialized_status)

    assert isinstance(round_tripped_status, FinishedStatus)
    assert round_tripped_status.final_step_name == "finish"


def test_dump_tracing_model_supports_plugin_components():
    flow = Flow.from_steps(
        [
            StartStep(name="start"),
            InputMessageStep(name="ask_name", message_template="What is your name?"),
            CompleteStep(name="end"),
        ]
    )

    event = AgentSpecFlowExecutionStart(flow=AgentSpecExporter().to_component(flow), inputs={})

    with pytest.raises(Exception, match="PluginInputMessageNode"):
        event.model_dump()

    dumped_event = dump_tracing_model(event)
    assert dumped_event["flow"]["nodes"][1]["component_type"] == "PluginInputMessageNode"

    listener = AgentSpecEventListener()
    dumped_with_listener = listener.dump_tracing_model(event)
    assert dumped_with_listener["flow"]["nodes"][1]["component_type"] == "PluginInputMessageNode"


def test_agentspec_tracing_supports_managerworkers_template_transform():
    llm = mock_llm()

    @tool
    def say_hello(user_name: Annotated[str, "Name of the user"]) -> str:
        """Return a greeting."""
        return f"Hello {user_name}!"

    manager_agent = Agent(name="manager", description="manager agent", tools=[say_hello], llm=llm)
    worker = Agent(name="worker", description="worker", llm=llm)
    group = ManagerWorkers(workers=[worker], group_manager=manager_agent)

    listener = AgentSpecEventListener()
    span_processor = DummyAgentSpecSpanProcessor()
    conversation = group.start_conversation()
    conversation.append_user_message("Dummy")

    with patch_llm(
        llm,
        outputs=[
            Message(
                render_template(
                    """
{{thoughts}}

{"name": {{tool_name}}, "parameters": {{tool_params}}}
""".strip(),
                    inputs=dict(
                        thoughts="",
                        tool_name="say_hello",
                        tool_params={"user_name": "Iris"},
                    ),
                ),
                message_type=MessageType.AGENT,
            ),
            "Dummy",
        ],
        patch_internal=True,
    ):
        with AgentSpecTrace(span_processors=[span_processor]):
            with register_event_listeners([listener]):
                status = conversation.execute()

    assert isinstance(status, UserMessageRequestStatus)
    assert any(isinstance(span, AgentSpecAgentExecutionSpan) for span in span_processor.starts)


def test_agentspec_flow_async_raises_correct_events(wayflow_flow: Flow):

    # Retrieve the wayflow LLM step to patch its LLM calls
    llm_step = wayflow_flow.steps["llm_node"]

    # Run the flow attaching an AgentSpecEventListener as context manager
    listener = AgentSpecEventListener()
    span_processor = DummyAgentSpecSpanProcessor()

    async def run() -> ExecutionStatus:
        conv = wayflow_flow.start_conversation()
        with patch_llm(llm_step.llm, ["Ferrari"], patch_internal=True):
            async with AgentSpecTrace(span_processors=[span_processor]) as trace:
                with register_event_listeners([listener]):
                    status_ = await conv.execute_async()
        return status_

    status = asyncio.run(run())
    # Sanity check on execution
    assert isinstance(status, FinishedStatus)
    assert span_processor.started_up_async and span_processor.shut_down_async

    # - Ensure that the right PyAgentSpec Events and Spans are activated and emitted
    assert all(any(start is end for end in span_processor.ends) for start in span_processor.starts)
    spans = span_processor.starts

    # Flow span with start/end events
    flow_spans = [s for s in spans if isinstance(s, AgentSpecFlowExecutionSpan)]
    assert flow_spans, "Expected at least one FlowExecutionSpan"
    flow_events = flow_spans[0].events
    assert any(isinstance(e, AgentSpecFlowExecutionStart) for e in flow_events)
    assert any(isinstance(e, AgentSpecFlowExecutionEnd) for e in flow_events)

    # Node (step) span with start/end events
    node_spans = [s for s in spans if isinstance(s, AgentSpecNodeExecutionSpan)]
    assert node_spans, "Expected at least one NodeExecutionSpan"
    node_events = node_spans[0].events
    assert any(isinstance(e, AgentSpecNodeExecutionStart) for e in node_events)
    assert any(isinstance(e, AgentSpecNodeExecutionEnd) for e in node_events)

    # Tool span with start/end events
    node_spans = [s for s in spans if isinstance(s, AgentSpecToolExecutionSpan)]
    assert node_spans, "Expected at least one ToolExecutionSpan"
    tool_events = node_spans[0].events
    assert any(isinstance(e, AgentSpecToolExecutionRequest) for e in tool_events)
    assert any(isinstance(e, AgentSpecToolExecutionResponse) for e in tool_events)
    request_event = next(e for e in tool_events if isinstance(e, AgentSpecToolExecutionRequest))
    assert request_event.inputs == {"tool_input": "input"}
    response_event = next(e for e in tool_events if isinstance(e, AgentSpecToolExecutionResponse))
    assert response_event.outputs == {"tool_output": "output"}
    assert request_event.request_id == response_event.request_id

    # LLM generation span with request/response events
    llm_spans = [s for s in spans if isinstance(s, AgentSpecLlmGenerationSpan)]
    assert llm_spans, "Expected at least one LlmGenerationSpan"
    llm_events = llm_spans[0].events
    assert any(isinstance(e, AgentSpecLlmGenerationRequest) for e in llm_events)
    assert any(isinstance(e, AgentSpecLlmGenerationResponse) for e in llm_events)
    response_event = next(e for e in llm_events if isinstance(e, AgentSpecLlmGenerationResponse))
    assert response_event.content == "Ferrari"
    assert all(e.request_id == response_event.request_id for e in llm_events)
