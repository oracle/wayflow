<a id="top-userinputinflows"></a>

# How to Ask for User Input in Flows![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[User input in flows how-to script](../end_to_end_code_examples/howto_userinputinflows.py)

#### Prerequisites
This guide assumes familiarity with:

- [Flows](../tutorials/basic_flow.md)
- [Tools](../api/tools.md)

WayFlow allows you to build powerful automation and agentic workflows.
In many real-world scenarios, your flows will need to request and incorporate input from a human user — either to execute a particular action, validate a decision, or simply continue the process.

This guide explains how to design flows that pause for user input, receive responses, and resume execution seamlessly (also known as Human-in-the-loop (HITL) machine learning).

## Overview

There are two standard patterns for requesting user input within a flow:

- **Simple user requests** (e.g., prompting the user for a question or parameter)
- **Interactive/branching patterns** (e.g., asking for confirmation before performing an action, with logic based on the user’s response)

This guide will show you how to:

- Add a user input request to your flow using the [InputMessageStep](../api/flows.md#inputmessagestep)
- Connect user responses to further steps for flexible flow logic
- Chain multiple interactions, including branching for confirmation scenarios

#### NOTE
User input is always delivered via `InputMessageStep`. WayFlow’s status objects make it easy to detect when input is required and to resume execution once the user has responded.

## Basic implementation

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

The easiest way to capture user input is with `InputMessageStep`.
Used in combination with an execution loop, this step is used to prompt the user for input,
pause flow execution, and deliver the user’s response into the flow’s data context for
use by subsequent steps.

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import (
    BranchingStep,
    CompleteStep,
    ExtractValueFromJsonStep,
    InputMessageStep,
    PromptExecutionStep,
    StartStep,
    ToolExecutionStep,
)
from wayflowcore.tools import tool

@tool(description_mode="only_docstring")
def get_user_name_tool() -> str:
    """Tool to get user name."""
    return "Alice"

start_step = StartStep(name="start")

get_user_name_step = ToolExecutionStep(
    name="get_user_name_step",
    tool=get_user_name_tool,
)

ask_user_request_step = InputMessageStep(
    name="ask_user_request_step", message_template="Hi {{username}}. What can I do for you today?"
)

answer_request_step = PromptExecutionStep(
    name="answer_request_step",
    llm=llm,
    prompt_template="Your are an helpful assistant. Help answer the user request: {{request}}",
    output_mapping={
        PromptExecutionStep.OUTPUT: "my_output"
    },  # what we want to expose as the output name
)

end_step = CompleteStep(name="end")

flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(start_step, get_user_name_step),
        ControlFlowEdge(get_user_name_step, ask_user_request_step),
        ControlFlowEdge(ask_user_request_step, answer_request_step),
        ControlFlowEdge(answer_request_step, end_step),
    ],
    data_flow_edges=[
        DataFlowEdge(
            get_user_name_step, ToolExecutionStep.TOOL_OUTPUT, ask_user_request_step, "username"
        ),
        DataFlowEdge(
            ask_user_request_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            answer_request_step,
            "request",
        ),
    ],
)
```

API Reference: [Flow](../api/flows.md#flow) | [InputMessageStep](../api/flows.md#inputmessagestep) | [CompleteStep](../api/flows.md#completestep)

You can then execute this flow as shown below. Notice how the execution is paused until the user enters their input:

```python
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
conversation = flow.start_conversation()
status = (
    conversation.execute()
)  # will get the user input, then pause the execution to ask for the user input

if not isinstance(status, UserMessageRequestStatus):
    raise ValueError(
        f"Execution status should be {UserMessageRequestStatus.__name__}, was {type(status)}"
    )
print(conversation.get_last_message().content)
# Hi Alice. What can I do for you today?

conversation.append_user_message("What is heavier? 20 pounds of bricks of 20 feathers?")
status = conversation.execute()  # we resume the execution

if not isinstance(status, FinishedStatus):
    raise ValueError(f"Execution status should be {FinishedStatus.__name__}, was {type(status)}")
print(
    status.output_values["my_output"]
)  # using the key name that we defined in the `output_mapping`
# [...] a surprisingly simple answer emerges: 20 pounds of bricks is heavier than 20 feathers by a massive margin, approximately 69.78 pounds.
```

#### NOTE
When `conversation.execute()` returns a `UserMessageRequestStatus`, you must append a user message (with `conversation.append_user_message(...)`) to continue the flow.

## Advanced pattern: Request user input for tool calls or approvals

#### SEE ALSO
For details on enabling client-side confirmations, see the guide [How to Add User Confirmation to Tool Call Requests](howto_userconfirmation.md).

In some cases, it is necessary not only to collect a user’s initial input but also request confirmation before executing certain actions — such as validating tool calls or branching flow execution based on user responses.

The following example demonstrates a more sophisticated flow.
The flow pauses both for the user’s main request and again for tool call confirmation, using branching to repeat or skip steps depending on the response.

```python
import json
from typing import Dict

from wayflowcore.contextproviders.constantcontextprovider import ConstantContextProvider
from wayflowcore.property import DictProperty, StringProperty

@tool(description_mode="only_docstring")
def my_tool(params: Dict[str, str]) -> str:
    """Params: {"param": str}"""
    return f"Invoked tool with {params=}"

prompt_template = """
Your are an helpful assistant. Help answer the user request.

Here is the list of tools:
{{tools}}

Here is the user request:
{{request}}

## Response format
Your response should be JSON-compliant dictionary with the following structure.

{
    "action": "answer|execute_tool",
    "tool_name": "None|tool_name",
    "tool_args": {"param1": "value1"}
}

When the action is "answer", "tool_name" should be "None" and "tool_args" should be {}
When the action is "execute_tool", "tool_name" should be the name of the tool to execute
and "tool_args" should be the JSON-compliant dictionary of arguments to pass to the tool.

CRITICAL: Only output the JSON-compliant dictionary otherwise the parsing will fail.
fail.
""".strip()

available_tools = [my_tool]
tool_context_provider = ConstantContextProvider(
    json.dumps([tool_.to_dict() for tool_ in available_tools]),
    output_description=StringProperty("tool_info"),
)

generate_action_step = PromptExecutionStep(
    name="generate_action_step", llm=llm, prompt_template=prompt_template
)

extract_result_step = ExtractValueFromJsonStep(
    name="extract_result_step",
    output_values={
        "action": ".action",
        "tool_name": ".tool_name",
        "tool_args": ".tool_args",
    },
    output_descriptors=[
        StringProperty(name='action'),
        StringProperty(name='tool_name'),
        DictProperty(name='tool_args'),
    ]
)

branching_step = BranchingStep(
    name="branching_step", branch_name_mapping={"answer": "answer", "execute_tool": "execute_tool"}
)

answer_end_step = CompleteStep(name="answer_end_step")

user_tool_validation_step = InputMessageStep(
    name="user_tool_validation_step",
    message_template="Requesting to invoke tool {{name}} with parameters {{params}}. Do you accept the request? (y/n)",
)

tool_selection_branching_step = BranchingStep(
    name="tool_selection_branching_step",
    branch_name_mapping={"y": "execute_tool", "n": "retry_llm"},
)

invoke_tool_step = ToolExecutionStep(
    name="invoke_tool_step",
    tool=my_tool,
)

invoke_tool_end_step = CompleteStep(name="invoke_tool_end_step")

flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(start_step, get_user_name_step),
        ControlFlowEdge(get_user_name_step, ask_user_request_step),
        ControlFlowEdge(ask_user_request_step, generate_action_step),
        ControlFlowEdge(generate_action_step, extract_result_step),
        ControlFlowEdge(extract_result_step, branching_step),
        ControlFlowEdge(branching_step, answer_end_step, source_branch="answer"),
        ControlFlowEdge(branching_step, user_tool_validation_step, source_branch="execute_tool"),
        ControlFlowEdge(
            branching_step, answer_end_step, source_branch=BranchingStep.BRANCH_DEFAULT
        ),
        ControlFlowEdge(user_tool_validation_step, tool_selection_branching_step),
        ControlFlowEdge(
            tool_selection_branching_step, invoke_tool_step, source_branch="execute_tool"
        ),
        ControlFlowEdge(
            tool_selection_branching_step, generate_action_step, source_branch="retry_llm"
        ),
        ControlFlowEdge(
            tool_selection_branching_step,
            generate_action_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(invoke_tool_step, invoke_tool_end_step),
    ],
    data_flow_edges=[
        DataFlowEdge(
            get_user_name_step, ToolExecutionStep.TOOL_OUTPUT, ask_user_request_step, "username"
        ),
        DataFlowEdge(
            ask_user_request_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            generate_action_step,
            "request",
        ),
        DataFlowEdge(tool_context_provider, "tool_info", generate_action_step, "tools"),
        DataFlowEdge(
            generate_action_step,
            PromptExecutionStep.OUTPUT,
            extract_result_step,
            ExtractValueFromJsonStep.TEXT,
        ),
        DataFlowEdge(extract_result_step, "action", branching_step, BranchingStep.NEXT_BRANCH_NAME),
        DataFlowEdge(extract_result_step, "tool_name", user_tool_validation_step, "name"),
        DataFlowEdge(extract_result_step, "tool_args", user_tool_validation_step, "params"),
        DataFlowEdge(
            user_tool_validation_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            tool_selection_branching_step,
            BranchingStep.NEXT_BRANCH_NAME,
        ),
        DataFlowEdge(extract_result_step, "tool_args", invoke_tool_step, "params"),
    ],
)
```

API Reference: [Flow](../api/flows.md#flow) | [InputMessageStep](../api/flows.md#inputmessagestep) | [BranchingStep](../api/flows.md#branchingstep) | [ToolExecutionStep](../api/flows.md#toolexecutionstep)

#### NOTE
The `InputMessageStep` can be reused at multiple points in a flow for different types of input—questions, approvals, parameter selection, etc. Use `BranchingStep` to control your logic flow depending on the user’s reply.

To drive this advanced flow, you execute and interact with the agent as follows:

```python
conversation = flow.start_conversation()
status = (
    conversation.execute()
)  # will get the user input, then pause the execution to ask for the user input

if not isinstance(status, UserMessageRequestStatus):
    raise ValueError(
        f"Execution status should be {UserMessageRequestStatus.__name__}, was {type(status)}"
    )
print(conversation.get_last_message().content)
# Hi Alice. What can I do for you today?

conversation.append_user_message("Invoke the tool with parameter 'value#007'")
status = conversation.execute()  # we resume the execution

if not isinstance(status, UserMessageRequestStatus):
    raise ValueError(
        f"Execution status should be {UserMessageRequestStatus.__name__}, was {type(status)}"
    )
print(conversation.get_last_message().content)
# Requesting to invoke tool my_tool with parameters {"param": "value#007"}. Do you accept the request? (y/n)

conversation.append_user_message("y")  # we accept the tool call request
status = conversation.execute()  # we resume the execution

if not isinstance(status, FinishedStatus):
    raise ValueError(f"Execution status should be {FinishedStatus.__name__}, was {type(status)}")

print(status.output_values[ToolExecutionStep.TOOL_OUTPUT])
# Invoked tool with params={'param': 'value#007'}
```

#### TIP
Design your `message_template` and branching mapping to ensure robust, user-friendly interactions.
You can combine user input at any point with decision logic for flexible, agent-like flows.

You can also use [CatchExceptionStep](../api/flows.md#catchexceptionstep) to handle issues such as user typing something else than “y/n”.

## Agent Spec Exporting/Loading

You can export the flow configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(flow)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "ExtendedFlow",
  "id": "44ca9623-5567-4abc-8972-065df61d94e7",
  "name": "flow_edbb400a__auto",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [],
  "outputs": [
    {
      "type": "string",
      "title": "tool_output"
    },
    {
      "description": "the generated text",
      "type": "string",
      "title": "output"
    },
    {
      "type": "string",
      "title": "tool_name"
    },
    {
      "type": "object",
      "additionalProperties": {
        "type": "string"
      },
      "key_type": {
        "type": "string"
      },
      "title": "tool_args"
    },
    {
      "type": "string",
      "title": "action"
    },
    {
      "description": "the input value provided by the user",
      "type": "string",
      "title": "user_provided_input"
    }
  ],
  "start_node": {
    "$component_ref": "df2e111a-b6ac-4c66-8d57-99e0b9c94fdd"
  },
  "nodes": [
    {
      "$component_ref": "df2e111a-b6ac-4c66-8d57-99e0b9c94fdd"
    },
    {
      "$component_ref": "a3614787-eae2-4330-a5be-cf8bdad4544d"
    },
    {
      "$component_ref": "28f6f69b-aa81-49f7-be22-c51a3b0baaa5"
    },
    {
      "$component_ref": "d093d2ee-d8cd-40f7-9163-154d3ae72a22"
    },
    {
      "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
    },
    {
      "$component_ref": "6e5fcaaf-1cf2-443d-9def-14c99333be68"
    },
    {
      "$component_ref": "e2126f15-b523-44de-a087-971799a810c2"
    },
    {
      "$component_ref": "82460353-8eac-483d-967e-04fa7614d5c4"
    },
    {
      "$component_ref": "6c170ac9-3277-4581-841a-8edf4db175e0"
    },
    {
      "$component_ref": "2ae6af7c-4c67-49a8-b578-f1666466a4ca"
    },
    {
      "$component_ref": "d326fb5d-a9b0-4845-aaba-b8f01e523471"
    }
  ],
  "control_flow_connections": [
    {
      "component_type": "ControlFlowEdge",
      "id": "42271781-8986-4ffc-be77-2700dd947ec5",
      "name": "start_to_get_user_name_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "df2e111a-b6ac-4c66-8d57-99e0b9c94fdd"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "a3614787-eae2-4330-a5be-cf8bdad4544d"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "1c830ec0-c8a5-41da-8565-12cc0a933e19",
      "name": "get_user_name_step_to_ask_user_request_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "a3614787-eae2-4330-a5be-cf8bdad4544d"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "28f6f69b-aa81-49f7-be22-c51a3b0baaa5"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "cb0100a1-307a-4352-bc69-550eb5c62d9a",
      "name": "ask_user_request_step_to_generate_action_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "28f6f69b-aa81-49f7-be22-c51a3b0baaa5"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "d093d2ee-d8cd-40f7-9163-154d3ae72a22"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "07c38ae3-0246-492b-bf11-7922004432fa",
      "name": "generate_action_step_to_extract_result_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "d093d2ee-d8cd-40f7-9163-154d3ae72a22"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "04308f40-8171-4651-8dbf-fbf527f8f9ed",
      "name": "extract_result_step_to_branching_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "6e5fcaaf-1cf2-443d-9def-14c99333be68"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "dab13845-d78b-4e5c-addf-cbd28f84da70",
      "name": "branching_step_to_answer_end_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "6e5fcaaf-1cf2-443d-9def-14c99333be68"
      },
      "from_branch": "answer",
      "to_node": {
        "$component_ref": "2ae6af7c-4c67-49a8-b578-f1666466a4ca"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "29c13062-7060-4878-8f32-b2a3735bf892",
      "name": "branching_step_to_user_tool_validation_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "6e5fcaaf-1cf2-443d-9def-14c99333be68"
      },
      "from_branch": "execute_tool",
      "to_node": {
        "$component_ref": "e2126f15-b523-44de-a087-971799a810c2"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "46f0cae7-aef3-4387-8c34-c8442f6008f5",
      "name": "branching_step_to_answer_end_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "6e5fcaaf-1cf2-443d-9def-14c99333be68"
      },
      "from_branch": "default",
      "to_node": {
        "$component_ref": "2ae6af7c-4c67-49a8-b578-f1666466a4ca"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "aec3a3d8-feba-40dd-839a-59690f17939c",
      "name": "user_tool_validation_step_to_tool_selection_branching_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "e2126f15-b523-44de-a087-971799a810c2"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "82460353-8eac-483d-967e-04fa7614d5c4"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "4506945a-6f39-4839-a910-c3eee14ad872",
      "name": "tool_selection_branching_step_to_invoke_tool_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "82460353-8eac-483d-967e-04fa7614d5c4"
      },
      "from_branch": "execute_tool",
      "to_node": {
        "$component_ref": "6c170ac9-3277-4581-841a-8edf4db175e0"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "eac1e546-a9e9-436b-a83b-63a74ad93bc6",
      "name": "tool_selection_branching_step_to_generate_action_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "82460353-8eac-483d-967e-04fa7614d5c4"
      },
      "from_branch": "retry_llm",
      "to_node": {
        "$component_ref": "d093d2ee-d8cd-40f7-9163-154d3ae72a22"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "8a20f70d-399f-41f1-8191-85502c5e947a",
      "name": "tool_selection_branching_step_to_generate_action_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "82460353-8eac-483d-967e-04fa7614d5c4"
      },
      "from_branch": "default",
      "to_node": {
        "$component_ref": "d093d2ee-d8cd-40f7-9163-154d3ae72a22"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "2487e15a-0f1c-4529-8b60-d21c43e1b926",
      "name": "invoke_tool_step_to_invoke_tool_end_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "6c170ac9-3277-4581-841a-8edf4db175e0"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "d326fb5d-a9b0-4845-aaba-b8f01e523471"
      }
    }
  ],
  "data_flow_connections": [
    {
      "component_type": "DataFlowEdge",
      "id": "3f74cc4f-237c-491d-8fd1-3ff44e08b6a8",
      "name": "get_user_name_step_tool_output_to_ask_user_request_step_username_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "a3614787-eae2-4330-a5be-cf8bdad4544d"
      },
      "source_output": "tool_output",
      "destination_node": {
        "$component_ref": "28f6f69b-aa81-49f7-be22-c51a3b0baaa5"
      },
      "destination_input": "username"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "476856ed-4b35-49e0-bb12-c29a53faf97f",
      "name": "ask_user_request_step_user_provided_input_to_generate_action_step_request_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "28f6f69b-aa81-49f7-be22-c51a3b0baaa5"
      },
      "source_output": "user_provided_input",
      "destination_node": {
        "$component_ref": "d093d2ee-d8cd-40f7-9163-154d3ae72a22"
      },
      "destination_input": "request"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "c40dadcb-35e9-4b41-bae1-2960e69852ce",
      "name": "a91502a3-117f-40af-a000-3663a3db87e3_tool_info_to_generate_action_step_tools_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "a91502a3-117f-40af-a000-3663a3db87e3"
      },
      "source_output": "tool_info",
      "destination_node": {
        "$component_ref": "d093d2ee-d8cd-40f7-9163-154d3ae72a22"
      },
      "destination_input": "tools"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "eec02f81-55e0-42c7-b3f4-12c364c52ed2",
      "name": "generate_action_step_output_to_extract_result_step_text_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "d093d2ee-d8cd-40f7-9163-154d3ae72a22"
      },
      "source_output": "output",
      "destination_node": {
        "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
      },
      "destination_input": "text"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "f7e9acbe-c472-45d8-bf92-b35f436190be",
      "name": "extract_result_step_action_to_branching_step_next_step_name_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
      },
      "source_output": "action",
      "destination_node": {
        "$component_ref": "6e5fcaaf-1cf2-443d-9def-14c99333be68"
      },
      "destination_input": "next_step_name"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "3a2ff915-ca72-43f3-b6a2-f9a3dbceb621",
      "name": "extract_result_step_tool_name_to_user_tool_validation_step_name_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
      },
      "source_output": "tool_name",
      "destination_node": {
        "$component_ref": "e2126f15-b523-44de-a087-971799a810c2"
      },
      "destination_input": "name"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "30845c9b-4b4c-4108-9b4e-4ebb9f881e32",
      "name": "extract_result_step_tool_args_to_user_tool_validation_step_params_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
      },
      "source_output": "tool_args",
      "destination_node": {
        "$component_ref": "e2126f15-b523-44de-a087-971799a810c2"
      },
      "destination_input": "params"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "3baa59bf-c302-434c-ac8c-55e5051db3e3",
      "name": "user_tool_validation_step_user_provided_input_to_tool_selection_branching_step_next_step_name_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "e2126f15-b523-44de-a087-971799a810c2"
      },
      "source_output": "user_provided_input",
      "destination_node": {
        "$component_ref": "82460353-8eac-483d-967e-04fa7614d5c4"
      },
      "destination_input": "next_step_name"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "c0fd3d7a-9d7d-471e-962a-a99e5fb52c96",
      "name": "extract_result_step_tool_args_to_invoke_tool_step_params_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
      },
      "source_output": "tool_args",
      "destination_node": {
        "$component_ref": "6c170ac9-3277-4581-841a-8edf4db175e0"
      },
      "destination_input": "params"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "9596e6a9-2b6f-4cc7-b9d8-ce778112c92d",
      "name": "get_user_name_step_tool_output_to_answer_end_step_tool_output_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "a3614787-eae2-4330-a5be-cf8bdad4544d"
      },
      "source_output": "tool_output",
      "destination_node": {
        "$component_ref": "2ae6af7c-4c67-49a8-b578-f1666466a4ca"
      },
      "destination_input": "tool_output"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "16eece12-6815-479e-b47f-7b09fc400604",
      "name": "invoke_tool_step_tool_output_to_answer_end_step_tool_output_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "6c170ac9-3277-4581-841a-8edf4db175e0"
      },
      "source_output": "tool_output",
      "destination_node": {
        "$component_ref": "2ae6af7c-4c67-49a8-b578-f1666466a4ca"
      },
      "destination_input": "tool_output"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "a16f467c-401a-4135-9d43-b777800e48fa",
      "name": "generate_action_step_output_to_answer_end_step_output_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "d093d2ee-d8cd-40f7-9163-154d3ae72a22"
      },
      "source_output": "output",
      "destination_node": {
        "$component_ref": "2ae6af7c-4c67-49a8-b578-f1666466a4ca"
      },
      "destination_input": "output"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "dd868b71-39c5-41c3-b6b0-520595600b9c",
      "name": "extract_result_step_tool_name_to_answer_end_step_tool_name_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
      },
      "source_output": "tool_name",
      "destination_node": {
        "$component_ref": "2ae6af7c-4c67-49a8-b578-f1666466a4ca"
      },
      "destination_input": "tool_name"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "a489f8cc-3be4-435a-8a2c-1bffd290f5c2",
      "name": "extract_result_step_tool_args_to_answer_end_step_tool_args_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
      },
      "source_output": "tool_args",
      "destination_node": {
        "$component_ref": "2ae6af7c-4c67-49a8-b578-f1666466a4ca"
      },
      "destination_input": "tool_args"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "739bacd9-78b9-470a-9dae-f784870998c1",
      "name": "extract_result_step_action_to_answer_end_step_action_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
      },
      "source_output": "action",
      "destination_node": {
        "$component_ref": "2ae6af7c-4c67-49a8-b578-f1666466a4ca"
      },
      "destination_input": "action"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "9e275423-8504-4d56-8c02-229101af294c",
      "name": "ask_user_request_step_user_provided_input_to_answer_end_step_user_provided_input_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "28f6f69b-aa81-49f7-be22-c51a3b0baaa5"
      },
      "source_output": "user_provided_input",
      "destination_node": {
        "$component_ref": "2ae6af7c-4c67-49a8-b578-f1666466a4ca"
      },
      "destination_input": "user_provided_input"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "da295e5e-8abb-4d16-b39b-3853e0df310d",
      "name": "user_tool_validation_step_user_provided_input_to_answer_end_step_user_provided_input_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "e2126f15-b523-44de-a087-971799a810c2"
      },
      "source_output": "user_provided_input",
      "destination_node": {
        "$component_ref": "2ae6af7c-4c67-49a8-b578-f1666466a4ca"
      },
      "destination_input": "user_provided_input"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "4bc35cfb-8f77-4537-8ce6-a12f6f19a554",
      "name": "get_user_name_step_tool_output_to_invoke_tool_end_step_tool_output_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "a3614787-eae2-4330-a5be-cf8bdad4544d"
      },
      "source_output": "tool_output",
      "destination_node": {
        "$component_ref": "d326fb5d-a9b0-4845-aaba-b8f01e523471"
      },
      "destination_input": "tool_output"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "4a1242bb-cb58-4578-be57-4a11764f19a5",
      "name": "invoke_tool_step_tool_output_to_invoke_tool_end_step_tool_output_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "6c170ac9-3277-4581-841a-8edf4db175e0"
      },
      "source_output": "tool_output",
      "destination_node": {
        "$component_ref": "d326fb5d-a9b0-4845-aaba-b8f01e523471"
      },
      "destination_input": "tool_output"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "307aef79-4a11-4bd7-8cfd-90d8ab4c5d52",
      "name": "generate_action_step_output_to_invoke_tool_end_step_output_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "d093d2ee-d8cd-40f7-9163-154d3ae72a22"
      },
      "source_output": "output",
      "destination_node": {
        "$component_ref": "d326fb5d-a9b0-4845-aaba-b8f01e523471"
      },
      "destination_input": "output"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "c31a0fba-93c9-46a8-a21e-efdcff8d1130",
      "name": "extract_result_step_tool_name_to_invoke_tool_end_step_tool_name_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
      },
      "source_output": "tool_name",
      "destination_node": {
        "$component_ref": "d326fb5d-a9b0-4845-aaba-b8f01e523471"
      },
      "destination_input": "tool_name"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "d5ea1f13-b60a-4010-bfd9-318a81cba2f3",
      "name": "extract_result_step_tool_args_to_invoke_tool_end_step_tool_args_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
      },
      "source_output": "tool_args",
      "destination_node": {
        "$component_ref": "d326fb5d-a9b0-4845-aaba-b8f01e523471"
      },
      "destination_input": "tool_args"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "8b3a2623-4d26-41ba-881a-8b5a566b8d7e",
      "name": "extract_result_step_action_to_invoke_tool_end_step_action_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb"
      },
      "source_output": "action",
      "destination_node": {
        "$component_ref": "d326fb5d-a9b0-4845-aaba-b8f01e523471"
      },
      "destination_input": "action"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "5361e910-0b85-490a-b9bd-0613eed38037",
      "name": "ask_user_request_step_user_provided_input_to_invoke_tool_end_step_user_provided_input_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "28f6f69b-aa81-49f7-be22-c51a3b0baaa5"
      },
      "source_output": "user_provided_input",
      "destination_node": {
        "$component_ref": "d326fb5d-a9b0-4845-aaba-b8f01e523471"
      },
      "destination_input": "user_provided_input"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "346f5ff8-f0a6-4b0d-9727-69a79a2f5489",
      "name": "user_tool_validation_step_user_provided_input_to_invoke_tool_end_step_user_provided_input_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "e2126f15-b523-44de-a087-971799a810c2"
      },
      "source_output": "user_provided_input",
      "destination_node": {
        "$component_ref": "d326fb5d-a9b0-4845-aaba-b8f01e523471"
      },
      "destination_input": "user_provided_input"
    }
  ],
  "context_providers": [
    {
      "$component_ref": "a91502a3-117f-40af-a000-3663a3db87e3"
    }
  ],
  "component_plugin_name": "FlowPlugin",
  "component_plugin_version": "25.4.0.dev0",
  "$referenced_components": {
    "28f6f69b-aa81-49f7-be22-c51a3b0baaa5": {
      "component_type": "PluginInputMessageNode",
      "id": "28f6f69b-aa81-49f7-be22-c51a3b0baaa5",
      "name": "ask_user_request_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "\"username\" input variable for the template",
          "type": "string",
          "title": "username"
        }
      ],
      "outputs": [
        {
          "description": "the input value provided by the user",
          "type": "string",
          "title": "user_provided_input"
        }
      ],
      "branches": [
        "next"
      ],
      "input_mapping": {},
      "output_mapping": {},
      "message_template": "Hi {{username}}. What can I do for you today?",
      "rephrase": false,
      "llm_config": null,
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "25.4.0.dev0"
    },
    "a3614787-eae2-4330-a5be-cf8bdad4544d": {
      "component_type": "ExtendedToolNode",
      "id": "a3614787-eae2-4330-a5be-cf8bdad4544d",
      "name": "get_user_name_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [],
      "outputs": [
        {
          "type": "string",
          "title": "tool_output"
        }
      ],
      "branches": [
        "next"
      ],
      "tool": {
        "component_type": "ServerTool",
        "id": "cfd9cae9-38b9-4b48-9a52-d324899a4859",
        "name": "get_user_name_tool",
        "description": "Tool to get user name.",
        "metadata": {
          "__metadata_info__": {}
        },
        "inputs": [],
        "outputs": [
          {
            "type": "string",
            "title": "tool_output"
          }
        ]
      },
      "input_mapping": {},
      "output_mapping": {},
      "raise_exceptions": false,
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "25.4.0.dev0"
    },
    "d093d2ee-d8cd-40f7-9163-154d3ae72a22": {
      "component_type": "LlmNode",
      "id": "d093d2ee-d8cd-40f7-9163-154d3ae72a22",
      "name": "generate_action_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "\"tools\" input variable for the template",
          "type": "string",
          "title": "tools"
        },
        {
          "description": "\"request\" input variable for the template",
          "type": "string",
          "title": "request"
        }
      ],
      "outputs": [
        {
          "description": "the generated text",
          "type": "string",
          "title": "output"
        }
      ],
      "branches": [
        "next"
      ],
      "llm_config": {
        "component_type": "VllmConfig",
        "id": "5fdf143c-a7ee-459c-8ff8-409df206e73b",
        "name": "LLAMA_MODEL_ID",
        "description": null,
        "metadata": {
          "__metadata_info__": {}
        },
        "default_generation_parameters": null,
        "url": "LLAMA_API_URL",
        "model_id": "LLAMA_MODEL_ID"
      },
      "prompt_template": "Your are an helpful assistant. Help answer the user request.\n\nHere is the list of tools:\n{{tools}}\n\nHere is the user request:\n{{request}}\n\n## Response format\nYour response should be JSON-compliant dictionary with the following structure.\n\n{\n    \"action\": \"answer|execute_tool\",\n    \"tool_name\": \"None|tool_name\",\n    \"tool_args\": {\"param1\": \"value1\"}\n}\n\nWhen the action is \"answer\", \"tool_name\" should be \"None\" and \"tool_args\" should be {}\nWhen the action is \"execute_tool\", \"tool_name\" should be the name of the tool to execute\nand \"tool_args\" should be the JSON-compliant dictionary of arguments to pass to the tool.\n\nCRITICAL: Only output the JSON-compliant dictionary otherwise the parsing will fail.\nfail."
    },
    "a91502a3-117f-40af-a000-3663a3db87e3": {
      "component_type": "PluginConstantContextProvider",
      "id": "a91502a3-117f-40af-a000-3663a3db87e3",
      "name": "a91502a3-117f-40af-a000-3663a3db87e3",
      "description": null,
      "metadata": {},
      "inputs": [],
      "outputs": [
        {
          "type": "string",
          "title": "tool_info"
        }
      ],
      "branches": [
        "next"
      ],
      "value": "[{\"name\": \"my_tool\", \"description\": \"Params: {\\\"param\\\": str}\", \"parameters\": {\"params\": {\"type\": \"object\", \"additionalProperties\": {\"type\": \"string\"}, \"title\": \"Params\"}}}]",
      "component_plugin_name": "ContextProviderPlugin",
      "component_plugin_version": "25.4.0.dev0"
    },
    "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb": {
      "component_type": "PluginExtractNode",
      "id": "b31c569b-2a66-4f2b-a98d-f52bfca2dfeb",
      "name": "extract_result_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "raw text to extract information from",
          "type": "string",
          "title": "text"
        }
      ],
      "outputs": [
        {
          "type": "string",
          "title": "action"
        },
        {
          "type": "string",
          "title": "tool_name"
        },
        {
          "type": "object",
          "additionalProperties": {
            "type": "string"
          },
          "key_type": {
            "type": "string"
          },
          "title": "tool_args"
        }
      ],
      "branches": [
        "next"
      ],
      "input_mapping": {},
      "output_mapping": {},
      "output_values": {
        "action": ".action",
        "tool_name": ".tool_name",
        "tool_args": ".tool_args"
      },
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "25.4.0.dev0"
    },
    "6e5fcaaf-1cf2-443d-9def-14c99333be68": {
      "component_type": "BranchingNode",
      "id": "6e5fcaaf-1cf2-443d-9def-14c99333be68",
      "name": "branching_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "Next branch name in the flow",
          "type": "string",
          "title": "next_step_name",
          "default": "default"
        }
      ],
      "outputs": [],
      "branches": [
        "answer",
        "default",
        "execute_tool"
      ],
      "mapping": {
        "answer": "answer",
        "execute_tool": "execute_tool"
      }
    },
    "e2126f15-b523-44de-a087-971799a810c2": {
      "component_type": "PluginInputMessageNode",
      "id": "e2126f15-b523-44de-a087-971799a810c2",
      "name": "user_tool_validation_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "\"name\" input variable for the template",
          "type": "string",
          "title": "name"
        },
        {
          "description": "\"params\" input variable for the template",
          "type": "string",
          "title": "params"
        }
      ],
      "outputs": [
        {
          "description": "the input value provided by the user",
          "type": "string",
          "title": "user_provided_input"
        }
      ],
      "branches": [
        "next"
      ],
      "input_mapping": {},
      "output_mapping": {},
      "message_template": "Requesting to invoke tool {{name}} with parameters {{params}}. Do you accept the request? (y/n)",
      "rephrase": false,
      "llm_config": null,
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "25.4.0.dev0"
    },
    "82460353-8eac-483d-967e-04fa7614d5c4": {
      "component_type": "BranchingNode",
      "id": "82460353-8eac-483d-967e-04fa7614d5c4",
      "name": "tool_selection_branching_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "Next branch name in the flow",
          "type": "string",
          "title": "next_step_name",
          "default": "default"
        }
      ],
      "outputs": [],
      "branches": [
        "default",
        "execute_tool",
        "retry_llm"
      ],
      "mapping": {
        "y": "execute_tool",
        "n": "retry_llm"
      }
    },
    "6c170ac9-3277-4581-841a-8edf4db175e0": {
      "component_type": "ExtendedToolNode",
      "id": "6c170ac9-3277-4581-841a-8edf4db175e0",
      "name": "invoke_tool_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "object",
          "additionalProperties": {
            "type": "string"
          },
          "title": "params"
        }
      ],
      "outputs": [
        {
          "type": "string",
          "title": "tool_output"
        }
      ],
      "branches": [
        "next"
      ],
      "tool": {
        "component_type": "ServerTool",
        "id": "5886e17c-c2c5-400d-9bf1-fdfe8490c35b",
        "name": "my_tool",
        "description": "Params: {\"param\": str}",
        "metadata": {
          "__metadata_info__": {}
        },
        "inputs": [
          {
            "type": "object",
            "additionalProperties": {
              "type": "string"
            },
            "title": "params"
          }
        ],
        "outputs": [
          {
            "type": "string",
            "title": "tool_output"
          }
        ]
      },
      "input_mapping": {},
      "output_mapping": {},
      "raise_exceptions": false,
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "25.4.0.dev0"
    },
    "2ae6af7c-4c67-49a8-b578-f1666466a4ca": {
      "component_type": "EndNode",
      "id": "2ae6af7c-4c67-49a8-b578-f1666466a4ca",
      "name": "answer_end_step",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "string",
          "title": "tool_output"
        },
        {
          "description": "the generated text",
          "type": "string",
          "title": "output"
        },
        {
          "type": "string",
          "title": "tool_name"
        },
        {
          "type": "object",
          "additionalProperties": {
            "type": "string"
          },
          "key_type": {
            "type": "string"
          },
          "title": "tool_args"
        },
        {
          "type": "string",
          "title": "action"
        },
        {
          "description": "the input value provided by the user",
          "type": "string",
          "title": "user_provided_input"
        }
      ],
      "outputs": [
        {
          "type": "string",
          "title": "tool_output"
        },
        {
          "description": "the generated text",
          "type": "string",
          "title": "output"
        },
        {
          "type": "string",
          "title": "tool_name"
        },
        {
          "type": "object",
          "additionalProperties": {
            "type": "string"
          },
          "key_type": {
            "type": "string"
          },
          "title": "tool_args"
        },
        {
          "type": "string",
          "title": "action"
        },
        {
          "description": "the input value provided by the user",
          "type": "string",
          "title": "user_provided_input"
        }
      ],
      "branches": [],
      "branch_name": "answer_end_step"
    },
    "d326fb5d-a9b0-4845-aaba-b8f01e523471": {
      "component_type": "EndNode",
      "id": "d326fb5d-a9b0-4845-aaba-b8f01e523471",
      "name": "invoke_tool_end_step",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "string",
          "title": "tool_output"
        },
        {
          "description": "the generated text",
          "type": "string",
          "title": "output"
        },
        {
          "type": "string",
          "title": "tool_name"
        },
        {
          "type": "object",
          "additionalProperties": {
            "type": "string"
          },
          "key_type": {
            "type": "string"
          },
          "title": "tool_args"
        },
        {
          "type": "string",
          "title": "action"
        },
        {
          "description": "the input value provided by the user",
          "type": "string",
          "title": "user_provided_input"
        }
      ],
      "outputs": [
        {
          "type": "string",
          "title": "tool_output"
        },
        {
          "description": "the generated text",
          "type": "string",
          "title": "output"
        },
        {
          "type": "string",
          "title": "tool_name"
        },
        {
          "type": "object",
          "additionalProperties": {
            "type": "string"
          },
          "key_type": {
            "type": "string"
          },
          "title": "tool_args"
        },
        {
          "type": "string",
          "title": "action"
        },
        {
          "description": "the input value provided by the user",
          "type": "string",
          "title": "user_provided_input"
        }
      ],
      "branches": [],
      "branch_name": "invoke_tool_end_step"
    },
    "df2e111a-b6ac-4c66-8d57-99e0b9c94fdd": {
      "component_type": "StartNode",
      "id": "df2e111a-b6ac-4c66-8d57-99e0b9c94fdd",
      "name": "start",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [],
      "outputs": [],
      "branches": [
        "next"
      ]
    }
  },
  "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: ExtendedFlow
id: 44ca9623-5567-4abc-8972-065df61d94e7
name: flow_edbb400a__auto
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs:
- type: string
  title: tool_output
- description: the generated text
  type: string
  title: output
- type: string
  title: tool_name
- type: object
  additionalProperties:
    type: string
  key_type:
    type: string
  title: tool_args
- type: string
  title: action
- description: the input value provided by the user
  type: string
  title: user_provided_input
start_node:
  $component_ref: df2e111a-b6ac-4c66-8d57-99e0b9c94fdd
nodes:
- $component_ref: df2e111a-b6ac-4c66-8d57-99e0b9c94fdd
- $component_ref: a3614787-eae2-4330-a5be-cf8bdad4544d
- $component_ref: 28f6f69b-aa81-49f7-be22-c51a3b0baaa5
- $component_ref: d093d2ee-d8cd-40f7-9163-154d3ae72a22
- $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
- $component_ref: 6e5fcaaf-1cf2-443d-9def-14c99333be68
- $component_ref: e2126f15-b523-44de-a087-971799a810c2
- $component_ref: 82460353-8eac-483d-967e-04fa7614d5c4
- $component_ref: 6c170ac9-3277-4581-841a-8edf4db175e0
- $component_ref: 2ae6af7c-4c67-49a8-b578-f1666466a4ca
- $component_ref: d326fb5d-a9b0-4845-aaba-b8f01e523471
control_flow_connections:
- component_type: ControlFlowEdge
  id: 42271781-8986-4ffc-be77-2700dd947ec5
  name: start_to_get_user_name_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: df2e111a-b6ac-4c66-8d57-99e0b9c94fdd
  from_branch: null
  to_node:
    $component_ref: a3614787-eae2-4330-a5be-cf8bdad4544d
- component_type: ControlFlowEdge
  id: 1c830ec0-c8a5-41da-8565-12cc0a933e19
  name: get_user_name_step_to_ask_user_request_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: a3614787-eae2-4330-a5be-cf8bdad4544d
  from_branch: null
  to_node:
    $component_ref: 28f6f69b-aa81-49f7-be22-c51a3b0baaa5
- component_type: ControlFlowEdge
  id: cb0100a1-307a-4352-bc69-550eb5c62d9a
  name: ask_user_request_step_to_generate_action_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 28f6f69b-aa81-49f7-be22-c51a3b0baaa5
  from_branch: null
  to_node:
    $component_ref: d093d2ee-d8cd-40f7-9163-154d3ae72a22
- component_type: ControlFlowEdge
  id: 07c38ae3-0246-492b-bf11-7922004432fa
  name: generate_action_step_to_extract_result_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: d093d2ee-d8cd-40f7-9163-154d3ae72a22
  from_branch: null
  to_node:
    $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
- component_type: ControlFlowEdge
  id: 04308f40-8171-4651-8dbf-fbf527f8f9ed
  name: extract_result_step_to_branching_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
  from_branch: null
  to_node:
    $component_ref: 6e5fcaaf-1cf2-443d-9def-14c99333be68
- component_type: ControlFlowEdge
  id: dab13845-d78b-4e5c-addf-cbd28f84da70
  name: branching_step_to_answer_end_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 6e5fcaaf-1cf2-443d-9def-14c99333be68
  from_branch: answer
  to_node:
    $component_ref: 2ae6af7c-4c67-49a8-b578-f1666466a4ca
- component_type: ControlFlowEdge
  id: 29c13062-7060-4878-8f32-b2a3735bf892
  name: branching_step_to_user_tool_validation_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 6e5fcaaf-1cf2-443d-9def-14c99333be68
  from_branch: execute_tool
  to_node:
    $component_ref: e2126f15-b523-44de-a087-971799a810c2
- component_type: ControlFlowEdge
  id: 46f0cae7-aef3-4387-8c34-c8442f6008f5
  name: branching_step_to_answer_end_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 6e5fcaaf-1cf2-443d-9def-14c99333be68
  from_branch: default
  to_node:
    $component_ref: 2ae6af7c-4c67-49a8-b578-f1666466a4ca
- component_type: ControlFlowEdge
  id: aec3a3d8-feba-40dd-839a-59690f17939c
  name: user_tool_validation_step_to_tool_selection_branching_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: e2126f15-b523-44de-a087-971799a810c2
  from_branch: null
  to_node:
    $component_ref: 82460353-8eac-483d-967e-04fa7614d5c4
- component_type: ControlFlowEdge
  id: 4506945a-6f39-4839-a910-c3eee14ad872
  name: tool_selection_branching_step_to_invoke_tool_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 82460353-8eac-483d-967e-04fa7614d5c4
  from_branch: execute_tool
  to_node:
    $component_ref: 6c170ac9-3277-4581-841a-8edf4db175e0
- component_type: ControlFlowEdge
  id: eac1e546-a9e9-436b-a83b-63a74ad93bc6
  name: tool_selection_branching_step_to_generate_action_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 82460353-8eac-483d-967e-04fa7614d5c4
  from_branch: retry_llm
  to_node:
    $component_ref: d093d2ee-d8cd-40f7-9163-154d3ae72a22
- component_type: ControlFlowEdge
  id: 8a20f70d-399f-41f1-8191-85502c5e947a
  name: tool_selection_branching_step_to_generate_action_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 82460353-8eac-483d-967e-04fa7614d5c4
  from_branch: default
  to_node:
    $component_ref: d093d2ee-d8cd-40f7-9163-154d3ae72a22
- component_type: ControlFlowEdge
  id: 2487e15a-0f1c-4529-8b60-d21c43e1b926
  name: invoke_tool_step_to_invoke_tool_end_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 6c170ac9-3277-4581-841a-8edf4db175e0
  from_branch: null
  to_node:
    $component_ref: d326fb5d-a9b0-4845-aaba-b8f01e523471
data_flow_connections:
- component_type: DataFlowEdge
  id: 3f74cc4f-237c-491d-8fd1-3ff44e08b6a8
  name: get_user_name_step_tool_output_to_ask_user_request_step_username_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: a3614787-eae2-4330-a5be-cf8bdad4544d
  source_output: tool_output
  destination_node:
    $component_ref: 28f6f69b-aa81-49f7-be22-c51a3b0baaa5
  destination_input: username
- component_type: DataFlowEdge
  id: 476856ed-4b35-49e0-bb12-c29a53faf97f
  name: ask_user_request_step_user_provided_input_to_generate_action_step_request_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 28f6f69b-aa81-49f7-be22-c51a3b0baaa5
  source_output: user_provided_input
  destination_node:
    $component_ref: d093d2ee-d8cd-40f7-9163-154d3ae72a22
  destination_input: request
- component_type: DataFlowEdge
  id: c40dadcb-35e9-4b41-bae1-2960e69852ce
  name: a91502a3-117f-40af-a000-3663a3db87e3_tool_info_to_generate_action_step_tools_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: a91502a3-117f-40af-a000-3663a3db87e3
  source_output: tool_info
  destination_node:
    $component_ref: d093d2ee-d8cd-40f7-9163-154d3ae72a22
  destination_input: tools
- component_type: DataFlowEdge
  id: eec02f81-55e0-42c7-b3f4-12c364c52ed2
  name: generate_action_step_output_to_extract_result_step_text_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: d093d2ee-d8cd-40f7-9163-154d3ae72a22
  source_output: output
  destination_node:
    $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
  destination_input: text
- component_type: DataFlowEdge
  id: f7e9acbe-c472-45d8-bf92-b35f436190be
  name: extract_result_step_action_to_branching_step_next_step_name_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
  source_output: action
  destination_node:
    $component_ref: 6e5fcaaf-1cf2-443d-9def-14c99333be68
  destination_input: next_step_name
- component_type: DataFlowEdge
  id: 3a2ff915-ca72-43f3-b6a2-f9a3dbceb621
  name: extract_result_step_tool_name_to_user_tool_validation_step_name_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
  source_output: tool_name
  destination_node:
    $component_ref: e2126f15-b523-44de-a087-971799a810c2
  destination_input: name
- component_type: DataFlowEdge
  id: 30845c9b-4b4c-4108-9b4e-4ebb9f881e32
  name: extract_result_step_tool_args_to_user_tool_validation_step_params_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
  source_output: tool_args
  destination_node:
    $component_ref: e2126f15-b523-44de-a087-971799a810c2
  destination_input: params
- component_type: DataFlowEdge
  id: 3baa59bf-c302-434c-ac8c-55e5051db3e3
  name: user_tool_validation_step_user_provided_input_to_tool_selection_branching_step_next_step_name_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: e2126f15-b523-44de-a087-971799a810c2
  source_output: user_provided_input
  destination_node:
    $component_ref: 82460353-8eac-483d-967e-04fa7614d5c4
  destination_input: next_step_name
- component_type: DataFlowEdge
  id: c0fd3d7a-9d7d-471e-962a-a99e5fb52c96
  name: extract_result_step_tool_args_to_invoke_tool_step_params_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
  source_output: tool_args
  destination_node:
    $component_ref: 6c170ac9-3277-4581-841a-8edf4db175e0
  destination_input: params
- component_type: DataFlowEdge
  id: 9596e6a9-2b6f-4cc7-b9d8-ce778112c92d
  name: get_user_name_step_tool_output_to_answer_end_step_tool_output_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: a3614787-eae2-4330-a5be-cf8bdad4544d
  source_output: tool_output
  destination_node:
    $component_ref: 2ae6af7c-4c67-49a8-b578-f1666466a4ca
  destination_input: tool_output
- component_type: DataFlowEdge
  id: 16eece12-6815-479e-b47f-7b09fc400604
  name: invoke_tool_step_tool_output_to_answer_end_step_tool_output_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 6c170ac9-3277-4581-841a-8edf4db175e0
  source_output: tool_output
  destination_node:
    $component_ref: 2ae6af7c-4c67-49a8-b578-f1666466a4ca
  destination_input: tool_output
- component_type: DataFlowEdge
  id: a16f467c-401a-4135-9d43-b777800e48fa
  name: generate_action_step_output_to_answer_end_step_output_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: d093d2ee-d8cd-40f7-9163-154d3ae72a22
  source_output: output
  destination_node:
    $component_ref: 2ae6af7c-4c67-49a8-b578-f1666466a4ca
  destination_input: output
- component_type: DataFlowEdge
  id: dd868b71-39c5-41c3-b6b0-520595600b9c
  name: extract_result_step_tool_name_to_answer_end_step_tool_name_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
  source_output: tool_name
  destination_node:
    $component_ref: 2ae6af7c-4c67-49a8-b578-f1666466a4ca
  destination_input: tool_name
- component_type: DataFlowEdge
  id: a489f8cc-3be4-435a-8a2c-1bffd290f5c2
  name: extract_result_step_tool_args_to_answer_end_step_tool_args_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
  source_output: tool_args
  destination_node:
    $component_ref: 2ae6af7c-4c67-49a8-b578-f1666466a4ca
  destination_input: tool_args
- component_type: DataFlowEdge
  id: 739bacd9-78b9-470a-9dae-f784870998c1
  name: extract_result_step_action_to_answer_end_step_action_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
  source_output: action
  destination_node:
    $component_ref: 2ae6af7c-4c67-49a8-b578-f1666466a4ca
  destination_input: action
- component_type: DataFlowEdge
  id: 9e275423-8504-4d56-8c02-229101af294c
  name: ask_user_request_step_user_provided_input_to_answer_end_step_user_provided_input_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 28f6f69b-aa81-49f7-be22-c51a3b0baaa5
  source_output: user_provided_input
  destination_node:
    $component_ref: 2ae6af7c-4c67-49a8-b578-f1666466a4ca
  destination_input: user_provided_input
- component_type: DataFlowEdge
  id: da295e5e-8abb-4d16-b39b-3853e0df310d
  name: user_tool_validation_step_user_provided_input_to_answer_end_step_user_provided_input_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: e2126f15-b523-44de-a087-971799a810c2
  source_output: user_provided_input
  destination_node:
    $component_ref: 2ae6af7c-4c67-49a8-b578-f1666466a4ca
  destination_input: user_provided_input
- component_type: DataFlowEdge
  id: 4bc35cfb-8f77-4537-8ce6-a12f6f19a554
  name: get_user_name_step_tool_output_to_invoke_tool_end_step_tool_output_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: a3614787-eae2-4330-a5be-cf8bdad4544d
  source_output: tool_output
  destination_node:
    $component_ref: d326fb5d-a9b0-4845-aaba-b8f01e523471
  destination_input: tool_output
- component_type: DataFlowEdge
  id: 4a1242bb-cb58-4578-be57-4a11764f19a5
  name: invoke_tool_step_tool_output_to_invoke_tool_end_step_tool_output_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 6c170ac9-3277-4581-841a-8edf4db175e0
  source_output: tool_output
  destination_node:
    $component_ref: d326fb5d-a9b0-4845-aaba-b8f01e523471
  destination_input: tool_output
- component_type: DataFlowEdge
  id: 307aef79-4a11-4bd7-8cfd-90d8ab4c5d52
  name: generate_action_step_output_to_invoke_tool_end_step_output_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: d093d2ee-d8cd-40f7-9163-154d3ae72a22
  source_output: output
  destination_node:
    $component_ref: d326fb5d-a9b0-4845-aaba-b8f01e523471
  destination_input: output
- component_type: DataFlowEdge
  id: c31a0fba-93c9-46a8-a21e-efdcff8d1130
  name: extract_result_step_tool_name_to_invoke_tool_end_step_tool_name_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
  source_output: tool_name
  destination_node:
    $component_ref: d326fb5d-a9b0-4845-aaba-b8f01e523471
  destination_input: tool_name
- component_type: DataFlowEdge
  id: d5ea1f13-b60a-4010-bfd9-318a81cba2f3
  name: extract_result_step_tool_args_to_invoke_tool_end_step_tool_args_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
  source_output: tool_args
  destination_node:
    $component_ref: d326fb5d-a9b0-4845-aaba-b8f01e523471
  destination_input: tool_args
- component_type: DataFlowEdge
  id: 8b3a2623-4d26-41ba-881a-8b5a566b8d7e
  name: extract_result_step_action_to_invoke_tool_end_step_action_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
  source_output: action
  destination_node:
    $component_ref: d326fb5d-a9b0-4845-aaba-b8f01e523471
  destination_input: action
- component_type: DataFlowEdge
  id: 5361e910-0b85-490a-b9bd-0613eed38037
  name: ask_user_request_step_user_provided_input_to_invoke_tool_end_step_user_provided_input_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 28f6f69b-aa81-49f7-be22-c51a3b0baaa5
  source_output: user_provided_input
  destination_node:
    $component_ref: d326fb5d-a9b0-4845-aaba-b8f01e523471
  destination_input: user_provided_input
- component_type: DataFlowEdge
  id: 346f5ff8-f0a6-4b0d-9727-69a79a2f5489
  name: user_tool_validation_step_user_provided_input_to_invoke_tool_end_step_user_provided_input_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: e2126f15-b523-44de-a087-971799a810c2
  source_output: user_provided_input
  destination_node:
    $component_ref: d326fb5d-a9b0-4845-aaba-b8f01e523471
  destination_input: user_provided_input
context_providers:
- $component_ref: a91502a3-117f-40af-a000-3663a3db87e3
component_plugin_name: FlowPlugin
component_plugin_version: 25.4.0.dev0
$referenced_components:
  28f6f69b-aa81-49f7-be22-c51a3b0baaa5:
    component_type: PluginInputMessageNode
    id: 28f6f69b-aa81-49f7-be22-c51a3b0baaa5
    name: ask_user_request_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: '"username" input variable for the template'
      type: string
      title: username
    outputs:
    - description: the input value provided by the user
      type: string
      title: user_provided_input
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    message_template: Hi {{username}}. What can I do for you today?
    rephrase: false
    llm_config: null
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.4.0.dev0
  a3614787-eae2-4330-a5be-cf8bdad4544d:
    component_type: ExtendedToolNode
    id: a3614787-eae2-4330-a5be-cf8bdad4544d
    name: get_user_name_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs:
    - type: string
      title: tool_output
    branches:
    - next
    tool:
      component_type: ServerTool
      id: cfd9cae9-38b9-4b48-9a52-d324899a4859
      name: get_user_name_tool
      description: Tool to get user name.
      metadata:
        __metadata_info__: {}
      inputs: []
      outputs:
      - type: string
        title: tool_output
    input_mapping: {}
    output_mapping: {}
    raise_exceptions: false
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.4.0.dev0
  d093d2ee-d8cd-40f7-9163-154d3ae72a22:
    component_type: LlmNode
    id: d093d2ee-d8cd-40f7-9163-154d3ae72a22
    name: generate_action_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: '"tools" input variable for the template'
      type: string
      title: tools
    - description: '"request" input variable for the template'
      type: string
      title: request
    outputs:
    - description: the generated text
      type: string
      title: output
    branches:
    - next
    llm_config:
      component_type: VllmConfig
      id: 5fdf143c-a7ee-459c-8ff8-409df206e73b
      name: LLAMA_MODEL_ID
      description: null
      metadata:
        __metadata_info__: {}
      default_generation_parameters: null
      url: LLAMA_API_URL
      model_id: LLAMA_MODEL_ID
    prompt_template: "Your are an helpful assistant. Help answer the user request.\n\
      \nHere is the list of tools:\n{{tools}}\n\nHere is the user request:\n{{request}}\n\
      \n## Response format\nYour response should be JSON-compliant dictionary with\
      \ the following structure.\n\n{\n    \"action\": \"answer|execute_tool\",\n\
      \    \"tool_name\": \"None|tool_name\",\n    \"tool_args\": {\"param1\": \"\
      value1\"}\n}\n\nWhen the action is \"answer\", \"tool_name\" should be \"None\"\
      \ and \"tool_args\" should be {}\nWhen the action is \"execute_tool\", \"tool_name\"\
      \ should be the name of the tool to execute\nand \"tool_args\" should be the\
      \ JSON-compliant dictionary of arguments to pass to the tool.\n\nCRITICAL: Only\
      \ output the JSON-compliant dictionary otherwise the parsing will fail.\nfail."
  a91502a3-117f-40af-a000-3663a3db87e3:
    component_type: PluginConstantContextProvider
    id: a91502a3-117f-40af-a000-3663a3db87e3
    name: a91502a3-117f-40af-a000-3663a3db87e3
    description: null
    metadata: {}
    inputs: []
    outputs:
    - type: string
      title: tool_info
    branches:
    - next
    value: '[{"name": "my_tool", "description": "Params: {\"param\": str}", "parameters":
      {"params": {"type": "object", "additionalProperties": {"type": "string"}, "title":
      "Params"}}}]'
    component_plugin_name: ContextProviderPlugin
    component_plugin_version: 25.4.0.dev0
  b31c569b-2a66-4f2b-a98d-f52bfca2dfeb:
    component_type: PluginExtractNode
    id: b31c569b-2a66-4f2b-a98d-f52bfca2dfeb
    name: extract_result_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: raw text to extract information from
      type: string
      title: text
    outputs:
    - type: string
      title: action
    - type: string
      title: tool_name
    - type: object
      additionalProperties:
        type: string
      key_type:
        type: string
      title: tool_args
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    output_values:
      action: .action
      tool_name: .tool_name
      tool_args: .tool_args
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.4.0.dev0
  6e5fcaaf-1cf2-443d-9def-14c99333be68:
    component_type: BranchingNode
    id: 6e5fcaaf-1cf2-443d-9def-14c99333be68
    name: branching_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: Next branch name in the flow
      type: string
      title: next_step_name
      default: default
    outputs: []
    branches:
    - answer
    - default
    - execute_tool
    mapping:
      answer: answer
      execute_tool: execute_tool
  e2126f15-b523-44de-a087-971799a810c2:
    component_type: PluginInputMessageNode
    id: e2126f15-b523-44de-a087-971799a810c2
    name: user_tool_validation_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: '"name" input variable for the template'
      type: string
      title: name
    - description: '"params" input variable for the template'
      type: string
      title: params
    outputs:
    - description: the input value provided by the user
      type: string
      title: user_provided_input
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    message_template: Requesting to invoke tool {{name}} with parameters {{params}}.
      Do you accept the request? (y/n)
    rephrase: false
    llm_config: null
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.4.0.dev0
  82460353-8eac-483d-967e-04fa7614d5c4:
    component_type: BranchingNode
    id: 82460353-8eac-483d-967e-04fa7614d5c4
    name: tool_selection_branching_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: Next branch name in the flow
      type: string
      title: next_step_name
      default: default
    outputs: []
    branches:
    - default
    - execute_tool
    - retry_llm
    mapping:
      y: execute_tool
      n: retry_llm
  6c170ac9-3277-4581-841a-8edf4db175e0:
    component_type: ExtendedToolNode
    id: 6c170ac9-3277-4581-841a-8edf4db175e0
    name: invoke_tool_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: object
      additionalProperties:
        type: string
      title: params
    outputs:
    - type: string
      title: tool_output
    branches:
    - next
    tool:
      component_type: ServerTool
      id: 5886e17c-c2c5-400d-9bf1-fdfe8490c35b
      name: my_tool
      description: 'Params: {"param": str}'
      metadata:
        __metadata_info__: {}
      inputs:
      - type: object
        additionalProperties:
          type: string
        title: params
      outputs:
      - type: string
        title: tool_output
    input_mapping: {}
    output_mapping: {}
    raise_exceptions: false
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.4.0.dev0
  2ae6af7c-4c67-49a8-b578-f1666466a4ca:
    component_type: EndNode
    id: 2ae6af7c-4c67-49a8-b578-f1666466a4ca
    name: answer_end_step
    description: null
    metadata:
      __metadata_info__: {}
    inputs:
    - type: string
      title: tool_output
    - description: the generated text
      type: string
      title: output
    - type: string
      title: tool_name
    - type: object
      additionalProperties:
        type: string
      key_type:
        type: string
      title: tool_args
    - type: string
      title: action
    - description: the input value provided by the user
      type: string
      title: user_provided_input
    outputs:
    - type: string
      title: tool_output
    - description: the generated text
      type: string
      title: output
    - type: string
      title: tool_name
    - type: object
      additionalProperties:
        type: string
      key_type:
        type: string
      title: tool_args
    - type: string
      title: action
    - description: the input value provided by the user
      type: string
      title: user_provided_input
    branches: []
    branch_name: answer_end_step
  d326fb5d-a9b0-4845-aaba-b8f01e523471:
    component_type: EndNode
    id: d326fb5d-a9b0-4845-aaba-b8f01e523471
    name: invoke_tool_end_step
    description: null
    metadata:
      __metadata_info__: {}
    inputs:
    - type: string
      title: tool_output
    - description: the generated text
      type: string
      title: output
    - type: string
      title: tool_name
    - type: object
      additionalProperties:
        type: string
      key_type:
        type: string
      title: tool_args
    - type: string
      title: action
    - description: the input value provided by the user
      type: string
      title: user_provided_input
    outputs:
    - type: string
      title: tool_output
    - description: the generated text
      type: string
      title: output
    - type: string
      title: tool_name
    - type: object
      additionalProperties:
        type: string
      key_type:
        type: string
      title: tool_args
    - type: string
      title: action
    - description: the input value provided by the user
      type: string
      title: user_provided_input
    branches: []
    branch_name: invoke_tool_end_step
  df2e111a-b6ac-4c66-8d57-99e0b9c94fdd:
    component_type: StartNode
    id: df2e111a-b6ac-4c66-8d57-99e0b9c94fdd
    name: start
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs: []
    branches:
    - next
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

print(config)
new_flow = AgentSpecLoader(
    tool_registry={
        'get_user_name_tool': get_user_name_tool,
        'my_tool': my_tool
    }
).load_json(config)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `PluginInputMessageNode`
- `PluginConstantContextProvider`
- `PluginExtractNode`
- `ExtendedToolNode`
- `ExtendedFlow`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Next steps

In this guide, you learned how to request and handle user input and approval inside WayFlow flows using `InputMessageStep`, as well as how to combine input with branching for selective actions. You may now proceed to:

- [How to Create Conditional Transitions in Flows](conditional_flows.md)
- [How to Add User Confirmation to Tool Call Requests](howto_userconfirmation.md)
- [How to Create a ServerTool from a Flow](create_a_tool_from_a_flow.md)

## Full code

Click on the card at the [top of this page](#top-userinputinflows) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Ask for User Input in Flows
# -------------------------------------------------

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
# python howto_userinputinflows.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Create LLM

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## Create Simple Flow

# %%
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import (
    BranchingStep,
    CompleteStep,
    ExtractValueFromJsonStep,
    InputMessageStep,
    PromptExecutionStep,
    StartStep,
    ToolExecutionStep,
)
from wayflowcore.tools import tool

@tool(description_mode="only_docstring")
def get_user_name_tool() -> str:
    """Tool to get user name."""
    return "Alice"

start_step = StartStep(name="start")

get_user_name_step = ToolExecutionStep(
    name="get_user_name_step",
    tool=get_user_name_tool,
)

ask_user_request_step = InputMessageStep(
    name="ask_user_request_step", message_template="Hi {{username}}. What can I do for you today?"
)

answer_request_step = PromptExecutionStep(
    name="answer_request_step",
    llm=llm,
    prompt_template="Your are an helpful assistant. Help answer the user request: {{request}}",
    output_mapping={
        PromptExecutionStep.OUTPUT: "my_output"
    },  # what we want to expose as the output name
)

end_step = CompleteStep(name="end")

flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(start_step, get_user_name_step),
        ControlFlowEdge(get_user_name_step, ask_user_request_step),
        ControlFlowEdge(ask_user_request_step, answer_request_step),
        ControlFlowEdge(answer_request_step, end_step),
    ],
    data_flow_edges=[
        DataFlowEdge(
            get_user_name_step, ToolExecutionStep.TOOL_OUTPUT, ask_user_request_step, "username"
        ),
        DataFlowEdge(
            ask_user_request_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            answer_request_step,
            "request",
        ),
    ],
)

# %%[markdown]
## Execute Simple Flow

# %%
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
conversation = flow.start_conversation()
status = (
    conversation.execute()
)  # will get the user input, then pause the execution to ask for the user input

if not isinstance(status, UserMessageRequestStatus):
    raise ValueError(
        f"Execution status should be {UserMessageRequestStatus.__name__}, was {type(status)}"
    )
print(conversation.get_last_message().content)
# Hi Alice. What can I do for you today?

conversation.append_user_message("What is heavier? 20 pounds of bricks of 20 feathers?")
status = conversation.execute()  # we resume the execution

if not isinstance(status, FinishedStatus):
    raise ValueError(f"Execution status should be {FinishedStatus.__name__}, was {type(status)}")
print(
    status.output_values["my_output"]
)  # using the key name that we defined in the `output_mapping`
# [...] a surprisingly simple answer emerges: 20 pounds of bricks is heavier than 20 feathers by a massive margin, approximately 69.78 pounds.

# %%[markdown]
## Create Complex Flow

# %%
import json
from typing import Dict

from wayflowcore.contextproviders.constantcontextprovider import ConstantContextProvider
from wayflowcore.property import DictProperty, StringProperty

@tool(description_mode="only_docstring")
def my_tool(params: Dict[str, str]) -> str:
    """Params: {"param": str}"""
    return f"Invoked tool with {params=}"

prompt_template = """
Your are an helpful assistant. Help answer the user request.

Here is the list of tools:
{{tools}}

Here is the user request:
{{request}}

## Response format
Your response should be JSON-compliant dictionary with the following structure.

{
    "action": "answer|execute_tool",
    "tool_name": "None|tool_name",
    "tool_args": {"param1": "value1"}
}

When the action is "answer", "tool_name" should be "None" and "tool_args" should be {}
When the action is "execute_tool", "tool_name" should be the name of the tool to execute
and "tool_args" should be the JSON-compliant dictionary of arguments to pass to the tool.

CRITICAL: Only output the JSON-compliant dictionary otherwise the parsing will fail.
fail.
""".strip()

available_tools = [my_tool]
tool_context_provider = ConstantContextProvider(
    json.dumps([tool_.to_dict() for tool_ in available_tools]),
    output_description=StringProperty("tool_info"),
)

generate_action_step = PromptExecutionStep(
    name="generate_action_step", llm=llm, prompt_template=prompt_template
)

extract_result_step = ExtractValueFromJsonStep(
    name="extract_result_step",
    output_values={
        "action": ".action",
        "tool_name": ".tool_name",
        "tool_args": ".tool_args",
    },
    output_descriptors=[
        StringProperty(name='action'),
        StringProperty(name='tool_name'),
        DictProperty(name='tool_args'),
    ]
)

branching_step = BranchingStep(
    name="branching_step", branch_name_mapping={"answer": "answer", "execute_tool": "execute_tool"}
)

answer_end_step = CompleteStep(name="answer_end_step")

user_tool_validation_step = InputMessageStep(
    name="user_tool_validation_step",
    message_template="Requesting to invoke tool {{name}} with parameters {{params}}. Do you accept the request? (y/n)",
)

tool_selection_branching_step = BranchingStep(
    name="tool_selection_branching_step",
    branch_name_mapping={"y": "execute_tool", "n": "retry_llm"},
)

invoke_tool_step = ToolExecutionStep(
    name="invoke_tool_step",
    tool=my_tool,
)

invoke_tool_end_step = CompleteStep(name="invoke_tool_end_step")

flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(start_step, get_user_name_step),
        ControlFlowEdge(get_user_name_step, ask_user_request_step),
        ControlFlowEdge(ask_user_request_step, generate_action_step),
        ControlFlowEdge(generate_action_step, extract_result_step),
        ControlFlowEdge(extract_result_step, branching_step),
        ControlFlowEdge(branching_step, answer_end_step, source_branch="answer"),
        ControlFlowEdge(branching_step, user_tool_validation_step, source_branch="execute_tool"),
        ControlFlowEdge(
            branching_step, answer_end_step, source_branch=BranchingStep.BRANCH_DEFAULT
        ),
        ControlFlowEdge(user_tool_validation_step, tool_selection_branching_step),
        ControlFlowEdge(
            tool_selection_branching_step, invoke_tool_step, source_branch="execute_tool"
        ),
        ControlFlowEdge(
            tool_selection_branching_step, generate_action_step, source_branch="retry_llm"
        ),
        ControlFlowEdge(
            tool_selection_branching_step,
            generate_action_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(invoke_tool_step, invoke_tool_end_step),
    ],
    data_flow_edges=[
        DataFlowEdge(
            get_user_name_step, ToolExecutionStep.TOOL_OUTPUT, ask_user_request_step, "username"
        ),
        DataFlowEdge(
            ask_user_request_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            generate_action_step,
            "request",
        ),
        DataFlowEdge(tool_context_provider, "tool_info", generate_action_step, "tools"),
        DataFlowEdge(
            generate_action_step,
            PromptExecutionStep.OUTPUT,
            extract_result_step,
            ExtractValueFromJsonStep.TEXT,
        ),
        DataFlowEdge(extract_result_step, "action", branching_step, BranchingStep.NEXT_BRANCH_NAME),
        DataFlowEdge(extract_result_step, "tool_name", user_tool_validation_step, "name"),
        DataFlowEdge(extract_result_step, "tool_args", user_tool_validation_step, "params"),
        DataFlowEdge(
            user_tool_validation_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            tool_selection_branching_step,
            BranchingStep.NEXT_BRANCH_NAME,
        ),
        DataFlowEdge(extract_result_step, "tool_args", invoke_tool_step, "params"),
    ],
)

# %%[markdown]
## Execute Complex Flow

# %%
conversation = flow.start_conversation()
status = (
    conversation.execute()
)  # will get the user input, then pause the execution to ask for the user input

if not isinstance(status, UserMessageRequestStatus):
    raise ValueError(
        f"Execution status should be {UserMessageRequestStatus.__name__}, was {type(status)}"
    )
print(conversation.get_last_message().content)
# Hi Alice. What can I do for you today?

conversation.append_user_message("Invoke the tool with parameter 'value#007'")
status = conversation.execute()  # we resume the execution

if not isinstance(status, UserMessageRequestStatus):
    raise ValueError(
        f"Execution status should be {UserMessageRequestStatus.__name__}, was {type(status)}"
    )
print(conversation.get_last_message().content)
# Requesting to invoke tool my_tool with parameters {"param": "value#007"}. Do you accept the request? (y/n)

conversation.append_user_message("y")  # we accept the tool call request
status = conversation.execute()  # we resume the execution

if not isinstance(status, FinishedStatus):
    raise ValueError(f"Execution status should be {FinishedStatus.__name__}, was {type(status)}")

print(status.output_values[ToolExecutionStep.TOOL_OUTPUT])
# Invoked tool with params={'param': 'value#007'}


# %%[markdown]
## Export Config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(flow)

# %%[markdown]
## Load Agent Spec Config

# %%
from wayflowcore.agentspec import AgentSpecLoader

print(config)
new_flow = AgentSpecLoader(
    tool_registry={
        'get_user_name_tool': get_user_name_tool,
        'my_tool': my_tool
    }
).load_json(config)
```
