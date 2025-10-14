# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import inspect
from enum import Enum
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
)

from wayflowcore.property import JsonSchemaParam, Property

from .servertools import ServerTool
from .tools import Tool


class DescriptionMode(str, Enum):
    """Modes for determining parameter descriptions."""

    INFER_FROM_SIGNATURE = "infer_from_signature"
    ONLY_DOCSTRING = "only_docstring"
    EXTRACT_FROM_DOCSTRING = "extract_from_docstring"


# JSON Schema type mapping for primitives
PRIMITIVE_TYPE_MAP = {
    str: "string",
    int: "integer",
    bool: "boolean",
    float: "number",
    type(None): "null",
    None: "null",
}


def _get_partial_schema_from_annotation(arg_type: Type[Any]) -> JsonSchemaParam:
    """
    Converts a Python type annotation into a JSON Schema representation.
    Supports primitives, List, Dict, Optional, Union, and Literal.
    """
    # Handle primitive types
    if arg_type in PRIMITIVE_TYPE_MAP:
        return {"type": PRIMITIVE_TYPE_MAP[arg_type]}

    origin = get_origin(arg_type)
    args = get_args(arg_type)

    # Handle List[X]
    if origin is list or origin is List:
        if not args:
            raise TypeError("List must have a specified type, e.g., List[int]")
        return {"type": "array", "items": _get_partial_schema_from_annotation(args[0])}

    # Handle Dict[str, X]
    if origin is dict or origin is Dict:
        if len(args) != 2:
            raise TypeError("Dict must have exactly two type arguments, e.g., Dict[str, int]")
        key_type, value_type = args
        if key_type is not str:
            raise TypeError("JSON object keys must be strings")
        return {
            "type": "object",
            "additionalProperties": _get_partial_schema_from_annotation(value_type),
        }

    # Handle Union[X, Y, Z]
    if origin is Union:
        return {"anyOf": [_get_partial_schema_from_annotation(t) for t in args]}

    # Handle Literal[X, Y, Z] (convert to anyOf with underlying types)
    if origin is Literal:
        unique_types = set(type(literal_value) for literal_value in args)
        if any(u not in PRIMITIVE_TYPE_MAP for u in unique_types):
            raise TypeError(
                f"Literal types with non-(str/int/float/bool) values are not supported, has types {unique_types}"
            )

        unique_json_types = [PRIMITIVE_TYPE_MAP[t] for t in unique_types]
        if len(unique_json_types) > 1:
            return {
                "anyOf": [
                    {"type": t, "enum": [v for v in args if PRIMITIVE_TYPE_MAP[type(v)] == t]}
                    for t in unique_json_types
                ]
            }
        return {"type": unique_json_types[0], "enum": list(args)}

    # Unsupported types
    raise TypeError(f"Unsupported type: {arg_type}")


def _is_annotated_type(type_: Type[Any]) -> bool:
    return get_origin(type_) is Annotated


def _unpack_annotated_types(arg_type: Type[Any]) -> Tuple[Type[Any], str]:
    if not _is_annotated_type(arg_type):
        raise TypeError(
            f"Argument of type {arg_type} is not Annotated. Either annotate your arguments "
            "or use the tool decorator with the description mode `only_docstring`."
        )

    annotated_args = get_args(arg_type)  # e.g. (<class 'str'>, 'param description')
    type_ = annotated_args[0]
    for annotation in annotated_args[1:]:
        if isinstance(annotation, str):
            return type_, annotation
    raise ValueError(f"Unable to find a string annotation in type {arg_type}")


def _get_tool_schema_no_parsing(
    tool_signature: inspect.Signature,
    tool_description: str,
    tool_name: str,
) -> Tuple[Dict[str, JsonSchemaParam], JsonSchemaParam]:

    if "self" in tool_signature.parameters.keys():
        raise TypeError(
            f"The tool decorator cannot be used directly on a class method, use `tool(my_object.my_method)` instead"
        )

    # Determining the schema of input parameters
    args_schema: Dict[str, JsonSchemaParam] = {}
    for param_name, param in tool_signature.parameters.items():
        if param_name in args_schema:
            raise TypeError(f"Duplicated input parameters in tool {tool_name}")

        if param.annotation == param.empty:
            raise TypeError(
                f"Found unspecified type annotation for parameter `{param_name}` of tool {tool_name}"
            )
        if _is_annotated_type(param.annotation):
            raise TypeError(
                f"Annotated types are not permitted when using the description mode `only_docstring`. "
                f"Parameter {param_name} of tool {tool_name} has type `{param.annotation}`"
            )
        param_schema = _get_partial_schema_from_annotation(param.annotation)

        if (param_default := param.default) != param.empty:
            param_schema["default"] = param_default

        args_schema[param_name] = param_schema

    # Determining the schema the tool output
    output_annotation = tool_signature.return_annotation
    if output_annotation == inspect.Parameter.empty:
        raise TypeError(f"Return annotation is not specified for tool {tool_name}")
    if _is_annotated_type(output_annotation):
        raise TypeError(
            f"Annotated types are not permitted when using the description mode `only_docstring`. "
            f"Return annotation of tool {tool_name} has type `{output_annotation}`"
        )
    output_schema = _get_partial_schema_from_annotation(output_annotation)
    return args_schema, output_schema


def _get_tool_schema_from_parsed_signature(
    tool_signature: inspect.Signature,
    tool_description: str,
    tool_name: str,
) -> Tuple[Dict[str, JsonSchemaParam], JsonSchemaParam]:

    if "self" in tool_signature.parameters.keys():
        raise TypeError(
            f"The tool decorator cannot be used directly on a class method, use `tool(my_object.my_method)` instead"
        )

    # Determining the schema of input parameters
    args_schema: Dict[str, JsonSchemaParam] = {}
    for param_name, annotated_param in tool_signature.parameters.items():
        if param_name in args_schema:
            raise TypeError(f"Duplicated input parameters in tool {tool_name}")

        if annotated_param.annotation == annotated_param.empty:
            raise TypeError(
                f"Found unspecified type annotation for parameter `{param_name}` of tool {tool_name}"
            )
        if not _is_annotated_type(annotated_param.annotation):
            raise TypeError(
                f"Description mode is `infer_from_signature` but parameter {param_name} of tool {tool_name} is not Annotated "
                f"(has type {annotated_param.annotation}). Either annotate the parameter or use the `only_docstring` description mode."
            )
        param_annotation, param_description = _unpack_annotated_types(annotated_param.annotation)
        param_schema = _get_partial_schema_from_annotation(param_annotation)

        param_schema["description"] = param_description
        if (param_default := annotated_param.default) != annotated_param.empty:
            param_schema["default"] = param_default

        args_schema[param_name] = param_schema

    # Determining the schema the tool output
    annotated_output_type = tool_signature.return_annotation
    if annotated_output_type == inspect.Parameter.empty:
        raise TypeError(f"Return annotation is not specified for tool {tool_name}")
    output_annotation: Any
    if _is_annotated_type(annotated_output_type):
        output_annotation, output_description = _unpack_annotated_types(annotated_output_type)
    else:
        output_annotation, output_description = annotated_output_type, ""

    output_schema = _get_partial_schema_from_annotation(output_annotation)
    if output_description:
        output_schema["description"] = output_description

    return args_schema, output_schema


def tool(
    *args: Union[str, Callable[..., Any]],
    description_mode: Literal[
        DescriptionMode.INFER_FROM_SIGNATURE,
        DescriptionMode.ONLY_DOCSTRING,
        DescriptionMode.EXTRACT_FROM_DOCSTRING,
    ] = DescriptionMode.INFER_FROM_SIGNATURE,
    output_descriptors: Optional[List[Property]] = None,
    requires_confirmation: bool = False,
) -> Union[ServerTool, Callable[[Callable[..., Any]], ServerTool]]:
    '''
    Make tools out of callables, can be used as a decorator or as a wrapper.

    Parameters
    ----------
    *args:
        The optional name and callable to convert to a ``ServerTool``.
        See the example section for common usage patterns.
    description_mode:
        Determines how parameter descriptions are set:

        * `"infer_from_signature"`: Extracted from the function signature.
        * `"only_docstring"`: Parameter descriptions are left empty; the full description is in the tool docstring.
        * `"extract_from_docstring"`: Parameter descriptions are parsed from the function's docstring. Currently not supported.

        Defaults to `"infer_from_signature"`.
    output_descriptors:
        list of properties to describe the tool outputs. Needed in case of tools with several outputs.
    requires_confirmation: bool
        Flag to make tool require confirmation before execution. Yields a ToolExecutionConfirmationStatus before its execution.
    Returns:
        The decorated/wrapper callable as a ``ServerTool``.

    Examples
    --------
    The ``tool`` helper can be used as a decorator:

    >>> from wayflowcore.tools import tool
    >>> @tool
    ... def my_callable() -> str:
    ...     """Callable description"""
    ...     return ""

    Tools can be renamed:

    >>> @tool("my_renamed_tool")
    ... def my_callable() -> str:
    ...     """Callable description"""
    ...     return ""

    The ``tool`` helper can automatically infer a tool input/output schema:

    >>> from typing import Annotated
    >>> @tool
    ... def my_callable(param1: Annotated[int, "param1 description"] = 2) -> int:
    ...     """Callable description"""
    ...     return 0

    The user can also specify not to infer the parameter descriptions (when they are in the docstring):

    >>> @tool(description_mode="only_docstring")
    ... def my_callable(param1: int = 2) -> int:
    ...     """Callable description
    ...     Parameters
    ...     ----------
    ...     param1:
    ...         Description of my parameter 1.
    ...     """
    ...     return 0

    The ``tool`` helper can also be used as a wrapper:

    >>> def my_callable() -> str:
    ...     """Callable description"""
    ...     return ""
    ...
    >>> my_tool = tool(my_callable)

    Use the ``tool`` helper as a wrapper to create stateful tools (tools that modifiy the internal state of the object):

    >>> class MyClass:
    ...     def my_callable(
    ...         self, param1: Annotated[int, "param1 description"] = 2
    ...     ) -> Annotated[int, "output description"]:
    ...         """Callable description"""
    ...         return 0
    ...
    >>> my_object = MyClass()
    >>> my_stateful_tool = tool(my_object.my_callable)

    Use the ``output_descriptors`` argument to make tools with several outputs:

    >>> from typing import Dict, Union
    >>> from wayflowcore.property import StringProperty, IntegerProperty
    >>> @tool(output_descriptors=[StringProperty(name='output1'), IntegerProperty(name='output2')])
    ... def my_callable() -> Dict[str, Union[str, int]]:
    ...     """Callable to return some outputs"""
    ...     return {'output1': 'some_output', 'output2': 2}

    Notes
    -----
    When creating tools, follow these guidelines to optimize tool calling performance with Agents:

    * **Choose descriptive names**: Select clear and concise names for your tools to facilitate understanding when using them in Agents.
    * **Write precise descriptions**: Provide precise descriptions for your tools, including information about their purpose, inputs, outputs, and any relevant constraints or assumptions.
    * **Use type annotations**: Annotate function parameters and return types with precise types to enable automatic schema inference and improve code readability.
    * **Specify return types**: Always specify the return type of your tool to ensure clarity (mandatory).

    '''

    def _make_tool(
        func: Callable[..., Any],
        tool_name: Optional[str] = None,
        description_mode: Literal[
            DescriptionMode.INFER_FROM_SIGNATURE,
            DescriptionMode.ONLY_DOCSTRING,
            DescriptionMode.EXTRACT_FROM_DOCSTRING,
        ] = DescriptionMode.INFER_FROM_SIGNATURE,
        output_descriptors: Optional[List[Property]] = None,
        requires_confirmation: bool = False,
    ) -> ServerTool:
        if inspect.isclass(func) or not hasattr(func, "__name__"):
            raise TypeError(
                f"Input callable type is not supported, callable is of of type `{func.__class__.__name__}`"
            )

        tool_description = inspect.getdoc(func)
        tool_signature = inspect.signature(func)

        if tool_description is None:
            raise ValueError(f"Empty callable description for callable {func}")

        tool_name = tool_name or func.__name__

        if description_mode == DescriptionMode.ONLY_DOCSTRING:
            args_schema, output_schema = _get_tool_schema_no_parsing(
                tool_signature, tool_description, tool_name
            )
        elif description_mode == DescriptionMode.INFER_FROM_SIGNATURE:
            args_schema, output_schema = _get_tool_schema_from_parsed_signature(
                tool_signature, tool_description, tool_name
            )
        elif description_mode == DescriptionMode.EXTRACT_FROM_DOCSTRING:
            raise NotImplementedError(
                "`extract_from_docstring` description mode is not yet supported"
            )
        else:
            raise ValueError("Not supported")

        return ServerTool(
            name=tool_name,
            description=tool_description,
            parameters=args_schema,
            output_descriptors=output_descriptors,
            output=output_schema if output_descriptors is None else None,
            func=func,
            requires_confirmation=requires_confirmation,
        )

    # When used as a wrapper, `args` can be [tool_name, callable] or [callable]
    # When used as a decorator, `args` can be [tool_name, callable] or [callable]
    if len(args) == 2 and (isinstance(args[0], str) and callable(args[1])):
        # Example case: wrapper with custom tool name
        # def my_callable():
        #     pass
        # my_tool = tool("my_callable1", my_callable)
        # here args[0] is the tool name, and args[1] the callable
        # we simply return the newly created ServerTool
        tool_name = args[0]
        return _make_tool(
            args[1], tool_name, description_mode, output_descriptors, requires_confirmation
        )
    elif len(args) == 1 and isinstance(args[0], str):
        # Example case: decorator with custom tool name
        # @tool("my_callable1")
        # def my_callable():
        #     pass
        # here args[0] is the tool name
        # Upon instantiation, first the `tool` function is called, directly followed
        # by the `_partial_with_name` function being called, thus converting the
        # callable to a ServerTool
        tool_name = args[0]

        def _partial_with_name(func: Callable[..., Any]) -> ServerTool:
            return _make_tool(
                func, tool_name, description_mode, output_descriptors, requires_confirmation
            )

        return _partial_with_name
    elif len(args) == 1 and callable(args[0]):
        # Example case: wrapper
        # def my_callable():
        #     pass
        # my_tool = tool(my_callable)
        # here args[0] is the callable
        # we simply return the newly created ServerTool
        return _make_tool(
            args[0], None, description_mode, output_descriptors, requires_confirmation
        )
    elif len(args) == 0:
        # Example case: decorator with user-specified description_mode
        # @tool(description_mode='only_docstring')
        # def my_callable(param1: int = 2) -> int:
        #     """Callable description"""
        #     return 0
        # Upon instantiation, first the `tool` function is called, directly followed
        # by the `_partial_no_name` function being called, thus converting the
        # callable to a ServerTool
        def _partial_no_name(func: Callable[..., Any]) -> ServerTool:
            return _make_tool(
                func, None, description_mode, output_descriptors, requires_confirmation
            )

        return _partial_no_name
    else:
        raise ValueError("Invalid usage of the `tool` helper")


def _find_json_schema_full_type(param_type: JsonSchemaParam) -> str:
    if "type" in param_type:
        json_type = param_type["type"]
        if isinstance(json_type, list):
            # another case of anyOf
            return " | ".join(json_type)
        return json_type
    elif "anyOf" in param_type:
        return " | ".join(_find_json_schema_full_type(p) for p in param_type["anyOf"])
    else:
        return "Any"


def _to_react_template_dict(tool: Tool) -> Dict[str, str]:
    if all(param_name in tool.description for param_name in tool.parameters):
        description = tool.description
    else:
        tool_as_str = f"{tool.description}\n\n"

        if len(tool.parameters) == 0:
            description = tool_as_str + "No input parameter"
        else:
            parameter_descriptions = []
            for parameter_name, parameter_info in tool.parameters.items():
                param_description = (
                    f"- {parameter_name}: {_find_json_schema_full_type(parameter_info)}"
                )
                if "default" in parameter_info:
                    param_description += f" (Optional, default={parameter_info['default']})"
                else:
                    param_description += " (Required)"
                if "description" in parameter_info:
                    param_description += f" {parameter_info['description']}"
                parameter_descriptions.append(param_description)

            formatted_parameter_descriptions = "\n".join(parameter_descriptions)
            description = tool_as_str + f"Parameters:\n{formatted_parameter_descriptions}"
    return {
        "name": tool.name,
        "description": description,
    }
