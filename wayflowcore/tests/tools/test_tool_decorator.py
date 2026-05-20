from typing import Any, Callable
from typing_extensions import assert_type
from wayflowcore.tools.servertools import ServerTool
from wayflowcore.tools.toolhelpers import DescriptionMode, tool


def test_tool_decorator_result_type_is_correct() -> None:
    tool_one = tool("tool_one")
    assert_type(tool_one, Callable[[Callable[..., Any]], ServerTool])
    assert isinstance(tool_one, Callable)

    def func_two() -> None:
        """Just a func"""

    tool_two = tool("tool_two", func_two)
    assert_type(tool_two, ServerTool)
    assert isinstance(tool_two, ServerTool)

    @tool("tool_three", description_mode=DescriptionMode.ONLY_DOCSTRING)
    def tool_three() -> None:
        """tool_three function"""

    @tool
    def tool_four() -> None:
        """tool_four function"""

    assert_type(tool_three, ServerTool)
    assert_type(tool_four, ServerTool)

    assert isinstance(tool_three, ServerTool)
    assert isinstance(tool_four, ServerTool)
