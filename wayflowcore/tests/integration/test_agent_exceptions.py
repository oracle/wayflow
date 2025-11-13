# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest

from wayflowcore import Agent
from wayflowcore.flow import Flow
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.models import LlmModel
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.swarm import Swarm
from wayflowcore.tools import ServerTool, ToolRequest, tool

from ..testhelpers.patching import patch_llm

ERROR_MESSAGE = "Error in tool execution"


@tool
def dummy_tool() -> None:
    """Return error"""
    raise ValueError(ERROR_MESSAGE)


TOOL_REQUEST = [ToolRequest(name="dummy_tool", args={}, tool_request_id="123")]
FLOW_REQUEST = [ToolRequest(name="dummy_flow", args={}, tool_request_id="124")]
AGENT_REQUEST = [ToolRequest(name="sub_agent", args={}, tool_request_id="125")]


def agent_with_error_tool(raise_exceptions: bool, llm: LlmModel) -> Agent:
    return Agent(llm=llm, tools=[dummy_tool], raise_exceptions=raise_exceptions)


def agent_with_error_sub_flow(raise_exceptions: bool, llm: LlmModel) -> Agent:
    tool_step = ToolExecutionStep(tool=dummy_tool)
    flow = Flow.from_steps([tool_step], name="dummy_flow")  # Execute this flow will raise error

    return Agent(llm=llm, flows=[flow], raise_exceptions=raise_exceptions)


def agent_with_error_sub_agent(raise_exceptions: bool, llm: LlmModel) -> Agent:
    sub_agent = agent_with_error_tool(
        raise_exceptions=True, llm=llm
    )  # Execute this agent will raise error
    sub_agent.name = "sub_agent"
    sub_agent.description = "sub agent"

    return Agent(llm=llm, agents=[sub_agent], raise_exceptions=raise_exceptions)


def swarm_with_error_first_agent(raise_exceptions: bool, llm: LlmModel) -> Swarm:
    first_agent = Agent(
        llm=llm,
        tools=[dummy_tool],
        description="First agent",
        raise_exceptions=raise_exceptions,
    )

    second_agent = Agent(
        llm=llm,
        description="Second agent",
    )

    return Swarm(
        first_agent=first_agent,
        relationships=[(first_agent, second_agent)],
    )


def managerworkers_with_error_manager_agent(
    raise_exceptions: bool, llm: LlmModel
) -> ManagerWorkers:
    group_manager = Agent(
        llm=llm,
        tools=[dummy_tool],
        description="First agent",
        raise_exceptions=raise_exceptions,
    )

    worker = Agent(
        llm=llm,
        description="Second agent",
    )

    return ManagerWorkers(group_manager=group_manager, workers=[worker])


def agent_with_tool_returning_uncopyable_output(raise_exceptions: bool, llm: LlmModel):
    from wayflowcore.property import ObjectProperty

    class UncopyableObject:
        def __deepcopy__(self, memo):
            raise TypeError("Cannot copy this object")

    tool = ServerTool(
        name="return_uncopyable_output",
        description="Return object that cannot be copied",
        input_descriptors=[],
        output_descriptors=[
            ObjectProperty(name="a", description="returned object"),
        ],
        func=(lambda: UncopyableObject()),
    )

    return Agent(tools=[tool], llm=llm, raise_exceptions=raise_exceptions)


def test_agent_raises_tool_exceptions_with_raise_exceptions(remotely_hosted_llm):
    llm = remotely_hosted_llm
    agent = agent_with_error_tool(raise_exceptions=True, llm=llm)

    conv = agent.start_conversation()
    conv.append_user_message("Dummy")

    with patch_llm(llm, outputs=[TOOL_REQUEST]):
        with pytest.raises(ValueError, match=ERROR_MESSAGE):
            conv.execute()


def test_agent_absorbs_tool_exceptions_without_raise_exceptions(remotely_hosted_llm):
    llm = remotely_hosted_llm
    agent = agent_with_error_tool(raise_exceptions=False, llm=llm)

    conv = agent.start_conversation()
    conv.append_user_message("Dummy")

    with patch_llm(llm, outputs=[TOOL_REQUEST, "Dummy"]):
        conv.execute()
    assert any(
        message.tool_requests and message.tool_requests[0].name == "dummy_tool"
        for message in conv.get_messages()
    )


def test_agent_raises_sub_flow_exceptions_with_raise_exceptions(remotely_hosted_llm):
    llm = remotely_hosted_llm
    agent = agent_with_error_sub_flow(raise_exceptions=True, llm=llm)

    conv = agent.start_conversation()
    conv.append_user_message("Dummy")

    with patch_llm(llm, outputs=[FLOW_REQUEST]):
        with pytest.raises(ValueError, match=ERROR_MESSAGE):
            conv.execute()


def test_agent_absorbs_sub_flow_exceptions_without_raise_exceptions(remotely_hosted_llm):
    llm = remotely_hosted_llm
    agent = agent_with_error_sub_flow(raise_exceptions=False, llm=llm)

    conv = agent.start_conversation()
    conv.append_user_message("Dummy")

    with patch_llm(llm, outputs=[FLOW_REQUEST, "Dummy"]):
        conv.execute()
    assert any(
        message.tool_requests and message.tool_requests[0].name == "dummy_flow"
        for message in conv.get_messages()
    )


def test_agent_raises_sub_agent_exceptions_with_raise_exceptions(remotely_hosted_llm):
    llm = remotely_hosted_llm
    agent = agent_with_error_sub_agent(raise_exceptions=True, llm=llm)

    conv = agent.start_conversation()
    conv.append_user_message("Dummy")

    with patch_llm(llm, outputs=[AGENT_REQUEST, TOOL_REQUEST]):
        with pytest.raises(ValueError, match=ERROR_MESSAGE):
            conv.execute()


def test_agent_absorbs_sub_agent_exceptions_without_raise_exceptions(remotely_hosted_llm):
    llm = remotely_hosted_llm
    agent = agent_with_error_sub_agent(raise_exceptions=False, llm=llm)

    conv = agent.start_conversation()
    conv.append_user_message("Dummy")

    with patch_llm(llm, outputs=[AGENT_REQUEST, TOOL_REQUEST, "Dummy"]):
        conv.execute()
    assert any(
        message.tool_requests and message.tool_requests[0].name == "sub_agent"
        for message in conv.get_messages()
    )


def test_swarm_raises_first_agent_exception_when_first_agent_raise_exceptions_true(
    remotely_hosted_llm,
):
    llm = remotely_hosted_llm
    swarm = swarm_with_error_first_agent(raise_exceptions=True, llm=llm)

    conv = swarm.start_conversation()
    conv.append_user_message("Dummy")

    with patch_llm(llm, [TOOL_REQUEST]):
        with pytest.raises(ValueError, match=ERROR_MESSAGE):
            conv.execute()


def test_swarm_absorbs_first_agent_error_when_first_agent_raise_exceptions_false(
    remotely_hosted_llm,
):
    llm = remotely_hosted_llm
    swarm = swarm_with_error_first_agent(raise_exceptions=False, llm=llm)

    conv = swarm.start_conversation()
    conv.append_user_message("Dummy")

    with patch_llm(llm, [TOOL_REQUEST, "Dummy"]):
        conv.execute()


def test_managerworkers_raises_manager_agent_exception_when_manager_agent_raise_exceptions_true(
    remotely_hosted_llm,
):
    llm = remotely_hosted_llm
    group = managerworkers_with_error_manager_agent(raise_exceptions=True, llm=llm)

    conv = group.start_conversation()
    conv.append_user_message("Dummy")

    with patch_llm(llm, [TOOL_REQUEST]):
        with pytest.raises(ValueError, match=ERROR_MESSAGE):
            conv.execute()


def test_managerworkers_absorbs_manager_agent_error_when_manager_agent_raise_exceptions_false(
    remotely_hosted_llm,
):
    llm = remotely_hosted_llm
    group = managerworkers_with_error_manager_agent(raise_exceptions=False, llm=llm)

    conv = group.start_conversation()
    conv.append_user_message("Dummy")

    with patch_llm(llm, [TOOL_REQUEST, "Dummy"]):
        conv.execute()


def test_agent_raises_for_uncopyable_tool_result_with_raise_exceptions(remotely_hosted_llm):
    llm = remotely_hosted_llm
    agent = agent_with_tool_returning_uncopyable_output(raise_exceptions=True, llm=llm)

    conv = agent.start_conversation()
    conv.append_user_message("Hello")

    with patch_llm(
        llm, [[ToolRequest(name="return_uncopyable_output", args={}, tool_request_id="123")]]
    ):
        with pytest.raises(TypeError, match="Tool output is not copyable"):
            conv.execute()


def test_agent_warns_for_uncopyable_tool_result_without_raise_exceptions(remotely_hosted_llm):
    llm = remotely_hosted_llm
    agent = agent_with_tool_returning_uncopyable_output(raise_exceptions=False, llm=llm)

    conv = agent.start_conversation()
    conv.append_user_message("Hello")

    with patch_llm(
        llm, [[ToolRequest(name="return_uncopyable_output", args={}, tool_request_id="123")]]
    ):
        with pytest.raises(UserWarning, match="Tool output is not copyable"):
            conv.execute()
