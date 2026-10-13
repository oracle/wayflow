# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""End-to-end tests shared by the available CodeExecutor implementations."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from tests.tools.codeexecutors.conftest import WAYFLOW_CODE_EXECUTOR_CONTAINER_IMAGE
from wayflowcore.tools.codeexecutors import (
    CodeExecutor,
    EndpointCodeExecutor,
    LocalContainerCodeExecutor,
    SubProcessCodeExecutor,
    subprocess_execution_enabled,
)
from wayflowcore.tools.codeexecutors._utils import (
    CodeExecutionFailed,
    CodeExecutionSucceeded,
    CodeExecutionTimedOut,
)


@dataclass(frozen=True)
class ExecutorConfig:
    """Configuration used to instantiate one E2E executor."""

    name: str
    executor_type: type[CodeExecutor]
    kwargs: dict[str, Any]


ALL_AVAILABLE_EXECUTORS = [
    ExecutorConfig(
        name="subprocess",
        executor_type=SubProcessCodeExecutor,
        kwargs={"timeout_seconds": 2.0, "max_code_chars": 50_000},
    ),
    ExecutorConfig(
        name="endpoint",
        executor_type=EndpointCodeExecutor,
        kwargs={"timeout_seconds": 2.0, "max_code_chars": 50_000},
    ),
]

if WAYFLOW_CODE_EXECUTOR_CONTAINER_IMAGE:
    ALL_AVAILABLE_EXECUTORS.append(
        ExecutorConfig(
            name="local-container",
            executor_type=LocalContainerCodeExecutor,
            kwargs={
                "image": WAYFLOW_CODE_EXECUTOR_CONTAINER_IMAGE,
                "timeout_seconds": 2.0,
                "max_code_chars": 50_000,
            },
        )
    )


with_all_code_executors = pytest.mark.parametrize(
    "executor_config",
    argvalues=ALL_AVAILABLE_EXECUTORS,
    ids=[config.name for config in ALL_AVAILABLE_EXECUTORS],
)


@pytest.fixture
def code_executor(
    executor_config: ExecutorConfig,
    request: pytest.FixtureRequest,
) -> Iterator[CodeExecutor]:
    """Yield one available executor and clean up its runtime afterward."""
    kwargs = dict(executor_config.kwargs)
    if executor_config.executor_type is EndpointCodeExecutor:
        kwargs["url"] = request.getfixturevalue("code_executor_url")
    executor = executor_config.executor_type(**kwargs)
    try:
        if isinstance(executor, SubProcessCodeExecutor):
            with subprocess_execution_enabled():
                yield executor
        else:
            yield executor
    finally:
        close = getattr(executor, "close", None)
        if callable(close):
            close()


@with_all_code_executors
def test_code_executor_e2e_runs_script_and_captures_stdout(
    code_executor: CodeExecutor,
) -> None:
    """Runs a script and returns captured standard output."""
    status = code_executor._execute_script("print('hello')", "python")

    assert isinstance(status, CodeExecutionSucceeded)
    assert status.stdout == "hello\n"


@with_all_code_executors
def test_code_executor_e2e_runs_function_with_structured_result(
    code_executor: CodeExecutor,
) -> None:
    """Runs a function and returns its structured result."""
    status = code_executor._execute_function(
        "def multiply(a, b):\n    return a * b",
        "python",
        "multiply",
        {"a": 6, "b": 7},
    )

    assert isinstance(status, CodeExecutionSucceeded)
    assert status.result == 42


@with_all_code_executors
def test_code_executor_e2e_captures_stderr(code_executor: CodeExecutor) -> None:
    """Captures standard error output from a script."""
    status = code_executor._execute_script(
        "import sys\nprint('warning', file=sys.stderr)",
        "python",
    )

    assert isinstance(status, CodeExecutionSucceeded)
    assert status.stderr == "warning\n"


@with_all_code_executors
def test_code_executor_e2e_returns_failed_status(code_executor: CodeExecutor) -> None:
    """Returns a failed status when user code raises an exception."""
    status = code_executor._execute_script("raise ValueError('boom')", "python")

    assert isinstance(status, CodeExecutionFailed)
    assert status.message is not None


@with_all_code_executors
def test_code_executor_e2e_returns_timed_out_status(code_executor: CodeExecutor) -> None:
    """Returns a timed-out status when execution exceeds its deadline."""
    code_executor.timeout_seconds = 0.1

    status = code_executor._execute_script("while True: pass", "python")

    assert isinstance(status, CodeExecutionTimedOut)
