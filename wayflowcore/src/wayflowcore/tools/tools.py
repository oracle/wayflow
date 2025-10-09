# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from abc import ABC
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Union

from wayflowcore._metadata import MetadataType
from wayflowcore.componentwithio import ComponentWithInputsOutputs
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.property import JsonSchemaParam, Property, StringProperty
from wayflowcore.serialization.serializer import SerializableDataclassMixin, SerializableObject

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from wayflowcore.serialization.context import DeserializationContext, SerializationContext


VALID_JSON_TYPES = {"boolean", "number", "integer", "string", "bool", "object", "array", "null"}

JSON_SCHEMA_NONE_TYPE = "null"


@dataclass(frozen=True)
class ToolRequest(SerializableDataclassMixin, SerializableObject):
    _can_be_referenced: ClassVar[bool] = False
    name: str
    args: Dict[str, Any]
    tool_request_id: str = field(default_factory=IdGenerator.get_or_generate_id)


@dataclass(frozen=True)
class ToolResult(SerializableDataclassMixin, SerializableObject):
    _can_be_referenced: ClassVar[bool] = False
    content: Any
    tool_request_id: str


TOOL_OUTPUT_NAME = "tool_output"


def _parameters_to_input_descriptors(parameters: Dict[str, JsonSchemaParam]) -> List[Property]:
    return [
        Property.from_json_schema(param_data, name=param_name, validate_default_type=False)
        for param_name, param_data in parameters.items()
    ]


def _input_descriptors_to_parameters(
    input_descriptors: List[Property],
) -> Dict[str, JsonSchemaParam]:
    return {property_.name: property_.to_json_schema() for property_ in input_descriptors}


def _output_descriptors_to_output(output_descriptors: List[Property]) -> JsonSchemaParam:
    if len(output_descriptors) == 1:
        return output_descriptors[0].to_json_schema()
    return {"type": "object", "properties": _input_descriptors_to_parameters(output_descriptors)}


def _output_to_output_descriptors(output: JsonSchemaParam) -> List[Property]:
    return [
        Property.from_json_schema(
            # legacy tools need to still show default output name
            output,
            name=output.get("title", TOOL_OUTPUT_NAME),
            validate_default_type=False,
        )
    ]


@dataclass
class Tool(ComponentWithInputsOutputs, SerializableObject, ABC):

    DEFAULT_TOOL_NAME: ClassVar[str] = TOOL_OUTPUT_NAME
    """str: Default name of the tool output if none is provided"""

    # override the type of the description
    description: str

    def __init__(
        self,
        name: str,
        description: str,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        parameters: Optional[Dict[str, JsonSchemaParam]] = None,
        output: Optional[JsonSchemaParam] = None,
        id: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        if input_descriptors is not None:
            self.input_descriptors = input_descriptors
            self.parameters = _input_descriptors_to_parameters(input_descriptors)
        elif parameters is not None:
            self.input_descriptors = _parameters_to_input_descriptors(parameters)
            self.parameters = parameters
        else:
            raise ValueError("Should specify `input_descriptors`")

        if output_descriptors is not None:
            if len(output_descriptors) == 1:
                self.output_descriptors = [
                    output_descriptors[0].copy(
                        name=output_descriptors[0].name or self.DEFAULT_TOOL_NAME
                    )
                ]
            else:
                self.output_descriptors = output_descriptors
            self.output = _output_descriptors_to_output(self.output_descriptors)
        elif output is not None:
            self.output_descriptors = _output_to_output_descriptors(output)
            self.output = output
        else:
            self.output_descriptors = [StringProperty(name=self.DEFAULT_TOOL_NAME)]
            self.output = _output_descriptors_to_output(self.output_descriptors)

        super().__init__(
            input_descriptors=self.input_descriptors,
            output_descriptors=self.output_descriptors,
            name=name,
            description=description,
            id=id,
            __metadata_info__=__metadata_info__,
        )
        self._set_title()
        self._check_valid_types()

    def _set_title(self) -> None:
        for param_name, param in self.parameters.items():
            if "title" not in param:
                param["title"] = param_name.title().replace("_", " ")

    def _check_valid_types(self) -> None:
        invalid_types = {
            param_name: param_info["type"]
            for param_name, param_info in self.parameters.items()
            if not self._is_type_valid(param_info.get("type", "object"))
        }
        if not self._is_type_valid(self.output.get("type", "object")):
            invalid_types["return_type"] = self.output["type"]

        if invalid_types:
            formatted_error_message = (
                f"Invalid parameter type(s) detected:\n"
                f"{', '.join(f'{param} ({type_})' for param, type_ in invalid_types.items())}\n"
                f"Valid types are: {', '.join(VALID_JSON_TYPES)}"
            )
            raise TypeError(formatted_error_message)

    def _is_type_valid(self, param_type: Union[str, List[str]]) -> bool:
        # JSON schema types can be described either as a string or as a list. For examples:
        # - {"type": "string"} means an object must be a string
        # - {"type": ["null", "string"]} means an object can be a string or None
        # Note that not all features of json schema typing are supported (missing features are
        # for example "allOf" or "anyOf")
        if isinstance(param_type, list):
            return all(self._is_type_valid(sub_param_type) for sub_param_type in param_type)
        else:
            return param_type in VALID_JSON_TYPES

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        from wayflowcore.serialization.toolserialization import serialize_tool_to_config

        return serialize_tool_to_config(self, serialization_context)

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        from wayflowcore.serialization.toolserialization import deserialize_tool_from_config

        return deserialize_tool_from_config(input_dict, deserialization_context)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            **({"parameters": self.parameters} if self.parameters else {}),
        }

    def to_openai_format(self) -> Dict[str, Any]:
        from wayflowcore._utils.formatting import _to_openai_function_dict

        return _to_openai_function_dict(self)

    @property
    def might_yield(self) -> bool:
        return False

    def _to_simple_json_format(self) -> Dict[str, Any]:
        """
        Compact/simplified json-style formatting of a tool schema.
        e.g. (indented for visualization purposes)
        {
            "name": tool.name,
            "parameters": {
                "param1": "int (required) : Description of required param1",
                "param2": "float (default=2.5) : Description of optional param2"
            }
        }
        """
        from wayflowcore._utils.formatting import _tool_to_simple_function_dict

        return _tool_to_simple_function_dict(self)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={repr(self.name)})"


def _make_tool_key(key: str, tools: Dict[str, Any]) -> str:
    if not key in tools:
        return key

    i = 1
    # TODO allow registration of multiple tools with the same name
    limit = 1
    while i < limit:
        new_key = f"{key}{i}"
        if not new_key in tools:
            return new_key
        i += 1

    raise OverflowError(f"Aborting, there are over {limit} tools with name {key}")


def _convert_list_of_properties_to_tool(
    properties: List[Property],
) -> "Tool":
    """Converts the list of properties into a tool that will have one argument per property. This can be used
    by an ``Agent`` to produce values for all the properties."""
    return Tool(
        name="expected_output",  # name doesn't matter, the important part will be the values of all arguments
        description="the expected output of the generation",
        input_descriptors=properties,
    )
