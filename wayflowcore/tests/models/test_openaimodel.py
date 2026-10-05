# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import os

import pytest

from wayflowcore.messagelist import Message
from wayflowcore.models import OpenAIAPIType, OpenAIModel, Prompt
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.openaicompatiblemodel import OPEN_API_KEY
from wayflowcore.serialization.serializer import serialize
from wayflowcore.templates import PromptTemplate
from wayflowcore.tools import Tool

from .test_openaicompatiblemodel import run_responses_tool_call_replay_e2e


@pytest.mark.skipif(OPEN_API_KEY not in os.environ, reason="OPENAI_API_KEY is not set")
@pytest.mark.parametrize("stream", [False, True])
def test_openai_reasoning_tools_use_responses_without_changing_config(stream):
    config = LlmGenerationConfig(max_tokens=1024, extra_args={"reasoning_effort": "low"})
    llm = OpenAIModel(model_id="gpt-5.4", generation_config=config)
    prompt = Prompt(
        messages=[Message(role="user", content="Call test_tool now.")],
        tools=[Tool(name="test_tool", description="A no-op tool.", input_descriptors=[])],
        generation_config=config,
    )
    message = list(llm.stream_generate(prompt))[-1][1] if stream else llm.generate(prompt).message
    assert message.tool_requests and message.tool_requests[0].name == "test_tool"
    assert llm.api_type == OpenAIAPIType.CHAT_COMPLETIONS
    assert llm.generation_config is config and prompt.generation_config is config
    assert config.extra_args == {"reasoning_effort": "low"}


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
