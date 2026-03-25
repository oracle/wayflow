# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from copy import deepcopy

from wayflowcore.agent import Agent
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.events.event import Event, ToolExecutionResultEvent
from wayflowcore.events.eventlistener import EventListener, register_event_listeners
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import LlmModelFactory
from wayflowcore.serialization import autodeserialize, serialize
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import ToolOutputArtifact, ToolOutputType, ToolRequest, ToolResult, tool
from wayflowcore.tools.tools import TOOL_OUTPUT_TYPE_METADATA_KEY

from ...conftest import VLLM_MODEL_CONFIG
from ...testhelpers.dummy import DummyModel
from ...testhelpers.patching import patch_llm


@tool(description_mode="only_docstring", output_type=ToolOutputType.CONTENT_AND_ARTIFACT)
def analyze_logs(topic: str) -> tuple[str, str]:
    """Summarize a log file and attach the full text as an artifact."""

    return f"summary:{topic}", f"full-log:{topic}"


class CaptureArtifacts(EventListener):

    def __init__(self):
        self.artifacts = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ToolExecutionResultEvent):
            self.artifacts.extend(event.tool_result.artifacts)


def test_agent_conversation_exposes_artifacts_in_events_and_messages():
    llm = DummyModel()
    agent = Agent(
        llm=llm,
        custom_instruction="Use tools when needed.",
        tools=[analyze_logs],
    )
    tool_request = ToolRequest(
        name=analyze_logs.name,
        args={"topic": "app"},
        tool_request_id="tool_call_1",
    )
    listener = CaptureArtifacts()

    with patch_llm(llm, outputs=[[tool_request], "done"]), register_event_listeners([listener]):
        conv = agent.start_conversation()
        conv.append_user_message("Analyze the app logs.")
        conv.execute()

    tool_result_message = next(
        message
        for message in conv.get_messages()
        if message.tool_result is not None
        and message.tool_result.tool_request_id == tool_request.tool_request_id
    )
    assert tool_result_message.tool_result is not None
    assert tool_result_message.tool_result.content == "summary:app"
    assert len(tool_result_message.tool_result.artifacts) == 1
    assert tool_result_message.tool_result.artifacts[0].data == "full-log:app"
    assert listener.artifacts == list(tool_result_message.tool_result.artifacts)


def test_flow_execution_exposes_artifacts_via_events():
    flow = create_single_step_flow(ToolExecutionStep(tool=analyze_logs))
    listener = CaptureArtifacts()

    with register_event_listeners([listener]):
        conv = flow.start_conversation(inputs={"topic": "flow"})
        conv.execute()

    assert len(listener.artifacts) == 1
    assert listener.artifacts[0].data == "full-log:flow"


def test_conversation_serialization_drops_artifacts():
    llm = LlmModelFactory.from_config(deepcopy(VLLM_MODEL_CONFIG))
    agent = Agent(
        llm=llm,
        custom_instruction="Use tools when needed.",
    )
    conversation = agent.start_conversation()
    conversation.message_list.append_message(
        Message(
            message_type=MessageType.TOOL_RESULT,
            tool_result=ToolResult(
                content="summary",
                tool_request_id="tool_call_1",
                artifacts=(
                    ToolOutputArtifact(
                        name="artifact.txt",
                        mime_type="text/plain",
                        data="artifact payload",
                    ),
                ),
            ),
        )
    )

    serialized_conversation = serialize(conversation)

    assert "artifact payload" not in serialized_conversation
    assert "artifact.txt" not in serialized_conversation
    assert '"artifacts"' not in serialized_conversation

    deserialized_conversation = autodeserialize(serialized_conversation)
    messages = deserialized_conversation.get_messages()
    assert messages[-1].tool_result is not None
    assert messages[-1].tool_result.content == "summary"
    assert messages[-1].tool_result.artifacts == ()


def test_agentspec_export_and_load_preserve_server_tool_output_type_metadata():
    llm = LlmModelFactory.from_config(deepcopy(VLLM_MODEL_CONFIG))
    agent = Agent(
        llm=llm,
        custom_instruction="Use tools when needed.",
        tools=[analyze_logs],
    )

    serialized_agent = AgentSpecExporter().to_json(agent)

    assert TOOL_OUTPUT_TYPE_METADATA_KEY in serialized_agent
    assert ToolOutputType.CONTENT_AND_ARTIFACT.value in serialized_agent

    loaded_agent = AgentSpecLoader(tool_registry={analyze_logs.name: analyze_logs.func}).load_json(
        serialized_agent
    )

    assert loaded_agent.tools is not None
    assert loaded_agent.tools[0].output_type == ToolOutputType.CONTENT_AND_ARTIFACT
