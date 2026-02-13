# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Serialize and Deserialize Conversations
# -------------------------------------------------------------

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
# python howto_serialize_conversations.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Imports for this guide

# %%
import json
import os

from wayflowcore.agent import Agent
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.conversation import Conversation
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    UserMessageRequestStatus,
)
from wayflowcore.flow import Flow
from wayflowcore.serialization import autodeserialize, serialize
from wayflowcore.steps import (
    CompleteStep,
    InputMessageStep,
    OutputMessageStep,
    StartStep,
)

# %%[markdown]
## Configure your LLM

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## Create storage functions

# %%
DIR_PATH = "path/to/your/dir"

def store_conversation(path: str, conversation: Conversation) -> str:
    """Store the given conversation and return the conversation id."""
    conversation_id = conversation.conversation_id
    serialized_conversation = serialize(conversation)

    # Read existing data
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
    else:
        data = {}

    # Add new conversation
    data[conversation_id] = serialized_conversation

    # Write back to file
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return conversation_id


def load_conversation(path: str, conversation_id: str) -> Conversation:
    """Load a conversation given its id."""
    with open(path, "r") as f:
        data = json.load(f)

    serialized_conversation = data[conversation_id]
    return autodeserialize(serialized_conversation)

# %%[markdown]
## Creating an agent

# %%
assistant = Agent(
    llm=llm,
    custom_instruction="You are a helpful assistant. Be concise.",
    agent_id="simple_assistant",
)

# %%[markdown]
## Run the agent

# %%
# Start a conversation
conversation = assistant.start_conversation()
conversation_id = conversation.conversation_id
print(f"1. Started conversation with ID: {conversation_id}")

# Execute initial greeting
status = conversation.execute()
print(f"2. Assistant says: {conversation.get_last_message().content}")

# Add user message
conversation.append_user_message("What is 2+2?")
print("3. User asks: What is 2+2?")

# Execute to get response
status = conversation.execute()
print(f"4. Assistant responds: {conversation.get_last_message().content}")

# %%[markdown]
## Serialize the conversation

# %%
AGENT_STORE_PATH = os.path.join(DIR_PATH, "agent_conversation.json")
store_conversation(AGENT_STORE_PATH, conversation)
print(f"5. Conversation serialized to {AGENT_STORE_PATH}")

# %%[markdown]
## Deserialize the conversation

# %%
loaded_conversation = load_conversation(AGENT_STORE_PATH, conversation_id)
print(f"6. Conversation deserialized from {AGENT_STORE_PATH}")

# Print the loaded conversation messages
print("7. Loaded conversation messages:")
messages = loaded_conversation.message_list.messages
for i, msg in enumerate(messages):
    if msg.message_type.name == "AGENT":
        role = "Assistant"
    elif msg.message_type.name == "USER":
        role = "User"
    else:
        role = msg.message_type.name
    print(f"   [{i}] {role}: {msg.content}")


# %%[markdown]
## Creating a flow

# %%
start_step = StartStep(name="start_step")
input_step = InputMessageStep(
    name="input_step",
    message_template="What's your favorite color?",
    output_mapping={InputMessageStep.USER_PROVIDED_INPUT: "user_color"},
)
output_step = OutputMessageStep(
    name="output_step", message_template="Your favorite color is {{ user_color }}. Nice choice!"
)
end_step = CompleteStep(name="end_step")

simple_flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(start_step, input_step),
        ControlFlowEdge(input_step, output_step),
        ControlFlowEdge(output_step, end_step),
    ],
    data_flow_edges=[
        DataFlowEdge(
            source_step=input_step,
            source_output="user_color",
            destination_step=output_step,
            destination_input="user_color",
        )
    ],
)

# %%[markdown]
## Run the flow

# %%
flow_conversation = simple_flow.start_conversation()
flow_id = flow_conversation.conversation_id
print(f"1. Started flow conversation with ID: {flow_id}")

# Execute until user input is needed
status = flow_conversation.execute()
print(f"2. Flow asks: {flow_conversation.get_last_message().content}")

# %%[markdown]
## Serialize before providing user input

# %%
FLOW_STORE_PATH = os.path.join(DIR_PATH, "flow_conversation.json")
store_conversation(FLOW_STORE_PATH, flow_conversation)
print(f"3. Flow conversation serialized to {FLOW_STORE_PATH}")

# %%[markdown]
## Deserialize the flow conversation

# %%
loaded_flow_conversation = load_conversation(FLOW_STORE_PATH, flow_id)
input_step_1 = loaded_flow_conversation.flow.steps['input_step']
print(f"4. Flow conversation deserialized from {FLOW_STORE_PATH}")

# Provide user input to the loaded conversation
loaded_flow_conversation.append_user_message("Blue")
print("5. User responds: Blue")

# %%[markdown]
## Resume the conversation execution

# %%
outputs = loaded_flow_conversation.execute()
print(f"6. Flow output: {outputs.output_values[OutputMessageStep.OUTPUT]}")

# Print the loaded conversation messages
print("7. Loaded flow conversation messages:")
messages = loaded_flow_conversation.message_list.messages
for i, msg in enumerate(messages):
    if msg.message_type.name == "AGENT":
        role = "Flow"
    elif msg.message_type.name == "USER":
        role = "User"
    else:
        role = msg.message_type.name
    print(f"   [{i}] {role}: {msg.content}")



# %%[markdown]
## Creating a persistent conversation loop

# %%
def run_persistent_agent(assistant: Agent, store_path: str, conversation_id: str = None):
    """Run an agent with persistent conversation storage."""

    # Load existing conversation or start new one
    if conversation_id:
        try:
            conversation = load_conversation(store_path, conversation_id)
            print(f"Resuming conversation {conversation_id}")
        except (FileNotFoundError, KeyError):
            print(f"Conversation {conversation_id} not found, starting new one")
            conversation = assistant.start_conversation()
    else:
        conversation = assistant.start_conversation()
        print(f"Started new conversation {conversation.conversation_id}")

    # Main conversation loop
    while True:
        status = conversation.execute()

        if isinstance(status, FinishedStatus):
            print("Conversation finished")
            break
        elif isinstance(status, UserMessageRequestStatus):
            # Save before waiting for user input
            store_conversation(store_path, conversation)

            print(f"Assistant: {conversation.get_last_message().content}")
            user_input = input("You: ")

            if user_input.lower() in ["exit", "quit"]:
                print("Exiting and saving conversation...")
                break

            conversation.append_user_message(user_input)

    # Final save
    final_id = store_conversation(store_path, conversation)
    print(f"Conversation saved with ID: {final_id}")
    return final_id



# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

assistant: Agent = AgentSpecLoader().load_json(serialized_assistant)
