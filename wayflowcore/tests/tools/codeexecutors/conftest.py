# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Fixtures for CodeExecutor integration tests."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.utils import _check_server_is_up, _terminate_process_tree, get_available_port

WAYFLOW_CODE_EXECUTOR_CONTAINER_IMAGE = os.environ.get("WAYFLOW_CODE_EXECUTOR_CONTAINER_IMAGE")


@pytest.fixture(scope="session")
def code_executor_url(session_tmp_path: Path) -> str:
    """Lazily start one local Code Executor endpoint for HTTP tests."""
    port = get_available_port(session_tmp_path)
    process = subprocess.Popen(
        [
            sys.executable,
            "-u",
            str(Path(__file__).with_name("start_codeserver.py")),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Code Executor server exited before becoming ready.")
            if _check_server_is_up(f"{url}/v1/code-executor", timeout_s=0.5):
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Code Executor server did not become ready in time.")
        yield url
    finally:
        _terminate_process_tree(process)
