# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import logging
import ssl
import sys
from contextlib import contextmanager
from enum import Enum
from random import Random, SystemRandom
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    AsyncIterable,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
)

import anyio
import httpx

from wayflowcore.retrypolicy import RetryPolicy

if TYPE_CHECKING:
    from wayflowcore.messagelist import Message

from wayflowcore.tokenusage import TokenUsage

logger = logging.getLogger(__name__)


DEFAULT_REQUEST_TIMEOUT: httpx.Timeout = httpx.Timeout(timeout=600, connect=20.0)
"""Default request timeout for remote calls."""


# Bandit B311: `random.Random()` isn't cryptographically secure. We only use
# this RNG for retry jitter (not security-sensitive), but prefer `SystemRandom`
# to avoid false positives and to be conservative.
_DEFAULT_RNG = SystemRandom()


def _compute_base_wait_seconds(policy: RetryPolicy, attempt: int) -> float:
    return min(
        float(policy.initial_retry_delay) * (float(policy.backoff_factor) ** attempt),
        float(policy.max_retry_delay),
    )


def _compute_wait_seconds(
    policy: RetryPolicy,
    attempt: int,
    status_code: Optional[int],
    previous_wait_seconds: Optional[float],
    rng: Random,
) -> float:
    base = _compute_base_wait_seconds(policy, attempt)
    jitter = policy.jitter

    if jitter is None:
        return base
    if jitter == "equal":
        return base / 2.0 + rng.random() * (base / 2.0)
    if jitter == "full":
        return rng.random() * base
    if jitter == "full_and_equal_for_throttle":
        # Design doc: full for 5xx errors and equal for 4xx errors.
        if status_code is not None and 400 <= status_code < 500:
            return base / 2.0 + rng.random() * (base / 2.0)
        return rng.random() * base
    if jitter == "decorrelated":
        prev = (
            previous_wait_seconds
            if previous_wait_seconds is not None
            else float(policy.initial_retry_delay)
        )
        upper = min(float(policy.max_retry_delay), float(policy.backoff_factor) * prev)
        return float(policy.initial_retry_delay) + rng.random() * (
            upper - float(policy.initial_retry_delay)
        )
    return base


def _find_retry_codes(policy: RetryPolicy, status_code: int) -> Optional[List[str]]:
    codes = policy.recoverable_statuses.get(str(status_code))
    return codes if codes is not None else None


def _is_security_non_retryable_status(status_code: int) -> bool:
    return status_code in {400, 401, 403, 422}


def _is_retryable_http_error(
    policy: RetryPolicy,
    status_code: int,
    response_error_text: str,
) -> bool:
    if _is_security_non_retryable_status(status_code):
        return False
    if status_code == 501:
        return False

    codes = _find_retry_codes(policy, status_code)
    if codes is not None:
        if not codes:
            return True
        lowered = response_error_text.lower()
        return any(code.lower() in lowered for code in codes)

    if policy.service_error_retry_on_any_5xx and 500 <= status_code < 600:
        return True
    return False


def _cap_retry_after_seconds(wait: float) -> float:
    # Security: cap server-provided retry-after to a reasonable value.
    return min(wait, 30.0)


def _is_tls_or_cert_error(exc: BaseException) -> bool:
    current: Optional[BaseException] = exc
    while current is not None:
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        msg = str(current)
        if any(
            s in msg
            for s in [
                "CERTIFICATE_VERIFY_FAILED",
                "certificate verify failed",
                "hostname",
                "self signed certificate",
            ]
        ):
            return True
        current = current.__cause__
    return False


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
    proxy: Optional[str] = None,
    retry_policy: Optional[RetryPolicy] = None,
    timeout: Union[float, httpx.Timeout] = DEFAULT_REQUEST_TIMEOUT,
    total_elapsed_time_seconds: Optional[float] = 600,
) -> Dict[str, Any]:
    """Makes a POST request using requests.post with OpenAI-like retry behavior"""
    policy = retry_policy or RetryPolicy()
    if policy.request_timeout is not None:
        timeout = cast(Union[float, httpx.Timeout], policy.request_timeout)
    # Agent Spec semantics: `max_attempts` is the number of retries (not counting
    # the initial attempt).
    max_attempts = max(policy.max_attempts + 1, 1)

    tries = 0
    last_exc = None
    previous_wait: Optional[float] = None
    started = anyio.current_time()
    while tries < max_attempts:
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=timeout) as session:
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
            retryable = _is_retryable_http_error(policy, response.status_code, response_error)

            if retryable:
                retry_after = response.headers.get("retry-after")
                if retry_after:
                    try:
                        wait = _cap_retry_after_seconds(float(retry_after))
                    except ValueError:
                        wait = _compute_wait_seconds(
                            policy,
                            attempt=tries,
                            status_code=response.status_code,
                            previous_wait_seconds=previous_wait,
                            rng=_DEFAULT_RNG,
                        )
                else:
                    wait = _compute_wait_seconds(
                        policy,
                        attempt=tries,
                        status_code=response.status_code,
                        previous_wait_seconds=previous_wait,
                        rng=_DEFAULT_RNG,
                    )

                if total_elapsed_time_seconds is not None:
                    remaining = total_elapsed_time_seconds - (anyio.current_time() - started)
                    if remaining <= 0:
                        break
                    wait = min(wait, remaining)
                logger.warning(
                    f"API request failed with status %s: %s. Retrying in %s seconds.",
                    response.status_code,
                    response_error,
                    wait,
                )
                await anyio.sleep(wait)
                previous_wait = wait
                tries += 1
                continue
            else:
                raise Exception(
                    f"API request failed with status code {response.status_code}: {response_error} ({response})",
                )
        except httpx.TransportError as exc:
            # Security: do not retry TLS / certificate validation failures.
            if _is_tls_or_cert_error(exc):
                raise

            last_exc = exc
            wait = _compute_wait_seconds(
                policy,
                attempt=tries,
                status_code=None,
                previous_wait_seconds=previous_wait,
                rng=_DEFAULT_RNG,
            )

            if total_elapsed_time_seconds is not None:
                remaining = total_elapsed_time_seconds - (anyio.current_time() - started)
                if remaining <= 0:
                    break
                wait = min(wait, remaining)
            logger.warning(
                f"Request exception ({type(exc).__name__}): {exc}. Retrying in {wait} seconds."
            )
            await anyio.sleep(wait)
            previous_wait = wait
        tries += 1
    if last_exc is not None:
        raise Exception(
            f"API request failed after retries due to network error: {type(last_exc).__name__}: {last_exc}"
        ) from last_exc
    raise Exception("API request failed after maximum retries.")


# Suppress “async generator ignored GeneratorExit” from httpcore/httpx streams:
# This warning happens when an async HTTP stream is cancelled/cleaned up mid-yield
# (e.g., httpcore’s connection pool iterator during teardown) — the generator gets
# a GeneratorExit that it doesn’t cleanly propagate, resulting in Python printing
# “async generator ignored GeneratorExit”. See:
# https://github.com/Chainlit/chainlit/issues/2361
def _silence_generator_exit_noise(unraisable: Any) -> None:
    exc = unraisable.exc_value
    ignored_exceptions = [
        "Attempted to exit cancel scope in a different task than it was entered in",
        "async generator ignored GeneratorExit",
    ]
    if isinstance(exc, RuntimeError) and any(x in str(exc) for x in ignored_exceptions):
        return
    sys.__unraisablehook__(unraisable)


@contextmanager
def silence_generator_exit_warnings() -> Generator[None, None, None]:
    prev_unraisable_hook = sys.unraisablehook
    try:
        # ignore unraisable error coming from httpx to avoid polluting the logs
        sys.unraisablehook = _silence_generator_exit_noise
        yield
    finally:
        sys.unraisablehook = prev_unraisable_hook


async def request_streaming_post_with_retries(
    request_params: Dict[str, Any],
    proxy: Optional[str] = None,
    retry_policy: Optional[RetryPolicy] = None,
    timeout: Union[float, httpx.Timeout] = DEFAULT_REQUEST_TIMEOUT,
    total_elapsed_time_seconds: Optional[float] = 600,
) -> AsyncGenerator[str, None]:
    policy = retry_policy or RetryPolicy()
    if policy.request_timeout is not None:
        timeout = cast(Union[float, httpx.Timeout], policy.request_timeout)
    # Agent Spec semantics: `max_attempts` is the number of retries (not counting
    # the initial attempt).
    max_attempts = max(policy.max_attempts + 1, 1)

    tries = 0
    last_exc = None
    previous_wait: Optional[float] = None

    started = anyio.current_time()

    with silence_generator_exit_warnings():
        while tries < max_attempts:
            try:
                async with httpx.AsyncClient(proxy=proxy, timeout=timeout) as session:
                    async with session.stream("POST", **request_params) as response:
                        if response.status_code == 200:
                            async for chunk in response.aiter_lines():
                                yield chunk
                            return

                        # Read the error body while the stream is still open.
                        # If we attempt to read outside the context manager, httpx
                        # raises `StreamClosed`.
                        raw_response = await response.aread()
                        response_content = raw_response.decode()

                    retryable = _is_retryable_http_error(
                        policy, response.status_code, response_content
                    )

                    if retryable:
                        retry_after = response.headers.get("retry-after")
                        if retry_after:
                            try:
                                wait = _cap_retry_after_seconds(float(retry_after))
                            except ValueError:
                                wait = _compute_wait_seconds(
                                    policy,
                                    attempt=tries,
                                    status_code=response.status_code,
                                    previous_wait_seconds=previous_wait,
                                    rng=_DEFAULT_RNG,
                                )
                        else:
                            wait = _compute_wait_seconds(
                                policy,
                                attempt=tries,
                                status_code=response.status_code,
                                previous_wait_seconds=previous_wait,
                                rng=_DEFAULT_RNG,
                            )

                        if total_elapsed_time_seconds is not None:
                            remaining = total_elapsed_time_seconds - (
                                anyio.current_time() - started
                            )
                            if remaining <= 0:
                                break
                            wait = min(wait, remaining)
                        logger.warning(
                            f"API streaming request failed with status %s: %s. Retrying in %s seconds.",
                            response.status_code,
                            response_content,
                            wait,
                        )
                        await anyio.sleep(wait)
                        previous_wait = wait
                        tries += 1
                        continue
                    else:
                        raise Exception(
                            f"API streaming request failed with status code {response.status_code}: {response_content} {response}"
                        )
            except httpx.TransportError as exc:
                if _is_tls_or_cert_error(exc):
                    raise
                last_exc = exc
                wait = _compute_wait_seconds(
                    policy,
                    attempt=tries,
                    status_code=None,
                    previous_wait_seconds=previous_wait,
                    rng=_DEFAULT_RNG,
                )

                if total_elapsed_time_seconds is not None:
                    remaining = total_elapsed_time_seconds - (anyio.current_time() - started)
                    if remaining <= 0:
                        break
                    wait = min(wait, remaining)
                logger.warning(
                    f"Streaming request exception ({type(exc).__name__}): {exc}. Retrying in {wait} seconds."
                )
                await anyio.sleep(wait)
                previous_wait = wait
            except (GeneratorExit, anyio.get_cancelled_exc_class()):
                raise
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
