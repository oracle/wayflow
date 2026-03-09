<a id="top-howtomapstep"></a>

# How to Do Map and Reduce Operations in Flows![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[MapStep how-to script](../end_to_end_code_examples/howto_mapstep.py)

#### Prerequisites
This guide assumes familiarity with [Flows](../tutorials/basic_flow.md).

Map-Reduce is a programming model essential for efficiently processing large datasets across distributed systems.
It is widely used in software engineering to enhance data processing speed and scalability by parallelizing tasks.

WayFlow supports the Map and Reduce operations in Flows, using the [MapStep](../api/flows.md#mapstep).
This guide will show you how to:

- use [MapStep](../api/flows.md#mapstep) perform an operation on **all elements of a list**
- use [MapStep](../api/flows.md#mapstep) to perform an operation on **all key/value pairs of a dictionary**
- use [MapStep](../api/flows.md#mapstep) to **parallelize** some operations

![Flow diagram of a MapStep](core/_static/howto/mapstep.svg)

To follow this guide, you need an LLM.
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

## Basic implementation

Assuming you want to summarize a few articles.

```python
articles = [
    "Sea turtles are ancient reptiles that have been around for over 100 million years. They play crucial roles in marine ecosystems, such as maintaining healthy seagrass beds and coral reefs. Unfortunately, they are under threat due to poaching, habitat loss, and pollution. Conservation efforts worldwide aim to protect nesting sites and reduce bycatch in fishing gear.",
    "Dolphins are highly intelligent marine mammals known for their playfulness and curiosity. They live in social groups called pods, which can consist of hundreds of individuals depending on the species. Dolphins communicate using a variety of clicks, whistles, and other sounds. They face threats from habitat loss, marine pollution, and bycatch in fishing operations.",
    "Manatees, often referred to as 'sea cows', are gentle aquatic giants found in shallow coastal areas and rivers. These herbivorous mammals spend most of their time eating, resting, and traveling. They are particularly known for their slow movement and inability to survive in cold waters. Manatee populations are vulnerable to boat collisions, loss of warm-water habitats, and environmental pollutants.",
]
```

You have the option to generate the summary with the [PromptExecutionStep](../api/flows.md#promptexecutionstep) class, as explained already in [the separate guide](howto_promptexecutionstep.md):

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep

start_step = StartStep(name="start_step", input_descriptors=[StringProperty("article")])
summarize_step = PromptExecutionStep(
    name="summarize_step",
    llm=llm,
    prompt_template="""Summarize this article in 10 words:
 {{article}}""",
    output_mapping={PromptExecutionStep.OUTPUT: "summary"},
)
summarize_flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_step),
        ControlFlowEdge(source_step=summarize_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "article", summarize_step, "article"),
    ],
)
```

This step takes a single article, and generates a summary.
Since you have a list of articles, use the `MapStep` class to generate a summary for each article.

```python
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import MapStep

map_step = MapStep(
    name="map_step",
    flow=summarize_flow,
    unpack_input={"article": "."},
    output_descriptors=[ListProperty(name="summary", item_type=StringProperty())],
    input_descriptors=[ListProperty(MapStep.ITERATED_INPUT, item_type=StringProperty())],
)
```

#### NOTE
In the `unpack_input` function, define how each sub-flow input is retrieved.
Here, the sub-flow requires an `article` input. Set its value to `.`, because each iterated item is the article and `.` is the identity
query in JQ.

The `output_descriptors` parameter specifies which outputs of the sub-flow will be collected and merged into a list.

Once this is done, create the flow for the `MapStep` and execute it:

```python
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import StartStep

start_step = StartStep(
    name="start_step",
    input_descriptors=[ListProperty("articles", item_type=StringProperty())]
)
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=map_step),
        ControlFlowEdge(source_step=map_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "articles", map_step, MapStep.ITERATED_INPUT),
    ],
)
conversation = flow.start_conversation(inputs={"articles": articles})
status = conversation.execute()
print(status.output_values)
```

As expected, your flow has generated summaries of three articles!

## Processing in parallel

By default, the [MapStep](../api/flows.md#mapstep) runs all operations sequentially in order.
This is done so that any flow (including flows that yield or ask the user) can be run.

In many cases (such as generating articles summary), the work is completely parallelizable because the operations are independent from each other.
In this context, you can just set the `parallel_execution` parameter to `True` and the operations will be run in parallel using a thread-pool.

```python
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import StartStep

start_step = StartStep(input_descriptors=[ListProperty("articles", item_type=StringProperty())])
map_step = MapStep(
    flow=summarize_flow,
    unpack_input={"article": "."},
    output_descriptors=[ListProperty(name="summary", item_type=StringProperty())],
    input_descriptors=[ListProperty(MapStep.ITERATED_INPUT, item_type=StringProperty())],
    parallel_execution=True,
)
map_step_name = "map_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        map_step_name: map_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=map_step),
        ControlFlowEdge(source_step=map_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "articles", map_step, MapStep.ITERATED_INPUT),
    ],
)
conversation = flow.start_conversation(inputs={"articles": articles})
status = conversation.execute()
print(status.output_values)
```

The same can be achieved using the [ParallelMapStep](../api/flows.md#parallelmapstep).
This step type is equivalent to the [MapStep](../api/flows.md#mapstep), the only difference is that parallelization is always enabled.

```python
from wayflowcore.steps import ParallelMapStep

parallel_map_step = ParallelMapStep(
    flow=summarize_flow,
    unpack_input={"article": "."},
    output_descriptors=[ListProperty(name="summary", item_type=StringProperty())],
    input_descriptors=[ListProperty(MapStep.ITERATED_INPUT, item_type=StringProperty())],
)
```

#### NOTE
The Global Interpreter Lock (GIL) in Python is not a problem for parallel remote requests
because I/O-bound operations, such as network requests, release the GIL during their execution,
allowing other threads to run concurrently while the I/O operation is in progress.

Not all sub-flows can be executed in parallel.
The table below summarizes the limitations of parallel execution for the [MapStep](../api/flows.md#mapstep):

> | Support                         | Type of flow                                                                                                                                       | Examples                                                                                                                               | Remarks                                                                                                                  |
> |---------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
> | **FULLY SUPPORTED**             | **Flows that do not yield and do not have any side-effect on the conversation** (no variable read/write, posting to the conversation, and so on)   | Embarrassingly parallel flows (simple independent operation), such as a `PromptExecutionStep`, `ApiCallStep` to post or get, and so on | N/A                                                                                                                      |
> | **SUPPORTED WITH SIDE EFFECTS** | **Flows that do not yield but have some side-effect on the conversation** (variable read/write, posting to the conversation, and so on)            | Flows with `OutputMessageStep`, `VariableStep`, `VariableReadStep`, `VariableWriteStep`, and so on                                     | No guarantee in the order of operations (such as posting to the conversation), only the outputs are guaranteed in order. |
> | **NON SUPPORTED**               | **Flows that yield**. WayFlow does not support this, otherwise a user might be confused in what branch they are currently when prompted to answer. | Flows with `InputMessageStep`, `AgentExecutionStep` that can ask questions, and so on                                                  | It will raise an exception at instantiation time if a sub-flow can yield and step set to parallel                        |

> ## Common patterns and best practices

Sometimes, you might have a dictionary, and you need to iterate on each of the key/value pairs.
To achieve this, set `iterated_input_type` to `DictProperty(<your_type>)`, and use the queries `._key` (respectively `._value`) to access the key (and respectively the value) from the key/value pair.

```python
from wayflowcore.property import DictProperty, ListProperty, StringProperty
from wayflowcore.steps import StartStep

articles_as_dict = {str(idx): article for idx, article in enumerate(articles)}

map_step = MapStep(
    name="map_step",
    flow=summarize_flow,
    unpack_input={"article": "._value"},
    input_descriptors=[DictProperty(MapStep.ITERATED_INPUT, value_type=StringProperty())],
    output_descriptors=[ListProperty(name="summary", item_type=StringProperty())],
)
start_step = StartStep(
    name="start_step",
    input_descriptors=[DictProperty("articles", value_type=StringProperty())]
)
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=map_step),
        ControlFlowEdge(source_step=map_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "articles", map_step, MapStep.ITERATED_INPUT),
    ],
)

conversation = flow.start_conversation(inputs={"articles": articles_as_dict})
status = conversation.execute()
print(status.output_values)
```

## Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(flow)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "Flow",
  "id": "4ec5b97c-ec15-43b6-b778-0ae068572d2f",
  "name": "flow_e47f0d21",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [
    {
      "type": "array",
      "items": {
        "type": "string"
      },
      "title": "articles"
    }
  ],
  "outputs": [
    {
      "type": "array",
      "items": {
        "type": "string"
      },
      "title": "summary"
    }
  ],
  "start_node": {
    "$component_ref": "4e291d9e-ec4e-45b7-ade8-1ed5bf37a405"
  },
  "nodes": [
    {
      "$component_ref": "4e291d9e-ec4e-45b7-ade8-1ed5bf37a405"
    },
    {
      "$component_ref": "c8ce9d86-b069-4338-8372-09f32462ed39"
    },
    {
      "$component_ref": "0e6801d2-803e-40bc-809d-9e3dc69e5720"
    }
  ],
  "control_flow_connections": [
    {
      "component_type": "ControlFlowEdge",
      "id": "8250a6ea-1250-45bd-9c97-3211c99511d6",
      "name": "start_step_to_map_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "4e291d9e-ec4e-45b7-ade8-1ed5bf37a405"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "c8ce9d86-b069-4338-8372-09f32462ed39"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "09a6ef4e-bc03-4db8-a49c-d7f2a03414d0",
      "name": "map_step_to_None End node_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "c8ce9d86-b069-4338-8372-09f32462ed39"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "0e6801d2-803e-40bc-809d-9e3dc69e5720"
      }
    }
  ],
  "data_flow_connections": [
    {
      "component_type": "DataFlowEdge",
      "id": "a377edf1-bbac-49e0-bca0-2dd1638ba5ab",
      "name": "start_step_articles_to_map_step_iterated_input_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "4e291d9e-ec4e-45b7-ade8-1ed5bf37a405"
      },
      "source_output": "articles",
      "destination_node": {
        "$component_ref": "c8ce9d86-b069-4338-8372-09f32462ed39"
      },
      "destination_input": "iterated_input"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "6aadb135-1e4a-4f46-a2f9-3e4181f77818",
      "name": "map_step_summary_to_None End node_summary_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "c8ce9d86-b069-4338-8372-09f32462ed39"
      },
      "source_output": "summary",
      "destination_node": {
        "$component_ref": "0e6801d2-803e-40bc-809d-9e3dc69e5720"
      },
      "destination_input": "summary"
    }
  ],
  "$referenced_components": {
    "c8ce9d86-b069-4338-8372-09f32462ed39": {
      "component_type": "ExtendedMapNode",
      "id": "c8ce9d86-b069-4338-8372-09f32462ed39",
      "name": "map_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "iterated_input"
        }
      ],
      "outputs": [
        {
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "summary"
        }
      ],
      "branches": [
        "next"
      ],
      "input_mapping": {},
      "output_mapping": {},
      "flow": {
        "component_type": "Flow",
        "id": "8f8b92e5-fc99-4dac-9a56-ff423ced6195",
        "name": "flow_191e481f",
        "description": "",
        "metadata": {
          "__metadata_info__": {}
        },
        "inputs": [
          {
            "type": "string",
            "title": "article"
          }
        ],
        "outputs": [
          {
            "description": "the generated text",
            "type": "string",
            "title": "summary"
          }
        ],
        "start_node": {
          "$component_ref": "3e35c34a-75fc-4b8f-9454-5cd2ff95a985"
        },
        "nodes": [
          {
            "$component_ref": "3e35c34a-75fc-4b8f-9454-5cd2ff95a985"
          },
          {
            "$component_ref": "48b07b6d-fa2d-4975-88f5-b2113821a426"
          },
          {
            "$component_ref": "76083393-ffeb-4a1a-b2e1-a1b163c8ebbb"
          }
        ],
        "control_flow_connections": [
          {
            "component_type": "ControlFlowEdge",
            "id": "7e971869-fdda-41d2-8b72-746a5f4103c8",
            "name": "start_step_to_summarize_step_control_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "from_node": {
              "$component_ref": "3e35c34a-75fc-4b8f-9454-5cd2ff95a985"
            },
            "from_branch": null,
            "to_node": {
              "$component_ref": "48b07b6d-fa2d-4975-88f5-b2113821a426"
            }
          },
          {
            "component_type": "ControlFlowEdge",
            "id": "ac52880e-53fe-4418-a9a1-7e3248f76c4b",
            "name": "summarize_step_to_None End node_control_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "from_node": {
              "$component_ref": "48b07b6d-fa2d-4975-88f5-b2113821a426"
            },
            "from_branch": null,
            "to_node": {
              "$component_ref": "76083393-ffeb-4a1a-b2e1-a1b163c8ebbb"
            }
          }
        ],
        "data_flow_connections": [
          {
            "component_type": "DataFlowEdge",
            "id": "f21834ca-2e6a-469e-a385-cd1dd3bbe76e",
            "name": "start_step_article_to_summarize_step_article_data_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "source_node": {
              "$component_ref": "3e35c34a-75fc-4b8f-9454-5cd2ff95a985"
            },
            "source_output": "article",
            "destination_node": {
              "$component_ref": "48b07b6d-fa2d-4975-88f5-b2113821a426"
            },
            "destination_input": "article"
          },
          {
            "component_type": "DataFlowEdge",
            "id": "d8bf35b3-5595-4a1a-91fa-08b984cee4a9",
            "name": "summarize_step_summary_to_None End node_summary_data_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "source_node": {
              "$component_ref": "48b07b6d-fa2d-4975-88f5-b2113821a426"
            },
            "source_output": "summary",
            "destination_node": {
              "$component_ref": "76083393-ffeb-4a1a-b2e1-a1b163c8ebbb"
            },
            "destination_input": "summary"
          }
        ],
        "$referenced_components": {
          "48b07b6d-fa2d-4975-88f5-b2113821a426": {
            "component_type": "LlmNode",
            "id": "48b07b6d-fa2d-4975-88f5-b2113821a426",
            "name": "summarize_step",
            "description": "",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "description": "\"article\" input variable for the template",
                "type": "string",
                "title": "article"
              }
            ],
            "outputs": [
              {
                "description": "the generated text",
                "type": "string",
                "title": "summary"
              }
            ],
            "branches": [
              "next"
            ],
            "llm_config": {
              "component_type": "VllmConfig",
              "id": "0ef47939-f5ce-4267-a4f1-8c4f3492bad3",
              "name": "LLAMA_MODEL_ID",
              "description": null,
              "metadata": {
                "__metadata_info__": {}
              },
              "default_generation_parameters": null,
              "url": "LLAMA_API_URL",
              "model_id": "LLAMA_MODEL_ID"
            },
            "prompt_template": "Summarize this article in 10 words:\n {{article}}"
          },
          "3e35c34a-75fc-4b8f-9454-5cd2ff95a985": {
            "component_type": "StartNode",
            "id": "3e35c34a-75fc-4b8f-9454-5cd2ff95a985",
            "name": "start_step",
            "description": "",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "type": "string",
                "title": "article"
              }
            ],
            "outputs": [
              {
                "type": "string",
                "title": "article"
              }
            ],
            "branches": [
              "next"
            ]
          },
          "76083393-ffeb-4a1a-b2e1-a1b163c8ebbb": {
            "component_type": "EndNode",
            "id": "76083393-ffeb-4a1a-b2e1-a1b163c8ebbb",
            "name": "None End node",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "description": "the generated text",
                "type": "string",
                "title": "summary"
              }
            ],
            "outputs": [
              {
                "description": "the generated text",
                "type": "string",
                "title": "summary"
              }
            ],
            "branches": [],
            "branch_name": "next"
          }
        }
      },
      "unpack_input": {
        "article": "."
      },
      "parallel_execution": true,
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "25.4.0.dev0"
    },
    "4e291d9e-ec4e-45b7-ade8-1ed5bf37a405": {
      "component_type": "StartNode",
      "id": "4e291d9e-ec4e-45b7-ade8-1ed5bf37a405",
      "name": "start_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "articles"
        }
      ],
      "outputs": [
        {
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "articles"
        }
      ],
      "branches": [
        "next"
      ]
    },
    "0e6801d2-803e-40bc-809d-9e3dc69e5720": {
      "component_type": "EndNode",
      "id": "0e6801d2-803e-40bc-809d-9e3dc69e5720",
      "name": "None End node",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "summary"
        }
      ],
      "outputs": [
        {
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "summary"
        }
      ],
      "branches": [],
      "branch_name": "next"
    }
  },
  "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: Flow
id: 4ec5b97c-ec15-43b6-b778-0ae068572d2f
name: flow_e47f0d21
description: ''
metadata:
  __metadata_info__: {}
inputs:
- type: array
  items:
    type: string
  title: articles
outputs:
- type: array
  items:
    type: string
  title: summary
start_node:
  $component_ref: 4e291d9e-ec4e-45b7-ade8-1ed5bf37a405
nodes:
- $component_ref: 4e291d9e-ec4e-45b7-ade8-1ed5bf37a405
- $component_ref: c8ce9d86-b069-4338-8372-09f32462ed39
- $component_ref: 0e6801d2-803e-40bc-809d-9e3dc69e5720
control_flow_connections:
- component_type: ControlFlowEdge
  id: 8250a6ea-1250-45bd-9c97-3211c99511d6
  name: start_step_to_map_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 4e291d9e-ec4e-45b7-ade8-1ed5bf37a405
  from_branch: null
  to_node:
    $component_ref: c8ce9d86-b069-4338-8372-09f32462ed39
- component_type: ControlFlowEdge
  id: 09a6ef4e-bc03-4db8-a49c-d7f2a03414d0
  name: map_step_to_None End node_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: c8ce9d86-b069-4338-8372-09f32462ed39
  from_branch: null
  to_node:
    $component_ref: 0e6801d2-803e-40bc-809d-9e3dc69e5720
data_flow_connections:
- component_type: DataFlowEdge
  id: a377edf1-bbac-49e0-bca0-2dd1638ba5ab
  name: start_step_articles_to_map_step_iterated_input_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 4e291d9e-ec4e-45b7-ade8-1ed5bf37a405
  source_output: articles
  destination_node:
    $component_ref: c8ce9d86-b069-4338-8372-09f32462ed39
  destination_input: iterated_input
- component_type: DataFlowEdge
  id: 6aadb135-1e4a-4f46-a2f9-3e4181f77818
  name: map_step_summary_to_None End node_summary_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: c8ce9d86-b069-4338-8372-09f32462ed39
  source_output: summary
  destination_node:
    $component_ref: 0e6801d2-803e-40bc-809d-9e3dc69e5720
  destination_input: summary
$referenced_components:
  c8ce9d86-b069-4338-8372-09f32462ed39:
    component_type: ExtendedMapNode
    id: c8ce9d86-b069-4338-8372-09f32462ed39
    name: map_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: array
      items:
        type: string
      title: iterated_input
    outputs:
    - type: array
      items:
        type: string
      title: summary
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    flow:
      component_type: Flow
      id: 8f8b92e5-fc99-4dac-9a56-ff423ced6195
      name: flow_191e481f
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - type: string
        title: article
      outputs:
      - description: the generated text
        type: string
        title: summary
      start_node:
        $component_ref: 3e35c34a-75fc-4b8f-9454-5cd2ff95a985
      nodes:
      - $component_ref: 3e35c34a-75fc-4b8f-9454-5cd2ff95a985
      - $component_ref: 48b07b6d-fa2d-4975-88f5-b2113821a426
      - $component_ref: 76083393-ffeb-4a1a-b2e1-a1b163c8ebbb
      control_flow_connections:
      - component_type: ControlFlowEdge
        id: 7e971869-fdda-41d2-8b72-746a5f4103c8
        name: start_step_to_summarize_step_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: 3e35c34a-75fc-4b8f-9454-5cd2ff95a985
        from_branch: null
        to_node:
          $component_ref: 48b07b6d-fa2d-4975-88f5-b2113821a426
      - component_type: ControlFlowEdge
        id: ac52880e-53fe-4418-a9a1-7e3248f76c4b
        name: summarize_step_to_None End node_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: 48b07b6d-fa2d-4975-88f5-b2113821a426
        from_branch: null
        to_node:
          $component_ref: 76083393-ffeb-4a1a-b2e1-a1b163c8ebbb
      data_flow_connections:
      - component_type: DataFlowEdge
        id: f21834ca-2e6a-469e-a385-cd1dd3bbe76e
        name: start_step_article_to_summarize_step_article_data_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        source_node:
          $component_ref: 3e35c34a-75fc-4b8f-9454-5cd2ff95a985
        source_output: article
        destination_node:
          $component_ref: 48b07b6d-fa2d-4975-88f5-b2113821a426
        destination_input: article
      - component_type: DataFlowEdge
        id: d8bf35b3-5595-4a1a-91fa-08b984cee4a9
        name: summarize_step_summary_to_None End node_summary_data_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        source_node:
          $component_ref: 48b07b6d-fa2d-4975-88f5-b2113821a426
        source_output: summary
        destination_node:
          $component_ref: 76083393-ffeb-4a1a-b2e1-a1b163c8ebbb
        destination_input: summary
      $referenced_components:
        48b07b6d-fa2d-4975-88f5-b2113821a426:
          component_type: LlmNode
          id: 48b07b6d-fa2d-4975-88f5-b2113821a426
          name: summarize_step
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - description: '"article" input variable for the template'
            type: string
            title: article
          outputs:
          - description: the generated text
            type: string
            title: summary
          branches:
          - next
          llm_config:
            component_type: VllmConfig
            id: 0ef47939-f5ce-4267-a4f1-8c4f3492bad3
            name: LLAMA_MODEL_ID
            description: null
            metadata:
              __metadata_info__: {}
            default_generation_parameters: null
            url: LLAMA_API_URL
            model_id: LLAMA_MODEL_ID
          prompt_template: "Summarize this article in 10 words:\n {{article}}"
        3e35c34a-75fc-4b8f-9454-5cd2ff95a985:
          component_type: StartNode
          id: 3e35c34a-75fc-4b8f-9454-5cd2ff95a985
          name: start_step
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - type: string
            title: article
          outputs:
          - type: string
            title: article
          branches:
          - next
        76083393-ffeb-4a1a-b2e1-a1b163c8ebbb:
          component_type: EndNode
          id: 76083393-ffeb-4a1a-b2e1-a1b163c8ebbb
          name: None End node
          description: null
          metadata:
            __metadata_info__: {}
          inputs:
          - description: the generated text
            type: string
            title: summary
          outputs:
          - description: the generated text
            type: string
            title: summary
          branches: []
          branch_name: next
    unpack_input:
      article: .
    parallel_execution: true
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.4.0.dev0
  4e291d9e-ec4e-45b7-ade8-1ed5bf37a405:
    component_type: StartNode
    id: 4e291d9e-ec4e-45b7-ade8-1ed5bf37a405
    name: start_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: array
      items:
        type: string
      title: articles
    outputs:
    - type: array
      items:
        type: string
      title: articles
    branches:
    - next
  0e6801d2-803e-40bc-809d-9e3dc69e5720:
    component_type: EndNode
    id: 0e6801d2-803e-40bc-809d-9e3dc69e5720
    name: None End node
    description: null
    metadata:
      __metadata_info__: {}
    inputs:
    - type: array
      items:
        type: string
      title: summary
    outputs:
    - type: array
      items:
        type: string
      title: summary
    branches: []
    branch_name: next
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

flow = AgentSpecLoader().load_json(serialized_flow)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `ExtendedMapNode`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Next steps

Having learned how to perform `map` and `reduce` operations in WayFlow, you may now proceed to [How to Use Agents in Flows](howto_agents_in_flows.md).

## Full code

Click on the card at the [top of this page](#top-howtomapstep) to download the full code
for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to Do Map and Reduce Operations in Flows
# -------------------------------------------------------------------

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
# python howto_mapstep.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Define the articles

# %%
articles = [
    "Sea turtles are ancient reptiles that have been around for over 100 million years. They play crucial roles in marine ecosystems, such as maintaining healthy seagrass beds and coral reefs. Unfortunately, they are under threat due to poaching, habitat loss, and pollution. Conservation efforts worldwide aim to protect nesting sites and reduce bycatch in fishing gear.",
    "Dolphins are highly intelligent marine mammals known for their playfulness and curiosity. They live in social groups called pods, which can consist of hundreds of individuals depending on the species. Dolphins communicate using a variety of clicks, whistles, and other sounds. They face threats from habitat loss, marine pollution, and bycatch in fishing operations.",
    "Manatees, often referred to as 'sea cows', are gentle aquatic giants found in shallow coastal areas and rivers. These herbivorous mammals spend most of their time eating, resting, and traveling. They are particularly known for their slow movement and inability to survive in cold waters. Manatee populations are vulnerable to boat collisions, loss of warm-water habitats, and environmental pollutants.",
]

# %%[markdown]
## Define the LLM

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## Create the Flow for the MapStep

# %%
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep

start_step = StartStep(name="start_step", input_descriptors=[StringProperty("article")])
summarize_step = PromptExecutionStep(
    name="summarize_step",
    llm=llm,
    prompt_template="""Summarize this article in 10 words:
 {{article}}""",
    output_mapping={PromptExecutionStep.OUTPUT: "summary"},
)
summarize_flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_step),
        ControlFlowEdge(source_step=summarize_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "article", summarize_step, "article"),
    ],
)

# %%[markdown]
## Create the MapStep

# %%
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import MapStep

map_step = MapStep(
    name="map_step",
    flow=summarize_flow,
    unpack_input={"article": "."},
    output_descriptors=[ListProperty(name="summary", item_type=StringProperty())],
    input_descriptors=[ListProperty(MapStep.ITERATED_INPUT, item_type=StringProperty())],
)

# %%[markdown]
## Create and execute the final Flow

# %%
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import StartStep

start_step = StartStep(
    name="start_step",
    input_descriptors=[ListProperty("articles", item_type=StringProperty())]
)
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=map_step),
        ControlFlowEdge(source_step=map_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "articles", map_step, MapStep.ITERATED_INPUT),
    ],
)
conversation = flow.start_conversation(inputs={"articles": articles})
status = conversation.execute()
print(status.output_values)

# %%[markdown]
## Iterate over a dictionary

# %%
from wayflowcore.property import DictProperty, ListProperty, StringProperty
from wayflowcore.steps import StartStep

articles_as_dict = {str(idx): article for idx, article in enumerate(articles)}

map_step = MapStep(
    name="map_step",
    flow=summarize_flow,
    unpack_input={"article": "._value"},
    input_descriptors=[DictProperty(MapStep.ITERATED_INPUT, value_type=StringProperty())],
    output_descriptors=[ListProperty(name="summary", item_type=StringProperty())],
)
start_step = StartStep(
    name="start_step",
    input_descriptors=[DictProperty("articles", value_type=StringProperty())]
)
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=map_step),
        ControlFlowEdge(source_step=map_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "articles", map_step, MapStep.ITERATED_INPUT),
    ],
)

conversation = flow.start_conversation(inputs={"articles": articles_as_dict})
status = conversation.execute()
print(status.output_values)

# %%[markdown]
## Parallel execution of map reduce operation

# %%
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import StartStep

start_step = StartStep(input_descriptors=[ListProperty("articles", item_type=StringProperty())])
map_step = MapStep(
    flow=summarize_flow,
    unpack_input={"article": "."},
    output_descriptors=[ListProperty(name="summary", item_type=StringProperty())],
    input_descriptors=[ListProperty(MapStep.ITERATED_INPUT, item_type=StringProperty())],
    parallel_execution=True,
)
map_step_name = "map_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        map_step_name: map_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=map_step),
        ControlFlowEdge(source_step=map_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "articles", map_step, MapStep.ITERATED_INPUT),
    ],
)
conversation = flow.start_conversation(inputs={"articles": articles})
status = conversation.execute()
print(status.output_values)

# %%[markdown]
## Parallel execution of map reduce operation with ParallelMapStep

# %%
from wayflowcore.steps import ParallelMapStep

parallel_map_step = ParallelMapStep(
    flow=summarize_flow,
    unpack_input={"article": "."},
    output_descriptors=[ListProperty(name="summary", item_type=StringProperty())],
    input_descriptors=[ListProperty(MapStep.ITERATED_INPUT, item_type=StringProperty())],
)

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(flow)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

flow = AgentSpecLoader().load_json(serialized_flow)
```
