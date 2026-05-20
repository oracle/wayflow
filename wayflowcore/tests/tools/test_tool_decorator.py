from typing import Any, Callable
from typing_extensions import assert_type
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
