# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
import os
from typing import Callable, Dict

import pytest

from wayflowcore.property import StringProperty
from wayflowcore.tools.servertools import ServerTool


@pytest.fixture
def mock_tool_registry() -> Dict[str, ServerTool]:
    get_tool: Callable[[str], ServerTool] = lambda name: ServerTool(
        name,
        "Says 'hello'",
        lambda: "hello",
        input_descriptors=[],
        output_descriptors=[StringProperty("greeting")],
    )

    compute_square_tool = ServerTool(
        name="compute_square_tool",
        description="Computes the square of a number",
        parameters={"x": {"title": "x", "type": "number"}},
        output={"title": "x_square", "type": "number"},
        func=lambda x: float(x * x),
    )

    division_tool = ServerTool(
        name="division_tool",
        description="Computes the ratio between two numbers",
        parameters={
            "numerator": {"title": "numerator", "type": "number"},
            "denominator": {"title": "denominator", "type": "number"},
        },
        output={"title": "result", "type": "number"},
        func=lambda numerator, denominator: float(numerator / denominator),
    )

    squared_sum_tool = ServerTool(
        name="squared_sum_tool",
        description="Computes the squared sum of a list of numbers",
        parameters={
            "x_list": {
                "title": "x_list",
                "type": "array",
                "items": {"type": "number"},
            }
        },
        output={"title": "squared_sum", "type": "number"},
        func=lambda x_list: float(sum(x_list) ** 2),
    )

    return {
        "run_python_code": get_tool("run_python_code"),
        "gather_user_account_information": get_tool("gather_user_account_information"),
        "add_user_account": get_tool("add_user_account"),
        "delete_user_account_information": get_tool("delete_user_account_information"),
        "compute_square_tool": compute_square_tool,
        "division_tool": division_tool,
        "squared_sum_tool": squared_sum_tool,
    }


@pytest.fixture(autouse=True)
def fake_openai_key():
    old_value = os.environ.get("OPENAI_API_KEY", None)
    try:
        os.environ["OPENAI_API_KEY"] = "fake-api-key"
        yield
    finally:
        if old_value is None:
            del os.environ["OPENAI_API_KEY"]
        else:
            os.environ["OPENAI_API_KEY"] = old_value
