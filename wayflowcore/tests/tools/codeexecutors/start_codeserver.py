# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Start a local Code Executor server for executor integration tests."""

from __future__ import annotations

import argparse

from wayflowcore.codeserver import CodeExecutorServer


def main() -> None:
    """Start the local Python Code Executor server."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    CodeExecutorServer().run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
