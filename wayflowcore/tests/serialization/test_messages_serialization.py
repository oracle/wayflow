# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest

from wayflowcore.messagelist import ImageContent, Message, MessageList, MessageType, TextContent
from wayflowcore.serialization.serializer import autodeserialize, deserialize, serialize
from wayflowcore.tools import ToolRequest, ToolResult

MESSAGES = [
    Message(message_type=MessageType.SYSTEM, content="answer the user's questions"),
    Message(message_type=MessageType.USER, content="In what city is my company 'OHOH' based?"),
    Message(
        message_type=MessageType.TOOL_REQUEST,
        content="I'll use the get_company_location with the user's company",
        tool_requests=[ToolRequest("get_location", {"company_name": "OHOH"}, "tc1")],
    ),
    Message(
        message_type=MessageType.INTERNAL,
        content="whatever",
    ),
    Message(
        message_type=MessageType.TOOL_RESULT,
        tool_result=ToolResult(tool_request_id="tc1", content="bern"),
    ),
    Message(contents=[TextContent("Text content 1"), TextContent("Text content 2")]),
    Message(
        contents=[
            ImageContent.from_bytes(bytes_content=b"12345", format="png"),
            TextContent("Text content 2"),
        ]
    ),
    Message(
        content="Test",
        message_type=MessageType.TOOL_RESULT,
        tool_result=ToolResult(tool_request_id="tc1", content="bern"),
    ),
]


@pytest.mark.parametrize("message", MESSAGES)
def test_serialize_and_deserialize_message(message: Message) -> None:
    serialized_message = serialize(message)

    for content in message.contents:
        if isinstance(content, TextContent):
            assert content.content in serialized_message
        elif isinstance(content, ImageContent):
            assert content.base64_content in serialized_message
        else:
            raise NotImplementedError()

    assert message.tool_result is None or message.tool_result.content in serialized_message
    assert message.tool_requests is None or message.tool_requests[0].name in serialized_message

    deserialized_message = deserialize(Message, serialized_message)

    assert message == deserialized_message


@pytest.mark.parametrize("message", MESSAGES)
def test_serialize_and_autodeserialize_message(message: Message) -> None:
    deserialized_message = autodeserialize(serialize(message))

    assert message == deserialized_message


def test_serialize_and_deserialize_message_list() -> None:
    message_list = MessageList(MESSAGES)

    serialized_message_list = serialize(message_list)
    deserialized_message_list = deserialize(MessageList, serialized_message_list)

    assert message_list == deserialized_message_list


def test_serialize_and_autodeserialize_message_list() -> None:
    message_list = MessageList(MESSAGES)
    deserialized_message_list = autodeserialize(serialize(message_list))

    assert message_list == deserialized_message_list
