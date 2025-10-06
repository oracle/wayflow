# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
from contextlib import contextmanager
from typing import Any, AsyncIterable, AsyncIterator, Callable, Dict, Generator, List, Union
from unittest.mock import patch

from wayflowcore import Message, MessageType
from wayflowcore.models import (
    LlmCompletion,
    LlmModel,
    StreamChunkType,
    TaggedMessageChunkType,
    TaggedMessageChunkTypeWithTokenUsage,
)
from wayflowcore.models.openaicompatiblemodel import OpenAICompatibleModel
from wayflowcore.tools import ToolRequest


def _get_next_completion(elements: List[Any]) -> Callable[[Any], Any]:
    n = len(elements)

    async def side_effect_func(*args: Any, **kwargs: Any) -> Any:
        try:
            return elements.pop(0)
        except IndexError:
            raise ValueError(
                f"The LLM generation was called {n+1} times, but you only provided {n} values."
            )

    return side_effect_func


def _get_next_completion_stream(elements: List[Any]) -> Callable[[Any], Any]:
    n = len(elements)

    async def side_effect_func(*args: Any, **kwargs: Any) -> Any:
        try:
            new_iterator = elements.pop(0)
            async for chunk in new_iterator:
                yield chunk
        except IndexError:
            raise ValueError(
                f"The LLM generation was called {n+1} times, but you only provided {n} values."
            )

    return side_effect_func


@contextmanager
def patch_llm(
    llm: "LlmModel",
    outputs: List[Union[str, List["ToolRequest"], "Message"]],
    patch_internal: bool = False,
) -> Generator[None, None, None]:
    """
    Patch `llm.generate` and `llm.stream_generate` so that every call returns
    the next element in outputs.

    Example
    -------
    >>> with patch_llm(llm, "hi", "there"):
    >>>    assert llm.generate("some prompt").message.content == "hi"
    >>>    assert llm.generate("some other prompt").message.content == "there"
    """

    def to_message(out: Union[str, List["ToolRequest"], "Message"]) -> "Message":
        if isinstance(out, str):
            return Message(content=out, message_type=MessageType.AGENT)
        elif isinstance(out, list):
            return Message(tool_requests=out, message_type=MessageType.TOOL_REQUEST)
        return out  # already a Message

    def build_iterator(msg: "Message") -> AsyncIterator[TaggedMessageChunkType]:
        async def _iterator(*args: Any, **kwargs: Any) -> AsyncIterator[TaggedMessageChunkType]:
            yield StreamChunkType.START_CHUNK, Message(content="", message_type=MessageType.AGENT)
            yield StreamChunkType.TEXT_CHUNK, msg
            yield StreamChunkType.END_CHUNK, msg

        return _iterator()

    def build_iterator_internal(
        msg: "Message",
    ) -> AsyncIterator[TaggedMessageChunkTypeWithTokenUsage]:
        async def _iterator(
            *args: Any, **kwargs: Any
        ) -> AsyncIterator[TaggedMessageChunkTypeWithTokenUsage]:
            yield StreamChunkType.START_CHUNK, Message(
                content="", message_type=MessageType.AGENT
            ), None
            yield StreamChunkType.TEXT_CHUNK, msg, None
            yield StreamChunkType.END_CHUNK, msg, None

        return _iterator()

    messages = [to_message(o) for o in outputs]

    completions = [LlmCompletion(message=m, token_usage=None) for m in messages]

    if not patch_internal:
        patch_generate = patch.object(
            llm, "generate_async", side_effect=_get_next_completion(completions)
        )
        iterators = [build_iterator(m) for m in messages]
        patch_stream = patch.object(
            llm, "stream_generate_async", side_effect=_get_next_completion_stream(iterators)
        )
    else:
        patch_generate = patch.object(
            llm, "_generate_impl", side_effect=_get_next_completion(completions)
        )
        internal_iterators = [build_iterator_internal(m) for m in messages]
        patch_stream = patch.object(
            llm,
            "_stream_generate_impl",
            side_effect=_get_next_completion_stream(internal_iterators),
        )

    with patch_generate, patch_stream:
        yield


@contextmanager
def patch_openai_compatible_llm(
    llm: OpenAICompatibleModel, txt: str
) -> Generator[None, None, None]:
    """
    Patches a vllm LLM remote call to return a given text. This context manager is useful to make tests
    deterministic and test prompt templates.

    Parameters
    ----------
    llm:
        The Vllm LLM to patch (patches both `generate` and `stream_generate`.
    txt:
        The raw text to return
    """

    async def _iterator(*args: Any, **kwargs: Any) -> AsyncIterable[Dict[str, Any]]:
        yield {"choices": [{"delta": {"content": txt}}]}

    def _generate(*arg: Any, **kwarg: Any) -> Any:
        return {"choices": [{"message": {"content": txt}}]}

    with patch.object(
        llm,
        "_post",
        side_effect=_get_next_completion([_generate()]),
    ), patch.object(
        llm,
        "_post_stream",
        side_effect=_get_next_completion_stream([_iterator()]),
    ):
        yield
