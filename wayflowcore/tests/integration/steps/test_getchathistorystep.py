# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import pytest

from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flowhelpers import _run_single_step_and_return_conv_and_status
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.steps import GetChatHistoryStep
from wayflowcore.steps.getchathistorystep import MessageSlice


@pytest.fixture
def chat_history():
    return [
        Message(content="system_message", message_type=MessageType.SYSTEM),
        Message(content="agent 1", message_type=MessageType.AGENT),
        Message(content="user 1", message_type=MessageType.USER),
        Message(content="internal", message_type=MessageType.INTERNAL),
        Message(content="agent 2", message_type=MessageType.AGENT),
        Message(content="user 2", message_type=MessageType.USER),
        Message(content="agent 3", message_type=MessageType.AGENT),
        Message(content="user 3", message_type=MessageType.USER),
        Message(content="agent 4", message_type=MessageType.AGENT),
    ]


@pytest.fixture
def chat_history_display_only():
    return [
        Message(content="system_message", message_type=MessageType.SYSTEM),
        Message(content="agent 1", message_type=MessageType.AGENT),
        Message(content="user 1", message_type=MessageType.DISPLAY_ONLY),
        Message(content="internal", message_type=MessageType.INTERNAL),
        Message(content="agent 2", message_type=MessageType.DISPLAY_ONLY),
        Message(content="user 2", message_type=MessageType.USER),
        Message(content="agent 3", message_type=MessageType.DISPLAY_ONLY),
        Message(content="user 3", message_type=MessageType.USER),
        Message(content="agent 4", message_type=MessageType.DISPLAY_ONLY),
    ]


def run_get_chat_history_step(step: GetChatHistoryStep, messages):
    _, status = _run_single_step_and_return_conv_and_status(
        step=step, inputs=None, user_input="", messages=messages, context_providers=None
    )
    assert isinstance(status, FinishedStatus)
    return status.output_values[GetChatHistoryStep.CHAT_HISTORY]


def test_can_return_string(chat_history):
    step = GetChatHistoryStep(output_template=None)
    filtered_messages = run_get_chat_history_step(step, chat_history)
    assert len(filtered_messages) == 7


def test_get_chat_history_does_not_return_display_only_by_default(chat_history_display_only):
    step = GetChatHistoryStep(output_template=None)
    filtered_messages = run_get_chat_history_step(step, chat_history_display_only)
    assert len(filtered_messages) == 3


def test_get_chat_history_can_return_display_only_messages(chat_history_display_only):
    step = GetChatHistoryStep(
        output_template=None,
        message_types=(MessageType.USER, MessageType.AGENT, MessageType.DISPLAY_ONLY),
    )
    filtered_messages = run_get_chat_history_step(step, chat_history_display_only)
    assert len(filtered_messages) == 7
    assert filtered_messages[-1].message_type == MessageType.DISPLAY_ONLY
    assert filtered_messages[-1].content == "agent 4"


def test_can_return_templated_chat_history(chat_history):
    step = GetChatHistoryStep(
        output_template="""{% for m in chat_history -%}
{{m.message_type.value}}>>>{{m.content}}
{% endfor %}"""
    )
    filtered_messages = run_get_chat_history_step(step, chat_history)
    assert isinstance(filtered_messages, str)
    assert (
        filtered_messages
        == """AGENT>>>agent 1
USER>>>user 1
AGENT>>>agent 2
USER>>>user 2
AGENT>>>agent 3
USER>>>user 3
AGENT>>>agent 4
"""
    )


def test_can_return_only_1_message(chat_history):
    step = GetChatHistoryStep(n=1, output_template=None)
    filtered_messages = run_get_chat_history_step(step, chat_history)
    assert len(filtered_messages) == 1
    filtered_messages[0].content == "agent 4"


def test_can_order_from_first_messages(chat_history):
    step = GetChatHistoryStep(n=1, which_messages=MessageSlice.FIRST_MESSAGES, output_template=None)
    filtered_messages = run_get_chat_history_step(step, chat_history)
    assert len(filtered_messages) == 1
    filtered_messages[0].content == "agent 1"


def test_can_retrieve_with_offset(chat_history):
    step = GetChatHistoryStep(n=1, offset=1, output_template=None)
    filtered_messages = run_get_chat_history_step(step, chat_history)
    assert len(filtered_messages) == 1
    filtered_messages[0].content == "user 1"


def test_can_retrieve_with_large_offset(chat_history):
    step = GetChatHistoryStep(n=1, offset=8, message_types=None, output_template=None)
    filtered_messages = run_get_chat_history_step(step, chat_history)
    assert len(filtered_messages) == 1
    filtered_messages[0].content == "user 1"

    step = GetChatHistoryStep(n=1, offset=9, message_types=None, output_template=None)
    filtered_messages = run_get_chat_history_step(step, chat_history)
    assert len(filtered_messages) == 0


def test_can_retrieve_all_messages(chat_history):
    step = GetChatHistoryStep(message_types=None, output_template=None)
    filtered_messages = run_get_chat_history_step(step, chat_history)
    assert len(filtered_messages) == 9


def test_can_retrieve_with_empty_messages():
    step = GetChatHistoryStep(output_template=None)
    filtered_messages = run_get_chat_history_step(step, [])
    assert len(filtered_messages) == 0


def test_can_use_all_arguments_at_once(chat_history):
    step = GetChatHistoryStep(
        n=3,
        which_messages=MessageSlice.LAST_MESSAGES,
        offset=1,
        message_types=(MessageType.AGENT, MessageType.INTERNAL),
    )
    filtered_messages = run_get_chat_history_step(step, chat_history)
    assert (
        filtered_messages
        == """INTERNAL >> internal
AGENT >> agent 2
AGENT >> agent 3"""
    )
