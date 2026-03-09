<a id="top-howtoasync"></a>

# How to Use Asynchronous APIs![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Asynchronous APIs how-to script](../end_to_end_code_examples/howto_async.py)

#### Prerequisites
This guide assumes familiarity with:

- [LLMs](../api/llmmodels.md)
- [Agent](../api/agent.md)
- [Flows](../api/flows.md)

## Why async matters

Asynchronous (async) programming in Python lets you start operations that wait on I/O (network, disk, etc.)
without blocking the main thread, enabling high concurrency with a single event loop.
Async is ideal for I/O-bound workloads (LLM calls, HTTP requests, databases) and less useful for CPU-bound tasks,
which should run in worker threads or processes to avoid blocking the event loop.

WayFlow provides asynchronous APIs across models (e.g., `generate_async`), conversations (`execute_async`),
agents, and flows so you can compose concurrent, high-throughput pipelines using libraries such as `anyio`.
Use async in the following cases:

- Many parallel LLM requests
- Agents calling several tools that perform remote I/O
- Flows coordinating multiple steps concurrently

## Basic implementation

This section shows how to:

1. Use an LLM asynchronously
2. Execute an agent and a flow asynchronously
3. Define tools properly for CPU-bound vs I/O-bound tasks
4. Run many agents concurrently with `anyio`
5. Understand when to still use synchronous APIs

For this tutorial, we will use a LLM. WayFlow supports several LLM API
providers, select a LLM from the options below:




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

### Using asynchronous APIs

From synchronous code, wrap the coroutine with `anyio.run(...)` to execute it in an event loop without blocking.
Inside an `async def` function, you would instead write `await ...`.
This pattern lets you fire off many I/O-bound calls concurrently and get much higher throughput than sync code.
For example, with an `LlmModel`:

```python
import anyio

prompt = "Who is the CEO of Oracle?"
# Run one async generation (non-blocking to the event loop)
anyio.run(llm.generate_async, prompt)
```

### Execute an Agent asynchronously

In async pipelines, you can now use `execute_async` to avoid head-of-line blocking.

```python
from wayflowcore.agent import Agent

agent = Agent(
    llm=llm,
    custom_instruction="You are a helpful assistant.",
)
conv = agent.start_conversation()
conv.append_user_message("Who is the CEO of Oracle?")
anyio.run(conv.execute_async)
```

### Execute a Flow asynchronously

Similarly, you can now run `Flows` asynchronously:

```python
from wayflowcore.flow import Flow
from wayflowcore.steps import PromptExecutionStep

step = PromptExecutionStep(
    llm=llm,
    prompt_template="Who is the CEO of Oracle?",
)
flow = Flow.from_steps(steps=[step])
flow_conv = flow.start_conversation()
anyio.run(flow_conv.execute_async)
```

### Async tools vs sync tools

[ServerTool](../api/tools.md#servertool) ‘s callable can be synchronous or asynchronous. The `tool` decorator
can therefore be applied to both synchronous and asynchronous functionx.

Use `async` tools for I/O-bound operations (HTTP calls, databases, storage) so they compose naturally
with the event loop. Keep CPU-bound work in synchronous functions, so that WayFlow automatically
runs them in worker threads in order to not block the event loop.

#### TIP
Avoid putting heavy CPU work inside an `async def` tool. If you must compute in an async context,
offload to a thread or keep it as a synchronous tool so WayFlow can schedule it efficiently.

```python
from wayflowcore.tools.toolhelpers import DescriptionMode, tool

# For CPU-bound tasks, async does not help. WayFlow runs synchronous tools
# in worker threads to avoid blocking the event loop.
@tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
def heavy_work() -> str:
    """Performs heavy CPU-bound work."""
    # WORK
    return ""

# For I/O-bound tasks, async is optimal. Asynchronous tools are directly used
# inside WayFlow's asynchronous stack to maximize efficiency.
@tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
async def remote_call() -> str:
    """Performs remote API calls (I/O-bound)."""
    # CALLS
    return ""
```

### Use tools in an async Agent

Combine tools with an agent and run it asynchronously.

```python
from wayflowcore.agent import Agent

agent_with_tools = Agent(
    llm=llm,
    custom_instruction="You are a helpful assistant, answering the user request about {{query}}",
    tools=[heavy_work, remote_call],
)

async def run_agent_async(query: str, result_list: list[str]) -> str:
    conversation = agent_with_tools.start_conversation(
        inputs={'query': query}
    )
    status = await conversation.execute_async()
    result_list.append(conversation.get_last_message().content)
```

### Run many Agents concurrently

To scale throughput, use `anyio.create_task_group()` to start many agent runs concurrently.
Each task awaits its own `execute_async` call; the event loop interleaves I/O so all runs make progress.
You can bound concurrency by using semaphores if your backend has rate limits.

```python
async def run_agents_concurrently(query: str, n: int) -> list[str]:
    solutions: list[str] = []
    async with anyio.create_task_group() as tg:
        for _ in range(n):
            tg.start_soon(run_agent_async, query, solutions)
    return solutions

# Spawn 10 agents concurrently
anyio.run(run_agents_concurrently, "who is the CEO of Oracle?", 10)
```

### Synchronous APIs in synchronous contexts

Synchronous APIs remain useful in simple scripts and batch jobs. Prefer them only when you are not inside
an event loop. If you call `execute()` or other sync APIs from async code, you risk blocking the loop;
WayFlow emits a warning and tells you which async method to use instead (for example, `execute_async`).

```python
# You can still use the synchronous API in a synchronous context.
sync_conv = agent.start_conversation()
sync_status = sync_conv.execute()

# Using synchronous APIs in an asynchronous context can block the event loop
# and lead to poor performance. WayFlow will emit a warning and indicate the
# appropriate asynchronous API to call instead (e.g., use execute_async).
```

## Agent Spec Exporting/Loading

You can export the agent configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(agent_with_tools)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "Agent",
  "id": "7017dd89-e176-476f-a655-06fce4310399",
  "name": "agent_0f9ffda8__auto",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [
    {
      "description": "\"query\" input variable for the template",
      "title": "query",
      "type": "string"
    }
  ],
  "outputs": [],
  "llm_config": {
    "component_type": "VllmConfig",
    "id": "2ceded67-85f7-4e47-be6c-2278f33f54f3",
    "name": "LLAMA_MODEL_ID",
    "description": null,
    "metadata": {
      "__metadata_info__": {}
    },
    "default_generation_parameters": null,
    "url": "LLAMA_API_URL",
    "model_id": "LLAMA_MODEL_ID"
  },
  "system_prompt": "You are a helpful assistant, answering the user request about {{query}}",
  "tools": [
    {
      "component_type": "ServerTool",
      "id": "bd53ed97-2f4b-4936-99fa-0c5b43d00a90",
      "name": "heavy_work",
      "description": "Performs heavy CPU-bound work.",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [],
      "outputs": [
        {
          "title": "tool_output",
          "type": "string"
        }
      ]
    },
    {
      "component_type": "ServerTool",
      "id": "e87b2e06-70db-4439-b653-02978390fa36",
      "name": "remote_call",
      "description": "Performs remote API calls (I/O-bound).",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [],
      "outputs": [
        {
          "title": "tool_output",
          "type": "string"
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
id: 7017dd89-e176-476f-a655-06fce4310399
name: agent_0f9ffda8__auto
description: ''
metadata:
  __metadata_info__: {}
inputs:
- description: '"query" input variable for the template'
  title: query
  type: string
outputs: []
llm_config:
  component_type: VllmConfig
  id: 2ceded67-85f7-4e47-be6c-2278f33f54f3
  name: LLAMA_MODEL_ID
  description: null
  metadata:
    __metadata_info__: {}
  default_generation_parameters: null
  url: LLAMA_API_URL
  model_id: LLAMA_MODEL_ID
system_prompt: You are a helpful assistant, answering the user request about {{query}}
tools:
- component_type: ServerTool
  id: bd53ed97-2f4b-4936-99fa-0c5b43d00a90
  name: heavy_work
  description: Performs heavy CPU-bound work.
  metadata:
    __metadata_info__: {}
  inputs: []
  outputs:
  - title: tool_output
    type: string
- component_type: ServerTool
  id: e87b2e06-70db-4439-b653-02978390fa36
  name: remote_call
  description: Performs remote API calls (I/O-bound).
  metadata:
    __metadata_info__: {}
  inputs: []
  outputs:
  - title: tool_output
    type: string
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {
    multiply.name: multiply,
    divide.name: divide,
    sum.name: sum,
    subtract.name: subtract,
}
new_agent = AgentSpecLoader(tool_registry=tool_registry).load_json(config)
```

## Next steps

Having learned how to use the asynchronous APIs, you may now proceed to:

- [Use Agents in Flows](howto_agents_in_flows.md)
- [Do Structured LLM Generation in Flows](howto_promptexecutionstep.md)
- [Build Assistants with WayFlow Tools](howto_build_assistants_with_tools.md)

## Full code

Click on the card at the [top of this page](#top-howtoasync) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to Use Asynchronous APIs
# ---------------------------------------------------

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
# python howto_async.py
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
## Single async generation

# %%
import anyio

prompt = "Who is the CEO of Oracle?"
# Run one async generation (non-blocking to the event loop)
anyio.run(llm.generate_async, prompt)


# %%[markdown]
## Async Agent execution

# %%
from wayflowcore.agent import Agent

agent = Agent(
    llm=llm,
    custom_instruction="You are a helpful assistant.",
)
conv = agent.start_conversation()
conv.append_user_message("Who is the CEO of Oracle?")
anyio.run(conv.execute_async)


# %%[markdown]
## Async Flow execution

# %%
from wayflowcore.flow import Flow
from wayflowcore.steps import PromptExecutionStep

step = PromptExecutionStep(
    llm=llm,
    prompt_template="Who is the CEO of Oracle?",
)
flow = Flow.from_steps(steps=[step])
flow_conv = flow.start_conversation()
anyio.run(flow_conv.execute_async)


# %%[markdown]
## Define tools async vs sync

# %%
from wayflowcore.tools.toolhelpers import DescriptionMode, tool

# For CPU-bound tasks, async does not help. WayFlow runs synchronous tools
# in worker threads to avoid blocking the event loop.
@tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
def heavy_work() -> str:
    """Performs heavy CPU-bound work."""
    # WORK
    return ""

# For I/O-bound tasks, async is optimal. Asynchronous tools are directly used
# inside WayFlow's asynchronous stack to maximize efficiency.
@tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
async def remote_call() -> str:
    """Performs remote API calls (I/O-bound)."""
    # CALLS
    return ""


# %%[markdown]
## Agent with async tools

# %%
from wayflowcore.agent import Agent

agent_with_tools = Agent(
    llm=llm,
    custom_instruction="You are a helpful assistant, answering the user request about {{query}}",
    tools=[heavy_work, remote_call],
)

async def run_agent_async(query: str, result_list: list[str]) -> str:
    conversation = agent_with_tools.start_conversation(
        inputs={'query': query}
    )
    status = await conversation.execute_async()
    result_list.append(conversation.get_last_message().content)


# %%[markdown]
## Run agents concurrently

# %%
async def run_agents_concurrently(query: str, n: int) -> list[str]:
    solutions: list[str] = []
    async with anyio.create_task_group() as tg:
        for _ in range(n):
            tg.start_soon(run_agent_async, query, solutions)
    return solutions

# Spawn 10 agents concurrently
anyio.run(run_agents_concurrently, "who is the CEO of Oracle?", 10)


# %%[markdown]
## Synchronous usage

# %%
# You can still use the synchronous API in a synchronous context.
sync_conv = agent.start_conversation()
sync_status = sync_conv.execute()

# Using synchronous APIs in an asynchronous context can block the event loop
# and lead to poor performance. WayFlow will emit a warning and indicate the
# appropriate asynchronous API to call instead (e.g., use execute_async).


# %%[markdown]
## Export Config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(agent_with_tools)

# %%[markdown]
## Load Agent Spec Config

# %%
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {
    heavy_work.name: heavy_work,
    remote_call.name: remote_call,
}
new_agent = AgentSpecLoader(tool_registry=tool_registry).load_json(config)
```
