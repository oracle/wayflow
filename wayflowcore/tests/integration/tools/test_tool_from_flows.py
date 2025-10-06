# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
import json
from typing import Any, List

import pytest

from wayflowcore import Step
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.messagelist import MessageType
from wayflowcore.property import FloatProperty, IntegerProperty, Property, StringProperty
from wayflowcore.steps import (
    BranchingStep,
    GetChatHistoryStep,
    InputMessageStep,
    OutputMessageStep,
    PromptExecutionStep,
    RegexExtractionStep,
    ToolExecutionStep,
)
from wayflowcore.tools import ServerTool, Tool

from ...testhelpers.dummy import DummyModel
from ..test_input_output_descriptors import check_descriptors_names_and_types_equality


def test_tool_from_step_without_input_has_correct_metadata() -> None:
    step = OutputMessageStep(message_template="hello world")
    tool = ServerTool.from_step(step, "hw_tool", "return hello world", OutputMessageStep.OUTPUT)
    assert isinstance(tool, ServerTool)
    assert tool.name == "hw_tool"
    assert tool.description == "return hello world"
    assert tool.parameters == {}
    assert tool.output == {
        "title": OutputMessageStep.OUTPUT,
        "description": "the message added to the messages list",
        "type": "string",
    }


def test_tool_from_step_without_input_can_be_called() -> None:
    step = OutputMessageStep(message_template="hello world")
    tool = ServerTool.from_step(step, "hw_tool", "return hello world", OutputMessageStep.OUTPUT)
    assert tool.run() == "hello world"


def test_tool_from_step_raises_when_output_name_does_not_exist() -> None:
    step = OutputMessageStep(message_template="hello world")
    with pytest.raises(ValueError):
        tool = ServerTool.from_step(step, "hw_tool", "return hello world", "THIS_DOES_NOT_EXIST")


def test_tool_from_step_raises_when_step_might_yield() -> None:
    yielding_step = InputMessageStep(message_template="How are you?")
    with pytest.raises(ValueError):
        tool = ServerTool.from_step(yielding_step, "greet", "greets the user")


def test_tool_from_step_correctly_infers_inputs() -> None:
    step = OutputMessageStep(
        message_template="{{x}}+{{y}}={{z}}\n{% for c in contexts %}{{c}}{% endfor %}"
    )
    tool = ServerTool.from_step(step, "build_equation_tool", "", "output_message")
    assert set(tool.parameters) == {"x", "y", "z", "contexts"}
    assert tool.parameters["y"] == {
        "title": "y",
        "type": "string",
        "description": '"y" input variable for the template',
    }
    # The 'contexts' input is `AnyProperty`
    assert tool.parameters["contexts"] == {
        "title": "contexts",
        "description": '"contexts" input variable for the template',
    }
    assert tool.run(x="5", y="5", z="10", contexts=["hello", "world"]) == "5+5=10\nhelloworld"


def test_tool_from_flow_can_be_instantiated_and_called() -> None:
    step = OutputMessageStep(
        message_template="{{x}}+{{y}}={{z}}\n{% for c in contexts %}{{c}}{% endfor %}"
    )
    flow = create_single_step_flow(step)
    tool = ServerTool.from_flow(flow, "build_equation_tool", "", "output_message")
    assert set(tool.parameters) == {"x", "y", "z", "contexts"}
    assert tool.parameters["y"] == {
        "title": "y",
        "type": "string",
        "description": '"y" input variable for the template',
    }
    # The 'contexts' input is `AnyProperty`
    assert tool.parameters["contexts"] == {
        "title": "contexts",
        "description": '"contexts" input variable for the template',
    }
    assert tool.run(x="5", y="5", z="10", contexts=["hello", "world"]) == "5+5=10\nhelloworld"


@pytest.fixture
def step_with_several_outputs() -> Step:
    llm = DummyModel()
    llm.set_next_output(json.dumps({"a": 1, "b": 0.1, "c": "some_text"}))
    return PromptExecutionStep(
        prompt_template="",
        llm=llm,
        output_descriptors=[IntegerProperty("a"), FloatProperty("b"), StringProperty("c")],
    )


all_outputs_parameters = [
    (
        None,
        [IntegerProperty("a"), FloatProperty("b"), StringProperty("c")],
        {"a": 1, "b": 0.1, "c": "some_text"},
        {"a": 1, "b": 0.1, "c": "some_text"},
    ),
    ([], [], {}, None),
    (["a"], [IntegerProperty("a")], {"a": 1}, 1),
    (
        ["a", "b"],
        [IntegerProperty("a"), FloatProperty("b")],
        {"a": 1, "b": 0.1},
        {"a": 1, "b": 0.1},
    ),
]


def run_flow_with_outputs(
    tool_from_: Tool, expected_descriptors: List[Property], expected_outputs: Any
):
    assert len(tool_from_.output_descriptors) == len(expected_descriptors)
    check_descriptors_names_and_types_equality(tool_from_.output_descriptors, expected_descriptors)
    flow = create_single_step_flow(ToolExecutionStep(tool_from_))
    conv = flow.start_conversation()
    status = flow.execute(conv)
    assert isinstance(status, FinishedStatus)
    assert status.output_values == expected_outputs


@pytest.mark.parametrize(
    "flow_outputs,expected_descriptors,expected_flow_outputs,expected_tool_output",
    all_outputs_parameters,
)
def test_tool_from_flow_can_return_selected_outputs(
    step_with_several_outputs,
    flow_outputs,
    expected_descriptors,
    expected_flow_outputs,
    expected_tool_output,
) -> None:
    flow_with_several_outputs = create_single_step_flow(step_with_several_outputs)
    flow_tool = ServerTool.from_flow(
        flow=flow_with_several_outputs,
        flow_name="generate",
        flow_description="",
        flow_output=flow_outputs,
    )
    run_flow_with_outputs(flow_tool, expected_descriptors, expected_flow_outputs)
    assert flow_tool.run() == expected_tool_output


@pytest.mark.parametrize(
    "step_outputs,expected_descriptors,expected_step_outputs, expected_tool_output",
    all_outputs_parameters,
)
def test_tool_from_step_can_return_selected_outputs(
    step_with_several_outputs,
    step_outputs,
    expected_descriptors,
    expected_step_outputs,
    expected_tool_output,
) -> None:
    step_tool = ServerTool.from_step(
        step=step_with_several_outputs,
        step_name="generate",
        step_description="",
        step_output=step_outputs,
    )
    run_flow_with_outputs(step_tool, expected_descriptors, expected_step_outputs)
    assert step_tool.run() == expected_tool_output


def test_tool_from_multi_step_flow_with_branching_can_be_called() -> None:
    output_choice = OutputMessageStep(
        message_template="{{user_choice}}",
        output_mapping={OutputMessageStep.OUTPUT: BranchingStep.NEXT_BRANCH_NAME},
    )
    branch_on_choice = BranchingStep({"LEFT": "LEFT", "RIGHT": "RIGHT"})
    left_output = OutputMessageStep(message_template="This is your arrow: <=")
    right_output = OutputMessageStep(message_template="This is your arrow: =>")
    failed = OutputMessageStep(message_template="Please try again")
    flow = Flow(
        begin_step_name="output_choice",
        steps={
            "output_choice": output_choice,
            "branch_on_choice": branch_on_choice,
            "left_output": left_output,
            "right_output": right_output,
            "failed": failed,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=output_choice, destination_step=branch_on_choice),
            ControlFlowEdge(
                source_step=branch_on_choice, source_branch="LEFT", destination_step=left_output
            ),
            ControlFlowEdge(
                source_step=branch_on_choice, source_branch="RIGHT", destination_step=right_output
            ),
            ControlFlowEdge(
                source_step=branch_on_choice, source_branch="default", destination_step=failed
            ),
            ControlFlowEdge(source_step=left_output, destination_step=None),
            ControlFlowEdge(source_step=right_output, destination_step=None),
            ControlFlowEdge(source_step=failed, destination_step=None),
        ],
    )
    tool = ServerTool.from_flow(flow, "g", "g", OutputMessageStep.OUTPUT)
    assert tool.run(user_choice="LEFT") == "This is your arrow: <="
    assert tool.run(user_choice="RIGHT") == "This is your arrow: =>"


def test_tool_from_flow_can_access_conversation_when_ran_in_tool_execution_step():
    print_code_flow = Flow.from_steps(
        steps=[
            GetChatHistoryStep(n=1, message_types=MessageType.USER),
            RegexExtractionStep(
                r"The\scode\sis\:\s(.*)",  # use a raw string to avoid escaping issues
                input_mapping={RegexExtractionStep.TEXT: GetChatHistoryStep.CHAT_HISTORY},
                output_mapping={RegexExtractionStep.OUTPUT: "code"},
            ),
            OutputMessageStep("The user revealed: {{code}}"),
        ],
        step_names=["get_first_user_message", "extract_code", "print_code"],
    )
    print_code_tool = ServerTool.from_flow(
        print_code_flow, "print_code_tool", "prints the code shared by the user"
    )
    call_tool_flow = Flow.from_steps(
        steps=[
            OutputMessageStep(message_template="I will now display the code you shared"),
            ToolExecutionStep(tool=print_code_tool),
        ],
        step_names=["display_message", "call_print_code_tool"],
    )
    conversation = call_tool_flow.start_conversation()
    conversation.append_user_message("Hello, I am a user. The code is: Expelliarmus")
    status = call_tool_flow.execute(conversation)
    assert isinstance(status, FinishedStatus)
    messages = conversation.get_messages()
    assert len(messages) == 3  # Call to the tool must have happened a message
    assert messages[-1].content == "The user revealed: Expelliarmus"
