# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors

# docs-title: Code Example - How to Add User Confirmation

# .. start-##Configure_LLM
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)
# .. end-##Configure_LLM

llm: VllmModel # docs-skiprow
(llm, ) = _update_globals(["llm_small"]) # docs-skiprow

# .. start-##Create_tools
from wayflowcore.tools.toolhelpers import tool
from wayflowcore.executors.executionstatus import ToolExecutionConfirmationStatus

@tool(requires_confirmation=True, description_mode="only_docstring")
def add_numbers_tool(number1: float, number2:  float) -> float:
    "Add two numbers"
    return number1 + number2

@tool(requires_confirmation=True, description_mode="only_docstring")
def subtract_numbers_tool(number1: float, number2:  float) -> float:
    "Subtract two numbers"
    return number1 - number2

@tool(requires_confirmation=False, description_mode="only_docstring")
def multiply_numbers_tool(number1: float, number2:  float) -> float:
    "Multiply two numbers"
    return number1 * number2

# .. end-##Create_tools
# .. start-##Create_tool_execution
def handle_tool_execution_confirmation(
    status: ToolExecutionConfirmationStatus
) -> None:
    for tool_request in status.tool_requests:
        if tool_request.name == "add_numbers":
            status.confirm_tool_execution(tool_request = tool_request)
        elif tool_request.name == "subtract_numbers":
            status.reject_tool_execution(tool_request = tool_request, reason = "The given numbers could not be subtracted as the tool is not currently functional")
        elif tool_request.name == "multiply_numbers":
            raise ValueError(f"Tool name {tool_request.name} should not raise a ToolExecutionConfirmationStatus as it does not require confirmation")
        else:
            raise ValueError(f"Tool name {tool_request.name} is not recognized")

# .. end-##Create_tool_execution

# .. start-##Create_agent
from wayflowcore.agent import Agent

assistant = Agent(
    llm=llm,
    tools=[add_numbers_tool, subtract_numbers_tool, multiply_numbers_tool],
    custom_instruction="Use the tools at your disposal to answer the user requests.",
)
# .. end-##Create_agent

# .. start-##Run_tool_loop
from wayflowcore.executors.executionstatus import (
    FinishedStatus, UserMessageRequestStatus
)

def run_agent_in_command_line(assistant: Agent) -> None:
    conversation_inputs = {}
    conversation = assistant.start_conversation(inputs=conversation_inputs)

    while True:
        status = conversation.execute()
        assistant_reply = conversation.get_last_message()
        if assistant_reply:
            print(f"Assistant>>> {assistant_reply.content}\n")
        if isinstance(status, FinishedStatus):
            print(f"Finished assistant execution. Output values:\n{status.output_values}",)
            break
        elif isinstance(status, UserMessageRequestStatus):
            user_input = input("User>>> ")
            print("\n")
            conversation.append_user_message(user_input)
        elif isinstance(status, ToolExecutionConfirmationStatus):
            handle_tool_execution_confirmation(status)

        else:
            raise ValueError(f"Unsupported execution status: '{status}'")

# run_agent_in_command_line(assistant)
# ^ uncomment and execute
# .. end-##Run_tool_loop
