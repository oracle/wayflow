# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Shared execution logic for Code Executor configurations."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import anyio

from wayflowcore._utils.notgiven import NOT_GIVEN
from wayflowcore.codeserver.models import (
    TASK_STATUS_CANCELLED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_TIMED_OUT,
    CodeExecutionRequest,
    ExecutionResponse,
    ExecutionResult,
    FunctionInput,
    ScriptInput,
)
from wayflowcore.component import DataclassComponent

from ._utils import (
    CodeExecutionCancelled,
    CodeExecutionFailed,
    CodeExecutionRejected,
    CodeExecutionStatus,
    CodeExecutionSucceeded,
    CodeExecutionTimedOut,
)

_POLL_INTERVAL_SECONDS = 0.1


@dataclass
class CodeExecutor(DataclassComponent, ABC):
    """Class to configure a code executor."""

    timeout_seconds: float = 30.0
    """Maximum wall-clock time allowed for one execution. The default value is ``30``."""

    max_code_chars: int = 50_000
    """Maximum accepted source length in characters. The default value is ``50000``."""

    def _execute_function(
        self,
        code: str,
        language: str,
        function_name: str,
        arguments: Mapping[str, Any],
        dependencies: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> CodeExecutionStatus:
        """Run one named function defined in source code.

        Parameters
        ----------
        code:
            Source code that defines ``function_name``.
        language:
            Language identifier understood by the configured server.
        function_name:
            Name of the function to invoke from ``code``.
        arguments:
            JSON-compatible named arguments passed to the function.
        dependencies:
            Dependency declarations required by the source code.
        metadata:
            Optional JSON-compatible caller data and suggested executor
            settings. The executor separates its own settings from caller
            correlation data before calling the server.

        Returns
        -------
        CodeExecutionStatus
            A terminal execution status.
        """
        request = CodeExecutionRequest(
            language_id=language,
            input=[
                FunctionInput(
                    type="function",
                    source_code=self._validate_code(code),
                    function_name=function_name,
                    arguments=dict(arguments),
                )
            ],
            dependencies=list(dependencies),
            metadata=dict(metadata or {}),
            wait=False,
        )
        return self._run_execution_request_to_completion(request)

    async def _execute_function_async(
        self,
        code: str,
        language: str,
        function_name: str,
        arguments: Mapping[str, Any],
        dependencies: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> CodeExecutionStatus:
        """Asynchronously run one named function and poll it."""
        return await anyio.to_thread.run_sync(
            self._execute_function,
            code,
            language,
            function_name,
            arguments,
            dependencies,
            metadata,
        )

    def _execute_script(
        self,
        code: str,
        language: str,
        dependencies: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> CodeExecutionStatus:
        """Run one script.

        Parameters
        ----------
        code:
            Source code to run as a script.
        language:
            Language identifier understood by the configured server.
        dependencies:
            Dependency declarations required by the source code.
        metadata:
            Optional JSON-compatible caller data and suggested executor
            settings. Script execution may use this mapping to carry a raw
            response to an earlier host request.

        Returns
        -------
        CodeExecutionStatus
            A terminal execution status, or ``waiting_for_context`` when the
            server asks the host to do work.
        """
        request = CodeExecutionRequest(
            language_id=language,
            input=[
                ScriptInput(
                    type="script",
                    source_code=self._validate_code(code),
                )
            ],
            dependencies=list(dependencies),
            metadata=dict(metadata or {}),
            wait=False,
        )
        return self._run_execution_request_to_completion(request)

    async def _execute_script_async(
        self,
        code: str,
        language: str,
        dependencies: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> CodeExecutionStatus:
        """Asynchronously run one script."""
        return await anyio.to_thread.run_sync(
            self._execute_script,
            code,
            language,
            dependencies,
            metadata,
        )

    def get_capabilities(self) -> dict[str, Any]:
        """Return capabilities supplied by the configured execution service."""
        return self._get_capabilities()

    def _run_execution_request_to_completion(
        self, request: CodeExecutionRequest
    ) -> CodeExecutionStatus:
        """Submit one request and poll its execution until it is terminal."""
        started_at = time.monotonic()
        try:
            response = self._create_execution(request)
        except Exception as exc:  # noqa: BLE001 - transport boundary.
            return CodeExecutionRejected(
                execution_id="",
                message=str(exc),
            )

        while response.status not in {
            TASK_STATUS_COMPLETED,
            TASK_STATUS_FAILED,
            TASK_STATUS_TIMED_OUT,
            TASK_STATUS_CANCELLED,
        }:
            if time.monotonic() - started_at >= self.timeout_seconds:
                try:
                    response = self._cancel_execution(response.id)
                except Exception as exc:  # noqa: BLE001 - transport boundary.
                    return CodeExecutionTimedOut(
                        execution_id=response.id,
                        message=str(exc),
                        metadata=response.metadata,
                    )
                return CodeExecutionTimedOut(
                    execution_id=response.id,
                    message="Execution timed out.",
                    metadata=response.metadata,
                )
            time.sleep(_POLL_INTERVAL_SECONDS)
            response = self._get_execution(response.id)
        return self._response_to_status(response)

    def _validate_code(self, code: str) -> str:
        """Validate the client-side source-size limit."""
        if len(code) > self.max_code_chars:
            raise ValueError("Code exceeds the maximum accepted source length.")
        return code

    @staticmethod
    def _response_to_status(response: ExecutionResponse) -> CodeExecutionStatus:
        """Convert one protocol response into a client execution status."""
        output = response.output[0] if response.output else None
        metadata = dict(response.metadata)
        message = metadata.get("error")  # TODO: see if we need to remove this
        message_text = message if isinstance(message, str) else None

        if response.status == TASK_STATUS_COMPLETED and isinstance(output, ExecutionResult):
            result = output.structured_content
            return CodeExecutionSucceeded(
                execution_id=response.id,
                stdout=_stream_text(output, "stdout"),
                stderr=_stream_text(output, "stderr"),
                result=result if result is not NOT_GIVEN else NOT_GIVEN,
                metadata=metadata,
            )
        if response.status == TASK_STATUS_FAILED:
            return CodeExecutionFailed(
                execution_id=response.id,
                message=message_text,
                stdout=_stream_text(output, "stdout"),
                stderr=_stream_text(output, "stderr"),
                metadata=metadata,
            )
        if response.status == TASK_STATUS_TIMED_OUT:
            return CodeExecutionTimedOut(
                execution_id=response.id,
                message=message_text,
                stdout=_stream_text(output, "stdout"),
                stderr=_stream_text(output, "stderr"),
                metadata=metadata,
            )
        if response.status == TASK_STATUS_CANCELLED:
            return CodeExecutionCancelled(
                execution_id=response.id,
                message=message_text,
                stdout=_stream_text(output, "stdout"),
                stderr=_stream_text(output, "stderr"),
                metadata=metadata,
            )
        return CodeExecutionFailed(
            execution_id=response.id,
            message=f"Unsupported execution response status: {response.status}",
            metadata=metadata,
        )

    @abstractmethod
    def _create_execution(self, request: CodeExecutionRequest) -> ExecutionResponse:
        """Submit an execution request through the configured transport."""
        raise NotImplementedError

    @abstractmethod
    def _get_execution(self, execution_id: str) -> ExecutionResponse:
        """Retrieve an execution snapshot through the configured transport."""
        raise NotImplementedError

    @abstractmethod
    def _cancel_execution(self, execution_id: str) -> ExecutionResponse:
        """Cancel an execution through the configured transport."""
        raise NotImplementedError

    @abstractmethod
    def _get_capabilities(self) -> dict[str, Any]:
        """Retrieve capabilities through the configured transport."""
        raise NotImplementedError


def _stream_text(output: object, stream: str) -> str:
    """Extract captured text for one stream from an execution result."""
    if not isinstance(output, ExecutionResult):
        return ""
    return "".join(block.text for block in output.content if block.stream == stream)
