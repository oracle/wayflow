# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Wayflow Code Example - How to Do Structured LLM Generation in Flows
# -------------------------------------------------------------------

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
# python howto_promptexecutionstep.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


# %%[markdown]
## Define the article

# %%
article = """Sea turtles are ancient reptiles that have been around for over 100 million years. They play crucial roles in marine ecosystems, such as maintaining healthy seagrass beds and coral reefs. Unfortunately, they are under threat due to poaching, habitat loss, and pollution. Conservation efforts worldwide aim to protect nesting sites and reduce bycatch in fishing gear."""


# %%[markdown]
## Define the llm

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## Create the flow using the prompt execution step

# %%
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep

start_step = StartStep(input_descriptors=[StringProperty("article")])
summarize_step = PromptExecutionStep(
    llm=llm,
    prompt_template="""Summarize this article in 10 words:\n {{article}}""",
    output_mapping={PromptExecutionStep.OUTPUT: "summary"},
)
summarize_step_name = "summarize_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        summarize_step_name: summarize_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_step),
        ControlFlowEdge(source_step=summarize_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "article", summarize_step, "article"),
    ],
)


# %%[markdown]
## Run the flow to get the summary

# %%
conversation = flow.start_conversation(inputs={"article": article})
status = conversation.execute()
print(status.output_values["summary"])
# Sea turtles face threats from poaching, habitat loss, and pollution globally.

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge


# %%[markdown]
## Use structured generation to extract formatted information

# %%
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep

animal_output = StringProperty(
    name="animal_name",
    description="name of the animal",
    default_value="",
)
danger_level_output = StringProperty(
    name="danger_level",
    description='level of danger of the animal. Can be "HIGH", "MEDIUM" or "LOW"',
    default_value="",
)
threats_output = ListProperty(
    name="threats",
    description="list of threats for the animal",
    item_type=StringProperty("threat"),
    default_value=[],
)


start_step = StartStep(input_descriptors=[StringProperty("article")])
summarize_step = PromptExecutionStep(
    llm=llm,
    prompt_template="""Extract from the following article the name of the animal, its danger level and the threats it's subject to. The article:\n\n {{article}}""",
    output_descriptors=[animal_output, danger_level_output, threats_output],
)
summarize_step_name = "summarize_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        summarize_step_name: summarize_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_step),
        ControlFlowEdge(source_step=summarize_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "article", summarize_step, "article"),
    ],
)

conversation = flow.start_conversation(inputs={"article": article})
status = conversation.execute()
print(status.output_values)
# {'threats': ['poaching', 'habitat loss', 'pollution'], 'danger_level': 'HIGH', 'animal_name': 'Sea turtles'}

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge


# %%[markdown]
## Use structured generation with JSON schema

# %%
from wayflowcore.property import Property, StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep

animal_json_schema = {
    "title": "animal_object",
    "description": "information about the animal",
    "type": "object",
    "properties": {
        "animal_name": {
            "type": "string",
            "description": "name of the animal",
            "default": "",
        },
        "danger_level": {
            "type": "string",
            "description": 'level of danger of the animal. Can be "HIGH", "MEDIUM" or "LOW"',
            "default": "",
        },
        "threats": {
            "type": "array",
            "description": "list of threats for the animal",
            "items": {"type": "string"},
            "default": [],
        },
    },
}
animal_descriptor = Property.from_json_schema(animal_json_schema)

start_step = StartStep(input_descriptors=[StringProperty("article")])
summarize_step = PromptExecutionStep(
    llm=llm,
    prompt_template="""Extract from the following article the name of the animal, its danger level and the threats it's subject to. The article:\n\n {{article}}""",
    output_descriptors=[animal_descriptor],
)
summarize_step_name = "summarize_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        summarize_step_name: summarize_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_step),
        ControlFlowEdge(source_step=summarize_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "article", summarize_step, "article"),
    ],
)

conversation = flow.start_conversation(inputs={"article": article})
status = conversation.execute()
print(status.output_values)
# {'animal_object': {'animal_name': 'Sea turtles', 'danger_level': 'MEDIUM', 'threats': ['Poaching', 'Habitat loss', 'Pollution']}}



# %%[markdown]
## Use structured generation with Agents in flows

# %%
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.steps import AgentExecutionStep, StartStep

start_step = StartStep(input_descriptors=[])
agent = Agent(
    llm=llm,
    custom_instruction="""Extract from the article given by the user the name of the animal, its danger level and the threats it's subject to.""",
    initial_message=None,
    caller_input_mode=CallerInputMode.ALWAYS,
    output_descriptors=[animal_output, danger_level_output, threats_output],
)

summarize_agent_step = AgentExecutionStep(agent=agent)
summarize_step_name = "summarize_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        summarize_step_name: summarize_agent_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_agent_step),
        ControlFlowEdge(source_step=summarize_agent_step, destination_step=None),
    ],
    data_flow_edges=[],
)

conversation = flow.start_conversation()
conversation.append_user_message("Here is the article: " + article)
status = conversation.execute()
print(status.output_values)
# {'animal_name': 'Sea turtles', 'danger_level': 'HIGH', 'threats': ['poaching', 'habitat loss', 'pollution']}


# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter
serialized_assistant = AgentSpecExporter().to_json(flow)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader
new_assistant = AgentSpecLoader().load_json(serialized_assistant)
