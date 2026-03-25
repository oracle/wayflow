# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import argparse
from typing import Literal

from fastmcp import FastMCP


def create_server() -> FastMCP:
    """Alternate MCP server exposing a different tool set.

    This server is used to validate that WayFlow's MCP session persistence does
    not cause two different toolboxes (backed by different transports/servers) to
    collide and return the same tool list.
    """

    server = FastMCP(
        name="Alternate MCP Server",
        instructions="Alternate MCP Server with a different tool set.",
    )

    @server.tool(description="Return the result of the alt_add operation between numbers a and b")
    def alt_add_tool(a: int, b: int) -> int:
        return a + b

    @server.tool(description="Return the result of the alt_mul operation between numbers a and b")
    def alt_mul_tool(a: int, b: int) -> int:
        return a * b

    return server


def main(
    host: str,
    port: int,
    mode: Literal["sse", "streamable-http"],
    ssl_keyfile: str | None,
    ssl_certfile: str | None,
    ssl_ca_certs: str | None,
    ssl_cert_reqs: int,
) -> None:
    import logging

    server = create_server()
    server.run(
        transport=mode,
        show_banner=False,
        host=host,
        port=port,
        uvicorn_config=dict(
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            ssl_ca_certs=ssl_ca_certs,
            ssl_cert_reqs=ssl_cert_reqs,
            log_level=logging.DEBUG,
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start alternate MCP test server.")

    parser.add_argument("--host", type=str)
    parser.add_argument("--port", type=int)
    parser.add_argument("--mode", type=str, choices=["sse", "streamable-http"])
    parser.add_argument("--ssl_keyfile", type=str)
    parser.add_argument("--ssl_certfile", type=str)
    parser.add_argument("--ssl_ca_certs", type=str)
    parser.add_argument("--ssl_cert_reqs", type=int)

    args = parser.parse_args()
    main(
        host=args.host,
        port=args.port,
        mode=args.mode,
        ssl_keyfile=args.ssl_keyfile,
        ssl_certfile=args.ssl_certfile,
        ssl_ca_certs=args.ssl_ca_certs,
        ssl_cert_reqs=args.ssl_cert_reqs,
    )
