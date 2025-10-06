# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import os
import sys
from multiprocessing.pool import ThreadPool
from typing import Annotated, List, Optional

import pytest

from wayflowcore._proxyingmode import (
    _DEV_COMPOSABILITY_MODE,
    ProxyCommunicationContext,
    _ProxyMode,
    _set_new_message_recipients_depending_on_communication_mode,
)
from wayflowcore.agent import Agent
from wayflowcore.contextproviders.constantcontextprovider import ConstantContextProvider
from wayflowcore.conversationalcomponent import _HUMAN_ENTITY_ID
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.property import StringProperty
from wayflowcore.tools import ToolRequest, ToolResult, tool

from ..testhelpers.testhelpers import retry_test

logger = logging.getLogger(__name__)

PARENT_AGENT_ENTITY_ID = "PARENT_AGENT_ENTITY_ID"
CURRENT_AGENT_ID = "CURRENT_AGENT_ID"
SUBAGENT_ID = "SUBAGENT_ID"
DUMMY_TOOL = "dummy_tool"

PARENT_ENTITY_MESSAGE_CONTENT = "PARENT_ENTITY_MESSAGE_CONTENT"
CURRENT_AGENT_REPONSE_MESSAGE_CONTENT = "CURRENT_AGENT_MESSAGE_CONTENT"
CURRENT_AGENT_TOOL_TOOL_REQUEST_CONTENT = "CURRENT_AGENT_TOOL_TOOL_REQUEST_CONTENT"
CURRENT_AGENT_EXPERT_TOOL_REQUEST_CONTENT = "CURRENT_AGENT_EXPERT_TOOL_REQUEST_CONTENT"
CURRENT_AGENT_TOOL_TOOL_RESULT_CONTENT = "CURRENT_AGENT_TOOL_TOOL_RESULT_CONTENT"
CURRENT_AGENT_EXPERT_TOOL_RESULT_CONTENT = "CURRENT_AGENT_EXPERT_TOOL_RESULT_CONTENT"
SUBAGENT_MESSAGE_CONTENT = "SUBAGENT_MESSAGE_CONTENT"


def _check_equality_in_messages(message1: Message, message2: Message):
    for attribute in [
        "content",
        "sender",
        "recipients",
        "message_type",
        "tool_result",
        "tool_requests",
    ]:
        if getattr(message1, attribute) != getattr(message2, attribute):
            return False
    return True


def parent_user_message(
    recipients: List[str],
    force_message_type: Optional[MessageType] = None,
    force_sender: Optional[str] = None,
):
    return Message(
        sender=force_sender or _HUMAN_ENTITY_ID,
        message_type=force_message_type or MessageType.USER,
        content=PARENT_ENTITY_MESSAGE_CONTENT,
        recipients=set(recipients),
    )


def parent_agent_message(recipients: List[str], force_message_type: Optional[MessageType] = None):
    return Message(
        sender=PARENT_AGENT_ENTITY_ID,
        message_type=force_message_type or MessageType.AGENT,
        content=PARENT_ENTITY_MESSAGE_CONTENT,
        recipients=set(recipients),
    )


def current_tool_toolresult_message(recipients: List[str]):
    return Message(
        sender=CURRENT_AGENT_ID,
        message_type=MessageType.TOOL_RESULT,
        tool_result=ToolResult(
            content=CURRENT_AGENT_TOOL_TOOL_RESULT_CONTENT, tool_request_id="TOOL_TOOLREQUESTID"
        ),
        recipients=set(recipients),
    )


def current_expert_toolresult_message(recipients: List[str]):
    return Message(
        sender=CURRENT_AGENT_ID,
        message_type=MessageType.TOOL_RESULT,
        tool_result=ToolResult(
            content=CURRENT_AGENT_EXPERT_TOOL_RESULT_CONTENT, tool_request_id="EXPERT_TOOLREQUESTID"
        ),
        recipients=set(recipients),
    )


def current_expert_toolresult_as_an_agent_message(recipients: List[str]):
    return Message(
        sender=CURRENT_AGENT_ID,
        message_type=MessageType.AGENT,
        content=CURRENT_AGENT_EXPERT_TOOL_RESULT_CONTENT,
        recipients=set(recipients),
    )


def current_tool_toolrequest_message(recipients: List[str]):
    return Message(
        sender=CURRENT_AGENT_ID,
        message_type=MessageType.TOOL_REQUEST,
        tool_requests=[ToolRequest(name=DUMMY_TOOL, args={}, tool_request_id="TOOL_TOOLREQUESTID")],
        content=CURRENT_AGENT_TOOL_TOOL_REQUEST_CONTENT,
        recipients=set(recipients),
    )


def current_expert_toolrequest_message(recipients: List[str]):
    return Message(
        sender=CURRENT_AGENT_ID,
        message_type=MessageType.TOOL_REQUEST,
        tool_requests=[
            ToolRequest(name=SUBAGENT_ID, args={}, tool_request_id="EXPERT_TOOLREQUESTID")
        ],
        content=CURRENT_AGENT_EXPERT_TOOL_REQUEST_CONTENT,
        recipients=set(recipients),
    )


def current_agent_response_message(recipients: List[str]):
    return Message(
        sender=CURRENT_AGENT_ID,
        message_type=MessageType.AGENT,
        content=CURRENT_AGENT_REPONSE_MESSAGE_CONTENT,
        recipients=set(recipients),
    )


def current_agent_toexpert_message(recipients: List[str]):
    return Message(
        sender=CURRENT_AGENT_ID,
        message_type=MessageType.AGENT,
        content=CURRENT_AGENT_EXPERT_TOOL_REQUEST_CONTENT,
        recipients=set(recipients),
    )


def sub_toolresult_message(recipients: List[str]):
    return Message(
        sender=SUBAGENT_ID,
        message_type=MessageType.TOOL_RESULT,
        tool_result=ToolResult(
            content=SUBAGENT_MESSAGE_CONTENT, tool_request_id="TOOL_TOOLREQUESTID"
        ),
        recipients=set(recipients),
    )


@pytest.fixture
def assistant_under_test(remotely_hosted_llm) -> Agent:
    llm = remotely_hosted_llm

    @tool(description_mode="only_docstring")
    def dummy_tool() -> str:
        """Dummy tool"""

    return Agent(
        llm=llm,
        agent_id=CURRENT_AGENT_ID,
        tools=[dummy_tool],
        agents=[
            Agent(llm=llm, agent_id=SUBAGENT_ID, name=SUBAGENT_ID, description="sub_assistant"),
        ],
    )


@pytest.fixture
def dummy_parent_assistant(remotely_hosted_llm) -> Agent:
    """Only used for the communication context"""
    return Agent(
        llm=remotely_hosted_llm,
        agent_id=PARENT_AGENT_ENTITY_ID,
    )


def _test_communication_to_recipients(
    assistant: Agent,
    proxy_mode: _ProxyMode,
    previous_messages: List[Message],
    last_message: Message,
    new_message: Message,
    expected_messages: List[Message],
    parent_assistant: Optional[Agent] = None,
):
    os.environ[_DEV_COMPOSABILITY_MODE] = proxy_mode.name
    # create a conversation
    conversation = assistant.start_conversation()
    begin_idx = len(previous_messages)
    for previous_msg in previous_messages:
        conversation.append_message(previous_msg)
    conversation.append_message(last_message)
    conversation.append_message(new_message)

    if parent_assistant is not None:
        with ProxyCommunicationContext(conversation, parent_assistant.agent_id):
            _set_new_message_recipients_depending_on_communication_mode(
                config=assistant,
                last_message=last_message,
                new_message=new_message,
                conversation=conversation,
                messages=conversation.message_list,
            )
    else:
        _set_new_message_recipients_depending_on_communication_mode(
            config=assistant,
            last_message=last_message,
            new_message=new_message,
            conversation=conversation,
            messages=conversation.message_list,
        )

    generated_messages = conversation.get_messages()[begin_idx:]  # need to filter for correctness
    os.environ.pop(_DEV_COMPOSABILITY_MODE)

    if (len(generated_messages) != len(expected_messages)) or not all(
        _check_equality_in_messages(generated_msg, expected_msg)
        for generated_msg, expected_msg in zip(generated_messages, expected_messages)
    ):
        print(f"Generated messages:\n{generated_messages}")
        print(f"Expected messages:\n{expected_messages}")
        raise ValueError("Matching error between generated and expected messages")


@pytest.mark.parametrize(
    "previous_messages,last_message,new_message,expected_messages",
    [
        (
            [],
            parent_user_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                parent_user_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
                current_agent_response_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
            ],
        ),
        (
            [],
            parent_user_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                parent_user_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [],
            parent_user_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                parent_user_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                current_agent_toexpert_message(
                    [SUBAGENT_ID]
                ),  # this message is a new message created by the assistant to forward information to the sub/expert agent
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_agent_response_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                current_agent_toexpert_message(
                    [SUBAGENT_ID]
                ),  # this message is a new message created by the assistant to forward information to the sub/expert agent
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_agent_response_message(
                    [_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]
                ),  # this message is a new message to forward information of the assistant tool result content to the user
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                current_agent_toexpert_message(
                    [SUBAGENT_ID]
                ),  # this message is a new message created by the assistant to forward information to the sub/expert agent
            ],
        ),
    ],
)
def test_main_fullproxy_communication_to_recipients(
    assistant_under_test: Agent,
    previous_messages: List[Message],
    last_message: Message,
    new_message: Message,
    expected_messages: List[Message],
    cleanup_env,
):
    _test_communication_to_recipients(
        assistant=assistant_under_test,
        proxy_mode=_ProxyMode.FULL_PROXY,
        previous_messages=previous_messages,
        last_message=last_message,
        new_message=new_message,
        expected_messages=expected_messages,
    )


@pytest.mark.parametrize(
    "previous_messages,last_message,new_message,expected_messages",
    [
        (
            [],
            parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
                current_agent_response_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [],
            parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [],
            parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                current_agent_toexpert_message(
                    [SUBAGENT_ID]
                ),  # this message is a new message created by the assistant to forward information to the sub/expert agent
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_agent_response_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                current_agent_toexpert_message(
                    [SUBAGENT_ID]
                ),  # this message is a new message created by the assistant to forward information to the sub/expert agent
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_agent_response_message(
                    [CURRENT_AGENT_ID]
                ),  # this message is a new message to forward information of the assistant tool result content to the user
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                current_agent_toexpert_message(
                    [SUBAGENT_ID]
                ),  # this message is a new message created by the assistant to forward information to the sub/expert agent
            ],
        ),
    ],
)
def test_expert_fullproxy_communication_to_recipients(
    assistant_under_test: Agent,
    dummy_parent_assistant: Agent,
    previous_messages: List[Message],
    last_message: Message,
    new_message: Message,
    expected_messages: List[Message],
    cleanup_env,
):
    _test_communication_to_recipients(
        assistant=assistant_under_test,
        proxy_mode=_ProxyMode.FULL_PROXY,
        previous_messages=previous_messages,
        last_message=last_message,
        new_message=new_message,
        expected_messages=expected_messages,
        parent_assistant=dummy_parent_assistant,
    )


@pytest.mark.parametrize(
    "previous_messages,last_message,new_message,expected_messages",
    [
        (
            [],
            parent_user_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                parent_user_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
                current_agent_response_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
            ],
        ),
        (
            [],
            parent_user_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                parent_user_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [],
            parent_user_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                parent_user_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                parent_user_message(
                    [SUBAGENT_ID],
                    force_message_type=MessageType.AGENT,
                    force_sender=CURRENT_AGENT_ID,
                ),  # this message is a new message created by the assistant to forward information from the user to the sub/expert agent
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_agent_response_message([_HUMAN_ENTITY_ID, CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                current_agent_toexpert_message(
                    [SUBAGENT_ID]
                ),  # this message is a new message created by the assistant to forward information to the sub/expert agent
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_agent_response_message([]),
                current_expert_toolresult_as_an_agent_message(
                    [_HUMAN_ENTITY_ID]
                ),  # this message is a new message to forward information of the assistant tool result content to the user
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                current_expert_toolresult_as_an_agent_message(
                    [SUBAGENT_ID]
                ),  # this message is a new message created by the assistant to forward information to the sub/expert agent
            ],
        ),
    ],
)
def test_main_noproxy_communication_to_recipients(
    assistant_under_test: Agent,
    previous_messages: List[Message],
    last_message: Message,
    new_message: Message,
    expected_messages: List[Message],
    cleanup_env,
):
    _test_communication_to_recipients(
        assistant=assistant_under_test,
        proxy_mode=_ProxyMode.NO_PROXY,
        previous_messages=previous_messages,
        last_message=last_message,
        new_message=new_message,
        expected_messages=expected_messages,
    )


@pytest.mark.parametrize(
    "previous_messages,last_message,new_message,expected_messages",
    [
        (
            [],
            parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
                current_agent_response_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [],
            parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [],
            parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                parent_user_message(
                    [SUBAGENT_ID],
                    force_message_type=MessageType.AGENT,
                    force_sender=CURRENT_AGENT_ID,
                ),
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_agent_response_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                current_agent_toexpert_message(
                    [SUBAGENT_ID]
                ),  # this message is a new message created by the assistant to forward information to the sub agent
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_agent_response_message([]),
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                current_expert_toolresult_as_an_agent_message([SUBAGENT_ID]),
            ],
        ),
    ],
)
def test_expert_noproxy_communication_to_recipients(
    assistant_under_test: Agent,
    dummy_parent_assistant: Agent,
    previous_messages: List[Message],
    last_message: Message,
    new_message: Message,
    expected_messages: List[Message],
    cleanup_env,
):
    _test_communication_to_recipients(
        assistant=assistant_under_test,
        proxy_mode=_ProxyMode.NO_PROXY,
        previous_messages=previous_messages,
        last_message=last_message,
        new_message=new_message,
        expected_messages=expected_messages,
        parent_assistant=dummy_parent_assistant,
    )


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


def _test_simple_end_to_endcomposability(llm):
    assistant = _get_fooza_zinimo_assistant(llm)
    conversation = assistant.start_conversation()
    conversation.append_user_message("compute the result the zinimo operation of 4 and 5")
    assistant.execute(conversation)
    last_message = conversation.get_last_message().content
    assert any([x in last_message for x in ["0", "zero"]])


@retry_test(max_attempts=4)
def test_simple_end_to_endcomposability_using_full_proxy(big_llama, cleanup_env):
    """
    Failure rate:          0 out of 10
    Observed on:           2024-12-19
    Average success time:  8.74 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    os.environ[_DEV_COMPOSABILITY_MODE] = _ProxyMode.FULL_PROXY.name
    _test_simple_end_to_endcomposability(big_llama)
    os.environ.pop(_DEV_COMPOSABILITY_MODE)


@retry_test(max_attempts=4)
def test_simple_end_to_endcomposability_using_no_proxy(big_llama, cleanup_env):
    """
    Failure rate:          0 out of 10
    Observed on:           2024-12-19
    Average success time:  8.63 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    os.environ[_DEV_COMPOSABILITY_MODE] = _ProxyMode.NO_PROXY.name
    _test_simple_end_to_endcomposability(big_llama)
    os.environ.pop(_DEV_COMPOSABILITY_MODE)


def _test_communication_to_recipients_multithreaded_run(
    assistant: Agent,
    previous_messages: List[Message],
    last_message: Message,
    new_message: Message,
    expected_messages: List[Message],
    parent_assistant: Optional[Agent] = None,
) -> bool:
    conversation = assistant.start_conversation()
    # To make sure the global_proxy_communication_context uses the same entry
    conversation.conversation_id = (
        "6d5567da-15ed-4846-8fe3-14662898dfb3da95e46c-5533-45d9-a7f2-026379799552"
    )

    begin_idx = len(previous_messages)
    for previous_msg in previous_messages:
        conversation.append_message(previous_msg)
    conversation.append_message(last_message)
    conversation.append_message(new_message)

    if parent_assistant is not None:
        with ProxyCommunicationContext(conversation, parent_assistant.agent_id):
            _set_new_message_recipients_depending_on_communication_mode(
                config=assistant,
                last_message=last_message,
                new_message=new_message,
                conversation=conversation,
                messages=conversation.message_list,
            )
    else:
        _set_new_message_recipients_depending_on_communication_mode(
            config=assistant,
            last_message=last_message,
            new_message=new_message,
            conversation=conversation,
            messages=conversation.message_list,
        )

    generated_messages = conversation.get_messages()[begin_idx:]  # need to filter for correctness

    if (len(generated_messages) != len(expected_messages)) or not all(
        _check_equality_in_messages(generated_msg, expected_msg)
        for generated_msg, expected_msg in zip(generated_messages, expected_messages)
    ):
        raise ValueError("Matching error between generated and expected messages")
    return True


def _test_communication_to_recipients_multithreaded(
    assistant: Agent,
    proxy_mode: _ProxyMode,
    previous_messages: List[Message],
    last_message: Message,
    new_message: Message,
    expected_messages: List[Message],
    parent_assistant: Optional[Agent] = None,
):
    os.environ[_DEV_COMPOSABILITY_MODE] = proxy_mode.name
    base_switch_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-9)

    try:
        THREAD_COUNT = 100
        with ThreadPool(processes=11) as pool:
            results = [
                pool.apply_async(
                    func=_test_communication_to_recipients_multithreaded_run,
                    args=[
                        assistant,
                        previous_messages,
                        last_message,
                        new_message,
                        expected_messages,
                        parent_assistant,
                    ],
                )
                for _ in range(THREAD_COUNT)
            ]
            assert all([res.get() for res in results])
    finally:
        sys.setswitchinterval(base_switch_interval)
        os.environ.pop(_DEV_COMPOSABILITY_MODE)


@pytest.mark.parametrize(
    "previous_messages,last_message,new_message,expected_messages",
    [
        (
            [],
            parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
                current_agent_response_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [],
            parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [],
            parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                parent_agent_message([PARENT_AGENT_ENTITY_ID, CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                current_agent_toexpert_message(
                    [SUBAGENT_ID]
                ),  # this message is a new message created by the assistant to forward information to the sub/expert agent
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_agent_response_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_tool_toolrequest_message([CURRENT_AGENT_ID])],
            current_tool_toolresult_message([CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                current_tool_toolresult_message([CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                current_agent_toexpert_message(
                    [SUBAGENT_ID]
                ),  # this message is a new message created by the assistant to forward information to the sub/expert agent
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_agent_response_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_agent_response_message(
                    [CURRENT_AGENT_ID]
                ),  # this message is a new message to forward information of the assistant tool result content to the user
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_tool_toolrequest_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_tool_toolrequest_message([CURRENT_AGENT_ID]),
            ],
        ),
        (
            [current_expert_toolrequest_message([CURRENT_AGENT_ID])],
            current_expert_toolresult_message([CURRENT_AGENT_ID]),
            current_expert_toolrequest_message([]),
            [
                current_expert_toolresult_message([CURRENT_AGENT_ID]),
                current_expert_toolrequest_message([CURRENT_AGENT_ID]),
                current_agent_toexpert_message(
                    [SUBAGENT_ID]
                ),  # this message is a new message created by the assistant to forward information to the sub/expert agent
            ],
        ),
    ],
)
def test_expert_fullproxy_communication_to_recipients_multithreaded(
    assistant_under_test: Agent,
    dummy_parent_assistant: Agent,
    previous_messages: List[Message],
    last_message: Message,
    new_message: Message,
    expected_messages: List[Message],
    cleanup_env,
):
    """
    The following executes a test similar to `test_expert_fullproxy_communication_to_recipients`,
    to make sure that the ProxyCommunicationContext doesn't get corrupted when using multiple of them
    in a multithreaded context, with the main differences being:

    - Run in multiple threads with a short switch interval to make race conditions more likely to occur
    - Use the same conversation_id to ensure the thread safe implementation protects against the worst case scenario
    """
    _test_communication_to_recipients_multithreaded(
        assistant=assistant_under_test,
        proxy_mode=_ProxyMode.FULL_PROXY,
        previous_messages=previous_messages,
        last_message=last_message,
        new_message=new_message,
        expected_messages=expected_messages,
        parent_assistant=dummy_parent_assistant,
    )


@retry_test(max_attempts=4)
def test_agents_provide_inputs_to_subagent(big_llama):
    """
    Test added for the bug. Error was "ValueError: Missing some contextual variables in conversation, {}, {'user_request'}"

    Failure rate:          0 out of 10
    Observed on:           2025-04-01
    Average success time:  9.21 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
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
        custom_instruction="You are a helpful LLM assistant, please use the experts at your dispoal to answer user queries",
        agents=[coding_agent],
    )
    conversation = parent_agent.start_conversation()
    conversation.append_user_message(
        "I have a coding question: Explain to me in one sentence what `inspect.getframeinfo` enables."
    )

    parent_agent.execute(conversation)

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
