# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors

# docs-title: Code Example - How to Specify the Generation Configuration when Using LLMs

# .. start-##_Imports
from wayflowcore.agent import Agent
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
# .. end-##_Imports

# .. start-##_Define_the_llm_generation_configuration
generation_config = LlmGenerationConfig(
    max_tokens=512,
    temperature=1.0,
    top_p=1.0,
    stop=["exit", "end"],
    frequency_penalty=0,
    extra_args={"seed": 1},
)
# .. end-##_Define_the_llm_generation_configuration

# .. start-##_Define_the_vLLM
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
    generation_config=generation_config,
)
# NOTE: host_port should be a string with the IP address/domain name and the port. An example string: "192.168.1.1:8000"
# NOTE: model_id usually indicates the HuggingFace model id,
# e.g. meta-llama/Llama-3.1-8B-Instruct from https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct
# .. end-##_Define_the_vLLM
(llm,) = _update_globals(["llm_small"])  # docs-skiprow
# .. start-##_Build_the_agent_and_run_it
agent = Agent(llm=llm)
conversation = agent.start_conversation()
conversation.append_user_message("What is the capital of Switzerland?")
conversation.execute()
print(conversation.get_last_message())
# .. end-##_Build_the_agent_and_run_it


from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

# .. start-##_Import_what_is_needed_to_build_a_flow
from wayflowcore.flow import Flow
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.property import StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep
# .. end-##_Import_what_is_needed_to_build_a_flow

# .. start-##_Build_the_flow_using_custom_generation_parameters
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
# .. end-##_Build_the_flow_using_custom_generation_parameters

# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_yaml(flow)
# .. end-##_Export_config_to_Agent_Spec

# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

assistant = AgentSpecLoader().load_yaml(serialized_assistant)
# .. end-##_Load_Agent_Spec_config

# .. start-##_Build_the_generation_configuration_from_dictionary
config_dict = {
    "max_tokens": 512,
    "temperature": 0.9,
}

config = LlmGenerationConfig.from_dict(config_dict)
# .. end-##_Build_the_generation_configuration_from_dictionary

# .. start-##_Export_a_generation_configuration_to_dictionary

config = LlmGenerationConfig(max_tokens=1024, temperature=0.8, top_p=0.6)
config_dict = config.to_dict()
# .. end-##_Export_a_generation_configuration_to_dictionary
