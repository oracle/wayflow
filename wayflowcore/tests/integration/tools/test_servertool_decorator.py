# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Type, Union

import pytest

from wayflowcore.property import IntegerProperty, JsonSchemaParam, StringProperty, UnionProperty
from wayflowcore.tools import ServerTool, tool
from wayflowcore.tools.toolhelpers import _get_partial_schema_from_annotation


def are_json_schema_equal(schema1: dict, schema2: dict, remove_title: bool = True) -> bool:
    remove_title = False
    if remove_title and "title" in schema1:
        del schema1["title"]

    for key in ["anyOf"]:
        if key in schema1:
            if key not in schema2:
                return False
            if len(schema1[key]) != len(schema2[key]):
                return False
            for actual_type in schema1[key]:
                if not any(
                    are_json_schema_equal(actual_type, expected_type, remove_title=remove_title)
                    for expected_type in schema2[key]
                ):
                    return False

    if "properties" in schema1:
        if "properties" not in schema2:
            return False
        if set(schema1["properties"]) != set(schema1["properties"]):
            return False
        for p_name in schema1["properties"]:
            if not are_json_schema_equal(
                schema1["properties"][p_name], schema2["properties"][p_name]
            ):
                return False

    for key in ["additionalProperties", "items"]:
        if key in schema1:
            if key not in schema2:
                return False
            if not are_json_schema_equal(schema1[key], schema2[key]):
                return False

    return {
        k: v
        for k, v in schema1.items()
        if k not in {"additionalProperties", "properties", "anyOf", "items"}
    } == {
        k: v
        for k, v in schema2.items()
        if k not in {"additionalProperties", "properties", "anyOf", "items"}
    }


@pytest.mark.parametrize(
    "arg_type, expected_schema",
    [
        # Primitive types
        (str, {"type": "string"}),
        (int, {"type": "integer"}),
        (bool, {"type": "boolean"}),
        (float, {"type": "number"}),
        # List[X] types
        (List[str], {"type": "array", "items": {"type": "string"}}),
        (List[int], {"type": "array", "items": {"type": "integer"}}),
        (List[bool], {"type": "array", "items": {"type": "boolean"}}),
        (List[float], {"type": "array", "items": {"type": "number"}}),
        # Nested lists
        (
            List[List[int]],
            {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}},
        ),
        (
            List[List[List[str]]],
            {
                "type": "array",
                "items": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
            },
        ),
        # Dict[str, X] (valid cases)
        (Dict[str, int], {"type": "object", "additionalProperties": {"type": "integer"}}),
        (Dict[str, str], {"type": "object", "additionalProperties": {"type": "string"}}),
        (
            Dict[str, List[str]],
            {
                "type": "object",
                "additionalProperties": {"type": "array", "items": {"type": "string"}},
            },
        ),
        (
            Dict[str, Dict[str, int]],
            {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "additionalProperties": {"type": "integer"},
                },
            },
        ),
        # Optional[X] (becomes Union[X, None])
        (Optional[str], {"anyOf": [{"type": "string"}, {"type": "null"}]}),
        (Optional[int], {"anyOf": [{"type": "integer"}, {"type": "null"}]}),
        (
            Optional[List[str]],
            {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]},
        ),
        (
            Optional[Dict[str, int]],
            {
                "anyOf": [
                    {
                        "type": "object",
                        "additionalProperties": {"type": "integer"},
                    },
                    {"type": "null"},
                ]
            },
        ),
        # Union[X, Y, Z]
        (Union[int, str], {"anyOf": [{"type": "integer"}, {"type": "string"}]}),
        (
            Union[Dict[str, int], List[str]],
            {
                "anyOf": [
                    {"type": "object", "additionalProperties": {"type": "integer"}},
                    {"type": "array", "items": {"type": "string"}},
                ]
            },
        ),
        # Literal[X, Y, Z] should be treated as a union of the types, for now we only support string
        (Literal["a", "b", "c"], {"type": "string", "enum": ["a", "b", "c"]}),
        # (Literal[1, 2, 3], {"anyOf": [{"type": "integer"}]}),
        # (Literal[True, False], {"anyOf": [{"type": "boolean"}]}),
    ],
)
def test_get_json_schema_from_annotation_valid_cases(arg_type: Type[Any], expected_schema: dict):
    """Test that _get_json_schema_from_annotation handles valid cases correctly."""
    assert are_json_schema_equal(_get_partial_schema_from_annotation(arg_type), expected_schema)


@pytest.mark.parametrize(
    "arg_type",
    [
        # Unsupported types
        Any,  # "Any" should not be supported
        object,  # Generic object should not be supported
        Dict[int, str],  # Non-string keys in Dict should not be supported
        set,  # Sets are not valid JSON schema types
        tuple,  # Tuples are not explicitly handled
        complex,  # Complex numbers are not valid JSON schema types
        bytes,  # Bytes are not valid JSON schema types
        frozenset,  # Frozensets are not valid JSON schema types
        Enum,
    ],
)
def test_get_json_schema_from_annotation_invalid_cases(arg_type: Type[Any]):
    """Test that _get_json_schema_from_annotation raises an error on unsupported types."""
    with pytest.raises(TypeError):
        _get_partial_schema_from_annotation(arg_type)


def test_get_json_schema_from_annotation_empty_annotation():
    """Test that an empty annotation returns proper json."""
    json_schema = _get_partial_schema_from_annotation(None)
    assert json_schema == {"type": "null"}


# Additional Edge Cases
@pytest.mark.parametrize(
    "arg_type, expected_schema",
    [
        # Union with nested structures
        (
            Union[List[int], Dict[str, str]],
            {
                "anyOf": [
                    {"type": "array", "items": {"type": "integer"}},
                    {"type": "object", "additionalProperties": {"type": "string"}},
                ]
            },
        ),
        # Deeply nested structures
        (
            List[Dict[str, List[int]]],
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": {"type": "array", "items": {"type": "integer"}},
                },
            },
        ),
    ],
)
def test_get_json_schema_from_annotation_edge_cases(arg_type: Type[Any], expected_schema: dict):
    """Test _get_json_schema_from_annotation with more complex nested types."""
    assert are_json_schema_equal(_get_partial_schema_from_annotation(arg_type), expected_schema)


@pytest.mark.parametrize(
    "arg_type, expected_schema",
    [
        # Optional inside Lists
        (
            Optional[List[int]],
            {"anyOf": [{"type": "array", "items": {"type": "integer"}}, {"type": "null"}]},
        ),
        (
            List[Optional[int]],
            {"type": "array", "items": {"anyOf": [{"type": "integer"}, {"type": "null"}]}},
        ),
        # Optional inside Dict
        (
            Dict[str, Optional[int]],
            {
                "type": "object",
                "additionalProperties": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            },
        ),
        (
            Dict[str, Optional[List[int]]],
            {
                "type": "object",
                "additionalProperties": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        {"type": "null"},
                    ]
                },
            },
        ),
        # Optional inside both List & Dict
        (
            List[Dict[str, Optional[int]]],
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                },
            },
        ),
    ],
)
def test_get_json_schema_from_annotation_nested_optional_cases(
    arg_type: Type[Any], expected_schema: dict
):
    """Test Optional inside List and Dict structures."""
    assert are_json_schema_equal(_get_partial_schema_from_annotation(arg_type), expected_schema)


# Helper function to check tool correctness
def _check_tool_correctness(
    tool_instance: ServerTool,
    expected_name: str,
    expected_description: str,
    expected_parameters: Dict[str, JsonSchemaParam],
    expected_output: JsonSchemaParam,
):
    assert isinstance(tool_instance, ServerTool)
    assert tool_instance.name == expected_name
    assert tool_instance.description == expected_description
    tool_params = tool_instance.to_openai_format()["function"]["parameters"].get("properties", {})
    assert set(tool_params.keys()) == set(expected_parameters.keys())
    for param_name in expected_parameters.keys():
        param_schema = tool_params[param_name]
        assert are_json_schema_equal(param_schema, expected_parameters[param_name])
    assert are_json_schema_equal(tool_instance.output, expected_output, remove_title=False)


# Positive Tests


def test_basic_decorator():
    @tool
    def my_callable(param1: Annotated[int, "param1 desc"] = 2) -> Annotated[int, "output desc"]:
        """Callable description"""
        return 0

    _check_tool_correctness(
        my_callable,
        "my_callable",
        "Callable description",
        {
            "param1": {
                "type": "integer",
                "description": "param1 desc",
                "default": 2,
                "title": "Param1",
            }
        },
        {"description": "output desc", "type": "integer"},
    )


def test_decorator_with_custom_name():
    @tool("custom_name")
    def my_callable(param1: Annotated[int, "param1 desc"] = 2) -> Annotated[int, "output desc"]:
        """Callable description"""
        return 0

    _check_tool_correctness(
        my_callable,
        "custom_name",
        "Callable description",
        {
            "param1": {
                "type": "integer",
                "description": "param1 desc",
                "default": 2,
                "title": "Param1",
            }
        },
        {"description": "output desc", "type": "integer"},
    )


def test_wrapper():
    def my_callable(param1: Annotated[int, "param1 desc"] = 2) -> Annotated[int, "output desc"]:
        """Callable description"""
        return 0

    my_tool = tool(my_callable)

    _check_tool_correctness(
        my_tool,
        "my_callable",
        "Callable description",
        {
            "param1": {
                "type": "integer",
                "description": "param1 desc",
                "default": 2,
                "title": "Param1",
            }
        },
        {"description": "output desc", "type": "integer"},
    )


def test_wrapper_with_custom_name():
    def my_callable(param1: Annotated[int, "param1 desc"] = 2) -> Annotated[int, "output desc"]:
        """Callable description"""
        return 0

    my_tool = tool("custom_name", my_callable)

    _check_tool_correctness(
        my_tool,
        "custom_name",
        "Callable description",
        {
            "param1": {
                "type": "integer",
                "description": "param1 desc",
                "default": 2,
                "title": "Param1",
            }
        },
        {"description": "output desc", "type": "integer"},
    )


def test_wrapper_with_stateful_tool():
    class MyTool:
        def my_callable(
            self, param1: Annotated[int, "param1 desc"] = 2
        ) -> Annotated[int, "output desc"]:
            """Callable description"""
            return 0

    _check_tool_correctness(
        tool(MyTool().my_callable),
        "my_callable",
        "Callable description",
        {
            "param1": {
                "type": "integer",
                "description": "param1 desc",
                "default": 2,
                "title": "Param1",
            }
        },
        {"description": "output desc", "type": "integer"},
    )


def test_wrapper_with_staticmethod():
    class MyTool:
        @staticmethod
        def my_callable(param1: Annotated[int, "param1 desc"] = 2) -> Annotated[int, "output desc"]:
            """Callable description"""
            return 0

    _check_tool_correctness(
        tool(MyTool.my_callable),
        "my_callable",
        "Callable description",
        {
            "param1": {
                "type": "integer",
                "description": "param1 desc",
                "default": 2,
                "title": "Param1",
            }
        },
        {"description": "output desc", "type": "integer"},
    )


def test_complex_types():
    @tool
    def complex_tool(
        param1: Annotated[List[Dict[str, Union[str, int]]], "Complex param"],
        param2: Annotated[Optional[bool], "Optional param"] = None,
    ) -> Annotated[Dict[str, List[int]], "Complex output"]:
        """Complex tool description"""
        return {"result": [1, 2, 3]}

    _check_tool_correctness(
        complex_tool,
        "complex_tool",
        "Complex tool description",
        {
            "param1": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
                },
                "description": "Complex param",
                "title": "Param1",
            },
            "param2": {
                "type": "boolean",
                "description": "Optional param",
                "default": None,
                "title": "Param2",
            },
        },
        {
            "type": "object",
            "additionalProperties": {"type": "array", "items": {"type": "integer"}},
            "description": "Complex output",
        },
    )


def test_many_parameters():
    @tool
    def many_params_tool(
        param1: Annotated[int, "Param 1 desc"] = 1,
        param2: Annotated[str, "Param 2 desc"] = "default",
        param3: Annotated[float, "Param 3 desc"] = 3.14,
        param4: Annotated[bool, "Param 4 desc"] = True,
        param5: Annotated[List[int], "Param 5 desc"] = [1, 2, 3],
        param6: Annotated[Dict[str, str], "Param 6 desc"] = {"key": "value"},
        param7: Annotated[Optional[int], "Param 7 desc"] = None,
        param8: Annotated[Union[int, str], "Param 8 desc"] = "union",
        param9: Annotated[List[Dict[str, int]], "Param 9 desc"] = [{"a": 1}],
        param10: Annotated[Dict[str, List[str]], "Param 10 desc"] = {"b": ["c"]},
    ) -> Annotated[str, "Output description"]:
        """Many parameters tool description"""
        return "result"

    expected_parameters = {
        "param1": {
            "type": "integer",
            "description": "Param 1 desc",
            "default": 1,
            "title": "Param1",
        },
        "param2": {
            "type": "string",
            "description": "Param 2 desc",
            "default": "default",
            "title": "Param2",
        },
        "param3": {
            "type": "number",
            "description": "Param 3 desc",
            "default": 3.14,
            "title": "Param3",
        },
        "param4": {
            "type": "boolean",
            "description": "Param 4 desc",
            "default": True,
            "title": "Param4",
        },
        "param5": {
            "type": "array",
            "description": "Param 5 desc",
            "default": [1, 2, 3],
            "items": {"type": "integer"},
            "title": "Param5",
        },
        "param6": {
            "type": "object",
            "description": "Param 6 desc",
            "default": {"key": "value"},
            "additionalProperties": {"type": "string"},
            "title": "Param6",
        },
        "param7": {
            "description": "Param 7 desc",
            "default": None,
            "type": "integer",
            "title": "Param7",
        },
        "param8": {
            "description": "Param 8 desc",
            "default": "union",
            "anyOf": [{"type": "integer"}, {"type": "string"}],
            "title": "Param8",
        },
        "param9": {
            "type": "array",
            "description": "Param 9 desc",
            "default": [{"a": 1}],
            "items": {"type": "object", "additionalProperties": {"type": "integer"}},
            "title": "Param9",
        },
        "param10": {
            "type": "object",
            "description": "Param 10 desc",
            "default": {"b": ["c"]},
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
            "title": "Param10",
        },
    }

    _check_tool_correctness(
        many_params_tool,
        "many_params_tool",
        "Many parameters tool description",
        expected_parameters,
        {"description": "Output description", "type": "string"},
    )


def test_description_mode_only_docstring():
    @tool(description_mode="only_docstring")
    def docstring_tool(param1: int = 2) -> int:
        """Docstring tool description

        Parameters
        ----------
        param1 : int
            Description of param1

        Returns
        -------
        int
            Description of return value
        """
        return 0

    _check_tool_correctness(
        docstring_tool,
        "docstring_tool",
        "Docstring tool description\n\nParameters\n----------\nparam1 : int\n    Description of param1\n\nReturns\n-------\nint\n    Description of return value",
        {"param1": {"type": "integer", "default": 2, "title": "Param1"}},
        {"type": "integer"},
    )


def test_tool_with_optional_only_docstring():

    @tool(description_mode="only_docstring")
    def query_studies(
        page: Optional[int] = 1,
        protocol_number: Optional[str] = None,
    ) -> Dict[str, str]:
        """Call the Activate API."""
        return {"test": "test"}

    _check_tool_correctness(
        query_studies,
        "query_studies",
        "Call the Activate API.",
        {
            "page": {"type": "integer", "default": 1, "title": "Page"},
            "protocol_number": {"type": "string", "default": None, "title": "Protocol Number"},
        },
        {
            "type": "object",
            "additionalProperties": {
                "type": "string",
            },
        },
    )


def test_tool_with_optional_infer_signature():

    @tool
    def query_studies(
        page: Annotated[Optional[int], "The page number to return specified as a number."] = 1,
        protocol_number: Annotated[Optional[str], "Filter by protocol_number."] = None,
    ) -> Dict[str, str]:
        """Call the Activate API."""
        return {"test": "test"}

    _check_tool_correctness(
        query_studies,
        "query_studies",
        "Call the Activate API.",
        {
            "page": {
                "type": "integer",
                "description": "The page number to return specified as a number.",
                "default": 1,
                "title": "Page",
            },
            "protocol_number": {
                "type": "string",
                "description": "Filter by protocol_number.",
                "default": None,
                "title": "Protocol Number",
            },
        },
        {
            "type": "object",
            "additionalProperties": {
                "type": "string",
            },
        },
    )


# Negative Tests


def test_decorator_incorrect_use_of_args():
    with pytest.raises(ValueError):

        @tool("arg1", "arg2", "arg3")
        def my_callable() -> str:
            """Callable description"""
            return ""


def test_decorator_no_docstring():
    with pytest.raises(ValueError):

        @tool
        def my_callable() -> str:
            return ""


def test_decorator_no_returntype():
    with pytest.raises(TypeError):

        @tool
        def my_callable():
            """Callable description"""
            return ""


def test_decorator_unsupported_classtype():
    with pytest.raises(TypeError):

        @tool
        class MyTool:
            """Class description"""


def test_decorator_unsupported_instantiatedclass():
    class MyTool:
        """class docstring"""

        def __call__(self) -> str:
            """Callable description"""
            return ""

    with pytest.raises(TypeError):
        tool(MyTool())


def test_decorator_unsupported_use():
    with pytest.raises(TypeError):

        class MyTool:
            @tool
            def __call__(self) -> str:
                """Callable description"""
                return ""


def test_invalid_description_mode():
    with pytest.raises(ValueError):

        @tool(description_mode="invalid_mode")
        def my_callable() -> str:
            """Callable description"""
            return ""


def test_extract_from_docstring_not_implemented():
    with pytest.raises(NotImplementedError):

        @tool(description_mode="extract_from_docstring")
        def my_callable() -> str:
            """Callable description"""
            return ""


def test_missing_annotation():
    with pytest.raises(TypeError):

        @tool
        def my_callable(param1) -> str:
            """Callable description"""
            return ""


def test_invalid_dict_key_type():
    with pytest.raises(TypeError):

        @tool(description_mode="only_docstring")
        def my_callable(param1: Dict[int, str]) -> str:
            """Callable description"""
            return ""


def test_unsupported_type():
    with pytest.raises(TypeError):

        @tool(description_mode="only_docstring")
        def my_callable(param1: set) -> str:
            """Callable description"""
            return ""


def test_missing_list_type():
    with pytest.raises(TypeError):

        @tool(description_mode="only_docstring")
        def my_callable(param1: List) -> str:
            """Callable description"""
            return ""


# Additional edge cases


def test_nested_optional_types():
    @tool
    def nested_optional(
        param1: Annotated[Optional[List[Optional[int]]], "Nested optional"],
    ) -> Annotated[Optional[Dict[str, Optional[List[int]]]], "Nested optional output"]:
        """Nested optional types"""
        return None

    _check_tool_correctness(
        nested_optional,
        "nested_optional",
        "Nested optional types",
        {
            "param1": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Nested optional",
                "title": "Param1",
            }
        },
        {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": {
                        "anyOf": [
                            {
                                "type": "array",
                                "items": {"type": "integer"},
                            },
                            {"type": "null"},
                        ]
                    },
                },
                {"type": "null"},
            ],
            "description": "Nested optional output",
        },
    )


def test_unsupported_literal_types():
    @tool
    def literal_tool(
        param1: Annotated[Literal["a", "b", "c"], "Literal param"],
    ) -> Annotated[Literal[1, 2, 3], "Literal output"]:
        """Literal types tool"""
        return 1

    assert literal_tool.input_descriptors == [
        StringProperty(name="param1", description="Literal param", enum=("a", "b", "c"))
    ]


def test_literal_types_only_docstring():
    @tool(description_mode="only_docstring")
    def literal_tool(param1: Literal["a", "b", "c"]) -> str:
        """Literal types tool"""
        return ""

    assert literal_tool.input_descriptors == [StringProperty(name="param1", enum=("a", "b", "c"))]


def test_literal_types_only_docstring_with_mixed_types():
    @tool(description_mode="only_docstring")
    def literal_tool(param1: Literal["a", "b", 2]) -> str:
        """Literal types tool"""
        return ""

    assert len(literal_tool.input_descriptors) == 1
    input_descriptor = next(iter(literal_tool.input_descriptors))
    assert isinstance(input_descriptor, UnionProperty)
    assert set(input_descriptor.any_of) == {
        IntegerProperty(enum=(2,)),
        StringProperty(enum=("a", "b")),
    }


def test_literal_types_only_docstring_with_mixed_unsupported_types():

    class MyCustomEnum(Enum):
        VAL = 0

    with pytest.raises(
        TypeError, match="Literal types with non-\\(str/int/float/bool\\) values are not supported"
    ):

        @tool(description_mode="only_docstring")
        def literal_tool(param1: Literal["a", "b", MyCustomEnum.VAL]) -> str:
            """Literal types tool"""
            return ""


def test_union_types():
    @tool
    def union_tool(
        param1: Annotated[Union[int, str, List[bool]], "Union param"],
    ) -> Annotated[Union[Dict[str, int], List[str], None], "Union output"]:
        """Union types tool"""
        return None

    _check_tool_correctness(
        union_tool,
        "union_tool",
        "Union types tool",
        {
            "param1": {
                "anyOf": [
                    {"type": "integer"},
                    {"type": "string"},
                    {"type": "array", "items": {"type": "boolean"}},
                ],
                "description": "Union param",
                "title": "Param1",
            }
        },
        {
            "anyOf": [
                {"type": "object", "additionalProperties": {"type": "integer"}},
                {"type": "array", "items": {"type": "string"}},
                {"type": "null"},
            ],
            "description": "Union output",
        },
    )


def test_complex_nested_types():
    @tool
    def complex_nested_tool(
        param1: Annotated[
            Dict[str, List[Union[int, Dict[str, Optional[bool]]]]], "Complex nested param"
        ],
        param2: Annotated[
            List[Union[str, List[Dict[str, Union[int, float]]]]], "Another complex param"
        ],
    ) -> Annotated[List[Dict[str, Union[int, List[Optional[str]]]]], "Complex nested output"]:
        """Complex nested types tool"""
        return None

    _check_tool_correctness(
        complex_nested_tool,
        "complex_nested_tool",
        "Complex nested types tool",
        {
            "param1": {
                "type": "object",
                "additionalProperties": {
                    "type": "array",
                    "items": {
                        "anyOf": [
                            {"type": "integer"},
                            {
                                "type": "object",
                                "additionalProperties": {
                                    "anyOf": [
                                        {
                                            "type": "boolean",
                                        },
                                        {"type": "null"},
                                    ]
                                },
                            },
                        ]
                    },
                },
                "description": "Complex nested param",
                "title": "Param1",
            },
            "param2": {
                "type": "array",
                "items": {
                    "anyOf": [
                        {"type": "string"},
                        {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": {
                                    "anyOf": [{"type": "integer"}, {"type": "number"}]
                                },
                            },
                        },
                    ]
                },
                "description": "Another complex param",
                "title": "Param2",
            },
        },
        {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": {
                    "anyOf": [
                        {"type": "integer"},
                        {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "null"},
                                ]
                            },
                        },
                    ]
                },
            },
            "description": "Complex nested output",
        },
    )


def test_default_values():
    @tool
    def default_values_tool(
        param1: Annotated[int, "Int param"] = 42,
        param2: Annotated[Optional[str], "Optional str param"] = None,
        param3: Annotated[List[int], "List param"] = [1, 2, 3],
        param4: Annotated[Dict[str, bool], "Dict param"] = {"key": True},
    ) -> Annotated[str, "Output"]:
        """Default values tool"""
        return "result"

    _check_tool_correctness(
        default_values_tool,
        "default_values_tool",
        "Default values tool",
        {
            "param1": {
                "type": "integer",
                "description": "Int param",
                "default": 42,
                "title": "Param1",
            },
            "param2": {
                "type": "string",
                "description": "Optional str param",
                "default": None,
                "title": "Param2",
            },
            "param3": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List param",
                "default": [1, 2, 3],
                "title": "Param3",
            },
            "param4": {
                "type": "object",
                "additionalProperties": {"type": "boolean"},
                "description": "Dict param",
                "default": {"key": True},
                "title": "Param4",
            },
        },
        {"type": "string", "description": "Output"},
    )


def test_description_mode_infer_from_signature():
    @tool(description_mode="infer_from_signature")
    def infer_signature_tool(
        param1: Annotated[int, "Int param description"],
        param2: Annotated[str, "Str param description"],
    ) -> Annotated[bool, "Bool output description"]:
        """Infer from signature tool"""
        return True

    _check_tool_correctness(
        infer_signature_tool,
        "infer_signature_tool",
        "Infer from signature tool",
        {
            "param1": {
                "type": "integer",
                "description": "Int param description",
                "title": "Param1",
            },
            "param2": {"type": "string", "description": "Str param description", "title": "Param2"},
        },
        {"type": "boolean", "description": "Bool output description"},
    )


# Negative tests


def test_tool_with_unsupported_annotation():
    with pytest.raises(TypeError):

        @tool
        def unsupported_tool(param: Annotated[complex, "Complex param"]) -> str:
            """Unsupported tool"""
            return "result"


def test_tool_with_missing_docstring():
    with pytest.raises(ValueError):

        @tool
        def no_docstring_tool(param: int) -> str:
            return "result"


def test_tool_with_invalid_description_mode():
    with pytest.raises(ValueError):

        @tool(description_mode="invalid_mode")
        def invalid_mode_tool(param: int) -> str:
            """Invalid mode tool"""
            return "result"


def test_tool_from_tool_decorator_can_return_several_outputs():
    @tool(output_descriptors=[StringProperty(name="o1"), IntegerProperty(name="o2")])
    def several_outputs_tool() -> Dict[str, Union[str, int]]:
        """A tool returning several outputs"""
        return {"o1": "some_text", "o2": 2}

    _check_tool_correctness(
        several_outputs_tool,
        "several_outputs_tool",
        "A tool returning several outputs",
        {},
        {
            "type": "object",
            "properties": {
                "o1": {"type": "string", "title": "o1"},
                "o2": {"type": "integer", "title": "o2"},
            },
        },
    )
    assert set(d.name for d in several_outputs_tool.output_descriptors) == {"o1", "o2"}
