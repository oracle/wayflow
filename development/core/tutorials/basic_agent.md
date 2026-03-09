<a id="core-basic-agent"></a>

# Build a Simple Conversational Assistant with Agents![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this tutorial.

[Agent tutorial script](../end_to_end_code_examples/tutorial_agent.py)

#### Prerequisites
This guide does not assume any prior knowledge about WayFlow. However, it assumes the reader has a basic knowledge of LLMs.

You will need a working installation of WayFlow - see [Installation](../installation.md).

## Learning Goals

In this first tutorial you will develop a simple HR chatbot Assistant that uses a [Tool](../api/tools.md) to search an
HR database to answer the employee’s HR-related question.

The HR system will be represented by a set of dummy data that we will
be made available to the agent. The agent will use this dummy data to answer your questions and if it is asked a question that can not
be answered from the dummy data, then it will say so.

By completing this tutorial, you will:

1. Get a feel for how WayFlow works by creating a simple conversational assistant.
2. Learn the basics of using an [Agent](../api/agent.md#agent) to build an assistant.

<a id="primer-on-agents"></a>

### A primer on Agents

**Assistants** created using WayFlow are AI-powered assistants designed to solve tasks in a (semi-)autonomous and intelligent manner.
WayFlow supports two main types of assistants:

- [Flows](../api/flows.md#flow) - Used for assistants that follow a predefined process to complete tasks. A Flow consists of individual **steps** connected to form a logical sequence of actions. Each step in a Flow serves a specific function, similar to functions in programming.
- [Agents](../api/agent.md#agent) - Used to create conversational agents that can autonomously plan, think, act, and execute tools in a flexible manner.

Additionally, WayFlow provides [Tools](../api/tools.md#clienttool), which are wrappers around external APIs.
Assistants can use these tools to retrieve relevant data and information necessary for completing tasks.

#### TIP
**When to use a Flow and when an Agent?** Flows are useful to model business processes with clear requirements, as these assistants provide a high level of
control over their behavior. On the other hand, Agents are not easy to control, but they can be useful in ambiguous
environments that necessitate flexibility and creativity.

In this tutorial, you will use the Agent, which is a general-purpose assistant that can interact with users, leverage LLMs, and execute tools to complete tasks.

#### NOTE
To learn more about building assistants with Flows, check out Build a Simple Fixed-flow Assistant with Flows [Build a Simple Fixed-Flow Assistant with Flows](basic_flow.md).

### Building the Agent

The process for building a simple Agent will be composed of the following elements:

1. Set up the coding environment by importing the necessary modules and configuring the LLMs.
2. Specify the Agents’ instructions.
3. Create the Agent.

### Imports and LLM configuration

First import what is needed for this tutorial:

```python
from wayflowcore.agent import Agent
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    UserMessageRequestStatus,
)
from wayflowcore.tools import tool
```

WayFlow supports several LLM API providers. First choose an LLM from one of the options below:




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
API keys should never be stored in code. Use environment variables and/or tools such as [python-dotenv](https://pypi.org/project/python-dotenv/)
instead.

### Creating a tool for the Agent

The agent shown in this tutorial is equipped with a tool `search_hr_database`, which -as the name indicates-
will enable the assistant to search a (fictitious) HR database.

```python
@tool(description_mode="only_docstring")
def search_hr_database(query: str) -> str:
    """Function that searches the HR database for employee benefits.

    Parameters
    ----------
    query:
        a query string

    Returns
    -------
        a JSON response

    """
    return '{"John Smith": {"benefits": "Unlimited PTO", "salary": "$1,000"}, "Mary Jones": {"benefits": "25 days", "salary": "$10,000"}}'

```

Here, the tool returns some dummy data about two fictitious employees, John Smith and Mary Jones. The dummy data
returned contains details of the salary and benefits for each of these employees. The agent will use this dummy data
to answer the user’s salary queries.

### Specifying the agent instructions

<a id="createagent-instructions"></a>

Next, give the agent instructions on how to approach the task. The instructions are shown below.

```python
HRASSISTANT_GENERATION_INSTRUCTIONS = """
You are a knowledgeable, factual, and helpful HR assistant that can answer simple \
HR-related questions like salary and benefits.
You are given a tool to look up the HR database.
Your task:
    - Ask the user if they need assistance
    - Use the provided tool below to retrieve HR data
    - Based on the data you retrieved, answer the user's question
Important:
    - Be helpful and concise in your messages
    - Do not tell the user any details not mentioned in the tool response, let's be factual.
""".strip()
```

The LLM is provided with these instructions to guide it in solving the task. In this context, the LLM acts as an HR assistant.

#### NOTE
For advanced LLM users, these instructions correspond to the system prompt.
The underlying LLM is used as a multi-turn chat model, with these instructions serving as the initial system prompt.

#### HINT
**How do I write good instructions?** Good instructions for an LLM should include the following elements:

1. A persona description defining the role of the agent.
2. A short description of the task to be solved.
3. A detailed description of the task. More precise descriptions lead to more consistent results.
4. Instructions on how the output should be formatted.

### Creating the Agent

Now that the tool is created and the instructions are written, you can then create the [Agent](../api/agent.md#agent).

The code for the agent is shown below.

```python
assistant = Agent(
    custom_instruction=HRASSISTANT_GENERATION_INSTRUCTIONS,
    tools=[search_hr_database],  # this is a decorated python function (Server tool in this example)
    llm=llm,  # the LLM object we created above
)
```

The [Agent](../api/agent.md#agent) interacts with the user through conversations. During each turn, it may choose to respond to the user, execute tools or flows, or consult expert agents.

This completes your first Agent!

### Running the Agent

Finally, run your agent using a simple turn-based conversation flow until the conversation concludes.
You can execute the assistant by implementing a finite conversation sequence, or a conversation loop.

In the given example conversation loop, the agent’s output is displayed to you, and when additional information
is needed, you will be prompted for input.
The script reads your input and responds accordingly, requiring it to be run in an “interactive” manner.

```python
# With a linear conversation
conversation = assistant.start_conversation()

conversation.append_user_message("What are John Smith's benefits?")
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")

# then continue the conversation

# %%
# Or with an execution loop
def run_agent_in_command_line(assistant: Agent):
    inputs = {}
    conversation = assistant.start_conversation(inputs)

    while True:
        status = conversation.execute()
        if isinstance(status, FinishedStatus):
            break
        assistant_reply = conversation.get_last_message()
        if assistant_reply is not None:
            print("\nAssistant >>>", assistant_reply.content)
        user_input = input("\nUser >>> ")
        conversation.append_user_message(user_input)

```

Before we run the assistant, what are some questions that you could ask it? The following questions can be answered form
the dummy HR data and are a good starting point.

1. What is the salary for John Smith?
2. Does John Smith earn more that Mary Jones?
3. How much annual leave does John Smith get?

But, we can also ask the assistant questions that it shouldn’t be able to answer, because it hasn’t been given any data that is relevant to the question:

1. How much does Jones Jones earn?
2. What is Mary Jones favorite color?

So with some questions ready you can now run the assistant. Run the code below to run the assistant. To quit the assistant type, Done.

```python
# run_agent_in_command_line(assistant)
# ^ uncomment and execute
```

### Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "Agent",
  "id": "61bd7075-4f41-4344-8e0d-1d6935975794",
  "name": "agent_58415549__auto",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [],
  "outputs": [],
  "llm_config": {
    "component_type": "VllmConfig",
    "id": "7796961b-db94-4a5e-bd12-8c532989fe0f",
    "name": "LLAMA_MODEL_ID",
    "description": null,
    "metadata": {
      "__metadata_info__": {}
    },
    "default_generation_parameters": null,
    "url": "LLAMA_API_URL",
    "model_id": "LLAMA_MODEL_ID"
  },
  "system_prompt": "You are a knowledgeable, factual, and helpful HR assistant that can answer simple HR-related questions like salary and benefits.\nYou are given a tool to look up the HR database.\nYour task:\n    - Ask the user if they need assistance\n    - Use the provided tool below to retrieve HR data\n    - Based on the data you retrieved, answer the user's question\nImportant:\n    - Be helpful and concise in your messages\n    - Do not tell the user any details not mentioned in the tool response, let's be factual.",
  "tools": [
    {
      "component_type": "ServerTool",
      "id": "c6d943c1-20a3-4f66-b89b-8173ab854e0b",
      "name": "search_hr_database",
      "description": "Function that searches the HR database for employee benefits.\n\nParameters\n----------\nquery:\n    a query string\n\nReturns\n-------\n    a JSON response",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "string",
          "title": "query"
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
id: 61bd7075-4f41-4344-8e0d-1d6935975794
name: agent_58415549__auto
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs: []
llm_config:
  component_type: VllmConfig
  id: 7796961b-db94-4a5e-bd12-8c532989fe0f
  name: LLAMA_MODEL_ID
  description: null
  metadata:
    __metadata_info__: {}
  default_generation_parameters: null
  url: LLAMA_API_URL
  model_id: LLAMA_MODEL_ID
system_prompt: "You are a knowledgeable, factual, and helpful HR assistant that can\
  \ answer simple HR-related questions like salary and benefits.\nYou are given a\
  \ tool to look up the HR database.\nYour task:\n    - Ask the user if they need\
  \ assistance\n    - Use the provided tool below to retrieve HR data\n    - Based\
  \ on the data you retrieved, answer the user's question\nImportant:\n    - Be helpful\
  \ and concise in your messages\n    - Do not tell the user any details not mentioned\
  \ in the tool response, let's be factual."
tools:
- component_type: ServerTool
  id: c6d943c1-20a3-4f66-b89b-8173ab854e0b
  name: search_hr_database
  description: "Function that searches the HR database for employee benefits.\n\n\
    Parameters\n----------\nquery:\n    a query string\n\nReturns\n-------\n    a\
    \ JSON response"
  metadata:
    __metadata_info__: {}
  inputs:
  - type: string
    title: query
  outputs:
  - type: string
    title: tool_output
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {"search_hr_database": search_hr_database}
assistant: Agent = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_json(serialized_assistant)
```

### Next steps

You have successfully learned how to build a conversational assistant using WayFlow [Agent](../api/agent.md#agent).
With the basics covered, you can now start building more complex assistants.

To continue learning, check out:

- [API reference](../api/index.md#api).
- [How-to guides](../howtoguides/index.md#how-to-guides)

### Full code

Click on the card at the [top of this page](#core-basic-agent) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Tutorial - Build a Conversational Assistant with Agents
# -------------------------------------------------------

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
# python tutorial_agent.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.




# %%[markdown]
## Imports for this guide

# %%
from wayflowcore.agent import Agent
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    UserMessageRequestStatus,
)
from wayflowcore.tools import tool

# %%[markdown]
## Configure your LLM

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA70B_MODEL_ID",
    host_port="LLAMA70BV33_API_URL",
)

# %%[markdown]
## Defining a tool for the agent

# %%
@tool(description_mode="only_docstring")
def search_hr_database(query: str) -> str:
    """Function that searches the HR database for employee benefits.

    Parameters
    ----------
    query:
        a query string

    Returns
    -------
        a JSON response

    """
    return '{"John Smith": {"benefits": "Unlimited PTO", "salary": "$1,000"}, "Mary Jones": {"benefits": "25 days", "salary": "$10,000"}}'


# %%[markdown]
## Specifying the agent instructions

# %%
HRASSISTANT_GENERATION_INSTRUCTIONS = """
You are a knowledgeable, factual, and helpful HR assistant that can answer simple \
HR-related questions like salary and benefits.
You are given a tool to look up the HR database.
Your task:
    - Ask the user if they need assistance
    - Use the provided tool below to retrieve HR data
    - Based on the data you retrieved, answer the user's question
Important:
    - Be helpful and concise in your messages
    - Do not tell the user any details not mentioned in the tool response, let's be factual.
""".strip()

# %%[markdown]
## Creating the agent

# %%
assistant = Agent(
    custom_instruction=HRASSISTANT_GENERATION_INSTRUCTIONS,
    tools=[search_hr_database],  # this is a decorated python function (Server tool in this example)
    llm=llm,  # the LLM object we created above
)

# %%[markdown]
## Running the agent

# %%
# With a linear conversation
conversation = assistant.start_conversation()

conversation.append_user_message("What are John Smith's benefits?")
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")

# then continue the conversation

# %%
# Or with an execution loop
def run_agent_in_command_line(assistant: Agent):
    inputs = {}
    conversation = assistant.start_conversation(inputs)

    while True:
        status = conversation.execute()
        if isinstance(status, FinishedStatus):
            break
        assistant_reply = conversation.get_last_message()
        if assistant_reply is not None:
            print("\nAssistant >>>", assistant_reply.content)
        user_input = input("\nUser >>> ")
        conversation.append_user_message(user_input)


# %%[markdown]
## Running with the execution loop

# %%
# run_agent_in_command_line(assistant)
# ^ uncomment and execute

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {"search_hr_database": search_hr_database}
assistant: Agent = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_json(serialized_assistant)
```
