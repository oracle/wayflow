# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List, Literal, TypedDict, Union, cast

from wayflowcore._metadata import MetadataType
from wayflowcore.property import JsonSchemaParam, Property
from wayflowcore.tools import ClientTool, ServerTool, Tool
from wayflowcore.tools.servertools import _convert_previously_supported_tool_into_server_tool

from ..idgeneration import IdGenerator
from ..tools.tools import _output_to_output_descriptors, _parameters_to_input_descriptors
from .context import DeserializationContext, SerializationContext
from .serializer import SerializableObject

SupportedToolTypesT = Literal["client", "server", "remote", "tool"]

ToolConfigT = TypedDict(
    "ToolConfigT",
    {
        "name": str,
        "description": str,
        "parameters": Dict[str, JsonSchemaParam],
        "output": JsonSchemaParam,
        "input_descriptors": List[Dict[str, Any]],
        "output_descriptors": List[Dict[str, Any]],
        "tool_type": SupportedToolTypesT,
        "id": str,
        "_component_type": Literal["Tool"],
        "__metadata_info__": MetadataType,
        "requires_confirmation": bool,
    },
    total=False,
)

TOOL_TYPE_MAPPING: Dict[str, SupportedToolTypesT] = {
    Tool.__name__: "tool",
    ClientTool.__name__: "client",
    ServerTool.__name__: "server",
}


def serialize_tool_to_config(
    tool: Tool, serialization_context: SerializationContext
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
    from wayflowcore.serialization.serializer import serialize_to_dict

    if tool.__class__.__name__ not in TOOL_TYPE_MAPPING:
        if isinstance(tool, SerializableObject):
            # remote tools, toolbox and mcp tools
            return serialize_to_dict(tool, serialization_context)
        else:
            raise TypeError(f"Unsupported tool type: '{tool.__class__.__name__}'")

    tool_type = TOOL_TYPE_MAPPING[tool.__class__.__name__]
    config = ToolConfigT(
        name=tool.name,
        description=tool.description or "",
        input_descriptors=[
            serialize_to_dict(prop_, serialization_context) for prop_ in tool.input_descriptors
        ],
        output_descriptors=[
            serialize_to_dict(prop_, serialization_context) for prop_ in tool.output_descriptors
        ],
        tool_type=tool_type,
        id=tool.id,
        _component_type="Tool",
        __metadata_info__=tool.__metadata_info__,
        requires_confirmation=tool.requires_confirmation,
    )
    return cast(Dict[str, Any], config)


def deserialize_tool_from_config(
    tool_config: Union[str, ToolConfigT, Dict[str, Any]],
    deserialization_context: DeserializationContext,
) -> Tool:
    """
    Builds an instance of Variable from its representation as a dict

    Parameters
    ----------
    tool_config:
      The representation of a Tool as a serializable type. It can either be a dictionary
      containing metadata information about the tool, or a single string that must correspond
      to a tool registered in the deserialiazation context.
    deserialization_context:
      The deserialization context might be used by the tools that are built using other wayflowcore
      components or by tools that must be retrieved from the deserialization context tool registry.
    """
    from wayflowcore.serialization.serializer import (
        autodeserialize_from_dict,
        deserialize_from_dict,
    )

    if not isinstance(tool_config, str) and "tool_type" not in tool_config:
        return cast(
            Tool,
            autodeserialize_from_dict(cast(Dict[str, Any], tool_config), deserialization_context),
        )

    if not (isinstance(tool_config, str) or tool_config["tool_type"] == "server"):
        return ClientTool(
            name=tool_config["name"],
            description=tool_config["description"],
            parameters=tool_config.get("parameters", None),
            output=tool_config.get("output", None),
            input_descriptors=(
                [
                    deserialize_from_dict(Property, prop_dict, deserialization_context)
                    for prop_dict in tool_config["input_descriptors"]
                ]
                if "input_descriptors" in tool_config
                else None
            ),
            output_descriptors=(
                [
                    deserialize_from_dict(Property, prop_dict, deserialization_context)
                    for prop_dict in tool_config["output_descriptors"]
                ]
                if "output_descriptors" in tool_config
                else None
            ),
            id=tool_config.get("id", IdGenerator.get_or_generate_id()),
            __metadata_info__=tool_config["__metadata_info__"],
        )

    tool_name = tool_config if isinstance(tool_config, str) else tool_config["name"]
    if tool_name not in deserialization_context.registered_tools:
        raise ValueError(
            f"While trying to deserialize tool named '{tool_name}', found no such tool "
            f"registered. Please make sure that the tool's name matches one of the registered "
            f"tools."
        )
    registered_tool = deserialization_context.registered_tools[tool_name]
    deserialized_tool: Tool
    if isinstance(registered_tool, Tool):
        deserialized_tool = registered_tool
    else:
        deserialized_tool = _convert_previously_supported_tool_into_server_tool(registered_tool)

    if isinstance(tool_config, dict):
        for key in ("name", "description"):
            if getattr(deserialized_tool, key) != tool_config.get(key):
                raise ValueError(
                    f"Information of the registered tool does not match the serialization. For"
                    f" key '{key}', '{getattr(deserialized_tool, key)}' != '{tool_config.get(key)}'"
                )

        if "parameters" in tool_config:
            input_descriptors = _parameters_to_input_descriptors(tool_config["parameters"])
        else:
            input_descriptors = [
                deserialize_from_dict(Property, prop_dict, deserialization_context)
                for prop_dict in tool_config["input_descriptors"]
            ]

        # We check whether the parameters are the same, and have the same type specified
        deserialized_tool_parameters = set(
            property_.name for property_ in deserialized_tool.input_descriptors
        )
        tool_config_parameters = set(property_.name for property_ in input_descriptors)
        if deserialized_tool_parameters != tool_config_parameters:
            raise ValueError(
                f"Information of the registered tool does not match the serialization."
                f"Parameters of serialized tool {deserialized_tool_parameters} do not match those of the registered tool ({tool_config_parameters})"
            )
        for parameter_property in input_descriptors:
            if parameter_property not in deserialized_tool.input_descriptors:
                raise ValueError(
                    f"Information of the registered tool does not match the serialization. "
                    f"For parameter '{parameter_property.name}', '{parameter_property}' not in '{deserialized_tool.input_descriptors}'"
                )

        if "output" in tool_config:
            output_descriptors = _output_to_output_descriptors(tool_config["output"])
        else:
            output_descriptors = [
                deserialize_from_dict(Property, prop_dict, deserialization_context)
                for prop_dict in tool_config["output_descriptors"]
            ]

        # Then we check the type of the output
        if output_descriptors != deserialized_tool.output_descriptors:
            raise ValueError(
                f"Information of the registered tool does not match the serialization. For"
                f"For the output, '{output_descriptors}' != '{deserialized_tool.output_descriptors}'"
            )
        # We check if the requires_confirmation flag is the same
        requires_confirmation = tool_config.get("requires_confirmation", False)
        if requires_confirmation != deserialized_tool.requires_confirmation:
            raise ValueError(
                f"Information of the registered tool does not match the serialization. For"
                f"requires_confirmation flag of serialized tool {deserialized_tool.requires_confirmation} does not match those of the registered tool ({requires_confirmation})"
            )

    return deserialized_tool
