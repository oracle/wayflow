# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict, Iterable, Iterator

import pytest

from wayflowcore import Message, MessageType, Tool
from wayflowcore.models import (
    LlmCompletion,
    LlmModel,
    Prompt,
    TaggedMessageChunkType,
    TaggedMessageChunkTypeWithTokenUsage,
    VllmModel,
)
from wayflowcore.property import StringProperty
from wayflowcore.templates import LLAMA_CHAT_TEMPLATE
from wayflowcore.tools import ToolRequest

from .patching import patch_llm, patch_openai_compatible_llm


class FakeLLM(LlmModel):
    def __init__(self):
        super().__init__(
            model_id="",
            generation_config=None,
            supports_structured_generation=True,
            supports_tool_calling=True,
        )

    async def _generate_impl(self, prompt: Prompt) -> LlmCompletion:
        raise AssertionError("This method must be patched!")

    async def _stream_generate_impl(
        self, prompt: Prompt
    ) -> Iterator[TaggedMessageChunkTypeWithTokenUsage]:
        raise AssertionError("This method must be patched!")

    @property
    def config(self) -> Dict[str, Any]:
        raise AssertionError("This method must be patched!")


def assert_message_equal(m1: Message, m2: Message) -> None:
    assert m1.content == m2.content
    assert (m1.tool_requests is None and m2.tool_requests is None) or {
        t.tool_request_id for t in m1.tool_requests
    } == {t.tool_request_id for t in m2.tool_requests}
    assert m1.message_type == m2.message_type


def iterate_llm_stream(stream: Iterable[TaggedMessageChunkType]) -> Message:
    content = None
    for chunk_type, content in stream:
        continue
    return content  # type: ignore


@pytest.mark.parametrize(
    "outputs, expected_message",
    [
        (["hello"], Message(content="hello", message_type=MessageType.AGENT)),
        (
            [[ToolRequest(name="ping", args={}, tool_request_id="1")]],
            Message(
                tool_requests=[ToolRequest(name="ping", args={}, tool_request_id="1")],
                message_type=MessageType.TOOL_REQUEST,
            ),
        ),
        (
            [Message(content="direct", message_type=MessageType.AGENT)],
            Message(content="direct", message_type=MessageType.AGENT),
        ),
    ],
)
def test_generate_and_stream_single_output(outputs, expected_message):
    llm = FakeLLM()

    with patch_llm(llm, outputs):

        completion = llm.generate(prompt="irrelevant")
        assert_message_equal(completion.message, expected_message)

        # streaming
        output = iterate_llm_stream(llm.stream_generate(prompt="irrelevant"))
        assert_message_equal(output, expected_message)


def test_multiple_outputs_are_returned_in_sequence():
    llm = FakeLLM()

    with patch_llm(llm, ["one", "two", "three"]):
        assert llm.generate("not relevant").message.content == "one"
        assert llm.generate("not relevant").message.content == "two"
        assert llm.generate("not relevant").message.content == "three"


def test_more_calls_than_outputs_raises_value_error():
    llm = FakeLLM()

    with patch_llm(llm, ["one", "two"]):
        assert llm.generate("not relevant").message.content == "one"
        assert llm.generate("not relevant").message.content == "two"

        with pytest.raises(ValueError, match="The LLM generation was called 3 times"):
            llm.generate("not relevant")  # will crash


@pytest.mark.anyio
async def test_nested_contexts_do_not_interfere():
    llm = FakeLLM()

    with patch_llm(llm, ["outer_1", "outer_2"]):
        assert (await llm.generate_async("not relevant")).message.content == "outer_1"

        with patch_llm(llm, ["inner"]):
            assert (await llm.generate_async("not relevant")).message.content == "inner"

        assert (await llm.generate_async("not relevant")).message.content == "outer_2"


@pytest.mark.anyio
async def test_openai_compatible_patch_pure_text():
    vllm_llm = VllmModel(model_id="agi", host_port="does/not/exist")

    with patch_openai_compatible_llm(llm=vllm_llm, txt="hi, how are you doing?"):
        completion = await vllm_llm.generate_async("not relevant")
        assert completion.message.content == "hi, how are you doing?"

    with patch_openai_compatible_llm(llm=vllm_llm, txt="hi, how are you doing?"):
        message = iterate_llm_stream(vllm_llm.stream_generate("not relevant"))
        assert message.content == "hi, how are you doing?"


@pytest.mark.anyio
async def test_openai_compatible_patch_tool_result():
    vllm_llm = VllmModel(
        model_id="agi",
        host_port="does/not/exist",
    )

    tools = [Tool(name="some_tool", description="", input_descriptors=[StringProperty(name="a")])]
    prompt = LLAMA_CHAT_TEMPLATE.with_tools(tools).format(
        inputs={LLAMA_CHAT_TEMPLATE.CHAT_HISTORY_PLACEHOLDER_NAME: []}
    )

    with patch_openai_compatible_llm(
        llm=vllm_llm, txt='{"name": "some_tool", "parameters": {"a": "text"}}'
    ):
        completion = await vllm_llm.generate_async(prompt)
        tool_requests = completion.message.tool_requests
        assert len(tool_requests) == 1
        assert tool_requests[0].name == "some_tool"
        assert tool_requests[0].args == {"a": "text"}

    with patch_openai_compatible_llm(
        llm=vllm_llm, txt='{"name": "some_tool", "parameters": {"a": "text"}}'
    ):
        message = iterate_llm_stream(vllm_llm.stream_generate(prompt))
        tool_requests = message.tool_requests
        assert len(tool_requests) == 1
        assert tool_requests[0].name == "some_tool"
        assert tool_requests[0].args == {"a": "text"}
