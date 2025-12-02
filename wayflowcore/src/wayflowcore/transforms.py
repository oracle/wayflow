# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, List, Literal, Optional

from wayflowcore._utils._templating_helpers import render_template
from wayflowcore._utils.async_helpers import is_coroutine_function, run_sync_in_thread
from wayflowcore.conversation import _get_current_conversation_id
from wayflowcore.datastore.entity import Entity
from wayflowcore.datastore.inmemory import InMemoryDatastore
from wayflowcore.messagelist import Message, MessageContent, MessageType, TextContent
from wayflowcore.models.llmmodel import Prompt
from wayflowcore.models.tokenusagehelpers import CountTokensHeuristics
from wayflowcore.property import FloatProperty, StringProperty
from wayflowcore.serialization.serializer import SerializableCallable, SerializableObject
from wayflowcore.tools import ToolResult

if TYPE_CHECKING:
    from wayflowcore.datastore import Datastore
    from wayflowcore.models import LlmModel

logger = logging.getLogger(__name__)


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
        from wayflowcore.messagelist import Message

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
    Split prompts on a marker into multiple messages with the same role. Only apply to the messages without
    tool_requests and tool_result.

    This transform is useful for script-based execution flows, where a single prompt script can be converted
    into multiple conversation turns for step-by-step reasoning.
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


class _MessageSummarizationCache:
    def __init__(
        self,
        max_cache_size: Optional[int],
        max_cache_lifetime: Optional[int],
        datastore: Optional["Datastore"],
        collection_name: str,
    ):
        self.max_cache_size = max_cache_size
        self.max_cache_lifetime = max_cache_lifetime

        if self.max_cache_lifetime and self.max_cache_lifetime <= 0:
            raise ValueError("max_cache_lifetime must be a positive integer or None.")
        if self.max_cache_size and self.max_cache_size <= 0:
            raise ValueError("max_cache_size must be a positive integer or None.")

        if datastore:
            self.datastore = datastore
        else:
            self.datastore = InMemoryDatastore(self._get_cache_schema(collection_name))

        self.collection_name = collection_name
        self._validate_datastore_schema()

    def _get_cache_schema(self, collection_name: str) -> dict[str, Entity]:
        return {collection_name: _MessageSummarizationCache.get_entity_definition()}

    @staticmethod
    def get_entity_definition() -> Entity:
        return Entity(
            properties={
                "cache_key": StringProperty(),
                "cache_content": StringProperty(),
                "created_at": FloatProperty(),
                "last_used_at": FloatProperty(),
            }
        )

    def _remove_expired_conversations(self) -> None:
        if self.max_cache_lifetime is None:
            return
        cached_conversations = self.datastore.list(self.collection_name)
        now_time = time.time()
        for conversation in cached_conversations:
            if now_time - conversation["created_at"] > self.max_cache_lifetime:
                self.datastore.delete(self.collection_name, conversation)

    def _remove_lru(self) -> None:
        # Sort by created_at such that oldest comes first
        cached_conversations = self.datastore.list(self.collection_name)
        cached_conversations.sort(key=lambda c: c.get("last_used_at", 0))
        cache_key = cached_conversations[0].get("cache_key")
        self.datastore.delete(self.collection_name, {"cache_key": cache_key})

    def retrieve_message(self, cache_key: str) -> Optional[str]:
        self._remove_expired_conversations()
        cached_conversation = self.datastore.list(
            self.collection_name,
            where={"cache_key": cache_key},
        )

        if len(cached_conversation) == 0:
            return None
        message = cached_conversation[0]["cache_content"]

        self.datastore.update(
            self.collection_name,
            {"cache_key": cache_key},
            {"last_used_at": time.time()},
        )
        return str(message)

    def store_message(self, cache_key: str, message_content: str) -> None:
        # This implementation is inefficient. A future improvement could optimize this could be to add
        # a method that returns the number of rows per collection in the Datastore interface.
        cache_size = len(self.datastore.list(self.collection_name))
        if self.max_cache_size and cache_size > self.max_cache_size:
            self._remove_lru()
        created_at = time.time()
        self._remove_expired_conversations()
        self.datastore.create(
            self.collection_name,
            {
                "cache_key": cache_key,
                "cache_content": message_content,
                "created_at": created_at,
                "last_used_at": created_at,
            },
        )

    def _validate_datastore_schema(self) -> None:
        found_schema = self.datastore.describe()
        correct_schema = self._get_cache_schema(self.collection_name)

        if self.collection_name not in found_schema:
            raise ValueError(
                f"Datastore should contain collection {self.collection_name}."
                f"Found {', '.join(found_schema.keys())})"
            )
        found_entity_properties = found_schema[self.collection_name].properties
        correct_entity_properties = correct_schema[self.collection_name].properties
        for column_name, property in correct_entity_properties.items():
            if column_name not in found_entity_properties:
                raise ValueError(
                    f"Datastore should contain column {column_name}"
                    f"Found {', '.join(found_entity_properties.keys())}"
                )
            found_property = found_entity_properties[column_name]
            correct_propery = property
            if not isinstance(found_property, type(correct_propery)):
                raise ValueError(
                    f"Datastore column {column_name} in collection {self.collection_name}"
                    f"Should be: {type(correct_propery)}, Found: {type(found_property)}."
                )


class MessageSummarizationTransform(MessageTransform):
    """
    Summarizes oversized messages using an LLM and optionally caches summaries.

    This is useful for long conversations where the context can become too large for the LLM to handle.


    Parameters
    ----------
    llm:
        LLM to use for the summarization. If the agent's llm supports images, then this llm should also support images.
    max_message_size:
        The maximum size in number of characters for the content of a message. This is converted
        to an estimated token count using heuristics (approximately max_message_size / 4). Images
        in the message are also converted to estimated token counts (assuming 16x16 patches and
        defaulting to 2048x2048 if the image type is not PNG, JPEG, or JPEG2000). Summarization
        is triggered when the total estimated token count (text + images) of a message exceeds
        this threshold.
    summarization_instructions:
        Instruction for the LLM on how to summarize the messages.
    summarized_message_template:
        Jinja2 template on how to present the summary (with variable `summary`) to the agent using the transform.
    datastore:
        Datastore on which to store the cache. If None, an in-memory Datastore will be created automatically.

        .. important::

            The datastore needs to have a collection called `cache_collection_name`. This collection's entries should be defined as follows
            `MessageSummarizationTransform.get_entity_definition`
            Its properties should be as follows:
            ```
            Entity({
                "cache_key": StringProperty(),
                "cache_content": StringProperty(),
                "created_at": FloatProperty(),
                "last_used_at": FloatProperty(),
            })
            ```
            You can get this object using `MessageSummarizationTransform.get_entity_definition()`.

    cache_collection_name:
        Name of the collection/table in the cache for storing summarized messages.
    max_cache_size:
        The number of cache entries (messages) kept in the cache.
        If None, there is no limit on cache size and no eviction occurs.
    max_cache_lifetime:
        max lifetime of a message in the cache in seconds.
        If None, cached data persists indefinitely.
    Examples
    --------
    >>> from wayflowcore.transforms import MessageSummarizationTransform
    >>> summarization_transform = MessageSummarizationTransform(
    ...     llm=llm,
    ...     max_message_size=30_000
    ... )

    """

    DEFAULT_CACHE_COLLECTION_NAME = "summarized_messages_cache"

    def __init__(
        self,
        llm: "LlmModel",
        max_message_size: int = 20_000,
        summarization_instructions: str = (
            "Please make a summary of this message. Include relevant information and keep it short. "
            "Your response will replace the message, so just output the summary directly, no introduction needed."
        ),
        summarized_message_template: str = "Summarized message: {{summary}}",
        datastore: Optional["Datastore"] = None,
        cache_collection_name: str = "summarized_messages_cache",
        max_cache_size: Optional[int] = 10_000,
        max_cache_lifetime: Optional[int] = 4 * 3600,
    ) -> None:
        super().__init__()
        self.llm = llm
        self.max_message_size = max_message_size
        self.summarization_instructions = summarization_instructions
        self.summarized_message_template = summarized_message_template
        self.messages_cache = _MessageSummarizationCache(
            max_cache_size=max_cache_size,
            max_cache_lifetime=max_cache_lifetime,
            datastore=datastore,
            collection_name=cache_collection_name,
        )
        self.max_tokens = CountTokensHeuristics.tokens_in_chars(self.max_message_size)

    async def call_async(self, messages: List["Message"]) -> List["Message"]:

        conv_id = _get_current_conversation_id()
        if not conv_id:
            logger.warning("conversation_id is None. Messages will not be summarized.")
            return messages

        new_messages = []
        # We go in reverse order so LRU is last (Heuristic for better kv cache use).
        for msg_idx in range(len(messages) - 1, -1, -1):
            message = messages[msg_idx]

            summarized_content = await self.summarize_if_needed(
                message.contents, conv_id, msg_idx, "content"
            )
            new_message = message.copy(contents=summarized_content)

            if new_message.tool_result is not None:
                # If there's a tool_result, we also summarize it.
                summarized_content = await self.summarize_if_needed(
                    [TextContent(new_message.tool_result.content)], conv_id, msg_idx, "toolres"
                )
                if isinstance(summarized_content[0], TextContent):
                    new_message.tool_result = ToolResult(
                        summarized_content[0].content, new_message.tool_result.tool_request_id
                    )

            new_messages.append(new_message)

        return new_messages[::-1]

    @staticmethod
    def get_entity_definition() -> Entity:
        return _MessageSummarizationCache.get_entity_definition()

    async def _summarize_chunk(self, previous_summary: str, chunk: List[MessageContent]) -> str:
        prompt = (
            f"{self.summarization_instructions}\n\n"
            "Previous summary:\n"
            f"{previous_summary}\n\n"
            "Added content:\n"
        )
        contents = [TextContent(prompt)] + chunk
        prompt_obj = Prompt([Message(contents=contents)])
        completion = await self.llm.generate_async(prompt_obj)
        return completion.message.content

    async def _summarize(self, contents: List[MessageContent]) -> str:
        chunk: List[MessageContent] = []
        tokens_in_chunk = 0
        summary = "Nothing summarized yet"
        for content in contents:
            tokens_in_chunk += CountTokensHeuristics.tokens_in_messagecontents([content])
            if tokens_in_chunk > self.max_tokens and chunk:
                summary = await self._summarize_chunk(summary, chunk)
                chunk = []
                tokens_in_chunk = 0
            chunk.append(content)
        if chunk:
            summary = await self._summarize_chunk(summary, chunk)
        final_summary = render_template(
            self.summarized_message_template, inputs={"summary": summary}
        )
        return final_summary

    async def summarize_if_needed(
        self,
        contents: List[MessageContent],
        conv_id: str,
        msg_idx: int,
        _type: Literal["toolres", "content"] = "content",
    ) -> List[MessageContent]:
        if CountTokensHeuristics.tokens_in_messagecontents(contents) <= self.max_tokens:
            return contents
        # Fetch from cache the content of the summarized version of messages.
        content_summary = self.messages_cache.retrieve_message(
            self._get_cache_key(conv_id, msg_idx, _type)
        )

        # No cached message found
        if not content_summary:
            content_summary = await self._summarize(contents)
            self.messages_cache.store_message(
                self._get_cache_key(conv_id, msg_idx, _type), content_summary
            )
        return [TextContent(content_summary)]

    def _get_cache_key(
        self,
        conversation_id: str,
        message_idx: int,
        _type: Literal["toolres", "content"] = "content",
    ) -> str:
        return conversation_id + "_" + str(message_idx) + "_" + _type
