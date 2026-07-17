# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Command-line entry point for the Code Executor server."""

from __future__ import annotations

import argparse
import os

from wayflowcore.codeserver import CodeExecutorServer

__all__ = ["add_parser", "codeserver"]


def add_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> argparse.ArgumentParser:
    """Add the ``codeserver`` command to the WayFlow CLI parser."""
    parser = subparsers.add_parser(
        "codeserver",
        help="Run a local Python Code Executor server.",
        description="Launch a Code Executor Protocol server with the local Python backend.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        default=8765,
        type=int,
        help="Port to bind (default: 8765).",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("WAYFLOW_API_KEY"),
        help="Bearer token required by the server (or WAYFLOW_API_KEY).",
    )
    parser.set_defaults(handler=_run_codeserver)
    return parser


def _run_codeserver(args: argparse.Namespace) -> None:
    """Run the configured local Python Code Executor server."""
    codeserver(host=args.host, port=args.port, api_key=args.api_key)


def codeserver(host: str = "127.0.0.1", port: int = 8765, api_key: str | None = None) -> None:
    """Run a local Python Code Executor server."""
    CodeExecutorServer().run(host=host, port=port, api_key=api_key)


# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
