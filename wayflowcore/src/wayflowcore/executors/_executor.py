# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Sequence

from wayflowcore.executors._events.event import Event, EventType

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.executors._executionstate import ConversationExecutionState
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
    def _register_event(
        state: ConversationExecutionState,
        conversation: Conversation,
        event_type: EventType,
    ) -> None:
        new_event = Event(type=event_type)
        state._register_event(new_event)
        # we collect all the statuses to be sure to run all the callbacks, as they might update their internal status
        interrupt_statuses = [
            execution_interrupt.on_event(new_event, state, conversation)
            for execution_interrupt in (state._get_execution_interrupts() or [])
        ]
        try:
            # We look the first non-null interrupt status we find
            execution_status = next(
                interrupt_status
                for interrupt_status in interrupt_statuses
                if interrupt_status is not None
            )
            # If we find one, we raise an ExecutionInterruptedException containing the status
            raise ExecutionInterruptedException(execution_status=execution_status)
        except StopIteration:
            # We did not find any non-null status, we can proceed
            pass

    @staticmethod
    @abstractmethod
    async def execute_async(
        conversation: "Conversation",
        execution_interrupts: Optional[Sequence["ExecutionInterrupt"]] = None,
    ) -> ExecutionStatus:
        """
        Runs a conversation given a list of messages and a state. The state is specific to the type of
        conversation (can be agent-based or flow-based).

        Parameters:
        -----------
        conversation: Conversation
        execution_interrupts: Optional[Sequence[ExecutionInterrupt]]
        """
