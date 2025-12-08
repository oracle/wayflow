# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import os.path
from pathlib import Path

import wayflowcore


def test_version_match():
    installed_version = wayflowcore.__version__
    version_file_path = Path(os.path.dirname(__file__)).parent.parent / "VERSION"
    dev_version = version_file_path.read_text().strip()
    assert (
        installed_version == dev_version
    ), f"Version mismatch: installed={installed_version}, dev={dev_version}"
