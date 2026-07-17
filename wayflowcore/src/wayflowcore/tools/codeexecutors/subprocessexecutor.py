# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from multiprocessing import Process, Queue
from multiprocessing.queues import Queue as QueueType
from queue import Empty
from typing import Any, Iterator

from wayflowcore.codeserver import CodeExecutorServer
from wayflowcore.codeserver.models import (
    CodeExecutionRequest,
    CodeExecutorCapabilities,
    ExecutionResponse,
)

from .executor import CodeExecutor

_SUBPROCESS_EXECUTION_ENABLED: ContextVar[bool] = ContextVar(
    "_SUBPROCESS_EXECUTION_ENABLED", default=False
)
_DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0
_CODE_EXECUTOR_PROTOCOL_VERSION = "26.1.3"
_CODE_EXECUTOR_SERVER_NAME = "wayflow-code-server"
_MAX_LIVE_PROCESSES = 4
_MAX_QUEUED_REQUESTS = 32


def _subprocess_worker(request_queue: QueueType[str], response_queue: QueueType[str]) -> None:
    """Serve serialized Code Executor requests in a child process."""
    server = CodeExecutorServer()
    service = server.service
    while True:
        message = request_queue.get()
        if message == "shutdown":
            return
        try:
            command = _decode_command(message)
            operation = command["operation"]
            if operation == "capabilities":
                result: Any = CodeExecutorCapabilities(
                    protocol_version=_CODE_EXECUTOR_PROTOCOL_VERSION,
                    server_name=_CODE_EXECUTOR_SERVER_NAME,
                    capabilities=service.backend.get_capabilities(),
                ).model_dump_json(by_alias=True)
            elif operation == "create_execution":
                request = CodeExecutionRequest.model_validate_json(command["payload"])
                result = service.execute(request).model_dump_json(by_alias=True)
            elif operation == "get_execution":
                result = service.get_execution(command["execution_id"]).model_dump_json(
                    by_alias=True
                )
            elif operation == "cancel_execution":
                result = service.cancel_execution(command["execution_id"]).model_dump_json(
                    by_alias=True
                )
            else:
                raise ValueError(f"Unsupported subprocess operation: {operation}")
            response_queue.put(_encode_response({"result": result}))
        except Exception as exc:  # noqa: BLE001 - child process boundary.
            response_queue.put(_encode_response({"error": str(exc)}))


def _decode_command(message: str) -> dict[str, str]:
    """Decode one parent-to-worker command."""
    value = json.loads(message)
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("Subprocess command must be a JSON object.")
    return value


def _encode_response(value: object) -> str:
    """Encode one worker response."""
    return json.dumps(value)


@dataclass(kw_only=True)
class SubProcessCodeExecutor(CodeExecutor):
    """Run code through a Code Executor subprocess."""

    request_timeout_seconds: float = _DEFAULT_REQUEST_TIMEOUT_SECONDS
    """Maximum time allowed for one IPC request."""

    _request_queue: QueueType[str] | None = field(default=None, init=False, repr=False)
    _response_queue: QueueType[str] | None = field(default=None, init=False, repr=False)
    _process: Process | None = field(default=None, init=False, repr=False)

    def _ensure_worker(self) -> None:
        """Start the child server process on first use."""
        if not _SUBPROCESS_EXECUTION_ENABLED.get():
            raise RuntimeError("Subprocess code execution requires subprocess_execution_enabled().")
        if self._process is not None and self._process.is_alive():
            return
        self._request_queue = Queue()
        self._response_queue = Queue()
        self._process = Process(
            target=_subprocess_worker,
            args=(self._request_queue, self._response_queue),
        )
        self._process.start()

    def _request(self, command: dict[str, str]) -> dict[str, Any]:
        """Send one command to the child server and await its response."""
        self._ensure_worker()
        if self._request_queue is None or self._response_queue is None:
            raise RuntimeError("Subprocess worker queues are unavailable.")
        self._request_queue.put(_encode_response(command))
        try:
            response = self._response_queue.get(timeout=self.request_timeout_seconds)
        except Empty as exc:
            raise TimeoutError("Subprocess request timed out.") from exc
        value = json.loads(response)
        if not isinstance(value, dict):
            raise RuntimeError("Subprocess response must be a JSON object.")
        if "error" in value:
            raise RuntimeError(str(value["error"]))
        return value

    def _create_execution(self, request: CodeExecutionRequest) -> ExecutionResponse:
        """Submit an execution request through the subprocess worker."""
        value = self._request(
            {
                "operation": "create_execution",
                "payload": request.model_dump_json(by_alias=True),
            }
        )
        return ExecutionResponse.model_validate_json(str(value["result"]))

    def _get_execution(self, execution_id: str) -> ExecutionResponse:
        """Retrieve an execution snapshot through the subprocess worker."""
        value = self._request({"operation": "get_execution", "execution_id": execution_id})
        return ExecutionResponse.model_validate_json(str(value["result"]))

    def _cancel_execution(self, execution_id: str) -> ExecutionResponse:
        """Cancel an execution through the subprocess worker."""
        value = self._request({"operation": "cancel_execution", "execution_id": execution_id})
        return ExecutionResponse.model_validate_json(str(value["result"]))

    def _get_capabilities(self) -> dict[str, Any]:
        """Retrieve capabilities through the subprocess worker."""
        value = self._request({"operation": "capabilities"})
        return CodeExecutorCapabilities.model_validate_json(str(value["result"])).capabilities

    def close(self) -> None:
        """Stop the child server process and release its queues."""
        if self._process is None:
            return
        if self._process.is_alive() and self._request_queue is not None:
            self._request_queue.put("shutdown")
            self._process.join(timeout=self.request_timeout_seconds)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join()
        self._request_queue = None
        self._response_queue = None
        self._process = None


@contextmanager
def subprocess_execution_enabled() -> Iterator[None]:
    """
    Temporarily enable subprocess code execution in the current context.
    """
    token = _SUBPROCESS_EXECUTION_ENABLED.set(True)
    try:
        yield
    finally:
        _SUBPROCESS_EXECUTION_ENABLED.reset(token)


def configure_subprocess_executor_runtime(
    max_live_processes: int = 4,
    max_queued_requests: int = 32,
) -> None:
    """
    Configure subprocess executor worker capacity.

    Parameters
    ----------
    max_live_processes
        Maximum number of worker subprocesses that may run concurrently.
    max_queued_requests
        Maximum number of execution requests that may wait for worker capacity.
    """
    global _MAX_LIVE_PROCESSES, _MAX_QUEUED_REQUESTS
    if max_live_processes <= 0:
        raise ValueError("max_live_processes must be positive.")
    if max_queued_requests < 0:
        raise ValueError("max_queued_requests must be non-negative.")
    _MAX_LIVE_PROCESSES = max_live_processes
    _MAX_QUEUED_REQUESTS = max_queued_requests
