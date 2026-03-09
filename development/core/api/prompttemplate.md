# PromptTemplate

This page presents all APIs and classes related to prompt Templates.

<a id="id1"></a>

### *class* wayflowcore.templates.template.PromptTemplate(messages, output_parser=None, input_descriptors=None, pre_rendering_transforms=None, post_rendering_transforms=None, tools=None, native_tool_calling=True, response_format=None, native_structured_generation=True, generation_config=None, \_partial_values=<factory>, \*, id=<factory>, \_\_metadata_info_\_=<factory>, name='', description=None)

Represents a flexible and extensible template for constructing prompts to be sent to large language models (LLMs).

The PromptTemplate class enables the definition of prompt messages with variable placeholders, supports both
native and custom tool calling, and allows for structured output generation.
It manages input descriptors, message transforms (pre- and post chat_history rendering), and partial formatting
for efficiency.
The class also integrates with output parsers, tools and llm generation configurations.

* **Parameters:**
  * **messages** (*Sequence* *[*[*Message*](conversation.md#wayflowcore.messagelist.Message) *|* [*MessageAsDictT*](#wayflowcore._utils._templating_helpers.MessageAsDictT) *]*)
  * **output_parser** ([*OutputParser*](#wayflowcore.outputparser.OutputParser) *|* *List* *[*[*OutputParser*](#wayflowcore.outputparser.OutputParser) *]*  *|* *None*)
  * **input_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*  *|* *None*)
  * **pre_rendering_transforms** (*List* *[*[*MessageTransform*](#wayflowcore.transforms.MessageTransform) *]*  *|* *None*)
  * **post_rendering_transforms** (*List* *[*[*MessageTransform*](#wayflowcore.transforms.MessageTransform) *]*  *|* *None*)
  * **tools** (*List* *[*[*Tool*](tools.md#wayflowcore.tools.tools.Tool) *]*  *|* *None*)
  * **native_tool_calling** (*bool*)
  * **response_format** ([*Property*](flows.md#wayflowcore.property.Property) *|* *None*)
  * **native_structured_generation** (*bool*)
  * **generation_config** ([*LlmGenerationConfig*](llmmodels.md#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig) *|* *None*)
  * **\_partial_values** (*Dict* *[**str* *,* *Any* *]*)
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)

#### CHAT_HISTORY_PLACEHOLDER *: `ClassVar`[[`Message`](conversation.md#wayflowcore.messagelist.Message)]* *= Message(id='fa8fad8d-c312-4d31-92d2-b9e9660e6d95', \_\_metadata_info_\_={}, role='system', contents=[TextContent(content='$$_\_CHAT_HISTORY_PLACEHOLDER_\_$$')], tool_requests=None, tool_result=None, display_only=False, \_prompt_cache_key=None, \_reasoning_content=None, sender=None, recipients=set(), \_extra_content=None)*

Message placeholder in case the chat history is formatted as a chat.

#### CHAT_HISTORY_PLACEHOLDER_NAME *: `ClassVar`[`str`]* *= '_\_CHAT_HISTORY_\_'*

Reserved name of the placeholder for the chat history, if rendered in one message.

#### RESPONSE_FORMAT_PLACEHOLDER_NAME *: `ClassVar`[`str`]* *= '_\_RESPONSE_FORMAT_\_'*

Reserved name of the placeholder for the expected output format. Only used if non-native structured
generation, to be able to specify the JSON format anywhere in the prompt.

#### TOOL_PLACEHOLDER_NAME *: `ClassVar`[`str`]* *= '_\_TOOLS_\_'*

Reserved name of the placeholder for tools.

#### copy()

Returns a copy of the template.

* **Return type:**
  [`PromptTemplate`](#wayflowcore.templates.template.PromptTemplate)

#### format(inputs=None, chat_history=None)

Formats the prompt into a list of messages to pass to the LLM

* **Return type:**
  [`Prompt`](llmmodels.md#wayflowcore.models.Prompt)
* **Parameters:**
  * **inputs** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **chat_history** (*List* *[*[*Message*](conversation.md#wayflowcore.messagelist.Message) *]*  *|* *None*)

#### *async* format_async(inputs=None, chat_history=None)

Synchronously formats the prompt into a list of messages to pass to the LLM

* **Return type:**
  [`Prompt`](llmmodels.md#wayflowcore.models.Prompt)
* **Parameters:**
  * **inputs** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **chat_history** (*List* *[*[*Message*](conversation.md#wayflowcore.messagelist.Message) *]*  *|* *None*)

#### *classmethod* from_string(template, output_parser=None, input_descriptors=None, pre_rendering_transforms=None, post_rendering_transforms=None, tools=None, native_tool_calling=True, response_format=None, native_structured_generation=True, generation_config=None)

Creates a prompt template from a string.

* **Return type:**
  [`PromptTemplate`](#wayflowcore.templates.template.PromptTemplate)
* **Parameters:**
  * **template** (*str*)
  * **output_parser** ([*OutputParser*](#wayflowcore.outputparser.OutputParser) *|* *None*)
  * **input_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*  *|* *None*)
  * **pre_rendering_transforms** (*List* *[*[*MessageTransform*](#wayflowcore.transforms.MessageTransform) *]*  *|* *None*)
  * **post_rendering_transforms** (*List* *[*[*MessageTransform*](#wayflowcore.transforms.MessageTransform) *]*  *|* *None*)
  * **tools** (*List* *[*[*Tool*](tools.md#wayflowcore.tools.tools.Tool) *]*  *|* *None*)
  * **native_tool_calling** (*bool*)
  * **response_format** ([*Property*](flows.md#wayflowcore.property.Property) *|* *None*)
  * **native_structured_generation** (*bool*)
  * **generation_config** ([*LlmGenerationConfig*](llmmodels.md#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig) *|* *None*)

#### generation_config *: `Optional`[LlmGenerationConfig]* *= None*

Parameters to configure the generation.

#### input_descriptors *: `Optional`[`List`[[`Property`](flows.md#wayflowcore.property.Property)]]* *= None*

Input descriptors that will be picked up by PromptExecutionStep or AgentExecutionStep.
Resolved by default from the variables present in the messages.

#### messages *: `Sequence`[`Union`[[`Message`](conversation.md#wayflowcore.messagelist.Message), [`MessageAsDictT`](#wayflowcore._utils._templating_helpers.MessageAsDictT)]]*

List of messages for the prompt.

#### native_structured_generation *: `bool`* *= True*

Whether to use native structured generation or not. All llm providers might not support it.

#### native_tool_calling *: `bool`* *= True*

Whether to use the native tool calling of the model or not. All llm providers might not support it.

#### output_parser *: `Union`[[`OutputParser`](#wayflowcore.outputparser.OutputParser), `List`[[`OutputParser`](#wayflowcore.outputparser.OutputParser)], `None`]* *= None*

Post-processing applied on the raw output of the LLM.

#### post_rendering_transforms *: `Optional`[`List`[[`MessageTransform`](#wayflowcore.transforms.MessageTransform)]]* *= None*

Message transform applied on the rendered list of messages.
Use these to ensure the remote LLM will accept the prompt: ensuring a single system_message,
ensuring alternating user/assistant messages, …

#### pre_rendering_transforms *: `Optional`[`List`[[`MessageTransform`](#wayflowcore.transforms.MessageTransform)]]* *= None*

Message transform applied before rendering the list of messages into the template.
Use these to summarize messages, …

#### response_format *: `Optional`[[`Property`](flows.md#wayflowcore.property.Property)]* *= None*

Specific format the llm answer should follow.

#### tools *: `Optional`[`List`[[`Tool`](tools.md#wayflowcore.tools.tools.Tool)]]* *= None*

Tools to use in the prompt.

#### with_additional_post_rendering_transform(transform, append_last=None, append=None)

Returns a copy of the prompt template with an additional post rendering transform

* **Return type:**
  [`PromptTemplate`](#wayflowcore.templates.template.PromptTemplate)
* **Parameters:**
  * **transform** ([*MessageTransform*](#wayflowcore.transforms.MessageTransform))
  * **append_last** (*bool* *|* *None*)
  * **append** (*bool* *|* *None*)

#### with_additional_pre_rendering_transform(transform, append_last=None, append=None)

Returns a copy of the prompt template with an additional pre rendering transform

* **Return type:**
  [`PromptTemplate`](#wayflowcore.templates.template.PromptTemplate)
* **Parameters:**
  * **transform** ([*MessageTransform*](#wayflowcore.transforms.MessageTransform))
  * **append_last** (*bool* *|* *None*)
  * **append** (*bool* *|* *None*)

#### with_generation_config(generation_config, override=True)

Override: Whether the template config should be overridden or should overridden this config.

* **Return type:**
  [`PromptTemplate`](#wayflowcore.templates.template.PromptTemplate)
* **Parameters:**
  * **generation_config** ([*LlmGenerationConfig*](llmmodels.md#wayflowcore.models.llmgenerationconfig.LlmGenerationConfig) *|* *None*)
  * **override** (*bool*)

#### with_output_parser(output_parser)

Replaces the output parser of this template.

* **Return type:**
  [`PromptTemplate`](#wayflowcore.templates.template.PromptTemplate)
* **Parameters:**
  **output_parser** ([*OutputParser*](#wayflowcore.outputparser.OutputParser) *|* *List* *[*[*OutputParser*](#wayflowcore.outputparser.OutputParser) *]*)

#### with_partial(inputs)

Partially formats the prompt with the given inputs (to avoid formatting everything at each call, if some
inputs do not change). These inputs are not rendered directly, but stored for a later call to format().

* **Return type:**
  [`PromptTemplate`](#wayflowcore.templates.template.PromptTemplate)
* **Parameters:**
  **inputs** (*Dict* *[**str* *,* *Any* *]*)

#### with_response_format(response_format)

Returns a copy of the template equipped with a given response format.

* **Return type:**
  [`PromptTemplate`](#wayflowcore.templates.template.PromptTemplate)
* **Parameters:**
  **response_format** ([*Property*](flows.md#wayflowcore.property.Property) *|* *None*)

#### with_tools(tools)

Returns a copy of the template equipped with the given tools.

* **Return type:**
  [`PromptTemplate`](#wayflowcore.templates.template.PromptTemplate)
* **Parameters:**
  **tools** (*List* *[*[*Tool*](tools.md#wayflowcore.tools.tools.Tool) *]*  *|* *None*)

## OutputParser

<a id="id2"></a>

### *class* wayflowcore.outputparser.OutputParser(\_\_metadata_info_\_=None, id=None)

Abstract base class for output parsers that process LLM outputs.

* **Parameters:**
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **id** (*str* *|* *None*)

#### *abstract* parse_output(content)

Parses the LLM raw output

* **Return type:**
  [`Message`](conversation.md#wayflowcore.messagelist.Message)
* **Parameters:**
  **content** ([*Message*](conversation.md#wayflowcore.messagelist.Message))

#### *abstract async* parse_output_streaming(content)

Can parse the result returned by streaming
By default does nothing until the message has been completely generated, but can implement specific stream methods if we want to stream something specific

* **Return type:**
  `Any`
* **Parameters:**
  **content** (*Any*)

<a id="regexoutputparser"></a>

### *class* wayflowcore.outputparser.RegexOutputParser(regex_pattern, strict=True, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Parses some text with Regex, potentially several regex to fill a dict

### Examples

```pycon
>>> import re
>>> from wayflowcore.messagelist import Message
>>> from wayflowcore.outputparser import RegexOutputParser, RegexPattern
>>> RegexOutputParser(
...     regex_pattern=RegexPattern(pattern=r"Solution is: (.*)", flags=re.DOTALL)
... ).parse_output(Message(content="Solution is: Bern is the capital of Switzerland")).content
'Bern is the capital of Switzerland'
```

```pycon
>>> RegexOutputParser(
...     regex_pattern={
...         'thought': "THOUGHT: (.*) ACTION:",
...         'action': "ACTION: (.*)",
...     }
... ).parse_output(Message("THOUGHT: blahblah ACTION: doing")).content
'{"thought": "blahblah", "action": "doing"}'
```

* **Parameters:**
  * **regex_pattern** (*str* *|* [*RegexPattern*](#wayflowcore.outputparser.RegexPattern) *|* *Dict* *[**str* *,* *str* *|* [*RegexPattern*](#wayflowcore.outputparser.RegexPattern) *]*)
  * **strict** (*bool*)
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### parse_output(message)

Parses the LLM raw output

* **Return type:**
  [`Message`](conversation.md#wayflowcore.messagelist.Message)
* **Parameters:**
  **message** ([*Message*](conversation.md#wayflowcore.messagelist.Message))

#### *async* parse_output_streaming(content)

Can parse the result returned by streaming
By default does nothing until the message has been completely generated, but can implement specific stream methods if we want to stream something specific

* **Return type:**
  `Any`
* **Parameters:**
  **content** (*Any*)

#### regex_pattern *: `Union`[`str`, [`RegexPattern`](#wayflowcore.outputparser.RegexPattern), `Dict`[`str`, `Union`[`str`, [`RegexPattern`](#wayflowcore.outputparser.RegexPattern)]]]*

Regex pattern to use

#### strict *: `bool`* *= True*

Whether to return empty string if no match is found or return the raw text

<a id="regexpattern"></a>

### *class* wayflowcore.outputparser.RegexPattern(pattern, match='first', flags=None)

Represents a regex pattern and matching options for output parsing.

* **Parameters:**
  * **pattern** (*str*)
  * **match** (*Literal* *[* *'first'* *,*  *'last'* *]*)
  * **flags** (*int* *|* *RegexFlag* *|* *None*)

#### flags *: `Union`[`int`, `RegexFlag`, `None`]* *= None*

Potential regex flags to use (re.DOTALL for multiline matching for example)

#### *static* from_str(pattern, flags=re.DOTALL)

* **Return type:**
  [`RegexPattern`](#wayflowcore.outputparser.RegexPattern)
* **Parameters:**
  * **pattern** (*str* *|* [*RegexPattern*](#wayflowcore.outputparser.RegexPattern))
  * **flags** (*int* *|* *RegexFlag* *|* *None*)

#### match *: `Literal`[`'first'`, `'last'`]* *= 'first'*

Whether to take the first match or the last match

#### pattern *: `str`*

Regex pattern to match

<a id="jsonoutputparser"></a>

### *class* wayflowcore.outputparser.JsonOutputParser(properties=None, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Parses output as JSON, repairing and serializing as needed.

* **Parameters:**
  * **properties** (*Dict* *[**str* *,* *str* *]*  *|* *None*)
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### parse_output(content)

Parses the LLM raw output

* **Return type:**
  [`Message`](conversation.md#wayflowcore.messagelist.Message)
* **Parameters:**
  **content** ([*Message*](conversation.md#wayflowcore.messagelist.Message))

#### *async* parse_output_streaming(content)

Can parse the result returned by streaming
By default does nothing until the message has been completely generated, but can implement specific stream methods if we want to stream something specific

* **Return type:**
  `Any`
* **Parameters:**
  **content** (*Any*)

#### properties *: `Optional`[`Dict`[`str`, `str`]]* *= None*

Dictionary of property names and jq queries to manipulate the loaded JSON

<a id="tooloutputparser"></a>

### *class* wayflowcore.outputparser.ToolOutputParser(tools=None, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Base parser for tool requests

* **Parameters:**
  * **tools** (*List* *[*[*Tool*](tools.md#wayflowcore.tools.tools.Tool) *]*  *|* *None*)
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### parse_output(message)

Separates the raw output into thoughts and calls, and then parses the calls into ToolRequests

* **Return type:**
  [`Message`](conversation.md#wayflowcore.messagelist.Message)
* **Parameters:**
  **message** ([*Message*](conversation.md#wayflowcore.messagelist.Message))

#### *async* parse_output_streaming(content)

Can parse the result returned by streaming
By default does nothing until the message has been completely generated, but can implement specific stream methods if we want to stream something specific

* **Return type:**
  `Any`
* **Parameters:**
  **content** (*Any*)

#### parse_thoughts_and_calls(raw_txt)

Default function to separate thoughts and tool calls

* **Return type:**
  `Tuple`[`str`, `str`]
* **Parameters:**
  **raw_txt** (*str*)

#### *abstract* parse_tool_request_from_str(raw_txt)

* **Return type:**
  `List`[[`ToolRequest`](tools.md#wayflowcore.tools.tools.ToolRequest)]
* **Parameters:**
  **raw_txt** (*str*)

#### tools *: `Optional`[`List`[[`Tool`](tools.md#wayflowcore.tools.tools.Tool)]]* *= None*

#### with_tools(tools)

Enhances the tool parser with some validation of the parsed tool calls according to specific tools

* **Return type:**
  [`ToolOutputParser`](#wayflowcore.outputparser.ToolOutputParser)
* **Parameters:**
  **tools** (*List* *[*[*Tool*](tools.md#wayflowcore.tools.tools.Tool) *]*  *|* *None*)

## Message transforms

<a id="messagetransform"></a>

### *class* wayflowcore.transforms.MessageTransform(id=None, name=None, description=None, \_\_metadata_info_\_=None)

Abstract base class for message transforms.

Subclasses should implement the \_\_call_\_ method to transform a list of Message objects
and return a new list of Message objects, typically for preprocessing or postprocessing
message flows in the system.

* **Parameters:**
  * **id** (*str* *|* *None*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### *async* call_async(messages)

Implement this method for asynchronous work (IO-bounded, with LLM calls, DB loading …)

* **Return type:**
  `List`[[`Message`](conversation.md#wayflowcore.messagelist.Message)]
* **Parameters:**
  **messages** (*List* *[*[*Message*](conversation.md#wayflowcore.messagelist.Message) *]*)

### *class* wayflowcore.transforms.CoalesceSystemMessagesTransform(id=None, name=None, description=None, \_\_metadata_info_\_=None)

Transform that merges consecutive system messages at the start of a message list
into a single system message. This is useful for reducing redundancy and ensuring
that only one system message appears at the beginning of the conversation.

* **Parameters:**
  * **id** (*str* *|* *None*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### *class* wayflowcore.transforms.RemoveEmptyNonUserMessageTransform(id=None, name=None, description=None, \_\_metadata_info_\_=None)

Transform that removes messages which are empty and not from the user.

Any message with empty content and no tool requests, except for user messages,
will be filtered out from the message list.

This is useful in case the template contains optional messages, which will be discarded if their
content is empty (with a string template such as “{% if \_\_PLAN_\_ %}{{ \_\_PLAN_\_ }}{% endif %}”).

* **Parameters:**
  * **id** (*str* *|* *None*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### *class* wayflowcore.transforms.AppendTrailingSystemMessageToUserMessageTransform(id=None, name=None, description=None, \_\_metadata_info_\_=None)

Transform that appends the content of a trailing system message to the previous user message.

If the last message in the list is a system message and the one before it is a user message,
this transform merges the system message content into the user message, reducing message clutter.

This is useful if the underlying LLM does not support system messages at the end.

* **Parameters:**
  * **id** (*str* *|* *None*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### *class* wayflowcore.transforms.SplitPromptOnMarkerMessageTransform(marker=None, id=None, name=None, description=None, \_\_metadata_info_\_=None)

Split prompts on a marker into multiple messages with the same role. Only apply to the messages without
tool_requests and tool_result.

This transform is useful for script-based execution flows, where a single prompt script can be converted
into multiple conversation turns for step-by-step reasoning.

* **Parameters:**
  * **marker** (*str* *|* *None*)
  * **id** (*str* *|* *None*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

<a id="canonicalizationtransform"></a>

### *class* wayflowcore.transforms.CanonicalizationMessageTransform(id=None, name=None, description=None, \_\_metadata_info_\_=None)

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

* **Parameters:**
  * **id** (*str* *|* *None*)
  * **name** (*str* *|* *None*)
  * **description** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### FIRST_DUMMY_USER_TEXT *= 'begin'*

#### NEXT_DUMMY_USER_TEXT *= 'continue'*

<a id="messagesummarizationtransform"></a>

### *class* wayflowcore.transforms.MessageSummarizationTransform(llm, max_message_size=20000, summarization_instructions='Please make a summary of this message. Include relevant information and keep it short. Your response will replace the message, so just output the summary directly, no introduction needed.', summarized_message_template='Summarized message: {{summary}}', datastore=\_UnspecifiedDatastore.DEFAULT_VALUE, cache_collection_name='summarized_messages_cache', max_cache_size=10000, max_cache_lifetime=14400, name=None, id=None, description=None, \_\_metadata_info_\_=None)

Summarizes oversized messages using an LLM and optionally caches summaries.

This is useful for long conversations where the context can become too large for the LLM to handle.

* **Parameters:**
  * **llm** ([`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)) – LLM to use for the summarization. If the agent’s llm supports images, then this llm should also support images.
  * **max_message_size** (`int`) – The maximum size in number of characters for the content of a message. This is converted
    to an estimated token count using heuristics (approximately max_message_size / 4). Images
    in the message are also converted to estimated token counts (assuming 16x16 patches and
    defaulting to 2048x2048 if the image type is not PNG, JPEG, or JPEG2000). Summarization
    is triggered when the total estimated token count (text + images) of a message exceeds
    this threshold.
  * **summarization_instructions** (`str`) – Instruction for the LLM on how to summarize the messages.
  * **summarized_message_template** (`str`) – Jinja2 template on how to present the summary (with variable summary) to the agent using the transform.
  * **datastore** (`Union`[[`Datastore`](datastores.md#wayflowcore.datastore.Datastore), `_UnspecifiedDatastore`, `None`]) – 

    Datastore on which to store the cache. If not specified, an in-memory Datastore will be created automatically.
    If None, caching is disabled (not recommended)

    #### IMPORTANT
    The datastore needs to have a collection called cache_collection_name. This collection’s entries should be defined using
    MessageSummarizationTransform.get_entity_definition or as follows:
    ``
    Entity({
    "cache_key": StringProperty(),
    "cache_content": StringProperty(),
    "created_at": FloatProperty(),
    "last_used_at": FloatProperty(),
    })
    ``
  * **cache_collection_name** (`str`) – Name of the collection/table in the cache for storing summarized messages.
  * **max_cache_size** (`Optional`[`int`]) – The number of cache entries (messages) kept in the cache.
    If None, there is no limit on cache size and no eviction occurs.
  * **max_cache_lifetime** (`Optional`[`int`]) – max lifetime of a message in the cache in seconds.
    If None, cached data persists indefinitely.
  * **name** (*str* *|* *None*)
  * **id** (*str* *|* *None*)
  * **description** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.transforms import MessageSummarizationTransform
>>> summarization_transform = MessageSummarizationTransform(
...     llm=llm,
...     max_message_size=30_000
... )
```

#### DEFAULT_CACHE_COLLECTION_NAME *= 'summarized_messages_cache'*

#### *async* call_async(messages)

Implement this method for asynchronous work (IO-bounded, with LLM calls, DB loading …)

* **Return type:**
  `List`[[`Message`](conversation.md#wayflowcore.messagelist.Message)]
* **Parameters:**
  **messages** (*List* *[*[*Message*](conversation.md#wayflowcore.messagelist.Message) *]*)

#### *static* get_entity_definition()

* **Return type:**
  [`Entity`](datastores.md#wayflowcore.datastore.Entity)

#### *async* summarize_if_needed(contents, conv_id, msg_idx, \_type='content')

* **Return type:**
  `List`[[`MessageContent`](conversation.md#wayflowcore.messagelist.MessageContent)]
* **Parameters:**
  * **contents** (*List* *[*[*MessageContent*](conversation.md#wayflowcore.messagelist.MessageContent) *]*)
  * **conv_id** (*str*)
  * **msg_idx** (*int*)
  * **\_type** (*Literal* *[* *'toolres'* *,*  *'content'* *]*)

<a id="conversationsummarizationtransform"></a>

### *class* wayflowcore.transforms.ConversationSummarizationTransform(llm, max_num_messages=50, min_num_messages=10, summarization_instructions='Please make a summary of this conversation. Include relevant information and keep it short. Your response will replace the messages, so just output the summary directly, no introduction needed.', summarized_conversation_template='Summarized conversation: {{summary}}', datastore=\_UnspecifiedDatastore.DEFAULT_VALUE, max_cache_size=10000, max_cache_lifetime=14400, cache_collection_name='summarized_conversations_cache', name=None, id=None, description=None, \_\_metadata_info_\_=None)

Summarizes conversations exceeding a given number of messages using an LLM and caches conversation summaries in a `Datastore`.

This is useful to reduce long conversation history into a concise context for downstream LLM calls.

* **Parameters:**
  * **llm** ([`LlmModel`](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)) – LLM to use for the summarization.
  * **max_num_messages** (`int`) – Number of message after which we trigger summarization. Tune this parameter depending on the
    context length of your model and the price you are willing to pay (higher means longer conversation
    prompts and more tokens).
  * **min_num_messages** (`int`) – Number of recent messages to keep from summarizing. Tune this parameter to prevent from summarizing
    very recent messages and keep a very responsive and relevant agent.
  * **summarization_instructions** (`str`) – Instruction for the LLM on how to summarize the conversation.
  * **summarized_conversation_template** (`str`) – Jinja2 template on how to present the summary (with variable summary) to the agent using the transform.
  * **datastore** (`Union`[[`Datastore`](datastores.md#wayflowcore.datastore.Datastore), `_UnspecifiedDatastore`, `None`]) – Datastore on which to store the cache. If not specified, an in-memory Datastore will be created automatically.
    If None, caching is disabled (not recommended)
  * **max_cache_size** (`Optional`[`int`]) – The maximum number of entries kept in the cache
    If None, there is no limit on cache size and no eviction occurs.
  * **max_cache_lifetime** (`Optional`[`int`]) – max lifetime of an element in the cache in seconds
    If None, cached data persists indefinitely.
  * **cache_collection_name** (`str`) – the collection in the cache datastore where summarized conversations will be stored
  * **name** (*str* *|* *None*)
  * **id** (*str* *|* *None*)
  * **description** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

### Examples

```pycon
>>> from wayflowcore.transforms import ConversationSummarizationTransform
>>> summarization_transform = ConversationSummarizationTransform(
...     llm=llm,
...     max_num_messages=30,
...     min_num_messages=10
... )
```

#### DEFAULT_CACHE_COLLECTION_NAME *= 'summarized_conversations_cache'*

#### *async* call_async(messages)

Implement this method for asynchronous work (IO-bounded, with LLM calls, DB loading …)

* **Return type:**
  `List`[[`Message`](conversation.md#wayflowcore.messagelist.Message)]
* **Parameters:**
  **messages** (*List* *[*[*Message*](conversation.md#wayflowcore.messagelist.Message) *]*)

#### *static* get_entity_definition()

* **Return type:**
  [`Entity`](datastores.md#wayflowcore.datastore.Entity)

## Helpers

<a id="prompttemplatehelpers"></a>

### wayflowcore.templates.structuredgeneration.adapt_prompt_template_for_json_structured_generation(prompt_template)

Adapts a prompt template for native structured generation to one
that leverages a special system prompt and a JSON Output Parser.

* **Parameters:**
  **prompt_template** ([*PromptTemplate*](#wayflowcore.templates.template.PromptTemplate)) – The prompt template to adapt
* **Returns:**
  The new prompt template, with the special system prompt and
  output parsers configured
* **Return type:**
  [PromptTemplate](#wayflowcore.templates.template.PromptTemplate)
* **Raises:**
  **ValueError** – If the prompt template is already configured to use non-native structured generation,
      or the prompt template has no response format.

### *class* wayflowcore._utils._templating_helpers.ToolRequestAsDictT

#### args *: `Dict`[`str`, `Any`]*

#### name *: `str`*

#### tool_request_id *: `str`*

### *class* wayflowcore._utils._templating_helpers.ToolResultAsDictT

#### content *: `Any`*

#### tool_request_id *: `str`*

### *class* wayflowcore._utils._templating_helpers.MessageAsDictT

#### content *: `str`*

#### role *: `Literal`[`'user'`, `'assistant'`, `'system'`]*

#### tool_requests *: `NotRequired`[`Optional`[`List`[[`ToolRequestAsDictT`](#wayflowcore._utils._templating_helpers.ToolRequestAsDictT)]]]*

#### tool_result *: `NotRequired`[`Optional`[[`ToolResultAsDictT`](#wayflowcore._utils._templating_helpers.ToolResultAsDictT)]]*
