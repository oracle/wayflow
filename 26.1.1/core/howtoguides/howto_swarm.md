<a id="top-howtoswarm"></a>

# How to Build a Swarm of Agents![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Swarm how-to script](../end_to_end_code_examples/howto_swarm.py)

#### Prerequisites
This guide assumes familiarity with [Agents](../tutorials/basic_agent.md).

The Swarm pattern is a type of agentic pattern that takes inspiration from [Swarm intelligence](https://en.wikipedia.org/wiki/Swarm_intelligence),
a phenomenon commonly seen in ant colonies, bee hives, and bird flocks, where coordinated behavior emerges from many simple actors rather than a central controller.
In this agentic pattern, each agent is assigned a specific responsibility and can delegate tasks to other specialized agents to improve overall performance.

**When to use the Swarm pattern?**

Compared to using a [hierarchical multi-agent pattern](howto_multiagent.md), the communication in [Swarm](../api/agent.md#swarm) pattern reduces the number of LLM calls
as showcased in the diagram below.

![How the Swarm pattern compares to hierarchical multi-agent pattern](core/_static/howto/hierarchical_vs_swarm.svg)

In the **hierarchical pattern**, a route User → Agent K → User will require:

1. All intermediate agent to call the correct sub-agent to go down to the Agent K.
2. The Agent K to generate its answer.
3. All intermediate agents to relay the answer back to the user.

In the **swarm pattern**, a route User → Agent K → User will require:

1. The first agent to call or handoff the conversation the Agent K (provided that the developer allows the connection between the two agents).
2. The Agent K to generate its answer.
3. The first agent to relay the answer (only when NOT using handoff; with handoff the Agent K **replaces** the first agent and is thus directly communicating with the human user)

---

This guide presents an example of a simple Swarm of agents applied to a medical use case.

![Example of a Swarm agent pattern for medical application](core/_static/howto/swarm_example.svg)

This guide will walk you through the following steps:

1. Defining agents equipped with tools
2. Assembling a Swarm using the defined agents
3. Executing the Swarm of agents

It also covers how to enable `handoff` when building the `Swarm`.

#### WARNING
The `Swarm` agentic pattern is currently in beta (e.g., it cannot yet be used in a `Flow`).
Its API and behavior are not guaranteed to be stable and may evolve in future versions.

For more information about `Swarm` and other agentic patterns in WayFlow, contact the AgentSpec development team.

## Basic implementation

First import what is needed for this guide:

```python
from typing import List
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    UserMessageRequestStatus,
)
from wayflowcore.agent import Agent
from wayflowcore.swarm import Swarm
from wayflowcore.tools import tool
```

To follow this guide, you will need access to a large language model (LLM).
WayFlow supports several LLM API providers.
Select an LLM from the options below:




OCI GenAI

```python
from wayflowcore.models import OCIGenAIModel, OCIClientConfigWithApiKey

llm = OCIGenAIModel(
    model_id="provider.model-id",
    compartment_id="compartment-id",
    client_config=OCIClientConfigWithApiKey(
        service_endpoint="https://url-to-service-endpoint.com",
    ),
)
```

vLLM

```python
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)
```

Ollama

```python
from wayflowcore.models import OllamaModel

llm = OllamaModel(
    model_id="model-id",
)
```

In this section, you will define the agents that will later be used to build the Swarm of agents.

### Creating the tools

The Swarm in this example consists of three [Agents](../api/agent.md#agent), each equipped with a single [Tool](../api/tools.md#tooldecorator).

```python
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
```

**API Reference:** [tool](../api/tools.md#tooldecorator)

### Defining the agents

The three agents need to be given the following elements:

* A name
* A description
* A system prompt (the instruction to give to the LLM to solve a given task)
* A LLM
* Some optional tools

#### General Practitioner Agent

The first agent the user interacts with is the General Practitioner Agent.

This agent is equipped with the symptoms checker tool, and can interact with the **Pharmacist Agent**
as well as the **Dermatologist Agent**.

<details>
<summary>Details</summary>

```python
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
```

</details>

The General Practitioner Agent can be configured as follows:

```python
general_practitioner = Agent(
    name="GeneralPractitioner",
    description="General Practitioner. Primary point of contact for patients, handles general medical inquiries, provides initial diagnoses, and manages referrals.",
    llm=llm,
    tools=[symptoms_checker],
    custom_instruction=general_practitioner_system_prompt,
)
```

#### Pharmacist Agent

The Pharmacist Agent is equipped with the tool to obtain medication information.
This agent cannot initiate a discussion with the other agents in the Swarm.

<details>
<summary>Details</summary>

```python
pharmacist_system_prompt = """
You are an helpful Pharmacist LLM Agent responsible for giving information about medication.
Your goal is to answer queries from the General Practitioner Doctor about medication information
and availabilities.

## When to Use Each Tool
- get_medication_info: Use this to look up availability and information about a specific medication.
""".strip()
```

</details>

```python
pharmacist = Agent(
    name="Pharmacist",
    description="Pharmacist. Gives availability and information about specific medication.",
    llm=llm,
    tools=[get_medication_info],
    custom_instruction=pharmacist_system_prompt,
)
```

#### Dermatologist Agent

The final agent in the Swarm is the Dermatologist agent which is equipped with a tool to query a skin condition knowledge base.
This agent can initiate a discussion with the **Pharmacist Agent**.

<details>
<summary>Details</summary>

```python
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
```

</details>

```python
dermatologist = Agent(
    name="Dermatologist",
    description="Dermatologist. Diagnoses and treats skin conditions.",
    llm=llm,
    tools=[knowledge_tool],
    custom_instruction=dermatologist_system_prompt,
)
```

### Creating the Swarm
```python
assistant = Swarm(
    name="Swarm",
    first_agent=general_practitioner,
    relationships=[
        (general_practitioner, pharmacist),
        (general_practitioner, dermatologist),
        (dermatologist, pharmacist),
    ],
)
```

**API Reference:** [Swarm](../api/agent.md#swarm)

The Swarm has two main parameters:

- The `first_agent` — the initial agent the user interacts with (in this example, the General Practitioner Agent).
- A list of relationships between agents.

The `relationships` parameter defines the communication edges between agents.
Each relationship is expressed as a tuple of Caller Agent → Recipient Agent, indicating that the caller is permitted to delegate work to the recipient.

These relationships apply to both types of delegation supported by the Swarm:

- They determine which agents may contact another agent using the send-message tool.
- They also define which pairs of agents are eligible for a handoff, meaning the full user–agent conversation can be transferred from the caller to the recipient.

In this example, the General Practitioner Doctor Agent can delegate to both the Pharmacist and the Dermatologist.
The Dermatologist can also delegate with the Pharmacist.

When invoked, each agent can either respond to its caller (a human user or another agent) or choose to initiate a discussion with
another agent if they are given the capability to do so.

### Executing the Swarm

Now that the Swarm is defined, you can execute it using an example user query.

```python
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
```

We recommend to implement an [execution loop](../misc/reference_sheet.md#refsheet-executionloop) to execute the `Swarm`, such as the following:

```python
# run_swarm_in_command_line(assistant)
# ^ uncomment and execute
```

## Advanced usage

### Different handoff modes in Swarm

One of the key benefits of Swarm is its handoff mechanism. When enabled, an agent can hand off its conversation — that is, transfer the entire message history between it and the human user — to another agent within the Swarm.

The handoff mechanism helps reduce response latency.
Normally, when agents talk to each other, the “distance” between the human user and the final answering agent increases, because messages must travel through multiple agents.
Handoff avoids this by directly transferring the conversation to another agent: while the agent changes, the user’s distance to the active agent stays the same.

Swarm provides three handoff modes:

- `HandoffMode.NEVER`
  Disables the handoff mechanism. Agents can still communicate with each other, but cannot transfer the entire user conversation to another agent.
  In this mode, the  `first_agent` is the only agent that can directly interact with the human user.
- `HandoffMode.OPTIONAL` (default)
  Agents may perform a handoff when it is beneficial.
  A handoff is performed only when the receiving agent is able to take over and independently address the user’s request.
  This strikes a balance between multi-agent collaboration and minimizing overhead.
- `HandoffMode.ALWAYS`
  Agents must use the handoff mechanism whenever delegating work to another agent. Direct *send-message* tools between agents are disabled in this mode.
  This mode is useful when most user requests are best handled by a single expert agent rather than through multi-agent collaboration.

To set the handoff mode, simply use [HandoffMode](../api/agent.md#handoffmode) and select the desired mode.

```python
from wayflowcore.swarm import HandoffMode
assistant = Swarm(
    name="Swarm",
    first_agent=general_practitioner,
    relationships=[
        (general_practitioner, pharmacist),
        (general_practitioner, dermatologist),
        (dermatologist, pharmacist),
    ],
    handoff=HandoffMode.ALWAYS,  # <-- Choose the handoff mode of your choice
)
```

**API Reference:** [HandoffMode](../api/agent.md#handoffmode)

### Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
    "component_type": "Swarm",
    "id": "f29e47fe-9306-45fe-ba60-31cce44330aa",
    "name": "Swarm",
    "description": null,
    "metadata": {
        "__metadata_info__": {}
    },
    "inputs": [],
    "outputs": [],
    "first_agent": {
        "$component_ref": "4e81121e-2e42-4a92-8454-05afdefa2068"
    },
    "relationships": [
        [
            {
                "$component_ref": "4e81121e-2e42-4a92-8454-05afdefa2068"
            },
            {
                "$component_ref": "6659c7b4-2937-43cd-9e22-e098b7d78a85"
            }
        ],
        [
            {
                "$component_ref": "4e81121e-2e42-4a92-8454-05afdefa2068"
            },
            {
                "$component_ref": "9c6541f3-b183-4239-aec4-d83b66b9486d"
            }
        ],
        [
            {
                "$component_ref": "9c6541f3-b183-4239-aec4-d83b66b9486d"
            },
            {
                "$component_ref": "6659c7b4-2937-43cd-9e22-e098b7d78a85"
            }
        ]
    ],
    "handoff": true,
    "$referenced_components": {
        "4e81121e-2e42-4a92-8454-05afdefa2068": {
            "component_type": "Agent",
            "id": "4e81121e-2e42-4a92-8454-05afdefa2068",
            "name": "GeneralPractitioner",
            "description": "General Practitioner. Primary point of contact for patients, handles general medical inquiries, provides initial diagnoses, and manages referrals.",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [],
            "outputs": [],
            "llm_config": {
                "$component_ref": "157ab376-3f2e-42ee-beed-e8e1f81c9a34"
            },
            "system_prompt": "You are an helpful general practitioner LLM doctor responsible for handling patient consultations.\nYour goal is to assess patients' symptoms, provide initial diagnoses, pescribe medication for\nmild conditions or refer to other specialists as needed.\n\n## When to Use Each Tool\n- symptoms_checker: Use this to look up possible conditions based on symptoms reported by the patient.\n\n## When to query other Agents\n- Pharmacist: Every time you need to prescribe some medication, give the condition description and prescription to the Pharmacist.\n- Dermatologist: If the patient has a skin condition, ask expert advice/diagnosis to the Dermatologist after the initial exchange.\n\n# Specific instructions\n## Initial exchange\nWhen a patient first shares symptoms ask about for exactly 1 round of questions, consisting of asking about medical history and\nsimple questions (e.g. do they have known allergies, when did the symptoms started, did they already tried some treatment/medication, etc)).\nAlways ask for this one round of information to the user before prescribing medication / referring to other agents.\n\n## Identifying condition\nUse the symptoms checker to confirm the condition (for mild conditions only. For other conditions, refer to specialists).\n\n## Mild conditions\n* If the patient has a mild cold, prescribe medicationA.\n    - Give the condition description and prescription to the Pharmacist.\n\n## Skin conditions\n* If the patient has a skin condition, ask for expert advice/diagnosis from the Dermatologist.\nHere, you don't need to ask for the user confirmation. Directly call the Dermatologist\n    - Provide the patient's symptoms/initial hypothesis to the Dermatologist and ask for a diagnosis.\n    - The Dermatologist may query the Pharmacist to confirm the availability of the prescribed medication.\n    - Once the treatment is confirmed, pass on the prescription to the patient and ask them to follow the instructions.",
            "tools": [
                {
                    "component_type": "ServerTool",
                    "id": "86b18dcf-139c-442f-93cd-1743a2afe581",
                    "name": "symptoms_checker",
                    "description": "Checks symptoms against the medical knowledge base.\nExisting entries for \"fever\", \"cough\" and \"headache\".\nFor other symptoms, you may need to refer to a specialist.\n\nParameters:\nsymptoms (list): List of symptoms reported by the patient.\n\nReturns:\nlist: Possible conditions based on the symptoms.",
                    "metadata": {
                        "__metadata_info__": {}
                    },
                    "inputs": [
                        {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "title": "symptoms"
                        }
                    ],
                    "outputs": [
                        {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "title": "tool_output"
                        }
                    ]
                }
            ]
        },
        "157ab376-3f2e-42ee-beed-e8e1f81c9a34": {
            "component_type": "VllmConfig",
            "id": "157ab376-3f2e-42ee-beed-e8e1f81c9a34",
            "name": "llm_bc782ae9__auto",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "default_generation_parameters": null,
            "url": "LLAMA_API_URL",
            "model_id": "LLAMA_MODEL_ID"
        },
        "6659c7b4-2937-43cd-9e22-e098b7d78a85": {
            "component_type": "Agent",
            "id": "6659c7b4-2937-43cd-9e22-e098b7d78a85",
            "name": "Pharmacist",
            "description": "Pharmacist. Gives availability and information about specific medication.",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [],
            "outputs": [],
            "llm_config": {
                "$component_ref": "157ab376-3f2e-42ee-beed-e8e1f81c9a34"
            },
            "system_prompt": "You are an helpful Pharmacist LLM Agent responsible for giving information about medication.\nYour goal is to answer queries from the General Practitioner Doctor about medication information\nand availabilities.\n\n## When to Use Each Tool\n- get_medication_info: Use this to look up availability and information about a specific medication.",
            "tools": [
                {
                    "component_type": "ServerTool",
                    "id": "741edc7c-701b-4073-891f-44f7028ffe79",
                    "name": "get_medication_info",
                    "description": "Provides availability and information about a medication.\nKnown information for \"medicationA\", \"medicationB\", \"medicationC\" and \"creamA\".\n\nParameters:\ndrug_name (str): Name of the drug.\n\nReturns:\nstr: Information about the drug.",
                    "metadata": {
                        "__metadata_info__": {}
                    },
                    "inputs": [
                        {
                            "type": "string",
                            "title": "drug_name"
                        }
                    ],
                    "outputs": [
                        {
                            "type": "string",
                            "title": "tool_output"
                        }
                    ]
                }
            ]
        },
        "9c6541f3-b183-4239-aec4-d83b66b9486d": {
            "component_type": "Agent",
            "id": "9c6541f3-b183-4239-aec4-d83b66b9486d",
            "name": "Dermatologist",
            "description": "Dermatologist. Diagnoses and treats skin conditions.",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [],
            "outputs": [],
            "llm_config": {
                "$component_ref": "157ab376-3f2e-42ee-beed-e8e1f81c9a34"
            },
            "system_prompt": "You are an helpful Dermatologist LLM Agent responsible for diagnosing and treating skin conditions.\nYour goal is to assess patients' symptoms, provide accurate diagnoses, and prescribe effective treatments.\n\n## When to Use Each Tool\n- knowledge_tool: Use this to look up diagnosis and treatment information for specific skin conditions.\n\n## When to query other Agents\n- Pharmacist: Every time you need to prescribe some medication, give the condition description and prescription to the Pharmacist.\n\n# Specific instructions\n## Initial exchange\nWhen a patient's symptoms are referred to you by the General Practitioner, review the symptoms and use the knowledge tool to confirm the diagnosis.\n## Prescription\nPrescribe the recommended treatment for the diagnosed condition and query the Pharmacist to confirm the availability of the prescribed medication.\n\nWhen answering back to the General Practitioner, describe your diagnosis and the prescription.\nTell the General Practitioner that you already checked with the pharmacist for availability.",
            "tools": [
                {
                    "component_type": "ServerTool",
                    "id": "ea29ed11-4141-4d48-8118-9bc4bff1df49",
                    "name": "knowledge_tool",
                    "description": "Provides diagnosis and treatment information for skin conditions.\nExisting entries for \"eczema\" and \"acne\".\n\nParameters:\ncondition (str): Name of the skin condition.\n\nReturns:\nstr: Diagnosis and treatment information.",
                    "metadata": {
                        "__metadata_info__": {}
                    },
                    "inputs": [
                        {
                            "type": "string",
                            "title": "condition"
                        }
                    ],
                    "outputs": [
                        {
                            "type": "string",
                            "title": "tool_output"
                        }
                    ]
                }
            ]
        }
    },
    "agentspec_version": "25.4.2"
}
```

YAML

```yaml
component_type: Swarm
id: 5a35bc2b-25bf-47e6-ad93-86528be5a785
name: Swarm
description: null
metadata:
  __metadata_info__: {}
inputs: []
outputs: []
first_agent:
  $component_ref: 1e1735d7-ec23-4659-9046-b984881163a1
relationships:
- - $component_ref: 1e1735d7-ec23-4659-9046-b984881163a1
  - $component_ref: c78b8336-2d92-4781-bd56-c28a476c839e
- - $component_ref: 1e1735d7-ec23-4659-9046-b984881163a1
  - $component_ref: efddcffd-6d3e-41ad-a071-89cf833fc8f8
- - $component_ref: efddcffd-6d3e-41ad-a071-89cf833fc8f8
  - $component_ref: c78b8336-2d92-4781-bd56-c28a476c839e
handoff: true
$referenced_components:
  1e1735d7-ec23-4659-9046-b984881163a1:
    component_type: Agent
    id: 1e1735d7-ec23-4659-9046-b984881163a1
    name: GeneralPractitioner
    description: General Practitioner. Primary point of contact for patients, handles
      general medical inquiries, provides initial diagnoses, and manages referrals.
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs: []
    llm_config:
      $component_ref: 28ae5559-8a7d-46bd-b1ff-82680db4f61f
    system_prompt: "You are an helpful general practitioner LLM doctor responsible\
      \ for handling patient consultations.\nYour goal is to assess patients' symptoms,\
      \ provide initial diagnoses, pescribe medication for\nmild conditions or refer\
      \ to other specialists as needed.\n\n## When to Use Each Tool\n- symptoms_checker:\
      \ Use this to look up possible conditions based on symptoms reported by the\
      \ patient.\n\n## When to query other Agents\n- Pharmacist: Every time you need\
      \ to prescribe some medication, give the condition description and prescription\
      \ to the Pharmacist.\n- Dermatologist: If the patient has a skin condition,\
      \ ask expert advice/diagnosis to the Dermatologist after the initial exchange.\n\
      \n# Specific instructions\n## Initial exchange\nWhen a patient first shares\
      \ symptoms ask about for exactly 1 round of questions, consisting of asking\
      \ about medical history and\nsimple questions (e.g. do they have known allergies,\
      \ when did the symptoms started, did they already tried some treatment/medication,\
      \ etc)).\nAlways ask for this one round of information to the user before prescribing\
      \ medication / referring to other agents.\n\n## Identifying condition\nUse the\
      \ symptoms checker to confirm the condition (for mild conditions only. For other\
      \ conditions, refer to specialists).\n\n## Mild conditions\n* If the patient\
      \ has a mild cold, prescribe medicationA.\n    - Give the condition description\
      \ and prescription to the Pharmacist.\n\n## Skin conditions\n* If the patient\
      \ has a skin condition, ask for expert advice/diagnosis from the Dermatologist.\n\
      Here, you don't need to ask for the user confirmation. Directly call the Dermatologist\n\
      \    - Provide the patient's symptoms/initial hypothesis to the Dermatologist\
      \ and ask for a diagnosis.\n    - The Dermatologist may query the Pharmacist\
      \ to confirm the availability of the prescribed medication.\n    - Once the\
      \ treatment is confirmed, pass on the prescription to the patient and ask them\
      \ to follow the instructions."
    tools:
    - component_type: ServerTool
      id: 384148cc-fc4c-438b-9ad3-f733f1912dd6
      name: symptoms_checker
      description: 'Checks symptoms against the medical knowledge base.

        Existing entries for "fever", "cough" and "headache".

        For other symptoms, you may need to refer to a specialist.


        Parameters:

        symptoms (list): List of symptoms reported by the patient.


        Returns:

        list: Possible conditions based on the symptoms.'
      metadata:
        __metadata_info__: {}
      inputs:
      - type: array
        items:
          type: string
        title: symptoms
      outputs:
      - type: array
        items:
          type: string
        title: tool_output
  28ae5559-8a7d-46bd-b1ff-82680db4f61f:
    component_type: VllmConfig
    id: 28ae5559-8a7d-46bd-b1ff-82680db4f61f
    name: llm_58b6cb28__auto
    description: null
    metadata:
      __metadata_info__: {}
    default_generation_parameters: null
    url: LLAMA_API_URL
    model_id: LLAMA_MODEL_ID
  c78b8336-2d92-4781-bd56-c28a476c839e:
    component_type: Agent
    id: c78b8336-2d92-4781-bd56-c28a476c839e
    name: Pharmacist
    description: Pharmacist. Gives availability and information about specific medication.
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs: []
    llm_config:
      $component_ref: 28ae5559-8a7d-46bd-b1ff-82680db4f61f
    system_prompt: 'You are an helpful Pharmacist LLM Agent responsible for giving
      information about medication.

      Your goal is to answer queries from the General Practitioner Doctor about medication
      information

      and availabilities.


      ## When to Use Each Tool

      - get_medication_info: Use this to look up availability and information about
      a specific medication.'
    tools:
    - component_type: ServerTool
      id: eb11af0c-e436-4815-b926-4b02cf3bb102
      name: get_medication_info
      description: 'Provides availability and information about a medication.

        Known information for "medicationA", "medicationB", "medicationC" and "creamA".


        Parameters:

        drug_name (str): Name of the drug.


        Returns:

        str: Information about the drug.'
      metadata:
        __metadata_info__: {}
      inputs:
      - type: string
        title: drug_name
      outputs:
      - type: string
        title: tool_output
  efddcffd-6d3e-41ad-a071-89cf833fc8f8:
    component_type: Agent
    id: efddcffd-6d3e-41ad-a071-89cf833fc8f8
    name: Dermatologist
    description: Dermatologist. Diagnoses and treats skin conditions.
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs: []
    llm_config:
      $component_ref: 28ae5559-8a7d-46bd-b1ff-82680db4f61f
    system_prompt: 'You are an helpful Dermatologist LLM Agent responsible for diagnosing
      and treating skin conditions.

      Your goal is to assess patients'' symptoms, provide accurate diagnoses, and
      prescribe effective treatments.


      ## When to Use Each Tool

      - knowledge_tool: Use this to look up diagnosis and treatment information for
      specific skin conditions.


      ## When to query other Agents

      - Pharmacist: Every time you need to prescribe some medication, give the condition
      description and prescription to the Pharmacist.


      # Specific instructions

      ## Initial exchange

      When a patient''s symptoms are referred to you by the General Practitioner,
      review the symptoms and use the knowledge tool to confirm the diagnosis.

      ## Prescription

      Prescribe the recommended treatment for the diagnosed condition and query the
      Pharmacist to confirm the availability of the prescribed medication.


      When answering back to the General Practitioner, describe your diagnosis and
      the prescription.

      Tell the General Practitioner that you already checked with the pharmacist for
      availability.'
    tools:
    - component_type: ServerTool
      id: d637a1fa-9680-407c-8297-df659215e795
      name: knowledge_tool
      description: 'Provides diagnosis and treatment information for skin conditions.

        Existing entries for "eczema" and "acne".


        Parameters:

        condition (str): Name of the skin condition.


        Returns:

        str: Diagnosis and treatment information.'
      metadata:
        __metadata_info__: {}
      inputs:
      - type: string
        title: condition
      outputs:
      - type: string
        title: tool_output
agentspec_version: 25.4.2
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {
    "symptoms_checker": symptoms_checker,
    "get_medication_info": get_medication_info,
    "knowledge_tool": knowledge_tool,
}
assistant: Swarm = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_json(serialized_assistant)
```

## Using Swarm within a Flow

The `Swarm` pattern can be integrated into a [Flow](../api/flows.md#flow) using the [AgentExecutionStep](../api/flows.md#agentexecutionstep).

Here’s an example of how to integrate a swarm into a flow:

```python
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep, CallerInputMode
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.property import StringProperty

# Example of using a Swarm within a Flow in non-conversational mode
def swarm_in_flow(swarm):
    severity_level = StringProperty(name="severity_level", default_value="", description='level of severity of the disease. Can be "HIGH", "MEDIUM" or "LOW"')
    agent_step = AgentExecutionStep(
        name="agent_step",
        agent=swarm,
        output_descriptors=[severity_level],
        caller_input_mode=CallerInputMode.NEVER,
    )
    output_step = OutputMessageStep(name="output_step", message_template="{{severity_level}}")

    flow = Flow(
        begin_step=agent_step,
        control_flow_edges=[
            ControlFlowEdge(source_step=agent_step, destination_step=output_step),
            ControlFlowEdge(source_step=output_step, destination_step=None),
        ],
        data_flow_edges=[DataFlowEdge(agent_step, "severity_level", output_step, "severity_level")],
    )
    return flow
```

You can run the flow with:

```python
flow = swarm_in_flow(assistant)
conversation = flow.start_conversation()
conversation.append_user_message("My skin has been itching for about a week. Can you tell me how severe it is?")
status = conversation.execute()
print(status.output_values["output_message"])
```

### Agent Spec Exporting/Loading

You can export the flow configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(flow)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
    "component_type": "Flow",
    "id": "33f78e41-52d0-437d-9192-aac771db6701",
    "name": "flow_f4d4d19d__auto",
    "description": "",
    "metadata": {
        "__metadata_info__": {}
    },
    "inputs": [],
    "outputs": [
        {
            "description": "the message added to the messages list",
            "type": "string",
            "title": "output_message"
        },
        {
            "description": "level of severity of the disease. Can be \"HIGH\", \"MEDIUM\" or \"LOW\"",
            "type": "string",
            "title": "severity_level",
            "default": ""
        }
    ],
    "start_node": {
        "$component_ref": "f2af74df-3b90-44d2-86a5-606e7da243ee"
    },
    "nodes": [
        {
            "$component_ref": "592c061c-a68a-49c3-ad2a-8e96d7be6dec"
        },
        {
            "$component_ref": "793fced3-20b2-40e2-836b-04d8e2310d16"
        },
        {
            "$component_ref": "f2af74df-3b90-44d2-86a5-606e7da243ee"
        },
        {
            "$component_ref": "8e0894a6-5940-4528-b518-22ab7ee3e6ff"
        }
    ],
    "control_flow_connections": [
        {
            "component_type": "ControlFlowEdge",
            "id": "9207760e-1ba5-4a83-b0ee-55f0de082119",
            "name": "agent_step_to_output_step_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "592c061c-a68a-49c3-ad2a-8e96d7be6dec"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "793fced3-20b2-40e2-836b-04d8e2310d16"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "66265aee-39f5-4f48-a027-804199358011",
            "name": "__StartStep___to_agent_step_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "f2af74df-3b90-44d2-86a5-606e7da243ee"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "592c061c-a68a-49c3-ad2a-8e96d7be6dec"
            }
        },
        {
            "component_type": "ControlFlowEdge",
            "id": "22b29e5f-e246-413a-bd09-c96c224d4932",
            "name": "output_step_to_None End node_control_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "from_node": {
                "$component_ref": "793fced3-20b2-40e2-836b-04d8e2310d16"
            },
            "from_branch": null,
            "to_node": {
                "$component_ref": "8e0894a6-5940-4528-b518-22ab7ee3e6ff"
            }
        }
    ],
    "data_flow_connections": [
        {
            "component_type": "DataFlowEdge",
            "id": "2889eada-d663-42b7-aff2-948d51e143e0",
            "name": "agent_step_severity_level_to_output_step_severity_level_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "592c061c-a68a-49c3-ad2a-8e96d7be6dec"
            },
            "source_output": "severity_level",
            "destination_node": {
                "$component_ref": "793fced3-20b2-40e2-836b-04d8e2310d16"
            },
            "destination_input": "severity_level"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "85a020be-6b81-4b56-b0ae-cee9729dc289",
            "name": "output_step_output_message_to_None End node_output_message_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "793fced3-20b2-40e2-836b-04d8e2310d16"
            },
            "source_output": "output_message",
            "destination_node": {
                "$component_ref": "8e0894a6-5940-4528-b518-22ab7ee3e6ff"
            },
            "destination_input": "output_message"
        },
        {
            "component_type": "DataFlowEdge",
            "id": "55de7cad-dd3f-4bb3-bdd6-6a2fc2429ee4",
            "name": "agent_step_severity_level_to_None End node_severity_level_data_flow_edge",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "source_node": {
                "$component_ref": "592c061c-a68a-49c3-ad2a-8e96d7be6dec"
            },
            "source_output": "severity_level",
            "destination_node": {
                "$component_ref": "8e0894a6-5940-4528-b518-22ab7ee3e6ff"
            },
            "destination_input": "severity_level"
        }
    ],
    "$referenced_components": {
        "793fced3-20b2-40e2-836b-04d8e2310d16": {
            "component_type": "PluginOutputMessageNode",
            "id": "793fced3-20b2-40e2-836b-04d8e2310d16",
            "name": "output_step",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "description": "\"severity_level\" input variable for the template",
                    "type": "string",
                    "title": "severity_level"
                }
            ],
            "outputs": [
                {
                    "description": "the message added to the messages list",
                    "type": "string",
                    "title": "output_message"
                }
            ],
            "branches": [
                "next"
            ],
            "message": "{{severity_level}}",
            "input_mapping": {},
            "output_mapping": {},
            "message_type": "AGENT",
            "rephrase": false,
            "llm_config": null,
            "expose_message_as_output": true,
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "26.2.0.dev0"
        },
        "592c061c-a68a-49c3-ad2a-8e96d7be6dec": {
            "component_type": "ExtendedAgentNode",
            "id": "592c061c-a68a-49c3-ad2a-8e96d7be6dec",
            "name": "agent_step",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [],
            "outputs": [
                {
                    "description": "level of severity of the disease. Can be \"HIGH\", \"MEDIUM\" or \"LOW\"",
                    "type": "string",
                    "title": "severity_level",
                    "default": ""
                }
            ],
            "branches": [
                "next"
            ],
            "agent": {
                "component_type": "Swarm",
                "id": "fcccae0f-f896-47f0-8c91-c9d9d9243feb",
                "name": "Swarm",
                "description": null,
                "metadata": {
                    "__metadata_info__": {}
                },
                "inputs": [],
                "outputs": [],
                "first_agent": {
                    "$component_ref": "112822d1-afa1-424f-8306-74c943950ec8"
                },
                "relationships": [
                    [
                        {
                            "$component_ref": "112822d1-afa1-424f-8306-74c943950ec8"
                        },
                        {
                            "$component_ref": "b599769f-fc6d-4657-a53a-65d8db461bf1"
                        }
                    ],
                    [
                        {
                            "$component_ref": "112822d1-afa1-424f-8306-74c943950ec8"
                        },
                        {
                            "$component_ref": "9c208b64-66dc-40d7-b574-dd1b494322e0"
                        }
                    ],
                    [
                        {
                            "$component_ref": "9c208b64-66dc-40d7-b574-dd1b494322e0"
                        },
                        {
                            "$component_ref": "b599769f-fc6d-4657-a53a-65d8db461bf1"
                        }
                    ]
                ],
                "handoff": "always",
                "$referenced_components": {
                    "112822d1-afa1-424f-8306-74c943950ec8": {
                        "component_type": "ExtendedAgent",
                        "id": "112822d1-afa1-424f-8306-74c943950ec8",
                        "name": "GeneralPractitioner",
                        "description": "General Practitioner. Primary point of contact for patients, handles general medical inquiries, provides initial diagnoses, and manages referrals.",
                        "metadata": {
                            "__metadata_info__": {}
                        },
                        "inputs": [],
                        "outputs": [],
                        "llm_config": {
                            "$component_ref": "c1687f76-2526-4f77-aeed-6468e433fbba"
                        },
                        "system_prompt": "You are an helpful general practitioner LLM doctor responsible for handling patient consultations.\nYour goal is to assess patients' symptoms, provide initial diagnoses, pescribe medication for\nmild conditions or refer to other specialists as needed.\n\n## When to Use Each Tool\n- symptoms_checker: Use this to look up possible conditions based on symptoms reported by the patient.\n\n## When to query other Agents\n- Pharmacist: Every time you need to prescribe some medication, give the condition description and prescription to the Pharmacist.\n- Dermatologist: If the patient has a skin condition, ask expert advice/diagnosis to the Dermatologist after the initial exchange.\n\n# Specific instructions\n## Initial exchange\nWhen a patient first shares symptoms ask about for exactly 1 round of questions, consisting of asking about medical history and\nsimple questions (e.g. do they have known allergies, when did the symptoms started, did they already tried some treatment/medication, etc)).\nAlways ask for this one round of information to the user before prescribing medication / referring to other agents.\n\n## Identifying condition\nUse the symptoms checker to confirm the condition (for mild conditions only. For other conditions, refer to specialists).\n\n## Mild conditions\n* If the patient has a mild cold, prescribe medicationA.\n    - Give the condition description and prescription to the Pharmacist.\n\n## Skin conditions\n* If the patient has a skin condition, ask for expert advice/diagnosis from the Dermatologist.\nHere, you don't need to ask for the user confirmation. Directly call the Dermatologist\n    - Provide the patient's symptoms/initial hypothesis to the Dermatologist and ask for a diagnosis.\n    - The Dermatologist may query the Pharmacist to confirm the availability of the prescribed medication.\n    - Once the treatment is confirmed, pass on the prescription to the patient and ask them to follow the instructions.",
                        "tools": [
                            {
                                "component_type": "ServerTool",
                                "id": "7a29c1a0-7118-4cb7-ac9e-df662a917fcd",
                                "name": "symptoms_checker",
                                "description": "Checks symptoms against the medical knowledge base.\nExisting entries for \"fever\", \"cough\" and \"headache\".\nFor other symptoms, you may need to refer to a specialist.\n\nParameters:\nsymptoms (list): List of symptoms reported by the patient.\n\nReturns:\nlist: Possible conditions based on the symptoms.",
                                "metadata": {
                                    "__metadata_info__": {}
                                },
                                "inputs": [
                                    {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        },
                                        "title": "symptoms"
                                    }
                                ],
                                "outputs": [
                                    {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        },
                                        "title": "tool_output"
                                    }
                                ],
                                "requires_confirmation": false
                            }
                        ],
                        "toolboxes": [],
                        "human_in_the_loop": true,
                        "transforms": [],
                        "context_providers": null,
                        "can_finish_conversation": false,
                        "raise_exceptions": false,
                        "max_iterations": 10,
                        "initial_message": "Hi! How can I help you?",
                        "caller_input_mode": "always",
                        "agents": [],
                        "flows": [],
                        "agent_template": null,
                        "component_plugin_name": "AgentPlugin",
                        "component_plugin_version": "26.2.0.dev0"
                    },
                    "c1687f76-2526-4f77-aeed-6468e433fbba": {
                        "component_type": "VllmConfig",
                        "id": "c1687f76-2526-4f77-aeed-6468e433fbba",
                        "name": "llm_4eef046b__auto",
                        "description": null,
                        "metadata": {
                            "__metadata_info__": {}
                        },
                        "default_generation_parameters": null,
                        "url": "LLAMA_API_URL",
                        "model_id": "LLAMA_MODEL_ID",
                        "api_type": "chat_completions",
                        "api_key": null
                    },
                    "b599769f-fc6d-4657-a53a-65d8db461bf1": {
                        "component_type": "ExtendedAgent",
                        "id": "b599769f-fc6d-4657-a53a-65d8db461bf1",
                        "name": "Pharmacist",
                        "description": "Pharmacist. Gives availability and information about specific medication.",
                        "metadata": {
                            "__metadata_info__": {}
                        },
                        "inputs": [],
                        "outputs": [],
                        "llm_config": {
                            "$component_ref": "c1687f76-2526-4f77-aeed-6468e433fbba"
                        },
                        "system_prompt": "You are an helpful Pharmacist LLM Agent responsible for giving information about medication.\nYour goal is to answer queries from the General Practitioner Doctor about medication information\nand availabilities.\n\n## When to Use Each Tool\n- get_medication_info: Use this to look up availability and information about a specific medication.",
                        "tools": [
                            {
                                "component_type": "ServerTool",
                                "id": "5494c169-d684-41cb-b8c4-57e7568c66d3",
                                "name": "get_medication_info",
                                "description": "Provides availability and information about a medication.\nKnown information for \"medicationA\", \"medicationB\", \"medicationC\" and \"creamA\".\n\nParameters:\ndrug_name (str): Name of the drug.\n\nReturns:\nstr: Information about the drug.",
                                "metadata": {
                                    "__metadata_info__": {}
                                },
                                "inputs": [
                                    {
                                        "type": "string",
                                        "title": "drug_name"
                                    }
                                ],
                                "outputs": [
                                    {
                                        "type": "string",
                                        "title": "tool_output"
                                    }
                                ],
                                "requires_confirmation": false
                            }
                        ],
                        "toolboxes": [],
                        "human_in_the_loop": true,
                        "transforms": [],
                        "context_providers": null,
                        "can_finish_conversation": false,
                        "raise_exceptions": false,
                        "max_iterations": 10,
                        "initial_message": "Hi! How can I help you?",
                        "caller_input_mode": "always",
                        "agents": [],
                        "flows": [],
                        "agent_template": null,
                        "component_plugin_name": "AgentPlugin",
                        "component_plugin_version": "26.2.0.dev0"
                    },
                    "9c208b64-66dc-40d7-b574-dd1b494322e0": {
                        "component_type": "ExtendedAgent",
                        "id": "9c208b64-66dc-40d7-b574-dd1b494322e0",
                        "name": "Dermatologist",
                        "description": "Dermatologist. Diagnoses and treats skin conditions.",
                        "metadata": {
                            "__metadata_info__": {}
                        },
                        "inputs": [],
                        "outputs": [],
                        "llm_config": {
                            "$component_ref": "c1687f76-2526-4f77-aeed-6468e433fbba"
                        },
                        "system_prompt": "You are an helpful Dermatologist LLM Agent responsible for diagnosing and treating skin conditions.\nYour goal is to assess patients' symptoms, provide accurate diagnoses, and prescribe effective treatments.\n\n## When to Use Each Tool\n- knowledge_tool: Use this to look up diagnosis and treatment information for specific skin conditions.\n\n## When to query other Agents\n- Pharmacist: Every time you need to prescribe some medication, give the condition description and prescription to the Pharmacist.\n\n# Specific instructions\n## Initial exchange\nWhen a patient's symptoms are referred to you by the General Practitioner, review the symptoms and use the knowledge tool to confirm the diagnosis.\n## Prescription\nPrescribe the recommended treatment for the diagnosed condition and query the Pharmacist to confirm the availability of the prescribed medication.\n\nWhen answering back to the General Practitioner, describe your diagnosis and the prescription.\nTell the General Practitioner that you already checked with the pharmacist for availability.",
                        "tools": [
                            {
                                "component_type": "ServerTool",
                                "id": "7e483336-ac47-4f04-a4b9-d6701dfe5dc6",
                                "name": "knowledge_tool",
                                "description": "Provides diagnosis and treatment information for skin conditions.\nExisting entries for \"eczema\" and \"acne\".\n\nParameters:\ncondition (str): Name of the skin condition.\n\nReturns:\nstr: Diagnosis and treatment information.",
                                "metadata": {
                                    "__metadata_info__": {}
                                },
                                "inputs": [
                                    {
                                        "type": "string",
                                        "title": "condition"
                                    }
                                ],
                                "outputs": [
                                    {
                                        "type": "string",
                                        "title": "tool_output"
                                    }
                                ],
                                "requires_confirmation": false
                            }
                        ],
                        "toolboxes": [],
                        "human_in_the_loop": true,
                        "transforms": [],
                        "context_providers": null,
                        "can_finish_conversation": false,
                        "raise_exceptions": false,
                        "max_iterations": 10,
                        "initial_message": "Hi! How can I help you?",
                        "caller_input_mode": "always",
                        "agents": [],
                        "flows": [],
                        "agent_template": null,
                        "component_plugin_name": "AgentPlugin",
                        "component_plugin_version": "26.2.0.dev0"
                    }
                }
            },
            "input_mapping": {},
            "output_mapping": {},
            "caller_input_mode": "always",
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "26.2.0.dev0"
        },
        "f2af74df-3b90-44d2-86a5-606e7da243ee": {
            "component_type": "StartNode",
            "id": "f2af74df-3b90-44d2-86a5-606e7da243ee",
            "name": "__StartStep__",
            "description": "",
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [],
            "outputs": [],
            "branches": [
                "next"
            ]
        },
        "8e0894a6-5940-4528-b518-22ab7ee3e6ff": {
            "component_type": "EndNode",
            "id": "8e0894a6-5940-4528-b518-22ab7ee3e6ff",
            "name": "None End node",
            "description": null,
            "metadata": {
                "__metadata_info__": {}
            },
            "inputs": [
                {
                    "description": "the message added to the messages list",
                    "type": "string",
                    "title": "output_message"
                },
                {
                    "description": "level of severity of the disease. Can be \"HIGH\", \"MEDIUM\" or \"LOW\"",
                    "type": "string",
                    "title": "severity_level",
                    "default": ""
                }
            ],
            "outputs": [
                {
                    "description": "the message added to the messages list",
                    "type": "string",
                    "title": "output_message"
                },
                {
                    "description": "level of severity of the disease. Can be \"HIGH\", \"MEDIUM\" or \"LOW\"",
                    "type": "string",
                    "title": "severity_level",
                    "default": ""
                }
            ],
            "branches": [],
            "branch_name": "next"
        }
    },
    "agentspec_version": "26.2.0"
}
```

YAML

```yaml
component_type: Flow
id: 0db01cf3-d0f7-424a-ac37-744ba7f99a94
name: flow_b1784ff0__auto
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs:
- description: the message added to the messages list
  type: string
  title: output_message
- description: level of severity of the disease. Can be "HIGH", "MEDIUM" or "LOW"
  type: string
  title: severity_level
  default: ''
start_node:
  $component_ref: 91792ebb-159b-4017-9b29-35ba282dd1d7
nodes:
- $component_ref: d094a96b-c3d4-4799-b1c7-dbfe5f53e24d
- $component_ref: 6fce39d0-ece6-4b80-bcb4-68af50997844
- $component_ref: 91792ebb-159b-4017-9b29-35ba282dd1d7
- $component_ref: 39e6a3b6-81fd-4ca9-8dfa-74caccf31a2c
control_flow_connections:
- component_type: ControlFlowEdge
  id: a7cdea50-18da-4cc2-8564-d76759b701d8
  name: agent_step_to_output_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: d094a96b-c3d4-4799-b1c7-dbfe5f53e24d
  from_branch: null
  to_node:
    $component_ref: 6fce39d0-ece6-4b80-bcb4-68af50997844
- component_type: ControlFlowEdge
  id: d778155b-d434-450d-90a2-5ab0815e2e2d
  name: __StartStep___to_agent_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 91792ebb-159b-4017-9b29-35ba282dd1d7
  from_branch: null
  to_node:
    $component_ref: d094a96b-c3d4-4799-b1c7-dbfe5f53e24d
- component_type: ControlFlowEdge
  id: c1e0009b-9d16-4f29-8b89-c7b8e0e372fa
  name: output_step_to_None End node_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 6fce39d0-ece6-4b80-bcb4-68af50997844
  from_branch: null
  to_node:
    $component_ref: 39e6a3b6-81fd-4ca9-8dfa-74caccf31a2c
data_flow_connections:
- component_type: DataFlowEdge
  id: 069d3126-8e2d-4dd3-95a8-2fd4989a116d
  name: agent_step_severity_level_to_output_step_severity_level_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: d094a96b-c3d4-4799-b1c7-dbfe5f53e24d
  source_output: severity_level
  destination_node:
    $component_ref: 6fce39d0-ece6-4b80-bcb4-68af50997844
  destination_input: severity_level
- component_type: DataFlowEdge
  id: fd0581fb-d4a7-4277-8cf1-275cff414f87
  name: output_step_output_message_to_None End node_output_message_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 6fce39d0-ece6-4b80-bcb4-68af50997844
  source_output: output_message
  destination_node:
    $component_ref: 39e6a3b6-81fd-4ca9-8dfa-74caccf31a2c
  destination_input: output_message
- component_type: DataFlowEdge
  id: 94eacd45-b60f-4ca9-ba62-5b59156fcc92
  name: agent_step_severity_level_to_None End node_severity_level_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: d094a96b-c3d4-4799-b1c7-dbfe5f53e24d
  source_output: severity_level
  destination_node:
    $component_ref: 39e6a3b6-81fd-4ca9-8dfa-74caccf31a2c
  destination_input: severity_level
$referenced_components:
  91792ebb-159b-4017-9b29-35ba282dd1d7:
    component_type: StartNode
    id: 91792ebb-159b-4017-9b29-35ba282dd1d7
    name: __StartStep__
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs: []
    branches:
    - next
  d094a96b-c3d4-4799-b1c7-dbfe5f53e24d:
    component_type: ExtendedAgentNode
    id: d094a96b-c3d4-4799-b1c7-dbfe5f53e24d
    name: agent_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs:
    - description: level of severity of the disease. Can be "HIGH", "MEDIUM" or "LOW"
      type: string
      title: severity_level
      default: ''
    branches:
    - next
    agent:
      component_type: Swarm
      id: b92f4c23-852a-482f-a1c1-54dc390465b6
      name: Swarm
      description: null
      metadata:
        __metadata_info__: {}
      inputs: []
      outputs: []
      first_agent:
        $component_ref: c087dc77-2906-47e5-bd54-c4a7786d0b12
      relationships:
      - - $component_ref: c087dc77-2906-47e5-bd54-c4a7786d0b12
        - $component_ref: 0d540d81-99dd-4681-99fb-e0a51e40de02
      - - $component_ref: c087dc77-2906-47e5-bd54-c4a7786d0b12
        - $component_ref: d9284501-c17a-48c1-a071-8d543a28e799
      - - $component_ref: d9284501-c17a-48c1-a071-8d543a28e799
        - $component_ref: 0d540d81-99dd-4681-99fb-e0a51e40de02
      handoff: always
      $referenced_components:
        c087dc77-2906-47e5-bd54-c4a7786d0b12:
          component_type: ExtendedAgent
          id: c087dc77-2906-47e5-bd54-c4a7786d0b12
          name: GeneralPractitioner
          description: General Practitioner. Primary point of contact for patients,
            handles general medical inquiries, provides initial diagnoses, and manages
            referrals.
          metadata:
            __metadata_info__: {}
          inputs: []
          outputs: []
          llm_config:
            $component_ref: 2ae71892-c494-4a9a-b4f3-ec0af36db69d
          system_prompt: "You are an helpful general practitioner LLM doctor responsible\
            \ for handling patient consultations.\nYour goal is to assess patients'\
            \ symptoms, provide initial diagnoses, pescribe medication for\nmild conditions\
            \ or refer to other specialists as needed.\n\n## When to Use Each Tool\n\
            - symptoms_checker: Use this to look up possible conditions based on symptoms\
            \ reported by the patient.\n\n## When to query other Agents\n- Pharmacist:\
            \ Every time you need to prescribe some medication, give the condition\
            \ description and prescription to the Pharmacist.\n- Dermatologist: If\
            \ the patient has a skin condition, ask expert advice/diagnosis to the\
            \ Dermatologist after the initial exchange.\n\n# Specific instructions\n\
            ## Initial exchange\nWhen a patient first shares symptoms ask about for\
            \ exactly 1 round of questions, consisting of asking about medical history\
            \ and\nsimple questions (e.g. do they have known allergies, when did the\
            \ symptoms started, did they already tried some treatment/medication,\
            \ etc)).\nAlways ask for this one round of information to the user before\
            \ prescribing medication / referring to other agents.\n\n## Identifying\
            \ condition\nUse the symptoms checker to confirm the condition (for mild\
            \ conditions only. For other conditions, refer to specialists).\n\n##\
            \ Mild conditions\n* If the patient has a mild cold, prescribe medicationA.\n\
            \    - Give the condition description and prescription to the Pharmacist.\n\
            \n## Skin conditions\n* If the patient has a skin condition, ask for expert\
            \ advice/diagnosis from the Dermatologist.\nHere, you don't need to ask\
            \ for the user confirmation. Directly call the Dermatologist\n    - Provide\
            \ the patient's symptoms/initial hypothesis to the Dermatologist and ask\
            \ for a diagnosis.\n    - The Dermatologist may query the Pharmacist to\
            \ confirm the availability of the prescribed medication.\n    - Once the\
            \ treatment is confirmed, pass on the prescription to the patient and\
            \ ask them to follow the instructions."
          tools:
          - component_type: ServerTool
            id: aaab97a0-97ad-4bae-a34f-837758bf326e
            name: symptoms_checker
            description: 'Checks symptoms against the medical knowledge base.

              Existing entries for "fever", "cough" and "headache".

              For other symptoms, you may need to refer to a specialist.


              Parameters:

              symptoms (list): List of symptoms reported by the patient.


              Returns:

              list: Possible conditions based on the symptoms.'
            metadata:
              __metadata_info__: {}
            inputs:
            - type: array
              items:
                type: string
              title: symptoms
            outputs:
            - type: array
              items:
                type: string
              title: tool_output
            requires_confirmation: false
          toolboxes: []
          human_in_the_loop: true
          transforms: []
          context_providers: null
          can_finish_conversation: false
          raise_exceptions: false
          max_iterations: 10
          initial_message: Hi! How can I help you?
          caller_input_mode: always
          agents: []
          flows: []
          agent_template: null
          component_plugin_name: AgentPlugin
          component_plugin_version: 26.2.0.dev0
        2ae71892-c494-4a9a-b4f3-ec0af36db69d:
          component_type: VllmConfig
          id: 2ae71892-c494-4a9a-b4f3-ec0af36db69d
          name: llm_37012f27__auto
          description: null
          metadata:
            __metadata_info__: {}
          default_generation_parameters: null
          url: LLAMA_API_URL
          model_id: LLAMA_MODEL_ID
          api_type: chat_completions
          api_key: null
        0d540d81-99dd-4681-99fb-e0a51e40de02:
          component_type: ExtendedAgent
          id: 0d540d81-99dd-4681-99fb-e0a51e40de02
          name: Pharmacist
          description: Pharmacist. Gives availability and information about specific
            medication.
          metadata:
            __metadata_info__: {}
          inputs: []
          outputs: []
          llm_config:
            $component_ref: 2ae71892-c494-4a9a-b4f3-ec0af36db69d
          system_prompt: 'You are an helpful Pharmacist LLM Agent responsible for
            giving information about medication.

            Your goal is to answer queries from the General Practitioner Doctor about
            medication information

            and availabilities.


            ## When to Use Each Tool

            - get_medication_info: Use this to look up availability and information
            about a specific medication.'
          tools:
          - component_type: ServerTool
            id: 7ed6d1c3-5524-4586-a7d1-0a957d52f490
            name: get_medication_info
            description: 'Provides availability and information about a medication.

              Known information for "medicationA", "medicationB", "medicationC" and
              "creamA".


              Parameters:

              drug_name (str): Name of the drug.


              Returns:

              str: Information about the drug.'
            metadata:
              __metadata_info__: {}
            inputs:
            - type: string
              title: drug_name
            outputs:
            - type: string
              title: tool_output
            requires_confirmation: false
          toolboxes: []
          human_in_the_loop: true
          transforms: []
          context_providers: null
          can_finish_conversation: false
          raise_exceptions: false
          max_iterations: 10
          initial_message: Hi! How can I help you?
          caller_input_mode: always
          agents: []
          flows: []
          agent_template: null
          component_plugin_name: AgentPlugin
          component_plugin_version: 26.2.0.dev0
        d9284501-c17a-48c1-a071-8d543a28e799:
          component_type: ExtendedAgent
          id: d9284501-c17a-48c1-a071-8d543a28e799
          name: Dermatologist
          description: Dermatologist. Diagnoses and treats skin conditions.
          metadata:
            __metadata_info__: {}
          inputs: []
          outputs: []
          llm_config:
            $component_ref: 2ae71892-c494-4a9a-b4f3-ec0af36db69d
          system_prompt: 'You are an helpful Dermatologist LLM Agent responsible for
            diagnosing and treating skin conditions.

            Your goal is to assess patients'' symptoms, provide accurate diagnoses,
            and prescribe effective treatments.


            ## When to Use Each Tool

            - knowledge_tool: Use this to look up diagnosis and treatment information
            for specific skin conditions.


            ## When to query other Agents

            - Pharmacist: Every time you need to prescribe some medication, give the
            condition description and prescription to the Pharmacist.


            # Specific instructions

            ## Initial exchange

            When a patient''s symptoms are referred to you by the General Practitioner,
            review the symptoms and use the knowledge tool to confirm the diagnosis.

            ## Prescription

            Prescribe the recommended treatment for the diagnosed condition and query
            the Pharmacist to confirm the availability of the prescribed medication.


            When answering back to the General Practitioner, describe your diagnosis
            and the prescription.

            Tell the General Practitioner that you already checked with the pharmacist
            for availability.'
          tools:
          - component_type: ServerTool
            id: 03592ad0-b2e9-430d-a1eb-048ed5557f10
            name: knowledge_tool
            description: 'Provides diagnosis and treatment information for skin conditions.

              Existing entries for "eczema" and "acne".


              Parameters:

              condition (str): Name of the skin condition.


              Returns:

              str: Diagnosis and treatment information.'
            metadata:
              __metadata_info__: {}
            inputs:
            - type: string
              title: condition
            outputs:
            - type: string
              title: tool_output
            requires_confirmation: false
          toolboxes: []
          human_in_the_loop: true
          transforms: []
          context_providers: null
          can_finish_conversation: false
          raise_exceptions: false
          max_iterations: 10
          initial_message: Hi! How can I help you?
          caller_input_mode: always
          agents: []
          flows: []
          agent_template: null
          component_plugin_name: AgentPlugin
          component_plugin_version: 26.2.0.dev0
    input_mapping: {}
    output_mapping: {}
    caller_input_mode: always
    component_plugin_name: NodesPlugin
    component_plugin_version: 26.2.0.dev0
  6fce39d0-ece6-4b80-bcb4-68af50997844:
    component_type: PluginOutputMessageNode
    id: 6fce39d0-ece6-4b80-bcb4-68af50997844
    name: output_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: '"severity_level" input variable for the template'
      type: string
      title: severity_level
    outputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    branches:
    - next
    message: '{{severity_level}}'
    input_mapping: {}
    output_mapping: {}
    message_type: AGENT
    rephrase: false
    llm_config: null
    expose_message_as_output: true
    component_plugin_name: NodesPlugin
    component_plugin_version: 26.2.0.dev0
  39e6a3b6-81fd-4ca9-8dfa-74caccf31a2c:
    component_type: EndNode
    id: 39e6a3b6-81fd-4ca9-8dfa-74caccf31a2c
    name: None End node
    description: null
    metadata:
      __metadata_info__: {}
    inputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    - description: level of severity of the disease. Can be "HIGH", "MEDIUM" or "LOW"
      type: string
      title: severity_level
      default: ''
    outputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    - description: level of severity of the disease. Can be "HIGH", "MEDIUM" or "LOW"
      type: string
      title: severity_level
      default: ''
    branches: []
    branch_name: next
agentspec_version: 26.2.0
```

</details>

You can then load the configuration back to a flow using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {
    "symptoms_checker": symptoms_checker,
    "get_medication_info": get_medication_info,
    "knowledge_tool": knowledge_tool,
}
flow: Flow = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_json(serialized_flow)
```

## Next steps

Now that you have learned how to define a Swarm, you may proceed to [How to Build Multi-Agent System](howto_multiagent.md).

## Full code

Click on the card at the [top of this page](#top-howtoswarm) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - Build a Swarm of Agents
# --------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_swarm.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.




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
        status = conversation.execute()
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
from wayflowcore.swarm import HandoffMode
assistant = Swarm(
    name="Swarm",
    first_agent=general_practitioner,
    relationships=[
        (general_practitioner, pharmacist),
        (general_practitioner, dermatologist),
        (dermatologist, pharmacist),
    ],
    handoff=HandoffMode.ALWAYS,  # <-- Choose the handoff mode of your choice
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

# %%[markdown]
## Using Swarm within a Flow

# %%
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep, CallerInputMode
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.property import StringProperty

# Example of using a Swarm within a Flow in non-conversational mode
def swarm_in_flow(swarm):
    severity_level = StringProperty(name="severity_level", default_value="", description='level of severity of the disease. Can be "HIGH", "MEDIUM" or "LOW"')
    agent_step = AgentExecutionStep(
        name="agent_step",
        agent=swarm,
        output_descriptors=[severity_level],
        caller_input_mode=CallerInputMode.NEVER,
    )
    output_step = OutputMessageStep(name="output_step", message_template="{{severity_level}}")

    flow = Flow(
        begin_step=agent_step,
        control_flow_edges=[
            ControlFlowEdge(source_step=agent_step, destination_step=output_step),
            ControlFlowEdge(source_step=output_step, destination_step=None),
        ],
        data_flow_edges=[DataFlowEdge(agent_step, "severity_level", output_step, "severity_level")],
    )
    return flow

# %%[markdown]
## Run Swarm within a Flow

# %%
flow = swarm_in_flow(assistant)
conversation = flow.start_conversation()
conversation.append_user_message("My skin has been itching for about a week. Can you tell me how severe it is?")
status = conversation.execute()
print(status.output_values["output_message"])

# %%[markdown]
## Export config to Agent Spec2

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(flow)

# %%[markdown]
## Load Agent Spec config2

# %%
from wayflowcore.agentspec import AgentSpecLoader

TOOL_REGISTRY = {
    "symptoms_checker": symptoms_checker,
    "get_medication_info": get_medication_info,
    "knowledge_tool": knowledge_tool,
}
flow: Flow = AgentSpecLoader(
    tool_registry=TOOL_REGISTRY
).load_json(serialized_flow)
```
