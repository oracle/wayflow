# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors

import os

# .. define-model-location:
os.environ["MY_LLM_HOST_PORT"] = "model.example.com"
# .. end-define-model-location

# .. start:
import os

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.models.llmmodelfactory import LlmModelFactory
from wayflowcore.property import StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep
from wayflowcore.tools.servertools import ServerTool

model_config = {
    "model_type": "vllm",
    "host_port": os.environ["MY_LLM_HOST_PORT"],
    "model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct",
}
llm = LlmModelFactory.from_config(model_config)

start_step = StartStep(input_descriptors=[StringProperty("topic")])
poem_generation_step = PromptExecutionStep(
    llm=llm, prompt_template="Write a 12 lines poem about the following topic: {{ topic }}"
)
poem_generation_flow = Flow(
    begin_step=start_step,
    steps={"start_step": start_step, "poem_generation_step": poem_generation_step},
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=poem_generation_step),
        ControlFlowEdge(source_step=poem_generation_step, destination_step=None),
    ],
    data_flow_edges=[DataFlowEdge(start_step, "topic", poem_generation_step, "topic")],
)

poem_generation_tool = ServerTool.from_flow(
    flow=poem_generation_flow,
    flow_name="generate_poem",
    flow_description="A simple flow to generate a 12 lines poem based on a topic.",
    # The below line is needed to specify which output of the flow should be used as the output of
    # the tool
    flow_output=PromptExecutionStep.OUTPUT,
)

# .. end-start
