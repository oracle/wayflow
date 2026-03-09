<a id="top-howtoparallelflowexecution"></a>

# How to Run Multiple Flows in Parallel![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Parallel flow execution how-to script](../end_to_end_code_examples/howto_parallelflowexecution.py)

#### Prerequisites
This guide assumes familiarity with [Flows](../tutorials/basic_flow.md).

Parallelism is a fundamental concept in computing that enables tasks to be processed concurrently,
significantly enhancing system efficiency, scalability, and overall performance.

WayFlow supports the execution of multiple Flows in parallel, using the [ParallelFlowExecutionStep](../api/flows.md#parallelflowexecutionstep).
This guide will show you how to:

- use [ParallelFlowExecutionStep](../api/flows.md#parallelflowexecutionstep) to run several tasks in parallel
- use [PromptExecutionStep](../api/flows.md#promptexecutionstep) to summarize the outcome of the parallel tasks

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

In this guide, we will create a `Flow` that generates a marketing message for a user.
Taking the username that identifies the user as input, we will take advantage of the `ParallelFlowExecutionStep`
to concurrently retrieve information about the user and the context, so that we can finally generate a
personalized marketing welcome message.

We first define the following tools that retrieve the desired information:

* One tool that retrieves the current time;
* One tool that retrieves the user information, like name and date of birth;
* One tool that gathers the user’s purchase history;
* One tool that looks for the current list of items on sale, which could be recommended to the user.

```python
from wayflowcore.property import DictProperty, ListProperty, StringProperty
from wayflowcore.tools.toolhelpers import DescriptionMode, tool


@tool(
    description_mode=DescriptionMode.ONLY_DOCSTRING,
    output_descriptors=[DictProperty(name="user_info", value_type=StringProperty())],
)
def get_user_information(username: str) -> dict[str, str]:
    """Retrieve information about a user"""
    return {
        "alice": {"name": "Alice", "email": "alice@email.com", "date_of_birth": "1980/05/01"},
        "bob": {"name": "Bob", "email": "bob@email.com", "date_of_birth": "1970/10/01"},
    }.get(username, {})


@tool(
    description_mode=DescriptionMode.ONLY_DOCSTRING,
    output_descriptors=[StringProperty(name="current_time")],
)
def get_current_time() -> str:
    """Return current time"""
    return "2025/10/01 10:30 PM"


@tool(
    description_mode=DescriptionMode.ONLY_DOCSTRING,
    output_descriptors=[
        ListProperty(name="user_purchases", item_type=DictProperty(value_type=StringProperty()))
    ],
)
def get_user_last_purchases(username: str) -> list[dict[str, str]]:
    """Retrieve the list of purchases made by a user"""
    return {
        "alice": [
            {"item_type": "videogame", "title": "Arkanoid", "date": "2000/10/10"},
            {"item_type": "videogame", "title": "Pacman", "date": "2002/09/09"},
        ],
        "bob": [
            {"item_type": "movie", "title": "Batman begins", "date": "2015/10/10"},
            {"item_type": "movie", "title": "The Dark Knight", "date": "2020/08/08"},
        ],
    }.get(username, [])


@tool(
    description_mode=DescriptionMode.ONLY_DOCSTRING,
    output_descriptors=[
        ListProperty(name="items_on_sale", item_type=DictProperty(value_type=StringProperty()))
    ],
)
def get_items_on_sale() -> list[dict[str, str]]:
    """Retrieve the list of items currently on sale"""
    return [
        {"item_type": "household", "title": "Broom"},
        {"item_type": "videogame", "title": "Metroid"},
        {"item_type": "movie", "title": "The Lord of the Rings"},
    ]


```

These tools simply gather information, therefore they can be easily parallelized.
We create the flows that wrap the tools we just created, and we collect them all in a `ParallelFlowExecutionStep`
for parallel execution.

```python
from wayflowcore.flow import Flow
from wayflowcore.steps import ParallelFlowExecutionStep, ToolExecutionStep

get_current_time_flow = Flow.from_steps(
    [ToolExecutionStep(name="get_current_time_step", tool=get_current_time)]
)
get_user_information_flow = Flow.from_steps(
    [ToolExecutionStep(name="get_user_information_step", tool=get_user_information)]
)
get_user_last_purchases_flow = Flow.from_steps(
    [ToolExecutionStep(name="get_user_last_purchases_step", tool=get_user_last_purchases)]
)
get_items_on_sale_flow = Flow.from_steps(
    [ToolExecutionStep(name="get_items_on_sale_steo", tool=get_items_on_sale)]
)

parallel_flow_step = ParallelFlowExecutionStep(
    name="parallel_flow_step",
    flows=[
        get_current_time_flow,
        get_user_information_flow,
        get_user_last_purchases_flow,
        get_items_on_sale_flow,
    ],
    max_workers=4,
)
```

The `ParallelFlowExecutionStep` will expose all the outputs that the different inner flows generate.
We use this information to ask an LLM to generate a personalized welcome message for the user, which should also
have a marketing purpose.

```python
from wayflowcore.models import VllmModel
from wayflowcore.steps import OutputMessageStep, PromptExecutionStep

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

prompt = """# Instructions

You are a marketing expert. You have to write a welcome message for a user.

The message must contain:
- A first sentence of greetings, including user's name, and personalized in case it's user's birthday
- A proposal containing something to buy

The purchase proposal must be:
- aligned with user's purchase history
- part of the list of items on sale

# User information

{{user_info}}

Note that the current time to check the birthday is: {{current_time}}

The list of items purchased by the user is:
{{user_purchases}}

# Items on sale

{{items_on_sale}}

Please write the welcome message for the user.
Do not give me the instructions to do it, I want only the final message to send.
"""

prompt_execution_step = PromptExecutionStep(
    name="prepare_marketing_message", prompt_template=prompt, llm=llm
)
output_message_step = OutputMessageStep(name="output_message_step", message_template="{{output}}")
```

Now that we have all the steps that compose our flow, we just put everything together to create it, and we
execute it to generate our personalized message.

```python
from wayflowcore.flow import Flow

flow = Flow.from_steps([parallel_flow_step, prompt_execution_step, output_message_step])

conversation = flow.start_conversation(inputs={"username": "bob"})
status = conversation.execute()
print(conversation.get_last_message().content)

# Expected output:
# Happy Birthday, Bob! We hope your special day is filled with excitement and joy.
# As a token of appreciation for being an valued customer, we'd like to recommend our sale on "The Lord of the Rings",
# a movie that we think you'll love, given your interest in superhero classics like "Batman Begins" and "The Dark Knight".
# It's now available at a discounted price, so don't miss out on this amazing opportunity to add it to your collection.
# Browse our sale now and enjoy!
```

## Notes about parallelization

Not all sub-flows can be executed in parallel.
The table below summarizes the limitations of parallel execution for the [ParallelFlowExecutionStep](../api/flows.md#parallelflowexecutionstep):

> | Support                         | Type of flow                                                                                                                                       | Examples                                                                                                                               | Remarks                                                                                                                  |
> |---------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
> | **FULLY SUPPORTED**             | **Flows that do not yield and do not have any side-effect on the conversation** (no variable read/write, posting to the conversation, and so on)   | Embarrassingly parallel flows (simple independent operation), such as a `PromptExecutionStep`, `ApiCallStep` to post or get, and so on | N/A                                                                                                                      |
> | **SUPPORTED WITH SIDE EFFECTS** | **Flows that do not yield but have some side-effect on the conversation** (variable read/write, posting to the conversation, and so on)            | Flows with `OutputMessageStep`, `VariableReadStep`, `VariableWriteStep`, and so on                                                     | No guarantee in the order of operations (such as posting to the conversation), only the outputs are guaranteed in order. |
> | **NON SUPPORTED**               | **Flows that yield**. WayFlow does not support this, otherwise a user might be confused in what branch they are currently when prompted to answer. | Flows with `InputMessageStep`, `AgentExecutionStep` that can ask questions, `ClientTool`, and so on                                    | It will raise an exception at instantiation time if a sub-flow can yield and step set to parallel                        |

> #### NOTE
> The Global Interpreter Lock (GIL) in Python is not a problem for parallel remote requests
> because I/O-bound operations, such as network requests, release the GIL during their execution,
> allowing other threads to run concurrently while the I/O operation is in progress.

> ## Agent Spec Exporting/Loading

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
  "id": "54d4d398-5680-4ded-a594-bfd99790311a",
  "name": "flow_d2c53e52__auto",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [
    {
      "type": "string",
      "title": "username"
    }
  ],
  "outputs": [
    {
      "type": "object",
      "additionalProperties": {
        "type": "string"
      },
      "key_type": {
        "type": "string"
      },
      "title": "user_info"
    },
    {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": {
          "type": "string"
        },
        "key_type": {
          "type": "string"
        }
      },
      "title": "items_on_sale"
    },
    {
      "description": "the message added to the messages list",
      "type": "string",
      "title": "output_message"
    },
    {
      "type": "string",
      "title": "current_time"
    },
    {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": {
          "type": "string"
        },
        "key_type": {
          "type": "string"
        }
      },
      "title": "user_purchases"
    },
    {
      "description": "the generated text",
      "type": "string",
      "title": "output"
    }
  ],
  "start_node": {
    "$component_ref": "ddcf926c-bce7-4050-a5f0-0a3da2110b52"
  },
  "nodes": [
    {
      "$component_ref": "6ce9d589-6649-4d21-992d-b9f1e76e01fa"
    },
    {
      "$component_ref": "b3642f57-f4da-4023-96dd-3916bc931b68"
    },
    {
      "$component_ref": "6594c3ef-67d2-4dfd-96a4-328a9fad8443"
    },
    {
      "$component_ref": "ddcf926c-bce7-4050-a5f0-0a3da2110b52"
    },
    {
      "$component_ref": "e8563485-edec-4ba2-ba13-4e2636e6de6c"
    }
  ],
  "control_flow_connections": [
    {
      "component_type": "ControlFlowEdge",
      "id": "eae402fb-9859-412f-9b98-d62dade4b757",
      "name": "parallel_flow_step_to_prepare_marketing_message_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "6ce9d589-6649-4d21-992d-b9f1e76e01fa"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "b3642f57-f4da-4023-96dd-3916bc931b68"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "229a2cb3-80b4-4a89-9824-2dd41a59e660",
      "name": "prepare_marketing_message_to_output_message_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "b3642f57-f4da-4023-96dd-3916bc931b68"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "6594c3ef-67d2-4dfd-96a4-328a9fad8443"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "d9801199-6ace-42fb-b9c4-109413041047",
      "name": "__StartStep___to_parallel_flow_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "ddcf926c-bce7-4050-a5f0-0a3da2110b52"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "6ce9d589-6649-4d21-992d-b9f1e76e01fa"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "9548adc6-82fb-4553-9cd9-6fd7367a93e7",
      "name": "output_message_step_to_None End node_control_flow_edge",
      "description": null,
      "metadata": {},
      "from_node": {
        "$component_ref": "6594c3ef-67d2-4dfd-96a4-328a9fad8443"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "e8563485-edec-4ba2-ba13-4e2636e6de6c"
      }
    }
  ],
  "data_flow_connections": [
    {
      "component_type": "DataFlowEdge",
      "id": "04675bc3-157f-48c8-bfba-2b2045153d33",
      "name": "parallel_flow_step_user_info_to_prepare_marketing_message_user_info_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "6ce9d589-6649-4d21-992d-b9f1e76e01fa"
      },
      "source_output": "user_info",
      "destination_node": {
        "$component_ref": "b3642f57-f4da-4023-96dd-3916bc931b68"
      },
      "destination_input": "user_info"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "785a09b7-2c39-48c7-a2ad-522ce7815ca7",
      "name": "parallel_flow_step_current_time_to_prepare_marketing_message_current_time_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "6ce9d589-6649-4d21-992d-b9f1e76e01fa"
      },
      "source_output": "current_time",
      "destination_node": {
        "$component_ref": "b3642f57-f4da-4023-96dd-3916bc931b68"
      },
      "destination_input": "current_time"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "52844a73-6b00-40b3-b714-f2f8790e0a08",
      "name": "parallel_flow_step_user_purchases_to_prepare_marketing_message_user_purchases_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "6ce9d589-6649-4d21-992d-b9f1e76e01fa"
      },
      "source_output": "user_purchases",
      "destination_node": {
        "$component_ref": "b3642f57-f4da-4023-96dd-3916bc931b68"
      },
      "destination_input": "user_purchases"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "3cd4824d-41bb-40a5-8f20-6e2aef9dcd25",
      "name": "parallel_flow_step_items_on_sale_to_prepare_marketing_message_items_on_sale_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "6ce9d589-6649-4d21-992d-b9f1e76e01fa"
      },
      "source_output": "items_on_sale",
      "destination_node": {
        "$component_ref": "b3642f57-f4da-4023-96dd-3916bc931b68"
      },
      "destination_input": "items_on_sale"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "f76e15fe-eb5c-47d6-b20d-de40bbd88991",
      "name": "prepare_marketing_message_output_to_output_message_step_output_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "b3642f57-f4da-4023-96dd-3916bc931b68"
      },
      "source_output": "output",
      "destination_node": {
        "$component_ref": "6594c3ef-67d2-4dfd-96a4-328a9fad8443"
      },
      "destination_input": "output"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "d7b0f627-aee4-4135-8052-361e63f21037",
      "name": "__StartStep___username_to_parallel_flow_step_username_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "ddcf926c-bce7-4050-a5f0-0a3da2110b52"
      },
      "source_output": "username",
      "destination_node": {
        "$component_ref": "6ce9d589-6649-4d21-992d-b9f1e76e01fa"
      },
      "destination_input": "username"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "48b06c96-7dad-4da2-8a94-bace2d0cac7e",
      "name": "parallel_flow_step_user_info_to_None End node_user_info_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "6ce9d589-6649-4d21-992d-b9f1e76e01fa"
      },
      "source_output": "user_info",
      "destination_node": {
        "$component_ref": "e8563485-edec-4ba2-ba13-4e2636e6de6c"
      },
      "destination_input": "user_info"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "0c514ff2-ca9b-4f98-86e9-62d7dece421a",
      "name": "parallel_flow_step_items_on_sale_to_None End node_items_on_sale_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "6ce9d589-6649-4d21-992d-b9f1e76e01fa"
      },
      "source_output": "items_on_sale",
      "destination_node": {
        "$component_ref": "e8563485-edec-4ba2-ba13-4e2636e6de6c"
      },
      "destination_input": "items_on_sale"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "4fdd2b40-9078-4f30-92f6-c8103d406e01",
      "name": "output_message_step_output_message_to_None End node_output_message_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "6594c3ef-67d2-4dfd-96a4-328a9fad8443"
      },
      "source_output": "output_message",
      "destination_node": {
        "$component_ref": "e8563485-edec-4ba2-ba13-4e2636e6de6c"
      },
      "destination_input": "output_message"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "aa31f23e-3ba0-41be-8214-dc32d9365401",
      "name": "parallel_flow_step_current_time_to_None End node_current_time_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "6ce9d589-6649-4d21-992d-b9f1e76e01fa"
      },
      "source_output": "current_time",
      "destination_node": {
        "$component_ref": "e8563485-edec-4ba2-ba13-4e2636e6de6c"
      },
      "destination_input": "current_time"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "bb699cc4-e9ae-423a-ac2e-fb4afc629b84",
      "name": "parallel_flow_step_user_purchases_to_None End node_user_purchases_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "6ce9d589-6649-4d21-992d-b9f1e76e01fa"
      },
      "source_output": "user_purchases",
      "destination_node": {
        "$component_ref": "e8563485-edec-4ba2-ba13-4e2636e6de6c"
      },
      "destination_input": "user_purchases"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "56bef94f-fe6a-4f13-8587-8dec9e8498b6",
      "name": "prepare_marketing_message_output_to_None End node_output_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "b3642f57-f4da-4023-96dd-3916bc931b68"
      },
      "source_output": "output",
      "destination_node": {
        "$component_ref": "e8563485-edec-4ba2-ba13-4e2636e6de6c"
      },
      "destination_input": "output"
    }
  ],
  "$referenced_components": {
    "6ce9d589-6649-4d21-992d-b9f1e76e01fa": {
      "component_type": "ExtendedParallelFlowNode",
      "id": "6ce9d589-6649-4d21-992d-b9f1e76e01fa",
      "name": "parallel_flow_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "string",
          "title": "username"
        }
      ],
      "outputs": [
        {
          "type": "string",
          "title": "current_time"
        },
        {
          "type": "object",
          "additionalProperties": {
            "type": "string"
          },
          "key_type": {
            "type": "string"
          },
          "title": "user_info"
        },
        {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": {
              "type": "string"
            },
            "key_type": {
              "type": "string"
            }
          },
          "title": "user_purchases"
        },
        {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": {
              "type": "string"
            },
            "key_type": {
              "type": "string"
            }
          },
          "title": "items_on_sale"
        }
      ],
      "branches": [
        "next"
      ],
      "input_mapping": {},
      "output_mapping": {},
      "flows": [
        {
          "component_type": "Flow",
          "id": "3e8130df-e277-4f19-918c-f6584d791d24",
          "name": "flow_9eb7e208__auto",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [],
          "outputs": [
            {
              "type": "string",
              "title": "current_time"
            }
          ],
          "start_node": {
            "$component_ref": "cddc1061-f534-4182-98a7-a265e9a24d58"
          },
          "nodes": [
            {
              "$component_ref": "0075a188-518a-48de-aa40-311e2b101db8"
            },
            {
              "$component_ref": "cddc1061-f534-4182-98a7-a265e9a24d58"
            },
            {
              "$component_ref": "6b29d2c5-02e4-405c-84fd-ab88df514c22"
            }
          ],
          "control_flow_connections": [
            {
              "component_type": "ControlFlowEdge",
              "id": "ab5b3f24-8caf-4de6-a4a9-059646aaa413",
              "name": "__StartStep___to_get_current_time_step_control_flow_edge",
              "description": null,
              "metadata": {
                "__metadata_info__": {}
              },
              "from_node": {
                "$component_ref": "cddc1061-f534-4182-98a7-a265e9a24d58"
              },
              "from_branch": null,
              "to_node": {
                "$component_ref": "0075a188-518a-48de-aa40-311e2b101db8"
              }
            },
            {
              "component_type": "ControlFlowEdge",
              "id": "eb8c4a33-49aa-43a8-a91a-fb42e45e3eb9",
              "name": "get_current_time_step_to_None End node_control_flow_edge",
              "description": null,
              "metadata": {},
              "from_node": {
                "$component_ref": "0075a188-518a-48de-aa40-311e2b101db8"
              },
              "from_branch": null,
              "to_node": {
                "$component_ref": "6b29d2c5-02e4-405c-84fd-ab88df514c22"
              }
            }
          ],
          "data_flow_connections": [
            {
              "component_type": "DataFlowEdge",
              "id": "6af5d6e0-a322-419a-adf6-e9aba36cca7c",
              "name": "get_current_time_step_current_time_to_None End node_current_time_data_flow_edge",
              "description": null,
              "metadata": {},
              "source_node": {
                "$component_ref": "0075a188-518a-48de-aa40-311e2b101db8"
              },
              "source_output": "current_time",
              "destination_node": {
                "$component_ref": "6b29d2c5-02e4-405c-84fd-ab88df514c22"
              },
              "destination_input": "current_time"
            }
          ],
          "$referenced_components": {
            "0075a188-518a-48de-aa40-311e2b101db8": {
              "component_type": "ToolNode",
              "id": "0075a188-518a-48de-aa40-311e2b101db8",
              "name": "get_current_time_step",
              "description": "",
              "metadata": {
                "__metadata_info__": {}
              },
              "inputs": [],
              "outputs": [
                {
                  "type": "string",
                  "title": "current_time"
                }
              ],
              "branches": [
                "next"
              ],
              "tool": {
                "component_type": "ServerTool",
                "id": "0cdd153f-4595-48f9-bfc0-7c11ecbda375",
                "name": "get_current_time",
                "description": "Return current time",
                "metadata": {
                  "__metadata_info__": {}
                },
                "inputs": [],
                "outputs": [
                  {
                    "type": "string",
                    "title": "current_time"
                  }
                ],
                "requires_confirmation": false
              }
            },
            "6b29d2c5-02e4-405c-84fd-ab88df514c22": {
              "component_type": "EndNode",
              "id": "6b29d2c5-02e4-405c-84fd-ab88df514c22",
              "name": "None End node",
              "description": "End node representing all transitions to None in the WayFlow flow",
              "metadata": {},
              "inputs": [
                {
                  "type": "string",
                  "title": "current_time"
                }
              ],
              "outputs": [
                {
                  "type": "string",
                  "title": "current_time"
                }
              ],
              "branches": [],
              "branch_name": "next"
            },
            "cddc1061-f534-4182-98a7-a265e9a24d58": {
              "component_type": "StartNode",
              "id": "cddc1061-f534-4182-98a7-a265e9a24d58",
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
          }
        },
        {
          "component_type": "Flow",
          "id": "25337c63-abcd-4361-baf9-bcaa66dcde86",
          "name": "flow_55ed320e__auto",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [
            {
              "type": "string",
              "title": "username"
            }
          ],
          "outputs": [
            {
              "type": "object",
              "additionalProperties": {
                "type": "string"
              },
              "key_type": {
                "type": "string"
              },
              "title": "user_info"
            }
          ],
          "start_node": {
            "$component_ref": "46f7b258-bc5e-4070-9efc-f25d51dfe3da"
          },
          "nodes": [
            {
              "$component_ref": "3ae0dda1-abcc-415c-8103-a07ae8e9bfa2"
            },
            {
              "$component_ref": "46f7b258-bc5e-4070-9efc-f25d51dfe3da"
            },
            {
              "$component_ref": "1fe576de-7456-49ad-965b-5965f6bffe24"
            }
          ],
          "control_flow_connections": [
            {
              "component_type": "ControlFlowEdge",
              "id": "0dfae366-ccfd-46ef-868b-cb5466ee2111",
              "name": "__StartStep___to_get_user_information_step_control_flow_edge",
              "description": null,
              "metadata": {
                "__metadata_info__": {}
              },
              "from_node": {
                "$component_ref": "46f7b258-bc5e-4070-9efc-f25d51dfe3da"
              },
              "from_branch": null,
              "to_node": {
                "$component_ref": "3ae0dda1-abcc-415c-8103-a07ae8e9bfa2"
              }
            },
            {
              "component_type": "ControlFlowEdge",
              "id": "c2f92a97-81c4-4b4c-9a01-d4b57a2ba3eb",
              "name": "get_user_information_step_to_None End node_control_flow_edge",
              "description": null,
              "metadata": {},
              "from_node": {
                "$component_ref": "3ae0dda1-abcc-415c-8103-a07ae8e9bfa2"
              },
              "from_branch": null,
              "to_node": {
                "$component_ref": "1fe576de-7456-49ad-965b-5965f6bffe24"
              }
            }
          ],
          "data_flow_connections": [
            {
              "component_type": "DataFlowEdge",
              "id": "e0584e50-3b3e-4efb-9749-0de208b9188b",
              "name": "__StartStep___username_to_get_user_information_step_username_data_flow_edge",
              "description": null,
              "metadata": {
                "__metadata_info__": {}
              },
              "source_node": {
                "$component_ref": "46f7b258-bc5e-4070-9efc-f25d51dfe3da"
              },
              "source_output": "username",
              "destination_node": {
                "$component_ref": "3ae0dda1-abcc-415c-8103-a07ae8e9bfa2"
              },
              "destination_input": "username"
            },
            {
              "component_type": "DataFlowEdge",
              "id": "145d6cc4-f92e-4303-b5ed-0fc4b2fbfb20",
              "name": "get_user_information_step_user_info_to_None End node_user_info_data_flow_edge",
              "description": null,
              "metadata": {},
              "source_node": {
                "$component_ref": "3ae0dda1-abcc-415c-8103-a07ae8e9bfa2"
              },
              "source_output": "user_info",
              "destination_node": {
                "$component_ref": "1fe576de-7456-49ad-965b-5965f6bffe24"
              },
              "destination_input": "user_info"
            }
          ],
          "$referenced_components": {
            "46f7b258-bc5e-4070-9efc-f25d51dfe3da": {
              "component_type": "StartNode",
              "id": "46f7b258-bc5e-4070-9efc-f25d51dfe3da",
              "name": "__StartStep__",
              "description": "",
              "metadata": {
                "__metadata_info__": {}
              },
              "inputs": [
                {
                  "type": "string",
                  "title": "username"
                }
              ],
              "outputs": [
                {
                  "type": "string",
                  "title": "username"
                }
              ],
              "branches": [
                "next"
              ]
            },
            "3ae0dda1-abcc-415c-8103-a07ae8e9bfa2": {
              "component_type": "ToolNode",
              "id": "3ae0dda1-abcc-415c-8103-a07ae8e9bfa2",
              "name": "get_user_information_step",
              "description": "",
              "metadata": {
                "__metadata_info__": {}
              },
              "inputs": [
                {
                  "type": "string",
                  "title": "username"
                }
              ],
              "outputs": [
                {
                  "type": "object",
                  "additionalProperties": {
                    "type": "string"
                  },
                  "key_type": {
                    "type": "string"
                  },
                  "title": "user_info"
                }
              ],
              "branches": [
                "next"
              ],
              "tool": {
                "component_type": "ServerTool",
                "id": "3faa1afa-e24b-47eb-a49d-4620c00943dc",
                "name": "get_user_information",
                "description": "Retrieve information about a user",
                "metadata": {
                  "__metadata_info__": {}
                },
                "inputs": [
                  {
                    "type": "string",
                    "title": "username"
                  }
                ],
                "outputs": [
                  {
                    "type": "object",
                    "additionalProperties": {
                      "type": "string"
                    },
                    "key_type": {
                      "type": "string"
                    },
                    "title": "user_info"
                  }
                ],
                "requires_confirmation": false
              }
            },
            "1fe576de-7456-49ad-965b-5965f6bffe24": {
              "component_type": "EndNode",
              "id": "1fe576de-7456-49ad-965b-5965f6bffe24",
              "name": "None End node",
              "description": "End node representing all transitions to None in the WayFlow flow",
              "metadata": {},
              "inputs": [
                {
                  "type": "object",
                  "additionalProperties": {
                    "type": "string"
                  },
                  "key_type": {
                    "type": "string"
                  },
                  "title": "user_info"
                }
              ],
              "outputs": [
                {
                  "type": "object",
                  "additionalProperties": {
                    "type": "string"
                  },
                  "key_type": {
                    "type": "string"
                  },
                  "title": "user_info"
                }
              ],
              "branches": [],
              "branch_name": "next"
            }
          }
        },
        {
          "component_type": "Flow",
          "id": "4a2b111b-4fd9-41c1-9f03-c597b24a1fff",
          "name": "flow_10816cad__auto",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [
            {
              "type": "string",
              "title": "username"
            }
          ],
          "outputs": [
            {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": {
                  "type": "string"
                },
                "key_type": {
                  "type": "string"
                }
              },
              "title": "user_purchases"
            }
          ],
          "start_node": {
            "$component_ref": "c9e389a4-0539-430e-b185-1183f6c4591a"
          },
          "nodes": [
            {
              "$component_ref": "829b22e1-ffbd-419e-a863-4edd780a830c"
            },
            {
              "$component_ref": "c9e389a4-0539-430e-b185-1183f6c4591a"
            },
            {
              "$component_ref": "9c866845-1800-4ea8-896f-c1347e21bc3d"
            }
          ],
          "control_flow_connections": [
            {
              "component_type": "ControlFlowEdge",
              "id": "98416c5b-5a24-4d4c-aef5-088c32ce6da0",
              "name": "__StartStep___to_get_user_last_purchases_step_control_flow_edge",
              "description": null,
              "metadata": {
                "__metadata_info__": {}
              },
              "from_node": {
                "$component_ref": "c9e389a4-0539-430e-b185-1183f6c4591a"
              },
              "from_branch": null,
              "to_node": {
                "$component_ref": "829b22e1-ffbd-419e-a863-4edd780a830c"
              }
            },
            {
              "component_type": "ControlFlowEdge",
              "id": "87a14198-b095-4c78-a10c-f85e6b796eb9",
              "name": "get_user_last_purchases_step_to_None End node_control_flow_edge",
              "description": null,
              "metadata": {},
              "from_node": {
                "$component_ref": "829b22e1-ffbd-419e-a863-4edd780a830c"
              },
              "from_branch": null,
              "to_node": {
                "$component_ref": "9c866845-1800-4ea8-896f-c1347e21bc3d"
              }
            }
          ],
          "data_flow_connections": [
            {
              "component_type": "DataFlowEdge",
              "id": "19d26e80-9ad0-4b47-9737-951f58ecf3ff",
              "name": "__StartStep___username_to_get_user_last_purchases_step_username_data_flow_edge",
              "description": null,
              "metadata": {
                "__metadata_info__": {}
              },
              "source_node": {
                "$component_ref": "c9e389a4-0539-430e-b185-1183f6c4591a"
              },
              "source_output": "username",
              "destination_node": {
                "$component_ref": "829b22e1-ffbd-419e-a863-4edd780a830c"
              },
              "destination_input": "username"
            },
            {
              "component_type": "DataFlowEdge",
              "id": "6ec7412a-eab1-43ff-9059-7f9bd77bfe81",
              "name": "get_user_last_purchases_step_user_purchases_to_None End node_user_purchases_data_flow_edge",
              "description": null,
              "metadata": {},
              "source_node": {
                "$component_ref": "829b22e1-ffbd-419e-a863-4edd780a830c"
              },
              "source_output": "user_purchases",
              "destination_node": {
                "$component_ref": "9c866845-1800-4ea8-896f-c1347e21bc3d"
              },
              "destination_input": "user_purchases"
            }
          ],
          "$referenced_components": {
            "c9e389a4-0539-430e-b185-1183f6c4591a": {
              "component_type": "StartNode",
              "id": "c9e389a4-0539-430e-b185-1183f6c4591a",
              "name": "__StartStep__",
              "description": "",
              "metadata": {
                "__metadata_info__": {}
              },
              "inputs": [
                {
                  "type": "string",
                  "title": "username"
                }
              ],
              "outputs": [
                {
                  "type": "string",
                  "title": "username"
                }
              ],
              "branches": [
                "next"
              ]
            },
            "829b22e1-ffbd-419e-a863-4edd780a830c": {
              "component_type": "ToolNode",
              "id": "829b22e1-ffbd-419e-a863-4edd780a830c",
              "name": "get_user_last_purchases_step",
              "description": "",
              "metadata": {
                "__metadata_info__": {}
              },
              "inputs": [
                {
                  "type": "string",
                  "title": "username"
                }
              ],
              "outputs": [
                {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "additionalProperties": {
                      "type": "string"
                    },
                    "key_type": {
                      "type": "string"
                    }
                  },
                  "title": "user_purchases"
                }
              ],
              "branches": [
                "next"
              ],
              "tool": {
                "component_type": "ServerTool",
                "id": "2d39d486-e499-4b14-a8db-a869343afc48",
                "name": "get_user_last_purchases",
                "description": "Retrieve the list of purchases made by a user",
                "metadata": {
                  "__metadata_info__": {}
                },
                "inputs": [
                  {
                    "type": "string",
                    "title": "username"
                  }
                ],
                "outputs": [
                  {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "additionalProperties": {
                        "type": "string"
                      },
                      "key_type": {
                        "type": "string"
                      }
                    },
                    "title": "user_purchases"
                  }
                ],
                "requires_confirmation": false
              }
            },
            "9c866845-1800-4ea8-896f-c1347e21bc3d": {
              "component_type": "EndNode",
              "id": "9c866845-1800-4ea8-896f-c1347e21bc3d",
              "name": "None End node",
              "description": "End node representing all transitions to None in the WayFlow flow",
              "metadata": {},
              "inputs": [
                {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "additionalProperties": {
                      "type": "string"
                    },
                    "key_type": {
                      "type": "string"
                    }
                  },
                  "title": "user_purchases"
                }
              ],
              "outputs": [
                {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "additionalProperties": {
                      "type": "string"
                    },
                    "key_type": {
                      "type": "string"
                    }
                  },
                  "title": "user_purchases"
                }
              ],
              "branches": [],
              "branch_name": "next"
            }
          }
        },
        {
          "component_type": "Flow",
          "id": "9e4ce3d6-a70a-47c2-9a2e-a234dfffd8f0",
          "name": "flow_f16c5a8b__auto",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [],
          "outputs": [
            {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": {
                  "type": "string"
                },
                "key_type": {
                  "type": "string"
                }
              },
              "title": "items_on_sale"
            }
          ],
          "start_node": {
            "$component_ref": "44a44892-848f-4b54-96e7-721950b0d849"
          },
          "nodes": [
            {
              "$component_ref": "3e5b0ee2-5a53-4911-b07b-6e10134b6f77"
            },
            {
              "$component_ref": "44a44892-848f-4b54-96e7-721950b0d849"
            },
            {
              "$component_ref": "b38ffcaf-ea0f-4852-8fea-4e82398e9c3b"
            }
          ],
          "control_flow_connections": [
            {
              "component_type": "ControlFlowEdge",
              "id": "5645365f-aa37-4848-9442-bdf25a8318f2",
              "name": "__StartStep___to_get_items_on_sale_steo_control_flow_edge",
              "description": null,
              "metadata": {
                "__metadata_info__": {}
              },
              "from_node": {
                "$component_ref": "44a44892-848f-4b54-96e7-721950b0d849"
              },
              "from_branch": null,
              "to_node": {
                "$component_ref": "3e5b0ee2-5a53-4911-b07b-6e10134b6f77"
              }
            },
            {
              "component_type": "ControlFlowEdge",
              "id": "2e82699e-cd5f-4df2-b2e5-998b17329078",
              "name": "get_items_on_sale_steo_to_None End node_control_flow_edge",
              "description": null,
              "metadata": {},
              "from_node": {
                "$component_ref": "3e5b0ee2-5a53-4911-b07b-6e10134b6f77"
              },
              "from_branch": null,
              "to_node": {
                "$component_ref": "b38ffcaf-ea0f-4852-8fea-4e82398e9c3b"
              }
            }
          ],
          "data_flow_connections": [
            {
              "component_type": "DataFlowEdge",
              "id": "1cb11a04-8b4a-4cda-83fe-0ceeab6474ea",
              "name": "get_items_on_sale_steo_items_on_sale_to_None End node_items_on_sale_data_flow_edge",
              "description": null,
              "metadata": {},
              "source_node": {
                "$component_ref": "3e5b0ee2-5a53-4911-b07b-6e10134b6f77"
              },
              "source_output": "items_on_sale",
              "destination_node": {
                "$component_ref": "b38ffcaf-ea0f-4852-8fea-4e82398e9c3b"
              },
              "destination_input": "items_on_sale"
            }
          ],
          "$referenced_components": {
            "3e5b0ee2-5a53-4911-b07b-6e10134b6f77": {
              "component_type": "ToolNode",
              "id": "3e5b0ee2-5a53-4911-b07b-6e10134b6f77",
              "name": "get_items_on_sale_steo",
              "description": "",
              "metadata": {
                "__metadata_info__": {}
              },
              "inputs": [],
              "outputs": [
                {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "additionalProperties": {
                      "type": "string"
                    },
                    "key_type": {
                      "type": "string"
                    }
                  },
                  "title": "items_on_sale"
                }
              ],
              "branches": [
                "next"
              ],
              "tool": {
                "component_type": "ServerTool",
                "id": "a316b69c-8e5d-4b09-bff2-35fccd48048a",
                "name": "get_items_on_sale",
                "description": "Retrieve the list of items currently on sale",
                "metadata": {
                  "__metadata_info__": {}
                },
                "inputs": [],
                "outputs": [
                  {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "additionalProperties": {
                        "type": "string"
                      },
                      "key_type": {
                        "type": "string"
                      }
                    },
                    "title": "items_on_sale"
                  }
                ],
                "requires_confirmation": false
              }
            },
            "b38ffcaf-ea0f-4852-8fea-4e82398e9c3b": {
              "component_type": "EndNode",
              "id": "b38ffcaf-ea0f-4852-8fea-4e82398e9c3b",
              "name": "None End node",
              "description": "End node representing all transitions to None in the WayFlow flow",
              "metadata": {},
              "inputs": [
                {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "additionalProperties": {
                      "type": "string"
                    },
                    "key_type": {
                      "type": "string"
                    }
                  },
                  "title": "items_on_sale"
                }
              ],
              "outputs": [
                {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "additionalProperties": {
                      "type": "string"
                    },
                    "key_type": {
                      "type": "string"
                    }
                  },
                  "title": "items_on_sale"
                }
              ],
              "branches": [],
              "branch_name": "next"
            },
            "44a44892-848f-4b54-96e7-721950b0d849": {
              "component_type": "StartNode",
              "id": "44a44892-848f-4b54-96e7-721950b0d849",
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
          }
        }
      ],
      "max_workers": null,
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "26.1.0.dev0"
    },
    "b3642f57-f4da-4023-96dd-3916bc931b68": {
      "component_type": "LlmNode",
      "id": "b3642f57-f4da-4023-96dd-3916bc931b68",
      "name": "prepare_marketing_message",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "\"user_info\" input variable for the template",
          "type": "string",
          "title": "user_info"
        },
        {
          "description": "\"current_time\" input variable for the template",
          "type": "string",
          "title": "current_time"
        },
        {
          "description": "\"user_purchases\" input variable for the template",
          "type": "string",
          "title": "user_purchases"
        },
        {
          "description": "\"items_on_sale\" input variable for the template",
          "type": "string",
          "title": "items_on_sale"
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
        "id": "deb3fd81-b199-4611-925d-01e22192f5c7",
        "name": "llm_c9adb3b0__auto",
        "description": null,
        "metadata": {
          "__metadata_info__": {}
        },
        "default_generation_parameters": null,
        "url": "LLAMA_API_URL",
        "model_id": "LLAMA_MODEL_ID"
      },
      "prompt_template": "# Instructions\n\nYou are a marketing expert. You have to write a welcome message for a user.\n\nThe message must contain:\n- A first sentence of greetings, including user's name, and personalized in case it's user's birthday\n- A proposal containing something to buy\n \nThe purchase proposal must be:\n- aligned with user's purchase history\n- part of the list of items on sale\n\n# User information\n\n{{user_info}}\n\nNote that the current time to check the birthday is: {{current_time}}\n\nThe list of items purchased by the user is:\n{{user_purchases}}\n\n# Items on sale\n\n{{items_on_sale}}\n\nPlease write the welcome message for the user.\nDo not give me the instructions to do it, I want only the final message to send.  \n"
    },
    "6594c3ef-67d2-4dfd-96a4-328a9fad8443": {
      "component_type": "PluginOutputMessageNode",
      "id": "6594c3ef-67d2-4dfd-96a4-328a9fad8443",
      "name": "output_message_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "\"output\" input variable for the template",
          "type": "string",
          "title": "output"
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
      "message": "{{output}}",
      "input_mapping": {},
      "output_mapping": {},
      "message_type": "AGENT",
      "rephrase": false,
      "llm_config": null,
      "expose_message_as_output": true,
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "26.1.0.dev0"
    },
    "ddcf926c-bce7-4050-a5f0-0a3da2110b52": {
      "component_type": "StartNode",
      "id": "ddcf926c-bce7-4050-a5f0-0a3da2110b52",
      "name": "__StartStep__",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "string",
          "title": "username"
        }
      ],
      "outputs": [
        {
          "type": "string",
          "title": "username"
        }
      ],
      "branches": [
        "next"
      ]
    },
    "e8563485-edec-4ba2-ba13-4e2636e6de6c": {
      "component_type": "EndNode",
      "id": "e8563485-edec-4ba2-ba13-4e2636e6de6c",
      "name": "None End node",
      "description": "End node representing all transitions to None in the WayFlow flow",
      "metadata": {},
      "inputs": [
        {
          "type": "object",
          "additionalProperties": {
            "type": "string"
          },
          "key_type": {
            "type": "string"
          },
          "title": "user_info"
        },
        {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": {
              "type": "string"
            },
            "key_type": {
              "type": "string"
            }
          },
          "title": "items_on_sale"
        },
        {
          "description": "the message added to the messages list",
          "type": "string",
          "title": "output_message"
        },
        {
          "type": "string",
          "title": "current_time"
        },
        {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": {
              "type": "string"
            },
            "key_type": {
              "type": "string"
            }
          },
          "title": "user_purchases"
        },
        {
          "description": "the generated text",
          "type": "string",
          "title": "output"
        }
      ],
      "outputs": [
        {
          "type": "object",
          "additionalProperties": {
            "type": "string"
          },
          "key_type": {
            "type": "string"
          },
          "title": "user_info"
        },
        {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": {
              "type": "string"
            },
            "key_type": {
              "type": "string"
            }
          },
          "title": "items_on_sale"
        },
        {
          "description": "the message added to the messages list",
          "type": "string",
          "title": "output_message"
        },
        {
          "type": "string",
          "title": "current_time"
        },
        {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": {
              "type": "string"
            },
            "key_type": {
              "type": "string"
            }
          },
          "title": "user_purchases"
        },
        {
          "description": "the generated text",
          "type": "string",
          "title": "output"
        }
      ],
      "branches": [],
      "branch_name": "next"
    }
  },
  "agentspec_version": "25.4.2"
}
```

YAML

```yaml
component_type: Flow
id: 9a1d50ff-401f-4eee-b757-4568f034da60
name: flow_ba0ca7d7__auto
description: ''
metadata:
  __metadata_info__: {}
inputs:
- type: string
  title: username
outputs:
- description: the generated text
  type: string
  title: output
- type: string
  title: current_time
- description: the message added to the messages list
  type: string
  title: output_message
- type: array
  items:
    type: object
    additionalProperties:
      type: string
    key_type:
      type: string
  title: user_purchases
- type: object
  additionalProperties:
    type: string
  key_type:
    type: string
  title: user_info
- type: array
  items:
    type: object
    additionalProperties:
      type: string
    key_type:
      type: string
  title: items_on_sale
start_node:
  $component_ref: 7ad04ec0-30e4-4f8d-b530-7c053a12d161
nodes:
- $component_ref: 3c2162e5-fc1d-4517-99fc-d4e1719a1311
- $component_ref: c9973ecb-029a-4302-adc1-0962dfdd4cf1
- $component_ref: 16309b0f-cb5b-4bfc-999f-b083dd28bba2
- $component_ref: 7ad04ec0-30e4-4f8d-b530-7c053a12d161
- $component_ref: ec3a335f-c612-4c68-bd8d-e3c61aa20169
control_flow_connections:
- component_type: ControlFlowEdge
  id: e9bd2c99-a5b3-4829-abfc-9ec93088f405
  name: parallel_flow_step_to_prepare_marketing_message_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 3c2162e5-fc1d-4517-99fc-d4e1719a1311
  from_branch: null
  to_node:
    $component_ref: c9973ecb-029a-4302-adc1-0962dfdd4cf1
- component_type: ControlFlowEdge
  id: a3326936-b0a1-4260-8432-4f90da974729
  name: prepare_marketing_message_to_output_message_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: c9973ecb-029a-4302-adc1-0962dfdd4cf1
  from_branch: null
  to_node:
    $component_ref: 16309b0f-cb5b-4bfc-999f-b083dd28bba2
- component_type: ControlFlowEdge
  id: 36921d31-06e1-4274-9f79-21773bbf8fcd
  name: __StartStep___to_parallel_flow_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 7ad04ec0-30e4-4f8d-b530-7c053a12d161
  from_branch: null
  to_node:
    $component_ref: 3c2162e5-fc1d-4517-99fc-d4e1719a1311
- component_type: ControlFlowEdge
  id: cc937bf8-8639-4b57-8a7a-3bc8a4c30119
  name: output_message_step_to_None End node_control_flow_edge
  description: null
  metadata: {}
  from_node:
    $component_ref: 16309b0f-cb5b-4bfc-999f-b083dd28bba2
  from_branch: null
  to_node:
    $component_ref: ec3a335f-c612-4c68-bd8d-e3c61aa20169
data_flow_connections:
- component_type: DataFlowEdge
  id: 224b181b-6f21-4e83-bea5-3c2af09b68df
  name: parallel_flow_step_user_info_to_prepare_marketing_message_user_info_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 3c2162e5-fc1d-4517-99fc-d4e1719a1311
  source_output: user_info
  destination_node:
    $component_ref: c9973ecb-029a-4302-adc1-0962dfdd4cf1
  destination_input: user_info
- component_type: DataFlowEdge
  id: cf335795-fe15-4d11-996b-0b16197289dc
  name: parallel_flow_step_current_time_to_prepare_marketing_message_current_time_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 3c2162e5-fc1d-4517-99fc-d4e1719a1311
  source_output: current_time
  destination_node:
    $component_ref: c9973ecb-029a-4302-adc1-0962dfdd4cf1
  destination_input: current_time
- component_type: DataFlowEdge
  id: af7435c8-73e1-42c1-bbdb-79c02923c9cd
  name: parallel_flow_step_user_purchases_to_prepare_marketing_message_user_purchases_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 3c2162e5-fc1d-4517-99fc-d4e1719a1311
  source_output: user_purchases
  destination_node:
    $component_ref: c9973ecb-029a-4302-adc1-0962dfdd4cf1
  destination_input: user_purchases
- component_type: DataFlowEdge
  id: 95a14d48-fc86-4c97-86fe-4c57cf699fee
  name: parallel_flow_step_items_on_sale_to_prepare_marketing_message_items_on_sale_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 3c2162e5-fc1d-4517-99fc-d4e1719a1311
  source_output: items_on_sale
  destination_node:
    $component_ref: c9973ecb-029a-4302-adc1-0962dfdd4cf1
  destination_input: items_on_sale
- component_type: DataFlowEdge
  id: feade911-73eb-4ffc-9926-8c9bddd7a0e4
  name: prepare_marketing_message_output_to_output_message_step_output_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: c9973ecb-029a-4302-adc1-0962dfdd4cf1
  source_output: output
  destination_node:
    $component_ref: 16309b0f-cb5b-4bfc-999f-b083dd28bba2
  destination_input: output
- component_type: DataFlowEdge
  id: 543bd23e-2bbf-4e42-b96d-8df96ff588c4
  name: __StartStep___username_to_parallel_flow_step_username_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 7ad04ec0-30e4-4f8d-b530-7c053a12d161
  source_output: username
  destination_node:
    $component_ref: 3c2162e5-fc1d-4517-99fc-d4e1719a1311
  destination_input: username
- component_type: DataFlowEdge
  id: 1e9aedc6-8b79-40f8-b873-88aceba21c07
  name: prepare_marketing_message_output_to_None End node_output_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: c9973ecb-029a-4302-adc1-0962dfdd4cf1
  source_output: output
  destination_node:
    $component_ref: ec3a335f-c612-4c68-bd8d-e3c61aa20169
  destination_input: output
- component_type: DataFlowEdge
  id: 374db01e-8906-47d2-ad44-b0014ce0b5ea
  name: parallel_flow_step_current_time_to_None End node_current_time_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 3c2162e5-fc1d-4517-99fc-d4e1719a1311
  source_output: current_time
  destination_node:
    $component_ref: ec3a335f-c612-4c68-bd8d-e3c61aa20169
  destination_input: current_time
- component_type: DataFlowEdge
  id: 4814b63c-062d-4740-bc55-1b73b37fafe6
  name: output_message_step_output_message_to_None End node_output_message_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 16309b0f-cb5b-4bfc-999f-b083dd28bba2
  source_output: output_message
  destination_node:
    $component_ref: ec3a335f-c612-4c68-bd8d-e3c61aa20169
  destination_input: output_message
- component_type: DataFlowEdge
  id: a58cb9bc-e326-4862-a7c0-e6301199f788
  name: parallel_flow_step_user_purchases_to_None End node_user_purchases_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 3c2162e5-fc1d-4517-99fc-d4e1719a1311
  source_output: user_purchases
  destination_node:
    $component_ref: ec3a335f-c612-4c68-bd8d-e3c61aa20169
  destination_input: user_purchases
- component_type: DataFlowEdge
  id: 38b9f912-d657-4e3e-9bfe-3c9db11fbd98
  name: parallel_flow_step_user_info_to_None End node_user_info_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 3c2162e5-fc1d-4517-99fc-d4e1719a1311
  source_output: user_info
  destination_node:
    $component_ref: ec3a335f-c612-4c68-bd8d-e3c61aa20169
  destination_input: user_info
- component_type: DataFlowEdge
  id: 15dd8804-63c5-4b42-be49-4052a7ef71f8
  name: parallel_flow_step_items_on_sale_to_None End node_items_on_sale_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 3c2162e5-fc1d-4517-99fc-d4e1719a1311
  source_output: items_on_sale
  destination_node:
    $component_ref: ec3a335f-c612-4c68-bd8d-e3c61aa20169
  destination_input: items_on_sale
$referenced_components:
  3c2162e5-fc1d-4517-99fc-d4e1719a1311:
    component_type: ExtendedParallelFlowNode
    id: 3c2162e5-fc1d-4517-99fc-d4e1719a1311
    name: parallel_flow_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: string
      title: username
    outputs:
    - type: string
      title: current_time
    - type: object
      additionalProperties:
        type: string
      key_type:
        type: string
      title: user_info
    - type: array
      items:
        type: object
        additionalProperties:
          type: string
        key_type:
          type: string
      title: user_purchases
    - type: array
      items:
        type: object
        additionalProperties:
          type: string
        key_type:
          type: string
      title: items_on_sale
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    flows:
    - component_type: Flow
      id: 830804f1-98aa-498e-97bb-f50693f65adc
      name: flow_e65028d9__auto
      description: ''
      metadata:
        __metadata_info__: {}
      inputs: []
      outputs:
      - type: string
        title: current_time
      start_node:
        $component_ref: 1372cf28-a4d5-4783-8e2e-17b3085b4b84
      nodes:
      - $component_ref: 1180cdb1-4e40-4c79-a656-efd445724ece
      - $component_ref: 1372cf28-a4d5-4783-8e2e-17b3085b4b84
      - $component_ref: 3439aa54-f922-4142-b73e-62701dc00420
      control_flow_connections:
      - component_type: ControlFlowEdge
        id: f16f4ce1-d0ab-4287-b3d1-0f68eec10652
        name: __StartStep___to_get_current_time_step_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: 1372cf28-a4d5-4783-8e2e-17b3085b4b84
        from_branch: null
        to_node:
          $component_ref: 1180cdb1-4e40-4c79-a656-efd445724ece
      - component_type: ControlFlowEdge
        id: 38d4dac5-4b38-42fd-ba37-a42ee7207927
        name: get_current_time_step_to_None End node_control_flow_edge
        description: null
        metadata: {}
        from_node:
          $component_ref: 1180cdb1-4e40-4c79-a656-efd445724ece
        from_branch: null
        to_node:
          $component_ref: 3439aa54-f922-4142-b73e-62701dc00420
      data_flow_connections:
      - component_type: DataFlowEdge
        id: 8be71bef-c2bd-4503-bb95-0c6d6785136f
        name: get_current_time_step_current_time_to_None End node_current_time_data_flow_edge
        description: null
        metadata: {}
        source_node:
          $component_ref: 1180cdb1-4e40-4c79-a656-efd445724ece
        source_output: current_time
        destination_node:
          $component_ref: 3439aa54-f922-4142-b73e-62701dc00420
        destination_input: current_time
      $referenced_components:
        1180cdb1-4e40-4c79-a656-efd445724ece:
          component_type: ToolNode
          id: 1180cdb1-4e40-4c79-a656-efd445724ece
          name: get_current_time_step
          description: ''
          metadata:
            __metadata_info__: {}
          inputs: []
          outputs:
          - type: string
            title: current_time
          branches:
          - next
          tool:
            component_type: ServerTool
            id: d5cf47f4-da0e-49f5-8d2f-6f4e3ce6ce09
            name: get_current_time
            description: Return current time
            metadata:
              __metadata_info__: {}
            inputs: []
            outputs:
            - type: string
              title: current_time
            requires_confirmation: false
        3439aa54-f922-4142-b73e-62701dc00420:
          component_type: EndNode
          id: 3439aa54-f922-4142-b73e-62701dc00420
          name: None End node
          description: End node representing all transitions to None in the WayFlow
            flow
          metadata: {}
          inputs:
          - type: string
            title: current_time
          outputs:
          - type: string
            title: current_time
          branches: []
          branch_name: next
        1372cf28-a4d5-4783-8e2e-17b3085b4b84:
          component_type: StartNode
          id: 1372cf28-a4d5-4783-8e2e-17b3085b4b84
          name: __StartStep__
          description: ''
          metadata:
            __metadata_info__: {}
          inputs: []
          outputs: []
          branches:
          - next
    - component_type: Flow
      id: 756e38b4-96cd-4c2a-8a3b-563e2f5f4f79
      name: flow_27983d79__auto
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - type: string
        title: username
      outputs:
      - type: object
        additionalProperties:
          type: string
        key_type:
          type: string
        title: user_info
      start_node:
        $component_ref: eb78a9c7-6a69-4f0c-b149-38fba2072de7
      nodes:
      - $component_ref: 2d6f3d55-12a2-44e6-a646-373c4008d889
      - $component_ref: eb78a9c7-6a69-4f0c-b149-38fba2072de7
      - $component_ref: b35aae7d-ceed-4726-8fc6-19a8541780be
      control_flow_connections:
      - component_type: ControlFlowEdge
        id: 5a418667-d9a0-44a5-a5d9-c8205b1e7cb3
        name: __StartStep___to_get_user_information_step_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: eb78a9c7-6a69-4f0c-b149-38fba2072de7
        from_branch: null
        to_node:
          $component_ref: 2d6f3d55-12a2-44e6-a646-373c4008d889
      - component_type: ControlFlowEdge
        id: a108a7f7-75b0-4582-a187-6092aa0097bc
        name: get_user_information_step_to_None End node_control_flow_edge
        description: null
        metadata: {}
        from_node:
          $component_ref: 2d6f3d55-12a2-44e6-a646-373c4008d889
        from_branch: null
        to_node:
          $component_ref: b35aae7d-ceed-4726-8fc6-19a8541780be
      data_flow_connections:
      - component_type: DataFlowEdge
        id: 073c7fb0-60f9-44ff-93d7-ab804b7e26a5
        name: __StartStep___username_to_get_user_information_step_username_data_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        source_node:
          $component_ref: eb78a9c7-6a69-4f0c-b149-38fba2072de7
        source_output: username
        destination_node:
          $component_ref: 2d6f3d55-12a2-44e6-a646-373c4008d889
        destination_input: username
      - component_type: DataFlowEdge
        id: 056f1436-7721-4249-b627-254468c70014
        name: get_user_information_step_user_info_to_None End node_user_info_data_flow_edge
        description: null
        metadata: {}
        source_node:
          $component_ref: 2d6f3d55-12a2-44e6-a646-373c4008d889
        source_output: user_info
        destination_node:
          $component_ref: b35aae7d-ceed-4726-8fc6-19a8541780be
        destination_input: user_info
      $referenced_components:
        eb78a9c7-6a69-4f0c-b149-38fba2072de7:
          component_type: StartNode
          id: eb78a9c7-6a69-4f0c-b149-38fba2072de7
          name: __StartStep__
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - type: string
            title: username
          outputs:
          - type: string
            title: username
          branches:
          - next
        2d6f3d55-12a2-44e6-a646-373c4008d889:
          component_type: ToolNode
          id: 2d6f3d55-12a2-44e6-a646-373c4008d889
          name: get_user_information_step
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - type: string
            title: username
          outputs:
          - type: object
            additionalProperties:
              type: string
            key_type:
              type: string
            title: user_info
          branches:
          - next
          tool:
            component_type: ServerTool
            id: 63901325-0817-49d3-a75b-fc7caa904150
            name: get_user_information
            description: Retrieve information about a user
            metadata:
              __metadata_info__: {}
            inputs:
            - type: string
              title: username
            outputs:
            - type: object
              additionalProperties:
                type: string
              key_type:
                type: string
              title: user_info
            requires_confirmation: false
        b35aae7d-ceed-4726-8fc6-19a8541780be:
          component_type: EndNode
          id: b35aae7d-ceed-4726-8fc6-19a8541780be
          name: None End node
          description: End node representing all transitions to None in the WayFlow
            flow
          metadata: {}
          inputs:
          - type: object
            additionalProperties:
              type: string
            key_type:
              type: string
            title: user_info
          outputs:
          - type: object
            additionalProperties:
              type: string
            key_type:
              type: string
            title: user_info
          branches: []
          branch_name: next
    - component_type: Flow
      id: c493c674-aa35-47a5-8e23-d2c4a4c422e9
      name: flow_caf4c68e__auto
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - type: string
        title: username
      outputs:
      - type: array
        items:
          type: object
          additionalProperties:
            type: string
          key_type:
            type: string
        title: user_purchases
      start_node:
        $component_ref: 8e2d6a74-f4f3-4eda-9b41-89dd159cfc32
      nodes:
      - $component_ref: da051da6-84d4-462b-9361-3bdb82158996
      - $component_ref: 8e2d6a74-f4f3-4eda-9b41-89dd159cfc32
      - $component_ref: 72a32d3f-d122-4f5a-bea6-57a72d41b5cc
      control_flow_connections:
      - component_type: ControlFlowEdge
        id: 7e3d5721-e733-46fe-8813-75c87757c5be
        name: __StartStep___to_get_user_last_purchases_step_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: 8e2d6a74-f4f3-4eda-9b41-89dd159cfc32
        from_branch: null
        to_node:
          $component_ref: da051da6-84d4-462b-9361-3bdb82158996
      - component_type: ControlFlowEdge
        id: 7098c560-8a6d-47e3-bccc-382610df834c
        name: get_user_last_purchases_step_to_None End node_control_flow_edge
        description: null
        metadata: {}
        from_node:
          $component_ref: da051da6-84d4-462b-9361-3bdb82158996
        from_branch: null
        to_node:
          $component_ref: 72a32d3f-d122-4f5a-bea6-57a72d41b5cc
      data_flow_connections:
      - component_type: DataFlowEdge
        id: 100de096-d0bd-4b1e-92ca-1a14112b1a93
        name: __StartStep___username_to_get_user_last_purchases_step_username_data_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        source_node:
          $component_ref: 8e2d6a74-f4f3-4eda-9b41-89dd159cfc32
        source_output: username
        destination_node:
          $component_ref: da051da6-84d4-462b-9361-3bdb82158996
        destination_input: username
      - component_type: DataFlowEdge
        id: 7ce979c8-e90e-4c0e-a47a-b05fb1ca15e7
        name: get_user_last_purchases_step_user_purchases_to_None End node_user_purchases_data_flow_edge
        description: null
        metadata: {}
        source_node:
          $component_ref: da051da6-84d4-462b-9361-3bdb82158996
        source_output: user_purchases
        destination_node:
          $component_ref: 72a32d3f-d122-4f5a-bea6-57a72d41b5cc
        destination_input: user_purchases
      $referenced_components:
        8e2d6a74-f4f3-4eda-9b41-89dd159cfc32:
          component_type: StartNode
          id: 8e2d6a74-f4f3-4eda-9b41-89dd159cfc32
          name: __StartStep__
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - type: string
            title: username
          outputs:
          - type: string
            title: username
          branches:
          - next
        da051da6-84d4-462b-9361-3bdb82158996:
          component_type: ToolNode
          id: da051da6-84d4-462b-9361-3bdb82158996
          name: get_user_last_purchases_step
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - type: string
            title: username
          outputs:
          - type: array
            items:
              type: object
              additionalProperties:
                type: string
              key_type:
                type: string
            title: user_purchases
          branches:
          - next
          tool:
            component_type: ServerTool
            id: 5f7e2292-e5c3-43ed-a52a-bc44fc5a68f8
            name: get_user_last_purchases
            description: Retrieve the list of purchases made by a user
            metadata:
              __metadata_info__: {}
            inputs:
            - type: string
              title: username
            outputs:
            - type: array
              items:
                type: object
                additionalProperties:
                  type: string
                key_type:
                  type: string
              title: user_purchases
            requires_confirmation: false
        72a32d3f-d122-4f5a-bea6-57a72d41b5cc:
          component_type: EndNode
          id: 72a32d3f-d122-4f5a-bea6-57a72d41b5cc
          name: None End node
          description: End node representing all transitions to None in the WayFlow
            flow
          metadata: {}
          inputs:
          - type: array
            items:
              type: object
              additionalProperties:
                type: string
              key_type:
                type: string
            title: user_purchases
          outputs:
          - type: array
            items:
              type: object
              additionalProperties:
                type: string
              key_type:
                type: string
            title: user_purchases
          branches: []
          branch_name: next
    - component_type: Flow
      id: 0d53e3b4-cd79-4fce-8114-5a8cb1fd9668
      name: flow_04bf21f9__auto
      description: ''
      metadata:
        __metadata_info__: {}
      inputs: []
      outputs:
      - type: array
        items:
          type: object
          additionalProperties:
            type: string
          key_type:
            type: string
        title: items_on_sale
      start_node:
        $component_ref: eb9f223a-41de-478a-b0ff-0513fea6efcb
      nodes:
      - $component_ref: 8f29c168-e6af-4c5c-91cf-c59909dcf851
      - $component_ref: eb9f223a-41de-478a-b0ff-0513fea6efcb
      - $component_ref: 8bd01b94-27d4-46f4-8d13-d6f1663daca4
      control_flow_connections:
      - component_type: ControlFlowEdge
        id: d58297bc-1064-436c-b1d6-769469ec5884
        name: __StartStep___to_get_items_on_sale_steo_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: eb9f223a-41de-478a-b0ff-0513fea6efcb
        from_branch: null
        to_node:
          $component_ref: 8f29c168-e6af-4c5c-91cf-c59909dcf851
      - component_type: ControlFlowEdge
        id: 3b4ff4ce-9159-4544-a882-c11f7a9c0cd0
        name: get_items_on_sale_steo_to_None End node_control_flow_edge
        description: null
        metadata: {}
        from_node:
          $component_ref: 8f29c168-e6af-4c5c-91cf-c59909dcf851
        from_branch: null
        to_node:
          $component_ref: 8bd01b94-27d4-46f4-8d13-d6f1663daca4
      data_flow_connections:
      - component_type: DataFlowEdge
        id: 5f22125b-1b81-4ab0-b21a-d1db6003bfe0
        name: get_items_on_sale_steo_items_on_sale_to_None End node_items_on_sale_data_flow_edge
        description: null
        metadata: {}
        source_node:
          $component_ref: 8f29c168-e6af-4c5c-91cf-c59909dcf851
        source_output: items_on_sale
        destination_node:
          $component_ref: 8bd01b94-27d4-46f4-8d13-d6f1663daca4
        destination_input: items_on_sale
      $referenced_components:
        8f29c168-e6af-4c5c-91cf-c59909dcf851:
          component_type: ToolNode
          id: 8f29c168-e6af-4c5c-91cf-c59909dcf851
          name: get_items_on_sale_steo
          description: ''
          metadata:
            __metadata_info__: {}
          inputs: []
          outputs:
          - type: array
            items:
              type: object
              additionalProperties:
                type: string
              key_type:
                type: string
            title: items_on_sale
          branches:
          - next
          tool:
            component_type: ServerTool
            id: a9692dfa-3310-4f80-adc3-71e294eeac5d
            name: get_items_on_sale
            description: Retrieve the list of items currently on sale
            metadata:
              __metadata_info__: {}
            inputs: []
            outputs:
            - type: array
              items:
                type: object
                additionalProperties:
                  type: string
                key_type:
                  type: string
              title: items_on_sale
            requires_confirmation: false
        8bd01b94-27d4-46f4-8d13-d6f1663daca4:
          component_type: EndNode
          id: 8bd01b94-27d4-46f4-8d13-d6f1663daca4
          name: None End node
          description: End node representing all transitions to None in the WayFlow
            flow
          metadata: {}
          inputs:
          - type: array
            items:
              type: object
              additionalProperties:
                type: string
              key_type:
                type: string
            title: items_on_sale
          outputs:
          - type: array
            items:
              type: object
              additionalProperties:
                type: string
              key_type:
                type: string
            title: items_on_sale
          branches: []
          branch_name: next
        eb9f223a-41de-478a-b0ff-0513fea6efcb:
          component_type: StartNode
          id: eb9f223a-41de-478a-b0ff-0513fea6efcb
          name: __StartStep__
          description: ''
          metadata:
            __metadata_info__: {}
          inputs: []
          outputs: []
          branches:
          - next
    max_workers: null
    component_plugin_name: NodesPlugin
    component_plugin_version: 26.1.0.dev0
  c9973ecb-029a-4302-adc1-0962dfdd4cf1:
    component_type: LlmNode
    id: c9973ecb-029a-4302-adc1-0962dfdd4cf1
    name: prepare_marketing_message
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: '"user_info" input variable for the template'
      type: string
      title: user_info
    - description: '"current_time" input variable for the template'
      type: string
      title: current_time
    - description: '"user_purchases" input variable for the template'
      type: string
      title: user_purchases
    - description: '"items_on_sale" input variable for the template'
      type: string
      title: items_on_sale
    outputs:
    - description: the generated text
      type: string
      title: output
    branches:
    - next
    llm_config:
      component_type: VllmConfig
      id: c8de93e2-7b26-4894-96dc-534b8a6ed5a7
      name: llm_01a5da8e__auto
      description: null
      metadata:
        __metadata_info__: {}
      default_generation_parameters: null
      url: LLAMA_API_URL
      model_id: LLAMA_MODEL_ID
    prompt_template: "# Instructions\n\nYou are a marketing expert. You have to write\
      \ a welcome message for a user.\n\nThe message must contain:\n- A first sentence\
      \ of greetings, including user's name, and personalized in case it's user's\
      \ birthday\n- A proposal containing something to buy\n \nThe purchase proposal\
      \ must be:\n- aligned with user's purchase history\n- part of the list of items\
      \ on sale\n\n# User information\n\n{{user_info}}\n\nNote that the current time\
      \ to check the birthday is: {{current_time}}\n\nThe list of items purchased\
      \ by the user is:\n{{user_purchases}}\n\n# Items on sale\n\n{{items_on_sale}}\n\
      \nPlease write the welcome message for the user.\nDo not give me the instructions\
      \ to do it, I want only the final message to send.  \n"
  16309b0f-cb5b-4bfc-999f-b083dd28bba2:
    component_type: PluginOutputMessageNode
    id: 16309b0f-cb5b-4bfc-999f-b083dd28bba2
    name: output_message_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: '"output" input variable for the template'
      type: string
      title: output
    outputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    branches:
    - next
    message: '{{output}}'
    input_mapping: {}
    output_mapping: {}
    message_type: AGENT
    rephrase: false
    llm_config: null
    expose_message_as_output: true
    component_plugin_name: NodesPlugin
    component_plugin_version: 26.1.0.dev0
  7ad04ec0-30e4-4f8d-b530-7c053a12d161:
    component_type: StartNode
    id: 7ad04ec0-30e4-4f8d-b530-7c053a12d161
    name: __StartStep__
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: string
      title: username
    outputs:
    - type: string
      title: username
    branches:
    - next
  ec3a335f-c612-4c68-bd8d-e3c61aa20169:
    component_type: EndNode
    id: ec3a335f-c612-4c68-bd8d-e3c61aa20169
    name: None End node
    description: End node representing all transitions to None in the WayFlow flow
    metadata: {}
    inputs:
    - description: the generated text
      type: string
      title: output
    - type: string
      title: current_time
    - description: the message added to the messages list
      type: string
      title: output_message
    - type: array
      items:
        type: object
        additionalProperties:
          type: string
        key_type:
          type: string
      title: user_purchases
    - type: object
      additionalProperties:
        type: string
      key_type:
        type: string
      title: user_info
    - type: array
      items:
        type: object
        additionalProperties:
          type: string
        key_type:
          type: string
      title: items_on_sale
    outputs:
    - description: the generated text
      type: string
      title: output
    - type: string
      title: current_time
    - description: the message added to the messages list
      type: string
      title: output_message
    - type: array
      items:
        type: object
        additionalProperties:
          type: string
        key_type:
          type: string
      title: user_purchases
    - type: object
      additionalProperties:
        type: string
      key_type:
        type: string
      title: user_info
    - type: array
      items:
        type: object
        additionalProperties:
          type: string
        key_type:
          type: string
      title: items_on_sale
    branches: []
    branch_name: next
agentspec_version: 25.4.2
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {
    "get_user_information": get_user_information,
    "get_current_time": get_current_time,
    "get_user_last_purchases": get_user_last_purchases,
    "get_items_on_sale": get_items_on_sale,
}
flow = AgentSpecLoader(tool_registry=tool_registry).load_json(serialized_flow)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `ExtendedParallelFlowNode`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Next steps

Having learned how to perform generic parallel operations in WayFlow, you may now proceed to
[How to Do Map and Reduce Operations in Flows](howto_mapstep.md).

## Full code

Click on the card at the [top of this page](#top-howtoparallelflowexecution) to download the full code
for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to Run Multiple Flows in Parallel
# ------------------------------------------------------------

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
# python howto_parallelflowexecution.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Define the tools

# %%
from wayflowcore.property import DictProperty, ListProperty, StringProperty
from wayflowcore.tools.toolhelpers import DescriptionMode, tool


@tool(
    description_mode=DescriptionMode.ONLY_DOCSTRING,
    output_descriptors=[DictProperty(name="user_info", value_type=StringProperty())],
)
def get_user_information(username: str) -> dict[str, str]:
    """Retrieve information about a user"""
    return {
        "alice": {"name": "Alice", "email": "alice@email.com", "date_of_birth": "1980/05/01"},
        "bob": {"name": "Bob", "email": "bob@email.com", "date_of_birth": "1970/10/01"},
    }.get(username, {})


@tool(
    description_mode=DescriptionMode.ONLY_DOCSTRING,
    output_descriptors=[StringProperty(name="current_time")],
)
def get_current_time() -> str:
    """Return current time"""
    return "2025/10/01 10:30 PM"


@tool(
    description_mode=DescriptionMode.ONLY_DOCSTRING,
    output_descriptors=[
        ListProperty(name="user_purchases", item_type=DictProperty(value_type=StringProperty()))
    ],
)
def get_user_last_purchases(username: str) -> list[dict[str, str]]:
    """Retrieve the list of purchases made by a user"""
    return {
        "alice": [
            {"item_type": "videogame", "title": "Arkanoid", "date": "2000/10/10"},
            {"item_type": "videogame", "title": "Pacman", "date": "2002/09/09"},
        ],
        "bob": [
            {"item_type": "movie", "title": "Batman begins", "date": "2015/10/10"},
            {"item_type": "movie", "title": "The Dark Knight", "date": "2020/08/08"},
        ],
    }.get(username, [])


@tool(
    description_mode=DescriptionMode.ONLY_DOCSTRING,
    output_descriptors=[
        ListProperty(name="items_on_sale", item_type=DictProperty(value_type=StringProperty()))
    ],
)
def get_items_on_sale() -> list[dict[str, str]]:
    """Retrieve the list of items currently on sale"""
    return [
        {"item_type": "household", "title": "Broom"},
        {"item_type": "videogame", "title": "Metroid"},
        {"item_type": "movie", "title": "The Lord of the Rings"},
    ]



# %%[markdown]
## Create the flows to be run in parallel

# %%
from wayflowcore.flow import Flow
from wayflowcore.steps import ParallelFlowExecutionStep, ToolExecutionStep

get_current_time_flow = Flow.from_steps(
    [ToolExecutionStep(name="get_current_time_step", tool=get_current_time)]
)
get_user_information_flow = Flow.from_steps(
    [ToolExecutionStep(name="get_user_information_step", tool=get_user_information)]
)
get_user_last_purchases_flow = Flow.from_steps(
    [ToolExecutionStep(name="get_user_last_purchases_step", tool=get_user_last_purchases)]
)
get_items_on_sale_flow = Flow.from_steps(
    [ToolExecutionStep(name="get_items_on_sale_steo", tool=get_items_on_sale)]
)

parallel_flow_step = ParallelFlowExecutionStep(
    name="parallel_flow_step",
    flows=[
        get_current_time_flow,
        get_user_information_flow,
        get_user_last_purchases_flow,
        get_items_on_sale_flow,
    ],
    max_workers=4,
)

# %%[markdown]
## Generate the marketing message

# %%
from wayflowcore.models import VllmModel
from wayflowcore.steps import OutputMessageStep, PromptExecutionStep

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

prompt = """# Instructions

You are a marketing expert. You have to write a welcome message for a user.

The message must contain:
- A first sentence of greetings, including user's name, and personalized in case it's user's birthday
- A proposal containing something to buy

The purchase proposal must be:
- aligned with user's purchase history
- part of the list of items on sale

# User information

{{user_info}}

Note that the current time to check the birthday is: {{current_time}}

The list of items purchased by the user is:
{{user_purchases}}

# Items on sale

{{items_on_sale}}

Please write the welcome message for the user.
Do not give me the instructions to do it, I want only the final message to send.
"""

prompt_execution_step = PromptExecutionStep(
    name="prepare_marketing_message", prompt_template=prompt, llm=llm
)
output_message_step = OutputMessageStep(name="output_message_step", message_template="{{output}}")

# %%[markdown]
## Create and test the final flow

# %%
from wayflowcore.flow import Flow

flow = Flow.from_steps([parallel_flow_step, prompt_execution_step, output_message_step])

conversation = flow.start_conversation(inputs={"username": "bob"})
status = conversation.execute()
print(conversation.get_last_message().content)

# Expected output:
# Happy Birthday, Bob! We hope your special day is filled with excitement and joy.
# As a token of appreciation for being an valued customer, we'd like to recommend our sale on "The Lord of the Rings",
# a movie that we think you'll love, given your interest in superhero classics like "Batman Begins" and "The Dark Knight".
# It's now available at a discounted price, so don't miss out on this amazing opportunity to add it to your collection.
# Browse our sale now and enjoy!

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(flow)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {
    "get_user_information": get_user_information,
    "get_current_time": get_current_time,
    "get_user_last_purchases": get_user_last_purchases,
    "get_items_on_sale": get_items_on_sale,
}
flow = AgentSpecLoader(tool_registry=tool_registry).load_json(serialized_flow)
```
