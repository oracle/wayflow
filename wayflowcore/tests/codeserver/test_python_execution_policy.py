# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Tests for strict Python execution through the local backend."""

import pytest

from wayflowcore.codeserver.backends.local_python import LocalPythonBackend
from wayflowcore.codeserver.backends.pythonexecutionpolicy import (
    StrictPythonExecutionPolicy,
)
from wayflowcore.codeserver.models import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED


@pytest.fixture
def strict_python_backend() -> LocalPythonBackend:
    """Create a local backend using the strict Python execution policy."""
    backend = LocalPythonBackend(
        policy=StrictPythonExecutionPolicy(allowed_imports=["math"]),
    )
    yield backend
    backend.close_all_sessions()


@pytest.mark.parametrize(
    ("code", "expected_substring"),
    [
        ("import os\nprint(os.getcwd())", "not allowed"),
        ("from pathlib import Path\nprint(Path.cwd())", "not allowed"),
        ("async def f():\n    return 1", "not allowed"),
        ("def f():\n    return 1", "not allowed"),
        ("class C:\n    pass", "not allowed"),
        ("print(__builtins__)", "not allowed"),
        ("print(dir(1))", "not allowed"),
        ("print((lambda x: x)(1))", "not allowed"),
        ("print((1).__class__)", "not allowed"),
        ("print((1).__subclasshook__)", "not allowed"),
        ("print(''.__class__.mro()[1].__subclasses__())", "not allowed"),
        ("print((1).__getattribute__)", "not allowed"),
        ("print(eval('1 + 1'))", "not allowed"),
        ("print(compile('1 + 1', '<x>', 'eval'))", "not allowed"),
        ("print([x for x in range(3)])", "not allowed"),
        ("print({x: x for x in range(3)})", "not allowed"),
        ("print((x for x in range(3)))", "not allowed"),
        ("x = (y := 1)", "not allowed"),
        ("try:\n    1 / 0\nexcept Exception as e:\n    print('x')", "not allowed"),
        ("def g():\n    yield 1", "not allowed"),
        ("print('x'.encode('utf-8'))", "not allowed"),
        ("print(b'x'.decode('utf-8'))", "not allowed"),
        ("print('{}'.format(1))", "not allowed"),
        ("print(''.mro())", "not allowed"),
    ],
)
def test_local_python_backend_rejects_unsafe_script(
    strict_python_backend: LocalPythonBackend,
    code: str,
    expected_substring: str,
) -> None:
    """Rejects unsafe script source before starting a worker."""
    with pytest.raises(ValueError, match=expected_substring):
        strict_python_backend.start_script(code)


def test_local_python_backend_rejects_unsupported_script_import(
    strict_python_backend: LocalPythonBackend,
) -> None:
    """Rejects imports outside the configured allow-list."""
    with pytest.raises(ValueError, match="not allowed"):
        strict_python_backend.start_script("import os")


def test_local_python_backend_accepts_allowed_script_import(
    strict_python_backend: LocalPythonBackend,
) -> None:
    """Runs a script importing an allowed top-level module."""
    execution = strict_python_backend.start_script("import math\nprint(math.sqrt(4))")

    assert execution.wait().status == TASK_STATUS_COMPLETED


def test_local_python_backend_rejects_relative_import(
    strict_python_backend: LocalPythonBackend,
) -> None:
    """Rejects relative imports before starting a worker."""
    with pytest.raises(ValueError, match="not allowed"):
        strict_python_backend.start_script("from .math import sqrt")


def test_local_python_backend_runs_valid_function(
    strict_python_backend: LocalPythonBackend,
) -> None:
    """Allows one named synchronous function for function execution."""
    execution = strict_python_backend.start_function(
        "def multiply(a, b):\n    return a * b",
        "multiply",
        {"a": 6, "b": 7},
    )

    result = execution.wait()

    assert result.status == TASK_STATUS_COMPLETED
    assert result.structured_content == 42


@pytest.mark.parametrize(
    ("code", "function_name"),
    [
        ("def multiply(a, b):\n    return a * b", "missing"),
        ("def a():\n    pass\ndef b():\n    pass", "a"),
        ("async def multiply(a, b):\n    return a * b", "multiply"),
        ("class Multiply:\n    pass", "Multiply"),
        ("def multiply(a, b):\n    return eval('1 + 1')", "multiply"),
    ],
)
def test_local_python_backend_rejects_invalid_function(
    strict_python_backend: LocalPythonBackend,
    code: str,
    function_name: str,
) -> None:
    """Rejects missing, ambiguous, asynchronous, or unsafe functions."""
    with pytest.raises(ValueError):
        strict_python_backend.start_function(code, function_name, {})


def test_local_python_backend_restricts_builtins(
    strict_python_backend: LocalPythonBackend,
) -> None:
    """Reports failure when code uses a builtin outside the restricted set."""
    execution = strict_python_backend.start_script("print(exec)")

    result = execution.wait()

    assert result.status == TASK_STATUS_FAILED
    assert result.error is not None
    assert "exec" in result.error


def test_local_python_backend_preserves_output_truncation(
    strict_python_backend: LocalPythonBackend,
) -> None:
    """Preserves the backend output limit while using the strict policy."""
    strict_python_backend.max_stdout_chars = 100
    execution = strict_python_backend.start_script("print('a' * 2000)")

    result = execution.wait()

    assert result.status == TASK_STATUS_COMPLETED
    assert len(result.stdout) >= 100
