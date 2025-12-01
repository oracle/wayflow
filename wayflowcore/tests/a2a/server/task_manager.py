# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations as _annotations

import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

from fasta2a.broker import Broker
from fasta2a.schema import (
    CancelTaskRequest,
    CancelTaskResponse,
    GetTaskPushNotificationRequest,
    GetTaskPushNotificationResponse,
    GetTaskRequest,
    GetTaskResponse,
    ResubscribeTaskRequest,
    SendMessageRequest,
    SendMessageResponse,
    SetTaskPushNotificationRequest,
    SetTaskPushNotificationResponse,
    StreamMessageRequest,
    TaskNotFoundError,
    TaskSendParams,
)
from fasta2a.storage import Storage


@dataclass
class TaskManager:
    """A task manager responsible for managing tasks."""

    broker: Broker
    storage: Storage[Any]

    _aexit_stack: AsyncExitStack | None = field(default=None, init=False)

    async def __aenter__(self):
        self._aexit_stack = AsyncExitStack()
        await self._aexit_stack.__aenter__()
        await self._aexit_stack.enter_async_context(self.broker)

        return self

    @property
    def is_running(self) -> bool:
        return self._aexit_stack is not None

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any):
        if self._aexit_stack is None:
            raise RuntimeError("TaskManager was not properly initialized.")
        await self._aexit_stack.__aexit__(exc_type, exc_value, traceback)
        self._aexit_stack = None

    async def send_message(self, request: SendMessageRequest) -> SendMessageResponse:
        """Send a message using the A2A v0.2.3 protocol."""
        request_id = request["id"]

        config = request["params"].get("configuration", {})
        history_length = config.get("history_length")

        message = request["params"]["message"]
        context_id = message.get("context_id", str(uuid.uuid4()))
        task_id = message.get("task_id", None)

        if not task_id:
            task = await self.storage.submit_task(context_id, message)
        else:
            task = await self.storage.load_task(task_id=task_id, history_length=history_length)
            await self.storage.update_task(
                task["id"],
                state="submitted",
                new_messages=[message],
            )

        broker_params: TaskSendParams = {
            "id": task["id"],
            "context_id": context_id,
            "message": message,
        }

        if history_length is not None:
            broker_params["history_length"] = history_length

        await self.broker.run_task(broker_params)
        return SendMessageResponse(jsonrpc="2.0", id=request_id, result=task)

    async def get_task(self, request: GetTaskRequest) -> GetTaskResponse:
        """Get a task, and return it to the client.

        No further actions are needed here.
        """
        task_id = request["params"]["id"]
        history_length = request["params"].get("history_length")
        task = await self.storage.load_task(task_id, history_length)
        if task is None:
            return GetTaskResponse(
                jsonrpc="2.0",
                id=request["id"],
                error=TaskNotFoundError(code=-32001, message="Task not found"),
            )
        return GetTaskResponse(jsonrpc="2.0", id=request["id"], result=task)

    async def cancel_task(self, request: CancelTaskRequest) -> CancelTaskResponse:
        await self.broker.cancel_task(request["params"])
        task = await self.storage.load_task(request["params"]["id"])
        if task is None:
            return CancelTaskResponse(
                jsonrpc="2.0",
                id=request["id"],
                error=TaskNotFoundError(code=-32001, message="Task not found"),
            )
        return CancelTaskResponse(jsonrpc="2.0", id=request["id"], result=task)

    async def stream_message(self, request: StreamMessageRequest) -> None:
        """Stream messages using Server-Sent Events."""
        raise NotImplementedError("message/stream method is not implemented yet.")

    async def set_task_push_notification(
        self, request: SetTaskPushNotificationRequest
    ) -> SetTaskPushNotificationResponse:
        raise NotImplementedError("SetTaskPushNotification is not implemented yet.")

    async def get_task_push_notification(
        self, request: GetTaskPushNotificationRequest
    ) -> GetTaskPushNotificationResponse:
        raise NotImplementedError("GetTaskPushNotification is not implemented yet.")

    async def resubscribe_task(self, request: ResubscribeTaskRequest) -> None:
        raise NotImplementedError("Resubscribe is not implemented yet.")
