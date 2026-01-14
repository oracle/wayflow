# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: How to Use A2A Agents

### Basic Usage

# .. start-##_Creating_the_agent
from wayflowcore.a2a.a2aagent import A2AAgent, A2AConnectionConfig

agent = A2AAgent(
    agent_url="http://<URL>",
    connection_config=A2AConnectionConfig(verify=False)
)
# .. end-##_Creating_the_agent
agent: A2AAgent  # docs-skiprow
(agent,) = _update_globals(["a2a_agent"])  # docs-skiprow # type: ignore

# .. start-##_Running_the_agent
from wayflowcore.executors.executionstatus import UserMessageRequestStatus

# With a linear conversation
conversation = agent.start_conversation()

conversation.append_user_message("What is the answer to 2+2?")
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")
# .. end-##_Running_the_agent

# .. start-##_Export_config_to_Agent_Spec1
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(agent)
# .. end-##_Export_config_to_Agent_Spec1
# .. start-##_Load_Agent_Spec_config1
from wayflowcore.agentspec import AgentSpecLoader

agent: A2AAgent = AgentSpecLoader().load_json(serialized_assistant)
# .. end-##_Load_Agent_Spec_config1

### Manager Workers Usage

# Server part
import random
from typing import Annotated

from wayflowcore.agentserver.server import A2AServer
from wayflowcore.agent import Agent
from wayflowcore.models import VllmModel
from wayflowcore.tools import tool

# .. start-##_llm
llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)
# .. end-##_llm

(llm,) = _update_globals(["vision_llm"])  # docs-skiprow # type: ignore


# .. start-##_Server_Setup_Prime_Agent
def get_prime_agent():
    @tool
    def check_prime(a: Annotated[int, "first required integer"]) -> bool:
        "Check if the first number (a) is a prime number."
        if a < 2:
            return False
        for i in range(2, int(a**0.5) + 1):
            if a % i == 0:
                return False
        return True
    agent = Agent(
        llm=llm,
        name="prime_agent",
        custom_instruction="You are a math agent that can check whether a number is prime or not using the equipped tool.",
        tools=[check_prime],
        can_finish_conversation=True,
    )
    return agent
# .. end-##_Server_Setup_Prime_Agent


# .. start-##_Server_Setup_Sample_Agent
def get_sample_agent():
    @tool
    def sample_number(a: Annotated[int, "first required integer"]) -> int:
        "Simulate sampling from a range, return a random number between 1 and the specified value."
        result = random.randint(1, a) # nosec
        return result
    agent = Agent(
        llm=llm,
        name="sample_agent",
        custom_instruction="You are an agent that can generate a random number between 1 and a specified value.",
        tools=[sample_number],
        can_finish_conversation=True,
    )
    return agent
# .. end-##_Server_Setup_Sample_Agent

# .. start-##_Server_Startup_Logic
# Start both sample and prime servers
sample_agent = get_sample_agent()
sample_server = A2AServer()
sample_server.serve_agent(sample_agent, "http://<sample_agent_url>")
# Note: Uncomment the line below to start the server
# sample_server.serve()

prime_agent = get_prime_agent()
prime_server = A2AServer()
prime_server.serve_agent(prime_agent, "http://<prime_agent_url>")
# Note: Uncomment the line below to start the server
# prime_server.serve(port=8001)
# .. end-##_Server_Startup_Logic

(sample_server,) = _update_globals(["sample_a2a_server"])  # docs-skiprow # type: ignore
(prime_server,) = _update_globals(["prime_a2a_server"])  # docs-skiprow # type: ignore

# Client part
from wayflowcore.a2a.a2aagent import A2AAgent, A2AConnectionConfig
from wayflowcore.agent import Agent
from wayflowcore.models import VllmModel

# .. start-##_Client_Setup
sample_agent = A2AAgent(
    name="sample_agent",
    agent_url="http://<sample_agent_url>",
    description="Agent that can generate random numbers",
    connection_config=A2AConnectionConfig(verify=False),
)
prime_agent = A2AAgent(
    name="prime_agent",
    agent_url="http://<prime_agent_url>",
    description="Agent that handles checking if numbers are prime.",
    connection_config=A2AConnectionConfig(verify=False),
)
# .. end-##_Client_Setup

(sample_agent, prime_agent) = _update_globals(
    ["sample_a2a_agent", "prime_a2a_agent"]
)  # docs-skiprow # type: ignore

# .. start-##_Manager_Setup
MANAGER_SYSTEM_PROMPT = """
You are a helpful assistant that can sample numbers and check if the sampled numbers are prime.
You delegate sampling tasks to the `sample_agent` and prime checking tasks to the `prime_agent`.
Follow these steps:
1. If the user asks to sample a number, delegate to the `sample_agent`.
2. If the user asks to check primes, delegate to the `prime_agent`.
3. If the user asks to sample a number and then check if the result is prime, call `sample_agent` first, then pass the result to `prime_agent`.
Always clarify the results before proceeding.
""".strip()

manager = Agent(
    name="PrimeChecker",
    description="You are a PrimeChecker who can sample integers and check if they are prime.",
    llm=llm,
    custom_instruction=MANAGER_SYSTEM_PROMPT,
)
# .. end-##_Manager_Setup

# .. start-##_ManagerWorkers_Execution
from wayflowcore.managerworkers import ManagerWorkers

group = ManagerWorkers(
    group_manager=manager,
    workers=[sample_agent, prime_agent],
)

main_conversation = group.start_conversation()
main_conversation.append_user_message("Sample a number from 1 to 20 and check if it's prime")
main_conversation.execute()
print(main_conversation.get_messages())
# .. end-##_ManagerWorkers_Execution

# .. start-##_Export_config_to_Agent_Spec2
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(group)
# .. end-##_Export_config_to_Agent_Spec2
# .. start-##_Load_Agent_Spec_config2
from wayflowcore.agentspec import AgentSpecLoader

agent: A2AAgent = AgentSpecLoader().load_json(serialized_assistant)
# .. end-##_Load_Agent_Spec_config2
