<a id="top-event-system"></a>

# How to Use the Event System![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Event System how-to script](../code_examples/howto_event_system.py)

#### Prerequisites
This guide assumes familiarity with:

- [Using agents](agents.md)

The event system in WayFlow provides a powerful framework for monitoring and debugging agents and flows.
By capturing detailed runtime data through structured events, it offers deep insights into interactions between agents, flows, tools, and LLMs.

This guide introduces the core concepts of the event system, describes available event types and listeners, and provides practical examples for effective implementation.

At its heart, WayFlow’s event system records and communicates key occurrences during an execution. Each event is a structured data object that captures details of a specific action or state change, such as starting a conversation, executing a tool, or generating an LLM response. Events include metadata like unique identifiers, timestamps, and relevant contextual information.

The system follows a publish-subscribe model: events are published as they occur, and components called listeners subscribe to receive and react to them. This separation of event generation and handling allows developers to add custom behaviors or logging without altering the core logic of agents or flows.

## Basic Implementation

To use the event system effectively, you need to understand its two main components: [Events](../api/events.md#events) and [EventListeners](../api/events.md#eventlisteners).

- [Events](../api/events.md#events) are data structures that represent occurrences within WayFlow, organized into different types for various scenarios.
- [EventListeners](../api/events.md#eventlisteners) are components that react to these published events.

Let’s explore this with two practical examples:

## Example 1: Computing LLM Token Usage

A key use of the event system is tracking resource consumption, such as monitoring token usage during LLM interactions.
Since token usage affects operational costs, this data can inform prompt and model optimization.
By subscribing to LLM response events, developers can aggregate and analyze token usage across a conversation.

```python
class TokenUsageListener(EventListener):
    """Custom event listener to track token usage from LLM responses."""
    def __init__(self):
        self.total_tokens_used = 0

    def __call__(self, event: Event):
        if isinstance(event, LlmGenerationResponseEvent):
            token_usage = event.completion.token_usage
            if token_usage:
                self.total_tokens_used += token_usage.total_tokens
                logging.info(f"Tokens used in this response: {token_usage.total_tokens}")
                logging.info(f"Running total tokens used: {self.total_tokens_used}")

    def get_total_tokens_used(self):
        """Return the total number of tokens used."""
        return self.total_tokens_used
```

In this example, `TokenUsageListener` is a custom listener that calculates total token usage by summing the tokens reported in each [LlmGenerationResponseEvent](../api/events.md#llmgenerationresponseevent).

## Example 2: Tracking Tool Calls

Another useful application is monitoring tool invocations within an agentic workflow.
Understanding which tools are used and their frequency helps developers evaluate the effectiveness of their toolset and identify opportunities for improvement.
By listening to tool execution events, you can log each call and track usage patterns.

```python
class ToolCallListener(EventListener):
    """Custom event listener to track the number and type of tool calls."""
    def __init__(self):
        self.tool_calls = defaultdict(int)

    def __call__(self, event: ToolExecutionStartEvent):
        if isinstance(event, ToolExecutionStartEvent):
            self.tool_calls[str(event.tool.name)] += 1

    def get_tool_call_summary(self):
        """Return a summary of tool calls."""
        return self.tool_calls
```

This snippet illustrates how to create a `ToolCallListener` to track tool invocations using [ToolExecutionStartEvent](../api/events.md#toolexecutionstartevent).

With both listeners implemented, let’s apply them in a conversation with an [Agent](../api/agent.md#agent).

For LLMs, WayFlow supports multiple API providers. Select an LLM from the options below:




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

Now, let’s set up an agent:

```python
@tool(description_mode="only_docstring")
def add(a: float, b: float) -> float:
    """Add two numbers.

    Parameters:
        a: The first number.
        b: The second number.

    Returns:
        float: The sum of the two numbers.
    """
    return a + b

@tool(description_mode="only_docstring")
def multiply(a: float, b: float) -> float:
    """Multiply two numbers.

    Parameters:
        a: The first number.
        b: The second number.

    Returns:
        float: The product of the two numbers.
    """
    return a * b

agent = Agent(llm=llm, tools=[add, multiply], name="Calculator Agent")
```

Using the agent in a conversation:

```python
token_listener = TokenUsageListener()
tool_call_listener = ToolCallListener()

event_listeners = [token_listener, tool_call_listener]

with register_event_listeners(event_listeners):
    conversation = agent.start_conversation()
    conversation.append_user_message("Calculate 6*2+3 using the tools you have.")
    status = conversation.execute()

print(f"Total Tokens Used in Conversation: {token_listener.get_total_tokens_used()}")
tool_summary = tool_call_listener.get_tool_call_summary()
print(f"Tool Call Summary: {tool_summary}")
```

Both listeners are registered within a context manager using [register_event_listeners](../api/events.md#registereventlisteners) during agent execution, ensuring they capture all relevant events.

Beyond the events highlighted here, WayFlow offers a wide range of events for detailed monitoring. Below is a table explaining various types of events in Wayflow:

<a id="listofsupportedevents"></a>

#### WayFlow Event Types

Event Name

Description

[Event](../api/events.md#event)

Base event class containing information relevant to all events.

[LlmGenerationRequestEvent](../api/events.md#llmgenerationrequestevent)

Recorded when the LLM receives a generation request.

[LlmGenerationResponseEvent](../api/events.md#llmgenerationresponseevent)

Recorded when the LLM generates a response.

[ConversationalComponentExecutionStartedEvent](../api/events.md#conversationalcomponentexecutionstartedevent)

Recorded when the agent/flow execution has started.

[ConversationalComponentExecutionFinishedEvent](../api/events.md#conversationalcomponentexecutionfinishedevent)

Recorded when the agent/flow execution has ended.

[ConversationCreatedEvent](../api/events.md#conversationcreatedevent)

Recorded whenever a new conversation with an agent or a flow was created.

[ConversationMessageAddedEvent](../api/events.md#conversationmessageaddedevent)

Recorded whenever a new message was added to the conversation.

[ConversationMessageStreamStartedEvent](../api/events.md#conversationmessagestreamstartedevent)

Recorded whenever a new message starts being streamed to the conversation.

[ConversationMessageStreamChunkEvent](../api/events.md#conversationmessagestreamchunkevent)

Recorded whenever a message is being streamed and a delta is added to the conversation.

[ConversationMessageStreamEndedEvent](../api/events.md#conversationmessagestreamendedevent)

Recorded whenever a streamed message to the conversation ends.

[ConversationExecutionStartedEvent](../api/events.md#conversationexecutionstartedevent)

Recorded whenever a conversation is started.

[ConversationExecutionFinishedEvent](../api/events.md#conversationexecutionfinishedevent)

Recorded whenever a conversation execution finishes.

[ToolExecutionStartEvent](../api/events.md#toolexecutionstartevent)

Recorded whenever a tool is executed.

[ToolExecutionResultEvent](../api/events.md#toolexecutionresultevent)

Recorded whenever a tool has finished execution.

[ToolConfirmationRequestStartEvent](../api/events.md#toolconfirmationrequeststartevent)

Recorded whenever a tool confirmation is required.

[ToolConfirmationRequestEndEvent](../api/events.md#toolconfirmationrequestendevent)

Recorded whenever a tool confirmation has been handled.

[StepInvocationStartEvent](../api/events.md#stepinvocationstartevent)

Recorded whenever a step is invoked.

[StepInvocationResultEvent](../api/events.md#stepinvocationresultevent)

Recorded whenever a step invocation has finished.

[ContextProviderExecutionRequestEvent](../api/events.md#contextproviderexecutionrequestevent)

Recorded whenever a context provider is called.

[ContextProviderExecutionResultEvent](../api/events.md#contextproviderexecutionresultevent)

Recorded whenever a context provider has returned a result.

[FlowExecutionIterationStartedEvent](../api/events.md#flowexecutioniterationstartedevent)

Recorded whenever an iteration of a flow has started executing.

[FlowExecutionIterationFinishedEvent](../api/events.md#flowexecutioniterationfinishedevent)

Recorded whenever an iteration of a flow has finished executing.

[AgentExecutionIterationStartedEvent](../api/events.md#agentexecutioniterationstartedevent)

Recorded whenever an iteration of an agent has started executing.

[AgentExecutionIterationFinishedEvent](../api/events.md#agentexecutioniterationfinishedevent)

Recorded whenever an iteration of an agent has finished executing.

[ExceptionRaisedEvent](../api/events.md#exceptionraisedevent)

Recorded whenever an exception occurs.

[AgentNextActionDecisionStartEvent](../api/events.md#agentnextactiondecisionstartevent)

Recorded at the start of the agent taking a decision on what to do next.

[AgentDecidedNextActionEvent](../api/events.md#agentdecidednextactionevent)

Recorded whenever the agent decided what to do next.

See [Events](../api/events.md#events) for more information. You can implement custom `EventListener` for these events as shown in the examples above.

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
    "id": "3ede6823-de48-4f1d-9453-ae6d259d3de8",
    "name": "Calculator Agent",
    "description": "",
    "metadata": {
        "__metadata_info__": {}
    },
    "inputs": [],
    "outputs": [],
    "llm_config": {
        "component_type": "VllmConfig",
        "id": "903495a0-9333-484b-b875-3e0405f3ecc6",
        "name": "llm_86037e63__auto",
        "description": null,
        "metadata": {
            "__metadata_info__": {}
        },
        "default_generation_parameters": null,
        "url": "LLAMA_API_URL",
        "model_id": "LLAMA_MODEL_ID"
    },
    "system_prompt": "",
    "tools": [
        {
            "component_type": "ServerTool",
            "id": "4907e7b5-7a30-48b0-9911-5f674e2a4ff2",
            "name": "add",
            "description": "Add two numbers.\n\nParameters:\n    a: The first number.\n    b: The second number.\n\nReturns:\n    float: The sum of the two numbers.",
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
            "id": "c9c2a079-b34e-44ac-93d8-864fc3ff3f87",
            "name": "multiply",
            "description": "Multiply two numbers.\n\nParameters:\n    a: The first number.\n    b: The second number.\n\nReturns:\n    float: The product of the two numbers.",
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
    "human_in_the_loop": true,
    "context_providers": null,
    "can_finish_conversation": false,
    "raise_exceptions": false,
    "max_iterations": 10,
    "initial_message": "Hi! How can I help you?",
    "caller_input_mode": "always",
    "agents": [],
    "flows": [],
    "agent_template": {
        "component_type": "PluginPromptTemplate",
        "id": "f05c7228-c45d-4605-90eb-89e66e4fe7da",
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
                "time_created": "2026-01-06T10:47:26.111071+00:00",
                "time_updated": "2026-01-06T10:47:26.111071+00:00"
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
                "time_created": "2026-01-06T10:47:26.106776+00:00",
                "time_updated": "2026-01-06T10:47:26.106777+00:00"
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
                "time_created": "2026-01-06T10:47:26.111096+00:00",
                "time_updated": "2026-01-06T10:47:26.111096+00:00"
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
                "id": "0a2cc909-11bc-4533-8ff1-2867938f4bb8",
                "name": "removeemptynonusermessage_messagetransform",
                "description": null,
                "metadata": {
                    "__metadata_info__": {}
                },
                "component_plugin_name": "MessageTransformPlugin",
                "component_plugin_version": "26.1.0.dev5"
            }
        ],
        "tools": null,
        "native_tool_calling": true,
        "response_format": null,
        "native_structured_generation": true,
        "generation_config": null,
        "component_plugin_name": "PromptTemplatePlugin",
        "component_plugin_version": "26.1.0.dev5"
    },
    "component_plugin_name": "AgentPlugin",
    "component_plugin_version": "26.1.0.dev5",
    "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: ExtendedAgent
id: 3ede6823-de48-4f1d-9453-ae6d259d3de8
name: Calculator Agent
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs: []
llm_config:
  component_type: VllmConfig
  id: 903495a0-9333-484b-b875-3e0405f3ecc6
  name: llm_86037e63__auto
  description: null
  metadata:
    __metadata_info__: {}
  default_generation_parameters: null
  url: LLAMA_API_URL
  model_id: LLAMA_MODEL_ID
system_prompt: ''
tools:
- component_type: ServerTool
  id: 4907e7b5-7a30-48b0-9911-5f674e2a4ff2
  name: add
  description: "Add two numbers.\n\nParameters:\n    a: The first number.\n    b:\
    \ The second number.\n\nReturns:\n    float: The sum of the two numbers."
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
  id: c9c2a079-b34e-44ac-93d8-864fc3ff3f87
  name: multiply
  description: "Multiply two numbers.\n\nParameters:\n    a: The first number.\n \
    \   b: The second number.\n\nReturns:\n    float: The product of the two numbers."
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
human_in_the_loop: true
context_providers: null
can_finish_conversation: false
raise_exceptions: false
max_iterations: 10
initial_message: Hi! How can I help you?
caller_input_mode: always
agents: []
flows: []
agent_template:
  component_type: PluginPromptTemplate
  id: f05c7228-c45d-4605-90eb-89e66e4fe7da
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
    time_created: '2026-01-06T10:47:26.111071+00:00'
    time_updated: '2026-01-06T10:47:26.111071+00:00'
  - role: system
    contents:
    - type: text
      content: $$__CHAT_HISTORY_PLACEHOLDER__$$
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2026-01-06T10:47:26.106776+00:00'
    time_updated: '2026-01-06T10:47:26.106777+00:00'
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
    time_created: '2026-01-06T10:47:26.111096+00:00'
    time_updated: '2026-01-06T10:47:26.111096+00:00'
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
    id: 45667ebd-800f-4a0e-8140-f6ccd06556e8
    name: removeemptynonusermessage_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 26.1.0.dev5
  tools: null
  native_tool_calling: true
  response_format: null
  native_structured_generation: true
  generation_config: null
  component_plugin_name: PromptTemplatePlugin
  component_plugin_version: 26.1.0.dev5
component_plugin_name: AgentPlugin
component_plugin_version: 26.1.0.dev5
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader(tool_registry={'add': add, 'multiply': multiply}).load_json(serialized_assistant)
```

## Next Steps

After exploring the event system in WayFlow, consider learning more about related features to further enhance your agentic applications:

- [How to Enable Tracing in WayFlow](howto_tracing.md)
- [How to Build a Swarm of Agents](howto_swarm.md)

## Full Code

Click on the card at the [top of this page](#top-event-system) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Use the Event System
# ------------------------------------------

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
# python howto_event_system.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


from collections import defaultdict
import logging

from wayflowcore.events.event import Event, LlmGenerationResponseEvent, ToolExecutionStartEvent
from wayflowcore.events.eventlistener import EventListener, register_event_listeners
from wayflowcore.models import VllmModel
from wayflowcore.agent import Agent
from wayflowcore.tools import tool


# %%[markdown]
## TokenUsage

# %%
class TokenUsageListener(EventListener):
    """Custom event listener to track token usage from LLM responses."""
    def __init__(self):
        self.total_tokens_used = 0

    def __call__(self, event: Event):
        if isinstance(event, LlmGenerationResponseEvent):
            token_usage = event.completion.token_usage
            if token_usage:
                self.total_tokens_used += token_usage.total_tokens
                logging.info(f"Tokens used in this response: {token_usage.total_tokens}")
                logging.info(f"Running total tokens used: {self.total_tokens_used}")

    def get_total_tokens_used(self):
        """Return the total number of tokens used."""
        return self.total_tokens_used


# %%[markdown]
## Tool Call Listener

# %%
class ToolCallListener(EventListener):
    """Custom event listener to track the number and type of tool calls."""
    def __init__(self):
        self.tool_calls = defaultdict(int)

    def __call__(self, event: ToolExecutionStartEvent):
        if isinstance(event, ToolExecutionStartEvent):
            self.tool_calls[str(event.tool.name)] += 1

    def get_tool_call_summary(self):
        """Return a summary of tool calls."""
        return self.tool_calls

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)


# %%[markdown]
## Agent

# %%
@tool(description_mode="only_docstring")
def add(a: float, b: float) -> float:
    """Add two numbers.

    Parameters:
        a: The first number.
        b: The second number.

    Returns:
        float: The sum of the two numbers.
    """
    return a + b

@tool(description_mode="only_docstring")
def multiply(a: float, b: float) -> float:
    """Multiply two numbers.

    Parameters:
        a: The first number.
        b: The second number.

    Returns:
        float: The product of the two numbers.
    """
    return a * b

agent = Agent(llm=llm, tools=[add, multiply], name="Calculator Agent")



# %%[markdown]
## Conversation

# %%
token_listener = TokenUsageListener()
tool_call_listener = ToolCallListener()

event_listeners = [token_listener, tool_call_listener]

with register_event_listeners(event_listeners):
    conversation = agent.start_conversation()
    conversation.append_user_message("Calculate 6*2+3 using the tools you have.")
    status = conversation.execute()

print(f"Total Tokens Used in Conversation: {token_listener.get_total_tokens_used()}")
tool_summary = tool_call_listener.get_tool_call_summary()
print(f"Tool Call Summary: {tool_summary}")


# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(agent)


# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader(tool_registry={'add': add, 'multiply': multiply}).load_json(serialized_assistant)
```

|    |    |
|----|----|
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
|    |    |
