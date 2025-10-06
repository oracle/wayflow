# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors

from typing import Any, List

from wayflowcore.agent import Agent
from wayflowcore.models import VllmModel
from wayflowcore.tools import ClientTool, ToolRequest

llm = VllmModel(
    model_id="meta-llama/Meta-Llama-3.1-8B-Instruct",
    host_port=os.environ["MY_LLM_HOST_PORT"],
)

# .. start-create_tools:
from wayflowcore.tools import ClientTool

add_numbers_tool = ClientTool(
    name="add_numbers",
    description="Add two numbers",
    parameters={
        "number1": {"description": "the first number", "type": "number"},
        "number2": {"description": "the second number", "type": "number"},
    },
    output={"type": "number"},
)
subtract_numbers_tool = ClientTool(
    name="subtract_numbers",
    description="Subtract two numbers",
    parameters={
        "number1": {"description": "the first number", "type": "number"},
        "number2": {"description": "the second number", "type": "number"},
    },
    output={"type": "number"},
)
multiply_numbers_tool = ClientTool(
    name="multiply_numbers",
    description="Multiply two numbers",
    parameters={
        "number1": {"description": "the first number", "type": "number"},
        "number2": {"description": "the second number", "type": "number"},
    },
    output={"type": "number"},
)
# .. end-create_tools
# .. start-create_tool_execution:
from typing import Any, List

from wayflowcore.tools import ToolRequest


def _add_numbers(number1: float, number2: float) -> float:
    return number1 + number2


def _subtract_numbers(number1: float, number2: float) -> float:
    return number1 - number2


def _multiply_numbers(number1: float, number2: float) -> float:
    return number1 * number2


def _ask_for_user_confirmation(tool_request: ToolRequest) -> bool:
    import json

    message = (
        "---\nThe Agent requests the following Tool Call:\n"
        f"Name: `{tool_request.name}`\n"
        f"Args: {json.dumps(tool_request.args, indent=2)}\n---\n"
        f"Do you accept this tool call request? (Y/N)\n"
        ">>> "
    )
    while True:
        user_response = input(message).strip()
        if user_response == "Y":
            return True
        elif user_response == "N":
            return False
        print(f"Unrecognized option: `{user_response}`.")


def execute_client_tool_from_tool_request(
    tool_request: ToolRequest, tools_requiring_confirmation: List[str]
) -> Any:
    if tool_request.name in tools_requiring_confirmation:
        is_confirmed = _ask_for_user_confirmation(tool_request)
        if not is_confirmed:
            return (
                f"The user denied the tool request for the tool {tool_request.name} at this time."
            )

    if tool_request.name == "add_numbers":
        return _add_numbers(**tool_request.args)
    elif tool_request.name == "subtract_numbers":
        return _subtract_numbers(**tool_request.args)
    elif tool_request.name == "multiply_numbers":
        return _multiply_numbers(**tool_request.args)
    else:
        raise ValueError(f"Tool name {tool_request.name} is not recognized")


# .. end-create_tool_execution

# .. start-create_agent:
from wayflowcore.agent import Agent

assistant = Agent(
    llm=llm,
    tools=[add_numbers_tool, subtract_numbers_tool, multiply_numbers_tool],
    custom_instruction="Use the tools at your disposal to answer the user requests.",
)
# .. end-create_agent:
