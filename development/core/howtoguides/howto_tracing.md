<a id="top-tracing"></a>

# How to Enable Tracing in WayFlow![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Tracing how-to script](../end_to_end_code_examples/howto_tracing.py)

#### Prerequisites
This guide assumes familiarity with:

- [Using agents](agents.md)

Tracing is a crucial aspect of any application, allowing developers to monitor and analyze the behavior of their system.
In the context of an agentic framework like WayFlow, tracing allows you to understand the interactions between agents,
tools, and other components.

In this guide, you will learn how to:

- Create a [SpanExporter](../api/tracing.md#spanexporter)
- Set up tracing in WayFlow
- Save your traces in a file

## What is Tracing?

Tracing refers to the process of collecting and analyzing data about the execution of a program or system.
This data can include information about function calls, variable assignments, and other events that occur during execution.
By analyzing this data, developers can identify performance bottlenecks, debug issues, and optimize their system for better performance.

## Why is Tracing Important?

Tracing is essential for several reasons:

* **Debugging**: Tracing helps developers identify and diagnose issues in their agents.
  By analyzing the trace data, they can pinpoint the exact location and cause of errors.
* **Performance Optimization**: Tracing provides insights into the performance characteristics of an agent, enabling
  developers to identify bottlenecks and optimize their architectures for better efficiency.
* **Monitoring**: Tracing allows developers to monitor the behavior of their agents in real-time, enabling them
  to detect anomalies and respond promptly to issues.

## Basic implementation

To set up tracing in WayFlow, you need to provide an implementation of the [SpanProcessor](../api/tracing.md#spanprocessor)
and [SpanExporter](../api/tracing.md#spanexporter) classes.

A [SpanProcessor](../api/tracing.md#spanprocessor) is a common concept in the observability world.
It is a component in the tracing pipeline responsible for receiving and processing spans as they are
created and completed by the application.
[SpanProcessor](../api/tracing.md#spanprocessor) sit between the tracing backend and the exporter, allowing developers
to implement logic such as batching, filtering, modification, or immediate export of [Spans](../api/tracing.md#span).
When a [Span](../api/tracing.md#span) ends, the [SpanProcessor](../api/tracing.md#spanprocessor) determines what happens to it next,
whether it’s sent off immediately, or collected for more efficient periodic export (e.g., doing batching).
This flexible mechanism enables customization of trace data handling before it’s ultimately exported to backend observability systems.

A [SpanExporter](../api/tracing.md#spanexporter) is a component that is responsible for sending finished spans, along with their
collected trace data, from the application to an external backend or observability system for storage and analysis.
The exporter receives spans from the [SpanProcessor](../api/tracing.md#spanprocessor) and translates them into the appropriate format
for the target system, such as [LangFuse](https://langfuse.com),
[LangSmith](https://www.langchain.com/langsmith), or
[OCI APM](https://www.oracle.com/nl/manageability/application-performance-monitoring/).
Exporters encapsulate the logic required to connect, serialize, and transmit data, allowing OpenTelemetry
to support a wide range of backends through a consistent, pluggable interface.
This mechanism enables seamless integration of collected trace data with various monitoring and tracing platforms.

In the following sections you will learn how to implement a combination of SpanProcessor and SpanExporter
that can export traces to a file.

### SpanProcessor and SpanExporter

#### DANGER
Several security concerns arise when implementing SpanProcessors and SpanExporters, which include,
but they are not limited to, the security of the network used to export traces, and the sensitivity of the
information exported. Please refer to our [Security Guidelines](../security.md) for more information.

As partially anticipated in the previous section, the most simple implementation of a [SpanProcessor](../api/tracing.md#spanprocessor)
is the one that exports the received [Span](../api/tracing.md#span) as-is, without any modification, as soon as the [Span](../api/tracing.md#span) is closed.
This implementation is provided by `wayflowcore`, and it is called [SimpleSpanProcessor](../api/tracing.md#simplespanprocessor).
You will use an instance of this [SpanProcessor](../api/tracing.md#spanprocessor) in this guide.

For what concerns the [SpanExporter](../api/tracing.md#spanexporter), you can implement a version of it that just prints
the information contained in the [Spans](../api/tracing.md#span) to a file at a given path.
The implementation can focus on the export method, that opens the file in append mode, and it prints in it
the content of the [Spans](../api/tracing.md#span) retrieved through the to_tracing_info method.

```python
import pprint
from pathlib import Path
from typing import List, Union
import os
from wayflowcore.tracing.span import Span
from wayflowcore.tracing.spanexporter import SpanExporter

class FileSpanExporter(SpanExporter):
    """SpanExporter that prints spans to a file.

    This class can be used for diagnostic purposes.
    It prints the exported spans to a file.
    """

    def __init__(self, filepath: Union[str, Path]):
        if isinstance(filepath, str):
            filepath = Path(filepath)
        self.filepath: Path = filepath

    def export(self, spans: List[Span], mask_sensitive_information=True) -> None:
        with open(self.filepath, "a") as file:
            for span in spans:
                print(
                    pprint.pformat(span.to_tracing_info(mask_sensitive_information), width=80, compact=True),
                    file=file,
                )

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass
```

You can now combine [SimpleSpanProcessor](../api/tracing.md#simplespanprocessor) with the FileSpanExporter you just implemented
to set up the basic components that will let you export traces to the desired file.

```python
from wayflowcore.tracing.spanprocessor import SimpleSpanProcessor

span_processor = SimpleSpanProcessor(
    span_exporter=FileSpanExporter(filepath="calculator_agent_traces.txt")
)
```

### Tracking an agent

Now that you have everything you need to process and export traces, you can work on your agent.

In this example, you are going to build a simple calculator agent with four tools, one for each of the basic operations:
addition, subtraction, multiplication, division.

```python
from wayflowcore.agent import Agent
from wayflowcore.models import VllmModel
from wayflowcore.tools import tool

@tool(description_mode="only_docstring")
def multiply(a: float, b: float) -> float:
    """Multiply two numbers"""
    return a * b


@tool(description_mode="only_docstring")
def divide(a: float, b: float) -> float:
    """Divide two numbers"""
    return a / b


@tool(description_mode="only_docstring")
def sum(a: float, b: float) -> float:
    """Sum two numbers"""
    return a + b


@tool(description_mode="only_docstring")
def subtract(a: float, b: float) -> float:
    """Subtract two numbers"""
    return a - b


llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

agent = Agent(
    agent_id="calculator_agent",
    name="Calculator agent",
    custom_instruction="You are a calculator agent. Please use tools to do math.",
    initial_message="Hi! I am a calculator agent. How can I help you?",
    llm=llm,
    tools=[sum, subtract, multiply, divide],
)
```

We now run your agent enabling traces, and using the `FileSpanExporter` in order to export the traces in a file.
To do that, just wrap the execution loop of our agent in a [Trace](../api/tracing.md#id2) context manager.

```python
from wayflowcore.tracing.span import ConversationSpan
from wayflowcore.tracing.trace import Trace

conversation = agent.start_conversation()
with Trace(span_processors=[span_processor]):
    with ConversationSpan(conversation=conversation) as conversation_span:
        conversation.execute()
        conversation.append_user_message("Compute 2+3")
        status = conversation.execute()
        conversation_span.record_end_span_event(execution_status=status)
```

You can now run our code and inspect the traces saved in your file.

## Emitting Agent Spec Traces

Open Agent Specification Tracing (short: Agent Spec Tracing) is an extension of
Agent Spec that standardizes how agent and flow executions emit traces.
It defines a unified, implementation-agnostic semantic for, Events, Spans, Traces, and SpanProcessors, with
the same semantic presented for WayFlow in this guide.

WayFlow offers an `EventListener` called [AgentSpecEventListener](../api/agentspec.md#agentspeceventlistener) that
makes WayFlow components emit traces according to the Agent Spec Tracing standard.
Here’s an example of how to use it in your code.

```python
from pyagentspec.tracing.trace import Trace as AgentSpecTrace
from wayflowcore.agentspec.tracing import AgentSpecEventListener
from wayflowcore.events.eventlistener import register_event_listeners

# Here you can register the SpanProcessors that consume Agent Spec Traces emitted by WayFlow
with AgentSpecTrace() as trace:
    with register_event_listeners([AgentSpecEventListener()]):
        conversation.execute()
        conversation.append_user_message("Compute 2+3")
        status = conversation.execute()
```

## Agent Spec Exporting/Loading

You can export the agent configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(agent)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "ExtendedAgent",
  "id": "calculator_agent",
  "name": "Calculator agent",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [],
  "outputs": [],
  "llm_config": {
    "component_type": "VllmConfig",
    "id": "2f1ca95b-d333-43a6-9518-a995a87418c1",
    "name": "LLAMA_MODEL_ID",
    "description": null,
    "metadata": {
      "__metadata_info__": {}
    },
    "default_generation_parameters": null,
    "url": "LLAMA_API_URL",
    "model_id": "LLAMA_MODEL_ID"
  },
  "system_prompt": "You are a calculator agent. Please use tools to do math.",
  "tools": [
    {
      "component_type": "ServerTool",
      "id": "bd8ba23f-162c-4c79-831d-96e03e40d2bd",
      "name": "sum",
      "description": "Sum two numbers",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "number",
          "title": "a"
        },
        {
          "type": "number",
          "title": "b"
        }
      ],
      "outputs": [
        {
          "type": "number",
          "title": "tool_output"
        }
      ]
    },
    {
      "component_type": "ServerTool",
      "id": "9bb68f19-8bd9-4089-8511-92afe680e21d",
      "name": "subtract",
      "description": "Subtract two numbers",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "number",
          "title": "a"
        },
        {
          "type": "number",
          "title": "b"
        }
      ],
      "outputs": [
        {
          "type": "number",
          "title": "tool_output"
        }
      ]
    },
    {
      "component_type": "ServerTool",
      "id": "e7d348eb-ced2-4d75-b80a-90c1b700ce7f",
      "name": "multiply",
      "description": "Multiply two numbers",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "number",
          "title": "a"
        },
        {
          "type": "number",
          "title": "b"
        }
      ],
      "outputs": [
        {
          "type": "number",
          "title": "tool_output"
        }
      ]
    },
    {
      "component_type": "ServerTool",
      "id": "29decfc0-687d-44de-bf96-3e0f8d716e8b",
      "name": "divide",
      "description": "Divide two numbers",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "number",
          "title": "a"
        },
        {
          "type": "number",
          "title": "b"
        }
      ],
      "outputs": [
        {
          "type": "number",
          "title": "tool_output"
        }
      ]
    }
  ],
  "toolboxes": [],
  "context_providers": null,
  "can_finish_conversation": false,
  "max_iterations": 10,
  "initial_message": "Hi! I am a calculator agent. How can I help you?",
  "caller_input_mode": "always",
  "agents": [],
  "flows": [],
  "agent_template": {
    "component_type": "PluginPromptTemplate",
    "id": "0d9a17fb-25aa-419a-97e6-f9fec9b327c3",
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
            "content": "{% if custom_instruction %}{{custom_instruction}}{% endif %}"
          }
        ],
        "tool_requests": null,
        "tool_result": null,
        "display_only": false,
        "sender": null,
        "recipients": [],
        "time_created": "2025-09-02T16:00:18.701799+00:00",
        "time_updated": "2025-09-02T16:00:18.701801+00:00"
      },
      {
        "role": "user",
        "contents": [],
        "tool_requests": null,
        "tool_result": null,
        "display_only": false,
        "sender": null,
        "recipients": [],
        "time_created": "2025-09-02T16:00:18.691523+00:00",
        "time_updated": "2025-09-02T16:00:18.691721+00:00"
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
        "time_created": "2025-09-02T16:00:18.701837+00:00",
        "time_updated": "2025-09-02T16:00:18.701838+00:00"
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
        "id": "6eae1b8c-4319-4bd0-bd49-0828e82d16fd",
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
id: calculator_agent
name: Calculator agent
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs: []
llm_config:
  component_type: VllmConfig
  id: 2f1ca95b-d333-43a6-9518-a995a87418c1
  name: LLAMA_MODEL_ID
  description: null
  metadata:
    __metadata_info__: {}
  default_generation_parameters: null
  url: LLAMA_API_URL
  model_id: LLAMA_MODEL_ID
system_prompt: You are a calculator agent. Please use tools to do math.
tools:
- component_type: ServerTool
  id: bd8ba23f-162c-4c79-831d-96e03e40d2bd
  name: sum
  description: Sum two numbers
  metadata:
    __metadata_info__: {}
  inputs:
  - type: number
    title: a
  - type: number
    title: b
  outputs:
  - type: number
    title: tool_output
- component_type: ServerTool
  id: 9bb68f19-8bd9-4089-8511-92afe680e21d
  name: subtract
  description: Subtract two numbers
  metadata:
    __metadata_info__: {}
  inputs:
  - type: number
    title: a
  - type: number
    title: b
  outputs:
  - type: number
    title: tool_output
- component_type: ServerTool
  id: e7d348eb-ced2-4d75-b80a-90c1b700ce7f
  name: multiply
  description: Multiply two numbers
  metadata:
    __metadata_info__: {}
  inputs:
  - type: number
    title: a
  - type: number
    title: b
  outputs:
  - type: number
    title: tool_output
- component_type: ServerTool
  id: 29decfc0-687d-44de-bf96-3e0f8d716e8b
  name: divide
  description: Divide two numbers
  metadata:
    __metadata_info__: {}
  inputs:
  - type: number
    title: a
  - type: number
    title: b
  outputs:
  - type: number
    title: tool_output
toolboxes: []
context_providers: null
can_finish_conversation: false
max_iterations: 10
initial_message: Hi! I am a calculator agent. How can I help you?
caller_input_mode: always
agents: []
flows: []
agent_template:
  component_type: PluginPromptTemplate
  id: 0d9a17fb-25aa-419a-97e6-f9fec9b327c3
  name: ''
  description: null
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
    time_created: '2025-09-02T16:00:18.701799+00:00'
    time_updated: '2025-09-02T16:00:18.701801+00:00'
  - role: user
    contents: []
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-09-02T16:00:18.691523+00:00'
    time_updated: '2025-09-02T16:00:18.691721+00:00'
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
    time_created: '2025-09-02T16:00:18.701837+00:00'
    time_updated: '2025-09-02T16:00:18.701838+00:00'
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
    id: 6eae1b8c-4319-4bd0-bd49-0828e82d16fd
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

tool_registry = {
    multiply.name: multiply,
    divide.name: divide,
    sum.name: sum,
    subtract.name: subtract,
}
new_agent = AgentSpecLoader(tool_registry=tool_registry).load_json(config)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `PluginPromptTemplate`
- `PluginRemoveEmptyNonUserMessageTransform`
- `ExtendedAgent`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Using OpenTelemetry SpanProcessors

[OpenTelemetry](https://opentelemetry.io) is an open-source observability framework that provides standardized APIs and
libraries to collect, process, and export telemetry data from distributed systems.
This standard is agnostic with respect to the domain of application, so it can be easily
adopted also for tracing in agentic frameworks.

Tracing in WayFlow is largely inspired by the OpenTelemetry standard, therefore most of the
concepts and APIs overlap.
For this reason, `wayflowcore` offers the implementation of two `SpanProcessors` that follow
the OpenTelemetry standard:

- [OtelSimpleSpanProcessor](../api/tracing.md#otelsimplespanprocessor): A span processor that exports spans one by one
- [OtelBatchSpanProcessor](../api/tracing.md#otelbatchspanprocessor): A span processor that exports spans in batches

These span processors wrap the OpenTelemetry implementation, transform WayFlow spans into OpenTelemetry ones,
and emulate the expected behavior of the processor.
Moreover, they allow using OpenTelemetry compatible `SpanExporter`, like, for example,
those offered by the [OpenTelemetry Exporters library](https://opentelemetry-python.readthedocs.io/en/latest/exporter/index.html).

## Next steps

Now that you’ve learned tracing in WayFlow, you might want to apply it in other scenarios:

- [How to Build a Swarm of Agents](howto_swarm.md)
- [How to Build Multi-Agent Assistants](howto_multiagent.md)

## Full code

Click on the card at the [top of this page](#top-tracing) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Enable Tracing
# ------------------------------------

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
# python howto_tracing.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import warnings

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.CRITICAL)


# %%[markdown]
## Span Exporter Setup

# %%
import pprint
from pathlib import Path
from typing import List, Union
import os
from wayflowcore.tracing.span import Span
from wayflowcore.tracing.spanexporter import SpanExporter

class FileSpanExporter(SpanExporter):
    """SpanExporter that prints spans to a file.

    This class can be used for diagnostic purposes.
    It prints the exported spans to a file.
    """

    def __init__(self, filepath: Union[str, Path]):
        if isinstance(filepath, str):
            filepath = Path(filepath)
        self.filepath: Path = filepath

    def export(self, spans: List[Span], mask_sensitive_information=True) -> None:
        with open(self.filepath, "a") as file:
            for span in spans:
                print(
                    pprint.pformat(span.to_tracing_info(mask_sensitive_information), width=80, compact=True),
                    file=file,
                )

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

# %%[markdown]
## Build Calculator Agent

# %%
from wayflowcore.agent import Agent
from wayflowcore.models import VllmModel
from wayflowcore.tools import tool

@tool(description_mode="only_docstring")
def multiply(a: float, b: float) -> float:
    """Multiply two numbers"""
    return a * b


@tool(description_mode="only_docstring")
def divide(a: float, b: float) -> float:
    """Divide two numbers"""
    return a / b


@tool(description_mode="only_docstring")
def sum(a: float, b: float) -> float:
    """Sum two numbers"""
    return a + b


@tool(description_mode="only_docstring")
def subtract(a: float, b: float) -> float:
    """Subtract two numbers"""
    return a - b


llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

agent = Agent(
    agent_id="calculator_agent",
    name="Calculator agent",
    custom_instruction="You are a calculator agent. Please use tools to do math.",
    initial_message="Hi! I am a calculator agent. How can I help you?",
    llm=llm,
    tools=[sum, subtract, multiply, divide],
)

# %%[markdown]
## Export Config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(agent)

# %%[markdown]
## Load Agent Spec Config

# %%
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {
    multiply.name: multiply,
    divide.name: divide,
    sum.name: sum,
    subtract.name: subtract,
}
new_agent = AgentSpecLoader(tool_registry=tool_registry).load_json(config)

# %%[markdown]
## Tracing Basics

# %%
from wayflowcore.tracing.spanprocessor import SimpleSpanProcessor

span_processor = SimpleSpanProcessor(
    span_exporter=FileSpanExporter(filepath="calculator_agent_traces.txt")
)

# %%[markdown]
## Agent Execution With Tracing

# %%
from wayflowcore.tracing.span import ConversationSpan
from wayflowcore.tracing.trace import Trace

conversation = agent.start_conversation()
with Trace(span_processors=[span_processor]):
    with ConversationSpan(conversation=conversation) as conversation_span:
        conversation.execute()
        conversation.append_user_message("Compute 2+3")
        status = conversation.execute()
        conversation_span.record_end_span_event(execution_status=status)


# %%[markdown]
## Enable Agent Spec Tracing

# %%
from pyagentspec.tracing.trace import Trace as AgentSpecTrace
from wayflowcore.agentspec.tracing import AgentSpecEventListener
from wayflowcore.events.eventlistener import register_event_listeners

# Here you can register the SpanProcessors that consume Agent Spec Traces emitted by WayFlow
with AgentSpecTrace() as trace:
    with register_event_listeners([AgentSpecEventListener()]):
        conversation.execute()
        conversation.append_user_message("Compute 2+3")
        status = conversation.execute()
```
