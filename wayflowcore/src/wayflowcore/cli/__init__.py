# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import argparse
from typing import Optional, Sequence

from .serve import add_parser as add_serve_parser

__all__ = ["main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wayflow",
        description="WayFlow command line interface.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_serve_parser(subparsers)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()

    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.error("No command specified.")

    handler(args)
