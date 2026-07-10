# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from .executor import CodeExecutor


@dataclass
class SubProcessCodeExecutor(CodeExecutor):
    """Run code through a Code Executor subprocess."""


@contextmanager
def subprocess_execution_enabled() -> Iterator[None]:
    """
    Temporarily enable subprocess code execution in the current context.
    """
    yield


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
    raise NotImplementedError
