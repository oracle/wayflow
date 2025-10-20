# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from typing import Annotated, Any, Callable, Dict, List, Optional, Union

import pytest

from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
)
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import (
    _run_single_step_and_return_conv_and_status,
    create_single_step_flow,
    run_flow_and_return_outputs,
    run_step_and_return_outputs,
)
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.property import (
    AnyProperty,
    BooleanProperty,
    DictProperty,
    FloatProperty,
    IntegerProperty,
    ListProperty,
    NullProperty,
    ObjectProperty,
    Property,
    StringProperty,
    UnionProperty,
)
from wayflowcore.steps import FlowExecutionStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.tools import ClientTool, ServerTool, ToolRequest, ToolResult, tool

from ...testhelpers.dummy import create_dummy_server_tool
from ...testhelpers.flowscriptrunner import (
    FlowScript,
    FlowScriptInteraction,
    FlowScriptRunner,
    IODictCheck,
)
from ...testhelpers.teststeps import _InputOutputSpecifiedStep


def create_weather_server_tool():
    import random

    @tool(description_mode="only_docstring")
    def get_weather(location: str) -> str:
        """Returns the weather in the provided location
        Parameters
        ----------
        location: str
            The location to get the weather from
        """
        return random.choice(["sunny", "rainy"])  # nosec

    return get_weather


def create_range_server_tool():

    @tool(description_mode="only_docstring")
    def create_range(stop: int) -> str:
        """Returns a list of integers from 0 to `stop`
        Parameters
        ----------
        stop: int
            the end of the range (excluded)
        """
        return f"Range: {str(list(range(stop)))}"

    return create_range


def create_error_server_tool():

    @tool(description_mode="only_docstring")
    def compute_error(y_true: float, y_pred: float, absolute: bool = False) -> str:
        """Returns the error.
        - If absolute==True, returns |y_true-y_pred|
        - If absolute==False, returns y_true-y_pred
        Parameters
        ----------
        y_true
            the true value
        y_pred
            the predicted value
        absolute
            whether we want the error in absolute value
        """
        error = (y_true - y_pred) / y_true
        if absolute:
            error = abs(error)
        error_percent = int(round(100 * error))
        return f"Computed error: {error_percent}%"

    return compute_error


def create_list_io_server_tool():

    @tool(description_mode="only_docstring")
    def double_list(arr: List[int]) -> List[int]:
        """Multiplies all list entries by 2.
        Parameters
        ----------
        arr
            the input list
        """
        return [i * 2 for i in arr]

    return double_list


def create_dict_io_server_tool() -> ServerTool:

    @tool(description_mode="only_docstring")
    def duplicate_list_values(input_dict: Dict[str, List[int]]) -> Dict[str, List[int]]:
        """Duplicates all lists for the input_dict keys.
        Parameters
        ----------
        input_dict
            the input dictionary
        """
        return {k: 2 * v for k, v in input_dict.items()}

    return duplicate_list_values


def create_builtin_types_list_to_dict_io_server_tool():

    @tool(description_mode="only_docstring")
    def list_to_dict(arr: List[int]) -> Dict[str, int]:
        """Turns list to enumerated dictionary
        Parameters
        ----------
        arr
            the input list
        """
        return {i: v for i, v in enumerate(arr)}

    return list_to_dict


def create_builtin_types_dict_to_list_io_server_tool():

    @tool(description_mode="only_docstring")
    def dict_to_list(input_dict: Dict[str, int]) -> List[int]:
        """Creates list out of dictionary values
        Parameters
        ----------
        input_dict
            the input dictionary
        """
        return [v for v in input_dict.values()]

    return dict_to_list


def create_server_tool_with_no_outputs():

    @tool(description_mode="only_docstring")
    def return_none() -> None:
        """Returns nothing"""
        return

    return return_none


def create_list_of_union_io_server_tool():

    @tool(description_mode="only_docstring")
    def convert_all_to_float(l: List[Union[int, float]]) -> Any:
        """Add a column to the dataframe containing the nums value as a percentage string.
        Parameters
        ----------
        l
            the input list
        """
        return [float(x) for x in l]

    return convert_all_to_float


def create_list_input_tool_description():
    get_length_tool = ClientTool(
        name="get_length",
        description="Returns the length of the input list.",
        parameters={
            "arr": {"description": "the input list", "type": "array", "items": {"type": "integer"}}
        },
    )
    return get_length_tool


def create_dict_input_tool_description():
    get_num_elements_tool = ClientTool(
        name="get_num_elements",
        description="Returns the number of elements in the input dictionary.",
        parameters={
            "input_dict": {
                "description": "the input dictionary",
                "type": "object",
                "additionalProperties": {"type": "array", "items": {"type": "boolean"}},
            }
        },
    )
    return get_num_elements_tool


def create_any_input_tool_description():
    get_num_elements_tool = ClientTool(
        name="get_sum_elements",
        description="Returns the sum of the specified column of the input dataframe.",
        parameters={
            "df": {"description": "the input dataframe"},
            "column": {"description": "the column name", "type": "string"},
        },
    )
    return get_num_elements_tool


@pytest.mark.parametrize(
    "tool,expected_input_descriptor_types",
    [
        (
            create_list_input_tool_description(),
            [ListProperty(name="arr", description="the input list", item_type=IntegerProperty())],
        ),
        (
            create_dict_input_tool_description(),
            [
                DictProperty(
                    name="input_dict",
                    description="the input dictionary",
                    key_type=AnyProperty(),
                    value_type=ListProperty(item_type=BooleanProperty()),
                )
            ],
        ),
        (
            create_any_input_tool_description(),
            [
                AnyProperty(name="df", description="the input dataframe"),
                StringProperty(name="column", description="the column name"),
            ],
        ),
    ],
)
def test_tool_execution_step_has_correct_input_descriptor_when_init_from_complex_tool_type(
    tool: ClientTool,
    expected_input_descriptor_types: List[Property],
) -> None:
    tool_execution_step = ToolExecutionStep(tool=tool)
    for step_input_descriptor, expected_input_descriptor_type in zip(
        tool_execution_step.input_descriptors, expected_input_descriptor_types
    ):
        assert step_input_descriptor == expected_input_descriptor_type


def run_assistant(
    script: Callable,
    tool: Any = None,
    outputs: Optional[List[Union[Any, Property]]] = None,
    output_values: Optional[Dict[str, Any]] = None,
    check: Union[str, Callable[[str], bool]] = None,
) -> None:
    assistant = Flow.from_steps(
        [
            _InputOutputSpecifiedStep(outputs=outputs, output_values=output_values),
            ToolExecutionStep(tool=tool),
        ]
    )

    flow_script = script(check)

    benchmark = FlowScriptRunner([assistant], [flow_script])
    benchmark.execute(raise_exceptions=True)


def init_interaction(check: Union[str, Callable[[str], bool]]) -> FlowScriptInteraction:
    if check:
        checks = [IODictCheck(check, ToolExecutionStep.TOOL_OUTPUT)]
    return FlowScriptInteraction(
        user_input="",
        checks=checks,
    )


def basic_flow_script(check: Union[str, Callable[[str], bool]]) -> FlowScript:
    return FlowScript(name="Running the agent", interactions=[init_interaction(check=check)])


@pytest.mark.parametrize(
    "flow_script_builder,tool,expected_tool_input_descriptors,tool_input_values,check",
    [
        (  # 0
            basic_flow_script,
            create_weather_server_tool(),
            [StringProperty("location")],
            {"location": "zurich"},
            lambda txt: ("sunny" in txt or "rainy" in txt),
        ),
        (  # 1
            basic_flow_script,
            create_range_server_tool(),
            [IntegerProperty("stop")],
            {"stop": 5},
            "Range: [0, 1, 2, 3, 4]",
        ),
        (  # 2
            basic_flow_script,
            create_error_server_tool(),
            [
                FloatProperty("y_true"),
                FloatProperty("y_pred"),
            ],
            {"y_true": 1.9, "y_pred": 2.0},
            "Computed error: -5%",
        ),
        (  # 3
            basic_flow_script,
            create_list_io_server_tool(),
            [
                ListProperty("arr", item_type=IntegerProperty()),
            ],
            {"arr": [1, 5, 9]},
            lambda res: (res == [2, 10, 18]),
        ),
        (  # 4
            basic_flow_script,
            create_dict_io_server_tool(),
            [
                DictProperty(
                    "input_dict",
                    value_type=ListProperty(item_type=IntegerProperty()),
                ),
            ],
            {"input_dict": {"2": [5]}},
            lambda res: (res == {"2": [5, 5]}),
        ),
        (  # 5
            basic_flow_script,
            create_builtin_types_list_to_dict_io_server_tool(),
            [
                ListProperty("arr", item_type=IntegerProperty()),
            ],
            {"arr": [5, 9]},
            lambda res: (res == {0: 5, 1: 9}),
        ),
        (  # 6
            basic_flow_script,
            create_builtin_types_dict_to_list_io_server_tool(),
            [
                DictProperty("input_dict", value_type=IntegerProperty()),
            ],
            {"input_dict": {"0": 5, "1": 9}},
            lambda res: (res == [5, 9]),
        ),
        (  # 16
            basic_flow_script,
            create_server_tool_with_no_outputs(),
            [],
            {},
            lambda res: (res is None),
        ),
    ],
)
def test_tool_execution_flowscripts(
    flow_script_builder: Callable,
    tool: ServerTool,
    expected_tool_input_descriptors: List[Union[Any, Property]],
    tool_input_values: Dict[str, Any],
    check: Union[Callable, str],
) -> None:
    """Explanation of the code flow when `run_assistant` is executed:
    1. We create the simple assistant consisting of a _InputOutputSpecifiedStep to pass the required
        inputs to the ToolExecutionStep
    2. We run the assistant conversation, which will invoke the tools during the ToolExecutionStep
    3. We check that the tools returned the expected values
    """
    run_assistant(
        flow_script_builder, tool, expected_tool_input_descriptors, tool_input_values, check
    )


@dataclass(eq=False)
class CustomKey:
    value: int

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: "CustomKey") -> bool:
        if isinstance(other, CustomKey):
            return self.value == other.value
        return False

    def __iter__(self):
        yield self.value


@pytest.mark.parametrize("dict_key", [2, CustomKey(2)])
def test_tool_execution_with_non_str_dict(dict_key: Union[CustomKey, int]) -> None:
    inputs = {"input_dict": {dict_key: [5]}}
    _, status = _run_single_step_and_return_conv_and_status(
        ToolExecutionStep(tool=create_dict_io_server_tool()), inputs=inputs
    )
    assert isinstance(status, FinishedStatus)
    assert status.output_values["tool_output"] == {dict_key: [5, 5]}


def test_tool_execution_step_might_not_yield() -> None:
    step = ToolExecutionStep(tool=create_dummy_server_tool())
    assert not step.might_yield


@pytest.fixture
def flow_with_client_tool_execution() -> Flow:
    addition_client_tool = ClientTool(
        name="add_numbers",
        description="Simply adds two numbers",
        parameters={
            "a": {
                "description": "the first number",
                "type": "integer",
            },
            "b": {
                "description": "the second number",
                "type": "integer",
            },
        },
    )

    tool_execution_step = ToolExecutionStep(
        tool=addition_client_tool,
        output_mapping={ToolExecutionStep.TOOL_OUTPUT: "d"},
    )
    output_message_step = OutputMessageStep(
        message_template="{{a}}+{{b}}={{d}}",
        input_descriptors=[IntegerProperty("a"), IntegerProperty("b")],
    )
    return Flow.from_steps(
        steps=[tool_execution_step, output_message_step],
        step_names=["tool_execution_step", "output_message_step"],
    )


def test_tool_execution_step_can_return_tool_request_message(
    flow_with_client_tool_execution: Flow,
) -> None:
    conversation = flow_with_client_tool_execution.start_conversation(inputs={"b": 34, "a": 56})
    assistant = flow_with_client_tool_execution
    execution_status = assistant.execute(conversation)
    assert isinstance(execution_status, ToolRequestStatus)
    messages = conversation.get_messages()
    assert len(messages) == 1
    last_message: Message = messages[-1]
    assert last_message.message_type == MessageType.TOOL_REQUEST
    assert (
        len(last_message.tool_requests) == 1
    )  # Tool execution steps only execute one tool at a time
    # TODO ensure messages carry only a single tool request
    tool_request: ToolRequest = last_message.tool_requests[0]
    assert tool_request.name == "add_numbers"
    assert tool_request.args["a"] == 56
    assert tool_request.args["b"] == 34


def test_tool_execution_step_can_be_reinvoked_with_tool_result(
    flow_with_client_tool_execution: Flow,
) -> None:
    conversation = flow_with_client_tool_execution.start_conversation(inputs={"b": 34, "a": 56})
    assistant = flow_with_client_tool_execution
    execution_status = assistant.execute(conversation)
    tool_call_id = execution_status.tool_requests[0].tool_request_id
    tool_result_message = Message(
        tool_result=ToolResult(content="123456789", tool_request_id=tool_call_id),
        message_type=MessageType.TOOL_RESULT,
    )
    conversation.append_message(tool_result_message)
    status = assistant.execute(conversation)
    assert isinstance(status, FinishedStatus)
    assert "d" in status.output_values
    assert status.output_values["d"] == "123456789"
    assert conversation.get_last_message().content == "56+34=123456789"


def test_tool_execution_step_can_be_reinvoked_with_non_str_tool_result(
    flow_with_client_tool_execution: Flow,
) -> None:

    client_tool = ClientTool(
        name="some_tool",
        description="some_description",
        parameters={"a": {"type": "number"}, "b": {"type": "array", "items": {"type": "boolean"}}},
        output={"type": "object", "additionalProperties": {"type": "integer"}},
    )

    step = ToolExecutionStep(tool=client_tool)
    flow = create_single_step_flow(step)

    conversation = flow.start_conversation(inputs={"a": 0.4, "b": [True, True, False]})

    status = flow.execute(conversation)
    assert isinstance(status, ToolRequestStatus)
    assert len(status.tool_requests) > 0
    tool_call_id = status.tool_requests[0].tool_request_id

    tool_result_message = Message(
        tool_result=ToolResult(content={"e": 1, "f": 2}, tool_request_id=tool_call_id),
        message_type=MessageType.TOOL_RESULT,
    )
    conversation.append_message(tool_result_message)

    status = flow.execute(conversation)
    assert isinstance(status, FinishedStatus)
    assert ToolExecutionStep.TOOL_OUTPUT in status.output_values
    assert status.output_values[ToolExecutionStep.TOOL_OUTPUT] == {"e": 1, "f": 2}


def test_tool_execution_step_raises_when_reinvoked_without_expected_tool_message(
    flow_with_client_tool_execution: Flow,
) -> None:
    conversation = flow_with_client_tool_execution.start_conversation(inputs={"b": 34, "a": 56})
    assistant = flow_with_client_tool_execution
    assistant.execute(conversation)
    with pytest.raises(ValueError):
        assistant.execute(conversation)


class MyCustomException(Exception):
    pass


def create_raise_tool() -> ServerTool:
    def func():
        raise MyCustomException()

    return ServerTool(name="", description="", parameters={}, output={}, func=func)


def test_tool_execution_step_can_raise_exception():
    with pytest.raises(MyCustomException):
        step = ToolExecutionStep(tool=create_raise_tool(), raise_exceptions=True)
        flow = create_single_step_flow(step)
        conv = flow.start_conversation()
        flow.execute(conv)


def test_tool_execution_step_can_catch_exception():
    step = ToolExecutionStep(tool=create_raise_tool(), raise_exceptions=False)
    flow = create_single_step_flow(step)
    conv = flow.start_conversation()
    flow.execute(conv)


def test_tool_execution_step_crashes_if_not_raising_exception_and_output_type_is_not_string():
    def func():
        raise MyCustomException()

    my_int_tool = ServerTool(
        name="", description="", parameters={}, output={"type": "integer"}, func=func
    )

    step = ToolExecutionStep(tool=my_int_tool, raise_exceptions=False)
    flow = create_single_step_flow(step)

    with pytest.raises(ValueError):
        conv = flow.start_conversation()
        flow.execute(conv)


all_tool_output_descriptors_possibilities = pytest.mark.parametrize(
    "tool_,tool_outputs,expected_step_outputs",
    [
        (
            ClientTool(
                name="", description="", input_descriptors=[], output_descriptors=[StringProperty()]
            ),
            "some_text",
            {"tool_output": "some_text"},
        ),
        (  # different type
            ClientTool(
                name="",
                description="",
                input_descriptors=[],
                output_descriptors=[IntegerProperty()],
            ),
            2,
            {"tool_output": 2},
        ),
        (  # rename output
            ClientTool(
                name="",
                description="",
                input_descriptors=[],
                output_descriptors=[IntegerProperty(name="o1")],
            ),
            2,
            {"o1": 2},
        ),
        (  # rename output
            ClientTool(name="", description="", input_descriptors=[], output_descriptors=[]),
            None,
            {},
        ),
        (  # no outputs
            ClientTool(name="", description="", input_descriptors=[], output_descriptors=[]),
            "ueiwbfuiewb",
            {},
        ),
        (  # several outputs
            ClientTool(
                name="",
                description="",
                input_descriptors=[],
                output_descriptors=[IntegerProperty(name="o1"), IntegerProperty(name="o2")],
            ),
            {"o1": 1, "o2": 2},
            {"o1": 1, "o2": 2},
        ),
    ],
)


@all_tool_output_descriptors_possibilities
def test_client_tool_step_can_return_several_outputs(tool_, tool_outputs, expected_step_outputs):
    tool_step = ToolExecutionStep(tool_)
    flow = create_single_step_flow(tool_step)
    conv = flow.start_conversation()
    status = flow.execute(conv)
    assert isinstance(status, ToolRequestStatus)
    assert len(status.tool_requests) == 1
    conv.append_tool_result(
        ToolResult(tool_request_id=status.tool_requests[0].tool_request_id, content=tool_outputs)
    )
    status = flow.execute(conv)
    assert isinstance(status, FinishedStatus)
    assert status.output_values == expected_step_outputs


@all_tool_output_descriptors_possibilities
def test_server_tool_step_can_return_several_outputs(tool_, tool_outputs, expected_step_outputs):
    server_tool = ServerTool(
        name=tool_.name,
        description=tool_.description,
        input_descriptors=tool_.input_descriptors,
        output_descriptors=tool_.output_descriptors,
        func=lambda *args, **kwargs: tool_outputs,
    )

    tool_step = ToolExecutionStep(server_tool)
    flow = create_single_step_flow(tool_step)
    conv = flow.start_conversation()
    status = flow.execute(conv)
    assert isinstance(status, FinishedStatus)
    assert status.output_values == expected_step_outputs


def test__tool_with_multiple_outputs_returning_non_dict_raises_clear_error():
    server_tool = ServerTool(
        name="multi_output_tool",
        description="some description",
        input_descriptors=[],
        output_descriptors=[StringProperty("a"), StringProperty("b")],
        func=lambda *args, **kwargs: "",
    )
    tool_step = ToolExecutionStep(server_tool)
    with pytest.raises(ValueError):
        run_step_and_return_outputs(tool_step)


def test_tool_with_multiple_outputs_missing_outputs_in_returned_dict_raises_clear_error():
    server_tool = ServerTool(
        name="multi_output_tool",
        description="some description",
        input_descriptors=[],
        output_descriptors=[StringProperty("a"), StringProperty("b")],
        func=lambda *args, **kwargs: {"a": "s1", "something_else": "s2"},
    )
    tool_step = ToolExecutionStep(server_tool)
    with pytest.raises(ValueError):
        run_step_and_return_outputs(tool_step)


def test_multiple_tool_execution_steps():
    tool_1 = ServerTool(
        name="tool_1",
        description="some description",
        input_descriptors=[],
        output_descriptors=[StringProperty("a"), StringProperty("b")],
        func=lambda: {"a": "some_output", "b": "2"},
    )

    tool_2 = ServerTool(
        name="tool_2",
        description="some description",
        input_descriptors=[StringProperty("a"), StringProperty("b")],
        output_descriptors=[StringProperty("c"), IntegerProperty("d")],
        func=lambda a, b: {"c": a + "suffix", "d": int(b)},
    )

    tool_3 = ServerTool(
        name="tool_3",
        description="some description",
        input_descriptors=[StringProperty("a"), IntegerProperty("d"), StringProperty("c")],
        output_descriptors=[
            StringProperty("e"),
            DictProperty("f", value_type=IntegerProperty()),
            ObjectProperty("g", properties={"g1": StringProperty(), "g2": FloatProperty()}),
        ],
        func=lambda a, d, c: {
            "e": a + "second_suffix",
            "f": {"d": d},
            "g": {"g1": c, "g2": float(d)},
        },
    )

    flow = Flow.from_steps(
        [ToolExecutionStep(tool_1), ToolExecutionStep(tool_2), ToolExecutionStep(tool_3)]
    )

    outputs = run_step_and_return_outputs(FlowExecutionStep(flow))
    assert outputs == {
        "d": 2,
        "a": "some_output",
        "e": "some_outputsecond_suffix",
        "b": "2",
        "f": {"d": 2},
        "g": {"g1": "some_outputsuffix", "g2": 2.0},
        "c": "some_outputsuffix",
    }


@tool
def my_tool_with_none(param1: Annotated[Optional[int], ""] = None) -> str:
    """Tool desc"""
    return str(param1)


@tool
def my_tool_with_non_optional_none(param1: Annotated[int, ""] = None) -> str:
    """Tool desc"""
    return str(param1)


@tool(description_mode="only_docstring")
def my_tool_with_none_with_doc_description_mode(param1: Optional[int] = None) -> str:
    """Tool desc"""
    return str(param1)


@tool(description_mode="only_docstring")
def my_tool_with_non_optional_none_with_doc_description_mode(param1: int = None) -> str:
    """Tool desc"""
    return str(param1)


EXPECTED_INPUT_TYPE = UnionProperty(
    name="param1",
    description="",
    default_value=None,
    any_of=[
        IntegerProperty(),
        NullProperty(),
    ],
)

my_tool_with_none_as_server_tool = ServerTool(
    name="my_tool_with_none_as_server_tool",
    description="Tool desc",
    input_descriptors=[EXPECTED_INPUT_TYPE],
    func=lambda param1: str(param1),
)


@pytest.mark.parametrize(
    "some_tool",
    [
        my_tool_with_none,
        my_tool_with_non_optional_none,
        my_tool_with_none_with_doc_description_mode,
        my_tool_with_non_optional_none_with_doc_description_mode,
        my_tool_with_none_as_server_tool,
    ],
)
def test_tool_with_none_parameters(some_tool):
    flow = Flow.from_steps(steps=[ToolExecutionStep(tool=some_tool)])

    assert flow.input_descriptors == [EXPECTED_INPUT_TYPE]

    outputs = run_flow_and_return_outputs(flow=flow, inputs={"param1": 1})
    assert outputs["tool_output"] == "1"

    outputs = run_flow_and_return_outputs(flow=flow, inputs={"param1": None})
    assert outputs["tool_output"] == "None"

    outputs = run_flow_and_return_outputs(flow=flow)
    assert outputs["tool_output"] == "None"


def test_execution_of_flow_does_not_raise_when_None_is_passed_to_str_input():
    @tool
    def my_tool(s: Annotated[str, "input"] = "helloworld") -> str:
        """doubles the string provided as argument"""
        return s + s

    flow = Flow.from_steps([ToolExecutionStep(my_tool)])
    conversation = flow.start_conversation({"s": None})
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values["tool_output"] == ""


def test_tool_with_optional_type_in_flow_correctly_receives_None_input():
    @tool
    def my_tool(s: Annotated[Optional[str], "input"] = "helloworld") -> str:
        """doubles the string provided as argument"""
        if s is None:
            return "Double None is still None"
        return s + s

    flow = Flow.from_steps([ToolExecutionStep(my_tool)])
    output_values = run_flow_and_return_outputs(flow, inputs={"s": None})
    assert output_values[ToolExecutionStep.TOOL_OUTPUT] == "Double None is still None"


def test_tool_confirmation_status_is_returned_for_every_tool_step_with_tool_that_requires_confirmation() -> (
    None
):
    name_func = lambda name: name
    name_tool = ServerTool(
        func=name_func,
        name="name_tool",
        description="Ask the user for some name",
        parameters={"name": {"type": "string"}},
        requires_confirmation=True,
    )

    assistant = Flow.from_steps(
        [
            ToolExecutionStep(tool=name_tool, raise_exceptions=False),
            ToolExecutionStep(tool=name_tool, raise_exceptions=False),
        ]
    )
    conv = assistant.start_conversation(inputs={"name": "dummy user"})
    status = assistant.execute(conv)
    assert isinstance(status, ToolExecutionConfirmationStatus)
    status.reject_tool_execution(tool_request=status.tool_requests[0], reason="No reason")
    status = assistant.execute(conv)
    assert isinstance(status, ToolExecutionConfirmationStatus)
    status.confirm_tool_execution(
        tool_request=status.tool_requests[0], modified_args={"name": "another user"}
    )
    status = assistant.execute(conv)
    assert isinstance(status, FinishedStatus)
    assert status.output_values["tool_output"] == "another user"


def test_tool_confirmation_raises_exceptions_in_flow_if_rejected() -> None:
    name_func = lambda name: name
    name_tool = ServerTool(
        func=name_func,
        name="name_tool",
        description="Ask the user for some name",
        parameters={"name": {"type": "string"}},
        requires_confirmation=True,
    )

    with pytest.raises(
        ValueError,
        match="Tool Execution was rejected by the user. "
        "This error is being raised because flow outputs need to be structured and rejecting tool execution could break the flow. "
        "Set raise_exceptions=False to set the rejection reason as the tool output",
    ):
        assistant = Flow.from_steps([ToolExecutionStep(tool=name_tool, raise_exceptions=True)])
        conv = assistant.start_conversation(inputs={"name": "dummy user"})
        status = assistant.execute(conv)
        assert isinstance(status, ToolExecutionConfirmationStatus)
        status.reject_tool_execution(tool_request=status.tool_requests[0], reason="No reason")
        status = assistant.execute(conv)
