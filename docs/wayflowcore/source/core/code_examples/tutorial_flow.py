# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors

# docs-title: Tutorial - Build a Fixed-Flow Assistant

# .. start-##_Imports
from textwrap import dedent

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow

# Create an LLM model to use later in the tutorial.
from wayflowcore.models import VllmModel
from wayflowcore.steps import (
    CompleteStep,
    InputMessageStep,
    OutputMessageStep,
    PromptExecutionStep,
    StartStep,
    ToolExecutionStep,
)
from wayflowcore.tools import tool
# .. end-##_Imports

# LLM model configuration

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# .. start-##_Define_value_names
# Names for the input parameters of the steps in the flow.
HR_QUERY = "user_query"
TOOL_QUERY = "query"
HR_DATA_CONTEXT = "hr_data_context"
QUERY_ANSWER = "answer"
USER_QUESTION = "user_question"
# .. end-##_Define_value_names
# .. start-##_Define_start_step
# A start step. This is where the flow starts.
start_step = StartStep(name="start_step", input_descriptors=None)
# .. end-##_Define_start_step
# .. start-##_Define_user_input_step
user_input_message_template = dedent(
    """
    I am an HR Assistant, designed to answer your questions about HR matters.
    What kinds of questions do you have today?
    Example of HR topics:
    - Employee benefits
    - Salaries
    - Career advancement
    """
)

user_input_step = InputMessageStep(
    name="user_input_step",
    message_template=user_input_message_template,
    output_mapping={InputMessageStep.USER_PROVIDED_INPUT: HR_QUERY},
)
# .. end-##_Define_user_input_step
# .. start-##_Define_HR_lookup_step
from wayflowcore.property import StringProperty

# A tool which will run a query on the HR system and return some data.
@tool(description_mode="only_docstring", output_descriptors=[StringProperty(HR_DATA_CONTEXT)])
def search_hr_database(query: str) -> str:
    """Function that searches the HR database for employee benefits.

    Parameters
    ----------
    query:
        a query string

    Returns
    -------
        a JSON response

    """
    # Returns mock data.
    return '{"John Smith": {"benefits": "Unlimited PTO", "salary": "$1,000"}, "Mary Jones": {"benefits": "25 days", "salary": "$10,000"}}'

# Step that runs the lookup of a query using the tool.
hr_lookup_step = ToolExecutionStep(
    name="hr_lookup_step",
    tool=search_hr_database,
)
# .. end-##_Define_HR_lookup_step
(llm,) = _update_globals(["llm_small"])  # docs-skiprow # type: ignore
# .. start-##_Define_llm_answer_step
# The template for the prompt to be used by the LLM. Notice the use of parameters
# such as, {{ user_question }}. The template is evaluated using the parameters that
# are passed into the PromptExecutionStep.
hrassistant_prompt_template = dedent(
    """
    You are a knowledgeable, factual, and helpful HR assistant that can answer simple \
    HR-related questions like salary and benefits.
    Your task:
        - Based on the HR data given below, answer the user's question
    Important:
        - Be helpful and concise in your messages
        - Do not tell the user any details not mentioned in the tool response, let's be factual.

    Here is the User question:
    - {{ user_question }}

    Here is the HR data:
    - {{ hr_data_context }}
    """
)

# Step that evaluates the prompt template and then passes the prompt to the LLM.
from wayflowcore.property import StringProperty

llm_answer_step = PromptExecutionStep(
    name="llm_answer_step",
    prompt_template=hrassistant_prompt_template,
    llm=llm,
    output_descriptors=[StringProperty(QUERY_ANSWER)],
)
# .. end-##_Define_llm_answer_step

# .. start-##_Define_user_output_step
# Step that outputs the answer to the user's query.
user_output_step = OutputMessageStep(
    name="user_output_step",
    message_template="My Assistant's Response: {{ answer }}",
)
# .. end-##_Define_user_output_step
# .. start-##_Define_flow_transitions
# Define the transitions between the steps.
control_flow_edges = [
    ControlFlowEdge(source_step=start_step, destination_step=user_input_step),
    ControlFlowEdge(source_step=user_input_step, destination_step=hr_lookup_step),
    ControlFlowEdge(source_step=hr_lookup_step, destination_step=llm_answer_step),
    ControlFlowEdge(source_step=llm_answer_step, destination_step=user_output_step),
    # Note: you can use a CompleteStep as the termination of the flow.
    ControlFlowEdge(source_step=user_output_step, destination_step=CompleteStep(name="final_step")),
]
# .. end-##_Define_flow_transitions
# .. start-##_Define_data_transitions
# Define the data flows between steps.
data_flow_edges = [
    DataFlowEdge(
        source_step=user_input_step,
        source_output=HR_QUERY,
        destination_step=hr_lookup_step,
        destination_input=TOOL_QUERY,
    ),
    DataFlowEdge(
        source_step=user_input_step,
        source_output=HR_QUERY,
        destination_step=llm_answer_step,
        destination_input=USER_QUESTION,
    ),
    DataFlowEdge(
        source_step=hr_lookup_step,
        source_output=HR_DATA_CONTEXT,
        destination_step=llm_answer_step,
        destination_input=HR_DATA_CONTEXT,
    ),
    DataFlowEdge(
        source_step=llm_answer_step,
        source_output=QUERY_ANSWER,
        destination_step=user_output_step,
        destination_input=QUERY_ANSWER,
    ),
]
# .. end-##_Define_data_transitions
# .. start-##_Create_assistant
# Create the flow passing in the steps, the name of the step to start with, the control_flow_edges and the data_flow_edges.
assistant = Flow(
    begin_step=start_step,
    control_flow_edges=control_flow_edges,
    data_flow_edges=data_flow_edges,
)
# .. end-##_Create_assistant
# .. start-##_Run_assistant
# Start a conversation.
conversation = assistant.start_conversation()

# Execute the assistant.
# This will print out the message to the user, then stop at the user input step.
conversation.execute()

# Ask a question of the assistant by appending a user message.
conversation.append_user_message("Does John Smith earn more that Mary Jones?")

# Execute the assistant again. Continues from the UserInputStep.
# As there are no other steps the flow will run to the end.
status = conversation.execute()

# "output_message" is the default key name for the output value
# of the OutputMessageStep.
from wayflowcore.executors.executionstatus import FinishedStatus
if isinstance(status, FinishedStatus):
    answer = status.output_values[OutputMessageStep.OUTPUT]
    print(answer)
else:
    print(
        f"Incorrect execution status, expected FinishedStatus, got {status.__class__.__name__}"
    )
# .. end-##_Run_assistant
# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)
# .. end-##_Export_config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {"search_hr_database": search_hr_database}

assistant = AgentSpecLoader(tool_registry=tool_registry).load_json(serialized_assistant)
# .. end-##_Load_Agent_Spec_config
