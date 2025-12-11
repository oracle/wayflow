# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import os
import subprocess
import time

import pytest

from ..utils import LogTee, _check_server_is_up, _terminate_process_tree, get_available_port

_START_SERVER_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "a2a", "start_a2a_server.py"
)


def _start_a2a_server(
    host: str, port: int, ready_timeout_s: float = 10.0
) -> tuple[subprocess.Popen, str]:
    process_args = [
        "python",
        "-u",  # unbuffered output
        _START_SERVER_FILE_PATH,
        "--host",
        host,
        "--port",
        str(port),
    ]

    url = f"http://{host}:{port}"

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    # Start process with pipes and its own process group so we can kill children
    process = subprocess.Popen(
        process_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # line-buffered
        env=env,
        start_new_session=True,
    )

    # Tee logs to CI and keep a ring buffer
    if process.stdout is None:
        raise RuntimeError("Failed to capture server stdout")
    tee = LogTee(process.stdout, prefix="[uvicorn] ")
    tee.start()

    try:
        # Poll for readiness or early exit
        start = time.time()
        while time.time() - start < ready_timeout_s:
            rc = process.poll()
            if rc is not None:
                raise RuntimeError(f"Uvicorn exited early with code {rc}.\nLogs:\n{tee.dump()}")

            if _check_server_is_up(url, timeout_s=0.5):
                print("A2A Server is up.", flush=True)
                return process, url
            time.sleep(0.2)

        # Timed out
        raise RuntimeError(
            f"Uvicorn server did not start in time ({ready_timeout_s}s).\nLogs so far:\n{tee.dump()}"
        )

    except Exception as e:
        _terminate_process_tree(process, timeout=5.0)
        raise e
    finally:
        tee.stop()


@pytest.fixture(scope="session", name="a2a_server")
def a2a_server_fixture():
    host = "localhost"
    port = get_available_port()
    process, url = _start_a2a_server(host=host, port=port)
    try:
        yield url
    finally:
        _terminate_process_tree(process, timeout=5.0)
