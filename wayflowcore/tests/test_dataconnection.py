# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import contextlib

import pytest

from wayflowcore.contextproviders.constantcontextprovider import ConstantContextProvider
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import (
    _run_flow_and_return_conversation_and_status,
    create_single_step_flow,
    run_flow_and_return_outputs,
)
from wayflowcore.property import (
    BooleanProperty,
    DictProperty,
    FloatProperty,
    IntegerProperty,
    ListProperty,
    ObjectProperty,
    Property,
    StringProperty,
)
from wayflowcore.steps import BranchingStep, OutputMessageStep


@pytest.fixture
def python_context_provider():
    return ConstantContextProvider(value="hello", output_description=StringProperty(name="output"))


def test_dataedge_can_be_created_with_steps():
    source_step = OutputMessageStep()
    destination_step = OutputMessageStep("{{input_message}}")

    data_edge = DataFlowEdge(
        source_step, OutputMessageStep.OUTPUT, destination_step, "input_message"
    )


def test_dataedge_can_be_created_with_context_provider_and_step(python_context_provider):
    source_context_provider = python_context_provider
    destination_step = OutputMessageStep("{{input_message}}")

    data_edge = DataFlowEdge(source_context_provider, "output", destination_step, "input_message")


@pytest.mark.parametrize(
    "source_step,destination_step",
    [
        (
            OutputMessageStep(input_mapping={"hello": "$hello"}, message_template="{{hello}}"),
            OutputMessageStep(),
        ),
        (
            OutputMessageStep(output_mapping={OutputMessageStep.OUTPUT: "$hello"}),
            OutputMessageStep(),
        ),
        (
            OutputMessageStep(),
            OutputMessageStep(input_mapping={"hello": "$hello"}, message_template="{{hello}}"),
        ),
        (
            OutputMessageStep(),
            OutputMessageStep(output_mapping={OutputMessageStep.OUTPUT: "$hello"}),
        ),
    ],
)
def test_dataedge_raises_error_if_step_have_wrong_iomapping(source_step, destination_step):
    with pytest.raises(
        ValueError, match="Source output .* is not in the list of output descriptors of step"
    ):
        data_edge = DataFlowEdge(source_step, "output", destination_step, OutputMessageStep.OUTPUT)


@pytest.mark.parametrize(
    "step_with_io_mapping",
    [
        OutputMessageStep(input_mapping={"hello": "$hello"}, message_template="{{hello}}"),
        OutputMessageStep(output_mapping={OutputMessageStep.OUTPUT: "$hello"}),
    ],
)
def test_flow_with_one_dataedge_works_with_io_mapping(step_with_io_mapping):
    source_step = OutputMessageStep()
    destination_step = OutputMessageStep("{{input_message}}")

    data_edge = DataFlowEdge(
        source_step, OutputMessageStep.OUTPUT, destination_step, "input_message"
    )
    flow = Flow.from_steps(
        steps=[source_step, destination_step, step_with_io_mapping],
        data_flow_edges=[data_edge],
    )


def test_dataedge_is_successfully_inferred_with_no_mapping():
    source_step = OutputMessageStep()
    destination_step = OutputMessageStep("{{" + OutputMessageStep.OUTPUT + "}}")

    flow = Flow.from_steps(
        steps=[source_step, destination_step],
    )
    expected_data_edge = DataFlowEdge(
        source_step, OutputMessageStep.OUTPUT, destination_step, OutputMessageStep.OUTPUT
    )
    assert expected_data_edge in flow.data_flow_edges


def test_dataedge_is_successfully_inferred_with_io_mapping():
    IO_VARNAME = "$variable"
    source_step = OutputMessageStep(output_mapping={OutputMessageStep.OUTPUT: IO_VARNAME})
    destination_step = OutputMessageStep(
        "{{message}} {{user_input}}", input_mapping={"message": IO_VARNAME}
    )

    flow = Flow.from_steps(
        steps=[source_step, destination_step],
    )
    expected_data_edge = DataFlowEdge(source_step, IO_VARNAME, destination_step, IO_VARNAME)
    assert expected_data_edge in flow.data_flow_edges


def test_e2e_with_simple_flow_without_mapping():
    fake_processing_step = OutputMessageStep("Successfully processed username {{username}}")
    output_step = OutputMessageStep('{{session_id}}: Received message "{{processing_message}}"')
    data_edge = DataFlowEdge(
        fake_processing_step, OutputMessageStep.OUTPUT, output_step, "processing_message"
    )

    flow = Flow.from_steps(
        steps=[fake_processing_step, output_step],
        data_flow_edges=[data_edge],
    )

    assert data_edge in flow.data_flow_edges
    conv, _ = _run_flow_and_return_conversation_and_status(
        flow, {"username": "Username#123", "session_id": "Session#456"}
    )
    assert (
        conv.get_last_message().content
        == 'Session#456: Received message "Successfully processed username Username#123"'
    )


def test_e2e_with_simple_flow_with_mapping():
    # I/O Variables
    USERNAME_IO = "$username"
    PROCESSING_MESSAGE_IO = "$processing_message"

    fake_processing_step = OutputMessageStep(
        "Successfully processed username {{username}}",
        input_mapping={"username": USERNAME_IO},
        output_mapping={OutputMessageStep.OUTPUT: PROCESSING_MESSAGE_IO},
    )
    output_step = OutputMessageStep(
        '{{session_id}}: Received message "{{processing_message}}"',
        input_mapping={"processing_message": PROCESSING_MESSAGE_IO},
    )

    flow = Flow.from_steps(
        steps=[fake_processing_step, output_step],
    )

    data_edge = DataFlowEdge(
        fake_processing_step, PROCESSING_MESSAGE_IO, output_step, PROCESSING_MESSAGE_IO
    )
    assert data_edge in flow.data_flow_edges
    # mix of using mapping for username and no mapping for the session id
    conv_inputs = {USERNAME_IO: "Username#123", "session_id": "Session#456"}
    conv, _ = _run_flow_and_return_conversation_and_status(flow, conv_inputs)
    assert (
        conv.get_last_message().content
        == 'Session#456: Received message "Successfully processed username Username#123"'
    )


def test_data_flow_edge_correctly_passes_data_from_context_provider(python_context_provider):
    step = OutputMessageStep("{{context}}{{context}}")
    edge = DataFlowEdge(python_context_provider, "output", step, "context")
    flow = create_single_step_flow(step, data_flow_edges=[edge])
    outputs = run_flow_and_return_outputs(flow)
    assert outputs[OutputMessageStep.OUTPUT] == "hellohello"


def test_flow_raises_error_on_colliding_context_provider_destinations():
    hello_cp = ConstantContextProvider(
        value="hello", output_description=StringProperty(name="hello_output")
    )
    world_cp = ConstantContextProvider(
        value="world", output_description=StringProperty(name="world_output")
    )
    step = OutputMessageStep("{{context}}{{context}}")
    hello_edge = DataFlowEdge(hello_cp, "hello_output", step, "context")
    world_edge = DataFlowEdge(world_cp, "world_output", step, "context")
    with pytest.raises(
        ValueError, match="Found multiple context providers targeting the same destinations"
    ):
        create_single_step_flow(
            step=step,
            context_providers=[hello_cp, world_cp],
            data_flow_edges=[hello_edge, world_edge],
        )


def test_flow_XYZ_to_zxy_correctly_runs_and_infers_ios():
    X, Y, Z = OutputMessageStep("X"), OutputMessageStep("Y"), OutputMessageStep("Z")
    x, y, z = OutputMessageStep(">{{a}}"), OutputMessageStep(">{{b}}"), OutputMessageStep(">{{c}}")
    X_to_y = DataFlowEdge(X, OutputMessageStep.OUTPUT, y, "b")
    X_to_z = DataFlowEdge(X, OutputMessageStep.OUTPUT, z, "c")
    Y_to_x = DataFlowEdge(Y, OutputMessageStep.OUTPUT, x, "a")
    Y_to_z = DataFlowEdge(Y, OutputMessageStep.OUTPUT, z, "c")
    Z_to_y = DataFlowEdge(Z, OutputMessageStep.OUTPUT, y, "b")
    Z_to_x = DataFlowEdge(Z, OutputMessageStep.OUTPUT, x, "a")
    branching_step = BranchingStep({"X": "branch_X", "Y": "branch_Y", "Z": "branch_Z"})
    X_to_branch = DataFlowEdge(
        X, OutputMessageStep.OUTPUT, branching_step, BranchingStep.NEXT_BRANCH_NAME
    )
    Y_to_branch = DataFlowEdge(
        Y, OutputMessageStep.OUTPUT, branching_step, BranchingStep.NEXT_BRANCH_NAME
    )
    Z_to_branch = DataFlowEdge(
        Z, OutputMessageStep.OUTPUT, branching_step, BranchingStep.NEXT_BRANCH_NAME
    )
    XYZ_then_branching_flow = Flow(
        begin_step=X,
        steps={"X": X, "Y": Y, "Z": Z, "x": x, "y": y, "z": z, "branch": branching_step},
        control_flow_edges=[
            ControlFlowEdge(source_step=X, destination_step=Y),
            ControlFlowEdge(source_step=Y, destination_step=Z),
            ControlFlowEdge(source_step=Z, destination_step=branching_step),
            ControlFlowEdge(
                source_step=branching_step, source_branch="branch_X", destination_step=x
            ),
            ControlFlowEdge(
                source_step=branching_step, source_branch="branch_Y", destination_step=y
            ),
            ControlFlowEdge(
                source_step=branching_step, source_branch="branch_Z", destination_step=z
            ),
            ControlFlowEdge(
                source_step=branching_step, source_branch="default", destination_step=None
            ),
            ControlFlowEdge(source_step=x, destination_step=None),
            ControlFlowEdge(source_step=y, destination_step=None),
            ControlFlowEdge(source_step=z, destination_step=None),
        ],
        data_flow_edges=[
            X_to_y,
            X_to_z,
            Y_to_x,
            Y_to_z,
            Z_to_y,
            Z_to_x,
            X_to_branch,
            Y_to_branch,
            Z_to_branch,
        ],
    )
    assert len(XYZ_then_branching_flow.input_descriptors_dict) == 0
    conversation = XYZ_then_branching_flow.start_conversation()
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values[OutputMessageStep.OUTPUT] == ">Y"


def test_no_name_mapping_occurs_when_data_flow_edges_are_specified():
    x, y, z = (
        OutputMessageStep("X"),
        OutputMessageStep(">{{output_message}}"),
        OutputMessageStep(">>{{output_message}}"),
    )
    edge = DataFlowEdge(x, OutputMessageStep.OUTPUT, z, "output_message")
    flow = Flow(
        begin_step=x,
        steps={"x": x, "y": y, "z": z},
        control_flow_edges=[
            ControlFlowEdge(source_step=x, destination_step=y),
            ControlFlowEdge(source_step=y, destination_step=z),
            ControlFlowEdge(source_step=z, destination_step=None),
        ],
        data_flow_edges=[edge],
    )
    assert set(flow.input_descriptors_dict) == {"output_message"}
    conversation = flow.start_conversation(inputs={"output_message": "This is Y"})
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    messages = conversation.get_messages()
    assert messages[0].content == "X"
    assert messages[1].content == ">This is Y"
    assert messages[2].content == ">>X"


def test_flow_can_have_both_data_edges_and_input_output_mapping():
    input_step = OutputMessageStep(
        "Here is a message",
        output_mapping={
            OutputMessageStep.OUTPUT: "message_1",
        },
    )
    output_step = OutputMessageStep(
        "first message was: {{first_message}}", input_mapping={"first_message": "message_1"}
    )
    flow = Flow(
        begin_step=input_step,
        steps={"input": input_step, "output": output_step},
        data_flow_edges=[
            DataFlowEdge(
                source_step=input_step,
                source_output="message_1",
                destination_step=output_step,
                destination_input="message_1",
            ),
        ],
        control_flow_edges=[
            ControlFlowEdge(source_step=input_step, destination_step=output_step),
            ControlFlowEdge(source_step=output_step, destination_step=None),
        ],
    )

    outputs = run_flow_and_return_outputs(flow)
    assert "message_1" in outputs


@pytest.mark.parametrize(
    "source_type, destination_type, can_be_casted",
    [
        (BooleanProperty(), BooleanProperty(), True),
        (BooleanProperty(), IntegerProperty(), True),
        (BooleanProperty(), FloatProperty(), True),
        (BooleanProperty(), StringProperty(), True),
        (BooleanProperty(), ListProperty(), False),
        (BooleanProperty(), DictProperty(), False),
        (BooleanProperty(), ObjectProperty(), False),
        (IntegerProperty(), BooleanProperty(), True),
        (IntegerProperty(), IntegerProperty(), True),
        (IntegerProperty(), FloatProperty(), True),
        (IntegerProperty(), StringProperty(), True),
        (IntegerProperty(), ListProperty(), False),
        (IntegerProperty(), DictProperty(), False),
        (IntegerProperty(), ObjectProperty(), False),
        (FloatProperty(), BooleanProperty(), True),
        (FloatProperty(), IntegerProperty(), True),
        (FloatProperty(), FloatProperty(), True),
        (FloatProperty(), StringProperty(), True),
        (FloatProperty(), ListProperty(), False),
        (FloatProperty(), DictProperty(), False),
        (FloatProperty(), ObjectProperty(), False),
        (StringProperty(), BooleanProperty(), False),
        (StringProperty(), IntegerProperty(), False),
        (StringProperty(), FloatProperty(), False),
        (StringProperty(), StringProperty(), True),
        (StringProperty(), ListProperty(), False),
        (StringProperty(), DictProperty(), False),
        (StringProperty(), ObjectProperty(), False),
        (ListProperty(), BooleanProperty(), False),
        (ListProperty(), IntegerProperty(), False),
        (ListProperty(), FloatProperty(), False),
        (ListProperty(), StringProperty(), True),
        (ListProperty(), ListProperty(), True),
        (
            ListProperty(item_type=IntegerProperty()),
            ListProperty(item_type=BooleanProperty()),
            True,
        ),
        (
            ListProperty(item_type=StringProperty()),
            ListProperty(item_type=BooleanProperty()),
            False,
        ),
        (ListProperty(), DictProperty(), False),
        (ListProperty(), ObjectProperty(), False),
        (DictProperty(), BooleanProperty(), False),
        (DictProperty(), IntegerProperty(), False),
        (DictProperty(), FloatProperty(), False),
        (DictProperty(), StringProperty(), True),
        (DictProperty(), ListProperty(), False),
        (DictProperty(), DictProperty(), True),
        (
            DictProperty(key_type=IntegerProperty(), value_type=BooleanProperty()),
            DictProperty(key_type=BooleanProperty(), value_type=StringProperty()),
            True,
        ),
        (DictProperty(key_type=BooleanProperty()), DictProperty(key_type=DictProperty()), False),
        (DictProperty(), ObjectProperty(), False),
        (ObjectProperty(), BooleanProperty(), False),
        (ObjectProperty(), IntegerProperty(), False),
        (ObjectProperty(), FloatProperty(), False),
        (ObjectProperty(), StringProperty(), True),
        (ObjectProperty(), ListProperty(), False),
        (ObjectProperty(), DictProperty(), True),
        (ObjectProperty(), ObjectProperty(), True),
        (
            ObjectProperty(properties={"a": IntegerProperty()}),
            ObjectProperty(properties={"a": IntegerProperty()}),
            True,
        ),
        (
            ObjectProperty(properties={"a": IntegerProperty()}),
            ObjectProperty(properties={"a": StringProperty()}),
            True,
        ),
        (
            ObjectProperty(properties={"a": IntegerProperty()}),
            ObjectProperty(properties={"b": IntegerProperty()}),
            False,
        ),
        (
            ObjectProperty(properties={"a": IntegerProperty()}),
            ObjectProperty(properties={"a": ListProperty()}),
            False,
        ),
    ],
)
def test_data_flow_edges_checks_types_correctly(
    source_type: Property, destination_type: Property, can_be_casted: bool
):
    source_step = OutputMessageStep(
        message_template="", output_descriptors=[source_type.copy(name=OutputMessageStep.OUTPUT)]
    )
    destination_step = OutputMessageStep(
        message_template="{{destination}}",
        input_descriptors=[destination_type.copy(name="destination")],
    )

    with (
        pytest.raises(TypeError, match="types are not compatible")
        if not can_be_casted
        else contextlib.suppress()
    ):
        DataFlowEdge(
            source_step=source_step,
            destination_step=destination_step,
            source_output=OutputMessageStep.OUTPUT,
            destination_input="destination",
        )
