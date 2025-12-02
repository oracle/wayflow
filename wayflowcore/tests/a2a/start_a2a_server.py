# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import argparse
import os
from enum import Enum
from typing import Annotated, Callable

import pytest
import uvicorn

from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.agentserver.server import A2AServer
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.models import VllmModel
from wayflowcore.property import StringProperty
from wayflowcore.steps import (
    AgentExecutionStep,
    CompleteStep,
    InputMessageStep,
    OutputMessageStep,
    ToolExecutionStep,
)
from wayflowcore.swarm import Swarm
from wayflowcore.tools import tool

llm = VllmModel(
    model_id="meta-llama/Meta-Llama-3.1-8B-Instruct",
    host_port=os.getenv("LLAMA_API_URL"),
)

# ============== Agent factory ==============
AGENT_FACTORIES: dict[str, Callable[[], Agent]] = {}


def register_agent(agent_enum: "AgentType"):
    """Decorator to register an agent factory for a given Enum member."""

    def decorator(func: Callable[[], Agent]):
        AGENT_FACTORIES[agent_enum.value] = func
        return func

    return decorator


# ============== Enum of available agents ==============
class AgentType(str, Enum):
    AGENT_WITHOUT_TOOL = "agent_without_tool"
    AGENT_WITH_SERVER_TOOL = "agent_with_server_tool"
    AGENT_WITH_VISION_CAPABILITY = "agent_with_vision_capability"
    FLOW_WITH_AGENT_STEP = "flow_with_agent_step"
    FLOW_WITH_AGENT_STEP_THAT_YIELDS_ONCE = "flow_with_agent_step_that_yields_once"
    FLOW_THAT_WITH_INPUT_STEP_YIELDS_ONCE = "flow_that_yields_once"
    MANAGER_WORKERS = "manager_workers"
    SWARM = "swarm"
    ADK_AGENT = "adk_agent"
    SAMPLE_AGENT = "sample_agent"
    PRIME_AGENT = "prime_agent"


# ============== Agent functions ==============
@register_agent(AgentType.AGENT_WITHOUT_TOOL)
def get_agent_without_tool() -> Agent:
    return Agent(llm=llm, can_finish_conversation=True)


@register_agent(AgentType.AGENT_WITH_SERVER_TOOL)
def get_agent_with_server_tool() -> Agent:
    @tool
    def multiply(
        a: Annotated[int, "first required integer"],
        b: Annotated[int, "second required integer"],
    ) -> int:
        "Return the result of multiplication between number a and b."
        print(f"multiply called: {a}, {b}")
        return a * b

    @tool
    def add(
        a: Annotated[int, "first required integer"],
        b: Annotated[int, "second required integer"],
    ) -> int:
        "Return the result of addition between number a and b."
        print(f"add called: {a}, {b}")
        return a + b

    return Agent(
        llm=llm,
        name="math_agent",
        custom_instruction="You are a Math agent that can do multiplication and addition using the equipped tools.",
        tools=[multiply, add],
        can_finish_conversation=True,
    )


# google-adk warnings
@pytest.mark.filterwarnings("ignore::UserWarning")
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.filterwarnings("ignore::FutureWarning")
@register_agent(AgentType.ADK_AGENT)
def get_adk_agent():
    from google.adk.agents import Agent as ADKAgent
    from google.adk.models.lite_llm import LiteLlm

    VLLM_MODEL_ID = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    VLLM_API_URL = os.getenv("LLAMA_API_URL")
    llm = LiteLlm(model=f"hosted_vllm/{VLLM_MODEL_ID}", base_url=f"http://{VLLM_API_URL}/v1")

    def multiply(a: int, b: int) -> int:
        """Multiply two numbers.

        Args:
            a: First number.
            b: Second number.

        Returns:
            product of a, b
        """
        return a * b

    def add(a: int, b: int) -> int:
        """Add two numbers.

        Args:
            a: First number.
            b: Second number.

        Returns:
            sum of a, b
        """
        return a + b

    return ADKAgent(
        model=llm,
        name="hello_world_agent",
        instruction="You are a Math agent that can do multiplication and addition with the tools",
        tools=[add, multiply],
    )


@register_agent(AgentType.FLOW_WITH_AGENT_STEP)
def get_flow_with_agent_step() -> Flow:
    agent = get_agent_with_server_tool()

    user_input_step = InputMessageStep(
        name="user_input_step",
        message_template="",
    )

    agent_step = AgentExecutionStep(
        name="agent",
        agent=agent,
    )

    flow = Flow(
        begin_step=user_input_step,
        control_flow_edges=[
            ControlFlowEdge(user_input_step, agent_step),
            ControlFlowEdge(agent_step, CompleteStep()),
        ],
    )

    return flow


@register_agent(AgentType.FLOW_WITH_AGENT_STEP_THAT_YIELDS_ONCE)
def get_flow_with_agent_step_that_yields_once() -> Flow:
    agent = Agent(llm=llm, can_finish_conversation=True)

    agent_step = AgentExecutionStep(
        name="agent_step",
        agent=agent,
        caller_input_mode=CallerInputMode.NEVER,
        output_descriptors=[StringProperty(name="output")],
    )

    user_output_step = OutputMessageStep(
        name="user_output_step", input_mapping={"message": "output"}
    )

    flow = Flow.from_steps([agent_step, user_output_step])
    return flow


@register_agent(AgentType.FLOW_THAT_WITH_INPUT_STEP_YIELDS_ONCE)
def get_flow_with_input_step_that_yields_once() -> Flow:
    @tool
    def hello_tool(name: Annotated[str, "user name"]) -> str:
        "Return hello"
        return f"Hello {name}!"

    user_input_step = InputMessageStep(name="user_input_step", message_template="")
    hello_step = ToolExecutionStep(name="hello_step", tool=hello_tool)
    user_output_step = OutputMessageStep(name="user_output_step", message_template="{{ output }}")

    flow = Flow(
        begin_step=user_input_step,
        control_flow_edges=[
            ControlFlowEdge(user_input_step, hello_step),
            ControlFlowEdge(hello_step, user_output_step),
            ControlFlowEdge(user_output_step, CompleteStep()),
        ],
        data_flow_edges=[
            DataFlowEdge(user_input_step, InputMessageStep.USER_PROVIDED_INPUT, hello_step, "name"),
            DataFlowEdge(hello_step, ToolExecutionStep.TOOL_OUTPUT, user_output_step, "output"),
        ],
    )

    return flow


@register_agent(AgentType.AGENT_WITH_VISION_CAPABILITY)
def get_agent_with_vision_capability() -> Agent:
    llm = VllmModel(
        host_port=os.environ.get("GEMMA_API_URL"),
        model_id="google/gemma-3-27b-it",
    )
    agent = Agent(
        llm=llm,
        custom_instruction="You are an agent that can answer questions about input images.",
        description="Agent can handle images",
    )

    return agent


@register_agent(AgentType.MANAGER_WORKERS)
def get_managerworkers() -> ManagerWorkers:
    manager = Agent(llm=llm, name="manager")
    worker = Agent(llm=llm, name="worker", description="worker agent")

    return ManagerWorkers(
        group_manager=manager,
        workers=[worker],
    )


@register_agent(AgentType.SWARM)
def get_swarm() -> Swarm:
    first_agent = Agent(llm=llm, name="first_agent")
    second_agent = Agent(llm=llm, name="second_agent", description="second agent")

    return Swarm(first_agent=first_agent, relationships=[(first_agent, second_agent)])


@register_agent(AgentType.SAMPLE_AGENT)
def get_sample_agent() -> Agent:
    @tool
    def sample_number(a: Annotated[int, "upper bound for random selection"]) -> int:
        "Simulate sampling a random number between 1 and the specified upper bound."
        import random

        result = random.randint(1, a)
        return result

    agent = Agent(
        llm=llm,
        name="sample_agent",
        custom_instruction="You are an agent that can generate a random number between 1 and a specified value.",
        tools=[sample_number],
        can_finish_conversation=True,
    )
    return agent


@register_agent(AgentType.PRIME_AGENT)
def get_prime_agent() -> Agent:
    @tool
    def check_prime(a: Annotated[int, "first required integer"]) -> bool:
        "Check if the input number is a prime number."
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


# ============== Server ==============
def create_server(agent_type: AgentType, host: str, port: int):
    """Create and configure the A2A server"""
    agent = AGENT_FACTORIES.get(agent_type.value)()
    server = A2AServer()
    server.serve_agent(agent=agent, url=f"http://{host}:{port}")
    return server


# google-adk warnings
@pytest.mark.filterwarnings("ignore::UserWarning")
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.filterwarnings("ignore::FutureWarning")
def main(host: str, port: int, agent_type: AgentType):
    if agent_type == AgentType.ADK_AGENT:
        from a2a.types import AgentCard
        from google.adk.a2a.utils.agent_to_a2a import to_a2a

        my_agent_card = AgentCard(
            **{
                "name": "file_agent",
                "url": "http://example.com",
                "description": "Test agent from file",
                "version": "1.0.0",
                "capabilities": {},
                "skills": [],
                "defaultInputModes": ["text/plain"],
                "defaultOutputModes": ["text/plain"],
                "supportsAuthenticatedExtendedCard": False,
            }
        )
        agent = AGENT_FACTORIES.get(agent_type.value)()
        a2a_app = to_a2a(agent, port=port, agent_card=my_agent_card)
        uvicorn.run(a2a_app, host=host, port=port)
    else:
        server = create_server(agent_type=agent_type, host=host, port=port)
        print(f"Starting A2A server on http://{host}:{port}")
        server.run(host=host, port=port)
        print("A2A server has stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start an A2A server for testing.")
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help='The host address (e.g., "localhost" or "127.0.0.1")',
    )
    parser.add_argument("--port", type=int, default=8000, help="The port number (e.g., 8000)")
    parser.add_argument(
        "--agent",
        type=AgentType,
        default=AgentType.AGENT_WITH_SERVER_TOOL,
        choices=list(AgentType),
        help="Which agent to serve",
    )
    args = parser.parse_args()
    main(host=args.host, port=args.port, agent_type=args.agent)
