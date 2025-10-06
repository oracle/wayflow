# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
from typing import Optional

import pytest

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus, ToolRequestStatus
from wayflowcore.flow import Flow
from wayflowcore.steps import (
    BranchingStep,
    CompleteStep,
    FlowExecutionStep,
    InputMessageStep,
    ToolExecutionStep,
)
from wayflowcore.tools import ClientTool, ToolResult

from ...testhelpers.teststeps import _InputOutputSpecifiedStep
from .test_branching_step import get_branching_flow

STEP_A = "step_a"
STEP_B = "step_b"
STEP_C = "step_c"
STEP_D = "step_d"
STEP_E = "step_e"


@pytest.fixture
def example_subflow():
    step_b = _InputOutputSpecifiedStep(inputs=["i1"], outputs=["o1"], branch_out=[STEP_C, STEP_D])
    step_c = _InputOutputSpecifiedStep(inputs=["o1", "i2"], outputs=["o2"])
    step_d = _InputOutputSpecifiedStep(inputs=["o1"], outputs=["o2", "o3"])
    return Flow(
        begin_step_name=STEP_B,
        steps={
            STEP_B: step_b,
            STEP_C: step_c,
            STEP_D: step_d,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=step_b, source_branch=STEP_C, destination_step=step_c),
            ControlFlowEdge(source_step=step_b, source_branch=STEP_D, destination_step=step_d),
            ControlFlowEdge(source_step=step_c, destination_step=None),
            ControlFlowEdge(source_step=step_d, destination_step=None),
        ],
    )


def get_flow_with_branching_subflow(
    success_branch_name: Optional[str] = None,
    failure_branch_name: Optional[str] = None,
    default_branch_name: Optional[str] = None,
) -> Flow:
    subflow = get_branching_flow(
        success_branch_name=success_branch_name,
        failure_branch_name=failure_branch_name,
        default_branch_name=default_branch_name,
    )

    start_step = FlowExecutionStep(
        name="start",
        flow=subflow,
    )
    sub_success_step = CompleteStep(name="sub_success_end_step")
    sub_failure_step = CompleteStep(name="sub_failure_end_step")
    sub_default_step = CompleteStep(name="sub_default_end_step")

    return Flow(
        begin_step=start_step,
        control_flow_edges=[
            ControlFlowEdge(
                source_step=start_step,
                source_branch=success_branch_name or "external_success_step",
                destination_step=sub_success_step,
            ),
            ControlFlowEdge(
                source_step=start_step,
                source_branch=failure_branch_name or "failure_branch",
                destination_step=sub_failure_step,
            ),
            ControlFlowEdge(
                source_step=start_step,
                source_branch=default_branch_name or "default_next_step",
                destination_step=sub_default_step,
            ),
        ],
    )


def test_simple_subflow(example_subflow: Flow) -> None:
    assistant = Flow.from_steps(
        [
            _InputOutputSpecifiedStep(outputs=["i1", "i2"]),
            FlowExecutionStep(flow=example_subflow),
            _InputOutputSpecifiedStep(inputs=["o2"]),
        ]
    )
    conversation = assistant.start_conversation()
    conversation.append_user_message(STEP_C)
    assistant.execute(conversation)


def test_simple_subflow_missing_output(example_subflow: Flow) -> None:
    with pytest.raises(ValueError):
        assistant = Flow.from_steps(
            [
                _InputOutputSpecifiedStep(outputs=["i1", "i2"]),
                FlowExecutionStep(flow=example_subflow),
                _InputOutputSpecifiedStep(inputs=["o3"]),
            ]
        )

        conversation = assistant.start_conversation()
        conversation.append_user_message(STEP_C)
        assistant.execute(conversation)


def test_simple_subflow_add_output(example_subflow: Flow) -> None:
    assistant = Flow.from_steps(
        [
            _InputOutputSpecifiedStep(outputs=["i1", "i2"]),
            FlowExecutionStep(flow=example_subflow),
            _InputOutputSpecifiedStep(inputs=["o3"]),
        ]
    )
    conversation = assistant.start_conversation({"o3": "o3"})
    conversation.append_user_message(STEP_C)
    assistant.execute(conversation)


def test_sequential_subflow_execution() -> None:
    s1_subflow = Flow.from_steps(
        [
            _InputOutputSpecifiedStep(inputs=["i1"], outputs=["i2"]),
            _InputOutputSpecifiedStep(inputs=["i2"], outputs=["i3"]),
        ]
    )
    s1 = FlowExecutionStep(flow=s1_subflow)

    # check that FlowExecutionStep reports the subflow
    assert s1.sub_flow() == s1_subflow

    assistant = Flow.from_steps(
        [
            _InputOutputSpecifiedStep(outputs=["i1"]),
            s1,
            FlowExecutionStep(
                flow=Flow.from_steps(
                    [
                        _InputOutputSpecifiedStep(inputs=["i3"], outputs=["i4"]),
                        _InputOutputSpecifiedStep(inputs=["i4"], outputs=["i5"]),
                    ]
                )
            ),
            _InputOutputSpecifiedStep(inputs=["i5"]),
        ]
    )
    conversation = assistant.start_conversation()
    assistant.execute(conversation)


def test_nested_subflow_execution() -> None:
    assistant = Flow.from_steps(
        [
            _InputOutputSpecifiedStep(outputs=["i1"]),
            FlowExecutionStep(
                flow=Flow.from_steps(
                    [
                        _InputOutputSpecifiedStep(inputs=["i1"], outputs=["i2"]),
                        FlowExecutionStep(
                            flow=Flow.from_steps(
                                [
                                    _InputOutputSpecifiedStep(inputs=["i2"], outputs=["i3"]),
                                    _InputOutputSpecifiedStep(inputs=["i3"], outputs=["i4"]),
                                ]
                            )
                        ),
                    ]
                )
            ),
            _InputOutputSpecifiedStep(inputs=["i4"]),
        ]
    )
    conversation = assistant.start_conversation()
    assistant.execute(conversation)


def test_sub_conversation_shares_same_message_list_as_main_conversation() -> None:
    subflow_step = FlowExecutionStep(flow=Flow.from_steps([InputMessageStep("Hello")]))
    assistant = Flow.from_steps([subflow_step])

    conversation = assistant.start_conversation()
    assistant.execute(conversation)

    subconversation = conversation._get_current_sub_conversation(subflow_step)

    assert conversation.get_messages() == subconversation.get_messages()
    conversation.append_message(None)
    assert conversation.get_messages() == subconversation.get_messages()


def test_subflow_execution_might_yield_when_flow_contains_yielding_steps() -> None:
    step = FlowExecutionStep(
        flow=Flow.from_steps(
            [
                _InputOutputSpecifiedStep(),
                InputMessageStep("Hello"),
            ]
        )
    )
    assert step.might_yield


def test_subflow_execution_might_not_yield_when_flow_contains_no_yielding_step() -> None:
    step = FlowExecutionStep(
        flow=Flow.from_steps(
            [
                _InputOutputSpecifiedStep(),
                _InputOutputSpecifiedStep(),
            ]
        )
    )
    assert not step.might_yield


def test_subflow_execution_might_yield_with_tool_request_inside() -> None:
    name_tool = ClientTool(
        name="name_tool",
        description="Ask the user for some name",
        parameters={},
    )
    step = FlowExecutionStep(
        flow=Flow.from_steps(
            [
                ToolExecutionStep(tool=name_tool),
            ]
        )
    )

    assistant = Flow.from_steps([step])
    conv = assistant.start_conversation()
    status = assistant.execute(conv)
    assert isinstance(status, ToolRequestStatus)
    conv.append_tool_result(
        ToolResult(content="whatever", tool_request_id=status.tool_requests[0].tool_request_id)
    )
    status = assistant.execute(conv)
    assert isinstance(status, FinishedStatus)


def get_flow(branch_name: Optional[str] = None) -> Flow:
    step = InputMessageStep("Hello")
    complete_step = CompleteStep(branch_name=branch_name)
    return Flow(
        begin_step=step,
        steps={
            "step_0": step,
            "inner_step1": complete_step,
        },
        control_flow_edges=[ControlFlowEdge(source_step=step, destination_step=complete_step)],
    )


@pytest.mark.parametrize(
    "branching_input,expected_last_step",
    [
        ("success", "sub_success_end_step"),
        ("unknown", "sub_default_end_step"),
        ("success_branch", "sub_default_end_step"),
        ("failure", "sub_failure_end_step"),
    ],
)
def test_can_use_branches_mapping(branching_input, expected_last_step):
    flow = get_flow_with_branching_subflow()
    conv = flow.start_conversation(inputs={BranchingStep.NEXT_BRANCH_NAME: branching_input})
    status = flow.execute(conv)
    assert isinstance(status, FinishedStatus)
    assert status.complete_step_name == expected_last_step


@pytest.mark.parametrize(
    "branching_input,expected_last_step",
    [
        ("success", "sub_success_end_step"),
        ("unknown", "sub_default_end_step"),
        ("success_branch", "sub_default_end_step"),
        ("failure", "sub_failure_end_step"),
    ],
)
def test_can_use_branches_mapping_with_complete_step_branch_names(
    branching_input, expected_last_step
):
    flow = get_flow_with_branching_subflow(
        success_branch_name="CUSTOM_SUCCESS",
        failure_branch_name="CUSTOM_FAILURE",
        default_branch_name="CUSTOM_DEFAULT",
    )
    conv = flow.start_conversation(inputs={BranchingStep.NEXT_BRANCH_NAME: branching_input})
    status = flow.execute(conv)
    assert isinstance(status, FinishedStatus)
    assert status.complete_step_name == expected_last_step


def test_execute_flow_on_wrong_conversation(remotely_hosted_llm):
    step = InputMessageStep("")
    flow_1 = Flow.from_steps([step])
    flow_2 = Flow.from_steps([step])

    conv = flow_1.start_conversation()
    with pytest.raises(ValueError, match="You are trying to call"):
        flow_2.execute(conv)
