<a id="top-howtovariable"></a>

# How to Use Variables for Shared State in Flows![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Variable how-to script](../end_to_end_code_examples/howto_variable.py)

#### Prerequisites
This guide assumes familiarity with [Flows](../tutorials/basic_flow.md)

When building Flows, you may need a way to preserve information as it moves from one step to another.
WayFlow provides this through [Variable](../api/variables.md#variable), which serves as the flow’s state — a place where values can be stored, accessed, and updated throughout execution.

Why to use Variable?

- **Shared state**: Holds data that multiple steps can share.
- **Intermediate results**: Store partial results and reuse them later.
- **Simpler data flow**: Avoid passing outputs between every step, persist them as state using Variable.

This guide will show you how to:

- Define a [Variable](../api/variables.md#variable) in a Flow.
- Read its value with [VariableReadStep](../api/flows.md#variablereadstep).
- Write to it with [VariableWriteStep](../api/flows.md#variablewritestep).

In this guide, you will see a simple example including defining a `Variable` that stores a list of user feedback,
using `VariableWriteStep` to insert new feedback into the list, and
using `VariableReadStep` to read all collected feedback.

## Define a Variable

To define a variable, you need to define it with a name, type and optionally, a default value.
The type of variable determines the kind of data it can hold and is defined using `Property`.
In this case, our `feedback_variable` has the type of `ListProperty` and the `item_type` of `StringProperty`.

```python
from wayflowcore.variable import Variable
from wayflowcore.property import ListProperty, StringProperty

feedback_variable = Variable(
    name="user_feedback",
    type=ListProperty(item_type=StringProperty()),
    description="list of user feedback",
    default_value=[],
)
```

**API Reference:** [Variable](../api/variables.md#variable) | [Property](../api/flows.md#property)

## Define Flow Steps

We will define a simple flow including the following steps.

```python
from wayflowcore.steps import StartStep, OutputMessageStep, VariableReadStep, VariableWriteStep
from wayflowcore.property import StringProperty

FEEDBACK_1 = "feedback_1"
FEEDBACK_2 = "feedback_2"

start_step = StartStep(
    name="start_step",
    input_descriptors={StringProperty(FEEDBACK_1), StringProperty(FEEDBACK_2)},
)

write_feedback_1 = VariableWriteStep(
    name="write_step_1",
    variable=feedback_variable,
    operation="insert",
)

write_feedback_2 = VariableWriteStep(
    name="write_step_2",
    variable=feedback_variable,
    operation="insert",
)

read_feedback = VariableReadStep(variable=feedback_variable, name="read_step")

output_step = OutputMessageStep("Collected feedback: {{ feedback }}", name="output_step")
```

For simplicity, we pass initial feedback to the `start_step`, which then routes values to `write_feedback_1` and `write_feedback_2`.
In practice, those inputs could come from other steps (e.g. [ToolExecutionStep](../api/flows.md#toolexecutionstep)).

The [VariableWriteStep](../api/flows.md#variablewritestep) requires the `variable` that it writes to. It also accepts the following options of write operation:

- `VariableWriteOperation.OVERWRITE` (or `'overwrite'`) works on any type of variable to replace its value with the incoming value.
- `VariableWriteOperation.MERGE` (or `'merge'`) updates a `Variable` of type dict (resp. list),
- `VariableWriteOperation.INSERT` (or `'insert'`) operation can be used to append a single element at the end of a list.

Here, we choose `insert` as we want to append new user feedback to the our list.

## Define a Flow with Variable

Now we connect everything into a flow: two write steps add feedback, and a read step collects it all for output.

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow

flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(start_step, write_feedback_1),
        ControlFlowEdge(write_feedback_1, write_feedback_2),
        ControlFlowEdge(write_feedback_2, read_feedback),
        ControlFlowEdge(read_feedback, output_step),
        ControlFlowEdge(output_step, None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, FEEDBACK_1, write_feedback_1, VariableWriteStep.VALUE),
        DataFlowEdge(start_step, FEEDBACK_2, write_feedback_2, VariableWriteStep.VALUE),
        DataFlowEdge(read_feedback, VariableReadStep.VALUE, output_step, "feedback"),
    ],
    variables=[feedback_variable],
)
```

The `VariableWriteStep` has a single input descriptor `VariableWriteStep.VALUE` - the value to write to the variable it holds.
Similarly, the `VariableReadStep` has a single output descriptor `VariableReadStep.VALUE`- the value it reads from the variable it holds.

Remember to include your defined variables in the Flow’s `variables` parameter.

## Execute the Flow

Finally, run the flow:

```python
conv = flow.start_conversation(
    inputs={
        FEEDBACK_1: "Very good!",
        FEEDBACK_2: "Need to improve!",
    }
)
conv.execute()

result = conv.get_last_message().content
print(result)
# >>> Collected feedback: ["Very good!", "Need to improve!"]
```

## Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_yaml(flow)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

YAML

```yaml
component_type: Flow
id: 5b86a3b4-22b1-442a-91f9-569a938d4789
name: flow_96bb6cb7
description: ''
metadata:
  __metadata_info__: {}
inputs:
- type: string
  title: feedback_2
- type: string
  title: feedback_1
outputs:
- description: list of user feedback
  type: array
  items:
    type: string
  title: value
  default: []
- description: the message added to the messages list
  type: string
  title: output_message
start_node:
  $component_ref: cfcab079-4674-4a0a-bc7c-f1128e852ca0
nodes:
- $component_ref: cfcab079-4674-4a0a-bc7c-f1128e852ca0
- $component_ref: ded88ecb-17c9-4578-ae45-5c80b01c34ad
- $component_ref: febaa510-2875-444a-ae51-ea39fbc708f7
- $component_ref: f592ae1a-682f-45e0-849f-579eeb803e04
- $component_ref: a6751ff9-5940-4ff0-90b4-12c7a15b8b87
- $component_ref: 83ea975c-1b64-46f2-9dfb-a12ee1ee8d90
state:
- description: list of user feedback
  type: array
  items:
    type: string
  title: user_feedback
  default: []
control_flow_connections:
- component_type: ControlFlowEdge
  id: 9340d618-bd88-415b-9f19-b4fed93f5896
  name: step_1a0d93db_to_step_709c5a35_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: cfcab079-4674-4a0a-bc7c-f1128e852ca0
  from_branch: null
  to_node:
    $component_ref: ded88ecb-17c9-4578-ae45-5c80b01c34ad
- component_type: ControlFlowEdge
  id: eca38c7f-f5cb-4e86-86fc-80d0810e2b14
  name: step_709c5a35_to_step_15af65a5_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: ded88ecb-17c9-4578-ae45-5c80b01c34ad
  from_branch: null
  to_node:
    $component_ref: febaa510-2875-444a-ae51-ea39fbc708f7
- component_type: ControlFlowEdge
  id: 135cc8b2-b2a1-480c-ac28-2b9226658efd
  name: step_15af65a5_to_step_a8581940_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: febaa510-2875-444a-ae51-ea39fbc708f7
  from_branch: null
  to_node:
    $component_ref: f592ae1a-682f-45e0-849f-579eeb803e04
- component_type: ControlFlowEdge
  id: e8c3990a-45e2-456a-bf40-758efdccb318
  name: step_a8581940_to_step_284a4a1d_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: f592ae1a-682f-45e0-849f-579eeb803e04
  from_branch: null
  to_node:
    $component_ref: a6751ff9-5940-4ff0-90b4-12c7a15b8b87
- component_type: ControlFlowEdge
  id: 5315ad19-52b1-44f1-bee8-f296e93d4b67
  name: step_284a4a1d_to_None End node_control_flow_edge
  description: null
  metadata: {}
  from_node:
    $component_ref: a6751ff9-5940-4ff0-90b4-12c7a15b8b87
  from_branch: null
  to_node:
    $component_ref: 83ea975c-1b64-46f2-9dfb-a12ee1ee8d90
data_flow_connections:
- component_type: DataFlowEdge
  id: cb51c4b1-0aab-4928-9d19-6bc098de4354
  name: step_1a0d93db_feedback_1_to_step_709c5a35_value_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: cfcab079-4674-4a0a-bc7c-f1128e852ca0
  source_output: feedback_1
  destination_node:
    $component_ref: ded88ecb-17c9-4578-ae45-5c80b01c34ad
  destination_input: value
- component_type: DataFlowEdge
  id: 9a794227-085d-4c79-b1f5-cf0d66e048b9
  name: step_1a0d93db_feedback_2_to_step_15af65a5_value_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: cfcab079-4674-4a0a-bc7c-f1128e852ca0
  source_output: feedback_2
  destination_node:
    $component_ref: febaa510-2875-444a-ae51-ea39fbc708f7
  destination_input: value
- component_type: DataFlowEdge
  id: f6ea2e6d-d1c8-411a-ae78-13abba142591
  name: step_a8581940_value_to_step_284a4a1d_feedback_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: f592ae1a-682f-45e0-849f-579eeb803e04
  source_output: value
  destination_node:
    $component_ref: a6751ff9-5940-4ff0-90b4-12c7a15b8b87
  destination_input: feedback
- component_type: DataFlowEdge
  id: 8db068f7-f246-4e8a-bf84-9f6b141aca54
  name: step_a8581940_value_to_None End node_value_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: f592ae1a-682f-45e0-849f-579eeb803e04
  source_output: value
  destination_node:
    $component_ref: 83ea975c-1b64-46f2-9dfb-a12ee1ee8d90
  destination_input: value
- component_type: DataFlowEdge
  id: 6c3ea770-a8b9-4bfb-95e7-aee1007d0195
  name: step_284a4a1d_output_message_to_None End node_output_message_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: a6751ff9-5940-4ff0-90b4-12c7a15b8b87
  source_output: output_message
  destination_node:
    $component_ref: 83ea975c-1b64-46f2-9dfb-a12ee1ee8d90
  destination_input: output_message
$referenced_components:
  cfcab079-4674-4a0a-bc7c-f1128e852ca0:
    component_type: StartNode
    id: cfcab079-4674-4a0a-bc7c-f1128e852ca0
    name: step_1a0d93db
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: string
      title: feedback_2
    - type: string
      title: feedback_1
    outputs:
    - type: string
      title: feedback_2
    - type: string
      title: feedback_1
    branches:
    - next
  ded88ecb-17c9-4578-ae45-5c80b01c34ad:
    component_type: PluginWriteVariableNode
    id: ded88ecb-17c9-4578-ae45-5c80b01c34ad
    name: step_709c5a35
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: list of user feedback (single element)
      type: string
      title: value
    outputs: []
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    variable:
      description: list of user feedback
      type: array
      items:
        type: string
      title: user_feedback
      default: []
    operation: insert
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.3.0.dev2
  febaa510-2875-444a-ae51-ea39fbc708f7:
    component_type: PluginWriteVariableNode
    id: febaa510-2875-444a-ae51-ea39fbc708f7
    name: step_15af65a5
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: list of user feedback (single element)
      type: string
      title: value
    outputs: []
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    variable:
      description: list of user feedback
      type: array
      items:
        type: string
      title: user_feedback
      default: []
    operation: insert
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.3.0.dev2
  f592ae1a-682f-45e0-849f-579eeb803e04:
    component_type: PluginReadVariableNode
    id: f592ae1a-682f-45e0-849f-579eeb803e04
    name: step_a8581940
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs:
    - description: list of user feedback
      type: array
      items:
        type: string
      title: value
      default: []
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    variable:
      description: list of user feedback
      type: array
      items:
        type: string
      title: user_feedback
      default: []
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.3.0.dev2
  a6751ff9-5940-4ff0-90b4-12c7a15b8b87:
    component_type: PluginOutputMessageNode
    id: a6751ff9-5940-4ff0-90b4-12c7a15b8b87
    name: step_284a4a1d
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: '"feedback" input variable for the template'
      type: string
      title: feedback
    outputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    message_template: 'Collected feedback: {{ feedback }}'
    message_type: AGENT
    rephrase: false
    llm_config: null
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.3.0.dev2
  83ea975c-1b64-46f2-9dfb-a12ee1ee8d90:
    component_type: EndNode
    id: 83ea975c-1b64-46f2-9dfb-a12ee1ee8d90
    name: None End node
    description: End node representing all transitions to None in the WayFlow flow
    metadata: {}
    inputs:
    - description: list of user feedback
      type: array
      items:
        type: string
      title: value
      default: []
    - description: the message added to the messages list
      type: string
      title: output_message
    outputs:
    - description: list of user feedback
      type: array
      items:
        type: string
      title: value
      default: []
    - description: the message added to the messages list
      type: string
      title: output_message
    branches: []
    branch_name: next
```

JSON

```json
{
    "$referenced_components": {
        "2ef3114a-3421-4a79-ac99-1ee83d04c735": {
            "branches": [
                "next"
            ],
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "25.3.0.dev2",
            "component_type": "PluginWriteVariableNode",
            "description": "",
            "id": "2ef3114a-3421-4a79-ac99-1ee83d04c735",
            "input_mapping": {},
            "inputs": [
                {
                    "description": "list of user feedback (single element)",
                    "title": "value",
                    "type": "string"
                }
            ],
            "metadata": {
                "__metadata_info__": {}
            },
            "name": "write_step_1",
            "operation": "insert",
            "output_mapping": {},
            "outputs": [],
            "variable": {
                "default": [],
                "description": "list of user feedback",
                "items": {
                    "type": "string"
                },
                "title": "user_feedback",
                "type": "array"
            }
        },
        "64a2de0a-2571-4f10-8b59-7b323b223873": {
            "branch_name": "next",
            "branches": [],
            "component_type": "EndNode",
            "description": "End node representing all transitions to None in the WayFlow flow",
            "id": "64a2de0a-2571-4f10-8b59-7b323b223873",
            "inputs": [
                {
                    "description": "the message added to the messages list",
                    "title": "output_message",
                    "type": "string"
                },
                {
                    "default": [],
                    "description": "list of user feedback",
                    "items": {
                        "type": "string"
                    },
                    "title": "value",
                    "type": "array"
                }
            ],
            "metadata": {},
            "name": "None End node",
            "outputs": [
                {
                    "description": "the message added to the messages list",
                    "title": "output_message",
                    "type": "string"
                },
                {
                    "default": [],
                    "description": "list of user feedback",
                    "items": {
                        "type": "string"
                    },
                    "title": "value",
                    "type": "array"
                }
            ]
        },
        "79c35cc6-f7e6-45da-80e3-8863d38003ab": {
            "branches": [
                "next"
            ],
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "25.3.0.dev2",
            "component_type": "PluginOutputMessageNode",
            "description": "",
            "id": "79c35cc6-f7e6-45da-80e3-8863d38003ab",
            "input_mapping": {},
            "inputs": [
                {
                    "description": "\"feedback\" input variable for the template",
                    "title": "feedback",
                    "type": "string"
                }
            ],
            "llm_config": null,
            "message_template": "Collected feedback: {{ feedback }}",
            "message_type": "AGENT",
            "metadata": {
                "__metadata_info__": {}
            },
            "name": "output_step",
            "output_mapping": {},
            "outputs": [
                {
                    "description": "the message added to the messages list",
                    "title": "output_message",
                    "type": "string"
                }
            ],
            "rephrase": false
        },
        "8546551f-4f9c-4e75-a60a-9a059404bfbf": {
            "branches": [
                "next"
            ],
            "component_type": "StartNode",
            "description": "",
            "id": "8546551f-4f9c-4e75-a60a-9a059404bfbf",
            "inputs": [
                {
                    "title": "feedback_2",
                    "type": "string"
                },
                {
                    "title": "feedback_1",
                    "type": "string"
                }
            ],
            "metadata": {
                "__metadata_info__": {}
            },
            "name": "start_step",
            "outputs": [
                {
                    "title": "feedback_2",
                    "type": "string"
                },
                {
                    "title": "feedback_1",
                    "type": "string"
                }
            ]
        },
        "b431983e-df59-40cd-8e41-83fbce628bdb": {
            "branches": [
                "next"
            ],
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "25.3.0.dev2",
            "component_type": "PluginReadVariableNode",
            "description": "",
            "id": "b431983e-df59-40cd-8e41-83fbce628bdb",
            "input_mapping": {},
            "inputs": [],
            "metadata": {
                "__metadata_info__": {}
            },
            "name": "read_step",
            "output_mapping": {},
            "outputs": [
                {
                    "default": [],
                    "description": "list of user feedback",
                    "items": {
                        "type": "string"
                    },
                    "title": "value",
                    "type": "array"
                }
            ],
            "variable": {
                "default": [],
                "description": "list of user feedback",
                "items": {
                    "type": "string"
                },
                "title": "user_feedback",
                "type": "array"
            }
        },
        "b876b461-2334-4ab3-b03b-6c0c0c5d35cb": {
            "branches": [
                "next"
            ],
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "25.3.0.dev2",
            "component_type": "PluginWriteVariableNode",
            "description": "",
            "id": "b876b461-2334-4ab3-b03b-6c0c0c5d35cb",
            "input_mapping": {},
            "inputs": [
                {
                    "description": "list of user feedback (single element)",
                    "title": "value",
                    "type": "string"
                }
            ],
            "metadata": {
                "__metadata_info__": {}
            },
            "name": "write_step_2",
            "operation": "insert",
            "output_mapping": {},
            "outputs": [],
            "variable": {
                "default": [],
                "description": "list of user feedback",
                "items": {
                    "type": "string"
                },
                "title": "user_feedback",
                "type": "array"
            }
        }
    },
    "component_type": "Flow",
    "control_flow_connections": [
        {
            "component_type": "ControlFlowEdge",
            "description": null,
            "from_branch": null,
            "from_node": {
                "$component_ref": "8546551f-4f9c-4e75-a60a-9a059404bfbf"
            },
            "id": "33311916-0bfa-4f50-80a6-a659f97337ad",
            "metadata": {
                "__metadata_info__": {}
            },
            "name": "start_step_to_write_step_1_control_flow_edge",
            "to_node": {
                "$component_ref": "2ef3114a-3421-4a79-ac99-1ee83d04c735"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "description": null,
            "from_branch": null,
            "from_node": {
                "$component_ref": "2ef3114a-3421-4a79-ac99-1ee83d04c735"
            },
            "id": "cd4b8a8c-a5e7-4288-aff5-f4ef5c082d6c",
            "metadata": {
                "__metadata_info__": {}
            },
            "name": "write_step_1_to_write_step_2_control_flow_edge",
            "to_node": {
                "$component_ref": "b876b461-2334-4ab3-b03b-6c0c0c5d35cb"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "description": null,
            "from_branch": null,
            "from_node": {
                "$component_ref": "b876b461-2334-4ab3-b03b-6c0c0c5d35cb"
            },
            "id": "be8df0e3-120a-4c3c-97e6-8c3af277627f",
            "metadata": {
                "__metadata_info__": {}
            },
            "name": "write_step_2_to_read_step_control_flow_edge",
            "to_node": {
                "$component_ref": "b431983e-df59-40cd-8e41-83fbce628bdb"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "description": null,
            "from_branch": null,
            "from_node": {
                "$component_ref": "b431983e-df59-40cd-8e41-83fbce628bdb"
            },
            "id": "98654d6c-db8c-4d94-8842-0cc9200f05a0",
            "metadata": {
                "__metadata_info__": {}
            },
            "name": "read_step_to_output_step_control_flow_edge",
            "to_node": {
                "$component_ref": "79c35cc6-f7e6-45da-80e3-8863d38003ab"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "description": null,
            "from_branch": null,
            "from_node": {
                "$component_ref": "79c35cc6-f7e6-45da-80e3-8863d38003ab"
            },
            "id": "eab26b31-86ec-4e9b-9d7d-24e9b009fb90",
            "metadata": {},
            "name": "output_step_to_None End node_control_flow_edge",
            "to_node": {
                "$component_ref": "64a2de0a-2571-4f10-8b59-7b323b223873"
            }
        }
    ],
    "data_flow_connections": [
        {
            "component_type": "DataFlowEdge",
            "description": null,
            "destination_input": "value",
            "destination_node": {
                "$component_ref": "2ef3114a-3421-4a79-ac99-1ee83d04c735"
            },
            "id": "5882a9f6-e363-46df-994c-3a9b00143dae",
            "metadata": {
                "__metadata_info__": {}
            },
            "name": "start_step_feedback_1_to_write_step_1_value_data_flow_edge",
            "source_node": {
                "$component_ref": "8546551f-4f9c-4e75-a60a-9a059404bfbf"
            },
            "source_output": "feedback_1"
        },
        {
            "component_type": "DataFlowEdge",
            "description": null,
            "destination_input": "value",
            "destination_node": {
                "$component_ref": "b876b461-2334-4ab3-b03b-6c0c0c5d35cb"
            },
            "id": "7d580306-9848-4d18-9c69-d5042946a52a",
            "metadata": {
                "__metadata_info__": {}
            },
            "name": "start_step_feedback_2_to_write_step_2_value_data_flow_edge",
            "source_node": {
                "$component_ref": "8546551f-4f9c-4e75-a60a-9a059404bfbf"
            },
            "source_output": "feedback_2"
        },
        {
            "component_type": "DataFlowEdge",
            "description": null,
            "destination_input": "feedback",
            "destination_node": {
                "$component_ref": "79c35cc6-f7e6-45da-80e3-8863d38003ab"
            },
            "id": "be793090-4a11-47b3-b392-0508de4c736d",
            "metadata": {
                "__metadata_info__": {}
            },
            "name": "read_step_value_to_output_step_feedback_data_flow_edge",
            "source_node": {
                "$component_ref": "b431983e-df59-40cd-8e41-83fbce628bdb"
            },
            "source_output": "value"
        },
        {
            "component_type": "DataFlowEdge",
            "description": null,
            "destination_input": "output_message",
            "destination_node": {
                "$component_ref": "64a2de0a-2571-4f10-8b59-7b323b223873"
            },
            "id": "7ca289a8-6270-4527-b8ac-b5c7090acaf1",
            "metadata": {},
            "name": "output_step_output_message_to_None End node_output_message_data_flow_edge",
            "source_node": {
                "$component_ref": "79c35cc6-f7e6-45da-80e3-8863d38003ab"
            },
            "source_output": "output_message"
        },
        {
            "component_type": "DataFlowEdge",
            "description": null,
            "destination_input": "value",
            "destination_node": {
                "$component_ref": "64a2de0a-2571-4f10-8b59-7b323b223873"
            },
            "id": "1567f968-75f0-4e72-b837-a24dd9f658a5",
            "metadata": {},
            "name": "read_step_value_to_None End node_value_data_flow_edge",
            "source_node": {
                "$component_ref": "b431983e-df59-40cd-8e41-83fbce628bdb"
            },
            "source_output": "value"
        }
    ],
    "description": "",
    "id": "817bf187-2abd-4153-a784-923bc8c5aa5c",
    "inputs": [
        {
            "title": "feedback_2",
            "type": "string"
        },
        {
            "title": "feedback_1",
            "type": "string"
        }
    ],
    "metadata": {
        "__metadata_info__": {}
    },
    "name": "flow_5c34cdba__auto",
    "nodes": [
        {
            "$component_ref": "8546551f-4f9c-4e75-a60a-9a059404bfbf"
        },
        {
            "$component_ref": "2ef3114a-3421-4a79-ac99-1ee83d04c735"
        },
        {
            "$component_ref": "b876b461-2334-4ab3-b03b-6c0c0c5d35cb"
        },
        {
            "$component_ref": "b431983e-df59-40cd-8e41-83fbce628bdb"
        },
        {
            "$component_ref": "79c35cc6-f7e6-45da-80e3-8863d38003ab"
        },
        {
            "$component_ref": "64a2de0a-2571-4f10-8b59-7b323b223873"
        }
    ],
    "outputs": [
        {
            "description": "the message added to the messages list",
            "title": "output_message",
            "type": "string"
        },
        {
            "default": [],
            "description": "list of user feedback",
            "items": {
                "type": "string"
            },
            "title": "value",
            "type": "array"
        }
    ],
    "start_node": {
        "$component_ref": "8546551f-4f9c-4e75-a60a-9a059404bfbf"
    },
    "state": [
        {
            "default": [],
            "description": "list of user feedback",
            "items": {
                "type": "string"
            },
            "title": "user_feedback",
            "type": "array"
        }
    ]
}
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

assistant: Flow = AgentSpecLoader().load_yaml(serialized_assistant)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `PluginReadVariableNode`
- `PluginWriteVariableNode`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Next steps

Now that you have learned how to use Variables in Flows, you may proceed to [FlowContextProvider](../api/contextproviders.md#flowcontextprovider) to learn how to provide context for flow execution.

## Full code

Click on the card at the [top of this page](#top-howtovariable) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Use Variables for Shared State in Flows
# -------------------------------------------------------------

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
# python howto_variable.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Define a Variable

# %%
from wayflowcore.variable import Variable
from wayflowcore.property import ListProperty, StringProperty

feedback_variable = Variable(
    name="user_feedback",
    type=ListProperty(item_type=StringProperty()),
    description="list of user feedback",
    default_value=[],
)


# %%[markdown]
## Define Flow Steps

# %%
from wayflowcore.steps import StartStep, OutputMessageStep, VariableReadStep, VariableWriteStep
from wayflowcore.property import StringProperty

FEEDBACK_1 = "feedback_1"
FEEDBACK_2 = "feedback_2"

start_step = StartStep(
    name="start_step",
    input_descriptors={StringProperty(FEEDBACK_1), StringProperty(FEEDBACK_2)},
)

write_feedback_1 = VariableWriteStep(
    name="write_step_1",
    variable=feedback_variable,
    operation="insert",
)

write_feedback_2 = VariableWriteStep(
    name="write_step_2",
    variable=feedback_variable,
    operation="insert",
)

read_feedback = VariableReadStep(variable=feedback_variable, name="read_step")

output_step = OutputMessageStep("Collected feedback: {{ feedback }}", name="output_step")


# %%[markdown]
## Define a Flow with variable

# %%
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow

flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(start_step, write_feedback_1),
        ControlFlowEdge(write_feedback_1, write_feedback_2),
        ControlFlowEdge(write_feedback_2, read_feedback),
        ControlFlowEdge(read_feedback, output_step),
        ControlFlowEdge(output_step, None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, FEEDBACK_1, write_feedback_1, VariableWriteStep.VALUE),
        DataFlowEdge(start_step, FEEDBACK_2, write_feedback_2, VariableWriteStep.VALUE),
        DataFlowEdge(read_feedback, VariableReadStep.VALUE, output_step, "feedback"),
    ],
    variables=[feedback_variable],
)


# %%[markdown]
## Execute flow

# %%
conv = flow.start_conversation(
    inputs={
        FEEDBACK_1: "Very good!",
        FEEDBACK_2: "Need to improve!",
    }
)
conv.execute()

result = conv.get_last_message().content
print(result)
# >>> Collected feedback: ["Very good!", "Need to improve!"]


# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_yaml(flow)


# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

assistant: Flow = AgentSpecLoader().load_yaml(serialized_assistant)
```
