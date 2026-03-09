<a id="top-howtodatastores"></a>

# How to Connect Assistants to Your Data![python-icon](_static/icons/python-icon.svg) Download In-Memory Script

Python script/notebook for the In-Memory Datastore example in this guide.

[In-memory datastore how-to script](../end_to_end_code_examples/howto_datastores.py)![python-icon](_static/icons/python-icon.svg) Download Oracle Database Script

Python script/notebook for Oracle Database Datastore  example in this guide.

[Oracle Database datastore how-to script](../end_to_end_code_examples/howto_connect_to_oracle_database.py)

#### Prerequisites
This guide assumes familiarity with

- [Agents](../tutorials/basic_agent.md)
- [Flows](../tutorials/basic_flow.md)

Agents rely on access to relevant data to function effectively.
Without a steady stream of high-quality data, AI models are unable to learn, reason, or make informed decisions.
Connecting an Agent or Flow to data sources is therefore a critical step in developing functional AI systems.
This connection enables agents to perceive their environment, update their knowledge or the underlying data source, and adapt to changing conditions.

In this tutorial, you will:

- **Define Entities** that an Agent or Flow can access and manipulate.
- **Populate a Datastore** with entities for development and testing.
- **Use Datastores in Flows and Agents** to create two types of inventory management assistants.

To ensure reproducibility of this tutorial, you will use an in-memory data source.
Check out the section [Using Oracle Database Datastore](#using-oracle-datastore) to see how to configure an
Oracle Database connection for persistent storage.

## Concepts shown in this guide
- [Entities](../api/datastores.md#id2) to model data
- [Datastore](../api/datastores.md#datastore) and [InMemoryDatastore](../api/datastores.md#inmemorydatastore) to manipulate collections of data
- Steps to use datastores in Agents and Flows ([DatastoreListStep](../api/flows.md#datastoreliststep), [DatastoreCreateStep](../api/flows.md#datastorecreatestep), [DatastoreUpdateStep](../api/flows.md#datastoreupdatestep), [DatastoreDeleteStep](../api/flows.md#datastoredeletestep))

#### NOTE
The [InMemoryDatastore](../api/datastores.md#inmemorydatastore) is mainly suitable for testing and development,
or other use-cases where data persistence across assistants and conversations is not a requirement.
For production use-cases, the [OracleDatabaseDatastore](../api/datastores.md#oracledatabasedatastore) provides a
robust and scalable persistence layer in Oracle Database.

Note that there are a few key differences between an in-memory and a database `Datastore`:

- With database Datastores, all tables relevant to the assistant must already be created in the database prior to connecting to it.
- You may choose to only model a subset of the tables available in the database via the [Entity](../api/datastores.md#id2) construct.
- Database Datastores offer an additional `query` method (and the corresponding [DatastoreQueryStep](../api/flows.md#datastorequerystep)),
  that enables flexible execution of SQL queries that cannot be modelled by the `list` operation on the in-memory datastore

## Datastores in Flows

In this section, you will build a simple Flow that performs operations on an inventory database based on user input.
This Flow helps users keep product descriptions up to date by leveraging an LLM for the creative writing component.

### Step 1. Add imports and LLM configuration

Import the required packages:

```python
from textwrap import dedent

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.datastore import Entity, InMemoryDatastore
from wayflowcore.datastore.entity import nullable
from wayflowcore.flow import Flow
from wayflowcore.property import (
    AnyProperty,
    DictProperty,
    FloatProperty,
    IntegerProperty,
    ObjectProperty,
    StringProperty,
)
from wayflowcore.steps import InputMessageStep, OutputMessageStep, PromptExecutionStep
from wayflowcore.steps.datastoresteps import (
    DatastoreCreateStep,
    DatastoreDeleteStep,
    DatastoreListStep,
    DatastoreUpdateStep,
)
```

In this assistant, you need to use an LLM.
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

#### IMPORTANT
API keys should not be stored anywhere in the code. Use environment variables and/or tools such as [python-dotenv](https://pypi.org/project/python-dotenv/).

### Step 2. Define data

Start by defining the schema for your data using the [Entity](../api/datastores.md#id2) construct.
In this example, you will manage products in an inventory, so a single collection is sufficient.
Datastores also support managing multiple collections at the same time if needed.

```python
product = Entity(
    properties={
        "ID": IntegerProperty(description="Unique product identifier"),
        # Descriptions can be helpful if an LLM needs to fill these fields,
        # or generally disambiguate non-obvious property names
        "title": StringProperty(description="Brief summary of the product"),
        "description": StringProperty(),
        "price": FloatProperty(default_value=0.1),
        # Use nullable to define optional properties
        "category": nullable(StringProperty()),
    },
)
```

Next, create an [InMemoryDatastore](../api/datastores.md#inmemorydatastore).
For simplicity, you will use dummy data:

```python
datastore = InMemoryDatastore(schema={"products": product})

dummy_data = [
    {
        "ID": 0,
        "title": "Broccoli",
        "description": "Healthy and delicious cruciferous vegetable!",
        "price": 1.5,
        "category": "Produce",
    },
    {
        "ID": 1,
        "title": "Oranges",
        "description": "Vitamin C-filled citrus fruits",
        "price": 1.8,
        "category": "Produce",
    },
    {
        "ID": 2,
        "title": "Shampoo",
        "description": "Shiny smooth hair in just 10 applications!",
        "price": 4.5,
        "category": "Personal hygiene",
    },
    {
        "ID": 3,
        "title": "Crushed ice",
        "description": "Cool any drink in seconds!",
        "price": 4.5,
    },
]

# Create supports both bulk-creation, as well as single element creation
datastore.create(collection_name="products", entities=dummy_data[:-1])
datastore.create(collection_name="products", entities=dummy_data[-1])
```

### Step 3. Create datastore steps

Now that the Datastore is set up, create steps to perform different operations in the flow.
In this case, the assistant only needs to retrieve the current description of products and update it.
See [the list of all available Datastore steps](../api/flows.md#datastoresteps) for more details.

```python
datastore_list_step = DatastoreListStep(
    datastore,
    name="product_list_step",
    collection_name="products",
    where={"title": "{{user_requested_product}}"},
    limit=1,
    unpack_single_entity_from_list=True,
)

datastore_update_step = DatastoreUpdateStep(
    datastore,
    name="product_update_step",
    collection_name="products",
    where={"title": "{{user_requested_product}}"}
)
```

Key points:

- Use `where` to filter which product to list and update. Configure it with a variable so that the user can dynamically choose the product title.
- In the `DatastoreListStep`, `limit` and `unpack_single_entity_from_list` are used to assume that product titles are unique, making the output concise and easy to handle.

The input to the `DatastoreListStep` is the title of the product to retrieve, and the output is a single object containing the corresponding product data.
The input to the `DatastoreUpdateStep` includes both the title of the product to update and the updates to apply, in the form of a dictionary containing the properties and the corresponding values.
The output will be the new properties that were updated.

### Step 4. Create the Flow

Now define the [Flow](../api/flows.md#flow) for this assistant.

After the user enters which product they want to update, and how the description should be updated, the datastore is queried to find the matching product.
The LLM is prompted with the product details and the user’s instructions.
The output is used to update the data, and the new result is returned back to the user.

<details>
<summary>Details</summary>

```python
# We create the steps needed by our flow
USER_INPUT_STEP = "user_product_input_step"
USER_TASK_INPUT_STEP = "user_task_input_step"
LLM_REWRITE_STEP = "llm_rewrite_step"
USER_OUTPUT_STEP = "user_output_step"

user_input_message_template = dedent(
    """I am an inventory Assistant, designed to help you keep product descriptions up-to-date.
    What product would you like to update? Please provide its title.
    """
)

user_task_message_template = "How would you like to update the description? I will help you rewrite it according to your instructions"

rewrite_description_prompt_template = dedent(
    """You are an inventory assistant.

    Your task:
        - Based on the product details given below, rewrite the description according to the user's request
    Important:
        - Be helpful and concise in your messages
        - Only provide the new description as an output, and nothing else

    Here is the User's request:
    - {{ user_request }}

    Here is the product description:
    - {{ product }}
    """
)

user_input_step = InputMessageStep(
    name=USER_INPUT_STEP,
    message_template=user_input_message_template,
)

user_task_input_step = InputMessageStep(
    name=USER_TASK_INPUT_STEP,
    message_template=user_task_message_template,
)

llm_rewrite_step = PromptExecutionStep(
    name=LLM_REWRITE_STEP,
    prompt_template=rewrite_description_prompt_template,
    llm=llm,
    input_descriptors=[
        DictProperty("product", key_type=StringProperty(), value_type=AnyProperty())
    ],
    output_descriptors=[
        ObjectProperty(
            name=PromptExecutionStep.OUTPUT, properties={"description": StringProperty()}
        )
    ],
)

user_output_step = OutputMessageStep(
    name=USER_OUTPUT_STEP,
    message_template="The product has been updated with the following description: {{ answer['description'] }}",
)

assistant = Flow(
    begin_step=user_input_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=user_input_step, destination_step=user_task_input_step),
        ControlFlowEdge(source_step=user_task_input_step, destination_step=datastore_list_step),
        ControlFlowEdge(source_step=datastore_list_step, destination_step=llm_rewrite_step),
        ControlFlowEdge(source_step=llm_rewrite_step, destination_step=datastore_update_step),
        ControlFlowEdge(source_step=datastore_update_step, destination_step=user_output_step),
        ControlFlowEdge(source_step=user_output_step, destination_step=None),
    ],
    data_flow_edges=[
        # The first title given by the user is mapped to the datastore steps for listing and updating
        DataFlowEdge(
            user_input_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            datastore_list_step,
            "user_requested_product",
        ),
        DataFlowEdge(
            user_input_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            datastore_update_step,
            "user_requested_product",
        ),
        # The task and product detail are given to the LLM in the prompt execution step
        DataFlowEdge(
            user_task_input_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            llm_rewrite_step,
            "user_request",
        ),
        DataFlowEdge(datastore_list_step, DatastoreListStep.ENTITIES, llm_rewrite_step, "product"),
        # The generated update is applied on the datastore, and echoed back to the user
        DataFlowEdge(
            llm_rewrite_step,
            PromptExecutionStep.OUTPUT,
            datastore_update_step,
            DatastoreUpdateStep.UPDATE,
        ),
        DataFlowEdge(llm_rewrite_step, PromptExecutionStep.OUTPUT, user_output_step, "answer"),
    ],
)
```

</details>

Note the use of structured generation in the `PromptExecutionStep` (via the `output_descriptors` parameter).
This ensures that the LLM generates exactly the structure expected by the `DatastoreUpdateStep`.

Finally, verify that the Flow works:

```python
conversation = assistant.start_conversation()
conversation.execute()
conversation.append_user_message("Broccoli")

conversation.execute()
conversation.append_user_message(
    "Shoppers don't know what 'cruciferous' means, we should find a catchier description."
)

conversation.execute()
print(conversation.get_last_message().content)
```

## Datastores in Agents

This section assumes you have completed the previous steps on using datastores in Flows.

The Flow you built earlier is quite helpful and reliable because it performs a single, specialized task.
Next, you will see how to define an Agent for inventory management when the task is not defined in advance.
This Agent will be able to interpret the user’s requests and autonomously decide which actions on the `Datastore` are required to fulfill each task.

### Step 1. Add imports and LLM configuration

Add the additional imports needed to use Agents:

```python
from wayflowcore.agent import Agent
```

### Step 2. Create Datastore Flows for an Agent

To use the  `Datastore` in an agent, create flows for the different operations you want the agent to perform.
In the simplest setup, you can define one flow per basic `Datastore` operation.
The agent will then determine the correct sequence of actions to achieve the user’s goal.

Define flows for:

```python
AGENT_PROMPT = dedent(
    """
    You are an inventory assistant. Your task is to help the user with their requests by using the available tools.
    If you are unsure about the action to take, or you don't have the right tool, simply tell the user so and follow their guidance.
    """
)

create_product_flow = Flow.from_steps(
    [DatastoreCreateStep(datastore, "products")],
    name="Create product",
    description="Creates a new product in the data source",
)
list_products_flow = Flow.from_steps(
    [DatastoreListStep(datastore, "products")],
    name="List all products",
    description="Lists all products in the data source.",
)
list_one_product_flow = Flow.from_steps(
    [datastore_list_step],
    name="List single product",
    description="Lists a single product in the data source by its title.",
)
update_product_flow = Flow.from_steps(
    [datastore_update_step],
    name="Update product",
    description="Updates a product in the data source by its title.",
)
delete_product_flow = Flow.from_steps(
    [DatastoreDeleteStep(datastore, "products", where={"title": "{{product_title}}"})],
    name="Delete product",
    description="Delete a product in the data source by its title.",
)
```

Notice the provided descriptions for the flows to help the agent understand the objective of each operation.

Additionally, you can incorporate more complex behaviors into these flows.
For example, you could ask for user confirmation before deleting entities, or you could provide the user with an overview, and an editing option of the updates made by the agent before they are applied.

### Step 3. Create the Agent

Finally, create the inventory management agent by combining the LLM, the datastore flows, and a custom instruction:

```python
agent = Agent(
    llm=llm,
    flows=[
        create_product_flow,
        list_products_flow,
        list_one_product_flow,
        update_product_flow,
        delete_product_flow,
    ],
    custom_instruction=AGENT_PROMPT,
)
```

This agent can now respond to the user and perform actions on the data on their behalf.

Refer to the [WayFlow Agents Tutorial](../tutorials/basic_agent.md) to see how to run this Agent.

## Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_agent = AgentSpecExporter().to_json(agent)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "ExtendedAgent",
  "id": "99f1d854-0f10-473a-ad2a-3558b8977244",
  "name": "agent_d18c1f13__auto",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [],
  "outputs": [],
  "llm_config": {
    "component_type": "VllmConfig",
    "id": "b10b47da-03bc-4bb3-a024-b2d8330a5be8",
    "name": "LLAMA_MODEL_ID",
    "description": null,
    "metadata": {
      "__metadata_info__": {}
    },
    "default_generation_parameters": null,
    "url": "LLAMA_API_URL",
    "model_id": "LLAMA_MODEL_ID"
  },
  "system_prompt": "\nYou are an inventory assistant. Your task is to help the user with their requests by using the available tools.\nIf you are unsure about the action to take, or you don't have the right tool, simply tell the user so and follow their guidance.\n",
  "tools": [],
  "toolboxes": [],
  "context_providers": null,
  "can_finish_conversation": false,
  "max_iterations": 10,
  "initial_message": "Hi! How can I help you?",
  "caller_input_mode": "always",
  "agents": [],
  "flows": [
    {
      "component_type": "Flow",
      "id": "96d3782c-552c-429c-bd7e-4f4af61ff713",
      "name": "Create product",
      "description": "Creates a new product in the data source",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "object",
          "additionalProperties": {},
          "key_type": {
            "type": "string"
          },
          "title": "entity"
        }
      ],
      "outputs": [
        {
          "type": "object",
          "additionalProperties": {},
          "key_type": {
            "type": "string"
          },
          "title": "created_entity"
        }
      ],
      "start_node": {
        "$component_ref": "79b6331a-5543-4310-8d8b-1d9f1337b025"
      },
      "nodes": [
        {
          "$component_ref": "331ca41a-8738-4751-a87e-5cc48b8a3e23"
        },
        {
          "$component_ref": "79b6331a-5543-4310-8d8b-1d9f1337b025"
        },
        {
          "$component_ref": "ae2f0460-cba8-499e-a993-62b946e56d40"
        }
      ],
      "control_flow_connections": [
        {
          "component_type": "ControlFlowEdge",
          "id": "fe4ef560-e504-4dc8-a298-7dbb3c067a6f",
          "name": "__StartStep___to_step_0_control_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "from_node": {
            "$component_ref": "79b6331a-5543-4310-8d8b-1d9f1337b025"
          },
          "from_branch": null,
          "to_node": {
            "$component_ref": "331ca41a-8738-4751-a87e-5cc48b8a3e23"
          }
        },
        {
          "component_type": "ControlFlowEdge",
          "id": "a16d091c-0d0c-4d29-9104-7761bdbb4cd3",
          "name": "step_0_to_None End node_control_flow_edge",
          "description": null,
          "metadata": {},
          "from_node": {
            "$component_ref": "331ca41a-8738-4751-a87e-5cc48b8a3e23"
          },
          "from_branch": null,
          "to_node": {
            "$component_ref": "ae2f0460-cba8-499e-a993-62b946e56d40"
          }
        }
      ],
      "data_flow_connections": [
        {
          "component_type": "DataFlowEdge",
          "id": "58dbd841-e0a5-4c87-ac0c-08a34625323b",
          "name": "__StartStep___entity_to_step_0_entity_data_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "source_node": {
            "$component_ref": "79b6331a-5543-4310-8d8b-1d9f1337b025"
          },
          "source_output": "entity",
          "destination_node": {
            "$component_ref": "331ca41a-8738-4751-a87e-5cc48b8a3e23"
          },
          "destination_input": "entity"
        },
        {
          "component_type": "DataFlowEdge",
          "id": "92415266-d5a4-40ca-b8e6-57e01ec002a5",
          "name": "step_0_created_entity_to_None End node_created_entity_data_flow_edge",
          "description": null,
          "metadata": {},
          "source_node": {
            "$component_ref": "331ca41a-8738-4751-a87e-5cc48b8a3e23"
          },
          "source_output": "created_entity",
          "destination_node": {
            "$component_ref": "ae2f0460-cba8-499e-a993-62b946e56d40"
          },
          "destination_input": "created_entity"
        }
      ],
      "$referenced_components": {
        "331ca41a-8738-4751-a87e-5cc48b8a3e23": {
          "component_type": "PluginDatastoreCreateNode",
          "id": "331ca41a-8738-4751-a87e-5cc48b8a3e23",
          "name": "step_0",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [
            {
              "type": "object",
              "additionalProperties": {},
              "key_type": {
                "type": "string"
              },
              "title": "entity"
            }
          ],
          "outputs": [
            {
              "type": "object",
              "additionalProperties": {},
              "key_type": {
                "type": "string"
              },
              "title": "created_entity"
            }
          ],
          "branches": [
            "next"
          ],
          "input_mapping": {},
          "output_mapping": {},
          "datastore": {
            "$component_ref": "4f8e1008-2f20-456c-9250-679146e88192"
          },
          "collection_name": "products",
          "ENTITY": "entity",
          "CREATED_ENTITY": "created_entity",
          "component_plugin_name": "DatastorePlugin",
          "component_plugin_version": "25.4.0.dev0"
        },
        "79b6331a-5543-4310-8d8b-1d9f1337b025": {
          "component_type": "StartNode",
          "id": "79b6331a-5543-4310-8d8b-1d9f1337b025",
          "name": "__StartStep__",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [
            {
              "type": "object",
              "additionalProperties": {},
              "key_type": {
                "type": "string"
              },
              "title": "entity"
            }
          ],
          "outputs": [
            {
              "type": "object",
              "additionalProperties": {},
              "key_type": {
                "type": "string"
              },
              "title": "entity"
            }
          ],
          "branches": [
            "next"
          ]
        },
        "ae2f0460-cba8-499e-a993-62b946e56d40": {
          "component_type": "EndNode",
          "id": "ae2f0460-cba8-499e-a993-62b946e56d40",
          "name": "None End node",
          "description": "End node representing all transitions to None in the WayFlow flow",
          "metadata": {},
          "inputs": [
            {
              "type": "object",
              "additionalProperties": {},
              "key_type": {
                "type": "string"
              },
              "title": "created_entity"
            }
          ],
          "outputs": [
            {
              "type": "object",
              "additionalProperties": {},
              "key_type": {
                "type": "string"
              },
              "title": "created_entity"
            }
          ],
          "branches": [],
          "branch_name": "next"
        }
      }
    },
    {
      "component_type": "Flow",
      "id": "ba1cd504-bef6-4af3-9498-cbf6e50a0bca",
      "name": "List all products",
      "description": "Lists all products in the data source.",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [],
      "outputs": [
        {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": {},
            "key_type": {
              "type": "string"
            }
          },
          "title": "entities"
        }
      ],
      "start_node": {
        "$component_ref": "bb1b722a-0aae-4e09-b2a4-cbcdb93b2cff"
      },
      "nodes": [
        {
          "$component_ref": "0c924103-23f5-4698-b69e-c553250186ab"
        },
        {
          "$component_ref": "bb1b722a-0aae-4e09-b2a4-cbcdb93b2cff"
        },
        {
          "$component_ref": "098f2832-4672-44eb-a060-ea9514ceefc5"
        }
      ],
      "control_flow_connections": [
        {
          "component_type": "ControlFlowEdge",
          "id": "a0392cfe-bed3-44cb-84c0-20a30f1cbe18",
          "name": "__StartStep___to_step_0_control_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "from_node": {
            "$component_ref": "bb1b722a-0aae-4e09-b2a4-cbcdb93b2cff"
          },
          "from_branch": null,
          "to_node": {
            "$component_ref": "0c924103-23f5-4698-b69e-c553250186ab"
          }
        },
        {
          "component_type": "ControlFlowEdge",
          "id": "3290795e-59ca-46f8-8a96-5a265d707c13",
          "name": "step_0_to_None End node_control_flow_edge",
          "description": null,
          "metadata": {},
          "from_node": {
            "$component_ref": "0c924103-23f5-4698-b69e-c553250186ab"
          },
          "from_branch": null,
          "to_node": {
            "$component_ref": "098f2832-4672-44eb-a060-ea9514ceefc5"
          }
        }
      ],
      "data_flow_connections": [
        {
          "component_type": "DataFlowEdge",
          "id": "308b92b6-70f4-4e9c-b41e-1563bc449a24",
          "name": "step_0_entities_to_None End node_entities_data_flow_edge",
          "description": null,
          "metadata": {},
          "source_node": {
            "$component_ref": "0c924103-23f5-4698-b69e-c553250186ab"
          },
          "source_output": "entities",
          "destination_node": {
            "$component_ref": "098f2832-4672-44eb-a060-ea9514ceefc5"
          },
          "destination_input": "entities"
        }
      ],
      "$referenced_components": {
        "098f2832-4672-44eb-a060-ea9514ceefc5": {
          "component_type": "EndNode",
          "id": "098f2832-4672-44eb-a060-ea9514ceefc5",
          "name": "None End node",
          "description": "End node representing all transitions to None in the WayFlow flow",
          "metadata": {},
          "inputs": [
            {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": {},
                "key_type": {
                  "type": "string"
                }
              },
              "title": "entities"
            }
          ],
          "outputs": [
            {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": {},
                "key_type": {
                  "type": "string"
                }
              },
              "title": "entities"
            }
          ],
          "branches": [],
          "branch_name": "next"
        },
        "0c924103-23f5-4698-b69e-c553250186ab": {
          "component_type": "PluginDatastoreListNode",
          "id": "0c924103-23f5-4698-b69e-c553250186ab",
          "name": "step_0",
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
                "additionalProperties": {},
                "key_type": {
                  "type": "string"
                }
              },
              "title": "entities"
            }
          ],
          "branches": [
            "next"
          ],
          "input_mapping": {},
          "output_mapping": {},
          "datastore": {
            "$component_ref": "4f8e1008-2f20-456c-9250-679146e88192"
          },
          "collection_name": "products",
          "where": null,
          "limit": null,
          "unpack_single_entity_from_list": false,
          "ENTITIES": "entities",
          "component_plugin_name": "DatastorePlugin",
          "component_plugin_version": "25.4.0.dev0"
        },
        "bb1b722a-0aae-4e09-b2a4-cbcdb93b2cff": {
          "component_type": "StartNode",
          "id": "bb1b722a-0aae-4e09-b2a4-cbcdb93b2cff",
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
      "id": "bad00138-48b3-4e7c-84a9-51bd385a38a2",
      "name": "List single product",
      "description": "Lists a single product in the data source by its title.",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "\"user_requested_product\" input variable for the template",
          "type": "string",
          "title": "user_requested_product"
        }
      ],
      "outputs": [
        {
          "type": "object",
          "additionalProperties": {},
          "key_type": {
            "type": "string"
          },
          "title": "entities"
        }
      ],
      "start_node": {
        "$component_ref": "76d19c9a-241f-4a4d-bbac-2bcbd3359498"
      },
      "nodes": [
        {
          "$component_ref": "d1b1f436-b91f-435c-867c-ecf9b5b187a1"
        },
        {
          "$component_ref": "76d19c9a-241f-4a4d-bbac-2bcbd3359498"
        },
        {
          "$component_ref": "aa8090d6-2220-40ad-ab16-6adb1bdead7b"
        }
      ],
      "control_flow_connections": [
        {
          "component_type": "ControlFlowEdge",
          "id": "e37ae190-e7f6-4090-8091-c5eddadf7a9d",
          "name": "__StartStep___to_product_list_step_control_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "from_node": {
            "$component_ref": "76d19c9a-241f-4a4d-bbac-2bcbd3359498"
          },
          "from_branch": null,
          "to_node": {
            "$component_ref": "d1b1f436-b91f-435c-867c-ecf9b5b187a1"
          }
        },
        {
          "component_type": "ControlFlowEdge",
          "id": "80680849-e51b-435d-aee6-cdb7e6571ee7",
          "name": "product_list_step_to_None End node_control_flow_edge",
          "description": null,
          "metadata": {},
          "from_node": {
            "$component_ref": "d1b1f436-b91f-435c-867c-ecf9b5b187a1"
          },
          "from_branch": null,
          "to_node": {
            "$component_ref": "aa8090d6-2220-40ad-ab16-6adb1bdead7b"
          }
        }
      ],
      "data_flow_connections": [
        {
          "component_type": "DataFlowEdge",
          "id": "dab6eb95-057c-4adc-85dd-2a40e14713eb",
          "name": "__StartStep___user_requested_product_to_product_list_step_user_requested_product_data_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "source_node": {
            "$component_ref": "76d19c9a-241f-4a4d-bbac-2bcbd3359498"
          },
          "source_output": "user_requested_product",
          "destination_node": {
            "$component_ref": "d1b1f436-b91f-435c-867c-ecf9b5b187a1"
          },
          "destination_input": "user_requested_product"
        },
        {
          "component_type": "DataFlowEdge",
          "id": "82d0a256-6c3d-45a8-a6bf-c1c949069927",
          "name": "product_list_step_entities_to_None End node_entities_data_flow_edge",
          "description": null,
          "metadata": {},
          "source_node": {
            "$component_ref": "d1b1f436-b91f-435c-867c-ecf9b5b187a1"
          },
          "source_output": "entities",
          "destination_node": {
            "$component_ref": "aa8090d6-2220-40ad-ab16-6adb1bdead7b"
          },
          "destination_input": "entities"
        }
      ],
      "$referenced_components": {
        "d1b1f436-b91f-435c-867c-ecf9b5b187a1": {
          "component_type": "PluginDatastoreListNode",
          "id": "d1b1f436-b91f-435c-867c-ecf9b5b187a1",
          "name": "product_list_step",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [
            {
              "description": "\"user_requested_product\" input variable for the template",
              "type": "string",
              "title": "user_requested_product"
            }
          ],
          "outputs": [
            {
              "type": "object",
              "additionalProperties": {},
              "key_type": {
                "type": "string"
              },
              "title": "entities"
            }
          ],
          "branches": [
            "next"
          ],
          "input_mapping": {},
          "output_mapping": {},
          "datastore": {
            "$component_ref": "4f8e1008-2f20-456c-9250-679146e88192"
          },
          "collection_name": "products",
          "where": {
            "title": "{{user_requested_product}}"
          },
          "limit": 1,
          "unpack_single_entity_from_list": true,
          "ENTITIES": "entities",
          "component_plugin_name": "DatastorePlugin",
          "component_plugin_version": "25.4.0.dev0"
        },
        "76d19c9a-241f-4a4d-bbac-2bcbd3359498": {
          "component_type": "StartNode",
          "id": "76d19c9a-241f-4a4d-bbac-2bcbd3359498",
          "name": "__StartStep__",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [
            {
              "description": "\"user_requested_product\" input variable for the template",
              "type": "string",
              "title": "user_requested_product"
            }
          ],
          "outputs": [
            {
              "description": "\"user_requested_product\" input variable for the template",
              "type": "string",
              "title": "user_requested_product"
            }
          ],
          "branches": [
            "next"
          ]
        },
        "aa8090d6-2220-40ad-ab16-6adb1bdead7b": {
          "component_type": "EndNode",
          "id": "aa8090d6-2220-40ad-ab16-6adb1bdead7b",
          "name": "None End node",
          "description": "End node representing all transitions to None in the WayFlow flow",
          "metadata": {},
          "inputs": [
            {
              "type": "object",
              "additionalProperties": {},
              "key_type": {
                "type": "string"
              },
              "title": "entities"
            }
          ],
          "outputs": [
            {
              "type": "object",
              "additionalProperties": {},
              "key_type": {
                "type": "string"
              },
              "title": "entities"
            }
          ],
          "branches": [],
          "branch_name": "next"
        }
      }
    },
    {
      "component_type": "Flow",
      "id": "a3047067-dea3-4cc9-a922-c26d35d97c48",
      "name": "Update product",
      "description": "Updates a product in the data source by its title.",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "\"user_requested_product\" input variable for the template",
          "type": "string",
          "title": "user_requested_product"
        },
        {
          "type": "object",
          "additionalProperties": {},
          "key_type": {
            "type": "string"
          },
          "title": "update"
        }
      ],
      "outputs": [
        {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": {},
            "key_type": {
              "type": "string"
            }
          },
          "title": "entities"
        }
      ],
      "start_node": {
        "$component_ref": "8c74a4c5-fdf0-447e-956f-59498da1dc09"
      },
      "nodes": [
        {
          "$component_ref": "487a708b-0553-4bb5-b015-948d2a97ede6"
        },
        {
          "$component_ref": "8c74a4c5-fdf0-447e-956f-59498da1dc09"
        },
        {
          "$component_ref": "9074c861-1cf4-4bd9-88dd-3fe209b2c218"
        }
      ],
      "control_flow_connections": [
        {
          "component_type": "ControlFlowEdge",
          "id": "64436400-797d-4d35-92df-78fc557006f2",
          "name": "__StartStep___to_product_update_step_control_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "from_node": {
            "$component_ref": "8c74a4c5-fdf0-447e-956f-59498da1dc09"
          },
          "from_branch": null,
          "to_node": {
            "$component_ref": "487a708b-0553-4bb5-b015-948d2a97ede6"
          }
        },
        {
          "component_type": "ControlFlowEdge",
          "id": "5e55b5d7-7bf8-435a-9044-f05f1b377671",
          "name": "product_update_step_to_None End node_control_flow_edge",
          "description": null,
          "metadata": {},
          "from_node": {
            "$component_ref": "487a708b-0553-4bb5-b015-948d2a97ede6"
          },
          "from_branch": null,
          "to_node": {
            "$component_ref": "9074c861-1cf4-4bd9-88dd-3fe209b2c218"
          }
        }
      ],
      "data_flow_connections": [
        {
          "component_type": "DataFlowEdge",
          "id": "43c29773-0a4b-4145-9c0d-ad5238410e9d",
          "name": "__StartStep___user_requested_product_to_product_update_step_user_requested_product_data_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "source_node": {
            "$component_ref": "8c74a4c5-fdf0-447e-956f-59498da1dc09"
          },
          "source_output": "user_requested_product",
          "destination_node": {
            "$component_ref": "487a708b-0553-4bb5-b015-948d2a97ede6"
          },
          "destination_input": "user_requested_product"
        },
        {
          "component_type": "DataFlowEdge",
          "id": "8e5f0ea8-8ea1-42ba-bdba-95a74082c908",
          "name": "__StartStep___update_to_product_update_step_update_data_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "source_node": {
            "$component_ref": "8c74a4c5-fdf0-447e-956f-59498da1dc09"
          },
          "source_output": "update",
          "destination_node": {
            "$component_ref": "487a708b-0553-4bb5-b015-948d2a97ede6"
          },
          "destination_input": "update"
        },
        {
          "component_type": "DataFlowEdge",
          "id": "1bd34870-1e52-4896-bfaf-5a71006da687",
          "name": "product_update_step_entities_to_None End node_entities_data_flow_edge",
          "description": null,
          "metadata": {},
          "source_node": {
            "$component_ref": "487a708b-0553-4bb5-b015-948d2a97ede6"
          },
          "source_output": "entities",
          "destination_node": {
            "$component_ref": "9074c861-1cf4-4bd9-88dd-3fe209b2c218"
          },
          "destination_input": "entities"
        }
      ],
      "$referenced_components": {
        "487a708b-0553-4bb5-b015-948d2a97ede6": {
          "component_type": "PluginDatastoreUpdateNode",
          "id": "487a708b-0553-4bb5-b015-948d2a97ede6",
          "name": "product_update_step",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [
            {
              "description": "\"user_requested_product\" input variable for the template",
              "type": "string",
              "title": "user_requested_product"
            },
            {
              "type": "object",
              "additionalProperties": {},
              "key_type": {
                "type": "string"
              },
              "title": "update"
            }
          ],
          "outputs": [
            {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": {},
                "key_type": {
                  "type": "string"
                }
              },
              "title": "entities"
            }
          ],
          "branches": [
            "next"
          ],
          "input_mapping": {},
          "output_mapping": {},
          "datastore": {
            "$component_ref": "4f8e1008-2f20-456c-9250-679146e88192"
          },
          "collection_name": "products",
          "where": {
            "title": "{{user_requested_product}}"
          },
          "ENTITIES": "entities",
          "UPDATE": "update",
          "component_plugin_name": "DatastorePlugin",
          "component_plugin_version": "25.4.0.dev0"
        },
        "8c74a4c5-fdf0-447e-956f-59498da1dc09": {
          "component_type": "StartNode",
          "id": "8c74a4c5-fdf0-447e-956f-59498da1dc09",
          "name": "__StartStep__",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [
            {
              "description": "\"user_requested_product\" input variable for the template",
              "type": "string",
              "title": "user_requested_product"
            },
            {
              "type": "object",
              "additionalProperties": {},
              "key_type": {
                "type": "string"
              },
              "title": "update"
            }
          ],
          "outputs": [
            {
              "description": "\"user_requested_product\" input variable for the template",
              "type": "string",
              "title": "user_requested_product"
            },
            {
              "type": "object",
              "additionalProperties": {},
              "key_type": {
                "type": "string"
              },
              "title": "update"
            }
          ],
          "branches": [
            "next"
          ]
        },
        "9074c861-1cf4-4bd9-88dd-3fe209b2c218": {
          "component_type": "EndNode",
          "id": "9074c861-1cf4-4bd9-88dd-3fe209b2c218",
          "name": "None End node",
          "description": "End node representing all transitions to None in the WayFlow flow",
          "metadata": {},
          "inputs": [
            {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": {},
                "key_type": {
                  "type": "string"
                }
              },
              "title": "entities"
            }
          ],
          "outputs": [
            {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": {},
                "key_type": {
                  "type": "string"
                }
              },
              "title": "entities"
            }
          ],
          "branches": [],
          "branch_name": "next"
        }
      }
    },
    {
      "component_type": "Flow",
      "id": "ebae9461-df3a-4544-9cfd-dd2a2e13e34e",
      "name": "Delete product",
      "description": "Delete a product in the data source by its title.",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "\"product_title\" input variable for the template",
          "type": "string",
          "title": "product_title"
        }
      ],
      "outputs": [],
      "start_node": {
        "$component_ref": "13d561e4-1c49-4808-974c-d82311479998"
      },
      "nodes": [
        {
          "$component_ref": "9cd4c282-5290-477d-b9c1-f069a599aa68"
        },
        {
          "$component_ref": "13d561e4-1c49-4808-974c-d82311479998"
        },
        {
          "$component_ref": "49384f2b-1825-4c6b-a876-86e8803b0014"
        }
      ],
      "control_flow_connections": [
        {
          "component_type": "ControlFlowEdge",
          "id": "7b91ecf7-f24e-4ff3-8df4-f6769847e7a4",
          "name": "__StartStep___to_step_0_control_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "from_node": {
            "$component_ref": "13d561e4-1c49-4808-974c-d82311479998"
          },
          "from_branch": null,
          "to_node": {
            "$component_ref": "9cd4c282-5290-477d-b9c1-f069a599aa68"
          }
        },
        {
          "component_type": "ControlFlowEdge",
          "id": "e666dfe3-6041-4141-b21b-afedfa74f3ab",
          "name": "step_0_to_None End node_control_flow_edge",
          "description": null,
          "metadata": {},
          "from_node": {
            "$component_ref": "9cd4c282-5290-477d-b9c1-f069a599aa68"
          },
          "from_branch": null,
          "to_node": {
            "$component_ref": "49384f2b-1825-4c6b-a876-86e8803b0014"
          }
        }
      ],
      "data_flow_connections": [
        {
          "component_type": "DataFlowEdge",
          "id": "a731fb73-ad3b-4a22-9f0b-35e9f1d63131",
          "name": "__StartStep___product_title_to_step_0_product_title_data_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "source_node": {
            "$component_ref": "13d561e4-1c49-4808-974c-d82311479998"
          },
          "source_output": "product_title",
          "destination_node": {
            "$component_ref": "9cd4c282-5290-477d-b9c1-f069a599aa68"
          },
          "destination_input": "product_title"
        }
      ],
      "$referenced_components": {
        "9cd4c282-5290-477d-b9c1-f069a599aa68": {
          "component_type": "PluginDatastoreDeleteNode",
          "id": "9cd4c282-5290-477d-b9c1-f069a599aa68",
          "name": "step_0",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [
            {
              "description": "\"product_title\" input variable for the template",
              "type": "string",
              "title": "product_title"
            }
          ],
          "outputs": [],
          "branches": [
            "next"
          ],
          "input_mapping": {},
          "output_mapping": {},
          "datastore": {
            "$component_ref": "4f8e1008-2f20-456c-9250-679146e88192"
          },
          "collection_name": "products",
          "where": {
            "title": "{{product_title}}"
          },
          "component_plugin_name": "DatastorePlugin",
          "component_plugin_version": "25.4.0.dev0"
        },
        "13d561e4-1c49-4808-974c-d82311479998": {
          "component_type": "StartNode",
          "id": "13d561e4-1c49-4808-974c-d82311479998",
          "name": "__StartStep__",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [
            {
              "description": "\"product_title\" input variable for the template",
              "type": "string",
              "title": "product_title"
            }
          ],
          "outputs": [
            {
              "description": "\"product_title\" input variable for the template",
              "type": "string",
              "title": "product_title"
            }
          ],
          "branches": [
            "next"
          ]
        },
        "49384f2b-1825-4c6b-a876-86e8803b0014": {
          "component_type": "EndNode",
          "id": "49384f2b-1825-4c6b-a876-86e8803b0014",
          "name": "None End node",
          "description": "End node representing all transitions to None in the WayFlow flow",
          "metadata": {},
          "inputs": [],
          "outputs": [],
          "branches": [],
          "branch_name": "next"
        }
      }
    }
  ],
  "agent_template": {
    "component_type": "PluginPromptTemplate",
    "id": "ea261004-a6d8-4380-af2a-4e5adbaf7b9c",
    "name": "",
    "description": null,
    "metadata": {
      "__metadata_info__": {}
    },
    "messages": [
      {
        "role": "system",
        "contents": [
          {
            "type": "text",
            "content": "{%- if __TOOLS__ -%}\nEnvironment: ipython\nCutting Knowledge Date: December 2023\n\nYou are a helpful assistant with tool calling capabilities. Only reply with a tool call if the function exists in the library provided by the user. If it doesn't exist, just reply directly in natural language. When you receive a tool call response, use the output to format an answer to the original user question.\n\nYou have access to the following functions. To call a function, please respond with JSON for a function call.\nRespond in the format {\"name\": function name, \"parameters\": dictionary of argument name and its value}.\nDo not use variables.\n\n[{% for tool in __TOOLS__%}{{tool.to_openai_format() | tojson}}{{', ' if not loop.last}}{% endfor %}]\n{%- endif -%}\n"
          }
        ],
        "tool_requests": null,
        "tool_result": null,
        "display_only": false,
        "sender": null,
        "recipients": [],
        "time_created": "2025-09-02T15:58:42.673848+00:00",
        "time_updated": "2025-09-02T15:58:42.673852+00:00"
      },
      {
        "role": "system",
        "contents": [
          {
            "type": "text",
            "content": "{%- if custom_instruction -%}Additional instructions:\n{{custom_instruction}}{%- endif -%}"
          }
        ],
        "tool_requests": null,
        "tool_result": null,
        "display_only": false,
        "sender": null,
        "recipients": [],
        "time_created": "2025-09-02T15:58:42.673915+00:00",
        "time_updated": "2025-09-02T15:58:42.673916+00:00"
      },
      {
        "role": "user",
        "contents": [],
        "tool_requests": null,
        "tool_result": null,
        "display_only": false,
        "sender": null,
        "recipients": [],
        "time_created": "2025-09-02T15:58:42.660189+00:00",
        "time_updated": "2025-09-02T15:58:42.660446+00:00"
      },
      {
        "role": "system",
        "contents": [
          {
            "type": "text",
            "content": "{% if __PLAN__ %}The current plan you should follow is the following: \n{{__PLAN__}}{% endif %}"
          }
        ],
        "tool_requests": null,
        "tool_result": null,
        "display_only": false,
        "sender": null,
        "recipients": [],
        "time_created": "2025-09-02T15:58:42.673985+00:00",
        "time_updated": "2025-09-02T15:58:42.673986+00:00"
      }
    ],
    "output_parser": {
      "component_type": "PluginJsonToolOutputParser",
      "id": "8d8b00f0-2c13-4e0f-894c-a46ad91eccbc",
      "name": "jsontool_outputparser",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "tools": null,
      "component_plugin_name": "OutputParserPlugin",
      "component_plugin_version": "25.4.0.dev0"
    },
    "inputs": [
      {
        "description": "\"__TOOLS__\" input variable for the template",
        "title": "__TOOLS__"
      },
      {
        "description": "\"custom_instruction\" input variable for the template",
        "type": "string",
        "title": "custom_instruction"
      },
      {
        "description": "\"__PLAN__\" input variable for the template",
        "type": "string",
        "title": "__PLAN__",
        "default": ""
      },
      {
        "type": "array",
        "items": {},
        "title": "__CHAT_HISTORY__"
      }
    ],
    "pre_rendering_transforms": null,
    "post_rendering_transforms": [
      {
        "component_type": "PluginRemoveEmptyNonUserMessageTransform",
        "id": "f964b648-4850-43ca-983b-6bf05ec6fe59",
        "name": "removeemptynonusermessage_messagetransform",
        "description": null,
        "metadata": {
          "__metadata_info__": {}
        },
        "component_plugin_name": "MessageTransformPlugin",
        "component_plugin_version": "25.4.0.dev0"
      },
      {
        "component_type": "PluginCoalesceSystemMessagesTransform",
        "id": "b0c702f1-14a8-4692-b746-490f3cc2a406",
        "name": "coalescesystemmessage_messagetransform",
        "description": null,
        "metadata": {
          "__metadata_info__": {}
        },
        "component_plugin_name": "MessageTransformPlugin",
        "component_plugin_version": "25.4.0.dev0"
      },
      {
        "component_type": "PluginLlamaMergeToolRequestAndCallsTransform",
        "id": "466f3fef-697b-4e2e-804b-cc9788186b0d",
        "name": "llamamergetoolrequestandcalls_messagetransform",
        "description": null,
        "metadata": {
          "__metadata_info__": {}
        },
        "component_plugin_name": "MessageTransformPlugin",
        "component_plugin_version": "25.4.0.dev0"
      }
    ],
    "tools": null,
    "native_tool_calling": false,
    "response_format": null,
    "native_structured_generation": true,
    "generation_config": null,
    "component_plugin_name": "PromptTemplatePlugin",
    "component_plugin_version": "25.4.0.dev0"
  },
  "component_plugin_name": "AgentPlugin",
  "component_plugin_version": "25.4.0.dev0",
  "$referenced_components": {
    "4f8e1008-2f20-456c-9250-679146e88192": {
      "component_type": "PluginInMemoryDatastore",
      "id": "4f8e1008-2f20-456c-9250-679146e88192",
      "name": "PluginInMemoryDatastore",
      "description": null,
      "metadata": {},
      "datastore_schema": {
        "products": {
          "description": "",
          "title": "",
          "properties": {
            "description": {
              "type": "string"
            },
            "ID": {
              "description": "Unique product identifier",
              "type": "integer"
            },
            "title": {
              "description": "Brief summary of the product",
              "type": "string"
            },
            "price": {
              "type": "number",
              "default": 0.1
            },
            "category": {
              "anyOf": [
                {
                  "type": "null"
                },
                {
                  "type": "string"
                }
              ],
              "default": null
            }
          }
        }
      },
      "component_plugin_name": "DatastorePlugin",
      "component_plugin_version": "25.4.0.dev0"
    }
  },
  "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: ExtendedAgent
id: 99f1d854-0f10-473a-ad2a-3558b8977244
name: agent_d18c1f13__auto
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs: []
llm_config:
  component_type: VllmConfig
  id: b10b47da-03bc-4bb3-a024-b2d8330a5be8
  name: LLAMA_MODEL_ID
  description: null
  metadata:
    __metadata_info__: {}
  default_generation_parameters: null
  url: LLAMA_API_URL
  model_id: LLAMA_MODEL_ID
system_prompt: '

  You are an inventory assistant. Your task is to help the user with their requests
  by using the available tools.

  If you are unsure about the action to take, or you don''t have the right tool, simply
  tell the user so and follow their guidance.

  '
tools: []
toolboxes: []
context_providers: null
can_finish_conversation: false
max_iterations: 10
initial_message: Hi! How can I help you?
caller_input_mode: always
agents: []
flows:
- component_type: Flow
  id: 96d3782c-552c-429c-bd7e-4f4af61ff713
  name: Create product
  description: Creates a new product in the data source
  metadata:
    __metadata_info__: {}
  inputs:
  - type: object
    additionalProperties: {}
    key_type:
      type: string
    title: entity
  outputs:
  - type: object
    additionalProperties: {}
    key_type:
      type: string
    title: created_entity
  start_node:
    $component_ref: 79b6331a-5543-4310-8d8b-1d9f1337b025
  nodes:
  - $component_ref: 331ca41a-8738-4751-a87e-5cc48b8a3e23
  - $component_ref: 79b6331a-5543-4310-8d8b-1d9f1337b025
  - $component_ref: ae2f0460-cba8-499e-a993-62b946e56d40
  control_flow_connections:
  - component_type: ControlFlowEdge
    id: fe4ef560-e504-4dc8-a298-7dbb3c067a6f
    name: __StartStep___to_step_0_control_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    from_node:
      $component_ref: 79b6331a-5543-4310-8d8b-1d9f1337b025
    from_branch: null
    to_node:
      $component_ref: 331ca41a-8738-4751-a87e-5cc48b8a3e23
  - component_type: ControlFlowEdge
    id: a16d091c-0d0c-4d29-9104-7761bdbb4cd3
    name: step_0_to_None End node_control_flow_edge
    description: null
    metadata: {}
    from_node:
      $component_ref: 331ca41a-8738-4751-a87e-5cc48b8a3e23
    from_branch: null
    to_node:
      $component_ref: ae2f0460-cba8-499e-a993-62b946e56d40
  data_flow_connections:
  - component_type: DataFlowEdge
    id: 58dbd841-e0a5-4c87-ac0c-08a34625323b
    name: __StartStep___entity_to_step_0_entity_data_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    source_node:
      $component_ref: 79b6331a-5543-4310-8d8b-1d9f1337b025
    source_output: entity
    destination_node:
      $component_ref: 331ca41a-8738-4751-a87e-5cc48b8a3e23
    destination_input: entity
  - component_type: DataFlowEdge
    id: 92415266-d5a4-40ca-b8e6-57e01ec002a5
    name: step_0_created_entity_to_None End node_created_entity_data_flow_edge
    description: null
    metadata: {}
    source_node:
      $component_ref: 331ca41a-8738-4751-a87e-5cc48b8a3e23
    source_output: created_entity
    destination_node:
      $component_ref: ae2f0460-cba8-499e-a993-62b946e56d40
    destination_input: created_entity
  $referenced_components:
    331ca41a-8738-4751-a87e-5cc48b8a3e23:
      component_type: PluginDatastoreCreateNode
      id: 331ca41a-8738-4751-a87e-5cc48b8a3e23
      name: step_0
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - type: object
        additionalProperties: {}
        key_type:
          type: string
        title: entity
      outputs:
      - type: object
        additionalProperties: {}
        key_type:
          type: string
        title: created_entity
      branches:
      - next
      input_mapping: {}
      output_mapping: {}
      datastore:
        $component_ref: 4f8e1008-2f20-456c-9250-679146e88192
      collection_name: products
      ENTITY: entity
      CREATED_ENTITY: created_entity
      component_plugin_name: DatastorePlugin
      component_plugin_version: 25.4.0.dev0
    79b6331a-5543-4310-8d8b-1d9f1337b025:
      component_type: StartNode
      id: 79b6331a-5543-4310-8d8b-1d9f1337b025
      name: __StartStep__
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - type: object
        additionalProperties: {}
        key_type:
          type: string
        title: entity
      outputs:
      - type: object
        additionalProperties: {}
        key_type:
          type: string
        title: entity
      branches:
      - next
    ae2f0460-cba8-499e-a993-62b946e56d40:
      component_type: EndNode
      id: ae2f0460-cba8-499e-a993-62b946e56d40
      name: None End node
      description: End node representing all transitions to None in the WayFlow flow
      metadata: {}
      inputs:
      - type: object
        additionalProperties: {}
        key_type:
          type: string
        title: created_entity
      outputs:
      - type: object
        additionalProperties: {}
        key_type:
          type: string
        title: created_entity
      branches: []
      branch_name: next
- component_type: Flow
  id: ba1cd504-bef6-4af3-9498-cbf6e50a0bca
  name: List all products
  description: Lists all products in the data source.
  metadata:
    __metadata_info__: {}
  inputs: []
  outputs:
  - type: array
    items:
      type: object
      additionalProperties: {}
      key_type:
        type: string
    title: entities
  start_node:
    $component_ref: bb1b722a-0aae-4e09-b2a4-cbcdb93b2cff
  nodes:
  - $component_ref: 0c924103-23f5-4698-b69e-c553250186ab
  - $component_ref: bb1b722a-0aae-4e09-b2a4-cbcdb93b2cff
  - $component_ref: 098f2832-4672-44eb-a060-ea9514ceefc5
  control_flow_connections:
  - component_type: ControlFlowEdge
    id: a0392cfe-bed3-44cb-84c0-20a30f1cbe18
    name: __StartStep___to_step_0_control_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    from_node:
      $component_ref: bb1b722a-0aae-4e09-b2a4-cbcdb93b2cff
    from_branch: null
    to_node:
      $component_ref: 0c924103-23f5-4698-b69e-c553250186ab
  - component_type: ControlFlowEdge
    id: 3290795e-59ca-46f8-8a96-5a265d707c13
    name: step_0_to_None End node_control_flow_edge
    description: null
    metadata: {}
    from_node:
      $component_ref: 0c924103-23f5-4698-b69e-c553250186ab
    from_branch: null
    to_node:
      $component_ref: 098f2832-4672-44eb-a060-ea9514ceefc5
  data_flow_connections:
  - component_type: DataFlowEdge
    id: 308b92b6-70f4-4e9c-b41e-1563bc449a24
    name: step_0_entities_to_None End node_entities_data_flow_edge
    description: null
    metadata: {}
    source_node:
      $component_ref: 0c924103-23f5-4698-b69e-c553250186ab
    source_output: entities
    destination_node:
      $component_ref: 098f2832-4672-44eb-a060-ea9514ceefc5
    destination_input: entities
  $referenced_components:
    098f2832-4672-44eb-a060-ea9514ceefc5:
      component_type: EndNode
      id: 098f2832-4672-44eb-a060-ea9514ceefc5
      name: None End node
      description: End node representing all transitions to None in the WayFlow flow
      metadata: {}
      inputs:
      - type: array
        items:
          type: object
          additionalProperties: {}
          key_type:
            type: string
        title: entities
      outputs:
      - type: array
        items:
          type: object
          additionalProperties: {}
          key_type:
            type: string
        title: entities
      branches: []
      branch_name: next
    0c924103-23f5-4698-b69e-c553250186ab:
      component_type: PluginDatastoreListNode
      id: 0c924103-23f5-4698-b69e-c553250186ab
      name: step_0
      description: ''
      metadata:
        __metadata_info__: {}
      inputs: []
      outputs:
      - type: array
        items:
          type: object
          additionalProperties: {}
          key_type:
            type: string
        title: entities
      branches:
      - next
      input_mapping: {}
      output_mapping: {}
      datastore:
        $component_ref: 4f8e1008-2f20-456c-9250-679146e88192
      collection_name: products
      where: null
      limit: null
      unpack_single_entity_from_list: false
      ENTITIES: entities
      component_plugin_name: DatastorePlugin
      component_plugin_version: 25.4.0.dev0
    bb1b722a-0aae-4e09-b2a4-cbcdb93b2cff:
      component_type: StartNode
      id: bb1b722a-0aae-4e09-b2a4-cbcdb93b2cff
      name: __StartStep__
      description: ''
      metadata:
        __metadata_info__: {}
      inputs: []
      outputs: []
      branches:
      - next
- component_type: Flow
  id: bad00138-48b3-4e7c-84a9-51bd385a38a2
  name: List single product
  description: Lists a single product in the data source by its title.
  metadata:
    __metadata_info__: {}
  inputs:
  - description: '"user_requested_product" input variable for the template'
    type: string
    title: user_requested_product
  outputs:
  - type: object
    additionalProperties: {}
    key_type:
      type: string
    title: entities
  start_node:
    $component_ref: 76d19c9a-241f-4a4d-bbac-2bcbd3359498
  nodes:
  - $component_ref: d1b1f436-b91f-435c-867c-ecf9b5b187a1
  - $component_ref: 76d19c9a-241f-4a4d-bbac-2bcbd3359498
  - $component_ref: aa8090d6-2220-40ad-ab16-6adb1bdead7b
  control_flow_connections:
  - component_type: ControlFlowEdge
    id: e37ae190-e7f6-4090-8091-c5eddadf7a9d
    name: __StartStep___to_product_list_step_control_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    from_node:
      $component_ref: 76d19c9a-241f-4a4d-bbac-2bcbd3359498
    from_branch: null
    to_node:
      $component_ref: d1b1f436-b91f-435c-867c-ecf9b5b187a1
  - component_type: ControlFlowEdge
    id: 80680849-e51b-435d-aee6-cdb7e6571ee7
    name: product_list_step_to_None End node_control_flow_edge
    description: null
    metadata: {}
    from_node:
      $component_ref: d1b1f436-b91f-435c-867c-ecf9b5b187a1
    from_branch: null
    to_node:
      $component_ref: aa8090d6-2220-40ad-ab16-6adb1bdead7b
  data_flow_connections:
  - component_type: DataFlowEdge
    id: dab6eb95-057c-4adc-85dd-2a40e14713eb
    name: __StartStep___user_requested_product_to_product_list_step_user_requested_product_data_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    source_node:
      $component_ref: 76d19c9a-241f-4a4d-bbac-2bcbd3359498
    source_output: user_requested_product
    destination_node:
      $component_ref: d1b1f436-b91f-435c-867c-ecf9b5b187a1
    destination_input: user_requested_product
  - component_type: DataFlowEdge
    id: 82d0a256-6c3d-45a8-a6bf-c1c949069927
    name: product_list_step_entities_to_None End node_entities_data_flow_edge
    description: null
    metadata: {}
    source_node:
      $component_ref: d1b1f436-b91f-435c-867c-ecf9b5b187a1
    source_output: entities
    destination_node:
      $component_ref: aa8090d6-2220-40ad-ab16-6adb1bdead7b
    destination_input: entities
  $referenced_components:
    d1b1f436-b91f-435c-867c-ecf9b5b187a1:
      component_type: PluginDatastoreListNode
      id: d1b1f436-b91f-435c-867c-ecf9b5b187a1
      name: product_list_step
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - description: '"user_requested_product" input variable for the template'
        type: string
        title: user_requested_product
      outputs:
      - type: object
        additionalProperties: {}
        key_type:
          type: string
        title: entities
      branches:
      - next
      input_mapping: {}
      output_mapping: {}
      datastore:
        $component_ref: 4f8e1008-2f20-456c-9250-679146e88192
      collection_name: products
      where:
        title: '{{user_requested_product}}'
      limit: 1
      unpack_single_entity_from_list: true
      ENTITIES: entities
      component_plugin_name: DatastorePlugin
      component_plugin_version: 25.4.0.dev0
    76d19c9a-241f-4a4d-bbac-2bcbd3359498:
      component_type: StartNode
      id: 76d19c9a-241f-4a4d-bbac-2bcbd3359498
      name: __StartStep__
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - description: '"user_requested_product" input variable for the template'
        type: string
        title: user_requested_product
      outputs:
      - description: '"user_requested_product" input variable for the template'
        type: string
        title: user_requested_product
      branches:
      - next
    aa8090d6-2220-40ad-ab16-6adb1bdead7b:
      component_type: EndNode
      id: aa8090d6-2220-40ad-ab16-6adb1bdead7b
      name: None End node
      description: End node representing all transitions to None in the WayFlow flow
      metadata: {}
      inputs:
      - type: object
        additionalProperties: {}
        key_type:
          type: string
        title: entities
      outputs:
      - type: object
        additionalProperties: {}
        key_type:
          type: string
        title: entities
      branches: []
      branch_name: next
- component_type: Flow
  id: a3047067-dea3-4cc9-a922-c26d35d97c48
  name: Update product
  description: Updates a product in the data source by its title.
  metadata:
    __metadata_info__: {}
  inputs:
  - description: '"user_requested_product" input variable for the template'
    type: string
    title: user_requested_product
  - type: object
    additionalProperties: {}
    key_type:
      type: string
    title: update
  outputs:
  - type: array
    items:
      type: object
      additionalProperties: {}
      key_type:
        type: string
    title: entities
  start_node:
    $component_ref: 8c74a4c5-fdf0-447e-956f-59498da1dc09
  nodes:
  - $component_ref: 487a708b-0553-4bb5-b015-948d2a97ede6
  - $component_ref: 8c74a4c5-fdf0-447e-956f-59498da1dc09
  - $component_ref: 9074c861-1cf4-4bd9-88dd-3fe209b2c218
  control_flow_connections:
  - component_type: ControlFlowEdge
    id: 64436400-797d-4d35-92df-78fc557006f2
    name: __StartStep___to_product_update_step_control_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    from_node:
      $component_ref: 8c74a4c5-fdf0-447e-956f-59498da1dc09
    from_branch: null
    to_node:
      $component_ref: 487a708b-0553-4bb5-b015-948d2a97ede6
  - component_type: ControlFlowEdge
    id: 5e55b5d7-7bf8-435a-9044-f05f1b377671
    name: product_update_step_to_None End node_control_flow_edge
    description: null
    metadata: {}
    from_node:
      $component_ref: 487a708b-0553-4bb5-b015-948d2a97ede6
    from_branch: null
    to_node:
      $component_ref: 9074c861-1cf4-4bd9-88dd-3fe209b2c218
  data_flow_connections:
  - component_type: DataFlowEdge
    id: 43c29773-0a4b-4145-9c0d-ad5238410e9d
    name: __StartStep___user_requested_product_to_product_update_step_user_requested_product_data_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    source_node:
      $component_ref: 8c74a4c5-fdf0-447e-956f-59498da1dc09
    source_output: user_requested_product
    destination_node:
      $component_ref: 487a708b-0553-4bb5-b015-948d2a97ede6
    destination_input: user_requested_product
  - component_type: DataFlowEdge
    id: 8e5f0ea8-8ea1-42ba-bdba-95a74082c908
    name: __StartStep___update_to_product_update_step_update_data_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    source_node:
      $component_ref: 8c74a4c5-fdf0-447e-956f-59498da1dc09
    source_output: update
    destination_node:
      $component_ref: 487a708b-0553-4bb5-b015-948d2a97ede6
    destination_input: update
  - component_type: DataFlowEdge
    id: 1bd34870-1e52-4896-bfaf-5a71006da687
    name: product_update_step_entities_to_None End node_entities_data_flow_edge
    description: null
    metadata: {}
    source_node:
      $component_ref: 487a708b-0553-4bb5-b015-948d2a97ede6
    source_output: entities
    destination_node:
      $component_ref: 9074c861-1cf4-4bd9-88dd-3fe209b2c218
    destination_input: entities
  $referenced_components:
    487a708b-0553-4bb5-b015-948d2a97ede6:
      component_type: PluginDatastoreUpdateNode
      id: 487a708b-0553-4bb5-b015-948d2a97ede6
      name: product_update_step
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - description: '"user_requested_product" input variable for the template'
        type: string
        title: user_requested_product
      - type: object
        additionalProperties: {}
        key_type:
          type: string
        title: update
      outputs:
      - type: array
        items:
          type: object
          additionalProperties: {}
          key_type:
            type: string
        title: entities
      branches:
      - next
      input_mapping: {}
      output_mapping: {}
      datastore:
        $component_ref: 4f8e1008-2f20-456c-9250-679146e88192
      collection_name: products
      where:
        title: '{{user_requested_product}}'
      ENTITIES: entities
      UPDATE: update
      component_plugin_name: DatastorePlugin
      component_plugin_version: 25.4.0.dev0
    8c74a4c5-fdf0-447e-956f-59498da1dc09:
      component_type: StartNode
      id: 8c74a4c5-fdf0-447e-956f-59498da1dc09
      name: __StartStep__
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - description: '"user_requested_product" input variable for the template'
        type: string
        title: user_requested_product
      - type: object
        additionalProperties: {}
        key_type:
          type: string
        title: update
      outputs:
      - description: '"user_requested_product" input variable for the template'
        type: string
        title: user_requested_product
      - type: object
        additionalProperties: {}
        key_type:
          type: string
        title: update
      branches:
      - next
    9074c861-1cf4-4bd9-88dd-3fe209b2c218:
      component_type: EndNode
      id: 9074c861-1cf4-4bd9-88dd-3fe209b2c218
      name: None End node
      description: End node representing all transitions to None in the WayFlow flow
      metadata: {}
      inputs:
      - type: array
        items:
          type: object
          additionalProperties: {}
          key_type:
            type: string
        title: entities
      outputs:
      - type: array
        items:
          type: object
          additionalProperties: {}
          key_type:
            type: string
        title: entities
      branches: []
      branch_name: next
- component_type: Flow
  id: ebae9461-df3a-4544-9cfd-dd2a2e13e34e
  name: Delete product
  description: Delete a product in the data source by its title.
  metadata:
    __metadata_info__: {}
  inputs:
  - description: '"product_title" input variable for the template'
    type: string
    title: product_title
  outputs: []
  start_node:
    $component_ref: 13d561e4-1c49-4808-974c-d82311479998
  nodes:
  - $component_ref: 9cd4c282-5290-477d-b9c1-f069a599aa68
  - $component_ref: 13d561e4-1c49-4808-974c-d82311479998
  - $component_ref: 49384f2b-1825-4c6b-a876-86e8803b0014
  control_flow_connections:
  - component_type: ControlFlowEdge
    id: 7b91ecf7-f24e-4ff3-8df4-f6769847e7a4
    name: __StartStep___to_step_0_control_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    from_node:
      $component_ref: 13d561e4-1c49-4808-974c-d82311479998
    from_branch: null
    to_node:
      $component_ref: 9cd4c282-5290-477d-b9c1-f069a599aa68
  - component_type: ControlFlowEdge
    id: e666dfe3-6041-4141-b21b-afedfa74f3ab
    name: step_0_to_None End node_control_flow_edge
    description: null
    metadata: {}
    from_node:
      $component_ref: 9cd4c282-5290-477d-b9c1-f069a599aa68
    from_branch: null
    to_node:
      $component_ref: 49384f2b-1825-4c6b-a876-86e8803b0014
  data_flow_connections:
  - component_type: DataFlowEdge
    id: a731fb73-ad3b-4a22-9f0b-35e9f1d63131
    name: __StartStep___product_title_to_step_0_product_title_data_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    source_node:
      $component_ref: 13d561e4-1c49-4808-974c-d82311479998
    source_output: product_title
    destination_node:
      $component_ref: 9cd4c282-5290-477d-b9c1-f069a599aa68
    destination_input: product_title
  $referenced_components:
    9cd4c282-5290-477d-b9c1-f069a599aa68:
      component_type: PluginDatastoreDeleteNode
      id: 9cd4c282-5290-477d-b9c1-f069a599aa68
      name: step_0
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - description: '"product_title" input variable for the template'
        type: string
        title: product_title
      outputs: []
      branches:
      - next
      input_mapping: {}
      output_mapping: {}
      datastore:
        $component_ref: 4f8e1008-2f20-456c-9250-679146e88192
      collection_name: products
      where:
        title: '{{product_title}}'
      component_plugin_name: DatastorePlugin
      component_plugin_version: 25.4.0.dev0
    13d561e4-1c49-4808-974c-d82311479998:
      component_type: StartNode
      id: 13d561e4-1c49-4808-974c-d82311479998
      name: __StartStep__
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - description: '"product_title" input variable for the template'
        type: string
        title: product_title
      outputs:
      - description: '"product_title" input variable for the template'
        type: string
        title: product_title
      branches:
      - next
    49384f2b-1825-4c6b-a876-86e8803b0014:
      component_type: EndNode
      id: 49384f2b-1825-4c6b-a876-86e8803b0014
      name: None End node
      description: End node representing all transitions to None in the WayFlow flow
      metadata: {}
      inputs: []
      outputs: []
      branches: []
      branch_name: next
agent_template:
  component_type: PluginPromptTemplate
  id: ea261004-a6d8-4380-af2a-4e5adbaf7b9c
  name: ''
  description: null
  metadata:
    __metadata_info__: {}
  messages:
  - role: system
    contents:
    - type: text
      content: '{%- if __TOOLS__ -%}

        Environment: ipython

        Cutting Knowledge Date: December 2023


        You are a helpful assistant with tool calling capabilities. Only reply with
        a tool call if the function exists in the library provided by the user. If
        it doesn''t exist, just reply directly in natural language. When you receive
        a tool call response, use the output to format an answer to the original user
        question.


        You have access to the following functions. To call a function, please respond
        with JSON for a function call.

        Respond in the format {"name": function name, "parameters": dictionary of
        argument name and its value}.

        Do not use variables.


        [{% for tool in __TOOLS__%}{{tool.to_openai_format() | tojson}}{{'', '' if
        not loop.last}}{% endfor %}]

        {%- endif -%}

        '
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-09-02T15:58:42.673848+00:00'
    time_updated: '2025-09-02T15:58:42.673852+00:00'
  - role: system
    contents:
    - type: text
      content: '{%- if custom_instruction -%}Additional instructions:

        {{custom_instruction}}{%- endif -%}'
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-09-02T15:58:42.673915+00:00'
    time_updated: '2025-09-02T15:58:42.673916+00:00'
  - role: user
    contents: []
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-09-02T15:58:42.660189+00:00'
    time_updated: '2025-09-02T15:58:42.660446+00:00'
  - role: system
    contents:
    - type: text
      content: "{% if __PLAN__ %}The current plan you should follow is the following:\
        \ \n{{__PLAN__}}{% endif %}"
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-09-02T15:58:42.673985+00:00'
    time_updated: '2025-09-02T15:58:42.673986+00:00'
  output_parser:
    component_type: PluginJsonToolOutputParser
    id: 8d8b00f0-2c13-4e0f-894c-a46ad91eccbc
    name: jsontool_outputparser
    description: null
    metadata:
      __metadata_info__: {}
    tools: null
    component_plugin_name: OutputParserPlugin
    component_plugin_version: 25.4.0.dev0
  inputs:
  - description: '"__TOOLS__" input variable for the template'
    title: __TOOLS__
  - description: '"custom_instruction" input variable for the template'
    type: string
    title: custom_instruction
  - description: '"__PLAN__" input variable for the template'
    type: string
    title: __PLAN__
    default: ''
  - type: array
    items: {}
    title: __CHAT_HISTORY__
  pre_rendering_transforms: null
  post_rendering_transforms:
  - component_type: PluginRemoveEmptyNonUserMessageTransform
    id: f964b648-4850-43ca-983b-6bf05ec6fe59
    name: removeemptynonusermessage_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 25.4.0.dev0
  - component_type: PluginCoalesceSystemMessagesTransform
    id: b0c702f1-14a8-4692-b746-490f3cc2a406
    name: coalescesystemmessage_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 25.4.0.dev0
  - component_type: PluginLlamaMergeToolRequestAndCallsTransform
    id: 466f3fef-697b-4e2e-804b-cc9788186b0d
    name: llamamergetoolrequestandcalls_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 25.4.0.dev0
  tools: null
  native_tool_calling: false
  response_format: null
  native_structured_generation: true
  generation_config: null
  component_plugin_name: PromptTemplatePlugin
  component_plugin_version: 25.4.0.dev0
component_plugin_name: AgentPlugin
component_plugin_version: 25.4.0.dev0
$referenced_components:
  4f8e1008-2f20-456c-9250-679146e88192:
    component_type: PluginInMemoryDatastore
    id: 4f8e1008-2f20-456c-9250-679146e88192
    name: PluginInMemoryDatastore
    description: null
    metadata: {}
    datastore_schema:
      products:
        description: ''
        title: ''
        properties:
          description:
            type: string
          ID:
            description: Unique product identifier
            type: integer
          title:
            description: Brief summary of the product
            type: string
          price:
            type: number
            default: 0.1
          category:
            anyOf:
            - type: 'null'
            - type: string
            default: null
    component_plugin_name: DatastorePlugin
    component_plugin_version: 25.4.0.dev0
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader().load_json(serialized_agent)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `PluginPromptTemplate`
- `PluginDatastoreCreateNode`
- `PluginDatastoreUpdateNode`
- `PluginDatastoreListNode`
- `PluginDatastoreDeleteNode`
- `PluginJsonToolOutputParser`
- `PluginRemoveEmptyNonUserMessageTransform`
- `PluginCoalesceSystemMessagesTransform`
- `PluginLlamaMergeToolRequestAndCallsTransform`
- `PluginInMemoryDatastore`
- `ExtendedAgent`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

<a id="using-oracle-datastore"></a>

## Using Oracle Database Datastore

This guide mirrors the earlier **in-memory** demo, but leverages Oracle Database
(Autonomous Database on OCI or an on-prem instance) for persistent storage.

#### Prerequisites
* An Oracle Database instance, reachable from your development machine
* Wallet files and/or database credentials for this instance
* A running LLM endpoint (the examples uses vLLM, but any provider works)

### Step 1. Configure the connection to the Database

WayFlow supports two secure transport mechanisms for connecting to Oracle databases.

When using **TLS** (one-way TLS) the database presents its certificate, the client verifies it,
and the user authenticates with username and password.

```python
connection_config = TlsOracleDatabaseConnectionConfig(
    user="<db user>",  # Replace with your DB user
    password="<db password>",  # Replace with your DB password  # nosec: this is just a placeholder
    dsn="<db connection string>",  # e.g. "(description=(retry_count=2)..."
    # This is optional, but helpful to re-configure credentials when loading the AgentSpec config for this object
    id="oracle_datastore_connection_config",
)
```

When using **mTLS** (mutual TLS) both sides exchange certificates: the client proves its identity
with a wallet (client cert + private key) in addition to the username and password.
This gives stronger, certificate-based client authentication and is often required for
Oracle Autonomous Database in “Require mTLS” mode.

```python
from wayflowcore.datastore import MTlsOracleDatabaseConnectionConfig

connection_config = MTlsOracleDatabaseConnectionConfig(
    config_dir="./oracle-wallet",
    dsn="<dbname>",  # Entry in tnsnames.ora
    wallet_location="./oracle-wallet",
    wallet_password="<your wallet password>",  # Replace with your wallet password  # nosec: this is just a placeholder
    user="<db user>",  # Replace with your DB user
    password="<db password>",  # Replace with your DB password  # nosec: this is just a placeholder
    # This is optional, but helpful to re-configure credentials when loading the AgentSpec config for this object
    id="oracle_datastore_connection_config",
)
```

#### IMPORTANT
Do **not** hard-code any database credentials or sensitive connection details directly in your code.
Please refer to our [Security Guidelines](../security.md) for more information.

#### Step 2. Define the data model and Datastore

#### WARNING
The following code snippet will create a new `products` table in the database.
Ensure you are using a throwaway schema with no other table named “products” when running this example.

For this guide, we use the same data model as in the in-memory example.
It manages products in an inventory, so a single collection is sufficient.
Datastores also support managing multiple database tables at the same time if needed.

Entities map the relational schema to strongly-typed objects that Flows and
Agents can validate at runtime.
The key difference to the in-memory example is that we require the Entity of
interest to be already defined as a table in the database.

Note that, if you have some columns in the database that are not relevant to your assistant,
you may simply omit them from the Entity definition (as is done in this example with the `external_system_id`).
However, it may not be possible for the datastore or assistant to create such entities if the omitted columns are required.

```python
table_definition = """CREATE TABLE products (
    ID NUMBER PRIMARY KEY,
    title VARCHAR2(255) NOT NULL,
    description VARCHAR2(255) NOT NULL,
    price NUMBER NOT NULL,
    category VARCHAR2(255) DEFAULT NULL,
    external_system_id NUMBER DEFAULT NULL
)"""

with connection_config.get_connection() as connection:
    connection.cursor().execute(table_definition)

product = Entity(
    properties={
        "ID": IntegerProperty(description="Unique product identifier"),
        # Descriptions can be helpful if an LLM needs to fill these fields,
        # or generally disambiguate non-obvious property names
        "title": StringProperty(description="Brief summary of the product"),
        "description": StringProperty(),
        "price": FloatProperty(default_value=0.1),
        # Use nullable to define optional properties
        "category": nullable(StringProperty()),
    },
)

datastore = OracleDatabaseDatastore(
    schema={"products": product}, connection_config=connection_config
)

dummy_data = [
    {
        "ID": 0,
        "title": "Broccoli",
        "description": "Healthy and delicious cruciferous vegetable!",
        "price": 1.5,
        "category": "Produce",
    },
    {
        "ID": 1,
        "title": "Oranges",
        # We introduce a typo in this entity for the Assistant to fix
        "description": "Vitamin C-filled cirus fruits",
        "price": 1.8,
        "category": "Produce",
    },
    {
        "ID": 2,
        "title": "Shampoo",
        "description": "Shiny smooth hair in just 10 applications!",
        "price": 4.5,
        "category": "Personal hygiene",
    },
    {
        "ID": 3,
        "title": "Crushed ice",
        "description": "Cool any drink in seconds!",
        "price": 4.5,
        "category": "Food",
    },
]

# Create supports both bulk-creation, as well as single element creation
datastore.create(collection_name="products", entities=dummy_data)
```

### Step 3. Create datastore steps

Now that the Datastore is set up, create steps to perform different operations in the flow.
In this guide, your assistant will identify inconsistencies in product descriptions of the same category.
To do so, you will use the [DatastoreQueryStep](../api/flows.md#datastorequerystep) to fetch product information, and a [PromptExecutionStep](../api/flows.md#promptexecutionstep) to identify the issues.

In particular, the `DatastoreQueryStep` can be used with Database Datastores to execute developer-defined SQL queries.
These queries can optionally be parametrized with bind variables.
See the [bind variables guide on the python-oracledb documentation](https://python-oracledb.readthedocs.io/en/latest/user_guide/bind.html) for more information.
See also [the list of all available Datastore steps](../api/flows.md#datastoresteps) for additional operations that can be performed with Oracle Database Datastores.

```python
datastore_query_step = DatastoreQueryStep(
    datastore,
    "SELECT title, description FROM products WHERE category = :product_category",
    name="product_selection_step",
    input_descriptors=[
        ObjectProperty("bind_variables", properties={"product_category": StringProperty("")})
    ],
)

detect_issues_prompt_template = dedent(
    """You are an inventory assistant.

    Your task:
        - Summarize potential inconsistencies across descriptions of products in the same category.
          For example, identify typos and highlight improvement opportunities
    Important:
        - Be helpful and concise in your messages

    Here are the product descriptions:
    {{ products }}
    """
)

llm_issue_detection_step = PromptExecutionStep(
    prompt_template=detect_issues_prompt_template,
    llm=llm,
)

user_output_step = OutputMessageStep(
    message_template="The following issues have been identified: {{ issues }}",
)

assistant = Flow(
    begin_step=datastore_query_step,
    control_flow_edges=[
        ControlFlowEdge(
            source_step=datastore_query_step, destination_step=llm_issue_detection_step
        ),
        ControlFlowEdge(source_step=llm_issue_detection_step, destination_step=user_output_step),
        ControlFlowEdge(source_step=user_output_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            datastore_query_step, DatastoreQueryStep.RESULT, llm_issue_detection_step, "products"
        ),
        DataFlowEdge(
            llm_issue_detection_step, PromptExecutionStep.OUTPUT, user_output_step, "issues"
        ),
    ],
)
```

Finally, verify that the Flow works as expected:

```python
conversation = assistant.start_conversation({"bind_variables": {"product_category": "Produce"}})
conversation.execute()
print(conversation.get_last_message().content)
```

## Agent Spec Exporting/Loading

This flow can be exported to Agent Spec using the `AgentSpecExporter` as you have seen in the
previous in-memory example, using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(assistant)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
    "component_type": "Flow",
    "id": "e1ce33a4-df88-4652-9714-6b51fea8871b",
    "name": "flow_2b8b504d__auto",
    "description": "",
    "metadata": {
        "__metadata_info__": {}
    },
    "inputs": [
        {
            "type": "object",
            "properties": {
                "product_category": {
                    "type": "string"
                }
            },
            "title": "bind_variables"
        }
    ],
    "outputs": [
        {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": {},
                "key_type": {
                    "type": "string"
                }
            },
            "title": "result"
        },
        {
            "description": "the generated text",
            "type": "string",
            "title": "output"
        },
        {
            "description": "the message added to the messages list",
            "type": "string",
            "title": "output_message"
        }
    ],
    "start_node": {
        "$component_ref": "9162d8ad-cf00-4fc2-bed7-a73ffed79b32"
    },
    "nodes": [
        {
            "$component_ref": "85190204-2604-4fd0-b94a-6b4eb8e37f4f"
        },
        {
            "$component_ref": "309c4bda-986e-4fd6-82b8-a83a91168d8d"
        },
        {
            "$component_ref": "9eab48d6-a51c-412e-a459-a7fd05283e1a"
        },
        {
            "$component_ref": "9162d8ad-cf00-4fc2-bed7-a73ffed79b32"
        },
        {
            "$component_ref": "992516a7-a3f8-4cac-ac0d-0b1cac4eb936"
        }
    ],
    "control_flow_connections": [
        {
            "component_type": "ControlFlowEdge",
            "id": "153fa298-b907-4453-84e4-7fa334fce680",
            "name": "product_selection_step_to_step_PromptExecutionStep_8f995292__auto_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "85190204-2604-4fd0-b94a-6b4eb8e37f4f"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "309c4bda-986e-4fd6-82b8-a83a91168d8d"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "bbb9d505-4aa6-4b58-8e8d-d50b1f4cc659",
            "name": "step_PromptExecutionStep_8f995292__auto_to_step_OutputMessageStep_2c68bdae__auto_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "309c4bda-986e-4fd6-82b8-a83a91168d8d"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "9eab48d6-a51c-412e-a459-a7fd05283e1a"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "8c4158f0-f48e-4a7b-8686-999efb70b7cb",
            "name": "__StartStep___to_product_selection_step_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "9162d8ad-cf00-4fc2-bed7-a73ffed79b32"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "85190204-2604-4fd0-b94a-6b4eb8e37f4f"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "05d5f99c-be1a-4f70-b0e2-4e85331016e1",
            "name": "step_OutputMessageStep_2c68bdae__auto_to_None End node_control_flow_edge",
            "description": null,
            "metadata": {},
            "from_node": {
                "$component_ref": "9eab48d6-a51c-412e-a459-a7fd05283e1a"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "992516a7-a3f8-4cac-ac0d-0b1cac4eb936"
            }
        }
    ],
    "data_flow_connections": [
        {
            "component_type": "DataFlowEdge",
            "id": "b34e1582-9c08-4ad2-871b-628edf98a0ee",
            "name": "product_selection_step_result_to_step_PromptExecutionStep_8f995292__auto_products_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "85190204-2604-4fd0-b94a-6b4eb8e37f4f"
            },
            "source_output": "result",
            "destination_node": {
                "$component_ref": "309c4bda-986e-4fd6-82b8-a83a91168d8d"
            },
            "destination_input": "products"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "d29d24f2-d0d1-469f-9ab4-fa12af5e76ee",
            "name": "step_PromptExecutionStep_8f995292__auto_output_to_step_OutputMessageStep_2c68bdae__auto_issues_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "309c4bda-986e-4fd6-82b8-a83a91168d8d"
            },
            "source_output": "output",
            "destination_node": {
                "$component_ref": "9eab48d6-a51c-412e-a459-a7fd05283e1a"
            },
            "destination_input": "issues"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "bc7a1760-8c23-4d0b-a985-b5b2cc14a90d",
            "name": "__StartStep___bind_variables_to_product_selection_step_bind_variables_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "9162d8ad-cf00-4fc2-bed7-a73ffed79b32"
            },
            "source_output": "bind_variables",
            "destination_node": {
                "$component_ref": "85190204-2604-4fd0-b94a-6b4eb8e37f4f"
            },
            "destination_input": "bind_variables"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "b3b92de4-10df-4abf-a9b0-149079c46408",
            "name": "product_selection_step_result_to_None End node_result_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
                "$component_ref": "85190204-2604-4fd0-b94a-6b4eb8e37f4f"
            },
            "source_output": "result",
            "destination_node": {
                "$component_ref": "992516a7-a3f8-4cac-ac0d-0b1cac4eb936"
            },
            "destination_input": "result"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "fa6df9aa-3e40-4923-a1d4-58cd7428c588",
            "name": "step_PromptExecutionStep_8f995292__auto_output_to_None End node_output_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
                "$component_ref": "309c4bda-986e-4fd6-82b8-a83a91168d8d"
            },
            "source_output": "output",
            "destination_node": {
                "$component_ref": "992516a7-a3f8-4cac-ac0d-0b1cac4eb936"
            },
            "destination_input": "output"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "aa996728-8289-48d2-a7b0-004d371b2d64",
            "name": "step_OutputMessageStep_2c68bdae__auto_output_message_to_None End node_output_message_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
                "$component_ref": "9eab48d6-a51c-412e-a459-a7fd05283e1a"
            },
            "source_output": "output_message",
            "destination_node": {
                "$component_ref": "992516a7-a3f8-4cac-ac0d-0b1cac4eb936"
            },
            "destination_input": "output_message"
        }
    ],
    "$referenced_components": {
        "9162d8ad-cf00-4fc2-bed7-a73ffed79b32": {
            "component_type": "StartNode",
            "id": "9162d8ad-cf00-4fc2-bed7-a73ffed79b32",
            "name": "__StartStep__",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "type": "object",
                    "properties": {
                        "product_category": {
                            "type": "string"
                        }
                    },
                    "title": "bind_variables"
                }
            ],
            "outputs": [
                {
                    "type": "object",
                    "properties": {
                        "product_category": {
                            "type": "string"
                        }
                    },
                    "title": "bind_variables"
                }
            ],
            "branches": [
                "next"
            ]
        },
        "85190204-2604-4fd0-b94a-6b4eb8e37f4f": {
            "component_type": "PluginDatastoreQueryNode",
            "id": "85190204-2604-4fd0-b94a-6b4eb8e37f4f",
            "name": "product_selection_step",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "type": "object",
                    "properties": {
                        "product_category": {
                            "type": "string"
                        }
                    },
                    "title": "bind_variables"
                }
            ],
            "outputs": [
                {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": {},
                        "key_type": {
                            "type": "string"
                        }
                    },
                    "title": "result"
                }
            ],
            "branches": [
                "next"
            ],
            "input_mapping": {},
            "output_mapping": {},
            "datastore": {
                "component_type": "PluginOracleDatabaseDatastore",
                "id": "2515997a-1dbf-47cb-9dfb-d1dd2dca1cee",
                "name": "PluginOracleDatabaseDatastore",
                "description": null,
                "metadata": {},
                "datastore_schema": {
                    "products": {
                        "description": "",
                        "title": "",
                        "properties": {
                            "description": {
                                "type": "string"
                            },
                            "ID": {
                                "description": "Unique product identifier",
                                "type": "integer"
                            },
                            "title": {
                                "description": "Brief summary of the product",
                                "type": "string"
                            },
                            "price": {
                                "type": "number",
                                "default": 0.1
                            },
                            "category": {
                                "anyOf": [
                                    {
                                        "type": "null"
                                    },
                                    {
                                        "type": "string"
                                    }
                                ],
                                "default": null
                            }
                        }
                    }
                },
                "connection_config": {
                    "component_type": "PluginTlsOracleDatabaseConnectionConfig",
                    "id": "13f2fc32-f442-49fb-b7cc-142a240bb8bc",
                    "name": "PluginTlsOracleDatabaseConnectionConfig",
                    "description": null,
                    "metadata": {},
                    "user": {
                        "$component_ref": "13f2fc32-f442-49fb-b7cc-142a240bb8bc.user"
                    },
                    "password": {
                        "$component_ref": "13f2fc32-f442-49fb-b7cc-142a240bb8bc.password"
                    },
                    "dsn": {
                        "$component_ref": "13f2fc32-f442-49fb-b7cc-142a240bb8bc.dsn"
                    },
                    "config_dir": null,
                    "component_plugin_name": "DatastorePlugin",
                    "component_plugin_version": "26.1.0.dev0"
                },
                "component_plugin_name": "DatastorePlugin",
                "component_plugin_version": "26.1.0.dev0"
            },
            "query": "SELECT title, description FROM products WHERE category = :product_category",
            "RESULT": "result",
            "component_plugin_name": "DatastorePlugin",
            "component_plugin_version": "26.1.0.dev0"
        },
        "309c4bda-986e-4fd6-82b8-a83a91168d8d": {
            "component_type": "LlmNode",
            "id": "309c4bda-986e-4fd6-82b8-a83a91168d8d",
            "name": "step_PromptExecutionStep_8f995292__auto",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "description": "\"products\" input variable for the template",
                    "type": "string",
                    "title": "products"
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
                "id": "115a6849-0e1b-4b1b-8bd2-be872c9bc64b",
                "name": "llm_41795d1f__auto",
                "description": null,
                "metadata": {
                    "__metadata_info__": {}
                },
                "default_generation_parameters": null,
                "url": "LLAMA_API_URL",
                "model_id": "LLAMA_MODEL_ID",
                "api_type": "chat_completions",
                "api_key": null
            },
            "prompt_template": "You are an inventory assistant.\n\n    Your task:\n        - Summarize potential inconsistencies across descriptions of products in the same category.\n          For example, identify typos and highlight improvement opportunities\n    Important:\n        - Be helpful and concise in your messages\n\n    Here are the product descriptions:\n    {{ products }}\n"
        },
        "9eab48d6-a51c-412e-a459-a7fd05283e1a": {
            "component_type": "PluginOutputMessageNode",
            "id": "9eab48d6-a51c-412e-a459-a7fd05283e1a",
            "name": "step_OutputMessageStep_2c68bdae__auto",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "description": "\"issues\" input variable for the template",
                    "type": "string",
                    "title": "issues"
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
            "message": "The following issues have been identified: {{ issues }}",
            "input_mapping": {},
            "output_mapping": {},
            "message_type": "AGENT",
            "rephrase": false,
            "llm_config": null,
            "expose_message_as_output": true,
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "26.1.0.dev0"
        },
        "992516a7-a3f8-4cac-ac0d-0b1cac4eb936": {
            "component_type": "EndNode",
            "id": "992516a7-a3f8-4cac-ac0d-0b1cac4eb936",
            "name": "None End node",
            "description": "End node representing all transitions to None in the WayFlow flow",
            "metadata": {},
            "inputs": [
                {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": {},
                        "key_type": {
                            "type": "string"
                        }
                    },
                    "title": "result"
                },
                {
                    "description": "the generated text",
                    "type": "string",
                    "title": "output"
                },
                {
                    "description": "the message added to the messages list",
                    "type": "string",
                    "title": "output_message"
                }
            ],
            "outputs": [
                {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": {},
                        "key_type": {
                            "type": "string"
                        }
                    },
                    "title": "result"
                },
                {
                    "description": "the generated text",
                    "type": "string",
                    "title": "output"
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
    "agentspec_version": "26.1.0"
}
```

YAML

```yaml
component_type: Flow
id: e1ce33a4-df88-4652-9714-6b51fea8871b
name: flow_2b8b504d__auto
description: ''
metadata:
  __metadata_info__: {}
inputs:
- type: object
  properties:
    product_category:
      type: string
  title: bind_variables
outputs:
- type: array
  items:
    type: object
    additionalProperties: {}
    key_type:
      type: string
  title: result
- description: the generated text
  type: string
  title: output
- description: the message added to the messages list
  type: string
  title: output_message
start_node:
  $component_ref: 9162d8ad-cf00-4fc2-bed7-a73ffed79b32
nodes:
- $component_ref: 85190204-2604-4fd0-b94a-6b4eb8e37f4f
- $component_ref: 309c4bda-986e-4fd6-82b8-a83a91168d8d
- $component_ref: 9eab48d6-a51c-412e-a459-a7fd05283e1a
- $component_ref: 9162d8ad-cf00-4fc2-bed7-a73ffed79b32
- $component_ref: 9f7c1027-0ed4-480d-918b-22a74656a00f
control_flow_connections:
- component_type: ControlFlowEdge
  id: 153fa298-b907-4453-84e4-7fa334fce680
  name: product_selection_step_to_step_PromptExecutionStep_8f995292__auto_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 85190204-2604-4fd0-b94a-6b4eb8e37f4f
  from_branch: null
  to_node:
    $component_ref: 309c4bda-986e-4fd6-82b8-a83a91168d8d
- component_type: ControlFlowEdge
  id: bbb9d505-4aa6-4b58-8e8d-d50b1f4cc659
  name: step_PromptExecutionStep_8f995292__auto_to_step_OutputMessageStep_2c68bdae__auto_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 309c4bda-986e-4fd6-82b8-a83a91168d8d
  from_branch: null
  to_node:
    $component_ref: 9eab48d6-a51c-412e-a459-a7fd05283e1a
- component_type: ControlFlowEdge
  id: 8c4158f0-f48e-4a7b-8686-999efb70b7cb
  name: __StartStep___to_product_selection_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 9162d8ad-cf00-4fc2-bed7-a73ffed79b32
  from_branch: null
  to_node:
    $component_ref: 85190204-2604-4fd0-b94a-6b4eb8e37f4f
- component_type: ControlFlowEdge
  id: 0127ead7-7e68-477a-847f-dc037dc0bcac
  name: step_OutputMessageStep_2c68bdae__auto_to_None End node_control_flow_edge
  description: null
  metadata: {}
  from_node:
    $component_ref: 9eab48d6-a51c-412e-a459-a7fd05283e1a
  from_branch: null
  to_node:
    $component_ref: 9f7c1027-0ed4-480d-918b-22a74656a00f
data_flow_connections:
- component_type: DataFlowEdge
  id: b34e1582-9c08-4ad2-871b-628edf98a0ee
  name: product_selection_step_result_to_step_PromptExecutionStep_8f995292__auto_products_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 85190204-2604-4fd0-b94a-6b4eb8e37f4f
  source_output: result
  destination_node:
    $component_ref: 309c4bda-986e-4fd6-82b8-a83a91168d8d
  destination_input: products
- component_type: DataFlowEdge
  id: d29d24f2-d0d1-469f-9ab4-fa12af5e76ee
  name: step_PromptExecutionStep_8f995292__auto_output_to_step_OutputMessageStep_2c68bdae__auto_issues_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 309c4bda-986e-4fd6-82b8-a83a91168d8d
  source_output: output
  destination_node:
    $component_ref: 9eab48d6-a51c-412e-a459-a7fd05283e1a
  destination_input: issues
- component_type: DataFlowEdge
  id: bc7a1760-8c23-4d0b-a985-b5b2cc14a90d
  name: __StartStep___bind_variables_to_product_selection_step_bind_variables_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 9162d8ad-cf00-4fc2-bed7-a73ffed79b32
  source_output: bind_variables
  destination_node:
    $component_ref: 85190204-2604-4fd0-b94a-6b4eb8e37f4f
  destination_input: bind_variables
- component_type: DataFlowEdge
  id: 973bd0b2-b264-458f-88bd-269f39e96e4d
  name: product_selection_step_result_to_None End node_result_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 85190204-2604-4fd0-b94a-6b4eb8e37f4f
  source_output: result
  destination_node:
    $component_ref: 9f7c1027-0ed4-480d-918b-22a74656a00f
  destination_input: result
- component_type: DataFlowEdge
  id: 8238696f-31f2-4f4e-9b5c-02ed64e93d15
  name: step_PromptExecutionStep_8f995292__auto_output_to_None End node_output_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 309c4bda-986e-4fd6-82b8-a83a91168d8d
  source_output: output
  destination_node:
    $component_ref: 9f7c1027-0ed4-480d-918b-22a74656a00f
  destination_input: output
- component_type: DataFlowEdge
  id: ee8f92a3-f52c-4f04-aceb-0d1c9666eafc
  name: step_OutputMessageStep_2c68bdae__auto_output_message_to_None End node_output_message_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 9eab48d6-a51c-412e-a459-a7fd05283e1a
  source_output: output_message
  destination_node:
    $component_ref: 9f7c1027-0ed4-480d-918b-22a74656a00f
  destination_input: output_message
$referenced_components:
  9162d8ad-cf00-4fc2-bed7-a73ffed79b32:
    component_type: StartNode
    id: 9162d8ad-cf00-4fc2-bed7-a73ffed79b32
    name: __StartStep__
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: object
      properties:
        product_category:
          type: string
      title: bind_variables
    outputs:
    - type: object
      properties:
        product_category:
          type: string
      title: bind_variables
    branches:
    - next
  85190204-2604-4fd0-b94a-6b4eb8e37f4f:
    component_type: PluginDatastoreQueryNode
    id: 85190204-2604-4fd0-b94a-6b4eb8e37f4f
    name: product_selection_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: object
      properties:
        product_category:
          type: string
      title: bind_variables
    outputs:
    - type: array
      items:
        type: object
        additionalProperties: {}
        key_type:
          type: string
      title: result
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    datastore:
      component_type: PluginOracleDatabaseDatastore
      id: 2515997a-1dbf-47cb-9dfb-d1dd2dca1cee
      name: PluginOracleDatabaseDatastore
      description: null
      metadata: {}
      datastore_schema:
        products:
          description: ''
          title: ''
          properties:
            description:
              type: string
            ID:
              description: Unique product identifier
              type: integer
            title:
              description: Brief summary of the product
              type: string
            price:
              type: number
              default: 0.1
            category:
              anyOf:
              - type: 'null'
              - type: string
              default: null
      connection_config:
        component_type: PluginTlsOracleDatabaseConnectionConfig
        id: 13f2fc32-f442-49fb-b7cc-142a240bb8bc
        name: PluginTlsOracleDatabaseConnectionConfig
        description: null
        metadata: {}
        user:
          $component_ref: 13f2fc32-f442-49fb-b7cc-142a240bb8bc.user
        password:
          $component_ref: 13f2fc32-f442-49fb-b7cc-142a240bb8bc.password
        dsn:
          $component_ref: 13f2fc32-f442-49fb-b7cc-142a240bb8bc.dsn
        config_dir: null
        component_plugin_name: DatastorePlugin
        component_plugin_version: 26.1.0.dev0
      component_plugin_name: DatastorePlugin
      component_plugin_version: 26.1.0.dev0
    query: SELECT title, description FROM products WHERE category = :product_category
    RESULT: result
    component_plugin_name: DatastorePlugin
    component_plugin_version: 26.1.0.dev0
  309c4bda-986e-4fd6-82b8-a83a91168d8d:
    component_type: LlmNode
    id: 309c4bda-986e-4fd6-82b8-a83a91168d8d
    name: step_PromptExecutionStep_8f995292__auto
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: '"products" input variable for the template'
      type: string
      title: products
    outputs:
    - description: the generated text
      type: string
      title: output
    branches:
    - next
    llm_config:
      component_type: VllmConfig
      id: 115a6849-0e1b-4b1b-8bd2-be872c9bc64b
      name: llm_41795d1f__auto
      description: null
      metadata:
        __metadata_info__: {}
      default_generation_parameters: null
      url: LLAMA_API_URL
      model_id: LLAMA_MODEL_ID
      api_type: chat_completions
      api_key: null
    prompt_template: "You are an inventory assistant.\n\n    Your task:\n        -\
      \ Summarize potential inconsistencies across descriptions of products in the same\
      \ category.\n          For example, identify typos and highlight improvement\
      \ opportunities\n    Important:\n        - Be helpful and concise in your messages\n\
      \n    Here are the product descriptions:\n    {{ products }}\n"
  9eab48d6-a51c-412e-a459-a7fd05283e1a:
    component_type: PluginOutputMessageNode
    id: 9eab48d6-a51c-412e-a459-a7fd05283e1a
    name: step_OutputMessageStep_2c68bdae__auto
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: '"issues" input variable for the template'
      type: string
      title: issues
    outputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    branches:
    - next
    message: 'The following issues have been identified: {{ issues }}'
    input_mapping: {}
    output_mapping: {}
    message_type: AGENT
    rephrase: false
    llm_config: null
    expose_message_as_output: true
    component_plugin_name: NodesPlugin
    component_plugin_version: 26.1.0.dev0
  9f7c1027-0ed4-480d-918b-22a74656a00f:
    component_type: EndNode
    id: 9f7c1027-0ed4-480d-918b-22a74656a00f
    name: None End node
    description: End node representing all transitions to None in the WayFlow flow
    metadata: {}
    inputs:
    - type: array
      items:
        type: object
        additionalProperties: {}
        key_type:
          type: string
      title: result
    - description: the generated text
      type: string
      title: output
    - description: the message added to the messages list
      type: string
      title: output_message
    outputs:
    - type: array
      items:
        type: object
        additionalProperties: {}
        key_type:
          type: string
      title: result
    - description: the generated text
      type: string
      title: output
    - description: the message added to the messages list
      type: string
      title: output_message
    branches: []
    branch_name: next
agentspec_version: 26.1.0
```

</details>

#### WARNING
The Oracle Database Connection Config objects contain several sensitive values
(like username, password, wallet location) that will not be serialized by the `AgentSpecExporter`.
These will be serialized as references that must be resolved at loading time, by specifying the values
of these sensitive fields in the `component_registry` argument of the loader:

```python
component_registry = {
    # We map the ID of the sensitive fields in the connection config to their values
    "oracle_datastore_connection_config.user": "<db user>",  # Replace with your DB user
    "oracle_datastore_connection_config.password": "<db password>",  # Replace with your DB password  # nosec: this is just a placeholder
    "oracle_datastore_connection_config.dsn": "<db connection string>",  # e.g. "(description=(retry_count=2)..."
}
```

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader().load_json(serialized_flow, components_registry=component_registry)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `PluginDatastoreQueryNode`
- `PluginOracleDatabaseDatastore`
- `PluginTlsOracleDatabaseConnectionConfig`
- `PluginOutputMessageNode`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Next steps

Having learned how to connect WayFlow assistants to data sources, you may now proceed to:

- [Create Conditional Transitions in Flows](conditional_flows.md)
- [Create a ServerTool from a Flow](create_a_tool_from_a_flow.md)

## Full code

### In-memory datastore

Click on the card at the [top of this page](#top-howtodatastores)
to download the full code for this guide or copy the code below.

<details>
<summary>Details</summary>

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to Connect to Your Data
# --------------------------------------------------

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
# python howto_datastores.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Imports

# %%
from textwrap import dedent

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.datastore import Entity, InMemoryDatastore
from wayflowcore.datastore.entity import nullable
from wayflowcore.flow import Flow
from wayflowcore.property import (
    AnyProperty,
    DictProperty,
    FloatProperty,
    IntegerProperty,
    ObjectProperty,
    StringProperty,
)
from wayflowcore.steps import InputMessageStep, OutputMessageStep, PromptExecutionStep
from wayflowcore.steps.datastoresteps import (
    DatastoreCreateStep,
    DatastoreDeleteStep,
    DatastoreListStep,
    DatastoreUpdateStep,
)

# %%[markdown]
## Define the llm

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## Create entities

# %%
product = Entity(
    properties={
        "ID": IntegerProperty(description="Unique product identifier"),
        # Descriptions can be helpful if an LLM needs to fill these fields,
        # or generally disambiguate non-obvious property names
        "title": StringProperty(description="Brief summary of the product"),
        "description": StringProperty(),
        "price": FloatProperty(default_value=0.1),
        # Use nullable to define optional properties
        "category": nullable(StringProperty()),
    },
)

# %%[markdown]
## Create datastore

# %%
datastore = InMemoryDatastore(schema={"products": product})

dummy_data = [
    {
        "ID": 0,
        "title": "Broccoli",
        "description": "Healthy and delicious cruciferous vegetable!",
        "price": 1.5,
        "category": "Produce",
    },
    {
        "ID": 1,
        "title": "Oranges",
        "description": "Vitamin C-filled citrus fruits",
        "price": 1.8,
        "category": "Produce",
    },
    {
        "ID": 2,
        "title": "Shampoo",
        "description": "Shiny smooth hair in just 10 applications!",
        "price": 4.5,
        "category": "Personal hygiene",
    },
    {
        "ID": 3,
        "title": "Crushed ice",
        "description": "Cool any drink in seconds!",
        "price": 4.5,
    },
]

# Create supports both bulk-creation, as well as single element creation
datastore.create(collection_name="products", entities=dummy_data[:-1])
datastore.create(collection_name="products", entities=dummy_data[-1])

# %%[markdown]
## Create Datastore step

# %%
datastore_list_step = DatastoreListStep(
    datastore,
    name="product_list_step",
    collection_name="products",
    where={"title": "{{user_requested_product}}"},
    limit=1,
    unpack_single_entity_from_list=True,
)

datastore_update_step = DatastoreUpdateStep(
    datastore,
    name="product_update_step",
    collection_name="products",
    where={"title": "{{user_requested_product}}"}
)

# %%[markdown]
## Create flow

# %%
# We create the steps needed by our flow
USER_INPUT_STEP = "user_product_input_step"
USER_TASK_INPUT_STEP = "user_task_input_step"
LLM_REWRITE_STEP = "llm_rewrite_step"
USER_OUTPUT_STEP = "user_output_step"

user_input_message_template = dedent(
    """I am an inventory Assistant, designed to help you keep product descriptions up-to-date.
    What product would you like to update? Please provide its title.
    """
)

user_task_message_template = "How would you like to update the description? I will help you rewrite it according to your instructions"

rewrite_description_prompt_template = dedent(
    """You are an inventory assistant.

    Your task:
        - Based on the product details given below, rewrite the description according to the user's request
    Important:
        - Be helpful and concise in your messages
        - Only provide the new description as an output, and nothing else

    Here is the User's request:
    - {{ user_request }}

    Here is the product description:
    - {{ product }}
    """
)

user_input_step = InputMessageStep(
    name=USER_INPUT_STEP,
    message_template=user_input_message_template,
)

user_task_input_step = InputMessageStep(
    name=USER_TASK_INPUT_STEP,
    message_template=user_task_message_template,
)

llm_rewrite_step = PromptExecutionStep(
    name=LLM_REWRITE_STEP,
    prompt_template=rewrite_description_prompt_template,
    llm=llm,
    input_descriptors=[
        DictProperty("product", key_type=StringProperty(), value_type=AnyProperty())
    ],
    output_descriptors=[
        ObjectProperty(
            name=PromptExecutionStep.OUTPUT, properties={"description": StringProperty()}
        )
    ],
)

user_output_step = OutputMessageStep(
    name=USER_OUTPUT_STEP,
    message_template="The product has been updated with the following description: {{ answer['description'] }}",
)

assistant = Flow(
    begin_step=user_input_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=user_input_step, destination_step=user_task_input_step),
        ControlFlowEdge(source_step=user_task_input_step, destination_step=datastore_list_step),
        ControlFlowEdge(source_step=datastore_list_step, destination_step=llm_rewrite_step),
        ControlFlowEdge(source_step=llm_rewrite_step, destination_step=datastore_update_step),
        ControlFlowEdge(source_step=datastore_update_step, destination_step=user_output_step),
        ControlFlowEdge(source_step=user_output_step, destination_step=None),
    ],
    data_flow_edges=[
        # The first title given by the user is mapped to the datastore steps for listing and updating
        DataFlowEdge(
            user_input_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            datastore_list_step,
            "user_requested_product",
        ),
        DataFlowEdge(
            user_input_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            datastore_update_step,
            "user_requested_product",
        ),
        # The task and product detail are given to the LLM in the prompt execution step
        DataFlowEdge(
            user_task_input_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            llm_rewrite_step,
            "user_request",
        ),
        DataFlowEdge(datastore_list_step, DatastoreListStep.ENTITIES, llm_rewrite_step, "product"),
        # The generated update is applied on the datastore, and echoed back to the user
        DataFlowEdge(
            llm_rewrite_step,
            PromptExecutionStep.OUTPUT,
            datastore_update_step,
            DatastoreUpdateStep.UPDATE,
        ),
        DataFlowEdge(llm_rewrite_step, PromptExecutionStep.OUTPUT, user_output_step, "answer"),
    ],
)

# %%[markdown]
## Execute flow

# %%
conversation = assistant.start_conversation()
conversation.execute()
conversation.append_user_message("Broccoli")

conversation.execute()
conversation.append_user_message(
    "Shoppers don't know what 'cruciferous' means, we should find a catchier description."
)

conversation.execute()
print(conversation.get_last_message().content)

# %%[markdown]
## Import agents

# %%
from wayflowcore.agent import Agent

# %%[markdown]
## Create agent flows

# %%
AGENT_PROMPT = dedent(
    """
    You are an inventory assistant. Your task is to help the user with their requests by using the available tools.
    If you are unsure about the action to take, or you don't have the right tool, simply tell the user so and follow their guidance.
    """
)

create_product_flow = Flow.from_steps(
    [DatastoreCreateStep(datastore, "products")],
    name="Create product",
    description="Creates a new product in the data source",
)
list_products_flow = Flow.from_steps(
    [DatastoreListStep(datastore, "products")],
    name="List all products",
    description="Lists all products in the data source.",
)
list_one_product_flow = Flow.from_steps(
    [datastore_list_step],
    name="List single product",
    description="Lists a single product in the data source by its title.",
)
update_product_flow = Flow.from_steps(
    [datastore_update_step],
    name="Update product",
    description="Updates a product in the data source by its title.",
)
delete_product_flow = Flow.from_steps(
    [DatastoreDeleteStep(datastore, "products", where={"title": "{{product_title}}"})],
    name="Delete product",
    description="Delete a product in the data source by its title.",
)

# %%[markdown]
## Create the agent

# %%
agent = Agent(
    llm=llm,
    flows=[
        create_product_flow,
        list_products_flow,
        list_one_product_flow,
        update_product_flow,
        delete_product_flow,
    ],
    custom_instruction=AGENT_PROMPT,
)

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_agent = AgentSpecExporter().to_json(agent)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader().load_json(serialized_agent)
```

</details>

### Oracle Database datastore

Click on the card at the [top of this page](#top-howtodatastores)
to download the full code for this guide, or copy the code below.

<details>
<summary>Details</summary>

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to Connect To Oracle Database
# --------------------------------------------------------

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
# python howto_connect_to_oracle_database.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.






# %%[markdown]
## Define the llm

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## imports:

# %%
from textwrap import dedent


from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

from wayflowcore.datastore import (
    Entity,
    MTlsOracleDatabaseConnectionConfig,
    OracleDatabaseDatastore,
    TlsOracleDatabaseConnectionConfig,
)
from wayflowcore.datastore.entity import nullable
from wayflowcore.flow import Flow
from wayflowcore.property import (
    FloatProperty,
    IntegerProperty,
    ObjectProperty,
    StringProperty,
)
from wayflowcore.steps import OutputMessageStep, PromptExecutionStep
from wayflowcore.steps.datastoresteps import DatastoreQueryStep

# %%[markdown]
## TLS Connection:

# %%
connection_config = TlsOracleDatabaseConnectionConfig(
    user="<db user>",  # Replace with your DB user
    password="<db password>",  # Replace with your DB password  # nosec: this is just a placeholder
    dsn="<db connection string>",  # e.g. "(description=(retry_count=2)..."
    # This is optional, but helpful to re-configure credentials when loading the AgentSpec config for this object
    id="oracle_datastore_connection_config",
)

# %%[markdown]
## mTLS Connection:

# %%
from wayflowcore.datastore import MTlsOracleDatabaseConnectionConfig

connection_config = MTlsOracleDatabaseConnectionConfig(
    config_dir="./oracle-wallet",
    dsn="<dbname>",  # Entry in tnsnames.ora
    wallet_location="./oracle-wallet",
    wallet_password="<your wallet password>",  # Replace with your wallet password  # nosec: this is just a placeholder
    user="<db user>",  # Replace with your DB user
    password="<db password>",  # Replace with your DB password  # nosec: this is just a placeholder
    # This is optional, but helpful to re-configure credentials when loading the AgentSpec config for this object
    id="oracle_datastore_connection_config",
)
# Datastore and Entity definitions

# %%[markdown]
## Schema

# %%
table_definition = """CREATE TABLE products (
    ID NUMBER PRIMARY KEY,
    title VARCHAR2(255) NOT NULL,
    description VARCHAR2(255) NOT NULL,
    price NUMBER NOT NULL,
    category VARCHAR2(255) DEFAULT NULL,
    external_system_id NUMBER DEFAULT NULL
)"""

with connection_config.get_connection() as connection:
    connection.cursor().execute(table_definition)

product = Entity(
    properties={
        "ID": IntegerProperty(description="Unique product identifier"),
        # Descriptions can be helpful if an LLM needs to fill these fields,
        # or generally disambiguate non-obvious property names
        "title": StringProperty(description="Brief summary of the product"),
        "description": StringProperty(),
        "price": FloatProperty(default_value=0.1),
        # Use nullable to define optional properties
        "category": nullable(StringProperty()),
    },
)

datastore = OracleDatabaseDatastore(
    schema={"products": product}, connection_config=connection_config
)

dummy_data = [
    {
        "ID": 0,
        "title": "Broccoli",
        "description": "Healthy and delicious cruciferous vegetable!",
        "price": 1.5,
        "category": "Produce",
    },
    {
        "ID": 1,
        "title": "Oranges",
        # We introduce a typo in this entity for the Assistant to fix
        "description": "Vitamin C-filled cirus fruits",
        "price": 1.8,
        "category": "Produce",
    },
    {
        "ID": 2,
        "title": "Shampoo",
        "description": "Shiny smooth hair in just 10 applications!",
        "price": 4.5,
        "category": "Personal hygiene",
    },
    {
        "ID": 3,
        "title": "Crushed ice",
        "description": "Cool any drink in seconds!",
        "price": 4.5,
        "category": "Food",
    },
]

# Create supports both bulk-creation, as well as single element creation
datastore.create(collection_name="products", entities=dummy_data)

# %%[markdown]
## Create Datastore step and flow

# %%
datastore_query_step = DatastoreQueryStep(
    datastore,
    "SELECT title, description FROM products WHERE category = :product_category",
    name="product_selection_step",
    input_descriptors=[
        ObjectProperty("bind_variables", properties={"product_category": StringProperty("")})
    ],
)

detect_issues_prompt_template = dedent(
    """You are an inventory assistant.

    Your task:
        - Summarize potential inconsistencies across descriptions of products in the same category.
          For example, identify typos and highlight improvement opportunities
    Important:
        - Be helpful and concise in your messages

    Here are the product descriptions:
    {{ products }}
    """
)

llm_issue_detection_step = PromptExecutionStep(
    prompt_template=detect_issues_prompt_template,
    llm=llm,
)

user_output_step = OutputMessageStep(
    message_template="The following issues have been identified: {{ issues }}",
)

assistant = Flow(
    begin_step=datastore_query_step,
    control_flow_edges=[
        ControlFlowEdge(
            source_step=datastore_query_step, destination_step=llm_issue_detection_step
        ),
        ControlFlowEdge(source_step=llm_issue_detection_step, destination_step=user_output_step),
        ControlFlowEdge(source_step=user_output_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            datastore_query_step, DatastoreQueryStep.RESULT, llm_issue_detection_step, "products"
        ),
        DataFlowEdge(
            llm_issue_detection_step, PromptExecutionStep.OUTPUT, user_output_step, "issues"
        ),
    ],
)

# %%[markdown]
## Execute flow

# %%
conversation = assistant.start_conversation({"bind_variables": {"product_category": "Produce"}})
conversation.execute()
print(conversation.get_last_message().content)

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(assistant)

# %%[markdown]
## Provide sensitive information when loading the Agent Spec config

# %%
component_registry = {
    # We map the ID of the sensitive fields in the connection config to their values
    "oracle_datastore_connection_config.user": "<db user>",  # Replace with your DB user
    "oracle_datastore_connection_config.password": "<db password>",  # Replace with your DB password  # nosec: this is just a placeholder
    "oracle_datastore_connection_config.dsn": "<db connection string>",  # e.g. "(description=(retry_count=2)..."
}

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader().load_json(serialized_flow, components_registry=component_registry)
```

</details>

| **Parameter**     | **Meaning**                                                                                                                                     |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| `user`            | Database username (e.g., `ADMIN`).                                                                                                              |
| `password`        | Password for `user`.                                                                                                                            |
| `dsn`             | Easy-connect string or TNS alias identifying the service.
Example:
`adb.us-ashburn-1.oraclecloud.com:1522/xyz_high`                     |
| `config_dir`      | Directory containing `sqlnet.ora` / `tnsnames.ora`.
when you want to reference a
TNS alias (e.g. `<dbname>_high`) instead of a raw DSN. |
| `wallet_location` | Path to the Oracle Wallet directory that contains
`cwallet.sso` / `ewallet.p12`.                                                            |
| `wallet_password` | Password that protects the wallet’s private key.                                                                                                |

| **Parameter**   | **Meaning**                                                                                                            |
|-----------------|------------------------------------------------------------------------------------------------------------------------|
| `user`          | Database username (e.g., `ADMIN`).                                                                                     |
| `password`      | Password for `user`.                                                                                                   |
| `dsn`           | Easy-connect string or TNS alias identifying the service.
(e.g., `adb.us-ashburn-1.oraclecloud.com:1522/xyz_high`) |
