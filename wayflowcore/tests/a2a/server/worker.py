# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from typing import Any

from _converter import (
    _convert_a2a_messages_to_wayflow_messages,
    _convert_wayflow_messages_to_a2a_messages,
)
from fasta2a import Worker
from fasta2a.schema import Artifact, Message, TaskIdParams, TaskSendParams

from wayflowcore.agent import Agent as WayflowAgent
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)

Context = list[Message]
"""The shape of the context you store in the storage."""


@dataclass
class A2AAgentWorker(Worker[Context]):
    """A worker that uses an Wayflow Agent to execute tasks"""

    agent: WayflowAgent
    message_id: int = 1

    async def run_task(self, params: TaskSendParams) -> None:
        task = await self.storage.load_task(params["id"])
        if task is None:
            raise ValueError(f'Task {params["id"]} not found')
        if task["status"]["state"] not in ["submitted", "input-required"]:
            raise ValueError(
                f'Task {params["id"]} has already been processed (state: {task["status"]["state"]})'
            )

        await self.storage.update_task(task["id"], state="working")

        # Context contains Wayflow Messages from previous tasks (not the current task because the current task is just created)
        context = await self.storage.load_context(task["context_id"]) or []

        # Note: do not need to load the task history because it is already included in the context
        # Another approach can be consider depending on the logic we want: filter out the messages of this task + append the task history
        new_message = params["message"]
        context.extend(_convert_a2a_messages_to_wayflow_messages([new_message]))

        try:
            conv = self.agent.start_conversation(messages=context)
            s = len(conv.get_messages())
            status = await conv.execute_async()

            await self.storage.update_context(task["context_id"], conv.get_messages())

            new_wayflow_messages = []
            for message in conv.get_messages()[s:]:
                # # We ignore tool requests and tool results as they are already saved in context messages
                # if message.tool_requests or message.tool_result:
                #     continue
                if message.role == "assistant":
                    new_wayflow_messages.append(message)
                else:  # user message
                    # Skip user messages as they are already in the task history
                    continue

            new_a2a_messages = _convert_wayflow_messages_to_a2a_messages(
                new_wayflow_messages, self.message_id
            )

            # TODO: do we have artifacts?
            artifacts = self.build_artifacts("123")
        except Exception:
            await self.storage.update_task(task["id"], state="failed")
            raise
        else:
            if isinstance(status, UserMessageRequestStatus) or isinstance(
                status, ToolRequestStatus
            ):
                task_state = "input-required"
            elif isinstance(status, FinishedStatus):
                task_state = "completed"

            await self.storage.update_task(
                task["id"],
                state=task_state,
                new_messages=new_a2a_messages,
                new_artifacts=artifacts,
            )

    async def cancel_task(self, params: TaskIdParams) -> None:
        pass

    def build_message_history(self, history: list[Message]) -> list[Any]: ...

    def build_artifacts(self, result: Any) -> list[Artifact]:
        return []
