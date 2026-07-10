# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Worker process entry point for the local Python backend."""

from __future__ import annotations

from typing import Any


def run_script(source_code: str, namespace: dict[str, Any]) -> Any:
    """Execute script source code in a worker namespace."""
    raise NotImplementedError


def run_function(
    source_code: str,
    function_name: str,
    arguments: dict[str, Any],
    namespace: dict[str, Any],
) -> Any:
    """Define source code and invoke one named function in a worker namespace."""
    raise NotImplementedError


def main() -> None:
    """Run the local Python worker command loop."""
    raise NotImplementedError


if __name__ == "__main__":
    main()
