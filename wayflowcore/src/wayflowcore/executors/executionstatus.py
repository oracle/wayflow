# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from __future__ import annotations

from abc import abstractmethod
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableDataclass, SerializableObject

if TYPE_CHECKING:
    from wayflowcore.tools import ToolRequest


@dataclass
class ExecutionStatus(SerializableDataclass):
    """
    Execution status returned by the Assistant. This indicates if the assistant yielded, finished the conversation, ...
    """

    @abstractmethod
    def _requires_yielding(self) -> bool:
        """Indicates whether this status requires the assistant to yield or not."""
        raise NotImplementedError()


@dataclass
class FinishedStatus(ExecutionStatus):
    """
    Execution status for when the conversation is finished. Contains the outputs of the conversation
    """

    output_values: Dict[str, Any]
    """The outputs produced by the agent or flow returning this execution status."""
    complete_step_name: Optional[str] = None
    """The name of the last step reached if the flow returning this execution status transitioned \
    to a ``CompleteStep``, otherwise ``None``."""

    def _requires_yielding(self) -> bool:
        return False

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return {"output_values": self.output_values, "complete_step_name": self.complete_step_name}

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        return FinishedStatus(
            output_values=input_dict["output_values"],
            complete_step_name=input_dict["complete_step_name"],
        )


class UserMessageRequestStatus(ExecutionStatus):
    """
    Execution status for when the assistant answered and will be waiting for the next user input
    """

    def _requires_yielding(self) -> bool:
        return True  # Indicates that execution yielded

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return {}

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        return UserMessageRequestStatus()


@dataclass
class ToolRequestStatus(ExecutionStatus):
    """
    Execution status for when the assistant is asking the user to call a tool and send back its result
    """

    tool_requests: List[ToolRequest]

    def _requires_yielding(self) -> bool:
        return True

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return {"tool_requests": [asdict(tool) for tool in self.tool_requests]}

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        from wayflowcore.tools import ToolRequest

        return ToolRequestStatus(
            tool_requests=[ToolRequest(**tool_dict) for tool_dict in input_dict["tool_requests"]]
        )
