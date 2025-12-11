# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
import logging
from collections import Counter
from typing import Any, List, Literal, Optional, Sequence, Tuple, Union

import anyio
from anyio.streams.memory import MemoryObjectSendStream
from fastapi import HTTPException
from fastapi import status as http_status_code

from wayflowcore.conversation import Conversation
from wayflowcore.events import Event, EventListener
from wayflowcore.events.event import (
    ConversationMessageStreamChunkEvent,
    ConversationMessageStreamEndedEvent,
    ConversationMessageStreamStartedEvent,
    LlmGenerationResponseEvent,
)
from wayflowcore.executors.executionstatus import (
    ExecutionStatus,
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.executors.interrupts.executioninterrupt import InterruptedExecutionStatus
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.messagelist import ImageContent, Message, MessageContent, TextContent
from wayflowcore.tokenusage import TokenUsage
from wayflowcore.tools import ToolRequest, ToolResult

from ..models.openairesponsespydanticmodels import (
    EasyInputMessage,
    FunctionCallOutputItemParam,
    FunctionToolCall,
    InputContent,
    InputFileContent,
    InputImageContent,
    InputItem,
    InputMessage,
    InputTextContent,
    OutputContent,
    OutputItem,
    OutputMessage,
    OutputTextContent,
    ReasoningItem,
    ReasoningTextContent,
    RefusalContent,
    ResponseError,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
    ResponseUsage,
)

logger = logging.getLogger(__name__)


class _TokenCounterListener(EventListener):
    """Event listener that counts all llm generation tokens events."""

    def __init__(self) -> None:
        self.usage = TokenUsage()

    def __call__(self, event: Event) -> None:
        if isinstance(event, LlmGenerationResponseEvent):
            self.usage += event.completion.token_usage


class _TextStreamingListener(EventListener):
    """Listener that catches all the text generation wayflow events and enqueues openai responses events for the server to yield"""

    def __init__(self, queue: MemoryObjectSendStream[ResponseStreamEvent]) -> None:
        self.queue = queue
        self.counter = 0
        self.current_item_id = ""

    def _enqueue(self, content: Any) -> None:
        try:
            # non-blocking send usable from sync code
            self.queue.send_nowait(content)
        except anyio.WouldBlock:
            # buffer full
            logger.warning("Async event queue is full, dropping an event: %s", content)

    def __call__(self, event: Event) -> None:
        if isinstance(event, ConversationMessageStreamChunkEvent):
            self._enqueue(
                ResponseTextDeltaEvent(
                    content_index=0,
                    delta=event.chunk,
                    item_id=self.current_item_id,
                    logprobs=[],
                    output_index=0,
                    sequence_number=0,
                    type="response.output_text.delta",
                )
            )
        elif isinstance(event, ConversationMessageStreamStartedEvent):
            self.current_item_id = IdGenerator.get_or_generate_id()
            self._enqueue(
                ResponseOutputItemAddedEvent(
                    output_index=0,
                    item=OutputMessage(
                        content=[
                            OutputTextContent(
                                text=event.message.content,
                                type="output_text",
                                annotations=[],
                            )
                        ],
                        role="assistant",
                        status="in_progress",
                        id=self.current_item_id,
                        type="message",
                    ),
                    sequence_number=0,
                    type="response.output_item.added",
                )
            )
        elif isinstance(event, ConversationMessageStreamEndedEvent):
            self._enqueue(
                ResponseTextDoneEvent(
                    content_index=0,
                    item_id=self.current_item_id,
                    logprobs=[],
                    output_index=0,
                    sequence_number=0,
                    text=event.message.content,
                    type="response.output_text.done",
                )
            )
            self._enqueue(
                ResponseOutputItemDoneEvent(
                    item=OutputMessage(
                        content=[
                            OutputTextContent(
                                text=event.message.content,
                                type="output_text",
                                annotations=[],
                            )
                        ],
                        role="assistant",
                        status="completed",
                        id=self.current_item_id,
                        type="message",
                    ),
                    output_index=0,
                    sequence_number=0,
                    type="response.output_item.done",
                )
            )


def _convert_wayflow_token_usage_into_oai_token_usage(token_usage: TokenUsage) -> ResponseUsage:
    return ResponseUsage(
        input_tokens=token_usage.input_tokens,
        output_tokens=token_usage.output_tokens,
        total_tokens=token_usage.total_tokens,
        input_tokens_details=dict(cached_tokens=token_usage.cached_tokens),
        output_tokens_details=dict(reasoning_tokens=token_usage.reasoning_tokens),
    )


def _create_response_args_from_wayflow_status(
    status: Optional[ExecutionStatus],
) -> Tuple[List[OutputItem], Optional[ResponseError]]:
    messages: List[OutputItem]
    match status:
        case UserMessageRequestStatus(message=message):
            messages = [
                OutputMessage(
                    id=IdGenerator.get_or_generate_id(),
                    content=[_convert_wayflow_content_to_oai_content(c) for c in message.contents],
                    status="completed",
                    type="message",
                    role="assistant",
                )
            ]
            return messages, None
        case FinishedStatus(output_values=output_values):
            messages = [
                OutputMessage(
                    id=IdGenerator.get_or_generate_id(),
                    content=[
                        OutputTextContent(
                            text=json.dumps(output_values),
                            type="output_text",
                            annotations=[],
                        )
                    ],
                    status="completed",
                    type="message",
                    role="assistant",
                )
            ]
            return messages, None
        case ToolRequestStatus(tool_requests=tool_requests):
            messages = _convert_tool_request_status_into_function_tool_call_items(tool_requests)
            return messages, None

        case InterruptedExecutionStatus(reason=reason):
            # TODO FIX THIS
            error = ResponseError(
                message=reason,
                code="server_error",
            )  # type: ignore
            return [], error
        case None:
            error = ResponseError(
                message="execution did not complete",
                code="server_error",
            )  # type: ignore
            return [], error
        case _:
            raise HTTPException(
                status_code=http_status_code.HTTP_501_NOT_IMPLEMENTED,
                detail="Unhandled wayflow status: {}".format(status),
            )


def _convert_tool_request_status_into_function_tool_call_items(
    tool_requests: List[ToolRequest],
) -> List[OutputItem]:
    return [
        FunctionToolCall(
            arguments=json.dumps(tool_call.args),
            name=tool_call.name,
            type="function_call",
            call_id=tool_call.tool_request_id,
            status="completed",
        )
        for tool_call in tool_requests
    ]


def _convert_wayflow_content_to_oai_content(content: MessageContent) -> OutputTextContent:
    if isinstance(content, TextContent):
        return OutputTextContent(
            text=content.content,
            type="output_text",
            annotations=[],
        )
    raise HTTPException(
        status_code=http_status_code.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Conversion for `{type(content).__name__}` content is not supported yet.",
    )


def _get_conversation_input_messages(
    request_input: Union[str, List[InputItem]],
) -> List[Message]:
    if isinstance(request_input, str):
        return [Message(role="user", content=request_input)]
    return [_convert_oai_item_into_wayflow_message(m) for m in request_input]


def _convert_oai_item_into_wayflow_message(item: InputItem) -> Message:
    match item:
        case EasyInputMessage(role=role, content=content) | InputMessage(
            role=role, content=content
        ):
            return Message(
                contents=_convert_oai_input_message_content_into_wayflow_content(content=content),
                role=_convert_oai_role_into_wayflow_role(role=role),
            )
        case OutputMessage(content=content):
            return Message(
                contents=_convert_oai_output_message_content_into_wayflow_content(content=content),
                role="assistant",
            )
        case FunctionToolCall(call_id=call_id, arguments=arguments, name=name):
            return Message(
                tool_requests=[
                    ToolRequest(
                        name=name,
                        args=json.loads(arguments),
                        tool_request_id=call_id,
                    )
                ]
            )
        case FunctionCallOutputItemParam(call_id=call_id, output=output):
            return Message(
                tool_result=ToolResult(
                    content=output,
                    tool_request_id=call_id,
                )
            )
        case ReasoningItem():
            raise HTTPException(
                status_code=http_status_code.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Reasoning content is currently not supported as input.",
            )
        case _:
            raise HTTPException(
                status_code=http_status_code.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"`{item}` is not supported yet",
            )


def _convert_oai_input_message_content_into_wayflow_content(
    content: Union[str, List[InputContent]],
) -> List[MessageContent]:
    if isinstance(content, str):
        return [TextContent(content=content)]
    contents: List[MessageContent] = []
    for msg_content in content:
        match msg_content:
            case InputTextContent(text=text):
                contents.append(TextContent(content=text))
            case InputImageContent(image_url=image_url):
                if image_url is None:
                    raise HTTPException(
                        status_code=http_status_code.HTTP_501_NOT_IMPLEMENTED,
                        detail="Only supports images with base_content encoded in the url",
                    )
                contents.append(ImageContent(base64_content=image_url))
            case InputFileContent():
                raise HTTPException(
                    status_code=http_status_code.HTTP_501_NOT_IMPLEMENTED,
                    detail="FileContent not supported yet",
                )
            case _:
                raise HTTPException(
                    status_code=http_status_code.HTTP_501_NOT_IMPLEMENTED,
                    detail="Unhandled wayflow content: {}".format(msg_content),
                )
    return contents


def _convert_oai_output_message_content_into_wayflow_content(
    content: Sequence[OutputContent],
) -> List[MessageContent]:
    contents: List[MessageContent] = []
    for msg_content in content:
        match msg_content:
            case OutputTextContent(text=text):
                contents.append(TextContent(content=text))
            case RefusalContent():
                raise HTTPException(
                    status_code=http_status_code.HTTP_501_NOT_IMPLEMENTED,
                    detail="Output refusal not supported yet",
                )
            case ReasoningTextContent():
                raise HTTPException(
                    status_code=http_status_code.HTTP_501_NOT_IMPLEMENTED,
                    detail="Output refusal not supported yet",
                )
            case _:
                raise HTTPException(
                    status_code=http_status_code.HTTP_501_NOT_IMPLEMENTED,
                    detail="Unhandled wayflow content: {}".format(msg_content),
                )
    return contents


def _convert_oai_role_into_wayflow_role(
    role: Literal["user", "system", "developer", "assistant"],
) -> Literal["user", "system", "assistant"]:
    match role:
        case "user":
            return "user"
        case "developer" | "system":
            return "system"
        case "assistant":
            return "assistant"
        case _:
            raise HTTPException(
                status_code=http_status_code.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Unknown role {role}.",
            )


def _get_conversation_new_input_messages(
    prev_conversation: Optional[Conversation],
    request_input: Union[str, List[InputItem]],
) -> List[Message]:
    messages = _get_conversation_input_messages(request_input=request_input)

    if prev_conversation is None:
        return messages

    if len(messages) == 1:
        # we assume single message is always new
        return messages

    previous_message_list = prev_conversation.get_messages()
    # we cache the messages to know whether they are in the conversation or not
    existing_message_cache = Counter(msg.hash for msg in previous_message_list)

    new_messages = []
    for msg in messages:
        msg_hash = msg.hash
        if msg_hash not in existing_message_cache:
            new_messages.append(msg)
        else:
            logger.info(
                "A message was passed as input again but was already present in the conversation, it will be ignored"
            )
            # we remove from cache to avoid removing new message with same hash
            if existing_message_cache[msg_hash] <= 1:
                existing_message_cache.pop(msg_hash)
            else:
                existing_message_cache[msg_hash] -= 1

    return new_messages
