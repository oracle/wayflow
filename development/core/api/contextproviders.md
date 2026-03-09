# Context Providers

## Base classes

<a id="contextprovider"></a>

### *class* wayflowcore.contextproviders.contextprovider.ContextProvider(name=None, description=None, id=None, \_\_metadata_info_\_=None)

Context providers are callable components that are used to provide dynamic contextual information to
WayFlow assistants. They are useful to connect external datasources to an assistant.

* **Parameters:**
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)
  * **id** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### *async* call_async(conversation)

Default sync callable of the context provider

* **Return type:**
  `Any`
* **Parameters:**
  **conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation))

#### *abstract* get_output_descriptors()

* **Return type:**
  `List`[[`Property`](flows.md#wayflowcore.property.Property)]

#### *classmethod* get_static_configuration_descriptors()

Returns a dictionary in which the keys are the names of the configuration items
and the values are the expected type.

* **Return type:**
  `Dict`[`str`, `type`]

#### *property* output_descriptors *: List[[Property](flows.md#wayflowcore.property.Property)]*

## Available Context Providers

<a id="toolcontextprovider"></a>

### *class* wayflowcore.contextproviders.toolcontextprovider.ToolContextProvider(tool, output_name=None, name=None, description=None, id=None, \_\_metadata_info_\_=None)

Context provider to wrap a tool execution.

* **Parameters:**
  * **tool** ([`ServerTool`](tools.md#wayflowcore.tools.servertools.ServerTool)) – The tool to be called as part of this context provider
  * **output_name** (`Optional`[`str`]) – The name of the output of this context provider.
    If None is given, the name of the tool followed by \_output is used.
  * **name** (`Optional`[`str`]) – The name of the context provider
  * **description** (*str* *|* *None*)
  * **id** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from time import time
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.contextproviders import ToolContextProvider
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.steps import OutputMessageStep
>>> from wayflowcore.tools import tool
>>>
>>> @tool(description_mode='only_docstring')
... def current_time() -> str:
...     '''Tool that returns time'''
...     from time import time
...     return str(time())
>>>
>>> context_provider = ToolContextProvider(tool=current_time, output_name="time_output_io", name="tool_step")
>>> display_first_step_time = OutputMessageStep(message_template="{{ time_output_io }}", name="display_first_step_time")
>>>
>>> display_second_step_time = OutputMessageStep(
...     message_template="{{ time_output_io }}", name="display_second_step_time"
... )
>>> flow = Flow(
...     begin_step=display_first_step_time,
...     control_flow_edges=[
...         ControlFlowEdge(
...             source_step=display_first_step_time,
...             destination_step=display_second_step_time,
...         ),
...         ControlFlowEdge(source_step=display_second_step_time, destination_step=None),
...     ],
...     context_providers=[context_provider],
... )
```

#### *async* call_async(conversation)

Default sync callable of the context provider

* **Return type:**
  `Any`
* **Parameters:**
  **conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation))

#### get_output_descriptors()

* **Return type:**
  `List`[[`Property`](flows.md#wayflowcore.property.Property)]

#### *classmethod* get_static_configuration_descriptors()

Returns a dictionary in which the keys are the names of the configuration items
and the values are the expected type.

* **Return type:**
  `Dict`[`str`, `type`]

<a id="flowcontextprovider"></a>

### *class* wayflowcore.contextproviders.flowcontextprovider.FlowContextProvider(flow, flow_output_names=None, name=None, description=None, id=None, \_\_metadata_info_\_=None)

Context provider that wraps and executes a flow.

* **Parameters:**
  * **flow** ([`Flow`](flows.md#wayflowcore.flow.Flow)) – The `Flow` to be used as context. It must not require inputs and must not yield.
  * **flow_output_names** (`Optional`[`List`[`str`]]) – List of output names for the context provider, to be used in the calling flow’s I/O system.
    This list must contain unique names.
    These names, if specified, must be a subset of the context flow’s outputs.
    If not specified, defaults to all outputs from all steps of the provided flow
  * **name** (`Optional`[`str`]) – The name of the context provider
  * **description** (*str* *|* *None*)
  * **id** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.contextproviders import FlowContextProvider
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.steps import OutputMessageStep
>>> contextual_flow = Flow.from_steps([OutputMessageStep(
...     message_template="The current time is 2pm.",
...     output_mapping={OutputMessageStep.OUTPUT: "time_output_io"},
... )])
>>> context_provider = FlowContextProvider(contextual_flow, flow_output_names=["time_output_io"])
>>> flow = Flow.from_steps(
...     steps=[OutputMessageStep("Last time message: {{time_output_io}}")],
...     context_providers=[context_provider]
... )
>>> conversation = flow.start_conversation()
>>> execution_status = conversation.execute()
>>> last_message = conversation.get_last_message()
>>> # print(last_message.content)
>>> # Last time message: The current time is 2pm.
```

#### *async* call_async(conversation)

Default sync callable of the context provider

* **Return type:**
  `Any`
* **Parameters:**
  **conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation))

#### get_output_descriptors()

* **Return type:**
  `List`[[`Property`](flows.md#wayflowcore.property.Property)]

#### *classmethod* get_static_configuration_descriptors()

Returns a dictionary in which the keys are the names of the configuration items
and the values are the expected type.

* **Return type:**
  `Dict`[`str`, `type`]
