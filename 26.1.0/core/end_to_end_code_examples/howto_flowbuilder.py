# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Build Flows with the Flow Builder
# -------------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_flowbuilder.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Build a linear flow

# %%
from wayflowcore.flowbuilder import FlowBuilder
from wayflowcore.steps import OutputMessageStep

n1 = OutputMessageStep(name="n1", message_template="{{username}}")
n2 = OutputMessageStep(name="n2", message_template="Hello, {{username}}")

flow = (
    FlowBuilder()
    .add_sequence([n1, n2])
    .set_entry_point(n1)
    .set_finish_points(n2)
    .build()
)
from wayflowcore.executors.executionstatus import FinishedStatus
conversation = flow.start_conversation({"username": "User_123"})
status = conversation.execute()
assert isinstance(status, FinishedStatus)
print(status.output_values)
# {'output_message': 'Hello, User_123'}

# %%[markdown]
## Build a linear flow equivalent

# %%
from wayflowcore.flowbuilder import FlowBuilder
from wayflowcore.steps import OutputMessageStep

greet = OutputMessageStep(name="greet", message_template="Say hello")
reply = OutputMessageStep(name="reply", message_template="Say world")

linear_flow = FlowBuilder.build_linear_flow([greet, reply])

# %%[markdown]
## Build a flow with a conditional

# %%
decider = OutputMessageStep(name="decider", message_template="Return success or fail")
on_success = OutputMessageStep(name="on_success", message_template="OK")
on_fail = OutputMessageStep(name="on_fail", message_template="KO")

flow_with_branch = (
    FlowBuilder()
    .add_step(decider)
    .add_step(on_success)
    .add_step(on_fail)
    .add_conditional(
        source_step=decider,
        source_value=decider.OUTPUT,
        destination_map={"success": on_success, "fail": on_fail},
        default_destination=on_fail,
    )
    .set_entry_point(decider)
    .set_finish_points([on_success, on_fail])
    .build()
)

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_agent = AgentSpecExporter().to_json(linear_flow)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader().load_json(serialized_agent)
