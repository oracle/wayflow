# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import argparse
from contextvars import ContextVar
from os import PathLike
from typing import Literal

from mcp.server.fastmcp import FastMCP as BaseFastMCP
from starlette.applications import Starlette
from typing_extensions import TypedDict

UvicornExtraConfig = TypedDict(
    "UvicornExtraConfig",
    {
        "ssl_keyfile": str | PathLike[str] | None,
        "ssl_certfile": str | PathLike[str] | None,
        "ssl_ca_certs": str | None,
        "ssl_cert_reqs": int,
    },
    total=False,
)

_EXTRA_CONFIG: ContextVar[UvicornExtraConfig | None] = ContextVar("_EXTRA_CONFIG", default=None)


class FastMCP(BaseFastMCP):
    async def _start_server(self, starlette_app: Starlette) -> None:
        import uvicorn

        extra_config = _EXTRA_CONFIG.get() or {}
        config = uvicorn.Config(
            starlette_app,
            host=self.settings.host,
            port=self.settings.port,
            log_level=self.settings.log_level.lower(),
            **extra_config,
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def run_sse_async(self, mount_path: str | None = None) -> None:
        starlette_app = self.sse_app(mount_path)
        await self._start_server(starlette_app)

    async def run_streamable_http_async(self) -> None:
        starlette_app = self.streamable_http_app()
        await self._start_server(starlette_app)


def create_server(host: str, port: int) -> FastMCP:
    """Alternate MCP server exposing a different tool set.

    This server is used to validate that WayFlow's MCP session persistence does
    not cause two different toolboxes (backed by different transports/servers) to
    collide and return the same tool list.
    """

    server = FastMCP(
        name="Alternate MCP Server",
        instructions="Alternate MCP Server with a different tool set.",
        host=host,
        port=port,
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
    _EXTRA_CONFIG.set(
        dict(
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            ssl_ca_certs=ssl_ca_certs,
            ssl_cert_reqs=ssl_cert_reqs,
        )
    )
    server = create_server(host=host, port=port)
    server.run(transport=mode)


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
