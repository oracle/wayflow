# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Code Example - Data Flow Edges in Flows

# .. start-##_Flow_with_multi_output_routing
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.controlconnection import ControlFlowEdge

# Flow with one step output used by two subsequent steps
producer = OutputMessageStep(name="Step 1", message_template="value", output_mapping={OutputMessageStep.OUTPUT: "A"})
consumer1 = OutputMessageStep(name="Step 2", message_template="{{A}}")
consumer2 = OutputMessageStep(name="Step 3", message_template="{{A}}")

flow = Flow(
    begin_step=producer,
    control_flow_edges=[
        ControlFlowEdge(producer, consumer1),
        ControlFlowEdge(consumer1, consumer2),
        ControlFlowEdge(consumer2, None)
    ],
)
# .. end-##_Flow_with_multi_output_routing
conv = flow.start_conversation()
_ = conv.execute()
# .. start-##_Flow_with_multi_output_routing_with_explicit_edges
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

producer = OutputMessageStep(name="Step 1", message_template="value")
consumer1 = OutputMessageStep(name="Step 2", message_template="{{A}}")
consumer2 = OutputMessageStep(name="Step 3", message_template="{{A}}")

flow = Flow(
    begin_step=producer,
    control_flow_edges=[
        ControlFlowEdge(producer, consumer1),
        ControlFlowEdge(consumer1, consumer2),
        ControlFlowEdge(consumer2, None)
    ],
    data_flow_edges=[
        DataFlowEdge(producer, source_output=OutputMessageStep.OUTPUT, destination_step=consumer1, destination_input="A"),
        DataFlowEdge(producer, source_output=OutputMessageStep.OUTPUT, destination_step=consumer2, destination_input="A"),
    ],
)
# .. end-##_Flow_with_multi_output_routing_with_explicit_edges
conv = flow.start_conversation()
_ = conv.execute()
# .. start-##_Flow_with_looping
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep, BranchingStep
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.property import StringProperty

# Looping flow
producer = OutputMessageStep(
    name="Step 1",
    message_template="value{{A}}",
    output_mapping={OutputMessageStep.OUTPUT: "B"},
    input_descriptors=[StringProperty(name="A", default_value="")],
    # ^ note that in this looping flow the default_value is required,
    # read the conceptual guide for more information
)
condition = BranchingStep(
    name="Branching",
    input_mapping={BranchingStep.NEXT_BRANCH_NAME: "B"},
    branch_name_mapping={"value": "branch1", "valueextra": "branch2"},
)
add_extra = OutputMessageStep(
    name="Step 2",
    output_mapping={OutputMessageStep.OUTPUT: "A"},
    message_template="extra",
)

flow = Flow(
    begin_step=producer,
    control_flow_edges=[
        ControlFlowEdge(producer, condition),
        ControlFlowEdge(condition, add_extra, source_branch="branch1"),
        ControlFlowEdge(condition, None, source_branch="branch2"),
        ControlFlowEdge(condition, None, source_branch=BranchingStep.BRANCH_DEFAULT),
        ControlFlowEdge(add_extra, producer)
    ],
)
# .. end-##_Flow_with_looping
conv = flow.start_conversation()
_ = conv.execute()
# .. start-##_Flow_with_looping_with_explicit_edges
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

# Looping flow
producer = OutputMessageStep(
    name="Step 1",
    message_template="value{{optional_value}}",
    input_descriptors=[StringProperty(name="optional_value", default_value="")],
    # ^ note that in this looping flow the default_value is required,
    # read the conceptual guide for more information
)
condition = BranchingStep(
    name="Branching",
    branch_name_mapping={"value": "branch1", "valueextra": "branch2"},
)
add_extra = OutputMessageStep(name="Step 3", message_template="extra")

flow = Flow(
    begin_step=producer,
    control_flow_edges=[
        ControlFlowEdge(producer, condition),
        ControlFlowEdge(condition, add_extra, source_branch="branch1"),
        ControlFlowEdge(condition, None, source_branch="branch2"),
        ControlFlowEdge(condition, None, source_branch=BranchingStep.BRANCH_DEFAULT),
        ControlFlowEdge(add_extra, producer)
    ],
    data_flow_edges=[
        DataFlowEdge(producer, source_output=OutputMessageStep.OUTPUT, destination_step=condition, destination_input=BranchingStep.NEXT_BRANCH_NAME),
        DataFlowEdge(add_extra, source_output=OutputMessageStep.OUTPUT, destination_step=producer, destination_input="optional_value"),
    ],
)
# .. end-##_Flow_with_looping_with_explicit_edges
conv = flow.start_conversation()
_ = conv.execute()
