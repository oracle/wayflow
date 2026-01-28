# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import pytest

from wayflowcore.agent import Agent
from wayflowcore.executors._flowconversation import FlowConversation
from wayflowcore.executors._managerworkersconversation import (
    ManagerWorkersConversation,
    ManagerWorkersConversationExecutionState,
)
from wayflowcore.flow import Flow
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.models import LlmModel
from wayflowcore.serialization import deserialize, serialize, serialize_to_dict
from wayflowcore.steps.agentexecutionstep import AgentExecutionStep

from ..conftest import _assert_config_are_equal
from ..test_managerworkers import simple_math_agents_example  # noqa
from .test_conversation_serialization import (
    assert_agent_conversations_are_equal,
    assert_flow_conversations_are_equal,
)
from .test_llm_serialization import assert_llms_are_equal


@pytest.fixture
def simple_managerworkers(simple_math_agents_example, remotely_hosted_llm) -> ManagerWorkers:
    addition_agent, multiplication_agent = simple_math_agents_example

    return ManagerWorkers(
        workers=[addition_agent, multiplication_agent],
        group_manager=remotely_hosted_llm,
    )


@pytest.fixture
def simple_managerworkers_in_flow(
    simple_math_agents_example, remotely_hosted_llm
) -> ManagerWorkers:
    addition_agent, multiplication_agent = simple_math_agents_example
    group = ManagerWorkers(
        workers=[addition_agent, multiplication_agent],
        group_manager=remotely_hosted_llm,
    )
    agent_execution_step = AgentExecutionStep(
        group,
    )
    return Flow.from_steps([agent_execution_step])


@pytest.fixture
def simple_conversation(simple_managerworkers: ManagerWorkers) -> ManagerWorkersConversation:
    return simple_managerworkers.start_conversation()


@pytest.fixture
def simple_conversation_in_flow(simple_managerworkers_in_flow: Flow) -> FlowConversation:
    conv = simple_managerworkers_in_flow.start_conversation()
    conv.execute()
    return conv


@pytest.fixture
def simple_state(
    simple_conversation: ManagerWorkersConversation,
) -> ManagerWorkersConversationExecutionState:
    return simple_conversation.state


def assert_managerworkers_agents_are_equal(
    old_agent: Agent,
    new_agent: Agent,
):
    assert old_agent.name == new_agent.name
    assert old_agent.description == new_agent.description
    assert old_agent.__metadata_info__ == new_agent.__metadata_info__
    assert new_agent.config.custom_instruction == old_agent.config.custom_instruction
    assert new_agent.config.max_iterations == old_agent.config.max_iterations
    assert new_agent.config.can_finish_conversation == old_agent.config.can_finish_conversation
    assert new_agent.config.caller_input_mode == old_agent.config.caller_input_mode
    assert set(new_agent.config.output_descriptors) == set(old_agent.config.output_descriptors)
    assert set(new_agent.config.input_descriptors) == set(old_agent.config.input_descriptors)


def assert_managerworkers_are_equal(old_instance: ManagerWorkers, new_instance: ManagerWorkers):
    if isinstance(old_instance.group_manager, LlmModel):
        assert_llms_are_equal(old_instance.group_manager, new_instance.group_manager)
    assert_managerworkers_agents_are_equal(old_instance.manager_agent, new_instance.manager_agent)

    assert len(old_instance.workers) == len(new_instance.workers)
    for old_worker, new_worker in zip(old_instance.workers, new_instance.workers):
        if isinstance(old_worker, ManagerWorkers) and isinstance(new_worker, ManagerWorkers):
            assert_managerworkers_are_equal(old_worker, new_worker)
        else:
            assert_managerworkers_agents_are_equal(old_worker, new_worker)

    assert old_instance.__metadata_info__ == new_instance.__metadata_info__


def assert_managerworkers_conversation_states_are_equal(
    old_state: ManagerWorkersConversationExecutionState,
    new_state: ManagerWorkersConversationExecutionState,
):
    assert old_state.current_agent_name == new_state.current_agent_name
    assert old_state.subconversations.keys() == new_state.subconversations.keys()
    for key in old_state.subconversations.keys():
        assert_agent_conversations_are_equal(
            old_state.subconversations[key], new_state.subconversations[key]
        )


def assert_managerworkers_conversations_are_equal(
    old_conv: ManagerWorkersConversation, new_conv: ManagerWorkersConversation
):
    assert_managerworkers_are_equal(old_conv.component, new_conv.component)

    assert_managerworkers_conversation_states_are_equal(old_conv.state, new_conv.state)

    assert old_conv.inputs == new_conv.inputs
    assert old_conv.message_list == new_conv.message_list
    assert old_conv.__metadata_info__ == new_conv.__metadata_info__


def test_can_serialize_simple_managerworkers(simple_managerworkers: ManagerWorkers):
    serialized_managerworkers = serialize(simple_managerworkers)
    assert isinstance(serialized_managerworkers, str)


def test_can_deserialize_simple_managerworkers(simple_managerworkers: ManagerWorkers):
    new_managerworkers = deserialize(ManagerWorkers, serialize(simple_managerworkers))

    _assert_config_are_equal(
        serialize_to_dict(simple_managerworkers),
        serialize_to_dict(new_managerworkers),
    )

    assert_managerworkers_are_equal(simple_managerworkers, new_managerworkers)


def test_can_serialize_simple_state(simple_state: ManagerWorkersConversationExecutionState):
    serialized_state = serialize(simple_state)
    assert isinstance(serialized_state, str)


def test_can_deserialize_simple_state(simple_state: ManagerWorkersConversationExecutionState):
    new_state = deserialize(ManagerWorkersConversationExecutionState, serialize(simple_state))

    assert_managerworkers_conversation_states_are_equal(simple_state, new_state)


def test_can_serialize_simple_conversation(simple_conversation: ManagerWorkersConversation):
    serialized_conversation = serialize(simple_conversation)
    assert isinstance(serialized_conversation, str)


def test_can_deserialize_a_serialized_conversation(
    simple_conversation: ManagerWorkersConversation, simple_math_agents_example
):
    addition_agent, _ = simple_math_agents_example
    simple_conversation.subconversations[addition_agent.name] = addition_agent.start_conversation()
    new_conversation = deserialize(ManagerWorkersConversation, serialize(simple_conversation))

    assert_managerworkers_conversations_are_equal(simple_conversation, new_conversation)

    s1 = serialize_to_dict(simple_conversation)
    s2 = serialize_to_dict(new_conversation)
    _assert_config_are_equal(s1, s2)


def test_can_continue_a_deserialized_conversation(simple_managerworkers: ManagerWorkers):
    conv = simple_managerworkers.start_conversation()
    conv.append_user_message("Hello")

    conv.execute()
    conv_length_before = len(conv.get_messages())

    ser_conv = serialize(conv)
    deser_conv = deserialize(ManagerWorkersConversation, ser_conv)

    assert len(deser_conv.get_messages()) == conv_length_before
    deser_conv.append_user_message("Hello")
    deser_conv.execute()


def test_can_serialize_simple_managerworkers_in_flow(simple_managerworkers_in_flow: Flow):
    serialized_flow = serialize(simple_managerworkers_in_flow)
    assert isinstance(serialized_flow, str)


def test_can_deserialize_simple_managerworkers_in_flow(simple_managerworkers_in_flow: Flow):
    new_flow = deserialize(Flow, serialize(simple_managerworkers_in_flow))
    assert isinstance(new_flow, Flow)
    assert_managerworkers_are_equal(
        simple_managerworkers_in_flow.steps["step_0"].agent, new_flow.steps["step_0"].agent
    )


def test_can_serialize_simple_conversation_in_flow(
    simple_conversation_in_flow: FlowConversation,
):
    serialized_conversation = serialize(simple_conversation_in_flow)
    assert isinstance(serialized_conversation, str)


def test_can_deserialize_simple_conversation_in_flow(simple_conversation_in_flow: FlowConversation):
    serialized_conversation = serialize(simple_conversation_in_flow)
    deserialized_conversation = deserialize(FlowConversation, serialized_conversation)
    assert isinstance(deserialized_conversation, FlowConversation)
    assert_flow_conversations_are_equal(simple_conversation_in_flow, deserialized_conversation)


def test_can_continue_a_deserialized_conversation_in_flow(simple_managerworkers_in_flow: Flow):
    conv = simple_managerworkers_in_flow.start_conversation()
    conv.append_user_message("Hello")
    conv.execute()
    conv_length_before = len(conv.get_messages())
    ser_conv = serialize(conv)
    deser_conv = deserialize(FlowConversation, ser_conv)
    assert len(deser_conv.get_messages()) == conv_length_before
    deser_conv.append_user_message("Hello")
    deser_conv.execute()


@pytest.fixture
def multi_managerworkers(simple_math_agents_example, remotely_hosted_llm) -> ManagerWorkers:
    addition_agent, multiplication_agent = simple_math_agents_example
    worker = ManagerWorkers(
        workers=[multiplication_agent],
        group_manager=remotely_hosted_llm,
    )
    return ManagerWorkers(
        workers=[addition_agent, worker],
        group_manager=remotely_hosted_llm,
    )


@pytest.fixture
def multi_conversation(multi_managerworkers: ManagerWorkers) -> ManagerWorkersConversation:
    return multi_managerworkers.start_conversation()


@pytest.fixture
def multi_state(
    multi_conversation: ManagerWorkersConversation,
) -> ManagerWorkersConversationExecutionState:
    return multi_conversation.state


def test_can_serialize_multi_managerworkers(multi_managerworkers: ManagerWorkers):
    serialized_managerworkers = serialize(multi_managerworkers)
    assert isinstance(serialized_managerworkers, str)


def test_can_deserialize_multi_managerworkers(multi_managerworkers: ManagerWorkers):
    new_managerworkers = deserialize(ManagerWorkers, serialize(multi_managerworkers))

    _assert_config_are_equal(
        serialize_to_dict(multi_managerworkers),
        serialize_to_dict(new_managerworkers),
    )

    assert_managerworkers_are_equal(multi_managerworkers, new_managerworkers)


def test_can_serialize_multi_state(multi_state: ManagerWorkersConversationExecutionState):
    serialized_state = serialize(multi_state)
    assert isinstance(serialized_state, str)


def test_can_deserialize_multi_state(multi_state: ManagerWorkersConversationExecutionState):
    new_state = deserialize(ManagerWorkersConversationExecutionState, serialize(multi_state))

    assert_managerworkers_conversation_states_are_equal(multi_state, new_state)


def test_can_serialize_multi_conversation(multi_conversation: ManagerWorkersConversation):
    serialized_conversation = serialize(multi_conversation)
    assert isinstance(serialized_conversation, str)


def test_can_deserialize_a_multi_serialized_conversation(
    multi_conversation: ManagerWorkersConversation, simple_math_agents_example
):
    addition_agent, _ = simple_math_agents_example
    multi_conversation.subconversations[addition_agent.name] = addition_agent.start_conversation()
    new_conversation = deserialize(ManagerWorkersConversation, serialize(multi_conversation))

    assert_managerworkers_conversations_are_equal(multi_conversation, new_conversation)

    s1 = serialize_to_dict(multi_conversation)
    s2 = serialize_to_dict(new_conversation)
    _assert_config_are_equal(s1, s2)


def test_can_continue_a_deserialized_multi_conversation(multi_managerworkers: ManagerWorkers):
    conv = multi_managerworkers.start_conversation()
    conv.append_user_message("Hello")

    conv.execute()
    conv_length_before = len(conv.get_messages())

    ser_conv = serialize(conv)
    deser_conv = deserialize(ManagerWorkersConversation, ser_conv)

    assert len(deser_conv.get_messages()) == conv_length_before
    deser_conv.append_user_message("Hello")
    deser_conv.execute()
