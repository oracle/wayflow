# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


from dataclasses import dataclass

from .executor import CodeExecutor


@dataclass(kw_only=True)
class LocalContainerCodeExecutor(CodeExecutor):
    """Run code through a locally started container-backed Code Executor."""

    image: str
    """Container image selected for the execution environment."""
