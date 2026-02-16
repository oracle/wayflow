# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# How to Create Conditional Transitions in Flows
# ----------------------------------------------

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
# python howto_branching.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import cast


from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="meta-llama/Meta-Llama-3.1-8B-Instruct",
    host_port="VLLM_HOST_PORT",
)

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty


# %%[markdown]
## Branching step

# %%
from wayflowcore.steps import BranchingStep, OutputMessageStep, StartStep

branching_step = BranchingStep(
    name="branching_step",
    branch_name_mapping={
        "[SUCCESS]": "success",
        "[FAILURE]": "failure",
    },
)



# %%[markdown]
## Flow

# %%
success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="start_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=branching_step),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=success_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "my_var", branching_step, BranchingStep.NEXT_BRANCH_NAME),
    ],
)



# %%[markdown]
## Execute

# %%
conversation = flow.start_conversation(inputs={"my_var": "[SUCCESS]"})
conversation.execute()
assert conversation.get_last_message().content == "It was a success"

conversation = flow.start_conversation(inputs={"my_var": "[FAILURE]"})
conversation.execute()
assert conversation.get_last_message().content == "It was a failure"

conversation = flow.start_conversation(inputs={"my_var": "unknown"})
conversation.execute()
assert conversation.get_last_message().content == "It was a failure"



# %%[markdown]
## Export to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter
serialized_flow = AgentSpecExporter().to_json(flow)


# %%[markdown]
## Load and execute with Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecLoader

new_flow: Flow = AgentSpecLoader().load_json(serialized_flow)

conversation = new_flow.start_conversation(inputs={"my_var": "[SUCCESS]"})
conversation.execute()
assert conversation.get_last_message().content == "It was a success"

conversation = new_flow.start_conversation(inputs={"my_var": "[FAILURE]"})
conversation.execute()
assert conversation.get_last_message().content == "It was a failure"

conversation = new_flow.start_conversation(inputs={"my_var": "unknown"})
conversation.execute()
assert conversation.get_last_message().content == "It was a failure"


# %%[markdown]
## Branching with a regular expression

# %%
import re

from wayflowcore.flow import Flow
from wayflowcore.steps import BranchingStep, OutputMessageStep, RegexExtractionStep

tokens = ["[SUCCESS]", "[FAILURE]"]

regex_step = RegexExtractionStep(
    name="regex_step",
    regex_pattern=rf"({'|'.join(re.escape(token) for token in tokens)})",
)
branching_step = BranchingStep(
    name="branching_step",
    branch_name_mapping={
        "[SUCCESS]": "success",
        "[FAILURE]": "failure",
    },
)

success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="start_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=regex_step),
        ControlFlowEdge(source_step=regex_step, destination_step=branching_step),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=success_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "my_var", regex_step, RegexExtractionStep.TEXT),
        DataFlowEdge(regex_step, RegexExtractionStep.OUTPUT, branching_step, BranchingStep.NEXT_BRANCH_NAME),
    ],
)
conversation = flow.start_conversation(
    inputs={"my_var": "The test passed successfully, so it's a [SUCCESS]"},
)
conversation.execute()
# "It was a success"



# %%[markdown]
## Branching with a regular expression AgentSpec export

# %%
serialized_flow = AgentSpecExporter().to_json(flow)
flow: Flow = AgentSpecLoader().load_json(serialized_flow)
conversation = flow.start_conversation(
    inputs={"my_var": "The test passed successfully, so it's a [SUCCESS]"},
)
conversation.execute()
assert conversation.get_last_message().content == "It was a success"


# %%[markdown]
## Branching with a template

# %%
from wayflowcore.steps import BranchingStep, OutputMessageStep, StartStep, TemplateRenderingStep
from wayflowcore.property import BooleanProperty

template = "{% if my_var %}[SUCCESS]{% else %}[FAILURE]{% endif %}"  # for boolean
# template = "{% if my_var > 10 %}[SUCCESS]{% else %}[FAILURE]{% endif %}"  # for integer
# template = "{% if lower(my_var) == '[success]' %}[SUCCESS]{% else %}[FAILURE]{% endif %}"  # with specific expressions

template_step = TemplateRenderingStep(
    name="template_step",
    template=template,
)
branching_step = BranchingStep(
    name="branching_step",
    branch_name_mapping={
        "[SUCCESS]": "success",
        "[FAILURE]": "failure",
    },
)
TEMPLATE_STEP = "template_step"
START_STEP = "start_step"

success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
start_step = StartStep(input_descriptors=[BooleanProperty("my_var")], name="start_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=template_step),
        ControlFlowEdge(source_step=template_step, destination_step=branching_step),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=success_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "my_var", template_step, "my_var"),
        DataFlowEdge(
            template_step, TemplateRenderingStep.OUTPUT, branching_step, BranchingStep.NEXT_BRANCH_NAME
        ),
    ],
)
conversation = flow.start_conversation(inputs={"my_var": True})
conversation.execute()
# "It was a success"



# %%[markdown]
## Branching with a template AgentSpec export

# %%
serialized_flow = AgentSpecExporter().to_json(flow)
flow = cast(Flow, AgentSpecLoader().load_json(serialized_flow))
conversation = flow.start_conversation(
    inputs={"my_var": True},
)
conversation.execute()
assert conversation.get_last_message().content == "It was a success"


# %%[markdown]
## Branching with an LLM

# %%
from wayflowcore.flow import Flow
from wayflowcore.steps import ChoiceSelectionStep, OutputMessageStep

choice_step = ChoiceSelectionStep(
    name="choice_step",
    llm=llm,
    next_steps=[
        ("success", "in case the test passed successfully"),
        ("failure", "in case the test did not pass"),
    ],
)

success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="start_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=choice_step),
        ControlFlowEdge(
            source_step=choice_step,
            destination_step=success_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=choice_step,
            destination_step=failure_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=choice_step,
            destination_step=failure_step,
            source_branch=ChoiceSelectionStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "my_var", choice_step, ChoiceSelectionStep.INPUT),
    ],
)
conversation = flow.start_conversation(inputs={"my_var": "TEST IS SUCCESSFUL"})
conversation.execute()
# "It was a success"



# %%[markdown]
## Branching with an LLM AgentSpec export

# %%
serialized_flow = AgentSpecExporter().to_json(flow)
flow = cast(Flow, AgentSpecLoader().load_json(serialized_flow))
conversation = flow.start_conversation(
    inputs={"my_var": True},
)
conversation.execute()
assert conversation.get_last_message().content == "It was a success"


# %%[markdown]
## Branching with a Subflow

# %%
from wayflowcore.flow import Flow
from wayflowcore.steps import BranchingStep, CompleteStep, FlowExecutionStep, OutputMessageStep

tokens = ["[SUCCESS]", "[FAILURE]"]

regex_step = RegexExtractionStep(
    name="regex_step",
    regex_pattern=rf"({'|'.join(re.escape(token) for token in tokens)})",
)
branching_step = BranchingStep(
    name="branching_step",
    branch_name_mapping={
        "[SUCCESS]": "success",
        "[FAILURE]": "failure",
    },
)

sub_start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="sub_start_step")
success_internal_step = CompleteStep(name="success_internal_step")
failure_internal_step = CompleteStep(name="failure_internal_step")
subflow = Flow(
    begin_step=sub_start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=sub_start_step, destination_step=regex_step),
        ControlFlowEdge(source_step=regex_step, destination_step=branching_step),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=success_internal_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_internal_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_internal_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
    ],
    data_flow_edges=[
        DataFlowEdge(sub_start_step, "my_var", regex_step, RegexExtractionStep.TEXT),
        DataFlowEdge(regex_step, RegexExtractionStep.OUTPUT, branching_step, BranchingStep.NEXT_BRANCH_NAME),
    ],
)

subflow_step = FlowExecutionStep(subflow, name="subflow_step")
subflow_step.get_branches()  # ['success_internal_step', 'failure_internal_step']

success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
outer_start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="outer_start_step")
flow = Flow(
    begin_step=outer_start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=outer_start_step, destination_step=subflow_step),
        ControlFlowEdge(
            source_step=subflow_step,
            destination_step=success_step,
            source_branch="success_internal_step",
        ),
        ControlFlowEdge(
            source_step=subflow_step,
            destination_step=failure_step,
            source_branch="failure_internal_step",
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(outer_start_step, "my_var", subflow_step, "my_var"),
    ],
)
conversation = flow.start_conversation(inputs={"my_var": "Test passed, so [SUCCESS]"})
conversation.execute()
# "It was a success"



# %%[markdown]
## Branching with a Subflow AgentSpec export

# %%
serialized_flow = AgentSpecExporter().to_json(flow)
flow = cast(Flow, AgentSpecLoader().load_json(serialized_flow))
conversation = flow.start_conversation(
    inputs={"my_var": "Test passed, so [SUCCESS]"},
)
conversation.execute()
assert conversation.get_last_message().content == "It was a success"
