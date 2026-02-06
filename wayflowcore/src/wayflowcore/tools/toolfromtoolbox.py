# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from logging import getLogger
from typing import TYPE_CHECKING, Any, Dict, Optional

from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject, serialize_to_dict
from wayflowcore.tools.toolbox import ToolBox
from wayflowcore.tools.tools import Tool

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.tools.tools import ToolRequest, ToolResult

logger = getLogger(__name__)


class ToolFromToolBox(Tool, SerializableObject):
    """
    A Tool that is extracted from a toolbox by name.

    On serialization to dict, includes the datastore config.
    On deserialization, restores the datastore to full object form.
    """

    def __init__(self, tool_name: str, toolbox: "ToolBox") -> None:
        self.toolbox = toolbox
        self.__name = tool_name
        _concrete_tool = toolbox._get_concrete_tool(tool_name)

        super().__init__(
            name=tool_name,
            description=_concrete_tool.description,
            input_descriptors=_concrete_tool.input_descriptors,
            output_descriptors=_concrete_tool.output_descriptors,
            output=_concrete_tool.output,
            requires_confirmation=_concrete_tool.requires_confirmation,
            __metadata_info__=_concrete_tool.__metadata_info__,
            parameters=_concrete_tool.parameters,
        )
        SerializableObject.__init__(self, None)

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return {
            "tool_name": self.__name,
            "toolbox": serialize_to_dict(self.toolbox, serialization_context),
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        from wayflowcore.serialization.serializer import autodeserialize_any_from_dict

        toolbox: ToolBox
        toolbox = autodeserialize_any_from_dict(
            input_dict["toolbox"], deserialization_context=deserialization_context
        )
        return ToolFromToolBox(
            tool_name=input_dict["tool_name"],
            toolbox=toolbox,
        )

    async def _run(
        self,
        conversation: "Conversation",
        tool_request: "ToolRequest",
        append_message: bool = False,
        raise_exceptions: bool = False,
    ) -> Optional["ToolResult"]:

        _concrete_tool = self.toolbox._get_concrete_tool(self.__name)
        if not _concrete_tool:
            raise ValueError(f"Tool is not supported for ToolBox: {self.toolbox}")

        return await _concrete_tool._run(
            conversation, tool_request, append_message, raise_exceptions
        )
