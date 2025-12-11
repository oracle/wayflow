# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations as _annotations

import uuid
from contextlib import AsyncExitStack, nullcontext
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import anyio
from fasta2a.broker import Broker
from fasta2a.schema import (
    CancelTaskRequest,
    CancelTaskResponse,
    GetTaskPushNotificationRequest,
    GetTaskPushNotificationResponse,
    GetTaskRequest,
    GetTaskResponse,
    InternalError,
    InvalidParamsError,
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

_BLOCKING_REQUESTS_MAX_TIME_SECONDS = 10


class TaskNotifier:
    """An async notifier that lets a task manager wait for tasks to finish and lets tasks signal when they are done."""

    def __init__(self) -> None:
        self._events: Dict[str, anyio.Event] = {}
        self._lock = anyio.Lock()

    async def wait_for(self, task_id: str, *, timeout: Optional[float] = None) -> None:
        async with self._lock:
            ev = self._events.get(task_id)
            if ev is None:
                ev = anyio.Event()
                self._events[task_id] = ev
        with anyio.fail_after(timeout) if timeout else nullcontext():
            await ev.wait()

    async def notify(self, task_id: str) -> None:
        async with self._lock:
            ev = self._events.get(task_id)
            if ev is None:
                ev = anyio.Event()
                self._events[task_id] = ev
            ev.set()


@dataclass
class TaskManager:
    """A task manager responsible for managing tasks."""

    broker: Broker
    storage: Storage[Any]
    notifier: TaskNotifier

    _aexit_stack: AsyncExitStack | None = field(default=None, init=False)

    async def __aenter__(self) -> "TaskManager":
        self._aexit_stack = AsyncExitStack()
        await self._aexit_stack.__aenter__()
        await self._aexit_stack.enter_async_context(self.broker)

        return self

    @property
    def is_running(self) -> bool:
        return self._aexit_stack is not None

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
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

        task_id = message.get("task_id", None)
        context_id = message.get("context_id", str(uuid.uuid4()))

        metadata = {}
        if not task_id:
            # Create a new task
            task = await self.storage.submit_task(context_id, message)
        else:
            # Client wants to continue an existing task
            task = await self.storage.load_task(task_id=task_id, history_length=history_length)
            if not task:
                # Task is not found
                return SendMessageResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error=InvalidParamsError(
                        code=-32602,
                        message="Invalid parameters",
                        data={
                            "parameter": "task_id",
                            "value": task_id,
                            "reason": "Task id not found",
                        },
                    ),
                )
            elif task["status"]["state"] != "input-required":
                # Task is already completed -> cannot continue
                return SendMessageResponse(
                    jsonrpc="2.0",
                    id=request_id,
                    error=InvalidParamsError(
                        code=-32602,
                        message="Invalid parameters",
                        data={
                            "parameter": "task_id",
                            "value": task_id,
                            "reason": "Cannot continue a completed task",
                        },
                    ),
                )
            task = await self.storage.update_task(task_id=task_id, state="submitted")

            # Prioritize to continue from the give task's conversation rather than from the context
            metadata["prioritize_task"] = True

        broker_params: TaskSendParams = {
            "id": task["id"],
            "context_id": context_id,
            "message": message,
            "metadata": metadata,
        }

        if history_length is not None:
            broker_params["history_length"] = history_length

        await self.broker.run_task(broker_params)

        blocking = config.get("blocking", False)
        if not blocking:
            # Send response notifying task is submitted
            return SendMessageResponse(jsonrpc="2.0", id=request_id, result=task)

        # Otherwise, wait until the task is finished
        try:
            await self.notifier.wait_for(task["id"], timeout=_BLOCKING_REQUESTS_MAX_TIME_SECONDS)
            finished_task = await self.storage.load_task(task["id"])

            return SendMessageResponse(jsonrpc="2.0", id=request_id, result=finished_task)
        except TimeoutError:
            return SendMessageResponse(
                jsonrpc="2.0",
                id=request_id,
                error=InternalError(
                    code=-32603, message="Internal error", data={"reason": "Time out error"}
                ),
            )

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
