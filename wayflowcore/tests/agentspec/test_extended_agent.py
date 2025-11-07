# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


from pyagentspec.agent import Agent
from pyagentspec.llms import VllmConfig

from wayflowcore import Agent as WayflowAgent
from wayflowcore.agent import CallerInputMode
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.agentspec.components.agent import ExtendedAgent
from wayflowcore.models import VllmModel


def test_agent_is_converted_correctly() -> None:

    from pyagentspec.property import IntegerProperty, StringProperty

    agent = Agent(
        name="agent",
        llm_config=VllmConfig(name="llm", url="http://my.url", model_id="my.llm"),
        system_prompt="What is the fastest italian car?",
        outputs=[
            StringProperty(title="brand", description="The brand of the car"),
            StringProperty(title="model", description="The name of the car's model"),
            IntegerProperty(
                title="hp", description="The horsepower amount, which expresses the car's power"
            ),
        ],
    )
    wayflow_agent = AgentSpecLoader().load_component(agent)
    assert isinstance(wayflow_agent, WayflowAgent)
    assert len(wayflow_agent.output_descriptors) == 3


def test_agent_is_serialized_correctly() -> None:

    from wayflowcore.property import IntegerProperty, StringProperty

    agent = WayflowAgent(
        llm=VllmModel(model_id="my.llm", host_port="http://my.url"),
        custom_instruction="What is the fastest italian car?",
        initial_message=None,
        output_descriptors=[
            StringProperty(name="brand", description="The brand of the car"),
            StringProperty(name="model", description="The name of the car's model"),
            IntegerProperty(
                name="hp", description="The horsepower amount, which expresses the car's power"
            ),
        ],
    )
    agentspec_agent = AgentSpecExporter().to_component(agent)
    assert isinstance(agentspec_agent, Agent)
    assert not isinstance(agentspec_agent, ExtendedAgent)
    assert len(agentspec_agent.outputs or []) == 3
    assert agentspec_agent.system_prompt == agent.custom_instruction


def test_extended_agent_is_serialized_correctly() -> None:

    from wayflowcore.property import IntegerProperty, StringProperty

    agent = WayflowAgent(
        llm=VllmModel(model_id="my.llm", host_port="http://my.url"),
        initial_message=None,
        custom_instruction="What is the fastest italian car?",
        caller_input_mode=CallerInputMode.NEVER,
        output_descriptors=[
            StringProperty(name="brand", description="The brand of the car"),
            StringProperty(name="model", description="The name of the car's model"),
            IntegerProperty(
                name="hp", description="The horsepower amount, which expresses the car's power"
            ),
        ],
    )
    agentspec_agent = AgentSpecExporter().to_component(agent)
    assert isinstance(agentspec_agent, ExtendedAgent)
    assert len(agentspec_agent.outputs or []) == 3
    assert agentspec_agent.system_prompt == agent.custom_instruction
    assert agentspec_agent.caller_input_mode == agent.caller_input_mode
