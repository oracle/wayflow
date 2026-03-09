# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Wayflow Code Example - How to Enable Tool Output Streaming
# ----------------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.2.0.dev0" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_tooloutputstreaming.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Define the llm

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)


# %%[markdown]
## Imports for this guide

# %%
import anyio
from typing import AsyncGenerator

from wayflowcore.agent import Agent
from wayflowcore.events.event import Event, ToolExecutionStreamingChunkReceivedEvent
from wayflowcore.events.eventlistener import EventListener, register_event_listeners
from wayflowcore.tools import tool

# %%[markdown]
## Define streaming tool

# %%
@tool(description_mode="only_docstring")
async def my_streaming_tool(topic: str) -> AsyncGenerator[str, None]:
    """Stream intermediate outputs, then yield the final result."""
    all_sentences = [f"{topic} part {i}" for i in range(2)]
    for i in range(2):
        await anyio.sleep(0.2)  # simulate work
        yield all_sentences[i]
    yield ". ".join(all_sentences)

# %%[markdown]
## Define event listener

# %%
class ToolStreamingListener(EventListener):
    def __call__(self, event: Event) -> None:
        if isinstance(event, ToolExecutionStreamingChunkReceivedEvent):
            print("[tool-chunk]", event.content)

# %%[markdown]
## Build the agent

# %%
assistant = Agent(
    llm=llm,
    name="streaming-agent",
    description="Agent that streams tool outputs",
    tools=[my_streaming_tool],
)

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {t.name: t for t in assistant.tools}
loader = AgentSpecLoader(tool_registry=tool_registry)

# %%[markdown]
## Load Agent Spec config

# %%
reloaded_assistant = loader.load_json(serialized_assistant)

# %%[markdown]
## Run agent with stream listener

# %%
from wayflowcore.events.eventlistener import register_event_listeners

with register_event_listeners([ToolStreamingListener()]):
    conv = assistant.start_conversation()
    conv.append_user_message("tell a story")
    status = conv.execute()

# %%[markdown]
## Run mcp streaming tool

# %%
from wayflowcore.mcp import MCPTool, SSETransport, enable_mcp_without_auth
from wayflowcore.flow import Flow
from wayflowcore.steps import ToolExecutionStep

enable_mcp_without_auth()
mcp_client = SSETransport(url="http://localhost:8080/sse")
mcp_tool = MCPTool(
    name="my_streaming_tool",
    client_transport=mcp_client,
)

# Option A: Use the tool in an Agent
assistant = Agent(llm=llm, tools=[mcp_tool])

# Option B: Use the tool in a Flow
assistant = Flow.from_steps([
    ToolExecutionStep(name="mcp_tool_step", tool=mcp_tool)
])

# Then use the same ToolExecutionStreamingChunkReceived listener as above
