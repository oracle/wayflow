# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Dict, List, Optional, Union

import pytest

from wayflowcore import Message, MessageType
from wayflowcore.outputparser import JsonToolOutputParser
from wayflowcore.tools import tool


@tool(description_mode="only_docstring")
def some_tool(
    str_arg: str = "dd",
    int_arg: int = 2,
    float_arg: float = 2.2,
    bool_arg: bool = False,
    list_arg: List[int] = [],
    dict_arg: Dict[str, List[int]] = {},
    none_arg: Optional[str] = None,
    union_arg: Union[bool, int] = True,
) -> str:
    """Some function"""
    return ""


@pytest.mark.parametrize(
    "raw_args,expected_tool_call_args",
    [
        # conversion to string
        ('{"str_arg": "something"}', {"str_arg": "something"}),
        ('{"str_arg": 2}', {"str_arg": "2"}),
        ('{"str_arg": 3.5}', {"str_arg": "3.5"}),
        # conversion to int
        ('{"int_arg": 3}', {"int_arg": 3}),
        ('{"int_arg": "3"}', {"int_arg": 3}),
        ('{"int_arg": True}', {"int_arg": 1}),
        # conversion to float
        ('{"float_arg": 3}', {"float_arg": 3.0}),
        ('{"float_arg": "3"}', {"float_arg": 3}),
        ('{"float_arg": True}', {"float_arg": 1}),
        # conversion to bool
        ('{"bool_arg": 2}', {"bool_arg": True}),
        ('{"bool_arg": 0}', {"bool_arg": False}),  # 10
        ('{"bool_arg": true}', {"bool_arg": True}),
        ('{"bool_arg": false}', {"bool_arg": False}),
        ('{"bool_arg": True}', {"bool_arg": True}),
        ('{"bool_arg": False}', {"bool_arg": False}),
        ('{"bool_arg": "yes"}', {"bool_arg": True}),
        ('{"bool_arg": "true"}', {"bool_arg": True}),
        ('{"bool_arg": "True"}', {"bool_arg": True}),
        ('{"bool_arg": "False"}', {"bool_arg": False}),
        ('{"bool_arg": "1"}', {"bool_arg": True}),
        ('{"bool_arg": "2"}', {"bool_arg": "2"}),  # could not correct  # 20
        # conversion to list
        ('{"list_arg": []}', {"list_arg": []}),
        ('{"list_arg": [1,2,3,4]}', {"list_arg": [1, 2, 3, 4]}),
        ('{"list_arg": ["1","2","3"]}', {"list_arg": [1, 2, 3]}),
        ('{"list_arg": [True,True,False]}', {"list_arg": [1, 1, 0]}),
        # conversion to dict
        ('{"dict_arg": {}', {"dict_arg": {}}),
        ('{"dict_arg": {"1": [1], "2": [2]}', {"dict_arg": {"1": [1], "2": [2]}}),
        ('{"dict_arg": {"1": ["1"], "2": ["2"]}', {"dict_arg": {"1": [1], "2": [2]}}),
        # conversion to optional
        ('{"none_arg": "something"', {"none_arg": "something"}),
        ('{"none_arg": ""}', {"none_arg": ""}),
        ('{"none_arg": null}', {"none_arg": None}),  # 30
        # conversion to optional
        ('{"union_arg": true', {"union_arg": True}),
        ('{"union_arg": 2', {"union_arg": 2}),
    ],
)
def test_llm_output_can_be_corrected_to_proper_tool_call(raw_args, expected_tool_call_args):
    llm_message = Message(
        message_type=MessageType.AGENT,
        content='{"name": "some_tool", "parameters": ' + raw_args + "}",
    )
    output_parser = JsonToolOutputParser(tools=[some_tool])

    parsed_llm_message = output_parser.parse_output(llm_message)
    assert parsed_llm_message.message_type == MessageType.TOOL_REQUEST
    assert len(parsed_llm_message.tool_requests) == 1
    assert parsed_llm_message.tool_requests[0].args == expected_tool_call_args
