# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import List

import pytest

from wayflowcore.messagelist import Message, MessageType
from wayflowcore.templates.llamatemplates import _LlamaMergeToolRequestAndCallsTransform
from wayflowcore.templates.pythoncalltemplates import _PythonMergeToolRequestAndCallsTransform
from wayflowcore.tools import ToolRequest, ToolResult
from wayflowcore.transforms.transforms import (
    CoalesceSystemMessagesTransform,
    RemoveEmptyNonUserMessageTransform,
    SplitPromptOnMarkerMessageTransform,
)


def assert_messages_are_correct(messages: List[Message], expected_messages: List[Message]):
    assert len(messages) == len(expected_messages), messages
    for message, expected_message in zip(messages, expected_messages):
        assert message.message_type == expected_message.message_type
        assert message.content == expected_message.content


SYSTEM_MESSAGE = Message(message_type=MessageType.SYSTEM, content="You are a helpful assistant")
USER_MESSAGE = Message(message_type=MessageType.USER, content="What is the capital of Switzerland?")
TOOL_REQUEST_MESSAGE = Message(
    message_type=MessageType.TOOL_REQUEST,
    tool_requests=[ToolRequest(name="some_tool", args={}, tool_request_id="id1")],
)
TOOL_RESULT = Message(
    message_type=MessageType.TOOL_RESULT,
    tool_result=ToolResult(tool_request_id="id1", content="some_output"),
)
AGENT_MESSAGE = Message(
    message_type=MessageType.AGENT, content="The capital of Switzerland is Bern"
)


@pytest.mark.parametrize(
    "messages,expected_messages",
    [
        ([USER_MESSAGE], [USER_MESSAGE]),
        ([SYSTEM_MESSAGE], [SYSTEM_MESSAGE]),
        (
            [SYSTEM_MESSAGE, SYSTEM_MESSAGE],
            [
                Message(
                    content="You are a helpful assistant\n\nYou are a helpful assistant",
                    message_type=MessageType.SYSTEM,
                )
            ],
        ),
        (
            [SYSTEM_MESSAGE, AGENT_MESSAGE, SYSTEM_MESSAGE],
            [SYSTEM_MESSAGE, AGENT_MESSAGE, SYSTEM_MESSAGE],
        ),
        (
            [SYSTEM_MESSAGE, SYSTEM_MESSAGE, SYSTEM_MESSAGE, AGENT_MESSAGE, SYSTEM_MESSAGE],
            [
                Message(
                    content="You are a helpful assistant\n\nYou are a helpful assistant\n\nYou are a helpful assistant",
                    message_type=MessageType.SYSTEM,
                ),
                AGENT_MESSAGE,
                SYSTEM_MESSAGE,
            ],
        ),
    ],
)
def test_coalesce_system_message_transform(messages, expected_messages):
    transform = CoalesceSystemMessagesTransform()
    transformed_messages = transform(messages)
    assert_messages_are_correct(transformed_messages, expected_messages)


EMPTY_USER_MESSAGE = Message(content="")
EMPTY_SYSTEM_MESSAGE = Message(content="", message_type=MessageType.SYSTEM)


@pytest.mark.parametrize(
    "messages,expected_messages",
    [
        (
            [AGENT_MESSAGE, EMPTY_USER_MESSAGE, EMPTY_SYSTEM_MESSAGE],
            [AGENT_MESSAGE, EMPTY_USER_MESSAGE],
        ),
        ([AGENT_MESSAGE, EMPTY_SYSTEM_MESSAGE, USER_MESSAGE], [AGENT_MESSAGE, USER_MESSAGE]),
        ([EMPTY_SYSTEM_MESSAGE, EMPTY_USER_MESSAGE], [EMPTY_USER_MESSAGE]),
    ],
)
def test_remove_empty_non_user_message_transform(messages, expected_messages):
    transform = RemoveEmptyNonUserMessageTransform()
    transformed_messages = transform(messages)
    assert_messages_are_correct(transformed_messages, expected_messages)


@pytest.mark.parametrize(
    "messages,expected_messages",
    [
        (
            [SYSTEM_MESSAGE, USER_MESSAGE, TOOL_REQUEST_MESSAGE, TOOL_RESULT, AGENT_MESSAGE],
            [
                Message(message_type=MessageType.SYSTEM, content="You are a helpful assistant"),
                USER_MESSAGE,
                Message(
                    message_type=MessageType.AGENT,
                    content='{"name": "some_tool", "parameters": {}}',
                ),
                Message(
                    message_type=MessageType.USER,
                    content='<tool_response>"some_output"</tool_response>',
                ),
                AGENT_MESSAGE,
            ],
        ),
    ],
)
def test_llama_merge_tool_request(messages, expected_messages):
    transform = _LlamaMergeToolRequestAndCallsTransform()
    transformed_messages = transform(messages)
    assert_messages_are_correct(transformed_messages, expected_messages)


COMPLEX_TOOL_REQUEST = Message(
    message_type=MessageType.TOOL_REQUEST,
    tool_requests=[
        ToolRequest(
            name="some_tool", args={"a": [1, 2, 3], "b": {1: "1"}, "c": True}, tool_request_id="id1"
        )
    ],
)


@pytest.mark.parametrize(
    "messages,expected_messages",
    [
        (
            [SYSTEM_MESSAGE, USER_MESSAGE, TOOL_REQUEST_MESSAGE, TOOL_RESULT, AGENT_MESSAGE],
            [
                Message(message_type=MessageType.SYSTEM, content="You are a helpful assistant"),
                USER_MESSAGE,
                Message(
                    message_type=MessageType.AGENT,
                    content="[some_tool()]",
                ),
                Message(
                    message_type=MessageType.USER,
                    content='<tool_response>"some_output"</tool_response>',
                ),
                AGENT_MESSAGE,
            ],
        ),
        (
            [SYSTEM_MESSAGE, USER_MESSAGE, COMPLEX_TOOL_REQUEST, TOOL_RESULT, AGENT_MESSAGE],
            [
                Message(message_type=MessageType.SYSTEM, content="You are a helpful assistant"),
                USER_MESSAGE,
                Message(
                    message_type=MessageType.AGENT,
                    content="[some_tool(a=[1, 2, 3],b={1: '1'},c=True)]",
                ),
                Message(
                    message_type=MessageType.USER,
                    content='<tool_response>"some_output"</tool_response>',
                ),
                AGENT_MESSAGE,
            ],
        ),
    ],
)
def test_python_merge_tool_request(messages, expected_messages):
    transform = _PythonMergeToolRequestAndCallsTransform()
    transformed_messages = transform(messages)
    assert_messages_are_correct(transformed_messages, expected_messages)


@pytest.mark.parametrize(
    "messages,expected_messages",
    [
        (
            [Message(message_type=MessageType.USER, content="First part\n---\nSecond part")],
            [
                Message(message_type=MessageType.USER, content="First part"),
                Message(message_type=MessageType.USER, content="Second part"),
            ],
        ),
        (
            [Message(message_type=MessageType.USER, content="A\n---\nB\n---\nC")],
            [
                Message(message_type=MessageType.USER, content="A"),
                Message(message_type=MessageType.USER, content="B"),
                Message(message_type=MessageType.USER, content="C"),
            ],
        ),
    ],
)
def test_split_prompt_on_marker(messages, expected_messages):
    transform = SplitPromptOnMarkerMessageTransform()
    transformed_messages = transform(messages)
    assert_messages_are_correct(transformed_messages, expected_messages)
