# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# %%[markdown]
# Code Example - How to use use images in conversations
# -----------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_imagecontent.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.


# %%[markdown]
## Imports

# %%
import requests
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
response = requests.get(image_url)
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
