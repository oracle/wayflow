# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Wayflow Code Example - How to Enable Tool Output Streaming


# .. start-##_Define_the_llm
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)
# .. end-##_Define_the_llm
(llm,) = _update_globals(["llm_big"])  # docs-skiprow # type: ignore

# .. start-##_Imports_for_this_guide
import anyio
from typing import AsyncGenerator

from wayflowcore.agent import Agent
from wayflowcore.events.event import (
    Event,
    ToolExecutionResultEvent,
    ToolExecutionStreamingChunkReceivedEvent,
)
from wayflowcore.events.eventlistener import EventListener, register_event_listeners
from wayflowcore.tools import ReturnArtifact, ToolOutputType, tool
# .. end-##_Imports_for_this_guide

# .. start-##_Define_simple_streaming_tool
@tool(description_mode="only_docstring")
async def my_streaming_tool(topic: str) -> AsyncGenerator[str, None]:
    """Stream intermediate outputs, then yield the final result."""
    all_sentences = [f"{topic} part {i}" for i in range(2)]
    for i in range(2):
        await anyio.sleep(0.2)  # simulate work
        yield all_sentences[i]
    yield ". ".join(all_sentences)
# .. end-##_Define_simple_streaming_tool

# .. start-##_Define_simple_stream_listener
class ToolStreamingListener(EventListener):
    def __call__(self, event: Event) -> None:
        if isinstance(event, ToolExecutionStreamingChunkReceivedEvent):
            print("[tool-chunk]", event.content)
# .. end-##_Define_simple_stream_listener

# .. start-##_Define_streaming_tool_with_artifacts
@tool(description_mode="only_docstring", output_type=ToolOutputType.CONTENT_AND_ARTIFACT)
async def my_streaming_tool_with_artifacts(topic: str) -> AsyncGenerator[ReturnArtifact[str], None]:
    """Stream intermediate outputs and attach artifacts to streamed chunks and the final result."""
    all_sentences = [f"{topic} part {i}" for i in range(2)]
    for i, sentence in enumerate(all_sentences):
        await anyio.sleep(0.2)  # simulate work
        yield sentence, {
            "name": f"{topic}_chunk_{i}.txt",
            "mime_type": "text/plain",
            "data": sentence,
        }

    full_story = ". ".join(all_sentences)
    yield full_story, {
        "name": f"{topic}_full.txt",
        "mime_type": "text/plain",
        "data": full_story,
    }
# .. end-##_Define_streaming_tool_with_artifacts

# .. start-##_Define_artifact_stream_listener
class ArtifactStreamingListener(EventListener):
    def __call__(self, event: Event) -> None:
        if isinstance(event, ToolExecutionStreamingChunkReceivedEvent):
            print("[tool-chunk]", event.content)
            if event.artifacts:
                print("[chunk-artifacts]", [artifact.name for artifact in event.artifacts])
        elif isinstance(event, ToolExecutionResultEvent) and event.tool_result.artifacts:
            print("[final-artifacts]", [artifact.name for artifact in event.tool_result.artifacts])
# .. end-##_Define_artifact_stream_listener

# .. start-##_Build_the_agent
assistant = Agent(
    llm=llm,
    name="streaming-agent",
    description="Agent that streams tool outputs",
    tools=[my_streaming_tool],
)
# .. end-##_Build_the_agent
# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {t.name: t for t in assistant.tools}
loader = AgentSpecLoader(tool_registry=tool_registry)
# .. end-##_Export_config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_config
reloaded_assistant = loader.load_json(serialized_assistant)
# .. end-##_Load_Agent_Spec_config
# .. start-##_Run_agent_with_stream_listener
with register_event_listeners([ToolStreamingListener()]):
    conv = assistant.start_conversation()
    conv.append_user_message("tell a story")
    status = conv.execute()
# .. end-##_Run_agent_with_stream_listener
# .. start-##_Run_mcp_streaming_tool
exit()  # docs-skiprow # type: ignore
from wayflowcore.mcp import MCPTool, SSETransport, enable_mcp_without_auth
from wayflowcore.flow import Flow
from wayflowcore.steps import ToolExecutionStep

enable_mcp_without_auth()
mcp_client = SSETransport(url="http://localhost:8080/sse")
mcp_tool = MCPTool(
    name="my_streaming_tool",
    client_transport=mcp_client,
)
# If the server-side MCP tool returns artifacts, also pass:
# output_type=ToolOutputType.CONTENT_AND_ARTIFACT

# Option A: Use the tool in an Agent
assistant = Agent(llm=llm, tools=[mcp_tool])

# Option B: Use the tool in a Flow
assistant = Flow.from_steps([
    ToolExecutionStep(name="mcp_tool_step", tool=mcp_tool)
])

# Then use the same ToolExecutionStreamingChunkReceived listener as above
# .. end-##_Run_mcp_streaming_tool
