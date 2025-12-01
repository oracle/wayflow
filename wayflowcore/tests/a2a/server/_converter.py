# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from fasta2a.schema import DataPart, Message, Part, TextPart

from wayflowcore.messagelist import Message as WayflowMessage
from wayflowcore.messagelist import MessageContent, TextContent
from wayflowcore.tools import ToolRequest, ToolResult


def _convert_a2a_parts_to_wayflow_contents(
    parts: list[Part],
) -> tuple[list[MessageContent], list[ToolRequest], list[ToolResult]]:
    contents = []
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
        else:
            raise NotImplementedError(f"{part['kind']} part is not supported yet")

    if len(tool_requests) == 0:
        tool_requests = None

    if tool_requests and tool_result:
        raise ValueError("Cannot have tool request and tool result in the same message")

    return contents, tool_requests, tool_result


def _convert_a2a_messages_to_wayflow_messages(
    messages: list[Message],
) -> list[WayflowMessage]:
    wayflow_messages = []
    for message in messages:
        # Convert Parts to corresponding Wayflow Message Contents
        contents, tool_requests, tool_result = _convert_a2a_parts_to_wayflow_contents(
            message["parts"]
        )
        wayflow_messages.append(
            WayflowMessage(
                role=message["role"] if message["role"] == "user" else "assistant",
                contents=contents,
                tool_requests=tool_requests,
                tool_result=tool_result,
            )
        )

    return wayflow_messages


def _convert_wayflow_messages_to_a2a_messages(
    messages: list[WayflowMessage], message_id
) -> list[Message]:
    a2a_messages = []

    for message in messages:
        # Convert contents to text part
        parts = []
        print(message)
        for chunk in message.contents:
            if isinstance(chunk, TextContent):
                parts.append(TextPart(text=chunk.content, kind="text"))
            else:
                raise (f"{type(chunk)} is not supported")

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
                kind="message",
                message_id=str(message_id),
            )
        )
        message_id += 1

    return a2a_messages
