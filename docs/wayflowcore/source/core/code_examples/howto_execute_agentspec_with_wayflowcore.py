# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: WayFlow Code Example - How to Execute Agent Spec with WayFlow

from wayflowcore.agentspec import AgentSpecLoader
from wayflowcore.tools import tool

# .. start-##_AgentSpec_Configuration
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
# .. end-##_AgentSpec_Configuration
# .. start-##_Tool_Registry_Setup
@tool(description_mode="only_docstring")
def multiplication_tool(a: int, b: int) -> int:
    """Tool that allows to compute multiplications."""
    return a * b

tool_registry = {
    "multiplication_tool": multiplication_tool,
}
# .. end-##_Tool_Registry_Setup
# .. start-##_Load_AgentSpec_Configuration
from wayflowcore.agentspec import AgentSpecLoader

loader = AgentSpecLoader(tool_registry=tool_registry)
assistant = loader.load_yaml(AgentSpec_CONFIG)
# .. end-##_Load_AgentSpec_Configuration
# .. start-##_Execution_Loop_Conversational
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
# .. end-##_Execution_Loop_Conversational
# .. start-##_Execution_Loop_Non_Conversational
def run_agent_non_conversational(assistant: Agent):
    conversation = assistant.start_conversation({ "some_input_name": "some_input_value"})
    conversation.execute()
    for output_name, output_value in conversation.state.input_output_key_values.items():
        print(f"{output_name} >>> \n{output_value}")

# run_agent_non_conversational(assistant)
# ^ uncomment and execute
# .. end-##_Execution_Loop_Non_Conversational
# .. start-##_Export_Config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(assistant)
# .. end-##_Export_Config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_Config
from wayflowcore.agentspec import AgentSpecLoader

tool_registry= {"multiplication_tool": multiplication_tool}
new_assistant = AgentSpecLoader(tool_registry=tool_registry).load_json(config)
# .. end-##_Load_Agent_Spec_Config
