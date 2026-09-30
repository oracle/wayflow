# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import os
import warnings
from unittest.mock import AsyncMock, patch

import pytest

from wayflowcore.messagelist import Message
from wayflowcore.models import OpenAIAPIType, OpenAIModel, Prompt
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.openaicompatiblemodel import OPEN_API_KEY, OpenAICompatibleModel
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
    return {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    }


@pytest.mark.parametrize("reasoning_effort", ["high", "HIGH"])
@pytest.mark.parametrize("model_id", ["gpt-5.4", "gpt-5.6-luna", "openai.gpt-6.1-luna"])
def test_openai_model_switches_incompatible_tool_request_to_responses(model_id, reasoning_effort):
    llm = OpenAIModel(model_id=model_id, api_key="test-key")
    prompt = _make_reasoning_tool_prompt(reasoning_effort)
    post = AsyncMock(return_value=_responses_text_result())

    with patch.object(OpenAICompatibleModel, "_post", new=post):
        with pytest.warns(UserWarning, match="(?i)switching.*responses"):
            completion = llm.generate(prompt)

    request_params = post.await_args.kwargs["request_params"]
    assert request_params["url"] == "https://api.openai.com/v1/responses"
    assert request_params["json"]["reasoning"]["effort"] == reasoning_effort.lower()
    assert "reasoning_effort" not in request_params["json"]
    assert len(request_params["json"]["tools"]) == 1
    assert completion.message.content == "hello"
    assert prompt.generation_config.extra_args == {"reasoning_effort": reasoning_effort}
    assert llm.api_type == OpenAIAPIType.CHAT_COMPLETIONS


@pytest.mark.parametrize(
    "model_id, reasoning_effort, include_tools, expected_effort",
    [
        ("gpt-5.6-luna", "none", True, "none"),
        ("gpt-5.6-luna", "NONE", True, "none"),
        ("gpt-5.6-luna", "HIGH", False, "high"),
        ("gpt-5.3", "high", True, "high"),
        ("gpt-5.3", "HIGH", True, "HIGH"),
        ("gpt-4o", "high", True, "high"),
    ],
)
def test_openai_model_keeps_compatible_request_on_configured_chat_completions(
    model_id, reasoning_effort, include_tools, expected_effort
):
    llm = OpenAIModel(model_id=model_id, api_key="test-key")
    prompt = _make_reasoning_tool_prompt(reasoning_effort, include_tools=include_tools)
    post = AsyncMock(
        return_value={
            "choices": [{"message": {"role": "assistant", "content": "hello"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
    )

    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        with patch.object(OpenAICompatibleModel, "_post", new=post):
            completion = llm.generate(prompt)

    request_params = post.await_args.kwargs["request_params"]
    assert request_params["url"] == "https://api.openai.com/v1/chat/completions"
    assert request_params["json"]["reasoning_effort"] == expected_effort
    assert completion.message.content == "hello"
    assert not recorded_warnings


@pytest.mark.anyio
async def test_openai_model_streaming_uses_responses_for_incompatible_tool_request():
    llm = OpenAIModel(model_id="gpt-5.6-luna", api_key="test-key")
    prompt = _make_reasoning_tool_prompt("HIGH")
    captured_request_params = {}

    def fake_post_stream(request_params, **kwargs):
        captured_request_params.update(request_params)

        async def json_stream():
            yield {"type": "response.output_text.delta", "delta": "hello"}
            yield {
                "type": "response.completed",
                "response": {
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "hello"}],
                        }
                    ],
                    "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                },
            }

        return json_stream()

    with patch.object(OpenAICompatibleModel, "_post_stream", side_effect=fake_post_stream):
        with pytest.warns(UserWarning, match="(?i)switching.*responses"):
            chunks = []
            async for chunk in llm.stream_generate_async(prompt):
                chunks.append(chunk)

    request_json = captured_request_params["json"]
    assert captured_request_params["url"] == "https://api.openai.com/v1/responses"
    assert request_json["reasoning"]["effort"] == "high"
    assert chunks[-1][1].content == "hello"


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
