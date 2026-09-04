# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest

from wayflowcore.codeserver.backends.local_python import LocalPythonBackend
from wayflowcore.codeserver.service import CodeExecutionService


@pytest.fixture
def python_service() -> CodeExecutionService:
    """Provides a service backed by the local Python implementation."""
    return CodeExecutionService(backend=LocalPythonBackend())


@pytest.fixture
def python_backend() -> LocalPythonBackend:
    """Provides a local Python backend for direct backend tests."""
    backend = LocalPythonBackend()
    yield backend
    backend.close_all_sessions()
