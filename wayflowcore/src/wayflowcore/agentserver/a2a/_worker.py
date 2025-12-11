# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from typing import Any, cast

from fasta2a import Worker
from fasta2a.schema import Artifact, Message, TaskIdParams, TaskSendParams

from wayflowcore.conversation import Conversation
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.flow import Flow as WayflowFlow
from wayflowcore.steps import InputMessageStep

from ._converter import (
    _convert_a2a_messages_to_wayflow_messages,
    _convert_wayflow_messages_to_a2a_messages,
)
from ._storage import A2AStorage
from ._task_manager import TaskNotifier

Context = Any
"""The shape of the context stored in the storage (is not used in our case but is added to be compatible with fasta2a's Worker class"""


@dataclass
class A2AAgentWorker(Worker[Context]):  # type: ignore[misc]
    """A worker that uses a WayFlow conversational component to execute tasks"""

    assistant: ConversationalComponent
    storage: A2AStorage
    notifier: TaskNotifier

    async def run_task(self, params: TaskSendParams) -> None:
        task = await self.storage.load_task(params["id"])
        if task is None:
            raise ValueError(f'Task {params["id"]} not found')
        if task["status"]["state"] not in ["submitted"]:
            raise ValueError(
                f'Task {params["id"]} has already been processed (state: {task["status"]["state"]})'
            )

        await self.storage.update_task(task_id=task["id"], state="working")

        prioritze_task = params.get("metadata", {}).get("prioritize_task", False)
        tools_dict = self.assistant._referenced_tools_dict()
        if prioritze_task:
            # Load the task's conversation
            # Task conversation will have UserMessageRequestStatus status since the task is guaranteed to have "input-required" state.
            conversation = await self.storage.load_task_conversation(
                task_id=task["id"],
                tools_dict=tools_dict,
            )
        else:
            # Load the context (i.e the conversation of the latest task in the context)
            # Context conversation may have FinishStatus since the latest task may be completed
            conversation = await self.storage.load_context_conversation(
                context_id=task["context_id"],
                tools_dict=tools_dict,
            )

        needs_new_conv = conversation is None or not isinstance(
            conversation.status, UserMessageRequestStatus
        )

        if needs_new_conv:
            # A new task/context -> need to create a new conversation
            # Otherwise, if last conversation does not have UserMessageRequestStatus -> create new conversation with last messages
            messages = None if conversation is None else conversation.message_list
            conversation = self.assistant.start_conversation(messages=messages)

            if isinstance(self.assistant, WayflowFlow) and any(
                isinstance(step, InputMessageStep) for step in self.assistant.steps.values()
            ):
                await conversation.execute_async()

        conversation = cast(Conversation, conversation)  # make mypy happy

        # Note: do not need to load the task history because it is already saved in the conversation
        a2a_input_message = params["message"]
        wayflow_input_message = _convert_a2a_messages_to_wayflow_messages([a2a_input_message])[0]
        conversation.append_message(wayflow_input_message)

        try:
            status = await conversation.execute_async()

            new_wayflow_messages = []
            for message in reversed(conversation.get_messages()):
                if message.role == "assistant":
                    new_wayflow_messages.append(message)
                else:  # user message
                    # Skip user messages as they are already in the task history
                    break
            new_wayflow_messages.reverse()

            new_a2a_messages = _convert_wayflow_messages_to_a2a_messages(new_wayflow_messages)
        except Exception:
            await self.storage.update_task(task["id"], state="failed")
            # Notify the task manager that the task failed in case it is waiting for the result (blocking mode)
            await self.notifier.notify(task["id"])
            raise
        else:
            # Update task
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
            )

            # Save conversation
            await self.storage.update_task_conversation(
                context_id=task["context_id"], task_id=task["id"], conv=conversation
            )

            # Notify the task manager that the task finished in case it is waiting for the result (blocking mode)
            await self.notifier.notify(task["id"])

    async def cancel_task(self, params: TaskIdParams) -> None:
        raise NotImplementedError()

    def build_message_history(self, history: list[Message]) -> list[Any]:
        raise NotImplementedError()

    def build_artifacts(self, result: Any) -> list[Artifact]:
        raise NotImplementedError()
