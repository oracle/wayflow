# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# %%[markdown]
# Code Example - How to Specify the Generation Configuration when Using LLMs
# --------------------------------------------------------------------------

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
# python example_generationconfig.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.




# %%[markdown]
## Imports

# %%
from wayflowcore.agent import Agent
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig


# %%[markdown]
## Define the llm generation configuration

# %%
generation_config = LlmGenerationConfig(
    max_tokens=512,
    temperature=1.0,
    top_p=1.0,
    stop=["exit", "end"],
    frequency_penalty=0,
    extra_args={"seed": 1},
)


# %%[markdown]
## Define the vLLM

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
    generation_config=generation_config,
)
# NOTE: host_port should be a string with the IP address/domain name and the port. An example string: "192.168.1.1:8000"
# NOTE: model_id usually indicates the HuggingFace model id,
# e.g. meta-llama/Llama-3.1-8B-Instruct from https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct

# %%[markdown]
## Build the agent and run it

# %%
agent = Agent(llm=llm)
conversation = agent.start_conversation()
conversation.append_user_message("What is the capital of Switzerland?")
conversation.execute()
print(conversation.get_last_message())


from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge


# %%[markdown]
## Import what is needed to build a flow

# %%
from wayflowcore.flow import Flow
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.property import StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep


# %%[markdown]
## Build the flow using custom generation parameters

# %%
start_step = StartStep(name="start_step", input_descriptors=[StringProperty("user_question")])
prompt_step = PromptExecutionStep(
    name="PromptExecution",
    prompt_template="{{user_question}}",
    llm=llm,
    generation_config=LlmGenerationConfig(temperature=0.8),
)
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=prompt_step),
        ControlFlowEdge(source_step=prompt_step, destination_step=None),
    ],
    data_flow_edges=[DataFlowEdge(start_step, "user_question", prompt_step, "user_question")],
)
conversation = flow.start_conversation(
    inputs={"user_question": "What is the capital of Switzerland?"}
)
conversation.execute()


# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_yaml(flow)


# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

assistant = AgentSpecLoader().load_yaml(serialized_assistant)


# %%[markdown]
## Build the generation configuration from dictionary

# %%
config_dict = {
    "max_tokens": 512,
    "temperature": 0.9,
}

config = LlmGenerationConfig.from_dict(config_dict)


# %%[markdown]
## Export a generation configuration to dictionary

# %%

config = LlmGenerationConfig(max_tokens=1024, temperature=0.8, top_p=0.6)
config_dict = config.to_dict()
