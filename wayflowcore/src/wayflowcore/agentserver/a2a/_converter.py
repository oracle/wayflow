# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import List, Optional, Tuple

from fasta2a.schema import DataPart, FilePart, FileWithBytes, Message, Part, TextPart

from wayflowcore.messagelist import ImageContent
from wayflowcore.messagelist import Message as WayflowMessage
from wayflowcore.messagelist import MessageContent, TextContent
from wayflowcore.tools import ToolRequest, ToolResult


def _convert_a2a_parts_to_wayflow_contents(
    parts: List[Part],
) -> Tuple[List[MessageContent], Optional[List[ToolRequest]], Optional[ToolResult]]:
    contents: List[MessageContent] = []
    tool_requests = []
    tool_result = None

    for part in parts:
        if part["kind"] == "text":
            contents.append(TextContent(part["text"]))
        elif part["kind"] == "data":
            if part["metadata"]["type"] == "tool_request":
                tool_requests.append(ToolRequest(**part["data"]))
            elif part["metadata"]["type"] == "tool_result":
                tool_result = ToolResult(**part["data"])
            else:
                raise ValueError("Data's type is wrong")
        elif part["kind"] == "file":
            contents.append(ImageContent(base64_content=part["file"]["bytes"]))
        else:
            raise NotImplementedError(f"{part['kind']} part is not supported yet")

    return contents, tool_requests if len(tool_requests) else None, tool_result


def _convert_a2a_messages_to_wayflow_messages(messages: List[Message]) -> List[WayflowMessage]:
    wayflow_messages = []
    for message in messages:
        # Convert Parts to corresponding Wayflow Message Contents
        contents, tool_requests, tool_result = _convert_a2a_parts_to_wayflow_contents(
            message["parts"]
        )
        wayflow_message = WayflowMessage(
            role=message["role"] if message["role"] == "user" else "assistant",
            contents=contents,
            tool_requests=tool_requests,
            tool_result=tool_result,
        )
        wayflow_message.id = message["message_id"]
        wayflow_messages.append(wayflow_message)

    return wayflow_messages


def _convert_wayflow_messages_to_a2a_messages(
    messages: List[WayflowMessage],
) -> List[Message]:
    a2a_messages = []

    for message in messages:
        parts = []
        for chunk in message.contents:
            if isinstance(chunk, TextContent):
                parts.append(TextPart(text=chunk.content, kind="text"))
            elif isinstance(chunk, ImageContent):
                parts.append(FilePart(file=FileWithBytes(bytes=chunk.base64_content, kind="file")))
            else:
                raise ValueError(f"{type(chunk)} is not supported")

        if message.tool_requests:
            for tool_request in message.tool_requests:
                parts.append(
                    DataPart(
                        data=tool_request.__dict__,
                        metadata={"type": "tool_request"},
                        kind="data",
                    )
                )

        if message.tool_result:
            parts.append(
                DataPart(
                    data=message.tool_result.__dict__,
                    metadata={"type": "tool_result"},
                    kind="data",
                )
            )

        a2a_messages.append(
            Message(
                role=message.role if message.role == "user" else "agent",
                parts=parts,
                message_id=message.id,
                kind="message",
            )
        )

    return a2a_messages
