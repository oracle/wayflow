# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import re
import warnings
from abc import ABC
from copy import deepcopy
from dataclasses import dataclass, field
from functools import cache
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
    Union,
    cast,
)

from wayflowcore._metadata import MetadataType
from wayflowcore.componentwithio import ComponentWithInputsOutputs
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.property import JsonSchemaParam, Property, StringProperty, _empty_default
from wayflowcore.serialization.serializer import SerializableDataclassMixin, SerializableObject

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from wayflowcore.models.openaiapitype import OpenAIAPIType
    from wayflowcore.serialization.context import DeserializationContext, SerializationContext

VALID_JSON_TYPES = {"boolean", "number", "integer", "string", "bool", "object", "array", "null"}

JSON_SCHEMA_NONE_TYPE = "null"

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


@dataclass
class ToolRequest(SerializableDataclassMixin, SerializableObject):
    _can_be_referenced: ClassVar[bool] = False
    name: str
    args: Dict[str, Any]
    tool_request_id: str = field(default_factory=IdGenerator.get_or_generate_id)
    # We use any here for loose typechecking, which works so long as we don't
    # expect to process the _extra_content (which is the case with the
    # thought_signature in Google models)
    _extra_content: Optional[Any] = None
    _requires_confirmation: bool = False
    _tool_execution_confirmed: Optional[bool] = None
    _tool_rejection_reason: Optional[str] = None


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

    # Ask for user confirmation, yields ToolExecutionConfirmationStatus if True
    requires_confirmation: bool

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
        requires_confirmation: bool = False,
    ):
        _validate_name(name, raise_on_invalid=False)  # next release cycle would raise an error

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

        self.requires_confirmation = requires_confirmation
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

    def _check_tool_outputs_copyable(self, tool_outputs: Any, raise_exceptions: bool) -> Any:
        """
        Ensure that the tool outputs can be safely deep-copied.

        If any output value cannot be copied:
        - Raises TypeError if `raise_exceptions` is True.
        - Otherwise warns and converts the uncopyable value(s) to string.

        Args:
            tool_outputs: The output returned by a tool, either a single value or a dict of values.
            raise_exceptions: Whether to raise an exception for uncopyable values.

        Returns:
            Copyable version of `tool_outputs` where uncopyable items are replaced with strings.
        """

        def handle_uncopyable(value: Any, key: Optional[str] = None) -> Any:
            try:
                deepcopy(value)
                return value
            except Exception as e:
                name = f" for arg '{key}'" if key else ""
                msg = f"Tool output is not copyable{name} ({type(value).__name__}: {e})."
                if raise_exceptions:
                    raise TypeError(
                        msg + " This prevents the value from being passed as a message to the LLM."
                    ) from e

                warnings.warn(
                    msg
                    + " The value has been automatically converted to its string representation.",
                    UserWarning,
                )
                return str(value)

        # Multiple outputs (dict)
        if len(self.output_descriptors) > 1 and isinstance(tool_outputs, dict):
            safe_output: Dict[str, Any] = {}
            for key, value in tool_outputs.items():
                safe_output[key] = handle_uncopyable(value, key)
            return safe_output

        # Single output
        return handle_uncopyable(tool_outputs, None)

    def _add_defaults_to_tool_outputs(self, tool_outputs: Any) -> Any:
        """
        In this method, in case we have multiple expected outputs we retrieve default values
        for outputs that were not generated, if they have one, otherwise we raise an exception
        """
        if len(self.output_descriptors) > 1:

            if not isinstance(tool_outputs, dict):
                raise ValueError(
                    f"Expected multiple outputs in a dictionary as result of tool `{self.name}`, "
                    f"but an object of type {type(tool_outputs)} was returned."
                )

            for tool_descriptor in self.output_descriptors:
                if tool_descriptor.name not in tool_outputs:
                    if tool_descriptor.default_value is not _empty_default:
                        tool_outputs[tool_descriptor.name] = tool_descriptor.default_value
                    else:
                        raise ValueError(
                            f"The tool `{self.name}` did not return all expected outputs. "
                            f"An output named {tool_descriptor.name} is expected, but no value with this name was returned. "
                            f"The names of the outputs returned by the tool are: {', '.join(tool_outputs.keys())}."
                        )

        return tool_outputs

    @property
    def _tool_type(self) -> SupportedToolTypesT:
        return "tool"

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        from wayflowcore.serialization.serializer import serialize_to_dict

        config = ToolConfigT(
            name=self.name,
            description=self.description or "",
            input_descriptors=[
                serialize_to_dict(prop_, serialization_context) for prop_ in self.input_descriptors
            ],
            output_descriptors=[
                serialize_to_dict(prop_, serialization_context) for prop_ in self.output_descriptors
            ],
            tool_type=self._tool_type,
            id=self.id,
            _component_type="Tool",
            __metadata_info__=self.__metadata_info__,
            requires_confirmation=self.requires_confirmation,
        )
        return cast(Dict[str, Any], config)

    @classmethod
    def _deserialize_from_dict(
        cls,
        input_dict: Dict[str, Any],
        deserialization_context: "DeserializationContext",
    ) -> "SerializableObject":
        from wayflowcore.serialization.serializer import deserialize_from_dict
        from wayflowcore.tools.clienttools import ClientTool
        from wayflowcore.tools.servertools import (
            _convert_previously_supported_tool_into_server_tool,
        )

        if not (isinstance(input_dict, str) or input_dict["tool_type"] == "server"):
            return ClientTool(
                name=input_dict["name"],
                description=input_dict["description"],
                parameters=input_dict.get("parameters", None),
                output=input_dict.get("output", None),
                input_descriptors=(
                    [
                        deserialize_from_dict(Property, prop_dict, deserialization_context)
                        for prop_dict in input_dict["input_descriptors"]
                    ]
                    if "input_descriptors" in input_dict
                    else None
                ),
                output_descriptors=(
                    [
                        deserialize_from_dict(Property, prop_dict, deserialization_context)
                        for prop_dict in input_dict["output_descriptors"]
                    ]
                    if "output_descriptors" in input_dict
                    else None
                ),
                id=input_dict.get("id", IdGenerator.get_or_generate_id()),
                __metadata_info__=input_dict["__metadata_info__"],
            )

        tool_name = input_dict if isinstance(input_dict, str) else input_dict["name"]
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

        if isinstance(input_dict, dict):
            for key in ("name", "description"):
                if getattr(deserialized_tool, key) != input_dict.get(key):
                    raise ValueError(
                        f"Information of the registered tool does not match the serialization. For"
                        f" key '{key}', '{getattr(deserialized_tool, key)}' != '{input_dict.get(key)}'"
                    )

            if "parameters" in input_dict:
                input_descriptors = _parameters_to_input_descriptors(input_dict["parameters"])
            else:
                input_descriptors = [
                    deserialize_from_dict(Property, prop_dict, deserialization_context)
                    for prop_dict in input_dict["input_descriptors"]
                ]

            # We check whether the parameters are the same, and have the same type specified
            deserialized_tool_parameters = set(
                property_.name for property_ in deserialized_tool.input_descriptors
            )
            input_dict_parameters = set(property_.name for property_ in input_descriptors)
            if deserialized_tool_parameters != input_dict_parameters:
                raise ValueError(
                    f"Information of the registered tool does not match the serialization."
                    f"Parameters of serialized tool {deserialized_tool_parameters} do not match those of the registered tool ({input_dict_parameters})"
                )
            for parameter_property in input_descriptors:
                if parameter_property not in deserialized_tool.input_descriptors:
                    raise ValueError(
                        f"Information of the registered tool does not match the serialization. "
                        f"For parameter '{parameter_property.name}', '{parameter_property}' not in '{deserialized_tool.input_descriptors}'"
                    )

            if "output" in input_dict:
                output_descriptors = _output_to_output_descriptors(input_dict["output"])
            else:
                output_descriptors = [
                    deserialize_from_dict(Property, prop_dict, deserialization_context)
                    for prop_dict in input_dict["output_descriptors"]
                ]

            # Then we check the type of the output
            if output_descriptors != deserialized_tool.output_descriptors:
                raise ValueError(
                    f"Information of the registered tool does not match the serialization. For"
                    f"For the output, '{output_descriptors}' != '{deserialized_tool.output_descriptors}'"
                )
            # We check if the requires_confirmation flag is the same
            requires_confirmation = input_dict.get("requires_confirmation", False)
            if requires_confirmation != deserialized_tool.requires_confirmation:
                raise ValueError(
                    f"Information of the registered tool does not match the serialization. For"
                    f"requires_confirmation flag of serialized tool {deserialized_tool.requires_confirmation} does not match those of the registered tool ({requires_confirmation})"
                )
        return deserialized_tool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            **({"parameters": self.parameters} if self.parameters else {}),
        }

    def to_openai_format(self, api_type: Optional["OpenAIAPIType"] = None) -> Dict[str, Any]:
        from wayflowcore._utils.formatting import _to_openai_function_dict
        from wayflowcore.models.openaiapitype import OpenAIAPIType

        if not api_type:
            api_type = OpenAIAPIType.CHAT_COMPLETIONS

        return _to_openai_function_dict(self, api_type=api_type)

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

    @property
    def might_yield(self) -> bool:
        """
        Indicates that the tool might yield inside a step or a flow.
        """
        return self.requires_confirmation


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


VALID_TOOL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
# Relaxed pattern when spaces are allowed
VALID_TOOL_NAME_PATTERN_WITH_SPACE = re.compile(r"^[a-zA-Z0-9 _-]+$")


@cache
def _validate_name(
    name: str,
    allow_space: bool = False,
    raise_on_invalid: bool = False,
) -> None:
    """
    Validates tool name against provider rules:
      - Default: Must match ^[a-zA-Z0-9_-]+$ (no spaces)
      - If allow_space=True: Must match ^[a-zA-Z0-9 _-]+$ (spaces allowed)
      - If raise_on_invalid=True: raise ValueError on invalid name; otherwise warn (DeprecationWarning).
    """
    if not isinstance(name, str) or name == "":
        raise ValueError(f"Invalid name '{name}', should be of type str and should not be empty")

    pattern = VALID_TOOL_NAME_PATTERN_WITH_SPACE if allow_space else VALID_TOOL_NAME_PATTERN

    if not pattern.fullmatch(name):
        expected = r"^[a-zA-Z0-9 _-]+$" if allow_space else r"^[a-zA-Z0-9_-]+$"
        msg = (
            f"Invalid name '{name}'. Names should match regex {expected} "
            f"({'spaces allowed' if allow_space else 'no whitespaces and special characters'}). "
            "Invalid agent/flow/tool naming is deprecated."
        )
        if raise_on_invalid:
            raise ValueError(msg)
        else:
            warnings.warn(msg, DeprecationWarning)


def _sanitize_tool_name(name: str) -> str:
    """This function is only used to transform agentic component names into tool names"""
    return name.replace(" ", "_")
