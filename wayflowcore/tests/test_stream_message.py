# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import AsyncIterator, Dict, Iterator, List, Optional, Tuple

import pytest

from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import StreamChunkType
from wayflowcore.steps import OutputMessageStep
from wayflowcore.tools import ToolRequest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


def simple_conversation():
    flow = create_single_step_flow(OutputMessageStep("Any message"))
    return flow.start_conversation()


@pytest.mark.anyio
async def test_streaming_single_message() -> None:
    conversation = simple_conversation()

    async def llm_generator() -> Iterator[Tuple[str, Optional[List[Dict]], bool, MessageType]]:
        yield StreamChunkType.START_CHUNK, Message(message_type=MessageType.AGENT, content="")
        assert conversation.get_last_message().content == ""
        yield StreamChunkType.TEXT_CHUNK, Message(content="Hello ")
        assert conversation.get_last_message().content == "Hello "
        yield StreamChunkType.TEXT_CHUNK, Message(content="World")
        assert conversation.get_last_message().content == "Hello World"
        yield StreamChunkType.TEXT_CHUNK, Message(content="!")
        assert conversation.get_last_message().content == "Hello World!"
        assert len(conversation.get_messages()) == 1
        yield StreamChunkType.END_CHUNK, Message(
            message_type=MessageType.AGENT, content="Hello World!"
        )
        assert conversation.get_last_message().content == "Hello World!"
        assert len(conversation.get_messages()) == 1

    message = await conversation.message_list._stream_message(llm_generator())
    assert message.content == "Hello World!"
    assert len(conversation.get_messages()) == 1
    assert conversation.get_last_message().content == message.content


@pytest.mark.anyio
async def test_streaming_multiple_messages() -> None:
    conversation = simple_conversation()

    async def llm_generator() -> Iterator[Tuple[str, Optional[List[Dict]], bool, MessageType]]:
        yield StreamChunkType.START_CHUNK, Message(message_type=MessageType.AGENT, content="Hello ")
        yield StreamChunkType.END_CHUNK, Message(message_type=MessageType.AGENT, content="Hello ")
        yield StreamChunkType.START_CHUNK, Message(message_type=MessageType.AGENT, content="World")
        yield StreamChunkType.END_CHUNK, Message(message_type=MessageType.AGENT, content="World")
        yield StreamChunkType.START_CHUNK, Message(message_type=MessageType.AGENT, content="!")
        yield StreamChunkType.END_CHUNK, Message(message_type=MessageType.AGENT, content="!")

    await conversation.message_list._stream_message(llm_generator())
    assert len(conversation.get_messages()) == 3
    assert conversation.get_messages()[0].content == "Hello "
    assert conversation.get_messages()[1].content == "World"
    assert conversation.get_messages()[2].content == "!"


@pytest.mark.skip_guard_filewrites
@pytest.mark.anyio
async def test_streaming_message_with_tools() -> None:
    conversation = simple_conversation()

    async def async_generator() -> (
        AsyncIterator[Tuple[str, Optional[List[Dict]], bool, MessageType]]
    ):
        yield StreamChunkType.START_CHUNK, Message(message_type=MessageType.AGENT, content="")
        yield StreamChunkType.TEXT_CHUNK, Message(content="Hello ")
        yield StreamChunkType.TEXT_CHUNK, Message(content="World")
        yield StreamChunkType.TEXT_CHUNK, Message(content="!")
        yield StreamChunkType.END_CHUNK, Message(
            message_type=MessageType.TOOL_REQUEST,
            content="Hello World!",
            tool_requests=[ToolRequest("foo", {"bar": "baz"}, "1234d")],
        )

    message = await conversation.message_list._stream_message(async_generator())
    assert message.content == "Hello World!"
    assert message.tool_requests is not None
    assert len(message.tool_requests) == 1
    assert message.tool_requests[0].tool_request_id == "1234d"
    assert message.tool_requests[0].name == "foo"
    assert message.tool_requests[0].args == {"bar": "baz"}
