# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, List, Optional

from wayflowcore._utils.async_helpers import is_coroutine_function, run_sync_in_thread
from wayflowcore.serialization.serializer import SerializableCallable, SerializableObject

if TYPE_CHECKING:
    from wayflowcore import Message


class MessageTransform(SerializableCallable, SerializableObject):
    """
    Abstract base class for message transforms.

    Subclasses should implement the __call__ method to transform a list of Message objects
    and return a new list of Message objects, typically for preprocessing or postprocessing
    message flows in the system.
    """

    def __call__(self, messages: List["Message"]) -> List["Message"]:
        """Implement this method for synchronous logic (CPU-bounded)"""
        raise NotImplementedError()

    async def call_async(self, messages: List["Message"]) -> List["Message"]:
        """Implement this method for asynchronous work (IO-bounded, with LLM calls, DB loading ...)"""
        return await run_sync_in_thread(self.__call__, messages)


@dataclass
class CallableMessageTransform(MessageTransform):
    func: Callable[..., Any]

    async def call_async(self, messages: List["Message"]) -> List["Message"]:
        if is_coroutine_function(self.func):
            return await self.func(messages)  # type: ignore
        else:
            return await run_sync_in_thread(self.func, messages)


class CoalesceSystemMessagesTransform(MessageTransform, SerializableObject):
    """
    Transform that merges consecutive system messages at the start of a message list
    into a single system message. This is useful for reducing redundancy and ensuring
    that only one system message appears at the beginning of the conversation.
    """

    def __call__(self, messages: List["Message"]) -> List["Message"]:
        from wayflowcore import Message, MessageType

        if len(messages) == 0 or messages[0].message_type is not MessageType.SYSTEM:
            return messages
        first_non_system_msg_idx = next(
            (i for i, msg in enumerate(messages) if msg.message_type != MessageType.SYSTEM),
            len(messages),
        )
        system_messages = [msg.content.strip("\n") for msg in messages[:first_non_system_msg_idx]]
        return [
            Message(content="\n\n".join(system_messages), message_type=MessageType.SYSTEM)
        ] + messages[first_non_system_msg_idx:]


class RemoveEmptyNonUserMessageTransform(MessageTransform, SerializableObject):
    """
    Transform that removes messages which are empty and not from the user.

    Any message with empty content and no tool requests, except for user messages,
    will be filtered out from the message list.

    This is useful in case the template contains optional messages, which will be discarded if their
    content is empty (with a string template such as "{% if __PLAN__ %}{{ __PLAN__ }}{% endif %}").
    """

    def __call__(self, messages: List["Message"]) -> List["Message"]:
        return [
            m
            for m in messages
            if m.content != ""
            or m.tool_requests is not None
            or m.role == "user"
            or m.tool_result is not None
        ]


class AppendTrailingSystemMessageToUserMessageTransform(MessageTransform, SerializableObject):
    """
    Transform that appends the content of a trailing system message to the previous user message.

    If the last message in the list is a system message and the one before it is a user message,
    this transform merges the system message content into the user message, reducing message clutter.

    This is useful if the underlying LLM does not support system messages at the end.
    """

    def __call__(self, messages: List["Message"]) -> List["Message"]:
        from wayflowcore.messagelist import MessageType

        if len(messages) < 2:
            return messages

        last_message = messages[-1]
        penultimate_message = messages[-2].copy()
        if (
            last_message.message_type != MessageType.SYSTEM
            or penultimate_message.message_type != MessageType.USER
        ):
            return messages

        penultimate_message.contents.extend(last_message.contents)
        return messages[:-2] + [penultimate_message]


class SplitPromptOnMarkerMessageTransform(MessageTransform, SerializableObject):
    """
    Split prompts on a marker into multiple messages with the same role. Only apply to the messages without tool_requests and tool_result.

    This transform is useful for script-based execution flows, where a single prompt script can be converted into multiple conversation turns for step-by-step reasoning.
    """

    def __init__(self, marker: Optional[str] = None):
        self.marker = marker if marker is not None else "\n---"

    def __call__(self, messages: list["Message"]) -> list["Message"]:
        new_messages = []

        for msg in messages:
            if msg.tool_requests is None and msg.tool_result is None and self.marker in msg.content:
                for part in (p.strip() for p in msg.content.split(self.marker) if p.strip()):
                    new_msg = msg.copy(content=part)
                    new_messages.append(new_msg)
            else:
                new_messages.append(msg)

        return new_messages
