# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from unittest.mock import AsyncMock, patch

import pytest

from wayflowcore.agent import Agent
from wayflowcore.datastore import InMemoryDatastore
from wayflowcore.executors._swarmconversation import SwarmConversation
from wayflowcore.messagelist import Message
from wayflowcore.models import LlmCompletion
from wayflowcore.serialization import autodeserialize, deserialize, serialize
from wayflowcore.swarm import Swarm
from wayflowcore.templates import PromptTemplate
from wayflowcore.templates._swarmtemplate import _DEFAULT_SWARM_CHAT_TEMPLATE
from wayflowcore.transforms import ConversationSummarizationTransform, MessageSummarizationTransform

from ..conftest import mock_llm
from ..testhelpers.patching import patch_llm


def test_template_with_conversation_summarization_transform_can_roundtrip():
    template = PromptTemplate(
        messages=[
            {"role": "system", "content": "Be concise."},
            PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
        ],
        pre_rendering_transforms=[
            ConversationSummarizationTransform(
                llm=mock_llm(),
                max_num_messages=4,
                min_num_messages=1,
                datastore=None,
            )
        ],
    )

    deserialized_template = autodeserialize(serialize(template))

    assert isinstance(deserialized_template, PromptTemplate)
    assert deserialized_template.pre_rendering_transforms is not None
    assert len(deserialized_template.pre_rendering_transforms) == 1

    transform = deserialized_template.pre_rendering_transforms[0]
    assert isinstance(transform, ConversationSummarizationTransform)
    assert transform.max_num_messages == 4
    assert transform.min_num_messages == 1


def test_template_with_message_summarization_transform_can_roundtrip():
    template = PromptTemplate(
        messages=[
            {"role": "system", "content": "Be concise."},
            PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
        ],
        pre_rendering_transforms=[
            MessageSummarizationTransform(
                llm=mock_llm(),
                max_message_size=1234,
                datastore=None,
            )
        ],
    )

    deserialized_template = autodeserialize(serialize(template))

    assert isinstance(deserialized_template, PromptTemplate)
    assert deserialized_template.pre_rendering_transforms is not None
    assert len(deserialized_template.pre_rendering_transforms) == 1

    transform = deserialized_template.pre_rendering_transforms[0]
    assert isinstance(transform, MessageSummarizationTransform)
    assert transform.max_message_size == 1234


@pytest.mark.filterwarnings(
    "ignore:InMemoryDatastore is for DEVELOPMENT and PROOF-OF-CONCEPT ONLY!:UserWarning"
)
def test_deserialized_swarm_conversation_with_conversation_summarization_can_continue():
    cache_collection_name = "test_swarm_conversation_summary_cache"
    summary_datastore = InMemoryDatastore(
        {
            cache_collection_name: ConversationSummarizationTransform.get_entity_definition(),
        }
    )
    summary_llm = mock_llm()
    router_llm = mock_llm()
    specialist_llm = mock_llm()

    summarization_transform = ConversationSummarizationTransform(
        llm=summary_llm,
        max_num_messages=3,
        min_num_messages=1,
        datastore=summary_datastore,
        cache_collection_name=cache_collection_name,
    )
    swarm_template = _DEFAULT_SWARM_CHAT_TEMPLATE.with_additional_pre_rendering_transform(
        summarization_transform,
        append_last=False,
    )

    router = Agent(
        name="Router",
        description="Front desk router.",
        llm=router_llm,
        custom_instruction="Reply in one short sentence and do not delegate.",
    )
    specialist = Agent(
        name="Specialist",
        description="Backup specialist.",
        llm=specialist_llm,
        custom_instruction="Reply in one short sentence.",
    )
    swarm = Swarm(
        first_agent=router,
        relationships=[(router, specialist)],
        swarm_template=swarm_template,
    )

    conversation = swarm.start_conversation()
    summary = "Summarized previous swarm conversation."
    # Patch the summarization model separately from the router model:
    # the transform calls its own llm.generate_async(), while the Swarm turn execution
    # goes through the router agent's llm.
    summarize_completion = AsyncMock(
        side_effect=lambda prompt: LlmCompletion(Message(summary), None)
    )

    with patch.object(summary_llm, "generate_async", summarize_completion):
        with patch_llm(router_llm, outputs=["Reply 1", "Reply 2", "Reply 3"]):
            conversation.append_user_message("Message 1")
            conversation.execute()
            conversation.append_user_message("Message 2")
            conversation.execute()
            conversation.append_user_message("Message 3")
            conversation.execute()

    assert summarize_completion.call_count > 0
    assert len(summary_datastore.list(cache_collection_name)) > 0

    deserialized_conversation = deserialize(SwarmConversation, serialize(conversation))
    deserialized_transform = (
        deserialized_conversation.component.swarm_template.pre_rendering_transforms[0]
    )
    assert isinstance(deserialized_transform, ConversationSummarizationTransform)

    with patch.object(
        deserialized_transform.llm,
        "generate_async",
        AsyncMock(side_effect=lambda prompt: LlmCompletion(Message(summary), None)),
    ) as deserialized_summary_generate:
        with patch_llm(deserialized_conversation.component.first_agent.llm, outputs=["Reply 4"]):
            deserialized_conversation.append_user_message("Message 4")
            deserialized_conversation.execute()

    assert deserialized_summary_generate.call_count > 0
    assert deserialized_conversation.get_last_message() is not None
    assert deserialized_conversation.get_last_message().content == "Reply 4"
