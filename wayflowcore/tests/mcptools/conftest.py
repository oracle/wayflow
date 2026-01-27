# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import os
import ssl
import subprocess
import time
from typing import Optional, Tuple

import pytest

from wayflowcore.mcp._session_persistence import shutdown_mcp_async_runtime

from ..utils import LogTee, _check_server_is_up, _terminate_process_tree, get_available_port

_START_SERVER_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "start_mcp_server.py"
)

from .encryption import (
    create_client_key_and_csr,
    create_root_ca,
    create_server_key_and_csr,
    issue_client_cert,
    issue_server_cert,
)


@pytest.fixture(scope="session")
def root_ca(session_tmp_path):
    return create_root_ca(common_name="TestRootCA", days=3650, tmpdir=session_tmp_path)


@pytest.fixture(scope="session")
def ca_key(root_ca):
    return root_ca[0]


@pytest.fixture(scope="session")
def ca_cert(root_ca):
    return root_ca[1]


@pytest.fixture(scope="session")
def ca_cert_path(root_ca) -> str:
    return root_ca[2]


@pytest.fixture(scope="session")
def server_key_and_csr(session_tmp_path):
    return create_server_key_and_csr(cn="localhost", tmpdir=session_tmp_path)


@pytest.fixture(scope="session")
def server_key_path(server_key_and_csr):
    return server_key_and_csr[2]


@pytest.fixture(scope="session")
def server_csr(server_key_and_csr):
    return server_key_and_csr[1]


@pytest.fixture(scope="session")
def server_cert_path(ca_key, ca_cert, server_csr, session_tmp_path) -> str:
    return issue_server_cert(ca_key, ca_cert, server_csr, days=365, tmpdir=session_tmp_path)[1]


@pytest.fixture(scope="session")
def client_key_and_csr(session_tmp_path):
    return create_client_key_and_csr(cn="mtls-client", tmpdir=session_tmp_path)


@pytest.fixture(scope="session")
def client_key_path(client_key_and_csr):
    return client_key_and_csr[2]


@pytest.fixture(scope="session")
def client_csr(client_key_and_csr):
    return client_key_and_csr[1]


@pytest.fixture(scope="session")
def client_cert_path(ca_key, ca_cert, client_csr, session_tmp_path) -> str:
    return issue_client_cert(ca_key, ca_cert, client_csr, days=365, tmpdir=session_tmp_path)[1]


def _start_mcp_server(
    host: str,
    port: int,
    mode: str,
    server_key_path: Optional[str] = None,
    server_cert_path: Optional[str] = None,
    ca_cert_path: Optional[str] = None,
    ssl_cert_reqs: int = 0,  # ssl.CERT_NONE
    client_key_path: Optional[str] = None,
    client_cert_path: Optional[str] = None,
    ready_timeout_s: float = 10.0,
) -> Tuple[subprocess.Popen, str, LogTee]:
    process_args = [
        "python",
        "-u",  # unbuffered output
        _START_SERVER_FILE_PATH,
        "--host",
        host,
        "--port",
        str(port),
        "--mode",
        mode,
        "--ssl_cert_reqs",
        str(ssl_cert_reqs),
    ]
    if server_key_path and server_cert_path and ca_cert_path:  # using https
        process_args.extend(
            [
                "--ssl_keyfile",
                server_key_path,
                "--ssl_certfile",
                server_cert_path,
                "--ssl_ca_certs",
                ca_cert_path,
            ]
        )
        url = f"https://{host}:{port}"
    else:
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

            if _check_server_is_up(
                url, client_key_path, client_cert_path, ca_cert_path, timeout_s=0.5
            ):
                print("Server is up.", flush=True)
                return process, url, tee
            time.sleep(0.2)

        # Timed out
        raise RuntimeError(
            f"Uvicorn server did not start in time ({ready_timeout_s}s).\nLogs so far:\n{tee.dump()}"
        )

    except Exception as e:
        _terminate_process_tree(process, timeout=5.0)
        raise e


def register_mcp_server_fixture(
    name: str,
    url_suffix: str,
    start_kwargs: dict,
    deps: tuple[str, ...] = (),
    host: str = "localhost",
    port: Optional[int] = None,
):
    def _fixture(request):
        # Resolve any dependent fixtures by name and merge into kwargs
        resolved = {name: request.getfixturevalue(name) for name in deps}
        kwargs = {
            **start_kwargs,
            **resolved,
            "host": host,
            "port": port or get_available_port(request.getfixturevalue("session_tmp_path")),
        }

        process, url, tee = _start_mcp_server(**kwargs)
        try:
            yield f"{url}/{url_suffix.strip('/')}"
        finally:
            shutdown_mcp_async_runtime()
            # ^ The MCP sessions are closed before the servers are
            # stopped to avoid sse_reader issues (solves the error:
            # `peer closed connection without sending complete message body
            # (incomplete chunked read)`)
            _terminate_process_tree(process, timeout=5.0)
            tee.stop()  # this needs to be stopped after the
            # MCP server so that the stdout is closed.

    return pytest.fixture(scope="session", name=name)(_fixture)


_MCP_SERVER_FIXTURE_DEPS = (
    "server_key_path",
    "server_cert_path",
    "ca_cert_path",
    "client_key_path",
    "client_cert_path",
)


sse_mcp_server_http = register_mcp_server_fixture(
    name="sse_mcp_server_http",
    url_suffix="sse",
    start_kwargs=dict(mode="sse", ssl_cert_reqs=0),
    deps=(),
)

streamablehttp_mcp_server_http = register_mcp_server_fixture(
    name="streamablehttp_mcp_server_http",
    url_suffix="mcp",
    start_kwargs=dict(mode="streamable-http", ssl_cert_reqs=int(ssl.CERT_NONE)),
    deps=(),
)

sse_mcp_server_https = register_mcp_server_fixture(
    name="sse_mcp_server_https",
    url_suffix="sse",
    start_kwargs=dict(mode="sse", ssl_cert_reqs=int(ssl.CERT_NONE)),
    deps=_MCP_SERVER_FIXTURE_DEPS,
)

streamablehttp_mcp_server_https = register_mcp_server_fixture(
    name="streamablehttp_mcp_server_https",
    url_suffix="mcp",
    start_kwargs=dict(mode="streamable-http", ssl_cert_reqs=int(ssl.CERT_NONE)),
    deps=_MCP_SERVER_FIXTURE_DEPS,
)

sse_mcp_server_mtls = register_mcp_server_fixture(
    name="sse_mcp_server_mtls",
    url_suffix="sse",
    start_kwargs=dict(mode="sse", ssl_cert_reqs=int(ssl.CERT_REQUIRED)),
    deps=_MCP_SERVER_FIXTURE_DEPS,
)

streamablehttp_mcp_server_mtls = register_mcp_server_fixture(
    name="streamablehttp_mcp_server_mtls",
    url_suffix="mcp",
    start_kwargs=dict(mode="streamable-http", ssl_cert_reqs=int(ssl.CERT_REQUIRED)),
    deps=_MCP_SERVER_FIXTURE_DEPS,
)
