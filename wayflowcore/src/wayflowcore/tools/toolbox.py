# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import copy
from abc import abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Sequence

from wayflowcore.component import Component
from wayflowcore.exceptions import AuthInterrupt
from wayflowcore.idgeneration import IdGenerator

if TYPE_CHECKING:
    from wayflowcore.tools import Tool


@dataclass
class ToolBox(Component):
    """
    Class to expose a list of tools to agentic components.

    ToolBox is dynamic which means that agentic components equipped
    with a toolbox can may see its tools to evolve throughout its
    execution.

    Parameters
    ----------
    requires_confirmation:
        Flag to ask for user confirmation whenever executing any of this toolbox's tools, yields ``ToolExecutionConfirmationStatus`` if True or if the ``Tool`` from the ``ToolBox`` requires confirmation.
    """

    id: str = field(default_factory=IdGenerator.get_or_generate_id, compare=False, hash=False)
    requires_confirmation: Optional[bool] = None

    @abstractmethod
    def _get_tools_inner(self) -> Sequence["Tool"]:
        """
        Return the list of tools exposed by the ``ToolBox``.

        Will be called inside `get_tools` method
        """

    def get_tools(self) -> Sequence["Tool"]:
        """
        Return the list of tools exposed by the ``ToolBox``.

        Will be called at every iteration in the execution loop
        of agentic components.
        """
        inner_tools = self._get_tools_inner()
        return self._handle_tool_confirmation(inner_tools)

    @abstractmethod
    async def _get_tools_inner_async(self) -> Sequence["Tool"]:
        """
        Return the list of tools exposed by the ``ToolBox`` in an asynchronous manner.

        Will be called inside `get_tools_async` method
        """

    async def get_tools_async(self) -> Sequence["Tool"]:
        """
        Return the list of tools exposed by the ``ToolBox`` in an asynchronous manner.

        Will be called at every iteration in the execution loop
        of agentic components.
        """
        inner_tools = await self._get_tools_inner_async()

        return self._handle_tool_confirmation(inner_tools)

    def _handle_tool_confirmation(self, tools: Sequence["Tool"]) -> Sequence["Tool"]:
        """
        Apply tool confirmation logic for each tool.
        """
        modified_tools = []
        any_modified = False
        for inner_tool in tools:
            if self.requires_confirmation and not inner_tool.requires_confirmation:
                inner_tool = copy.deepcopy(inner_tool)
                inner_tool.requires_confirmation = True
                any_modified = True
            modified_tools.append(inner_tool)

        if not any_modified:
            # Preserve original object and type if nothing changed
            return tools

        # Reconstruct the same concrete sequence type when possible
        if isinstance(tools, (tuple, list, set, deque, range)):
            return tools.__class__(modified_tools)
        else:
            # Fallback to list
            return modified_tools

    @property
    def might_yield(self) -> bool:
        try:
            return any(t.might_yield for t in self.get_tools())
        except AuthInterrupt:
            raise ValueError("Calling `might_yield` on Toolbox requiring auth is not supported")

    def _get_concrete_tool(self, tool_name: str) -> "Tool":
        """
        Return the Tool
        """
        raise NotImplementedError()
