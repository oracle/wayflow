# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Sequence

from httpx import Timeout

from wayflowcore._utils.lazy_loader import LazyLoader
from wayflowcore.conversation import Conversation
from wayflowcore.executors._executionstate import ConversationExecutionState
from wayflowcore.executors._executor import ConversationExecutor
from wayflowcore.executors.executionstatus import ExecutionStatus, UserMessageRequestStatus
from wayflowcore.executors.interrupts import ExecutionInterrupt
from wayflowcore.messagelist import Message as WayflowMessage
from wayflowcore.messagelist import MessageContent, TextContent

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    # Important: do not move this import out of the TYPE_CHECKING block so long as `fasta2a` is an optional dependency.
    # Otherwise, importing the module when they are not installed would lead to an import error.
    import fasta2a
else:
    fasta2a = LazyLoader("fasta2a")

DEFAULT_RESPONSE = "Hi! How can I help you?"


@dataclass
class A2AAgentState(ConversationExecutionState):
    last_message_idx: int


class A2AAgentExecutor(ConversationExecutor):
    @staticmethod
    async def execute_async(
        conversation: "Conversation",
        execution_interrupts: Optional[Sequence["ExecutionInterrupt"]] = None,
    ) -> ExecutionStatus:
        from fasta2a.client import A2AClient

        from wayflowcore.executors._a2aagentconversation import A2AAgentConversation

        if not isinstance(conversation, A2AAgentConversation):
            raise ValueError(f"Should be an A2A Client Agent conversation, but was {conversation}")

        component = conversation.component
        agent_state = conversation.state
        all_messages = conversation.get_messages()

        new_user_messages = (
            all_messages[agent_state.last_message_idx + 1 :]
            if agent_state.last_message_idx != -1
            else all_messages
        )

        if not new_user_messages:
            return UserMessageRequestStatus(
                message=get_last_message(conversation), _conversation_id=conversation.id
            )

        a2a_messages = _convert_wayflow_messages_to_a2a_messages(
            new_user_messages, agent_state.last_message_idx + 1, conversation.id
        )

        http_client = component._http_factory(
            headers=component.connection_config.headers,
            timeout=Timeout(component.connection_config.timeout),
        )
        try:
            # Send Messages
            task_ids = []
            a2aclient = A2AClient(component.agent_url, http_client)
            for msg in a2a_messages:
                response = await a2aclient.send_message(msg)
                if (
                    "result" in response
                    and "history" in response["result"]
                    and response["result"]["history"]
                    and "task_id" in response["result"]["history"][-1]
                ):
                    task_id = response["result"]["history"][-1]["task_id"]
                else:
                    raise RuntimeError("Missing `task_id` in server response for polling.")
                task_ids.append(task_id)
                agent_state.last_message_idx += 1

            # Get the contents of the replies via polling
            responses = []
            for task_id in task_ids:
                task_info_response = await poll_task(
                    a2aclient,
                    task_id,
                    timeout=component.session_parameters.timeout,
                    poll_interval=component.session_parameters.poll_interval,
                    max_retries=component.session_parameters.max_retries,
                )
                responses.append(task_info_response)

            converted_messages = _convert_a2a_messages_to_wayflow_messages(responses)
            for msg in converted_messages:
                agent_state.last_message_idx += 1
                conversation.append_message(msg)

            return UserMessageRequestStatus(
                message=get_last_message(conversation), _conversation_id=conversation.id
            )
        finally:
            await http_client.aclose()


def get_last_message(conversation: Conversation) -> WayflowMessage:
    last_message = conversation.get_last_message()
    if last_message is None:
        return WayflowMessage(DEFAULT_RESPONSE, role="assistant")
    return last_message


def _convert_a2a_parts_to_wayflow_contents(
    parts: list["fasta2a.schema.Part"],
) -> list[MessageContent]:
    contents: list[MessageContent] = []
    for part in parts:
        if part["kind"] == "text" or part["kind"] == "data":
            # `text` contains normal text and `data` contains json/dict
            contents.append(TextContent(str(part[part["kind"]])))
        else:
            # only `file` part is not supported
            raise NotImplementedError(f"{part['kind']} part is not supported yet")
    return contents


def _convert_wayflow_messages_to_a2a_messages(
    messages: list[WayflowMessage], message_id: int, context_id: str
) -> list["fasta2a.schema.Message"]:
    from fasta2a.schema import Message, TextPart

    a2a_messages = []
    for message in messages:
        parts = []
        for chunk in message.contents:
            if isinstance(chunk, TextContent):
                parts.append(TextPart(text=chunk.content, kind="text"))
            else:
                raise ValueError(f"{type(chunk)} is not supported")
        a2a_messages.append(
            Message(
                role=message.role if message.role == "user" else "agent",
                parts=parts,
                kind="message",
                message_id=str(message_id),
                context_id=context_id,
            )
        )
    return a2a_messages


def _convert_a2a_messages_to_wayflow_messages(
    responses: list["fasta2a.schema.GetTaskResponse"],
) -> list[WayflowMessage]:
    converted_messages = []
    for resp in responses:
        if "result" in resp and "history" in resp["result"] and resp["result"]["history"]:
            # index 0 has the user message already, each task should have its own history
            for entry in resp["result"]["history"][1:]:
                if "parts" in entry and "role" in entry:
                    a2a_msg_parts = entry["parts"]
                    contents = _convert_a2a_parts_to_wayflow_contents(a2a_msg_parts)
                    msg = WayflowMessage(
                        role=(entry["role"] if entry["role"] == "user" else "assistant"),
                        contents=contents,
                    )
                    converted_messages.append(msg)
        else:
            raise RuntimeError(
                "Unable to parse server response due to missing `result` or `history` data."
            )
    return converted_messages


async def poll_task(
    a2aclient: "fasta2a.client.A2AClient",
    task_id: str,
    timeout: float = 60.0,
    poll_interval: float = 2.0,
    max_retries: int = 5,
) -> "fasta2a.schema.GetTaskResponse":
    start_time = time.time()
    retry_count = 0
    while time.time() - start_time < timeout:
        try:
            response = await a2aclient.get_task(task_id)
            logger.debug(f"Polling task {task_id}, attempt {retry_count + 1}/{max_retries + 1}")
            if "result" in response and "status" in response["result"]:
                state = response["result"]["status"]["state"]
                logger.debug(f"Task {task_id} state: {state}")
                if state in ["completed", "input-required"]:
                    logger.debug(f"Task {task_id} completed successfully.")
                    return response
                elif state in ["failed", "canceled", "rejected"]:
                    error_msg = f"Task {task_id} ended with state: {state}"
                    logger.debug(error_msg)
                    raise RuntimeError(error_msg)
            else:
                logger.debug(f"Unexpected response format for task {task_id}: {response}")
            await asyncio.sleep(poll_interval)
            retry_count = 0
        except Exception as e:
            retry_count += 1
            error_msg = (
                f"Error polling task {task_id}: {str(e)} (Retry {retry_count}/{max_retries})"
            )
            logger.error(error_msg)
            if retry_count > max_retries:
                raise ConnectionError(
                    f"Failed to poll task {task_id} after {max_retries} retries: {str(e)}"
                )
            await asyncio.sleep(poll_interval)
    raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")
