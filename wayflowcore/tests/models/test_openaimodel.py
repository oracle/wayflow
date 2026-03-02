# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import os
from unittest.mock import Mock

import pytest

from wayflowcore.agent import Agent
from wayflowcore.models import OpenAIAPIType, OpenAIModel
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.openaicompatiblemodel import OPEN_API_KEY
from wayflowcore.property import StringProperty
from wayflowcore.serialization.serializer import serialize
from wayflowcore.templates import PromptTemplate
from wayflowcore.tools import ServerTool


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
def test_openai_responses_e2e_can_continue_after_tool_call_with_replayed_history() -> None:
    echo_mock = Mock(side_effect=lambda text: text)

    echo_tool = ServerTool(
        name="echo",
        description="Echo back the input.",
        func=echo_mock,
        input_descriptors=[StringProperty(name="text", description="Text to echo.")],
        output_descriptors=[StringProperty(name="echoed", description="Echoed text.")],
    )

    llm = OpenAIModel(
        model_id="gpt-5.2",
        api_type=OpenAIAPIType.RESPONSES,
        generation_config=LlmGenerationConfig(
            max_tokens=256,
            temperature=0,
            extra_args={"reasoning": {"effort": "none"}},
        ),
    )

    agent = Agent(
        llm=llm,
        tools=[echo_tool],
        custom_instruction="You are a helpful assistant.",
    )
    conversation = agent.start_conversation()
    conversation.append_user_message(
        "You MUST call the `echo` tool with text='hi'. "
        "DO NOT reply to the user until after you receive the tool result. "
        "After receiving the tool result, reply with exactly: echoed: hi"
    )

    conversation.execute()

    assert echo_mock.call_count >= 1

    messages = conversation.get_messages()
    tool_request_id = next(
        tool_request.tool_request_id
        for message in messages
        for tool_request in message.tool_requests or []
        if tool_request.name == "echo"
    )
    tool_result_index = next(
        i
        for i, message in enumerate(messages)
        if message.tool_result is not None
        and message.tool_result.tool_request_id == tool_request_id
    )

    assert messages[tool_result_index].tool_result is not None
    assert messages[tool_result_index].tool_result.content == "hi"
    assert tool_result_index < len(messages) - 1, "Expected a follow-up assistant message."
