# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import logging
import ssl
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from enum import Enum
from random import Random, SystemRandom
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    AsyncIterable,
    Awaitable,
    Callable,
    Dict,
    Generator,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
)

import anyio
import httpx

from wayflowcore.retrypolicy import RetryJitter, RetryPolicy

if TYPE_CHECKING:
    from wayflowcore.messagelist import Message

from wayflowcore.tokenusage import TokenUsage

logger = logging.getLogger(__name__)

VerifyType = Union[bool, str, ssl.SSLContext]


DEFAULT_REQUEST_TIMEOUT: httpx.Timeout = httpx.Timeout(timeout=600, connect=20.0)
"""Default request timeout for remote calls."""

DEFAULT_TOTAL_ELAPSED_TIME_SECONDS = 600.0
"""Default retry budget across all attempts for helper-level retry loops."""

MAX_RETRY_AFTER_SECONDS = 30.0
"""Maximum server-provided ``Retry-After`` value honored by the retry helpers."""


# Bandit B311: `random.Random()` isn't cryptographically secure. We only use
# this RNG for retry jitter (not security-sensitive), but prefer `SystemRandom`
# to avoid false positives and to be conservative.
_DEFAULT_RNG = SystemRandom()
"""Random generator used for retry jitter calculations."""


def _compute_wait_seconds(
    policy: RetryPolicy,
    attempt_num: int,
    status_code: Optional[int],
    rng: Random,
) -> float:
    base = min(
        float(policy.initial_retry_delay) * (float(policy.backoff_factor) ** attempt_num),
        float(policy.max_retry_delay),
    )
    jitter = policy.jitter

    if jitter is None:
        return base
    elif jitter == RetryJitter.EQUAL:
        return base / 2.0 + rng.random() * (base / 2.0)
    elif jitter == RetryJitter.FULL:
        return rng.random() * base
    elif (
        jitter == RetryJitter.FULL_AND_EQUAL_FOR_THROTTLE
        and status_code is not None
        and 400 <= status_code < 500
    ):
        # Design doc: equal jitter for 4xx throttling-style responses.
        return base / 2.0 + rng.random() * (base / 2.0)
    elif jitter == RetryJitter.FULL_AND_EQUAL_FOR_THROTTLE:
        # Design doc: full jitter for the remaining retryable responses.
        return rng.random() * base
    elif jitter == RetryJitter.DECORRELATED:
        return min(base + rng.random(), float(policy.max_retry_delay))
    return base


def _is_retryable_http_error(
    policy: RetryPolicy,
    status_code: int,
    response_error_text: str,
) -> bool:
    if status_code in {400, 401, 403, 422}:
        return False
    if status_code == 501:
        return False

    retry_codes = policy.recoverable_statuses.get(str(status_code))
    if retry_codes is not None:
        if not retry_codes:
            return True
        lowered = response_error_text.lower()
        return any(code.lower() in lowered for code in retry_codes)

    if policy.service_error_retry_on_any_5xx and 500 <= status_code < 600:
        return True
    return False


def _cap_retry_after_seconds(wait: float) -> float:
    # Security: cap server-provided retry-after to a reasonable value.
    return min(wait, MAX_RETRY_AFTER_SECONDS)


def _get_retry_after_seconds(
    retry_after_value: Optional[str],
    *,
    now: Optional[datetime] = None,
) -> Optional[float]:
    if retry_after_value is None:
        return None
    try:
        return _cap_retry_after_seconds(float(retry_after_value))
    except ValueError:
        pass

    try:
        retry_after_datetime = parsedate_to_datetime(retry_after_value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None

    if retry_after_datetime.tzinfo is None:
        retry_after_datetime = retry_after_datetime.replace(tzinfo=timezone.utc)

    current_datetime = now or datetime.now(timezone.utc)
    return _cap_retry_after_seconds(
        max(0.0, (retry_after_datetime - current_datetime).total_seconds())
    )


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


def _resolve_timeout(
    timeout: Union[float, httpx.Timeout],
    retry_policy: Optional[RetryPolicy],
) -> Union[float, httpx.Timeout]:
    if retry_policy is None:
        return timeout
    return cast(Union[float, httpx.Timeout], retry_policy.request_timeout)


def _compute_wait_before_next_attempt(
    *,
    policy: RetryPolicy,
    attempt_num: int,
    status_code: Optional[int],
    retry_after_value: Optional[str],
    previous_wait_seconds: Optional[float],
    time_started: float,
    elapsed_time_seconds_fn: Callable[[], float],
    total_elapsed_time_seconds: Optional[float],
    rng: Random,
) -> Optional[float]:
    wait_time_seconds = _get_retry_after_seconds(retry_after_value)
    if wait_time_seconds is None:
        wait_time_seconds = _compute_wait_seconds(
            policy,
            attempt_num=attempt_num,
            status_code=status_code,
            rng=rng,
        )

    if total_elapsed_time_seconds is None:
        return wait_time_seconds

    remaining = total_elapsed_time_seconds - (elapsed_time_seconds_fn() - time_started)
    if remaining <= 0:
        return None
    return min(wait_time_seconds, remaining)


def _stringify_response_error(response_error: Any) -> str:
    if isinstance(response_error, str):
        return response_error
    try:
        return json.dumps(response_error)
    except TypeError:
        return str(response_error)


RetryClassification = Optional[Tuple[Optional[int], Optional[str]]]
"""Retry metadata returned by exception classifiers as ``(status_code, retry_after)``."""

RetryResultT = TypeVar("RetryResultT")
"""Generic result type returned by retry wrappers."""

ExceptionRetryClassifier = Callable[[Exception, RetryPolicy], RetryClassification]
"""Callable that maps an exception to retry metadata or ``None`` when it is non-retryable."""


def _get_retry_after_value_from_headers(headers: Optional[Mapping[str, Any]]) -> Optional[str]:
    if headers is None:
        return None
    retry_after = headers.get("retry-after")
    if retry_after is None:
        return None
    return str(retry_after)


def _classify_oci_service_error_for_retry(
    exc: Any,
    policy: RetryPolicy,
    *,
    retry_without_status: bool = False,
) -> RetryClassification:
    """Classify OCI service errors into retry metadata."""
    try:
        status_code = int(exc.status)
    except (TypeError, ValueError):
        status_code = 0

    if not status_code:
        return (None, None) if retry_without_status else None
    if not _is_retryable_http_error(policy, status_code, exc.message):
        return None
    return status_code, _get_retry_after_value_from_headers(exc.headers)


def execute_sync_with_retry(
    operation: Callable[[], RetryResultT],
    *,
    retry_policy: Optional[RetryPolicy],
    classify_exception: ExceptionRetryClassifier,
    total_elapsed_time_seconds: Optional[float] = DEFAULT_TOTAL_ELAPSED_TIME_SECONDS,
    retry_budget_exhausted_message: str = "Request retry budget exhausted",
    sleep_fn: Callable[[float], None] = time.sleep,
    elapsed_time_seconds_fn: Callable[[], float] = time.monotonic,
    rng: Random = _DEFAULT_RNG,
) -> RetryResultT:
    """Run a synchronous operation with retry-policy-based retries."""
    policy = retry_policy if retry_policy is not None else RetryPolicy()
    previous_wait_time_seconds: Optional[float] = None
    time_started = elapsed_time_seconds_fn()

    for attempt_num in range(policy.total_attempts):
        try:
            return operation()
        except Exception as exc:
            retry_classification = classify_exception(exc, policy)
            if retry_classification is None or attempt_num >= policy.total_attempts - 1:
                raise

            status_code, retry_after_value = retry_classification
            wait_time_seconds = _compute_wait_before_next_attempt(
                policy=policy,
                attempt_num=attempt_num,
                status_code=status_code,
                retry_after_value=retry_after_value,
                previous_wait_seconds=previous_wait_time_seconds,
                time_started=time_started,
                elapsed_time_seconds_fn=elapsed_time_seconds_fn,
                total_elapsed_time_seconds=total_elapsed_time_seconds,
                rng=rng,
            )
            if wait_time_seconds is None:
                raise RuntimeError(retry_budget_exhausted_message) from exc
            previous_wait_time_seconds = wait_time_seconds
            sleep_fn(wait_time_seconds)

    raise RuntimeError("Retry attempts were exhausted unexpectedly.")


async def execute_async_with_retry(
    operation: Callable[[], Awaitable[RetryResultT]],
    retry_policy: Optional[RetryPolicy],
    classify_exception: ExceptionRetryClassifier,
    total_elapsed_time_seconds: Optional[float] = DEFAULT_TOTAL_ELAPSED_TIME_SECONDS,
    retry_budget_exhausted_message: str = "Request retry budget exhausted",
    sleep_fn: Callable[[float], Awaitable[Any]] = anyio.sleep,
    elapsed_time_seconds_fn: Callable[[], float] = anyio.current_time,
    rng: Random = _DEFAULT_RNG,
) -> RetryResultT:
    """Run an asynchronous operation with retry-policy-based retries.

    Parameters
    ----------
    operation:
        Operation to execute.
    retry_policy:
        Retry configuration to apply. When ``None``, the default retry policy is used.
    classify_exception:
        Callback that determines whether an exception is retryable and returns retry metadata.
    total_elapsed_time_seconds:
        Maximum total retry budget across all attempts. ``None`` disables this budget.
        Defaults to ``DEFAULT_TOTAL_ELAPSED_TIME_SECONDS``.
    retry_budget_exhausted_message:
        Error message used when the elapsed-time retry budget is exhausted.
        Defaults to ``"Request retry budget exhausted"``.
    sleep_fn:
        Async sleep function used between attempts. Defaults to ``anyio.sleep``.
    elapsed_time_seconds_fn:
        Clock function used to track elapsed retry time.
        Defaults to ``anyio.current_time``.
    rng:
        Random generator used for jitter calculations.
        Defaults to ``_DEFAULT_RNG``.

    Returns
    -------
    RetryResultT
        Result returned by ``operation``.

    Raises
    ------
    Exception
        Re-raises the last non-retryable exception from ``operation``.
    RuntimeError
        Raised when the configured retry budget is exhausted.
    """
    policy = retry_policy if retry_policy is not None else RetryPolicy()
    previous_wait_time_seconds: Optional[float] = None
    time_started = elapsed_time_seconds_fn()

    for attempt_num in range(policy.total_attempts):
        try:
            return await operation()
        except Exception as exc:
            retry_classification = classify_exception(exc, policy)
            if retry_classification is None or attempt_num >= policy.total_attempts - 1:
                raise

            status_code, retry_after_value = retry_classification
            wait_time_seconds = _compute_wait_before_next_attempt(
                policy=policy,
                attempt_num=attempt_num,
                status_code=status_code,
                retry_after_value=retry_after_value,
                previous_wait_seconds=previous_wait_time_seconds,
                time_started=time_started,
                elapsed_time_seconds_fn=elapsed_time_seconds_fn,
                total_elapsed_time_seconds=total_elapsed_time_seconds,
                rng=rng,
            )
            if wait_time_seconds is None:
                raise RuntimeError(retry_budget_exhausted_message) from exc
            previous_wait_time_seconds = wait_time_seconds
            await sleep_fn(wait_time_seconds)

    raise RuntimeError("Retry attempts were exhausted unexpectedly.")


class RetryingAsyncClient(httpx.AsyncClient):
    """HTTPX async client that applies ``RetryPolicy`` to transport and HTTP failures."""

    def __init__(
        self,
        *args: Any,
        retry_policy: Optional[RetryPolicy] = None,
        total_elapsed_time_seconds: Optional[float] = DEFAULT_TOTAL_ELAPSED_TIME_SECONDS,
        **kwargs: Any,
    ) -> None:
        """Initialize the client with optional retry configuration."""
        self._retry_policy = retry_policy
        self._total_elapsed_time_seconds = total_elapsed_time_seconds
        super().__init__(*args, **kwargs)

    async def send(
        self,
        request: httpx.Request,
        *,
        stream: bool = False,
        auth: Any = httpx.USE_CLIENT_DEFAULT,
        follow_redirects: Any = httpx.USE_CLIENT_DEFAULT,
    ) -> httpx.Response:
        """Send a request and retry retryable transport or HTTP failures."""
        if self._retry_policy is None:
            return await super().send(
                request,
                stream=stream,
                auth=auth,
                follow_redirects=follow_redirects,
            )

        policy = self._retry_policy if self._retry_policy is not None else RetryPolicy()
        previous_wait_time_seconds: Optional[float] = None
        last_exc: Optional[BaseException] = None
        time_started = anyio.current_time()

        for request_attempt_num in range(policy.total_attempts):
            try:
                response = await super().send(
                    request,
                    stream=stream,
                    auth=auth,
                    follow_redirects=follow_redirects,
                )
            except httpx.TransportError as exc:
                if _is_tls_or_cert_error(exc) or request_attempt_num >= policy.total_attempts - 1:
                    raise

                last_exc = exc
                wait_time_seconds = _compute_wait_before_next_attempt(
                    policy=policy,
                    attempt_num=request_attempt_num,
                    status_code=None,
                    retry_after_value=None,
                    previous_wait_seconds=previous_wait_time_seconds,
                    time_started=time_started,
                    elapsed_time_seconds_fn=anyio.current_time,
                    total_elapsed_time_seconds=self._total_elapsed_time_seconds,
                    rng=_DEFAULT_RNG,
                )
                if wait_time_seconds is None:
                    raise
                previous_wait_time_seconds = wait_time_seconds
                await anyio.sleep(wait_time_seconds)
                continue

            if response.is_success:
                return response

            response_error_text = _stringify_response_error(await response.aread())
            if request_attempt_num >= policy.total_attempts - 1 or not _is_retryable_http_error(
                policy, response.status_code, response_error_text
            ):
                return response

            wait_time_seconds = _compute_wait_before_next_attempt(
                policy=policy,
                attempt_num=request_attempt_num,
                status_code=response.status_code,
                retry_after_value=response.headers.get("retry-after"),
                previous_wait_seconds=previous_wait_time_seconds,
                time_started=time_started,
                elapsed_time_seconds_fn=anyio.current_time,
                total_elapsed_time_seconds=self._total_elapsed_time_seconds,
                rng=_DEFAULT_RNG,
            )
            if wait_time_seconds is None:
                return response
            previous_wait_time_seconds = wait_time_seconds
            await response.aclose()
            await anyio.sleep(wait_time_seconds)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Request failed after retry attempts were exhausted.")


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
    verify: VerifyType = True,
    retry_policy: Optional[RetryPolicy] = None,
    timeout: Union[float, httpx.Timeout] = DEFAULT_REQUEST_TIMEOUT,
    total_elapsed_time_seconds: Optional[float] = DEFAULT_TOTAL_ELAPSED_TIME_SECONDS,
) -> Dict[str, Any]:
    """Makes a POST request using requests.post with OpenAI-like retry behavior"""
    policy = retry_policy if retry_policy is not None else RetryPolicy()
    timeout = _resolve_timeout(timeout, retry_policy)

    last_exc: Optional[BaseException] = None
    previous_wait_time_seconds: Optional[float] = None
    time_started = anyio.current_time()
    for request_attempt_num in range(policy.total_attempts):
        try:
            # Ignore ambient proxy environment variables with `trust_env=False` to prevent injected
            # HTTPS proxy settings from hijack localhost TLS test traffic and cause the client to
            # validate the proxy certificate instead of the test server certificate.
            async with httpx.AsyncClient(
                proxy=proxy,
                timeout=timeout,
                # Preserve the caller's TLS verification mode or CA bundle configuration.
                verify=verify,
                trust_env=False,
            ) as session:
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
            error_is_retryable = _is_retryable_http_error(
                policy, response.status_code, response_error
            )

            if error_is_retryable:
                wait_time_seconds = _compute_wait_before_next_attempt(
                    policy=policy,
                    attempt_num=request_attempt_num,
                    status_code=response.status_code,
                    retry_after_value=response.headers.get("retry-after"),
                    previous_wait_seconds=previous_wait_time_seconds,
                    time_started=time_started,
                    elapsed_time_seconds_fn=anyio.current_time,
                    total_elapsed_time_seconds=total_elapsed_time_seconds,
                    rng=_DEFAULT_RNG,
                )
                if wait_time_seconds is None or request_attempt_num >= policy.total_attempts - 1:
                    break
                logger.warning(
                    f"API request failed with status %s: %s. Retrying in %s seconds.",
                    response.status_code,
                    response_error,
                    wait_time_seconds,
                )
                await anyio.sleep(wait_time_seconds)
                previous_wait_time_seconds = wait_time_seconds
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
            wait_time_seconds = _compute_wait_before_next_attempt(
                policy=policy,
                attempt_num=request_attempt_num,
                status_code=None,
                retry_after_value=None,
                previous_wait_seconds=previous_wait_time_seconds,
                time_started=time_started,
                elapsed_time_seconds_fn=anyio.current_time,
                total_elapsed_time_seconds=total_elapsed_time_seconds,
                rng=_DEFAULT_RNG,
            )
            if wait_time_seconds is None or request_attempt_num >= policy.total_attempts - 1:
                break
            logger.warning(
                f"Request exception ({type(exc).__name__}): {exc}. Retrying in {wait_time_seconds} seconds."
            )
            await anyio.sleep(wait_time_seconds)
            previous_wait_time_seconds = wait_time_seconds
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
    verify: VerifyType = True,
    retry_policy: Optional[RetryPolicy] = None,
    timeout: Union[float, httpx.Timeout] = DEFAULT_REQUEST_TIMEOUT,
    total_elapsed_time_seconds: Optional[float] = DEFAULT_TOTAL_ELAPSED_TIME_SECONDS,
) -> AsyncGenerator[str, None]:
    policy = retry_policy if retry_policy is not None else RetryPolicy()
    timeout = _resolve_timeout(timeout, retry_policy)

    last_exc: Optional[BaseException] = None
    previous_wait_time_seconds: Optional[float] = None

    time_started = anyio.current_time()

    with silence_generator_exit_warnings():
        for request_attempt_num in range(policy.total_attempts):
            try:
                # Match non-streaming behavior: only use the explicit `proxy` argument and do
                # not inherit proxy settings from the process environment.
                async with httpx.AsyncClient(
                    proxy=proxy,
                    timeout=timeout,
                    # Preserve the caller's TLS verification mode or CA bundle configuration.
                    verify=verify,
                    trust_env=False,
                ) as session:
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

                    error_is_retryable = _is_retryable_http_error(
                        policy, response.status_code, response_content
                    )

                    if error_is_retryable:
                        wait_time_seconds = _compute_wait_before_next_attempt(
                            policy=policy,
                            attempt_num=request_attempt_num,
                            status_code=response.status_code,
                            retry_after_value=response.headers.get("retry-after"),
                            previous_wait_seconds=previous_wait_time_seconds,
                            time_started=time_started,
                            elapsed_time_seconds_fn=anyio.current_time,
                            total_elapsed_time_seconds=total_elapsed_time_seconds,
                            rng=_DEFAULT_RNG,
                        )
                        if (
                            wait_time_seconds is None
                            or request_attempt_num >= policy.total_attempts - 1
                        ):
                            break
                        logger.warning(
                            f"API streaming request failed with status %s: %s. Retrying in %s seconds.",
                            response.status_code,
                            response_content,
                            wait_time_seconds,
                        )
                        await anyio.sleep(wait_time_seconds)
                        previous_wait_time_seconds = wait_time_seconds
                        continue
                    else:
                        raise Exception(
                            f"API streaming request failed with status code {response.status_code}: {response_content} {response}"
                        )
            except httpx.TransportError as exc:
                if _is_tls_or_cert_error(exc):
                    raise
                last_exc = exc
                wait_time_seconds = _compute_wait_before_next_attempt(
                    policy=policy,
                    attempt_num=request_attempt_num,
                    status_code=None,
                    retry_after_value=None,
                    previous_wait_seconds=previous_wait_time_seconds,
                    time_started=time_started,
                    elapsed_time_seconds_fn=anyio.current_time,
                    total_elapsed_time_seconds=total_elapsed_time_seconds,
                    rng=_DEFAULT_RNG,
                )
                if wait_time_seconds is None or request_attempt_num >= policy.total_attempts - 1:
                    break
                logger.warning(
                    f"Streaming request exception ({type(exc).__name__}): {exc}. Retrying in {wait_time_seconds} seconds."
                )
                await anyio.sleep(wait_time_seconds)
                previous_wait_time_seconds = wait_time_seconds
            except (GeneratorExit, anyio.get_cancelled_exc_class()):
                raise

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
