# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
import os
import ssl
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Dict, Iterator, Tuple

import pytest

from ..mcptools.encryption import (
    create_client_key_and_csr,
    create_root_ca,
    create_server_key_and_csr,
    issue_client_cert,
    issue_server_cert,
)


@dataclass
class TLSMaterial:
    ca_cert_path: str
    server_key_path: str
    server_cert_path: str
    client_key_path: str
    client_cert_path: str


@dataclass
class CapturedHTTPSRequest:
    path: str
    body: bytes
    headers: Dict[str, str]


def create_tls_material(tmpdir: str) -> TLSMaterial:
    """Create a CA, server cert, and client cert bundle for local HTTPS tests."""
    os.makedirs(tmpdir, exist_ok=True)
    ca_key, ca_cert, ca_cert_path = create_root_ca(tmpdir=tmpdir)
    _, server_csr, server_key_path = create_server_key_and_csr(tmpdir=tmpdir)
    _, server_cert_path = issue_server_cert(
        ca_key=ca_key,
        ca_cert=ca_cert,
        csr=server_csr,
        tmpdir=tmpdir,
    )
    _, client_csr, client_key_path = create_client_key_and_csr(tmpdir=tmpdir)
    _, client_cert_path = issue_client_cert(
        ca_key=ca_key,
        ca_cert=ca_cert,
        csr=client_csr,
        tmpdir=tmpdir,
    )
    return TLSMaterial(
        ca_cert_path=ca_cert_path,
        server_key_path=server_key_path,
        server_cert_path=server_cert_path,
        client_key_path=client_key_path,
        client_cert_path=client_cert_path,
    )


@contextmanager
def run_https_json_server(
    response_factory: Callable[[CapturedHTTPSRequest], Tuple[int, Dict[str, object]]],
    tls_material: TLSMaterial,
    require_client_cert: bool = False,
) -> Iterator[str]:
    """Run a temporary HTTPS JSON server and yield its base URL."""

    class RequestHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            request = CapturedHTTPSRequest(
                path=self.path,
                body=body,
                headers=dict(self.headers.items()),
            )
            status_code, payload = response_factory(request)
            response_bytes = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_bytes)))
            self.end_headers()
            self.wfile.write(response_bytes)

        def log_message(self, format: str, *args: object) -> None:
            return None

    # Let the kernel pick and bind a free port atomically to avoid a reserve-then-bind race.
    server = ThreadingHTTPServer(("127.0.0.1", 0), RequestHandler)
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(
        certfile=tls_material.server_cert_path,
        keyfile=tls_material.server_key_path,
    )
    ssl_context.load_verify_locations(cafile=tls_material.ca_cert_path)
    ssl_context.verify_mode = ssl.CERT_REQUIRED if require_client_cert else ssl.CERT_NONE
    server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    # ^ Enable TLS on the test server socket.

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)


@pytest.fixture
def tls_material_factory(tmp_path):
    """Return a factory that creates isolated TLS materials under the test temp directory."""
    counter = 0

    def _factory(subdir_name: str = "") -> TLSMaterial:
        nonlocal counter
        counter += 1
        target_dir = Path(tmp_path) / (subdir_name or f"tls-material-{counter}")
        return create_tls_material(str(target_dir))

    return _factory


@pytest.fixture
def tls_material(tls_material_factory) -> TLSMaterial:
    """Provide a default TLS material bundle for a test."""
    return tls_material_factory()


@pytest.fixture
def https_json_server_factory():
    """Return a factory for starting temporary HTTPS JSON servers in tests."""

    @contextmanager
    def _factory(
        response_factory: Callable[[CapturedHTTPSRequest], Tuple[int, Dict[str, object]]],
        tls_material: TLSMaterial,
        require_client_cert: bool = False,
    ) -> Iterator[str]:
        with run_https_json_server(
            response_factory=response_factory,
            tls_material=tls_material,
            require_client_cert=require_client_cert,
        ) as base_url:
            yield base_url

    return _factory


@pytest.fixture
def https_json_server(https_json_server_factory, tls_material):
    """Provide a default HTTPS JSON server context manager backed by shared TLS material."""

    @contextmanager
    def _server(
        response_factory: Callable[[CapturedHTTPSRequest], Tuple[int, Dict[str, object]]],
        require_client_cert: bool = False,
    ) -> Iterator[str]:
        with https_json_server_factory(
            response_factory=response_factory,
            tls_material=tls_material,
            require_client_cert=require_client_cert,
        ) as base_url:
            yield base_url

    return _server
