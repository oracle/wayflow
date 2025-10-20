# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from wayflowcore.executors._events.event import Event, EventType
from wayflowcore.executors.executionstatus import ExecutionStatus
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.executors._executionstate import ConversationExecutionState


@dataclass
class InterruptedExecutionStatus(ExecutionStatus, SerializableObject):
    """
    ExecutionStatus type thrown by the interrupts.
    It contains the ``ExecutionInterrupt`` that stopped the execution,
    and the reason why the execution was stopped.

    Parameters
    ----------
    interrupter:
        The ``ExecutionInterrupt`` that stopped the execution.
    reason:
        Why the execution was stopped.
    """

    interrupter: ExecutionInterrupt
    reason: str

    @property
    def _requires_yielding(self) -> bool:
        return True

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        from wayflowcore.serialization.serializer import serialize_to_dict

        return {
            "interrupter": serialize_to_dict(self.interrupter, serialization_context),
            "reason": self.reason,
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        from wayflowcore.serialization.serializer import autodeserialize_from_dict

        return InterruptedExecutionStatus(
            interrupter=cast(
                ExecutionInterrupt,
                autodeserialize_from_dict(input_dict["interrupter"], deserialization_context),
            ),
            reason=input_dict["reason"],
        )


class ExecutionInterrupt(SerializableObject, metaclass=ABCMeta):
    """
    Execution Interrupts give developers a way to interact with the standard execution
    of an assistant, offering the chance to stop it when some events are triggered.
    """

    def on_event(
        self, event: Event, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        """
        Checks if the interrupt should be triggered at the current state,
        based on the given execution status.
        If the interrupt is triggered, this method returns the ``InterruptedExecutionStatus``
        that should be returned to the execution caller.

        Parameters
        ----------
        event:
            The current event happening.
        state:
            The current ``ConversationExecutionState``.

        Returns
        -------
        An instance of a ``InterruptedExecutionStatus`` subclass if the execution should be interrupted.
        ``None`` if the execution can continue.
        """
        if event.type == EventType.EXECUTION_START:
            return self._on_execution_start(state, conversation)
        if event.type == EventType.EXECUTION_END:
            return self._on_execution_end(state, conversation)
        if event.type == EventType.EXECUTION_LOOP_ITERATION_START:
            return self._on_execution_loop_iteration_start(state, conversation)
        if event.type == EventType.EXECUTION_LOOP_ITERATION_END:
            return self._on_execution_loop_iteration_end(state, conversation)
        return None

    @abstractmethod
    def _on_execution_start(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        pass

    @abstractmethod
    def _on_execution_end(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        pass

    @abstractmethod
    def _on_execution_loop_iteration_start(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        pass

    @abstractmethod
    def _on_execution_loop_iteration_end(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        pass


class FlowExecutionInterrupt(ExecutionInterrupt):
    """
    Execution interrupt that can be used in the execution of flow assistants.
    """

    def on_event(
        self, event: Event, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        if event.type == EventType.STEP_EXECUTION_START:
            return self._on_step_execution_start(state, conversation)
        if event.type == EventType.STEP_EXECUTION_END:
            return self._on_step_execution_end(state, conversation)
        return super().on_event(event, state, conversation)

    @abstractmethod
    def _on_step_execution_start(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        pass

    @abstractmethod
    def _on_step_execution_end(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        pass


class FlexibleExecutionInterrupt(ExecutionInterrupt):
    """
    Execution interrupt that can be used in the execution of agents.
    """

    def on_event(
        self, event: Event, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        if event.type == EventType.GENERATION_START:
            return self._on_generation_start(state, conversation)
        if event.type == EventType.GENERATION_END:
            return self._on_generation_end(state, conversation)
        if event.type == EventType.TOOL_CALL_START:
            return self._on_tool_call_start(state, conversation)
        if event.type == EventType.TOOL_CALL_END:
            return self._on_tool_call_end(state, conversation)
        if event.type == EventType.AGENT_CALL_START:
            return self._on_agent_call_start(state, conversation)
        if event.type == EventType.AGENT_CALL_END:
            return self._on_agent_call_end(state, conversation)
        return super().on_event(event, state, conversation)

    @abstractmethod
    def _on_generation_start(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        pass

    @abstractmethod
    def _on_generation_end(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        pass

    @abstractmethod
    def _on_tool_call_start(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        pass

    @abstractmethod
    def _on_tool_call_end(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        pass

    @abstractmethod
    def _on_agent_call_start(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        pass

    @abstractmethod
    def _on_agent_call_end(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        pass


class _AllEventsInterruptMixin(ABC):
    """
    This is an execution interrupt mixing that replicates the same interruption logic for every event.
    In the basic use case, one should simply implement the ``_return_status_if_condition_is_met`` method.
    """

    @abstractmethod
    def _return_status_if_condition_is_met(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        pass

    def _on_execution_start(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        return self._return_status_if_condition_is_met(state, conversation)

    def _on_execution_end(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        return self._return_status_if_condition_is_met(state, conversation)

    def _on_execution_loop_iteration_start(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        return self._return_status_if_condition_is_met(state, conversation)

    def _on_execution_loop_iteration_end(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        return self._return_status_if_condition_is_met(state, conversation)

    def _on_step_execution_start(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        return self._return_status_if_condition_is_met(state, conversation)

    def _on_step_execution_end(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        return self._return_status_if_condition_is_met(state, conversation)

    def _on_generation_start(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        return self._return_status_if_condition_is_met(state, conversation)

    def _on_generation_end(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        return self._return_status_if_condition_is_met(state, conversation)

    def _on_tool_call_start(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        return self._return_status_if_condition_is_met(state, conversation)

    def _on_tool_call_end(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        return self._return_status_if_condition_is_met(state, conversation)

    def _on_agent_call_start(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        return self._return_status_if_condition_is_met(state, conversation)

    def _on_agent_call_end(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        return self._return_status_if_condition_is_met(state, conversation)


class _NullExecutionInterrupt(
    _AllEventsInterruptMixin, FlexibleExecutionInterrupt, FlowExecutionInterrupt
):
    """
    Execution interrupt that never interrupts.
    Useful in case an interrupt needs to intervene in a single event.
    In that case, one could extend this class and override only the ``_on_...`` method related to the event of interest.
    """

    def _return_status_if_condition_is_met(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        return None
