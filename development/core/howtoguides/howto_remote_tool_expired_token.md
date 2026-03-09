# How to Do Remote API Calls with Potentially Expiring Tokens![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[MCP how-to script](../end_to_end_code_examples/howto_remote_tool_expired_token.py)

#### Prerequisites
This guide assumes familiarity with:
- [Building Assistants with Tools](howto_build_assistants_with_tools.md)

When building assistants with tools that reply on remote API calls, it is important to handle the authentication failures gracefully—especially those caused by expired access tokens.
In this guide, you will build an assistant that calls a mock service requiring a valid token for authentication.

## Setup

To demonstrate the concept in a safe environment, we first set up a local mock API server (here, using Starlette).
This simulates an endpoint that requires and validates an authentication token. If the token provided is:

* a valid token (valid-token): the service responds with a success message.
* an expired token (expired-token) or invalid token: the 401 Unauthorized error is returned with details.

```python
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.routing import Route
from starlette.exceptions import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED

async def protected_endpoint(request: Request):
    user = request.query_params.get("user")
    if user is None:
        return JSONResponse({"detail": "Missing 'user' query parameter."}, status_code=400)

    authorization = request.headers.get("authorization")
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1]
    if token == "valid-token":
        return JSONResponse({"response": f"Success! You are authenticated, {user}."})
    elif token == "expired-token":
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer error='invalid_token', error_description='The access token expired'"},
        )
    else:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": "Bearer error='invalid_token'"},
        )

app = Starlette(debug=True, routes=[
    Route("/protected", protected_endpoint)
])

# Start the server: Uncomment these lines
# import uvicorn
# uvicorn.run(app, host="localhost", port=8003)
```

## Basic implementation

In this example, you will build a simple [Agent](../api/agent.md#agent) that includes a [Flow](../api/flows.md#flow) with three steps:

* A start step to get the user name
* A step to trigger a client tool that collects a token from the user
* A step to call a remote API given the user name and the token

This guide requires the use of an LLM.
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

### Importing libraries

First import what is needed for this tutorial:

```python
from wayflowcore.property import StringProperty
from wayflowcore.tools import ClientTool
from wayflowcore.steps import (
    StartStep,
    CompleteStep,
    ApiCallStep,
    ToolExecutionStep
)
from wayflowcore.flow import Flow
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
```

### Creating the steps

Define the variable names and steps.

```python
TOKEN = "token"
USER = "user"
```

```python
# 1. Start step
start_step = StartStep(
    name="start_step",
    input_descriptors=[StringProperty(name=USER)]
)

# 2. Get token step
# A client tool to get token at client side
get_token_tool = ClientTool(
    name="get_token_tool",
    description="Get token from user",
    input_descriptors=[],
    output_descriptors=[StringProperty(name=TOKEN)]
)

# A step gets token by using the get_token_tool
get_token_tool_step = ToolExecutionStep(
    name="get_token_step",
    tool=get_token_tool,
)

# 3. Call API step
call_api_step = ApiCallStep(
    name="call_api_step",
    url="http://localhost:8003/protected",
    allow_insecure_http=True,
    method="GET",
    headers={"Authorization": "Bearer {{ token }}"},
    params={"user": "{{ user }}"},
)

# 4. End step
end_step = CompleteStep(name="end_step")
```

In this simple example, we manually input the user name and the token in the code.
For a more interactive approach, consider using [InputMessageStep](../api/flows.md#inputmessagestep) to prompt the user to enter these values during execution.

### Creating the flow
```python
remote_call_flow = Flow(
    name="Remote Call Flow",
    description="Perform a call to a remote endpoint given the `user` parameter.",
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=get_token_tool_step),
        ControlFlowEdge(source_step=get_token_tool_step, destination_step=call_api_step),
        ControlFlowEdge(source_step=call_api_step, destination_step=end_step),
    ],
    data_flow_edges=[
        DataFlowEdge(
            source_step=start_step,
            source_output=USER,
            destination_step=call_api_step,
            destination_input=USER,
        ),
        DataFlowEdge(
            source_step=get_token_tool_step,
            source_output=TOKEN,
            destination_step=call_api_step,
            destination_input=TOKEN,
        ),
    ]
)
```

This flow simply proceeds through three steps as defined in the `control_flow_edges`.
The `data_flow_edges` connect the outputs of each step—the user name from `start_step` and the token from `get_token_tool_step`—to the inputs required by `call_api_step`.

### Testing the flow
```python
from wayflowcore.executors.executionstatus import ToolRequestStatus
from wayflowcore.tools import ToolResult

inputs = {"user": "alice"}
conversation = remote_call_flow.start_conversation(inputs=inputs)

auth_token = "valid-token"
# auth_token = "expired-token" # This will raise error

status = conversation.execute()
if isinstance(status, ToolRequestStatus): # Asking for token
    tool_request_id = status.tool_requests[0].tool_request_id # Need to be adapted when using parallel tool calling (not the case here)
    conversation.append_tool_result(ToolResult(content=auth_token, tool_request_id=tool_request_id))
else:
    print(
        f"Invalid execution status, expected ToolRequestStatus, received {type(status)}"
    )
```

To simulate a valid user, provide `auth_token = "valid-token"`.
To test expiry handling, use `auth_token = "expired-token"`, which is expected to raise an error.
The flow should pause at the token step, mimicking a credential input prompt, then proceed upon receiving input.

### Creating an agent

Now, create an agent that includes the defined flow:

```python
from wayflowcore.agent import Agent

agent = Agent(
    name="Agent",
    flows=[remote_call_flow],
    llm=llm,
)
```

### Testing the agent
```python
from wayflowcore.executors.executionstatus import ToolRequestStatus, UserMessageRequestStatus
from wayflowcore.tools import ToolResult

conversation = agent.start_conversation()
conversation.append_user_message("Call the remote tool with user `alice`")

auth_token = "valid-token"
# auth_token = "expired-token" # This will raise error
status = conversation.execute()

if isinstance(status, ToolRequestStatus): # Asking for token
    tool_request_id = status.tool_requests[0].tool_request_id # Needs to be adapted when using parallel tool calling (not the case here)
    conversation.append_tool_result(ToolResult(content=auth_token, tool_request_id=tool_request_id))
else:
    print(
        f"Invalid execution status, expected ToolRequestStatus, received {type(status)}"
    )

status = conversation.execute() # Resuming the conversation after the client provided the auth token
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(
        f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}"
    )
```

The code block above demonstrates an interaction flow between a user and the agent, simulating how the assistant processes a remote, authenticated API call.
During the first execution, the agent determines that a token is required and issues a tool request to the client. This is reflected by the `status` being an instance of `ToolRequestStatus`.
After the client provides the required credential (the token), the second execution resumes the conversation.
If authentication is successful, the agent proceeds to call the API, processes the response, and generates a user message as its reply.
At this stage, the `status` should be `UserMessageRequestStatus`, which indicates that the agent has completed processing and is now ready to present a message to the user or wait for the next user prompt.
Checking for `UserMessageRequestStatus` ensures that your code only tries to access the assistant’s reply when it is actually available.

## Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(agent)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "ExtendedAgent",
  "id": "f3afdfe1-4b5b-469e-9505-33f72b3cd342",
  "name": "Agent",
  "description": "",
  "metadata": {
    "__metadata_info__": {
      "name": "Agent",
      "description": ""
    }
  },
  "inputs": [],
  "outputs": [],
  "llm_config": {
    "component_type": "VllmConfig",
    "id": "ab50c1e4-d6f3-493b-84b6-c570da3c7464",
    "name": "LLAMA_MODEL_ID",
    "description": null,
    "metadata": {
      "__metadata_info__": {}
    },
    "default_generation_parameters": null,
    "url": "LLAMA_API_URL",
    "model_id": "LLAMA_MODEL_ID"
  },
  "system_prompt": "",
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
      "id": "8e8bc09a-6b3c-47c3-b8b8-ec64743beca8",
      "name": "Remote Call Flow",
      "description": "Perform a call to a remote endpoint given the `user` parameter.",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "string",
          "title": "user"
        }
      ],
      "outputs": [
        {
          "type": "string",
          "title": "token"
        },
        {
          "description": "returned http status code",
          "type": "integer",
          "title": "http_status_code"
        }
      ],
      "start_node": {
        "$component_ref": "2b14ec5f-efe2-4b00-bfd9-1a7070b501b7"
      },
      "nodes": [
        {
          "$component_ref": "2b14ec5f-efe2-4b00-bfd9-1a7070b501b7"
        },
        {
          "$component_ref": "d4b896d7-fa3d-49ec-a45c-79021bf74e28"
        },
        {
          "$component_ref": "ed43def1-9d9b-4f15-84a3-cc9068143021"
        },
        {
          "$component_ref": "969d49b1-785b-4108-bd1e-6082b09160da"
        }
      ],
      "control_flow_connections": [
        {
          "component_type": "ControlFlowEdge",
          "id": "f44393b4-b9fb-4acd-9dc9-f4d496ccecae",
          "name": "start_step_to_get_token_step_control_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "from_node": {
            "$component_ref": "2b14ec5f-efe2-4b00-bfd9-1a7070b501b7"
          },
          "from_branch": null,
          "to_node": {
            "$component_ref": "d4b896d7-fa3d-49ec-a45c-79021bf74e28"
          }
        },
        {
          "component_type": "ControlFlowEdge",
          "id": "212e435b-059c-4842-9204-ed3b02f2bd17",
          "name": "get_token_step_to_call_api_step_control_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "from_node": {
            "$component_ref": "d4b896d7-fa3d-49ec-a45c-79021bf74e28"
          },
          "from_branch": null,
          "to_node": {
            "$component_ref": "ed43def1-9d9b-4f15-84a3-cc9068143021"
          }
        },
        {
          "component_type": "ControlFlowEdge",
          "id": "1b509ffa-24fe-4cda-a441-5456675ad64a",
          "name": "call_api_step_to_end_step_control_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "from_node": {
            "$component_ref": "ed43def1-9d9b-4f15-84a3-cc9068143021"
          },
          "from_branch": null,
          "to_node": {
            "$component_ref": "969d49b1-785b-4108-bd1e-6082b09160da"
          }
        }
      ],
      "data_flow_connections": [
        {
          "component_type": "DataFlowEdge",
          "id": "a2efbfb4-7046-4cba-b88f-010adaa77784",
          "name": "start_step_user_to_call_api_step_user_data_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "source_node": {
            "$component_ref": "2b14ec5f-efe2-4b00-bfd9-1a7070b501b7"
          },
          "source_output": "user",
          "destination_node": {
            "$component_ref": "ed43def1-9d9b-4f15-84a3-cc9068143021"
          },
          "destination_input": "user"
        },
        {
          "component_type": "DataFlowEdge",
          "id": "6d1baa26-611e-48d3-8021-c2ef39ec60d4",
          "name": "get_token_step_token_to_call_api_step_token_data_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "source_node": {
            "$component_ref": "d4b896d7-fa3d-49ec-a45c-79021bf74e28"
          },
          "source_output": "token",
          "destination_node": {
            "$component_ref": "ed43def1-9d9b-4f15-84a3-cc9068143021"
          },
          "destination_input": "token"
        },
        {
          "component_type": "DataFlowEdge",
          "id": "91b4c20c-93e6-4238-8dcd-28aea890788c",
          "name": "get_token_step_token_to_end_step_token_data_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "source_node": {
            "$component_ref": "d4b896d7-fa3d-49ec-a45c-79021bf74e28"
          },
          "source_output": "token",
          "destination_node": {
            "$component_ref": "969d49b1-785b-4108-bd1e-6082b09160da"
          },
          "destination_input": "token"
        },
        {
          "component_type": "DataFlowEdge",
          "id": "1c10dfaa-f6f9-4634-9b83-7e286996650c",
          "name": "call_api_step_http_status_code_to_end_step_http_status_code_data_flow_edge",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "source_node": {
            "$component_ref": "ed43def1-9d9b-4f15-84a3-cc9068143021"
          },
          "source_output": "http_status_code",
          "destination_node": {
            "$component_ref": "969d49b1-785b-4108-bd1e-6082b09160da"
          },
          "destination_input": "http_status_code"
        }
      ],
      "$referenced_components": {
        "ed43def1-9d9b-4f15-84a3-cc9068143021": {
          "component_type": "ApiNode",
          "id": "ed43def1-9d9b-4f15-84a3-cc9068143021",
          "name": "call_api_step",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [
            {
              "description": "string template variable named user",
              "type": "string",
              "title": "user"
            },
            {
              "description": "string template variable named token",
              "type": "string",
              "title": "token"
            }
          ],
          "outputs": [
            {
              "description": "returned http status code",
              "type": "integer",
              "title": "http_status_code"
            }
          ],
          "branches": [
            "next"
          ],
          "url": "http://localhost:8003/protected",
          "http_method": "GET",
          "api_spec_uri": null,
          "data": {},
          "query_params": {
            "user": "{{ user }}"
          },
          "headers": {
            "Authorization": "Bearer {{ token }}"
          }
        },
        "2b14ec5f-efe2-4b00-bfd9-1a7070b501b7": {
          "component_type": "StartNode",
          "id": "2b14ec5f-efe2-4b00-bfd9-1a7070b501b7",
          "name": "start_step",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [
            {
              "type": "string",
              "title": "user"
            }
          ],
          "outputs": [
            {
              "type": "string",
              "title": "user"
            }
          ],
          "branches": [
            "next"
          ]
        },
        "d4b896d7-fa3d-49ec-a45c-79021bf74e28": {
          "component_type": "ExtendedToolNode",
          "id": "d4b896d7-fa3d-49ec-a45c-79021bf74e28",
          "name": "get_token_step",
          "description": "",
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [],
          "outputs": [
            {
              "type": "string",
              "title": "token"
            }
          ],
          "branches": [
            "next"
          ],
          "tool": {
            "component_type": "ClientTool",
            "id": "41399e99-d42a-45c1-adc5-d3d016bd5a1c",
            "name": "get_token_tool",
            "description": "Get token from user",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [],
            "outputs": [
              {
                "type": "string",
                "title": "token"
              }
            ]
          },
          "input_mapping": {},
          "output_mapping": {},
          "raise_exceptions": false,
          "component_plugin_name": "NodesPlugin",
          "component_plugin_version": "25.4.0.dev0"
        },
        "969d49b1-785b-4108-bd1e-6082b09160da": {
          "component_type": "EndNode",
          "id": "969d49b1-785b-4108-bd1e-6082b09160da",
          "name": "end_step",
          "description": null,
          "metadata": {
            "__metadata_info__": {}
          },
          "inputs": [
            {
              "type": "string",
              "title": "token"
            },
            {
              "description": "returned http status code",
              "type": "integer",
              "title": "http_status_code"
            }
          ],
          "outputs": [
            {
              "type": "string",
              "title": "token"
            },
            {
              "description": "returned http status code",
              "type": "integer",
              "title": "http_status_code"
            }
          ],
          "branches": [],
          "branch_name": "end_step"
        }
      }
    }
  ],
  "agent_template": {
    "component_type": "PluginPromptTemplate",
    "id": "95b539ce-0908-4a45-9ab0-cd6fa1b346d7",
    "name": "",
    "description": "",
    "metadata": {
      "__metadata_info__": {}
    },
    "messages": [
      {
        "role": "system",
        "contents": [
          {
            "type": "text",
            "content": "{% if custom_instruction %}{{custom_instruction}}{% endif %}"
          }
        ],
        "tool_requests": null,
        "tool_result": null,
        "display_only": false,
        "sender": null,
        "recipients": [],
        "time_created": "2025-09-02T15:52:22.014400+00:00",
        "time_updated": "2025-09-02T15:52:22.014401+00:00"
      },
      {
        "role": "user",
        "contents": [],
        "tool_requests": null,
        "tool_result": null,
        "display_only": false,
        "sender": null,
        "recipients": [],
        "time_created": "2025-09-02T15:52:22.008803+00:00",
        "time_updated": "2025-09-02T15:52:22.010218+00:00"
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
        "time_created": "2025-09-02T15:52:22.014421+00:00",
        "time_updated": "2025-09-02T15:52:22.014421+00:00"
      }
    ],
    "output_parser": null,
    "inputs": [
      {
        "description": "\"custom_instruction\" input variable for the template",
        "type": "string",
        "title": "custom_instruction",
        "default": ""
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
        "id": "372d6f16-b945-4b10-b1c8-adc143ddab9d",
        "name": "removeemptynonusermessage_messagetransform",
        "description": null,
        "metadata": {
          "__metadata_info__": {}
        },
        "component_plugin_name": "MessageTransformPlugin",
        "component_plugin_version": "25.4.0.dev0"
      }
    ],
    "tools": null,
    "native_tool_calling": true,
    "response_format": null,
    "native_structured_generation": true,
    "generation_config": null,
    "component_plugin_name": "PromptTemplatePlugin",
    "component_plugin_version": "25.4.0.dev0"
  },
  "component_plugin_name": "AgentPlugin",
  "component_plugin_version": "25.4.0.dev0",
  "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: ExtendedAgent
id: f3afdfe1-4b5b-469e-9505-33f72b3cd342
name: Agent
description: ''
metadata:
  __metadata_info__:
    name: Agent
    description: ''
inputs: []
outputs: []
llm_config:
  component_type: VllmConfig
  id: ab50c1e4-d6f3-493b-84b6-c570da3c7464
  name: LLAMA_MODEL_ID
  description: null
  metadata:
    __metadata_info__: {}
  default_generation_parameters: null
  url: LLAMA_API_URL
  model_id: LLAMA_MODEL_ID
system_prompt: ''
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
  id: 8e8bc09a-6b3c-47c3-b8b8-ec64743beca8
  name: Remote Call Flow
  description: Perform a call to a remote endpoint given the `user` parameter.
  metadata:
    __metadata_info__: {}
  inputs:
  - type: string
    title: user
  outputs:
  - type: string
    title: token
  - description: returned http status code
    type: integer
    title: http_status_code
  start_node:
    $component_ref: 2b14ec5f-efe2-4b00-bfd9-1a7070b501b7
  nodes:
  - $component_ref: 2b14ec5f-efe2-4b00-bfd9-1a7070b501b7
  - $component_ref: d4b896d7-fa3d-49ec-a45c-79021bf74e28
  - $component_ref: ed43def1-9d9b-4f15-84a3-cc9068143021
  - $component_ref: 969d49b1-785b-4108-bd1e-6082b09160da
  control_flow_connections:
  - component_type: ControlFlowEdge
    id: f44393b4-b9fb-4acd-9dc9-f4d496ccecae
    name: start_step_to_get_token_step_control_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    from_node:
      $component_ref: 2b14ec5f-efe2-4b00-bfd9-1a7070b501b7
    from_branch: null
    to_node:
      $component_ref: d4b896d7-fa3d-49ec-a45c-79021bf74e28
  - component_type: ControlFlowEdge
    id: 212e435b-059c-4842-9204-ed3b02f2bd17
    name: get_token_step_to_call_api_step_control_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    from_node:
      $component_ref: d4b896d7-fa3d-49ec-a45c-79021bf74e28
    from_branch: null
    to_node:
      $component_ref: ed43def1-9d9b-4f15-84a3-cc9068143021
  - component_type: ControlFlowEdge
    id: 1b509ffa-24fe-4cda-a441-5456675ad64a
    name: call_api_step_to_end_step_control_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    from_node:
      $component_ref: ed43def1-9d9b-4f15-84a3-cc9068143021
    from_branch: null
    to_node:
      $component_ref: 969d49b1-785b-4108-bd1e-6082b09160da
  data_flow_connections:
  - component_type: DataFlowEdge
    id: a2efbfb4-7046-4cba-b88f-010adaa77784
    name: start_step_user_to_call_api_step_user_data_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    source_node:
      $component_ref: 2b14ec5f-efe2-4b00-bfd9-1a7070b501b7
    source_output: user
    destination_node:
      $component_ref: ed43def1-9d9b-4f15-84a3-cc9068143021
    destination_input: user
  - component_type: DataFlowEdge
    id: 6d1baa26-611e-48d3-8021-c2ef39ec60d4
    name: get_token_step_token_to_call_api_step_token_data_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    source_node:
      $component_ref: d4b896d7-fa3d-49ec-a45c-79021bf74e28
    source_output: token
    destination_node:
      $component_ref: ed43def1-9d9b-4f15-84a3-cc9068143021
    destination_input: token
  - component_type: DataFlowEdge
    id: 91b4c20c-93e6-4238-8dcd-28aea890788c
    name: get_token_step_token_to_end_step_token_data_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    source_node:
      $component_ref: d4b896d7-fa3d-49ec-a45c-79021bf74e28
    source_output: token
    destination_node:
      $component_ref: 969d49b1-785b-4108-bd1e-6082b09160da
    destination_input: token
  - component_type: DataFlowEdge
    id: 1c10dfaa-f6f9-4634-9b83-7e286996650c
    name: call_api_step_http_status_code_to_end_step_http_status_code_data_flow_edge
    description: null
    metadata:
      __metadata_info__: {}
    source_node:
      $component_ref: ed43def1-9d9b-4f15-84a3-cc9068143021
    source_output: http_status_code
    destination_node:
      $component_ref: 969d49b1-785b-4108-bd1e-6082b09160da
    destination_input: http_status_code
  $referenced_components:
    ed43def1-9d9b-4f15-84a3-cc9068143021:
      component_type: ApiNode
      id: ed43def1-9d9b-4f15-84a3-cc9068143021
      name: call_api_step
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - description: string template variable named user
        type: string
        title: user
      - description: string template variable named token
        type: string
        title: token
      outputs:
      - description: returned http status code
        type: integer
        title: http_status_code
      branches:
      - next
      url: http://localhost:8003/protected
      http_method: GET
      api_spec_uri: null
      data: {}
      query_params:
        user: '{{ user }}'
      headers:
        Authorization: Bearer {{ token }}
    2b14ec5f-efe2-4b00-bfd9-1a7070b501b7:
      component_type: StartNode
      id: 2b14ec5f-efe2-4b00-bfd9-1a7070b501b7
      name: start_step
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - type: string
        title: user
      outputs:
      - type: string
        title: user
      branches:
      - next
    d4b896d7-fa3d-49ec-a45c-79021bf74e28:
      component_type: ExtendedToolNode
      id: d4b896d7-fa3d-49ec-a45c-79021bf74e28
      name: get_token_step
      description: ''
      metadata:
        __metadata_info__: {}
      inputs: []
      outputs:
      - type: string
        title: token
      branches:
      - next
      tool:
        component_type: ClientTool
        id: 41399e99-d42a-45c1-adc5-d3d016bd5a1c
        name: get_token_tool
        description: Get token from user
        metadata:
          __metadata_info__: {}
        inputs: []
        outputs:
        - type: string
          title: token
      input_mapping: {}
      output_mapping: {}
      raise_exceptions: false
      component_plugin_name: NodesPlugin
      component_plugin_version: 25.4.0.dev0
    969d49b1-785b-4108-bd1e-6082b09160da:
      component_type: EndNode
      id: 969d49b1-785b-4108-bd1e-6082b09160da
      name: end_step
      description: null
      metadata:
        __metadata_info__: {}
      inputs:
      - type: string
        title: token
      - description: returned http status code
        type: integer
        title: http_status_code
      outputs:
      - type: string
        title: token
      - description: returned http status code
        type: integer
        title: http_status_code
      branches: []
      branch_name: end_step
agent_template:
  component_type: PluginPromptTemplate
  id: 95b539ce-0908-4a45-9ab0-cd6fa1b346d7
  name: ''
  description: ''
  metadata:
    __metadata_info__: {}
  messages:
  - role: system
    contents:
    - type: text
      content: '{% if custom_instruction %}{{custom_instruction}}{% endif %}'
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-09-02T15:52:22.014400+00:00'
    time_updated: '2025-09-02T15:52:22.014401+00:00'
  - role: user
    contents: []
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-09-02T15:52:22.008803+00:00'
    time_updated: '2025-09-02T15:52:22.010218+00:00'
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
    time_created: '2025-09-02T15:52:22.014421+00:00'
    time_updated: '2025-09-02T15:52:22.014421+00:00'
  output_parser: null
  inputs:
  - description: '"custom_instruction" input variable for the template'
    type: string
    title: custom_instruction
    default: ''
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
    id: 372d6f16-b945-4b10-b1c8-adc143ddab9d
    name: removeemptynonusermessage_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 25.4.0.dev0
  tools: null
  native_tool_calling: true
  response_format: null
  native_structured_generation: true
  generation_config: null
  component_plugin_name: PromptTemplatePlugin
  component_plugin_version: 25.4.0.dev0
component_plugin_name: AgentPlugin
component_plugin_version: 25.4.0.dev0
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

assistant: Agent = AgentSpecLoader().load_json(serialized_assistant)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `PluginPromptTemplate`
- `PluginRemoveEmptyNonUserMessageTransform`
- `ExtendedToolNode`
- `ExtendedAgent`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Next steps

In this guide, you learned how to define a simple flow that retrieves a token from the user and uses it to authenticate remote API calls.
To continue learning, checkout:

- [How to Catch Exceptions in Flows](catching_exceptions.md).

## Full code
```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Do Remote API Calls with Potentially Expiring Tokens
# --------------------------------------------------------------------------

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
# python howto_remote_tool_expired_token.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.




# %%[markdown]
## Mock server

# %%
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.routing import Route
from starlette.exceptions import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED

async def protected_endpoint(request: Request):
    user = request.query_params.get("user")
    if user is None:
        return JSONResponse({"detail": "Missing 'user' query parameter."}, status_code=400)

    authorization = request.headers.get("authorization")
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1]
    if token == "valid-token":
        return JSONResponse({"response": f"Success! You are authenticated, {user}."})
    elif token == "expired-token":
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer error='invalid_token', error_description='The access token expired'"},
        )
    else:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": "Bearer error='invalid_token'"},
        )

app = Starlette(debug=True, routes=[
    Route("/protected", protected_endpoint)
])

# Start the server: Uncomment these lines
# import uvicorn
# uvicorn.run(app, host="localhost", port=8003)

# %%[markdown]
## Import libraries

# %%
from wayflowcore.property import StringProperty
from wayflowcore.tools import ClientTool
from wayflowcore.steps import (
    StartStep,
    CompleteStep,
    ApiCallStep,
    ToolExecutionStep
)
from wayflowcore.flow import Flow
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

# %%[markdown]
## Configure your LLM

# %%
from wayflowcore.models import VllmModel
llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## Variable names

# %%
TOKEN = "token"
USER = "user"

# %%[markdown]
## Defining steps

# %%
# 1. Start step
start_step = StartStep(
    name="start_step",
    input_descriptors=[StringProperty(name=USER)]
)

# 2. Get token step
# A client tool to get token at client side
get_token_tool = ClientTool(
    name="get_token_tool",
    description="Get token from user",
    input_descriptors=[],
    output_descriptors=[StringProperty(name=TOKEN)]
)

# A step gets token by using the get_token_tool
get_token_tool_step = ToolExecutionStep(
    name="get_token_step",
    tool=get_token_tool,
)

# 3. Call API step
call_api_step = ApiCallStep(
    name="call_api_step",
    url="http://localhost:8003/protected",
    allow_insecure_http=True,
    method="GET",
    headers={"Authorization": "Bearer {{ token }}"},
    params={"user": "{{ user }}"},
)

# 4. End step
end_step = CompleteStep(name="end_step")

# %%[markdown]
## Defining flow

# %%
remote_call_flow = Flow(
    name="Remote Call Flow",
    description="Perform a call to a remote endpoint given the `user` parameter.",
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=get_token_tool_step),
        ControlFlowEdge(source_step=get_token_tool_step, destination_step=call_api_step),
        ControlFlowEdge(source_step=call_api_step, destination_step=end_step),
    ],
    data_flow_edges=[
        DataFlowEdge(
            source_step=start_step,
            source_output=USER,
            destination_step=call_api_step,
            destination_input=USER,
        ),
        DataFlowEdge(
            source_step=get_token_tool_step,
            source_output=TOKEN,
            destination_step=call_api_step,
            destination_input=TOKEN,
        ),
    ]
)

# %%[markdown]
## Testing flow

# %%
from wayflowcore.executors.executionstatus import ToolRequestStatus
from wayflowcore.tools import ToolResult

inputs = {"user": "alice"}
conversation = remote_call_flow.start_conversation(inputs=inputs)

auth_token = "valid-token"
# auth_token = "expired-token" # This will raise error

status = conversation.execute()
if isinstance(status, ToolRequestStatus): # Asking for token
    tool_request_id = status.tool_requests[0].tool_request_id # Need to be adapted when using parallel tool calling (not the case here)
    conversation.append_tool_result(ToolResult(content=auth_token, tool_request_id=tool_request_id))
else:
    print(
        f"Invalid execution status, expected ToolRequestStatus, received {type(status)}"
    )

# %%[markdown]
## Defining agent

# %%
from wayflowcore.agent import Agent

agent = Agent(
    name="Agent",
    flows=[remote_call_flow],
    llm=llm,
)

# %%[markdown]
## Testing agent

# %%
from wayflowcore.executors.executionstatus import ToolRequestStatus, UserMessageRequestStatus
from wayflowcore.tools import ToolResult

conversation = agent.start_conversation()
conversation.append_user_message("Call the remote tool with user `alice`")

auth_token = "valid-token"
# auth_token = "expired-token" # This will raise error
status = conversation.execute()

if isinstance(status, ToolRequestStatus): # Asking for token
    tool_request_id = status.tool_requests[0].tool_request_id # Needs to be adapted when using parallel tool calling (not the case here)
    conversation.append_tool_result(ToolResult(content=auth_token, tool_request_id=tool_request_id))
else:
    print(
        f"Invalid execution status, expected ToolRequestStatus, received {type(status)}"
    )

status = conversation.execute() # Resuming the conversation after the client provided the auth token
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(
        f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}"
    )

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(agent)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

assistant: Agent = AgentSpecLoader().load_json(serialized_assistant)
```
