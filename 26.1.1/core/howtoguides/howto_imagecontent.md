<a id="top-howtoimagecontent"></a>

# How to Send Images to LLMs and Agents![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Tutorial on using Images with WayFlow models](../end_to_end_code_examples/howto_imagecontent.py)

#### Prerequisites
- Familiarity with [basic agent and prompt workflows](../tutorials/basic_agent.md).

## Overview

Some Large Language Models (LLMs) can handle images in addition to text.
WayFlow supports passing images alongside text in both direct prompt requests and full agent conversations
using the ImageContent API.

This guide will show you:

- How to create ImageContent in code.
- How to run a prompt with image input directly with the model.
- How to send image+text messages in an Agent conversation.
- How to inspect and use model/agent outputs with image reasoning.

### What is `ImageContent`?

ImageContent is a type of message content that stores image bytes and format metadata.
You can combine an image with additional TextContent in a single message.

## Basic implementation

First import what is needed for this guide:

```python
import httpx
from wayflowcore.agent import Agent
from wayflowcore.messagelist import ImageContent, Message, TextContent
from wayflowcore.models.llmmodel import Prompt

```

To follow this guide, you will need access to a **Multimodal** large language model (LLM).
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

## Step 1: Creating a prompt with ImageContent

Before sending requests to your vision-capable LLMs or agents, you need to construct a prompt containing both the image and text content. The example below demonstrates:

- Downloading an image (here, the Oracle logo) via HTTP request
- Creating an ImageContent object from the image bytes
- Adding a TextContent question
- Packing both into a Message, then into a Prompt

```python
# Download the Oracle logo as PNG (publicly accessible image)
image_url = "https://www.oracle.com/a/ocom/img/oracle-logo.png"
response = httpx.get(image_url)
response.raise_for_status()
image_bytes = response.content

# Create ImageContent: format must match the image (in this case: "png")
image_content = ImageContent.from_bytes(bytes_content=image_bytes, format="png")

# Compose a message with both image and question
text_content = TextContent(content="Which company's logo is this?")
user_message = Message(contents=[image_content, text_content], role="user")
prompt = Prompt(messages=[user_message])
```

## Step 2: Sending image input to a vision-capable model

You can send images directly to your LLM by constructing a prompt with both ImageContent and TextContent.
The example below downloads the Oracle logo PNG and queries the LLM for recognition.

```python
result = llm.generate(prompt)
print("Model output:", result.message.content)
# For the Oracle logo, output should mention "Oracle Corporation"
```

**Expected output:** The model should identify the company (e.g. “Oracle Corporation” or equivalent).
If your model does not support images, you will get an error.

## Step 3: Using images in Agent conversations

You can pass images in an Agent-driven chat workflow.
This allows assistants to process visual information alongside user dialog.

```python
# Create an Agent configured for vision
agent = Agent(llm=llm)

# Start a new conversation
conversation = agent.start_conversation()

# Add a user message with both image and text as contents
conversation.append_message(Message(contents=[image_content, text_content], role="user"))

# Run agent logic for this input
conversation.execute()

# Retrieve and print the agent's last response
agent_output = conversation.get_last_message()
if agent_output is not None:
    print("Agent output:", agent_output.content)
# The output should mention "Oracle Corporation"
```

**Expected output:** The agent response should mention “Oracle Corporation”.

## API Reference and Practical Information
- [ImageContent](../api/conversation.md#imagecontent)
- [TextContent](../api/conversation.md#textcontent)
- [`wayflowcore.agent.Agent`](../api/agent.md#wayflowcore.agent.Agent)

### Supported Image Formats

Most vision LLMs support PNG, JPG, JPEG, GIF, or WEBP.
Always specify the correct format for ImageContent.

## Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_agent = AgentSpecExporter().to_json(agent)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "Agent",
  "id": "2fc0cb26-98db-4a53-869b-61587a784b1a",
  "name": "agent_df87a3d8",
  "description": "",
  "metadata": {
    "__metadata_info__": {
      "name": "agent_df87a3d8",
      "description": ""
    }
  },
  "inputs": [],
  "outputs": [],
  "llm_config": {
    "component_type": "VllmConfig",
    "id": "16d7437d-b510-4599-b1d4-51e8418043c4",
    "name": "GEMMA_MODEL_ID",
    "description": null,
    "metadata": {
      "__metadata_info__": {}
    },
    "default_generation_parameters": null,
    "url": "GEMMA_API_URL",
    "model_id": "GEMMA_MODEL_ID"
  },
  "system_prompt": "",
  "tools": [],
  "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: Agent
id: 2fc0cb26-98db-4a53-869b-61587a784b1a
name: agent_df87a3d8
description: ''
metadata:
  __metadata_info__:
    name: agent_df87a3d8
    description: ''
inputs: []
outputs: []
llm_config:
  component_type: VllmConfig
  id: 16d7437d-b510-4599-b1d4-51e8418043c4
  name: GEMMA_MODEL_ID
  description: null
  metadata:
    __metadata_info__: {}
  default_generation_parameters: null
  url: GEMMA_API_URL
  model_id: GEMMA_MODEL_ID
system_prompt: ''
tools: []
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader().load_json(serialized_agent)
```

## Next steps

Having learned how to send images to LLMs and Agents, you may now proceed to:

- [Build a Simple Conversational Assistant with Agents](../tutorials/basic_agent.md)

## Full code

Click on the card at the [top of this page](#top-howtoimagecontent) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to use use images in conversations
# -----------------------------------------------------

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
# python howto_imagecontent.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


# %%[markdown]
## Imports

# %%
import httpx
from wayflowcore.agent import Agent
from wayflowcore.messagelist import ImageContent, Message, TextContent
from wayflowcore.models.llmmodel import Prompt


# %%[markdown]
## Model configuration

# %%
from wayflowcore.models import VllmModel
llm = VllmModel(
    model_id="GEMMA_MODEL_ID",
    host_port="GEMMA_API_URL",
)

# %%[markdown]
## Create prompt

# %%
# Download the Oracle logo as PNG (publicly accessible image)
image_url = "https://www.oracle.com/a/ocom/img/oracle-logo.png"
response = httpx.get(image_url)
response.raise_for_status()
image_bytes = response.content

# Create ImageContent: format must match the image (in this case: "png")
image_content = ImageContent.from_bytes(bytes_content=image_bytes, format="png")

# Compose a message with both image and question
text_content = TextContent(content="Which company's logo is this?")
user_message = Message(contents=[image_content, text_content], role="user")
prompt = Prompt(messages=[user_message])

# %%[markdown]
## Generate completion with an image as input

# %%
result = llm.generate(prompt)
print("Model output:", result.message.content)
# For the Oracle logo, output should mention "Oracle Corporation"

# %%[markdown]
## Pass an image to an agent as input

# %%
# Create an Agent configured for vision
agent = Agent(llm=llm)

# Start a new conversation
conversation = agent.start_conversation()

# Add a user message with both image and text as contents
conversation.append_message(Message(contents=[image_content, text_content], role="user"))

# Run agent logic for this input
conversation.execute()

# Retrieve and print the agent's last response
agent_output = conversation.get_last_message()
if agent_output is not None:
    print("Agent output:", agent_output.content)
# The output should mention "Oracle Corporation"

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_agent = AgentSpecExporter().to_json(agent)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader().load_json(serialized_agent)
```
