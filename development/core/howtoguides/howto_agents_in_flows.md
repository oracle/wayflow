<a id="top-howtoagentsinflows"></a>

# How to Use Agents in Flows![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Agents in Flows how-to script](../end_to_end_code_examples/howto_agents_in_flows.py)

#### Prerequisites
This guide assumes familiarity with:

- [Flows](../tutorials/basic_flow.md)
- [Agents](../tutorials/basic_agent.md)

Usually, flows serve as pipelines to ensure the robustness of agentic workloads.
Employing an agent for a specific task is desirable because of its ability to invoke tools when necessary and autonomously select parameters for certain actions.

WayFlow enables the use of agents within flows, combining the predictability of flows with the adaptability of agents.
This guide demonstrates how to utilize the [AgentExecutionStep](../api/flows.md#agentexecutionstep) to embed an agent within a flow to execute a specific task.

![Flow diagram of a pipeline that uses agents](core/_static/howto/agentstep.svg)

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

Assuming you want to write an article.
Writing an article typically involves the following steps:

1. Find the topic for the article.
2. Write the article. This stage typically includes looking for sources on the web, drafting the entire text, reviewing, checking grammar, sources, proofreading.
3. Submit the article by sending it via email to the editor.

Steps 1 and 3 are straightforward and can be managed using standard procedures.
However, Step 2 involves complex tasks beyond a simple LLM generation, such as web browsing and content review.
To address this, you can use `AgentExecutionStep` that allows an agent to flexibly utilize tools for web browsing and article review.

Assuming you already have the following tools to browse the web and to proofread the text:

```python
import httpx
from wayflowcore.tools.toolhelpers import DescriptionMode, tool

@tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
def get_wikipedia_page_content(topic: str) -> str:
    """Looks for information and sources on internet about a given topic."""
    url = "https://en.wikipedia.org/w/api.php"
    headers = {"User-Agent": "MyApp/1.0 (https://example.com; myemail@example.com)"}

    response = httpx.get(
        url, params={"action": "query", "format": "json", "list": "search", "srsearch": topic}, headers=headers,
    )
    # extract page id
    data = response.json()
    search_results = data["query"]["search"]
    if not search_results:
        return "No results found."

    page_id = search_results[0]["pageid"]

    response = httpx.get(
        url,
        params={
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "explaintext": True,
            "pageids": page_id,
        },
        headers=headers,
    )

    # extract page content
    page_data = response.json()
    return str(page_data["query"]["pages"][str(page_id)]["extract"])


@tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
def proofread(text: str) -> str:
    """Checks and correct grammar mistakes"""
    return text
```

Continue creating the agent, specifying the agent’s expected output using the `outputs` argument:

```python
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.property import StringProperty

output = StringProperty(
    name="article",
    description="article to submit to the editor. Needs to be cited with sources and proofread",
    default_value="",
)

writing_agent = Agent(
    llm=llm,
    tools=[get_wikipedia_page_content, proofread],
    custom_instruction="""Your task is to write an article about the subject given by the user. You need to:
1. find some information about the topic with sources.
2. write an article
3. proofread the article
4. repeat steps 1-2-3 until the article looks good

The article needs to be around 100 words, always need cite sources and should be written in a professional tone.""",
    output_descriptors=[output],
)
```

The agent should operate within a flow without user interaction.
For that, set the `caller_input_mode` mode to `CallerInputMode.NEVER`.

```python
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep

agent_step = AgentExecutionStep(
    name="agent_step",
    agent=writing_agent,
    caller_input_mode=CallerInputMode.NEVER,
    output_descriptors=[output],
)
```

Now finalize the entire flow:

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import InputMessageStep, OutputMessageStep

email_template = """Dear ...,

Here is the article I told you about:
{{article}}

Best
"""

user_step = InputMessageStep(name="user_step", message_template="")
send_email_step = OutputMessageStep(name="send_email_step", message_template=email_template)

flow = Flow(
    begin_step=user_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=user_step, destination_step=agent_step),
        ControlFlowEdge(source_step=agent_step, destination_step=send_email_step),
        ControlFlowEdge(source_step=send_email_step, destination_step=None),
    ],
    data_flow_edges=[DataFlowEdge(agent_step, "article", send_email_step, "article")],
)
```

After completing the previous configurations, execute the flow.

```python
conversation = flow.start_conversation()
conversation.execute()

conversation.append_user_message("Oracle DB")
conversation.execute()

print(conversation.get_last_message())
```

As expected, the final execution message should be the email to be sent to the editor.

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
  "id": "a5a83bff-aef6-408c-a29f-5d927b6bd68a",
  "name": "flow_433ed84e__auto",
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
    },
    {
      "description": "article to submit to the editor. Needs to be cited with sources and proofread",
      "type": "string",
      "title": "article",
      "default": ""
    },
    {
      "description": "the input value provided by the user",
      "type": "string",
      "title": "user_provided_input"
    }
  ],
  "start_node": {
    "$component_ref": "420fc58e-e8fd-4785-8cce-f9958894a8f7"
  },
  "nodes": [
    {
      "$component_ref": "1a698e2a-f6f5-4102-af16-806073d94b9f"
    },
    {
      "$component_ref": "abcf3e84-eae4-4ee4-a373-7e8fcfc1db10"
    },
    {
      "$component_ref": "a2fc6b81-1b9c-4429-9875-7bcecbecccf3"
    },
    {
      "$component_ref": "420fc58e-e8fd-4785-8cce-f9958894a8f7"
    },
    {
      "$component_ref": "93bc5db7-7868-423f-ad3b-23bc366a8b08"
    }
  ],
  "control_flow_connections": [
    {
      "component_type": "ControlFlowEdge",
      "id": "f8e4bb84-6ed1-4a58-9acc-7a6598cb65fc",
      "name": "user_step_to_agent_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "1a698e2a-f6f5-4102-af16-806073d94b9f"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "abcf3e84-eae4-4ee4-a373-7e8fcfc1db10"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "9c9007e4-9003-4ba2-83ac-7089164f4438",
      "name": "agent_step_to_send_email_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "abcf3e84-eae4-4ee4-a373-7e8fcfc1db10"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "a2fc6b81-1b9c-4429-9875-7bcecbecccf3"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "c275c4c2-d585-4547-9db2-0430197574c1",
      "name": "__StartStep___to_user_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "420fc58e-e8fd-4785-8cce-f9958894a8f7"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "1a698e2a-f6f5-4102-af16-806073d94b9f"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "d90237ea-5e67-4465-8a51-6b67d55991c1",
      "name": "send_email_step_to_None End node_control_flow_edge",
      "description": null,
      "metadata": {},
      "from_node": {
        "$component_ref": "a2fc6b81-1b9c-4429-9875-7bcecbecccf3"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "93bc5db7-7868-423f-ad3b-23bc366a8b08"
      }
    }
  ],
  "data_flow_connections": [
    {
      "component_type": "DataFlowEdge",
      "id": "23300e2a-8af3-4bd0-9bf2-430dede761c5",
      "name": "agent_step_article_to_send_email_step_article_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "abcf3e84-eae4-4ee4-a373-7e8fcfc1db10"
      },
      "source_output": "article",
      "destination_node": {
        "$component_ref": "a2fc6b81-1b9c-4429-9875-7bcecbecccf3"
      },
      "destination_input": "article"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "dad51224-512d-4241-b908-37ee82a2d09e",
      "name": "send_email_step_output_message_to_None End node_output_message_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "a2fc6b81-1b9c-4429-9875-7bcecbecccf3"
      },
      "source_output": "output_message",
      "destination_node": {
        "$component_ref": "93bc5db7-7868-423f-ad3b-23bc366a8b08"
      },
      "destination_input": "output_message"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "67931f4d-0ac4-4f26-aeba-9575f5086830",
      "name": "agent_step_article_to_None End node_article_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "abcf3e84-eae4-4ee4-a373-7e8fcfc1db10"
      },
      "source_output": "article",
      "destination_node": {
        "$component_ref": "93bc5db7-7868-423f-ad3b-23bc366a8b08"
      },
      "destination_input": "article"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "a1d61214-c6fc-400c-bb2d-1d9fdc996050",
      "name": "user_step_user_provided_input_to_None End node_user_provided_input_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "1a698e2a-f6f5-4102-af16-806073d94b9f"
      },
      "source_output": "user_provided_input",
      "destination_node": {
        "$component_ref": "93bc5db7-7868-423f-ad3b-23bc366a8b08"
      },
      "destination_input": "user_provided_input"
    }
  ],
  "$referenced_components": {
    "a2fc6b81-1b9c-4429-9875-7bcecbecccf3": {
      "component_type": "PluginOutputMessageNode",
      "id": "a2fc6b81-1b9c-4429-9875-7bcecbecccf3",
      "name": "send_email_step",
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
          "description": "the message added to the messages list",
          "type": "string",
          "title": "output_message"
        }
      ],
      "branches": [
        "next"
      ],
      "expose_message_as_output": true,
      "message": "Dear ...,\n\nHere is the article I told you about:\n{{article}}\n\nBest\n",
      "input_mapping": {},
      "output_mapping": {},
      "message_type": "AGENT",
      "rephrase": false,
      "llm_config": null,
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "25.4.0.dev0"
    },
    "abcf3e84-eae4-4ee4-a373-7e8fcfc1db10": {
      "component_type": "AgentNode",
      "id": "abcf3e84-eae4-4ee4-a373-7e8fcfc1db10",
      "name": "agent_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [],
      "outputs": [
        {
          "description": "article to submit to the editor. Needs to be cited with sources and proofread",
          "type": "string",
          "title": "article",
          "default": ""
        }
      ],
      "branches": [
        "next"
      ],
      "agent": {
        "component_type": "Agent",
        "id": "0bcd0ffc-7781-402c-860c-6768dbb2fd91",
        "name": "agent_5324c936__auto",
        "description": "",
        "metadata": {
          "__metadata_info__": {}
        },
        "inputs": [],
        "outputs": [
          {
            "description": "article to submit to the editor. Needs to be cited with sources and proofread",
            "type": "string",
            "title": "article",
            "default": ""
          }
        ],
        "llm_config": {
          "component_type": "VllmConfig",
          "id": "f33a26ae-6149-4c59-9e78-2891dffb40bb",
          "name": "LLAMA_MODEL_ID",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "default_generation_parameters": null,
          "url": "LLAMA_API_URL",
          "model_id": "LLAMA_MODEL_ID"
        },
        "system_prompt": "Your task is to write an article about the subject given by the user. You need to:\n1. find some information about the topic with sources.\n2. write an article\n3. proofread the article\n4. repeat steps 1-2-3 until the article looks good\n\nThe article needs to be around 100 words, always need cite sources and should be written in a professional tone.",
        "tools": [
          {
            "component_type": "ServerTool",
            "id": "c7971c42-a911-43db-a05c-ce897f135bb8",
            "name": "get_wikipedia_page_content",
            "description": "Looks for information and sources on internet about a given topic.",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "type": "string",
                "title": "topic"
              }
            ],
            "outputs": [
              {
                "type": "string",
                "title": "tool_output"
              }
            ]
          },
          {
            "component_type": "ServerTool",
            "id": "0680a945-80c9-4ce7-81b7-fadeabbd5314",
            "name": "proofread",
            "description": "Checks and correct grammar mistakes",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "type": "string",
                "title": "text"
              }
            ],
            "outputs": [
              {
                "type": "string",
                "title": "tool_output"
              }
            ]
          }
        ]
      }
    },
    "93bc5db7-7868-423f-ad3b-23bc366a8b08": {
      "component_type": "EndNode",
      "id": "93bc5db7-7868-423f-ad3b-23bc366a8b08",
      "name": "None End node",
      "description": "End node representing all transitions to None in the WayFlow flow",
      "metadata": {},
      "inputs": [
        {
          "description": "the message added to the messages list",
          "type": "string",
          "title": "output_message"
        },
        {
          "description": "article to submit to the editor. Needs to be cited with sources and proofread",
          "type": "string",
          "title": "article",
          "default": ""
        },
        {
          "description": "the input value provided by the user",
          "type": "string",
          "title": "user_provided_input"
        }
      ],
      "outputs": [
        {
          "description": "the message added to the messages list",
          "type": "string",
          "title": "output_message"
        },
        {
          "description": "article to submit to the editor. Needs to be cited with sources and proofread",
          "type": "string",
          "title": "article",
          "default": ""
        },
        {
          "description": "the input value provided by the user",
          "type": "string",
          "title": "user_provided_input"
        }
      ],
      "branches": [],
      "branch_name": "next"
    },
    "1a698e2a-f6f5-4102-af16-806073d94b9f": {
      "component_type": "PluginInputMessageNode",
      "id": "1a698e2a-f6f5-4102-af16-806073d94b9f",
      "name": "user_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [],
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
      "message_template": "",
      "rephrase": false,
      "llm_config": null,
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "25.4.0.dev0"
    },
    "420fc58e-e8fd-4785-8cce-f9958894a8f7": {
      "component_type": "StartNode",
      "id": "420fc58e-e8fd-4785-8cce-f9958894a8f7",
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
id: a5a83bff-aef6-408c-a29f-5d927b6bd68a
name: flow_433ed84e__auto
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs:
- description: the message added to the messages list
  type: string
  title: output_message
- description: article to submit to the editor. Needs to be cited with sources and
    proofread
  type: string
  title: article
  default: ''
- description: the input value provided by the user
  type: string
  title: user_provided_input
start_node:
  $component_ref: 420fc58e-e8fd-4785-8cce-f9958894a8f7
nodes:
- $component_ref: 1a698e2a-f6f5-4102-af16-806073d94b9f
- $component_ref: abcf3e84-eae4-4ee4-a373-7e8fcfc1db10
- $component_ref: a2fc6b81-1b9c-4429-9875-7bcecbecccf3
- $component_ref: 420fc58e-e8fd-4785-8cce-f9958894a8f7
- $component_ref: 93bc5db7-7868-423f-ad3b-23bc366a8b08
control_flow_connections:
- component_type: ControlFlowEdge
  id: f8e4bb84-6ed1-4a58-9acc-7a6598cb65fc
  name: user_step_to_agent_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 1a698e2a-f6f5-4102-af16-806073d94b9f
  from_branch: null
  to_node:
    $component_ref: abcf3e84-eae4-4ee4-a373-7e8fcfc1db10
- component_type: ControlFlowEdge
  id: 9c9007e4-9003-4ba2-83ac-7089164f4438
  name: agent_step_to_send_email_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: abcf3e84-eae4-4ee4-a373-7e8fcfc1db10
  from_branch: null
  to_node:
    $component_ref: a2fc6b81-1b9c-4429-9875-7bcecbecccf3
- component_type: ControlFlowEdge
  id: c275c4c2-d585-4547-9db2-0430197574c1
  name: __StartStep___to_user_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 420fc58e-e8fd-4785-8cce-f9958894a8f7
  from_branch: null
  to_node:
    $component_ref: 1a698e2a-f6f5-4102-af16-806073d94b9f
- component_type: ControlFlowEdge
  id: d90237ea-5e67-4465-8a51-6b67d55991c1
  name: send_email_step_to_None End node_control_flow_edge
  description: null
  metadata: {}
  from_node:
    $component_ref: a2fc6b81-1b9c-4429-9875-7bcecbecccf3
  from_branch: null
  to_node:
    $component_ref: 93bc5db7-7868-423f-ad3b-23bc366a8b08
data_flow_connections:
- component_type: DataFlowEdge
  id: 23300e2a-8af3-4bd0-9bf2-430dede761c5
  name: agent_step_article_to_send_email_step_article_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: abcf3e84-eae4-4ee4-a373-7e8fcfc1db10
  source_output: article
  destination_node:
    $component_ref: a2fc6b81-1b9c-4429-9875-7bcecbecccf3
  destination_input: article
- component_type: DataFlowEdge
  id: dad51224-512d-4241-b908-37ee82a2d09e
  name: send_email_step_output_message_to_None End node_output_message_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: a2fc6b81-1b9c-4429-9875-7bcecbecccf3
  source_output: output_message
  destination_node:
    $component_ref: 93bc5db7-7868-423f-ad3b-23bc366a8b08
  destination_input: output_message
- component_type: DataFlowEdge
  id: 67931f4d-0ac4-4f26-aeba-9575f5086830
  name: agent_step_article_to_None End node_article_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: abcf3e84-eae4-4ee4-a373-7e8fcfc1db10
  source_output: article
  destination_node:
    $component_ref: 93bc5db7-7868-423f-ad3b-23bc366a8b08
  destination_input: article
- component_type: DataFlowEdge
  id: a1d61214-c6fc-400c-bb2d-1d9fdc996050
  name: user_step_user_provided_input_to_None End node_user_provided_input_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 1a698e2a-f6f5-4102-af16-806073d94b9f
  source_output: user_provided_input
  destination_node:
    $component_ref: 93bc5db7-7868-423f-ad3b-23bc366a8b08
  destination_input: user_provided_input
$referenced_components:
  a2fc6b81-1b9c-4429-9875-7bcecbecccf3:
    component_type: PluginOutputMessageNode
    id: a2fc6b81-1b9c-4429-9875-7bcecbecccf3
    name: send_email_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: '"article" input variable for the template'
      type: string
      title: article
    outputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    branches:
    - next
    expose_message_as_output: True
    message: 'Dear ...,


      Here is the article I told you about:

      {{article}}


      Best

      '
    input_mapping: {}
    output_mapping: {}
    message_type: AGENT
    rephrase: false
    llm_config: null
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.4.0.dev0
  abcf3e84-eae4-4ee4-a373-7e8fcfc1db10:
    component_type: AgentNode
    id: abcf3e84-eae4-4ee4-a373-7e8fcfc1db10
    name: agent_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs:
    - description: article to submit to the editor. Needs to be cited with sources
        and proofread
      type: string
      title: article
      default: ''
    branches:
    - next
    agent:
      component_type: Agent
      id: 0bcd0ffc-7781-402c-860c-6768dbb2fd91
      name: agent_5324c936__auto
      description: ''
      metadata:
        __metadata_info__: {}
      inputs: []
      outputs:
      - description: article to submit to the editor. Needs to be cited with sources
          and proofread
        type: string
        title: article
        default: ''
      llm_config:
        component_type: VllmConfig
        id: f33a26ae-6149-4c59-9e78-2891dffb40bb
        name: LLAMA_MODEL_ID
        description: null
        metadata:
          __metadata_info__: {}
        default_generation_parameters: null
        url: LLAMA_API_URL
        model_id: LLAMA_MODEL_ID
      system_prompt: 'Your task is to write an article about the subject given by
        the user. You need to:

        1. find some information about the topic with sources.

        2. write an article

        3. proofread the article

        4. repeat steps 1-2-3 until the article looks good


        The article needs to be around 100 words, always need cite sources and should
        be written in a professional tone.'
      tools:
      - component_type: ServerTool
        id: c7971c42-a911-43db-a05c-ce897f135bb8
        name: get_wikipedia_page_content
        description: Looks for information and sources on internet about a given topic.
        metadata:
          __metadata_info__: {}
        inputs:
        - type: string
          title: topic
        outputs:
        - type: string
          title: tool_output
      - component_type: ServerTool
        id: 0680a945-80c9-4ce7-81b7-fadeabbd5314
        name: proofread
        description: Checks and correct grammar mistakes
        metadata:
          __metadata_info__: {}
        inputs:
        - type: string
          title: text
        outputs:
        - type: string
          title: tool_output
  93bc5db7-7868-423f-ad3b-23bc366a8b08:
    component_type: EndNode
    id: 93bc5db7-7868-423f-ad3b-23bc366a8b08
    name: None End node
    description: End node representing all transitions to None in the WayFlow flow
    metadata: {}
    inputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    - description: article to submit to the editor. Needs to be cited with sources
        and proofread
      type: string
      title: article
      default: ''
    - description: the input value provided by the user
      type: string
      title: user_provided_input
    outputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    - description: article to submit to the editor. Needs to be cited with sources
        and proofread
      type: string
      title: article
      default: ''
    - description: the input value provided by the user
      type: string
      title: user_provided_input
    branches: []
    branch_name: next
  1a698e2a-f6f5-4102-af16-806073d94b9f:
    component_type: PluginInputMessageNode
    id: 1a698e2a-f6f5-4102-af16-806073d94b9f
    name: user_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs:
    - description: the input value provided by the user
      type: string
      title: user_provided_input
    branches:
    - next
    input_mapping: {}
    output_mapping: {}
    message_template: ''
    rephrase: false
    llm_config: null
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.4.0.dev0
  420fc58e-e8fd-4785-8cce-f9958894a8f7:
    component_type: StartNode
    id: 420fc58e-e8fd-4785-8cce-f9958894a8f7
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

tool_registry = {
    "get_wikipedia_page_content": get_wikipedia_page_content,
    "proofread": proofread,
}

flow = AgentSpecLoader(tool_registry=tool_registry).load_json(serialized_flow)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `PluginInputMessageNode`
- `PluginOutputMessageNode`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Next steps

Having learned how to use Agents inside Flows, you may now proceed to:

- [How to Create Conditional Transitions in Flows](conditional_flows.md) to branch out depending on the agent’s response.

## Full code

Click on the card at the [top of this page](#top-howtoagentsinflows) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to Use Agents in Flows
# -------------------------------------------------

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
# python howto_agents_in_flows.py
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
## Define the tools

# %%
import httpx
from wayflowcore.tools.toolhelpers import DescriptionMode, tool

@tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
def get_wikipedia_page_content(topic: str) -> str:
    """Looks for information and sources on internet about a given topic."""
    url = "https://en.wikipedia.org/w/api.php"
    headers = {"User-Agent": "MyApp/1.0 (https://example.com; myemail@example.com)"}

    response = httpx.get(
        url, params={"action": "query", "format": "json", "list": "search", "srsearch": topic}, headers=headers,
    )
    # extract page id
    data = response.json()
    search_results = data["query"]["search"]
    if not search_results:
        return "No results found."

    page_id = search_results[0]["pageid"]

    response = httpx.get(
        url,
        params={
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "explaintext": True,
            "pageids": page_id,
        },
        headers=headers,
    )

    # extract page content
    page_data = response.json()
    return str(page_data["query"]["pages"][str(page_id)]["extract"])


@tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
def proofread(text: str) -> str:
    """Checks and correct grammar mistakes"""
    return text

# %%[markdown]
## Define the agent

# %%
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.property import StringProperty

output = StringProperty(
    name="article",
    description="article to submit to the editor. Needs to be cited with sources and proofread",
    default_value="",
)

writing_agent = Agent(
    llm=llm,
    tools=[get_wikipedia_page_content, proofread],
    custom_instruction="""Your task is to write an article about the subject given by the user. You need to:
1. find some information about the topic with sources.
2. write an article
3. proofread the article
4. repeat steps 1-2-3 until the article looks good

The article needs to be around 100 words, always need cite sources and should be written in a professional tone.""",
    output_descriptors=[output],
)

# %%[markdown]
## Define the agent step

# %%
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep

agent_step = AgentExecutionStep(
    name="agent_step",
    agent=writing_agent,
    caller_input_mode=CallerInputMode.NEVER,
    output_descriptors=[output],
)

# %%[markdown]
## Define the Flow

# %%
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import InputMessageStep, OutputMessageStep

email_template = """Dear ...,

Here is the article I told you about:
{{article}}

Best
"""

user_step = InputMessageStep(name="user_step", message_template="")
send_email_step = OutputMessageStep(name="send_email_step", message_template=email_template)

flow = Flow(
    begin_step=user_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=user_step, destination_step=agent_step),
        ControlFlowEdge(source_step=agent_step, destination_step=send_email_step),
        ControlFlowEdge(source_step=send_email_step, destination_step=None),
    ],
    data_flow_edges=[DataFlowEdge(agent_step, "article", send_email_step, "article")],
)

# %%[markdown]
## Execute the flow

# %%
conversation = flow.start_conversation()
conversation.execute()

conversation.append_user_message("Oracle DB")
conversation.execute()

print(conversation.get_last_message())

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
    "get_wikipedia_page_content": get_wikipedia_page_content,
    "proofread": proofread,
}

flow = AgentSpecLoader(tool_registry=tool_registry).load_json(serialized_flow)
```
