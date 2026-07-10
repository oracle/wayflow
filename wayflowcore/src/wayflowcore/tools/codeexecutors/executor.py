# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Base classes for code executor configurations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from wayflowcore.component import Component

from ._utils import CodeExecutionStatus


@dataclass
class CodeExecutor(Component):
    """Class to configure a code executor."""

    timeout_seconds: float
    """Maximum wall-clock time allowed for one execution. The default value is ``30``."""
    max_code_chars: int
    """Maximum accepted source length in characters. The default value is ``50000``."""

    def _execute_function(
        self,
        code: str,
        language: str,
        function_name: str,
        arguments: Mapping[str, Any],
        dependencies: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> CodeExecutionStatus:
        """Run one named function defined in source code.

        Parameters
        ----------
        code:
            Source code that defines ``function_name``.
        language:
            Language identifier understood by the configured server.
        function_name:
            Name of the function to invoke from ``code``.
        arguments:
            JSON-compatible named arguments passed to the function.
        dependencies:
            Dependency declarations required by the source code.
        metadata:
            Optional JSON-compatible caller data and suggested executor
            settings. The executor separates its own settings from caller
            correlation data before calling the server.

        Returns
        -------
        CodeExecutionStatus
            A terminal execution status.
        """
        raise NotImplementedError

    async def _execute_function_async(
        self,
        code: str,
        language: str,
        function_name: str,
        arguments: Mapping[str, Any],
        dependencies: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> CodeExecutionStatus:
        """Asynchronously run one named function defined in source code."""
        raise NotImplementedError

    def _execute_script(
        self,
        code: str,
        language: str,
        dependencies: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> CodeExecutionStatus:
        """Run one script.

        Parameters
        ----------
        code:
            Source code to run as a script.
        language:
            Language identifier understood by the configured server.
        dependencies:
            Dependency declarations required by the source code.
        metadata:
            Optional JSON-compatible caller data and suggested executor
            settings. Script execution may use this mapping to carry a raw
            response to an earlier host request.

        Returns
        -------
        CodeExecutionStatus
            A terminal execution status, or ``waiting_for_context`` when the
            server asks the host to do work.
        """
        raise NotImplementedError

    async def _execute_script_async(
        self,
        code: str,
        language: str,
        dependencies: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> CodeExecutionStatus:
        """Asynchronously run one script."""
        raise NotImplementedError

    def get_capabilities(self) -> dict[str, Any]:
        """Return capability information supplied by the configured server,
        which may include the supported languages, supported execution modes,
        and any other supported feature.
        """
        raise NotImplementedError
