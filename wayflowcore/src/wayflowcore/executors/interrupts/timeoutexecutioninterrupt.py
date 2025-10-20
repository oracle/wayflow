# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Optional

from wayflowcore.executors.interrupts.executioninterrupt import (
    FlexibleExecutionInterrupt,
    FlowExecutionInterrupt,
    InterruptedExecutionStatus,
    _AllEventsInterruptMixin,
)
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.executors._executionstate import ConversationExecutionState


class SoftTimeoutExecutionInterrupt(
    _AllEventsInterruptMixin,
    FlexibleExecutionInterrupt,
    FlowExecutionInterrupt,
    SerializableObject,
):

    _DEFAULT_TIMEOUT: ClassVar[float] = 10 * 60

    def __init__(self, timeout: Optional[float] = None):
        """
        Execution interrupt that stops the assistant's execution after a given time limit.
        This is a soft limit, as it does not force the interruption of the execution at any time.
        For example:
        - It does not interrupt the execution of a step (except for ``FlowExecutionStep``)
        - It does not interrupt the execution of a tool
        - It does not interrupt LLM models during generation

        Parameters
        ----------
        timeout:
            The timeout in seconds after which the assistant execution should be stopped.
            Default value set to 600 seconds (10 minutes).

        Example
        -------
        >>> from wayflowcore.agent import Agent
        >>> from wayflowcore.executors.interrupts.timeoutexecutioninterrupt import SoftTimeoutExecutionInterrupt
        >>> from wayflowcore.executors.executionstatus import ExecutionStatus
        >>> from wayflowcore.executors.interrupts.executioninterrupt import InterruptedExecutionStatus
        >>> from wayflowcore.models.llmmodelfactory import LlmModelFactory
        >>> VLLM_CONFIG = {"model_type": "vllm", "host_port": LLAMA70B_API_ENDPOINT, "model_id": "/storage/models/Llama-3.1-70B-Instruct",}
        >>> llm = LlmModelFactory.from_config(VLLM_CONFIG)
        >>> assistant = Agent(llm=llm, custom_instruction="You are a helpful assistant")
        >>> conversation = assistant.start_conversation()
        >>> conversation.append_user_message("Tell me something interesting")
        >>> timeout_interrupt = SoftTimeoutExecutionInterrupt(timeout=1)
        >>> status = conversation.execute(execution_interrupts=[timeout_interrupt])
        >>> isinstance(status, ExecutionStatus) or isinstance(status, InterruptedExecutionStatus)
        True

        """
        self.timeout: float = timeout if timeout is not None else self._DEFAULT_TIMEOUT
        self.starting_time: Optional[float] = None

        super().__init__()

    def _return_status_if_condition_is_met(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        if self.timeout is None or self.starting_time is None:
            # This should never happen, but we put a safeguard anyway
            raise ValueError("Illegal State: execution start event was not called correctly")
        if time.time() - self.starting_time > self.timeout:
            return InterruptedExecutionStatus(self, "Execution time limit reached")
        return None

    def _on_execution_start(
        self, state: ConversationExecutionState, conversation: "Conversation"
    ) -> Optional[InterruptedExecutionStatus]:
        self.starting_time = time.time()
        return super()._on_execution_start(state, conversation)

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return {
            "timeout": self.timeout,
            "starting_time": self.starting_time,
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        interrupt = SoftTimeoutExecutionInterrupt(
            timeout=input_dict["timeout"],
        )
        interrupt.starting_time = input_dict["starting_time"]
        return interrupt
