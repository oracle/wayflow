# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from typing import Annotated

from wayflowcore.agent import Agent
from wayflowcore.contextproviders.constantcontextprovider import ConstantContextProvider
from wayflowcore.messagelist import MessageType
from wayflowcore.property import StringProperty
from wayflowcore.tools import tool

from ..testhelpers.testhelpers import retry_test

logger = logging.getLogger(__name__)


@tool
def fooza_tool(
    a: Annotated[int, "first required integer"], b: Annotated[int, "second required integer"]
) -> int:
    """Return the result of the fooza operation between numbers a and b."""
    return a * 2 + b * 3 - 1


@tool
def zinimo_tool(
    a: Annotated[int, "first required integer"], b: Annotated[int, "second required integer"]
) -> int:
    """Return the result of the zinimo operation between numbers a and b. Both inputs are required."""
    return a - b + 1


def _get_fooza_zinimo_assistant(remotely_hosted_llm):
    llm = remotely_hosted_llm

    return Agent(
        custom_instruction="""The functions you have access to allows you to call experts. Use JSON to formulate function calls. Always rephrase the expert's answers to the user""",
        llm=llm,
        agent_id="master",
        agents=[
            Agent(
                custom_instruction="You are a fooza operation specialist. Answer the user requests about the fooza operation, and their request only (do not attempt to solve unrelated tasks). The fooza operation is a linear transformation, designed by Mr. Fooza. Only tackle the requests you are specialized to tackle, and let other agents take care of the rest.",
                llm=llm,
                tools=[fooza_tool],
                agent_id="fooza_expert",
                name="request_fooza_expert_help",
                description="Delegate tasks to an agent that can compute any operations related with the fooza operation",
            ),
            Agent(
                custom_instruction="You are a zinimo operation specialist. Answer the user requests about the zinimo operation, and their request only (do not attempt to solve unrelated tasks). The zinimo operation is a linear transformation, designed by Mr. Zinimo. Only tackle the requests you are specialized to tackle, and let other agents take care of the rest.",
                llm=llm,
                tools=[zinimo_tool],
                agent_id="zinimo_expert",
                name="request_zinimo_expert_help",
                description="Delegate tasks to an agent that can compute any operations related with the zinimo operation",
            ),
        ],
        max_iterations=4,
    )


@retry_test(max_attempts=4)
def test_simple_end_to_endcomposability(big_llama):
    """
    Failure rate:          0 out of 10
    Observed on:           2024-12-19
    Average success time:  8.74 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    assistant = _get_fooza_zinimo_assistant(big_llama)
    conversation = assistant.start_conversation()
    conversation.append_user_message("compute the result the zinimo operation of 4 and 5")
    conversation.execute()
    last_message = conversation.get_last_message().content
    assert any([x in last_message for x in ["0", "zero"]])


@retry_test(max_attempts=4)
def test_agent_with_subagent_with_whitespace_in_name_correctly_executes(big_llama):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-10-27
    Average success time:  3.87 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """

    from wayflowcore.templates import NATIVE_AGENT_TEMPLATE

    agent = Agent(
        custom_instruction="""The functions you have access to allows you to call experts. Use JSON to formulate function calls. Always rephrase the expert's answers to the user""",
        llm=big_llama,
        name="master",
        agents=[
            Agent(
                custom_instruction="You are a fooza operation specialist. Answer the user requests about the fooza operation, and their request only (do not attempt to solve unrelated tasks). The fooza operation is a linear transformation, designed by Mr. Fooza. Only tackle the requests you are specialized to tackle, and let other agents take care of the rest.",
                llm=big_llama,
                tools=[fooza_tool],
                agent_id="fooza_expert",
                name="Expert of Fooza Ops",
                description="Delegate tasks to an agent that can compute any operations related with the fooza operation",
            ),
        ],
        agent_template=NATIVE_AGENT_TEMPLATE,
        max_iterations=4,
    )
    conversation = agent.start_conversation()
    conversation.append_user_message("compute the result the fooza operation of 4 and 5")
    conversation.execute()

    assert any(
        message.message_type == MessageType.TOOL_REQUEST
        and message.tool_requests  # has tool requests
        and message.tool_requests[0].name == "Expert_of_Fooza_Ops"  # transformed name
        and set(message.tool_requests[0].args.keys()) == {"context"}
        for message in conversation.get_messages()
    )


@retry_test(max_attempts=4)
def test_agents_provide_inputs_to_subagent(big_llama):
    """
    Test added for the bug. Error was "ValueError: Missing some contextual variables in conversation, {}, {'user_request'}"

    Failure rate:          0 out of 20
    Observed on:           2026-01-21
    Average success time:  7.92 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    llm = big_llama

    coding_agent = Agent(
        name="CoderAgent",
        description="Coding Expert Agent to call when facing coding questions/requests.",
        llm=llm,
        custom_instruction="You are a Coding Expert LLM Agent, please answer the following user request {{user_request}}",
    )
    parent_agent = Agent(
        name="ManagerAgent",
        description="Manager Agent",
        llm=llm,
        custom_instruction="You are a helpful LLM assistant, please use the experts at your disposal to answer user queries",
        agents=[coding_agent],
    )
    conversation = parent_agent.start_conversation()
    conversation.append_user_message(
        "I have a coding question: Explain to me in one sentence what `inspect.getframeinfo` enables."
    )
    conversation.execute()
    assert any(
        message.message_type == MessageType.TOOL_REQUEST
        and message.tool_requests  # has tool requests
        and message.tool_requests[0].name == "CoderAgent"  # correct agent name
        and set(message.tool_requests[0].args.keys())
        == {"context", "user_request"}  # correct inputs
        for message in conversation.get_messages()
    )


def test_subagent_does_not_expose_contextprovider_data_in_inputs(big_llama):
    """
    Test added.
    """
    llm = big_llama

    sub_agent = Agent(
        name="sub_agent",
        description="my sub agent",
        llm=llm,
        custom_instruction="{{variable_that_should_not_be_exposed}} {{variable_that_should_be_exposed}}",
        context_providers=[
            ConstantContextProvider(
                value="value",
                output_description=StringProperty(name="variable_that_should_not_be_exposed"),
            )
        ],
    )
    parent_agent = Agent(
        llm=llm,
        agents=[sub_agent],
    )

    sub_agent_tool = next(
        (tool_ for tool_ in parent_agent._all_static_tools if tool_.name == "sub_agent"), None
    )

    assert sub_agent_tool
    assert "variable_that_should_not_be_exposed" not in sub_agent_tool.parameters
    assert "variable_that_should_be_exposed" in sub_agent_tool.parameters


def test_subagent_cannot_use_values_from_parent_contextproviders(big_llama):
    """
    Context providers from the parent component should not be used to fill prompt templates of a sub-component
    """
    llm = big_llama

    sub_agent = Agent(
        name="sub_agent",
        description="Sub Agent to call to delegate tasks.",
        llm=llm,
        custom_instruction="{{variable}}",
    )
    parent_agent = Agent(
        llm=llm,
        agents=[sub_agent],
        context_providers=[
            ConstantContextProvider(
                value="value", output_description=StringProperty(name="variable")
            )
        ],
    )

    sub_agent_tool = next(
        (tool_ for tool_ in parent_agent._all_static_tools if tool_.name == "sub_agent"), None
    )

    assert sub_agent_tool
    assert "variable" in sub_agent_tool.parameters


def test_warning_is_raised_when_missing_property_description_in_subagent_inputs(recwarn, big_llama):
    # see https://docs.pytest.org/en/stable/how-to/capture-warnings.html#recwarn
    llm = big_llama
    sub_agent = Agent(
        name="sub_agent",
        description="Sub Agent to call to delegate tasks.",
        llm=llm,
        custom_instruction="{{variable}}",
    )
    parent_agent = Agent(
        llm=llm,
        agents=[sub_agent],
    )

    sub_agent_tool = next(
        (tool_ for tool_ in parent_agent._all_static_tools if tool_.name == "sub_agent"), None
    )

    assert sub_agent_tool
    assert len(recwarn) > 0
    warning_record = recwarn.pop(UserWarning)
    assert "Input with name 'variable' for agent 'sub_agent' uses a default description." in str(
        warning_record.message
    )


def test_warning_is_not_raised_when_property_have_description_in_subagent_inputs(
    recwarn, big_llama
):
    # see https://docs.pytest.org/en/stable/how-to/capture-warnings.html#recwarn
    llm = big_llama
    sub_agent = Agent(
        name="sub_agent",
        description="Sub Agent to call to delegate tasks.",
        llm=llm,
        custom_instruction="{{variable}}",
        input_descriptors=[
            StringProperty(name="variable", description="Description of the variable")
        ],
    )
    parent_agent = Agent(
        llm=llm,
        agents=[sub_agent],
    )

    assert not any(
        "Input with name 'variable' for agent 'sub_agent' uses a default description."
        in str(warning_record.message)
        for warning_record in recwarn
    )
