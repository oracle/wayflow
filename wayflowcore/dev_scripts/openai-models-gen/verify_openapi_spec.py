#!/usr/bin/env python

# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""
Small helper used by `generate_apis.sh` to verify a downloaded OpenAPI spec.

Usage:
    python verify_openapi_spec.py SPEC_PATH EXPECTED_SHA256

Example:
    python verify_openapi_spec.py data/openapi.documented.yml 2de803...

Exit code 0 means the file matches the approved SHA256. Exit code 1 means it does not.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: verify_openapi_spec.py SPEC_PATH EXPECTED_SHA256", file=sys.stderr)
        return 1

    spec_path = Path(sys.argv[1])
    expected_sha256 = sys.argv[2]

    digest = hashlib.sha256()
    with spec_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_sha256 = digest.hexdigest()

    if actual_sha256 != expected_sha256:
        print(
            f"ERROR: OpenAI spec SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
