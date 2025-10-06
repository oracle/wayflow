# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors

# .. start-imports_multioutput_tool:
from typing import Dict, Union

from wayflowcore.flow import Flow
from wayflowcore.property import (
    BooleanProperty,
    DictProperty,
    IntegerProperty,
    StringProperty,
    UnionProperty,
)
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import ServerTool, tool

# .. end-imports_multioutput_tool:


# .. start-basic_tool_decorator:
@tool(description_mode="only_docstring")
def my_func() -> Dict[str, Union[str, int]]:
    """..."""
    return {"my_string": "Hello World!", "my_int": 2147483647, "my_bool": False}


flow = Flow.from_steps(
    [ToolExecutionStep(tool=my_func, output_mapping={ToolExecutionStep.TOOL_OUTPUT: "full_output"})]
)

conv = flow.start_conversation()
status = conv.execute()
print(status.output_values)
# .. end-basic_tool_decorator


# .. start-multi_output_decorator:
@tool(description_mode="only_docstring", output_descriptors=[
        StringProperty(name="my_string"),
        IntegerProperty(name="my_int"),
        BooleanProperty(name="my_bool"),
    ])
def my_func() -> Dict[str, Union[str, int]]:
    """..."""
    return {"my_string": "Hello World!", "my_int": 2147483647, "my_bool": False}


flow = Flow.from_steps(
    [
        ToolExecutionStep(
            tool=my_func,
            output_mapping={
                "my_int": "integer_output",
                "my_string": "string_output",
                "my_bool": "bool_output",
            },
        )
    ]
)

conv = flow.start_conversation()
status = conv.execute()
print(status.output_values)
# .. end-multi_output_decorator


# .. start-multi_output_server:
def my_func() -> Dict[str, Union[str, int]]:
    return {"my_string": "Hello World!", "my_int": 2147483647, "my_bool": False}


my_tool = ServerTool(
    name="my_tool",
    description="...",
    func=my_func,
    input_descriptors=[],
    output_descriptors=[
        StringProperty(name="my_string"),
        IntegerProperty(name="my_int"),
        BooleanProperty(name="my_bool"),
    ],
)

flow = Flow.from_steps(
    [
        ToolExecutionStep(
            tool=my_tool,
            output_mapping={
                "my_int": "integer_output",
                "my_string": "string_output",
                "my_bool": "bool_output",
            },
        )
    ]
)

conv = flow.start_conversation()
status = conv.execute()
print(status.output_values)
# .. end-multi_output_server
