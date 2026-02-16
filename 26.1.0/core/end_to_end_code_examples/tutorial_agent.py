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
# pip install "wayflowcore==26.1" 
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
