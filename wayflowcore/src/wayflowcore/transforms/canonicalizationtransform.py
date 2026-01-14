# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging
from typing import List, Optional

from wayflowcore.messagelist import Message, TextContent
from wayflowcore.serialization.serializer import SerializableObject

from .transforms import MessageTransform

logger = logging.getLogger(__name__)


class CanonicalizationMessageTransform(MessageTransform, SerializableObject):
    """
    Produce a conversation shaped like:

        System   (optional, at most one, always first if present)
        User
        Assistant
        User
        Assistant
        ...

    This is useful because some models (like Gemma) require such formatting of the messages.

    * several system messages are merged
    * consecutive assistant (resp. user) messages are merged, unless there are several tool calls,
      in which case they are split and their responses are interleaving the requests.

    """

    FIRST_DUMMY_USER_TEXT = "begin"
    NEXT_DUMMY_USER_TEXT = "continue"

    def __call__(self, messages: List["Message"]) -> List["Message"]:
        system_msg: Message | None = None
        formatted_messages: List[Message] = []
        modified = False

        tool_requests_queue = []

        dummy_user_count = 0  # track number of dummy message added

        def last_role() -> str:
            return formatted_messages[-1].role if formatted_messages else ""

        def make_dummy_user() -> Message:
            nonlocal dummy_user_count
            text = (
                self.FIRST_DUMMY_USER_TEXT if dummy_user_count == 0 else self.NEXT_DUMMY_USER_TEXT
            )
            dummy_user_count += 1
            return Message(role="user", contents=[TextContent(text)])

        def merge_contents(a: Message, b: Message, prefix: Optional[str] = None) -> Message:
            extra = ([TextContent(prefix)] if prefix else []) + b.contents
            return a.copy(contents=a.contents + extra)

        def merge_assistant_tool_requests(a: Message, b: Message) -> Message:
            return a.copy(
                tool_requests=(a.tool_requests or []) + (b.tool_requests or []),
            )

        def append_user_or_merge(msg: Message) -> None:
            nonlocal modified
            if last_role() == "user":
                prev = formatted_messages[-1]
                if msg.tool_result:
                    if prev.tool_result:
                        # both messages have tool results, we
                        # need to insert an assistant message containing
                        # the associated tool call
                        formatted_messages.append(
                            find_associated_tool_request_message(msg.tool_result.tool_request_id)
                        )
                        formatted_messages.append(msg)
                        return
                    else:
                        # we add the tool result to the previous user message
                        prev = prev.copy(tool_result=msg.tool_result)

                formatted_messages[-1] = merge_contents(prev, msg)
                modified = True
            else:
                formatted_messages.append(msg)

        def append_assistant_or_merge(msg: Message) -> None:
            nonlocal modified
            if last_role() == "assistant":
                prev = formatted_messages[-1]
                merged = merge_contents(prev, msg)
                merged = merge_assistant_tool_requests(merged, msg)
                formatted_messages[-1] = merged
                modified = True
            else:
                formatted_messages.append(msg)

        def split_message_with_several_tool_requests_if_needed(msg: Message) -> Message:
            if msg.tool_requests is None or len(msg.tool_requests) <= 1:
                return msg
            kept_tool_request, remaining_tool_requests = msg.tool_requests[0], msg.tool_requests[1:]
            # these tool requests should be added later with their responses
            tool_requests_queue.extend(remaining_tool_requests)
            return msg.copy(tool_requests=[kept_tool_request])

        def find_associated_tool_request_message(tool_request_id: str) -> Message:
            for tool_request_idx in range(len(tool_requests_queue)):
                tool_request = tool_requests_queue[tool_request_idx]
                if tool_request.tool_request_id == tool_request_id:
                    tool_requests_queue.pop(tool_request_idx)
                    return Message(tool_requests=[tool_request])
            raise RuntimeError(f"No tool request with id {tool_request_id} found")

        # ensure alternation & merge message when needed
        for msg in messages:
            role = msg.role

            if role == "system":
                if system_msg is None:
                    system_msg = msg
                else:
                    system_msg = merge_contents(system_msg, msg)
                    modified = True
            elif role == "assistant":
                msg = split_message_with_several_tool_requests_if_needed(msg)

                if not formatted_messages or last_role() == "system":
                    formatted_messages.append(make_dummy_user())
                    modified = True

                append_assistant_or_merge(msg)
            elif role == "user":  # role == "user"
                append_user_or_merge(msg)
            else:
                raise ValueError(f"Unsupported role: {role}")

        # check we don't have ay remaining requests
        if len(tool_requests_queue) > 0:
            raise ValueError(
                f"Some tool requests are missing their tool results: {tool_requests_queue}"
            )

        # guarantee at least one user exists
        if not any(m.role == "user" for m in formatted_messages):
            formatted_messages.append(make_dummy_user())
            modified = True

        # add the system message
        if system_msg is not None:
            formatted_messages.insert(0, system_msg)

        if modified:
            logger.debug(
                "Message list modified to strictly alternate user/assistant: %s",
                formatted_messages,
            )

        return formatted_messages
