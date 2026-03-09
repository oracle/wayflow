<a id="top-userconfirmation"></a>

# How to Add User Confirmation to Tool Call Requests![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[User Confirmation how-to script](../end_to_end_code_examples/howto_userconfirmation.py)

#### Prerequisites
This guide assumes familiarity with:

- [Agents](../tutorials/basic_agent.md)
- [Building Assistants with Tools](howto_build_assistants_with_tools.md)

WayFlow [Agents](../api/agent.md#agent) can be equipped with [Tools](../api/tools.md) to enhance their capabilities.
However, end users may want to confirm or deny tool call requests emitted from the agent.

This guide shows you how to achieve this with the [ServerTool](../api/tools.md#servertool). You can also do this using a [ClientTool](../api/tools.md#clienttool)

## Basic implementation

In this example, you will build a simple [Agent](../api/agent.md#agent) equipped with three tools:

* A tool to add numbers
* A tool to subtract numbers
* A tool to multiply numbers

This guide requires the use of an LLM.
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

To learn more about the different LLM providers, read the guide on [How to Use LLMs from Different Providers](llm_from_different_providers.md).
The sample LLM used for this guide is defined as follows:

```python
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)
```

### Creating the tools

Sometimes you will want to ask for user confirmation before executing certain tools. You can do this by using a [ServerTool](../api/tools.md#servertool) with the flag `requires_confirmation` set to `True`. This will raise a `ToolExecutionConfirmationStatus`
whenever the `Agent` tries to execute the tool. We set the multiply_numbers tool to not require confirmation to highlight the differences. Note that the `requires_confirmation` flag can be used for any WayFlow tool.

```python
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

```

### Creating the user-side execution logic

To enable users to accept or deny tool call requests, you add simple validation logic before executing the tools requested by the agent.

```python
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

```

Here, you simply loop until the user answers whether to accept the tool request or reject it. You can accept the tool request by using the `status.confirm_tool_execution` method.
While accepting, you need to specify the specific tool request and you also have the option to add `modified_args` in this method to change the arguments of the called tool.
Similarly, for rejection you can use the `status.reject_tool_execution` with an optional `reason` so that the  `Agent` can take the reason into account while planning the next action to take.

### Creating the agent

Finally, you create a simple `Agent` to test the execution code written in the previous section.

```python
from wayflowcore.agent import Agent

assistant = Agent(
    llm=llm,
    tools=[add_numbers_tool, subtract_numbers_tool, multiply_numbers_tool],
    custom_instruction="Use the tools at your disposal to answer the user requests.",
)
```

### Running the agent in an execution loop

Now, you create a simple execution loop to test the agent.
In this loop, you can input the instructions you want the agent to execute and test it out for yourself!

```python
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
```

## Recap

In this guide, you learned how to support user-side confirmation for tool call requests by using `ServerTool`.

## Next steps

Having learned how to add user confirmation for tool calls, you may now proceed to:

- [How to Create Conditional Transitions in Flows](conditional_flows.md)
- [How to Create a ServerTool from a Flow](create_a_tool_from_a_flow.md)

## Full code

Click on the card at the [top of this page](#top-userconfirmation) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Add User Confirmation
# -------------------------------------------

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
# python howto_userconfirmation.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
##Configure LLM

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)



# %%[markdown]
##Create tools

# %%
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


# %%[markdown]
##Create tool execution

# %%
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



# %%[markdown]
##Create agent

# %%
from wayflowcore.agent import Agent

assistant = Agent(
    llm=llm,
    tools=[add_numbers_tool, subtract_numbers_tool, multiply_numbers_tool],
    custom_instruction="Use the tools at your disposal to answer the user requests.",
)


# %%[markdown]
##Run tool loop

# %%
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
```
