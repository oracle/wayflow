# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import asyncio
import os
import warnings
from contextlib import asynccontextmanager
from copy import deepcopy
from json import dumps
from unittest.mock import AsyncMock, patch

import httpx2
import pytest

from wayflowcore.messagelist import Message
from wayflowcore.models import OpenAIAPIType, OpenAIModel, Prompt
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.openaicompatiblemodel import OPEN_API_KEY
from wayflowcore.serialization.serializer import serialize
from wayflowcore.templates import PromptTemplate
from wayflowcore.tools import Tool

from .test_openaicompatiblemodel import run_responses_tool_call_replay_e2e


def _make_reasoning_tool_prompt(reasoning_effort: str, include_tools: bool = True) -> Prompt:
    return Prompt(
        messages=[Message(content="Say hello.", role="user")],
        tools=(
            [Tool(name="dummy", description="A dummy tool.", input_descriptors=[])]
            if include_tools
            else None
        ),
        generation_config=LlmGenerationConfig(extra_args={"reasoning_effort": reasoning_effort}),
    )


def _responses_text_result(text: str = "hello"):
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}


@pytest.mark.anyio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(
    "model_id, effort, tools, use_responses",
    [
        ("gpt-5.4", "HIGH", True, True),
        ("gpt-6.1-luna", "low", True, True),
        ("gpt-5.3", "HIGH", True, False),
        ("gpt-5.4", "NONE", True, False),
        ("gpt-5.4", "HIGH", False, False),
    ],
)
async def test_openai_reasoning_tool_routing(model_id, effort, tools, use_responses, stream):
    llm = OpenAIModel(model_id=model_id, api_key="test-key")
    prompt = _make_reasoning_tool_prompt(effort, tools)
    prompt.generation_config.max_tokens = 42
    if use_responses:
        prompt.generation_config.extra_args["reasoning"] = {"summary": "detailed"}
    original_config = deepcopy(prompt.generation_config.extra_args)
    result = (
        _responses_text_result()
        if use_responses
        else {"choices": [{"message": {"content": "hello"}}]}
    )
    post = AsyncMock(return_value=httpx2.Response(200, json=result))
    captured = {}

    @asynccontextmanager
    async def post_stream(self, method, **params):
        captured.update(params)
        events = (
            [
                {"type": "response.output_text.delta", "delta": "hello"},
                {"type": "response.completed", "response": result},
            ]
            if use_responses
            else [{"choices": [{"delta": {"content": "hello"}}]}]
        )
        yield httpx2.Response(200, text="".join(f"data: {dumps(event)}\n\n" for event in events))

    with (
        patch("httpx2.AsyncClient.post", new=post),
        patch("httpx2.AsyncClient.stream", new=post_stream),
        warnings.catch_warnings(record=True) as recorded,
    ):
        warnings.simplefilter("always")
        if stream:
            chunks = [chunk async for chunk in llm.stream_generate_async(prompt)]
            message = chunks[-1][1]
        else:
            message = (await llm.generate_async(prompt)).message
            captured.update(post.await_args.kwargs)

    assert captured["url"].endswith("/responses" if use_responses else "/chat/completions")
    payload = captured["json"]
    if use_responses:
        assert payload["reasoning"] == {"summary": "detailed", "effort": effort.lower()}
        assert payload["max_output_tokens"] == 42
        assert payload["tools"]
        assert "reasoning_effort" not in payload
    else:
        assert payload["reasoning_effort"] == (effort if model_id == "gpt-5.3" else effort.lower())
    assert bool(recorded) == use_responses
    assert message.content == "hello"
    assert prompt.generation_config.extra_args == original_config
    assert llm.api_type == OpenAIAPIType.CHAT_COMPLETIONS


@pytest.mark.anyio
async def test_openai_concurrent_requests_keep_their_selected_api():
    llm = OpenAIModel(model_id="gpt-5.4", api_key="test-key")
    prompts = [_make_reasoning_tool_prompt("HIGH", tools) for tools in (True, False)]
    requests = []

    async def post(self, **params):
        requests.append(params)
        await asyncio.sleep(0)
        result = (
            _responses_text_result()
            if params["url"].endswith("/responses")
            else {"choices": [{"message": {"content": "hello"}}]}
        )
        return httpx2.Response(200, json=result)

    with patch("httpx2.AsyncClient.post", new=post), pytest.warns(UserWarning, match="switching"):
        results = await asyncio.gather(*(llm.generate_async(prompt) for prompt in prompts))

    assert [params["url"].rsplit("/", 1)[-1] for params in requests] == ["responses", "completions"]
    assert all(result.message.content == "hello" for result in results)
    assert all(
        prompt.generation_config.extra_args == {"reasoning_effort": "HIGH"} for prompt in prompts
    )
    assert llm.api_type == OpenAIAPIType.CHAT_COMPLETIONS


def test_openai_model_with_api_key():
    if OPEN_API_KEY not in os.environ:
        pytest.skip("OPENAI API KEY not available in environment")

    api_key = os.environ[OPEN_API_KEY]
    try:
        del os.environ[OPEN_API_KEY]
        llm = OpenAIModel(api_key=api_key)
        prompt = (
            PromptTemplate.from_string("Please count to 10")
            .with_generation_config(LlmGenerationConfig(max_tokens=1))
            .format()
        )
        response = llm.generate(prompt).message.content
        assert len(response) > 1
        serialized_model = serialize(llm)
        assert api_key not in serialized_model
    finally:
        os.environ[OPEN_API_KEY] = api_key


def test_model_proxy():
    llm = OpenAIModel(
        model_id="gpt-4o",
        proxy="http://wrong-proxy",
        api_key="something",
    )
    with pytest.raises(Exception, match="API request failed after retries due to network error"):
        llm.generate("count to 10")


def test_model_proxy_stream():
    llm = OpenAIModel(
        model_id="gpt-4o",
        proxy="http://wrong_proxy",
        api_key="something",
    )

    with pytest.raises(
        Exception, match="API streaming request failed after retries due to network error"
    ):
        for x in llm.stream_generate("count to 10"):
            pass


def test_model_properly_counts_cached_tokens(gpt_llm):
    prompt = "Hello" * 2000
    first_completion = gpt_llm.generate(prompt)
    second_completion = gpt_llm.generate(prompt)
    token_usage = second_completion.token_usage
    assert token_usage.cached_tokens > 0


def test_model_properly_counts_cached_tokens_streaming(gpt_llm):
    prompt = "Hello" * 2000
    first_completion = gpt_llm.generate(prompt)

    stream = gpt_llm.stream_generate(prompt)
    for chunk_type, content in stream:
        continue
    assert gpt_llm.token_usage_standalone is not None
    assert gpt_llm.token_usage_standalone.cached_tokens > 0


@pytest.mark.skipif(
    OPEN_API_KEY not in os.environ,
    reason="OPENAI_API_KEY is not set",
)
@pytest.mark.parametrize("model_id", ["gpt-5", "gpt-5.1", "gpt-5.2"])
def test_openai_responses_e2e_can_continue_after_tool_call_with_replayed_history(
    model_id: str,
) -> None:
    llm = OpenAIModel(
        model_id=model_id,
        api_type=OpenAIAPIType.RESPONSES,
        generation_config=LlmGenerationConfig(
            max_tokens=64,
            extra_args={"reasoning": {"effort": "minimal" if model_id == "gpt-5" else "none"}},
        ),
    )
    run_responses_tool_call_replay_e2e(llm)
