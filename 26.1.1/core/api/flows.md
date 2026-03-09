# Flows

This page presents all APIs and classes related to flows and steps in WayFlow.

![agentspec-icon](_static/icons/agentspec-icon.svg)

Visit the Agent Spec API Documentation to learn more about Flow Components.

[Agent Spec - Flows API Reference](https://oracle.github.io/agent-spec/api/flows.html)

#### TIP
Click the button above ↑ to visit the [Agent Spec Documentation](https://oracle.github.io/agent-spec/index.html)

## Flows & Steps

<a id="flow"></a>

### *class* wayflowcore.flow.Flow(steps=None, begin_step=None, data_flow_edges=None, control_flow_edges=None, context_providers=None, variables=None, name=None, description='', flow_id=None, input_descriptors=None, output_descriptors=None, \_\_metadata_info_\_=None, transitions=None, id=None)

Represents a conversational assistant that defines the flow of a conversation.

The flow consists of a set of steps (states) and possible transitions between steps.
Transitions are validated to ensure compliance with expected scenarios.
The flow can have arbitrary loops, and each step can indicate whether it should be followed by
a direct execution of the next step or yielding back to the user.

#### NOTE
A flow has input and output descriptors, describing what values the flow requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, the input descriptors of the flow are resolved
automatically based on the shape of the flow. This means that we consider an input descriptor of the flow
all input descriptors that are defined in the `StartStep`.

If no `StartStep` is provided for the flow, the input descriptors of the step are resolved
automatically based on the shape of the flow. They consist of all input descriptors of its steps that are
not linked with a `data_flow_edge` to an output descriptor of another step in this flow.

If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
in particular using the new type instead of the detected one. If some of them are missing,
they won’t be exposed as inputs of the flow.

When starting a conversation with a `Flow`, you need to pass an input for each input_descriptor of
the flow using `flow.start_conversation(inputs=<INPUTS>)`.

**Output descriptors**

By default, when `output_descriptors` is set to `None`, the flow will auto-detect all outputs that are
produced in any path in this flow. This means that we consider an output descriptor of the flow all output
descriptors that were produced when reaching any of the `CompleteStep` / steps transitioning to `None`.

If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
in particular using the new type instead of the detected one. If some of them are missing,
they won’t be exposed as outputs of the flow.

If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
the flow will not work if they don’t have default values.

**Branches**

Flows sometimes can have different paths, and finish in different `CompleteStep`. Each name of a `CompleteStep` in the flow
will be exposed as a different end of the flow (or branch).

* **Parameters:**
  * **steps** (`Union`[`Dict`[`str`, [`Step`](#wayflowcore.steps.step.Step)], `List`[[`Step`](#wayflowcore.steps.step.Step)], `None`]) – Dictionary of steps linking names with stateless instances of steps.
  * **begin_step** (`Optional`[[`Step`](#wayflowcore.steps.step.Step)]) – First step of the flow.
  * **data_flow_edges** (`Optional`[`List`[[`DataFlowEdge`](#wayflowcore.dataconnection.DataFlowEdge)]]) – Data flow edges indicate which outputs that step or context provider produce are passed
    to the next steps in the Flow.
  * **control_flow_edges** (`Optional`[`List`[[`ControlFlowEdge`](#wayflowcore.controlconnection.ControlFlowEdge)]]) – Control flow edges indicate transitions between each steps.
  * **context_providers** (`Optional`[`List`[[`ContextProvider`](contextproviders.md#wayflowcore.contextproviders.contextprovider.ContextProvider)]]) – List of objects that add context to specific steps.
  * **variables** (`Optional`[`List`[[`Variable`](variables.md#wayflowcore.variable.Variable)]]) – 

    List of variables for the flow, whose values are visible per conversation.

    #### NOTE
    `Variables` defined in this list must have unique names. Whenever a flow starts
    a new conversation, a variable store is created with keys being the flow’s
    variables and values being the variables’ default values.
  * **name** (`Optional`[`str`]) – name of the agent, used for composition
  * **description** (`str`) – description of the agent, used for composition
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – 

    Input descriptors of the flow. `None` means the flow will resolve the input descriptors automatically in a best effort manner.
    .. note:
    ```default
    If ``input_descriptors`` are specified, they will override the resolved descriptors but will be matched
    by ``name`` against them to check that types can be casted from one another, raising an error if they can't.
    If some expected descriptors are missing from the ``input_descriptors`` (i.e. you forgot to specify one),
    a warning will be raised and the flow is not guaranteed to work properly.
    ```
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – 

    Output descriptors of the flow. `None` means the flow will resolve the output descriptors automatically in a best effort manner.

    #### NOTE
    If `output_descriptors` are specified, they will override the resolved descriptors but will be matched
    by `name` against them to check that types can be casted from one another, raising an error if they can’t.
    If some expected descriptors are missing from the `output_descriptors` (i.e. you forgot to specify one),
    a warning will be raised and the flow is not guaranteed to work properly.
  * **flow_id** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **transitions** (*Mapping* *[**str* *,* *List* *[**str* *|* *None* *]*  *|* *Mapping* *[**str* *,* *str* *|* *None* *]* *]*  *|* *None*)
  * **id** (*str* *|* *None*)

### Examples

```pycon
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.steps import OutputMessageStep, InputMessageStep, StartStep, CompleteStep
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.property import StringProperty
>>> USER_NAME = "$message"
>>> start_step = StartStep(name="start_step", input_descriptors=[StringProperty(name=USER_NAME)])
>>> output_step = OutputMessageStep(
...     name="output_step",
...     message_template="Welcome, {{username}}",
...     input_mapping={"username": USER_NAME}
... )
>>> complete_step = CompleteStep(name='complete_step')
>>> flow = Flow(
...     begin_step=start_step,
...     steps=[start_step, output_step, complete_step],
...     control_flow_edges=[
...         ControlFlowEdge(source_step=start_step, destination_step=output_step),
...         ControlFlowEdge(source_step=output_step, destination_step=complete_step),
...     ],
... )
>>> conversation = flow.start_conversation(inputs={USER_NAME: "User"})
>>> status = conversation.execute()
>>> status.output_values
{'output_message': 'Welcome, User'}
```

#### add_context_providers(providers)

Adds context key value providers to the flow.

* **Parameters:**
  **providers** (`List`[[`ContextProvider`](contextproviders.md#wayflowcore.contextproviders.contextprovider.ContextProvider)]) – Context providers to add to the flow.
* **Return type:**
  `None`

#### as_client_tool()

Converts this flow into a client tool

* **Return type:**
  [`ClientTool`](tools.md#wayflowcore.tools.clienttools.ClientTool)

#### as_server_tool()

Converts this flow into a server tool. Can only convert non-yielding flows

* **Return type:**
  [`ServerTool`](tools.md#wayflowcore.tools.servertools.ServerTool)

#### clone(name, description)

Clones a flow with a different name and description

* **Return type:**
  [`Flow`](#wayflowcore.flow.Flow)
* **Parameters:**
  * **name** (*str*)
  * **description** (*str*)

#### *property* flow_id *: str*

#### *static* from_steps(steps, data_flow_edges=None, context_providers=None, variables=None, loop=False, step_names=None, name=None, description='', input_descriptors=None, output_descriptors=None)

Helper method to create a sequential flow from a list of steps. Each step will be executed in the order
they are passed.

* **Parameters:**
  * **steps** (`List`[[`Step`](#wayflowcore.steps.step.Step)]) – the steps to create an assistant from
  * **data_flow_edges** (`Optional`[`List`[[`DataFlowEdge`](#wayflowcore.dataconnection.DataFlowEdge)]]) – list of data flow edges
  * **context_providers** (`Optional`[`list`[[`ContextProvider`](contextproviders.md#wayflowcore.contextproviders.contextprovider.ContextProvider)]]) – list of context providers
  * **variables** (`Optional`[`List`[[`Variable`](variables.md#wayflowcore.variable.Variable)]]) – list of variables
  * **loop** (`bool`) – whether the flow should loop back the first step or finish after the last step.
  * **step_names** (`Optional`[`List`[`str`]]) – List of step names. Will default to “step_{idx}” if not passed.
  * **name** (`Optional`[`str`]) – Name of the flow
  * **description** (`str`) – Description of the flow
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the flow
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the flow
* **Return type:**
  [`Flow`](#wayflowcore.flow.Flow)

### Examples

Create a flow in one line using this function:

```pycon
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.steps import OutputMessageStep
>>> flow = Flow.from_steps(
...     steps=[
...         OutputMessageStep('step 1 executes'),
...         OutputMessageStep('step 2 executes'),
...         OutputMessageStep('step 3 executes'),
...     ],
... )
```

#### *property* llms *: List[[LlmModel](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)]*

#### *property* might_yield *: bool*

Indicates if the flow might yield back to the user.
`True` if any of the steps in the flow might yield.

#### start_conversation(inputs=None, messages=None, conversation_id=None, nesting_level=0, context_providers_from_parent_flow=None)

Start the conversation.

* **Parameters:**
  * **inputs** (`Optional`[`Dict`[`str`, `Any`]]) – Dictionary of inputs. Keys are the variable identifiers and
    values are the actual inputs to start the conversation.
  * **conversation_id** (`Optional`[`str`]) – Conversation id of the parent conversation.
  * **messages** (`Union`[`None`, `str`, [`Message`](conversation.md#wayflowcore.messagelist.Message), `List`[[`Message`](conversation.md#wayflowcore.messagelist.Message)], [`MessageList`](conversation.md#wayflowcore.messagelist.MessageList)]) – List of messages (`MessageList` object) before starting the conversation.
  * **context_providers_from_parent_flow** (`Optional`[`Set`[`str`]]) – Context provider that don’t need to be checked when validating existing inputs.
  * **nesting_level** (`int`) – Nesting level of the conversation.
* **Returns:**
  A Flow Conversation object.
* **Return type:**
  [Conversation](conversation.md#wayflowcore.conversation.Conversation)

<a id="assistantstep"></a>

### *class* wayflowcore.steps.step.Step(step_static_configuration, llm=None, input_mapping=None, output_mapping=None, input_descriptors=None, output_descriptors=None, name=None, \_\_metadata_info_\_=None)

Assistant steps are what get executed by the flow.
They can have custom logic in the `.invoke()` method.
They can act based on input values passed to them, or messages in the messages list.
The messages list should be used to reflect the conversation with the user, i.e.
only things that make sense to show to the user or that were provided by the user.
They should indicate what is the next step upon return.

* **Parameters:**
  * **llm** (`Optional`[[`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)]) – Model that is used when executing the step.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – List of input descriptors of the step. They will compose the input dictionary that will be passed at `.invoke()` time.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – List of output descriptors of the step. The executor will assume that what is returned by `.invoke()` contains a value for all these descriptors.
  * **step_static_configuration** (*Dict* *[**str* *,* *Any* *]*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### BRANCH_NEXT *= 'next'*

Name of the branch taken by steps that do not have flow control and just have one transition

* **Type:**
  str

#### BRANCH_SELF *= '_\_self_\_'*

Name of the branch taken by a step that will come back to itself.

* **Type:**
  str

#### get_branches()

Returns the names of the control flow output branches of this step

* **Return type:**
  `List`[`str`]

#### *classmethod* get_static_configuration_descriptors()

* **Return type:**
  `Dict`[`str`, `type`]

#### invoke(inputs, conversation)

* **Return type:**
  [`StepResult`](#wayflowcore.steps.step.StepResult)
* **Parameters:**
  * **inputs** (*Dict* *[**str* *,* *Any* *]*)
  * **conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation))

#### *async* invoke_async(inputs, conversation)

* **Return type:**
  [`StepResult`](#wayflowcore.steps.step.StepResult)
* **Parameters:**
  * **inputs** (*Dict* *[**str* *,* *Any* *]*)
  * **conversation** ([*Conversation*](conversation.md#wayflowcore.conversation.Conversation))

#### *property* llms *: List[[LlmModel](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)]*

#### *property* might_yield *: bool*

Indicates if the step might yield back to the user.
Might be the step directly, or one of the steps it calls.

#### remap_inputs(inputs)

* **Return type:**
  `Dict`[`str`, `Any`]
* **Parameters:**
  **inputs** (*Dict* *[**str* *,* *Any* *]*)

#### remap_outputs(outputs)

* **Return type:**
  `Dict`[`str`, `type`]
* **Parameters:**
  **outputs** (*Dict* *[**str* *,* *Any* *]*)

#### sub_flow()

Returns the first sub-flow this step uses, if it does.

* **Return type:**
  `Optional`[[`Flow`](#wayflowcore.flow.Flow)]

#### sub_flows()

Returns the sub-flows this step uses, if it does.

* **Return type:**
  `Optional`[`List`[[`Flow`](#wayflowcore.flow.Flow)]]

#### *property* supports_dict_io_with_non_str_keys *: bool*

Indicates if the step can accept/return dictionaries with
keys that are not strings as IO.

<a id="dataflowedge"></a>

### *class* wayflowcore.dataconnection.DataFlowEdge(source_step, source_output, destination_step, destination_input, \*, id=<factory>, \_\_metadata_info_\_=<factory>, name='', description=None)

A data flow edge specifies how the output of a step or context provider propagates as input of another step.

Note: An output can be propagated as input of several steps.

* **Parameters:**
  * **source_step** (`Union`[[`Step`](#wayflowcore.steps.step.Step), [`ContextProvider`](contextproviders.md#wayflowcore.contextproviders.contextprovider.ContextProvider)]) – The source step or context provider where the data is outputted from.
    This can be an instance of either `Step` or `ContextProvider`.
  * **source_output** (`str`) – The name of the output generated by the `source_step`.
    This is used to identify the specific output data being propagated.
  * **destination_step** ([`Step`](#wayflowcore.steps.step.Step)) – The destination step where the data is directed to.
  * **destination_input** (`str`) – The name of the input in the `destination_step` where the data is propagated to.
    This is used to specify how the output data is used as input in the destination step.
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)

### Example

```pycon
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.dataconnection import DataFlowEdge
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.steps import OutputMessageStep
>>>
>>> mock_processing_step = OutputMessageStep("Successfully processed username {{username}}", name="processing_step")
>>> output_step = OutputMessageStep('{{session_id}}: Received message "{{processing_message}}"', name="output_step")
>>> flow = Flow(
...     begin_step=mock_processing_step,
...     control_flow_edges=[
...         ControlFlowEdge(source_step=mock_processing_step, destination_step=output_step),
...         ControlFlowEdge(source_step=output_step, destination_step=None),
...     ],
...     data_flow_edges=[
...         DataFlowEdge(mock_processing_step, OutputMessageStep.OUTPUT, output_step, "processing_message")
...     ]
... )
>>> conversation = flow.start_conversation(inputs={
...     "username": "Username#123",
...     "session_id": "Session#456"
... })
>>> status = conversation.execute()
>>> last_message = conversation.get_last_message()
>>> # last_message.content
>>> # Session#456: Received message "Successfully processed username Username#123"
```

#### destination_input *: `str`*

#### destination_step *: Step*

#### source_output *: `str`*

#### source_step *: `Union`[Step, ContextProvider]*

<a id="controlflowedge"></a>

### *class* wayflowcore.controlconnection.ControlFlowEdge(source_step, destination_step, source_branch='next', \*, id=<factory>, \_\_metadata_info_\_=<factory>, name='', description=None)

A control flow edge specifies how we transition from a step to another

* **Parameters:**
  * **source_step** ([`Step`](#wayflowcore.steps.step.Step)) – Source `Step` to transition from.
  * **destination_step** (`Optional`[[`Step`](#wayflowcore.steps.step.Step)]) – Destination `Step` where the transition is directed to.
  * **source_branch** (`str`) – Name of the specific step branch to transition from.
    Defaults to `Step.BRANCH_NEXT`.
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)

### Example

```pycon
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.steps import OutputMessageStep
>>> opening_step = OutputMessageStep("Opening session", name="open_step")
>>> closing_step = OutputMessageStep('Closing session"', name="close_step")
>>> flow = Flow(
...     begin_step=opening_step,
...     control_flow_edges=[
...         ControlFlowEdge(source_step=opening_step, destination_step=closing_step),
...         ControlFlowEdge(source_step=closing_step, destination_step=None),
...     ],
... )
>>> conversation = flow.start_conversation()
>>> status = conversation.execute()
>>> print(conversation.get_messages())  
```

#### destination_step *: `Optional`[Step]*

#### source_branch *: `str`* *= 'next'*

#### source_step *: Step*

<a id="presentstep"></a>

## Task steps

<a id="agentexecutionstep"></a>

### *class* wayflowcore.steps.agentexecutionstep.AgentExecutionStep(agent, caller_input_mode=None, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None, \_share_conversation=True)

Step that executes an agent. If given some outputs, it will ask the agent to return these outputs.
Otherwise, it will never exit the step and allows the user to ask questions to the agent.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, the input_descriptors will be automatically inferred
from the `custom_instruction` template of the `Agent`, with one input descriptor per variable in the template,
trying to detect the type of the variable based on how it is used in the template.
See [TemplateRenderingStep](#templaterenderingstep) for concrete examples on how descriptors are
extracted from text prompts.

If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
in particular using the new type instead of the detected one. If some of them are missing,
an error will be thrown at the instantiation of the `Agent`.

If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
they won’t be used during the execution of the step.

**Output descriptors**

By default, when `output_descriptors` is set to `None`, the step will have the same output descriptors
as its `Agent`. See [Agent](agent.md#agent) to learn more about how their output descriptors are computed.

If you provide a list of output descriptors, the step will prompt the `Agent` to gather and output
values that will match the expected output descriptors, which means it can either yield to the user or
finish the conversation by outputting the output values. If the `Agent` is not able to generate them,
the values will be filled with their default values if they are specified, or the default values
of their respective types, after the maximum amount of iterations of the `Agent` is reached.

* **Parameters:**
  * **agent** (`Union`[[`Agent`](agent.md#wayflowcore.agent.Agent), [`OciAgent`](agent.md#wayflowcore.ociagent.OciAgent), [`Swarm`](agent.md#wayflowcore.swarm.Swarm), [`ManagerWorkers`](agent.md#wayflowcore.managerworkers.ManagerWorkers)]) – Agent that will be used in the step.
  * **caller_input_mode** (`Optional`[[`CallerInputMode`](agent.md#wayflowcore.agent.CallerInputMode)]) – 

    Whether the agent is allowed to ask the user questions (CallerInputMode.ALWAYS) or not (CallerInputMode.NEVER).
    If set to NEVER, the step won’t be able to yield. Defaults to `None`, which means it will use the `caller_input_mode`
    of the underlying agent.

    #### WARNING
    This overrides `caller_input_mode` of the `agent` component.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – 

    Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.

    #### WARNING
    Changing this will change the behavior of the step. If not `None`, the `Agent` will be prompted
    to generate the expected outputs and the step will only return when the `Agent` submits values for
    all these outputs.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **\_share_conversation** (*bool*)

#### SEE ALSO
[`Agent`](agent.md#wayflowcore.agent.Agent)
: the agent class that will be run inside this step.

### Notes

Here are some guidelines to ensure the best performance of this step:

1. `custom_instruction` of the Agent: specify in it what the task is about. Don’t use phrasing of style “You are a helpful assistant …” because our tool calling template contains it. Only specify relevant information for your use-case
2. `caller_input_mode`: if `NEVER`, you might improve performance by reminding the model to only output a single function at a time and not to talk to the user

### Examples

To run this example, you need to install `duckduckgosearch` with `pip install duckduckgo-search`

```pycon
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.agent import Agent
>>> from wayflowcore.property import (
...     IntegerProperty,
...     Property,
...     StringProperty,
... )
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.steps import InputMessageStep
>>> from wayflowcore.steps.agentexecutionstep import AgentExecutionStep, CallerInputMode
>>> from langchain_community.tools import DuckDuckGoSearchRun  
>>> search_tool = DuckDuckGoSearchRun().as_tool()  
>>> agent = Agent(
...     llm=llm,
...     custom_instruction=(
...         "Your task is to gather the required information for the user: "
...         "creation_date, name, CEO, country"
...     ),
...     tools=[search_tool],
... )  
>>> flow = Flow.from_steps([
...     InputMessageStep("Which company are you interested in?"),
...     AgentExecutionStep(
...         agent=agent,
...         caller_input_mode=CallerInputMode.NEVER,
...         output_descriptors=[
...             IntegerProperty(
...                 name='creation_date',
...                 description='year when the company was founded',
...                 default_value=-1,
...             ),
...             StringProperty(
...                 name='name',
...                 description='official name of the company',
...                 default_value='',
...             ),
...             StringProperty(
...                 name='CEO',
...                 description='name of the CEO of the company',
...                 default_value='',
...             ),
...             StringProperty(
...                 name='country',
...                 description='country where the headquarters are based',
...                 default_value='',
...             )
...         ]
...     )
... ])  
>>> conv = flow.start_conversation()  
>>> status = conv.execute()  
>>> conv.append_user_message('Oracle')  
>>> status = conv.execute()  
>>> # status.output_values
>>> # {'name': 'Oracle', 'creation_date': 1977, 'CEO': 'Safra A. Catz', 'country': 'US'}
```

#### input_mapping *: Dict[str, str]*

#### *property* might_yield *: bool*

Indicates if the step might yield back to the user.
Might be the step directly, or one of the steps it calls.

#### output_mapping *: Dict[str, str]*

<a id="promptexecutionstep"></a>

### *class* wayflowcore.steps.promptexecutionstep.PromptExecutionStep(prompt_template, llm, generation_config=None, \_structured_generation_mode=StructuredGenerationMode.JSON_GENERATION, send_message=False, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to generate text using an LLM and a prompt template.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, the input_descriptors will be automatically inferred
from the `prompt_template`, with one input descriptor per variable in the template, trying to detect
the type of the variable based on how it is used in the template. See
[TemplateRenderingStep](#templaterenderingstep) for concrete examples on how descriptors are extracted
from text prompts.

If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
in particular using the new type instead of the detected one.
If some of them are missing, an error will be thrown at instantiation of the step.

If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
they won’t be used during the execution of the step.

**Output descriptors**

By default, when `output_descriptors` is set to `None`, this step will have a single output descriptor,
`PromptExecutionStep.OUTPUT`, type `StringProperty()`, which will be the raw text generated by the LLM.

If you provide a list of output descriptors, the `PromptExecutionStep` will use structured generation
to ensure generating all expected outputs with the right types. If the LLM is not able to generate them,
the values will be filled with their default values if they are specified, or the default values
of their respective types.

* **Parameters:**
  * **prompt_template** (`Union`[`str`, [`PromptTemplate`](prompttemplate.md#wayflowcore.templates.template.PromptTemplate)]) – 

    Jinja str prompt template to use for generation. See docstring/documentation of the `TemplateRenderingStep`
    for concrete examples of how to work with jinja prompts in WayFlow.
    Can also be a fully defined PromptTemplate, in which case the arguments of this step will be matched to
    the ones of the prompt to make sure they are compatible.
    If the PromptTemplate includes a chat history placeholder, this will be populated
    automatically by step with the agent, user and tool messages in the conversation.

    #### WARNING
    Note that not all LLMs support native structured generation (which is the default
    structured generation mode when simply configuring a `PromptTemplate` with a response
    format). For such cases, or to improve the reasoning performed by the model before
    generating the structured output, you can use the helper method
    `adapt_prompt_template_for_json_structured_generation` to quickly get started with
    JSON structured generation. For more complex use-cases, you can check out the
    [PromptTemplate how-to guide](../howtoguides/howto_prompttemplate.md#top-howtoprompttemplates).
  * **llm** ([`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)) – Model that is used when executing the step.
  * **generation_config** (`Optional`[[`LlmGenerationConfig`](llmmodels.md#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig)]) – Optional generation arguments for the LLM generation in this step. See `LlmGenerationConfig` for available parameters.
  * **send_message** (`bool`) – Determines whether to send the generated content to the current message list or not. Note that message is still streamed if streaming is not disabled.
    By default, the content is only exposed as an output.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – 

    Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.

    #### WARNING
    If not `None` and doesn’t have a single `StringProperty` descriptor, the step will perform
    structured generation.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_structured_generation_mode** ([*StructuredGenerationMode*](#wayflowcore.steps.promptexecutionstep.StructuredGenerationMode))
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Example

```pycon
>>> from wayflowcore.steps import PromptExecutionStep
>>> from wayflowcore.flowhelpers import create_single_step_flow
>>> from wayflowcore.models.llmmodelfactory import LlmModelFactory
>>> VLLM_CONFIG = {"model_type": "vllm", "host_port": LLAMA70B_API_ENDPOINT, "model_id": "/storage/models/Llama-3.3-70B-Instruct",}
>>> llm = LlmModelFactory.from_config(VLLM_CONFIG)
>>> step = PromptExecutionStep(
...     prompt_template="What is the capital of {{ country }} The answer is among {% for city in cities %}- {{city}}\n{% endfor %}",
...     llm=llm,
... )
>>> [s.name for s in step.input_descriptors]
['country', 'cities']
```

```pycon
>>> assistant = create_single_step_flow(step, 'step')
>>> conversation = assistant.start_conversation(inputs={'country': 'Switzerland', 'cities': ['bern', 'basel', 'zurich']})
>>> status = conversation.execute()
>>> len(status.output_values[PromptExecutionStep.OUTPUT]) > 0
True
```

#### JSON_CONSTRAINED_GENERATION_PROMPT *= 'At the end of your answer, finish with <final_answer>$your_answer$</final_answer> with $your_answer$ being a properly formatted json that is valid against this JSON schema:'*

Additional prompt that is appended to the prompt to ask the LLM to generate a json that respects a particular JSON Schema

* **Type:**
  str

#### OUTPUT *= 'output'*

Output key for the output generated by the LLM.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="templaterenderingstep"></a>

### *class* wayflowcore.steps.templaterenderingstep.TemplateRenderingStep(template, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to render a template given some inputs.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, the input_descriptors will be automatically inferred
from the `template`, with one input descriptor per variable in the template,
trying to detect the type of the variable based on how it is used in the template.
See below for concrete examples on how descriptors are extracted from text prompts.

If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
in particular using the new type instead of the detected one.
If some of them are missing, an error will be thrown at instantiation of the step.

If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
they won’t be used during the execution of the step.

**Output descriptors**

This step has one output descriptor, `TemplateRenderingStep.OUTPUT`, of type `StringProperty()`, that
is the text rendered by the step.

* **Parameters:**
  * **template** (`str`) – jinja template to format. Any jinja variable appearing in this template will be a required input of
    this step. See the example section for concrete examples with WayFlow, or check the reference of
    jinja2 at [https://jinja.palletsprojects.com/en/stable/templates](https://jinja.palletsprojects.com/en/stable/templates).
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

We provide here some basic examples to work with templates in WayFlow. Any wayflowcore step that takes
jinja2 templates will automatically detect jinja2 variables and add them as the step inputs.

**1) Simple variable in a template**

To add a variable to a template, you just need to wrap its named between double brackets:

```pycon
>>> from wayflowcore.steps import TemplateRenderingStep
>>> TemplateRenderingStep.format_template(
...     template="What is the capital of {{country}}?",
...     inputs={'country': 'Switzerland'},
... )
'What is the capital of Switzerland?'
```

With simple brackets, the variable will be of type string. The variable will be a required
input of the step.

**2) More complex variable in a template**

In many cases, we want to format list of objects inside a template. To do this, we can use the for loop syntax
of jinja2:

```pycon
>>> TemplateRenderingStep.format_template(
...     template=(
...         "What is the largest capital between "
...         "{% for country in countries %}"
...         "{{country}}{{ ' and ' if not loop.last }}"
...         "{% endfor %}?"
...     ),
...     inputs={'countries': ['Switzerland', 'France']},
... )
'What is the largest capital between Switzerland and France?'
```

Here, the detected variable will be countries and its type will be any. You can also loop with list of dicts
or objects (see more at [https://jinja.palletsprojects.com/en/stable/templates/#for](https://jinja.palletsprojects.com/en/stable/templates/#for)).
The variable will be a required input of the step.

**3) Optional variables in a template**

Sometimes, you might want to change the template depending on whether a value exist or not (for example,
to include feedback when you generate with an LLM, but you don’t have any feedback at first). In this case,
you can use the if jinja syntax as follows:

```pycon
>>> TemplateRenderingStep.format_template(
...     template="{% if visited %}Welcome back{% else %}Welcome{% endif %}",
...     inputs={'visited': None},
... )
'Welcome'
>>> TemplateRenderingStep.format_template(
...     template="{% if visited %}Welcome back{% else %}Welcome{% endif %}",
...     inputs={'visited': 'something'},
... )
'Welcome back'
```

In this case, the detected variable is of type any and optional and will default to None
if needed in the step.

#### OUTPUT *= 'output'*

Output key for the rendered template.

* **Type:**
  str

#### *classmethod* format_template(template, inputs)

* **Return type:**
  `str`
* **Parameters:**
  * **template** (*str*)
  * **inputs** (*Dict* *[**str* *,* *Any* *]*)

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="toolexecutionstep"></a>

### *class* wayflowcore.steps.toolexecutionstep.ToolExecutionStep(tool, raise_exceptions=True, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to execute a WayFlow tool. This step does not require the use of LLMs.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, the input descriptors will be inferred from
the arguments of the tool, with one input descriptor per argument.

**Output descriptors**

By default, when `output_descriptors` is set to `None`, this step will have the same output descriptors
as the tool. By default, if the tool has a single output, the name will be `ToolExecutionStep.TOOL_OUTPUT`,
of the same type as the return type of the tool, which represents the result returned by the tool.

If you provide a list of output descriptors, each descriptor passed will override the automatically
detected one, in particular using the new type instead of the detected one.
If some of them are missing, an error will be thrown at instantiation of the step.

If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
they won’t be used during the execution of the step.

* **Parameters:**
  * **tool** ([`Tool`](tools.md#wayflowcore.tools.tools.Tool)) – The tool to be executed.
  * **raise_exceptions** (`bool`) – Whether to raise or not exceptions raised by the tool. If `False`, it will put the error message as the result
    of the tool if the tool output type is string.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.flowhelpers import create_single_step_flow
>>> from wayflowcore.steps import ToolExecutionStep
>>> from wayflowcore.tools import ServerTool
>>> from wayflowcore.property import FloatProperty
>>>
>>> square_root_tool = ServerTool(
...     name="compute_square_root",
...     description="Computes the square root of a number",
...     input_descriptors=[FloatProperty(name="x", description="The number to use")],
...     func=lambda x: x**0.5,
...     output_descriptors=[FloatProperty()]
... )
>>> step = ToolExecutionStep(tool=square_root_tool)
>>> assistant = create_single_step_flow(step)
>>> conversation = assistant.start_conversation(inputs={"x": 123456789.0})
>>> status = conversation.execute()
>>> print(status.output_values)
{'tool_output': 11111.111060555555}
```

#### TOOL_OUTPUT *= 'tool_output'*

Output key for the result obtained from executing the tool.

* **Type:**
  str

#### TOOL_REQUEST *= 'tool_request'*

ToolRequest for uuid of the tool request (useful when using tools requiring confirmation)

* **Type:**
  str

#### TOOL_REQUEST_UUID *= 'tool_request_uuid'*

Output key for uuid of the tool request (useful when using `ClientTool` and tools with confirmation)

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### *property* might_yield *: bool*

Indicates if the step might yield back to the user.
Might be the step directly, or one of the steps it calls.

#### output_mapping *: Dict[str, str]*

#### *property* supports_dict_io_with_non_str_keys *: bool*

Indicates if the step can accept/return dictionaries with
keys that are not strings as IO.

<a id="extractvaluefromjsonstep"></a>

### *class* wayflowcore.steps.textextractionstep.extractvaluefromjsonstep.ExtractValueFromJsonStep(output_values, llm=None, retry=False, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to extract information from a raw json text. It will first remove any ````` or ````json` delimiters, then load the json,
and outputs all extracted values for which a jq expression was given.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

This step has a single input descriptor:

* `ExtractValueFromJsonStep.TEXT`: `StringProperty()`, text to extract the values from.

**Output descriptors**

This step can have several output descriptors, one per key in the `output_values` mapping. The type will be `AnyProperty()`.

* **Parameters:**
  * **output_values** (`Dict`[`Union`[`str`, [`Property`](#wayflowcore.property.Property)], `str`]) – The keys are either output names of this step or complete `Property`. The values are the jq formulas to extract them from the json detected
  * **llm** (`Optional`[[`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)]) – LLM to correct the json with. By default, no LLM-based correction is applied.
  * **retry** (`bool`) – If true, and there was a problem parsing the json, this step will try again to fix it. Defaults to False.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.steps import ExtractValueFromJsonStep
>>> from wayflowcore.flowhelpers import create_single_step_flow
```

To match some part of the llm output, you might use some regex like:

```pycon
>>> step = ExtractValueFromJsonStep(
...     output_values={
...         'thought': '.thought',
...         'name': '.action.function_name',
...     },
... )
>>> assistant = create_single_step_flow(step, 'step')
>>> conversation = assistant.start_conversation(inputs={ExtractValueFromJsonStep.TEXT: '{"thought":"I should call a tool", "action": {"function_name":"some_tool", "function_args": {}}}'})
>>> status = conversation.execute()
>>> status.output_values['name'] == "some_tool"
True
>>> status.output_values['thought'] == "I should call a tool"
True
```

#### TEXT *= 'text'*

Input key for the raw json text to be parsed.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="regexextractionstep"></a>

### *class* wayflowcore.steps.textextractionstep.regexextractionstep.RegexExtractionStep(regex_pattern, return_first_match_only=True, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to extract information from a raw text using a regular expression (regex). The step returns the first matched text in the regex.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

This step has a single input descriptor:

* `RegexExtractionStep.TEXT`: `StringProperty()`, text on which to use the regex pattern

**Output descriptors**

This step has a single output descriptor:

* `RegexExtractionStep.OUTPUT`: `StringProperty()` / `ListProperty(StringProperty())`, the matched text / list of texts if `return_first_match_only` is `True`

* **Parameters:**
  * **regex_pattern** (`Union`[`str`, [`RegexPattern`](prompttemplate.md#wayflowcore.outputparser.RegexPattern)]) – Regex pattern to match the output(s).
  * **return_first_match_only** (`bool`) – Whether to return a single match (if several matches are found) or all the matches as a list.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.steps import RegexExtractionStep
```

To match some part of the llm output, you might use some regex like:

```pycon
>>> step = RegexExtractionStep(
...     regex_pattern=r"Thought: (.*)\nAction:",
... ) 
```

to extract from a Thought: … Action: … REACT pattern. It will return only the first match.

To match all emails present in the text, use for example:

```pycon
>>> step = RegexExtractionStep(
...     regex_pattern=r"\b\w+@\w+\.\w+",
...     return_first_match_only=False,
... ) 
```

and it will return a list of all emails matched in the text.

#### OUTPUT *= 'output'*

Output key for the result from the regex parsing.

* **Type:**
  str

#### TEXT *= 'text'*

Input key for the raw text to be parsed with regex.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

### *class* wayflowcore.steps.promptexecutionstep.StructuredGenerationMode(value)

Method to perform constrained generation

#### CONSTRAINED_GENERATION *= 'constrained_generation'*

Mode that uses constrained generation to perform structured generation. The LLM will be forced to answer directly and won’t be able to reason first for most models, which might improve the latency but reduce accuracy.

#### JSON_GENERATION *= 'json_generation'*

Mode that adds to the prompt the json_schema and asks to generate a JSON. The raw answer is then parsed using an `ExtractValueFromJsonStep`. With this mode, the LLM will be able to reason first before giving its final output, increasing the accuracy but worsening the latency.

#### TOOL_GENERATION *= 'tool_generation'*

Mode that uses a generate tool that has expected outputs as arguments. The llm answers will be a tool request that is parsed into the expected outputs. Depending on the model, it might be able to reason first, increasing the accuracy but worsening the latency.

<a id="datastoresteps"></a>

### Datastore tasks

#### On the transactional consistency of datastore tasks
When executing Datastore tasks in a flow, each step will execute one
atomic operation on the datastore (that is, one transaction in
database-backed datastores). Therefore, rolling-back a sequence of
operations in case one or more steps fail during execution is not
supported. Please keep this in mind when designing flows using these
steps.

<a id="datastoreliststep"></a>

### *class* wayflowcore.steps.datastoresteps.DatastoreListStep(datastore, collection_name, where=None, limit=None, unpack_single_entity_from_list=False, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step that can list entities in a `Datastore`.

Initialize a new `DatastoreListStep`.

#### NOTE
A step has input and output descriptors, describing what values
the step requires to run and what values it produces.

**Input descriptors**

By default, this step has no input descriptor.
However, the `collection_name` and keys and values in the `where`
dictionary can be parametrized with jinja-style variables.
By default, the inferred input descriptors will be of type string,
but this can be overridden with the `input_descriptors` parameter.

**Output descriptors**

This step has a single output descriptor: `DatastoreCreateStep.ENTITIES`,
a list of dictionaries representing the retrieved entities.

* **Parameters:**
  * **datastore** ([`Datastore`](datastores.md#wayflowcore.datastore.Datastore)) – Datastore this step operates on
  * **collection_name** (`str`) – Collection in the datastore manipulated by this step. Can be
    parametrized using jinja variables, and the resulting input
    descriptors will be inferred by the step.
  * **where** (`Optional`[`Dict`[`str`, `Any`]]) – Filtering to be applied when retrieving entities. The dictionary
    is composed of property name and value pairs to filter by
    with exact matches. Only entities matching all conditions in
    the dictionary will be retrieved. For example, {“name”: “Fido”,
    “breed”: “Golden Retriever”} will match all `Golden Retriever`
    dogs named `Fido`.
  * **limit** (`Optional`[`int`]) – Maximum number of entities to list. By default retrieves all entities.
  * **unpack_single_entity_from_list** (`Optional`[`bool`]) – When limit is set to 1, one may optionally decide to unpack
    the single entity in the list and only return a the
    dictionary representing the retrieved entity. This can be
    useful when, e.g., reading a single entity by its ID.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.datastore import Entity
>>> from wayflowcore.datastore.inmemory import InMemoryDatastore
>>> from wayflowcore.flowhelpers import create_single_step_flow
>>> from wayflowcore.property import StringProperty, IntegerProperty
>>> from wayflowcore.steps.datastoresteps import DatastoreListStep
```

To use this step, you need first need to create a `Datastore`. Here, we populate it with dummy data:

```pycon
>>> document = Entity(
...     properties={ "id": IntegerProperty(), "content": StringProperty(default_value="Empty...") }
... )
>>> datastore = InMemoryDatastore({"documents": document})
>>> dummy_data = [
...     {"id": 2, "content": "The rat the cat the dog bit chased escaped."},
...     {"id": 3, "content": "More people have been to Russia than I have."}
... ]
>>> datastore.create("documents", dummy_data)
[{'content': 'The rat the cat the dog bit chased escaped.', 'id': 2}, {'content': 'More people have been to Russia than I have.', 'id': 3}]
```

Now you can use this `Datastore` in a `DatastoreListStep`

```pycon
>>> datastore_list_flow = create_single_step_flow(DatastoreListStep(datastore, "documents"))
>>> conversation = datastore_list_flow.start_conversation()
>>> execution_status = conversation.execute()
>>> execution_status.output_values
{'entities': [{'content': 'The rat the cat the dog bit chased escaped.', 'id': 2}, {'content': 'More people have been to Russia than I have.', 'id': 3}]}
```

You can parametrize inputs to the step if required; this is done via variable templating.
Other configurations allow you to control the size and type of the output. Note that by
default, all variables you define here are assumed to be of type string; specify the exact
type you need via the input_descriptors parameter:

```pycon
>>> datastore_list_flow = create_single_step_flow(
...     DatastoreListStep(
...         datastore,
...         collection_name="{{entity_to_list}}",
...         where={"id": "{{target_id}}"},
...         limit=1,
...         unpack_single_entity_from_list=True,
...         input_descriptors=[IntegerProperty("target_id")]
...     )
... )
>>> conversation = datastore_list_flow.start_conversation({"entity_to_list": "documents", "target_id": 2})
>>> execution_status = conversation.execute()
>>> execution_status.output_values
{'entities': {'content': 'The rat the cat the dog bit chased escaped.', 'id': 2}}
```

#### ENTITIES *= 'entities'*

Output key for the entities listed by this step.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="datastorecreatestep"></a>

### *class* wayflowcore.steps.datastoresteps.DatastoreCreateStep(datastore, collection_name, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step that can create a new entity in a `Datastore`.

Initialize a new `DatastoreCreateStep`.

#### NOTE
A step has input and output descriptors, describing what values
the step requires to run and what values it produces.

**Input descriptors**

By default, this step has a single input descriptor, the new
entity object to be created (`DatastoreCreateStep.ENTITY`).
Additionally, the `collection_name` parameter may contain
jinja-style variables that can be used to dynamically configure
which entity is being created by the step.

**Output descriptors**

This step has a single output descriptor: `DatastoreCreateStep.CREATED_ENTITY`,
a dictionary representing the newly created entity

* **Parameters:**
  * **datastore** ([`Datastore`](datastores.md#wayflowcore.datastore.Datastore)) – Datastore this step operates on
  * **collection_name** (`str`) – Collection in the datastore manipulated by this step. Can be
    parametrized using jinja variables, and the resulting input
    descriptors will be inferred by the step.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.datastore import Entity
>>> from wayflowcore.datastore.inmemory import InMemoryDatastore
>>> from wayflowcore.flowhelpers import create_single_step_flow
>>> from wayflowcore.property import StringProperty, IntegerProperty
>>> from wayflowcore.steps.datastoresteps import DatastoreCreateStep
```

To use this step, you need first need to create a `Datastore`:

```pycon
>>> document = Entity(
...     properties={ "id": IntegerProperty(), "content": StringProperty(default_value="Empty...") }
... )
>>> datastore = InMemoryDatastore({"documents": document})
```

Now you can use this `Datastore` in a `DatastoreCreateStep`

```pycon
>>> datastore_create_flow = create_single_step_flow(DatastoreCreateStep(datastore, "documents"))
>>> conversation = datastore_create_flow.start_conversation({"entity": {'content': 'The rat the cat the dog bit chased escaped.', 'id': 0}})
>>> execution_status = conversation.execute()
```

Since not all properties of documents are required, we can let the Datastore fill in the rest:

```pycon
>>> datastore_create_flow = create_single_step_flow(DatastoreCreateStep(datastore, "documents"))
>>> conversation = datastore_create_flow.start_conversation({"entity": {'id': 1}})
>>> execution_status = conversation.execute()
```

You can then finally verify that the entities were indeed created:

```pycon
>>> datastore.list("documents")
[{'content': 'The rat the cat the dog bit chased escaped.', 'id': 0}, {'content': 'Empty...', 'id': 1}]
```

#### CREATED_ENTITY *= 'created_entity'*

Output key for the newly created entity.

* **Type:**
  str

#### ENTITY *= 'entity'*

Input key for the entity to be created.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="datastoreupdatestep"></a>

### *class* wayflowcore.steps.datastoresteps.DatastoreUpdateStep(datastore, collection_name, where, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step that can update entities in a `Datastore`.

Initialize a new `DatastoreUpdateStep`.

#### NOTE
A step has input and output descriptors, describing what values
the step requires to run and what values it produces.

**Input descriptors**

By default, this step has a single input descriptor, the
dictionary of updates to be made to the entities
(`DatastoreUpdateStep.UPDATE`).
Additionally, the `collection_name` and keys and values in the `where`
dictionary can be parametrized with jinja-style variables.
Use this construct sparingly, as there is no special validation
performed on update.
By default, the inferred input descriptors will be of type string,
but this can be overridden with the `input_descriptors` parameter.

**Output descriptors**

This step has a single output descriptor: `DatastoreCreateStep.ENTITIES`,
a list of dictionaries representing the newly updated entities.

* **Parameters:**
  * **datastore** ([`Datastore`](datastores.md#wayflowcore.datastore.Datastore)) – Datastore this step operates on
  * **collection_name** (`str`) – Collection in the datastore manipulated by this step. Can be
    parametrized using jinja variables, and the resulting input
    descriptors will be inferred by the step.
  * **where** (`Dict`[`str`, `Any`]) – Filtering to be applied when updating entities. The dictionary
    is composed of property name and value pairs to filter by
    with exact matches. Only entities matching all conditions in
    the dictionary will be updated. For example, {“name”: “Fido”,
    “breed”: “Golden Retriever”} will match all `Golden Retriever`
    dogs with name `Fido`.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.datastore import Entity
>>> from wayflowcore.datastore.inmemory import InMemoryDatastore
>>> from wayflowcore.flowhelpers import create_single_step_flow
>>> from wayflowcore.property import StringProperty, IntegerProperty
>>> from wayflowcore.steps.datastoresteps import DatastoreUpdateStep
```

To use this step, you need first need to create a `Datastore`. Here, we populate it with dummy data:

```pycon
>>> document = Entity(
...     properties={ "id": IntegerProperty(), "content": StringProperty(default_value="Empty...") }
... )
>>> datastore = InMemoryDatastore({"documents": document})
>>> dummy_data = [
...     {"id": 2, "content": "The rat the cat the dog bit chased escaped."},
...     {"id": 3, "content": "More people have been to Russia than I have."}
... ]
>>> datastore.create("documents", dummy_data)
[{'content': 'The rat the cat the dog bit chased escaped.', 'id': 2}, {'content': 'More people have been to Russia than I have.', 'id': 3}]
```

Now you can use this `Datastore` in a `DatastoreUpdateStep`

```pycon
>>> datastore_update_flow = create_single_step_flow(DatastoreUpdateStep(datastore, "documents", where={"id": 2}))
>>> conversation = datastore_update_flow.start_conversation({"update": {"content": "A brand new sentence"}})
>>> execution_status = conversation.execute()
```

The output of this step will provide all the entities that were updated during the execution:

```pycon
>>> execution_status.output_values
{'entities': [{'content': 'A brand new sentence', 'id': 2}]}
```

You can parametrize inputs to the step if required; this is done via variable templating.
Note that by default, all variables you define here are assumed to be of type string; specify
the exact type you need via the input_descriptors parameter:

```pycon
>>> datastore_update_flow = create_single_step_flow(
...     DatastoreUpdateStep(
...         datastore,
...         collection_name="{{entity_to_list}}",
...         where={"id": "{{target_id}}"},
...         input_descriptors=[IntegerProperty("target_id")]
...     )
... )
>>> conversation = datastore_update_flow.start_conversation({
...     "entity_to_list": "documents",
...     "target_id": 2,
...     "update": {"content": "Yet another content"},
... })
>>> execution_status = conversation.execute()
>>> execution_status.output_values
{'entities': [{'content': 'Yet another content', 'id': 2}]}
```

#### ENTITIES *= 'entities'*

Output key for the entities listed by this step.

* **Type:**
  str

#### UPDATE *= 'update'*

Input key for the dictionary of the updates to be made.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="datastoredeletestep"></a>

### *class* wayflowcore.steps.datastoresteps.DatastoreDeleteStep(datastore, collection_name, where, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step that can delete entities in a `Datastore`.

Initialize a new `DatastoreDeleteStep`.

#### NOTE
A step has input and output descriptors, describing what values
the step requires to run and what values it produces.

**Input descriptors**

By default, this step has no input descriptor.
However, the `collection_name` and keys and values in the `where`
dictionary can be parametrized with jinja-style variables.
Use this construct sparingly, as there is no special validation
performed on delete. By default, the inferred input descriptors
will be of type string, but this can be overridden with the
`input_descriptors` parameter.

**Output descriptors**

This step has no output descriptors.

* **Parameters:**
  * **datastore** ([`Datastore`](datastores.md#wayflowcore.datastore.Datastore)) – Datastore this step operates on
  * **collection_name** (`str`) – Collection in the datastore manipulated by this step. Can be
    parametrized using jinja variables, and the resulting input
    descriptors will be inferred by the step.
  * **where** (`Dict`[`str`, `Any`]) – Filtering to be applied when deleting entities. The dictionary
    is composed of property name and value pairs to filter by
    with exact matches. Only entities matching all conditions in
    the dictionary will be deleted. For example, {“name”: “Fido”,
    “breed”: “Golden Retriever”} will match all `Golden Retriever`
    dogs named `Fido`.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_descriptors** (*List* *[*[*Property*](#wayflowcore.property.Property) *]*  *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.datastore import Entity
>>> from wayflowcore.datastore.inmemory import InMemoryDatastore
>>> from wayflowcore.flowhelpers import create_single_step_flow
>>> from wayflowcore.property import StringProperty, IntegerProperty
>>> from wayflowcore.steps.datastoresteps import DatastoreDeleteStep
```

To use this step, you need first need to create a `Datastore`. Here, we populate it with dummy data:

```pycon
>>> document = Entity(
...     properties={ "id": IntegerProperty(), "content": StringProperty(default_value="Empty...") }
... )
>>> datastore = InMemoryDatastore({"documents": document})
>>> dummy_data = [
...     {"id": 2, "content": "The rat the cat the dog bit chased escaped."},
...     {"id": 3, "content": "More people have been to Russia than I have."}
... ]
>>> datastore.create("documents", dummy_data)
[{'content': 'The rat the cat the dog bit chased escaped.', 'id': 2}, {'content': 'More people have been to Russia than I have.', 'id': 3}]
```

Now you can use this `Datastore` in a `DatastoreDeleteStep`

```pycon
>>> datastore_delete_flow = create_single_step_flow(DatastoreDeleteStep(datastore, "documents", where={"id": 2}))
>>> conversation = datastore_delete_flow.start_conversation()
>>> execution_status = conversation.execute()
```

You can then verify that the entity was indeed deleted:

```pycon
>>> datastore.list("documents")
[{'content': 'More people have been to Russia than I have.', 'id': 3}]
```

You can parametrize inputs to the step if required; this is done via variable templating.
Note that by default, all variables you define here are assumed to be of type string; specify
the exact type you need via the input_descriptors parameter:

```pycon
>>> datastore_delete_flow = create_single_step_flow(
...     DatastoreDeleteStep(
...         datastore,
...         collection_name="{{entity_to_list}}",
...         where={"id": "{{target_id}}"},
...         input_descriptors=[IntegerProperty("target_id")]
...     )
... )
>>> conversation = datastore_delete_flow.start_conversation(
...     {
...         "entity_to_list": "documents",
...         "target_id": 3,
...     }
... )
>>> execution_status = conversation.execute()
>>> datastore.list("documents")
[]
```

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="datastorequerystep"></a>

### *class* wayflowcore.steps.datastoresteps.DatastoreQueryStep(datastore, query, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to execute a parameterized SQL query on a relational `Datastore`
(`OracleDatabaseDatastore`), that supports SQL queries (the specific
SQL dialect depends on the database backing the datastore).

This step enables safe, flexible querying of datastores using
parameterized SQL.  Queries must use bind variables (e.g., :customer_id).
String templating within queries is forbidden for security reasons;
any such usage raises an error.

Initialize a new `DatastoreQueryStep`.

#### NOTE
A step has input and output descriptors, describing what values
the step requires to run and what values it produces.

**Input descriptors**

By default, this step has a single input descriptor.
`bind_variables` is a dictionary mapping variable names in the
SQL query to their value at execution time.

**Output descriptors**

This step has a single output descriptor: `DatastoreQueryStep.RESULT`,
the query result rows, with each row represented as a dictionary
mapping column names to their values.

#### WARNING
While the input descriptor maps the bound variable name to a
type AnyProperty to offer maximum flexibility, runtime
validation will be performed to assess if the provided values
are valid bind variables, and whether they match the expected
type in the query.
You may override the default input descriptor to specialize
it to the bind variables in your query, to benefit from
additional static validation (see example below).

* **Parameters:**
  * **datastore** ([`RelationalDatastore`](datastores.md#wayflowcore.datastore._relational.RelationalDatastore)) – The `Datastore` to execute the query against.
  * **query** (`str`) – 

    SQL query string using bind variables (e.g., `SELECT * FROM table WHERE id = :val`).
    String templating/interpolation is forbidden and will raise an exception.

    #### IMPORTANT
    The provided query will be executed with the session user’s privileges
    (the user configured in the datastore’s connection config). SQL queries should be
    designed carefully, to ensure their correctness prior to execution.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input
    descriptors automatically.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically
    using its static configuration in a best effort manner.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in
    the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in
    the conversation input/output dictionary.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Notes

- Bind variable values are passed in the input as a dictionary with key “bind_variables”.
- Output is always a list of dictionaries (row-oriented).

### Examples

```pycon
>>> from wayflowcore.datastore import OracleDatabaseDatastore, MTlsOracleDatabaseConnectionConfig
>>> from wayflowcore.steps.datastoresteps import DatastoreQueryStep
>>> from wayflowcore.datastore import Entity
>>> from wayflowcore.flowhelpers import create_single_step_flow
>>> from wayflowcore.property import FloatProperty, ObjectProperty, StringProperty, IntegerProperty
```

We start by defining the entity of interest in the datastore. We assume here that an employees table
already exists in the target database:

```pycon
>>> employees = Entity(
...     properties={
...         "ID": IntegerProperty(),
...         "name": StringProperty(),
...         "email": StringProperty(),
...         "department_name": StringProperty(),
...         "department_area": StringProperty(),
...         "salary": FloatProperty(default_value=0.1),
...     },
... )
```

Next, we can connect to the Oracle Database. For connection configuration options see
`OracleDatabaseConnectionConfig`:

```pycon
>>> datastore = OracleDatabaseDatastore({"employees": employees}, database_connection_config)
```

We can create the `DatastoreQueryStep` to execute a query structure that cannot
be modelled, for example, by a `DatastoreListStep`:

```pycon
>>> datastore_query_flow = create_single_step_flow(
...     DatastoreQueryStep(
...         datastore,
...         "SELECT email, salary FROM employees WHERE department_name = :department OR salary < :salary"
...     )
... )
>>> conversation = datastore_query_flow.start_conversation({"bind_variables": {"salary": 100000, "department": "reception"}})
>>> execution_status = conversation.execute()
>>> execution_status.output_values
{'result': [{'email': 'pam@dudemuffin.com', 'salary': 95000.0}]}
```

To ensure the bind variables will not create any issues at runtime, we may specialize
the default input descriptor to exactly match the types and values of bound variables in
the query:

```pycon
>>> datastore_query_flow = create_single_step_flow(
...     DatastoreQueryStep(
...         testing_oracle_data_store_with_data,
...         "SELECT email, salary FROM employees WHERE department_name = :depname OR salary < :salary",
...         input_descriptors=[
...             ObjectProperty(
...                 "bind_variables",
...                 properties={
...                     "salary": FloatProperty(),
...                     "depname": StringProperty()
...                 }
...             )
...         ]
...     )
... )
```

Inputs to this step can now be validated before the step is executed:

```pycon
>>> conversation = datastore_query_flow.start_conversation(
...     {"bind_variables": {"salary": "1", "depname": "sales"}}
... )  
Traceback (most recent call last):
    ...
TypeError: The input passed: `{'salary': '1', 'depname': 'sales'}` of type `dict` is not of the expected type ...
```

#### RESULT *= 'result'*

Output key for the query result (list of dictionaries, one per row).

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

## IO steps

<a id="inputmessagestep"></a>

### *class* wayflowcore.steps.inputmessagestep.InputMessageStep(message_template, rephrase=False, llm=None, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to get an input from the conversation with the user.

The input step prints a message to the user, asks for an answer and returns it as
an output of the step. It places both messages in the messages list so that it is
possible to visualize the conversation, but also returns the user input as an output.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, the input_descriptors will be automatically inferred
from the `message_template`, with one input descriptor per variable in the template,
trying to detect the type of the variable based on how it is used in the template.
See [TemplateRenderingStep](#templaterenderingstep) for concrete examples on how descriptors are
extracted from text prompts.

If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
in particular using the new type instead of the detected one.
If some of them are missing, an error will be thrown at instantiation of the step.

If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
they won’t be used during the execution of the step.

**Output descriptors**

By default, this step has one single output descriptor named `InputMessageStep.USER_PROVIDED_INPUT`, of type
`StringProperty()`, which will be the message generated by the step.

* **Parameters:**
  * **message_template** (`Optional`[`str`]) – The message template to use to ask for more information to the user, in jinja format.
    See docstring/documentation of the `TemplateRenderingStep`
    for concrete examples of how to work with jinja prompts in WayFlow.
    If None, no message is sent to the user.
  * **rephrase** (`bool`) – Whether to rephrase the message. Requires `llm` to be set.
  * **llm** (`Optional`[[`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)]) – LLM to use to rephrase the message. Only required if `rephrase=True`.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve them automatically
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### SEE ALSO
[`OutputMessageStep`](#wayflowcore.steps.outputmessagestep.OutputMessageStep)
: Step to output a message to the chat history.

### Examples

```pycon
>>> from wayflowcore.flowhelpers import create_single_step_flow
>>> from wayflowcore.steps import InputMessageStep
>>> step = InputMessageStep(message_template="Please enter a message")
>>> assistant = create_single_step_flow(step)
>>> conversation = assistant.start_conversation()
>>> status = conversation.execute() # Yielding back to the user
>>> conversation.append_user_message("This is a user message.")
>>> status = conversation.execute()
>>> status.output_values
{'user_provided_input': 'This is a user message.'}
```

#### USER_PROVIDED_INPUT *= 'user_provided_input'*

Output key for the input text provided by the user.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### *property* might_yield *: bool*

Indicates that this step might yield (it always does).

#### output_mapping *: Dict[str, str]*

<a id="outputmessagestep"></a>

### *class* wayflowcore.steps.outputmessagestep.OutputMessageStep(message_template='{{ message }}', message_type=MessageType.AGENT, rephrase=False, llm=None, expose_message_as_output=True, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to output a message to the chat history.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, the input_descriptors will be automatically inferred
from the `message_template`, with one input descriptor per variable in the template,
trying to detect the type of the variable based on how it is used in the template.
See [TemplateRenderingStep](#templaterenderingstep) for concrete examples on how descriptors are
extracted from text prompts.

If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
in particular using the new type instead of the detected one.
If some of them are missing, an error will be thrown at instantiation of the step.

If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
they won’t be used during the execution of the step.

**Output descriptors**

By default, this step has one single output descriptor named `OutputMessageStep.OUTPUT`, of type
`StringProperty()`, which will be the message generated by the step.

* **Parameters:**
  * **message_template** (`str`) – Jinja str prompt template to use to output a message. See docstring/documentation of
    the `TemplateRenderingStep` for concrete examples of how to work with jinja prompts
    in WayFlow. By default the template is `{{ message }}`.
  * **message_type** ([`MessageType`](conversation.md#wayflowcore.messagelist.MessageType)) – Message type of the message added to the message history.
  * **rephrase** (`bool`) – Whether to rephrase the message. Requires `llm` to be set.
  * **llm** (`Optional`[[`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)]) – LLM to use to rephrase the message. Only required if `rephrase=True`.
    Whether to rephrase the message. Requires `llms` to be set.
  * **expose_message_as_output** (`bool`) – Whether the message generated by this step should appear among the output descriptors
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### SEE ALSO
[`InputMessageStep`](#wayflowcore.steps.inputmessagestep.InputMessageStep)
: Step to get an input from the conversation with the user.

### Examples

```pycon
>>> from wayflowcore.flowhelpers import create_single_step_flow
>>> from wayflowcore.steps import OutputMessageStep
>>> step = OutputMessageStep(message_template="The user message is `{{user_message}}`")
>>> assistant = create_single_step_flow(step)
>>> conversation = assistant.start_conversation(inputs={"user_message": "Hello world!"})
>>> status = conversation.execute()
>>> status.output_values
{'output_message': 'The user message is `Hello world!`'}
```

#### OUTPUT *= 'output_message'*

Output key for the output message generated by the `OutputMessageStep`.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="getchathistorystep"></a>

### *class* wayflowcore.steps.getchathistorystep.GetChatHistoryStep(n=10, which_messages=MessageSlice.LAST_MESSAGES, offset=0, message_types=(MessageType.USER, MessageType.AGENT), output_template='', input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to get messages from the messages list e.g. last 4 messages and return it as output.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

This step has no input descriptors.

**Output descriptors**

This step has a single output descriptor:

* `GetChatHistoryStep.CHAT_HISTORY`: the chat history extract from the conversation, type is either `StringProperty()` or `ListProperty(item_type=AnyProperty())` if `output_template` is `None`.

* **Parameters:**
  * **n** (`int`) – Number of messages to retrieve.
  * **which_messages** ([`MessageSlice`](#wayflowcore.steps.getchathistorystep.MessageSlice)) – Strategy for which messages to collect. Either `last_messages` or `first_messages`.
  * **offset** (`int`) – Number of messages to ignore in the given order. Needs to be a non-negative integer.
  * **message_types** (`Optional`[`Tuple`[[`MessageType`](conversation.md#wayflowcore.messagelist.MessageType), `...`]]) – Optional filter to select specific messages. `None` means take all the messages from the history.
  * **output_template** (`Optional`[`str`]) – Template to format the chat history. If None, this step will return the list of messages. If string,
    it will format the `chat_history` messages into this template using jinja2 syntax.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

This step can be used to format the conversation into a string that can be used in a prompt.
For example, if the conversation is:

```pycon
>>> from wayflowcore.messagelist import Message, MessageType, MessageList
>>> from wayflowcore.steps import GetChatHistoryStep
>>> from wayflowcore.flowhelpers import create_single_step_flow
>>> messages = [
...     Message(content='How can I help you?', message_type=MessageType.AGENT),
...     Message(content='What is the capital of Switzerland?', message_type=MessageType.AGENT),
...     Message(content='The capital of Switzerland is Bern?', message_type=MessageType.AGENT),
... ]
```

If we want to format the chat history into a string directly in the step:

```pycon
>>> step = GetChatHistoryStep(n=10)
>>> assistant = create_single_step_flow(step, 'step')
>>> conversation = assistant.start_conversation(inputs={}, messages=messages)
>>> status = conversation.execute()
>>> status.output_values[GetChatHistoryStep.CHAT_HISTORY]  
AGENT>>>How can I help you?
USER>>>What is the capital of Switzerland?
AGENT>>>The capital of Switzerland is Bern?
```

If we want to use the chat history in a later step (`PromptExecutionStep` for example), we can set the template
of the `GetChatHistoryStep` to None and use the object returned by this step in a later template, similarly to
how it’s used in the default `GetChatHistoryStep` template.

```pycon
>>> from wayflowcore.steps import PromptExecutionStep
>>> step = GetChatHistoryStep(n=10, output_template=None)
>>> prompt_execution_step = PromptExecutionStep(
...     llm=llm,
...     prompt_template='{% for m in chat_history -%}>>>{{m.content}}{% endfor %}',
...     input_mapping={'chat_history': GetChatHistoryStep.CHAT_HISTORY}
... )
```

#### CHAT_HISTORY *= 'chat_history'*

Output key for the chat history collected by the `GetChatHistoryStep`.

* **Type:**
  str

#### DEFAULT_OUTPUT_TEMPLATE *= '{% for m in chat_history -%}\\n{{m.message_type}} >> {{m.content}}{{ "\\n" if not loop.last }}\\n{%- endfor %}'*

Default output template to be used to format the chat history.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="variablereadstep"></a>

### *class* wayflowcore.steps.variablesteps.variablereadstep.VariableReadStep(variable, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to perform a read on a Variable.
This step has no input, and a single output “value”.
These variables are stored in a key-value store distinct from the I/O system.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

This step has no input descriptor.

**Output descriptors**

This step has a single output descriptor:

* `VariableReadStep.VALUE`: `variable type`, the value read from the variable store.

* **Parameters:**
  * **variable** ([`Variable`](variables.md#wayflowcore.variable.Variable)) – `Variable` to read from.
    If the variable refers to a non-existent `Variable` (not passed into the flow), the flow constructor will throw an error.
    An exception is raised if the read returns a `None` value.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.dataconnection import DataFlowEdge
>>> from wayflowcore.steps import VariableReadStep, OutputMessageStep
>>> from wayflowcore.variable import Variable
>>> from wayflowcore.property import ListProperty, FloatProperty
>>>
>>> float_variable = Variable(
...     name="float_variable",
...     type=ListProperty(item_type=FloatProperty()),
...     description="list of floats variable",
...     default_value=[1.0, 2.0, 3.0, 4.0],
... )
>>>
>>> read_step = VariableReadStep(variable=float_variable)
>>> output_step = OutputMessageStep("The variable is {{ variable }}")
>>>
>>> flow = Flow(
...     begin_step=read_step,
...     control_flow_edges=[
...         ControlFlowEdge(read_step, output_step),
...         ControlFlowEdge(output_step, None),
...     ],
...     data_flow_edges=[
...         DataFlowEdge(read_step, VariableReadStep.VALUE, output_step, "variable"),
...     ],
...     variables=[float_variable],
... )
>>> conv = flow.start_conversation()
>>> status = conv.execute()
>>> last_message = conv.get_last_message()
>>> last_message.content
'The variable is [1.0, 2.0, 3.0, 4.0]'
```

#### VALUE *= 'value'*

Output key for the read value from the `VariableReadStep`.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="variablewritestep"></a>

### *class* wayflowcore.steps.variablesteps.variablewritestep.VariableWriteStep(variable, operation=VariableWriteOperation.OVERWRITE, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to perform a write on a Variable.
This step has no output and a single input, called “value”.
These variables are stored in a key-value store distinct from the I/O system.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

This step has a single input descriptor:

* `VariableWriteStep.VALUE`: `??`, the value to write in the variable store. Type will be resolved depending on the variable type and the type of variable write operation.

**Output descriptors**

This step has no output descriptor.

* **Parameters:**
  * **variable** ([`Variable`](variables.md#wayflowcore.variable.Variable)) – `Variable` to write to.
    If the variable refers to a non-existent Variable (not passed into the flow), the flow construction will throw an error.
  * **operation** ([`VariableWriteOperation`](variables.md#wayflowcore.variable.VariableWriteOperation)) – 

    The type of write operation to perform.

    #### NOTE
    `VariableWriteOperation.OVERWRITE` (or `'overwrite'`) works on any type of variable to replace its value with the incoming value.
    `VariableWriteOperation.MERGE` (or `'merge'`) updates a `Variable` of type dict (resp. list),
    so that the variable will contain both the existing data stored in the variable along with the new values in the incoming dict (resp. list).
    If the operation is `MERGE` but the variable’s value is `None`, it will throw an error,
    as a default value should have been provided when constructing the `Variable`.
    The `VariableWriteOperation.INSERT` (or `'insert'`) operation can be used to append a single element at the end of a list.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.steps import VariableWriteStep
>>> from wayflowcore.variable import Variable
>>> from wayflowcore.property import ListProperty, FloatProperty
>>>
>>> VARIABLE_IO = "$variable"
>>> # ^ how the variable value is stored in the I/O dict
>>>
>>> float_variable = Variable(
...     name="float_variable",
...     type=ListProperty(item_type=FloatProperty()),
...     description="list of floats variable",
...     default_value=[],
... )
>>>
>>> write_step = VariableWriteStep(
...     variable=float_variable,
...     input_mapping={VariableWriteStep.VALUE: VARIABLE_IO}
... )
>>>
>>> flow = Flow(
...     begin_step=write_step,
...     control_flow_edges=[
...         ControlFlowEdge(write_step, None),
...     ],
...     variables=[float_variable],
... )
>>> conv = flow.start_conversation(inputs={VARIABLE_IO: [1.0, 2.0, 3.0, 4.0]})
>>> status = conv.execute()
>>> new_variable_value = conv._get_variable_value(float_variable)
>>> # In practice, the value can be accessed with a VariableReadStep in the flow
>>> new_variable_value
[1.0, 2.0, 3.0, 4.0]
```

#### VALUE *= 'value'*

Input key for the value to write for the `VariableWriteStep`.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="constantvaluesstep"></a>

### *class* wayflowcore.steps.ConstantValuesStep(constant_values, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to provide constant values.

#### NOTE
**Output descriptors**

The output descriptors of this step are automatically inferred and
generated based on the values and names provided in the configuration.
The supported types are integer, float, boolean and string.

* **Parameters:**
  * **constant_values** (`Dict`[`str`, `Any`]) – Dictionary mapping names to constant values.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.steps import ConstantValuesStep
>>> from wayflowcore.flowhelpers import create_single_step_flow
>>> assistant = create_single_step_flow(ConstantValuesStep(constant_values={"PI":3.14, "PI_string": "3.14"}))
>>> conversation = assistant.start_conversation()
>>> status = conversation.execute()
>>> status.output_values["PI"] == 3.14
True
>>> status.output_values["PI_string"] == "3.14"
True
```

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

### *class* wayflowcore.steps.getchathistorystep.MessageSlice(value)

An enumeration.

#### FIRST_MESSAGES *= 'first'*

#### LAST_MESSAGES *= 'last'*

## Flow steps

<a id="retrystep"></a>

### *class* wayflowcore.steps.retrystep.RetryStep(flow, success_condition, max_num_trials=5, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step that can be used to execute a given `Flow` and retries if a success condition
is not met.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, the input_descriptors will be automatically inferred
from the input descriptors of the `flow` that this step will run.
See [Flow](#flow) to learn more about how flow inputs are resolved.

If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
in particular using the new type instead of the detected one.
If some of them are missing, an error will be thrown at instantiation of the step.

If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
they won’t be used during the execution of the step.

**Output descriptors**

By default, when `output_descriptors` is set to `None`, the outputs descriptors of this step will be
the same as the outputs descriptors of the `flow` that this step will run.
See [Flow](#flow) to learn more about how flow outputs are resolved.

It also has two additional descriptors:

* `RetryStep.SUCCESS_VAR`: `BooleanProperty()`, whether the step succeeded or not.
* `RetryStep.NUM_RETRIES_VAR`: `IntegerProperty()`, the number of trials the step used to succeed.

**Branches**

This step can have several next steps and perform conditional branching based on how the execution went. It has all the
branches exposed by the `flow` it runs (see [FlowExecutionStep](#flowexecutionstep) to learn more about how flow branches are resolved).

It has an additional branch, named `RetryStep.BRANCH_FAILURE`, that is taken in case the step runs out of `max_num_trials`.

* **Parameters:**
  * **flow** ([`Flow`](#wayflowcore.flow.Flow)) – Flow to be executed inside the `RetryStep`.
  * **success_condition** (`str`) – Name of the variable in the flow that defines success. The success is evaluated
    with `bool(flow_output[success_condition])`
  * **max_num_trials** (`int`) – 

    Maximum number of times to retry the flow execution. Defaults to 5.

    #### WARNING
    `max_num_trials` should not exceed `MAX_RETRY` retries.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.steps import ExtractValueFromJsonStep, PromptExecutionStep, RetryStep
>>> from wayflowcore.property import Property, BooleanProperty
```

```pycon
>>> prompt_step = PromptExecutionStep(llm=llm, prompt_template=(
...     "Please answer whether the following user query is a relevant HR question."
...     "User query: {{user_query}}"
...     'Answer with a json containing: {"in_domain": "false/true as string", "reason": "text explaining why its classified this way"}'
... ), output_mapping={PromptExecutionStep.OUTPUT: ExtractValueFromJsonStep.TEXT})
>>> json_step = ExtractValueFromJsonStep(
...     output_values = {
...         'in_domain': '.in_domain',
...         'reason': '.reason',
...         BooleanProperty(name='success'): ' has("reason")'}
... )
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.flowhelpers import run_single_step
>>> retry_step = RetryStep(
...     flow = Flow.from_steps([prompt_step, json_step]),
...     success_condition="success",
... )
>>> conv, messages = run_single_step(retry_step, inputs={'user_query': 'how many vacation days to I have left?'})
```

#### BRANCH_FAILURE *= 'failure'*

Name of the branch taken in case the condition is still not met after the maximum number of trials

#### MAX_RETRY *= 20*

Global upper limit on the number of retries for the `RetryStep`.

* **Type:**
  int

#### NUM_RETRIES_VAR *= 'retry_step_num_retries'*

Output key for the number of retries the retry step took to succeed or exit.

* **Type:**
  str

#### SUCCESS_VAR *= 'retry_step_success'*

Output key for whether the retry step succeeded in the end or not.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### *property* might_yield *: bool*

Indicates that this step might yield if the subflow might.

#### output_mapping *: Dict[str, str]*

#### sub_flows()

Returns the sub-flows this step uses, if it does.

* **Return type:**
  `Optional`[`List`[[`Flow`](#wayflowcore.flow.Flow)]]

<a id="catchexceptionstep"></a>

### *class* wayflowcore.steps.catchexceptionstep.CatchExceptionStep(flow, except_on=None, catch_all_exceptions=False, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Executes a `Flow` inside a step and catches specific potential exceptions.
If no exception is caught, it will transition to the branches of its subflow.
If an exception is caught, it will transition to some specific exception branch has configured in this step.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

The input descriptors of this step are the same as the input descriptors of the `flow` that this step will run.
See [Flow](#flow) to learn more about how flow inputs are resolved.

**Output descriptors**

The outputs descriptors of this step are the same as the outputs descriptors of the `flow` that this step will run.
See [Flow](#flow) to learn more about how flow outputs are resolved.

This step also has two additional output descriptors:

* `CatchExceptionStep.EXCEPTION_NAME_OUTPUT_NAME`: `StringProperty()`, the name of the caught exception if any.
* `CatchExceptionStep.EXCEPTION_PAYLOAD_OUTPUT_NAME`: `StringProperty()`, the payload of the caught exception if any.

**Branches**

This step can have several next steps depending on how its execution goes. It has the same
next branches as the `flow` it runs, plus some additional branches:

* all the values of the `except_on` mapping argument, which is taken if a particular exception is caught
* the `CatchExceptionStep.DEFAULT_EXCEPTION_BRANCH` in case `catch_all_exceptions` is `True` and another exception is caught.

* **Parameters:**
  * **flow** ([`Flow`](#wayflowcore.flow.Flow)) – `Flow` to execute and catch errors from
  * **except_on** (`Optional`[`Dict`[`str`, `str`]]) – Dictionary mapping error class names to the branch name they should transition to.
  * **catch_all_exceptions** (`bool`) – Whether to catch any error or just the ones present in the `except_on` parameter.
    If `True`, the step will transition to `CatchExceptionStep.DEFAULT_EXCEPTION_BRANCH`
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### DEFAULT_EXCEPTION_BRANCH *= 'default_exception_branch'*

Name of the branch where the step will transition if `catch_all_exceptions` is `True` and an exception was caught.

* **Type:**
  str

#### EXCEPTION_NAME_OUTPUT_NAME *= 'exception_name'*

Variable containing the name of the caught exception.

* **Type:**
  str

#### EXCEPTION_PAYLOAD_OUTPUT_NAME *= 'exception_payload_name'*

Variable containing the exception payload. Does not contain any higher-level stacktrace information than the wayflowcore stacktraces.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### *property* might_yield *: bool*

Indicates if the step might yield back to the user.
It depends on the sub-flow we are executing

#### output_mapping *: Dict[str, str]*

#### sub_flows()

Returns the sub-flows this step uses, if it does.

* **Return type:**
  `Optional`[`List`[[`Flow`](#wayflowcore.flow.Flow)]]

<a id="flowexecutionstep"></a>

### *class* wayflowcore.steps.flowexecutionstep.FlowExecutionStep(flow, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Executes a flow inside a step.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, the input_descriptors will be automatically inferred
from the input descriptors of the `flow` that this step will run.
See [Flow](#flow) to learn more about how flow inputs are resolved.

If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
in particular using the new type instead of the detected one.
If some of them are missing, an error will be thrown at instantiation of the step.

If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
they won’t be used during the execution of the step.

**Output descriptors**

The outputs descriptors of this step are the same as the outputs descriptors of the `flow` that this step will run.
See [Flow](#flow) to learn more about how flow outputs are resolved.

**Branches**

This step can have several next steps and perform conditional branching depending on where the `flow` finishes.
This step will have one branch per name of `CompleteStep` present in the `flow`, plus an additional one named
`FlowExecutionStep.NEXT_STEP` if the inside `flow` contains transitions to `None`.

* **Parameters:**
  * **flow** ([`Flow`](#wayflowcore.flow.Flow)) – `Flow` that the step needs to execute.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Example

The `FlowExecutionStep` is particularly suitable when subflows can be reused inside a wayflowcore project.
Let’s see an example with a flow that estimates numerical value using the “wisdowm of the crowd” effect:

```pycon
>>> from typing import List
>>> from wayflowcore.property import Property, StringProperty, ListProperty, IntegerProperty
>>> from wayflowcore.flowhelpers import create_single_step_flow
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.steps import MapStep, PromptExecutionStep, ToolExecutionStep
>>> from wayflowcore.tools import tool
>>>
>>> @tool(description_mode="only_docstring")
... def duplication_tool(element: str, n: int) -> List[str]:
...     '''Returns a list containing the passed element, n times'''
...     return [element for _ in range(n)]
...
>>> @tool(description_mode="only_docstring")
... def reduce_tool(elements: List[str]) -> str:
...     '''Returns the average of the first number found in each element'''
...     import re
...     extracted_elements = [re.search('-?\d*\.?\d+', elt) for elt in elements]
...     extracted_numbers = [float(x.group(0)) for x in extracted_elements if x is not None] or [-1.]
...     return str(sum(extracted_numbers) / len(extracted_numbers))
...
>>> # Defining flow input/output variables
>>> USER_QUERY_IO = "$user_query"
>>> N_REPEAT_IO = "$n_repeat"
>>> FLOW_ITERABLE_QUERIES_IO = "$flow_iterable_queries"
>>> FLOW_PROCESSED_QUERIES_IO = "$flow_processed_queries"
>>> FINAL_ANSWER_IO = "$answer_io"
>>> # Defining a simple prompt
>>> REASONING_PROMPT_TEMPLATE = '''Provide your best numerical estimate for: {{user_input}}
... Your answer should be a single number. Do not include any units, reasoning, or extra text.'''
>>> # Defining the subflow
>>> duplication_step = ToolExecutionStep(
...     tool=duplication_tool,
...     input_mapping={"element": USER_QUERY_IO, "n": N_REPEAT_IO},
...     output_mapping={ToolExecutionStep.TOOL_OUTPUT: FLOW_ITERABLE_QUERIES_IO},
...     name="DUPLICATION",
... )
>>> map_step = MapStep(
...     flow=create_single_step_flow(
...         PromptExecutionStep(
...             prompt_template=REASONING_PROMPT_TEMPLATE,
...             llm=llm,
...             output_mapping={PromptExecutionStep.OUTPUT: FLOW_PROCESSED_QUERIES_IO},
...         ),
...         step_name="REASONING"
...     ),
...     unpack_input={"user_input": "."},
...     output_descriptors=[ListProperty(name=FLOW_PROCESSED_QUERIES_IO, item_type=StringProperty())],
...     input_mapping={MapStep.ITERATED_INPUT: FLOW_ITERABLE_QUERIES_IO},
...     name="MAP"
... )
>>> reduce_step = ToolExecutionStep(
...     tool=reduce_tool,
...     input_mapping={"elements": FLOW_PROCESSED_QUERIES_IO},
...     output_mapping={ToolExecutionStep.TOOL_OUTPUT: FINAL_ANSWER_IO},
...     name="REDUCE",
... )
>>> mapreduce_flow = Flow.from_steps(steps=[duplication_step, map_step, reduce_step])
```

Once the subflow is created we can simply integrate it with the `FlowExecutionStep`:

```pycon
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.steps import FlowExecutionStep, OutputMessageStep
>>> MAPREDUCE_STEP = "MAPREDUCE"
>>> OUTPUT_STEP = "OUTPUT"
>>> mapreduce_step = FlowExecutionStep(mapreduce_flow, name=MAPREDUCE_STEP)
>>> output_step = OutputMessageStep(
...     "The estimation is {{value}}",
...     input_mapping={"value": FINAL_ANSWER_IO},
...     name=OUTPUT_STEP,
... )
>>> assistant = Flow(
...     begin_step=mapreduce_step,
...     control_flow_edges=[
...         ControlFlowEdge(source_step=mapreduce_step, destination_step=output_step),
...         ControlFlowEdge(source_step=output_step, destination_step=None),
...     ],
... )
>>> conversation = assistant.start_conversation(inputs={
...     USER_QUERY_IO: "How many calories are in a typical slice of pepperoni pizza?",
...     N_REPEAT_IO: 2
... })
>>> status = conversation.execute()
>>> # print(conversation.get_last_message().content)
>>> # The estimation is 285.5
```

#### input_mapping *: Dict[str, str]*

#### *property* might_yield *: bool*

Indicates if the step might yield back to the user.
It depends on the subflow we are executing

#### output_mapping *: Dict[str, str]*

#### sub_flows()

Returns the sub-flows this step uses, if it does.

* **Return type:**
  `Optional`[`List`[[`Flow`](#wayflowcore.flow.Flow)]]

<a id="parallelflowexecutionstep"></a>

### *class* wayflowcore.steps.parallelflowexecutionstep.ParallelFlowExecutionStep(flows, max_workers=None, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Executes several flows in parallel inside a step.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, the input_descriptors is set to the union of the
input descriptors of the subflows of this step. Inputs of subflows that have the same name and type are merged
together. However, if the input name matches, but the type is not the same, an error will be thrown.
See [Flow](#flow) to learn more about how flow inputs are resolved.

If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
in particular using the new type instead of the detected one.
If some of them are missing, an error will be thrown at instantiation of the step.

If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
they won’t be used during the execution of the step.

**Output descriptors**

The outputs descriptors of this step are the union of all the outputs generated by all the inner flows.
If outputs of different subflows have the same name, an error will be thrown.
See [Flow](#flow) to learn more about how flow outputs are resolved.

* **Parameters:**
  * **flows** (`List`[[`Flow`](#wayflowcore.flow.Flow)]) – `Flow` s that the step needs to execute in parallel.
  * **max_workers** (`Optional`[`int`]) – Number of workers to use if parallel execution is enabled.
    If None, the number of threads set in the initialize_threadpool is used.
    If initialize_threadpool was not called with an explicit number of threads, 20 is used as upper limit.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically
    using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the
    conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the
    conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Example

In the following example, we will perform the 4 basic math operations on the same couple of inputs in parallel:

```pycon
>>> from wayflowcore import Flow
>>> from wayflowcore.property import IntegerProperty
>>> from wayflowcore.steps import ParallelFlowExecutionStep
>>> from wayflowcore.steps import ToolExecutionStep
>>> from wayflowcore.tools.toolhelpers import DescriptionMode, ServerTool
>>>
>>> add = ServerTool(
...     name="add",
...     description="Sum two numbers",
...     input_descriptors=[IntegerProperty(name="a"), IntegerProperty(name="b")],
...     output_descriptors=[IntegerProperty(name="sum")],
...     func=lambda a, b: a + b,
... )
>>> subtract = ServerTool(
...     name="subtract",
...     description="Subtract two numbers",
...     input_descriptors=[IntegerProperty(name="a"), IntegerProperty(name="b")],
...     output_descriptors=[IntegerProperty(name="difference")],
...     func=lambda a, b: a - b,
... )
>>> multiply = ServerTool(
...     name="multiply",
...     description="Multiply two numbers",
...     input_descriptors=[IntegerProperty(name="a"), IntegerProperty(name="b")],
...     output_descriptors=[IntegerProperty(name="product")],
...     func=lambda a, b: a * b,
... )
>>> divide = ServerTool(
...     name="divide",
...     description="Divide two numbers",
...     input_descriptors=[IntegerProperty(name="a"), IntegerProperty(name="b")],
...     output_descriptors=[IntegerProperty(name="quotient")],
...     func=lambda a, b: a // b,
... )
>>> sum_flow = Flow.from_steps([ToolExecutionStep(name="sum_step", tool=add)])
>>> subtract_flow = Flow.from_steps([ToolExecutionStep(name="subtract_step", tool=subtract)])
>>> multiply_flow = Flow.from_steps([ToolExecutionStep(name="multiply_step", tool=multiply)])
>>> divide_flow = Flow.from_steps([ToolExecutionStep(name="divide_step", tool=divide)])
>>> parallel_flow_step = ParallelFlowExecutionStep(
...    name="parallel_flow_step",
...    flows=[sum_flow, subtract_flow, multiply_flow, divide_flow],
... )
>>> flow = Flow.from_steps([parallel_flow_step])
>>> conversation = flow.start_conversation(inputs={"a": 16, "b": 4})
>>> status = conversation.execute()
```

#### input_mapping *: Dict[str, str]*

#### *property* might_yield *: bool*

Indicates if the step might yield back to the user.
It depends on the subflow we are executing

#### output_mapping *: Dict[str, str]*

#### sub_flows()

Returns the sub-flows this step uses, if it does.

* **Return type:**
  `List`[[`Flow`](#wayflowcore.flow.Flow)]

<a id="mapstep"></a>

### *class* wayflowcore.steps.mapstep.MapStep(flow, unpack_input=None, parallel_execution=False, max_workers=None, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to execute an inside flow on all the elements of an iterable. Order in the iterable is guaranteed the same
as order of execution.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, this step will have several inputs descriptors.
One will be named `MapStep.ITERATED_INPUT` of type `ListProperty` will be the iterable on which the step
will iterate. The step will also expose all input descriptors of the `flow` it runs if their names
are not in the `unpack_input` mapping (if they are, these values are extracted from `MapStep.ITERATED_INPUT`).
See [Flow](#flow) to learn more about how flow input descriptors are resolved.

If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
in particular using the new type instead of the detected one. In particular, the type of
`MapStep.ITERATED_INPUT` will impact the way the step iterates on the iterable (see `unpack_input`
parameter for more details).

If some of them are missing, an error will be thrown at instantiation of the step.

If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
they won’t be used during the execution of the step.

**Output descriptors**

By default, when `output_descriptors` is set to `None`, this step will not have any output descriptor.

If you provide a list of output descriptors, their names much match with the names of the output
descriptors of the inside `flow` and their type should be `ListProperty`.
This way. the step will collect the output of each iteration of the inside `flow` into these outputs.

* **Parameters:**
  * **flow** ([`Flow`](#wayflowcore.flow.Flow)) – Flow that is being executed with each iteration of the input.
  * **unpack_input** (`Optional`[`Dict`[`str`, `str`]]) – 

    Mapping to specify how to unpack when each iter item is a `dict` and we need to map its element to the inside flow inputs.

    #### NOTE
    Keys are names of input variables of the inside flow, while values are jq queries to extract a specific part of each iterated item (see [https://jqlang.github.io/jq/](https://jqlang.github.io/jq/) for more information on jq queries). Using the item as-is can be done with the `.` query.
    If the iterated input type is `dict`, then the iterated items will be key/value pairs and you can access both using `._key` and `._value` as jq queries.
  * **parallel_execution** (`bool`) – Executes the mapping operation in parallel. Cannot be set to true if the internal flow can yield. This feature is
    in beta, be aware that flows might have side effects on one another, since they share most resources (e.g., conversation).
    Parallel execution is performed through asynchronous task groups, it is not actual multi-threading nor multi-processing.
  * **max_workers** (`Optional`[`int`]) – Maximum number of tasks executed in parallel if parallel execution is enabled.
    If None, the number of workers set in the initialize_threadpool is used.
    If initialize_threadpool was not called with an explicit number of threads, 20 is used as upper limit.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – 

    Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.

    #### WARNING
    Setting this value to something else than `None` will change the behavior of the step. The step will
    iterate differently depending on the type of the `MapStep.ITERATED_INPUT` descriptor and the
    value of `unpack_inputs`
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – 

    Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.

    #### WARNING
    Setting this value to something else than `None` will change the behavior of the step. It will try to collect
    these output descriptors values from the outputs of each run of the inside `flow`.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Notes

If the mapping between iterated items and the inside
flow input is 1 to 1 (`unpack_input` is a `str`), then the `iterated_input_type` subtype will be inferred from the inside flow’s input type.
Otherwise, it will be set to `AnyType`.

### Examples

```pycon
>>> from wayflowcore.steps import MapStep, OutputMessageStep
>>> from wayflowcore import Flow
>>> from wayflowcore.property import DictProperty, AnyProperty, Property
```

You can iterate in simple lists:

```pycon
>>> sub_flow = Flow.from_steps([OutputMessageStep(message_template="username={{user}}", name='step')])
>>> step = MapStep(
...     name="step",
...     flow=sub_flow,
...     unpack_input={'user': '.'},
...     output_descriptors=[AnyProperty(name=OutputMessageStep.OUTPUT)],
... )
>>> iterable = ["a", "b"]
>>> assistant = Flow.from_steps([step])
>>> conversation = assistant.start_conversation(inputs={MapStep.ITERATED_INPUT: iterable})
>>> status = conversation.execute()
>>> status.output_values
{'output_message': ['username=a', 'username=b']}
```

You can also extract from list of elements:

```pycon
>>> sub_flow=Flow.from_steps([
...     OutputMessageStep(message_template="{{user}}:{{email}}", name='step')
... ])
>>> step = MapStep(
...     name="step",
...     flow=sub_flow,
...     unpack_input={
...        'user': '.username',
...        'email': '.email',
...     },
...     output_descriptors=[AnyProperty(name=OutputMessageStep.OUTPUT)],
... )
>>> iterable = [
...     {"username": "a", "email": "a@oracle.com"},
...     {"username": "b", "email": "b@oracle.com"},
... ]
>>> assistant = Flow.from_steps([step])
>>> conversation = assistant.start_conversation(inputs={MapStep.ITERATED_INPUT: iterable})
>>> status = conversation.execute()
>>> status.output_values
{'output_message': ['a:a@oracle.com', 'b:b@oracle.com']}
```

You can also iterate through dictionaries:

```pycon
>>> sub_flow=Flow.from_steps([
...     OutputMessageStep(message_template="{{user}}:{{email}}", name='step')
... ])
>>> step = MapStep(
...     name="step",
...     flow=sub_flow,
...     unpack_input={
...        'user': '._key',
...        'email': '._value.email',
...     },
...     input_descriptors=[DictProperty(name=MapStep.ITERATED_INPUT, value_type=AnyProperty('inner_value'))],
...     output_descriptors=[AnyProperty(name=OutputMessageStep.OUTPUT)],
... )
>>> iterable = {
...     'a': {"username": "a", "email": "a@oracle.com"},
...     'b': {"username": "b", "email": "b@oracle.com"},
... }
>>> assistant = Flow.from_steps([step])
>>> conversation = assistant.start_conversation(inputs={MapStep.ITERATED_INPUT: iterable})
>>> status = conversation.execute()
>>> status.output_values
{'output_message': ['a:a@oracle.com', 'b:b@oracle.com']}
```

#### ITERATED_INPUT *= 'iterated_input'*

Input key for the iterable to use the `MapStep` on.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### *property* might_yield *: bool*

Indicates if the step might yield back to the user.
Might be the step directly, or one of the steps it calls.

#### output_mapping *: Dict[str, str]*

#### sub_flows()

Returns the sub-flows this step uses, if it does.

* **Return type:**
  `Optional`[`List`[[`Flow`](#wayflowcore.flow.Flow)]]

<a id="parallelmapstep"></a>

### *class* wayflowcore.steps.mapstep.ParallelMapStep(flow, unpack_input=None, max_workers=None, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to execute an inside flow on all the elements of an iterable in parallel.
The order in the iterable is guaranteed the same as order of execution.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, this step will have several inputs descriptors.
One will be named `ParallelMapStep.ITERATED_INPUT` of type `ListProperty` will be the iterable on which the step
will iterate. The step will also expose all input descriptors of the `flow` it runs if their names
are not in the `unpack_input` mapping (if they are, these values are extracted from `ParallelMapStep.ITERATED_INPUT`).
See [Flow](#flow) to learn more about how flow input descriptors are resolved.

If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
in particular using the new type instead of the detected one. In particular, the type of
`ParallelMapStep.ITERATED_INPUT` will impact the way the step iterates on the iterable (see `unpack_input`
parameter for more details).

If some of them are missing, an error will be thrown at instantiation of the step.

If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
they won’t be used during the execution of the step.

**Output descriptors**

By default, when `output_descriptors` is set to `None`, this step will not have any output descriptor.

If you provide a list of output descriptors, their names much match with the names of the output
descriptors of the inside `flow` and their type should be `ListProperty`.
This way. the step will collect the output of each iteration of the inside `flow` into these outputs.

* **Parameters:**
  * **flow** ([`Flow`](#wayflowcore.flow.Flow)) – Flow that is being executed with each iteration of the input.
  * **unpack_input** (`Optional`[`Dict`[`str`, `str`]]) – 

    Mapping to specify how to unpack when each iter item is a `dict` and we need to map its element to the inside flow inputs.

    #### NOTE
    Keys are names of input variables of the inside flow, while values are jq queries to extract a specific part of each iterated item (see [https://jqlang.github.io/jq/](https://jqlang.github.io/jq/) for more information on jq queries). Using the item as-is can be done with the `.` query.
    If the iterated input type is `dict`, then the iterated items will be key/value pairs and you can access both using `._key` and `._value` as jq queries.
  * **max_workers** (`Optional`[`int`]) – Maximum number of tasks executed in parallel.
    If None, the number of workers set in the initialize_threadpool is used.
    If initialize_threadpool was not called with an explicit number of threads, 20 is used as upper limit.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – 

    Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.

    #### WARNING
    Setting this value to something else than `None` will change the behavior of the step. The step will
    iterate differently depending on the type of the `ParallelMapStep.ITERATED_INPUT` descriptor and the
    value of `unpack_inputs`
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – 

    Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.

    #### WARNING
    Setting this value to something else than `None` will change the behavior of the step. It will try to collect
    these output descriptors values from the outputs of each run of the inside `flow`.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Notes

If the mapping between iterated items and the inside
flow input is 1 to 1 (`unpack_input` is a `str`), then the `iterated_input_type` subtype will be inferred from the inside flow’s input type.
Otherwise, it will be set to `AnyType`.

### Examples

```pycon
>>> from wayflowcore.steps import ParallelMapStep, OutputMessageStep
>>> from wayflowcore import Flow
>>> from wayflowcore.property import DictProperty, AnyProperty
```

You can iterate in simple lists:

```pycon
>>> sub_flow = Flow.from_steps([
...     OutputMessageStep(message_template="username={{user}}", name='step')
... ])
>>> step = ParallelMapStep(
...     name="step",
...     flow=sub_flow,
...     unpack_input={'user': '.'},
...     output_descriptors=[AnyProperty(name=OutputMessageStep.OUTPUT)],
... )
>>> iterable = ["a", "b"]
>>> assistant = Flow.from_steps([step])
>>> conversation = assistant.start_conversation(inputs={ParallelMapStep.ITERATED_INPUT: iterable})
>>> status = conversation.execute()
>>> status.output_values
{'output_message': ['username=a', 'username=b']}
```

You can also extract from list of elements:

```pycon
>>> sub_flow=Flow.from_steps([
...     OutputMessageStep(message_template="{{user}}:{{email}}", name='step')
... ])
>>> step = ParallelMapStep(
...     name="step",
...     flow=sub_flow,
...     unpack_input={
...        'user': '.username',
...        'email': '.email',
...     },
...     output_descriptors=[AnyProperty(name=OutputMessageStep.OUTPUT)],
... )
>>> iterable = [
...     {"username": "a", "email": "a@oracle.com"},
...     {"username": "b", "email": "b@oracle.com"},
... ]
>>> assistant = Flow.from_steps([step])
>>> conversation = assistant.start_conversation(inputs={ParallelMapStep.ITERATED_INPUT: iterable})
>>> status = conversation.execute()
>>> status.output_values
{'output_message': ['a:a@oracle.com', 'b:b@oracle.com']}
```

You can also iterate through dictionaries:

```pycon
>>> sub_flow=Flow.from_steps([
...     OutputMessageStep(message_template="{{user}}:{{email}}", name='step')
... ])
>>> step = ParallelMapStep(
...     name="step",
...     flow=sub_flow,
...     unpack_input={
...        'user': '._key',
...        'email': '._value.email',
...     },
...     input_descriptors=[DictProperty(name=ParallelMapStep.ITERATED_INPUT, value_type=AnyProperty('inner_value'))],
...     output_descriptors=[AnyProperty(name=OutputMessageStep.OUTPUT)],
... )
>>> iterable = {
...     'a': {"username": "a", "email": "a@oracle.com"},
...     'b': {"username": "b", "email": "b@oracle.com"},
... }
>>> assistant = Flow.from_steps([step])
>>> conversation = assistant.start_conversation(inputs={ParallelMapStep.ITERATED_INPUT: iterable})
>>> status = conversation.execute()
>>> status.output_values
{'output_message': ['a:a@oracle.com', 'b:b@oracle.com']}
```

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="branchingstep"></a>

### *class* wayflowcore.steps.branchingstep.BranchingStep(branch_name_mapping=None, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

This step impacts the control flow of the assistant by deciding what step to go next based on the input passed to it.
This step does not involve the use of LLMs, as it simply uses the given input step name and an optional mapping.
As a consequence, exact match in the step names is required for this step.
For more flexibility please use the `ChoiceSelectionStep` where the next step is determined by an LLM.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, this step has a single input descriptor, named
`BranchingStep.NEXT_BRANCH_NAME`, of type `StringProperty()`, that represents the value that will be
mapped against `branch_name_mapping` to determine the next branch.

**Output descriptors**

By default, this step has no output descriptor.

**Branches**

This step can have several next steps and perform conditional branching based on the value of its inputs. It has one
possible branch per value in the `branch_name_mapping` dictionary, plus `BRANCH_DEFAULT` which is chosen
in case the value passed as input does not appear in the `branch_name_mapping` mapping.

* **Parameters:**
  * **branch_name_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between input values of this step and particular branches. Used to branch out based on the input value.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### SEE ALSO
[`ChoiceSelectionStep`](#wayflowcore.steps.choiceselectionstep.ChoiceSelectionStep)
: Flexible version of the `BranchingStep` using an LLM to select the next step.

### Examples

```pycon
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.steps import BranchingStep, OutputMessageStep
>>> NEXT_STEP_NAME_IO = "$next_step_name"
>>> branching_step = BranchingStep(
...     branch_name_mapping={"yes": "access_is_granted", "no": "access_is_denied"},
...     input_mapping={BranchingStep.NEXT_BRANCH_NAME: NEXT_STEP_NAME_IO},
...     name="BRANCHING"
... )
>>> output_access_granted_step = OutputMessageStep(
...     "Access granted. Press any key to continue...", name="ACCESS_GRANTED"
... )
>>> output_access_denied_step = OutputMessageStep(
...     "Access denied. Please exit the conversation.", name="ACCESS_DENIED"
... )
>>> assistant = Flow(
...     begin_step=branching_step,
...     control_flow_edges=[
...         ControlFlowEdge(
...             source_step=branching_step,
...             source_branch="access_is_granted",
...             destination_step=output_access_granted_step,
...         ),
...         ControlFlowEdge(
...             source_step=branching_step,
...             source_branch="access_is_denied",
...             destination_step=output_access_denied_step,
...         ),
...         ControlFlowEdge(
...             source_step=branching_step,
...             source_branch=BranchingStep.BRANCH_DEFAULT,
...             destination_step=output_access_denied_step,
...         ),
...         ControlFlowEdge(source_step=output_access_granted_step, destination_step=None),
...         ControlFlowEdge(source_step=output_access_denied_step, destination_step=None),
...     ],
... )
>>> conversation = assistant.start_conversation(inputs={NEXT_STEP_NAME_IO: "yes"})
>>> status = conversation.execute()
>>> # conversation.get_last_message().content
>>> # Access granted. Press any key to continue...
```

#### BRANCH_DEFAULT *= 'default'*

Name of the branch taken if none of the branch_name_mapping transitions match

* **Type:**
  str

#### NEXT_BRANCH_NAME *= 'next_step_name'*

Input key for the name to transition to next.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="choiceselectionstep"></a>

### *class* wayflowcore.steps.choiceselectionstep.ChoiceSelectionStep(llm, next_steps, prompt_template='', num_tokens=7, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step that decides what next step to go to (control flow change) based on an input and description of the next steps,
powered by an LLM. If the next step named as an explicit mapping to some existing value, please use the
`BranchingStep`, which is similar to this step but doesn’t use any LLM.

It outputs the selected choice index so that it can be consumed by downstreams steps if they need it,
as well as the full text given back by the LLM.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

This step has for input descriptors all the variables extracted from `prompt_template`. See [TemplateRenderingStep](#templaterenderingstep) for concrete examples on how descriptors are extracted from text prompts.

**Output descriptors**

This step has two output descriptors:

* `ChoiceSelectionStep.SELECTED_CHOICE`: `StringProperty()`, the name of the branch selected by the step
* `ChoiceSelectionStep.LLM_OUTPUT`: `StringProperty()`, the raw LLM output before parsing

**Branches**

This step can have several next steps and perform conditional branching using the `llm` and the given input values. The branches
this step can take are simply all the branches mentioned in the `next_step` argument.

* **Parameters:**
  * **llm** ([`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)) – Model that is used to determine the choice of next step.
  * **next_steps** (`List`[`Union`[`Tuple`[`str`, `str`], `Tuple`[`str`, `str`, `str`], [`StepDescription`](#wayflowcore.stepdescription.StepDescription)]]) – List of tuples containing the next step name and a description of it. If the name displayed in prompt is different than
    the real step name, then pass tuples with the format `Tuple[step_name, step_description, displayed_step_name]`.
    Will be passed in the prompt for making the choice.
  * **prompt_template** (`str`) – Prompt template to be used to have the LLM determine the next step to transition to. Defaults to `DEFAULT_CHOICE_SELECTION_TEMPLATE`,
  * **num_tokens** (`int`) – 

    Upper limit on the number of tokens that can be generated by the LLM.

    #### NOTE
    `num_tokens` should be as small as possible to ensure low latency, but high enough
    to encode all the displayed_step_names. Adjust the value depending on the length of the step names.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### SEE ALSO
[`BranchingStep`](#wayflowcore.steps.branchingstep.BranchingStep)
: Strict version of the `ChoiceSelectionStep` that does not use an LLM.

### Notes

The success of this steps depends on the performance of the LLM. You can increase the robustness of this step by:

- Tweaking the prompt template for your specific use case.
- Using a better LLM
- Wrapping the step inside a `RetryStep`

### Examples

```pycon
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.steps import ChoiceSelectionStep, OutputMessageStep
>>> CHOICE_SELECTION_IO = "$choice_selection"
>>> choice_selection_step = ChoiceSelectionStep(
...         llm=llm,
...         next_steps=[
...             ("OUTPUT1", "The access is denied", "is_access_denied"),
...             ("OUTPUT2", "The access is granted", "is_access_granted"),
...         ],
...         input_mapping={ChoiceSelectionStep.INPUT: CHOICE_SELECTION_IO},
...         name="CHOICE_SELECTION"
...     )
>>> output_step1 = OutputMessageStep("Access denied. Please exit the conversation.", name="OUTPUT1")
>>> output_step2 = OutputMessageStep("Access granted. Press any key to continue...", name="OUTPUT2")
>>> assistant = Flow(
...     begin_step=choice_selection_step,
...     control_flow_edges=[
...         ControlFlowEdge(
...             source_step=choice_selection_step,
...             source_branch="OUTPUT1",
...             destination_step=output_step1,
...         ),
...         ControlFlowEdge(
...             source_step=choice_selection_step,
...             source_branch="OUTPUT2",
...             destination_step=output_step2,
...         ),
...         ControlFlowEdge(
...             source_step=choice_selection_step,
...             source_branch=ChoiceSelectionStep.BRANCH_DEFAULT,
...             destination_step=output_step1,
...         ),
...         ControlFlowEdge(source_step=output_step1, destination_step=None),
...         ControlFlowEdge(source_step=output_step2, destination_step=None),
...     ],
... )
>>> conversation = assistant.start_conversation(inputs={CHOICE_SELECTION_IO: "I grant the access to the user"})
>>> status = conversation.execute() 
>>> # conversation.get_last_message().content
>>> # Access granted. Press any key to continue...
```

#### BRANCH_DEFAULT *= 'default'*

Name of the branch taken in case the LLM is not able to choose a next step

* **Type:**
  str

#### DEFAULT_CHOICE_SELECTION_TEMPLATE *= 'You are a helpful assistant. You must pick a task to execute, given some user input.\\nYou have several tasks to select from, with the format:\\n\`\`\`\\ntask_name: task_description\\n\`\`\`\\n\\nThe available tasks are:\\n\`\`\`\\n{% for desc in next_steps -%}\\n- {{ desc.displayed_step_name }}: {{ desc.description }}\\n{% endfor -%}\\n\`\`\`\\n\\nReturn the task_name (and only the task_name) that you need to execute for this request: {{ input }}'*

Default prompt template to be used by the LLM to determine the next step to transition to.

* **Type:**
  str

#### INPUT *= 'input'*

Input key for the input to be used to determine the next step to transition to.

* **Type:**
  str

#### LLM_OUTPUT *= 'llm_output'*

Output key for the final next step decision after parsing the LLM decision.

* **Type:**
  str

#### SELECTED_CHOICE *= 'selected_choice'*

Output key for the raw next step decision generated by the LLM.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

#### sub_flows()

Returns the sub-flows this step uses, if it does.

* **Return type:**
  `Optional`[`List`[[`Flow`](#wayflowcore.flow.Flow)]]

<a id="completestep"></a>

### *class* wayflowcore.steps.completestep.CompleteStep(branch_name=None, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to exit a `Flow`.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

This step has no input descriptors.

**Output descriptors**

This step has no output descriptors.

* **Parameters:**
  * **branch_name** (`Optional`[`str`]) – Name of the outgoing branch of this step when being used in a sub-flow (i.e. flows used in a `FlowExecutionStep`).
    If `None`, the step `name` is used.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.dataconnection import DataFlowEdge
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.property import StringProperty
>>> from wayflowcore.steps import BranchingStep, OutputMessageStep, StartStep
>>> BRANCHING_VAR_NAME = "my_branching_var"
>>> branching_step = BranchingStep(
...     name="branching_step",
...     branch_name_mapping={
...         "[SUCCESS]": "success",
...         "[FAILURE]": "failure",
...     },
... )
>>> start_step = StartStep(name="start_step", input_descriptors=[StringProperty(BRANCHING_VAR_NAME)])
>>> success_step = OutputMessageStep(name="success_step", message_template="It was a success")
>>> failure_step = OutputMessageStep(name="failure_step", message_template="It was a failure")
>>> flow = Flow(
...     begin_step=start_step,
...     control_flow_edges=[
...         ControlFlowEdge(source_step=start_step, destination_step=branching_step),
...         ControlFlowEdge(
...             source_step=branching_step,
...             destination_step=success_step,
...             source_branch="success",
...         ),
...         ControlFlowEdge(
...             source_step=branching_step,
...             destination_step=failure_step,
...             source_branch="failure",
...         ),
...         ControlFlowEdge(
...             source_step=branching_step,
...             destination_step=failure_step,
...             source_branch=BranchingStep.BRANCH_DEFAULT,
...         ),
...         ControlFlowEdge(source_step=success_step, destination_step=None),
...         ControlFlowEdge(source_step=failure_step, destination_step=None),
...     ],
...     data_flow_edges=[
...         DataFlowEdge(start_step, BRANCHING_VAR_NAME, branching_step, BranchingStep.NEXT_BRANCH_NAME),
...     ],
... )
>>> conversation = flow.start_conversation(inputs={BRANCHING_VAR_NAME: "[SUCCESS]"})
>>> status = conversation.execute()
>>> print(conversation.get_last_message().content)
It was a success
```

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="startstep"></a>

### *class* wayflowcore.steps.startstep.StartStep(input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, name=None, \_\_metadata_info_\_=None)

Step to enter a `Flow`.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

By default, when `input_descriptors` is set to `None`, the input descriptors of the step are empty.
The user should set the `input_descriptors` to the list of inputs that are expected to be provided
as inputs to the flow this step belongs to.

**Output descriptors**

The output descriptors of this step are equal to the input descriptors.

* **Parameters:**
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – The list of input descriptors that the flow containing this step takes as input.
    `None` means the step will not have any input descriptor.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner. The output descriptors should be a subset of the input_descriptors.
    This parameter should not be used in this step.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
    This parameter should not be used in this step.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.property import StringProperty
>>> from wayflowcore.dataconnection import DataFlowEdge
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.steps import (
...     CompleteStep,
...     PromptExecutionStep,
...     StartStep,
... )
>>> start_step = StartStep(
...     input_descriptors=[
...         StringProperty(
...             name="user_question",
...             description="The user question.",
...         )
...     ],
...     name="start_step"
... )
>>> llm_step = PromptExecutionStep(
...     prompt_template="Answer the user question: {{user_question}}",
...     llm=llm,
...     name="llm_answer_step"
... )
>>> complete_step = CompleteStep(name="complete_step")
>>> control_flow_edges = [
...     ControlFlowEdge(source_step=start_step, destination_step=llm_step),
...     ControlFlowEdge(source_step=llm_step, destination_step=complete_step),
... ]
>>> assistant = Flow(
...     begin_step=start_step,
...     control_flow_edges=control_flow_edges,
... )
>>> conversation = assistant.start_conversation(
...     inputs={"user_question": "Could you talk about the Oracle Cloud Infrastructure?"}
... )
```

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

<a id="apicallstep"></a>

### *class* wayflowcore.steps.apicallstep.ApiCallStep(url, method, json_body=None, data=None, params=None, headers=None, sensitive_headers=None, cookies=None, output_values_json=None, store_response=False, ignore_bad_http_requests=False, num_retry_on_bad_http_request=3, allow_insecure_http=False, name=None, url_allow_list=None, allow_credentials=True, allow_fragments=True, default_ports={'http': 80, 'https': 443}, input_descriptors=None, output_descriptors=None, input_mapping=None, output_mapping=None, \_\_metadata_info_\_=None)

A step for calling remote APIs.
It can do GET/POST/PUT/DELETE/etc. requests to endpoints.
The query parameters, body, headers, cookies can be configured and can be templated so that they
take values from the IO system.
If the response is JSON its contents can be automatically extracted using json queries.

#### CAUTION
Since the Agent can generate arguments (url, method, json_body, data, params, headers, cookies) or parts of these arguments in the respective Jinja
templates, this can impose a security risk of information leakage and enable specific attack vectors like automated DDOS attacks. Please use
`ApiCallStep` responsibly and ensure that only valid URLs can be given as arguments or that no sensitive information is used for any of these arguments by the agent.
Please use the url_allow_list, allow_credentials and allow_fragments parameters to control which URLs are treated as valid.

Initializes the api call step.

#### NOTE
A step has input and output descriptors, describing what values the step requires to run and what values it produces.

**Input descriptors**

This step has for input descriptors all the variables extracted from the `url`, `method`, `data`, `json_body`, `params`, `headers` or `cookies` templates. See [TemplateRenderingStep](#templaterenderingstep) for concrete examples on how descriptors are extracted from text prompts.

**Output descriptors**

This step has several output descriptors:

* `ApiCallStep.HTTP_STATUS_CODE`: `IntegerProperty()`, status code of the API call
* `ApiCallStep.HTTP_RESPONSE`: `StringProperty()`, http response of the API call if `store_response` is `True`

It also has one output descriptor per entry in the `output_values_json` mapping, which are `AnyProperty()` extract from the json response

The requested URL is validated and normalized before the request is executed. Normalization expects URLs containing non-Latin characters or
underscores to be normalized to punycode, else they will be rejected during normalization.

* **Parameters:**
  * **url** (`str`) – Url to call.
    Can be templated using jinja templates.
  * **method** (`str`) – HTTP method to call.
    Common methods are: GET, OPTIONS, HEAD, POST, PUT, PATCH, or DELETE.
    Can be templated using jinja templates.
  * **json_body** (`Optional`[`Any`]) – 

    A json-serializable object that will automatically be converted to json and sent as a body.
    Cannot be used in combination with `data`.
    Can be templated using jinja templates.

    #### NOTE
    Special case: if the `json_body` is a `str` it will be taken as a literal json string.
    Setting this parameter automatically sets the `Content-Type: application/json` header.

    #### WARNING
    The `json_body` parameter is only relevant for http methods that allow bodies, e.g. POST, PUT, PATCH.
  * **data** (`Union`[`Dict`[`Any`, `Any`], `List`[`Tuple`[`Any`, `Any`]], `str`, `bytes`, `None`]) – 

    Raw data that will be sent in the body.
    Semantics of this are the same as in the `requests` library.
    Cannot be used in combination with `json_body`.
    Can be templated using jinja templates.

    #### WARNING
    The `data` parameter is only relevant for http methods that allow bodies, e.g. POST, PUT, PATCH.
  * **params** (`Union`[`Dict`[`Any`, `Any`], `List`[`Tuple`[`Any`, `Any`]], `str`, `bytes`, `None`]) – Data to send as query-parameters (i.e. the `?foo=bar&gnu=gna` part of queries)
    Semantics of this are the same as in the `requests` library.
    Can be templated using jinja templates.
  * **headers** (`Optional`[`Dict`[`str`, `str`]]) – 

    Explicitly set headers.
    Can be templated using jinja templates.
    Keys of `sensitive_headers` and `headers` dictionaries cannot overlap.

    #### NOTE
    This will override any of the implicitly set headers (e.g. `Content-Type` from `json_body`).
  * **sensitive_headers** (`Optional`[`Dict`[`str`, `str`]]) – Explicitly set headers that contain sensitive information.
    These headers will behave equivalently to the `headers` parameter, but it will be excluded
    from any serialization for security reasons.
    Keys of `sensitive_headers` and `headers` dictionaries cannot overlap.
  * **cookies** (`Optional`[`Dict`[`str`, `str`]]) – Cookies to transmit.
    Can be templated using jinja templates.
  * **output_values_json** (`Optional`[`Dict`[`Union`[`str`, [`Property`](#wayflowcore.property.Property)], `str`]]) – 

    Interpret the response as json and extract values according to the provided dict, which contains pairs of (“key-in-io”: “jq-query”),
    This will extract from the response json the value described by the “jq-query” and store it in “key-in-io”.

    #### NOTE
    By default this is `None`, so if `output_values_json` is not set and the `store_response` parameter is not explicitly set to `True`,
    this step will not return anything from the response.
  * **store_response** (`bool`) – 

    If `True`, store the complete response in the IO system under the key `HTTP_RESPONSE`.
    (useful for e.g. later extraction through a specialized step, or if the response does not require extraction or is not json)

    #### NOTE
    By default this is `False`, so if output_values_json is not set and the `store_response` parameter is not explicitly set to `True`,
    this step will not return anything from the response body.
  * **ignore_bad_http_requests** (`bool`) – If `True`, don’t throw an exception when query results in a bad status code (e.g. 4xx, 5xx); if `False` throws an exception.
  * **num_retry_on_bad_http_request** (`int`) – Number of times to retry a failed http request before continuing (depending on the `ignore_bad_http_requests` setting above).
  * **allow_insecure_http** (`bool`) – If `True`, allows url to have a unsecured non-ssl http scheme. Default is `False` and throws a ValueError if url is unsecure.
  * **name** (`Optional`[`str`]) – Name of the step.
  * **url_allow_list** (`Optional`[`List`[`str`]]) – 

    A list of URLs that any request URL is matched against.
    If there is at least one entry in the allow list that the requested URL matches,
    the request is considered allowed.

    We consider URLs following the generic-URL syntax as defined in [RFC 1808](https://datatracker.ietf.org/doc/html/rfc1808.html):
    `<scheme>://<net_loc>/<path>;<params>?<query>#<fragment>`

    Matching is done according to the following rules:
    * URL scheme must match exactly
    * URL authority (net_loc) must match exactly
    * URL path must prefix match the path given by the entry in the allow list
    * We do not support matching against specific params, fragments or query elements of the URLs.

    Examples of matches:
    * URL: “[https://example.com/page](https://example.com/page)”, allow_list: [”[https://example.com](https://example.com)”]
    * URL: “[https://specific.com/path/and/more](https://specific.com/path/and/more)”, allow_list: [”[https://specific.com/path](https://specific.com/path)”]

    Examples of mismatches:
    * URL: “[http://someurl.example.com](http://someurl.example.com)”, allow_list: [”[http://other.example.com](http://other.example.com)”]
    * URL: “[http://someurl.example.com/endpoint](http://someurl.example.com/endpoint)”, allow_list: [”[http://](http://)”] (results in a validation error)

    Can be used to restrict requests to a set of allowed urls.
  * **allow_credentials** (`bool`) – 

    Whether to allow URLs containing credentials.
    If set to `False`, requested URLs and those in the allow list containing credentials will be rejected.
    Default is `True`.

    Example of a URL containing credentials: “[https://user:pass@example.com/](https://user:pass@example.com/)”
  * **allow_fragments** (`bool`) – 

    Whether to allow fragments in requested URLs and in entries in the allow list.
    If set to `False`, fragments will not be allowed. Default is `True`.

    We consider URLs following the generic-URL syntax as defined in [RFC 1808](https://datatracker.ietf.org/doc/html/rfc1808.html):
    `<scheme>://<net_loc>/<path>;<params>?<query>#<fragment>`
  * **default_ports** (`Dict`[`str`, `int`]) – A dictionary containing default schemes and their respective ports.
    These ports will be removed from URLs requested or from entries in the allow list during URL normalization.
    Default is `{'http': 80, 'https': 443}`.
  * **input_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Input descriptors of the step. `None` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
  * **output_descriptors** (`Optional`[`List`[[`Property`](#wayflowcore.property.Property)]]) – Output descriptors of the step. `None` means the step will resolve them automatically using its static
    configuration in a best effort manner.
  * **input_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **output_mapping** (`Optional`[`Dict`[`str`, `str`]]) – Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
* **Raises:**
  **ValueError** – Thrown when both `json_body` and `data` are set.

### Examples

```pycon
>>> from wayflowcore.steps.apicallstep import ApiCallStep
>>> from wayflowcore.property import Property, ListProperty, IntegerProperty
>>> call_current_weather_step = ApiCallStep(
...     url = "https://example.com/weather",     # call the URL https://example.com/weather
...     method = "GET",                          # using the GET method
...     params = {
...         "location": "zurich",                # hardcode a query parameter "location" to "zurich" (will result in a GET call to https://example.com/weather?location=zurich)
...     },
...     output_values_json = {                   # from the returned JSON extract the `.weather` and `.temperature.celsius` properties and put it on the IO system under the key `weather` and `temperature`
...         "weather": ".weather",
...         "temperature_c": ".temperature.celsius"
...     }
... )
>>>
>>> create_order_step = ApiCallStep(
...     url = "https://example.com/orders/{{ order_id }}",         # call the URL https://example.com/orders/{{ order_id }}
...     method = "POST",                            # using the POST method
...     json_body = {                               # sending an object which will automatically be transformed into JSON
...         "topic_id": 12345,                      # define a static body parameter
...         "item_id": "{{ item_id }}",             # define a templated body parameter. the value for {{ item_id }} will be taken from the IO system at runtime
...     },
...     params = {
...         "store_id": "{{ store_id }}",          # provide one templated query parameter called "store_id" which will take it's value from the IO system from key "store_id"
...     },
...     headers = {                                # set headers
...         "session_id": "{{ session_id }}",      # set header session_id. the value is coming from the IO system
...     },
...     output_values_json = {                     # from the returned JSON extract the `.weather` property and put it on the IO system under the key `weather`
...         "first_order_status": ".orders[0].status",                                                           # more complicated query,
...         ListProperty(
...             name="order_ids",
...             description="List of order ids",
...             item_type=IntegerProperty("inner_int")
...         ): "[.orders[].id]",  # extract a list of values
...     },
...     url_allow_list = ["https://example.com/orders/"] # Example usage of allow_list: Domains and base path are allowed explicitly. We allow any downstream path elements (like the order id in this example) since only the beginning of the path needs to precisely match. All other URLs are rejected.
... )
>>>
>>> call_current_weather_step = ApiCallStep(
...     url = "https://user:pass@example.com/weather",     # call the URL https://example.com/weather
...     method = "GET",                          # using the GET method
...     params = {
...         "location": "zurich",                # hardcode a query parameter "location" to "zurich" (will result in a GET call to https://example.com/weather?location=zurich)
...     },
...     output_values_json = {                   # from the returned JSON extract the `.weather` and `.temperature.celsius` properties and put it on the IO system under the key `weather` and `temperature`
...         "weather": ".weather",
...         "temperature_c": ".temperature.celsius"
...     },
...     allow_credentials = False,              # in this example requests will be rejected since we explicitly disallow credentials in the URL.
... )
>>>
>>> call_current_weather_step = ApiCallStep(
...     url = "https://example.com/weather#switzerland",     # call the URL https://example.com/weather
...     method = "GET",                          # using the GET method
...     params = {
...         "location": "zurich",                # hardcode a query parameter "location" to "zurich" (will result in a GET call to https://example.com/weather?location=zurich)
...     },
...     output_values_json = {                   # from the returned JSON extract the `.weather` and `.temperature.celsius` properties and put it on the IO system under the key `weather` and `temperature`
...         "weather": ".weather",
...         "temperature_c": ".temperature.celsius"
...     },
...     allow_fragments = False,              # in this example the requests will be rejected since we explicitly disallow fragments in the URL.
... )
>>>
```

#### HTTP_RESPONSE *= 'http_response'*

Output key for the http response resulting from the API call.

* **Type:**
  str

#### HTTP_STATUS_CODE *= 'http_status_code'*

Output key for the http status code resulting from the API call.

* **Type:**
  str

#### input_mapping *: Dict[str, str]*

#### output_mapping *: Dict[str, str]*

### *class* wayflowcore.stepdescription.StepDescription(step_name, description, displayed_step_name=None)

Data class that contains all the information needed to describe a step.
This is used by Steps in order to identify steps inside LLM prompts.

* **Parameters:**
  * **step_name** (*str*)
  * **description** (*str*)
  * **displayed_step_name** (*str*)

#### description *: `str`*

#### displayed_step_name *: `str`* *= None*

#### step_name *: `str`*

## Classes for the IO system properties

<a id="property"></a>

### *class* wayflowcore.property.Property(name='', description='', default_value=<class 'wayflowcore.property._empty_default'>, enum=None, \_validate_default_type=False, \_\_metadata_info_\_=<factory>)

Base class to describe an input/output value for a component (flow or agent).

* **Parameters:**
  * **name** (`str`) – Name of the property. Optional when the property is nested (e.g. `StringProperty` in a `ListProperty`)
  * **description** (`str`) – 

    Optional description of the variable.

    #### IMPORTANT
    It can be helpful to put a description in two cases:
    * to help potential users to know what this property is about, and simplify the usage of a potential `Step` using it
    * to help an LLM if it needs to generate values for this property (e.g. in `PromptExecutionStep` or `AgentExecutionStep`).
  * **default_value** (`Any`) – 

    Optional default value. By default, there is no default value (`Property.empty_default`), meaning that if a component has this property
    as input, the value will need to be produced or passed before (it will appear as an input of an
    `Agent`/`Flow` OR it needs to be produced by a previous `Step` in a `Flow`).

    #### IMPORTANT
    Setting a default value might be needed in several cases:
    * when **generating a value for a property** (e.g. `PromptExecutionStep` or `AgentExecutionStep`), it is
      possible that the LLM is not able to generate the value. In this case, the default value of the given property
      type will be used, but you can specify your own `default_value`.
    * when **a value might not be yet produced / not passed as input** in a `Flow` (e.g. caught exception, some other branch execution, …),
      but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
      the flow can always execute properly with some defaults if needed.
  * **enum** (`Optional`[`Tuple`[`Any`, `...`]]) – Restricted accepted values of this property (in the case of an enumeration).
    In case of validation, the first value in this tuple as default of the property.
  * **\_validate_default_type** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### copy(name=None, description=None, default_value=None, enum=None)

Copy a `Property` with potentially some new attributes.

* **Parameters:**
  * **name** (`Optional`[`str`]) – Optional name to override this property’s name. By default uses the same name.
  * **description** (`Optional`[`str`]) – Optional description to override this property’s description. By default uses the same description.
  * **default_value** (`Optional`[`Any`]) – Optional default_value to override this property’s default_value. By default uses the same default_value.
  * **enum** (`Optional`[`Tuple`[`Any`, `...`]]) – Values for an enumeration.
* **Return type:**
  [`Property`](#wayflowcore.property.Property)

#### default_value

alias of [`_empty_default`](#wayflowcore.property._empty_default)

#### description *: `str`* *= ''*

#### empty_default

Any: Marker for no default value

alias of [`_empty_default`](#wayflowcore.property._empty_default)

#### enum *: `Optional`[`Tuple`[`Any`, `...`]]* *= None*

#### *static* from_json_schema(schema, name=None, description=None, default_value=None, enum=None, validate_default_type=True)

Convert a JSON Schema into a `Property` object.

* **Parameters:**
  * **schema** ([`JsonSchemaParam`](#wayflowcore.property.JsonSchemaParam)) – JSON Schema to convert.
  * **name** (`Optional`[`str`]) – Optional name to override the `title` that might exist in the JSON Schema.
  * **description** (`Optional`[`str`]) – Optional description to override the `description` that might exist in the JSON Schema.
  * **default_value** (`Optional`[`Any`]) – Optional default_value to override the `default` that might exist in the JSON Schema
  * **enum** (`Optional`[`Tuple`[`Any`, `...`]]) – Potential values for a enumeration
  * **validate_default_type** (`bool`) – Whether to ensure that any default_value has the correct type.
* **Return type:**
  [`Property`](#wayflowcore.property.Property)

#### get_python_type_str()

* **Return type:**
  `str`

#### get_type_str()

* **Return type:**
  `str`

#### *property* has_default *: bool*

Whether this property has a default value or not

#### is_value_of_expected_type(value)

Check whether a value corresponds to this property’s type.

* **Parameters:**
  **value** (`Any`) – value for which to check the type
* **Return type:**
  `bool`

#### name *: `str`* *= ''*

#### pretty_str()

* **Return type:**
  `str`

#### to_json_schema(openai_compatible=False)

Convert this `Property` object into a corresponding JSON Schema.

* **Parameters:**
  **openai_compatible** (`bool`) – Adds additional properties into the JSON schema to ensure valid
  requests are made to OpenAI compatible APIs in `strict` mode.
  Note that this will make all properties required in the resulting
  JSON schema. If you need a parameter to be optional, you can achieve
  this behaviour by unioning it with the `NullProperty`.
* **Return type:**
  [`JsonSchemaParam`](#wayflowcore.property.JsonSchemaParam)

<a id="booleanproperty"></a>

### *class* wayflowcore.property.BooleanProperty(name='', description='', default_value=<class 'wayflowcore.property._empty_default'>, enum=None, \_validate_default_type=False, \_\_metadata_info_\_=<factory>)

Class to describe a boolean input/output value for a component (flow or agent).
Its JSON type equivalent is `boolean`.

* **Parameters:**
  * **name** (`str`) – Name of the property. Optional when the property is nested (e.g. `StringProperty` in a `ListProperty`)
  * **description** (`str`) – 

    Optional description of the variable.

    #### IMPORTANT
    It can be helpful to put a description in two cases:
    * to help potential users to know what this property is about, and simplify the usage of a potential `Step` using it
    * to help an LLM if it needs to generate values for this property (e.g. in `PromptExecutionStep` or `AgentExecutionStep`).
  * **default_value** (`Any`) – 

    Optional default value. By default, there is no default value (`Property.empty_default`), meaning that if a component has this property
    as input, the value will need to be produced or passed before (it will appear as an input of an
    `Agent`/`Flow` OR it needs to be produced by a previous `Step` in a `Flow`).

    #### IMPORTANT
    Setting a default value might be needed in several cases:
    * when **generating a value for a property** (e.g. `PromptExecutionStep` or `AgentExecutionStep`), it is
      possible that the LLM is not able to generate the value. In this case, the default value of the given property
      type will be used, but you can specify your own `default_value`.
    * when **a value might not be yet produced / not passed as input** in a `Flow` (e.g. caught exception, some other branch execution, …),
      but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
      the flow can always execute properly with some defaults if needed.
  * **enum** (*Tuple* *[**Any* *,*  *...* *]*  *|* *None*)
  * **\_validate_default_type** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

<a id="floatproperty"></a>

### *class* wayflowcore.property.FloatProperty(name='', description='', default_value=<class 'wayflowcore.property._empty_default'>, enum=None, \_validate_default_type=False, \_\_metadata_info_\_=<factory>)

Class to describe a float input/output value for a component (flow or agent).
Its JSON type equivalent is `number`.

* **Parameters:**
  * **name** (`str`) – Name of the property. Optional when the property is nested (e.g. `StringProperty` in a `ListProperty`)
  * **description** (`str`) – 

    Optional description of the variable.

    #### IMPORTANT
    It can be helpful to put a description in two cases:
    * to help potential users to know what this property is about, and simplify the usage of a potential `Step` using it
    * to help an LLM if it needs to generate values for this property (e.g. in `PromptExecutionStep` or `AgentExecutionStep`).
  * **default_value** (`Any`) – 

    Optional default value. By default, there is no default value (`Property.empty_default`), meaning that if a component has this property
    as input, the value will need to be produced or passed before (it will appear as an input of an
    `Agent`/`Flow` OR it needs to be produced by a previous `Step` in a `Flow`).

    #### IMPORTANT
    Setting a default value might be needed in several cases:
    * when **generating a value for a property** (e.g. `PromptExecutionStep` or `AgentExecutionStep`), it is
      possible that the LLM is not able to generate the value. In this case, the default value of the given property
      type will be used, but you can specify your own `default_value`.
    * when **a value might not be yet produced / not passed as input** in a `Flow` (e.g. caught exception, some other branch execution, …),
      but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
      the flow can always execute properly with some defaults if needed.
  * **enum** (*Tuple* *[**Any* *,*  *...* *]*  *|* *None*)
  * **\_validate_default_type** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

<a id="messageproperty"></a>

### *class* wayflowcore.property.MessageProperty(name='', description='', default_value=<class 'wayflowcore.property._empty_default'>, enum=None, \_validate_default_type=False, \_\_metadata_info_\_=<factory>)

Class to describe a message input/output value for a component (flow or agent).

* **Parameters:**
  * **name** (`str`) – Name of the property. Optional when the property is nested (e.g. `StringProperty` in a `ListProperty`)
  * **description** (`str`) – 

    Optional description of the variable.

    #### IMPORTANT
    It can be helpful to put a description in two cases:
    * to help potential users to know what this property is about, and simplify the usage of a potential `Step` using it
    * to help an LLM if it needs to generate values for this property (e.g. in `PromptExecutionStep` or `AgentExecutionStep`).
  * **default_value** (`Any`) – 

    Optional default value. By default, there is no default value (`Property.empty_default`), meaning that if a component has this property
    as input, the value will need to be produced or passed before (it will appear as an input of an
    `Agent`/`Flow` OR it needs to be produced by a previous `Step` in a `Flow`).

    #### IMPORTANT
    Setting a default value might be needed in several cases:
    * when **generating a value for a property** (e.g. `PromptExecutionStep` or `AgentExecutionStep`), it is
      possible that the LLM is not able to generate the value. In this case, the default value of the given property
      type will be used, but you can specify your own `default_value`.
    * when **a value might not be yet produced / not passed as input** in a `Flow` (e.g. caught exception, some other branch execution, …),
      but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
      the flow can always execute properly with some defaults if needed.
  * **enum** (*Tuple* *[**Any* *,*  *...* *]*  *|* *None*)
  * **\_validate_default_type** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

<a id="integerproperty"></a>

### *class* wayflowcore.property.IntegerProperty(name='', description='', default_value=<class 'wayflowcore.property._empty_default'>, enum=None, \_validate_default_type=False, \_\_metadata_info_\_=<factory>)

Class to describe an integer input/output value for a component (flow or agent).
Its JSON type equivalent is `integer`.

* **Parameters:**
  * **name** (`str`) – Name of the property. Optional when the property is nested (e.g. `StringProperty` in a `ListProperty`)
  * **description** (`str`) – 

    Optional description of the variable.

    #### IMPORTANT
    It can be helpful to put a description in two cases:
    * to help potential users to know what this property is about, and simplify the usage of a potential `Step` using it
    * to help an LLM if it needs to generate values for this property (e.g. in `PromptExecutionStep` or `AgentExecutionStep`).
  * **default_value** (`Any`) – 

    Optional default value. By default, there is no default value (`Property.empty_default`), meaning that if a component has this property
    as input, the value will need to be produced or passed before (it will appear as an input of an
    `Agent`/`Flow` OR it needs to be produced by a previous `Step` in a `Flow`).

    #### IMPORTANT
    Setting a default value might be needed in several cases:
    * when **generating a value for a property** (e.g. `PromptExecutionStep` or `AgentExecutionStep`), it is
      possible that the LLM is not able to generate the value. In this case, the default value of the given property
      type will be used, but you can specify your own `default_value`.
    * when **a value might not be yet produced / not passed as input** in a `Flow` (e.g. caught exception, some other branch execution, …),
      but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
      the flow can always execute properly with some defaults if needed.
  * **enum** (*Tuple* *[**Any* *,*  *...* *]*  *|* *None*)
  * **\_validate_default_type** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

<a id="stringproperty"></a>

### *class* wayflowcore.property.StringProperty(name='', description='', default_value=<class 'wayflowcore.property._empty_default'>, enum=None, \_validate_default_type=False, \_\_metadata_info_\_=<factory>)

Class to describe a string input/output value for a component (flow or agent).
Its JSON type equivalent is `string`.

* **Parameters:**
  * **name** (`str`) – Name of the property. Optional when the property is nested (e.g. `StringProperty` in a `ListProperty`)
  * **description** (`str`) – 

    Optional description of the variable.

    #### IMPORTANT
    It can be helpful to put a description in two cases:
    * to help potential users to know what this property is about, and simplify the usage of a potential `Step` using it
    * to help an LLM if it needs to generate values for this property (e.g. in `PromptExecutionStep` or `AgentExecutionStep`).
  * **default_value** (`Any`) – 

    Optional default value. By default, there is no default value (`Property.empty_default`), meaning that if a component has this property
    as input, the value will need to be produced or passed before (it will appear as an input of an
    `Agent`/`Flow` OR it needs to be produced by a previous `Step` in a `Flow`).

    #### IMPORTANT
    Setting a default value might be needed in several cases:
    * when **generating a value for a property** (e.g. `PromptExecutionStep` or `AgentExecutionStep`), it is
      possible that the LLM is not able to generate the value. In this case, the default value of the given property
      type will be used, but you can specify your own `default_value`.
    * when **a value might not be yet produced / not passed as input** in a `Flow` (e.g. caught exception, some other branch execution, …),
      but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
      the flow can always execute properly with some defaults if needed.
  * **enum** (*Tuple* *[**Any* *,*  *...* *]*  *|* *None*)
  * **\_validate_default_type** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

<a id="anyproperty"></a>

### *class* wayflowcore.property.AnyProperty(name='', description='', default_value=<class 'wayflowcore.property._empty_default'>, enum=None, \_validate_default_type=False, \_\_metadata_info_\_=<factory>)

Class to describe any input/output value for a component (flow or agent).

* **Parameters:**
  * **name** (`str`) – Name of the property. Optional when the property is nested (e.g. `StringProperty` in a `ListProperty`)
  * **description** (`str`) – 

    Optional description of the variable.

    #### IMPORTANT
    It can be helpful to put a description in two cases:
    * to help potential users to know what this property is about, and simplify the usage of a potential `Step` using it
    * to help an LLM if it needs to generate values for this property (e.g. in `PromptExecutionStep` or `AgentExecutionStep`).
  * **default_value** (`Any`) – 

    Optional default value. By default, there is no default value (`Property.empty_default`), meaning that if a component has this property
    as input, the value will need to be produced or passed before (it will appear as an input of an
    `Agent`/`Flow` OR it needs to be produced by a previous `Step` in a `Flow`).

    #### IMPORTANT
    Setting a default value might be needed in several cases:
    * when **generating a value for a property** (e.g. `PromptExecutionStep` or `AgentExecutionStep`), it is
      possible that the LLM is not able to generate the value. In this case, the default value of the given property
      type will be used, but you can specify your own `default_value`.
    * when **a value might not be yet produced / not passed as input** in a `Flow` (e.g. caught exception, some other branch execution, …),
      but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
      the flow can always execute properly with some defaults if needed.
  * **enum** (*Tuple* *[**Any* *,*  *...* *]*  *|* *None*)
  * **\_validate_default_type** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

<a id="listproperty"></a>

### *class* wayflowcore.property.ListProperty(name='', description='', default_value=<class 'wayflowcore.property._empty_default'>, enum=None, \_validate_default_type=False, \_\_metadata_info_\_=<factory>, item_type=<factory>)

Class to describe a list input/output value for a component (flow or agent). It also contains the type
of its items.
Its JSON type equivalent is `array`.

* **Parameters:**
  * **name** (`str`) – Name of the property. Optional when the property is nested (e.g. `StringProperty` in a `ListProperty`)
  * **description** (`str`) – 

    Optional description of the variable.

    #### IMPORTANT
    It can be helpful to put a description in two cases:
    * to help potential users to know what this property is about, and simplify the usage of a potential `Step` using it
    * to help an LLM if it needs to generate values for this property (e.g. in `PromptExecutionStep` or `AgentExecutionStep`).
  * **default_value** (`Any`) – 

    Optional default value. By default, there is no default value (`Property.empty_default`), meaning that if a component has this property
    as input, the value will need to be produced or passed before (it will appear as an input of an
    `Agent`/`Flow` OR it needs to be produced by a previous `Step` in a `Flow`).

    #### IMPORTANT
    Setting a default value might be needed in several cases:
    * when **generating a value for a property** (e.g. `PromptExecutionStep` or `AgentExecutionStep`), it is
      possible that the LLM is not able to generate the value. In this case, the default value of the given property
      type will be used, but you can specify your own `default_value`.
    * when **a value might not be yet produced / not passed as input** in a `Flow` (e.g. caught exception, some other branch execution, …),
      but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
      the flow can always execute properly with some defaults if needed.
  * **item_type** ([`Property`](#wayflowcore.property.Property)) – Type of the items of the list. Defaults to `StringProperty`.
  * **enum** (*Tuple* *[**Any* *,*  *...* *]*  *|* *None*)
  * **\_validate_default_type** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### get_type_str()

* **Return type:**
  `str`

#### item_type *: [`Property`](#wayflowcore.property.Property)*

<a id="dictproperty"></a>

### *class* wayflowcore.property.DictProperty(name='', description='', default_value=<class 'wayflowcore.property._empty_default'>, enum=None, \_validate_default_type=False, \_\_metadata_info_\_=<factory>, value_type=<factory>, key_type=<factory>)

Class to describe a dictionary input/output value for a component (flow or agent). It also contains the type
if its keys and its values.
Its JSON type equivalent is `object` with `additionalProperties`.

* **Parameters:**
  * **name** (`str`) – Name of the property. Optional when the property is nested (e.g. `StringProperty` in a `ListProperty`)
  * **description** (`str`) – 

    Optional description of the variable.

    #### IMPORTANT
    It can be helpful to put a description in two cases:
    * to help potential users to know what this property is about, and simplify the usage of a potential `Step` using it
    * to help an LLM if it needs to generate values for this property (e.g. in `PromptExecutionStep` or `AgentExecutionStep`).
  * **default_value** (`Any`) – 

    Optional default value. By default, there is no default value (`Property.empty_default`), meaning that if a component has this property
    as input, the value will need to be produced or passed before (it will appear as an input of an
    `Agent`/`Flow` OR it needs to be produced by a previous `Step` in a `Flow`).

    #### IMPORTANT
    Setting a default value might be needed in several cases:
    * when **generating a value for a property** (e.g. `PromptExecutionStep` or `AgentExecutionStep`), it is
      possible that the LLM is not able to generate the value. In this case, the default value of the given property
      type will be used, but you can specify your own `default_value`.
    * when **a value might not be yet produced / not passed as input** in a `Flow` (e.g. caught exception, some other branch execution, …),
      but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
      the flow can always execute properly with some defaults if needed.
  * **value_type** ([`Property`](#wayflowcore.property.Property)) – Type of the values of the dict. Defaults to `StringProperty`.
  * **key_type** ([`Property`](#wayflowcore.property.Property)) – Type of the keys of the dict. Defaults to `StringProperty`.
  * **enum** (*Tuple* *[**Any* *,*  *...* *]*  *|* *None*)
  * **\_validate_default_type** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### get_type_str()

* **Return type:**
  `str`

#### key_type *: [`Property`](#wayflowcore.property.Property)*

#### value_type *: [`Property`](#wayflowcore.property.Property)*

<a id="objectproperty"></a>

### *class* wayflowcore.property.ObjectProperty(name='', description='', default_value=<class 'wayflowcore.property._empty_default'>, enum=None, \_validate_default_type=False, \_\_metadata_info_\_=<factory>, properties=<factory>)

Class to describe an object input/output value for a component (flow or agent). It contains the names of its
properties and their associated types. It supports both dictionaries with specific keys & types and objects with
specific attributes & types.
Its JSON type equivalent is `object` with `properties`.

* **Parameters:**
  * **name** (`str`) – Name of the property. Optional when the property is nested (e.g. `StringProperty` in a `ListProperty`)
  * **description** (`str`) – 

    Optional description of the variable.

    #### IMPORTANT
    It can be helpful to put a description in two cases:
    * to help potential users to know what this property is about, and simplify the usage of a potential `Step` using it
    * to help an LLM if it needs to generate values for this property (e.g. in `PromptExecutionStep` or `AgentExecutionStep`).
  * **default_value** (`Any`) – 

    Optional default value. By default, there is no default value (`Property.empty_default`), meaning that if a component has this property
    as input, the value will need to be produced or passed before (it will appear as an input of an
    `Agent`/`Flow` OR it needs to be produced by a previous `Step` in a `Flow`).

    #### IMPORTANT
    Setting a default value might be needed in several cases:
    * when **generating a value for a property** (e.g. `PromptExecutionStep` or `AgentExecutionStep`), it is
      possible that the LLM is not able to generate the value. In this case, the default value of the given property
      type will be used, but you can specify your own `default_value`.
    * when **a value might not be yet produced / not passed as input** in a `Flow` (e.g. caught exception, some other branch execution, …),
      but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
      the flow can always execute properly with some defaults if needed.
  * **properties** (`Dict`[`str`, [`Property`](#wayflowcore.property.Property)]) – Dictionary of property names and their types. Defaults without any property.
  * **enum** (*Tuple* *[**Any* *,*  *...* *]*  *|* *None*)
  * **\_validate_default_type** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### get_type_str()

* **Return type:**
  `str`

#### properties *: `Dict`[`str`, [`Property`](#wayflowcore.property.Property)]*

<a id="unionproperty"></a>

### *class* wayflowcore.property.UnionProperty(name='', description='', default_value=<class 'wayflowcore.property._empty_default'>, enum=None, \_validate_default_type=False, \_\_metadata_info_\_=<factory>, any_of=<factory>)

* **Parameters:**
  * **name** (*str*)
  * **description** (*str*)
  * **default_value** (*Any*)
  * **enum** (*Tuple* *[**Any* *,*  *...* *]*  *|* *None*)
  * **\_validate_default_type** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **any_of** (*List* *[*[*Property*](#wayflowcore.property.Property) *]*)

#### any_of *: `List`[[`Property`](#wayflowcore.property.Property)]*

#### get_type_str()

* **Return type:**
  `str`

<a id="nullproperty"></a>

### *class* wayflowcore.property.NullProperty(name='', description='', default_value=<class 'wayflowcore.property._empty_default'>, enum=None, \_validate_default_type=False, \_\_metadata_info_\_=<factory>)

* **Parameters:**
  * **name** (*str*)
  * **description** (*str*)
  * **default_value** (*Any*)
  * **enum** (*Tuple* *[**Any* *,*  *...* *]*  *|* *None*)
  * **\_validate_default_type** (*bool*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

### *class* wayflowcore.property.\_empty_default

Marker object for Property.empty_default

### *class* wayflowcore.property.JsonSchemaParam

#### additionalProperties *: `Union`[[`JsonSchemaParam`](#wayflowcore.property.JsonSchemaParam), `bool`]*

#### anyOf *: `List`[[`JsonSchemaParam`](#wayflowcore.property.JsonSchemaParam)]*

#### default *: `Any`*

#### description *: `Optional`[`str`]*

#### enum *: `List`[`Any`]*

#### key_type *: [`JsonSchemaParam`](#wayflowcore.property.JsonSchemaParam)*

#### properties *: `Dict`[`str`, [`JsonSchemaParam`](#wayflowcore.property.JsonSchemaParam)]*

#### required *: `List`[`str`]*

#### title *: `str`*

#### type *: `Union`[`str`, `List`[`str`]]*

## Other classes and helpers used in fixed flows

<a id="assistantstepresult"></a>

### *class* wayflowcore.steps.step.StepResult(outputs, branch_name='next', step_type=StepExecutionStatus.PASSTHROUGH)

Output information collected from the execution of a `Step`.

* **Parameters:**
  * **outputs** (`Dict`[`str`, `Any`]) – Dictionary of outputs collected from the executed `Step`.
  * **branch_name** (`str`) – Name of the control flow branch the step is taking.
  * **step_type** ([`StepExecutionStatus`](#wayflowcore.steps.step.StepExecutionStatus)) – Whether we want to be able to go back to this step (`StepExecutionStatus.YIELDING`) or simply continue with the next step (`StepExecutionStatus.PASSTHROUGH`).

#### branch_name *: `str`* *= 'next'*

#### outputs *: `Dict`[`str`, `Any`]*

#### step_type *: [`StepExecutionStatus`](#wayflowcore.steps.step.StepExecutionStatus)* *= 'PASSTHROUGH'*

### *class* wayflowcore.steps.step.StepExecutionStatus(value)

Enumeration for the type of an assistant step.
This mainly influences whether to stop and go back to the invoker (yielding step)
for example to ask user input, or to just continue to the next step (passthrough step).

#### INTERRUPTED *= 'INTERRUPTED'*

#### PASSTHROUGH *= 'PASSTHROUGH'*

#### YIELDING *= 'YIELDING'*

### *class* wayflowcore.flowhelpers.run_step_and_return_outputs(step, inputs=None, messages=None, context_providers=None)

Helper function to run a step with some inputs and return the outputs of the step.

* **Parameters:**
  * **step** ([`Step`](#wayflowcore.steps.step.Step)) – Step to run
  * **inputs** (`Optional`[`Dict`[`str`, `Any`]]) – Inputs for the step. Need to contain all expected inputs of the step. Their names and types
    can be checked using `step.input_descriptors`.
  * **messages** (`Optional`[`List`[[`Message`](conversation.md#wayflowcore.messagelist.Message)]]) – List of previous messages
  * **user_input** – Initial message from the user
  * **context_providers** (*List* *[*[*ContextProvider*](contextproviders.md#wayflowcore.contextproviders.contextprovider.ContextProvider) *]*  *|* *None*)
* **Return type:**
  `Dict`[`str`, `Any`]

### Examples

```pycon
>>> from wayflowcore.steps import PromptExecutionStep
>>> from wayflowcore.flowhelpers import run_step_and_return_outputs
>>> step = PromptExecutionStep(
...     llm=llm,
...     prompt_template="What is the capital of {{country}}?"
... )
>>> outputs = run_step_and_return_outputs(step, inputs={'country': 'Switzerland'})
>>> # {"output": "the capital of Switzerland is Bern"}
```

### *class* wayflowcore.flowhelpers.run_flow_and_return_outputs(flow, inputs=None, messages=None)

Runs a Flow until completion and returns the outputs of the flow. It should not use any ClientTool nor Agent.

* **Parameters:**
  * **flow** ([`Flow`](#wayflowcore.flow.Flow)) – Flow to run
  * **inputs** (`Optional`[`Dict`[`str`, `Any`]]) – Inputs for the flow. Need to contain all expected inputs of the flow. Their names and types
    can be checked using `flow.input_descriptors`.
  * **messages** (`Optional`[`List`[[`Message`](conversation.md#wayflowcore.messagelist.Message)]]) – Initial messages of the conversation
* **Return type:**
  `Dict`[`str`, `Any`]

### Examples

```pycon
>>> from wayflowcore.steps import PromptExecutionStep, BranchingStep, OutputMessageStep
>>> from wayflowcore.controlconnection import ControlFlowEdge
>>> from wayflowcore.flow import Flow
>>> from wayflowcore.flowhelpers import run_flow_and_return_outputs
>>> generation_step = PromptExecutionStep(
...     llm=llm,
...     prompt_template="What is the capital of {{country}}? Only answer by the name of city, and the name of the city only.",
...     name='generation',
... )
>>> branching_step = BranchingStep(
...     branch_name_mapping={'bern': 'success'}, name='branching'
... )
>>> success_step = OutputMessageStep('Well done, llama!', name='success')
>>> failure_step = OutputMessageStep("That's not it...", name='failure')
>>> flow = Flow(
...     begin_step=generation_step,
...     control_flow_edges=[
...         ControlFlowEdge(source_step=generation_step, destination_step=branching_step),
...         ControlFlowEdge(source_step=branching_step, destination_step=success_step, source_branch='success'),
...         ControlFlowEdge(source_step=branching_step, destination_step=failure_step, source_branch=branching_step.BRANCH_DEFAULT),
...         ControlFlowEdge(source_step=success_step, destination_step=None),
...         ControlFlowEdge(source_step=failure_step, destination_step=None),
...     ],
... )
>>> outputs = run_flow_and_return_outputs(flow, inputs={'country': 'Switzerland'})
```

### *class* wayflowcore.flowhelpers.create_single_step_flow(step, step_name='single_step', context_providers=None, data_flow_edges=None, variables=None, flow_name=None, flow_description='')

Create a flow that consist of one step only

* **Parameters:**
  * **step** ([`Step`](#wayflowcore.steps.step.Step)) – the step that this flow should consist of
  * **step_name** (`str`) – the name of the single step
  * **context_providers** (`Union`[`Dict`[[`Property`](#wayflowcore.property.Property), `Callable`[[[`Conversation`](conversation.md#wayflowcore.conversation.Conversation)], `Any`]], `List`[[`ContextProvider`](contextproviders.md#wayflowcore.contextproviders.contextprovider.ContextProvider)], `None`]) – context providers that should be available to the assistant
  * **data_flow_edges** (`Optional`[`List`[[`DataFlowEdge`](#wayflowcore.dataconnection.DataFlowEdge)]]) – list of data flow edges
  * **variables** (`Optional`[`List`[[`Variable`](variables.md#wayflowcore.variable.Variable)]]) – list of variables of the flow
  * **flow_name** (`Optional`[`str`]) – optional name of the flow
  * **flow_description** (`str`) – optional description of the flow
* **Return type:**
  [`Flow`](#wayflowcore.flow.Flow)

## Flow Builder

The Flow Builder provides a concise, chainable API to assemble WayFlow Flows programmatically.
It helps wire control and data edges, use conditional branching, set entry/finish points,
and serialize flows to JSON/YAML.

See code examples in the [Reference Sheet](../misc/reference_sheet.md#flowbuilder-ref-sheet).

<a id="flowbuilder"></a>

### *class* wayflowcore.flowbuilder.FlowBuilder

A builder for constructing WayFlow Flows.

#### add_conditional(source_step, source_value, destination_map, default_destination, branching_step_name=None)

Add a condition/branching to the Flow.

* **Parameters:**
  * **source_step** ([`Step`](#wayflowcore.steps.step.Step) | `str`) – Step/name from which to start the branching from.
  * **source_value** (`str` | `tuple`[[`Step`](#wayflowcore.steps.step.Step) | `str`, `str`]) – Which value to use to perform the branching condition. If str, uses the source_step.
    If tuple[Step | str, str], uses the specified step and output name.
  * **destination_map** (`dict`[`str`, [`Step`](#wayflowcore.steps.step.Step) | `str`]) – Dictionary which specifies which step to transition to for given input values.
  * **default_destination** ([`Step`](#wayflowcore.steps.step.Step) | `str`) – Step/name where to transition to if no matching value/transition is found
    in the destination_map.
  * **branching_step_name** (`Optional`[`str`]) – Optional name for the branching step. Uses automatically generated auto-incrementing
    names if not providing.
* **Return type:**
  [`FlowBuilder`](#wayflowcore.flowbuilder.FlowBuilder)

### Example

```pycon
>>> from wayflowcore.flowbuilder import FlowBuilder
>>> from wayflowcore.steps import OutputMessageStep
>>>
>>> flow = (
...     FlowBuilder()
...     .add_step(OutputMessageStep(name="source_step", message_template="{{ value }}"))
...     .add_step(OutputMessageStep(name="fail_step", message_template="FAIL"))
...     .add_step(OutputMessageStep(name="success_step", message_template="SUCCESS"))
...     .add_conditional("source_step", OutputMessageStep.OUTPUT,
...                      {"success": "success_step", "fail": "fail_step"},
...                      default_destination="fail_step"
...     )
...     .set_entry_point("source_step")
...     .set_finish_points(["fail_step", "success_step"])
...     .build()
... )
```

#### add_data_edge(source_step, dest_step, data_name, edge_name=None)

Add a data flow edge to the Flow.

* **Parameters:**
  * **source_step** ([`Step`](#wayflowcore.steps.step.Step) | `str`) – Step/name which constitutes the start/source of the data flow edge.
  * **dest_step** ([`Step`](#wayflowcore.steps.step.Step) | `str`) – Step/name that constitutes the end/destination of the data flow edge.
  * **data_name** (`str` | `tuple`[`str`, `str`]) – Name of the data property to propagate between the two steps, either
    str when the name is shared, or tuple (source_output, destination_input)
    when the names are different.
  * **edge_name** (`Optional`[`str`]) – Name for the edge. Defaults to “data_flow_edge”
* **Return type:**
  [`FlowBuilder`](#wayflowcore.flowbuilder.FlowBuilder)

#### add_edge(source_step, dest_step, from_branch=None, edge_name=None)

Add a control flow edge to the Flow.

* **Parameters:**
  * **source_step** (`list`[[`Step`](#wayflowcore.steps.step.Step) | `str`] | [`Step`](#wayflowcore.steps.step.Step) | `str`) – Single step/name (creates 1 edge) or list of steps/names (creates N edges)
    which constitute the start of the control flow edge(s).
  * **dest_step** (`Union`[[`Step`](#wayflowcore.steps.step.Step), `str`, `None`]) – Step/name that constitutes the end of the control flow edge(s). Pass `None` to finish the flow
    from the source step(s).
  * **from_branch** (`Union`[`list`[`Optional`[`str`]], `str`, `None`]) – Optional source branch name(s) to use in the control flow edge(s).
    When a list, must be of the same length as the list of `source_step`.
  * **edge_name** (`Optional`[`str`]) – Name for the edge. Defaults to f”control_edge_{source_step.name}_{dest_step.name}_{from_branch}”.
* **Return type:**
  [`FlowBuilder`](#wayflowcore.flowbuilder.FlowBuilder)

#### add_sequence(steps)

Add a sequence of steps to the Flow and automatically
creates control flow edges between them.

* **Parameters:**
  **steps** (`list`[[`Step`](#wayflowcore.steps.step.Step)]) – List of steps to add to the Flow.
* **Return type:**
  [`FlowBuilder`](#wayflowcore.flowbuilder.FlowBuilder)

#### add_step(step)

Add a new step to the Flow.

* **Parameters:**
  **step** ([`Step`](#wayflowcore.steps.step.Step)) – Step to add to the Flow.
* **Return type:**
  [`FlowBuilder`](#wayflowcore.flowbuilder.FlowBuilder)

#### build(name='Flow', description='')

Build the Flow.

Will raise errors if encountering any while building the Flow.

* **Return type:**
  [`Flow`](#wayflowcore.flow.Flow)
* **Parameters:**
  * **name** (*str*)
  * **description** (*str*)

### Examples

```pycon
>>> from wayflowcore.flowbuilder import FlowBuilder
>>> from wayflowcore.steps import OutputMessageStep
>>>
>>> n1 = OutputMessageStep(name="n1", message_template="Hello")
>>> n2 = OutputMessageStep(name="n2", message_template="World")
>>>
>>> flow = (
...     FlowBuilder()
...     .add_sequence([n1, n2])
...     .set_entry_point(n1)
...     .set_finish_points(n2)
...     .build()
... )
```

#### build_agent_spec(name='Flow', serialize_as='JSON')

Build the Flow and return its Agent Spec JSON or YAML configuration.

Will raise errors if encountering any while building the Flow.

* **Return type:**
  `str`
* **Parameters:**
  * **name** (*str*)
  * **serialize_as** (*Literal* *[* *'JSON'* *,*  *'YAML'* *]*)

#### *classmethod* build_linear_flow(steps, name='Flow', serialize_as=None, data_flow_edges=None, input_descriptors=None, output_descriptors=None)

Build a linear flow from a list of steps.

* **Parameters:**
  * **steps** (`list`[[`Step`](#wayflowcore.steps.step.Step)]) – List of steps to use to create the linear/sequential Flow.
  * **serialize_as** (`Optional`[`Literal`[`'JSON'`, `'YAML'`]]) – Format for the returned object. If None, returns a WayFlow Flow.
    Otherwise, returns its Agent Spec configuration as JSON/YAML.
  * **data_flow_edges** (`Optional`[`list`[[`DataFlowEdge`](#wayflowcore.dataconnection.DataFlowEdge)]]) – Optional list of data flow edges.
  * **input_descriptors** (`Optional`[`list`[[`Property`](#wayflowcore.property.Property)]]) – Optional list of inputs for the flow. If None, auto-detects as the list of
    inputs that are not generated at some point in the execution of the flow.
  * **output_descriptors** (`Optional`[`list`[[`Property`](#wayflowcore.property.Property)]]) – Optional list of outputs for the flow. If None, auto-detects as the
    intersection of all the outputs generated by any step in any execution
    branch of the flow.
  * **name** (*str*)
* **Return type:**
  [`Flow`](#wayflowcore.flow.Flow) | `str`

#### set_entry_point(step, input_descriptors=None)

Sets the first step to execute in the Flow.

* **Parameters:**
  * **step** ([`Step`](#wayflowcore.steps.step.Step) | `str`) – Step/name that will first be run in the Flow.
  * **input_descriptors** (`Optional`[`list`[[`Property`](#wayflowcore.property.Property)]]) – Optional list of inputs for the flow. If None, auto-detects as the list of
    inputs that are not generated at some point in the execution of the flow.
* **Return type:**
  [`FlowBuilder`](#wayflowcore.flowbuilder.FlowBuilder)

#### set_finish_points(step, output_descriptors=None)

Specifies the potential points of completion of the Flow.

* **Parameters:**
  * **step** (`list`[[`Step`](#wayflowcore.steps.step.Step) | `str`] | [`Step`](#wayflowcore.steps.step.Step) | `str`) – Step/name or list of steps/names which are terminal steps in the Flow.
  * **output_descriptors** (`Optional`[`list`[[`Property`](#wayflowcore.property.Property)]]) – Optional list of outputs for the flow. If None, auto-detects as the
    intersection of all the outputs generated by any step in any execution
    branch of the flow.
* **Return type:**
  [`FlowBuilder`](#wayflowcore.flowbuilder.FlowBuilder)
