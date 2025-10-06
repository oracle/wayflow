# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional, Tuple

import pytest

from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import StreamChunkType
from wayflowcore.steps import OutputMessageStep

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


def simple_conversation():
    flow = create_single_step_flow(OutputMessageStep("Any message"))
    return flow.start_conversation()


def test_message_has_initial_created_time_and_updated_time() -> None:
    before_message_creation_ts = datetime.now(timezone.utc)
    message = Message(content="foo", message_type=MessageType.USER)
    assert message.time_created is not None
    assert before_message_creation_ts <= message.time_created <= datetime.now(timezone.utc)
    assert message.time_updated is not None
    assert before_message_creation_ts <= message.time_updated <= datetime.now(timezone.utc)


def test_message_time_updated_automatically_set(test_with_llm_fixture) -> None:
    # llm fixture to skip in SKIP_LLM_TESTS because too slow
    message = Message(content="foo", message_type=MessageType.USER)
    assert message.time_created is not None
    after_message_creation_ts = message.time_updated
    # use actual sleep to make sure the timestamps are different
    # related to https://github.com/python/cpython/issues/75720
    time.sleep(2)
    message.content = "updated!"
    time.sleep(2)
    assert after_message_creation_ts < message.time_updated < datetime.now(timezone.utc)


def test_message_initialisation_crashes_with_role_and_message_type() -> None:
    with pytest.raises(
        ValueError, match="Messages should not be created with `message_type` and `role` specified"
    ):
        message = Message(content="foo", role="user", message_type=MessageType.AGENT)

    message = Message(content="foo", role="assistant")
    message = Message(content="foo", message_type=MessageType.AGENT)


async def llm_generator() -> Iterator[Tuple[str, Optional[List[Dict]], bool, MessageType]]:
    yield StreamChunkType.START_CHUNK, Message("", message_type=MessageType.AGENT)
    # use actual sleep to make sure the timestamps are different
    # related to https://github.com/python/cpython/issues/75720
    time.sleep(0.1)
    yield StreamChunkType.TEXT_CHUNK, Message(content="Hello ")
    time.sleep(0.1)
    yield StreamChunkType.TEXT_CHUNK, Message(content="World")
    time.sleep(0.1)
    yield StreamChunkType.TEXT_CHUNK, Message(content="!")
    time.sleep(0.1)
    yield StreamChunkType.END_CHUNK, Message("Hello World!", message_type=MessageType.AGENT)
    time.sleep(0.1)


@pytest.mark.anyio
async def test_streaming_message_time_created_time_updated(test_with_llm_fixture) -> None:
    # llm fixture to skip in SKIP_LLM_TESTS because too slow
    conversation = simple_conversation()

    before_message_creation_ts = datetime.now(timezone.utc)

    # to make the test actually synchronous
    await conversation.message_list._stream_message(llm_generator())

    message = conversation.get_last_message()

    assert message.content == "Hello World!"
    assert before_message_creation_ts <= message.time_created
    assert message.time_created <= message.time_updated
    assert message.time_updated <= datetime.now(timezone.utc)
