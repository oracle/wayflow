# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.executors.executionstatus import ExecutionStatus
    from wayflowcore.executors.interrupts.executioninterrupt import (
        ExecutionInterrupt,
        InterruptedExecutionStatus,
    )


class ExecutionInterruptedException(Exception):

    def __init__(self, execution_status: InterruptedExecutionStatus):
        super().__init__("Execution interrupted")
        self.execution_status: InterruptedExecutionStatus = execution_status


class ConversationExecutor(ABC):
    """Base Executor class. An executor is stateless, and exposes an execute method on the conversation."""

    @staticmethod
    @abstractmethod
    async def execute_async(
        conversation: "Conversation",
        execution_interrupts: Optional[Sequence["ExecutionInterrupt"]] = None,
    ) -> ExecutionStatus:
        """
        Runs a conversation given a list of messages and a state. The state is specific to the type of
        conversation (can be agent-based or flow-based).

        Parameters
        ----------
        conversation:
            A conversation object
        execution_interrupts:
            List of execution interrupts
        """
