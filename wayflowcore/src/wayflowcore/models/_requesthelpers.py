# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterable,
    Callable,
    Dict,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

import httpx

if TYPE_CHECKING:
    from wayflowcore.messagelist import Message

from wayflowcore.tokenusage import TokenUsage

logger = logging.getLogger(__name__)


@dataclass
class _RetryStrategy:
    max_retries: int = 2
    """Maximum number of retries for a request that fails with a recoverable status"""
    min_wait: float = 0.5
    """Minimum amount of time to wait between retries (in seconds)"""
    max_wait: float = 8
    """Maximum amount of time to wait between 2 retries (in seconds)"""
    backoff_factor: float = 2.0
    """Back-off factor to increase the amount of time between 2 retries: t(n+1) = backoff_factor * t(n)"""
    recoverable_statuses: Sequence[int] = (429, 500, 502, 503, 504)
    """
    Statuses considered as recoverable:
    - 429: throttling (retry after x time)
    - 5xx: network issues
    """
    timeout: Union[float, httpx.Timeout] = field(
        default_factory=lambda: httpx.Timeout(timeout=600, connect=20.0)
    )
    # fix httpx async client timeout
    # our default timeout is 10 minutes
    # default connection timeout is 20 seconds
    """Timeout for the remote request. Can be a `httpx.Timeout` object or a float, in which case all timeouts (connect, read, ...) will be set to this value."""


async def _parse_streaming_response_text(stream_lines: AsyncIterable[str]) -> str:
    """
    This method parses the typical streaming content from a hosted LLM model

    The response text should typically look like the below:
    ```
    data: {"id": "abcde", "object": "chat.completion.chunk", "created": 1756815855, "model": "xyz", "choices": [{"index": 0, "delta": {"content": "That"}}]}
    data: {"id": "abcde", "object": "chat.completion.chunk", "created": 1756815855, "model": "xyz", "choices": [{"index": 0, "delta": {"content": "\'s"}}]}
    data: {"id": "abcde", "object": "chat.completion.chunk", "created": 1756815855, "model": "xyz", "choices": [{"index": 0, "delta": {"content": " a"}}]}
    data: {"id": "abcde", "object": "chat.completion.chunk", "created": 1756815855, "model": "xyz", "choices": [{"index": 0, "delta": {"content": " wonderfully"}}]}
    data: {"id": "abcde", "object": "chat.completion.chunk", "created": 1756815855, "model": "xyz", "choices": [{"index": 0, "delta": {"content": " deep"}}]}
    data: {"id": "abcde", "object": "chat.completion.chunk", "created": 1756815855, "model": "xyz", "choices": [{"index": 0, "delta": {"content": " question."}}]}
    data: [DONE]
    ```
    """
    message = ""
    async for line in stream_lines:
        line = line.strip()
        if not line or line == "data: [DONE]":
            continue
        if not line.startswith("data:"):
            continue
        chunk = json.loads(line[len("data: ") :])
        content = chunk["choices"][0]["delta"].get("content")
        if content:
            message += content
    return message


async def request_post_with_retries(
    request_params: Dict[str, Any],
    retry_strategy: _RetryStrategy,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """Makes a POST request using requests.post with OpenAI-like retry behavior"""
    tries = 0
    last_exc = None
    while tries <= retry_strategy.max_retries:
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=retry_strategy.timeout) as session:
                response = await session.post(**request_params)
            if response.status_code == 200:
                try:
                    return response.json()  # type: ignore
                except json.decoder.JSONDecodeError as json_decode_error:
                    # It may happen that llm hosting servers forces streaming even so the
                    # default is stream=False and the request specifies stream=False. In this case
                    # we catch the JSON decode error and fall back on parsing the message from the
                    # list of chunks received.
                    try:
                        message = await _parse_streaming_response_text(response.aiter_lines())
                        if not message:
                            raise json_decode_error
                        else:
                            return {"choices": [{"message": {"content": message}}]}
                    except Exception as streaming_parsing_exception:
                        raise streaming_parsing_exception from json_decode_error
            # read response to avoid errors when reading response.text
            raw_response = await response.aread()
            response_error = raw_response.decode()
            if response.status_code in retry_strategy.recoverable_statuses:
                retry_after = response.headers.get("retry-after")
                if retry_after:
                    try:
                        wait = float(retry_after)
                    except ValueError:
                        wait = retry_strategy.min_wait * (retry_strategy.backoff_factor**tries)
                else:
                    wait = min(
                        retry_strategy.min_wait * (retry_strategy.backoff_factor**tries),
                        retry_strategy.max_wait,
                    )
                logger.warning(
                    f"API request failed with status %s: %s. Retrying in %s seconds.",
                    response.status_code,
                    response_error,
                    wait,
                )
                time.sleep(wait)
            else:
                raise Exception(
                    f"API request failed with status code {response.status_code}: {response_error} ({response})",
                )
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError) as exc:
            last_exc = exc
            wait = min(
                retry_strategy.min_wait * (retry_strategy.backoff_factor**tries),
                retry_strategy.max_wait,
            )
            logger.warning(
                f"Request exception ({type(exc).__name__}): {exc}. Retrying in {wait} seconds."
            )
            time.sleep(wait)
        tries += 1
    if last_exc is not None:
        raise Exception(
            f"API request failed after retries due to network error: {type(last_exc).__name__}: {last_exc}"
        ) from last_exc
    raise Exception("API request failed after maximum retries.")


async def request_streaming_post_with_retries(
    request_params: Dict[str, Any],
    retry_strategy: _RetryStrategy,
    proxy: Optional[str] = None,
) -> AsyncIterable[str]:
    tries = 0
    last_exc = None

    while tries <= retry_strategy.max_retries:
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=retry_strategy.timeout) as session:
                async with session.stream("POST", **request_params) as response:
                    if response.status_code == 200:
                        async for chunk in response.aiter_lines():
                            yield chunk
                        return
                    # read streaming response to get the error message properly
                    raw_response = await response.aread()
                    response_content = raw_response.decode()
                if response.status_code in retry_strategy.recoverable_statuses:
                    retry_after = response.headers.get("retry-after")
                    if retry_after:
                        try:
                            wait = float(retry_after)
                        except ValueError:
                            wait = retry_strategy.min_wait * (retry_strategy.backoff_factor**tries)
                    else:
                        wait = min(
                            retry_strategy.min_wait * (retry_strategy.backoff_factor**tries),
                            retry_strategy.max_wait,
                        )
                    logger.warning(
                        f"API streaming request failed with status %s: %s. Retrying in %s seconds.",
                        response.status_code,
                        response_content,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    raise Exception(
                        f"API streaming request failed with status code {response.status_code}: {response_content} {response}"
                    )
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError) as exc:
            last_exc = exc
            wait = min(
                retry_strategy.min_wait * (retry_strategy.backoff_factor**tries),
                retry_strategy.max_wait,
            )
            logger.warning(
                f"Streaming request exception ({type(exc).__name__}): {exc}. Retrying in {wait} seconds."
            )
            time.sleep(wait)
        tries += 1

    if last_exc is not None:
        raise Exception(
            f"API streaming request failed after retries due to network error: {type(last_exc).__name__}: {last_exc}"
        ) from last_exc
    raise Exception("API streaming request failed after maximum retries.")


class StreamChunkType(Enum):
    IGNORED = 0  # doc: Won't be taken into account
    TEXT_CHUNK = 1  # doc: Expect a str and will append it to the previous message
    END_CHUNK = 2  # doc: Expect a message, will replace the previous message with this one
    START_CHUNK = 3  # doc: Expect a message and append it to the messages list


TaggedMessageChunkType = Tuple[StreamChunkType, Optional["Message"]]
TaggedMessageChunkTypeWithTokenUsage = Tuple[
    StreamChunkType, Optional["Message"], Optional[TokenUsage]
]


S = TypeVar("S")
R = TypeVar("R")


async def map_iterator(iterator: AsyncIterable[S], map_func: Callable[[S], R]) -> AsyncIterable[R]:
    async for elem in iterator:
        yield map_func(elem)
