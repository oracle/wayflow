# Copyright © 2025 Oracle and/or its affiliates.
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
import asyncio
from typing import AsyncGenerator

from wayflowcore.agent import Agent
from wayflowcore.events.event import Event, ToolExecutionStreamingChunkReceived
from wayflowcore.events.eventlistener import EventListener, register_event_listeners
from wayflowcore.tools import tool
# .. end-##_Imports_for_this_guide
# .. start-##_Define_streaming_tool_and_listener
class ToolStreamingListener(EventListener):
    def __call__(self, event: Event) -> None:
        if isinstance(event, ToolExecutionStreamingChunkReceived):
            print("[tool-chunk]", event.content)


@tool(description_mode="only_docstring")
async def my_streaming_tool(topic: str) -> AsyncGenerator[str, None]:
    """Stream intermediate outputs, then yield the final result."""
    for i in range(2):
        await asyncio.sleep(0.2)  # simulate work
        yield f"{topic} part {i}"
    yield f"{topic} FINAL"
# .. end-##_Define_streaming_tool_and_listener
# .. start-##_Build_the_agent
def build_agent_for_streaming(llm_model: VllmModel) -> Agent:
    return Agent(
        llm=llm_model,
        name="streaming-agent",
        description="Agent that streams tool outputs",
        tools=[my_streaming_tool],
        custom_instruction="You can stream outputs from tools",
    )

assistant = build_agent_for_streaming(llm)
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
from wayflowcore.events.eventlistener import register_event_listeners

agent = build_agent_for_streaming(llm)
with register_event_listeners([ToolStreamingListener()]):
    conv = agent.start_conversation()
    conv.append_user_message("tell a story")
    status = conv.execute()
# .. end-##_Run_agent_with_stream_listener
