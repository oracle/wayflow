# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from typing import Dict, Optional

from wayflowcore.retrypolicy import RetryPolicy

from .executor import CodeExecutor


@dataclass
class EndpointCodeExecutor(CodeExecutor):
    """Run code through a Code Executor endpoint."""

    url: str
    """Code Executor base URL."""

    headers: dict[str, str] | None = None
    """Non-sensitive transport headers."""

    sensitive_headers: Optional[Dict[str, str]] = None
    """Sensitive transport headers."""

    retry_policy: RetryPolicy | None = None
    """Transport retry policy."""
