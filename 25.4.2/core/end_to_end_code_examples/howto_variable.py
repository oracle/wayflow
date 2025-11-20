# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# %%[markdown]
# Code Example - How to Use Variables for Shared State in Flows
# -------------------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==25.4" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_variable.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.



# %%[markdown]
## Define a Variable

# %%
from wayflowcore.variable import Variable
from wayflowcore.property import ListProperty, StringProperty

feedback_variable = Variable(
    name="user_feedback",
    type=ListProperty(item_type=StringProperty()),
    description="list of user feedback",
    default_value=[],
)


# %%[markdown]
## Define Flow Steps

# %%
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


# %%[markdown]
## Define a Flow with variable

# %%
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


# %%[markdown]
## Execute flow

# %%
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


# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_yaml(flow)


# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

assistant: Flow = AgentSpecLoader().load_yaml(serialized_assistant)
