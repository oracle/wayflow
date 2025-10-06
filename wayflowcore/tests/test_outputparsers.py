# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import json
import re
from typing import List, Optional, Union

import pytest

from wayflowcore.messagelist import Message, MessageType
from wayflowcore.outputparser import (
    JsonToolOutputParser,
    PythonToolOutputParser,
    RegexOutputParser,
    RegexPattern,
)
from wayflowcore.tools import ToolRequest, tool


@pytest.fixture
def sample_message():
    return Message(content="Sample content", message_type=MessageType.USER)


def test_parse_output_single_regex(sample_message):
    parser = RegexOutputParser(regex_pattern=r"Sample")
    result = parser.parse_output(sample_message)
    assert result.content == "Sample"


def test_parse_output_multiple_regex(sample_message):
    parser = RegexOutputParser(regex_pattern={"key1": r"Sample", "key2": r"content"})
    result = parser.parse_output(sample_message)
    expected_content = json.dumps({"key1": "Sample", "key2": "content"})
    assert result.content == expected_content


def test_parse_output_no_match(sample_message):
    parser = RegexOutputParser(regex_pattern=r"NoMatch")
    result = parser.parse_output(sample_message)
    assert result.content == ""


def test_parse_output_empty_regex(sample_message):
    parser = RegexOutputParser(regex_pattern="")
    result = parser.parse_output(sample_message)
    assert result.content == ""


def test_parse_output_invalid_regex(sample_message):
    parser = RegexOutputParser(regex_pattern="[")
    with pytest.raises(re.error):
        parser.parse_output(sample_message)


def test_parse_output_dict_regex(sample_message):
    parser = RegexOutputParser(regex_pattern={"key1": r"Sample", "key2": r"content"})
    result = parser.parse_output(sample_message)
    expected_content = json.dumps({"key1": "Sample", "key2": "content"})
    assert result.content == expected_content


def test_parse_output_dict_regex_no_match(sample_message):
    parser = RegexOutputParser(regex_pattern={"key1": r"NoMatch", "key2": r"NoMatch"})
    result = parser.parse_output(sample_message)
    expected_content = json.dumps({"key1": "", "key2": ""})
    assert result.content == expected_content


def test_parse_output_dict_regex_empty_regex(sample_message):
    parser = RegexOutputParser(regex_pattern={"key1": "", "key2": ""})
    result = parser.parse_output(sample_message)
    expected_content = json.dumps({"key1": "", "key2": ""})
    assert result.content == expected_content


def test_parse_output_dict_regex_invalid_regex(sample_message):
    parser = RegexOutputParser(regex_pattern={"key1": "[", "key2": "["})
    with pytest.raises(re.error):
        parser.parse_output(sample_message)


def test_though_action_regex_parser():
    message = Message(content="Thoughts: I should call some tool. Action: some_tool()")
    parser = RegexOutputParser(
        regex_pattern={"thought": "Thoughts: (.*) Action", "action": "Action: (.*)"}
    )
    assert parser.parse_output(message).content == json.dumps(
        {"thought": "I should call some tool.", "action": "some_tool()"}
    )


def test_though_action_regex_parser_with_flag():
    message = Message(
        content="Thoughts: I should call some tool.\nOr maybe not. Action: some_tool()"
    )
    parser = RegexOutputParser(
        regex_pattern={
            "thought": RegexPattern(pattern="Thoughts: (.*) Action", flags=re.DOTALL),
            "action": "Action: (.*)",
        }
    )
    assert parser.parse_output(message).content == json.dumps(
        {"thought": "I should call some tool.\nOr maybe not.", "action": "some_tool()"}
    )


@tool(description_mode="only_docstring")
def some_tool_1(arg1: str, arg2: int = 2) -> str:
    """Some tool 1"""
    return ""


@tool(description_mode="only_docstring")
def some_tool_2(arg3: List[int], arg4: Union[int, bool], arg5: Optional[str] = None) -> str:
    """Some tool 1"""
    return ""


def assert_tool_requests_are_equal(
    tool_requests: List[ToolRequest], expected_tool_requests: List[ToolRequest]
) -> None:
    assert len(tool_requests) == len(expected_tool_requests)
    for tr, expected_tr in zip(tool_requests, expected_tool_requests):
        assert tr.name == expected_tr.name
        assert tr.args == expected_tr.args


SEVERAL_TOOL_REQUESTS = [
    ToolRequest(name="some_tool_1", args={"arg1": "s"}, tool_request_id="id1"),
    ToolRequest(name="some_tool_1", args={"arg1": "4"}, tool_request_id="id2"),
    ToolRequest(name="some_tool_2", args={"arg3": [2, 2, 2], "arg4": True}, tool_request_id="id3"),
]


@pytest.mark.parametrize(
    "llm_output, expected_tool_calls",
    [
        (
            "some_tool_1(arg1='s')",
            [ToolRequest(name="some_tool_1", args={"arg1": "s"}, tool_request_id="id1")],
        ),
        (
            "some_tool_1(arg1=1)",
            [ToolRequest(name="some_tool_1", args={"arg1": "1"}, tool_request_id="id1")],
        ),
        (
            "some_tool_1(arg1='s', arg2='4')",
            [ToolRequest(name="some_tool_1", args={"arg1": "s", "arg2": 4}, tool_request_id="id1")],
        ),
        (  # with ; separators
            "some_tool_1(arg1='s');some_tool_1(arg1=4);some_tool_2(arg3=['2',2,2],arg4=True)",
            SEVERAL_TOOL_REQUESTS,
        ),
        (  # with , separators
            "some_tool_1(arg1='s'),some_tool_1(arg1=4),some_tool_2(arg3=['2',2,2],arg4=True)",
            SEVERAL_TOOL_REQUESTS,
        ),
    ],
)
def test_python_tool_output_parser_simple(llm_output, expected_tool_calls):
    parser = PythonToolOutputParser().with_tools([some_tool_1, some_tool_2])
    message = parser.parse_output(Message(content=llm_output))
    assert_tool_requests_are_equal(message.tool_requests, expected_tool_calls)


@pytest.mark.parametrize(
    "llm_output, expected_tool_calls",
    [
        (
            '{"name": "some_tool_1", "parameters": {"arg1":"s"}}',
            [ToolRequest(name="some_tool_1", args={"arg1": "s"}, tool_request_id="id1")],
        ),
        (
            '{"name": "some_tool_1", "parameters": {"arg1":1}}',
            [ToolRequest(name="some_tool_1", args={"arg1": "1"}, tool_request_id="id1")],
        ),
        (
            '{"name": "some_tool_1", "parameters": {"arg1": "s", "arg2":"4"}}',
            [ToolRequest(name="some_tool_1", args={"arg1": "s", "arg2": 4}, tool_request_id="id1")],
        ),
        (  # with ; separators
            '{"name": "some_tool_1", "parameters": {"arg1": "s"}};'
            '{"name": "some_tool_1", "parameters": {"arg1": 4}};'
            '{"name": "some_tool_2", "parameters": {"arg3": ["2",2,2], "arg4":"true"}}',
            SEVERAL_TOOL_REQUESTS,
        ),
        (  # with , separators
            '{"name": "some_tool_1", "parameters": {"arg1": "s"}},'
            '{"name": "some_tool_1", "parameters": {"arg1": 4}},'
            '{"name": "some_tool_2", "parameters": {"arg3": ["2",2,2], "arg4":True}}',
            SEVERAL_TOOL_REQUESTS,
        ),
        (  # within a python list
            '[{"name": "some_tool_1", "parameters": {"arg1": "s"}},'
            '{"name": "some_tool_1", "parameters": {"arg1": 4}},'
            '{"name": "some_tool_2", "parameters": {"arg3": ["2",2,2], "arg4":3.0}}]',
            SEVERAL_TOOL_REQUESTS,
        ),
    ],
)
def test_python_tool_output_parser(llm_output, expected_tool_calls):
    parser = JsonToolOutputParser().with_tools([some_tool_1, some_tool_2])
    message = parser.parse_output(Message(content=llm_output))
    assert_tool_requests_are_equal(message.tool_requests, expected_tool_calls)
