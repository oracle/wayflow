# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from __future__ import annotations

import warnings
from abc import ABC
from dataclasses import dataclass, field
from typing import ClassVar, List, Optional, Sequence, cast

from wayflowcore.component import DataclassComponent
from wayflowcore.executors._events.event import Event
from wayflowcore.executors.interrupts.executioninterrupt import ExecutionInterrupt
from wayflowcore.executors.interrupts.timeoutexecutioninterrupt import SoftTimeoutExecutionInterrupt


@dataclass
class ConversationExecutionState(DataclassComponent, ABC):
    """
    State of a conversation except messages.
    Implementation depends on the type of conversation (flow-based or agent-based).
    """

    events: List[Event] = field(init=False, default_factory=list)
    interrupts: Optional[List[ExecutionInterrupt]] = field(init=False, default=None)
    _EVENTS_LIST_MAX_LENGTH: ClassVar[int] = 1000000

    def _register_event(self, event: Event) -> None:
        # If we reached the length limit, we pop the oldest event before adding the new one
        if len(self.events) >= self._EVENTS_LIST_MAX_LENGTH:
            self.events.pop(0)
        self.events.append(event)

    def _resolve_execution_interrupts(
        self, execution_interrupts: Optional[Sequence[ExecutionInterrupt]]
    ) -> List[ExecutionInterrupt]:
        if execution_interrupts is None:
            # By default, we set an execution timeout at 10 minutes, in order to avoid never-ending assistants
            execution_interrupts = [SoftTimeoutExecutionInterrupt()]
        elif not any(
            isinstance(execution_interrupt, SoftTimeoutExecutionInterrupt)
            for execution_interrupt in execution_interrupts
        ):
            # If the user did not pass any time limit, we raise a warning, but we let him do it
            warnings.warn("The assistant is being executed without a time limit!")
        return cast(List[ExecutionInterrupt], execution_interrupts)

    def _set_execution_interrupts(self, interrupts: Optional[Sequence[ExecutionInterrupt]]) -> None:
        self.interrupts = self._resolve_execution_interrupts(interrupts)

    def _get_execution_interrupts(self) -> Optional[Sequence[ExecutionInterrupt]]:
        return self.interrupts
