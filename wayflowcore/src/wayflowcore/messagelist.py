# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import base64
import logging
import warnings
from abc import ABC
from copy import deepcopy
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterable,
    Callable,
    ClassVar,
    Dict,
    List,
    Literal,
    Optional,
    Set,
    Union,
    cast,
    overload,
)

from deprecated import deprecated
from typing_extensions import TypeAlias

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.hash import fast_stable_hash
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import (
    SerializableDataclass,
    SerializableDataclassMixin,
    SerializableObject,
    autodeserialize_any_from_dict,
)
from wayflowcore.tools.tools import ToolRequest, ToolResult

if TYPE_CHECKING:
    from wayflowcore.models._requesthelpers import TaggedMessageChunkType


logger = logging.getLogger(__name__)

_ReasoningContent: TypeAlias = Dict[str, Any]


class MessageType(str, Enum):
    """Type of messages"""

    SYSTEM = "SYSTEM"  # doc: system message, used as instructions by LLMs
    AGENT = "AGENT"  # doc: agent message
    USER = "USER"  # doc: user message
    THOUGHT = "THOUGHT"  # doc: though message, created as CoT by the model
    INTERNAL = "INTERNAL"  # doc: internal message, used by steps
    TOOL_REQUEST = "TOOL_REQUEST"  # doc: tool call message
    TOOL_RESULT = "TOOL_RESULT"  # doc: result of a tool call
    ERROR = "ERROR"  # doc: wayflowcore error, but will appear as user message for the llm
    DISPLAY_ONLY = "DISPLAY_ONLY"  # doc: Message excluded from any context. Its only purpose is to be displayed in a chat UI (e.g debugging message)


@dataclass
class MessageContent(SerializableDataclassMixin, SerializableObject, ABC):
    """
    Abstract base class for message content chunks.

    All message content types (such as text and images) should derive from this class
    and specify a class-level 'type' field to distinguish content variant.
    Subclasses may also add additional fields for content-specific data.

    Parameters
    ----------
    type:
        Identifier for the content type, to be implemented by subclasses.
    """

    _can_be_referenced: ClassVar[bool] = False
    type: ClassVar[str]


@dataclass
class TextContent(MessageContent, SerializableObject):
    """
    Represents the content of a text message.

    Parameters
    ----------
    content:
        The textual content of the message.
    type:
        Identifier for the text content type.
    """

    content: str = ""
    type: ClassVar[Literal["text"]] = "text"

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            logger.warning(
                "Message.content should be of type `str` but is of type `%s`. Make sure that the "
                "message content can be cast to a string",
                type(self.content).__name__,
            )
            self.content = str(self.content)


@dataclass
class ImageContent(MessageContent, SerializableObject):
    """
    Represents the content of an image message, storing image data as a base64-encoded string.

    Parameters
    ----------
    base64_content:
        A base64-encoded string representing the image data.
    type:
        Identifier for the image content type.

    Examples
    --------
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
    """

    type = "image"
    base64_content: str

    @classmethod
    def from_bytes(cls, bytes_content: bytes, format: str) -> "ImageContent":
        # Optionally, you can use 'format' if needed for processing/validation
        base64_image = base64.b64encode(bytes_content).decode("utf-8")

        encoded = f"data:image/{format};base64,{base64_image}"

        return cls(encoded)

    def __repr__(self) -> str:
        fields = []
        for k, v in self.__dict__.items():
            if k == "base64_content" and isinstance(v, bytes):
                preview = v[:20]
                suffix = b"..." if len(v) > 10 else b""
                fields.append(f"{k}={preview!r}{suffix.decode()}")
            else:
                fields.append(f"{k}={v!r}")
        return f"{self.__class__.__name__}({', '.join(fields)})"


@dataclass(init=False)
class Message(SerializableDataclass):
    """
    Messages are an exchange medium between the user, LLM agent, and controller logic.
    This helps to determine who provided what information.

    Parameters
    ----------
    content:
        Content of the message.
    message_type:
        A message type out of the following ones:
        SYSTEM, AGENT, USER, THOUGHT, INTERNAL, TOOL_REQUEST, TOOL_RESULT.
    tool_requests:
        A list of ``ToolRequest`` objects representing the tools invoked as part
        of this message. Each request includes the tool's name, arguments,
        and a unique identifier.
    tool_result:
        A ``ToolResult`` object representing the outcome of a tool invocation.
        It includes the returned content and a reference to the related tool request ID.
    display_only:
        If True, the message is excluded from any context. Its only purpose is to be displayed in the chat UI (e.g debugging message)
    sender:
        Sender of the message in str format.
    recipients:
        Recipients of the message in str format.
    time_created:
        Creation timestamp of the message.
    time_updated:
        Update timestamp of the message.
    contents:
        Message content. Is a list of chunks with potentially different types
    role:
        Role of the sender of the message. Can be `user`, `system` or `assistant`
    """

    # message content (showed to users or LLMs)
    role: Literal["user", "assistant", "system"]
    contents: List[MessageContent]
    tool_requests: Optional[List["ToolRequest"]] = None
    tool_result: Optional["ToolResult"] = None
    display_only: bool = False
    _prompt_cache_key: Optional[str] = (
        None  # Works for both OpenAI Responses and Chat Completions API
    )
    _reasoning_content: Optional[_ReasoningContent] = None  # Only for OpenAI Responses API

    _can_be_referenced: ClassVar[bool] = False

    # message metadata (specifies behavior)
    sender: Optional[str] = None
    recipients: Set[str] = field(default_factory=set)
    time_created: datetime = field(default_factory=lambda: datetime.now(timezone.utc), repr=False)
    time_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc), repr=False)

    def __init__(
        self,
        content: str = "",
        message_type: Optional[MessageType] = None,  # deprecated
        tool_requests: Optional[List["ToolRequest"]] = None,
        tool_result: Optional["ToolResult"] = None,
        is_error: bool = False,  # deprecated
        display_only: bool = False,
        sender: Optional[str] = None,
        recipients: Optional[Set[str]] = None,
        time_created: Optional[datetime] = None,
        time_updated: Optional[datetime] = None,
        contents: Optional[List[MessageContent]] = None,
        role: Optional[Literal["user", "system", "assistant"]] = None,
        _prompt_cache_key: Optional[str] = None,  # Only for OpenAI Responses API
        _reasoning_content: Optional[_ReasoningContent] = None,  # Only for OpenAI Responses API
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        if __metadata_info__ is None:
            __metadata_info__ = {}
        # because parent is dataclass, the super is the one from dataclasses
        super().__init__(__metadata_info__=__metadata_info__)

        if contents is not None and len(content):
            raise RuntimeError("Contents and content should not be both specified at the same time")
        if recipients is None:
            recipients = set()

        if time_created is None:
            time_created = datetime.now(timezone.utc)
        if time_updated is None:
            time_updated = datetime.now(timezone.utc)

        if contents is None:
            contents = []

        self.display_only = display_only

        # NOTE: This function has side-effects. It modifies input arguments in-place
        role_from_conversion = cast(
            Optional[Literal["user", "system", "assistant"]],
            self._convert_deprecated_arguments(
                content,
                message_type,
                is_error,
                contents,
                __metadata_info__,
            ),
        )
        effective_role = "user"

        if role_from_conversion is not None:
            if role is not None:
                raise ValueError(
                    "Messages should not be created with `message_type` and `role` specified"
                )
            else:
                effective_role = role_from_conversion
        elif role:
            effective_role = role

        self.tool_requests = tool_requests
        self.tool_result = tool_result

        valid_roles = ["user", "system", "assistant"]
        if effective_role not in valid_roles:
            warnings.warn(
                f"An invalid role was passed as parameter {role}. The role should be one of {valid_roles}"
            )
        self.role = cast(Literal["user", "assistant", "system"], effective_role)
        self.contents = contents
        self.sender = sender
        self.recipients = recipients
        self._reasoning_content = _reasoning_content
        self._prompt_cache_key = _prompt_cache_key
        self.time_created = time_created
        self.time_updated = time_updated
        self._validate()

        self._hash_compute_time = time_updated
        self._hash: Optional[str] = None

    def _convert_deprecated_arguments(
        self,
        content: str,
        message_type: Optional[MessageType],
        is_error: bool,
        contents: List[MessageContent],
        __metadata_info__: MetadataType,
    ) -> Optional[str]:
        # NOTE: This function has side effects. It modifies input arguments in-place
        self.display_only = self.display_only or message_type == MessageType.DISPLAY_ONLY
        role = None
        if message_type is not None:
            # NOTE: To deprecate later

            if message_type == MessageType.USER:
                role = "user"
            elif message_type == MessageType.SYSTEM:
                role = "system"
            elif message_type == MessageType.TOOL_REQUEST:
                role = "assistant"
            elif message_type == MessageType.TOOL_RESULT:
                role = "assistant"
            else:
                role = "assistant"
                # save potential other message_type
                __metadata_info__["message_type"] = message_type.value
        if is_error:
            warnings.warn(
                "Passing `is_error` to messages is deprecated.",
                DeprecationWarning,
            )
            __metadata_info__["is_error"] = True
        if content is not None and content != "":
            contents.append(TextContent(content=content))
        return role

    @property
    def message_type(self) -> MessageType:
        """Getter to guarantee backward compatibility"""
        # NOTE: To deprecate later
        if self.role == "system":
            return MessageType.SYSTEM

        if self.tool_requests is not None:
            return MessageType.TOOL_REQUEST
        elif self.tool_result is not None:
            return MessageType.TOOL_RESULT
        elif self.role == "user":
            return MessageType.USER

        if self.__metadata_info__.get("is_error", False):
            return MessageType.ERROR
        elif "message_type" in self.__metadata_info__:
            return MessageType(self.__metadata_info__["message_type"])
        elif self.display_only:
            return MessageType.DISPLAY_ONLY
        else:
            return MessageType.AGENT

    @property
    def content(self) -> str:
        """Text content getter"""

        from wayflowcore._utils.formatting import stringify

        txt_chunks = [c.content for c in self.contents if isinstance(c, TextContent)]
        if txt_chunks:
            return "\n".join(txt_chunks)

        # 2. BACK-COMPAT: expose tool_result text
        if self.tool_result is not None:
            return stringify(self.tool_result.content or "")

        return ""

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        from wayflowcore.serialization.serializer import serialize_to_dict

        # NOTE: Manual deserialization is required because of the tool request and tool result objects

        return {
            "sender": self.sender,
            "recipients": list(self.recipients),
            "time_created": self.time_created,
            "time_updated": self.time_updated,
            "role": self.role,
            "contents": (
                [serialize_to_dict(content, serialization_context) for content in self.contents]
                if self.contents
                else []
            ),
            "__metadata_info__": self.__metadata_info__,
            "tool_requests": (
                [
                    {"name": t.name, "args": t.args, "tool_request_id": t.tool_request_id}
                    for t in self.tool_requests
                ]
                if self.tool_requests is not None
                else None
            ),
            "tool_result": (
                {
                    "tool_request_id": self.tool_result.tool_request_id,
                    "content": self.tool_result.content,
                }
                if self.tool_result is not None
                else None
            ),
        }

    @property
    @deprecated("`is_error` is deprecated.")
    def is_error(self) -> bool:
        return bool(self.__metadata_info__.get("is_error", False))

    def __setattr__(self, name: str, value: Optional[Union[str, MessageType, datetime]]) -> None:
        if (
            name != "time_updated"
            and name != "__metadata_info__"
            and name != "_hash"
            and name != "_hash_compute_time"
        ):
            super().__setattr__("time_updated", datetime.now(timezone.utc))
        if name == "content" and isinstance(value, str):
            self.contents = [TextContent(content=value)]
        else:
            super().__setattr__(name, value)

    @property
    def hash(self) -> str:
        if self._hash is None or self._hash_compute_time < self.time_updated:
            hashable_values = [
                [self.contents],
                self.tool_result,
                self.tool_requests,
                str(self.role),
            ]
            self._hash = fast_stable_hash(hashable_values)
            self._hash_compute_time = datetime.now(timezone.utc)
        return self._hash

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        return Message(
            sender=input_dict["sender"],
            recipients=set(input_dict["recipients"]),
            time_created=input_dict["time_created"],
            time_updated=input_dict["time_updated"],
            role=input_dict.get("role", None),
            contents=(
                autodeserialize_any_from_dict(input_dict["contents"], deserialization_context)
                if "contents" in input_dict
                else []
            ),
            # backward compatibility
            tool_requests=(
                [
                    ToolRequest(
                        name=t["name"], args=t["args"], tool_request_id=t["tool_request_id"]
                    )
                    for t in input_dict["tool_requests"]
                ]
                if input_dict.get("tool_requests", None) is not None
                else None
            ),
            tool_result=(
                ToolResult(
                    content=input_dict["tool_result"]["content"],
                    tool_request_id=input_dict["tool_result"]["tool_request_id"],
                )
                if input_dict.get("tool_result", None) is not None
                else None
            ),
            content=input_dict.get("content", ""),
            is_error=input_dict.get("is_error", False),
            message_type=(
                MessageType(input_dict["message_type"]) if "message_type" in input_dict else None
            ),
            __metadata_info__=input_dict["__metadata_info__"],
        )

    def copy(self, **kwargs: Any) -> "Message":
        """Create a copy of the given message."""
        self_params = {k: deepcopy(v) for k, v in self.__dict__.items() if k not in kwargs}
        # If `content` is specified it will overwrite `contents`
        if "contents" in self_params and "content" in kwargs:
            self_params.pop("contents")
        self_params.update(kwargs)
        # Id is not part of the message constructor
        self_params.pop("id", None)
        self_params.pop("_hash", None)
        self_params.pop("_hash_compute_time", None)
        return Message(**self_params)

    def _validate(self) -> None:

        if self.tool_requests is not None and self.message_type != MessageType.TOOL_REQUEST:
            raise ValueError(
                f"Message contains a tool_requests, but is of type {self.message_type.value} instead of TOOL_REQUEST"
            )
        if self.message_type == MessageType.TOOL_REQUEST and self.tool_requests is None:
            raise ValueError("Message of type TOOL_REQUEST should contain a list of tool_requests")
        if self.tool_result is not None and self.message_type != MessageType.TOOL_RESULT:
            raise ValueError(
                f"Message contains a tool_result, but is of type {self.message_type.value} instead of TOOL_RESULT"
            )
        if self.message_type == MessageType.TOOL_RESULT and self.tool_result is None:
            raise ValueError("Message of type TOOL_RESULT should contain a tool_result")
        if self.tool_requests is not None and any(
            not isinstance(tr, ToolRequest) for tr in self.tool_requests
        ):
            raise ValueError(
                f"Message.tool_requests should be of type List[ToolRequest] but was {self.tool_requests}"
            )

        if self.tool_result is not None and not isinstance(self.tool_result, ToolResult):
            raise ValueError("Message.tool_results should be of type ToolResult")


@dataclass
class MessageList(SerializableDataclass):
    """
    Object that carries a list of messages. We may only append to this object, not remove

    Parameters
    ----------
    messages:
        list of messages to start from.
    """

    messages: List[Message] = field(default_factory=list)

    @classmethod
    def from_messages(
        cls, messages: Union[None, str, Message, List[Message]] = None
    ) -> "MessageList":
        if messages is None:
            messages = []
        elif isinstance(messages, str):
            messages = [Message(role="user", content=messages)]
        elif isinstance(messages, Message):
            messages = [messages]
        else:
            messages = messages
        return MessageList(messages=messages)

    def append_message(self, message: Message) -> None:
        """Add a message to a message list.

        Parameters
        ----------
        message:
            Message to append to the message list.
        """
        from wayflowcore.events.event import ConversationMessageAddedEvent
        from wayflowcore.events.eventlistener import record_event

        if message is None:
            warnings.warn(
                "Attempted to append a None message to the messages list. This message has been discarded."
            )
            return
        if not isinstance(message, Message):
            raise TypeError(f"`message` should be of type `Message` but is of type {type(message)}")
        self.messages.append(message)
        record_event(
            ConversationMessageAddedEvent(
                message=message,
                streamed=False,
            )
        )

    def append_agent_message(self, agent_input: str, is_error: bool = False) -> None:
        """Append a new message object of type ``MessageType.AGENT`` to the messages list.

        Parameters
        ----------
        agent_input:
            message to append.
        """
        message = Message(content=agent_input, message_type=MessageType.AGENT, is_error=is_error)
        self.append_message(message)

    def append_user_message(self, user_input: Union[str, List[MessageContent]]) -> None:
        """Append a new message object of type ``MessageType.USER`` to the messages list.

        Parameters
        ----------
        user_input:
            message to append.
        """
        self.append_message(
            Message(
                contents=(
                    user_input
                    if isinstance(user_input, list)
                    else [TextContent(content=user_input)]
                ),
                role="user",
            )
        )

    def append_tool_result(self, tool_result: "ToolResult") -> None:
        """Append a new message object of type ``MessageType.TOOL_RESULT`` to the messages list.

        Parameters
        ----------
        tool_result:
            message to append.
        """
        self.append_message(
            Message(
                tool_result=tool_result,
                message_type=MessageType.TOOL_RESULT,
            )
        )

    def _update_last_message(self, new_message: Message, append_only: bool) -> None:
        """
        This method is used during streaming to either append to the latest message or to fully
        replace it, depending on the streaming event type.

        Parameters
        ----------
        new_message:
            The chunk of message received from the stream. Its content may contain only a few
            tokens of a complete message
        append_only:
            If true appends to the last message, otherwise, it completely replaces it.
        """
        if len(self.messages) == 0:
            raise ValueError("No message to update")
        if append_only:
            last_message = self.messages[-1]
            last_text_chunk = next(
                iter(m for m in last_message.contents[::-1] if isinstance(m, TextContent)), None
            )
            if last_text_chunk is None:
                last_text_chunk = TextContent(content="")
                last_message.contents.append(last_text_chunk)
            last_text_chunk.content += new_message.content
        else:
            self._update_last_message_fields(
                {field.name: getattr(new_message, field.name) for field in fields(new_message)}
            )

    def _update_last_message_fields(self, fields: Dict[str, Any]) -> None:
        last_message = self.messages[-1]
        for field_name, field_value in fields.items():
            setattr(last_message, field_name, field_value)

    async def _stream_message(self, stream: AsyncIterable["TaggedMessageChunkType"]) -> Message:
        from wayflowcore.events.event import (
            ConversationMessageAddedEvent,
            ConversationMessageStreamChunkEvent,
        )
        from wayflowcore.events.eventlistener import record_event
        from wayflowcore.models import StreamChunkType
        from wayflowcore.tracing.span import ConversationMessageStreamSpan

        full_streamed_message = ""
        new_message = None
        streaming_span: Optional[ConversationMessageStreamSpan] = None
        async for chunk in stream:
            chunk_type, content_chunk = chunk
            if chunk_type == StreamChunkType.IGNORED or content_chunk is None:
                pass
            elif chunk_type == StreamChunkType.START_CHUNK:
                full_streamed_message += content_chunk.content
                self.messages.append(content_chunk)
                streaming_span = ConversationMessageStreamSpan(
                    message_list=self,
                    initial_message=content_chunk,
                )
                streaming_span.start()
            elif chunk_type == StreamChunkType.TEXT_CHUNK:
                self._update_last_message(content_chunk, append_only=True)
                if content_chunk.content:
                    full_streamed_message += content_chunk.content
                    record_event(ConversationMessageStreamChunkEvent(chunk=content_chunk.content))
            elif chunk_type == StreamChunkType.END_CHUNK:
                new_message = content_chunk
                self._update_last_message(content_chunk, append_only=False)
                if streaming_span is not None:
                    streaming_span.record_end_span_event(message=content_chunk)
                    streaming_span.end()
                record_event(
                    ConversationMessageAddedEvent(message=self.messages[-1], streamed=True)
                )
                if full_streamed_message != new_message.content:
                    logger.debug(
                        'The content streamed "%s" is different than the final content "%s"',
                        full_streamed_message,
                        new_message.content,
                    )
        if new_message is None:
            raise ValueError("There was no END_CHUNK, so no message was produced")
        return new_message

    async def _append_streaming_message(
        self,
        stream: AsyncIterable["TaggedMessageChunkType"],
        extract_func: Optional[Callable[[Any], "TaggedMessageChunkType"]] = None,
    ) -> Message:
        """
        This function is blocking. It will block until the whole text stream has been added to the messages list.

        Parameters
        ----------
        stream:
            The async iterator to stream.
        extract_func:
            the function to convert the element of the stream into Tuple[txt_chunk, start_new_message, message_type]
            to be able to be added to the messages of the conversation.
            Default behaviour is that all the text of the stream will be added to a single agent message.

        Notes
        -----
        Format of the stream. The stream is composed of Tuples of ``StreamChunkType``, Union[str, Message]. Check out the
        example section below for a concrete example on how the stream will affect the messages list.

        Examples
        --------
        >>> from wayflowcore.models import StreamChunkType
        >>> def stream():
        ...     yield StreamChunkType.START_CHUNK, Message(content='')  # append new message
        ...     yield StreamChunkType.TEXT_CHUNK, 'Hello '  # adds this content to the previous message
        ...     yield StreamChunkType.TEXT_CHUNK, 'world'   # adds this content to the previous message
        ...     yield StreamChunkType.START_CHUNK, 'Hello'   # append a new message
        ...     yield StreamChunkType.END_CHUNK, Message('Hello', tool_call={...})   # append a new message

        """
        from wayflowcore.models._requesthelpers import map_iterator

        if extract_func is not None:
            stream = map_iterator(stream, extract_func)

        return await self._stream_message(stream)

    def get_messages(self) -> List[Message]:
        """Returns a copy of the messages list"""
        return [message.copy() for message in self.messages]

    @overload
    def get_last_message(self) -> Optional[Message]: ...
    @overload
    def get_last_message(self, strict: Literal[True]) -> Message: ...
    @overload
    def get_last_message(self, strict: Literal[False]) -> Optional[Message]: ...
    @overload
    def get_last_message(self, strict: bool) -> Optional[Message]: ...

    def get_last_message(self, strict: bool = False) -> Optional[Message]:
        """Returns the last message from the conversation.
        If strict=True, raises an exception if no messages exist."""
        if len(self.messages) == 0:
            if strict:
                raise ValueError("No messages in conversation")
            return None
        return self.messages[-1].copy()

    @staticmethod
    def _filter_messages_by_type(
        messages: List[Message], types_to_include: List[MessageType]
    ) -> List[Message]:
        filtered_messages = []
        for message in messages:
            if message.message_type in set(types_to_include):
                filtered_messages.append(message)
        return filtered_messages

    def copy(self) -> "MessageList":
        """Create a copy of the given message list."""
        return MessageList(
            messages=[message.copy() for message in self.messages],
            __metadata_info__=deepcopy(self.__metadata_info__),
        )

    def __len__(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        return f"MessageList({self.messages!r})"
