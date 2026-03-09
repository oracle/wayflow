<a id="top-serdeser"></a>

# How to Serialize and Deserialize Flows and Agents![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Serialization and deserialization how-to script](../end_to_end_code_examples/howto_serdeser.py)

#### Prerequisites
This guide assumes familiarity with:

- [Flows](../tutorials/basic_flow.md)
- [Agents](../tutorials/basic_agent.md)

Assistant serialization is a crucial feature in WayFlow that allows you to save and load [Agents](../api/agent.md#agent) and [Flows](../api/flows.md#flow),
making it easy to persist their configurations and reuse them as needed.

In this guide, you will learn how to:

- Serialize a simple Agent or Flow and deserialize it back into an executable assistant.
- Use serialization for more complex assistants using tools.

![Serialization/deserialization of Agents and Flows in WayFlow](core/_static/howto/ser_deser.svg)

## Saving and loading simple assistants

This section shows you how to serialize and reload WayFlow [Agents](../api/agent.md#agent) and [Flows](../api/flows.md#flow).

### Flows

Start by creating a simple `Flow` that takes a user question as input and responds using an LLM.

```python
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty
from wayflowcore.steps import CompleteStep, OutputMessageStep, PromptExecutionStep, StartStep
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

start_step = StartStep(input_descriptors=[StringProperty("user_question")], name="start_step")
llm_execution_step = PromptExecutionStep(
    prompt_template="You are a helpful assistant, please answer the user request:{{user_request}}",
    llm=llm,
    name="llm_execution_step",
)
output_step = OutputMessageStep(message_template="{{llm_answer}}", name="output_step")
complete_step = CompleteStep(name="complete_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=llm_execution_step),
        ControlFlowEdge(source_step=llm_execution_step, destination_step=output_step),
        ControlFlowEdge(source_step=output_step, destination_step=complete_step),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "user_question", llm_execution_step, "user_request"),
        DataFlowEdge(llm_execution_step, PromptExecutionStep.OUTPUT, output_step, "llm_answer"),
    ],
)
```

**API Reference:** [Flow](../api/flows.md#flow) | [PromptExecutionStep](../api/flows.md#promptexecutionstep)

Once you have built the flow, you can serialize it using the `serialize` helper function.

```python
from wayflowcore.serialization import serialize

serialized_flow = serialize(flow)
# Then the serialized flow can be easily saved as a YAML file
# with open("flow_config.yaml", 'w') as f:
#     f.write(serialized_flow)
```

**API Reference:** [serialize](../api/serialization.md#serialize)

Then, save the serialized flow as a regular text file.

To deserialize the flow configuration back, use the `autodeserialize` helper function.

```python
from wayflowcore.serialization import autodeserialize

# The YAML representation can be loaded as follows
# with open("flow_config.yaml") as f:
#     serialized_flow = f.read()

serialized_flow = """
_component_type: Flow
_referenced_objects:
  controlflowedge/4440502672:
    destination_step:
      $ref: promptexecutionstep/4440501184
    source_branch: next
    source_step:
      $ref: startstep/4440501136
  controlflowedge/4440505648:
    destination_step: null
    source_branch: next
    source_step:
      $ref: outputmessagestep/4440505696
  controlflowedge/4440505888:
    destination_step:
      $ref: outputmessagestep/4440505696
    source_branch: next
    source_step:
      $ref: promptexecutionstep/4440501184
  dataflowedge/4440503008:
    destination_input: llm_answer
    destination_step:
      $ref: outputmessagestep/4440505696
    source_output: output
    source_step:
      $ref: promptexecutionstep/4440501184
  dataflowedge/4440504592:
    destination_input: user_request
    destination_step:
      $ref: promptexecutionstep/4440501184
    source_output: user_question
    source_step:
      $ref: startstep/4440501136
  outputmessagestep/4440505696:
    _component_type: Step
    input_descriptors:
    - $ref: stringproperty/4440504160
    input_mapping: {}
    output_descriptors:
    - $ref: stringproperty/4440503200
    output_mapping: {}
    step_args:
      input_descriptors:
      - _component_type: Property
        description: '"llm_answer" input variable for the template'
        title: llm_answer
        type: string
      input_mapping: {}
      llm: null
      message_template: '{{llm_answer}}'
      message_type: AGENT
      output_descriptors:
      - _component_type: Property
        description: the message added to the messages list
        title: output_message
        type: string
      output_mapping: {}
      rephrase: false
    step_cls: OutputMessageStep
  promptexecutionstep/4440501184:
    _component_type: Step
    input_descriptors:
    - $ref: stringproperty/4440502720
    input_mapping: {}
    output_descriptors:
    - $ref: stringproperty/4440501376
    output_mapping: {}
    step_args:
      generation_config: null
      input_descriptors:
      - _component_type: Property
        description: '"user_request" input variable for the template'
        title: user_request
        type: string
      input_mapping: {}
      llm:
        $ref: vllmmodel/4384406112
      output_descriptors:
      - _component_type: Property
        description: the generated text
        title: output
        type: string
      output_mapping: {}
      prompt_template: You are a helpful assistant, please answer the user request:{{user_request}}
    step_cls: PromptExecutionStep
  startstep/4440501136:
    _component_type: Step
    input_descriptors:
    - $ref: stringproperty/4384405872
    input_mapping: {}
    output_descriptors:
    - $ref: stringproperty/4384405872
    output_mapping: {}
    step_args:
      input_descriptors:
      - _component_type: Property
        title: user_question
        type: string
      input_mapping: {}
      output_descriptors:
      - _component_type: Property
        title: user_question
        type: string
      output_mapping: {}
    step_cls: StartStep
  stringproperty/4384405872:
    _component_type: Property
    title: user_question
    type: string
  stringproperty/4440501376:
    _component_type: Property
    description: the generated text
    title: output
    type: string
  stringproperty/4440502720:
    _component_type: Property
    description: '"user_request" input variable for the template'
    title: user_request
    type: string
  stringproperty/4440503200:
    _component_type: Property
    description: the message added to the messages list
    title: output_message
    type: string
  stringproperty/4440504160:
    _component_type: Property
    description: '"llm_answer" input variable for the template'
    title: llm_answer
    type: string
  vllmmodel/4384406112:
    _component_type: LlmModel
    generation_config: null
    host_port: LLAMA70BV33_API_URL
    model_id: LLAMA70B_MODEL_ID
    model_type: vllm
begin_step_name: start_step
control_flow_edges:
- $ref: controlflowedge/4440502672
- $ref: controlflowedge/4440505888
- $ref: controlflowedge/4440505648
data_flow_edges:
- $ref: dataflowedge/4440504592
- $ref: dataflowedge/4440503008
end_steps:
- null
steps:
  llm_execution_step:
    $ref: promptexecutionstep/4440501184
  output_step:
    $ref: outputmessagestep/4440505696
  start_step:
    $ref: startstep/4440501136
variables: []
""".strip()

deserialized_flow: Flow = autodeserialize(serialized_flow)
```

**API Reference:** [autodeserialize](../api/serialization.md#autodeserialize)

After deserialization, the flow is ready to execute like any other WayFlow assistant.

#### NOTE
The serialized configuration file contains all elements that compose the [Flow](../api/flows.md#flow).
However, this file is not intended to be human-readable and should only be handled using the `serialize` and `autodeserialize` functions.

### Agents

Continue to building a simple conversational `Agent` that can answer user questions.

```python
from wayflowcore.agent import Agent

agent = Agent(
    llm=llm,
    custom_instruction="You are a helpful assistant, please answer user requests",
)
```

**API Reference:** [Agent](../api/agent.md#agent)

Once you have built the agent, you can serialize it using the `serialize` helper function.

```python
from wayflowcore.serialization import serialize

serialized_agent = serialize(agent)
# Then the serialized agent can be easily saved as a YAML file
# with open("agent_config.yaml", 'w') as f:
#     f.write(serialized_agent)
```

**API Reference:** [serialize](../api/serialization.md#serialize)

Then, save the serialized agent as a regular text file.

To deserialize the agent configuration back, use the `autodeserialize` helper function.

```python
from wayflowcore.serialization import autodeserialize

# The YAML representation can be loaded as follows
# with open("agent_config.yaml") as f:
#     serialized_agent = f.read()

serialized_agent = """
_component_type: Agent
_referenced_objects:
  vllmmodel/4357290592:
    _component_type: LlmModel
    generation_config: null
    host_port: LLAMA70BV33_API_URL
    model_id: LLAMA70B_MODEL_ID
    model_type: vllm
agents: []
caller_input_mode: always
can_finish_conversation: false
context_providers: []
custom_instruction: You are a helpful assistant, please answer user requests
flows: []
initial_message: Hi! How can I help you?
input_descriptors: []
llm:
  $ref: vllmmodel/4357290592
max_iterations: 10
output_descriptors: []
tools: []
""".strip()
deserialized_agent: Agent = autodeserialize(serialized_agent)

```

**API Reference:** [autodeserialize](../api/serialization.md#autodeserialize)

Similar to the Flow example above, once deserialized, the agent is ready to execute like any other WayFlow assistant.

## Saving and loading assistants equipped with tools

In this more advanced example, you will build assistants that use WayFlow Tools (such as [ServerTool](../api/tools.md#servertool)).
These assistants require additional code to deserialize them into executable assistants.

### Flows

Create a `Flow` that asks the user for an input text, counts the number of characters, and generates a message with the result.

```python
from typing import Annotated

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.steps import InputMessageStep, OutputMessageStep, ToolExecutionStep

# Step names
ASK_USER_FOR_TEXT_STEP = "ask_user_for_text_step"
EXECUTE_TOOL_STEP = "execute_tool_step"
OUTPUT_MESSAGE_STEP = "output_message_step"

# Tool
from wayflowcore.tools import tool

@tool
def count_characters(
    text: Annotated[str, "Text for which want compute the number of characters"],
) -> str:
    """Count the number of characters in the given text"""
    return str(len(text))

# Define the steps and the Flow
ask_user_for_text_step = InputMessageStep(
    message_template="Please enter the text to count the number of characters of",
    name="ask_user_for_text_step",
)
execute_tool_step = ToolExecutionStep(tool=count_characters, name="execute_tool_step")
output_message_step = OutputMessageStep(
    message_template="There are {{num_characters}} characters in the following text:\n{{input_text}}",
    name="output_message_step",
)
flow = Flow(
    begin_step=ask_user_for_text_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=ask_user_for_text_step, destination_step=execute_tool_step),
        ControlFlowEdge(source_step=execute_tool_step, destination_step=output_message_step),
        ControlFlowEdge(source_step=output_message_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            ask_user_for_text_step, InputMessageStep.USER_PROVIDED_INPUT, execute_tool_step, "text"
        ),
        DataFlowEdge(
            ask_user_for_text_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            output_message_step,
            "input_text",
        ),
        DataFlowEdge(
            execute_tool_step, ToolExecutionStep.TOOL_OUTPUT, output_message_step, "num_characters"
        ),
        DataFlowEdge(
            ask_user_for_text_step, InputMessageStep.USER_PROVIDED_INPUT, execute_tool_step, "text"
        ),
        DataFlowEdge(
            ask_user_for_text_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            output_message_step,
            "input_text",
        ),
        DataFlowEdge(
            execute_tool_step, ToolExecutionStep.TOOL_OUTPUT, output_message_step, "num_characters"
        ),
    ],
)
# We can serialize the flow as before
serialized_flow = serialize(flow)
```

**API Reference:** [InputMessageStep](../api/flows.md#inputmessagestep) |
[OutputMessageStep](../api/flows.md#outputmessagestep) | [ToolExecutionStep](../api/flows.md#toolexecutionstep) |
[ServerTool](../api/tools.md#servertool)

Serialize your flow just like any other assistant.

To deserialize the flow, you need to provide context about the tool used in the original flow.
This can be done using `DeserializationContext`.

```python
from wayflowcore.serialization import autodeserialize
from wayflowcore.serialization.context import DeserializationContext

serialized_flow = """
_component_type: Flow
_referenced_objects:
  controlflowedge/4395505584:
    destination_step:
      $ref: toolexecutionstep/4395515664
    source_branch: next
    source_step:
      $ref: inputmessagestep/4395511296
  controlflowedge/4395506928:
    destination_step:
      $ref: outputmessagestep/4395511584
    source_branch: next
    source_step:
      $ref: toolexecutionstep/4395515664
  controlflowedge/4395514320:
    destination_step: null
    source_branch: next
    source_step:
      $ref: outputmessagestep/4395511584
  controlflowedge/4395514656:
    destination_step:
      $ref: inputmessagestep/4395511296
    source_branch: next
    source_step:
      $ref: startstep/4395515424
  dataflowedge/4395503760:
    destination_input: num_characters
    destination_step:
      $ref: outputmessagestep/4395511584
    source_output: tool_output
    source_step:
      $ref: toolexecutionstep/4395515664
  dataflowedge/4395510192:
    destination_input: input_text
    destination_step:
      $ref: outputmessagestep/4395511584
    source_output: user_provided_input
    source_step:
      $ref: inputmessagestep/4395511296
  dataflowedge/4395514032:
    destination_input: text
    destination_step:
      $ref: toolexecutionstep/4395515664
    source_output: user_provided_input
    source_step:
      $ref: inputmessagestep/4395511296
  inputmessagestep/4395511296:
    _component_type: Step
    input_descriptors: []
    input_mapping: {}
    output_descriptors:
    - $ref: stringproperty/4395512400
    output_mapping: {}
    step_args:
      input_descriptors: []
      input_mapping: {}
      llm: null
      message_template: Please enter the text to count the number of characters of
      output_descriptors:
      - _component_type: Property
        description: the input value provided by the user
        title: user_provided_input
        type: string
      output_mapping: {}
      rephrase: false
    step_cls: InputMessageStep
  outputmessagestep/4395511584:
    _component_type: Step
    input_descriptors:
    - $ref: stringproperty/4395506880
    - $ref: stringproperty/4395510000
    input_mapping: {}
    output_descriptors:
    - $ref: stringproperty/4395508896
    output_mapping: {}
    step_args:
      input_descriptors:
      - _component_type: Property
        description: '"input_text" input variable for the template'
        title: input_text
        type: string
      - _component_type: Property
        description: '"num_characters" input variable for the template'
        title: num_characters
        type: string
      input_mapping: {}
      llm: null
      message_template: 'There are {{num_characters}} characters in the following
        text:

        {{input_text}}'
      message_type: AGENT
      output_descriptors:
      - _component_type: Property
        description: the message added to the messages list
        title: output_message
        type: string
      output_mapping: {}
      rephrase: false
    step_cls: OutputMessageStep
  servertool/4401253344:
    __metadata_info__: {}
    _component_type: Tool
    description: Count the number of characters in the given text
    name: count_characters
    output:
      type: string
    parameters:
      text:
        description: Text for which want compute the number of characters
        title: Text
        type: string
    tool_type: server
  startstep/4395515424:
    _component_type: Step
    input_descriptors: []
    input_mapping: {}
    output_descriptors: []
    output_mapping: {}
    step_args:
      input_descriptors: []
      input_mapping: {}
      output_descriptors: []
      output_mapping: {}
    step_cls: StartStep
  stringproperty/4395506160:
    _component_type: Property
    title: tool_output
    type: string
  stringproperty/4395506208:
    _component_type: Property
    description: Text for which want compute the number of characters
    title: text
    type: string
  stringproperty/4395506880:
    _component_type: Property
    description: '"input_text" input variable for the template'
    title: input_text
    type: string
  stringproperty/4395508896:
    _component_type: Property
    description: the message added to the messages list
    title: output_message
    type: string
  stringproperty/4395510000:
    _component_type: Property
    description: '"num_characters" input variable for the template'
    title: num_characters
    type: string
  stringproperty/4395512400:
    _component_type: Property
    description: the input value provided by the user
    title: user_provided_input
    type: string
  toolexecutionstep/4395515664:
    _component_type: Step
    input_descriptors:
    - $ref: stringproperty/4395506208
    input_mapping: {}
    output_descriptors:
    - $ref: stringproperty/4395506160
    output_mapping: {}
    step_args:
      input_descriptors:
      - _component_type: Property
        description: Text for which want compute the number of characters
        title: text
        type: string
      input_mapping: {}
      output_descriptors:
      - _component_type: Property
        title: tool_output
        type: string
      output_mapping: {}
      raise_exceptions: false
      tool:
        $ref: servertool/4401253344
    step_cls: ToolExecutionStep
begin_step_name: __StartStep__
control_flow_edges:
- $ref: controlflowedge/4395505584
- $ref: controlflowedge/4395506928
- $ref: controlflowedge/4395514320
- $ref: controlflowedge/4395514656
data_flow_edges:
- $ref: dataflowedge/4395514032
- $ref: dataflowedge/4395510192
- $ref: dataflowedge/4395503760
end_steps:
- null
steps:
  __StartStep__:
    $ref: startstep/4395515424
  ask_user_for_text_step:
    $ref: inputmessagestep/4395511296
  execute_tool_step:
    $ref: toolexecutionstep/4395515664
  output_message_step:
    $ref: outputmessagestep/4395511584
variables: []
""".strip()

deserialization_context = DeserializationContext()
deserialization_context.registered_tools[count_characters.name] = count_characters
deserialized_flow: Flow = autodeserialize(serialized_flow, deserialization_context)
```

After registering the tool in the dictionary of tools, pass the deserialization context to the `autodeserialize` function to deserialize the flow.

#### IMPORTANT
Ensure that tool names in `DeserializationContext.registered_tools` are unique to avoid conflicts.

### Agents

Create an `Agent` that can access a tool to count the number of characters in a given text (this agent is equivalent to the flow example above).

```python
from wayflowcore.tools import tool

# Tool
@tool
def count_characters(
    text: Annotated[str, "Text for which want compute the number of characters"],
) -> str:
    """Count the number of characters in the given text"""
    return str(len(text))

agent = Agent(
    llm=llm,
    tools=[count_characters],
    custom_instruction="You are a helpful assistant, please answer user requests",
)
serialized_agent = serialize(agent)
```

**API Reference:** [ServerTool](../api/tools.md#servertool)

Serialize your agent just like any other assistant.

Similar to the Flow example, deserializing the agent requires providing context about the tool used in the original agent.
This can be done using `DeserializationContext`.

```python
from wayflowcore.serialization import autodeserialize
from wayflowcore.serialization.context import DeserializationContext

serialized_agent = """
_component_type: Agent
_referenced_objects:
  servertool/4443551104:
    __metadata_info__: {}
    _component_type: Tool
    description: Count the number of characters in the given text
    name: count_characters
    output:
      type: string
    parameters:
      text:
        description: Text for which want compute the number of characters
        title: Text
        type: string
    tool_type: server
  vllmmodel/4426025136:
    _component_type: LlmModel
    generation_config: null
    host_port: LLAMA70BV33_API_URL
    model_id: LLAMA70B_MODEL_ID
    model_type: vllm
agents: []
caller_input_mode: always
can_finish_conversation: false
context_providers: []
custom_instruction: You are a helpful assistant, please answer user requests
flows: []
initial_message: Hi! How can I help you?
llm:
  $ref: vllmmodel/4426025136
max_iterations: 10
outputs: null
tools:
- $ref: servertool/4443551104
""".strip()

deserialization_context = DeserializationContext()
deserialization_context.registered_tools[count_characters.name] = count_characters
deserialized_agent: Agent = autodeserialize(serialized_agent, deserialization_context)
```

After registering the tool in the dictionary of tools, pass the deserialization context to the `autodeserialize` function to deserialize the agent.

#### IMPORTANT
Ensure that tool names in `DeserializationContext.registered_tools` are unique to avoid conflicts.

## Agent Spec Exporting/Loading

You can export the flow or agent configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

config_flow = AgentSpecExporter().to_json(flow)
config_agent = AgentSpecExporter().to_json(agent)
```

And load it back using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

new_flow = AgentSpecLoader(tool_registry={"count_characters": count_characters}).load_json(
    config_flow
)
new_agent = AgentSpecLoader(tool_registry={"count_characters": count_characters}).load_json(
    config_agent
)
```

## Recap

In this guide, you learned how to serialize WayFlow [Agents](../api/agent.md#agent) and [Flows](../api/flows.md#flow), as well as how to handle deserialization for assistants that use tools.

## Next steps

Having learned how to serialize and deserialize assistants built with WayFlow, you may now proceed to:

- [How to Create Conditional Transitions in Flows](conditional_flows.md)
- [How to Create a ServerTool from a Flow](create_a_tool_from_a_flow.md)

## Full code

Click on the card at the [top of this page](#top-serdeser) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Serialize and Deserialize Components
# ----------------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.2.0.dev0" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_serdeser.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Configure LLM

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## Simple Flow Creation

# %%
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty
from wayflowcore.steps import CompleteStep, OutputMessageStep, PromptExecutionStep, StartStep
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

start_step = StartStep(input_descriptors=[StringProperty("user_question")], name="start_step")
llm_execution_step = PromptExecutionStep(
    prompt_template="You are a helpful assistant, please answer the user request:{{user_request}}",
    llm=llm,
    name="llm_execution_step",
)
output_step = OutputMessageStep(message_template="{{llm_answer}}", name="output_step")
complete_step = CompleteStep(name="complete_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=llm_execution_step),
        ControlFlowEdge(source_step=llm_execution_step, destination_step=output_step),
        ControlFlowEdge(source_step=output_step, destination_step=complete_step),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "user_question", llm_execution_step, "user_request"),
        DataFlowEdge(llm_execution_step, PromptExecutionStep.OUTPUT, output_step, "llm_answer"),
    ],
)

# %%[markdown]
## Simple Flow Serialization

# %%
from wayflowcore.serialization import serialize

serialized_flow = serialize(flow)
# Then the serialized flow can be easily saved as a YAML file
# with open("flow_config.yaml", 'w') as f:
#     f.write(serialized_flow)

# %%[markdown]
## Simple Flow Deserialization

# %%
from wayflowcore.serialization import autodeserialize

# The YAML representation can be loaded as follows
# with open("flow_config.yaml") as f:
#     serialized_flow = f.read()

serialized_flow = """
_component_type: Flow
_referenced_objects:
  controlflowedge/4440502672:
    destination_step:
      $ref: promptexecutionstep/4440501184
    source_branch: next
    source_step:
      $ref: startstep/4440501136
  controlflowedge/4440505648:
    destination_step: null
    source_branch: next
    source_step:
      $ref: outputmessagestep/4440505696
  controlflowedge/4440505888:
    destination_step:
      $ref: outputmessagestep/4440505696
    source_branch: next
    source_step:
      $ref: promptexecutionstep/4440501184
  dataflowedge/4440503008:
    destination_input: llm_answer
    destination_step:
      $ref: outputmessagestep/4440505696
    source_output: output
    source_step:
      $ref: promptexecutionstep/4440501184
  dataflowedge/4440504592:
    destination_input: user_request
    destination_step:
      $ref: promptexecutionstep/4440501184
    source_output: user_question
    source_step:
      $ref: startstep/4440501136
  outputmessagestep/4440505696:
    _component_type: Step
    input_descriptors:
    - $ref: stringproperty/4440504160
    input_mapping: {}
    output_descriptors:
    - $ref: stringproperty/4440503200
    output_mapping: {}
    step_args:
      input_descriptors:
      - _component_type: Property
        description: '"llm_answer" input variable for the template'
        title: llm_answer
        type: string
      input_mapping: {}
      llm: null
      message_template: '{{llm_answer}}'
      message_type: AGENT
      output_descriptors:
      - _component_type: Property
        description: the message added to the messages list
        title: output_message
        type: string
      output_mapping: {}
      rephrase: false
    step_cls: OutputMessageStep
  promptexecutionstep/4440501184:
    _component_type: Step
    input_descriptors:
    - $ref: stringproperty/4440502720
    input_mapping: {}
    output_descriptors:
    - $ref: stringproperty/4440501376
    output_mapping: {}
    step_args:
      generation_config: null
      input_descriptors:
      - _component_type: Property
        description: '"user_request" input variable for the template'
        title: user_request
        type: string
      input_mapping: {}
      llm:
        $ref: vllmmodel/4384406112
      output_descriptors:
      - _component_type: Property
        description: the generated text
        title: output
        type: string
      output_mapping: {}
      prompt_template: You are a helpful assistant, please answer the user request:{{user_request}}
    step_cls: PromptExecutionStep
  startstep/4440501136:
    _component_type: Step
    input_descriptors:
    - $ref: stringproperty/4384405872
    input_mapping: {}
    output_descriptors:
    - $ref: stringproperty/4384405872
    output_mapping: {}
    step_args:
      input_descriptors:
      - _component_type: Property
        title: user_question
        type: string
      input_mapping: {}
      output_descriptors:
      - _component_type: Property
        title: user_question
        type: string
      output_mapping: {}
    step_cls: StartStep
  stringproperty/4384405872:
    _component_type: Property
    title: user_question
    type: string
  stringproperty/4440501376:
    _component_type: Property
    description: the generated text
    title: output
    type: string
  stringproperty/4440502720:
    _component_type: Property
    description: '"user_request" input variable for the template'
    title: user_request
    type: string
  stringproperty/4440503200:
    _component_type: Property
    description: the message added to the messages list
    title: output_message
    type: string
  stringproperty/4440504160:
    _component_type: Property
    description: '"llm_answer" input variable for the template'
    title: llm_answer
    type: string
  vllmmodel/4384406112:
    _component_type: LlmModel
    generation_config: null
    host_port: LLAMA70BV33_API_URL
    model_id: LLAMA70B_MODEL_ID
    model_type: vllm
begin_step_name: start_step
control_flow_edges:
- $ref: controlflowedge/4440502672
- $ref: controlflowedge/4440505888
- $ref: controlflowedge/4440505648
data_flow_edges:
- $ref: dataflowedge/4440504592
- $ref: dataflowedge/4440503008
end_steps:
- null
steps:
  llm_execution_step:
    $ref: promptexecutionstep/4440501184
  output_step:
    $ref: outputmessagestep/4440505696
  start_step:
    $ref: startstep/4440501136
variables: []
""".strip()

deserialized_flow: Flow = autodeserialize(serialized_flow)

# %%[markdown]
## Simple Agent Creation

# %%
from wayflowcore.agent import Agent

agent = Agent(
    llm=llm,
    custom_instruction="You are a helpful assistant, please answer user requests",
)

# %%[markdown]
## Simple Agent Serialization

# %%
from wayflowcore.serialization import serialize

serialized_agent = serialize(agent)
# Then the serialized agent can be easily saved as a YAML file
# with open("agent_config.yaml", 'w') as f:
#     f.write(serialized_agent)

# %%[markdown]
## Simple Agent Deserialization

# %%
from wayflowcore.serialization import autodeserialize

# The YAML representation can be loaded as follows
# with open("agent_config.yaml") as f:
#     serialized_agent = f.read()

serialized_agent = """
_component_type: Agent
_referenced_objects:
  vllmmodel/4357290592:
    _component_type: LlmModel
    generation_config: null
    host_port: LLAMA70BV33_API_URL
    model_id: LLAMA70B_MODEL_ID
    model_type: vllm
agents: []
caller_input_mode: always
can_finish_conversation: false
context_providers: []
custom_instruction: You are a helpful assistant, please answer user requests
flows: []
initial_message: Hi! How can I help you?
input_descriptors: []
llm:
  $ref: vllmmodel/4357290592
max_iterations: 10
output_descriptors: []
tools: []
""".strip()
deserialized_agent: Agent = autodeserialize(serialized_agent)


# %%[markdown]
## Complex Flow Creation

# %%
from typing import Annotated

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.steps import InputMessageStep, OutputMessageStep, ToolExecutionStep

# Step names
ASK_USER_FOR_TEXT_STEP = "ask_user_for_text_step"
EXECUTE_TOOL_STEP = "execute_tool_step"
OUTPUT_MESSAGE_STEP = "output_message_step"

# Tool
from wayflowcore.tools import tool

@tool
def count_characters(
    text: Annotated[str, "Text for which want compute the number of characters"],
) -> str:
    """Count the number of characters in the given text"""
    return str(len(text))

# Define the steps and the Flow
ask_user_for_text_step = InputMessageStep(
    message_template="Please enter the text to count the number of characters of",
    name="ask_user_for_text_step",
)
execute_tool_step = ToolExecutionStep(tool=count_characters, name="execute_tool_step")
output_message_step = OutputMessageStep(
    message_template="There are {{num_characters}} characters in the following text:\n{{input_text}}",
    name="output_message_step",
)
flow = Flow(
    begin_step=ask_user_for_text_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=ask_user_for_text_step, destination_step=execute_tool_step),
        ControlFlowEdge(source_step=execute_tool_step, destination_step=output_message_step),
        ControlFlowEdge(source_step=output_message_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            ask_user_for_text_step, InputMessageStep.USER_PROVIDED_INPUT, execute_tool_step, "text"
        ),
        DataFlowEdge(
            ask_user_for_text_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            output_message_step,
            "input_text",
        ),
        DataFlowEdge(
            execute_tool_step, ToolExecutionStep.TOOL_OUTPUT, output_message_step, "num_characters"
        ),
        DataFlowEdge(
            ask_user_for_text_step, InputMessageStep.USER_PROVIDED_INPUT, execute_tool_step, "text"
        ),
        DataFlowEdge(
            ask_user_for_text_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            output_message_step,
            "input_text",
        ),
        DataFlowEdge(
            execute_tool_step, ToolExecutionStep.TOOL_OUTPUT, output_message_step, "num_characters"
        ),
    ],
)
# We can serialize the flow as before
serialized_flow = serialize(flow)

# %%[markdown]
## Complex Flow Deserialization

# %%
from wayflowcore.serialization import autodeserialize
from wayflowcore.serialization.context import DeserializationContext

serialized_flow = """
_component_type: Flow
_referenced_objects:
  controlflowedge/4395505584:
    destination_step:
      $ref: toolexecutionstep/4395515664
    source_branch: next
    source_step:
      $ref: inputmessagestep/4395511296
  controlflowedge/4395506928:
    destination_step:
      $ref: outputmessagestep/4395511584
    source_branch: next
    source_step:
      $ref: toolexecutionstep/4395515664
  controlflowedge/4395514320:
    destination_step: null
    source_branch: next
    source_step:
      $ref: outputmessagestep/4395511584
  controlflowedge/4395514656:
    destination_step:
      $ref: inputmessagestep/4395511296
    source_branch: next
    source_step:
      $ref: startstep/4395515424
  dataflowedge/4395503760:
    destination_input: num_characters
    destination_step:
      $ref: outputmessagestep/4395511584
    source_output: tool_output
    source_step:
      $ref: toolexecutionstep/4395515664
  dataflowedge/4395510192:
    destination_input: input_text
    destination_step:
      $ref: outputmessagestep/4395511584
    source_output: user_provided_input
    source_step:
      $ref: inputmessagestep/4395511296
  dataflowedge/4395514032:
    destination_input: text
    destination_step:
      $ref: toolexecutionstep/4395515664
    source_output: user_provided_input
    source_step:
      $ref: inputmessagestep/4395511296
  inputmessagestep/4395511296:
    _component_type: Step
    input_descriptors: []
    input_mapping: {}
    output_descriptors:
    - $ref: stringproperty/4395512400
    output_mapping: {}
    step_args:
      input_descriptors: []
      input_mapping: {}
      llm: null
      message_template: Please enter the text to count the number of characters of
      output_descriptors:
      - _component_type: Property
        description: the input value provided by the user
        title: user_provided_input
        type: string
      output_mapping: {}
      rephrase: false
    step_cls: InputMessageStep
  outputmessagestep/4395511584:
    _component_type: Step
    input_descriptors:
    - $ref: stringproperty/4395506880
    - $ref: stringproperty/4395510000
    input_mapping: {}
    output_descriptors:
    - $ref: stringproperty/4395508896
    output_mapping: {}
    step_args:
      input_descriptors:
      - _component_type: Property
        description: '"input_text" input variable for the template'
        title: input_text
        type: string
      - _component_type: Property
        description: '"num_characters" input variable for the template'
        title: num_characters
        type: string
      input_mapping: {}
      llm: null
      message_template: 'There are {{num_characters}} characters in the following
        text:

        {{input_text}}'
      message_type: AGENT
      output_descriptors:
      - _component_type: Property
        description: the message added to the messages list
        title: output_message
        type: string
      output_mapping: {}
      rephrase: false
    step_cls: OutputMessageStep
  servertool/4401253344:
    __metadata_info__: {}
    _component_type: Tool
    description: Count the number of characters in the given text
    name: count_characters
    output:
      type: string
    parameters:
      text:
        description: Text for which want compute the number of characters
        title: Text
        type: string
    tool_type: server
  startstep/4395515424:
    _component_type: Step
    input_descriptors: []
    input_mapping: {}
    output_descriptors: []
    output_mapping: {}
    step_args:
      input_descriptors: []
      input_mapping: {}
      output_descriptors: []
      output_mapping: {}
    step_cls: StartStep
  stringproperty/4395506160:
    _component_type: Property
    title: tool_output
    type: string
  stringproperty/4395506208:
    _component_type: Property
    description: Text for which want compute the number of characters
    title: text
    type: string
  stringproperty/4395506880:
    _component_type: Property
    description: '"input_text" input variable for the template'
    title: input_text
    type: string
  stringproperty/4395508896:
    _component_type: Property
    description: the message added to the messages list
    title: output_message
    type: string
  stringproperty/4395510000:
    _component_type: Property
    description: '"num_characters" input variable for the template'
    title: num_characters
    type: string
  stringproperty/4395512400:
    _component_type: Property
    description: the input value provided by the user
    title: user_provided_input
    type: string
  toolexecutionstep/4395515664:
    _component_type: Step
    input_descriptors:
    - $ref: stringproperty/4395506208
    input_mapping: {}
    output_descriptors:
    - $ref: stringproperty/4395506160
    output_mapping: {}
    step_args:
      input_descriptors:
      - _component_type: Property
        description: Text for which want compute the number of characters
        title: text
        type: string
      input_mapping: {}
      output_descriptors:
      - _component_type: Property
        title: tool_output
        type: string
      output_mapping: {}
      raise_exceptions: false
      tool:
        $ref: servertool/4401253344
    step_cls: ToolExecutionStep
begin_step_name: __StartStep__
control_flow_edges:
- $ref: controlflowedge/4395505584
- $ref: controlflowedge/4395506928
- $ref: controlflowedge/4395514320
- $ref: controlflowedge/4395514656
data_flow_edges:
- $ref: dataflowedge/4395514032
- $ref: dataflowedge/4395510192
- $ref: dataflowedge/4395503760
end_steps:
- null
steps:
  __StartStep__:
    $ref: startstep/4395515424
  ask_user_for_text_step:
    $ref: inputmessagestep/4395511296
  execute_tool_step:
    $ref: toolexecutionstep/4395515664
  output_message_step:
    $ref: outputmessagestep/4395511584
variables: []
""".strip()

deserialization_context = DeserializationContext()
deserialization_context.registered_tools[count_characters.name] = count_characters
deserialized_flow: Flow = autodeserialize(serialized_flow, deserialization_context)

# %%[markdown]
## Complex Agent Creation

# %%
from wayflowcore.tools import tool

# Tool
@tool
def count_characters(
    text: Annotated[str, "Text for which want compute the number of characters"],
) -> str:
    """Count the number of characters in the given text"""
    return str(len(text))

agent = Agent(
    llm=llm,
    tools=[count_characters],
    custom_instruction="You are a helpful assistant, please answer user requests",
)
serialized_agent = serialize(agent)

# %%[markdown]
## Complex Agent Deserialization

# %%
from wayflowcore.serialization import autodeserialize
from wayflowcore.serialization.context import DeserializationContext

serialized_agent = """
_component_type: Agent
_referenced_objects:
  servertool/4443551104:
    __metadata_info__: {}
    _component_type: Tool
    description: Count the number of characters in the given text
    name: count_characters
    output:
      type: string
    parameters:
      text:
        description: Text for which want compute the number of characters
        title: Text
        type: string
    tool_type: server
  vllmmodel/4426025136:
    _component_type: LlmModel
    generation_config: null
    host_port: LLAMA70BV33_API_URL
    model_id: LLAMA70B_MODEL_ID
    model_type: vllm
agents: []
caller_input_mode: always
can_finish_conversation: false
context_providers: []
custom_instruction: You are a helpful assistant, please answer user requests
flows: []
initial_message: Hi! How can I help you?
llm:
  $ref: vllmmodel/4426025136
max_iterations: 10
outputs: null
tools:
- $ref: servertool/4443551104
""".strip()

deserialization_context = DeserializationContext()
deserialization_context.registered_tools[count_characters.name] = count_characters
deserialized_agent: Agent = autodeserialize(serialized_agent, deserialization_context)

# %%[markdown]
## Export Config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

config_flow = AgentSpecExporter().to_json(flow)
config_agent = AgentSpecExporter().to_json(agent)

# %%[markdown]
## Load Agent Spec Config

# %%
from wayflowcore.agentspec import AgentSpecLoader

new_flow = AgentSpecLoader(tool_registry={"count_characters": count_characters}).load_json(
    config_flow
)
new_agent = AgentSpecLoader(tool_registry={"count_characters": count_characters}).load_json(
    config_agent
)
```
