# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to Do Map and Reduce Operations in Flows
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
# python howto_mapstep.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Define the articles

# %%
articles = [
    "Sea turtles are ancient reptiles that have been around for over 100 million years. They play crucial roles in marine ecosystems, such as maintaining healthy seagrass beds and coral reefs. Unfortunately, they are under threat due to poaching, habitat loss, and pollution. Conservation efforts worldwide aim to protect nesting sites and reduce bycatch in fishing gear.",
    "Dolphins are highly intelligent marine mammals known for their playfulness and curiosity. They live in social groups called pods, which can consist of hundreds of individuals depending on the species. Dolphins communicate using a variety of clicks, whistles, and other sounds. They face threats from habitat loss, marine pollution, and bycatch in fishing operations.",
    "Manatees, often referred to as 'sea cows', are gentle aquatic giants found in shallow coastal areas and rivers. These herbivorous mammals spend most of their time eating, resting, and traveling. They are particularly known for their slow movement and inability to survive in cold waters. Manatee populations are vulnerable to boat collisions, loss of warm-water habitats, and environmental pollutants.",
]

# %%[markdown]
## Define the LLM

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## Create the Flow for the MapStep

# %%
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep

start_step = StartStep(name="start_step", input_descriptors=[StringProperty("article")])
summarize_step = PromptExecutionStep(
    name="summarize_step",
    llm=llm,
    prompt_template="""Summarize this article in 10 words:
 {{article}}""",
    output_mapping={PromptExecutionStep.OUTPUT: "summary"},
)
summarize_flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=summarize_step),
        ControlFlowEdge(source_step=summarize_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "article", summarize_step, "article"),
    ],
)

# %%[markdown]
## Create the MapStep

# %%
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import MapStep

map_step = MapStep(
    name="map_step",
    flow=summarize_flow,
    unpack_input={"article": "."},
    output_descriptors=[ListProperty(name="summary", item_type=StringProperty())],
    input_descriptors=[ListProperty(MapStep.ITERATED_INPUT, item_type=StringProperty())],
)

# %%[markdown]
## Create and execute the final Flow

# %%
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import StartStep

start_step = StartStep(
    name="start_step",
    input_descriptors=[ListProperty("articles", item_type=StringProperty())]
)
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=map_step),
        ControlFlowEdge(source_step=map_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "articles", map_step, MapStep.ITERATED_INPUT),
    ],
)
conversation = flow.start_conversation(inputs={"articles": articles})
status = conversation.execute()
print(status.output_values)

# %%[markdown]
## Iterate over a dictionary

# %%
from wayflowcore.property import DictProperty, ListProperty, StringProperty
from wayflowcore.steps import StartStep

articles_as_dict = {str(idx): article for idx, article in enumerate(articles)}

map_step = MapStep(
    name="map_step",
    flow=summarize_flow,
    unpack_input={"article": "._value"},
    input_descriptors=[DictProperty(MapStep.ITERATED_INPUT, value_type=StringProperty())],
    output_descriptors=[ListProperty(name="summary", item_type=StringProperty())],
)
start_step = StartStep(
    name="start_step",
    input_descriptors=[DictProperty("articles", value_type=StringProperty())]
)
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=map_step),
        ControlFlowEdge(source_step=map_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "articles", map_step, MapStep.ITERATED_INPUT),
    ],
)

conversation = flow.start_conversation(inputs={"articles": articles_as_dict})
status = conversation.execute()
print(status.output_values)

# %%[markdown]
## Parallel execution of map reduce operation

# %%
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import StartStep

start_step = StartStep(input_descriptors=[ListProperty("articles", item_type=StringProperty())])
map_step = MapStep(
    flow=summarize_flow,
    unpack_input={"article": "."},
    output_descriptors=[ListProperty(name="summary", item_type=StringProperty())],
    input_descriptors=[ListProperty(MapStep.ITERATED_INPUT, item_type=StringProperty())],
    parallel_execution=True,
)
map_step_name = "map_step"
flow = Flow(
    begin_step=start_step,
    steps={
        "start_step": start_step,
        map_step_name: map_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=map_step),
        ControlFlowEdge(source_step=map_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "articles", map_step, MapStep.ITERATED_INPUT),
    ],
)
conversation = flow.start_conversation(inputs={"articles": articles})
status = conversation.execute()
print(status.output_values)

# %%[markdown]
## Parallel execution of map reduce operation with ParallelMapStep

# %%
from wayflowcore.steps import ParallelMapStep

parallel_map_step = ParallelMapStep(
    flow=summarize_flow,
    unpack_input={"article": "."},
    output_descriptors=[ListProperty(name="summary", item_type=StringProperty())],
    input_descriptors=[ListProperty(MapStep.ITERATED_INPUT, item_type=StringProperty())],
)

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(flow)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

flow = AgentSpecLoader().load_json(serialized_flow)
