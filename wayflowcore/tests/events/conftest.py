# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Type, Union

from wayflowcore.agent import Agent
from wayflowcore.events.event import Event
from wayflowcore.events.eventlistener import EventListener, GenericEventListener
from wayflowcore.executors._agentexecutor import (
    EXIT_CONVERSATION_CONFIRMATION_MESSAGE,
    EXIT_CONVERSATION_TOOL_NAME,
)
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.steps.outputmessagestep import OutputMessageStep
from wayflowcore.tools.clienttools import ClientTool
from wayflowcore.tools.flowbasedtools import DescribedFlow
from wayflowcore.tools.servertools import ServerTool
from wayflowcore.tools.tools import ToolRequest

from ..testhelpers.dummy import DummyModel

if TYPE_CHECKING:
    from wayflowcore.flow import Flow


@dataclass(frozen=True)
class MyCustomEvent(Event):
    pass


class MyCustomEventListener(EventListener):

    def __init__(self):
        self.triggered_events: List[Event] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, MyCustomEvent):
            self.triggered_events.append(event)


def create_generic_event_listener_with_list_of_triggered_events(
    event_classes: Optional[List[Type[Event]]] = None,
) -> Tuple[EventListener, List[Event]]:

    triggered_events: List[Event] = []

    def _inner_function(event: Event) -> None:
        triggered_events.append(event)

    return (
        GenericEventListener(
            event_classes=event_classes or [MyCustomEvent],
            function=_inner_function,
        ),
        triggered_events,
    )


def count_agents_and_flows_in_agent(agent: "Agent") -> int:
    return sum(1 + count_agents_and_flows_in_agent(sub_agent) for sub_agent in agent.agents) + sum(
        1 + count_agents_and_flows_in_flow(sub_flow) for sub_flow in agent.flows
    )


def count_agents_and_flows_in_flow(flow: "Flow") -> int:
    from wayflowcore.agent import Agent
    from wayflowcore.flow import Flow

    num_flows_and_agents = 0
    for step in flow.steps.values():
        for step_config_name, step_config in step.get_static_configuration_descriptors().items():
            if step_config == Flow:
                num_flows_and_agents += 1 + count_agents_and_flows_in_flow(
                    getattr(step, step_config_name)
                )
            elif step_config == Agent:
                num_flows_and_agents += 1 + count_agents_and_flows_in_agent(
                    getattr(step, step_config_name)
                )
    return num_flows_and_agents


def create_dummy_llm_with_next_output(
    next_output: Union[
        str, List[str], Dict[Optional[str], str], Message, Dict[Optional[str], Message]
    ],
) -> DummyModel:
    llm = DummyModel()
    llm.set_next_output(next_output)
    return llm


GET_LOCATION_CLIENT_TOOL = ClientTool(
    name="get_location",
    description="Search the location of a given company",
    parameters={
        "company_name": {
            "type": "string",
            "description": "Name of the company to search the location for",
            "default": "Oracle",
        },
    },
)

GET_LOCATION_CLIENT_TOOL_WITH_CONFIRMATION = ClientTool(
    name="get_location",
    description="Search the location of a given company",
    parameters={
        "company_name": {
            "type": "string",
            "description": "Name of the company to search the location for",
            "default": "Oracle",
        },
    },
    requires_confirmation=True,
)

GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION = ServerTool(
    name="get_location",
    description="Search the location of a given company",
    func=lambda company_name: company_name,
    parameters={
        "company_name": {
            "type": "string",
            "description": "Name of the company to search the location for",
            "default": "Oracle",
        },
    },
    requires_confirmation=True,
)

# NOTE: The following dummy agents work for multiple tests because they're configured using a dictionary, which doesn't get cleared and works for all iterations

DUMMY_AGENT_WITH_GET_LOCATION_TOOL = Agent(
    agent_id="a123",
    custom_instruction="Be polite",
    llm=create_dummy_llm_with_next_output(
        {
            "Please use the tool": Message(
                tool_requests=[
                    ToolRequest(
                        name=GET_LOCATION_CLIENT_TOOL.name,
                        args={"company_name": "Oracle Labs"},
                        tool_request_id="tool_request_id_1",
                    )
                ],
                message_type=MessageType.TOOL_REQUEST,
                sender="a123",
                recipients={"a123"},
            )
        }
    ),
    tools=[GET_LOCATION_CLIENT_TOOL],
)

DUMMY_AGENT_WITH_GET_LOCATION_TOOL_WITH_CONFIRMATION = Agent(
    agent_id="a123",
    custom_instruction="Be polite",
    llm=create_dummy_llm_with_next_output(
        {
            "Please use the tool": Message(
                tool_requests=[
                    ToolRequest(
                        name=GET_LOCATION_CLIENT_TOOL_WITH_CONFIRMATION.name,
                        args={"company_name": "Oracle Labs"},
                        tool_request_id="tool_request_id_1",
                    )
                ],
                message_type=MessageType.TOOL_REQUEST,
                sender="a123",
                recipients={"a123"},
            )
        }
    ),
    tools=[GET_LOCATION_CLIENT_TOOL_WITH_CONFIRMATION],
)

DUMMY_AGENT_WITH_SERVER_TOOL = Agent(
    agent_id="a123",
    custom_instruction="Be polite",
    llm=create_dummy_llm_with_next_output(
        {
            "Please use the tool": Message(
                tool_requests=[
                    ToolRequest(
                        name=GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION.name,
                        args={"company_name": "Oracle Labs"},
                        tool_request_id="tool_request_id_2",
                    )
                ],
                message_type=MessageType.TOOL_REQUEST,
                sender="a123",
                recipients={"a123"},
            )
        }
    ),
    tools=[GET_LOCATION_SERVER_TOOL_WITH_CONFIRMATION],
)

"""Do not modify this variable in place"""

DUMMY_AGENT_WITH_CONVERSATION_EXIT = Agent(
    agent_id="a123",
    custom_instruction="Be polite",
    llm=create_dummy_llm_with_next_output(
        {
            "I'm done, you can exit": Message(
                tool_requests=[
                    ToolRequest(
                        name=EXIT_CONVERSATION_TOOL_NAME,
                        args={},
                        tool_request_id="tool_request_id_1",
                    )
                ],
                message_type=MessageType.TOOL_REQUEST,
                sender="a123",
                recipients={"a123"},
            ),
            EXIT_CONVERSATION_CONFIRMATION_MESSAGE: Message(
                tool_requests=[
                    ToolRequest(
                        name=EXIT_CONVERSATION_TOOL_NAME,
                        args={},
                        tool_request_id="tool_request_id_2",
                    )
                ],
                message_type=MessageType.TOOL_REQUEST,
                sender="a123",
                recipients={"a123"},
            ),
        },
    ),
    can_finish_conversation=True,
)
"""Do not modify this variable in place"""

DUMMY_AGENT_WITH_GET_LOCATION_FLOW_AS_TOOL = Agent(
    agent_id="a123",
    custom_instruction="Be polite",
    llm=create_dummy_llm_with_next_output(
        {
            "Please use the tool": Message(
                tool_requests=[
                    ToolRequest(
                        name=GET_LOCATION_CLIENT_TOOL.name,
                        args={},
                        tool_request_id="tool_request_id_1",
                    )
                ],
                message_type=MessageType.TOOL_REQUEST,
                sender="a123",
                recipients={"a123"},
            ),
            "In shore X": Message(
                content="The company is in shore X",
                message_type=MessageType.AGENT,
            ),
        },
    ),
    flows=[
        DescribedFlow(
            name=GET_LOCATION_CLIENT_TOOL.name,
            description="Use this flow to get location of a company",
            flow=create_single_step_flow(step=OutputMessageStep("In shore X")),
        )
    ],
)
"""Do not modify this variable in place"""
