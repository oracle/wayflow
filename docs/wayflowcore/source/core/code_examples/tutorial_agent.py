# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Tutorial - Build a Conversational Assistant with Agents

from wayflowcore.models import VllmModel # docs-skiprow
from wayflowcore.serialization import serialize # docs-skiprow

# .. start-##_Imports_for_this_guide
from wayflowcore.agent import Agent
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    UserMessageRequestStatus,
)
from wayflowcore.tools import tool
# .. end-##_Imports_for_this_guide
# .. start-##_Configure_your_LLM
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA70B_MODEL_ID",
    host_port="LLAMA70B_API_URL",
)
# .. end-##_Configure_your_LLM
# .. start-##_Defining_a_tool_for_the_agent
@tool(description_mode="only_docstring")
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
    return '{"John Smith": {"benefits": "Unlimited PTO", "salary": "$1,000"}, "Mary Jones": {"benefits": "25 days", "salary": "$10,000"}}'

# .. end-##_Defining_a_tool_for_the_agent
# .. start-##_Specifying_the_agent_instructions
HRASSISTANT_GENERATION_INSTRUCTIONS = """
You are a knowledgeable, factual, and helpful HR assistant that can answer simple \
HR-related questions like salary and benefits.
You are given a tool to look up the HR database.
Your task:
    - Ask the user if they need assistance
    - Use the provided tool below to retrieve HR data
    - Based on the data you retrieved, answer the user's question
Important:
    - Be helpful and concise in your messages
    - Do not tell the user any details not mentioned in the tool response, let's be factual.
""".strip()
# .. end-##_Specifying_the_agent_instructions
llm: VllmModel  # docs-skiprow
(llm,) = _update_globals(["llm_small"])  # docs-skiprow # type: ignore
# .. start-##_Creating_the_agent
assistant = Agent(
    custom_instruction=HRASSISTANT_GENERATION_INSTRUCTIONS,
    tools=[search_hr_database],  # this is a decorated python function (Server tool in this example)
    llm=llm,  # the LLM object we created above
)
# .. end-##_Creating_the_agent
serialized_assistant = AgentSpecExporter().to_json(assistant) # docs-skiprow
new_assistant: Agent = AgentSpecLoader(tool_registry={"search_hr_database": search_hr_database}).load_json(serialized_assistant) # docs-skiprow
# assert serialize(assistant) == serialize(new_assistant) # Manually verified # docs-skiprow
# .. start-##_Running_the_agent
# With a linear conversation
conversation = assistant.start_conversation()

conversation.append_user_message("What are John Smith's benefits?")
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")

# then continue the conversation

# %%
# Or with an execution loop
def run_agent_in_command_line(assistant: Agent):
    inputs = {}
    conversation = assistant.start_conversation(inputs)

    while True:
        status = conversation.execute()
        if isinstance(status, FinishedStatus):
            break
        assistant_reply = conversation.get_last_message()
        if assistant_reply is not None:
            print("\nAssistant >>>", assistant_reply.content)
        user_input = input("\nUser >>> ")
        conversation.append_user_message(user_input)

# .. end-##_Running_the_agent
# .. start-##_Running_with_the_execution_loop
# run_agent_in_command_line(assistant)
# ^ uncomment and execute
# .. end-##_Running_with_the_execution_loop
# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)
# .. end-##_Export_config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {"search_hr_database": search_hr_database}
assistant: Agent = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_json(serialized_assistant)
# .. end-##_Load_Agent_Spec_config
