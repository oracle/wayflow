<a id="agentspec-adapters"></a>

# Agent Spec Adapters

This page presents all APIs and classes related to Agent Spec and WayFlow.

![agentspec-icon](_static/icons/agentspec-icon.svg)

Visit the Agent Spec API Documentation to learn more about the native Agent Spec Components.

[Agent Spec - API Reference](https://oracle.github.io/agent-spec/api/index.html)

#### TIP
Click the button above ↑ to visit the [Agent Spec Documentation](https://oracle.github.io/agent-spec/index.html)

<a id="agentspecexporter"></a>

### *class* wayflowcore.agentspec.agentspecexporter.AgentSpecExporter(plugins=None)

Helper class to convert WayFlow objects to Agent Spec configurations.

* **Parameters:**
  **plugins** (`Optional`[`List`[`Union`[`ComponentSerializationPlugin`, [`WayflowSerializationPlugin`](serialization.md#wayflowcore.serialization.plugins.WayflowSerializationPlugin)]]]) – 

  List of additional wayflow plugins to use. By default, uses the latest supported builtin plugins only.
  <!-- note:

  Passing a list of ``ComponentSerializationPlugin`` from ``pyagentspec`` is deprecated
  since wayflowcore==26.1.0. -->

#### to_component(runtime_component)

Transform the given WayFlow component into the respective PyAgentSpec Component.

* **Parameters:**
  **runtime_component** ([`Component`](component.md#wayflowcore.component.Component)) – WayFlow Component to serialize to a corresponding PyAgentSpec Component.
* **Return type:**
  `Component`

#### to_json(runtime_component, agentspec_version=None, disaggregated_components=None, export_disaggregated_components=False)

Transform the given WayFlow component into the respective Agent Spec JSON representation.

* **Parameters:**
  * **runtime_component** ([`Component`](component.md#wayflowcore.component.Component)) – WayFlow component to serialize to an Agent Spec configuration.
  * **agentspec_version** (`Optional`[`AgentSpecVersionEnum`]) – The Agent Spec version of the component.
  * **disaggregated_components** (`Optional`[`Sequence`[`Union`[[`Component`](component.md#wayflowcore.component.Component), `Tuple`[[`Component`](component.md#wayflowcore.component.Component), `str`]]]]) – 

    Configuration specifying the components/fields to disaggregate upon serialization.
    Each item can be:
    - A `Component`: to disaggregate the component using its id
    - A tuple `(Component, str)`: to disaggregate the component using
      a custom id.

    #### NOTE
    Components in `disaggregated_components` are disaggregated
    even if `export_disaggregated_components` is `False`.
  * **export_disaggregated_components** (`bool`) – Whether to export the disaggregated components or not. Defaults to `False`.
* **Return type:**
  `Union`[`str`, `Tuple`[`str`, `str`]]
* **Returns:**
  * If `export_disaggregated_components` is `True`
  * *str* – The JSON serialization of the root component.
  * *str* – The JSON serialization of the disaggregated components.
  * If `export_disaggregated_components` is `False`
  * *str* – The JSON serialization of the root component.

### Examples

Basic serialization is done as follows.

```pycon
>>> from wayflowcore.agent import Agent
>>> from wayflowcore.agentspec import AgentSpecExporter
>>> from wayflowcore.models import VllmModel
>>> from wayflowcore.tools import tool
>>>
>>> llm = VllmModel(
...     model_id="model-id",
...     host_port="VLLM_HOST_PORT",
... )
>>> @tool
... def say_hello_tool() -> str:
...     '''This tool returns "hello"'''
...     return "hello"
...
>>> agent = Agent(
...     name="Simple Agent",
...     llm=llm,
...     tools=[say_hello_tool]
... )
>>> config = AgentSpecExporter().to_json(agent)
```

To use component disaggregation, specify the component(s) to disaggregate
in the `disaggregated_components` parameter, and ensure that
`export_disaggregated_components` is set to `True`.

```pycon
>>> main_config, disag_config = AgentSpecExporter().to_json(
...     agent,
...     disaggregated_components=[llm],
...     export_disaggregated_components=True
... )
```

Finally, you can specify custom ids for the disaggregated components.

```pycon
>>> main_config, disag_config = AgentSpecExporter().to_json(
...     agent,
...     disaggregated_components=[(llm, "custom_llm_id")],
...     export_disaggregated_components=True
... )
```

#### to_yaml(runtime_component, agentspec_version=None, disaggregated_components=None, export_disaggregated_components=False)

Transform the given WayFlow component into the respective Agent Spec YAML representation.

* **Parameters:**
  * **runtime_component** ([`Component`](component.md#wayflowcore.component.Component)) – WayFlow component to serialize to an Agent Spec configuration.
  * **agentspec_version** (`Optional`[`AgentSpecVersionEnum`]) – The Agent Spec version of the component.
  * **disaggregated_components** (`Optional`[`Sequence`[`Union`[[`Component`](component.md#wayflowcore.component.Component), `Tuple`[[`Component`](component.md#wayflowcore.component.Component), `str`]]]]) – 

    Configuration specifying the components/fields to disaggregate upon serialization.
    Each item can be:
    - A `Component`: to disaggregate the component using its id
    - A tuple `(Component, str)`: to disaggregate the component using
      a custom id.

    #### NOTE
    Components in `disaggregated_components` are disaggregated
    even if `export_disaggregated_components` is `False`.
  * **export_disaggregated_components** (`bool`) – Whether to export the disaggregated components or not. Defaults to `False`.
* **Return type:**
  `Union`[`str`, `Tuple`[`str`, `str`]]
* **Returns:**
  * If `export_disaggregated_components` is `True`
  * *str* – The YAML serialization of the root component.
  * *str* – The YAML serialization of the disaggregated components.
  * If `export_disaggregated_components` is `False`
  * *str* – The YAML serialization of the root component.

### Examples

Basic serialization is done as follows.

```pycon
>>> from wayflowcore.agent import Agent
>>> from wayflowcore.agentspec import AgentSpecExporter
>>> from wayflowcore.models import VllmModel
>>> from wayflowcore.tools import tool
>>>
>>> llm = VllmModel(
...     model_id="model-id",
...     host_port="VLLM_HOST_PORT",
... )
>>> @tool
... def say_hello_tool() -> str:
...     '''This tool returns "hello"'''
...     return "hello"
...
>>> agent = Agent(
...     name="Simple Agent",
...     llm=llm,
...     tools=[say_hello_tool]
... )
>>> config = AgentSpecExporter().to_yaml(agent)
```

To use component disaggregation, specify the component(s) to disaggregate
in the `disaggregated_components` parameter, and ensure that
`export_disaggregated_components` is set to `True`.

```pycon
>>> main_config, disag_config = AgentSpecExporter().to_yaml(
...     agent,
...     disaggregated_components=[llm],
...     export_disaggregated_components=True
... )
```

Finally, you can specify custom ids for the disaggregated components.

```pycon
>>> main_config, disag_config = AgentSpecExporter().to_yaml(
...     agent,
...     disaggregated_components=[(llm, "custom_llm_id")],
...     export_disaggregated_components=True
... )
```

<a id="agentspecloader"></a>

### *class* wayflowcore.agentspec.runtimeloader.AgentSpecLoader(tool_registry=None, plugins=None)

Helper class to convert Agent Spec configurations to WayFlow objects.

* **Parameters:**
  * **tool_registry** (`Optional`[`Dict`[`str`, `Union`[[`ServerTool`](tools.md#wayflowcore.tools.servertools.ServerTool), `Callable`[`...`, `Any`]]]]) – Optional dictionary to enable converting/loading assistant configurations involving the
    use of tools. Keys must be the tool names as specified in the serialized configuration, and
    the values are the ServerTool objects or callables that will be used to create ServerTools.
  * **plugins** (`Optional`[`List`[`Union`[[`WayflowDeserializationPlugin`](serialization.md#wayflowcore.serialization.plugins.WayflowDeserializationPlugin), `ComponentDeserializationPlugin`]]]) – 

    List of additional wayflow plugins to use. By default, uses the latest supported builtin plugins only.
    <!-- note:

    Passing a list of ``ComponentDeserializationPlugin`` from ``pyagentspec`` is deprecated
    since wayflowcore==26.1.0. -->

#### load_component(agentspec_component)

Transform the given PyAgentSpec Component into the respective WayFlow Component

* **Parameters:**
  **agentspec_component** (`Component`) – PyAgentSpec Component to be converted to a WayFlow Component.
* **Return type:**
  [`Component`](component.md#wayflowcore.component.Component)

#### load_json(serialized_assistant, components_registry=None, import_only_referenced_components=False)

Transform the given Agent Spec JSON representation into the respective WayFlow Component

* **Parameters:**
  * **serialized_assistant** (`str`) – Serialized Agent Spec configuration to be converted to a WayFlow Component.
  * **components_registry** (`Optional`[`Mapping`[`str`, `Union`[[`Component`](component.md#wayflowcore.component.Component), `Any`]]]) – A dictionary of loaded WayFlow components and values to use when deserializing the
    main component.
  * **import_only_referenced_components** (`bool`) – When `True`, loads the referenced/disaggregated components
    into a dictionary to be used as the `components_registry`
    when deserializing the main component. Otherwise, loads the
    main component. Defaults to `False`
* **Return type:**
  `Union`[[`Component`](component.md#wayflowcore.component.Component), `Dict`[`str`, [`Component`](component.md#wayflowcore.component.Component)]]
* **Returns:**
  * If `import_only_referenced_components` is `False`
  * *Component* – The deserialized component.
  * If `import_only_referenced_components` is `False`
  * *Dict[str, Component]* – A dictionary containing the loaded referenced components.

### Examples

Basic deserialization is done as follows. First, serialize a component (here an `Agent`).

```pycon
>>> from wayflowcore.agent import Agent
>>> from wayflowcore.agentspec import AgentSpecExporter
>>> from wayflowcore.models import VllmModel
>>> from wayflowcore.tools import tool
>>> llm = VllmModel(
...     model_id="model-id",
...     host_port="VLLM_HOST_PORT",
... )
>>> @tool
... def say_hello_tool() -> str:
...     '''This tool returns "hello"'''
...     return "hello"
...
>>> agent = Agent(
...     name="Simple Agent",
...     llm=llm,
...     tools=[say_hello_tool]
... )
>>> config = AgentSpecExporter().to_json(agent)
```

Then deserialize using the `AgentSpecLoader`.

```pycon
>>> from wayflowcore.agentspec import AgentSpecLoader
>>> TOOL_REGISTRY = {"say_hello_tool": say_hello_tool}
>>> loader = AgentSpecLoader(tool_registry=TOOL_REGISTRY)
>>> deser_agent = loader.load_json(config)
```

When using disaggregated components, the deserialization must be done
in several phases, as follows.

```pycon
>>> main_config, disag_config = AgentSpecExporter().to_json(
...     agent,
...     disaggregated_components=[(llm, "custom_llm_id")],
...     export_disaggregated_components=True
... )
>>> TOOL_REGISTRY = {"say_hello_tool": say_hello_tool}
>>> loader = AgentSpecLoader(tool_registry=TOOL_REGISTRY)
>>> disag_components = loader.load_json(
...     disag_config, import_only_referenced_components=True
... )
>>> deser_agent = loader.load_json(
...     main_config,
...     components_registry=disag_components
... )
```

#### load_yaml(serialized_assistant, components_registry=None, import_only_referenced_components=False)

Transform the given Agent Spec YAML representation into the respective WayFlow Component

* **Parameters:**
  * **serialized_assistant** (`str`) – Serialized Agent Spec configuration to be converted to a WayFlow Component.
  * **components_registry** (`Optional`[`Mapping`[`str`, `Union`[[`Component`](component.md#wayflowcore.component.Component), `Any`]]]) – A dictionary of loaded WayFlow components to use when deserializing the
    main component.
  * **import_only_referenced_components** (`bool`) – When `True`, loads the referenced/disaggregated components
    into a dictionary to be used as the `components_registry`
    when deserializing the main component. Otherwise, loads the
    main component. Defaults to `False`
* **Return type:**
  `Union`[[`Component`](component.md#wayflowcore.component.Component), `Dict`[`str`, [`Component`](component.md#wayflowcore.component.Component)]]
* **Returns:**
  * If `import_only_referenced_components` is `False`
  * *Component* – The deserialized component.
  * If `import_only_referenced_components` is `False`
  * *Dict[str, Component]* – A dictionary containing the loaded referenced components.

### Examples

Basic deserialization is done as follows. First, serialize a component (here an `Agent`).

```pycon
>>> from wayflowcore.agent import Agent
>>> from wayflowcore.agentspec import AgentSpecExporter
>>> from wayflowcore.models import VllmModel
>>> from wayflowcore.tools import tool
>>> llm = VllmModel(
...     model_id="model-id",
...     host_port="VLLM_HOST_PORT",
... )
>>> @tool
... def say_hello_tool() -> str:
...     '''This tool returns "hello"'''
...     return "hello"
...
>>> agent = Agent(
...     name="Simple Agent",
...     llm=llm,
...     tools=[say_hello_tool]
... )
>>> config = AgentSpecExporter().to_yaml(agent)
```

Then deserialize using the `AgentSpecLoader`.

```pycon
>>> from wayflowcore.agentspec import AgentSpecLoader
>>> TOOL_REGISTRY = {"say_hello_tool": say_hello_tool}
>>> loader = AgentSpecLoader(tool_registry=TOOL_REGISTRY)
>>> deser_agent = loader.load_yaml(config)
```

When using disaggregated components, the deserialization must be done
in several phases, as follows.

```pycon
>>> main_config, disag_config = AgentSpecExporter().to_yaml(
...     agent,
...     disaggregated_components=[(llm, "custom_llm_id")],
...     export_disaggregated_components=True
... )
>>> TOOL_REGISTRY = {"say_hello_tool": say_hello_tool}
>>> loader = AgentSpecLoader(tool_registry=TOOL_REGISTRY)
>>> disag_components = loader.load_yaml(
...     disag_config, import_only_referenced_components=True
... )
>>> deser_agent = loader.load_yaml(
...     main_config,
...     components_registry=disag_components
... )
```

# Agent Spec Tracing

This event listener makes WayFlow components emit traces according to the Agent Spec Tracing standard.

<a id="agentspeceventlistener"></a>

### *class* wayflowcore.agentspec.tracing.AgentSpecEventListener

Event listener that emits traces according to the Open Agent Spec Tracing standard

# Custom Components

These are example of custom Agent Spec components that can be used in Agent Spec configurations and
loaded/executed in WayFlow.

#### NOTE
Both extended and plugin components are introduced to allow assistant developers to export
their WayFlow assistants to Agent Spec.

They may be added as native Agent Spec components with modified component name and fields.

## Extended Components

Extended components are Agent Spec components extended with additional fields.

<a id="agentspecagent"></a>

### *class* wayflowcore.agentspec.components.agent.ExtendedAgent(\*\*data)

Agent that can handle a conversation with a user, interact with external tools
and follow interaction flows. Compared to the basic Agent Spec Agent, this
ExtendedAgent supports composition with subflows and subagents, custom
prompt templates, context providers, and some more customizations on the agent’s execution.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **llm_config** (*Annotated* *[**LlmConfig* *,* *SerializeAsAny* *(* *)* *]*)
  * **system_prompt** (*str*)
  * **tools** (*List* *[**Annotated* *[**Tool* *,* *SerializeAsAny* *(* *)* *]* *]*)
  * **toolboxes** (*List* *[**Annotated* *[**ToolBox* *,* *SerializeAsAny* *(* *)* *]* *]*)
  * **human_in_the_loop** (*bool*)
  * **transforms** (*List* *[**MessageTransform* *]*)
  * **context_providers** (*List* *[**Annotated* *[*[*PluginContextProvider*](#wayflowcore.agentspec.components.contextprovider.PluginContextProvider) *,* *SerializeAsAny* *(* *)* *]* *]*  *|* *None*)
  * **can_finish_conversation** (*bool*)
  * **raise_exceptions** (*bool*)
  * **max_iterations** (*int*)
  * **initial_message** (*str* *|* *None*)
  * **caller_input_mode** (*Annotated* *[*[*CallerInputMode*](agent.md#wayflowcore.agent.CallerInputMode) *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *]*)
  * **agents** (*List* *[**Agent* *]*)
  * **flows** (*List* *[**Flow* *]*)
  * **agent_template** (*Annotated* *[*[*PluginPromptTemplate*](#wayflowcore.agentspec.components.template.PluginPromptTemplate) *,* *SerializeAsAny* *(* *)* *]*  *|* *None*)

#### agent_template *: `Optional`[`Annotated`[[`PluginPromptTemplate`](#wayflowcore.agentspec.components.template.PluginPromptTemplate)]]*

Specific agent template for more advanced prompting techniques. It will be overloaded with the current
agent `tools`, and can have placeholders:
\* `custom_instruction` placeholder for the `system_prompt` parameter

#### agents *: `List`[`Agent`]*

Other agents that the agent can call (expert agents).

#### caller_input_mode *: `Annotated`[[`CallerInputMode`](agent.md#wayflowcore.agent.CallerInputMode)]*

Whether the agent is allowed to ask the user questions (CallerInputMode.ALWAYS) or not (CallerInputMode.NEVER).
If set to NEVER, the agent won’t be able to yield.

#### can_finish_conversation *: `bool`*

Whether the agent can decide to end the conversation or not.

#### context_providers *: `Optional`[`List`[`Annotated`[[`PluginContextProvider`](#wayflowcore.agentspec.components.contextprovider.PluginContextProvider)]]]*

Context providers for jinja variables in the `system_prompt`.

#### flows *: `List`[`Flow`]*

#### initial_message *: `Optional`[`str`]*

Initial message the agent will post if no previous user message.
Default to `Agent.NOT_SET_INITIAL_MESSAGE`. If None, the LLM will generate it but the agent requires
a custom_instruction.

#### max_iterations *: `int`*

Maximum number of calls to the agent executor before yielding back to the user.

#### raise_exceptions *: `bool`*

Whether exceptions from sub-executions (tool, sub-agent, or sub-flow execution) are raised or not.

<a id="agentspecflow"></a>

### *class* wayflowcore.agentspec.components.flow.ExtendedFlow(\*\*data)

Extension of the basic Agent Spec Flow that supports context providers

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **start_node** (*Annotated* *[**Node* *,* *SerializeAsAny* *(* *)* *]*)
  * **nodes** (*List* *[**Annotated* *[**Node* *,* *SerializeAsAny* *(* *)* *]* *]*)
  * **control_flow_connections** (*List* *[**ControlFlowEdge* *]*)
  * **data_flow_connections** (*List* *[**DataFlowEdge* *]*  *|* *None*)
  * **context_providers** (*List* *[**Annotated* *[*[*PluginContextProvider*](#wayflowcore.agentspec.components.contextprovider.PluginContextProvider) *,* *SerializeAsAny* *(* *)* *]* *]*  *|* *None*)
  * **state** (*List* *[**Property* *]*)

#### context_providers *: `Optional`[`List`[`Annotated`[[`PluginContextProvider`](#wayflowcore.agentspec.components.contextprovider.PluginContextProvider)]]]*

List of providers that add context to specific steps.

#### state *: `List`[`Property`]*

The list of properties that compose the state of the Flow

<a id="agentspectoolnode"></a>

### *class* wayflowcore.agentspec.components.nodes.ExtendedToolNode(\*\*data)

Extension of the Agent Spec ToolNode. Supports silencing exceptions raised by tools.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **branches** (*List* *[**str* *]*)
  * **tool** (*Annotated* *[**Tool* *,* *SerializeAsAny* *(* *)* *]*)
  * **input_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **output_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **raise_exceptions** (*bool*)

#### raise_exceptions *: `bool`*

Whether to raise or not exceptions raised by the tool. If `False`, it will put the error message
as the result of the tool if the tool output type is string.

<a id="agentspecllmnode"></a>

### *class* wayflowcore.agentspec.components.nodes.ExtendedLlmNode(\*\*data)

Extended version of the Agent Spec LlmNode. Supports prompt templates and streaming.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **branches** (*List* *[**str* *]*)
  * **llm_config** (*Annotated* *[**LlmConfig* *,* *SerializeAsAny* *(* *)* *]*)
  * **prompt_template** (*str*)
  * **input_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **output_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **prompt_template_object** ([*PluginPromptTemplate*](#wayflowcore.agentspec.components.template.PluginPromptTemplate) *|* *None*)
  * **send_message** (*bool*)

#### OUTPUT *: `ClassVar`[`str`]* *= 'output'*

Output key for the output generated by the LLM, matching the Reference Runtime default value.

#### *classmethod* check_either_prompt_str_or_object_is_used(data, handler)

Wrap validation_func and accumulate errors.

* **Return type:**
  `TypeVar`(`BaseModelSelf`, bound= BaseModel)
* **Parameters:**
  * **data** (*Dict* *[**str* *,* *Any* *]*)
  * **handler** (*Any*)

#### prompt_template_object *: `Optional`[[`PluginPromptTemplate`](#wayflowcore.agentspec.components.template.PluginPromptTemplate)]*

Prompt template object. Either use prompt_template or prompt_template_object.

#### send_message *: `bool`*

Determines whether to send the generated content to the current message list or not.
By default, the content is only exposed as an output.

<a id="agentspecmapnode"></a>

### *class* wayflowcore.agentspec.components.nodes.ExtendedMapNode(\*\*data)

Extension of the Agent Spec MapNode. Supports parallel execution and input extraction.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **branches** (*List* *[**str* *]*)
  * **input_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **output_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **flow** (*Flow*)
  * **unpack_input** (*Dict* *[**str* *,* *str* *]*)
  * **parallel_execution** (*bool*)
  * **max_workers** (*int* *|* *None*)

#### ITERATED_INPUT *: `ClassVar`[`str`]* *= 'iterated_input'*

Input key for the iterable to use the `MapStep` on.

#### flow *: `Flow`*

Flow that is being executed with each iteration of the input.

#### max_workers *: `Optional`[`int`]*

The number of workers to use in case of parallel execution.

#### parallel_execution *: `bool`*

Executes the mapping operation in parallel. Cannot be set to true if the internal flow can yield.
This feature is in beta, be aware that flows might have side effects on one another.
Each thread will use a different IO dict, but they will all share the same message list.

#### unpack_input *: `Dict`[`str`, `str`]*

Mapping to specify how to unpack when each iter item is a `dict`
and we need to map its element to the inside flow inputs.

## Plugin Components

Plugin components are new components that are not natively supported in Agent Spec.

### Agentic patterns

<a id="agentspecswarmpattern"></a>

### *class* wayflowcore.agentspec.components.swarm.PluginSwarm(\*\*data)

#### Deprecated
Deprecated since version 26.1: PluginSwarm is deprecated, use Agent Spec Swarm instead.

Defines a `Swarm` conversational component.

A `Swarm` is a multi-agent conversational component in which each agent determines
the next agent to be executed, based on a list of pre-defined relationships.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **first_agent** (*Annotated* *[**Agent* *,* *SerializeAsAny* *(* *)* *]*)
  * **relationships** (*List* *[**List* *[**Annotated* *[**Agent* *,* *SerializeAsAny* *(* *)* *]* *]* *]*)
  * **handoff** (*bool*)

#### first_agent *: `Annotated`[`Agent`]*

What is the first `Agent` to interact with the human user.

#### handoff *: `bool`*

* When `False`, agent can only talk to each other, the `first_agent` is fixed for the entire conversation;
* When `True`, agents can handoff the conversation to each other, i.e. transferring the list of messages between
  an agent and the user to another agent in the Swarm. They can also talk to each other as when `handoff=False`

#### relationships *: `List`[`List`[`Annotated`[`Agent`]]]*

Determine the list of allowed interactions in the `Swarm`.
Each element in the list is a tuple `(caller_agent, recipient_agent)`
specifying that the `caller_agent` can query the `recipient_agent`.

### Messages

<a id="agentspecmessage"></a>

### *class* wayflowcore.agentspec.components.messagelist.PluginMessage(\*\*data)

Messages are an exchange medium between the user, LLM agent, and controller logic.
This helps determining who provided what information.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **role** (*Literal* *[* *'user'* *,*  *'assistant'* *,*  *'system'* *]*)
  * **contents** (*List* *[**Annotated* *[*[*PluginTextContent*](#wayflowcore.agentspec.components.messagelist.PluginTextContent) *|* [*PluginImageContent*](#wayflowcore.agentspec.components.messagelist.PluginImageContent) *,* *FieldInfo* *(**annotation=NoneType* *,* *required=True* *,* *discriminator='type'* *)* *]* *]*)
  * **tool_requests** (*List* *[*[*PluginToolRequest*](#wayflowcore.agentspec.components.tools.PluginToolRequest) *]*  *|* *None*)
  * **tool_result** ([*PluginToolResult*](#wayflowcore.agentspec.components.tools.PluginToolResult) *|* *None*)
  * **display_only** (*bool*)
  * **sender** (*str* *|* *None*)
  * **recipients** (*List* *[**str* *]*)
  * **time_created** (*datetime*)
  * **time_updated** (*datetime*)

#### contents *: `List`[`Annotated`[`Union`[[`PluginTextContent`](#wayflowcore.agentspec.components.messagelist.PluginTextContent), [`PluginImageContent`](#wayflowcore.agentspec.components.messagelist.PluginImageContent)]]]*

Message content. Is a list of chunks with potentially different types

#### *classmethod* deserialize_time_created(v)

* **Return type:**
  `Any`
* **Parameters:**
  **v** (*Any*)

#### *classmethod* deserialize_time_updated(v)

* **Return type:**
  `Any`
* **Parameters:**
  **v** (*Any*)

#### display_only *: `bool`*

If True, the message is excluded from any context. Its only purpose is to be displayed
in the chat UI (e.g debugging message)

#### recipients *: `List`[`str`]*

Recipients of the message in str format.

#### role *: `Literal`[`'user'`, `'assistant'`, `'system'`]*

Role of the sender of the message. Can be user, system or assistant

#### sender *: `Optional`[`str`]*

Sender of the message in str format.

#### serialize_time_created(value)

* **Return type:**
  `Any`
* **Parameters:**
  **value** (*Any*)

#### serialize_time_updated(value)

* **Return type:**
  `Any`
* **Parameters:**
  **value** (*Any*)

#### time_created *: `datetime`*

Creation timestamp of the message.

#### time_updated *: `datetime`*

Update timestamp of the message.

#### tool_requests *: `Optional`[`List`[[`PluginToolRequest`](#wayflowcore.agentspec.components.tools.PluginToolRequest)]]*

A list of `ToolRequest` objects representing the tools invoked as part
of this message. Each request includes the tool’s name, arguments,
and a unique identifier.

#### tool_result *: `Optional`[[`PluginToolResult`](#wayflowcore.agentspec.components.tools.PluginToolResult)]*

A `ToolResult` object representing the outcome of a tool invocation.
It includes the returned content and a reference to the related tool request ID.

<a id="agentspectextcontent"></a>

### *class* wayflowcore.agentspec.components.messagelist.PluginTextContent(\*\*data)

Represents the content of a text message.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **type** (*Literal* *[* *'text'* *]*)
  * **content** (*str*)

#### content *: `str`*

The textual content of the message.

#### type *: `Literal`[`'text'`]*

#### validate_text_content_type()

* **Return type:**
  `Self`

<a id="agentspecimagecontent"></a>

### *class* wayflowcore.agentspec.components.messagelist.PluginImageContent(\*\*data)

Represents the content of an image message, storing image data as a base64-encoded string.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **type** (*Literal* *[* *'image'* *]*)
  * **base64_content** (*str*)

#### base64_content *: `str`*

A base64-encoded string representing the image data.

#### type *: `Literal`[`'image'`]*

<a id="agentspecregexpattern"></a>

### *class* wayflowcore.agentspec.components.outputparser.PluginRegexPattern(\*\*data)

Represents a regex pattern and matching options for output parsing.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **pattern** (*str*)
  * **match** (*Literal* *[* *'first'* *,*  *'last'* *]*)
  * **flags** (*RegexFlag* *|* *int* *|* *None*)

#### flags *: `Union`[`RegexFlag`, `int`, `None`]*

Potential regex flags to use (re.DOTALL for multiline matching for example)

#### *static* from_str(pattern)

* **Return type:**
  [`PluginRegexPattern`](#wayflowcore.agentspec.components.outputparser.PluginRegexPattern)
* **Parameters:**
  **pattern** (*str* *|* [*PluginRegexPattern*](#wayflowcore.agentspec.components.outputparser.PluginRegexPattern))

#### match *: `Literal`[`'first'`, `'last'`]*

Whether to take the first match or the last match

#### pattern *: `str`*

Regex pattern to match

<a id="agentspecoutputparser"></a>

### *class* wayflowcore.agentspec.components.outputparser.PluginOutputParser(\*\*data)

Abstract base class for output parsers that process LLM outputs.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)

#### model_config *: ClassVar[ConfigDict]* *= {'extra': 'forbid'}*

Configuration for the model, should be a dictionary conforming to [ConfigDict][pydantic.config.ConfigDict].

#### model_post_init(\_Component_\_context)

Override of the method used by Pydantic as post-init.

* **Return type:**
  `None`
* **Parameters:**
  **\_Component_\_context** (*Any*)

<a id="agentspecregexoutputparser"></a>

### *class* wayflowcore.agentspec.components.outputparser.PluginRegexOutputParser(\*\*data)

Parses some text with Regex, potentially several regex to fill a dict

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **regex_pattern** (*Dict* *[**str* *,* *str* *|* [*PluginRegexPattern*](#wayflowcore.agentspec.components.outputparser.PluginRegexPattern) *]*  *|* [*PluginRegexPattern*](#wayflowcore.agentspec.components.outputparser.PluginRegexPattern) *|* *str*)
  * **strict** (*bool*)

#### regex_pattern *: `Union`[`Dict`[`str`, `Union`[`str`, [`PluginRegexPattern`](#wayflowcore.agentspec.components.outputparser.PluginRegexPattern)]], [`PluginRegexPattern`](#wayflowcore.agentspec.components.outputparser.PluginRegexPattern), `str`]*

Regex pattern to use

#### strict *: `bool`*

Whether to return empty string if no match is found or return the raw text

<a id="agentspecjsonoutputparser"></a>

### *class* wayflowcore.agentspec.components.outputparser.PluginJsonOutputParser(\*\*data)

Parses output as JSON, repairing and serializing as needed.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **properties** (*Dict* *[**str* *,* *str* *]*  *|* *None*)

#### properties *: `Optional`[`Dict`[`str`, `str`]]*

Dictionary of property names and jq queries to manipulate the loaded JSON

<a id="agentspectooloutputparser"></a>

### *class* wayflowcore.agentspec.components.outputparser.PluginToolOutputParser(\*\*data)

Base parser for tool requests

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **tools** (*List* *[**Annotated* *[**Tool* *,* *SerializeAsAny* *(* *)* *]* *]*  *|* *None*)

#### tools *: `Optional`[`List`[`Annotated`[`Tool`]]]*

<a id="agentspecjsontooloutputparser"></a>

### *class* wayflowcore.agentspec.components.outputparser.PluginJsonToolOutputParser(\*\*data)

Parses tool requests from JSON-formatted strings.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **tools** (*List* *[**Annotated* *[**Tool* *,* *SerializeAsAny* *(* *)* *]* *]*  *|* *None*)

<a id="agentspecpythontooloutputparser"></a>

### *class* wayflowcore.agentspec.components.outputparser.PluginPythonToolOutputParser(\*\*data)

Parses tool requests from Python function call syntax.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **tools** (*List* *[**Annotated* *[**Tool* *,* *SerializeAsAny* *(* *)* *]* *]*  *|* *None*)

<a id="agentspecreacttooloutputparser"></a>

### *class* wayflowcore.agentspec.components.outputparser.PluginReactToolOutputParser(\*\*data)

Parses ReAct-style tool requests.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **tools** (*List* *[**Annotated* *[**Tool* *,* *SerializeAsAny* *(* *)* *]* *]*  *|* *None*)

<a id="agentspecprompttemplate"></a>

### *class* wayflowcore.agentspec.components.template.PluginPromptTemplate(\*\*data)

Represents a flexible and extensible template for constructing prompts to be sent to large language models (LLMs).

The PromptTemplate class enables the definition of prompt messages with variable placeholders, supports both
native and custom tool calling, and allows for structured output generation.
It manages input descriptors, message transforms (pre- and post chat_history rendering), and partial formatting
for efficiency.
The class also integrates with output parsers, tools and llm generation configurations.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **messages** (*List* *[*[*PluginMessage*](#wayflowcore.agentspec.components.messagelist.PluginMessage) *]*)
  * **output_parser** (*List* *[**Annotated* *[*[*PluginOutputParser*](#wayflowcore.agentspec.components.outputparser.PluginOutputParser) *,* *SerializeAsAny* *(* *)* *]* *]*  *|* *Annotated* *[*[*PluginOutputParser*](#wayflowcore.agentspec.components.outputparser.PluginOutputParser) *,* *SerializeAsAny* *(* *)* *]*  *|* *None*)
  * **inputs** (*List* *[**Annotated* *[**Property* *,* *SerializeAsAny* *(* *)* *]* *]*  *|* *None*)
  * **pre_rendering_transforms** (*List* *[**Annotated* *[*[*PluginMessageTransform*](#wayflowcore.agentspec.components.transforms.PluginMessageTransform) *,* *SerializeAsAny* *(* *)* *]* *]*  *|* *None*)
  * **post_rendering_transforms** (*List* *[**Annotated* *[*[*PluginMessageTransform*](#wayflowcore.agentspec.components.transforms.PluginMessageTransform) *,* *SerializeAsAny* *(* *)* *]* *]*  *|* *None*)
  * **tools** (*List* *[**Annotated* *[**Tool* *,* *SerializeAsAny* *(* *)* *]* *]*  *|* *None*)
  * **native_tool_calling** (*bool*)
  * **response_format** (*Annotated* *[**Property* *,* *SerializeAsAny* *(* *)* *]*  *|* *None*)
  * **native_structured_generation** (*bool*)
  * **generation_config** (*LlmGenerationConfig* *|* *None*)

#### CHAT_HISTORY_PLACEHOLDER *: `ClassVar`[[`PluginMessage`](#wayflowcore.agentspec.components.messagelist.PluginMessage)]* *= PluginMessage(role='user', contents=[], tool_requests=None, tool_result=None, display_only=False, sender=None, recipients=[])*

Message placeholder in case the chat history is formatted as a chat.

#### CHAT_HISTORY_PLACEHOLDER_NAME *: `ClassVar`[`str`]* *= '_\_CHAT_HISTORY_\_'*

Reserved name of the placeholder for the chat history, if rendered in one message.

#### RESPONSE_FORMAT_PLACEHOLDER_NAME *: `ClassVar`[`str`]* *= '_\_RESPONSE_FORMAT_\_'*

Reserved name of the placeholder for the expected output format. Only used if non-native structured
generation, to be able to specify the JSON format anywhere in the prompt.

#### TOOL_PLACEHOLDER_NAME *: `ClassVar`[`str`]* *= '_\_TOOLS_\_'*

Reserved name of the placeholder for tools.

#### generation_config *: `Optional`[`LlmGenerationConfig`]*

Parameters to configure the generation.

#### inputs *: `Optional`[`List`[`Annotated`[`Property`]]]*

Input descriptors that will be picked up by PromptExecutionStep or AgentExecutionStep.
Resolved by default from the variables present in the messages.

#### messages *: `List`[[`PluginMessage`](#wayflowcore.agentspec.components.messagelist.PluginMessage)]*

List of messages for the prompt.

#### native_structured_generation *: `bool`*

Whether to use native structured generation or not. All llm providers might not support it.

#### native_tool_calling *: `bool`*

Whether to use the native tool calling of the model or not. All llm providers might not support it.

#### output_parser *: `Union`[`List`[`Annotated`[[`PluginOutputParser`](#wayflowcore.agentspec.components.outputparser.PluginOutputParser)]], `Annotated`[[`PluginOutputParser`](#wayflowcore.agentspec.components.outputparser.PluginOutputParser)], `None`]*

Post-processing applied on the raw output of the LLM.

#### post_rendering_transforms *: `Optional`[`List`[`Annotated`[[`PluginMessageTransform`](#wayflowcore.agentspec.components.transforms.PluginMessageTransform)]]]*

Message transform applied on the rendered list of messages.

#### pre_rendering_transforms *: `Optional`[`List`[`Annotated`[[`PluginMessageTransform`](#wayflowcore.agentspec.components.transforms.PluginMessageTransform)]]]*

Message transform applied before rendering the list of messages into the template.

#### response_format *: `Optional`[`Annotated`[`Property`]]*

Specific format the llm answer should follow.

#### tools *: `Optional`[`List`[`Annotated`[`Tool`]]]*

Tools to use in the prompt.

<a id="agentspecmessagetransform"></a>

### *class* wayflowcore.agentspec.components.transforms.PluginMessageTransform(\*\*data)

Abstract base class for message transforms.

Subclasses should implement the \_\_call_\_ method to transform a list of Message objects
and return a new list of Message objects, typically for preprocessing or postprocessing
message flows in the system.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)

<a id="agentspeccoalescesystemmessagestransform"></a>

### *class* wayflowcore.agentspec.components.transforms.PluginCoalesceSystemMessagesTransform(\*\*data)

Transform that merges consecutive system messages at the start of a message list
into a single system message. This is useful for reducing redundancy and ensuring
that only one system message appears at the beginning of the conversation.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)

<a id="agentspecremoveemptynonusermessagetransform"></a>

### *class* wayflowcore.agentspec.components.transforms.PluginRemoveEmptyNonUserMessageTransform(\*\*data)

Transform that removes messages which are empty and not from the user.

Any message with empty content and no tool requests, except for user messages,
will be filtered out from the message list.

This is useful in case the template contains optional messages, which will be discarded if their
content is empty (with a string template such as “{% if \_\_PLAN_\_ %}{{ \_\_PLAN_\_ }}{% endif %}”).

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)

<a id="agentspecappendtrailingsystemmessagetousermessagetransform"></a>

### *class* wayflowcore.agentspec.components.transforms.PluginAppendTrailingSystemMessageToUserMessageTransform(\*\*data)

Transform that appends the content of a trailing system message to the previous user message.

If the last message in the list is a system message and the one before it is a user message,
this transform merges the system message content into the user message, reducing message clutter.

This is useful if the underlying LLM does not support system messages at the end.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)

<a id="agentspecllamamergetoolrequestsandcallstransform"></a>

### *class* wayflowcore.agentspec.components.transforms.PluginLlamaMergeToolRequestAndCallsTransform(\*\*data)

Llama-specific message transform

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)

<a id="agentspecreactmergetoolrequestsandcallstransform"></a>

### *class* wayflowcore.agentspec.components.transforms.PluginReactMergeToolRequestAndCallsTransform(\*\*data)

Simple message processor that joins tool requests and calls into a python-like message

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)

<a id="agentspeccanonicalizationmessagetransform"></a>

### *class* wayflowcore.agentspec.components.transforms.PluginCanonicalizationMessageTransform(\*\*data)

Produce a conversation shaped like:

> System   (optional, at most one, always first if present)
> User
> Assistant
> User
> Assistant
> …

This is useful because some models (like Gemma) require such formatting of the messages.

* several system messages are merged
* consecutive assistant (resp. user) messages are merged, unless there are several tool calls,
  in which case they are split and their responses are interleaving the requests.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)

<a id="agentspecsplitpromptonmarkermessagetransform"></a>

### *class* wayflowcore.agentspec.components.transforms.PluginSplitPromptOnMarkerMessageTransform(\*\*data)

Split prompts on a marker into multiple messages with the same role. Only apply to the messages without
tool_requests and tool_result.

This transform is useful for script-based execution flows, where a single prompt script can be converted
into multiple conversation turns for step-by-step reasoning.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **marker** (*str* *|* *None*)

#### marker *: `Optional`[`str`]*

### Nodes

<a id="agentspeccatchexceptionnode"></a>

### *class* wayflowcore.agentspec.components.nodes.PluginCatchExceptionNode(\*\*data)

Executes a `Flow` inside a step and catches specific potential exceptions.
If no exception is caught, it will transition to the branches of its subflow.
If an exception is caught, it will transition to some specific exception branch has configured in this step.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **branches** (*List* *[**str* *]*)
  * **input_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **output_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **flow** (*Annotated* *[**Flow* *,* *SerializeAsAny* *(* *)* *]*)
  * **except_on** (*Dict* *[**str* *,* *str* *]*  *|* *None*)
  * **catch_all_exceptions** (*bool*)

#### DEFAULT_EXCEPTION_BRANCH *: `ClassVar`[`str`]* *= 'default_exception_branch'*

Name of the branch where the step will transition if `catch_all_exceptions` is `True`
and an exception was caught.

#### EXCEPTION_NAME_OUTPUT_NAME *: `ClassVar`[`str`]* *= 'exception_name'*

Variable containing the name of the caught exception.

#### EXCEPTION_PAYLOAD_OUTPUT_NAME *: `ClassVar`[`str`]* *= 'exception_payload_name'*

Variable containing the exception payload. Does not contain any higher-level stacktrace
information than the wayflowcore stacktraces.

#### catch_all_exceptions *: `bool`*

Whether to catch any exception and redirect to the default exception branch.

#### except_on *: `Optional`[`Dict`[`str`, `str`]]*

Names of exceptions to catch and their associated branches.

#### flow *: `Annotated`[`Flow`]*

The flow to run and catch exceptions from.

<a id="agentspecextractnode"></a>

### *class* wayflowcore.agentspec.components.nodes.PluginExtractNode(\*\*data)

Node to extract information from a raw json text.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **branches** (*List* *[**str* *]*)
  * **input_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **output_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **output_values** (*Dict* *[**str* *,* *str* *]*)
  * **llm_config** (*Annotated* *[**LlmConfig* *,* *SerializeAsAny* *(* *)* *]*  *|* *None*)
  * **retry** (*bool*)

#### TEXT *: `ClassVar`[`str`]* *= 'text'*

Input key for the raw json text to be parsed.

#### llm_config *: `Optional`[`Annotated`[`LlmConfig`]]*

LLM to use to rephrase the message. Only required if `retry=True`.

#### output_values *: `Dict`[`str`, `str`]*

The keys are output names of this step. The values are the jq formulas
to extract them from the json detected

#### retry *: `bool`*

Whether to reprompt a LLM to fix the error or not

<a id="agentspecinputmessagenode"></a>

### *class* wayflowcore.agentspec.components.nodes.PluginInputMessageNode(\*\*data)

Node to get an input from the conversation with the user.

The input step prints a message to the user, asks for an answer and returns it as
an output of the step. It places both messages in the messages list so that it is
possible to visualize the conversation, but also returns the user input as an output.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **branches** (*List* *[**str* *]*)
  * **message** (*str* *|* *None*)
  * **input_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **output_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **message_template** (*str* *|* *None*)
  * **rephrase** (*bool*)
  * **llm_config** (*Annotated* *[**LlmConfig* *,* *SerializeAsAny* *(* *)* *]*  *|* *None*)

#### USER_PROVIDED_INPUT *: `ClassVar`[`str`]* *= 'user_provided_input'*

Output key for the input text provided by the user.

#### llm_config *: `Optional`[`Annotated`[`LlmConfig`]]*

LLM to use to rephrase the message. Only required if `rephrase=True`.

#### message_template *: `Optional`[`str`]*

The message template to use to ask for more information to the user, in jinja format.

#### rephrase *: `bool`*

Whether to rephrase the message. Requires `llm` to be set.

<a id="agentspecoutputmessagenode"></a>

### *class* wayflowcore.agentspec.components.nodes.PluginOutputMessageNode(\*\*data)

Node to output a message to the chat history.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **branches** (*List* *[**str* *]*)
  * **message_template** (*str*)
  * **input_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **output_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **message_type** (*Annotated* *[*[*MessageType*](conversation.md#wayflowcore.messagelist.MessageType) *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *]*)
  * **rephrase** (*bool*)
  * **llm_config** (*Annotated* *[**LlmConfig* *,* *SerializeAsAny* *(* *)* *]*  *|* *None*)
  * **expose_message_as_output** (*bool*)

#### OUTPUT *: `ClassVar`[`str`]* *= 'output_message'*

Output key for the output message generated by the `PluginOutputMessageNode`.

#### expose_message_as_output *: `bool`*

Whether the message generated by this step should appear among the output descriptors

#### llm_config *: `Optional`[`Annotated`[`LlmConfig`]]*

LLM to use to rephrase the message. Only required if `rephrase=True`.

#### message *: `str`*

Content of the agent message to append. Allows placeholders, which can define inputs.

#### message_type *: `Annotated`[[`MessageType`](conversation.md#wayflowcore.messagelist.MessageType)]*

Message type of the message added to the message history.

#### rephrase *: `bool`*

Whether to rephrase the message. Requires `llm` to be set.

<a id="agentspecdatastorecreatenode"></a>

### *class* wayflowcore.agentspec.components.datastores.nodes.PluginDatastoreCreateNode(\*\*data)

Node that can create a new entity in a `PluginDatastore`.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **branches** (*List* *[**str* *]*)
  * **input_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **output_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **datastore** ([*PluginDatastore*](#wayflowcore.agentspec.components.datastores.datastore.PluginDatastore))
  * **collection_name** (*str*)
  * **ENTITY** (*str*)
  * **CREATED_ENTITY** (*str*)

#### CREATED_ENTITY *: `str`*

Output key for the newly created entity.

* **Type:**
  str

#### ENTITY *: `str`*

Input key for the entity to be created.

* **Type:**
  str

#### collection_name *: `str`*

Collection in the datastore manipulated by this step.
Can be parametrized using jinja variables, and the resulting input
descriptors will be inferred by the step.

#### datastore *: [`PluginDatastore`](#wayflowcore.agentspec.components.datastores.datastore.PluginDatastore)*

PluginDatastore this step operates on

<a id="agentspecdatastoredeletenode"></a>

### *class* wayflowcore.agentspec.components.datastores.nodes.PluginDatastoreDeleteNode(\*\*data)

Step that can delete entities in a `PluginDatastore`.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **branches** (*List* *[**str* *]*)
  * **input_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **output_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **datastore** ([*PluginDatastore*](#wayflowcore.agentspec.components.datastores.datastore.PluginDatastore))
  * **collection_name** (*str*)
  * **where** (*Dict* *[**str* *,* *Any* *]*)

#### collection_name *: `str`*

Collection in the datastore manipulated by this node.
Can be parametrized using jinja variables, and the resulting input
descriptors will be inferred by the node.

#### datastore *: [`PluginDatastore`](#wayflowcore.agentspec.components.datastores.datastore.PluginDatastore)*

PluginDatastore this node operates on

#### where *: `Dict`[`str`, `Any`]*

Filtering to be applied when deleting entities. The dictionary is composed of
property name and value pairs to filter by with exact matches.
Only entities matching all conditions in the dictionary will be deleted.
For example, {“name”: “Fido”, “breed”: “Golden Retriever”} will match
all `Golden Retriever` dogs named `Fido`.

<a id="agentspecdatastorelistnode"></a>

### *class* wayflowcore.agentspec.components.datastores.nodes.PluginDatastoreListNode(\*\*data)

Step that can list entities in a `PluginDatastore`.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **branches** (*List* *[**str* *]*)
  * **input_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **output_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **datastore** ([*PluginDatastore*](#wayflowcore.agentspec.components.datastores.datastore.PluginDatastore))
  * **collection_name** (*str*)
  * **where** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **limit** (*int* *|* *None*)
  * **unpack_single_entity_from_list** (*bool* *|* *None*)
  * **ENTITIES** (*str*)

#### ENTITIES *: `str`*

Output key for the entities listed by this step.

* **Type:**
  str

#### collection_name *: `str`*

Collection in the datastore manipulated by this step.
Can be parametrized using jinja variables, and the resulting input
descriptors will be inferred by the step.

#### datastore *: [`PluginDatastore`](#wayflowcore.agentspec.components.datastores.datastore.PluginDatastore)*

PluginDatastore this step operates on

#### limit *: `Optional`[`int`]*

Maximum number of entities to list. By default retrieves all entities.

#### unpack_single_entity_from_list *: `Optional`[`bool`]*

When limit is set to 1, one may optionally decide to unpack the single entity
in the list and only return a the dictionary representing the retrieved entity.
This can be useful when, e.g., reading a single entity by its ID.

#### where *: `Optional`[`Dict`[`str`, `Any`]]*

Filtering to be applied when retrieving entities. The dictionary is composed of
property name and value pairs to filter by with exact matches.
Only entities matching all conditions in the dictionary will be retrieved.
For example, {“name”: “Fido”, “breed”: “Golden Retriever”} will match
all `Golden Retriever` dogs named `Fido`.

<a id="agentspecdatastorequerynode"></a>

### *class* wayflowcore.agentspec.components.datastores.nodes.PluginDatastoreQueryNode(\*\*data)

Step to execute a parameterized SQL query on a relational `PluginDatastore`
(`PluginOracleDatabaseDatastore`), that supports SQL queries (the specific
SQL dialect depends on the database backing the datastore).

This step enables safe, flexible querying of datastores using
parameterized SQL.  Queries must use bind variables (e.g., :customer_id).
String templating within queries is forbidden for security reasons;
any such usage raises an error.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **branches** (*List* *[**str* *]*)
  * **input_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **output_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **datastore** ([*PluginRelationalDatastore*](#wayflowcore.agentspec.components.datastores.relational_datastore.PluginRelationalDatastore))
  * **query** (*str*)
  * **RESULT** (*str*)

#### RESULT *: `str`*

Output key for the query result (list of dictionaries, one per row).

* **Type:**
  str

#### datastore *: [`PluginRelationalDatastore`](#wayflowcore.agentspec.components.datastores.relational_datastore.PluginRelationalDatastore)*

The `PluginDatastore` to execute the query against

#### query *: `str`*

SQL query string using bind variables (e.g., `SELECT * FROM table WHERE id = :val`).
String templating/interpolation is forbidden and will raise an exception.

<a id="agentspecdatastoreupdatenode"></a>

### *class* wayflowcore.agentspec.components.datastores.nodes.PluginDatastoreUpdateNode(\*\*data)

Step that can update entities in a `PluginDatastore`.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **branches** (*List* *[**str* *]*)
  * **input_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **output_mapping** (*Dict* *[**str* *,* *str* *]*)
  * **datastore** ([*PluginDatastore*](#wayflowcore.agentspec.components.datastores.datastore.PluginDatastore))
  * **collection_name** (*str*)
  * **where** (*Dict* *[**str* *,* *Any* *]*)
  * **ENTITIES** (*str*)
  * **UPDATE** (*str*)

#### ENTITIES *: `str`*

Output key for the entities listed by this step.

* **Type:**
  str

#### UPDATE *: `str`*

Input key for the dictionary of the updates to be made.

* **Type:**
  str

#### collection_name *: `str`*

Collection in the datastore manipulated by this step.
Can be parametrized using jinja variables, and the resulting input
descriptors will be inferred by the step.

#### datastore *: [`PluginDatastore`](#wayflowcore.agentspec.components.datastores.datastore.PluginDatastore)*

PluginDatastore this step operates on

#### where *: `Dict`[`str`, `Any`]*

Filtering to be applied when updating entities. The dictionary is composed of
property name and value pairs to filter by with exact matches.
Only entities matching all conditions in the dictionary will be updated.
For example, {“name”: “Fido”, “breed”: “Golden Retriever”} will match
all `Golden Retriever` dogs with name `Fido`.

### Context Providers

<a id="agentspeccontextprovider"></a>

### *class* wayflowcore.agentspec.components.contextprovider.PluginContextProvider(\*\*data)

Context providers are callable components that are used to provide dynamic contextual information to
WayFlow assistants. They are useful to connect external datasources to an assistant.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **inputs** (*List* *[**Property* *]*  *|* *None*)
  * **outputs** (*List* *[**Property* *]*  *|* *None*)
  * **branches** (*List* *[**str* *]*)

### Datastores

<a id="agentspecdatastore"></a>

### *class* wayflowcore.agentspec.components.datastores.datastore.PluginDatastore(\*\*data)

Store and perform basic manipulations on collections of entities of various types.

Provides an interface for listing, creating, deleting and updating collections.
It also provides a way of describing the entities in this datastore.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)

<a id="agentspecentity"></a>

### wayflowcore.agentspec.components.datastores.entity.PluginEntity

alias of `Property`

<a id="agentspecinmemorydatastore"></a>

### *class* wayflowcore.agentspec.components.datastores.inmemory_datastore.PluginInMemoryDatastore(\*\*data)

In-memory datastore for testing and development purposes.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **datastore_schema** (*Dict* *[**str* *,* *Property* *]*)

#### datastore_schema *: `Dict`[`str`, `Property`]*

Mapping of collection names to entity definitions used by this datastore.

<a id="agentspecmtlsoracledatabaseconnectionconfig"></a>

### *class* wayflowcore.agentspec.components.datastores.oracle_datastore.PluginMTlsOracleDatabaseConnectionConfig(\*\*data)

Mutual-TLS Connection Configuration to Oracle Database.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **config_dir** (*Annotated* *[**str* *,*  *'SENSITIVE_FIELD_MARKER'* *]*)
  * **dsn** (*Annotated* *[**str* *,*  *'SENSITIVE_FIELD_MARKER'* *]*)
  * **user** (*Annotated* *[**str* *,*  *'SENSITIVE_FIELD_MARKER'* *]*)
  * **password** (*Annotated* *[**str* *,*  *'SENSITIVE_FIELD_MARKER'* *]*)
  * **wallet_location** (*Annotated* *[**str* *,*  *'SENSITIVE_FIELD_MARKER'* *]*)
  * **wallet_password** (*Annotated* *[**str* *,*  *'SENSITIVE_FIELD_MARKER'* *]*)

#### config_dir *: `Annotated`[`str`]*

TNS Admin directory

#### dsn *: `Annotated`[`str`]*

Connection string for the database, or entry in the tnsnames.ora file

#### password *: `Annotated`[`str`]*

Password for the provided user

#### user *: `Annotated`[`str`]*

Connection string for the database

#### wallet_location *: `Annotated`[`str`]*

Location where the Oracle Database wallet is stored.

#### wallet_password *: `Annotated`[`str`]*

Password for the provided wallet.

<a id="agentspecoracledatabaseconnectionconfig"></a>

### *class* wayflowcore.agentspec.components.datastores.oracle_datastore.PluginOracleDatabaseConnectionConfig(\*\*data)

Base class used for configuring connections to Oracle Database.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)

<a id="agentspecoracledatabasedatastore"></a>

### *class* wayflowcore.agentspec.components.datastores.oracle_datastore.PluginOracleDatabaseDatastore(\*\*data)

Datastore that uses Oracle Database as the storage mechanism.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **datastore_schema** (*Dict* *[**str* *,* *Property* *]*)
  * **connection_config** (*Annotated* *[*[*PluginOracleDatabaseConnectionConfig*](#wayflowcore.agentspec.components.datastores.oracle_datastore.PluginOracleDatabaseConnectionConfig) *,* *SerializeAsAny* *(* *)* *]*)

#### connection_config *: `Annotated`[[`PluginOracleDatabaseConnectionConfig`](#wayflowcore.agentspec.components.datastores.oracle_datastore.PluginOracleDatabaseConnectionConfig)]*

Configuration of connection parameters

#### datastore_schema *: `Dict`[`str`, `Property`]*

Mapping of collection names to entity definitions used by this datastore.

<a id="agentspectlsoracledatabaseconnectionconfig"></a>

### *class* wayflowcore.agentspec.components.datastores.oracle_datastore.PluginTlsOracleDatabaseConnectionConfig(\*\*data)

TLS Connection Configuration to Oracle Database.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **user** (*Annotated* *[**str* *,*  *'SENSITIVE_FIELD_MARKER'* *]*)
  * **password** (*Annotated* *[**str* *,*  *'SENSITIVE_FIELD_MARKER'* *]*)
  * **dsn** (*Annotated* *[**str* *,*  *'SENSITIVE_FIELD_MARKER'* *]*)
  * **config_dir** (*Annotated* *[**str* *|* *None* *,*  *'SENSITIVE_FIELD_MARKER'* *]*)

#### config_dir *: `Annotated`[`Optional`[`str`]]*

Configuration directory for the database connection. Set this if you are using an
alias from your tnsnames.ora files as a DSN. Make sure that the specified DSN is
appropriate for TLS connections (as the tnsnames.ora file in a downloaded wallet
will only include DSN entries for mTLS connections)

#### dsn *: `Annotated`[`str`]*

Connection string for the database (e.g., created using oracledb.make_dsn)

#### password *: `Annotated`[`str`]*

Password for the provided user

#### user *: `Annotated`[`str`]*

User used to connect to the database

<a id="agentspecrelationaldatastore"></a>

### *class* wayflowcore.agentspec.components.datastores.relational_datastore.PluginRelationalDatastore(\*\*data)

A relational data store that supports querying data using SQL-like queries.

This class extends the PluginDatastore class and adds support for querying
data using SQL-like queries.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **id** (*str*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **metadata** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **min_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)
  * **max_agentspec_version** (*Annotated* *[**AgentSpecVersionEnum* *,* *PlainSerializer* *(**func=~pyagentspec.component.<lambda>* *,* *return_type=PydanticUndefined* *,* *when_used=always* *)* *,* *SkipJsonSchema* *(* *)* *]*)

### Tools

<a id="agentspecplugintoolrequest"></a>

### *class* wayflowcore.agentspec.components.tools.PluginToolRequest(\*\*data)

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **name** (*str*)
  * **args** (*Dict* *[**str* *,* *Any* *]*)
  * **tool_request_id** (*str*)

#### args *: `Dict`[`str`, `Any`]*

#### model_config *: ClassVar[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [ConfigDict][pydantic.config.ConfigDict].

#### name *: `str`*

#### tool_request_id *: `str`*

<a id="agentspecplugintoolresult"></a>

### *class* wayflowcore.agentspec.components.tools.PluginToolResult(\*\*data)

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **content** (*Any*)
  * **tool_request_id** (*str*)

#### content *: `Any`*

#### model_config *: ClassVar[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [ConfigDict][pydantic.config.ConfigDict].

#### tool_request_id *: `str`*

### Context

### *class* wayflowcore.agentspec._runtimeconverter.AgentSpecToWayflowConversionContext(plugins=None)

* **Parameters:**
  **plugins** (*List* *[*[*WayflowDeserializationPlugin*](serialization.md#wayflowcore.serialization.plugins.WayflowDeserializationPlugin) *]*  *|* *None*)

#### convert(agentspec_component, tool_registry, converted_components=None)

Convert the given PyAgentSpec component object into the corresponding Runtime component

* **Return type:**
  `Any`
* **Parameters:**
  * **agentspec_component** (*Component*)
  * **tool_registry** (*Dict* *[**str* *,* [*ServerTool*](tools.md#wayflowcore.tools.servertools.ServerTool) *|* *Callable* *[* *[* *...* *]* *,* *Any* *]* *]*)
  * **converted_components** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### *class* wayflowcore.agentspec._agentspecconverter.WayflowToAgentSpecConversionContext(plugins=None)

* **Parameters:**
  **plugins** (*List* *[*[*WayflowSerializationPlugin*](serialization.md#wayflowcore.serialization.plugins.WayflowSerializationPlugin) *]*  *|* *None*)

#### convert(runtime_component, referenced_objects=None)

Convert the given WayFlow component object into the corresponding PyAgentSpec component

* **Return type:**
  `Component`
* **Parameters:**
  * **runtime_component** ([*SerializableObject*](serialization.md#wayflowcore.serialization.serializer.SerializableObject))
  * **referenced_objects** (*Dict* *[**str* *,* *Component* *]*  *|* *None*)
