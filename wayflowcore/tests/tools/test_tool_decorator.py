from typing import Any, Callable
from typing_extensions import assert_type
from wayflowcore.property import StringProperty
from wayflowcore.tools.servertools import ServerTool
from wayflowcore.tools.toolhelpers import DescriptionMode, tool


def test_tool_decorator_result_type_is_correct() -> None:
    # Wrapper with different name
    tool_one = tool("tool_one")
    assert_type(tool_one, Callable[[Callable[..., Any]], ServerTool])
    assert isinstance(tool_one, Callable)

    def actual_func() -> None:
        """Actual func"""

    func_tool = tool_one(actual_func)
    assert_type(func_tool, ServerTool)
    assert isinstance(func_tool, ServerTool)
    assert func_tool.name == "tool_one"

    # Decorator with different tool name

    @tool("real_function_name")
    def another_func() -> None:
        """Another func"""

    assert_type(another_func, ServerTool)
    assert isinstance(another_func, ServerTool)
    assert another_func.name == "real_function_name"

    # Wrapper with name and function passed as arguments
    def func_two() -> None:
        """Just a func"""

    tool_two = tool("tool_two", func_two)
    assert_type(tool_two, ServerTool)
    assert isinstance(tool_two, ServerTool)

    # Decorator with description mode
    @tool("tool_three", description_mode=DescriptionMode.ONLY_DOCSTRING)
    def tool_three() -> None:
        """tool_three function"""

    assert_type(tool_three, ServerTool)
    assert isinstance(tool_three, ServerTool)

    # Decorator with no arguments passed
    @tool
    def tool_four() -> None:
        """tool_four function"""

    assert_type(tool_four, ServerTool)
    assert isinstance(tool_four, ServerTool)

    # Decorator with only description mode passed
    @tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
    def tool_five() -> None:
        """tool_five function"""

    assert_type(tool_five, ServerTool)
    assert isinstance(tool_five, ServerTool)

    # Decorator with only description mode passed as a string
    @tool(description_mode="only_docstring")
    def tool_six() -> None:
        """tool_six function"""

    assert_type(tool_six, ServerTool)
    assert isinstance(tool_six, ServerTool)

    # Decorator with only output_descriptors
    @tool(output_descriptors=[StringProperty("result")])
    def tool_seven() -> str:
        """tool_seven function"""
        return "result"

    assert_type(tool_seven, ServerTool)
    assert isinstance(tool_seven, ServerTool)
    output_desc = tool_seven.output_descriptors[0]
    assert output_desc.name == "result"
    assert isinstance(output_desc, StringProperty)

    # Decorator with only requires_confirmation
    @tool(requires_confirmation=True)
    def tool_eight() -> None:
        """tool_eight function"""

    assert_type(tool_eight, ServerTool)
    assert isinstance(tool_eight, ServerTool)
    assert tool_eight.requires_confirmation

    # Decorator with name, output_descriptors and requires_confirmation
    @tool(
        "servertool_nine",
        requires_confirmation=False,
        output_descriptors=[StringProperty("result_nine")],
        description_mode="infer_from_signature",
    )
    def tool_nine() -> str:
        """tool_nine function"""
        return "result"

    assert_type(tool_nine, ServerTool)
    assert isinstance(tool_nine, ServerTool)

    assert tool_nine.name == "servertool_nine"
    assert not tool_nine.requires_confirmation

    assert tool_nine.description == "tool_nine function"

    output_desc_nine = tool_nine.output_descriptors[0]
    assert output_desc_nine.name == "result_nine"
    assert isinstance(output_desc_nine, StringProperty)
