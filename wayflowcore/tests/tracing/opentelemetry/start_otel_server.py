# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict


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


def main(host: str, port: int):
    server_address = (host, port)
    httpd = HTTPServer(server_address, SimpleOTLPHandler)
    httpd.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process host, port, and mode.")
    parser.add_argument("--host", type=str, default="localhost", help="The host address")
    parser.add_argument("--port", type=int, default=4318, help="The port number (e.g., 4318)")
    args = parser.parse_args()
    main(host=args.host, port=args.port)
