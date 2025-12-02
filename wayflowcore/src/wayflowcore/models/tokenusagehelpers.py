# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
from typing import TYPE_CHECKING, List, Optional

from wayflowcore.messagelist import ImageContent, TextContent

if TYPE_CHECKING:
    from wayflowcore.messagelist import Message, MessageContent
    from wayflowcore.tools import Tool

import logging

logger = logging.getLogger(__name__)


class CountTokensHeuristics:
    # Constants for image dimension limits
    MAX_IMAGE_WIDTH = 2048
    MAX_IMAGE_HEIGHT = 2048
    IMAGE_PATCH_SIZE = 16

    @staticmethod
    def tokens_in_chars(nchars: int) -> int:
        """
        Returns an estimate of the number of tokens corresponding to `nchars` chars.
        """
        return (nchars + 3) // 4

    @staticmethod
    def _tokens_in_image_with_dims(width: int, height: int) -> int:
        """
        Returns an estimate of the number of tokens corresponding to a `width`x`height` image.
        This estimate is intentionally over-estimating the number of tokens.
        """
        max_width = CountTokensHeuristics.MAX_IMAGE_WIDTH
        max_height = CountTokensHeuristics.MAX_IMAGE_HEIGHT
        patch_size = CountTokensHeuristics.IMAGE_PATCH_SIZE

        # Clamp the input width and height to the maximum allowed
        width = min(width, max_width)
        height = min(height, max_height)

        # Calculate number of patches (tokens) along each dimension, rounding up
        patches_w = (width + patch_size - 1) // patch_size
        patches_h = (height + patch_size - 1) // patch_size

        # Each patch corresponds to a token
        token_count = patches_w * patches_h

        return token_count

    @staticmethod
    def _tokens_in_image(image: "ImageContent") -> int:
        """
        Returns an estimate of the number of tokens corresponding to an image.
        Currently assumes the maximal possible image size. Next step includes getting the exact image size using PIL.
        """
        # TODO replace with actual image size after adding PIL as a dependency
        width = CountTokensHeuristics.MAX_IMAGE_WIDTH
        height = CountTokensHeuristics.MAX_IMAGE_HEIGHT
        return CountTokensHeuristics._tokens_in_image_with_dims(width, height)

    @staticmethod
    def tokens_in_messagecontents(contents: List["MessageContent"]) -> int:
        ntokens = 0
        for content in contents:
            if isinstance(content, TextContent):
                ntokens += CountTokensHeuristics.tokens_in_chars(len(content.content))
            if isinstance(content, ImageContent):
                ntokens += CountTokensHeuristics._tokens_in_image(content)
        return ntokens


def _count_tokens_in_str(s: str) -> int:
    return CountTokensHeuristics.tokens_in_chars(len(s))


def _count_token_single_message(message: "Message") -> int:
    # measured on `vllm`, each new message with llama is around 6 tokens
    token_count = 6 + _count_tokens_in_str(message.content)
    token_count += sum(
        [
            CountTokensHeuristics._tokens_in_image(c)
            for c in message.contents
            if isinstance(c, ImageContent)
        ]
    )
    if message.tool_requests is not None:
        for tool_request in message.tool_requests:
            # we assume the model generated the tool call as a json
            token_count += _count_tokens_in_str(tool_request.name) + _count_tokens_in_str(
                json.dumps(tool_request.args)
            )
    return token_count


def _count_tokens_for_tools(tools: Optional[List["Tool"]]) -> int:
    from wayflowcore._utils.formatting import _to_openai_function_dict

    token_count = 0
    for tool in tools or []:
        # we assume the model was presented the tools with the openai function format
        token_count += _count_tokens_in_str(json.dumps(_to_openai_function_dict(tool)))

    return token_count


def _get_approximate_num_token_from_wayflowcore_message(message: "Message") -> int:
    return _count_token_single_message(message)


def _get_approximate_num_reasoning_tokens_from_wayflowcore_message(message: "Message") -> int:
    """Count approximate reasoning tokens from WayFlow message. This is a very rough estimate, most models with summaries will return their exact token counts anyway"""
    if message._reasoning_content:
        total_count = 0
        if "content" in message._reasoning_content and len(
            message._reasoning_content["content"][0]["text"]
        ):
            total_count += _count_tokens_in_str(message._reasoning_content["content"][0]["text"])

        elif "encrypted_content" in message._reasoning_content and len(
            message._reasoning_content["encrypted_content"]
        ):
            total_count += _count_tokens_in_str(message._reasoning_content["encrypted_content"])

        elif "summary" in message._reasoning_content and len(
            message._reasoning_content["summary"][0]["text"]
        ):
            total_count += _count_tokens_in_str(message._reasoning_content["summary"][0]["text"])

        return total_count

    return 0


def _get_approximate_num_token_from_wayflowcore_list_of_messages(
    messages: List["Message"], tools: Optional[List["Tool"]] = None
) -> int:
    # measured on `vllm`, initial system prompt for llama is around 20 tokens
    return (
        30
        + sum([_count_token_single_message(message) for message in messages])
        + _count_tokens_for_tools(tools)
    )
