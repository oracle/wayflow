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
- Read and write its value with [VariableStep](../api/flows.md#variablestep).

In this guide, you will see a simple example including defining a `Variable` that stores a list of user feedback,
using `VariableStep` to insert new feedback into the list and read all collected feedback.

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
from wayflowcore.steps import StartStep, OutputMessageStep, VariableStep
from wayflowcore.property import StringProperty
from wayflowcore.variable import VariableWriteOperation

FEEDBACK_1 = "feedback_1"
FEEDBACK_2 = "feedback_2"

start_step = StartStep(
    name="start_step",
    input_descriptors=[StringProperty(FEEDBACK_1), StringProperty(FEEDBACK_2)],
)

write_feedback_1 = VariableStep(
    name="write_var_step_1",
    write_variables=[feedback_variable],
    write_operations=VariableWriteOperation.INSERT,
)

write_feedback_2 = VariableStep(
    name="write_var_step_2",
    write_variables=[feedback_variable],
    write_operations=VariableWriteOperation.INSERT,
)

read_feedback = VariableStep(
    name="read_var_step",
    read_variables=[feedback_variable],
)

output_step = OutputMessageStep("Collected feedback: {{ feedback }}", name="output_step")
```

For simplicity, we pass initial feedback to the `start_step`, which then routes values to `write_feedback_1` and `write_feedback_2`.
In practice, those inputs could come from other steps (e.g. [ToolExecutionStep](../api/flows.md#toolexecutionstep)).

When updating some variables, the [VariableStep](../api/flows.md#variablestep) requires the `write_variables` that it writes to. It also accepts the following options of write operations:

- `VariableWriteOperation.OVERWRITE` (or `'overwrite'`) works on any type of variable to replace its value with the incoming value.
- `VariableWriteOperation.MERGE` (or `'merge'`) updates a `Variable` of type dict (resp. list),
- `VariableWriteOperation.INSERT` (or `'insert'`) operation can be used to append a single element at the end of a list.

Here, we choose `insert` as we want to append new user feedback to the our list.

The `VariableStep` can also read one or more variables, via the `read_variables` parameter.

The `VariableStep` can perform both writes and reads of multiple variables at the same time.
If you configure a step to both write and read a given variable, the value will be written first, and the updated variable will be used for the read operation.

In general, the input and output descriptors of the `VariableStep` correspond to the properties referenced by the variables being written and/or read in this step, respectively.
For example, if the step is configured to overwrite a `Variable(name="manager", type=DictProperty())`, to extend a `Variable(name="employees", type=ListProperty(item_type=DictProperty("employee"))`, and to read back the updated value of the employee list, the step would have the following descriptors:

* An input descriptor `DictProperty("manager")`, to overwrite the full manager variable;
* An input descriptor `DictProperty("employee")`, since the extend operation expects a single item of the employees list;
* An output descriptor `ListProperty("employees", item_type=DictProperty("employee"))`

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
        DataFlowEdge(start_step, FEEDBACK_1, write_feedback_1, feedback_variable.name),
        DataFlowEdge(start_step, FEEDBACK_2, write_feedback_2, feedback_variable.name),
        DataFlowEdge(read_feedback, feedback_variable.name, output_step, "feedback"),
    ],
    variables=[feedback_variable],
)
```

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
component_type: ExtendedFlow
id: b41482ac-31b3-4117-805e-cb34931e9971
name: flow_3fc1343f__auto
description: ''
metadata:
  __metadata_info__: {}
inputs:
- type: string
  title: feedback_1
- type: string
  title: feedback_2
outputs:
- description: list of user feedback
  type: array
  items:
    type: string
  title: user_feedback
  default: []
- description: the message added to the messages list
  type: string
  title: output_message
start_node:
  $component_ref: 57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b
nodes:
- $component_ref: 57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b
- $component_ref: be27d2dc-0185-41b0-bbbc-31060306b34c
- $component_ref: 4991b600-4fe1-4e46-82f8-6d0764989291
- $component_ref: e8e2df93-abc9-492a-9c0b-92c4a68895b9
- $component_ref: bd2331f9-c336-446d-b6e8-5c4365e4327b
- $component_ref: 9834131e-83bf-4927-81bc-89965824271f
control_flow_connections:
- component_type: ControlFlowEdge
  id: c98164c9-eeaa-42da-9f42-c8e574b34c4a
  name: start_step_to_write_var_step_1_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b
  from_branch: null
  to_node:
    $component_ref: be27d2dc-0185-41b0-bbbc-31060306b34c
- component_type: ControlFlowEdge
  id: 95b902ad-6e56-4587-9e92-d725c955f5b1
  name: write_var_step_1_to_write_var_step_2_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: be27d2dc-0185-41b0-bbbc-31060306b34c
  from_branch: null
  to_node:
    $component_ref: 4991b600-4fe1-4e46-82f8-6d0764989291
- component_type: ControlFlowEdge
  id: 57bafe45-a33c-44bc-a21a-51205da9a8d8
  name: write_var_step_2_to_read_var_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 4991b600-4fe1-4e46-82f8-6d0764989291
  from_branch: null
  to_node:
    $component_ref: e8e2df93-abc9-492a-9c0b-92c4a68895b9
- component_type: ControlFlowEdge
  id: 621e214c-4048-409d-920d-7af0a09dd46a
  name: read_var_step_to_output_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: e8e2df93-abc9-492a-9c0b-92c4a68895b9
  from_branch: null
  to_node:
    $component_ref: bd2331f9-c336-446d-b6e8-5c4365e4327b
- component_type: ControlFlowEdge
  id: 4325173c-575c-41d1-9222-8f263267ec93
  name: output_step_to_None End node_control_flow_edge
  description: null
  metadata: {}
  from_node:
    $component_ref: bd2331f9-c336-446d-b6e8-5c4365e4327b
  from_branch: null
  to_node:
    $component_ref: 9834131e-83bf-4927-81bc-89965824271f
data_flow_connections:
- component_type: DataFlowEdge
  id: 29904c9b-8ff3-410c-a484-d95a9f4f9248
  name: start_step_feedback_1_to_write_var_step_1_user_feedback_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b
  source_output: feedback_1
  destination_node:
    $component_ref: be27d2dc-0185-41b0-bbbc-31060306b34c
  destination_input: user_feedback
- component_type: DataFlowEdge
  id: 5440b896-e11b-48b3-ae83-4e0832f87bc6
  name: start_step_feedback_2_to_write_var_step_2_user_feedback_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b
  source_output: feedback_2
  destination_node:
    $component_ref: 4991b600-4fe1-4e46-82f8-6d0764989291
  destination_input: user_feedback
- component_type: DataFlowEdge
  id: ff59cde4-e95d-4caf-b8b3-0e9097013bb2
  name: read_var_step_user_feedback_to_output_step_feedback_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: e8e2df93-abc9-492a-9c0b-92c4a68895b9
  source_output: user_feedback
  destination_node:
    $component_ref: bd2331f9-c336-446d-b6e8-5c4365e4327b
  destination_input: feedback
- component_type: DataFlowEdge
  id: f003fdad-8e7c-4d24-914f-1f30fa393f0d
  name: read_var_step_user_feedback_to_None End node_user_feedback_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: e8e2df93-abc9-492a-9c0b-92c4a68895b9
  source_output: user_feedback
  destination_node:
    $component_ref: 9834131e-83bf-4927-81bc-89965824271f
  destination_input: user_feedback
- component_type: DataFlowEdge
  id: 200b7819-9b5a-449e-9ce0-dbf1c78d8430
  name: output_step_output_message_to_None End node_output_message_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: bd2331f9-c336-446d-b6e8-5c4365e4327b
  source_output: output_message
  destination_node:
    $component_ref: 9834131e-83bf-4927-81bc-89965824271f
  destination_input: output_message
context_providers: []
state:
- description: list of user feedback
  type: array
  items:
    type: string
  title: user_feedback
  default: []
component_plugin_name: FlowPlugin
component_plugin_version: 26.1.0.dev4
$referenced_components:
  57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b:
    component_type: StartNode
    id: 57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b
    name: start_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: string
      title: feedback_1
    - type: string
      title: feedback_2
    outputs:
    - type: string
      title: feedback_1
    - type: string
      title: feedback_2
    branches:
    - next
  be27d2dc-0185-41b0-bbbc-31060306b34c:
    component_type: PluginVariableNode
    id: be27d2dc-0185-41b0-bbbc-31060306b34c
    name: write_var_step_1
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: list of user feedback (single element)
      type: string
      title: user_feedback
    outputs: []
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    write_variables:
    - description: list of user feedback
      type: array
      items:
        type: string
      title: user_feedback
      default: []
    read_variables: []
    write_operations:
      user_feedback: insert
    component_plugin_name: NodesPlugin
    component_plugin_version: 26.1.0.dev4
  4991b600-4fe1-4e46-82f8-6d0764989291:
    component_type: PluginVariableNode
    id: 4991b600-4fe1-4e46-82f8-6d0764989291
    name: write_var_step_2
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: list of user feedback (single element)
      type: string
      title: user_feedback
    outputs: []
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    write_variables:
    - description: list of user feedback
      type: array
      items:
        type: string
      title: user_feedback
      default: []
    read_variables: []
    write_operations:
      user_feedback: insert
    component_plugin_name: NodesPlugin
    component_plugin_version: 26.1.0.dev4
  e8e2df93-abc9-492a-9c0b-92c4a68895b9:
    component_type: PluginVariableNode
    id: e8e2df93-abc9-492a-9c0b-92c4a68895b9
    name: read_var_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs:
    - description: list of user feedback
      type: array
      items:
        type: string
      title: user_feedback
      default: []
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    write_variables: []
    read_variables:
    - description: list of user feedback
      type: array
      items:
        type: string
      title: user_feedback
      default: []
    write_operations: {}
    component_plugin_name: NodesPlugin
    component_plugin_version: 26.1.0.dev4
  bd2331f9-c336-446d-b6e8-5c4365e4327b:
    component_type: PluginOutputMessageNode
    id: bd2331f9-c336-446d-b6e8-5c4365e4327b
    name: output_step
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
    message: 'Collected feedback: {{ feedback }}'
    input_mapping: {}
    output_mapping: {}
    message_type: AGENT
    rephrase: false
    llm_config: null
    expose_message_as_output: true
    component_plugin_name: NodesPlugin
    component_plugin_version: 26.1.0.dev4
  9834131e-83bf-4927-81bc-89965824271f:
    component_type: EndNode
    id: 9834131e-83bf-4927-81bc-89965824271f
    name: None End node
    description: End node representing all transitions to None in the WayFlow flow
    metadata: {}
    inputs:
    - description: list of user feedback
      type: array
      items:
        type: string
      title: user_feedback
      default: []
    - description: the message added to the messages list
      type: string
      title: output_message
    outputs:
    - description: list of user feedback
      type: array
      items:
        type: string
      title: user_feedback
      default: []
    - description: the message added to the messages list
      type: string
      title: output_message
    branches: []
    branch_name: next
agentspec_version: 25.4.2
```

JSON

```json
{
    "component_type": "ExtendedFlow",
    "id": "b41482ac-31b3-4117-805e-cb34931e9971",
    "name": "flow_3fc1343f__auto",
    "description": "",
    "metadata": {
        "__metadata_info__": {}
    },
    "inputs": [
        {
            "type": "string",
            "title": "feedback_1"
        },
        {
            "type": "string",
            "title": "feedback_2"
        }
    ],
    "outputs": [
        {
            "description": "list of user feedback",
            "type": "array",
            "items": {
                "type": "string"
            },
            "title": "user_feedback",
            "default": []
        },
        {
            "description": "the message added to the messages list",
            "type": "string",
            "title": "output_message"
        }
    ],
    "start_node": {
        "$component_ref": "57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b"
    },
    "nodes": [
        {
            "$component_ref": "57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b"
        },
        {
            "$component_ref": "be27d2dc-0185-41b0-bbbc-31060306b34c"
        },
        {
            "$component_ref": "4991b600-4fe1-4e46-82f8-6d0764989291"
        },
        {
            "$component_ref": "e8e2df93-abc9-492a-9c0b-92c4a68895b9"
        },
        {
            "$component_ref": "bd2331f9-c336-446d-b6e8-5c4365e4327b"
        },
        {
            "$component_ref": "e139d3c9-66ca-4e0e-afd5-af41c0bbffd0"
        }
    ],
    "control_flow_connections": [
        {
            "component_type": "ControlFlowEdge",
            "id": "c98164c9-eeaa-42da-9f42-c8e574b34c4a",
            "name": "start_step_to_write_var_step_1_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "be27d2dc-0185-41b0-bbbc-31060306b34c"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "95b902ad-6e56-4587-9e92-d725c955f5b1",
            "name": "write_var_step_1_to_write_var_step_2_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "be27d2dc-0185-41b0-bbbc-31060306b34c"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "4991b600-4fe1-4e46-82f8-6d0764989291"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "57bafe45-a33c-44bc-a21a-51205da9a8d8",
            "name": "write_var_step_2_to_read_var_step_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "4991b600-4fe1-4e46-82f8-6d0764989291"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "e8e2df93-abc9-492a-9c0b-92c4a68895b9"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "621e214c-4048-409d-920d-7af0a09dd46a",
            "name": "read_var_step_to_output_step_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "e8e2df93-abc9-492a-9c0b-92c4a68895b9"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "bd2331f9-c336-446d-b6e8-5c4365e4327b"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "6484068a-3369-48d9-bf23-5192b3a805c1",
            "name": "output_step_to_None End node_control_flow_edge",
            "description": null,
            "metadata": {},
            "from_node": {
                "$component_ref": "bd2331f9-c336-446d-b6e8-5c4365e4327b"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "e139d3c9-66ca-4e0e-afd5-af41c0bbffd0"
            }
        }
    ],
    "data_flow_connections": [
        {
            "component_type": "DataFlowEdge",
            "id": "29904c9b-8ff3-410c-a484-d95a9f4f9248",
            "name": "start_step_feedback_1_to_write_var_step_1_user_feedback_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b"
            },
            "source_output": "feedback_1",
            "destination_node": {
                "$component_ref": "be27d2dc-0185-41b0-bbbc-31060306b34c"
            },
            "destination_input": "user_feedback"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "5440b896-e11b-48b3-ae83-4e0832f87bc6",
            "name": "start_step_feedback_2_to_write_var_step_2_user_feedback_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b"
            },
            "source_output": "feedback_2",
            "destination_node": {
                "$component_ref": "4991b600-4fe1-4e46-82f8-6d0764989291"
            },
            "destination_input": "user_feedback"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "ff59cde4-e95d-4caf-b8b3-0e9097013bb2",
            "name": "read_var_step_user_feedback_to_output_step_feedback_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "e8e2df93-abc9-492a-9c0b-92c4a68895b9"
            },
            "source_output": "user_feedback",
            "destination_node": {
                "$component_ref": "bd2331f9-c336-446d-b6e8-5c4365e4327b"
            },
            "destination_input": "feedback"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "b3b923f5-5329-4c3c-aed6-a497f0709010",
            "name": "read_var_step_user_feedback_to_None End node_user_feedback_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
                "$component_ref": "e8e2df93-abc9-492a-9c0b-92c4a68895b9"
            },
            "source_output": "user_feedback",
            "destination_node": {
                "$component_ref": "e139d3c9-66ca-4e0e-afd5-af41c0bbffd0"
            },
            "destination_input": "user_feedback"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "a4acc7e5-0def-494b-8721-b1d3a51bc46e",
            "name": "output_step_output_message_to_None End node_output_message_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
                "$component_ref": "bd2331f9-c336-446d-b6e8-5c4365e4327b"
            },
            "source_output": "output_message",
            "destination_node": {
                "$component_ref": "e139d3c9-66ca-4e0e-afd5-af41c0bbffd0"
            },
            "destination_input": "output_message"
        }
    ],
    "context_providers": [],
    "state": [
        {
            "description": "list of user feedback",
            "type": "array",
            "items": {
                "type": "string"
            },
            "title": "user_feedback",
            "default": []
        }
    ],
    "component_plugin_name": "FlowPlugin",
    "component_plugin_version": "26.1.0.dev4",
    "$referenced_components": {
        "57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b": {
            "component_type": "StartNode",
            "id": "57f93e9d-9d58-4c7b-8d53-22f6d40b2a3b",
            "name": "start_step",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "type": "string",
                    "title": "feedback_1"
                },
                {
                    "type": "string",
                    "title": "feedback_2"
                }
            ],
            "outputs": [
                {
                    "type": "string",
                    "title": "feedback_1"
                },
                {
                    "type": "string",
                    "title": "feedback_2"
                }
            ],
            "branches": [
                "next"
            ]
        },
        "be27d2dc-0185-41b0-bbbc-31060306b34c": {
            "component_type": "PluginVariableNode",
            "id": "be27d2dc-0185-41b0-bbbc-31060306b34c",
            "name": "write_var_step_1",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "description": "list of user feedback (single element)",
                    "type": "string",
                    "title": "user_feedback"
                }
            ],
            "outputs": [],
            "branches": [
                "next"
            ],
            "input_mapping": {},
            "output_mapping": {},
            "write_variables": [
                {
                    "description": "list of user feedback",
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "title": "user_feedback",
                    "default": []
                }
            ],
            "read_variables": [],
            "write_operations": {
                "user_feedback": "insert"
            },
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "26.1.0.dev4"
        },
        "4991b600-4fe1-4e46-82f8-6d0764989291": {
            "component_type": "PluginVariableNode",
            "id": "4991b600-4fe1-4e46-82f8-6d0764989291",
            "name": "write_var_step_2",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "description": "list of user feedback (single element)",
                    "type": "string",
                    "title": "user_feedback"
                }
            ],
            "outputs": [],
            "branches": [
                "next"
            ],
            "input_mapping": {},
            "output_mapping": {},
            "write_variables": [
                {
                    "description": "list of user feedback",
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "title": "user_feedback",
                    "default": []
                }
            ],
            "read_variables": [],
            "write_operations": {
                "user_feedback": "insert"
            },
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "26.1.0.dev4"
        },
        "e8e2df93-abc9-492a-9c0b-92c4a68895b9": {
            "component_type": "PluginVariableNode",
            "id": "e8e2df93-abc9-492a-9c0b-92c4a68895b9",
            "name": "read_var_step",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [],
            "outputs": [
                {
                    "description": "list of user feedback",
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "title": "user_feedback",
                    "default": []
                }
            ],
            "branches": [
                "next"
            ],
            "input_mapping": {},
            "output_mapping": {},
            "write_variables": [],
            "read_variables": [
                {
                    "description": "list of user feedback",
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "title": "user_feedback",
                    "default": []
                }
            ],
            "write_operations": {},
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "26.1.0.dev4"
        },
        "bd2331f9-c336-446d-b6e8-5c4365e4327b": {
            "component_type": "PluginOutputMessageNode",
            "id": "bd2331f9-c336-446d-b6e8-5c4365e4327b",
            "name": "output_step",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "description": "\"feedback\" input variable for the template",
                    "type": "string",
                    "title": "feedback"
                }
            ],
            "outputs": [
                {
                    "description": "the message added to the messages list",
                    "type": "string",
                    "title": "output_message"
                }
            ],
            "branches": [
                "next"
            ],
            "message": "Collected feedback: {{ feedback }}",
            "input_mapping": {},
            "output_mapping": {},
            "message_type": "AGENT",
            "rephrase": false,
            "llm_config": null,
            "expose_message_as_output": true,
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "26.1.0.dev4"
        },
        "e139d3c9-66ca-4e0e-afd5-af41c0bbffd0": {
            "component_type": "EndNode",
            "id": "e139d3c9-66ca-4e0e-afd5-af41c0bbffd0",
            "name": "None End node",
            "description": "End node representing all transitions to None in the WayFlow flow",
            "metadata": {},
            "inputs": [
                {
                    "description": "list of user feedback",
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "title": "user_feedback",
                    "default": []
                },
                {
                    "description": "the message added to the messages list",
                    "type": "string",
                    "title": "output_message"
                }
            ],
            "outputs": [
                {
                    "description": "list of user feedback",
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "title": "user_feedback",
                    "default": []
                },
                {
                    "description": "the message added to the messages list",
                    "type": "string",
                    "title": "output_message"
                }
            ],
            "branches": [],
            "branch_name": "next"
        }
    },
    "agentspec_version": "25.4.2"
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
# Copyright © 2025, 2026 Oracle and/or its affiliates.
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
# pip install "wayflowcore==26.2.0.dev0" 
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
from wayflowcore.steps import StartStep, OutputMessageStep, VariableStep
from wayflowcore.property import StringProperty
from wayflowcore.variable import VariableWriteOperation

FEEDBACK_1 = "feedback_1"
FEEDBACK_2 = "feedback_2"

start_step = StartStep(
    name="start_step",
    input_descriptors=[StringProperty(FEEDBACK_1), StringProperty(FEEDBACK_2)],
)

write_feedback_1 = VariableStep(
    name="write_var_step_1",
    write_variables=[feedback_variable],
    write_operations=VariableWriteOperation.INSERT,
)

write_feedback_2 = VariableStep(
    name="write_var_step_2",
    write_variables=[feedback_variable],
    write_operations=VariableWriteOperation.INSERT,
)

read_feedback = VariableStep(
    name="read_var_step",
    read_variables=[feedback_variable],
)

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
        DataFlowEdge(start_step, FEEDBACK_1, write_feedback_1, feedback_variable.name),
        DataFlowEdge(start_step, FEEDBACK_2, write_feedback_2, feedback_variable.name),
        DataFlowEdge(read_feedback, feedback_variable.name, output_step, "feedback"),
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
