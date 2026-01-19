# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from copy import deepcopy
from dataclasses import dataclass, fields
from typing import Sequence, cast

import pytest

from wayflowcore import Message, MessageType, Tool, __version__
from wayflowcore.agent import Agent
from wayflowcore.executors._agentconversation import AgentConversation
from wayflowcore.executors._agentexecutor import AgentConversationExecutionState
from wayflowcore.executors._flowconversation import FlowConversation
from wayflowcore.executors._flowexecutor import (
    FlowConversationExecutionState,
    FlowConversationExecutor,
)
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.executors.interrupts.timeoutexecutioninterrupt import SoftTimeoutExecutionInterrupt
from wayflowcore.executors.interrupts.tokenlimitexecutioninterrupt import (
    SoftTokenLimitExecutionInterrupt,
)
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.messagelist import ImageContent, TextContent
from wayflowcore.models import LlmModelFactory
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.serialization import autodeserialize, deserialize, serialize
from wayflowcore.serialization.context import DeserializationContext
from wayflowcore.serialization.serializer import SerializableDataclass, SerializableObject
from wayflowcore.steps import (
    FlowExecutionStep,
    InputMessageStep,
    OutputMessageStep,
    PromptExecutionStep,
    ToolExecutionStep,
)
from wayflowcore.swarm import Swarm
from wayflowcore.tools import (
    ClientTool,
    DescribedFlow,
    ServerTool,
    ToolBox,
    ToolRequest,
    ToolResult,
    register_server_tool,
)

from ..conftest import VLLM_MODEL_CONFIG
from ..testhelpers.dummy import DummyModel
from ..testhelpers.patching import patch_llm
from ..testhelpers.serialization import make_deserialization_plugin, make_serialization_plugin
from ..testhelpers.testhelpers import retry_test
from .test_assistant_serialization import add_number_tool, agent, create_agent, flow  # noqa


def assert_flow_conversations_are_equal(conv1: FlowConversation, conv2: FlowConversation) -> None:
    if conv1 is None and conv2 is None:
        return

    assert conv1.message_list.messages == conv1.message_list.messages

    assert conv1.id == conv2.id

    assert isinstance(conv1.state, FlowConversationExecutionState)
    assert isinstance(conv2.state, FlowConversationExecutionState)

    assert conv1.status == conv2.status

    state_1 = {field.name: getattr(conv1.state, field.name) for field in fields(conv1.state)}
    state_2 = {field.name: getattr(conv2.state, field.name) for field in fields(conv2.state)}

    # same flow
    assert set(state_1.pop("flow").steps.keys()) == set(state_2.pop("flow").steps.keys())
    # same context providers
    # same context values
    state_context_dict_1 = state_1.pop("internal_context_key_values")
    state_context_dict_2 = state_2.pop("internal_context_key_values")
    assert set(state_context_dict_1.keys()) == set(state_context_dict_2.keys())
    for context_key in state_context_dict_1.keys():
        if context_key == FlowConversationExecutor._SUPER_CONVERSATION_KEY:
            # skip otherwise it's infinitely recursive
            pass
        elif FlowConversationExecutor._SUB_CONVERSATION_KEY in context_key:
            assert_flow_conversations_are_equal(
                state_context_dict_1[context_key], state_context_dict_2[context_key]
            )
        else:
            assert state_context_dict_1[context_key] == state_context_dict_2[context_key]

    state_1.pop("interrupts", None)
    state_2.pop("interrupts", None)
    state_1.pop("events", None)
    state_2.pop("events", None)
    assert state_1 == state_2


def assert_agent_conversations_are_equal(
    conv1: AgentConversation, conv2: AgentConversation
) -> None:
    assert conv1.message_list.messages == conv1.message_list.messages

    assert conv1.status == conv2.status
    assert conv1.id == conv2.id

    assert len(conv1.component.tools) == len(conv2.component.tools)

    assert len(conv1.agent.tools) == len(conv2.agent.tools)

    assert isinstance(conv1.state, AgentConversationExecutionState)
    assert isinstance(conv2.state, AgentConversationExecutionState)

    state_1 = {field.name: getattr(conv1.state, field.name) for field in fields(conv1.state)}
    state_2 = {field.name: getattr(conv2.state, field.name) for field in fields(conv2.state)}

    assert state_1.pop("plan") == state_2.pop("plan")

    assert_flow_conversations_are_equal(
        state_1.pop("current_flow_conversation"), state_2.pop("current_flow_conversation")
    )

    state_1.pop("interrupts", None)
    state_2.pop("interrupts", None)
    state_1.pop("events", None)
    state_2.pop("events", None)
    state_1.pop("current_retrieved_tools", None)
    state_2.pop("current_retrieved_tools", None)
    assert state_1 == state_2


def test_serialize_agent_conversation(
    agent: Agent,
) -> None:
    conversation = agent.start_conversation()
    conversation.execute()
    # first message of conversation should be a hardcoded one
    assert "Hi! How can I help you?" == conversation.get_last_message().content

    conversation.append_user_message("what is 2 + 2?")

    serialized_conversation = serialize(conversation)
    deserialization_context = DeserializationContext()
    register_server_tool(add_number_tool, deserialization_context.registered_tools)

    deserialized_conv = cast(
        AgentConversation,
        deserialize(
            AgentConversation,
            serialized_conversation,
            deserialization_context=deserialization_context,
        ),
    )
    deserialized_conv.execute()
    # should continue the conversation, ie second message is not hardcoded
    assert "Hi! How can I help you?" != deserialized_conv.get_last_message().content


def test_serialize_flow_with_subflows_conversation(
    flow: Flow,
) -> None:

    subflow_step = FlowExecutionStep(flow)
    single_step_flow = create_single_step_flow(subflow_step)

    conversation = single_step_flow.start_conversation()
    status = conversation.execute()
    # first message of conversation should be the usermessage yielding
    assert isinstance(status, UserMessageRequestStatus)
    assert "you?" == conversation.get_last_message().content

    conversation.append_user_message("something")

    serialized_conversation = serialize(conversation)
    deserialization_context = DeserializationContext()
    deserialized_conv = deserialize(
        FlowConversation,
        serialized_conversation,
        deserialization_context=deserialization_context,
    )

    assert_flow_conversations_are_equal(conversation, deserialized_conv)

    status = deserialized_conv.execute()
    # should continue the conversation, ie finish the flow
    assert isinstance(status, FinishedStatus)


def test_serialize_flow_conversation(
    flow: Flow,
) -> None:
    conversation = flow.start_conversation()
    status = conversation.execute()
    # first message of conversation should be the usermessage yielding
    assert isinstance(status, UserMessageRequestStatus)
    assert "you?" == conversation.get_last_message().content

    conversation.append_user_message("something")

    serialized_conversation = serialize(conversation)
    deserialization_context = DeserializationContext()

    deserialized_conv = cast(
        FlowConversation,
        deserialize(
            FlowConversation,
            serialized_conversation,
            deserialization_context=deserialization_context,
        ),
    )
    status = deserialized_conv.execute()
    # should continue the conversation, ie finish the flow
    assert isinstance(status, FinishedStatus)


def test_serialize_agent_conversation_with_internal_states(remotely_hosted_llm) -> None:
    client_tool = ClientTool(
        name="add_numbers",
        description="Add the two numbers:",
        parameters={
            "a": {"type": "integer"},
            "b": {"type": "integer"},
        },
        output={"type": "integer"},
    )

    dummy_llm = DummyModel()
    dummy_llm.set_next_output(
        Message(
            message_type=MessageType.TOOL_REQUEST,
            content="",
            tool_requests=[ToolRequest("flow_tool", {"a": 2, "b": 3}, "tc1")],
        )
    )

    agent = create_agent(
        llm=dummy_llm,
        flows=[
            DescribedFlow(
                name="flow_tool",
                description="flow tool",
                flow=create_single_step_flow(ToolExecutionStep(tool=client_tool)),
            )
        ],
    )

    conversation = agent.start_conversation()
    status = conversation.execute()
    # first message of conversation should be the user message yielding
    assert isinstance(status, UserMessageRequestStatus)
    assert "Hi! How can I help you?" == conversation.get_last_message().content

    conversation.append_user_message("what is the result of 2 + 3?")
    status = conversation.execute()

    assert isinstance(status, ToolRequestStatus)
    assert len(status.tool_requests) == 1
    tool_request_id = status.tool_requests[0].tool_request_id

    agent.llm = remotely_hosted_llm

    serialized_conversation = serialize(conversation)
    deserialization_context = DeserializationContext()
    deserialized_conv = deserialize(
        AgentConversation,
        serialized_conversation,
        deserialization_context=deserialization_context,
    )

    assert_agent_conversations_are_equal(conversation, deserialized_conv)

    # set the next output again
    deserialized_conv.component.llm = dummy_llm
    dummy_llm.set_next_output(
        Message(
            message_type=MessageType.AGENT,
            content="the answer is 5",
        )
    )
    deserialized_conv.append_tool_result(ToolResult(content=5, tool_request_id=tool_request_id))
    status = deserialized_conv.execute()
    # should continue the conversation, ie finish the flow
    assert isinstance(status, UserMessageRequestStatus)


@pytest.mark.parametrize(
    "interrupter_builder",
    [
        lambda llm: SoftTimeoutExecutionInterrupt(timeout=0),
        lambda llm: SoftTokenLimitExecutionInterrupt(total_tokens=1, all_models=[llm]),
    ],
)
def test_interrupted_status_properly_serde(remotely_hosted_llm, interrupter_builder):
    interrupter = interrupter_builder(remotely_hosted_llm)
    step = PromptExecutionStep(
        llm=remotely_hosted_llm,
        prompt_template="count to 5",
        generation_config=LlmGenerationConfig(max_tokens=10),
    )
    flow = create_single_step_flow(step)
    conv = flow.start_conversation()
    status = conv.execute(execution_interrupts=[interrupter])
    serialized_conv = serialize(conv)
    deserialized_conv = autodeserialize(serialized_conv)


@retry_test(max_attempts=3)
def test_can_resume_agentconversation_execution_with_conversation_execute_method():
    """
    Failure rate:          0 out of 30
    Observed on:           2025-05-20
    Average success time:  0.55 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000
    """
    llm_config = deepcopy(VLLM_MODEL_CONFIG)
    llm_config["generation_config"] = {"max_tokens": 10}
    llm = LlmModelFactory.from_config(llm_config)

    USER_MSG_1 = "User message 1"
    USER_MSG_2 = "User message 2"

    agent = Agent(
        llm=llm, custom_instruction='This is a test. Output "TEST" to every user message.'
    )
    conversation = agent.start_conversation()
    conversation.append_user_message(USER_MSG_1)

    conversation.execute()
    ser_conv = serialize(conversation)

    deser_conv: AgentConversation = autodeserialize(ser_conv)
    deser_conv.append_user_message(USER_MSG_2)
    deser_conv.execute()

    all_messages = deser_conv.get_messages()
    assert len(all_messages) == 4
    user_message1, agent_message1, user_message2, agent_message2 = all_messages

    assert user_message1.message_type == MessageType.USER and user_message1.content == USER_MSG_1
    assert agent_message1.message_type == MessageType.AGENT
    assert user_message2.message_type == MessageType.USER and user_message2.content == USER_MSG_2
    assert agent_message2.message_type == MessageType.AGENT


def test_can_resume_flowconversation_execution_with_conversation_execute_method():
    INPUT_MSG = "Input message"
    USER_MSG = "User message"
    OUTPUT_MSG = "Output message"

    flow = Flow.from_steps([InputMessageStep(INPUT_MSG), OutputMessageStep(OUTPUT_MSG)])

    conversation = flow.start_conversation()
    conversation.execute()
    ser_conv = serialize(conversation)

    deser_conv: AgentConversation = autodeserialize(ser_conv)

    deser_conv.append_user_message(USER_MSG)
    deser_conv.execute()

    all_messages = deser_conv.get_messages()
    assert len(all_messages) == 3
    input_message, user_message, output_message = all_messages

    assert input_message.content == INPUT_MSG
    assert user_message.message_type == MessageType.USER and user_message.content == USER_MSG
    assert output_message.content == OUTPUT_MSG


@retry_test(max_attempts=4)
def test_can_resume_swarmconversation_execution_with_conversation_execute_method():
    """
    Failure rate:          2 out of 30
    Observed on:           2025-05-20
    Average success time:  1.54 seconds per successful attempt
    Average failure time:  1.89 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 7.7 / 100'000

    Note:
    The flakiness comes from the following scenario:
    * An agent in the Swarm calls another agent with "send_message"
    * The recipient agent uses the `talk_to_user` tool with incorrect input param (supposed to be "text")
    * A user message "Something went wrong. Please retry your request" is generated (from `_convert_talk_to_user_tool_call_into_agent_message`)
    * `_post_agent_answer_to_previous_thread` raises and error because what is supposed to be an agent response is instead of type USER...

    """
    llm_config = deepcopy(VLLM_MODEL_CONFIG)
    llm_config["generation_config"] = {"max_tokens": 10}
    llm = LlmModelFactory.from_config(llm_config)

    first_agent = Agent(
        name="agent1",
        description="agent 1",
        llm=llm,
        custom_instruction='This is a test. Output "TEST" to every user message.',
    )
    recipient_agent = Agent(
        name="agent2",
        description="agent 2",
        llm=llm,
        custom_instruction='This is a test. Output "TEST" to every user message.',
    )

    swarm = Swarm(first_agent=first_agent, relationships=[(first_agent, recipient_agent)])

    USER_MSG_1 = "User message 1"
    USER_MSG_2 = "User message 1"

    conversation = swarm.start_conversation()
    conversation.append_user_message(USER_MSG_1)
    conversation.execute()
    ser_conv = serialize(conversation)

    deser_conv: AgentConversation = autodeserialize(ser_conv)

    deser_conv.append_user_message(USER_MSG_2)
    deser_conv.execute()

    all_messages_contents = {msg.content for msg in deser_conv.get_messages()}

    assert USER_MSG_1 in all_messages_contents
    assert USER_MSG_2 in all_messages_contents


def test_serialize_conversation_with_multiple_message_content_types():

    messages = [
        Message(
            content="I'll use the get_company_location with the user's company",
            tool_requests=[ToolRequest("get_location", {"company_name": "OHOH"}, "tc1")],
        ),
        Message(
            tool_result=ToolResult(tool_request_id="tc1", content="bern"),
        ),
        Message(contents=[TextContent("Text content 1"), TextContent("Text content 2")]),
        Message(
            contents=[
                ImageContent.from_bytes(bytes_content=b"12345", format="png"),
                TextContent("Text content 2"),
            ]
        ),
        Message(
            content="Test",
            tool_result=ToolResult(tool_request_id="tc1", content="bern"),
        ),
    ]
    OUTPUT_MSG = "Output message"

    flow = Flow.from_steps([OutputMessageStep(OUTPUT_MSG)])

    conversation = flow.start_conversation()
    conversation.execute()
    for message in messages:
        conversation.append_message(message)
    deserialized_conv = cast(FlowConversation, autodeserialize(serialize(conversation)))
    assert len(deserialized_conv.message_list) == len(conversation.message_list)
    for message_orig, message_deserialized in zip(
        conversation.get_messages(), deserialized_conv.get_messages()
    ):
        assert message_orig == message_deserialized


@pytest.fixture
def custom_toolbox():
    @dataclass
    class MyToolBox(ToolBox, SerializableDataclass):

        def _get_tools_inner(self) -> Sequence["Tool"]:
            raise NotImplementedError()

        async def _get_tools_inner_async(self) -> Sequence["Tool"]:
            return [
                ClientTool(name="my_client_tool", description="", input_descriptors=[]),
                ServerTool(
                    name="my_server_tool", description="", input_descriptors=[], func=lambda: ""
                ),
            ]

    try:
        yield MyToolBox()
    finally:
        # need to manually remove it from registry so that it doesn't appear in the registry of other tests
        SerializableObject._COMPONENT_REGISTRY.pop(MyToolBox.__name__)


def test_agent_with_toolbox_does_not_crash_in_between_calls(custom_toolbox, remotely_hosted_llm):

    toolbox_serialization_plugin = make_serialization_plugin(
        [custom_toolbox.__class__], name="MyToolboxPlugin", version=__version__
    )
    toolbox_deserialization_plugin = make_deserialization_plugin(
        [custom_toolbox.__class__], name="MyToolboxPlugin", version=__version__
    )

    agent = Agent(
        llm=remotely_hosted_llm,
        tools=[custom_toolbox],
        initial_message=None,
        custom_instruction="you are a helpful assistant",
    )

    serialized_agent = serialize(agent, plugins=[toolbox_serialization_plugin])
    deserialized_agent = cast(
        Agent, autodeserialize(serialized_agent, plugins=[toolbox_deserialization_plugin])
    )

    conversation = deserialized_agent.start_conversation()

    serialized_conv = serialize(conversation, plugins=[toolbox_serialization_plugin])
    deserialized_conv = cast(
        AgentConversation,
        autodeserialize(serialized_conv, plugins=[toolbox_deserialization_plugin]),
    )

    with patch_llm(
        deserialized_conv.component.llm,
        outputs=[[ToolRequest(name="my_client_tool", args={}, tool_request_id="id1")]],
    ):
        status = deserialized_conv.execute()

    assert isinstance(status, ToolRequestStatus)
    assert len(status.tool_requests) == 1
    deserialized_conv.append_tool_result(
        ToolResult(tool_request_id=status.tool_requests[0].tool_request_id, content="ok")
    )

    deserialized_conv = serialize(deserialized_conv, plugins=[toolbox_serialization_plugin])
    deserialized_conv = cast(
        AgentConversation,
        autodeserialize(deserialized_conv, plugins=[toolbox_deserialization_plugin]),
    )

    with patch_llm(deserialized_conv.component.llm, outputs=["bye"]):
        status = deserialized_conv.execute()

    messages = deserialized_conv.get_messages()

    assert isinstance(status, UserMessageRequestStatus)

    assert messages[-1].content == "bye"
    assert messages[-2].tool_result.content == "ok"
