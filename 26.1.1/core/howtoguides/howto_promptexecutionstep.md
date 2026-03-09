<a id="top-howtopromptexecutionstep"></a>

# How to Do Structured LLM Generation in Flows![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Prompt execution step how-to script](../end_to_end_code_examples/howto_promptexecutionstep.py)

#### Prerequisites
This guide assumes familiarity with [Flows](../tutorials/basic_flow.md).

WayFlow enables you to leverage LLMs to generate text and structured outputs.
This guide will show you how to:

- use the [PromptExecutionStep](../api/flows.md#promptexecutionstep) to generate text using an LLM
- use the [PromptExecutionStep](../api/flows.md#promptexecutionstep) to generate structured outputs
- use the [AgentExecutionStep](../api/flows.md#agentexecutionstep) to generate structured outputs using an agent

## Basic implementation

In this how-to guide, you will learn how to perform structured LLM generation with Flows.

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

Assuming you want to summarize this article:

```python
article = """Sea turtles are ancient reptiles that have been around for over 100 million years. They play crucial roles in marine ecosystems, such as maintaining healthy seagrass beds and coral reefs. Unfortunately, they are under threat due to poaching, habitat loss, and pollution. Conservation efforts worldwide aim to protect nesting sites and reduce bycatch in fishing gear."""
```

WayFlow offers the [PromptExecutionStep](../api/flows.md#promptexecutionstep) for this type of query.
Use the code below to generate a 10-word summary:

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep

start_step = StartStep(input_descriptors=[StringProperty("article")])
summarize_step = PromptExecutionStep(
    llm=llm,
    prompt_template="""Summarize this article in 10 words:\n {{article}}""",
    output_mapping={PromptExecutionStep.OUTPUT: "summary"},
)
summarize_step_name = "summarize_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        summarize_step_name: summarize_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_step),
        ControlFlowEdge(source_step=summarize_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "article", summarize_step, "article"),
    ],
)
```

#### NOTE
In the prompt, `article` is a Jinja2 syntax to specify a placeholder for a variable, which will appear as an input for the step.
If you use `{{var_name}}`, the variable named `var_name` will be of type `StringProperty`.
If you specify anything else Jinja2 compatible (for loops, filters, and so on), it will be of type `AnyProperty`.

Now execute the flow:

```python
from wayflowcore.executors.executionstatus import FinishedStatus

conversation = flow.start_conversation(inputs={"article": article})
status = conversation.execute()
if isinstance(status, FinishedStatus):
    print(status.output_values["summary"])
else:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")
# Sea turtles face threats from poaching, habitat loss, and pollution globally.
```

As expected, your flow has generated the article summary!

## Structured generation with Flows

In many cases, generating raw text within a flow is not very useful, as it is difficult to leverage in later steps.
Instead, you might want to generate attributes that follow a particular schema.
The `PromptExecutionStep` class enables this through the output_descriptors parameter.

```python
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep

animal_output = StringProperty(
    name="animal_name",
    description="name of the animal",
    default_value="",
)
danger_level_output = StringProperty(
    name="danger_level",
    description='level of danger of the animal. Can be "HIGH", "MEDIUM" or "LOW"',
    default_value="",
)
threats_output = ListProperty(
    name="threats",
    description="list of threats for the animal",
    item_type=StringProperty("threat"),
    default_value=[],
)


start_step = StartStep(input_descriptors=[StringProperty("article")])
summarize_step = PromptExecutionStep(
    llm=llm,
    prompt_template="""Extract from the following article the name of the animal, its danger level and the threats it's subject to. The article:\n\n {{article}}""",
    output_descriptors=[animal_output, danger_level_output, threats_output],
)
summarize_step_name = "summarize_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        summarize_step_name: summarize_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_step),
        ControlFlowEdge(source_step=summarize_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "article", summarize_step, "article"),
    ],
)

conversation = flow.start_conversation(inputs={"article": article})
status = conversation.execute()
if isinstance(status, FinishedStatus):
    print(status.output_values)
else:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")
# {'threats': ['poaching', 'habitat loss', 'pollution'], 'danger_level': 'HIGH', 'animal_name': 'Sea turtles'}
```

## Complex JSON objects

Sometimes, you might need to generate an object that follows a specific JSON Schema.
You can do that by using an output descriptor of type `ObjectProperty`, or directly converting your JSON Schema into a descriptor:

```python
from wayflowcore.property import Property, StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep

animal_json_schema = {
    "title": "animal_object",
    "description": "information about the animal",
    "type": "object",
    "properties": {
        "animal_name": {
            "type": "string",
            "description": "name of the animal",
            "default": "",
        },
        "danger_level": {
            "type": "string",
            "description": 'level of danger of the animal. Can be "HIGH", "MEDIUM" or "LOW"',
            "default": "",
        },
        "threats": {
            "type": "array",
            "description": "list of threats for the animal",
            "items": {"type": "string"},
            "default": [],
        },
    },
}
animal_descriptor = Property.from_json_schema(animal_json_schema)

start_step = StartStep(input_descriptors=[StringProperty("article")])
summarize_step = PromptExecutionStep(
    llm=llm,
    prompt_template="""Extract from the following article the name of the animal, its danger level and the threats it's subject to. The article:\n\n {{article}}""",
    output_descriptors=[animal_descriptor],
)
summarize_step_name = "summarize_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        summarize_step_name: summarize_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_step),
        ControlFlowEdge(source_step=summarize_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "article", summarize_step, "article"),
    ],
)

conversation = flow.start_conversation(inputs={"article": article})
status = conversation.execute()
if isinstance(status, FinishedStatus):
    print(status.output_values)
else:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")
# {'animal_object': {'animal_name': 'Sea turtles', 'danger_level': 'MEDIUM', 'threats': ['Poaching', 'Habitat loss', 'Pollution']}}
```

## Structured generation with Agents

In certain scenarios, you might need an agent to generate well-formatted outputs within your flow.
You can instruct the agent to generate them, and use it in the `AgentExecutionStep` class to perform structured generation.

```python
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.steps import AgentExecutionStep, StartStep

start_step = StartStep(input_descriptors=[])
agent = Agent(
    llm=llm,
    custom_instruction="""Extract from the article given by the user the name of the animal, its danger level and the threats it's subject to.""",
    initial_message=None,
    caller_input_mode=CallerInputMode.NEVER,  # <- ensure the agent does not ask the user questions, just produces the expected outputs
    output_descriptors=[animal_output, danger_level_output, threats_output],
)

summarize_agent_step = AgentExecutionStep(agent=agent)
summarize_step_name = "summarize_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        summarize_step_name: summarize_agent_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_agent_step),
        ControlFlowEdge(source_step=summarize_agent_step, destination_step=None),
    ],
    data_flow_edges=[],
)

conversation = flow.start_conversation()
conversation.append_user_message("Here is the article: " + article)
status = conversation.execute()
if isinstance(status, FinishedStatus):
    print(status.output_values)
else:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")
# {'animal_name': 'Sea turtles', 'danger_level': 'HIGH', 'threats': ['poaching', 'habitat loss', 'pollution']}
```

## How to write secure prompts with Jinja templating

<a id="securejinjatemplating"></a>

[Jinja2](https://jinja.palletsprojects.com/en/stable/intro/) is a fast and flexible templating engine for Python,
enabling dynamic generation of text-based formats by combining templates with data.

However, enabling all Jinja templating capabilities poses some security challenges.
For this reason, WayFlow relies on a stricter implementation of the Jinja2’s SandboxedEnvironment for higher security.
Every callable is considered unsafe, and every attribute and item access is prevented, except for:

* The attributes `index0`, `index`, `first`, `last`, `length` of the `jinja2.runtime.LoopContext`;
* The entries of a Python dictionary (only native type is accepted);
* The items of a Python list (only native type is accepted).

You should never write a template that includes a function call, or access to any internal attribute or element of
an arbitrary variable: that is considered unsafe, and it will raise a `SecurityException`.

Moreover, WayFlow performs additional checks on the inputs provided for rendering.
In particular, only elements and sub-elements that are of basic Python types
(`str`, `int`, `float`, `bool`, `list`, `dict`, `tuple`, `set`, `NoneType`) are accepted.
In any other case, a `SecurityException` is raised.

### What you can write

Here’s a set of common patterns that are accepted by WayFlow’s restricted Jinja templating.

Templates that access variables of base Python types:

> ```python
> my_var: str = "simple string"
> template = "{{ my_var }}"
> # Expected outcome: "simple string"
> ```

Templates that access elements of a list of base Python types:

> ```python
> my_var: list[str] = ["simple string"]
> template = "{{ my_var[0] }}"
> # Expected outcome: "simple string"
> ```

Templates that access dictionary entries of base Python types:

> ```python
> my_var: dict[str, str] = {"k1": "simple string"}
> template = "{{ my_var['k1'] }}"
> # Expected outcome: "simple string"

> my_var: dict[str, str] = {"k1": "simple string"}
> template = "{{ my_var.k1 }}"
> # Expected outcome: "simple string"
> ```

Builtin functions of Jinja, like `length` or `format`:

> ```python
> my_var: list[str] = ["simple string"]
> template = "{{ my_var | length }}"
> # Expected outcome: "1"
> ```

Simple expressions:

> ```python
> template = "{{ 7*7 }}"
> # Expected outcome: "49"
> ```

`For` loops, optionally accessing the `LoopContext`:

> ```python
> my_var: list[int] = [1, 2, 3]
> template = "{% for e in my_var %}{{e}}{{ ', ' if not loop.last }}{% endfor %}"
> # Expected outcome: "1, 2, 3"
> ```

`If` conditions:

> ```python
> my_var: int = 4
> template = "{% if my_var % 2 == 0 %}even{% else %}odd{% endif %}"
> # Expected outcome: "even"
> ```

Our general recommendation is to avoid complex logic in templates, and to pre-process the data you want to render instead.
For example, in case of complex objects, in order to comply with restrictions above, you should conveniently
transform them recursively into a dictionary of entries of basic Python types (see list of accepted types above).

### What you cannot write

Here’s a set of common patterns that are **NOT** accepted by WayFlow’s restricted Jinja templating.

Templates that access arbitrary objects:

> ```python
> my_var: MyComplexObject = MyComplexObject()
> template = "{{ my_var }}"
> # Expected outcome: SecurityException
> ```

Templates that access attributes of arbitrary objects:

> ```python
> my_var: MyComplexObject = MyComplexObject(attribute="my string")
> template = "{{ my_var.attribute }}"
> # Expected outcome: SecurityException
> ```

Templates that access internals of any type and object:

> ```python
> my_var: dict = {"k1": "my string"}
> template = "{{ my_var.__init__ }}"
> # Expected outcome: SecurityException
> ```

Templates that access non-existing keys of a dictionary:

> ```python
> my_var: dict = {"k1": "my string"}
> template = "{{ my_var['non-existing-key'] }}"
> # Expected outcome: SecurityException
> ```

Templates that access keys of a dictionary of type different from `int` or `str`:

> ```python
> my_var: dict = {("complex", "key"): "my string"}
> template = "{{ my_var[('complex', 'key')] }}"
> # Expected outcome: SecurityException
> ```

Templates that access callables:

> ```python
> my_var: Callable = lambda x: f"my value {x}"
> template = "{{ my_var(2) }}"
> # Expected outcome: SecurityException

> my_var: list = [1, 2, 3]
> template = "{{ len(my_var) }}"
> # Expected outcome: SecurityException

> my_var: MyComplexObject = MyComplexObject()
> template = "{{ my_var.to_string() }}"
> # Expected outcome: SecurityException
> ```

For more information, please check our [Security considerations page](../security.md).

## Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter
serialized_assistant = AgentSpecExporter().to_json(flow)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "Flow",
  "id": "e075072d-6aa0-4da4-84bd-dd54ce060ff4",
  "name": "flow_021b3829__auto",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [],
  "outputs": [
    {
      "description": "name of the animal",
      "type": "string",
      "title": "animal_name",
      "default": ""
    },
    {
      "description": "list of threats for the animal",
      "type": "array",
      "items": {
        "type": "string",
        "title": "threat"
      },
      "title": "threats",
      "default": []
    },
    {
      "description": "level of danger of the animal. Can be \"HIGH\", \"MEDIUM\" or \"LOW\"",
      "type": "string",
      "title": "danger_level",
      "default": ""
    }
  ],
  "start_node": {
    "$component_ref": "5c227b46-f36a-413c-8090-3be75fafbdec"
  },
  "nodes": [
    {
      "$component_ref": "5c227b46-f36a-413c-8090-3be75fafbdec"
    },
    {
      "$component_ref": "4c691ba3-2d4f-4d30-8714-11fe71a731a0"
    },
    {
      "$component_ref": "6bb4d577-8da4-4e05-83da-e16d10dbfa1c"
    }
  ],
  "control_flow_connections": [
    {
      "component_type": "ControlFlowEdge",
      "id": "de3e74f8-9b09-402f-a1ec-b8d5a35d9a3d",
      "name": "start_step_to_summarize_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "5c227b46-f36a-413c-8090-3be75fafbdec"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "4c691ba3-2d4f-4d30-8714-11fe71a731a0"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "47583cac-4599-4e3a-8cab-7edb2cba870f",
      "name": "summarize_step_to_None End node_control_flow_edge",
      "description": null,
      "metadata": {},
      "from_node": {
        "$component_ref": "4c691ba3-2d4f-4d30-8714-11fe71a731a0"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "6bb4d577-8da4-4e05-83da-e16d10dbfa1c"
      }
    }
  ],
  "data_flow_connections": [
    {
      "component_type": "DataFlowEdge",
      "id": "3620497d-5f8e-4280-a496-439cc2f32936",
      "name": "summarize_step_animal_name_to_None End node_animal_name_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "4c691ba3-2d4f-4d30-8714-11fe71a731a0"
      },
      "source_output": "animal_name",
      "destination_node": {
        "$component_ref": "6bb4d577-8da4-4e05-83da-e16d10dbfa1c"
      },
      "destination_input": "animal_name"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "137eb74d-0a75-48c5-8084-99b679567f44",
      "name": "summarize_step_threats_to_None End node_threats_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "4c691ba3-2d4f-4d30-8714-11fe71a731a0"
      },
      "source_output": "threats",
      "destination_node": {
        "$component_ref": "6bb4d577-8da4-4e05-83da-e16d10dbfa1c"
      },
      "destination_input": "threats"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "90669e70-722c-459c-9f64-cc8ba6fac091",
      "name": "summarize_step_danger_level_to_None End node_danger_level_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "4c691ba3-2d4f-4d30-8714-11fe71a731a0"
      },
      "source_output": "danger_level",
      "destination_node": {
        "$component_ref": "6bb4d577-8da4-4e05-83da-e16d10dbfa1c"
      },
      "destination_input": "danger_level"
    }
  ],
  "$referenced_components": {
    "4c691ba3-2d4f-4d30-8714-11fe71a731a0": {
      "component_type": "AgentNode",
      "id": "4c691ba3-2d4f-4d30-8714-11fe71a731a0",
      "name": "summarize_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [],
      "outputs": [
        {
          "description": "name of the animal",
          "type": "string",
          "title": "animal_name",
          "default": ""
        },
        {
          "description": "level of danger of the animal. Can be \"HIGH\", \"MEDIUM\" or \"LOW\"",
          "type": "string",
          "title": "danger_level",
          "default": ""
        },
        {
          "description": "list of threats for the animal",
          "type": "array",
          "items": {
            "type": "string",
            "title": "threat"
          },
          "title": "threats",
          "default": []
        }
      ],
      "branches": [
        "next"
      ],
      "agent": {
        "component_type": "Agent",
        "id": "eb2f9b51-e5b2-44e2-91d5-69711665b550",
        "name": "agent_72c8e146__auto",
        "description": "",
        "metadata": {
          "__metadata_info__": {}
        },
        "inputs": [],
        "outputs": [
          {
            "description": "name of the animal",
            "type": "string",
            "title": "animal_name",
            "default": ""
          },
          {
            "description": "level of danger of the animal. Can be \"HIGH\", \"MEDIUM\" or \"LOW\"",
            "type": "string",
            "title": "danger_level",
            "default": ""
          },
          {
            "description": "list of threats for the animal",
            "type": "array",
            "items": {
              "type": "string",
              "title": "threat"
            },
            "title": "threats",
            "default": []
          }
        ],
        "llm_config": {
          "component_type": "VllmConfig",
          "id": "ce3c577c-9e03-44f8-bec2-258bda52789e",
          "name": "llm_8052f2ad__auto",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "default_generation_parameters": null,
          "url": "LLAMA_API_URL",
          "model_id": "LLAMA_MODEL_ID"
        },
        "system_prompt": "Extract from the article given by the user the name of the animal, its danger level and the threats it's subject to.",
        "tools": []
      }
    },
    "6bb4d577-8da4-4e05-83da-e16d10dbfa1c": {
      "component_type": "EndNode",
      "id": "6bb4d577-8da4-4e05-83da-e16d10dbfa1c",
      "name": "None End node",
      "description": "End node representing all transitions to None in the WayFlow flow",
      "metadata": {},
      "inputs": [
        {
          "description": "name of the animal",
          "type": "string",
          "title": "animal_name",
          "default": ""
        },
        {
          "description": "list of threats for the animal",
          "type": "array",
          "items": {
            "type": "string",
            "title": "threat"
          },
          "title": "threats",
          "default": []
        },
        {
          "description": "level of danger of the animal. Can be \"HIGH\", \"MEDIUM\" or \"LOW\"",
          "type": "string",
          "title": "danger_level",
          "default": ""
        }
      ],
      "outputs": [
        {
          "description": "name of the animal",
          "type": "string",
          "title": "animal_name",
          "default": ""
        },
        {
          "description": "list of threats for the animal",
          "type": "array",
          "items": {
            "type": "string",
            "title": "threat"
          },
          "title": "threats",
          "default": []
        },
        {
          "description": "level of danger of the animal. Can be \"HIGH\", \"MEDIUM\" or \"LOW\"",
          "type": "string",
          "title": "danger_level",
          "default": ""
        }
      ],
      "branches": [],
      "branch_name": "next"
    },
    "5c227b46-f36a-413c-8090-3be75fafbdec": {
      "component_type": "StartNode",
      "id": "5c227b46-f36a-413c-8090-3be75fafbdec",
      "name": "start_step",
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
id: a7d68700-f2f6-43cb-b8e2-db5e0f7eb984
name: flow_0c07fc25__auto
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs:
- description: list of threats for the animal
  type: array
  items:
    type: string
    title: threat
  title: threats
  default: []
- description: level of danger of the animal. Can be "HIGH", "MEDIUM" or "LOW"
  type: string
  title: danger_level
  default: ''
- description: name of the animal
  type: string
  title: animal_name
  default: ''
start_node:
  $component_ref: a65b2a43-c65a-4cca-947f-f76e1410ff66
nodes:
- $component_ref: a65b2a43-c65a-4cca-947f-f76e1410ff66
- $component_ref: fe378524-69cb-4fcd-9d3a-f8fcb1c28316
- $component_ref: cb466062-c8c3-4d8c-ae59-2ec21e1df9ea
control_flow_connections:
- component_type: ControlFlowEdge
  id: 2c43b11c-9e07-469d-b38d-c4c2a323cc89
  name: start_step_to_summarize_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: a65b2a43-c65a-4cca-947f-f76e1410ff66
  from_branch: null
  to_node:
    $component_ref: fe378524-69cb-4fcd-9d3a-f8fcb1c28316
- component_type: ControlFlowEdge
  id: df47bf8f-46d3-496f-9e5e-a57c8abb9658
  name: summarize_step_to_None End node_control_flow_edge
  description: null
  metadata: {}
  from_node:
    $component_ref: fe378524-69cb-4fcd-9d3a-f8fcb1c28316
  from_branch: null
  to_node:
    $component_ref: cb466062-c8c3-4d8c-ae59-2ec21e1df9ea
data_flow_connections:
- component_type: DataFlowEdge
  id: a14b42bc-c53a-4f58-a385-af6bca465872
  name: summarize_step_threats_to_None End node_threats_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: fe378524-69cb-4fcd-9d3a-f8fcb1c28316
  source_output: threats
  destination_node:
    $component_ref: cb466062-c8c3-4d8c-ae59-2ec21e1df9ea
  destination_input: threats
- component_type: DataFlowEdge
  id: 78113887-9b21-4924-a35a-c6042b5bbe2b
  name: summarize_step_danger_level_to_None End node_danger_level_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: fe378524-69cb-4fcd-9d3a-f8fcb1c28316
  source_output: danger_level
  destination_node:
    $component_ref: cb466062-c8c3-4d8c-ae59-2ec21e1df9ea
  destination_input: danger_level
- component_type: DataFlowEdge
  id: 5225f4ae-dfec-4edc-92f4-52e57a53000f
  name: summarize_step_animal_name_to_None End node_animal_name_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: fe378524-69cb-4fcd-9d3a-f8fcb1c28316
  source_output: animal_name
  destination_node:
    $component_ref: cb466062-c8c3-4d8c-ae59-2ec21e1df9ea
  destination_input: animal_name
$referenced_components:
  a65b2a43-c65a-4cca-947f-f76e1410ff66:
    component_type: StartNode
    id: a65b2a43-c65a-4cca-947f-f76e1410ff66
    name: start_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs: []
    branches:
    - next
  fe378524-69cb-4fcd-9d3a-f8fcb1c28316:
    component_type: AgentNode
    id: fe378524-69cb-4fcd-9d3a-f8fcb1c28316
    name: summarize_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs:
    - description: name of the animal
      type: string
      title: animal_name
      default: ''
    - description: level of danger of the animal. Can be "HIGH", "MEDIUM" or "LOW"
      type: string
      title: danger_level
      default: ''
    - description: list of threats for the animal
      type: array
      items:
        type: string
        title: threat
      title: threats
      default: []
    branches:
    - next
    agent:
      component_type: Agent
      id: 3fe4580a-2bc6-4de8-85bb-cb8b0b361366
      name: agent_776abfae__auto
      description: ''
      metadata:
        __metadata_info__: {}
      inputs: []
      outputs:
      - description: name of the animal
        type: string
        title: animal_name
        default: ''
      - description: level of danger of the animal. Can be "HIGH", "MEDIUM" or "LOW"
        type: string
        title: danger_level
        default: ''
      - description: list of threats for the animal
        type: array
        items:
          type: string
          title: threat
        title: threats
        default: []
      llm_config:
        component_type: VllmConfig
        id: b32f4c62-2bd2-477d-a660-60ec1443b00c
        name: llm_650f3ae8__auto
        description: null
        metadata:
          __metadata_info__: {}
        default_generation_parameters: null
        url: LLAMA_API_URL
        model_id: LLAMA_MODEL_ID
      system_prompt: Extract from the article given by the user the name of the animal,
        its danger level and the threats it's subject to.
      tools: []
  cb466062-c8c3-4d8c-ae59-2ec21e1df9ea:
    component_type: EndNode
    id: cb466062-c8c3-4d8c-ae59-2ec21e1df9ea
    name: None End node
    description: End node representing all transitions to None in the WayFlow flow
    metadata: {}
    inputs:
    - description: list of threats for the animal
      type: array
      items:
        type: string
        title: threat
      title: threats
      default: []
    - description: level of danger of the animal. Can be "HIGH", "MEDIUM" or "LOW"
      type: string
      title: danger_level
      default: ''
    - description: name of the animal
      type: string
      title: animal_name
      default: ''
    outputs:
    - description: list of threats for the animal
      type: array
      items:
        type: string
        title: threat
      title: threats
      default: []
    - description: level of danger of the animal. Can be "HIGH", "MEDIUM" or "LOW"
      type: string
      title: danger_level
      default: ''
    - description: name of the animal
      type: string
      title: animal_name
      default: ''
    branches: []
    branch_name: next
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader
new_assistant = AgentSpecLoader().load_json(serialized_assistant)
```

## Recap

In this guide, you learned how to incorporate LLMs into flows to:

- generate raw text
- produce structured output
- perform structured generation using the agent and [AgentExecutionStep](../api/flows.md#agentexecutionstep)

## Next steps

Having learned how to perform structured generation in WayFlow, you may now proceed to:

- [Config Generation](generation_config.md) to change LLM generation parameters.
- [Catching Exceptions](catching_exceptions.md) to ensure robustness of the generated outputs.

## Full code

Click on the card at the [top of this page](#top-howtopromptexecutionstep) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Wayflow Code Example - How to Do Structured LLM Generation in Flows
# -------------------------------------------------------------------

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
# python howto_promptexecutionstep.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


# %%[markdown]
## Define the article

# %%
article = """Sea turtles are ancient reptiles that have been around for over 100 million years. They play crucial roles in marine ecosystems, such as maintaining healthy seagrass beds and coral reefs. Unfortunately, they are under threat due to poaching, habitat loss, and pollution. Conservation efforts worldwide aim to protect nesting sites and reduce bycatch in fishing gear."""


# %%[markdown]
## Define the llm

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## Create the flow using the prompt execution step

# %%
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep

start_step = StartStep(input_descriptors=[StringProperty("article")])
summarize_step = PromptExecutionStep(
    llm=llm,
    prompt_template="""Summarize this article in 10 words:\n {{article}}""",
    output_mapping={PromptExecutionStep.OUTPUT: "summary"},
)
summarize_step_name = "summarize_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        summarize_step_name: summarize_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_step),
        ControlFlowEdge(source_step=summarize_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "article", summarize_step, "article"),
    ],
)


# %%[markdown]
## Run the flow to get the summary

# %%
from wayflowcore.executors.executionstatus import FinishedStatus

conversation = flow.start_conversation(inputs={"article": article})
status = conversation.execute()
if isinstance(status, FinishedStatus):
    print(status.output_values["summary"])
else:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")
# Sea turtles face threats from poaching, habitat loss, and pollution globally.

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge


# %%[markdown]
## Use structured generation to extract formatted information

# %%
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep

animal_output = StringProperty(
    name="animal_name",
    description="name of the animal",
    default_value="",
)
danger_level_output = StringProperty(
    name="danger_level",
    description='level of danger of the animal. Can be "HIGH", "MEDIUM" or "LOW"',
    default_value="",
)
threats_output = ListProperty(
    name="threats",
    description="list of threats for the animal",
    item_type=StringProperty("threat"),
    default_value=[],
)


start_step = StartStep(input_descriptors=[StringProperty("article")])
summarize_step = PromptExecutionStep(
    llm=llm,
    prompt_template="""Extract from the following article the name of the animal, its danger level and the threats it's subject to. The article:\n\n {{article}}""",
    output_descriptors=[animal_output, danger_level_output, threats_output],
)
summarize_step_name = "summarize_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        summarize_step_name: summarize_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_step),
        ControlFlowEdge(source_step=summarize_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "article", summarize_step, "article"),
    ],
)

conversation = flow.start_conversation(inputs={"article": article})
status = conversation.execute()
if isinstance(status, FinishedStatus):
    print(status.output_values)
else:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")
# {'threats': ['poaching', 'habitat loss', 'pollution'], 'danger_level': 'HIGH', 'animal_name': 'Sea turtles'}

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge


# %%[markdown]
## Use structured generation with JSON schema

# %%
from wayflowcore.property import Property, StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep

animal_json_schema = {
    "title": "animal_object",
    "description": "information about the animal",
    "type": "object",
    "properties": {
        "animal_name": {
            "type": "string",
            "description": "name of the animal",
            "default": "",
        },
        "danger_level": {
            "type": "string",
            "description": 'level of danger of the animal. Can be "HIGH", "MEDIUM" or "LOW"',
            "default": "",
        },
        "threats": {
            "type": "array",
            "description": "list of threats for the animal",
            "items": {"type": "string"},
            "default": [],
        },
    },
}
animal_descriptor = Property.from_json_schema(animal_json_schema)

start_step = StartStep(input_descriptors=[StringProperty("article")])
summarize_step = PromptExecutionStep(
    llm=llm,
    prompt_template="""Extract from the following article the name of the animal, its danger level and the threats it's subject to. The article:\n\n {{article}}""",
    output_descriptors=[animal_descriptor],
)
summarize_step_name = "summarize_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        summarize_step_name: summarize_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_step),
        ControlFlowEdge(source_step=summarize_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "article", summarize_step, "article"),
    ],
)

conversation = flow.start_conversation(inputs={"article": article})
status = conversation.execute()
if isinstance(status, FinishedStatus):
    print(status.output_values)
else:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")
# {'animal_object': {'animal_name': 'Sea turtles', 'danger_level': 'MEDIUM', 'threats': ['Poaching', 'Habitat loss', 'Pollution']}}



# %%[markdown]
## Use structured generation with Agents in flows

# %%
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.steps import AgentExecutionStep, StartStep

start_step = StartStep(input_descriptors=[])
agent = Agent(
    llm=llm,
    custom_instruction="""Extract from the article given by the user the name of the animal, its danger level and the threats it's subject to.""",
    initial_message=None,
    caller_input_mode=CallerInputMode.NEVER,  # <- ensure the agent does not ask the user questions, just produces the expected outputs
    output_descriptors=[animal_output, danger_level_output, threats_output],
)

summarize_agent_step = AgentExecutionStep(agent=agent)
summarize_step_name = "summarize_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        summarize_step_name: summarize_agent_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_agent_step),
        ControlFlowEdge(source_step=summarize_agent_step, destination_step=None),
    ],
    data_flow_edges=[],
)

conversation = flow.start_conversation()
conversation.append_user_message("Here is the article: " + article)
status = conversation.execute()
if isinstance(status, FinishedStatus):
    print(status.output_values)
else:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")
# {'animal_name': 'Sea turtles', 'danger_level': 'HIGH', 'threats': ['poaching', 'habitat loss', 'pollution']}


# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter
serialized_assistant = AgentSpecExporter().to_json(flow)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader
new_assistant = AgentSpecLoader().load_json(serialized_assistant)
```
