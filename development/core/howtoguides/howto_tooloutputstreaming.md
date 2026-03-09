<a id="top-tooloutputstreaming"></a>

# How to Enable Tool Output Streaming![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Tool Output Streaming how-to script](../end_to_end_code_examples/howto_tooloutputstreaming.py)

#### Prerequisites
- Familiarity with WayFlow Agents and Tools
- Basic understanding of async functions in Python

In this guide you will:

- Create a [Server Tool](../api/tools.md#servertool) that streams output chunks;
- Consume tool chunk events with an [Event Listener](../api/events.md#eventlistener).

## Tool output streaming for Server Tools

WayFlow supports several LLM API providers.
Select an LLM from the options below:




OCI GenAI

```python
from wayflowcore.models import OCIGenAIModel, OCIClientConfigWithApiKey

llm = OCIGenAIModel(
    model_id="provider.model-id",
    compartment_id="compartment-id",
    client_config=OCIClientConfigWithApiKey(
        service_endpoint="https://url-to-service-endpoint.com",
    ),
)
```

vLLM

```python
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)
```

Ollama

```python
from wayflowcore.models import OllamaModel

llm = OllamaModel(
    model_id="model-id",
)
```

#### NOTE
**What is tool output streaming:**
Tool output streaming lets a tool produce **intermediate outputs** while it is still running,
instead of waiting until the execution completes to return a single final result.
When streaming is enabled, WayFlow emits chunk events as the tool makes progress (this is emitted as
[ToolExecutionStreamingChunkReceivedEvent](../api/events.md#toolexecutionstreamingchunkreceivedevent)).
This enables UIs and listeners to display partial results in near real time.
The tool’s **final output is the last value produced** (i.e., the completed tool result);
earlier values are treated as streamed chunks emitted during execution.

You can enable tool output streaming by creating an async generator
(i.e., an async callable yielding items with `yield` instead of `return`).

When running the async tool callable, yielded items are streamed via the event
[ToolExecutionStreamingChunkReceivedEvent](../api/events.md#toolexecutionstreamingchunkreceivedevent).

The last yielded item is treated as the final tool result **and is not streamed.**

Here is an example using the [@tool decorator](../api/tools.md#tooldecorator):

```python
@tool(description_mode="only_docstring")
async def my_streaming_tool(topic: str) -> AsyncGenerator[str, None]:
    """Stream intermediate outputs, then yield the final result."""
    all_sentences = [f"{topic} part {i}" for i in range(2)]
    for i in range(2):
        await anyio.sleep(0.2)  # simulate work
        yield all_sentences[i]
    yield ". ".join(all_sentences)
```

You can then define an [EventListener](../api/events.md#eventlistener) to observe the streamed chunks:

```python
class ToolStreamingListener(EventListener):
    def __call__(self, event: Event) -> None:
        if isinstance(event, ToolExecutionStreamingChunkReceivedEvent):
            print("[tool-chunk]", event.content)
```

Finally, register a listener before running your Agent/Flow:

```python
from wayflowcore.events.eventlistener import register_event_listeners

with register_event_listeners([ToolStreamingListener()]):
    conv = assistant.start_conversation()
    conv.append_user_message("tell a story")
    status = conv.execute()
```

## Tool output streaming for MCP Tools

You can also enable tool output streaming when using MCP tools by wrapping your server-side async callable
with the [@mcp_streaming_tool](../api/tools.md#mcpstreamingtool) decorator.

#### NOTE
Wrapping the callable allows to automatically handle the streaming by using the progress
notification feature from MCP. This feature only works in async code, so you need to write an
async callable to use the output streaming feature for MCP tools.

Here is an example using the official MCP SDK:

```python
import anyio
from typing import AsyncGenerator
from mcp.server.fastmcp import FastMCP
from wayflowcore.mcp.mcphelpers import mcp_streaming_tool

server = FastMCP(
    name="Example MCP Server",
    instructions="A MCP Server.",
)

@server.tool(description="Stream intermediate outputs, then yield the final result.")
@mcp_streaming_tool
async def my_streaming_tool(topic: str) -> AsyncGenerator[str, None]:
    all_sentences = [f"{topic} part {i}" for i in range(2)]
    for i in range(2):
        await anyio.sleep(0.2)  # simulate work
        yield all_sentences[i]
    yield ". ".join(all_sentences)

server.run(transport="streamable-http")
```

When using other MCP libraries (e.g., [https://gofastmcp.com/](https://gofastmcp.com/)), you need to
provide the context class when using the `mcp_streaming_tool` wrapper.

```python
from fastmcp import FastMCP, Context

server = FastMCP(
   name="Example MCP Server",
   instructions="A MCP Server.",
)

async def my_tool() -> AsyncGenerator[str, None]:
   contents = [f"This is the sentence N°{i}" for i in range(5)]
   for chunk in contents:
         yield chunk  # streamed chunks
         await anyio.sleep(0.2)

   yield ". ".join(contents)  # final result

streaming_tool = mcp_streaming_tool(my_tool, context_cls=Context)
server.tool(description="...")(streaming_tool)
```

From the client-side, you can consume the MCP tool and observe the streamed chunks
using an event listener as shown above with server tools.

```python
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

# Option A: Use the tool in an Agent
assistant = Agent(llm=llm, tools=[mcp_tool])

# Option B: Use the tool in a Flow
assistant = Flow.from_steps([
    ToolExecutionStep(name="mcp_tool_step", tool=mcp_tool)
])

# Then use the same ToolExecutionStreamingChunkReceived listener as above
```

#### SEE ALSO
For more information read the [Guide on using MCP Tools](howto_mcp.md)

## Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {t.name: t for t in assistant.tools}
loader = AgentSpecLoader(tool_registry=tool_registry)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
    "component_type": "Agent",
    "id": "ce59e1be-aa7a-4a38-ba89-2c3cd546d51f",
    "name": "streaming-agent",
    "description": "Agent that streams tool outputs",
    "metadata": {
        "__metadata_info__": {}
    },
    "inputs": [],
    "outputs": [],
    "llm_config": {
        "component_type": "VllmConfig",
        "id": "424b4cf5-9eed-48bc-afa8-909524d3b6a0",
        "name": "llm_f95a3161__auto",
        "description": null,
        "metadata": {
            "__metadata_info__": {}
        },
        "default_generation_parameters": null,
        "url": "LLAMA_API_URL",
        "model_id": "LLAMA_MODEL_ID"
    },
    "system_prompt": "You can stream outputs from tools",
    "tools": [
        {
            "component_type": "ServerTool",
            "id": "ddd75c20-0053-46b2-80e9-139277b3f4f4",
            "name": "my_streaming_tool",
            "description": "Stream intermediate outputs, then yield the final result.",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "type": "string",
                    "title": "topic"
                }
            ],
            "outputs": [
                {
                    "type": "string",
                    "title": "tool_output"
                }
            ]
        }
    ],
    "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: Agent
id: ce59e1be-aa7a-4a38-ba89-2c3cd546d51f
name: streaming-agent
description: Agent that streams tool outputs
metadata:
  __metadata_info__: {}
inputs: []
outputs: []
llm_config:
  component_type: VllmConfig
  id: 424b4cf5-9eed-48bc-afa8-909524d3b6a0
  name: llm_f95a3161__auto
  description: null
  metadata:
    __metadata_info__: {}
  default_generation_parameters: null
  url: LLAMA_API_URL
  model_id: LLAMA_MODEL_ID
system_prompt: You can stream outputs from tools
tools:
- component_type: ServerTool
  id: ddd75c20-0053-46b2-80e9-139277b3f4f4
  name: my_streaming_tool
  description: Stream intermediate outputs, then yield the final result.
  metadata:
    __metadata_info__: {}
  inputs:
  - type: string
    title: topic
  outputs:
  - type: string
    title: tool_output
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
reloaded_assistant = loader.load_json(serialized_assistant)
```

## Recap

In this guide, you learned how to:

- Implement streaming Server Tools using async generators
- Listen to tool chunk events and correlate them with executions
- Adjust the streaming cap (including unlimited)

## Next steps

Having learned how to stream tool outputs and consume chunk events, you may now proceed to:

- [Build Assistants with Tools](howto_build_assistants_with_tools.md) to design richer tool-enabled agents and flows.
- [Use the Event System](howto_event_system.md) to implement custom listeners, tracing, and monitoring.

## Full code

Click on the card at the [top of this page](#top-tooloutputstreaming) to download the full code for this guide or copy the code below.

```python
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
```
