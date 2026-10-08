# Build Flows with the Flow Builder

This guide shows how to assemble WayFlow Flows using the chainable `FlowBuilder` API.

#### Prerequisites
This guide assumes you are familiar with the following concepts:

- [Flows](../api/flows.md#flow) and basic steps/edges

## Overview

`FlowBuilder` lets you quickly construct flows without manually wiring every edge. It supports:

- `add_sequence`: add steps in order and wire control edges between them.
- `set_entry_point` and `set_finish_points`: declare the entry and terminal steps.
- `add_conditional`: branch based on an input to a [BranchingStep](../api/flows.md#branchingstep).
- `build_linear_flow`: convenience to assemble a linear flow in one call.

See the full API in [API › Flows](../api/flows.md) and quick snippets in the [Reference Sheet](../misc/reference_sheet.md#flowbuilder-ref-sheet).

## 1. Build a linear flow

Create two steps and connect them linearly with a single call.

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

You can also use the `build_linear_flow` method:

```python
from wayflowcore.flowbuilder import FlowBuilder
from wayflowcore.steps import OutputMessageStep

greet = OutputMessageStep(name="greet", message_template="Say hello")
reply = OutputMessageStep(name="reply", message_template="Say world")

linear_flow = FlowBuilder.build_linear_flow([greet, reply])
```

## 2. Add a conditional branch

Add a branching step where an upstream step’s output determines which branch to execute.

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

Notes:

- `add_conditional` accepts the branch key as a string output name, or a tuple `(step_or_name, output_name)` to read from another step.
- `set_finish_points` declares which steps finish the flow (creates control edges to `CompleteStep`).

## 3. Export the flow

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_agent = AgentSpecExporter().to_json(linear_flow)
```

### Here is what the Agent Spec representation will look like ↓

<details>
<summary>Details</summary>

JSON

```json
{
    "component_type": "Flow",
    "id": "99c4917a-5b5b-4b90-9eb2-4f55cf1f0c87",
    "name": "Flow",
    "description": "",
    "metadata": {
        "__metadata_info__": {}
    },
    "inputs": [],
    "outputs": [
        {
            "description": "the message added to the messages list",
            "type": "string",
            "title": "output_message"
        }
    ],
    "start_node": {
        "$component_ref": "e1c08ec1-fd8a-4ee4-9e7b-e061805af104"
    },
    "nodes": [
        {
            "$component_ref": "723a3386-d1ac-45d8-a491-81b79c597a1f"
        },
        {
            "$component_ref": "e3fa084f-7c93-4196-92f3-503a194d9dd7"
        },
        {
            "$component_ref": "e1c08ec1-fd8a-4ee4-9e7b-e061805af104"
        },
        {
            "$component_ref": "3ae47fc3-1bd7-437b-b3f5-dda3154c0c3a"
        }
    ],
    "control_flow_connections": [
        {
            "component_type": "ControlFlowEdge",
            "id": "02fd1540-d1a0-494f-8df7-8cc09dd56105",
            "name": "greet_to_reply_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "723a3386-d1ac-45d8-a491-81b79c597a1f"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "e3fa084f-7c93-4196-92f3-503a194d9dd7"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "51379f46-96b1-4345-81b3-e5c2e8d1f6fe",
            "name": "__StartStep___to_greet_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "e1c08ec1-fd8a-4ee4-9e7b-e061805af104"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "723a3386-d1ac-45d8-a491-81b79c597a1f"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "158d2498-dbbe-45b8-9069-3c1237e1bfa7",
            "name": "reply_to_None End node_control_flow_edge",
            "description": null,
            "metadata": {},
            "from_node": {
                "$component_ref": "e3fa084f-7c93-4196-92f3-503a194d9dd7"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "3ae47fc3-1bd7-437b-b3f5-dda3154c0c3a"
            }
        }
    ],
    "data_flow_connections": [
        {
            "component_type": "DataFlowEdge",
            "id": "c130b808-5ec4-43e5-9346-91e5183c2e52",
            "name": "greet_output_message_to_None End node_output_message_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
                "$component_ref": "723a3386-d1ac-45d8-a491-81b79c597a1f"
            },
            "source_output": "output_message",
            "destination_node": {
                "$component_ref": "3ae47fc3-1bd7-437b-b3f5-dda3154c0c3a"
            },
            "destination_input": "output_message"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "a22a544a-4ad5-41be-b3e4-83deb48a90c2",
            "name": "reply_output_message_to_None End node_output_message_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
                "$component_ref": "e3fa084f-7c93-4196-92f3-503a194d9dd7"
            },
            "source_output": "output_message",
            "destination_node": {
                "$component_ref": "3ae47fc3-1bd7-437b-b3f5-dda3154c0c3a"
            },
            "destination_input": "output_message"
        }
    ],
    "$referenced_components": {
        "3ae47fc3-1bd7-437b-b3f5-dda3154c0c3a": {
            "component_type": "EndNode",
            "id": "3ae47fc3-1bd7-437b-b3f5-dda3154c0c3a",
            "name": "None End node",
            "description": "End node representing all transitions to None in the WayFlow flow",
            "metadata": {},
            "inputs": [
                {
                    "description": "the message added to the messages list",
                    "type": "string",
                    "title": "output_message"
                }
            ],
            "outputs": [
                {
                    "description": "the message added to the messages list",
                    "type": "string",
                    "title": "output_message"
                }
            ],
            "branches": [],
            "branch_name": "next"
        },
        "723a3386-d1ac-45d8-a491-81b79c597a1f": {
            "component_type": "PluginOutputMessageNode",
            "id": "723a3386-d1ac-45d8-a491-81b79c597a1f",
            "name": "greet",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [],
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
            "message": "Say hello",
            "input_mapping": {},
            "output_mapping": {},
            "message_type": "AGENT",
            "rephrase": false,
            "llm_config": null,
            "expose_message_as_output": true,
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "26.1.0.dev4"
        },
        "e3fa084f-7c93-4196-92f3-503a194d9dd7": {
            "component_type": "PluginOutputMessageNode",
            "id": "e3fa084f-7c93-4196-92f3-503a194d9dd7",
            "name": "reply",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [],
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
            "message": "Say world",
            "input_mapping": {},
            "output_mapping": {},
            "message_type": "AGENT",
            "rephrase": false,
            "llm_config": null,
            "expose_message_as_output": true,
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "26.1.0.dev4"
        },
        "e1c08ec1-fd8a-4ee4-9e7b-e061805af104": {
            "component_type": "StartNode",
            "id": "e1c08ec1-fd8a-4ee4-9e7b-e061805af104",
            "name": "__StartStep__",
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
component_type: Flow
id: 99c4917a-5b5b-4b90-9eb2-4f55cf1f0c87
name: Flow
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs:
- description: the message added to the messages list
  type: string
  title: output_message
start_node:
  $component_ref: e1c08ec1-fd8a-4ee4-9e7b-e061805af104
nodes:
- $component_ref: 723a3386-d1ac-45d8-a491-81b79c597a1f
- $component_ref: e3fa084f-7c93-4196-92f3-503a194d9dd7
- $component_ref: e1c08ec1-fd8a-4ee4-9e7b-e061805af104
- $component_ref: ea0e42f1-bd8e-4926-a02b-1256c4747128
control_flow_connections:
- component_type: ControlFlowEdge
  id: 02fd1540-d1a0-494f-8df7-8cc09dd56105
  name: greet_to_reply_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 723a3386-d1ac-45d8-a491-81b79c597a1f
  from_branch: null
  to_node:
    $component_ref: e3fa084f-7c93-4196-92f3-503a194d9dd7
- component_type: ControlFlowEdge
  id: 51379f46-96b1-4345-81b3-e5c2e8d1f6fe
  name: __StartStep___to_greet_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: e1c08ec1-fd8a-4ee4-9e7b-e061805af104
  from_branch: null
  to_node:
    $component_ref: 723a3386-d1ac-45d8-a491-81b79c597a1f
- component_type: ControlFlowEdge
  id: 5a0f8368-c9e0-4865-a2fb-da18f7c304e3
  name: reply_to_None End node_control_flow_edge
  description: null
  metadata: {}
  from_node:
    $component_ref: e3fa084f-7c93-4196-92f3-503a194d9dd7
  from_branch: null
  to_node:
    $component_ref: ea0e42f1-bd8e-4926-a02b-1256c4747128
data_flow_connections:
- component_type: DataFlowEdge
  id: 262ca29a-ec07-42b5-8d7d-db5b59cb095a
  name: greet_output_message_to_None End node_output_message_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 723a3386-d1ac-45d8-a491-81b79c597a1f
  source_output: output_message
  destination_node:
    $component_ref: ea0e42f1-bd8e-4926-a02b-1256c4747128
  destination_input: output_message
- component_type: DataFlowEdge
  id: d4f73e1f-2c62-49d8-9bac-8f47aa22b2cc
  name: reply_output_message_to_None End node_output_message_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: e3fa084f-7c93-4196-92f3-503a194d9dd7
  source_output: output_message
  destination_node:
    $component_ref: ea0e42f1-bd8e-4926-a02b-1256c4747128
  destination_input: output_message
$referenced_components:
  ea0e42f1-bd8e-4926-a02b-1256c4747128:
    component_type: EndNode
    id: ea0e42f1-bd8e-4926-a02b-1256c4747128
    name: None End node
    description: End node representing all transitions to None in the WayFlow flow
    metadata: {}
    inputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    outputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    branches: []
    branch_name: next
  723a3386-d1ac-45d8-a491-81b79c597a1f:
    component_type: PluginOutputMessageNode
    id: 723a3386-d1ac-45d8-a491-81b79c597a1f
    name: greet
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    branches:
    - next
    message: Say hello
    input_mapping: {}
    output_mapping: {}
    message_type: AGENT
    rephrase: false
    llm_config: null
    expose_message_as_output: true
    component_plugin_name: NodesPlugin
    component_plugin_version: 26.1.0.dev4
  e3fa084f-7c93-4196-92f3-503a194d9dd7:
    component_type: PluginOutputMessageNode
    id: e3fa084f-7c93-4196-92f3-503a194d9dd7
    name: reply
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    branches:
    - next
    message: Say world
    input_mapping: {}
    output_mapping: {}
    message_type: AGENT
    rephrase: false
    llm_config: null
    expose_message_as_output: true
    component_plugin_name: NodesPlugin
    component_plugin_version: 26.1.0.dev4
  e1c08ec1-fd8a-4ee4-9e7b-e061805af104:
    component_type: StartNode
    id: e1c08ec1-fd8a-4ee4-9e7b-e061805af104
    name: __StartStep__
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

agent = AgentSpecLoader().load_json(serialized_agent)
```

## Recap

This how-to guide showed how to:

- Build a linear flow in one line with `build_linear_flow`
- Add a conditional branch with `set_conditional`
- Declare entry and finish points and serialize your flow

## Next steps
- Explore more patterns in the [Reference Sheet](../misc/reference_sheet.md#flowbuilder-ref-sheet)
- See the complete API in [API › Flows](../api/flows.md)
- Learn about branching and loops in [How to Develop a Flow with Conditional Branches](conditional_flows.md)
