# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Queue-based worker process for the local Python execution backend."""

from __future__ import annotations

import contextlib
import io
import json
import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from multiprocessing.queues import Queue
from typing import cast

from wayflowcore._utils.notgiven import NOT_GIVEN, NotGiven
from wayflowcore.codeserver.backend import PythonExecutionPolicy
from wayflowcore.codeserver.models import JsonValue

WorkerCommand = dict[str, object]
WorkerMessage = dict[str, object]


class _OutputCapture(io.TextIOBase):
    """Bounded text capture for one execution stream."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._parts: list[str] = []
        self._size = 0
        self.truncated = False

    def writable(self) -> bool:
        """Report that text may be written to this capture."""
        return True

    def write(self, text: str) -> int:
        """Capture text up to the configured limit."""
        available = self._limit - self._size
        if available > 0:
            captured = text[:available]
            self._parts.append(captured)
            self._size += len(captured)
        if len(text) > available:
            self.truncated = True
        return len(text)

    @property
    def text(self) -> str:
        """Return the captured text."""
        return "".join(self._parts)


@dataclass
class _HostBridge:
    """Object injected into a session namespace for host callbacks."""

    command_queue: Queue[object]
    result_queue: Queue[object]
    stdout: _OutputCapture
    stderr: _OutputCapture

    def tool_execution(self, name: str, /, **arguments: JsonValue) -> JsonValue:
        """Request one host tool execution and wait for its matching response."""
        request_id = f"callback_{uuid.uuid4().hex}"
        self.result_queue.put(
            {
                "type": "host_request",
                "request_id": request_id,
                "request_type": "tool_execution",
                "name": name,
                "arguments": arguments,
                "stdout": self.stdout.text,
                "stderr": self.stderr.text,
            }
        )

        while True:
            command = _require_command(self.command_queue.get())
            if command.get("type") == "close":
                raise RuntimeError("Session closed while waiting for a host callback response.")
            if command.get("type") != "callback_response":
                raise RuntimeError("Expected a host callback response.")
            if command.get("request_id") != request_id:
                raise RuntimeError("Host callback response did not match the pending request.")
            return _json_value(command.get("result"))


def run_script(source_code: str, namespace: dict[str, object]) -> None:
    """Execute script source code in a worker namespace."""
    compiled = compile(source_code, filename="<wayflow_code>", mode="exec")
    exec(compiled, namespace, namespace)  # nosec B102 - intentional code executor behavior.


def run_function(
    source_code: str,
    function_name: str,
    arguments: Mapping[str, JsonValue],
    namespace: dict[str, object],
) -> object:
    """Define source code and invoke one named function in a worker namespace."""
    run_script(source_code, namespace)
    function = namespace.get(function_name)
    if not callable(function):
        raise ValueError(f"Function '{function_name}' is not defined.")
    return function(**arguments)


def execute_command(
    command: WorkerCommand,
    *,
    namespace: dict[str, object],
    command_queue: Queue[object],
    result_queue: Queue[object],
) -> bool:
    """Execute one worker command and return whether the loop should continue."""
    command_type = command.get("type")
    if command_type == "close":
        return False
    if command_type != "run":
        _emit_failed(result_queue, "Unsupported worker command.")
        return True

    source_code = _required_str(command, "source_code")
    mode = _required_str(command, "mode")
    max_stdout_chars = _required_non_negative_int(command, "max_stdout_chars")
    max_stderr_chars = _required_non_negative_int(command, "max_stderr_chars")
    stdout = _OutputCapture(max_stdout_chars)
    stderr = _OutputCapture(max_stderr_chars)

    if command.get("host_interactions_enabled") is True:
        namespace["host"] = _HostBridge(command_queue, result_queue, stdout, stderr)
    else:
        namespace.pop("host", None)

    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):  # type: ignore[type-var]
            if mode == "script":
                run_script(source_code, namespace)
                result_queue.put(_completed_message(stdout, stderr))
            elif mode == "function":
                function_name = _required_str(command, "function_name")
                arguments = _json_object(command.get("arguments"), "arguments")
                result = run_function(source_code, function_name, arguments, namespace)
                result_queue.put(
                    _completed_message(stdout, stderr, structured_content=_json_value(result))
                )
            else:
                raise ValueError("Execution mode must be 'script' or 'function'.")
    except Exception as exc:  # noqa: BLE001 - user-code boundary.
        _emit_failed(result_queue, str(exc) or type(exc).__name__, stdout, stderr)
    return True


def worker_main(
    command_queue: Queue[object],
    result_queue: Queue[object],
    policy: PythonExecutionPolicy | None,
    *,
    session_mode: bool,
) -> None:
    """Run the queue-based local Python worker command loop."""
    if os.name == "posix":
        os.setsid()

    namespace = {} if policy is None else policy.build_namespace()
    while True:
        command = _require_command(command_queue.get())
        if not execute_command(
            command,
            namespace=namespace,
            command_queue=command_queue,
            result_queue=result_queue,
        ):
            return
        if not session_mode:
            return


def _completed_message(
    stdout: _OutputCapture,
    stderr: _OutputCapture,
    *,
    structured_content: JsonValue | NotGiven = NOT_GIVEN,
) -> WorkerMessage:
    """Create one completed worker message."""
    message: WorkerMessage = {
        "type": "completed",
        "stdout": stdout.text,
        "stderr": stderr.text,
        "stdout_truncated": stdout.truncated,
        "stderr_truncated": stderr.truncated,
    }
    if structured_content is not NOT_GIVEN:
        message["structured_content"] = structured_content
    return message


def _emit_failed(
    result_queue: Queue[object],
    error: str,
    stdout: _OutputCapture | None = None,
    stderr: _OutputCapture | None = None,
) -> None:
    """Send one normalized worker failure message."""
    result_queue.put(
        {
            "type": "failed",
            "error": error,
            "stdout": "" if stdout is None else stdout.text,
            "stderr": "" if stderr is None else stderr.text,
            "stdout_truncated": False if stdout is None else stdout.truncated,
            "stderr_truncated": False if stderr is None else stderr.truncated,
        }
    )


def _require_command(value: object) -> WorkerCommand:
    """Validate a queue value as a worker command."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise RuntimeError("Worker command must be an object with string keys.")
    return cast(WorkerCommand, value)


def _required_str(command: Mapping[str, object], name: str) -> str:
    """Return one required string field from a worker command."""
    value = command.get(name)
    if not isinstance(value, str):
        raise ValueError(f"Worker command field '{name}' must be a string.")
    return value


def _required_non_negative_int(command: Mapping[str, object], name: str) -> int:
    """Return one required non-negative integer field from a worker command."""
    value = command.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"Worker command field '{name}' must be a non-negative integer.")
    return value


def _json_object(value: object, name: str) -> dict[str, JsonValue]:
    """Validate an object as a JSON object."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"Worker command field '{name}' must be an object.")
    return {key: _json_value(item) for key, item in value.items()}


def _json_value(value: object) -> JsonValue:
    """Return a JSON-compatible copy of one value or raise ``ValueError``."""
    try:
        encoded = json.dumps(value, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Value is not JSON-compatible.") from exc
    return cast(JsonValue, json.loads(encoded))


def main() -> None:
    """Reject direct module execution without worker queue arguments."""
    raise SystemExit("This module is launched by LocalPythonBackend through multiprocessing.")


if __name__ == "__main__":
    main()
