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
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from wayflowcore import Agent, Message, Tool
from wayflowcore.models import (
    LlmCompletion,
    OllamaModel,
    OpenAICompatibleModel,
    Prompt,
    StreamChunkType,
    VllmModel,
)
from wayflowcore.models import LlmCompletion, OpenAICompatibleModel, Prompt, StreamChunkType
from wayflowcore import Message, Tool
from wayflowcore.messagelist import MessageType
from wayflowcore.models import LlmCompletion, OpenAICompatibleModel, Prompt, StreamChunkType
from wayflowcore.models._requesthelpers import _RetryStrategy
from wayflowcore.models.llmmodel import LlmGenerationConfig
from wayflowcore.models.llmmodelfactory import LlmModelFactory
from wayflowcore.models.openaicompatiblemodel import OPEN_API_KEY
from wayflowcore.property import StringProperty
from wayflowcore.tools import ToolRequest
from wayflowcore.tools.tools import ToolResult

from ..conftest import (
    OPENAI_REASONING_RESPONSES_CONFIG,
    OPENAI_RESPONSES_CONFIG,
    VLLM_OSS_CONFIG,
    VLLM_OSS_REASONING_CONFIG,
    llama_api_url,
)
from ..testhelpers.testhelpers import retry_test
from .test_models import REQUIRES_REASONING_PROMPT


@pytest.fixture
def openai_responses_llm():
    if OPEN_API_KEY not in os.environ:
        pytest.skip("OPENAI API KEY not available in environment")
    return LlmModelFactory.from_config(OPENAI_RESPONSES_CONFIG)


@pytest.fixture
def vllm_responses_llm():
    return LlmModelFactory.from_config(VLLM_OSS_CONFIG)


@pytest.fixture
def openai_reasoning_responses_llm():
    if OPEN_API_KEY not in os.environ:
        pytest.skip("OPENAI API KEY not available in environment")
    return LlmModelFactory.from_config(OPENAI_REASONING_RESPONSES_CONFIG)


@pytest.fixture
def vllm_reasoning_responses_llm():
    return LlmModelFactory.from_config(VLLM_OSS_REASONING_CONFIG)


from ..conftest import llama_api_url
from ..testhelpers.dummy import create_dummy_server_tool


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
    )._generate_request_params(prompt, stream=False)
    assert payload["url"] == expected
    if os.environ.get("OPENAI_API_KEY") is None:
        assert payload.get("headers", {}).get("Authorization") is None  # no api_key was specified


@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-012-MOCKED_KEY"})
def test_model_has_correct_api_key():
    prompt = Prompt(messages=[Message(role="user", content="hello")])
    model = OpenAICompatibleModel(model_id="my.model-id", base_url="my_awesome_llm")
    payload = model._generate_request_params(prompt, stream=False)
    payload["headers"] = model._get_headers()
    assert payload.get("headers", {}).get("Authorization") == "Bearer sk-012-MOCKED_KEY"


@retry_test(max_attempts=3)
def test_responses_open_ai_compatible_model_works_with_multiple_inputs(openai_responses_llm):
    """
    Failure rate:          0 out of 10
    Observed on:           2025-11-25
    Average success time:  1.69 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    prompt = Prompt(
        messages=[
            Message("What is the capital of Switzerland?"),
            Message("What is the capital of France?"),
            Message("What is the capital of Germany?"),
        ]
    )
    llm_completion = openai_responses_llm.generate(prompt)
    assert len(llm_completion.message.content) > 1


@retry_test(max_attempts=3)
def test_open_ai_compatible_model_works_with_streaming_responses(openai_responses_llm):
    """
    Failure rate:          0 out of 10
    Observed on:           2025-11-25
    Average success time:  7.75 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    stream = openai_responses_llm.stream_generate("What is life?")
    res_content = ""
    final_res = None
    for chunk_type, chunk in stream:
        if chunk_type == StreamChunkType.TEXT_CHUNK:
            res_content += chunk.content
        elif chunk_type == StreamChunkType.END_CHUNK:
            final_res = chunk
        elif chunk_type == StreamChunkType.START_CHUNK:
            res_content += chunk.content
        else:
            pass

    assert (
        final_res.content in res_content
    ), "Final chunk didn't return same content as what was streamed."


@retry_test(max_attempts=3)
def test_open_ai_compatible_reasoning_model_gives_encrypted_content_responses(
    openai_reasoning_responses_llm,
):
    """
    Failure rate:          0 out of 10
    Observed on:           2025-11-25
    Average success time:  16.96 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    llm_completion = openai_reasoning_responses_llm.generate(
        "Puzzle: You are outside a closed room with three light switches. Only one of them controls a light inside the room."
        "You can flip the switches as much as you want, but you can only enter the room once to check. How do you know which switch controls the light?"
    )
    assert llm_completion.message._reasoning_content is not None
    assert "encrypted_content" in llm_completion.message._reasoning_content
    assert llm_completion.message._reasoning_content["encrypted_content"] is not None


@retry_test(max_attempts=3)
def test_vllm_reasoning_model_gives_reasoning_content_responses(
    vllm_reasoning_responses_llm,
):
    """
    Failure rate:          0 out of 10
    Observed on:           2025-11-25
    Average success time:  12.09 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    llm_completion = vllm_reasoning_responses_llm.generate(REQUIRES_REASONING_PROMPT)
    assert llm_completion.message._reasoning_content is not None
    assert "content" in llm_completion.message._reasoning_content
    assert llm_completion.message._reasoning_content["content"][0]["text"] is not None


@retry_test(max_attempts=3)
def test_vllm_responses_model_runs_with_agent(vllm_responses_llm):
    """
    Failure rate:          0 out of 10
    Observed on:           2025-11-25
    Average success time:  1.66 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    agent = Agent(llm=vllm_responses_llm)
    conv = agent.start_conversation()
    conv.append_user_message("Hi, how are you doing?")
    conv.execute()
    conv.append_user_message("I'm great.")
    conv.execute()
    all_messages = conv.get_messages()
    assert len(all_messages) == 4


@retry_test(max_attempts=3)
def test_open_ai_compatible_responses_model_runs_with_agent_with_prompt_cache_key(
    openai_responses_llm,
):
    """
    Failure rate:          0 out of 10
    Observed on:           2025-11-25
    Average success time:  3.15 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """

    agent = Agent(llm=openai_responses_llm)
    conv = agent.start_conversation()
    conv.append_user_message("Hi, how are you doing?")
    conv.execute()
    conv.append_user_message("I'm great.")
    conv.execute()
    all_messages = conv.get_messages()

    assert any([message._prompt_cache_key is not None for message in all_messages])


@retry_test(max_attempts=3)
def test_open_ai_compatible_responses_model_raises_with_less_tokens(openai_responses_llm):
    """
    Failure rate:          0 out of 10
    Observed on:           2025-11-25
    Average success time:  10.54 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    agent = Agent(llm=openai_responses_llm)
    conv = agent.start_conversation()

    with pytest.raises(
        ValueError, match="Streaming incomplete due to reason: {'reason': 'max_output_tokens'}"
    ):
        conv.append_user_message("How do birds survive in nature?")
        conv.execute()
        conv.append_user_message("Do you think this is a reasonable strategy? Give reasons")
        conv.execute()
        conv.append_user_message("That sounds great! Tell me more")
        conv.execute()


@pytest.mark.parametrize(
    "tool_call_args",
    [
        "{}",
        '{"arg1":"val1"}',
        '{"arg1":"val1}',  # broken JSON, can be repaired
        '{"arg1"val1"}',  # broken JSON, can be repaired
        "{",  # completely broken, will be ignored
    ],
)
def test_openai_model_does_not_raise_on_receiving_incomplete_tool_calls_from_remote(
    remotely_hosted_llm, tool_call_args
):
    mocked_response = {
        "id": "test-id",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "It is sunny in Zurich.",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "get_weather",
                                "arguments": tool_call_args,
                            },
                            "id": "id1",
                        }
                    ],
                }
            }
        ],
    }

    mock_httpx_response = httpx.Response(status_code=200, json=mocked_response)

    async_mock = AsyncMock(return_value=mock_httpx_response)

    with patch("httpx.AsyncClient.post", async_mock):
        completion = remotely_hosted_llm.generate("what is the weather in Zurich?")
        tool_call = completion.message.tool_requests[0]

        assert tool_call.name == "get_weather"

        if "arg1" in tool_call_args:
            assert tool_call.args.get("arg1") is not None


@pytest.mark.parametrize("model_cls", [VllmModel, OllamaModel])
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
def test_vllm_ollama_with_correct_url(model_cls, base_url, expected):
    prompt = Prompt(messages=[Message(role="user", content="hello")])
    payload = model_cls(model_id="my.model-id", host_port=base_url)._generate_request_params(
        prompt, stream=False
    )
    assert payload["url"] == expected
    if os.environ.get("OPENAI_API_KEY") is None:
        assert payload.get("headers", {}).get("Authorization") is None  # no api_key was specified


@pytest.mark.parametrize("model_cls", [VllmModel, OllamaModel])
@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-034-MOCKED_KEY"})
def test_vllm_ollama_with_api_key(model_cls):
    prompt = Prompt(messages=[Message(role="user", content="hello")])
    model = model_cls(model_id="my.model-id", host_port="localhost:80000")
    payload = model._generate_request_params(prompt, stream=False)
    payload["headers"] = model._get_headers()
    assert payload.get("headers", {}).get("Authorization") == "Bearer sk-034-MOCKED_KEY"

@pytest.fixture
def thought_signature_llm():
    if "GEMINI_API_KEY" not in os.environ:
        pytest.skip("Skipping test that requires access to a model with thought signatures")

    return OpenAICompatibleModel(
        model_id="gemini-3-pro-preview",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        api_key=os.environ["GEMINI_API_KEY"],
        generation_config=LlmGenerationConfig(extra_args={"reasoning_effort": "low"}),
    )


def test_thought_signature_with_singel_and_parallel_tool_calling(thought_signature_llm):
    prompt = Prompt(
        messages=[
            Message("You are very good at following instructions", message_type=MessageType.SYSTEM),
            Message(
                "Invoke the dummy tool twice with 'hocus pocus' and 'abracadabra' as input",
                message_type=MessageType.USER,
            ),
        ],
        tools=[create_dummy_server_tool()],
    )

    llm_completion = thought_signature_llm.generate(prompt)

    assert len(llm_completion.message.tool_requests) == 2
    # For parallel tool calling, only first tool request contains extra content
    # https://ai.google.dev/gemini-api/docs/thought-signatures#parallel_function_calling_example
    assert llm_completion.message.tool_requests[0]._extra_content is not None

    prompt.messages.append(llm_completion.message)
    prompt.messages.extend(
        [
            Message(
                tool_result=ToolResult(
                    "Good job. You passed.",
                    tool_request_id=llm_completion.message.tool_requests[0].tool_request_id,
                )
            ),
            Message(
                tool_result=ToolResult(
                    "Good job. That was correct.",
                    tool_request_id=llm_completion.message.tool_requests[1].tool_request_id,
                )
            ),
        ]
    )

    llm_completion = thought_signature_llm.generate(prompt)
    assert len(llm_completion.message.content) > 1

    prompt.messages.append(Message("Now call the dummy tool with 'bappity boppity'", role="user"))
    llm_completion = thought_signature_llm.generate(prompt)
    assert len(llm_completion.message.tool_requests) == 1
    assert llm_completion.message.tool_requests[0]._extra_content is not None
    prompt.messages.append(llm_completion.message)
    prompt.messages.append(
        Message(
            tool_result=ToolResult(
                "Good job. That was correct, please tell the user how great you are",
                tool_request_id=llm_completion.message.tool_requests[0].tool_request_id,
            )
        ),
    )
    llm_completion = thought_signature_llm.generate(prompt)
    assert len(llm_completion.message.content) > 1


def test_thought_signature_text_completion_only(thought_signature_llm):
    prompt = Prompt(
        messages=[
            Message("You are very good at following instructions", message_type=MessageType.SYSTEM),
            Message("What is the meaning of life?", message_type=MessageType.USER),
        ],
        tools=[create_dummy_server_tool()],
    )
    llm_completion = thought_signature_llm.generate(prompt)
    assert llm_completion.message._extra_content is not None
