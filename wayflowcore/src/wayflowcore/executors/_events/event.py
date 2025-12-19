# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict

from wayflowcore.component import DataclassComponent
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.tokenusage import TokenUsage


class EventType(Enum):
    """
    Enumeration for the type of event happening in the assistant's execution.
    """

    EXECUTION_START = "EXECUTION_START"
    EXECUTION_END = "EXECUTION_END"
    EXECUTION_LOOP_ITERATION_START = "EXECUTION_LOOP_ITERATION_START"
    EXECUTION_LOOP_ITERATION_END = "EXECUTION_LOOP_ITERATION_END"
    STEP_EXECUTION_START = "STEP_EXECUTION_START"
    STEP_EXECUTION_END = "STEP_EXECUTION_END"
    GENERATION_START = "GENERATION_START"
    GENERATION_END = "GENERATION_END"
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_END = "TOOL_CALL_END"
    AGENT_CALL_START = "AGENT_CALL_START"
    AGENT_CALL_END = "AGENT_CALL_END"

    TOKEN_CONSUMPTION = "TOKEN_CONSUMPTION"  # nosec0001 # the reported issue by pybandit that variables should not be named token is hard to comply with in this context as the variable refers to the usage report of a LLM that is counted in number of tokens


@dataclass
class Event(DataclassComponent):
    type: EventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc), repr=False)

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "__metadata_info__": self.__metadata_info__,
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        return Event(
            type=EventType(input_dict["type"]),
            timestamp=datetime.fromisoformat(input_dict["timestamp"]),
            __metadata_info__=input_dict["__metadata_info__"],
        )


@dataclass
class _TokenConsumptionEvent(Event):
    # TODO feat: Event collection for tracing Agent sessions
    type: EventType = EventType.TOKEN_CONSUMPTION
    token_usage: TokenUsage = field(default_factory=TokenUsage, repr=False)

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        config_dict = super()._serialize_to_dict(serialization_context)
        config_dict["token_usage"] = asdict(self.token_usage)
        return config_dict

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        return _TokenConsumptionEvent(
            token_usage=TokenUsage(**input_dict.get("token_usage", {})),
            type=EventType(input_dict["type"]),
            timestamp=datetime.fromisoformat(input_dict["timestamp"]),
            __metadata_info__=input_dict["__metadata_info__"],
        )
