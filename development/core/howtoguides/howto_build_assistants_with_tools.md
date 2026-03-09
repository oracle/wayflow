<a id="tool-use"></a>

# How to Build Assistants with Tools![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Tool use how-to script](../end_to_end_code_examples/howto_tooluse.py)

#### Prerequisites
This guide assumes familiarity with:

- [Flows](../tutorials/basic_flow.md)
- [Agents](../tutorials/basic_agent.md)

Equipping assistants with [Tools](../api/tools.md) enhances their capabilities.
In WayFlow, tools can be used in both conversational assistants (also known as Agents) as well as in Flows by using the `ToolExecutionStep` class.

WayFlow supports **server-side**, **client-side** tools as well as **remote-tools**.

#### SEE ALSO
This guide focuses on using server/client tools. Read the [API Documentation](../api/tools.md#remotetool) to learn
more about the `RemoteTool`.

![image](core/_static/howto/types_of_tools.svg)

In this guide, you will build a **PDF summarizer** using the different types of supported tools, both within a flow and with an agent.

## Imports and LLM configuration

To get started, first import the `PyPDF` library.
First, install the PyPDF library:

```bash
$ pip install pypdf
```

Building LLM-powered assistants with tools in WayFlow requires the following imports.

```python
from typing import Annotated

from wayflowcore.agent import Agent
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.flow import Flow
from wayflowcore.models.llmmodelfactory import LlmModel
from wayflowcore.property import BooleanProperty, StringProperty
from wayflowcore.steps import OutputMessageStep, PromptExecutionStep, ToolExecutionStep
from wayflowcore.tools import ClientTool, ServerTool, Tool, ToolRequest, ToolResult, tool
```

In this guide, you will use an LLM.

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

#### NOTE
API keys should not be stored anywhere in the code. Use environment variables or tools such as [python-dotenv](https://pypi.org/project/python-dotenv/).

## Helper functions

The underlying tool used in this example is a PDF parser tool. The tool:

- loads a PDF file;
- reads the content of the pages;
- returns the extracted text.

The `PyPDFLoader` API from the [langchain_community Python library](https://pypi.org/project/langchain-community/) is used for this purpose.

```python
def _read_and_clean_pdf_file(file_path: str, clean_pdf: bool = False):
    from langchain_community.document_loaders import PyPDFLoader

    loader = PyPDFLoader(file_path=file_path)
    page_content_list = []
    for page in loader.lazy_load():
        page_content_list.append(page.page_content)
    if clean_pdf:
        # we remove the extras "\n"
        all_content = []
        for page_content in page_content_list:
            for row in page_content.split("\n"):
                if not row.strip().endswith("."):
                    all_content.append(row)
                else:
                    all_content.append(row + "\n")
    else:
        all_content = page_content_list
    return "\n".join(page_content_list)


# The path to the pdf file to be summarized
PDF_FILE_PATH = "path/to/example_document.pdf"
```

<details>
<summary>Details</summary>

```markdown
# Oracle Corporation

Oracle Corporation is an American multinational computer technology company headquartered in Austin, Texas. Co-founded in 1977 in Santa Clara, California, by Larry Ellison, who remains executive chairman, Oracle Corporation is the fourth-largest software company in the world by market capitalization as of 2025. Its market value was approximately US$614 billion in June 2025. The company's 2023 ranking in the Forbes Global 2000 was 80. The company sells database software, (particularly the Oracle Database), and cloud computing software and hardware. Oracle's core application software is a suite of enterprise software products, including enterprise resource planning (ERP), human capital management (HCM), customer relationship management (CRM), enterprise performance management (EPM), Customer Experience Commerce (CX Commerce) and supply chain management (SCM) software.
```

</details>

<a id="overview-of-tool-types"></a>

## Overview of the types of tools

This section covers how to use the following tools:

* `@tool` decorator - The simplest way to create server-side tools by decorating Python functions.
* `ServerTool` - For tools to be executed on the server side. Use this for tools running within the WayFlow environment, including local execution.
* `ClientTool` - For tools to be executed on the client application.

### Using the @tool Decorator

WayFlow provides a convenient `@tool` decorator that simplifies the creation of server-side tools. By decorating a Python function with `@tool`, you automatically convert it into a `ServerTool` object ready to be used in your Flows and Agents.

The decorator automatically extracts information from the function:

- The function name becomes the tool name
- The function docstring becomes the tool description
- Type annotations and parameter docstrings define input parameters
- Return type annotations define the output type

In the example below, we show a few options for how to create a server-side tool using the `@tool` decorator:

```python
### Option 1 - Using typing.Annotated
@tool("read_pdf")
def read_pdf_server_tool(
    file_path: Annotated[str, "Path to the pdf file"],
    clean_pdf: Annotated[bool, "Cleans and reformat the pdf pages"] = False,
) -> str:
    """Reads a PDF file given a filepath."""
    return _read_and_clean_pdf_file(file_path, clean_pdf)

### Option 2 - Using only the docstring
@tool("read_pdf", description_mode="only_docstring")
def read_pdf_server_tool(file_path: str, clean_pdf: bool = False) -> str:
    """Reads a PDF file given a filepath."""
    return _read_and_clean_pdf_file(file_path, clean_pdf)

```

In the above example, the decorated function `read_pdf_server_tool` is transformed into a `ServerTool` object.
The tool’s name is derived from the function name, the description from the docstring, and the input parameters and output type from the type annotations.

#### TIP
You can set the `description_mode` parameter of the `@tool` decorator to `only_docstring` to use the parameter signature information from
the docstrings instead of having to manually define them using `Annotated[Type, "description"]`.

### Creating a ServerTool

The `ServerTool` is defined by specifying:

- A tool name
- A tool description
- Input parameters, including names, types, and optional default values.
- A Python callable, the function executed by the tool.
- The output type.

In the example below, the tool takes two input parameters, one of which is optional, and returns a string.

```python
### Option 1 - Using Properties
read_pdf_server_tool = ServerTool(
    name="read_pdf",
    description="Reads a PDF file given a filepath",
    input_descriptors=[
        StringProperty("file_path", description="Path to the pdf file"),
        BooleanProperty(
            "clean_pdf", description="Cleans and reformat the pdf pages", default_value=False
        ),
    ],
    output_descriptors=[StringProperty()],
    func=_read_and_clean_pdf_file,
)

### Option 2 - Using JSON Schema
read_pdf_server_tool = ServerTool(
    name="read_pdf",
    description="Reads a PDF file given a filepath",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Path to the pdf file",
        },
        "clean_pdf": {
            "type": "boolean",
            "default": False,
            "description": "Cleans and reformat the pdf pages",
        },
    },
    func=_read_and_clean_pdf_file,
    output={"type": "string", "title": "tool_output"},
)
```

### Creating a ClientTool

The `ClientTool` is defined similarly to a `ServerTool`, except that it does not include a Python callable in its definition.
When executed, a `ClientTool` returns a `ToolRequest`, which must be executed on the client side.
The client then sends the execution result back to the assistant.

In the following example, the tool execution function is also defined.
This function should be implemented based on the specific requirements of the assistant developer.

```python
def _execute_read_pdf_request(tool_request: ToolRequest) -> str:
    args = tool_request.args
    if "file_path" not in args or "clean_pdf" not in args:
        print(f"Missing arguments in tool request, args were {args}")
        return "INVALID_REQUEST"
    return _read_and_clean_pdf_file(args["file_path"], args["clean_pdf"])


def execute_tool_from_tool_request(tool_request: ToolRequest) -> str:
    if tool_request.name == "read_pdf":
        return _execute_read_pdf_request(tool_request)
    else:
        raise ValueError(f"Unknown tool in tool request: {tool_request.name}")


### Option 1 - Using Properties
read_pdf_client_tool = ClientTool(
    name="read_pdf",
    description="Reads a PDF file given a filepath",
    input_descriptors=[
        StringProperty("file_path", description="Path to the pdf file"),
        BooleanProperty(
            "clean_pdf", description="Cleans and reformat the pdf pages", default_value=False
        ),
    ],
    output_descriptors=[StringProperty()],
)

### Option 2 - Using JSON Schema
read_pdf_client_tool = ClientTool(
    name="read_pdf",
    description="Reads a PDF file given a filepath",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Path to the pdf file",
        },
        "clean_pdf": {
            "type": "boolean",
            "default": False,
            "description": "Cleans and reformat the pdf pages",
        },
    },
    output={"type": "string"},
)
```

## Building Flows with Tools using the ToolExecutionStep

Executing tools in Flows can be done using the [ToolExecutionStep](../api/flows.md#toolexecutionstep).
The step simply requires the user to specify the tool to execute when the step is invoked.

Once the tool execution step is defined, the Flow can be constructed as usual.
For more information, refer to the tutorial on [Flows](../tutorials/basic_flow.md).

```python
def build_flow(llm: LlmModel, tool: Tool) -> Flow:
    pdf_read_step = ToolExecutionStep(
        name="pdf_read_step",
        tool=tool,
    )
    summarization_step = PromptExecutionStep(
        name="summarization_step",
        llm=llm,
        prompt_template="Please summarize the following PDF in 100 words or less. PDF:\n{{pdf_content}}",
        input_mapping={"pdf_content": ToolExecutionStep.TOOL_OUTPUT},
    )
    output_step = OutputMessageStep(
        name="output_step",
        message_template="Here is the summarized pdf:\n{{summarized_pdf}}",
        input_mapping={"summarized_pdf": PromptExecutionStep.OUTPUT},
    )
    return Flow(
        begin_step=pdf_read_step,
        control_flow_edges=[
            ControlFlowEdge(source_step=pdf_read_step, destination_step=summarization_step),
            ControlFlowEdge(source_step=summarization_step, destination_step=output_step),
            ControlFlowEdge(source_step=output_step, destination_step=None),
        ],
    )
```

### Executing ServerTool with a Flow

When using the `ServerTool`, the tool execution is performed on the server side.
As a consequence, the flow can be executed end-to-end with a single `execute` instruction.

```python
assistant = build_flow(llm, read_pdf_server_tool)

inputs = {"file_path": PDF_FILE_PATH, "clean_pdf": False}
conversation = assistant.start_conversation(inputs=inputs)

status = conversation.execute()
if isinstance(status, FinishedStatus):
    flow_outputs = status.output_values
    print(f"---\nFlow outputs >>> {flow_outputs}\n---")
else:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")

```

<details>
<summary>Details</summary>

Here is the summarized PDF:

Oracle Corporation is an American multinational computer technology company headquartered
in Austin, Texas. It sells database software, cloud computing software and hardware, and
enterprise software products including ERP, HCM, CRM, and SCM software.

</details>

### Executing ClientTool with a Flow

When using a `ClientTool`, the tool execution is performed on the client side.
Upon request, the assistant sends a `ToolRequest` to the client, which is responsible for executing the tool.
Once completed, the client returns a `ToolResult` to the assistant, allowing it to continue execution until the task is complete.

```python
assistant = build_flow(llm, read_pdf_client_tool)

inputs = {"file_path": PDF_FILE_PATH, "clean_pdf": False}
conversation = assistant.start_conversation(inputs=inputs)

status = conversation.execute()

failed = False
if isinstance(status, ToolRequestStatus):
    # Executing the request and sending it back to the assistant
    tool_request = status.tool_requests[0]
    tool_result = execute_tool_from_tool_request(tool_request)
    conversation.append_tool_result(
        ToolResult(content=tool_result, tool_request_id=tool_request.tool_request_id)
    )
else:
    failed = True
    print(f"Invalid execution status, expected ToolRequestStatus, received {type(status)}")

if not failed:
    # Continuing the conversation
    status = conversation.execute()

if not failed and isinstance(status, FinishedStatus):
    flow_outputs = status.output_values
    print(f"---\nFlow outputs >>> {flow_outputs}\n---")
elif not failed:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")
else:
    pass

```

## Building Agents with Tools

Agents can be equipped with tools by specifying the list of tools the agent can access.

You do not need to mention the tools in the agent’s `custom_instruction`, as tool descriptions are automatically added internally.

```python
def build_agent(llm: LlmModel, tool: Tool) -> Agent:
    from textwrap import dedent

    custom_instruction = dedent(
        """
        You are helping to load and summarize a PDF file given a filepath.
        ## Context
        You will receive a filepath from the username which indicates the path to the
        PDF file we want to summarize
        ## Task
        You will follow the next instructions:
        1. Use the tool to load the PDF file (don't go to the next step unless the file content was received).
           If the user does not specify anything, do not clean the PDF prior to summarizing it.
        2. Summarize the given PDF content in 100 words or less.
        ## Output Format
        Return the summarized document as follows:
        ```
        Here is the summarized pdf:
        [summarized pdf]
        ```
        """
    ).strip()

    return Agent(
        llm=llm,
        tools=[tool],
        custom_instruction=custom_instruction,
        max_iterations=3,
    )
```

#### NOTE
[Agents](../api/agent.md#agent) can also be equipped with other flows and agents. This topic will be covered in a dedicated tutorial.

### Executing ServerTool with an Agent

Similar to executing a Flow with a `ServerTool`, Agents can be executed end-to-end using a single `execute` instruction.
The key difference is that the file path is provided as a conversation message rather than as a flow input.

```python
assistant = build_agent(llm, read_pdf_server_tool)

conversation = assistant.start_conversation()

conversation.append_user_message(
    f"Please summarize my PDF document (can be found at {PDF_FILE_PATH})"
)
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")

```

#### IMPORTANT
In this case, the LLM must correctly generate the tool call with the file path as an input parameter. Smaller LLMs may struggle to reproduce the path accurately.
In general, assistant developers should try to avoid having LLMs to manipulate complex strings.

### Executing ClientTool with an Agent

Similar to executing a Flow with a `ClientTool`, the tool request must be handled on the client side.
The only difference is that the file path is provided as a conversation message instead of as a flow input.

```python
assistant = build_agent(llm, read_pdf_client_tool)

conversation = assistant.start_conversation()
conversation.append_user_message(
    f"Please summarize my PDF document (can be found at {PDF_FILE_PATH})"
)

status = conversation.execute()

# Executing the request and sending it back to the assistant
if isinstance(status, ToolRequestStatus):
    tool_request = status.tool_requests[0]
    tool_result = execute_tool_from_tool_request(tool_request)
    conversation.append_tool_result(
        ToolResult(content=tool_result, tool_request_id=tool_request.tool_request_id)
    )
else:
    failed = True
    print(f"Invalid execution status, expected ToolRequestStatus, received {type(status)}")

if not failed:
    # Continuing the conversation
    status = conversation.execute()

if not failed and isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
elif not failed:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")
else:
    pass

```

## Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "ExtendedAgent",
  "id": "382a74eb-fd01-4725-abe1-4ad2da5805de",
  "name": "agent_74b004c2",
  "description": "",
  "metadata": {
    "__metadata_info__": {
      "name": "agent_74b004c2",
      "description": ""
    }
  },
  "inputs": [],
  "outputs": [],
  "llm_config": {
    "component_type": "VllmConfig",
    "id": "dbe50cdc-1a2d-4b4a-8c20-09cba28c21f6",
    "name": "LLAMA_MODEL_ID",
    "description": null,
    "metadata": {
      "__metadata_info__": {}
    },
    "default_generation_parameters": null,
    "url": "LLAMA_API_URL",
    "model_id": "LLAMA_MODEL_ID"
  },
  "system_prompt": "You are helping to load and summarize a PDF file given a filepath.\n## Context\nYou will receive a filepath from the username which indicates the path to the\nPDF file we want to summarize\n## Task\nYou will follow the next instructions:\n1. Use the tool to load the PDF file (don't go to the next step unless the file content was received).\n   If the user does not specify anything, do not clean the PDF prior to summarizing it.\n2. Summarize the given PDF content in 100 words or less.\n## Output Format\nReturn the summarized document as follows:\n```\nHere is the summarized pdf:\n[summarized pdf]\n```",
  "tools": [
    {
      "component_type": "ClientTool",
      "id": "4b1a808b-473f-4e00-b413-23fd7143baf6",
      "name": "read_pdf",
      "description": "Reads a PDF file given a filepath",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "Path to the pdf file",
          "type": "string",
          "title": "file_path"
        },
        {
          "description": "Cleans and reformat the pdf pages",
          "type": "boolean",
          "title": "clean_pdf",
          "default": false
        }
      ],
      "outputs": [
        {
          "type": "string",
          "title": "tool_output"
        }
      ]
    }
  ],
  "toolboxes": [],
  "context_providers": null,
  "can_finish_conversation": false,
  "max_iterations": 3,
  "initial_message": "Hi! How can I help you?",
  "caller_input_mode": "always",
  "agents": [],
  "flows": [],
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
id: 382a74eb-fd01-4725-abe1-4ad2da5805de
name: agent_74b004c2
description: ''
metadata:
  __metadata_info__:
    name: agent_74b004c2
    description: ''
inputs: []
outputs: []
llm_config:
  component_type: VllmConfig
  id: dbe50cdc-1a2d-4b4a-8c20-09cba28c21f6
  name: LLAMA_MODEL_ID
  description: null
  metadata:
    __metadata_info__: {}
  default_generation_parameters: null
  url: LLAMA_API_URL
  model_id: LLAMA_MODEL_ID
system_prompt: "You are helping to load and summarize a PDF file given a filepath.\n\
  ## Context\nYou will receive a filepath from the username which indicates the path\
  \ to the\nPDF file we want to summarize\n## Task\nYou will follow the next instructions:\n\
  1. Use the tool to load the PDF file (don't go to the next step unless the file\
  \ content was received).\n   If the user does not specify anything, do not clean\
  \ the PDF prior to summarizing it.\n2. Summarize the given PDF content in 100 words\
  \ or less.\n## Output Format\nReturn the summarized document as follows:\n```\n\
  Here is the summarized pdf:\n[summarized pdf]\n```"
tools:
- component_type: ClientTool
  id: 4b1a808b-473f-4e00-b413-23fd7143baf6
  name: read_pdf
  description: Reads a PDF file given a filepath
  metadata:
    __metadata_info__: {}
  inputs:
  - description: Path to the pdf file
    type: string
    title: file_path
  - description: Cleans and reformat the pdf pages
    type: boolean
    title: clean_pdf
    default: false
  outputs:
  - type: string
    title: tool_output
toolboxes: []
context_providers: null
can_finish_conversation: false
max_iterations: 3
initial_message: Hi! How can I help you?
caller_input_mode: always
agents: []
flows: []
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

TOOL_REGISTRY = {"read_pdf": read_pdf_server_tool}
assistant: Agent = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_json(serialized_assistant)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `PluginPromptTemplate`
- `PluginRemoveEmptyNonUserMessageTransform`
- `ExtendedAgent`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Next steps

Having learned how to use `ServerTool` and `ClientTool` with assistants in WayFlow, you may now proceed to:

- [How to Create Tools with Multiple Outputs](howto_multiple_output_tool.md)
- [How to Install and Use Ollama](installing_ollama.md)
- [How to Connect Assistants to Data](howto_datastores.md).

## Full code

Click on the card at the [top of this page](#tool-use) to download the full code for this guide or copy the code below.

download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Build Assistants with Tools
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
# python howto_tooluse.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.




# %%[markdown]
## Imports for this guide

# %%
from typing import Annotated

from wayflowcore.agent import Agent
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.flow import Flow
from wayflowcore.models.llmmodelfactory import LlmModel
from wayflowcore.property import BooleanProperty, StringProperty
from wayflowcore.steps import OutputMessageStep, PromptExecutionStep, ToolExecutionStep
from wayflowcore.tools import ClientTool, ServerTool, Tool, ToolRequest, ToolResult, tool

# %%[markdown]
## Configure your LLM

# %%
from wayflowcore.models.vllmmodel import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## Defining some helper functions

# %%
def _read_and_clean_pdf_file(file_path: str, clean_pdf: bool = False):
    from langchain_community.document_loaders import PyPDFLoader

    loader = PyPDFLoader(file_path=file_path)
    page_content_list = []
    for page in loader.lazy_load():
        page_content_list.append(page.page_content)
    if clean_pdf:
        # we remove the extras "\n"
        all_content = []
        for page_content in page_content_list:
            for row in page_content.split("\n"):
                if not row.strip().endswith("."):
                    all_content.append(row)
                else:
                    all_content.append(row + "\n")
    else:
        all_content = page_content_list
    return "\n".join(page_content_list)


# The path to the pdf file to be summarized
PDF_FILE_PATH = "path/to/example_document.pdf"



# %%[markdown]
## Defining a tool using the tool decorator

# %%
### Option 1 - Using typing.Annotated
@tool("read_pdf")
def read_pdf_server_tool(
    file_path: Annotated[str, "Path to the pdf file"],
    clean_pdf: Annotated[bool, "Cleans and reformat the pdf pages"] = False,
) -> str:
    """Reads a PDF file given a filepath."""
    return _read_and_clean_pdf_file(file_path, clean_pdf)

### Option 2 - Using only the docstring
@tool("read_pdf", description_mode="only_docstring")
def read_pdf_server_tool(file_path: str, clean_pdf: bool = False) -> str:
    """Reads a PDF file given a filepath."""
    return _read_and_clean_pdf_file(file_path, clean_pdf)


# %%[markdown]
## Defining a tool using the ServerTool

# %%
### Option 1 - Using Properties
read_pdf_server_tool = ServerTool(
    name="read_pdf",
    description="Reads a PDF file given a filepath",
    input_descriptors=[
        StringProperty("file_path", description="Path to the pdf file"),
        BooleanProperty(
            "clean_pdf", description="Cleans and reformat the pdf pages", default_value=False
        ),
    ],
    output_descriptors=[StringProperty()],
    func=_read_and_clean_pdf_file,
)

### Option 2 - Using JSON Schema
read_pdf_server_tool = ServerTool(
    name="read_pdf",
    description="Reads a PDF file given a filepath",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Path to the pdf file",
        },
        "clean_pdf": {
            "type": "boolean",
            "default": False,
            "description": "Cleans and reformat the pdf pages",
        },
    },
    func=_read_and_clean_pdf_file,
    output={"type": "string", "title": "tool_output"},
)

# %%[markdown]
## Defining a build flow helper function

# %%
def build_flow(llm: LlmModel, tool: Tool) -> Flow:
    pdf_read_step = ToolExecutionStep(
        name="pdf_read_step",
        tool=tool,
    )
    summarization_step = PromptExecutionStep(
        name="summarization_step",
        llm=llm,
        prompt_template="Please summarize the following PDF in 100 words or less. PDF:\n{{pdf_content}}",
        input_mapping={"pdf_content": ToolExecutionStep.TOOL_OUTPUT},
    )
    output_step = OutputMessageStep(
        name="output_step",
        message_template="Here is the summarized pdf:\n{{summarized_pdf}}",
        input_mapping={"summarized_pdf": PromptExecutionStep.OUTPUT},
    )
    return Flow(
        begin_step=pdf_read_step,
        control_flow_edges=[
            ControlFlowEdge(source_step=pdf_read_step, destination_step=summarization_step),
            ControlFlowEdge(source_step=summarization_step, destination_step=output_step),
            ControlFlowEdge(source_step=output_step, destination_step=None),
        ],
    )

# %%[markdown]
## Creating and running a flow with a server tool

# %%
assistant = build_flow(llm, read_pdf_server_tool)

inputs = {"file_path": PDF_FILE_PATH, "clean_pdf": False}
conversation = assistant.start_conversation(inputs=inputs)

status = conversation.execute()
if isinstance(status, FinishedStatus):
    flow_outputs = status.output_values
    print(f"---\nFlow outputs >>> {flow_outputs}\n---")
else:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")


# %%[markdown]
## Defining a build agent helper function

# %%
def build_agent(llm: LlmModel, tool: Tool) -> Agent:
    from textwrap import dedent

    custom_instruction = dedent(
        """
        You are helping to load and summarize a PDF file given a filepath.
        ## Context
        You will receive a filepath from the username which indicates the path to the
        PDF file we want to summarize
        ## Task
        You will follow the next instructions:
        1. Use the tool to load the PDF file (don't go to the next step unless the file content was received).
           If the user does not specify anything, do not clean the PDF prior to summarizing it.
        2. Summarize the given PDF content in 100 words or less.
        ## Output Format
        Return the summarized document as follows:
        ```
        Here is the summarized pdf:
        [summarized pdf]
        ```
        """
    ).strip()

    return Agent(
        llm=llm,
        tools=[tool],
        custom_instruction=custom_instruction,
        max_iterations=3,
    )

# %%[markdown]
## Creating and running an agent with a server tool

# %%
assistant = build_agent(llm, read_pdf_server_tool)

conversation = assistant.start_conversation()

conversation.append_user_message(
    f"Please summarize my PDF document (can be found at {PDF_FILE_PATH})"
)
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")


# %%[markdown]
## Defining a tool using the ClientTool

# %%
def _execute_read_pdf_request(tool_request: ToolRequest) -> str:
    args = tool_request.args
    if "file_path" not in args or "clean_pdf" not in args:
        print(f"Missing arguments in tool request, args were {args}")
        return "INVALID_REQUEST"
    return _read_and_clean_pdf_file(args["file_path"], args["clean_pdf"])


def execute_tool_from_tool_request(tool_request: ToolRequest) -> str:
    if tool_request.name == "read_pdf":
        return _execute_read_pdf_request(tool_request)
    else:
        raise ValueError(f"Unknown tool in tool request: {tool_request.name}")


### Option 1 - Using Properties
read_pdf_client_tool = ClientTool(
    name="read_pdf",
    description="Reads a PDF file given a filepath",
    input_descriptors=[
        StringProperty("file_path", description="Path to the pdf file"),
        BooleanProperty(
            "clean_pdf", description="Cleans and reformat the pdf pages", default_value=False
        ),
    ],
    output_descriptors=[StringProperty()],
)

### Option 2 - Using JSON Schema
read_pdf_client_tool = ClientTool(
    name="read_pdf",
    description="Reads a PDF file given a filepath",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Path to the pdf file",
        },
        "clean_pdf": {
            "type": "boolean",
            "default": False,
            "description": "Cleans and reformat the pdf pages",
        },
    },
    output={"type": "string"},
)

# %%[markdown]
## Creating and running a flow with a client tool

# %%
assistant = build_flow(llm, read_pdf_client_tool)

inputs = {"file_path": PDF_FILE_PATH, "clean_pdf": False}
conversation = assistant.start_conversation(inputs=inputs)

status = conversation.execute()

failed = False
if isinstance(status, ToolRequestStatus):
    # Executing the request and sending it back to the assistant
    tool_request = status.tool_requests[0]
    tool_result = execute_tool_from_tool_request(tool_request)
    conversation.append_tool_result(
        ToolResult(content=tool_result, tool_request_id=tool_request.tool_request_id)
    )
else:
    failed = True
    print(f"Invalid execution status, expected ToolRequestStatus, received {type(status)}")

if not failed:
    # Continuing the conversation
    status = conversation.execute()

if not failed and isinstance(status, FinishedStatus):
    flow_outputs = status.output_values
    print(f"---\nFlow outputs >>> {flow_outputs}\n---")
elif not failed:
    print(f"Invalid execution status, expected FinishedStatus, received {type(status)}")
else:
    pass


# %%[markdown]
## Creating and running an agent with a client tool

# %%
assistant = build_agent(llm, read_pdf_client_tool)

conversation = assistant.start_conversation()
conversation.append_user_message(
    f"Please summarize my PDF document (can be found at {PDF_FILE_PATH})"
)

status = conversation.execute()

# Executing the request and sending it back to the assistant
if isinstance(status, ToolRequestStatus):
    tool_request = status.tool_requests[0]
    tool_result = execute_tool_from_tool_request(tool_request)
    conversation.append_tool_result(
        ToolResult(content=tool_result, tool_request_id=tool_request.tool_request_id)
    )
else:
    failed = True
    print(f"Invalid execution status, expected ToolRequestStatus, received {type(status)}")

if not failed:
    # Continuing the conversation
    status = conversation.execute()

if not failed and isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
elif not failed:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")
else:
    pass


# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {"read_pdf": read_pdf_server_tool}
assistant: Agent = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_json(serialized_assistant)
```
