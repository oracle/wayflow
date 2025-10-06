# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# %%[markdown]
# WayFlow Code Example - How to Execute Agent Spec with WayFlow
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
# python howto_execute_agentspec_with_wayflowcore.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.


from wayflowcore.agentspec import AgentSpecLoader
from wayflowcore.tools import tool


# %%[markdown]
## AgentSpec Configuration

# %%
AgentSpec_CONFIG = """
  $referenced_components:
    multiplication_tool:
      component_type: ServerTool
      description: Tool that allows to compute multiplications
      id: multiplication_tool
      inputs:
      - title: a
        type: integer
      - title: b
        type: integer
      name: multiplication_tool
      outputs:
      - title: product
        type: integer
    vllm_config:
      component_type: VllmConfig
      default_generation_parameters: null
      description: null
      id: vllm_config
      model_id: meta-llama/Meta-Llama-3.1-8B-Instruct
      name: llama-3.1-8b-instruct
      url: http://insert-your-model-url-here
  component_type: Agent
  llm_config:
    $component_ref: vllm_config
  name: Math homework assistant
  system_prompt: You are an assistant for helping with math homework.
  tools:
  - $component_ref: multiplication_tool
  agentspec_version: 25.4.1
"""

# %%[markdown]
## Tool Registry Setup

# %%
@tool(description_mode="only_docstring")
def multiplication_tool(a: int, b: int) -> int:
    """Tool that allows to compute multiplications."""
    return a * b

tool_registry = {
    "multiplication_tool": multiplication_tool,
}

# %%[markdown]
## Load AgentSpec Configuration

# %%
from wayflowcore.agentspec import AgentSpecLoader

loader = AgentSpecLoader(tool_registry=tool_registry)
assistant = loader.load_yaml(AgentSpec_CONFIG)

# %%[markdown]
## Execution Loop Conversational

# %%
from wayflowcore import MessageType
from wayflowcore import Agent

# %%
# Or with an execution loop
def run_agent_in_command_line(assistant: Agent):
    conversation = assistant.start_conversation()
    message_idx = 0
    while True:
        user_input = input("\nUSER >>> ")
        conversation.append_user_message(user_input)
        conversation.execute()
        messages = conversation.get_messages()
        for message in messages[message_idx + 1 :]:
            if message.message_type == MessageType.TOOL_REQUEST:
                print(f"\n{message.message_type.value} >>> {message.tool_requests}")
            else:
                print(f"\n{message.message_type.value} >>> {message.content}")
        message_idx = len(messages)

# run_agent_in_command_line(assistant)
# ^ uncomment and execute

# %%[markdown]
## Execution Loop Non Conversational

# %%
def run_agent_non_conversational(assistant: Agent):
    conversation = assistant.start_conversation({ "some_input_name": "some_input_value"})
    conversation.execute()
    for output_name, output_value in conversation.state.input_output_key_values.items():
        print(f"{output_name} >>> \n{output_value}")

# run_agent_non_conversational(assistant)
# ^ uncomment and execute

# %%[markdown]
## Export Config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(assistant)

# %%[markdown]
## Load Agent Spec Config

# %%
from wayflowcore.agentspec import AgentSpecLoader

tool_registry= {"multiplication_tool": multiplication_tool}
new_assistant = AgentSpecLoader(tool_registry=tool_registry).load_json(config)
