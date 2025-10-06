# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import json
from typing import List, Optional

from wayflowcore.messagelist import Message
from wayflowcore.tools import Tool


def _count_tokens_in_str(text: Optional[str]) -> int:
    if text is None:
        return 0
    # we assume the approximation of 1 token == 3/4 words
    # https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them
    return int(len(text.split(" ")) * 4 / 3)


def _count_token_single_message(message: Message) -> int:
    # measured on `vllm`, each new message with llama is around 6 tokens
    token_count = 6 + _count_tokens_in_str(message.content)
    if message.tool_requests is not None:
        for tool_request in message.tool_requests:
            # we assume the model generated the tool call as a json
            token_count += _count_tokens_in_str(tool_request.name) + _count_tokens_in_str(
                json.dumps(tool_request.args)
            )
    return token_count


def _count_tokens_for_tools(tools: Optional[List[Tool]]) -> int:
    from wayflowcore._utils.formatting import _to_openai_function_dict

    token_count = 0
    for tool in tools or []:
        # we assume the model was presented the tools with the openai function format
        token_count += _count_tokens_in_str(json.dumps(_to_openai_function_dict(tool)))

    return token_count


def _get_approximate_num_token_from_wayflowcore_message(message: Message) -> int:
    return _count_token_single_message(message)


def _get_approximate_num_token_from_wayflowcore_list_of_messages(
    messages: List[Message], tools: Optional[List[Tool]] = None
) -> int:
    # measured on `vllm`, initial system prompt for llama is around 20 tokens
    return (
        30
        + sum([_count_token_single_message(message) for message in messages])
        + _count_tokens_for_tools(tools)
    )
