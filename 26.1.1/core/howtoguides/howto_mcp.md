<a id="top-howtomcp"></a>

# How to connect MCP tools to Assistants![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[MCP how-to script](../end_to_end_code_examples/howto_mcp.py)

#### Prerequisites
This guide assumes familiarity with:

- [Tools](../api/tools.md)
- [Building Assistants with Tools](howto_build_assistants_with_tools.md)

[Model Context Protocol](https://modelcontextprotocol.io/introduction) (MCP) is an open protocol that standardizes how applications provide context to LLMs.
You can use an MCP server to provide a consistent tool interface to your agents and flows, without having to create custom adapters for different APIs.

#### TIP
See the [Oracle MCP Server Repository](https://github.com/oracle/mcp) to explore examples
of reference implementations of MCP servers for managing and interacting with Oracle products.

In this guide, you will learn how to:

* Create a simple MCP Server (in a separate Python file)
* Connect an Agent to an MCP Server (including how to export/load via Agent Spec, and run it)
* Connect a Flow to an MCP Server (including export/load/run)

#### IMPORTANT
This guide does not aim at explaining how to make secure MCP servers, but instead mainly aims at showing how to connect to one.
You should ensure that your MCP server configurations are secure, and only connect to trusted external MCP servers.

## Prerequisite: Setup a simple MCP Server

First, let’s see how to create and start a simple MCP server exposing a couple of tools.

#### NOTE
You should copy the following server code and run it in a separate Python process.

```python
from mcp.server.fastmcp import FastMCP

PAYSLIPS = [
    {
        "Amount": 7612,
        "Currency": "USD",
        "PeriodStartDate": "2025/05/15",
        "PeriodEndDate": "2025/06/15",
        "PaymentDate": "",
        "DocumentId": 2,
        "PersonId": 2,
    },
    {
        "Amount": 5000,
        "Currency": "CHF",
        "PeriodStartDate": "2024/05/01",
        "PeriodEndDate": "2024/06/01",
        "PaymentDate": "2024/05/15",
        "DocumentId": 1,
        "PersonId": 1,
    },
    {
        "Amount": 10000,
        "Currency": "EUR",
        "PeriodStartDate": "2025/06/15",
        "PeriodEndDate": "2025/10/15",
        "PaymentDate": "",
        "DocumentsId": 3,
        "PersonId": 3,
    },
]

def create_server(host: str, port: int):
    """Create and configure the MCP server"""
    server = FastMCP(
        name="Example MCP Server",
        instructions="A MCP Server.",
        host=host,
        port=port,
    )

    @server.tool(description="Return session details for the current user")
    def get_user_session():
        return {
            "PersonId": "1",
            "Username": "Bob.b",
            "DisplayName": "Bob B",
        }

    @server.tool(description="Return payslip details for a given PersonId")
    def get_payslips(PersonId: int):
        return [payslip for payslip in PAYSLIPS if payslip["PersonId"] == int(PersonId)]

    return server


def start_mcp_server() -> str:
    host: str = "localhost"
    port: int = 8080
    server = create_server(host=host, port=port)
    server.run(transport="sse")

    return f"http://{host}:{port}/sse"

# mcp_server_url = start_mcp_server() # <--- Move the code above to a separate file then uncomment
```

This MCP server exposes two example tools: `get_user_session` and `get_payslips`.
Once started, it will be available at (by default): `http://localhost:8080/sse`.

#### NOTE
When choosing a transport for MCP:

- Use [Stdio](../api/tools.md#stdiotransport) when launching and communicating with an MCP server as a local subprocess on the same machine as the client.
- Use [Streamable HTTP](../api/tools.md#streamablehttpmtlstransport) when connecting to a remote MCP server.

For more information, visit [https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#stdio](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#stdio)

## Connecting an Agent to the MCP Server

You can now connect an agent to this running MCP server.

### Add imports and configure an LLM

Start by importing the necessary packages for this guide:

```python
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.agent import Agent
from wayflowcore.mcp import MCPTool, MCPToolBox, SSETransport, enable_mcp_without_auth
from wayflowcore.flow import Flow
from wayflowcore.steps import ToolExecutionStep

mcp_server_url = f"http://localhost:8080/sse" # change to your own URL
# We will see below how to connect a specific tool to an assistant, e.g.
MCP_TOOL_NAME = "get_user_session"
# And see how to build an agent that can answer questions, e.g.
USER_QUERY = "What was the payment date of the last payslip for the current user?"
```

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

### Build the Agent

[Agents](../api/agent.md#agent) can connect to MCP tools by either using a [MCPToolBox](../api/tools.md#mcptoolbox) or a [MCPTool](../api/tools.md#mcptool).
Here you will use the toolbox (see the section on Flows to see how to use the `MCPTool`).

```python
enable_mcp_without_auth() # <--- See https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization#security-considerations
mcp_client = SSETransport(url=mcp_server_url)
mcp_toolbox = MCPToolBox(client_transport=mcp_client)

assistant = Agent(
    llm=llm,
    tools=[mcp_toolbox]
)
```

Specify the [transport](../api/tools.md#clienttransport) to use to handle the connection to the server and create the toolbox.
You can then equip an agent with the toolbox similarly to tools.

#### NOTE
`enable_mcp_without_auth()` disables authorization for local/testing only—do not use in production.

### Running the Agent

You can now run the agent in a simple conversation:

```python
# With a linear conversation
conversation = assistant.start_conversation()

conversation.append_user_message(USER_QUERY)
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")

# then continue the conversation
```

Alternatively, run the agent interactively in a command-line loop:

```python
def run_agent_in_command_line(assistant: Agent):
    inputs = {}
    conversation = assistant.start_conversation(inputs)

    while True:
        status = conversation.execute()
        if isinstance(status, FinishedStatus):
            break
        assistant_reply = conversation.get_last_message()
        if assistant_reply is not None:
            print("\nAssistant >>>", assistant_reply.content)
        user_input = input("\nUser >>> ")
        conversation.append_user_message(user_input)

# run_agent_in_command_line(assistant)
# ^ uncomment and execute
```

#### NOTE
WayFlow maintains MCP Client sessions between calls, which means that the client
does not need to re-authenticate at every call. After establishing a secure connection,
MCP servers can safely perform session recognition (e.g. for retrieving user information)

## Connecting a Flow to the MCP Server

You can also use MCP tools in a [Flow](../api/flows.md#flow) by using the [MCPTool](../api/tools.md#mcptool) in a [ToolExecutionStep](../api/flows.md#toolexecutionstep).

### Build the Flow

Create the flow using the MCP tool:

```python
mcp_tool = MCPTool(
    name=MCP_TOOL_NAME,
    client_transport=mcp_client
)

assistant = Flow.from_steps([
    ToolExecutionStep(name="mcp_tool_step", tool=mcp_tool)
])
```

Here you specify the client transport as with the MCP ToolBox, as well as the name of the specific tool
you want to use. Additionally, you can override the tool description (exposed by the MCP server) by
specifying the `description` parameter.

#### TIP
Use the `_validate_tool_exist_on_server` parameter to validate whether the tool is available or not
at instantiation time.

### Running the Flow

Execute the flow as follows:

```python
inputs = {}
conversation = assistant.start_conversation(inputs=inputs)

status = conversation.execute()
if isinstance(status, FinishedStatus):
    flow_outputs = status.output_values
    print(f"---\nFlow outputs >>> {flow_outputs}\n---")
else:
    print(
        f"Invalid execution status, expected FinishedStatus, received {type(status)}"
    )
```

## Advanced use: Complex types in MCP tools

WayFlow supports MCP tools with non-string outputs, such as:

- List of string
- Dictionary with key and values of string type

From the MCP server-side, you may need to enable the `structured_output` parameter
of your MCP server (depends on the implementation).

```python
server = FastMCP(
    name="Example MCP Server",
    instructions="A MCP Server.",
    host=host,
    port=port,
)

@server.tool(description="Tool that generates a dictionary", structured_output=True)
def generate_dict() -> dict[str, str]:
    return {"key": "value"}

@server.tool(description="Tool that generates a list", structured_output=True)
def generate_list() -> list[str]:
    return ["value1", "value2"]
```

On the WayFlow side, the input and output descriptors can be automatically inferred.

```python
generate_dict_tool = MCPTool(
    name="generate_dict",
    description="Tool that generates a dictionary",
    client_transport=mcp_client,
    # output_descriptors=[DictProperty(name="generate_dictOutput")], # this will be automatically inferred
)

generate_list_tool = MCPTool(
    name="generate_list",
    description="Tool that generates a list",
    client_transport=mcp_client,
    # output_descriptors=[ListProperty(name="generate_listOutput")], # this will be automatically inferred
)
```

You can then use those tools in a [Flow](../api/flows.md#flow) to natively support the manipulation of complex data types with MCP tools.

You can also use Pydantic models to change the tool output names. Note that in this advanced use,
you must wrap the outputs in a result field as expected by MCP when using non-dict types.
This also enables the use of multi-output in tools by using tuples.

```python
from typing import Annotated
from pydantic import BaseModel, RootModel, Field

class GenerateTupleOut(BaseModel, title="tool_output"):
    result: tuple[
        Annotated[str, Field(title="str_output")],
        Annotated[bool, Field(title="bool_output")]
    ]
    # /!\ this needs to be named `result`

class GenerateListOut(BaseModel, title="tool_output"):
    result: list[str] # /!\ this needs to be named `result`

class GenerateDictOut(RootModel[dict[str, str]], title="tool_output"):
    pass

server = FastMCP(
    name="Example MCP Server",
    instructions="A MCP Server.",
    host=host,
    port=port,
)

@server.tool(description="Tool that generates a dictionary", structured_output=True)
def generate_dict() -> GenerateDictOut:
    return GenerateDictOut({"key": "value"})

@server.tool(description="Tool that generates a list", structured_output=True)
def generate_list() -> GenerateListOut:
    return GenerateListOut(result=["value1", "value2"])

@server.tool(description="Tool that returns multiple outputs", structured_output=True)
def generate_tuple(inputs: list[str]) -> GenerateTupleOut:
    value = "; ".join(inputs)
    return GenerateTupleOut(result=("value", True))
```

You can then match the output descriptors on the WayFlow side.

```python
generate_dict_tool = MCPTool(
    name="generate_dict",
    description="Tool that generates a dictionary",
    client_transport=mcp_client,
    output_descriptors=[DictProperty(name="tool_output")],
)

generate_list_tool = MCPTool(
    name="generate_list",
    description="Tool that generates a list",
    client_transport=mcp_client,
    output_descriptors=[ListProperty(name="tool_output")],
)

generate_tuple_tool = MCPTool(
    name="generate_tuple",
    description="Tool that returns multiple outputs",
    client_transport=mcp_client,
    input_descriptors=[ListProperty(name="inputs")],
    output_descriptors=[StringProperty(name="str_output"), BooleanProperty(name="bool_output")],
)
```

When specified, the input/output descriptors of the MCP tool will be validated against the schema fetched from the MCP server.

#### NOTE
MCPToolBox are not compatible with complex output types.
Tools from MCPToolBox will always return string values.

## Exporting/Loading with Agent Spec

You can export the assistant from this tutorial to Agent Spec:

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

Agent Configuration

JSON

```json
{
    "component_type": "ExtendedAgent",
    "id": "024a2c39-3695-450f-a950-eabc1663db17",
    "name": "agent_b2a01d24__auto",
    "description": "",
    "metadata": {
        "__metadata_info__": {}
    },
    "inputs": [],
    "outputs": [],
    "llm_config": {
        "component_type": "VllmConfig",
        "id": "f42c7884-3cfb-4f82-86eb-1cea1a5a51c6",
        "name": "LLAMA_MODEL_ID",
        "description": null,
        "metadata": {
            "__metadata_info__": {}
        },
        "default_generation_parameters": {
            "max_tokens": 512
        },
        "url": "LLAMA_API_URL",
        "model_id": "LLAMA_MODEL_ID"
    },
    "system_prompt": "",
    "tools": [],
    "toolboxes": [
        {
            "component_type": "PluginMCPToolBox",
            "id": "43a0c0dc-2638-4dee-b868-44dd2b9afa35",
            "name": "",
            "description": null,
            "metadata": {},
            "client_transport": {
                "component_type": "SSETransport",
                "id": "ca2e9a97-6e1a-4f11-931a-774826c975ad",
                "name": "mcp_client_transport",
                "description": null,
                "metadata": {},
                "session_parameters": {
                    "read_timeout_seconds": 60
                },
                "url": "http://localhost:61799/sse",
                "headers": null
            },
            "tool_filter": null,
            "component_plugin_name": "MCPPlugin",
            "component_plugin_version": "25.4.1"
        }
    ],
    "context_providers": null,
    "can_finish_conversation": false,
    "max_iterations": 10,
    "initial_message": "Hi! How can I help you?",
    "caller_input_mode": "always",
    "agents": [],
    "flows": [],
    "agent_template": {
        "component_type": "PluginPromptTemplate",
        "id": "b33b40c4-02d2-4f91-b60a-d3ea1c4d725d",
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
                "time_created": "2025-10-07T08:08:34.942842+00:00",
                "time_updated": "2025-10-07T08:08:34.942844+00:00"
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
                "time_created": "2025-10-07T08:08:34.942869+00:00",
                "time_updated": "2025-10-07T08:08:34.942870+00:00"
            },
            {
                "role": "system",
                "contents": [
                    {
                        "type": "text",
                        "content": "$$__CHAT_HISTORY_PLACEHOLDER__$$"
                    }
                ],
                "tool_requests": null,
                "tool_result": null,
                "display_only": false,
                "sender": null,
                "recipients": [],
                "time_created": "2025-10-07T08:08:34.934280+00:00",
                "time_updated": "2025-10-07T08:08:34.934523+00:00"
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
                "time_created": "2025-10-07T08:08:34.942886+00:00",
                "time_updated": "2025-10-07T08:08:34.942886+00:00"
            }
        ],
        "output_parser": {
            "component_type": "PluginJsonToolOutputParser",
            "id": "b5e2e684-7434-4efd-857d-06d9172c2bab",
            "name": "jsontool_outputparser",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "tools": null,
            "component_plugin_name": "OutputParserPlugin",
            "component_plugin_version": "25.4.1"
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
                "id": "10c7ba9e-49a7-4c1e-b317-081daa14e771",
                "name": "removeemptynonusermessage_messagetransform",
                "description": null,
                "metadata": {
                    "__metadata_info__": {}
                },
                "component_plugin_name": "MessageTransformPlugin",
                "component_plugin_version": "25.4.1"
            },
            {
                "component_type": "PluginCoalesceSystemMessagesTransform",
                "id": "f3ac574f-8794-4a2c-8087-3ed21894b4bf",
                "name": "coalescesystemmessage_messagetransform",
                "description": null,
                "metadata": {
                    "__metadata_info__": {}
                },
                "component_plugin_name": "MessageTransformPlugin",
                "component_plugin_version": "25.4.1"
            },
            {
                "component_type": "PluginLlamaMergeToolRequestAndCallsTransform",
                "id": "baf2fd46-ca48-4a73-a8af-98cf805ecb08",
                "name": "llamamergetoolrequestandcalls_messagetransform",
                "description": null,
                "metadata": {
                    "__metadata_info__": {}
                },
                "component_plugin_name": "MessageTransformPlugin",
                "component_plugin_version": "25.4.1"
            }
        ],
        "tools": null,
        "native_tool_calling": false,
        "response_format": null,
        "native_structured_generation": true,
        "generation_config": null,
        "component_plugin_name": "PromptTemplatePlugin",
        "component_plugin_version": "25.4.1"
    },
    "component_plugin_name": "AgentPlugin",
    "component_plugin_version": "25.4.1",
    "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: ExtendedAgent
id: 024a2c39-3695-450f-a950-eabc1663db17
name: agent_b2a01d24__auto
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs: []
llm_config:
  component_type: VllmConfig
  id: f42c7884-3cfb-4f82-86eb-1cea1a5a51c6
  name: LLAMA_MODEL_ID
  description: null
  metadata:
    __metadata_info__: {}
  default_generation_parameters:
    max_tokens: 512
  url: LLAMA_API_URL
  model_id: LLAMA_MODEL_ID
system_prompt: ''
tools: []
toolboxes:
- component_type: PluginMCPToolBox
  id: 43a0c0dc-2638-4dee-b868-44dd2b9afa35
  name: ''
  description: null
  metadata: {}
  client_transport:
    component_type: SSETransport
    id: ca2e9a97-6e1a-4f11-931a-774826c975ad
    name: mcp_client_transport
    description: null
    metadata: {}
    session_parameters:
      read_timeout_seconds: 60
    url: http://localhost:61799/sse
    headers: null
  tool_filter: null
  component_plugin_name: MCPPlugin
  component_plugin_version: 25.4.1
context_providers: null
can_finish_conversation: false
max_iterations: 10
initial_message: Hi! How can I help you?
caller_input_mode: always
agents: []
flows: []
agent_template:
  component_type: PluginPromptTemplate
  id: b33b40c4-02d2-4f91-b60a-d3ea1c4d725d
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
    time_created: '2025-10-07T08:08:34.942842+00:00'
    time_updated: '2025-10-07T08:08:34.942844+00:00'
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
    time_created: '2025-10-07T08:08:34.942869+00:00'
    time_updated: '2025-10-07T08:08:34.942870+00:00'
  - role: system
    contents:
    - type: text
      content: $$__CHAT_HISTORY_PLACEHOLDER__$$
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-10-07T08:08:34.934280+00:00'
    time_updated: '2025-10-07T08:08:34.934523+00:00'
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
    time_created: '2025-10-07T08:08:34.942886+00:00'
    time_updated: '2025-10-07T08:08:34.942886+00:00'
  output_parser:
    component_type: PluginJsonToolOutputParser
    id: b5e2e684-7434-4efd-857d-06d9172c2bab
    name: jsontool_outputparser
    description: null
    metadata:
      __metadata_info__: {}
    tools: null
    component_plugin_name: OutputParserPlugin
    component_plugin_version: 25.4.1
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
    id: 6300f350-7556-4d27-87ac-8b846f56f2e8
    name: removeemptynonusermessage_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 25.4.1
  - component_type: PluginCoalesceSystemMessagesTransform
    id: 6b5cb6cb-0286-4f90-9aa6-ad86839b3d8e
    name: coalescesystemmessage_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 25.4.1
  - component_type: PluginLlamaMergeToolRequestAndCallsTransform
    id: a8477082-5fd5-4a40-9fdf-315fc27e82af
    name: llamamergetoolrequestandcalls_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 25.4.1
  tools: null
  native_tool_calling: false
  response_format: null
  native_structured_generation: true
  generation_config: null
  component_plugin_name: PromptTemplatePlugin
  component_plugin_version: 25.4.1
component_plugin_name: AgentPlugin
component_plugin_version: 25.4.1
agentspec_version: 25.4.1
```

Flow Configuration

JSON

```json
{
    "component_type": "Flow",
    "id": "f87896a0-62c2-4bf0-9999-7f2c91466369",
    "name": "flow_4aa9c976__auto",
    "description": "",
    "metadata": {
        "__metadata_info__": {}
    },
    "inputs": [],
    "outputs": [
        {
            "type": "string",
            "title": "tool_output"
        }
    ],
    "start_node": {
        "$component_ref": "8cb3bb26-f92c-4c6b-a044-34229d4300d7"
    },
    "nodes": [
        {
            "$component_ref": "0898c700-b180-4bbd-aab5-cbd8e16f5b4f"
        },
        {
            "$component_ref": "8cb3bb26-f92c-4c6b-a044-34229d4300d7"
        },
        {
            "$component_ref": "1dc851f1-7b43-419c-b08a-031d509abaf6"
        }
    ],
    "control_flow_connections": [
        {
            "component_type": "ControlFlowEdge",
            "id": "62fc12c8-c853-4b6a-89f3-177ec8368210",
            "name": "__StartStep___to_mcp_tool_step_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "8cb3bb26-f92c-4c6b-a044-34229d4300d7"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "0898c700-b180-4bbd-aab5-cbd8e16f5b4f"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "bb3fe1fc-76d7-4a82-b4bf-d2cee6618d1e",
            "name": "mcp_tool_step_to_None End node_control_flow_edge",
            "description": null,
            "metadata": {},
            "from_node": {
                "$component_ref": "0898c700-b180-4bbd-aab5-cbd8e16f5b4f"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "1dc851f1-7b43-419c-b08a-031d509abaf6"
            }
        }
    ],
    "data_flow_connections": [
        {
            "component_type": "DataFlowEdge",
            "id": "b2b6ceb1-1ab8-48a0-b34c-bfad4ddd7927",
            "name": "mcp_tool_step_tool_output_to_None End node_tool_output_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
                "$component_ref": "0898c700-b180-4bbd-aab5-cbd8e16f5b4f"
            },
            "source_output": "tool_output",
            "destination_node": {
                "$component_ref": "1dc851f1-7b43-419c-b08a-031d509abaf6"
            },
            "destination_input": "tool_output"
        }
    ],
    "$referenced_components": {
        "0898c700-b180-4bbd-aab5-cbd8e16f5b4f": {
            "component_type": "ToolNode",
            "id": "0898c700-b180-4bbd-aab5-cbd8e16f5b4f",
            "name": "mcp_tool_step",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [],
            "outputs": [
                {
                    "type": "string",
                    "title": "tool_output"
                }
            ],
            "branches": [
                "next"
            ],
            "tool": {
                "component_type": "MCPTool",
                "id": "ca82dd68-00a8-4b57-b996-7d30369d85b8",
                "name": "generate_random_string",
                "description": "Tool to return a random string",
                "metadata": {
                    "__metadata_info__": {}
                },
                "inputs": [],
                "outputs": [
                    {
                        "type": "string",
                        "title": "tool_output"
                    }
                ],
                "client_transport": {
                    "component_type": "SSETransport",
                    "id": "ca2e9a97-6e1a-4f11-931a-774826c975ad",
                    "name": "mcp_client_transport",
                    "description": null,
                    "metadata": {},
                    "session_parameters": {
                        "read_timeout_seconds": 60
                    },
                    "url": "http://localhost:61799/sse",
                    "headers": null
                }
            }
        },
        "8cb3bb26-f92c-4c6b-a044-34229d4300d7": {
            "component_type": "StartNode",
            "id": "8cb3bb26-f92c-4c6b-a044-34229d4300d7",
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
        },
        "1dc851f1-7b43-419c-b08a-031d509abaf6": {
            "component_type": "EndNode",
            "id": "1dc851f1-7b43-419c-b08a-031d509abaf6",
            "name": "None End node",
            "description": "End node representing all transitions to None in the WayFlow flow",
            "metadata": {},
            "inputs": [
                {
                    "type": "string",
                    "title": "tool_output"
                }
            ],
            "outputs": [
                {
                    "type": "string",
                    "title": "tool_output"
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
id: f87896a0-62c2-4bf0-9999-7f2c91466369
name: flow_4aa9c976__auto
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs:
- type: string
  title: tool_output
start_node:
  $component_ref: 8cb3bb26-f92c-4c6b-a044-34229d4300d7
nodes:
- $component_ref: 0898c700-b180-4bbd-aab5-cbd8e16f5b4f
- $component_ref: 8cb3bb26-f92c-4c6b-a044-34229d4300d7
- $component_ref: a58e1610-bd38-4935-8f00-f7f278664bf9
control_flow_connections:
- component_type: ControlFlowEdge
  id: 62fc12c8-c853-4b6a-89f3-177ec8368210
  name: __StartStep___to_mcp_tool_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 8cb3bb26-f92c-4c6b-a044-34229d4300d7
  from_branch: null
  to_node:
    $component_ref: 0898c700-b180-4bbd-aab5-cbd8e16f5b4f
- component_type: ControlFlowEdge
  id: f3b41946-373c-4f4d-97c2-563a421ebe96
  name: mcp_tool_step_to_None End node_control_flow_edge
  description: null
  metadata: {}
  from_node:
    $component_ref: 0898c700-b180-4bbd-aab5-cbd8e16f5b4f
  from_branch: null
  to_node:
    $component_ref: a58e1610-bd38-4935-8f00-f7f278664bf9
data_flow_connections:
- component_type: DataFlowEdge
  id: 6d6bdf46-4cc0-4f80-9876-cbd0c3eed509
  name: mcp_tool_step_tool_output_to_None End node_tool_output_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 0898c700-b180-4bbd-aab5-cbd8e16f5b4f
  source_output: tool_output
  destination_node:
    $component_ref: a58e1610-bd38-4935-8f00-f7f278664bf9
  destination_input: tool_output
$referenced_components:
  0898c700-b180-4bbd-aab5-cbd8e16f5b4f:
    component_type: ToolNode
    id: 0898c700-b180-4bbd-aab5-cbd8e16f5b4f
    name: mcp_tool_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs:
    - type: string
      title: tool_output
    branches:
    - next
    tool:
      component_type: MCPTool
      id: ca82dd68-00a8-4b57-b996-7d30369d85b8
      name: generate_random_string
      description: Tool to return a random string
      metadata:
        __metadata_info__: {}
      inputs: []
      outputs:
      - type: string
        title: tool_output
      client_transport:
        component_type: SSETransport
        id: ca2e9a97-6e1a-4f11-931a-774826c975ad
        name: mcp_client_transport
        description: null
        metadata: {}
        session_parameters:
          read_timeout_seconds: 60
        url: http://localhost:61799/sse
        headers: null
  8cb3bb26-f92c-4c6b-a044-34229d4300d7:
    component_type: StartNode
    id: 8cb3bb26-f92c-4c6b-a044-34229d4300d7
    name: __StartStep__
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs: []
    branches:
    - next
  a58e1610-bd38-4935-8f00-f7f278664bf9:
    component_type: EndNode
    id: a58e1610-bd38-4935-8f00-f7f278664bf9
    name: None End node
    description: End node representing all transitions to None in the WayFlow flow
    metadata: {}
    inputs:
    - type: string
      title: tool_output
    outputs:
    - type: string
      title: tool_output
    branches: []
    branch_name: next
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

assistant: Flow = AgentSpecLoader().load_json(serialized_assistant)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `PluginMCPToolBox`
- `ExtendedToolNode`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Next Steps

Having learned how to integrate MCP servers in WayFlow, you may now proceed to:

- [How to Enable Tool Output Streaming](howto_tooloutputstreaming.md)
- [How to Add User Confirmation to Tool Call Requests](howto_userconfirmation.md)
- [How to Create a ServerTool from a Flow](create_a_tool_from_a_flow.md)

## Full code

Click on the card at the [top of this page](#top-howtomcp) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to connect MCP tools to Assistants
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
# python howto_mcp.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.




# %%[markdown]
##Create a MCP Server

# %%
from mcp.server.fastmcp import FastMCP

PAYSLIPS = [
    {
        "Amount": 7612,
        "Currency": "USD",
        "PeriodStartDate": "2025/05/15",
        "PeriodEndDate": "2025/06/15",
        "PaymentDate": "",
        "DocumentId": 2,
        "PersonId": 2,
    },
    {
        "Amount": 5000,
        "Currency": "CHF",
        "PeriodStartDate": "2024/05/01",
        "PeriodEndDate": "2024/06/01",
        "PaymentDate": "2024/05/15",
        "DocumentId": 1,
        "PersonId": 1,
    },
    {
        "Amount": 10000,
        "Currency": "EUR",
        "PeriodStartDate": "2025/06/15",
        "PeriodEndDate": "2025/10/15",
        "PaymentDate": "",
        "DocumentsId": 3,
        "PersonId": 3,
    },
]

def create_server(host: str, port: int):
    """Create and configure the MCP server"""
    server = FastMCP(
        name="Example MCP Server",
        instructions="A MCP Server.",
        host=host,
        port=port,
    )

    @server.tool(description="Return session details for the current user")
    def get_user_session():
        return {
            "PersonId": "1",
            "Username": "Bob.b",
            "DisplayName": "Bob B",
        }

    @server.tool(description="Return payslip details for a given PersonId")
    def get_payslips(PersonId: int):
        return [payslip for payslip in PAYSLIPS if payslip["PersonId"] == int(PersonId)]

    return server


def start_mcp_server() -> str:
    host: str = "localhost"
    port: int = 8080
    server = create_server(host=host, port=port)
    server.run(transport="sse")

    return f"http://{host}:{port}/sse"

# mcp_server_url = start_mcp_server() # <--- Move the code above to a separate file then uncomment

# %%[markdown]
## Imports for this guide

# %%
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.agent import Agent
from wayflowcore.mcp import MCPTool, MCPToolBox, SSETransport, enable_mcp_without_auth
from wayflowcore.flow import Flow
from wayflowcore.steps import ToolExecutionStep

mcp_server_url = f"http://localhost:8080/sse" # change to your own URL
# We will see below how to connect a specific tool to an assistant, e.g.
MCP_TOOL_NAME = "get_user_session"
# And see how to build an agent that can answer questions, e.g.
USER_QUERY = "What was the payment date of the last payslip for the current user?"

# %%[markdown]
## Configure your LLM

# %%
from wayflowcore.models import VllmModel
llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)


# %%[markdown]
## Connecting an agent to the MCP server

# %%
enable_mcp_without_auth() # <--- See https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization#security-considerations
mcp_client = SSETransport(url=mcp_server_url)
mcp_toolbox = MCPToolBox(client_transport=mcp_client)

assistant = Agent(
    llm=llm,
    tools=[mcp_toolbox]
)


# %%[markdown]
## Running the agent

# %%
# With a linear conversation
conversation = assistant.start_conversation()

conversation.append_user_message(USER_QUERY)
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")

# then continue the conversation

# %%[markdown]
## Running with an execution loop

# %%
def run_agent_in_command_line(assistant: Agent):
    inputs = {}
    conversation = assistant.start_conversation(inputs)

    while True:
        status = conversation.execute()
        if isinstance(status, FinishedStatus):
            break
        assistant_reply = conversation.get_last_message()
        if assistant_reply is not None:
            print("\nAssistant >>>", assistant_reply.content)
        user_input = input("\nUser >>> ")
        conversation.append_user_message(user_input)

# run_agent_in_command_line(assistant)
# ^ uncomment and execute

# %%[markdown]
## Connecting a flow to the MCP server

# %%
mcp_tool = MCPTool(
    name=MCP_TOOL_NAME,
    client_transport=mcp_client
)

assistant = Flow.from_steps([
    ToolExecutionStep(name="mcp_tool_step", tool=mcp_tool)
])

# %%[markdown]
## Running the flow

# %%
inputs = {}
conversation = assistant.start_conversation(inputs=inputs)

status = conversation.execute()
if isinstance(status, FinishedStatus):
    flow_outputs = status.output_values
    print(f"---\nFlow outputs >>> {flow_outputs}\n---")
else:
    print(
        f"Invalid execution status, expected FinishedStatus, received {type(status)}"
    )

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

assistant: Flow = AgentSpecLoader().load_json(serialized_assistant)
```
