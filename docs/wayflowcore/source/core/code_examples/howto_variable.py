# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Code Example - How to Use Variables for Shared State in Flows

# .. start-##_Define_a_Variable
from wayflowcore.variable import Variable
from wayflowcore.property import ListProperty, StringProperty

feedback_variable = Variable(
    name="user_feedback",
    type=ListProperty(item_type=StringProperty()),
    description="list of user feedback",
    default_value=[],
)
# .. end-##_Define_a_Variable

# .. start-##_Define_Flow_Steps
from wayflowcore.steps import StartStep, OutputMessageStep, VariableReadStep, VariableWriteStep
from wayflowcore.property import StringProperty

FEEDBACK_1 = "feedback_1"
FEEDBACK_2 = "feedback_2"

start_step = StartStep(
    name="start_step",
    input_descriptors={StringProperty(FEEDBACK_1), StringProperty(FEEDBACK_2)},
)

write_feedback_1 = VariableWriteStep(
    name="write_step_1",
    variable=feedback_variable,
    operation="insert",
)

write_feedback_2 = VariableWriteStep(
    name="write_step_2",
    variable=feedback_variable,
    operation="insert",
)

read_feedback = VariableReadStep(variable=feedback_variable, name="read_step")

output_step = OutputMessageStep("Collected feedback: {{ feedback }}", name="output_step")
# .. end-##_Define_Flow_Steps

# .. start-##_Define_a_Flow_with_variable
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow

flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(start_step, write_feedback_1),
        ControlFlowEdge(write_feedback_1, write_feedback_2),
        ControlFlowEdge(write_feedback_2, read_feedback),
        ControlFlowEdge(read_feedback, output_step),
        ControlFlowEdge(output_step, None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, FEEDBACK_1, write_feedback_1, VariableWriteStep.VALUE),
        DataFlowEdge(start_step, FEEDBACK_2, write_feedback_2, VariableWriteStep.VALUE),
        DataFlowEdge(read_feedback, VariableReadStep.VALUE, output_step, "feedback"),
    ],
    variables=[feedback_variable],
)
# .. end-##_Define_a_Flow_with_variable

# .. start-##_Execute_flow
conv = flow.start_conversation(
    inputs={
        FEEDBACK_1: "Very good!",
        FEEDBACK_2: "Need to improve!",
    }
)
conv.execute()

result = conv.get_last_message().content
print(result)
# >>> Collected feedback: ["Very good!", "Need to improve!"]
# .. end-##_Execute_flow

# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_yaml(flow)
# .. end-##_Export_config_to_Agent_Spec

# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

assistant: Flow = AgentSpecLoader().load_yaml(serialized_assistant)
# .. end-##_Load_Agent_Spec_config
