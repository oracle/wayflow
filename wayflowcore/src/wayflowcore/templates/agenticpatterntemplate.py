# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
from textwrap import shorten
from typing import List

from wayflowcore.messagelist import Message, TextContent
from wayflowcore.transforms import MessageTransform

_MAX_CHAR_TOOL_RESULT_HEADER = 140
"""Max number of characters in the message header when formatting a Tool Result"""


class ToolRequestAndCallsTransform(MessageTransform):
    def __call__(self, messages: List["Message"]) -> List["Message"]:
        """
        Format tool requests as agent messages and tool results as user messages so the
        conversation remains a simple user/agent sequence.
        """
        from wayflowcore import Message, MessageType

        tool_request_by_id = {
            tool_request.tool_request_id: tool_request
            for msg in messages
            if msg.message_type is MessageType.TOOL_REQUEST and msg.tool_requests
            for tool_request in msg.tool_requests
        }

        formatted_messages = []
        for message in messages:
            if message.message_type == MessageType.TOOL_RESULT:
                if not message.tool_result:
                    raise ValueError(f"TOOL_RESULT message must contain tool_result: {message}")
                tool_request_id = message.tool_result.tool_request_id
                tool_request = tool_request_by_id.get(tool_request_id)
                if not tool_request:
                    raise ValueError(
                        f"Could not find matching ToolRequest for TOOL_RESULT with id: {tool_request_id}"
                    )

                message_header_tool_info = shorten(
                    f"name={tool_request.name}, parameters={tool_request.args}",
                    width=_MAX_CHAR_TOOL_RESULT_HEADER,
                    placeholder=" ...}",
                )
                formatted_messages.append(
                    Message(
                        content=(
                            f"--- TOOL RESULT: {message_header_tool_info} ---\n"
                            f"{message.tool_result.content!r}"
                        ),
                        message_type=MessageType.USER,
                    )
                )
            elif message.message_type == MessageType.TOOL_REQUEST:
                if not message.tool_requests:
                    raise ValueError(
                        "Message is of type TOOL_REQUEST but has no tool_requests. This should be reported."
                    )

                formatted_tool_calls = "\n".join(
                    json.dumps({"name": tool_request.name, "parameters": tool_request.args})
                    for tool_request in message.tool_requests
                )

                header = f"--- MESSAGE: From: {message.sender} ---\n"
                content = (
                    message.content
                    if message.content.startswith(header)
                    else f"{header}{message.content}"
                )
                formatted_messages.append(
                    Message(
                        content=(
                            f"{content}\n{formatted_tool_calls}"
                            if formatted_tool_calls not in content
                            else f"{content}"
                        ),
                        message_type=MessageType.AGENT,
                    )
                )
            elif message.message_type == MessageType.SYSTEM:
                formatted_messages.append(message)
            else:
                message_copy = message.copy()
                if message_copy.role == "user" and not message_copy.sender:
                    message_copy.sender = "HUMAN USER"
                message_copy.contents.insert(
                    0, TextContent(f"--- MESSAGE: From: {message_copy.sender} ---\n")
                )
                formatted_messages.append(message_copy)
        return formatted_messages
