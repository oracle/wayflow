# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import os
import time
from contextlib import contextmanager, nullcontext
from json import JSONDecodeError
from typing import Any, Dict
from unittest import mock
from unittest.mock import Mock, patch

import httpx
import pytest

from wayflowcore import Message, Tool
from wayflowcore.models import LlmCompletion, OpenAICompatibleModel, Prompt
from wayflowcore.models._requesthelpers import _RetryStrategy
from wayflowcore.property import StringProperty
from wayflowcore.tools import ToolRequest

from ..conftest import llama_api_url


class FakeResponse:
    def __init__(self, status_code: int = 200, content: str = ""):
        self.status_code = status_code
        self.content = content

    def json(self):
        return {"choices": [{"message": {"content": "something"}}]}

    @property
    def text(self) -> str:
        return self.content

    def read(self) -> bytes:
        return self.text.encode()

    async def aread(self) -> bytes:
        return self.text.encode()

    @property
    def headers(self) -> Dict[str, Any]:
        return {}

    def __await__(self):
        yield self

    def iter_lines(self):
        yield ""

    async def aiter_lines(self):
        yield ""


def _get_fake_request_that_succeeds_after_x_trials(x: int, status_code: int = 429):
    counter = 0

    async def fake_post(*args, **kwargs):
        nonlocal counter
        if counter < x:
            counter += 1
            return FakeResponse(status_code=status_code)
        else:
            return FakeResponse(status_code=200)

    return fake_post


def _get_fake_streaming_request_that_succeeds_after_x_trials(x: int, status_code: int = 429):
    counter = 0

    class FakePost:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            nonlocal counter
            if counter < x:
                counter += 1
                return FakeResponse(status_code=status_code)
            else:
                return FakeResponse(status_code=200)

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    return FakePost


@pytest.mark.parametrize(
    "retry_strategy, status_code",
    [
        (_RetryStrategy(), 400),
        (_RetryStrategy(recoverable_statuses=(400,)), 429),
    ],
)
def test_model_cannot_recover_from_non_recoverable_error(
    remotely_hosted_llm, retry_strategy, status_code
):
    async def _generate(*args, **kwargs):
        return FakeResponse(status_code, "error")

    remotely_hosted_llm._retry_strategy = retry_strategy
    with pytest.raises(Exception, match="API request failed with status code"):
        with patch(
            "httpx.AsyncClient.post",
            side_effect=_generate,
        ):
            remotely_hosted_llm.generate("Hello")


@pytest.mark.parametrize(
    "retry_strategy,expected_number_calls,expected_min_time",
    [
        (_RetryStrategy(), 3, 0.5 + 1 + 2),
        (_RetryStrategy(max_retries=10, min_wait=0.1, max_wait=0.1), 6, 0.5),
        (_RetryStrategy(max_retries=5, min_wait=0.1, max_wait=10, backoff_factor=1), 6, 0.5),
        (_RetryStrategy(max_retries=3, min_wait=0.05, max_wait=0.2, backoff_factor=10), 4, 0.6),
    ],
)
def test_model_can_recover_from_status(
    retry_strategy, expected_number_calls, expected_min_time, remotely_hosted_llm
):
    remotely_hosted_llm._retry_strategy = retry_strategy

    succeeds_after_x_failures = 5

    with patch(
        "httpx.AsyncClient.post",
        side_effect=_get_fake_request_that_succeeds_after_x_trials(succeeds_after_x_failures),
    ) as mock:
        start = time.time()
        with (
            pytest.raises(Exception, match="API request failed after maximum retries")
            if retry_strategy.max_retries < succeeds_after_x_failures
            else nullcontext()
        ):
            remotely_hosted_llm.generate("Hello")
        duration = time.time() - start
        assert mock.call_count == expected_number_calls
        assert duration > expected_min_time


def test_model_network_error_retries_and_fails(remotely_hosted_llm):
    retry_strategy = _RetryStrategy(max_retries=2, min_wait=0.01, max_wait=0.01)
    remotely_hosted_llm._retry_strategy = retry_strategy
    import httpx

    with patch(
        "httpx.AsyncClient.post", side_effect=httpx.ConnectError("Fake connection error")
    ) as mock:
        with pytest.raises(
            Exception, match="API request failed after retries due to network error"
        ):
            remotely_hosted_llm.generate("Hello")
        assert mock.call_count == retry_strategy.max_retries + 1


def test_model_json_decode_error_propagates(remotely_hosted_llm):
    remotely_hosted_llm._retry_strategy = _RetryStrategy()

    class FakeResponse:
        status_code = 200

        def json(self):
            raise ValueError("No JSON")

    async def _generate(*args, **kwargs):
        return FakeResponse()

    with patch("httpx.AsyncClient.post", side_effect=_generate):
        with pytest.raises(ValueError, match="No JSON"):
            remotely_hosted_llm.generate("Hello")


def test_model_streaming_network_error_retries_and_fails(remotely_hosted_llm):
    retry_strategy = _RetryStrategy(max_retries=2, min_wait=0.01, max_wait=0.01)
    remotely_hosted_llm._retry_strategy = retry_strategy

    def always_fail(*args, **kwargs):
        raise httpx.ConnectError("fake streaming connection error", request=None)

    with patch("httpx.AsyncClient.stream", side_effect=always_fail) as mock_post:
        with pytest.raises(
            Exception, match="API streaming request failed after retries due to network error"
        ):
            iterator = remotely_hosted_llm.stream_generate("hello")
            for x in iterator:
                pass
        assert mock_post.call_count == retry_strategy.max_retries + 1


def test_model_streaming_cannot_recover_from_nonrecoverable_status(remotely_hosted_llm):
    fake_post = _get_fake_streaming_request_that_succeeds_after_x_trials(100, 400)
    with patch("httpx.AsyncClient.stream", new=Mock(side_effect=fake_post)):
        with pytest.raises(Exception, match="API streaming request failed with status code"):
            iterator = remotely_hosted_llm.stream_generate("hello")
            for x in iterator:
                pass


def test_model_streaming_can_try_again_from_recoverable_status(remotely_hosted_llm):
    fake_post = _get_fake_streaming_request_that_succeeds_after_x_trials(10)
    with patch("httpx.AsyncClient.stream", new=Mock(side_effect=fake_post)):
        with pytest.raises(Exception, match="API streaming request failed after maximum retries"):
            iterator = remotely_hosted_llm.stream_generate("hello")
            for x in iterator:
                pass


def test_model_streaming_can_recover_from_recoverable_status(remotely_hosted_llm):
    fake_post = _get_fake_streaming_request_that_succeeds_after_x_trials(2)
    with patch("httpx.AsyncClient.stream", new=fake_post):
        iterator = remotely_hosted_llm.stream_generate("hello")
        for x in iterator:
            pass


def test_model_without_tool_support_raises_when_prompted_with_tools():
    prompt = Prompt(
        messages=[Message(role="user", content="hello")],
        tools=[
            Tool(name="some_tool", description="", input_descriptors=[StringProperty(name="arg1")])
        ],
    )
    llm = OpenAICompatibleModel(
        model_id="some_model_without_tool_support", base_url="some/url", supports_tool_calling=False
    )
    with pytest.raises(ValueError, match="doesn't support tool calling"):
        llm.generate(prompt)


def test_model_without_structured_generation_support_raises_when_prompted_with_tools():
    prompt = Prompt(
        messages=[Message(role="user", content="hello")],
        response_format=StringProperty(name="arg1"),
    )
    llm = OpenAICompatibleModel(
        model_id="some_model_without_tool_support",
        base_url="some/url",
        supports_structured_generation=False,
    )
    with pytest.raises(ValueError, match="doesn't support structured generation"):
        llm.generate(prompt)


@contextmanager
def _patch_generate_impl(message):
    async def _generate_impl(*args, **kwargs):
        return LlmCompletion(message=message, token_usage=None)

    with patch(
        "wayflowcore.models.openaicompatiblemodel.OpenAICompatibleModel._generate_impl",
        side_effect=_generate_impl,
    ):
        yield


def test_model_can_auto_detect_tool_and_structured_generation_support():
    with _patch_generate_impl(
        message=Message(role="assistant", tool_requests=[ToolRequest(name="get_weather", args={})])
    ):
        llm = OpenAICompatibleModel(
            model_id="some_model_without_tool_support",
            base_url="some/url",
            supports_tool_calling=None,
            supports_structured_generation=False,
        )
        assert llm.supports_tool_calling is True
        assert llm.supports_structured_generation is False

    with _patch_generate_impl(message=Message(role="assistant", content="get_weather")):
        llm = OpenAICompatibleModel(
            model_id="some_model_without_tool_support",
            base_url="some/url",
            supports_tool_calling=None,
            supports_structured_generation=False,
        )
        assert llm.supports_structured_generation is False
        assert llm.supports_tool_calling is False

    with _patch_generate_impl(message=Message(role="assistant", content='{"year": 2025}')):
        llm = OpenAICompatibleModel(
            model_id="some_model_with_tool_support",
            base_url="some/url",
            supports_tool_calling=True,
            supports_structured_generation=None,
        )
        assert llm.supports_structured_generation is True
        assert llm.supports_tool_calling is True

    with _patch_generate_impl(message=Message(role="assistant", content="it is 2025")):
        llm = OpenAICompatibleModel(
            model_id="some_model_without_tool_support",
            base_url="some/url",
            supports_tool_calling=True,
            supports_structured_generation=None,
        )
        assert llm.supports_structured_generation is False
        assert llm.supports_tool_calling is True


def test_open_ai_compatible_model_works_with_full_endpoint_url():
    llm = OpenAICompatibleModel(
        model_id="meta-llama/Meta-Llama-3.1-8B-Instruct",
        base_url=f"{llama_api_url}/v1/chat/completions",
    )
    llm_completion = llm.generate("What is life?")
    assert len(llm_completion.message.content) > 1


class ForcedStreamingResponse:
    def __init__(self, status_code: int = 200, content: str = ""):
        self.status_code = status_code

    def json(self):
        raise JSONDecodeError("Expecting value:", "line 1 column 1 (char 0)", 0)

    async def aiter_lines(self) -> str:
        for chunk in [
            'data: {"id": "abcde", "object": "chat.completion.chunk","created": 1756815855, "model": "xyz", "choices": [{"index": 0, "delta": {"content": "That"}}]}\n',
            'data: {"id": "abcde", "object": "chat.completion.chunk","created": 1756815855, "model": "xyz", "choices": [{"index": 0, "delta": {"content": "\'s"}}]}\n',
            'data: {"id": "abcde", "object": "chat.completion.chunk","created": 1756815855, "model": "xyz", "choices": [{"index": 0, "delta": {"content": " a"}}]}\n',
            'data: {"id": "abcde", "object": "chat.completion.chunk","created": 1756815855, "model": "xyz", "choices": [{"index": 0, "delta": {"content": " wonderfully"}}]}\n',
            'data: {"id": "abcde", "object": "chat.completion.chunk","created": 1756815855, "model": "xyz", "choices": [{"index": 0, "delta": {"content": " deep"}}]}\n',
            'data: {"id": "abcde", "object": "chat.completion.chunk","created": 1756815855, "model": "xyz", "choices": [{"index": 0, "delta": {"content": " question."}}]}\n',
            "data: [DONE]\n",
        ]:
            yield chunk


@patch("httpx.AsyncClient.post", return_value=ForcedStreamingResponse())
def test_non_streaming_works_when_backend_forces_streaming_response(mocked_httpx_post):
    llm = OpenAICompatibleModel(
        model_id="meta-llama/Meta-Llama-3.1-8B-Instruct",
        base_url=f"{llama_api_url}/v1/chat/completions",
    )
    llm_completion = llm.generate("What is life?")
    assert llm_completion.message.content == "That's a wonderfully deep question."


# this prompt will crash because it starts with an assistant message
ERRONEOUS_GEMMA_PROMPT = Prompt(messages=[Message(role="assistant", content="hi")])


def test_model_returns_error(remote_gemma_llm):
    with pytest.raises(Exception, match="API request failed with status code 400"):
        remote_gemma_llm.generate(prompt=ERRONEOUS_GEMMA_PROMPT)


def test_model_returns_error_streaming(remote_gemma_llm):
    with pytest.raises(Exception, match="API streaming request failed with status code 400"):
        for chunk in remote_gemma_llm.stream_generate(prompt=ERRONEOUS_GEMMA_PROMPT):
            pass


@pytest.mark.parametrize(
    "base_url, expected",
    [
        ("https://www.example.com/v1/", "https://www.example.com/v1/chat/completions"),
        (
            "https://www.example.com/v1/chat/completions",
            "https://www.example.com/v1/chat/completions",
        ),
        ("http://www.example.com", "http://www.example.com/v1/chat/completions"),
        ("www.example.com/v1", "http://www.example.com/v1/chat/completions"),
        ("127.0.0.1:8080", "http://127.0.0.1:8080/v1/chat/completions"),
    ],
    ids=["https", "https-full", "http", "no-scheme/v1", "localhost"],
)
def test_model_calls_correct_url(base_url, expected):
    prompt = Prompt(messages=[Message(role="user", content="hello")])
    payload = OpenAICompatibleModel(
        model_id="my.model-id", base_url=base_url
    )._generate_request_params(prompt)
    assert payload["url"] == expected
    if os.environ.get("OPENAI_API_KEY") is None:
        assert payload.get("headers", {}).get("Authorization") is None  # no api_key was specified


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-012-MOCKED_KEY"})
def test_model_has_correct_api_key():
    prompt = Prompt(messages=[Message(role="user", content="hello")])
    payload = OpenAICompatibleModel(
        model_id="my.model-id", base_url="my_awesome_llm"
    )._generate_request_params(prompt)
    assert payload.get("headers", {}).get("Authorization") == "Bearer sk-012-MOCKED_KEY"
