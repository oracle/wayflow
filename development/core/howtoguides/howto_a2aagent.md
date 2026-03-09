<a id="top-howtoa2aagent"></a>

# How to Connect to A2A Agents![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[A2A Agent how-to script](../end_to_end_code_examples/howto_a2aagent.py)

#### Prerequisites
This guide assumes familiarity with:

- [LLM configuration](llm_from_different_providers.md)
- [Using agents](agents.md)

[A2A Protocol](https://a2a-protocol.org/latest/) is an open standard that defines how two agents can communicate
with each other. It covers both the serving and consumption aspects of agent interaction.

In this guide, you will learn how to connect to a remote agent using this protocol with the [A2AAgent](../api/agent.md#a2aagent)
class from the `wayflowcore` package.

## Basic usage

To get started with an A2A agent, you need the URL of the remote server agent you wish to connect to.
Once you have this information, creating your A2A agent is straightforward and can be done in just a few lines of code:

```python
from wayflowcore.a2a.a2aagent import A2AAgent, A2AConnectionConfig

agent = A2AAgent(
    agent_url="http://<URL>",
    connection_config=A2AConnectionConfig(verify=False)
)
```

Then, use the agent as shown below:

```python
from wayflowcore.executors.executionstatus import UserMessageRequestStatus

# With a linear conversation
conversation = agent.start_conversation()

conversation.append_user_message("What is the answer to 2+2?")
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")
```

## Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(agent)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
    "component_type": "A2AAgent",
    "id": "5ba508ef-7cae-417a-9197-8f2aeee870b6",
    "name": "a2a_agent_4311ebd5__auto",
    "description": "",
    "metadata": {
        "__metadata_info__": {}
    },
    "inputs": [],
    "outputs": [],
    "agent_url": "http://<URL>",
    "connection_config": {
        "component_type": "A2AConnectionConfig",
        "id": "c01ebe14-f467-4c01-a25b-0f3f22bfa550",
        "name": "connection_config",
        "description": null,
        "metadata": {},
        "timeout": 600.0,
        "headers": null,
        "verify": false,
        "key_file": null,
        "cert_file": null,
        "ssl_ca_cert": null
    },
    "session_parameters": {
        "timeout": 60.0,
        "poll_interval": 2.0,
        "max_retries": 5
    },
    "agentspec_version": "25.4.2"
}
```

YAML

```yaml
component_type: A2AAgent
id: 5ba508ef-7cae-417a-9197-8f2aeee870b6
name: a2a_agent_4311ebd5__auto
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs: []
agent_url: http://<URL>
connection_config:
  component_type: A2AConnectionConfig
  id: 7d7a7c03-616b-4740-bd8e-ebcfed45092c
  name: connection_config
  description: null
  metadata: {}
  timeout: 600.0
  headers: null
  verify: false
  key_file: null
  cert_file: null
  ssl_ca_cert: null
session_parameters:
  timeout: 60.0
  poll_interval: 2.0
  max_retries: 5
agentspec_version: 25.4.2
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

agent: A2AAgent = AgentSpecLoader().load_json(serialized_assistant)
```

## Next steps

Now that you have learned how to use A2A Agents in WayFlow, you may proceed to [How to Use Agents in Flows](howto_agents_in_flows.md).

## Full code

Click on the card at the [top of this page](#top-howtoa2aagent) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Use A2A Agents
# ------------------------------------

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
# python howto_a2aagent.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Creating the agent

# %%
from wayflowcore.a2a.a2aagent import A2AAgent, A2AConnectionConfig

agent = A2AAgent(
    agent_url="http://<URL>",
    connection_config=A2AConnectionConfig(verify=False)
)


# %%[markdown]
## Running the agent

# %%
from wayflowcore.executors.executionstatus import UserMessageRequestStatus

# With a linear conversation
conversation = agent.start_conversation()

conversation.append_user_message("What is the answer to 2+2?")
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")


# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(agent)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

agent: A2AAgent = AgentSpecLoader().load_json(serialized_assistant)
```
