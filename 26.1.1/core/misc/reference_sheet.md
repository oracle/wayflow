<a id="core-ref-sheet"></a>

# WayFlow Reference Sheet

This reference sheet provides a single-page overview of basic code snippets covering the core concepts used in WayFlow.

Each section includes links to additional tutorials and guides for deeper learning.

## LLMs

WayFlow Agents and Flows may require the use of Large Language Models (LLMs).
This section shows how to initialize an LLM and perform quick tests.

### Loading an LLM instance

WayFlow supports several LLM API providers.
For an overview of supported LLMs, see the guide
[How to Use LLMs from Different Providers](../howtoguides/llm_from_different_providers.md).

Start by selecting an LLM from one of the available providers:




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

Read more about the LLMs support in the [API reference](../api/llmmodels.md#id1).

### Testing inference with LLMs

#### Single prompt generation

Use a simple [PromptExecutionStep](../api/flows.md#promptexecutionstep) to test an LLM.

```python
from wayflowcore.flowhelpers import create_single_step_flow, run_flow_and_return_outputs
from wayflowcore.steps import PromptExecutionStep

flow = create_single_step_flow(PromptExecutionStep(prompt_template="{{prompt}}", llm=llm))
prompt = "Write a simple Python function to sum two numbers"
response = run_flow_and_return_outputs(flow, {"prompt": prompt})[PromptExecutionStep.OUTPUT]

print(response)  # Here's a simple Python function...
```

**API Reference:** [PromptExecutionStep](../api/flows.md#promptexecutionstep) | [Flow](../api/flows.md#flow)

#### TIP
Use the helper methods `create_single_step_flow` and `run_flow_and_return_outputs` for quick prototyping.

#### Parallel generation

Add a [MapStep](../api/flows.md#mapstep) to perform inference on a batch of inputs (parallel generation).

```python
from wayflowcore.flowhelpers import create_single_step_flow, run_flow_and_return_outputs
from wayflowcore.property import ListProperty
from wayflowcore.steps import MapStep, PromptExecutionStep

flow = create_single_step_flow(
    MapStep(
        create_single_step_flow(PromptExecutionStep(prompt_template="{{prompt}}", llm=llm)),
        parallel_execution=True,
        unpack_input={"prompt": "."},
        output_descriptors=[ListProperty(PromptExecutionStep.OUTPUT)],
    )
)

NUM_RESPONSES = 3
prompt = "Write a simple Python function to sum two numbers"
prompt_batch = [prompt] * NUM_RESPONSES
response = run_flow_and_return_outputs(flow, {MapStep.ITERATED_INPUT: prompt_batch})[
    PromptExecutionStep.OUTPUT
]

print(*response, sep=f"\n\n{'-'*30}\n\n")
```

**API Reference:** [ListProperty](../api/flows.md#listproperty) | [PromptExecutionStep](../api/flows.md#promptexecutionstep) | [MapStep](../api/flows.md#mapstep) | [Flow](../api/flows.md#flow)

#### NOTE
Note the use of a [ListProperty](../api/flows.md#listproperty) to specify the output of the [MapStep](../api/flows.md#mapstep).

#### Structured generation

WayFlow supports [structured generation](glossary.md#defstructuredgeneration) (such as controlling LLM outputs to conform to specific formats, schemas, or patterns, for example, Json Schema).

Structured generation can be achieved by specifying the output descriptors of the [PromptExecutionStep](../api/flows.md#promptexecutionstep).

```python
from wayflowcore.flowhelpers import create_single_step_flow, run_flow_and_return_outputs
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import PromptExecutionStep

product_name = StringProperty(
    name="product_name",
    description="name of the product",
    default_value="",
)
product_description = StringProperty(
    name="product_description",
    description="One sentence description of the product.",
    default_value="",
)
functionalities = ListProperty(
    name="functionalities",
    description="List of functionalities of the product",
    item_type=StringProperty("functionality"),
    default_value=[],
)

flow = create_single_step_flow(
    PromptExecutionStep(
        prompt_template="{{prompt}}",
        llm=llm,
        output_descriptors=[product_name, product_description, functionalities],
    )
)
prompt = "Create a simple product for students."
response = run_flow_and_return_outputs(flow, {"prompt": prompt})

print(
    f"Name: {response['product_name']}\n"
    f"Description: {response['product_description']}\n"
    f"Functionalities:\n{response['functionalities']}"
)
```

**API Reference:** [StringProperty](../api/flows.md#stringproperty) | [PromptExecutionStep](../api/flows.md#promptexecutionstep) | [Flow](../api/flows.md#flow)

Read the guide on [How to Perform Structured Generation](../howtoguides/howto_promptexecutionstep.md) for more information.

## Tools

Tools are essential for building powerful Agents and Flows.
WayFlow supports the use of [ServerTool](../api/tools.md#servertool) (which can be simply built with the [tool](../api/tools.md#tooldecorator) decorator), the [RemoteTool](../api/tools.md#remotetool) as well as
the [ClientTool](../api/tools.md#clienttool).

![image](core/_static/howto/types_of_tools.svg)

**Figure:** The different tools in WayFlow.

### Creating a simple tool

The simplest way to create a tool in WayFlow is by using the [tool](../api/tools.md#tooldecorator) decorator, which creates a [ServerTool](../api/tools.md#servertool) (see definition [in the glossary](glossary.md#defservertool)).

```python
from datetime import datetime
from typing import Annotated

from wayflowcore.tools import tool


@tool
def days_between_dates(
    date1: Annotated[str, "First date in 'dd/mm/yyyy' format."],
    date2: Annotated[str, "Second date in 'dd/mm/yyyy' format."],
) -> Annotated[int, "Absolute difference in days between the two dates."]:
    """
    Calculate the absolute difference in days between two dates.
    """
    return abs((datetime.strptime(date2, "%d/%m/%Y") - datetime.strptime(date1, "%d/%m/%Y")).days)


# days_between_dates is not a callable anymore, it is a `ServerTool`
print(days_between_dates.func("01/01/2020", "31/12/2020"))  # 365
```

**API Reference:** [tool](../api/tools.md#tooldecorator)

For more information, read the guide on [How to Build Assistants with Tools](../howtoguides/howto_build_assistants_with_tools.md) or read
the [API reference](../api/tools.md) to learn about the available types of tools in WayFlow.

### Creating a stateful tool

To build stateful tools, simply use the [tool](../api/tools.md#tooldecorator) helper as a wrapper to the method of an instantiated class.

```python
from wayflowcore.tools import tool


class Counter:
    def __init__(self):
        self.value = 0

    def increment(self) -> str:
        """Increment the counter"""
        self.value += 1
        return f"The updated count is {self.value}"


counter = Counter()
counter_tool = tool("increment_counter", counter.increment)
print(counter_tool.func())  # The updated count is 1
```

**API Reference:** [tool](../api/tools.md#tooldecorator)

### Creating and using a Client tool

Use the [ClientTool](../api/tools.md#clienttool) to create tools that are meant to be executed on the client side (see [definition in the glossary](glossary.md#defclienttool)).

```python
from datetime import datetime
from typing import Any

from wayflowcore.executors.executionstatus import ToolRequestStatus
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import ClientTool, ToolRequest, ToolResult


def _days_between_dates(date1: str, date2: str) -> int:
    return abs((datetime.strptime(date2, "%d/%m/%Y") - datetime.strptime(date1, "%d/%m/%Y")).days)


def execute_client_tool_from_tool_request(tool_request: ToolRequest) -> Any:
    if tool_request.name == "days_between_dates":
        return _days_between_dates(**tool_request.args)
    else:
        raise ValueError(f"Tool name {tool_request.name} is not recognized")


days_client_tools = ClientTool(
    name="days_between_dates",
    description="Calculate the absolute difference in days between two dates.",
    parameters={
        "date1": {
            "description": "First date in 'dd/mm/yyyy' format.",
            "type": "string",
        },
        "date2": {
            "description": "Second date in 'dd/mm/yyyy' format.",
            "type": "string",
        },
    },
    output={"type": "string", "description": "Absolute difference in days between the two dates."},
)

flow = create_single_step_flow(ToolExecutionStep(days_client_tools))
conversation = flow.start_conversation({"date1": "01/01/2020", "date2": "31/12/2020"})
status = conversation.execute()
assert isinstance(status, ToolRequestStatus)
tool_request = status.tool_requests[0]
tool_execution_content = execute_client_tool_from_tool_request(tool_request)

status.submit_tool_result(ToolResult(tool_execution_content, tool_request.tool_request_id))
# conversation.execute() # continue the execution of the Flow
```

**API Reference:** [ClientTool](../api/tools.md#clienttool) | [ToolRequest](../api/tools.md#toolrequest) | [ToolResult](../api/tools.md#toolresult) | [ToolExecutionStep](../api/flows.md#toolexecutionstep) | [ToolRequestStatus](../api/conversation.md#toolrequestexecutionstatus) | [Flow](../api/flows.md#flow)

Learn more about tools by reading [How to Build Assistants with Tools](../howtoguides/howto_build_assistants_with_tools.md), and the [Tools API reference](../api/tools.md).

<a id="refsheet-executionloop"></a>

## Execution loop and statuses

This section illustrates a basic execution loop for WayFlow assistants (Agents and Flows).

1. A new conversation is created.
2. The assistant is executed on the conversation.
3. Based on the status returned from the assistant execution:
   \* The loop exits if the status is `FinishedStatus`.
   \* The user is prompted for input if the status is `UserMessageRequestStatus`.
   \* A `ClientTool` is executed if the status is `ToolRequestStatus`.

The loop continues until the assistant returns a `FinishedStatus`.

```python
from typing import Any
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.executors.executionstatus import (
   FinishedStatus, UserMessageRequestStatus, ToolRequestStatus
)
from wayflowcore.tools import ToolRequest, ToolResult

def execute_client_tool_from_tool_request(tool_request: ToolRequest) -> Any:
   if tool_request.name == "my_tool_name":
      return _my_tool_callable(**tool_request.args)
   else:
      raise ValueError(f"Tool name {tool_request.name} is not recognized")

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
   elif isinstance(status, ToolRequestStatus):
      tool_request = status.tool_requests[0]
      tool_result = execute_client_tool_from_tool_request(tool_request)
      print(f"{tool_result!r}")
      conversation.append_message(
            Message(
               tool_result=ToolResult(content=tool_result, tool_request_id=tool_request.tool_request_id),
               message_type=MessageType.TOOL_RESULT,
            )
      )
   else:
      raise ValueError(f"Unsupported execution status: '{status}'")
```

Learn more about execution loops by reading the [Execution Status API reference](../api/conversation.md#id1).

## Agents

WayFlow [Agents](../api/agent.md#agent) are LLM-powered assistants that can interact with users, leverage external tools, and interact with other WayFlow assistants to take specific actions
in order to solve user requests through conversational interfaces.

### Creating a simple Agent

Creating an [Agent](../api/agent.md#agent) only requires an LLM and optional instructions to guide the agent behavior.

```python
from wayflowcore.agent import Agent

agent = Agent(
    llm, custom_instruction="You are a helpful assistant, please answer the user requests."
)

conversation = agent.start_conversation(messages="Please write a simple Python function to compute the sum of 2 numbers.")
conversation.execute()
print(conversation.get_last_message().content)
# Here's a simple Python function that...
```

**API Reference:** [Agent](../api/agent.md#agent)

Learn more about Agents by reading the tutorial [Build a Simple Conversational Assistant with Agents](../tutorials/basic_agent.md)
and the [Agent API reference](../api/agent.md#agent).

### Creating a Agent with tools

You can simply equip [Agents](../api/agent.md#agent) with tools using the `tools` attribute of the agent.

```python
from datetime import datetime
from typing import Annotated

from wayflowcore.agent import Agent
from wayflowcore.tools import tool


@tool
def days_between_dates(
    date1: Annotated[str, "First date in 'dd/mm/yyyy' format."],
    date2: Annotated[str, "Second date in 'dd/mm/yyyy' format."],
) -> Annotated[int, "Absolute difference in days between the two dates."]:
    """
    Calculate the absolute difference in days between two dates.
    """
    return abs((datetime.strptime(date2, "%d/%m/%Y") - datetime.strptime(date1, "%d/%m/%Y")).days)


agent = Agent(llm, tools=[days_between_dates])
conversation = agent.start_conversation(messages="How many days are there between 01/01/2020 and 31/12/2020?")
status = conversation.execute()
assert isinstance(status, UserMessageRequestStatus)
print(status.message.content)
# There are 365 days between 01/01/2020 and 31/12/2020.
```

**API Reference:** [Agent](../api/agent.md#agent) | [tool](../api/tools.md#tooldecorator)

## Flows

WayFlow [Flows](../api/flows.md#flow) are LLM-powered structured assistants composed of individual steps that are connected to form a coherent sequence of actions.
Each step in a `Flow` is designed to perform a specific function, similar to functions in programming.

### Creating a simple Flow
```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep

opening_step = OutputMessageStep("Opening session")
closing_step = OutputMessageStep('Closing session"')
flow = Flow(
    begin_step=opening_step,
    steps={
        "open_step": opening_step,
        "close_step": closing_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=opening_step, destination_step=closing_step),
        ControlFlowEdge(source_step=closing_step, destination_step=None),
    ],
)
conversation = flow.start_conversation()
status = conversation.execute()
assert isinstance(status, UserMessageRequestStatus)
print(status.message.content)
```

**API Reference:** [ControlFlowEdge](../api/flows.md#controlflowedge) | [Flow](../api/flows.md#flow) | [OutputMessageStep](../api/flows.md#outputmessagestep)

Learn more about Flows by reading the tutorial [Build a Simple Fixed-Flow Assistant with Flows](../tutorials/basic_flow.md) and the [Flow API reference](../api/flows.md#flow).

### Creating Flow with explicit data connection
```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep

MOCK_PROCESSING_STEP = "processing_step"
OUTPUT_STEP = "output_step"
mock_processing_step = OutputMessageStep("Successfully processed username {{username}}")
output_step = OutputMessageStep('{{session_id}}: Received message "{{processing_message}}"')
flow = Flow(
    begin_step=mock_processing_step,
    steps={
        MOCK_PROCESSING_STEP: mock_processing_step,
        OUTPUT_STEP: output_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=mock_processing_step, destination_step=output_step),
        ControlFlowEdge(source_step=output_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            mock_processing_step, OutputMessageStep.OUTPUT, output_step, "processing_message"
        )
    ],
)
conversation = flow.start_conversation(
    inputs={"username": "Username#123", "session_id": "Session#456"}
)
status = conversation.execute()
last_message = status.message
# last_message.content
# Session#456: Received message "Successfully processed username Username#123"
```

**API Reference:** [ControlFlowEdge](../api/flows.md#controlflowedge) | [DataFlowEdge](../api/flows.md#dataflowedge) | [Flow](../api/flows.md#flow) | [OutputMessageStep](../api/flows.md#outputmessagestep)

Learn more about data flow edges in the [Data Flow Edges API reference](../api/flows.md#dataflowedge).

### Executing a sub-flow to an iterable with the MapStep

Applying or executing a sub-flow to an iterable is a common pattern and can be achieved in WayFlow using the [MapStep](../api/flows.md#mapstep).

```python
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.property import AnyProperty
from wayflowcore.steps import MapStep, OutputMessageStep

sub_flow = create_single_step_flow(
    OutputMessageStep(message_template="username={{user}}"), step_name="step"
)
step = MapStep(
    flow=sub_flow,
    unpack_input={"user": "."},
    output_descriptors=[AnyProperty(name=OutputMessageStep.OUTPUT)],
)
iterable = ["a", "b"]
assistant = create_single_step_flow(step, "step")
conversation = assistant.start_conversation(inputs={MapStep.ITERATED_INPUT: iterable})
status = conversation.execute()
status.output_values  # {'output_message': ['username=a', 'username=b']}
```

**API Reference:** [Flow](../api/flows.md#flow) | [MapStep](../api/flows.md#mapstep) | [OutputMessageStep](../api/flows.md#outputmessagestep) | [AnyProperty](../api/flows.md#anyproperty)

Learn more about MapSteps by reading [How to Do Map and Reduce Operations in Flows](../howtoguides/howto_mapstep.md) and the [MapStep API reference](../api/flows.md#mapstep).

### Adding conditional branching to Flows with the BranchingStep

It is also frequent to want to transition in a [Flow](../api/flows.md#flow) depending on a condition, and this can be achieved in WayFlow with the [BranchingStep](../api/flows.md#branchingstep).

![Flow diagram of a simple branching step](core/_static/howto/branchingstep.svg)

**Figure:** An example of a `Flow` using a `BranchingStep`.

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import BranchingStep, OutputMessageStep

NEXT_STEP_NAME_IO = "$next_step_name"
branching_step = BranchingStep(
    branch_name_mapping={"yes": "access_is_granted", "no": "access_is_denied"},
    input_mapping={BranchingStep.NEXT_BRANCH_NAME: NEXT_STEP_NAME_IO},
)
access_granted_output_step = OutputMessageStep("Access granted. Press any key to continue...")
access_denied_output_step = OutputMessageStep("Access denied. Please exit the conversation.")
assistant = Flow(
    begin_step=branching_step,
    steps={
        "branching_step": branching_step,
        "access_granted_output_step": access_granted_output_step,
        "access_denied_output_step": access_denied_output_step,
    },
    control_flow_edges=[
        ControlFlowEdge(
            branching_step, access_granted_output_step, source_branch="access_is_granted"
        ),
        ControlFlowEdge(
            branching_step, access_denied_output_step, source_branch="access_is_denied"
        ),
        ControlFlowEdge(
            branching_step, access_denied_output_step, source_branch=branching_step.BRANCH_DEFAULT
        ),
        ControlFlowEdge(access_granted_output_step, None),
        ControlFlowEdge(access_denied_output_step, None),
    ],
)
conversation = assistant.start_conversation(inputs={NEXT_STEP_NAME_IO: "yes"})
status = conversation.execute()
# status.message.content
# Access granted. Press any key to continue...
```

**API Reference:** [Flow](../api/flows.md#flow) | [BranchingStep](../api/flows.md#branchingstep) | [OutputMessageStep](../api/flows.md#outputmessagestep)

Learn more about branching steps by reading [How to Create Conditional Transitions in Flows](../howtoguides/conditional_flows.md) and
the [BranchingStep API reference](../api/flows.md#branchingstep).

### Adding tools to Flows with the ToolExecutionStep

To use tools in [Flows](../api/flows.md#flow), use the [ToolExecutionStep](../api/flows.md#toolexecutionstep).

```python
from typing import Annotated

from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import tool

@tool
def compute_square_root(x: Annotated[float, "input number to square"]) -> float:
    """Computes the square root of a number"""
    return x**0.5

step = ToolExecutionStep(tool=compute_square_root)
assistant = create_single_step_flow(step)
conversation = assistant.start_conversation(inputs={"x": 123456789.0})
status = conversation.execute()
print(status.output_values)
```

**API Reference:** [Flow](../api/flows.md#flow) | [ToolExecutionStep](../api/flows.md#toolexecutionstep) | [ServerTool](../api/tools.md#servertool)

Learn more about `ToolexecutionSteps` by reading [How to Build Assistants with Tools](../howtoguides/howto_build_assistants_with_tools.md)
and the [ToolexecutionSteps API reference](../api/flows.md#toolexecutionstep).

## Agentic composition patterns

There are four majors agentic composition patterns supported in WayFlow:

* Calling Agents in Flows
* Calling Agents in Agents
* Calling Flows in Agents
* Calling Flows in Flows

### Using an Agent in a Flow

To use [Agents](../api/agent.md#agent) in [Flows](../api/flows.md#flow), you can use the [AgentExecutionStep](../api/flows.md#agentexecutionstep).

```python
from wayflowcore.agent import Agent
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import AgentExecutionStep

code_agent = Agent(
    llm=llm, custom_instruction="Please assist the user by answering their code-related questions"
)

flow = create_single_step_flow(AgentExecutionStep(code_agent))
conversation = flow.start_conversation()
status = conversation.execute()
assert isinstance(status, UserMessageRequestStatus)
print(status.message.content)  # Hi! How can I help you?
status.submit_user_response("Write a simple Python function to sum two numbers")
status = conversation.execute()
assert isinstance(status, UserMessageRequestStatus)
print(status.message.content)  # Here's a simple Python function that ...
```

**API Reference:** [Flow](../api/flows.md#flow) | [Agent](../api/agent.md#agent) | [AgentExecutionStep](../api/flows.md#agentexecutionstep)

Learn more about Agents in Flows by reading [How to Use Agents in Flows](../howtoguides/howto_agents_in_flows.md)
and the [Agent Execution Step API reference](../api/flows.md#agentexecutionstep).

#### WARNING
The `AgentExecutionStep` is currently in beta and may undergo significant changes.
The API and behaviour are not guaranteed to be stable and may change in future versions.

### Multi-Level Agent Workflows

WayFlow supports hierarchical multi-agent systems, by using expert [Agents](../api/agent.md#agent) with a master / manager agent.
This can be achieved by using a [DescribedAgent](../api/agent.md#describedassistant).

```python
from wayflowcore.agent import Agent

code_expert_agent = Agent(
    llm=llm,
    custom_instruction="Please assist the user by answering their code-related questions",
    agent_id="code_expert_subagent",
    name="code_expert",
    description="Expert agent that can assist with code questions",
)
agent = Agent(
    llm=llm,
    custom_instruction="Please assist the user by answering their questions. Call the expert agents at your disposal when needed.",
    agents=[code_expert_agent],
    agent_id="main_agent",
)

conversation = agent.start_conversation()
status = conversation.execute()
assert isinstance(status, UserMessageRequestStatus)
print(status.message.content)  # Hi! How can I help you?
status.submit_user_response("Write a simple Python function to sum two numbers")
status = conversation.execute()
assert isinstance(status, UserMessageRequestStatus)
print(status.message.content)  # Here's a simple Python function that ...
```

**API Reference:** [Agent](../api/agent.md#agent) | [DescribedAgent](../api/agent.md#describedassistant)

#### WARNING
The use of expert agents is currently in beta and may undergo significant changes.
The API and behaviour are not guaranteed to be stable and may change in future versions.

### Using Flows Within Agents

To use [Flows](../api/flows.md#flow) in [Agents](../api/agent.md#agent), use the [DescribedFlow](../api/agent.md#id1).

```python
from wayflowcore.agent import Agent
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import PromptExecutionStep
from wayflowcore.tools import DescribedFlow

code_reviewing_flow = create_single_step_flow(
    PromptExecutionStep(
        prompt_template="Here is some code:\n{{input_code}}\n---\nPlease check for potential bugs in the code",
        llm=llm,
    )
)

agent = Agent(
    llm=llm,
    custom_instruction="Please assist the user by answering their code questions. When creating code, use the code reviewing tool to ensure the code validity before answering the user.",
    flows=[
        DescribedFlow(
            flow=code_reviewing_flow,
            name="reviewing_tool",
            description="Tool to check for potential bugs in a given code",
        )
    ],
)

conversation = agent.start_conversation()
status = conversation.execute()
assert isinstance(status, UserMessageRequestStatus)
print(status.message.content)  # Hi! How can I help you?
status.submit_user_response("Write a simple Python function to sum two numbers")
status = conversation.execute()
assert isinstance(status, UserMessageRequestStatus)
print(status.message.content)  # Here's a simple Python function that ...
```

**API Reference:** [ControlFlowEdge](../api/flows.md#controlflowedge) | [DataFlowEdge](../api/flows.md#dataflowedge) | [Flow](../api/flows.md#flow) | [PromptExecutionStep](../api/flows.md#promptexecutionstep) | [DescribedFlow](../api/agent.md#id1)

Learn more about the use of [Flows](../api/flows.md#flow) in [Agents](../api/agent.md#agent) in the [API reference](../api/agent.md#id1).

### Using Sub-Flows Within Flows

To use sub-flows in [Flows](../api/flows.md#flow), use the [FlowExecutionStep](../api/flows.md#flowexecutionstep).

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import FlowExecutionStep, OutputMessageStep, PromptExecutionStep

code_generation_subflow = create_single_step_flow(
    PromptExecutionStep(
        prompt_template="Please answer the following user question:\n{{user_input}}", llm=llm
    )
)
code_reviewing_subflow = create_single_step_flow(
    PromptExecutionStep(
        prompt_template="Here is some code:\n{{code_input}}\n---\nPlease check for potential bugs in the code and propose an improved version of the code",
        llm=llm,
    )
)

code_generation_step = FlowExecutionStep(code_generation_subflow)
code_reviewing_step = FlowExecutionStep(code_reviewing_subflow)
output_step = OutputMessageStep("{{output_content}}")
flow = Flow(
    begin_step=code_generation_step,
    steps={
        "code_generation": code_generation_step,
        "code_reviewing": code_reviewing_step,
        "display_output": output_step,
    },
    control_flow_edges=[
        ControlFlowEdge(code_generation_step, code_reviewing_step),
        ControlFlowEdge(code_reviewing_step, output_step),
        ControlFlowEdge(output_step, None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            code_generation_step, PromptExecutionStep.OUTPUT, code_reviewing_step, "code_input"
        ),
        DataFlowEdge(
            code_reviewing_step, PromptExecutionStep.OUTPUT, output_step, "output_content"
        ),
    ],
)

conversation = flow.start_conversation(
    {"user_input": "Write a simple Python function to sum two numbers"}
)
status = conversation.execute()
assert isinstance(status, UserMessageRequestStatus)
print(status.message.content)
```

**API Reference:** [ControlFlowEdge](../api/flows.md#controlflowedge) | [DataFlowEdge](../api/flows.md#dataflowedge) | [Flow](../api/flows.md#flow) | [FlowExecutionStep](../api/flows.md#flowexecutionstep) | [OutputMessageStep](../api/flows.md#outputmessagestep) | [PromptExecutionStep](../api/flows.md#promptexecutionstep)

Learn more about the use of sub-flows in [Flows](../api/flows.md#flow) by reading the [FlowExecutionStep API reference](../api/flows.md#flowexecutionstep).

## Saving and loading WayFlow assistants![Serialization/deserialization of Agents and Flows in WayFlow](core/_static/howto/ser_deser.svg)

**Figure:** How serialization works in WayFlow.

### Saving and loading simple assistants

Save and load WayFlow assistants using the [serialize](../api/serialization.md#serialize) and [autodeserialize](../api/serialization.md#autodeserialize) helper functions.

```python
from wayflowcore.agent import Agent
from wayflowcore.serialization import autodeserialize, serialize

agent = Agent(
    llm, custom_instruction="You are a helpful assistant, please answer the user requests."
)

# saving an assistant to its serialized form
serialized_assistant = serialize(agent)

# with open("path/to/agent_config.yaml", "w") as f:
#     f.write(serialized_assistant)

# loading an assistant from its serialized form
# with open("path/to/agent_config.yaml") as f:
#     serialized_assistant = f.read()

agent = autodeserialize(serialized_assistant)
```

**API Reference:** [Agent](../api/agent.md#agent) | [serialize](../api/serialization.md#serialize) | [autodeserialize](../api/serialization.md#autodeserialize)

Learn more about Serialisation by reading [How to Serialize and Deserialize Flows and Agents](../howtoguides/howto_serdeser.md)
and the [Serialisation API reference](../api/serialization.md#serialization).

### Saving and loading assistants with tools

Register tools to a `DeserializationContext` to load assistants using tools.

```python
from wayflowcore.agent import Agent
from wayflowcore.serialization import autodeserialize, serialize
from wayflowcore.serialization.context import DeserializationContext
from wayflowcore.tools import register_server_tool, tool


@tool
def say_hello() -> str:
    """Say hello"""
    return "hello"


agent = Agent(
    llm,
    tools=[say_hello],
    custom_instruction="You are a helpful assistant, please answer the user requests.",
)

# saving an assistant to its serialized form
serialized_assistant = serialize(agent)

# with open("path/to/agent_config.yaml", "w") as f:
#     f.write(serialized_assistant)

# loading an assistant from its serialized form
# with open("path/to/agent_config.yaml") as f:
#     serialized_assistant = f.read()

deserialization_context = DeserializationContext()
register_server_tool(say_hello, deserialization_context.registered_tools)
agent = autodeserialize(serialized_assistant, deserialization_context)
```

**API Reference:** [Agent](../api/agent.md#agent) | [serialize](../api/serialization.md#serialize) | [autodeserialize](../api/serialization.md#autodeserialize) | [tool](../api/tools.md#tooldecorator)

Learn more about Serialisation by reading [How to Serialize and Deserialize Flows and Agents](../howtoguides/howto_serdeser.md)
and the [Serialisation API reference](../api/serialization.md#serialization).

## Providing context to assistants

Passing contextual information to assistants can be done in several ways, including:

* By specifying input values when creating the [Conversation](../api/conversation.md#id2).
* By using [ContextProviders](../api/contextproviders.md#contextprovider).
* By using [Variables](../api/variables.md#variable).

### Providing context with inputs

You can pass static inputs when creating a new [Conversation](../api/conversation.md#id2).

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep

output_step = OutputMessageStep("{{message_content}}")
flow = Flow(
    begin_step=output_step,
    steps={"output_step": output_step},
    control_flow_edges=[ControlFlowEdge(output_step, None)],
)

input_context = {"message_content": "Here is my input context"}
conversation = flow.start_conversation(inputs=input_context)
status = conversation.execute()
assert isinstance(status, UserMessageRequestStatus)
print(status.message.content)
```

**API Reference:** [ControlFlowEdge](../api/flows.md#controlflowedge) | [Flow](../api/flows.md#flow) | [OutputMessageStep](../api/flows.md#outputmessagestep)

Learn more about passing static inputs in the [Conversation API reference](../api/conversation.md#id2).

### Providing dynamic inputs with ContextProviders

[ContextProviders](../api/contextproviders.md#contextprovider) can be used to provide dynamic information to WayFlow assistants.

#### Using the ToolContextProvider

Use the [ToolContextProvider](../api/contextproviders.md#toolcontextprovider) to provide information to an assistant with a tool.

```python
from wayflowcore.contextproviders import ToolContextProvider
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.tools import tool


@tool
def current_time() -> str:
    """Return the current time"""
    from datetime import datetime

    return str(datetime.now())


current_time_contextprovider = ToolContextProvider(current_time, "current_time")
output_step = OutputMessageStep("Current time: {{time}}\nMessage content: {{message_content}}")
flow = Flow(
    begin_step=output_step,
    steps={"output_step": output_step},
    control_flow_edges=[ControlFlowEdge(output_step, None)],
    data_flow_edges=[
        DataFlowEdge(current_time_contextprovider, "current_time", output_step, "time")
    ],
    context_providers=[current_time_contextprovider],
)

input_context = {"message_content": "Here is my input context"}
conversation = flow.start_conversation(inputs=input_context)
conversation.execute()
assert isinstance(status, UserMessageRequestStatus)
print(status.message.content)
```

**API Reference:** [ControlFlowEdge](../api/flows.md#controlflowedge) | [ToolContextProvider](../api/contextproviders.md#toolcontextprovider) | [DataFlowEdge](../api/flows.md#dataflowedge) | [Flow](../api/flows.md#flow) | [tool](../api/tools.md#tooldecorator) | [OutputMessageStep](../api/flows.md#outputmessagestep)

Learn more by reading the [ToolContextProvider API reference](../api/contextproviders.md#toolcontextprovider).

#### Using the FlowContextProvider

Use the [FlowContextProvider](../api/contextproviders.md#flowcontextprovider) to provide information to an assistant with a [Flow](../api/flows.md#flow).

```python
from wayflowcore.contextproviders import FlowContextProvider
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import OutputMessageStep

contextual_flow = create_single_step_flow(
    OutputMessageStep(
        message_template="The current time is 2pm.",
        output_mapping={OutputMessageStep.OUTPUT: "time_output"},
    )
)
context_provider = FlowContextProvider(contextual_flow, flow_output_names=["time_output"])
output_step = OutputMessageStep("Last time message: {{time_output_io}}")
flow = Flow(
    begin_step=output_step,
    steps={"output_step": output_step},
    control_flow_edges=[ControlFlowEdge(output_step, None)],
    data_flow_edges=[DataFlowEdge(context_provider, "time_output", output_step, "time_output_io")],
    context_providers=[context_provider],
)
conversation = flow.start_conversation()
execution_status = conversation.execute()
assert isinstance(execution_status, UserMessageRequestStatus)
print(execution_status.message.content)  # Last time message: The current time is 2pm.
```

**API Reference:** [FlowContextProvider](../api/contextproviders.md#flowcontextprovider) | [ControlFlowEdge](../api/flows.md#controlflowedge) | [DataFlowEdge](../api/flows.md#dataflowedge) | [Flow](../api/flows.md#flow) | [OutputMessageStep](../api/flows.md#outputmessagestep)

Learn more by reading the [FlowContextProvider API reference](../api/contextproviders.md#flowcontextprovider).

### Using Variables to provide context

You can use [Variables](../api/variables.md#variable) as an alternative way to manage context (or shared state) in [Flows](../api/flows.md#flow).
They let you store and reuse information across different steps in Flows.

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import FloatProperty
from wayflowcore.steps import OutputMessageStep, VariableReadStep, ToolExecutionStep, VariableWriteStep
from wayflowcore.variable import Variable
from wayflowcore.tools import tool

float_variable = Variable(
    name="float_variable",
    type=FloatProperty(),
    description="a float variable",
    default_value=5.0,
)

read_step_1 = VariableReadStep(variable=float_variable)


@tool(description_mode="only_docstring")
def triple_number(x: float) -> float:
    "Tool that triples a number"
    return x*3

triple_step = ToolExecutionStep(tool=triple_number)

write_step = VariableWriteStep(variable=float_variable)
read_step_2 = VariableReadStep(variable=float_variable)
output_step = OutputMessageStep("The variable is {{ variable }}")

flow = Flow(
    begin_step=read_step_1,
    control_flow_edges=[
        ControlFlowEdge(read_step_1, triple_step),
        ControlFlowEdge(triple_step, write_step),
        ControlFlowEdge(write_step, read_step_2),
        ControlFlowEdge(read_step_2, output_step),
        ControlFlowEdge(output_step, None),
    ],
    data_flow_edges=[
        DataFlowEdge(read_step_1, VariableReadStep.VALUE, triple_step, "x"),
        DataFlowEdge(triple_step, ToolExecutionStep.TOOL_OUTPUT, write_step, VariableWriteStep.VALUE),
        DataFlowEdge(read_step_2, VariableReadStep.VALUE, output_step, "variable")
    ],
    variables=[float_variable]
)

conversation = flow.start_conversation()
status = conversation.execute()
assert isinstance(status, UserMessageRequestStatus)
print(status.message.content)
```

**API Reference:** [ControlFlowEdge](../api/flows.md#controlflowedge) | [DataFlowEdge](../api/flows.md#dataflowedge) | [Flow](../api/flows.md#flow) | [ListProperty](../api/flows.md#listproperty) | [FloatProperty](../api/flows.md#floatproperty) | [VariableReadStep](../api/flows.md#variablereadstep) | [VariableWriteStep](../api/flows.md#variablewritestep) | [OutputMessageStep](../api/flows.md#outputmessagestep) | [Variable](../api/variables.md#variable)

Learn more by reading the [Variables API reference](../api/variables.md#variable).

<a id="flowbuilder-ref-sheet"></a>

### Flow Builder quick snippets

Build a sequence, then entry/finish:

```python
from wayflowcore.flowbuilder import FlowBuilder
from wayflowcore.steps import OutputMessageStep

n1 = OutputMessageStep(name="n1", message_template="{{username}}")
n2 = OutputMessageStep(name="n2", message_template="Hello, {{username}}")

flow = (
    FlowBuilder()
    .add_sequence([n1, n2])
    .set_entry_point(n1)
    .set_finish_points(n2)
    .build()
)
from wayflowcore.executors.executionstatus import FinishedStatus
conversation = flow.start_conversation({"username": "User_123"})
status = conversation.execute()
assert isinstance(status, FinishedStatus)
print(status.output_values)
# {'output_message': 'Hello, User_123'}
```

API Reference: [FlowBuilder](../api/flows.md#flowbuilder)

Build a linear flow in one line:

```python
from wayflowcore.flowbuilder import FlowBuilder
from wayflowcore.steps import OutputMessageStep

greet = OutputMessageStep(name="greet", message_template="Say hello")
reply = OutputMessageStep(name="reply", message_template="Say world")

linear_flow = FlowBuilder.build_linear_flow([greet, reply])
```

Add a conditional using a step output as key, with a default branch:

```python
decider = OutputMessageStep(name="decider", message_template="Return success or fail")
on_success = OutputMessageStep(name="on_success", message_template="OK")
on_fail = OutputMessageStep(name="on_fail", message_template="KO")

flow_with_branch = (
    FlowBuilder()
    .add_step(decider)
    .add_step(on_success)
    .add_step(on_fail)
    .add_conditional(
        source_step=decider,
        source_value=decider.OUTPUT,
        destination_map={"success": on_success, "fail": on_fail},
        default_destination=on_fail,
    )
    .set_entry_point(decider)
    .set_finish_points([on_success, on_fail])
    .build()
)
```
