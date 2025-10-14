# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from __future__ import annotations

import warnings
from abc import abstractmethod
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional

from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableDataclass, SerializableObject

if TYPE_CHECKING:
    from wayflowcore.tools import ToolRequest


@dataclass
class ExecutionStatus(SerializableDataclass):
    """
    Execution status returned by the Assistant. This indicates if the assistant yielded, finished the conversation, ...
    """

    _can_be_referenced: ClassVar[bool] = False

    @property
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

    @property
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

    @property
    def _requires_yielding(self) -> bool:
        return True  # Indicates that execution yielded


@dataclass
class ToolRequestStatus(ExecutionStatus):
    """
    Execution status for when the assistant is asking the user to call a tool and send back its result
    """

    tool_requests: List["ToolRequest"]
    _conversation_id: Optional[str]

    @property
    def _requires_yielding(self) -> bool:
        return True

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return {
            "tool_requests": [asdict(tool) for tool in self.tool_requests],
            "_conversation_id": self._conversation_id,
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        from wayflowcore.tools import ToolRequest

        return ToolRequestStatus(
            tool_requests=[ToolRequest(**tool_dict) for tool_dict in input_dict["tool_requests"]],
            _conversation_id=input_dict.get("_conversation_id"),
        )


@dataclass
class ToolExecutionConfirmationStatus(ExecutionStatus):
    """
    Execution status for when the assistant is asking the user to confirm or reject the execution of a tool
    """

    tool_requests: List["ToolRequest"]
    """
    List of tool requests for the user to confirm or deny individually
    """
    _conversation_id: Optional[str]

    @property
    def _requires_yielding(self) -> bool:
        return True

    def confirm_tool_execution(
        self, tool_request: "ToolRequest", modified_args: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Confirms a tool request, which will be executed.

        Parameters
        ----------
        tool_request:
            Tool request to accept.
        modified_args:
            Can be specified to slightly change the parameters to call the tool.
            Can be used for example to validate access-control.
        """
        if not tool_request._requires_confirmation:
            raise ValueError(
                f"Expected requires_confirmation flag to be set to True in the tool_request: {tool_request}"
            )

        tool_request._tool_execution_confirmed = True

        if modified_args:
            for key, value in modified_args.items():
                if key in tool_request.args:
                    tool_request.args[key] = value
                else:
                    warnings.warn(
                        f"Modified argument: {modified_args[key]} is not a valid input for given tool request: {tool_request}",
                        UserWarning,
                    )

    def reject_tool_execution(
        self,
        tool_request: "ToolRequest",
        reason: Optional[str] = None,
    ) -> None:
        """
        Rejects a tool request, which won't be executed.

        Parameters
        ----------
        tool_request:
            Tool request to reject.
        reason:
            Can be specified to explain to the model why the tool execution was rejected, so that it can adapt the arguments to form a potentially acceptable tool request.
        """
        if not tool_request._requires_confirmation:
            raise ValueError(
                f"Expected requires_confirmation flag to be present in the tool_request: {tool_request}"
            )

        tool_request._tool_execution_confirmed = False
        tool_request._tool_rejection_reason = reason

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return {
            "tool_requests": [asdict(tool) for tool in self.tool_requests],
            "_conversation_id": self._conversation_id,
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        from wayflowcore.tools import ToolRequest

        return ToolExecutionConfirmationStatus(
            tool_requests=[ToolRequest(**tool_dict) for tool_dict in input_dict["tool_requests"]],
            _conversation_id=input_dict.get("_conversation_id"),
        )
