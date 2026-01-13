# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import time
import warnings
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Tuple

from wayflowcore._metadata import MetadataType
from wayflowcore._utils._templating_helpers import render_template
from wayflowcore._utils.formatting import stringify
from wayflowcore.conversation import _get_current_conversation_id
from wayflowcore.datastore.entity import Entity
from wayflowcore.datastore.inmemory import _INMEMORY_USER_WARNING, InMemoryDatastore
from wayflowcore.messagelist import Message, MessageContent, TextContent
from wayflowcore.models.llmmodel import Prompt
from wayflowcore.models.tokenusagehelpers import CountTokensHeuristics
from wayflowcore.property import FloatProperty, IntegerProperty, StringProperty
from wayflowcore.tools.tools import ToolResult
from wayflowcore.transforms.transforms import MessageTransform

logger = logging.getLogger(__name__)

_SUMMARIZATION_WARNING_MESSAGE = (
    "Using a SummarizationMessageTransform without specifying the datastore "
    "will create by default an InMemoryDatastore for caching which is not recommended for production systems."
)

if TYPE_CHECKING:
    from wayflowcore.datastore import Datastore
    from wayflowcore.models import LlmModel


class _MessageCache:
    """
    A helper class for caching message summaries and other content to avoid redundant summarization.

    This class manages a cache with configurable size and lifetime limits, storing and retrieving
    cached content using a datastore interface. It handles automatic eviction of expired and least
    recently used entries.
    """

    MANAGED_FIELDS = ["created_at", "last_used_at"]

    def __init__(
        self,
        max_cache_size: Optional[int],
        max_cache_lifetime: Optional[int],
        datastore: Optional["Datastore"],
        collection_name: str,
        entity_def: Entity,
    ):
        self.max_cache_size = max_cache_size
        self.max_cache_lifetime = max_cache_lifetime

        if self.max_cache_lifetime and self.max_cache_lifetime <= 0:
            raise ValueError("max_cache_lifetime must be a positive integer or None.")
        if self.max_cache_size and self.max_cache_size <= 0:
            raise ValueError("max_cache_size must be a positive integer or None.")

        self.collection_name = collection_name
        self.entity_def = entity_def

        if datastore:
            self.datastore = datastore
            # Validate that the user provided datastore corresponds has the required
            # fields.
            self._validate_datastore_schema()
        else:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=f"{_INMEMORY_USER_WARNING}*")
                self.datastore = InMemoryDatastore(
                    self._get_cache_schema(collection_name, entity_def)
                )
            warnings.warn(_SUMMARIZATION_WARNING_MESSAGE)

    def _get_cache_schema(self, collection_name: str, entity_def: Entity) -> dict[str, Entity]:
        return {collection_name: entity_def}

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

    def retrieve(self, cache_key: str) -> Optional[Dict[str, Any]]:
        self._remove_expired_conversations()
        cached_conversation = self.datastore.list(
            self.collection_name,
            where={"cache_key": cache_key},
        )

        if len(cached_conversation) == 0:
            return None
        content = cached_conversation[0]

        self.datastore.update(
            self.collection_name,
            {"cache_key": cache_key},
            {"last_used_at": time.time()},
        )
        return content

    def store(self, cache_key: str, content: Dict[str, Any]) -> None:
        # This implementation is inefficient. A future improvement could optimize this could be to add
        # a method that returns the number of rows per collection in the Datastore interface.
        cache_size = len(self.datastore.list(self.collection_name))
        if self.max_cache_size and cache_size > self.max_cache_size:
            self._remove_lru()
        self._validate_content(content)

        created_at = time.time()
        self._remove_expired_conversations()
        self.datastore.create(
            self.collection_name,
            {
                "cache_key": cache_key,
                **content,
                "created_at": created_at,
                "last_used_at": created_at,
            },
        )

    def _validate_content(self, content: Dict[str, Any]) -> None:
        for field in self.MANAGED_FIELDS:
            if field in content:
                raise ValueError(
                    f"Field {field} should not be provided in content. It is managed by _MessageCache"
                )
        if "cache_key" in content:
            raise ValueError(
                "cache_key should be passed as parameter and not in content dictionnary."
            )
        valid_fields = self.entity_def.properties
        for field in content.keys():
            if field not in valid_fields:
                raise ValueError(f"Invalid field {field}")

    def _validate_datastore_schema(self) -> None:
        found_schema = self.datastore.describe()
        correct_schema = self._get_cache_schema(self.collection_name, self.entity_def)

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


class _Summarizer:
    """
    A helper class for summarizing message contents using an LLM.
    """

    _PROMPT_TEMPLATE = "{instructions}\n\nPrevious summary:\n{previous_summary}\n\nAdded content:\n"

    def __init__(
        self, llm: "LlmModel", summarization_instructions: str, summarized_content_template: str
    ) -> None:
        self.llm = llm
        self.summarization_instructions = summarization_instructions
        self.summarized_content_template = summarized_content_template

    async def _summarize_chunk(self, previous_summary: str, chunk: List[MessageContent]) -> str:
        prompt = self._PROMPT_TEMPLATE.format(
            instructions=self.summarization_instructions, previous_summary=previous_summary
        )
        contents = [TextContent(prompt)] + chunk
        prompt_obj = Prompt([Message(contents=contents)])
        completion = await self.llm.generate_async(prompt_obj)
        return completion.message.content

    async def summarize(self, contents: List[MessageContent], max_tokens: int) -> str:
        chunk: List[MessageContent] = []
        tokens_in_chunk = 0
        summary = "Nothing summarized yet"
        for content in contents:
            tokens_in_chunk += CountTokensHeuristics.tokens_in_messagecontents([content])
            if tokens_in_chunk > max_tokens and chunk:
                summary = await self._summarize_chunk(summary, chunk)
                chunk = []
                tokens_in_chunk = 0
            chunk.append(content)
        if chunk:
            summary = await self._summarize_chunk(summary, chunk)
        final_summary = render_template(
            self.summarized_content_template, inputs={"summary": summary}
        )
        return final_summary


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

            The datastore needs to have a collection called `cache_collection_name`. This collection's entries should be defined using
            `MessageSummarizationTransform.get_entity_definition` or as follows:
            ```
            Entity({
            "cache_key": StringProperty(),
            "cache_content": StringProperty(),
            "created_at": FloatProperty(),
            "last_used_at": FloatProperty(),
            })
            ```

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
        cache_collection_name: str = DEFAULT_CACHE_COLLECTION_NAME,
        max_cache_size: Optional[int] = 10_000,
        max_cache_lifetime: Optional[int] = 4 * 3600,
        name: str = "message-summarization-transform",
        id: Optional[str] = None,
        description: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        super().__init__(name=name, id=id, description=description)
        self.llm = llm
        self.summarization_instructions = summarization_instructions
        self.summarized_message_template = summarized_message_template
        self.cache_collection_name = cache_collection_name
        self.max_cache_size = max_cache_size
        self.max_cache_lifetime = max_cache_lifetime
        self._summarizer = _Summarizer(llm, summarization_instructions, summarized_message_template)
        self.max_message_size = max_message_size
        if self.max_message_size <= 0:
            raise ValueError("max_message_size must be a positive integer.")
        self.cache = _MessageCache(
            max_cache_size=max_cache_size,
            max_cache_lifetime=max_cache_lifetime,
            datastore=datastore,
            collection_name=cache_collection_name,
            entity_def=self.get_entity_definition(),
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
                    [TextContent(stringify(new_message.tool_result.content))],
                    conv_id,
                    msg_idx,
                    "toolres",
                )
                if isinstance(summarized_content[0], TextContent):
                    new_message.tool_result = ToolResult(
                        summarized_content[0].content, new_message.tool_result.tool_request_id
                    )

            new_messages.append(new_message)

        return new_messages[::-1]

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
        cache_content = self.cache.retrieve(self._get_cache_key(conv_id, msg_idx, _type))
        # No cached message found
        if not cache_content:
            summarized_content = await self._summarizer.summarize(contents, self.max_tokens)
            self.cache.store(
                self._get_cache_key(conv_id, msg_idx, _type), {"cache_content": summarized_content}
            )
        else:
            summarized_content = cache_content["cache_content"]
        return [TextContent(summarized_content)]

    def _get_cache_key(
        self,
        conversation_id: str,
        message_idx: int,
        _type: Literal["toolres", "content"] = "content",
    ) -> str:
        return conversation_id + "_" + str(message_idx) + "_" + _type


class ConversationSummarizationTransform(MessageTransform):
    """
    Summarizes conversations exceeding a given number of messages using an LLM and caches conversation summaries in a ``Datastore``.

    This is useful to reduce long conversation history into a concise context for downstream LLM calls.

    Parameters
    ----------
    llm:
        LLM to use for the summarization.
    max_num_messages:
        Number of message after which we trigger summarization. Tune this parameter depending on the
        context length of your model and the price you are willing to pay (higher means longer conversation
        prompts and more tokens).
    min_num_messages:
        Number of recent messages to keep from summarizing. Tune this parameter to prevent from summarizing
        very recent messages and keep a very responsive and relevant agent.
    summarization_instructions:
        Instruction for the LLM on how to summarize the conversation.
    summarized_conversation_template:
        Jinja2 template on how to present the summary (with variable `summary`) to the agent using the transform.
    datastore:
        Datastore on which to store the cache. If not specified, an in-memory Datastore will be created automatically.
    max_cache_size:
        The maximum number of entries kept in the cache
        If None, there is no limit on cache size and no eviction occurs.
    max_cache_lifetime:
        max lifetime of an element in the cache in seconds
        If None, cached data persists indefinitely.
    cache_collection_name:
        the collection in the cache datastore where summarized conversations will be stored

    Examples
    --------
    >>> from wayflowcore.transforms import ConversationSummarizationTransform
    >>> summarization_transform = ConversationSummarizationTransform(
    ...     llm=llm,
    ...     max_num_messages=30,
    ...     min_num_messages=10
    ... )

    """

    DEFAULT_CACHE_COLLECTION_NAME = "summarized_conversations_cache"
    _TOKENS_PER_CHUNK = CountTokensHeuristics.tokens_in_chars(20000)

    def __init__(
        self,
        llm: "LlmModel",
        max_num_messages: int = 50,
        min_num_messages: int = 10,
        summarization_instructions: str = "Please make a summary of this conversation. Include relevant information and keep it short. "
        "Your response will replace the messages, so just output the summary directly, no introduction needed.",
        summarized_conversation_template: str = "Summarized conversation: {{summary}}",
        datastore: Optional["Datastore"] = None,
        max_cache_size: Optional[int] = 10_000,
        max_cache_lifetime: Optional[int] = 4 * 3600,
        cache_collection_name: str = DEFAULT_CACHE_COLLECTION_NAME,
    ) -> None:
        super().__init__()
        self._summarizer = _Summarizer(
            llm, summarization_instructions, summarized_conversation_template
        )
        self.max_num_messages = max_num_messages
        self.min_num_messages = min_num_messages
        self.summarized_conversation_template = summarized_conversation_template
        self.max_cache_size = max_cache_size
        self.max_cache_lifetime = max_cache_lifetime
        self.cache_collection_name = cache_collection_name

        if self.max_num_messages <= 0:
            raise ValueError("max_num_messages must be a positive integer.")
        if self.min_num_messages < 0:
            raise ValueError("min_num_messages must be a non-negative integer.")
        if self.min_num_messages > self.max_num_messages:
            raise ValueError("min_num_messages must not exceed max_num_messages.")

        self.cache = _MessageCache(
            max_cache_size=max_cache_size,
            max_cache_lifetime=max_cache_lifetime,
            datastore=datastore,
            collection_name=cache_collection_name,
            entity_def=self.get_entity_definition(),
        )

    def _split_messages_and_guarantee_tool_calling_consistency(
        self, messages: List["Message"], keep_x_most_recent_messages: int
    ) -> Tuple[List["Message"], List["Message"]]:
        """
        Guarantees consistency of tool requests / results.
        This function guarantees that we keep at least `keep_x_most_recent_messages` non summarized.
        """
        messages_to_summarize = messages[:-keep_x_most_recent_messages]
        messages_to_keep = messages[-keep_x_most_recent_messages:]

        # detect tool results in messages_to_keep missing their tool request
        missing_tool_request_ids = set()
        tool_request_ids = set()
        for msg in messages_to_keep:
            if msg.tool_requests:
                for tool_request in msg.tool_requests:
                    tool_request_ids.add(tool_request.tool_request_id)
            if msg.tool_result:
                tool_request_id = msg.tool_result.tool_request_id
                if tool_request_id not in tool_request_ids:
                    missing_tool_request_ids.add(tool_request_id)

        if len(missing_tool_request_ids) == 0:
            return messages_to_summarize, messages_to_keep

        for idx, msg in enumerate(messages_to_summarize):
            # if a message has the tool request of a tool result in messages_to_keep that misses
            # its tool request, then this message and the ones after should be kept
            if any(
                tc.tool_request_id in missing_tool_request_ids for tc in (msg.tool_requests or [])
            ):
                # all the rest after the tool call should be summarized
                return messages_to_summarize[:idx], messages_to_summarize[idx:] + messages_to_keep

        return messages_to_summarize, messages_to_keep

    def _construct_messages_using_cache(
        self, conversation_id: str, messages: List["Message"]
    ) -> Tuple[Optional[Message], List["Message"]]:
        """Returns: (summarized messages in cache,  non summarized messages + new messages)"""
        content = self.cache.retrieve(conversation_id)
        if content is None:
            return None, messages
        prefix_size = int(content["prefix_size"])
        summarized_message = content["cache_content"]
        return Message(contents=[TextContent(summarized_message)]), messages[prefix_size:]

    async def call_async(self, messages: List["Message"]) -> List["Message"]:
        conv_id = _get_current_conversation_id()
        if not conv_id:
            logger.warning("conversation_id is None. Messages will not be summarized.")
            return messages

        # If the initial message list is not too long. We don't need to summarize it
        if len(messages) <= self.max_num_messages:
            return messages

        # The current message list is : previously summarized part + non summarized part + new messages.
        previous_summarized_message, non_summarized_messages = self._construct_messages_using_cache(
            conv_id, messages
        )

        current_messages = non_summarized_messages
        if previous_summarized_message:
            current_messages = [previous_summarized_message] + non_summarized_messages

        # If the current message list is not too long. We don't need to summarize it
        if len(current_messages) <= self.max_num_messages:
            return current_messages

        messages_to_summarize, messages_to_keep = (
            self._split_messages_and_guarantee_tool_calling_consistency(
                messages=current_messages,
                keep_x_most_recent_messages=self.min_num_messages,
            )
        )
        contents_to_summarize: List[MessageContent] = []
        for message in messages_to_summarize:
            if message != previous_summarized_message:
                contents_to_summarize.append(TextContent("\n\n\n" + message.role + ":\n\n"))
            for c in message.contents:
                contents_to_summarize.append(c)
            if message.tool_result:
                contents_to_summarize.append(TextContent(stringify(message.tool_result.content)))

        summarized_message = await self._summarizer.summarize(
            contents_to_summarize, self._TOKENS_PER_CHUNK
        )

        self.cache.store(
            conv_id,
            {
                "prefix_size": len(messages) - len(messages_to_keep),
                "cache_content": summarized_message,
            },
        )

        return [Message(summarized_message)] + messages_to_keep

    @staticmethod
    def get_entity_definition() -> Entity:
        return Entity(
            properties={
                "cache_key": StringProperty(),
                "cache_content": StringProperty(),
                "prefix_size": IntegerProperty(),
                "created_at": FloatProperty(),
                "last_used_at": FloatProperty(),
            }
        )
