# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict

import pytest

from ...utils import get_available_port


class SimpleOTLPHandler(BaseHTTPRequestHandler):

    stored_spans: Dict[int, Any] = {}

    def _traces(self) -> None:
        response_status = 200
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            trace_data = json.loads(body)
            span_id = int(trace_data["context"]["span_id"], 16) - 1
            SimpleOTLPHandler.stored_spans[span_id] = trace_data
        except Exception:
            response_status = 400

        self.send_response(response_status)
        self.end_headers()
        self.wfile.write(b"")  # Empty response

    def _get_span(self):
        response_status = 200
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            request_data = json.loads(body)
            trace_data = json.dumps(SimpleOTLPHandler.stored_spans[int(request_data["span_id"])])
        except Exception:
            trace_data = "Provided body data was in wrong format"
            response_status = 400

        self.send_response(response_status)
        self.end_headers()
        self.wfile.write(trace_data.encode())

    def do_GET(self) -> None:
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        if self.path == "/v1/traces":
            self._traces()
        elif self.path == "/v1/getspan":
            self._get_span()
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture(scope="session")
@pytest.mark.xdist_group("requires-server-port")
def otel_server(session_tmp_path: str):
    host = "localhost"
    port = get_available_port(session_tmp_path)
    url = f"{host}:{port}"

    server = HTTPServer((host, port), SimpleOTLPHandler)

    thread = threading.Thread(
        target=server.serve_forever,
        name="otel-test-server",
        daemon=True,
    )
    thread.start()
    try:
        yield url
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
