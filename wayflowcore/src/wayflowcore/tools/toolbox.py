# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Sequence

from wayflowcore.component import Component
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
    """

    id: str = field(default_factory=IdGenerator.get_or_generate_id, compare=False, hash=False)

    @abstractmethod
    def get_tools(self) -> Sequence["Tool"]:
        """
        Return the list of tools exposed by the ``ToolBox``.

        Will be called at every iteration in the execution loop
        of agentic components.
        """

    @abstractmethod
    async def get_tools_async(self) -> Sequence["Tool"]:
        """
        Return the list of tools exposed by the ``ToolBox`` in an asynchronous manner.

        Will be called at every iteration in the execution loop
        of agentic components.
        """

    @property
    def might_yield(self) -> bool:
        return any(t.might_yield for t in self.get_tools())
