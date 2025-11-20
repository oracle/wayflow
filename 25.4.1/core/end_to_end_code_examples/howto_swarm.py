# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# %%[markdown]
# Code Example - Build a Swarm of Agents
# --------------------------------------

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
# python howto_swarm.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.




# %%[markdown]
## Imports for this guide

# %%
from typing import List
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    UserMessageRequestStatus,
)
from wayflowcore.agent import Agent
from wayflowcore.swarm import Swarm
from wayflowcore.tools import tool

# %%[markdown]
## Configure your LLM

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## Creating the tools

# %%
# tools for doctor
medical_knowledge = {
    "fever": ["flu", "infection"],
    "runny nose": ["cold", "allergies"],
    "fatigue": ["cold"],
    "cough": ["cold", "allergies"],
    "headache": ["tension headache", "migraine"],
}

@tool(description_mode="only_docstring")
def symptoms_checker(symptoms: List[str]) -> List[str]:
    """
    Checks symptoms against the medical knowledge base.
    Existing entries for "fever", "cough" and "headache".
    For other symptoms, you may need to refer to a specialist.

    Parameters:
    symptoms (list): List of symptoms reported by the patient.

    Returns:
    list: Possible conditions based on the symptoms.
    """
    possible_conditions = []
    for symptom in symptoms:
        if symptom in medical_knowledge:
            possible_conditions.extend(medical_knowledge[symptom])
    return list(set(possible_conditions))


medication_info = {
    "medicationA": "Available. For a mild cold, take two tablets every 6 hours for 3 days.",
    "medicationB": "Available.",
    "medicationC": "Not available.",
    "creamA": "Available. For exczema, apply the cream twice a day for the next 2 weeks.",
}


@tool(description_mode="only_docstring")
def get_medication_info(drug_name: str) -> str:
    """
    Provides availability and information about a medication.
    Known information for "medicationA", "medicationB", "medicationC" and "creamA".

    Parameters:
    drug_name (str): Name of the drug.

    Returns:
    str: Information about the drug.
    """
    return medication_info.get(drug_name, "Drug not found.")


dermatologist_knowledge = {
    "eczema": "Apply creamA twice a day for 2 weeks.",
    "acne": "Apply creamB once a day for 1 week.",
}


@tool(description_mode="only_docstring")
def knowledge_tool(condition: str) -> str:
    """
    Provides diagnosis and treatment information for skin conditions.
    Existing entries for "eczema" and "acne".

    Parameters:
    condition (str): Name of the skin condition.

    Returns:
    str: Diagnosis and treatment information.
    """
    return dermatologist_knowledge.get(condition, "Condition not found.")

# %%[markdown]
## Prompt for the General Practitioner Agent

# %%
general_practitioner_system_prompt = """
You are an helpful general practitioner LLM doctor responsible for handling patient consultations.
Your goal is to assess patients' symptoms, provide initial diagnoses, pescribe medication for
mild conditions or refer to other specialists as needed.

## When to Use Each Tool
- symptoms_checker: Use this to look up possible conditions based on symptoms reported by the patient.

## When to query other Agents
- Pharmacist: Every time you need to prescribe some medication, give the condition description and prescription to the Pharmacist.
- Dermatologist: If the patient has a skin condition, ask expert advice/diagnosis to the Dermatologist after the initial exchange.

# Specific instructions
## Initial exchange
When a patient first shares symptoms ask about for exactly 1 round of questions, consisting of asking about medical history and
simple questions (e.g. do they have known allergies, when did the symptoms started, did they already tried some treatment/medication, etc)).
Always ask for this one round of information to the user before prescribing medication / referring to other agents.

## Identifying condition
Use the symptoms checker to confirm the condition (for mild conditions only. For other conditions, refer to specialists).

## Mild conditions
* If the patient has a mild cold, prescribe medicationA.
    - Give the condition description and prescription to the Pharmacist.

## Skin conditions
* If the patient has a skin condition, ask for expert advice/diagnosis from the Dermatologist.
Here, you don't need to ask for the user confirmation. Directly call the Dermatologist
    - Provide the patient's symptoms/initial hypothesis to the Dermatologist and ask for a diagnosis.
    - The Dermatologist may query the Pharmacist to confirm the availability of the prescribed medication.
    - Once the treatment is confirmed, pass on the prescription to the patient and ask them to follow the instructions.
""".strip()

# %%[markdown]
## Define the General Practitioner Agent

# %%
general_practitioner = Agent(
    name="GeneralPractitioner",
    description="General Practitioner. Primary point of contact for patients, handles general medical inquiries, provides initial diagnoses, and manages referrals.",
    llm=llm,
    tools=[symptoms_checker],
    custom_instruction=general_practitioner_system_prompt,
)

# %%[markdown]
## Prompt for the Pharmacist Agent

# %%
pharmacist_system_prompt = """
You are an helpful Pharmacist LLM Agent responsible for giving information about medication.
Your goal is to answer queries from the General Practitioner Doctor about medication information
and availabilities.

## When to Use Each Tool
- get_medication_info: Use this to look up availability and information about a specific medication.
""".strip()

# %%[markdown]
## Define the Pharmacist Agent

# %%
pharmacist = Agent(
    name="Pharmacist",
    description="Pharmacist. Gives availability and information about specific medication.",
    llm=llm,
    tools=[get_medication_info],
    custom_instruction=pharmacist_system_prompt,
)

# %%[markdown]
## Prompt for the Dermatologist Agent

# %%
dermatologist_system_prompt = """
You are an helpful Dermatologist LLM Agent responsible for diagnosing and treating skin conditions.
Your goal is to assess patients' symptoms, provide accurate diagnoses, and prescribe effective treatments.

## When to Use Each Tool
- knowledge_tool: Use this to look up diagnosis and treatment information for specific skin conditions.

## When to query other Agents
- Pharmacist: Every time you need to prescribe some medication, give the condition description and prescription to the Pharmacist.

# Specific instructions
## Initial exchange
When a patient's symptoms are referred to you by the General Practitioner, review the symptoms and use the knowledge tool to confirm the diagnosis.
## Prescription
Prescribe the recommended treatment for the diagnosed condition and query the Pharmacist to confirm the availability of the prescribed medication.

When answering back to the General Practitioner, describe your diagnosis and the prescription.
Tell the General Practitioner that you already checked with the pharmacist for availability.
""".strip()

# %%[markdown]
## Define the Dermatologist Agent

# %%
dermatologist = Agent(
    name="Dermatologist",
    description="Dermatologist. Diagnoses and treats skin conditions.",
    llm=llm,
    tools=[knowledge_tool],
    custom_instruction=dermatologist_system_prompt,
)

# %%[markdown]
## Creating the Swarm

# %%
assistant = Swarm(
    name="Swarm",
    first_agent=general_practitioner,
    relationships=[
        (general_practitioner, pharmacist),
        (general_practitioner, dermatologist),
        (dermatologist, pharmacist),
    ],
)


# %%[markdown]
## Running the Swarm

# %%
# With a linear conversation
conversation = assistant.start_conversation()

conversation.append_user_message(
    "My skin has been itching for some about a week, can you help me understand what is going on?"
)
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")

# then continue the conversation
# %%
# Or with an execution loop
def run_swarm_in_command_line(assistant: Swarm):
    inputs = {}
    conversation = assistant.start_conversation(inputs)

    while True:
        status = assistant.execute(conversation)
        if isinstance(status, FinishedStatus):
            break
        assistant_reply = conversation.get_last_message()
        if assistant_reply is not None:
            print("\nAssistant >>>", assistant_reply.content)
        user_input = input("\nUser >>> ")
        conversation.append_user_message(user_input)


# %%[markdown]
## Running with the execution loop

# %%
# run_swarm_in_command_line(assistant)
# ^ uncomment and execute

# %%[markdown]
## Enabling handoff in the Swarm

# %%
assistant = Swarm(
    name="Swarm",
    first_agent=general_practitioner,
    relationships=[
        (general_practitioner, pharmacist),
        (general_practitioner, dermatologist),
        (dermatologist, pharmacist),
    ],
    handoff=True,  # <-- Add this
)

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {
    "symptoms_checker": symptoms_checker,
    "get_medication_info": get_medication_info,
    "knowledge_tool": knowledge_tool,
}
assistant: Swarm = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_json(serialized_assistant)
