# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import os
import subprocess
import time
from typing import Tuple

import httpx

_START_SERVER_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "start_otel_server.py"
)


def _check_server_is_up(url: str) -> bool:
    with httpx.Client() as client:
        for _ in range(50):  # up to 5 seconds
            try:
                resp = client.get(url)
                if resp.status_code < 500:
                    return True
            except Exception:
                time.sleep(0.2)
        else:
            return False


def _start_otel_server(host: str, port: int) -> Tuple[subprocess.Popen, str]:
    process = subprocess.Popen(
        [
            "python",
            _START_SERVER_FILE_PATH,
            "--host",
            host,
            "--port",
            str(port),
        ]
    )
    url = f"http://{host}:{port}"
    server_is_up = _check_server_is_up(url)
    if not server_is_up:
        raise RuntimeError("Uvicorn server did not start in time")
    return process, url
