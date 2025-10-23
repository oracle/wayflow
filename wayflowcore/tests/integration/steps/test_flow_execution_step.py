# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import Optional

import pytest

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
)
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty
from wayflowcore.steps import (
    BranchingStep,
    CompleteStep,
    FlowExecutionStep,
    InputMessageStep,
    ToolExecutionStep,
)
from wayflowcore.tools import ClientTool, ServerTool, ToolResult

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
        begin_step=step_b,
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
    conversation.execute()


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
        conversation.execute()


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
    conversation.execute()


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
    conversation.execute()


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
    conversation.execute()


def test_sub_conversation_shares_same_message_list_as_main_conversation() -> None:
    subflow_step = FlowExecutionStep(flow=Flow.from_steps([InputMessageStep("Hello")]))
    assistant = Flow.from_steps([subflow_step])

    conversation = assistant.start_conversation()
    conversation.execute()

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
    status = conv.execute()
    assert isinstance(status, ToolRequestStatus)
    conv.append_tool_result(
        ToolResult(content="whatever", tool_request_id=status.tool_requests[0].tool_request_id)
    )
    status = conv.execute()
    assert isinstance(status, FinishedStatus)


@pytest.fixture
def flow_with_client_tool_confirmation() -> Flow:
    name_tool = ClientTool(
        name="name_tool",
        description="Ask the user for some name",
        parameters={},
        requires_confirmation=True,
    )
    step = FlowExecutionStep(
        flow=Flow.from_steps(
            [
                ToolExecutionStep(tool=name_tool, raise_exceptions=False),
            ]
        )
    )
    assistant = Flow.from_steps([step])
    return assistant


def test_subflow_with_client_tool_confirmation_works_with_tool_confirmation(
    flow_with_client_tool_confirmation,
) -> None:
    conv = flow_with_client_tool_confirmation.start_conversation()
    status = conv.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    status.confirm_tool_execution(tool_request=status.tool_requests[0])
    status = conv.execute()
    assert isinstance(status, ToolRequestStatus)
    conv.append_tool_result(
        ToolResult(content="whatever", tool_request_id=status.tool_requests[0].tool_request_id)
    )
    status = conv.execute()
    assert isinstance(status, FinishedStatus)


def test_subflow_with_client_tool_confirmation_works_with_tool_rejection(
    flow_with_client_tool_confirmation,
) -> None:
    conv = flow_with_client_tool_confirmation.start_conversation()
    status = conv.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    status.reject_tool_execution(tool_request=status.tool_requests[0])
    status = conv.execute()
    assert isinstance(status, FinishedStatus)


def test_subflow_with_client_tool_confirmation_raises_if_not_confirmed(
    flow_with_client_tool_confirmation,
) -> None:
    conv = flow_with_client_tool_confirmation.start_conversation()
    status = conv.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    with pytest.raises(ValueError):
        status = conv.execute()


def test_subflow_execution_will_yield_with_tool_execution_confirmation_status_inside() -> None:
    random_func = lambda name: name
    name_tool = ServerTool(
        func=random_func,
        name="name_tool",
        description="Ask the user for some name",
        parameters={"name": {"type": "string"}},
        requires_confirmation=True,
    )
    step = FlowExecutionStep(
        flow=Flow.from_steps(
            [
                ToolExecutionStep(tool=name_tool, raise_exceptions=False),
            ]
        )
    )
    assistant = Flow.from_steps([step])
    conv = assistant.start_conversation(inputs={"name": "dummy user"})
    status = conv.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    status.reject_tool_execution(tool_request=status.tool_requests[0], reason="No reason")
    status = conv.execute()
    assert isinstance(status, FinishedStatus)

    conv = assistant.start_conversation(inputs={"name": "dummy user"})
    status = conv.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    status.confirm_tool_execution(
        tool_request=status.tool_requests[0], modified_args={"name": "another user"}
    )
    status = conv.execute()
    assert isinstance(status, FinishedStatus)

    conv = assistant.start_conversation(inputs={"name": "dummy user"})
    status = conv.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    with pytest.raises(ValueError):
        status = conv.execute()


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
    status = conv.execute()
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
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.complete_step_name == expected_last_step


def test_subflow_with_subset_of_inputs_outputs_exposes_only_selected_inputs_and_outputs():
    map_tool = ServerTool(
        name="tool",
        description="tool",
        input_descriptors=[
            StringProperty(name="input_a"),
            StringProperty(name="input_b", default_value="hello"),
        ],
        output_descriptors=[StringProperty(name="output_a"), StringProperty(name="output_b")],
        func=lambda input_a, input_b: {"output_a": input_a, "output_b": input_b},
    )
    tool_step = ToolExecutionStep(name="tool_node", tool=map_tool)
    subflow = Flow(
        name="flow",
        begin_step=tool_step,
        control_flow_edges=[ControlFlowEdge(source_step=tool_step, destination_step=None)],
        input_descriptors=[StringProperty(name="input_a")],
        output_descriptors=[StringProperty(name="output_a")],
    )
    subflow_step = FlowExecutionStep(name="subflow_node", flow=subflow)

    assert len(subflow_step.input_descriptors) == 1
    assert subflow_step.input_descriptors[0].name == "input_a"

    assert len(subflow_step.output_descriptors) == 1
    assert subflow_step.output_descriptors[0].name == "output_a"

    flow = Flow.from_steps([subflow_step])

    assert len(flow.input_descriptors) == 1
    assert flow.input_descriptors[0].name == "input_a"
    assert len(flow.input_descriptors_dict) == 1
    assert "input_a" in flow.input_descriptors_dict

    assert len(flow.output_descriptors) == 1
    assert flow.output_descriptors[0].name == "output_a"
    assert len(flow.output_descriptors_dict) == 1
    assert "output_a" in flow.output_descriptors_dict

    conversation = flow.start_conversation(inputs={"input_a": "a"})
    state = conversation.execute()

    assert isinstance(state, FinishedStatus)
    assert len(state.output_values) == 1
    assert state.output_values["output_a"] == "a"
