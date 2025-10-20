# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Code Example - How to Serialize and Deserialize Conversations

# .. start-##_Imports_for_this_guide
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
# .. end-##_Imports_for_this_guide
# .. start-##_Configure_your_LLM
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)
# .. end-##_Configure_your_LLM
# .. start-##_Create_storage_functions
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
# .. end-##_Create_storage_functions
llm: VllmModel  # docs-skiprow
(llm, DIR_PATH) = _update_globals(["llm_small", "tmp_path"])  # docs-skiprow # type: ignore
# .. start-##_Creating_an_agent
assistant = Agent(
    llm=llm,
    custom_instruction="You are a helpful assistant. Be concise.",
    agent_id="simple_assistant",
)
# .. end-##_Creating_an_agent
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader # docs-skiprow
serialized_assistant = AgentSpecExporter().to_json(assistant) # docs-skiprow
new_assistant: Agent = AgentSpecLoader().load_json(serialized_assistant) # docs-skiprow
# assert serialize(assistant) == serialize(new_assistant) # Manually verified # docs-skiprow
# .. start-##_Run_the_agent
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
# .. end-##_Run_the_agent
# .. start-##_Serialize_the_conversation
AGENT_STORE_PATH = os.path.join(DIR_PATH, "agent_conversation.json")
store_conversation(AGENT_STORE_PATH, conversation)
print(f"5. Conversation serialized to {AGENT_STORE_PATH}")
# .. end-##_Serialize_the_conversation
# .. start-##_Deserialize_the_conversation
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

# .. end-##_Deserialize_the_conversation
# .. start-##_Creating_a_flow
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
# .. end-##_Creating_a_flow
# .. start-##_Run_the_flow
flow_conversation = simple_flow.start_conversation()
flow_id = flow_conversation.conversation_id
print(f"1. Started flow conversation with ID: {flow_id}")

# Execute until user input is needed
status = flow_conversation.execute()
print(f"2. Flow asks: {flow_conversation.get_last_message().content}")
# .. end-##_Run_the_flow
# .. start-##_Serialize_before_providing_user_input
FLOW_STORE_PATH = os.path.join(DIR_PATH, "flow_conversation.json")
store_conversation(FLOW_STORE_PATH, flow_conversation)
print(f"3. Flow conversation serialized to {FLOW_STORE_PATH}")
# .. end-##_Serialize_before_providing_user_input
# .. start-##_Deserialize_the_flow_conversation
loaded_flow_conversation = load_conversation(FLOW_STORE_PATH, flow_id)
input_step_1 = loaded_flow_conversation.flow.steps['input_step']
print(f"4. Flow conversation deserialized from {FLOW_STORE_PATH}")

# Provide user input to the loaded conversation
loaded_flow_conversation.append_user_message("Blue")
print("5. User responds: Blue")
# .. end-##_Deserialize_the_flow_conversation
# .. start-##_Resume_the_conversation_execution
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


# .. end-##_Resume_the_conversation_execution
# .. start-##_Creating_a_persistent_conversation_loop
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


# .. end-##_Creating_a_persistent_conversation_loop
# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)
# .. end-##_Export_config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

assistant: Agent = AgentSpecLoader().load_json(serialized_assistant)
# .. end-##_Load_Agent_Spec_config
