# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import TYPE_CHECKING, Any, Dict, Union, cast

from deprecated import deprecated

from wayflowcore.tools import Tool
from wayflowcore.tools.tools import ToolConfigT

if TYPE_CHECKING:
    from wayflowcore.serialization.context import DeserializationContext, SerializationContext


@deprecated(
    "`serialize_tool_to_config` is deprecated. Please use `serialize_to_dict(Tool, ...)` instead."
)
def serialize_tool_to_config(
    tool: Tool, serialization_context: "SerializationContext"
) -> Dict[str, Any]:
    """
    Converts a Variable to a nested dict of standard types such that it can be easily
    serialized with either JSON or YAML

    Parameters
    ----------
    tool:
      The Tool that is intended to be serialized
    serialization_context:
      The Serialization context might be used for tools built using other wayflowcore components
    """
    return tool._serialize_to_dict(serialization_context)


@deprecated(
    "`deserialize_tool_from_config` is deprecated. Please use `deserialize_from_dict(Tool, ...)` instead."
)
def deserialize_tool_from_config(
    tool_config: Union[str, ToolConfigT, Dict[str, Any]],
    deserialization_context: "DeserializationContext",
) -> Tool:
    """
    Builds an instance of Variable from its representation as a dict

    Parameters
    ----------
    tool_config:
      The representation of a Tool as a serializable type. It can either be a dictionary
      containing metadata information about the tool, or a single string that must correspond
      to a tool registered in the deserialization context.
    deserialization_context:
      The deserialization context might be used by the tools that are built using other wayflowcore
      components or by tools that must be retrieved from the deserialization context tool registry.
    """
    return cast(Tool, Tool._deserialize_from_dict(tool_config, deserialization_context))  # type: ignore
