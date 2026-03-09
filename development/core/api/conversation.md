# Conversations

## Messages

<a id="message"></a>

### *class* wayflowcore.messagelist.Message(content='', message_type=None, tool_requests=None, tool_result=None, is_error=False, display_only=False, sender=None, recipients=None, time_created=None, time_updated=None, contents=None, role=None, \_prompt_cache_key=None, \_reasoning_content=None, \_\_metadata_info_\_=None, \_extra_content=None)

Messages are an exchange medium between the user, LLM agent, and controller logic.
This helps to determine who provided what information.

* **Parameters:**
  * **content** (`str`) – Content of the message.
  * **message_type** (`Optional`[[`MessageType`](#wayflowcore.messagelist.MessageType)]) – A message type out of the following ones:
    SYSTEM, AGENT, USER, THOUGHT, INTERNAL, TOOL_REQUEST, TOOL_RESULT.
  * **tool_requests** (`Optional`[`List`[[`ToolRequest`](tools.md#wayflowcore.tools.tools.ToolRequest)]]) – A list of `ToolRequest` objects representing the tools invoked as part
    of this message. Each request includes the tool’s name, arguments,
    and a unique identifier.
  * **tool_result** (`Optional`[[`ToolResult`](tools.md#wayflowcore.tools.tools.ToolResult)]) – A `ToolResult` object representing the outcome of a tool invocation.
    It includes the returned content and a reference to the related tool request ID.
  * **display_only** (`bool`) – If True, the message is excluded from any context. Its only purpose is to be displayed in the chat UI (e.g debugging message)
  * **sender** (`Optional`[`str`]) – Sender of the message in str format.
  * **recipients** (`Optional`[`Set`[`str`]]) – Recipients of the message in str format.
  * **time_created** (`Optional`[`datetime`]) – Creation timestamp of the message.
  * **time_updated** (`Optional`[`datetime`]) – Update timestamp of the message.
  * **contents** (`Optional`[`List`[[`MessageContent`](#wayflowcore.messagelist.MessageContent)]]) – Message content. Is a list of chunks with potentially different types
  * **role** (`Optional`[`Literal`[`'user'`, `'system'`, `'assistant'`]]) – Role of the sender of the message. Can be user, system or assistant
  * **\_extra_content** (`Optional`[`Dict`[`str`, `Any`]]) – Any additional information required when interacting with the LLM.
    Generally, this is provided in the model response itself, when required.
  * **is_error** (*bool*)
  * **\_prompt_cache_key** (*str* *|* *None*)
  * **\_reasoning_content** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### *property* content *: str*

Text content getter

#### contents *: `List`[[`MessageContent`](#wayflowcore.messagelist.MessageContent)]*

#### copy(\*\*kwargs)

Create a copy of the given message.

* **Return type:**
  [`Message`](#wayflowcore.messagelist.Message)
* **Parameters:**
  **kwargs** (*Any*)

#### display_only *: `bool`* *= False*

#### *property* hash *: str*

#### *property* is_error *: bool*

#### *property* message_type *: [MessageType](#wayflowcore.messagelist.MessageType)*

Getter to guarantee backward compatibility

#### recipients *: `Set`[`str`]*

#### role *: `Literal`[`'user'`, `'assistant'`, `'system'`]*

#### sender *: `Optional`[`str`]* *= None*

#### time_created *: `datetime`*

#### time_updated *: `datetime`*

#### tool_requests *: `Optional`[`List`[ToolRequest]]* *= None*

#### tool_result *: `Optional`[ToolResult]* *= None*

<a id="messagetype"></a>

### *class* wayflowcore.messagelist.MessageType(value)

Type of messages

#### AGENT *= 'AGENT'*

#### DISPLAY_ONLY *= 'DISPLAY_ONLY'*

#### ERROR *= 'ERROR'*

#### INTERNAL *= 'INTERNAL'*

#### SYSTEM *= 'SYSTEM'*

#### THOUGHT *= 'THOUGHT'*

#### TOOL_REQUEST *= 'TOOL_REQUEST'*

#### TOOL_RESULT *= 'TOOL_RESULT'*

#### USER *= 'USER'*

<a id="messagecontent"></a>

### *class* wayflowcore.messagelist.MessageContent

Abstract base class for message content chunks.

All message content types (such as text and images) should derive from this class
and specify a class-level ‘type’ field to distinguish content variant.
Subclasses may also add additional fields for content-specific data.

* **Parameters:**
  **type** – Identifier for the content type, to be implemented by subclasses.

#### type *: `ClassVar`[`str`]*

<a id="textcontent"></a>

### *class* wayflowcore.messagelist.TextContent(content='')

Represents the content of a text message.

* **Parameters:**
  * **content** (`str`) – The textual content of the message.
  * **type** – Identifier for the text content type.

#### content *: `str`* *= ''*

#### type *: `ClassVar`[`Literal`[`'text'`]]* *= 'text'*

<a id="imagecontent"></a>

### *class* wayflowcore.messagelist.ImageContent(base64_content)

Represents the content of an image message, storing image data as a base64-encoded string.

* **Parameters:**
  * **base64_content** (`str`) – A base64-encoded string representing the image data.
  * **type** – Identifier for the image content type.

### Examples

```pycon
>>> import requests
>>> from wayflowcore.messagelist import Message, TextContent, ImageContent
>>> from wayflowcore.models import Prompt
>>> # Download the Oracle logo as bytes
>>> url = "https://www.oracle.com/a/ocom/img/oracle-logo.png"
>>> response = requests.get(url)
>>> img_content = ImageContent.from_bytes(response.content, format="png")
>>> prompt = Prompt(messages=[Message(contents = [TextContent("Which company's logo is this?") , img_content])])
>>> completion = multimodal_llm.generate(prompt)
>>> # LlmCompletion(message=Message(content="That is the logo for **Oracle Corporation**."))
```

#### base64_content *: `str`*

#### *classmethod* from_bytes(bytes_content, format)

* **Return type:**
  [`ImageContent`](#wayflowcore.messagelist.ImageContent)
* **Parameters:**
  * **bytes_content** (*bytes*)
  * **format** (*str*)

#### type *: ClassVar[str]* *= 'image'*

<a id="messagelist"></a>

### *class* wayflowcore.messagelist.MessageList(messages=<factory>, \*, id=<factory>, \_\_metadata_info_\_=<factory>)

Object that carries a list of messages. We may only append to this object, not remove

* **Parameters:**
  * **messages** (`List`[[`Message`](#wayflowcore.messagelist.Message)]) – list of messages to start from.
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)

#### append_agent_message(agent_input, is_error=False)

Append a new message object of type `MessageType.AGENT` to the messages list.

* **Parameters:**
  * **agent_input** (`str`) – message to append.
  * **is_error** (*bool*)
* **Return type:**
  `None`

#### append_message(message)

Add a message to a message list.

* **Parameters:**
  **message** ([`Message`](#wayflowcore.messagelist.Message)) – Message to append to the message list.
* **Return type:**
  `None`

#### append_tool_result(tool_result)

Append a new message object of type `MessageType.TOOL_RESULT` to the messages list.

* **Parameters:**
  **tool_result** ([`ToolResult`](tools.md#wayflowcore.tools.tools.ToolResult)) – message to append.
* **Return type:**
  `None`

#### append_user_message(user_input)

Append a new message object of type `MessageType.USER` to the messages list.

* **Parameters:**
  **user_input** (`Union`[`str`, `List`[[`MessageContent`](#wayflowcore.messagelist.MessageContent)]]) – message to append.
* **Return type:**
  `None`

#### copy()

Create a copy of the given message list.

* **Return type:**
  [`MessageList`](#wayflowcore.messagelist.MessageList)

#### *classmethod* from_messages(messages=None)

* **Return type:**
  [`MessageList`](#wayflowcore.messagelist.MessageList)
* **Parameters:**
  **messages** (*None* *|* *str* *|* [*Message*](#wayflowcore.messagelist.Message) *|* *List* *[*[*Message*](#wayflowcore.messagelist.Message) *]*)

#### get_last_message(strict=False)

Returns the last message from the conversation.
If strict=True, raises an exception if no messages exist.

* **Return type:**
  `Optional`[[`Message`](#wayflowcore.messagelist.Message)]
* **Parameters:**
  **strict** (*bool*)

#### get_messages()

Returns a copy of the messages list

* **Return type:**
  `List`[[`Message`](#wayflowcore.messagelist.Message)]

#### messages *: `List`[[`Message`](#wayflowcore.messagelist.Message)]*

## ExecutionStatus

<a id="id1"></a>

### *class* wayflowcore.executors.executionstatus.ExecutionStatus(\*, id=<factory>, \_\_metadata_info_\_=<factory>, \_conversation_id=None)

Execution status returned by the Assistant. This indicates if the assistant yielded, finished the conversation, …

* **Parameters:**
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **\_conversation_id** (*str* *|* *None*)

<a id="usermessagerequesttatus"></a>

### *class* wayflowcore.executors.executionstatus.UserMessageRequestStatus(\*, id=<factory>, \_\_metadata_info_\_=<factory>, \_conversation_id=None, message, \_user_response=None)

Execution status for when the assistant answered and will be waiting for the next user input

* **Parameters:**
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **\_conversation_id** (*str* *|* *None*)
  * **message** ([*Message*](#wayflowcore.messagelist.Message))
  * **\_user_response** ([*Message*](#wayflowcore.messagelist.Message) *|* *None*)

#### message *: Message*

The message from the assistant to which the user needs to answer to.

#### submit_user_response(response)

Submit the answer to this user message request.

* **Return type:**
  `None`
* **Parameters:**
  **response** (*str* *|* [*Message*](#wayflowcore.messagelist.Message))

<a id="finishedexecutionstatus"></a>

### *class* wayflowcore.executors.executionstatus.FinishedStatus(output_values, complete_step_name=None, \*, id=<factory>, \_\_metadata_info_\_=<factory>, \_conversation_id=None)

Execution status for when the conversation is finished. Contains the outputs of the conversation

* **Parameters:**
  * **output_values** (*Dict* *[**str* *,* *Any* *]*)
  * **complete_step_name** (*str* *|* *None*)
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **\_conversation_id** (*str* *|* *None*)

#### complete_step_name *: Optional[str]* *= None*

The name of the last step reached if the flow returning this execution status transitioned     to a `CompleteStep`, otherwise `None`.

#### output_values *: Dict[str, Any]*

The outputs produced by the agent or flow returning this execution status.

<a id="toolrequestexecutionstatus"></a>

### *class* wayflowcore.executors.executionstatus.ToolRequestStatus(\*, id=<factory>, \_\_metadata_info_\_=<factory>, \_conversation_id=None, tool_requests, \_tool_results=None)

Execution status for when the assistant is asking the user to call a tool and send back its result

* **Parameters:**
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **\_conversation_id** (*str* *|* *None*)
  * **tool_requests** (*List* *[*[*ToolRequest*](tools.md#wayflowcore.tools.tools.ToolRequest) *]*)
  * **\_tool_results** (*List* *[*[*ToolResult*](tools.md#wayflowcore.tools.tools.ToolResult) *]*  *|* *None*)

#### submit_tool_result(tool_result)

Submit the tool results to the given tool requests.

* **Return type:**
  `None`
* **Parameters:**
  **tool_result** ([*ToolResult*](tools.md#wayflowcore.tools.tools.ToolResult))

#### submit_tool_results(tool_results)

Submit the tool results to the given tool requests.

* **Return type:**
  `None`
* **Parameters:**
  **tool_results** (*List* *[*[*ToolResult*](tools.md#wayflowcore.tools.tools.ToolResult) *]*)

#### tool_requests *: List['ToolRequest']*

The tool requests for the client tools that the client need to run.

<a id="authchallengerequeststatus"></a>

### *class* wayflowcore.executors.executionstatus.AuthChallengeRequestStatus(\*, id=<factory>, \_\_metadata_info_\_=<factory>, \_conversation_id=None, challenge, client_transport_id)

Execution status for when authorization is required to access a resource.

* **Parameters:**
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **\_conversation_id** (*str* *|* *None*)
  * **challenge** ([*AuthChallengeRequest*](auth.md#wayflowcore.auth.auth.AuthChallengeRequest))
  * **client_transport_id** (*str*)

#### challenge *: AuthChallengeRequest*

#### client_transport_id *: str*

#### submit_result(result, timeout=20.0)

Submit the Auth challenge result to complete the auth flow.

* **Parameters:**
  * **result** ([`AuthChallengeResult`](auth.md#wayflowcore.auth.auth.AuthChallengeResult)) – Auth challenge result, containing information such as
    auth challenge code and state.
  * **timeout** (`float`) – Timeout for the auth flow completion after the result
    has been submitted and the auth flow has been resumed.
* **Return type:**
  `None`

## Conversation

Base class for conversations. Can manipulate a conversation object, and can be serialized/deserialized.

<a id="conversationalcomponent"></a>

### *class* wayflowcore.conversationalcomponent.ConversationalComponent(name, description, input_descriptors, output_descriptors, runner, conversation_class, id=None, \_\_metadata_info_\_=None)

* **Parameters:**
  * **name** (*str*)
  * **description** (*str* *|* *None*)
  * **input_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*)
  * **output_descriptors** (*List* *[*[*Property*](flows.md#wayflowcore.property.Property) *]*)
  * **runner** (*Type* *[**ConversationExecutor* *]*)
  * **conversation_class** (*Any*)
  * **id** (*str* *|* *None*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)

#### *property* llms *: List[[LlmModel](llmmodels.md#wayflowcore.models.llmmodel.LlmModel)]*

#### *abstract* start_conversation(inputs=None, messages=None)

* **Return type:**
  [`Conversation`](#wayflowcore.conversation.Conversation)
* **Parameters:**
  * **inputs** (*Dict* *[**str* *,* *Any* *]*  *|* *None*)
  * **messages** (*None* *|* *str* *|* [*Message*](#wayflowcore.messagelist.Message) *|* *List* *[*[*Message*](#wayflowcore.messagelist.Message) *]*  *|* [*MessageList*](#wayflowcore.messagelist.MessageList))

<a id="id2"></a>

### *class* wayflowcore.conversation.Conversation(component, state, inputs, message_list, status, conversation_id='', status_handled=False, \*, id=<factory>, \_\_metadata_info_\_=<factory>, name='', description=None)

* **Parameters:**
  * **component** ([*ConversationalComponent*](#wayflowcore.conversationalcomponent.ConversationalComponent))
  * **state** (*ConversationExecutionState*)
  * **inputs** (*Dict* *[**str* *,* *Any* *]*)
  * **message_list** ([*MessageList*](#wayflowcore.messagelist.MessageList))
  * **status** ([*ExecutionStatus*](#wayflowcore.executors.executionstatus.ExecutionStatus) *|* *None*)
  * **conversation_id** (*str*)
  * **status_handled** (*bool*)
  * **id** (*str*)
  * **\_\_metadata_info_\_** (*Dict* *[**str* *,* *Any* *]*)
  * **name** (*str*)
  * **description** (*str* *|* *None*)

#### append_agent_message(agent_input, is_error=False)

Append a new message object of type `MessageType.AGENT` to the messages list.

* **Parameters:**
  * **agent_input** (`str`) – message to append.
  * **is_error** (*bool*)
* **Return type:**
  `None`

#### append_message(message)

Append a message to the messages list of this `Conversation` object.

* **Parameters:**
  **message** ([`Message`](#wayflowcore.messagelist.Message)) – message to append.
* **Return type:**
  `None`

#### append_tool_result(tool_result)

Append a new message object of type `MessageType.TOOL_RESULT` to the messages list.

* **Parameters:**
  **tool_result** ([`ToolResult`](tools.md#wayflowcore.tools.tools.ToolResult)) – message to append.
* **Return type:**
  `None`

#### append_user_message(user_input)

Append a new message object of type `MessageType.USER` to the messages list.

* **Parameters:**
  **user_input** (`Union`[`str`, `List`[[`MessageContent`](#wayflowcore.messagelist.MessageContent)]]) – str or list of message contents to append as a user message.
* **Return type:**
  `None`

#### component *: [`ConversationalComponent`](#wayflowcore.conversationalcomponent.ConversationalComponent)*

#### conversation_id *: `str`* *= ''*

#### *abstract property* current_step_name *: str*

#### execute(execution_interrupts=None)

Execute the conversation and get its `ExecutionStatus` based on the outcome.

The `Execution` status is returned by the Assistant and indicates if the assistant yielded,
finished the conversation.

* **Return type:**
  [`ExecutionStatus`](#wayflowcore.executors.executionstatus.ExecutionStatus)
* **Parameters:**
  **execution_interrupts** (*Sequence* *[*[*ExecutionInterrupt*](interrupts.md#wayflowcore.executors.interrupts.executioninterrupt.ExecutionInterrupt) *]*  *|* *None*)

#### *async* execute_async(execution_interrupts=None)

Execute the conversation and get its `ExecutionStatus` based on the outcome.

The `Execution` status is returned by the Assistant and indicates if the assistant yielded,
finished the conversation.

* **Return type:**
  [`ExecutionStatus`](#wayflowcore.executors.executionstatus.ExecutionStatus)
* **Parameters:**
  **execution_interrupts** (*Sequence* *[*[*ExecutionInterrupt*](interrupts.md#wayflowcore.executors.interrupts.executioninterrupt.ExecutionInterrupt) *]*  *|* *None*)

#### get_last_message()

Get the last message from the messages List.

* **Return type:**
  `Optional`[[`Message`](#wayflowcore.messagelist.Message)]

#### get_messages()

Return all `Message` objects of the messages list in a python list.

* **Return type:**
  `List`[[`Message`](#wayflowcore.messagelist.Message)]

#### inputs *: `Dict`[`str`, `Any`]*

#### message_list *: [`MessageList`](#wayflowcore.messagelist.MessageList)*

#### *property* plan *: [ExecutionPlan](#wayflowcore.planning.ExecutionPlan) | None*

#### state *: ConversationExecutionState*

#### status *: `Optional`[[`ExecutionStatus`](#wayflowcore.executors.executionstatus.ExecutionStatus)]*

#### status_handled *: `bool`* *= False*

Whether the current status associated to this conversation was already handled or not
(messages/tool results were added to the conversation)

#### token_usage *: [`TokenUsage`](llmmodels.md#wayflowcore.tokenusage.TokenUsage)*

## Execution Plan

### *class* wayflowcore.planning.ExecutionPlan(plan=None)

* **Parameters:**
  **plan** (*List* *[*[*Task*](#wayflowcore.planning.Task) *]*  *|* *None*)

#### *static* from_str(plan_text)

* **Return type:**
  [`ExecutionPlan`](#wayflowcore.planning.ExecutionPlan)
* **Parameters:**
  **plan_text** (*str*)

#### to_str()

* **Return type:**
  `str`

### *class* wayflowcore.planning.Task(id, description, status=TaskStatus.PENDING, tool=None)

* **Parameters:**
  * **id** (*str*)
  * **description** (*str*)
  * **status** ([*TaskStatus*](#wayflowcore.planning.TaskStatus))
  * **tool** (*str* *|* *None*)

#### description *: `str`*

#### *static* from_str(line)

* **Return type:**
  `Optional`[[`Task`](#wayflowcore.planning.Task)]
* **Parameters:**
  **line** (*str*)

#### id *: `str`*

#### status *: [`TaskStatus`](#wayflowcore.planning.TaskStatus)* *= 'PENDING'*

#### to_str()

* **Return type:**
  `str`

#### tool *: `Optional`[`str`]* *= None*

### *class* wayflowcore.planning.TaskStatus(value)

Status of a task

#### CANCELLED *= 'CANCELLED'*

#### ERROR *= 'ERROR'*

#### IN_PROGRESS *= 'IN_PROGRESS'*

#### NEEDS_REFINEMENT *= 'NEEDS_REFINEMENT'*

#### PENDING *= 'PENDING'*

#### SUCCESS *= 'SUCCESS'*
