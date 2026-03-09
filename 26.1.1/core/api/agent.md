# Agents

This page presents all APIs and classes related to WayFlow agents.

![agentspec-icon](_static/icons/agentspec-icon.svg)

Visit the Agent Spec API Documentation to learn more about Agent Components.

[Agent Spec - Agents API Reference](https://oracle.github.io/agent-spec/api/agent.html)

#### TIP
Click the button above ↑ to visit the [Agent Spec Documentation](https://oracle.github.io/agent-spec/index.html)

## Agent related classes

### Agent class

<a id="agent"></a>

### *class* wayflowcore.agent.Agent(llm, tools=None, flows=None, agents=None, custom_instruction=None, agent_id=None, id=None, max_iterations=10, context_providers=None, can_finish_conversation=False, raise_exceptions=False, initial_message='N/A', caller_input_mode=CallerInputMode.ALWAYS, input_descriptors=None, output_descriptors=None, name=None, description='', agent_template=None, transforms=None, \_add_talk_to_user_tool=True, \_\_metadata_info_\_=None)

Agent that can handle a conversation with a user, interact with external tools
and follow interaction flows.

#### NOTE
An `Agent` has input and output descriptors, describing what values the agent requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, the input_descriptors will be automatically inferred
from the `custom_instruction` template of the `Agent`, with one input descriptor per variable in the template,
trying to detect the type of the variable based on how it is used in the template.
See [TemplateRenderingStep](flows.md#templaterenderingstep) for concrete examples on how descriptors are
extracted from text prompts.

If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
in particular using the new type instead of the detected one. If some of them are missing,
the Agent’s execution is not guaranteed to succeed.

If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
they won’t be used during the execution of the step.

**Output descriptors**

By default, when `output_descriptors` is set to `None`, the `Agent` won’t have any output descriptors,
which means that it can only ask question to the user by yielding.

If you provide a list of output descriptors, the `Agent` will be prompted to gather and output
values that will match the expected output descriptors, which means it can either yield to the user or
finish the conversation by outputting the output values. If the `Agent` is not able to generate them,
the values will be filled with their default values if they are specified, or the default values
of their respective types, after the maximum amount of iterations of the `Agent` is reached.

* **Parameters:**
  * **llm** ([`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)) – Model to use for the agent executor (which chooses the next action to do).
  * **tools** (`Optional`[`Sequence`[`Union`[[`Tool`](tools.md#wayflowcore.tools.tools.Tool), [`ToolBox`](tools.md#wayflowcore.tools.toolbox.ToolBox)]]]) – List of tools available for the agent.
  * **flows** (`Optional`[`List`[[`Flow`](flows.md#wayflowcore.flow.Flow)]]) – List of flows available for the agent.
  * **agents** (`Optional`[`List`[`Union`[[`Agent`](#wayflowcore.agent.Agent), [`OciAgent`](#wayflowcore.ociagent.OciAgent)]]]) – 

    Other agents that the agent can call (expert agents).

    #### WARNING
    The use of expert agents is currently in beta and may undergo significant changes.
    The API and behaviour are not guaranteed to be stable and may change in future versions.
  * **custom_instruction** (`Optional`[`str`]) – Custom instruction for the agent that will be passed in the system prompt.
    You need to include the context and what the agent is supposed to help the
    user with. This can contain variables in the jinja syntax, and their context
    providers need to be passed in the context_providers parameter.
  * **max_iterations** (`int`) – Maximum number of calls to the agent executor before yielding back to the user.
  * **context_providers** (`Optional`[`List`[[`ContextProvider`](contextproviders.md#wayflowcore.contextproviders.contextprovider.ContextProvider)]]) – Context providers for jinja variables in the custom_instruction.
  * **can_finish_conversation** (`bool`) – Whether the agent can decide to end the conversation or not.
  * **raise_exceptions** (`bool`) – Whether exceptions from sub-executions (tool, sub-agent, or sub-flow execution) are raised or not.
  * **initial_message** (`Optional`[`str`]) – Initial message the agent will post if no previous user message. It must be None for CallerInputMode.NEVER
    If None for CallerInputMode.ALWAYS, the LLM will generate it given the custom_instruction. Default to
    Agent.DEFAULT_INITIAL_MESSAGE for CallerInputMode.ALWAYS and None for CallerInputMode.NEVER.
  * **caller_input_mode** ([`CallerInputMode`](#wayflowcore.agent.CallerInputMode)) – Whether the agent is allowed to ask the user questions (CallerInputMode.ALWAYS) or not (CallerInputMode.NEVER).
    If set to NEVER, the agent won’t be able to yield.
  * **input_descriptors** (`Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]) – 

    Input descriptors of the agent. `None` means the agent will resolve the input descriptors automatically in a best effort manner.

    #### NOTE
    In some cases, the static configuration might not be enough to infer them properly, so this argument allows to override them.

    If `input_descriptors` are specified, they will override the resolved descriptors but will be matched
    by `name` against them to check that types can be casted from one another, raising an error if they can’t.
    If some expected descriptors are missing from the `input_descriptors` (i.e. you forgot to specify one),
    a warning will be raised and the agent is not guaranteed to work properly.
  * **output_descriptors** (`Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]) – 

    Outputs that the agent is expected to generate.

    #### WARNING
    If not `None`, it will change the agent’s behavior and the agent will be prompted to output values for
    all outputs. The `Agent` will be able to submit values when it sees fit to finish the conversation.
    The outputs are mandatory if no default value is provided (the agent will have to submit a value for
    it to finish the conversation, and will be re-prompted to do so if it does not provide a value for it)
    but optional if a default value is passed (it will use the default value if the LLM doesn’t generate
    a value for it.
  * **name** (`Optional`[`str`]) – name of the agent, used for composition
  * **description** (`str`) – description of the agent, used for composition
  * **id** (`Optional`[`str`]) – ID of the agent
  * **agent_template** (`Optional`[[`PromptTemplate`](prompttemplate.md#wayflowcore.templates.template.PromptTemplate)]) – Specific agent template for more advanced prompting techniques. It will be overloaded with the current
    agent `tools`, and can have placeholders:
    \* `custom_instruction` placeholder for the `custom_instruction` parameter.
  * **transforms** (`Optional`[`List`[[`MessageTransform`](prompttemplate.md#wayflowcore.transforms.MessageTransform)]]) – List of MessageTransform objets to run in order on each conversation before passing to the LLM.
  * **agent_id** (*str* *|* *None*)
  * **\_add_talk_to_user_tool** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.agent import Agent
>>> agent = Agent(llm=llm)
>>> conversation = agent.start_conversation()
>>> conversation.append_user_message("I need help regarding my sql query")
>>> status = conversation.execute()
>>> agent_answer = conversation.get_last_message().content
>>> # I'd be happy to help with your SQL query
```

#### DEFAULT_INITIAL_MESSAGE *: `ClassVar`[`str`]* *= 'Hi! How can I help you?'*

Message the agent will post if no previous user message to welcome them.

* **Type:**
  str

#### NOT_SET_INITIAL_MESSAGE *: `ClassVar`[`str`]* *= 'N/A'*

Placeholder for non-explicitly set initial message.

* **Type:**
  str

#### *property* agent_id *: str*

#### agent_template *: [`PromptTemplate`](prompttemplate.md#wayflowcore.templates.template.PromptTemplate)*

#### agents *: `List`[`Union`[Agent, OciAgent]]*

Sub-agents the agent has access to

#### caller_input_mode *: [`CallerInputMode`](#wayflowcore.agent.CallerInputMode)*

Whether the agent can ask the user for additional information or needs to just deal with the task itself

#### can_finish_conversation *: `bool`*

Whether the agent can just exist the conversation when thinks it is done helping the user

#### clone(name, description)

Clones an agent with a different name and description

* **Return type:**
  [`Agent`](#wayflowcore.agent.Agent)
* **Parameters:**
  * **name** (*str*)
  * **description** (*str*)

#### *static* compute_agent_inputs(custom_instruction, context_providers, user_specified_input_descriptors, agent_template)

* **Return type:**
  `Tuple`[`List`[[`Property`](flows.md#wayflowcore.property.Property)], `List`[`str`]]
* **Parameters:**
  * **custom_instruction** (*str* *|* *None*)
  * **context_providers** (*List* *[*[*ContextProvider*](contextproviders.md#wayflowcore.contextproviders.contextprovider.ContextProvider) *]*)
  * **user_specified_input_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*)
  * **agent_template** ([*PromptTemplate*](prompttemplate.md#wayflowcore.templates.template.PromptTemplate))

#### *property* config *: [Agent](#wayflowcore.agent.Agent)*

#### context_providers *: `List`[ContextProvider]*

Context providers for variables present in the custom instructions of the agent

#### custom_instruction *: `Optional`[`str`]*

Additional instructions to put in the agent system prompt

#### description *: `Optional`[`str`]*

#### *property* executor *: ConversationExecutor*

#### flows *: `List`[Flow]*

Flows the agent has access to

#### id *: `str`*

Id of the agent, needed to deal with message visibility

#### initial_message *: `Optional`[`str`]*

Initial hardcoded message the agent might post if it doesn’t have any user message in the conversation

#### input_descriptors *: `List`[[`Property`](flows.md#wayflowcore.property.Property)]*

Input descriptors of the agent. Can be updated based on other agent attributes

#### llm *: [`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)*

LLM used for the react agent

#### *property* llms *: List[[LlmModel](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)]*

#### max_iterations *: `int`*

Maximum number of iterations the agent can loop before returning to the user

#### *property* might_yield *: bool*

#### name *: `str`*

#### output_descriptors *: `List`[[`Property`](flows.md#wayflowcore.property.Property)]*

Output descriptors of the agent

#### raise_exceptions *: `bool`*

Whether exceptions from sub-executions (tool, sub-agent, or sub-flow execution) are raised or not.

#### start_conversation(inputs=None, messages=None, conversation_id=None)

Initializes a conversation with the agent.

* **Parameters:**
  * **inputs** (`Optional`[`Dict`[`str`, `Any`]]) – This argument is not used.
    It is included for compatibility with the Flow class.
  * **messages** (`Union`[`None`, `str`, [`Message`](conversation.md#wayflowcore.messagelist.Message), `List`[[`Message`](conversation.md#wayflowcore.messagelist.Message)], [`MessageList`](conversation.md#wayflowcore.messagelist.MessageList)]) – Message list to which the agent will participate
  * **conversation_id** (`Optional`[`str`]) – Conversation id of the parent conversation.
* **Returns:**
  The conversation object of the agent.
* **Return type:**
  [Conversation](conversation.md#wayflowcore.conversation.Conversation)

#### tools *: `Sequence`[`Union`[[`Tool`](tools.md#wayflowcore.tools.tools.Tool), [`ToolBox`](tools.md#wayflowcore.tools.toolbox.ToolBox)]]*

Tools the agent has access to

### OCI Agent class

<a id="ociagent"></a>

### *class* wayflowcore.ociagent.OciAgent(agent_endpoint_id, client_config, initial_message='Hi! How can I help you?', name=None, description='', agent_id=None, id=None, \_\_metadata_info_\_=None)

An agent is a component that can do several rounds of conversation to solve a task.

The agent is defined on the OCI console and this is only a wrapper to connect to it.
It can be executed by itself, or be executed in a flow using an AgentNode, or used as a sub-agent of
another WayFlow Agent.

#### WARNING
`OciAgent` is currently in beta and may undergo significant changes.
The API and behaviour are not guaranteed to be stable and may change in future versions.

Connects to a remote `OciAgent`. The remote agent needs to be first created on the OCI console, this class
only connects to existing remote agents.

* **Parameters:**
  * **agent_endpoint_id** (`str`) – A unique ID for the endpoint.
  * **client_config** ([`OCIClientConfig`](llmmodels.md#wayflowcore.models.ociclientconfig.OCIClientConfig)) – oci client config to authenticate the OCI service
  * **initial_message** (`str`) – Initial message the agent will post if no previous user message.
    Default to `OciGenAIAgent.DEFAULT_INITIAL_MESSAGE`.
  * **name** (`Optional`[`str`]) – Name of the OCI agent.
  * **description** (`str`) – Description of the OCI agent. Is needed when the agent is used as the sub-agent of another agent.
  * **agent_id** (`Optional`[`str`]) – Unique ID to define the agent
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### DEFAULT_INITIAL_MESSAGE *: `ClassVar`[`str`]* *= 'Hi! How can I help you?'*

Message the agent will post if no previous user message to welcome them.

* **Type:**
  str

#### agent_endpoint_id *: `str`*

#### *property* agent_id *: str*

#### client_config *: [`OCIClientConfig`](llmmodels.md#wayflowcore.models.ociclientconfig.OCIClientConfig)*

#### description *: `str`*

#### id *: `str`*

#### initial_message *: `str`*

#### name *: `str`*

#### start_conversation(inputs=None, messages=None)

Initializes a conversation with the agent.

* **Parameters:**
  * **inputs** (`Optional`[`Dict`[`str`, `Any`]]) – This argument is not used.
    It is included for compatibility with the Flow class.
  * **messages** (`Union`[`None`, `str`, [`Message`](conversation.md#wayflowcore.messagelist.Message), `List`[[`Message`](conversation.md#wayflowcore.messagelist.Message)], [`MessageList`](conversation.md#wayflowcore.messagelist.MessageList)]) – Message list to which the agent will participate
* **Returns:**
  The conversation object of the agent.
* **Return type:**
  [Conversation](conversation.md#wayflowcore.conversation.Conversation)

### A2A Agent class

<a id="a2aagent"></a>

### *class* wayflowcore.a2a.a2aagent.A2AAgent(agent_url, connection_config, session_parameters=None, name=None, description='', id=None, \_\_metadata_info_\_=None)

An agent that facilitates agent-to-agent (A2A) communication with a remote server agent for conversational tasks.

The `A2AAgent` serves as a client-side wrapper to establish and manage connections with a server-side agent
through a specified URL. It handles the setup of HTTP connections, including security configurations for mutual
TLS (mTLS), and manages conversational interactions with the remote agent.

* **Parameters:**
  * **id** (`Optional`[`str`]) – A unique identifier for the agent.
  * **name** (`Optional`[`str`]) – The name of the agent, often used for identification in conversational contexts.
  * **description** (`str`) – A brief description of the agent’s purpose or functionality.
  * **agent_url** (`str`) – The URL of the remote server agent to connect to.
  * **connection_config** ([`A2AConnectionConfig`](a2a.md#wayflowcore.a2a.a2aagent.A2AConnectionConfig)) – Configuration settings for establishing HTTP connections, including timeout and security parameters.
  * **session_parameters** (`Optional`[[`A2ASessionParameters`](a2a.md#wayflowcore.a2a.a2aagent.A2ASessionParameters)]) – Parameters controlling session behavior such as polling timeouts and retry logic.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### NOTE
`A2AAgent` is specifically designed for agent-to-agent communication and requires a valid server
endpoint to function properly. Ensure the provided URL and connection configurations are correct
to avoid connection issues.

Initializes an `A2AAgent` to connect with a remote server agent.

This sets up the agent with the necessary connection details to interact with
a server agent at the specified URL.

* **Parameters:**
  * **agent_url** (`str`) – The URL of the server agent to connect to. Must be a valid URL with scheme and netloc.
  * **connection_config** ([`A2AConnectionConfig`](a2a.md#wayflowcore.a2a.a2aagent.A2AConnectionConfig)) – Configuration settings for establishing HTTP connections.
  * **session_parameters** (`Optional`[[`A2ASessionParameters`](a2a.md#wayflowcore.a2a.a2aagent.A2ASessionParameters)]) – Parameters controlling session behavior such as polling timeouts and retry logic.
    Defaults to an instance of A2ASessionParameters with default values.
  * **name** (`Optional`[`str`]) – Optional name for the agent. If not provided, a default name with prefix
    `a2a_agent_` is generated. Defaults to None.
  * **description** (`str`) – Description of the agent’s purpose or functionality. Defaults to an empty string.
  * **id** (`Optional`[`str`]) – Optional unique identifier for the agent. If not provided, one is generated.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
* **Raises:**
  * **ValueError** – If the provided `agent_url` is not a valid URL.
  * **TypeError** – If the provided `agent_url` is not a string.

#### *property* agent_id *: str*

#### agent_url *: `str`*

#### connection_config *: [`A2AConnectionConfig`](a2a.md#wayflowcore.a2a.a2aagent.A2AConnectionConfig)*

#### description *: `str`*

#### id *: `str`*

#### name *: `str`*

#### session_parameters *: [`A2ASessionParameters`](a2a.md#wayflowcore.a2a.a2aagent.A2ASessionParameters)*

#### start_conversation(inputs=None, messages=None)

Initiates a new conversation with the remote server agent.

Creates and returns a conversation instance tied to this agent, optionally initialized
with input data and a message history.

* **Parameters:**
  * **inputs** (`Optional`[`Dict`[`str`, `Any`]]) – Optional dictionary of initial input data for the conversation. Defaults to an empty
    dictionary if not provided.
  * **messages** (`Union`[`None`, `str`, [`Message`](conversation.md#wayflowcore.messagelist.Message), `List`[[`Message`](conversation.md#wayflowcore.messagelist.Message)], [`MessageList`](conversation.md#wayflowcore.messagelist.MessageList)]) – Optional initial message list for the conversation. Can be either a `MessageList`
    or a list of `Message` objects. Defaults to an empty `MessageList` if not provided.
* **Returns:**
  A new conversation object associated with this agent.
* **Return type:**
  [Conversation](conversation.md#wayflowcore.conversation.Conversation)

### DescribedFlow

<a id="id1"></a>

### *class* wayflowcore.tools.DescribedFlow(flow, name, description, output=None)

DescribedFlow are used to store additional information about Flow
to enable flow as tool support in the AgentExecutionStep.

The name and description of the flow should represent the purpose of the
flow when used as a tool.

* **Parameters:**
  * **flow** ([`Flow`](flows.md#wayflowcore.flow.Flow)) – Flow object.
  * **name** (`str`) – Name of the flow.
  * **description** (`str`) – Description of the purpose of the flow when used as a tool.
  * **output** (`Optional`[`str`]) – Description of the output of the flow.

#### description *: `str`*

#### flow *: Flow*

#### *static* from_config(config, deserialization_context=None)

Creates a DescribedFlow object from a configuration dictionary.

* **Parameters:**
  * **config** (`Dict`[`str`, `Any`]) – Dictionary representing the configuration of the described flow.
  * **serialization_context** – Serialization context for the object.
  * **deserialization_context** ([*DeserializationContext*](serialization.md#wayflowcore.serialization.context.DeserializationContext) *|* *None*)
* **Returns:**
  A DescribedFlow object created from the configuration.
* **Return type:**
  [DescribedFlow](#wayflowcore.tools.DescribedFlow)

#### name *: `str`*

#### output *: `Optional`[`str`]* *= None*

#### to_config(serialization_context=None)

Converts the described flow to a configuration dictionary.

* **Parameters:**
  **serialization_context** (`Optional`[[`SerializationContext`](serialization.md#wayflowcore.serialization.context.SerializationContext)]) – Serialization context for the object.
* **Returns:**
  A dictionary representing the configuration of the described flow.
* **Return type:**
  Dict

### DescribedAgent

<a id="describedassistant"></a>

### *class* wayflowcore.tools.DescribedAgent(agent, name, description)

DescribedAgent are used to store additional information about agents
to enable their use as tool support in the AgentExecutionStep.

The name and description of the agent should represent the purpose of the
agent when used as a tool.

* **Parameters:**
  * **agent** ([`Agent`](#wayflowcore.agent.Agent)) – Agent object.
  * **name** (`str`) – Name of the agent.
  * **description** (`str`) – Description of the purpose of the agent when used as a tool.

#### agent *: Agent*

#### description *: `str`*

#### *static* from_config(config, deserialization_context)

Creates a DescribedAgent object from a configuration dictionary.

* **Parameters:**
  * **config** (`Dict`[`str`, `Any`]) – Dictionary representing the configuration of the described agent.
  * **deserialization_context** (`Optional`[[`DeserializationContext`](serialization.md#wayflowcore.serialization.context.DeserializationContext)]) – Deserialization context for the object.
* **Returns:**
  A DescribedAgent object created from the configuration.
* **Return type:**
  [DescribedAgent](#wayflowcore.tools.DescribedAgent)

#### name *: `str`*

#### to_config(serialization_context)

Converts the described agent to a configuration dictionary.

* **Parameters:**
  **serialization_context** (`Optional`[[`SerializationContext`](serialization.md#wayflowcore.serialization.context.SerializationContext)]) – Serialization context for the object.
* **Returns:**
  A dictionary representing the configuration of the described agent.
* **Return type:**
  Dict

### Swarm class

<a id="swarm"></a>

### *class* wayflowcore.swarm.Swarm(first_agent, relationships, handoff=HandoffMode.OPTIONAL, caller_input_mode=CallerInputMode.ALWAYS, swarm_template=None, input_descriptors=None, output_descriptors=None, name=None, description=None, \_\_metadata_info_\_=None, id=None)

Defines a `Swarm` conversational component.

A `Swarm` is a multi-agent conversational component in which each agent determines
the next agent to be executed, based on a list of pre-defined relationships.

* **Parameters:**
  * **first_agent** ([`Agent`](#wayflowcore.agent.Agent)) – The first `Agent` to interact with the human user.
  * **relationships** (`List`[`Tuple`[[`Agent`](#wayflowcore.agent.Agent), [`Agent`](#wayflowcore.agent.Agent)]]) – 

    Determine the list of allowed interactions in the `Swarm`.
    Each element in the list is a tuple `(caller_agent, recipient_agent)`
    specifying that the `caller_agent` can query the `recipient_agent`.

    Agents can delegate in two ways, depending on the `handoff` mode:
    * **Message passing** via *send_message* tool — the caller requests a sub-task and waits for the recipient to reply. Note the the recipient does *not* need to have a reverse relatiship (i.e (recipient_agent, caller_agent)) in order to send a response back to the caller.
    * **Conversation handoff** via *handoff_conversation* tool — the caller transfers the entire conversation history with the user to the recipient, who then becomes the new active agent speaking to the user.
  * **handoff** (`Union`[[`HandoffMode`](#wayflowcore.swarm.HandoffMode), `bool`]) – 

    Specifies how agents are allowed to delegate work. See `HandoffMode` for full details.
    * `HandoffMode.NEVER`: Agents can only use *send_message*. The `first_agent` is the only agent that can interact with the user.
    * `HandoffMode.OPTIONAL`: Agents may either send messages or fully hand off the conversation. This provides the most flexibility and often results in natural delegation.
    * `HandoffMode.ALWAYS`: Agents cannot send messages to other agents. Any delegation must be performed through *handoff_conversation*.

    #### NOTE
    A key benefit of using Handoff is the reduced response latency: While talking to other agents increases the “distance”
    between the human user and the current agent, transferring a conversation to another agent keeps this distance unchanged
    (i.e. the agent interacting with the user is different but the user is still the same). However, transferring the full conversation might increase the token usage.
  * **input_descriptors** (`Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]) – 

    Input descriptors of the swarm. `None` means the swarm will resolve the input descriptors automatically in a best effort manner.

    #### NOTE
    In some cases, the static configuration might not be enough to infer them properly, so this argument allows to override them.

    If `input_descriptors` are specified, they will override the resolved descriptors but will be matched
    by `name` against them to check that types can be casted from one another, raising an error if they can’t.
    If some expected descriptors are missing from the `input_descriptors` (i.e. you forgot to specify one),
    a warning will be raised and the swarm is not guaranteed to work properly.
  * **output_descriptors** (`Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]) – Output descriptors of the swarm. `None` means the swarm will resolve them automatically in a best effort manner.
  * **caller_input_mode** ([`CallerInputMode`](#wayflowcore.agent.CallerInputMode)) – Whether the agent in swarm can ask the user for additional information or needs to handle the task internally within the swarm.
  * **name** (`Optional`[`str`]) – name of the swarm, used for composition
  * **description** (`Optional`[`str`]) – description of the swarm, used for composition
  * **id** (`Optional`[`str`]) – ID of the Swarm
  * **swarm_template** ([*PromptTemplate*](prompttemplate.md#wayflowcore.templates.template.PromptTemplate))
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Example

```pycon
>>> from wayflowcore.agent import Agent
>>> from wayflowcore.swarm import Swarm
>>> addition_agent = Agent(name="addition_agent", description="Agent that can do additions", llm=llm, custom_instruction="You can do additions.")
>>> multiplication_agent = Agent(name="multiplication_agent", description="Agent that can do multiplication", llm=llm, custom_instruction="You can do multiplication.")
>>> division_agent = Agent(name="division_agent", description="Agent that can do division", llm=llm, custom_instruction="You can do division.")
>>>
>>> swarm = Swarm(
...     first_agent=addition_agent,
...     relationships=[
...         (addition_agent, multiplication_agent),
...         (addition_agent, division_agent),
...         (multiplication_agent, division_agent),
...     ]
... )
>>> conversation = swarm.start_conversation()
>>> conversation.append_user_message("Please compute 2*2+1")
>>> status = conversation.execute()
>>> swarm_answer = conversation.get_last_message().content
>>> # The answer to 2*2+1 is 5.
```

#### caller_input_mode *: [`CallerInputMode`](#wayflowcore.agent.CallerInputMode)*

#### description *: `Optional`[`str`]*

#### first_agent *: [`Agent`](#wayflowcore.agent.Agent)*

#### handoff *: `Union`[[`HandoffMode`](#wayflowcore.swarm.HandoffMode), `bool`]*

#### id *: `str`*

#### input_descriptors *: `List`[Property]*

#### name *: `str`*

#### output_descriptors *: `List`[Property]*

#### relationships *: `List`[`Tuple`[[`Agent`](#wayflowcore.agent.Agent), [`Agent`](#wayflowcore.agent.Agent)]]*

#### start_conversation(inputs=None, messages=None, conversation_id=None, conversation_name=None)

* **Return type:**
  [`Conversation`](conversation.md#wayflowcore.conversation.Conversation)
* **Parameters:**
  * **inputs** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **messages** (*None* *|* *str* *|* [*Message*](conversation.md#wayflowcore.messagelist.Message) *|* *List* *[*[*Message*](conversation.md#wayflowcore.messagelist.Message) *]*  *|* [*MessageList*](conversation.md#wayflowcore.messagelist.MessageList))
  * **conversation_id** (*str* *|* *None*)
  * **conversation_name** (*str* *|* *None*)

#### swarm_template *: PromptTemplate*

<a id="handoffmode"></a>

### *class* wayflowcore.swarm.HandoffMode(value)

Controls how agents in a Swarm may delegate work to one another.
This setting determines whether an agent is equipped with:

* *send_message* — a tool for asking another agent to perform a sub-task and reply back.
* *handoff_conversation* — a tool for transferring the full user–agent conversation to another agent.

Depending on the selected mode, agents have different capabilities for delegation and collaboration.

#### ALWAYS *= 'always'*

Agents receive **only** the *handoff_conversation* tool.
Message-passing is disabled:

* Agents *must* hand off the user conversation when delegating work.
* They cannot simply send a message and receive a response.

This mode enforces a strict chain-of-ownership: whenever an agent involves another agent,
it must transfer the full dialogue context. The next agent can either respond directly to the user
or continue handing off the conversation to another agent.

#### NEVER *= 'never'*

Agent is not equipped with the *handoff_conversation* tool.
Delegation is limited to message-passing:

* Agents *can* use *send_message* to request a sub-task from another agent.
* Agents *cannot* transfer the user conversation to another agent.

As a consequence, the `first_agent` always remains the primary point of contact with the user.

#### OPTIONAL *= 'optional'*

Agents receive **both** *handoff_conversation* and *send_message* tool.
This gives agents full flexibility:

* They may pass a message to another agent and wait for a reply.
* Or they may fully hand off the user conversation to another agent.

Use this mode when you want agents to intelligently choose the most natural delegation strategy.

### ManagerWorkers class

<a id="managerworkers"></a>

### *class* wayflowcore.managerworkers.ManagerWorkers(group_manager, workers, caller_input_mode=CallerInputMode.ALWAYS, managerworkers_template=None, input_descriptors=None, output_descriptors=None, name=None, description='', \_\_metadata_info_\_=None, id=None)

Defines a `ManagerWorkers` conversational component.

A `ManagerWorkers` is a multi-agent conversational component in which a group manager agent
assigns tasks to worker agents.

* **Parameters:**
  * **workers** (`List`[`Union`[[`Agent`](#wayflowcore.agent.Agent), [`ManagerWorkers`](#wayflowcore.managerworkers.ManagerWorkers)]]) – List of Agents or other ManagerWorkers that participate in the group as workers. There should be at least one worker in the list.
  * **group_manager** (`Union`[[`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel), [`Agent`](#wayflowcore.agent.Agent)]) – Can either be an LLM or an agent that manages the group. If an LLM is passed, a manager agent
    will be created using that LLM.
  * **caller_input_mode** ([`CallerInputMode`](#wayflowcore.agent.CallerInputMode)) – Whether the manager can ask the user for additional information or needs to handle the task internally within the team.
    This overrides manager agent’s `caller_input_mode`.
  * **input_descriptors** (`Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]) – 

    Input descriptors of the ManagerWorkers. `None` means the ManagerWorks will resolve the input descriptors automatically in a best effort manner.

    #### NOTE
    In some cases, the static configuration might not be enough to infer them properly, so this argument allows to override them.

    If `input_descriptors` are specified, they will override the resolved descriptors but will be matched
    by `name` against them to check that types can be casted from one another, raising an error if they can’t.
    If some expected descriptors are missing from the `input_descriptors` (i.e. you forgot to specify one),
    a warning will be raised and the ManagerWorkers is not guaranteed to work properly.
  * **output_descriptors** (`Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]) – Output descriptors of the ManagerWorkers. `None` means the ManagerWorkers will resolve them automatically in a best effort manner.
  * **name** (`Optional`[`str`]) – name of the ManagerWorkers, used for composition
  * **description** (`str`) – description of the ManagerWorkers, used for composition
  * **managerworkers_template** ([*PromptTemplate*](prompttemplate.md#wayflowcore.templates.template.PromptTemplate))
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **id** (*str*)

### Example

```pycon
>>> from wayflowcore.agent import Agent
>>> from wayflowcore.managerworkers import ManagerWorkers
>>> addition_agent = Agent(name="addition_agent", description="Agent that can do additions", llm=llm, custom_instruction="You can do additions.")
>>> multiplication_agent = Agent(name="multiplication_agent", description="Agent that can do multiplication", llm=llm, custom_instruction="You can do multiplication.")
>>> division_agent = Agent(name="division_agent", description="Agent that can do division", llm=llm, custom_instruction="You can do division.")
>>>
>>> group = ManagerWorkers(
...     workers=[addition_agent, multiplication_agent, division_agent],
...     group_manager=llm,
... )
>>> conversation = group.start_conversation()
>>> conversation.append_user_message("Please compute 2*2 + 1")
>>> status = conversation.execute()
>>> answer = conversation.get_last_message().content
>>> # The answer to 2*2 + 1 is 5.
```

#### caller_input_mode *: [`CallerInputMode`](#wayflowcore.agent.CallerInputMode)*

#### description *: `Optional`[`str`]*

#### group_manager *: `Union`[[`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel), [`Agent`](#wayflowcore.agent.Agent)]*

#### id *: `str`*

#### input_descriptors *: `List`[Property]*

#### managerworkers_template *: PromptTemplate*

#### name *: `str`*

#### output_descriptors *: `List`[Property]*

#### start_conversation(inputs=None, messages=None, conversation_id=None, conversation_name=None)

Initializes a conversation with the managerworkers.

* **Parameters:**
  * **inputs** (`Optional`[`Dict`[`str`, `Any`]]) – Dictionary of inputs. Keys are the variable identifiers and
    values are the actual inputs to start the main conversation.
  * **messages** (`Union`[`None`, `str`, [`Message`](conversation.md#wayflowcore.messagelist.Message), `List`[[`Message`](conversation.md#wayflowcore.messagelist.Message)], [`MessageList`](conversation.md#wayflowcore.messagelist.MessageList)]) – Message list of the manager agent and the end-user.
  * **conversation_id** (`Optional`[`str`]) – Conversation id of the main conversation.
  * **conversation_name** (*str* *|* *None*)
* **Returns:**
  The conversation object of the managerworkers.
* **Return type:**
  [Conversation](conversation.md#wayflowcore.conversation.Conversation)

#### workers *: `List`[`Union`[[`Agent`](#wayflowcore.agent.Agent), ManagerWorkers]]*

## Agent Behavior Configuration

<a id="callerinputmode"></a>

### *class* wayflowcore.agent.CallerInputMode(value)

Mode into which the caller of an Agent/AgentExecutionStep sets the Agent.

#### ALWAYS *= 'always'*

#### NEVER *= 'never'*
