<a id="top-howtoociagent"></a>

# How to Use OCI Generative AI Agents![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[OCI Agent how-to script](../end_to_end_code_examples/howto_ociagent.py)

#### Prerequisites
This guide assumes familiarity with:

- [LLM configuration](llm_from_different_providers.md)
- [Using agents](agents.md)

[OCI GenAI Agents](https://www.oracle.com/artificial-intelligence/generative-ai/agents) is a service to create agents in the OCI console.
These agents are defined remotely, including their tools, prompts, and optional documents for retrieval-augmented generation (RAG), and can be used for inference.

In this guide, you will learn how to connect an OCI agent using the [OciAgent](../api/agent.md#ociagent) class from the `wayflowcore` package.

## Basic usage

To get started, first create your OCI Agent in the OCI Console.
Consult the OCI documentation for detailed steps: [https://docs.oracle.com/en-us/iaas/Content/generative-ai-agents/home.htm](https://docs.oracle.com/en-us/iaas/Content/generative-ai-agents/home.htm).

Next, create an `OciClientConfig` object to configure the connection to the OCI service.
See the [OCI LLM configuration](llm_from_different_providers.md) for detailed instructions how to configure this object.

You will also need the `agent_endpoint_id` from the OCI Console.
This ID points to the agent you want to connect to, while the client configuration is about connecting to the entire service.

Once these are in place, you can create your agent in a few lines:

```python
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey
from wayflowcore.ociagent import OciAgent

oci_config = OCIClientConfigWithApiKey(service_endpoint="OCIGENAI_ENDPOINT")

agent = OciAgent(
    agent_endpoint_id="AGENT_ENDPOINT",
    client_config=oci_config,
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

# %%
# Or with an execution loop
# inputs = {}
# conversation = assistant.start_conversation(inputs)

# # What is the answer to 2+2?

# while True:
#     status = conversation.execute()
#     if isinstance(status, FinishedStatus):
#         break
#     assistant_reply = conversation.get_last_message()
#     if assistant_reply is not None:
#         print("\nAssistant >>>", assistant_reply.content)
#     user_input = input("\nUser >>> ")
#     conversation.append_user_message(user_input)
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
  "component_type": "OciAgent",
  "id": "be5b6589",
  "name": "oci_agent_be5b6589",
  "description": "",
  "metadata": {
    "__metadata_info__": {
      "name": "oci_agent_be5b6589",
      "description": ""
    }
  },
  "inputs": [],
  "outputs": [],
  "agent_endpoint_id": "AGENT_ENDPOINT",
  "client_config": {
    "component_type": "OciClientConfigWithApiKey",
    "id": "ceb3acb1-d2c2-4aed-8f4e-c1cd24daa40c",
    "name": "oci_client_config",
    "description": null,
    "metadata": {},
    "service_endpoint": "OCIGENAI_ENDPOINT",
    "auth_type": "API_KEY",
    "auth_profile": "DEFAULT",
    "auth_file_location": "~/.oci/config"
  },
  "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: OciAgent
id: be5b6589
name: oci_agent_be5b6589
description: ''
metadata:
  __metadata_info__:
    name: oci_agent_be5b6589
    description: ''
inputs: []
outputs: []
agent_endpoint_id: AGENT_ENDPOINT
client_config:
  component_type: OciClientConfigWithApiKey
  id: ceb3acb1-d2c2-4aed-8f4e-c1cd24daa40c
  name: oci_client_config
  description: null
  metadata: {}
  service_endpoint: OCIGENAI_ENDPOINT
  auth_type: API_KEY
  auth_profile: DEFAULT
  auth_file_location: ~/.oci/config
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

agent: OciAgent = AgentSpecLoader().load_json(serialized_assistant)
```

## Next steps

Now that you have learned how to use OCI agents in WayFlow, you may proceed to [How to Use Agents in Flows](howto_agents_in_flows.md).

## Full code

Click on the card at the [top of this page](#top-howtoociagent) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Use OCI Agents
# ------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_ociagent.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Creating the agent

# %%
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey
from wayflowcore.ociagent import OciAgent

oci_config = OCIClientConfigWithApiKey(service_endpoint="OCIGENAI_ENDPOINT")

agent = OciAgent(
    agent_endpoint_id="AGENT_ENDPOINT",
    client_config=oci_config,
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

# %%
# Or with an execution loop
# inputs = {}
# conversation = assistant.start_conversation(inputs)

# # What is the answer to 2+2?

# while True:
#     status = conversation.execute()
#     if isinstance(status, FinishedStatus):
#         break
#     assistant_reply = conversation.get_last_message()
#     if assistant_reply is not None:
#         print("\nAssistant >>>", assistant_reply.content)
#     user_input = input("\nUser >>> ")
#     conversation.append_user_message(user_input)

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(agent)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

agent: OciAgent = AgentSpecLoader().load_json(serialized_assistant)
```
