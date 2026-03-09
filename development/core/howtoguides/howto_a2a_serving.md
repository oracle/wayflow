<a id="top-howtoa2aserving"></a>

# How to Serve Assistants with A2A Protocol![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[A2A Agent how-to script](../end_to_end_code_examples/howto_a2a_serving.py)

[A2A Protocol](https://a2a-protocol.org/latest/) is an open standard that defines how two agents can communicate
with each other. It covers both the serving and consumption aspects of agent interaction.

This guide will show you how to serve a WayFlow assistant using this protocol either through the [A2AServer](../api/agentserver.md#a2aserver) or from the command line.

## Basic implementation

With the provided `A2AServer`, you can:

- Serve any conversational component in WayFlow, including [Agent](../api/agent.md#agent), [Flow](../api/flows.md#flow), [ManagerWorkers](../api/agent.md#managerworkers), and [Swarm](../api/agent.md#swarm).
- Serve from a serialized AgentSpec JSON/YAML string
- Serve from a path to an AgentSpec config file.

In this guide, we start with serving a simple math agent equipped with a multiplication tool.

To define the agent, you will need access to a large language model (LLM).
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

### Creating the agent
```python
from typing import Annotated
from wayflowcore.agent import Agent
from wayflowcore.tools import tool

@tool
def multiply(
    a: Annotated[int, "first required integer"],
    b: Annotated[int, "second required integer"],
) -> int:
    "Return the result of multiplication between number a and b."
    return a * b

agent = Agent(
    llm=llm,
    name="math_agent",
    custom_instruction="You are a Math agent that can do multiplication using the equipped tool.",
    can_finish_conversation=True,
)
```

**API Reference:** [tool](../api/tools.md#tooldecorator), [Agent](../api/agent.md#agent)

We recommend setting `can_finish_conversation=True` because, in A2A, each user request is treated as a [Task](https://a2a-protocol.org/latest/topics/life-of-a-task/) that should complete once the request is processed.
Enabling this option allows the agent to return a *completed* status to clearly indicate that the task has finished.

### Serving the agent with `A2AServer`
```python
from wayflowcore.agentserver.server import A2AServer

server = A2AServer()
server.serve_agent(agent=agent, url="https://<the_public_url_where_agent_can_be_found>")
# server.run(host="127.0.0.1", port=8002) # Uncomment this line to start the server
```

**API Reference:** [A2AServer](../api/agentserver.md#a2aserver)

You must specify the public URL where the agent will be reachable.
This URL is used to specify the agent’s address in the Agent Card.

When doing `server.run`, the agent will be served at the specified `host` and `port`.
The server exposes the following standard A2A endpoints:

- `/message/send`: for sending message requests
- `/tasks/get`: for getting the information of a task
- `/.well-known/agent-card.json`: for getting the agent card

By default, when a client sends a message request, the server responds that the task has been submitted.
The client must then poll `/tasks/get` using the returned `task_id`.

If the client prefers to block and wait for the final response, it can set `blocking=True` when sending the message request.

### Serving the agent via CLI

You can also serve an agent using its serialized AgentSpec configuration directly from the CLI:

```bash
wayflow serve \
  --api a2a \
  --agent-config agent.json \
  --tool-registry <path to a Python module exposing a `tool_registry` dictionary for agent server tools>
```

Since the agent uses a tool, you must pass the `tool_registry`.
See the [API reference](../api/agentserver.md#cliwayflowreference) for a complete description of all arguments.

## Advanced usage

### Storage configuration

By default, `InMemoryDatastore` is used.
This is suitable for testing or local development, but not production.
For production, configure a persistent datastore through [ServerStorageConfig](../api/agentserver.md#serverstorageconfig).

We support the following types of datastores:

- `InMemoryDatastore` (not persistent)
- `OracleDatastore` (persistent)
- `PostGresDatastore` (persistent)

### Serving other WayFlow components

We support serving all conversational components in WayFlow.

For Flows:

- Only Flows that *yield* are supported—that is, Flows containing [InputMessageStep](../api/flows.md#inputmessagestep) or [AgentExecutionStep](../api/flows.md#agentexecutionstep).
- A Flow should include an [OutputMessageStep](../api/flows.md#outputmessagestep) so that its final result can be returned to the client as a message.

Below is example Flow that is valid for serving, along with how it can be served:

```python
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.property import StringProperty
from wayflowcore.flow import Flow
from wayflowcore.steps import AgentExecutionStep, OutputMessageStep

agent = Agent(llm=llm, can_finish_conversation=True)
agent_step = AgentExecutionStep(
    name="agent_step",
    agent=agent,
    caller_input_mode=CallerInputMode.NEVER,
    output_descriptors=[StringProperty(name="output")],
)

user_output_step = OutputMessageStep(
    name="user_output_step", input_mapping={"message": "output"}
)

flow = Flow.from_steps([agent_step, user_output_step])

server = A2AServer()
server.serve_agent(
    agent=flow,
    url="https://<the_public_url_where_agent_can_be_found>"
)
```

**API Reference:** [Flow](../api/flows.md#flow), [InputMessageStep](../api/flows.md#inputmessagestep), [AgentExecutionStep](../api/flows.md#agentexecutionstep), [OutputMessageStep](../api/flows.md#outputmessagestep)

## Next steps

Now that you have learned how to serve WayFlow assistants using A2A protocol, you may proceed to [How to Build A2A Agents](howto_a2aagent.md) to learn how consume an A2A-served agent.

## Full code

Click on the card at the [top of this page](#top-howtoa2aserving) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# How to Serve Agents with A2A Protocol
# -------------------------------------

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
# python howto_a2a_serving.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.




# %%[markdown]
## Create the agent

# %%
from typing import Annotated
from wayflowcore.agent import Agent
from wayflowcore.tools import tool

@tool
def multiply(
    a: Annotated[int, "first required integer"],
    b: Annotated[int, "second required integer"],
) -> int:
    "Return the result of multiplication between number a and b."
    return a * b

agent = Agent(
    llm=llm,
    name="math_agent",
    custom_instruction="You are a Math agent that can do multiplication using the equipped tool.",
    can_finish_conversation=True,
)


# %%[markdown]
## Serve the agent

# %%
from wayflowcore.agentserver.server import A2AServer

server = A2AServer()
server.serve_agent(agent=agent, url="https://<the_public_url_where_agent_can_be_found>")
# server.run(host="127.0.0.1", port=8002) # Uncomment this line to start the server


# %%[markdown]
## Serve a flow

# %%
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.property import StringProperty
from wayflowcore.flow import Flow
from wayflowcore.steps import AgentExecutionStep, OutputMessageStep

agent = Agent(llm=llm, can_finish_conversation=True)
agent_step = AgentExecutionStep(
    name="agent_step",
    agent=agent,
    caller_input_mode=CallerInputMode.NEVER,
    output_descriptors=[StringProperty(name="output")],
)

user_output_step = OutputMessageStep(
    name="user_output_step", input_mapping={"message": "output"}
)

flow = Flow.from_steps([agent_step, user_output_step])

server = A2AServer()
server.serve_agent(
    agent=flow,
    url="https://<the_public_url_where_agent_can_be_found>"
)
```
