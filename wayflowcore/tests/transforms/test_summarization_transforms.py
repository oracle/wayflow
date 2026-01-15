# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tests.testhelpers.testhelpers import retry_test
from wayflowcore.agent import Agent
from wayflowcore.datastore.inmemory import _INMEMORY_USER_WARNING, InMemoryDatastore
from wayflowcore.messagelist import ImageContent, Message, MessageType, TextContent
from wayflowcore.models.llmmodel import LlmCompletion, LlmModel
from wayflowcore.tools import ToolRequest, ToolResult, tool
from wayflowcore.transforms import ConversationSummarizationTransform, MessageSummarizationTransform
from wayflowcore.transforms.summarization import _SUMMARIZATION_WARNING_MESSAGE

from ..conftest import mock_llm, patch_streaming_llm
from ..testhelpers.patching import patch_llm
from .conftest import (
    CONVERSATION_SUMMARIZATION_CACHE_COLLECTION_NAME,
    MESSAGE_SUMMARIZATION_CACHE_COLLECTION_NAME,
    at_least_one_keyword_present,
    execute_conversation_check_summarizer_ran,
    get_incorrect_schemas,
)

IMAGE_CONTENT_PNG = ImageContent.from_bytes(
    bytes_content=(Path(__file__).parent.parent / "configs/test_data/oracle_logo.png").read_bytes(),
    format="png",
)
IMAGE_CONTENT_JPEG = ImageContent.from_bytes(
    bytes_content=(
        Path(__file__).parent.parent / "configs/test_data/oracle_logo.jpeg"
    ).read_bytes(),
    format="jpeg",
)
CONVERSATION_WITH_LONG_MESSAGES = [
    Message(
        message_type=MessageType.USER,
        content="Hi! Can you tell me something interesting about dolphins?",
    ),
    Message(
        message_type=MessageType.AGENT,
        contents=[
            TextContent(
                "Absolutely! Dolphins are fascinating creatures, famous for their intelligence and complex behavior. "
                "For example, they have been observed using tools, such as covering their snouts with sponges to protect themselves "
                "while foraging on the seafloor. Dolphins also display strong social bonds and have been known to help injured "
                "individuals within their pods. Communication among dolphins is advanced; they use a series of clicks, whistles, "
                "and body movements to convey information, and some species even have distinctive signature whistles that function like names."
            ),
            IMAGE_CONTENT_PNG,
        ],
    ),
    Message(
        message_type=MessageType.USER,
        content="Wow, I didn't know that. Do dolphins have good memory?",
    ),
    Message(
        message_type=MessageType.AGENT,
        contents=[
            TextContent(
                "Dolphins possess remarkable memories, particularly when it comes to their social groups and vocal communication. "
                "Researchers have discovered that dolphins can remember the unique signature whistles of other dolphins for over 20 years, "
                "which is the longest social memory recorded in non-human animals. This ability highlights their sophisticated cognitive abilities "
            ),
            TextContent(
                "and the importance of long-term relationships in dolphin societies. Memory also plays a crucial role in their navigation and hunting skills, "
                "as dolphins migrate and follow paths in the oceans over great distances. In addition, their keen memory supports learning from one another, "
                "enhancing the social structure of their pods."
            ),
            IMAGE_CONTENT_JPEG,
        ],
    ),
    Message(
        message_type=MessageType.USER,
        content="That's impressive. Are there other animals with similar intelligence?",
    ),
]
CONVERSATION_WITH_TOOL_REQUESTS = [
    Message(
        message_type=MessageType.USER,
        content="Hi! Can you tell me something interesting about dolphins?",
    ),
    Message(
        contents=[],
        message_type=MessageType.TOOL_REQUEST,
        tool_requests=[
            ToolRequest(name="retrieve_facts", args={"subject": "dolphin"}, tool_request_id="id1")
        ],
    ),
    Message(
        contents=[],
        message_type=MessageType.TOOL_RESULT,
        tool_result=ToolResult(
            content=(
                "Absolutely! Dolphins are fascinating creatures, famous for their intelligence and complex behavior. "
                "For example, they have been observed using tools, such as covering their snouts with sponges to protect themselves "
                "while foraging on the seafloor. Dolphins also display strong social bonds and have been known to help injured "
                "individuals within their pods. Communication among dolphins is advanced; they use a series of clicks, whistles, "
                "and body movements to convey information, and some species even have distinctive signature whistles that function like names."
            ),
            tool_request_id="id1",
        ),
    ),
    Message(
        message_type=MessageType.USER,
        content="Wow, I didn't know that. Do dolphins have good memory?",
    ),
    Message(
        contents=[],
        message_type=MessageType.TOOL_REQUEST,
        tool_requests=[
            ToolRequest(
                name="retrieve_facts", args={"subject": "dolphin memory"}, tool_request_id="id2"
            )
        ],
    ),
    Message(
        contents=[],
        message_type=MessageType.TOOL_RESULT,
        tool_result=ToolResult(
            content=(
                "Dolphins possess remarkable memories, particularly when it comes to their social groups and vocal communication. "
                "Researchers have discovered that dolphins can remember the unique signature whistles of other dolphins for over 20 years, "
                "which is the longest social memory recorded in non-human animals. This ability highlights their sophisticated cognitive abilities "
                "and the importance of long-term relationships in dolphin societies. Memory also plays a crucial role in their navigation and hunting skills, "
                "as dolphins migrate and follow paths in the oceans over great distances. In addition, their keen memory supports learning from one another, "
                "enhancing the social structure of their pods."
            ),
            tool_request_id="id2",
        ),
    ),
    Message(
        message_type=MessageType.USER,
        content="That's impressive. Are there other animals with similar intelligence?",
    ),
]

LONG_CONVERSATION = [
    Message(
        message_type=MessageType.USER,
        content="Hi! Can you tell me something interesting about dolphins?",
    ),
    Message(
        message_type=MessageType.AGENT,
        contents=[
            TextContent(
                "Absolutely! Dolphins are fascinating creatures, famous for their intelligence and complex behavior. "
                "For example, they have been observed using tools, such as covering their snouts with sponges to protect themselves "
                "while foraging on the seafloor. Dolphins also display strong social bonds and have been known to help injured "
                "individuals within their pods. Communication among dolphins is advanced; they use a series of clicks, whistles, "
                "and body movements to convey information, and some species even have distinctive signature whistles that function like names."
            ),
            IMAGE_CONTENT_PNG,
        ],
    ),
    Message(
        message_type=MessageType.USER,
        content="Wow, I didn't know that. Do dolphins have good memory?",
    ),
    Message(
        message_type=MessageType.AGENT,
        contents=[
            TextContent(
                "Dolphins possess remarkable memories, particularly when it comes to their social groups and vocal communication. "
                "Researchers have discovered that dolphins can remember the unique signature whistles of other dolphins for over 20 years, "
                "which is the longest social memory recorded in non-human animals. This ability highlights their sophisticated cognitive abilities "
            ),
            TextContent(
                "and the importance of long-term relationships in dolphin societies. Memory also plays a crucial role in their navigation and hunting skills, "
                "as dolphins migrate and follow paths in the oceans over great distances. In addition, their keen memory supports learning from one another, "
                "enhancing the social structure of their pods."
            ),
            IMAGE_CONTENT_JPEG,
        ],
    ),
    Message(
        message_type=MessageType.USER,
        content="That's impressive. Are there other animals with similar intelligence?",
    ),
    Message(
        contents=[],
        message_type=MessageType.TOOL_REQUEST,
        tool_requests=[
            ToolRequest(
                name="retrieve_facts",
                args={"subject": "animals with high intelligence"},
                tool_request_id="id3",
            )
        ],
    ),
    Message(
        contents=[],
        message_type=MessageType.TOOL_RESULT,
        tool_result=ToolResult(
            content=(
                "Yes, several other animals are recognized for their advanced intelligence, including chimpanzees, elephants, octopuses, and some birds like crows and parrots. "
                "Chimpanzees use tools and show complex social behaviors. Elephants have strong memories, use tools, and exhibit empathy. "
                "Octopuses display problem-solving abilities and can navigate mazes and manipulate objects. Crows and parrots are known for their mimicry, problem-solving, and tool use. "
                "These animals demonstrate various forms of intelligence, such as learning, memory, communication, emotion, and creativity."
            ),
            tool_request_id="id3",
        ),
    ),
    Message(
        message_type=MessageType.USER,
        content="Do dolphins use tools like chimpanzees do?",
    ),
    Message(
        contents=[],
        message_type=MessageType.TOOL_REQUEST,
        tool_requests=[
            ToolRequest(
                name="retrieve_facts", args={"subject": "dolphin tool use"}, tool_request_id="id4"
            )
        ],
    ),
    Message(
        contents=[],
        message_type=MessageType.TOOL_RESULT,
        tool_result=ToolResult(
            content=(
                "Indeed, dolphins are one of the few non-human species observed using tools. "
                "For instance, some bottlenose dolphins use marine sponges to cover their snouts while searching the seafloor for food, "
                "which protects them from sharp objects or stinging animals. This behavior is taught by mothers to their offspring, providing evidence of culture and learning."
            ),
            tool_request_id="id4",
        ),
    ),
    Message(
        message_type=MessageType.USER,
        content="That's fascinating! Do dolphins have unique personalities?",
    ),
    Message(
        contents=[],
        message_type=MessageType.TOOL_REQUEST,
        tool_requests=[
            ToolRequest(
                name="retrieve_facts",
                args={"subject": "dolphin personalities"},
                tool_request_id="id5",
            )
        ],
    ),
    Message(
        contents=[],
        message_type=MessageType.TOOL_RESULT,
        tool_result=ToolResult(
            content=(
                "Yes, research suggests that dolphins display a variety of personality traits, such as boldness, curiosity, sociability, and playfulness. "
                "Individual dolphins may prefer different activities or companions, and their distinct personalities can influence social roles within their pods. "
                "Some dolphins show a greater tendency for innovation, such as inventing new games or ways to interact with humans and objects."
            ),
            tool_request_id="id5",
        ),
    ),
    Message(
        message_type=MessageType.USER,
        content="How do dolphins communicate over long distances?",
    ),
    Message(
        contents=[],
        message_type=MessageType.TOOL_REQUEST,
        tool_requests=[
            ToolRequest(
                name="retrieve_facts",
                args={"subject": "dolphin long distance communication"},
                tool_request_id="id6",
            )
        ],
    ),
    Message(
        contents=[],
        message_type=MessageType.TOOL_RESULT,
        tool_result=ToolResult(
            content=(
                "Dolphins use a range of vocalizations, mostly clicks and whistles, which travel well through water to communicate across long distances. "
                "They can modulate the frequency and duration of their calls to send specific signals. Their echolocation clicks can also be detected by other dolphins miles away, "
                "helping them stay connected even when separated."
            ),
            tool_request_id="id6",
        ),
    ),
]


def message_summarization_transform_setup(llm: LlmModel):
    collection_name = MESSAGE_SUMMARIZATION_CACHE_COLLECTION_NAME
    datastore = InMemoryDatastore(
        {collection_name: MessageSummarizationTransform.get_entity_definition()}
    )
    transforms = [
        MessageSummarizationTransform(
            llm=llm,
            max_message_size=500,
            datastore=datastore,
            cache_collection_name=collection_name,
        )
    ]
    return {
        "transforms": transforms,
        "datastore": datastore,
        "collection_name": collection_name,
        "summarization_llm": llm,
    }


def message_and_conversation_summarization_transforms_setup(llm: LlmModel):
    collections = {
        transformcls.DEFAULT_CACHE_COLLECTION_NAME: transformcls.get_entity_definition()
        for transformcls in [MessageSummarizationTransform, ConversationSummarizationTransform]
    }
    datastore = InMemoryDatastore(collections)
    summarization_llm = llm
    transforms = [
        MessageSummarizationTransform(
            llm=summarization_llm,
            datastore=datastore,
            max_message_size=500,
        ),
        ConversationSummarizationTransform(
            llm=summarization_llm,
            datastore=datastore,
            max_num_messages=10,
            min_num_messages=5,
            summarized_conversation_template="Summarized conversation: {{summary}}",
        ),
    ]
    return {
        "transforms": transforms,
        "datastore": datastore,
        "collection_name": ConversationSummarizationTransform.DEFAULT_CACHE_COLLECTION_NAME,
        "summarization_llm": summarization_llm,
    }


def check_transform_summarizes_long_messages_only(
    agent, messages, long_msgs_indices, max_message_size=500
):
    long_messages = [m.content for m in messages if len(m.content) > max_message_size]
    short_messages = [m.content for m in messages if len(m.content) <= max_message_size]
    # We have this check because this test requires short and long messages.
    assert len(long_messages) == 2 and len(short_messages) >= 3
    conversation = agent.start_conversation()
    for m in messages:
        conversation.append_message(m)

    with patch_streaming_llm(agent.llm, "This is a mock llm generation.") as patched_agent_llm:
        conversation.execute()

        # We will check that the messages passed to the llm where summarized iff they were long.
        transformed_messages = [
            message
            for prompts, _ in patched_agent_llm.call_args_list
            for prompt in prompts
            for message in prompt.messages
        ]
        assert len(transformed_messages) == len(messages)

        # These tests are not strict on purpose to avoid flakiness.
        assert at_least_one_keyword_present(
            ["smart", "intelligent", "social", "information", "signature"],
            transformed_messages[long_msgs_indices[0]].content,
        )
        assert at_least_one_keyword_present(
            ["memory", "20 year", "cognitive", "memories", "migrate"],
            transformed_messages[long_msgs_indices[1]].content,
        )

        for original_message, transformed_message in zip(messages, transformed_messages):
            if original_message.content in short_messages:
                assert original_message.content == transformed_message.content
            else:
                assert len(transformed_message.content) < len(original_message.content)


def check_conversation_summarization_transformer_summarizes_long_conversations(
    agent, messages, max_num_messages=10
):
    # These tests are to ensure that our test cases cover both executed paths.
    assert len(CONVERSATION_WITH_LONG_MESSAGES) < max_num_messages
    assert len(LONG_CONVERSATION) > max_num_messages
    conversation = agent.start_conversation()

    for m in messages:
        conversation.append_message(m)

    with patch_streaming_llm(agent.llm, "This is a mock llm generation.") as patched_agent_llm:
        conversation.execute()

        # We will check that the messages passed to the llm where summarized iff they were long.
        transformed_messages = [
            message
            for prompts, _ in patched_agent_llm.call_args_list
            for prompt in prompts
            for message in prompt.messages
        ]

        if len(messages) <= max_num_messages:
            assert len(transformed_messages) == len(messages)
        else:
            assert len(transformed_messages) < len(messages)
            summary = "\n".join([m.content for m in transformed_messages])
            # Agent Message 1: Interesting facts about dolphins
            assert at_least_one_keyword_present(
                [
                    "intelligence",
                    "tool use",
                    "sponges",
                    "foraging",
                    "social bonds",
                    "communication",
                    "signature whistles",
                ],
                summary,
            )

            # Agent Message 2: Dolphin memories and cognition
            assert at_least_one_keyword_present(
                [
                    "memory",
                    "signature whistles",
                    "long-term",
                    "cognitive abilities",
                    "social groups",
                    "learning",
                ],
                summary,
            )

            # Tool Result 1: Other intelligent animals
            assert at_least_one_keyword_present(
                [
                    "chimpanzees",
                    "elephants",
                    "octopuses",
                    "crows",
                    "parrots",
                    "intelligence",
                    "tool use",
                    "memory",
                    "problem-solving",
                    "communication",
                    "emotion",
                    "creativity",
                ],
                summary,
            )

            # Tool Result 2: Dolphin tool use
            assert at_least_one_keyword_present(
                ["tool use", "sponges", "foraging", "culture", "learning", "mother-offspring"],
                summary,
            )

            # Tool Result 3: Dolphin personalities
            assert at_least_one_keyword_present(
                [
                    "personality traits",
                    "boldness",
                    "curiosity",
                    "sociability",
                    "playfulness",
                    "innovation",
                    "social roles",
                ],
                summary,
            )

            # Tool Result 4: Dolphin long distance communication
            assert at_least_one_keyword_present(
                [
                    "long distance",
                    "communication",
                    "vocalizations",
                    "clicks",
                    "whistles",
                    "signals",
                    "echolocation",
                ],
                summary,
            )


@pytest.mark.filterwarnings(f"ignore:{_INMEMORY_USER_WARNING}:UserWarning")
@retry_test(max_attempts=4)
@pytest.mark.parametrize(
    "get_setup",
    [
        message_summarization_transform_setup,
        message_and_conversation_summarization_transforms_setup,
    ],
)
@pytest.mark.parametrize(
    "messages, long_msgs_indices",
    [(CONVERSATION_WITH_LONG_MESSAGES, [1, 3]), (CONVERSATION_WITH_TOOL_REQUESTS, [2, 5])],
)
def test_transform_summarizes_long_messages_only(
    get_setup, messages, long_msgs_indices, remote_gemma_llm
):
    """
    Failure rate:          0 out of 10
    Observed on:           2025-11-25
    Average success time:  2.66 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    max_message_size = 500
    long_messages = [m.content for m in messages if len(m.content) > max_message_size]
    short_messages = [m.content for m in messages if len(m.content) <= max_message_size]
    transforms = get_setup(remote_gemma_llm)["transforms"]
    # We have this check because this test requires short and long messages.
    assert len(long_messages) == 2 and len(short_messages) >= 3
    # We pass a mock_llm because we will not need the agent's generation.
    agent_llm = mock_llm()
    agent = Agent(llm=agent_llm, tools=[], transforms=transforms)
    check_transform_summarizes_long_messages_only(agent, messages, long_msgs_indices)


@retry_test(max_attempts=4)
@pytest.mark.filterwarnings(f"ignore:{_INMEMORY_USER_WARNING}:UserWarning")
def test_transform_summarizes_long_messages_only_from_agentspec(
    converted_wayflow_agent_with_message_summarization_transform_from_agentspec,
):
    """
    Failure rate:          0 out of 10
    Observed on:           2026-01-15
    Average success time:  2.33 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    check_transform_summarizes_long_messages_only(
        converted_wayflow_agent_with_message_summarization_transform_from_agentspec,
        messages=CONVERSATION_WITH_LONG_MESSAGES,
        long_msgs_indices=[1, 3],
    )


@pytest.mark.filterwarnings(f"ignore:{_SUMMARIZATION_WARNING_MESSAGE}:UserWarning")
@pytest.mark.filterwarnings(f"ignore:{_INMEMORY_USER_WARNING}:UserWarning")
@pytest.mark.parametrize(
    "params,messages,collection_name,transform_type",
    [
        (
            {"max_message_size": 500},
            CONVERSATION_WITH_LONG_MESSAGES,
            MESSAGE_SUMMARIZATION_CACHE_COLLECTION_NAME,
            MessageSummarizationTransform,
        ),
        (
            {"max_num_messages": 10, "min_num_messages": 5},
            LONG_CONVERSATION,
            CONVERSATION_SUMMARIZATION_CACHE_COLLECTION_NAME,
            ConversationSummarizationTransform,
        ),
    ],
)
def test_summarization_transform_caches_summarization(
    params, messages, transform_type, remotely_hosted_llm, collection_name, testing_data_store
):
    summarization_llm = remotely_hosted_llm
    transform = transform_type(
        llm=remotely_hosted_llm,
        datastore=testing_data_store,
        cache_collection_name=collection_name,
        **params,
    )
    if transform_type == MessageSummarizationTransform:
        assert len(messages[0].content) < params["max_message_size"]
        assert len(messages[1].content) > params["max_message_size"]
    # We pass a mock_llm because we will not need the agent's generation.
    agent_llm = mock_llm()
    agent = Agent(llm=agent_llm, tools=[], transforms=[transform])
    conversation = agent.start_conversation()
    for m in messages:
        conversation.append_message(m)
    # On first try the conversation should not be cached.
    assert execute_conversation_check_summarizer_ran(conversation, summarization_llm, agent_llm)

    # Now we expect that our long message has been cached and the summarizer did not run.
    conversation.append_message(Message("This is another mock message."))
    assert not execute_conversation_check_summarizer_ran(conversation, summarization_llm, agent_llm)


@pytest.mark.filterwarnings(f"ignore:{_SUMMARIZATION_WARNING_MESSAGE}:UserWarning")
@pytest.mark.filterwarnings(f"ignore:{_INMEMORY_USER_WARNING}:UserWarning")
@pytest.mark.parametrize(
    "params,messages,collection_name,transform_type",
    [
        (
            {"max_message_size": 500, "max_cache_size": 6},
            CONVERSATION_WITH_LONG_MESSAGES[:2],
            MESSAGE_SUMMARIZATION_CACHE_COLLECTION_NAME,
            MessageSummarizationTransform,
        ),
        (
            {"max_num_messages": 10, "min_num_messages": 5, "max_cache_size": 6},
            LONG_CONVERSATION,
            CONVERSATION_SUMMARIZATION_CACHE_COLLECTION_NAME,
            ConversationSummarizationTransform,
        ),
    ],
)
def test_summarization_transform_cache_evicts_lru(
    params, messages, transform_type, collection_name, remotely_hosted_llm, testing_data_store
):
    summarization_llm = remotely_hosted_llm
    max_cache_size = params["max_cache_size"]
    transform = transform_type(
        llm=remotely_hosted_llm,
        datastore=testing_data_store,
        cache_collection_name=collection_name,
        **params,
    )
    if transform_type == MessageSummarizationTransform:
        assert len(messages[0].content) < params["max_message_size"]
        assert len(messages[1].content) > params["max_message_size"]
    # We pass a mock_llm because we will not need the agent's generation.
    agent_llm = mock_llm()
    agent = Agent(llm=agent_llm, tools=[], transforms=[transform])

    def run_many_conversations(n_convs):
        conversations = []
        for _ in range(n_convs):
            conv = agent.start_conversation()

            for m in messages:
                conv.append_message(m)

            # execute these conversations, this will add them to cache.
            assert execute_conversation_check_summarizer_ran(conv, summarization_llm, agent_llm)
            conversations.append(conv)
        return conversations

    # PART 1: Checks the case we elements are not reused (here LRU = FIFO)
    # each conversation has one long message.
    conversations_to_evict = run_many_conversations(max_cache_size)
    conversations_to_keep = run_many_conversations(max_cache_size)

    # We NEED to check conversations_to_keep BEFORE conversations_to_evict
    # because otherwise conversations_to_evict's conversations will be loaded back to cache.
    for conv in conversations_to_keep:
        assert not execute_conversation_check_summarizer_ran(conv, summarization_llm, agent_llm)

    for conv in conversations_to_evict:
        assert execute_conversation_check_summarizer_ran(conv, summarization_llm, agent_llm)
    # By this point the cache contains conversations_to_evict.

    # PART2: checks the case where elemets are reused.
    # We evict both conversations_to_keep and conversations_to_evict.
    _ = run_many_conversations(max_cache_size)
    # We fill have of the cache with conversations_to_keep[:max_cache_size//2]
    # And the other half with conversations_to_evict[:max_cache_size//2]
    assert max_cache_size % 2 == 0
    for conv in conversations_to_keep[: max_cache_size // 2]:
        # This assert ensures reseting cache works.
        assert execute_conversation_check_summarizer_ran(conv, summarization_llm, agent_llm)
    for conv in conversations_to_evict[: max_cache_size // 2]:
        # This assert ensures reseting cache works.
        assert execute_conversation_check_summarizer_ran(conv, summarization_llm, agent_llm)
    # We reuse conversations_to_keep[:max_cache_size//2]
    for conv in conversations_to_keep[: max_cache_size // 2]:
        # This assert ensures caching works. This line should update the LRU
        assert not execute_conversation_check_summarizer_ran(conv, summarization_llm, agent_llm)
    # After this LRU should evict conversations_to_evicts And FIFO evicts conversations_to_keep
    _ = run_many_conversations(max_cache_size // 2)  # Evicts LRU
    for conv in conversations_to_evict[: max_cache_size // 2]:
        assert execute_conversation_check_summarizer_ran(conv, summarization_llm, agent_llm)


@pytest.mark.parametrize(
    "datastore_with_incorrect_schemas",
    get_incorrect_schemas(),
    indirect=True,
)
def test_summarization_transform_raises_error_incorrect_oracle_ds_schema(
    datastore_with_incorrect_schemas,
):
    with pytest.raises(ValueError):
        MessageSummarizationTransform(
            llm=mock_llm(),
            datastore=datastore_with_incorrect_schemas,
            cache_collection_name=MessageSummarizationTransform.DEFAULT_CACHE_COLLECTION_NAME,
        )


@pytest.mark.filterwarnings(f"ignore:{_INMEMORY_USER_WARNING}:UserWarning")
@pytest.mark.parametrize(
    "inmemory_datastore_with_incorrect_schemas",
    get_incorrect_schemas(),
    indirect=True,
)
def test_summarization_transform_raises_error_incorrect_inmemory_ds_schema(
    inmemory_datastore_with_incorrect_schemas,
):
    with pytest.raises(ValueError):
        MessageSummarizationTransform(
            llm=mock_llm(),
            datastore=inmemory_datastore_with_incorrect_schemas,
            cache_collection_name=MessageSummarizationTransform.DEFAULT_CACHE_COLLECTION_NAME,
        )


@pytest.mark.filterwarnings(f"ignore:{_INMEMORY_USER_WARNING}:UserWarning")
@pytest.mark.parametrize(
    "transform_type,params,messages,collection_name",
    [
        (
            MessageSummarizationTransform,
            {"max_message_size": 500},
            CONVERSATION_WITH_LONG_MESSAGES[:2],
            MESSAGE_SUMMARIZATION_CACHE_COLLECTION_NAME,
        ),
        (
            ConversationSummarizationTransform,
            {"max_num_messages": 5, "min_num_messages": 2},
            LONG_CONVERSATION[:6],
            CONVERSATION_SUMMARIZATION_CACHE_COLLECTION_NAME,
        ),
    ],
)
def test_summarization_transform_removes_expired_messages(
    messages, params, collection_name, testing_data_store, transform_type
):
    if not testing_data_store:
        return
    summarization_llm = mock_llm()
    max_cache_lifetime = 1
    transform = transform_type(
        llm=summarization_llm,
        datastore=testing_data_store,
        cache_collection_name=collection_name,
        **(params | {"max_cache_lifetime": 1}),
    )

    agent_llm = mock_llm()
    agent = Agent(llm=agent_llm, tools=[], transforms=[transform])

    first_conv = agent.start_conversation()
    if transform_type == MessageSummarizationTransform:
        assert len(messages[0].content) < params["max_message_size"]
        assert len(messages[1].content) > params["max_message_size"]
    for m in messages:
        first_conv.append_message(m)

    execute_conversation_check_summarizer_ran(first_conv, summarization_llm, agent_llm)

    cache_key = ""
    if transform_type == MessageSummarizationTransform:
        cache_key = str(first_conv.id) + "_1_content"  # second message in the list is the long one.
    elif transform_type == ConversationSummarizationTransform:
        cache_key = str(first_conv.id)

    assert (
        len(
            testing_data_store.list(
                collection_name,
                {"cache_key": cache_key},
            )
        )
        == 1
    )

    time.sleep(max_cache_lifetime * 2)

    # we create another conversation because expired messages are eliminated when running
    # the transform.
    second_conv = agent.start_conversation()
    for m in messages:
        second_conv.append_message(m)
    execute_conversation_check_summarizer_ran(second_conv, summarization_llm, agent_llm)

    if transform_type == MessageSummarizationTransform:
        assert (
            len(
                testing_data_store.list(
                    collection_name,
                    {"cache_key": cache_key},
                )
            )
            == 0
        )


@pytest.mark.filterwarnings(f"ignore:{_SUMMARIZATION_WARNING_MESSAGE}:UserWarning")
@pytest.mark.parametrize(
    "toolres_message_contents",
    [[], [TextContent(CONVERSATION_WITH_TOOL_REQUESTS[2].tool_result.content)]],
)
def test_summarization_transform_updates_tool_result_content(toolres_message_contents):

    max_message_size = 500
    assert CONVERSATION_WITH_TOOL_REQUESTS[2].tool_result is not None
    toolres_len = len(CONVERSATION_WITH_TOOL_REQUESTS[2].tool_result.content)
    assert toolres_len > max_message_size

    CONVERSATION_WITH_TOOL_REQUESTS[2].contents = toolres_message_contents

    summarization_llm = mock_llm()
    transform = MessageSummarizationTransform(
        llm=summarization_llm, max_message_size=max_message_size
    )
    agent_llm = mock_llm()

    @tool(description_mode="only_docstring")
    def retrieve_facts(subject: str) -> str:
        """A tool to retrieve facts on given subjects"""
        return ""

    agent = Agent(llm=agent_llm, tools=[retrieve_facts], transforms=[transform])

    conv = agent.start_conversation()
    for message in CONVERSATION_WITH_TOOL_REQUESTS:
        conv.append_message(message)

    summarized_message = "Dolphins are really smart"
    mock_generate_summary = AsyncMock(
        side_effect=lambda prompt: LlmCompletion(Message(summarized_message), None)
    )

    with patch_streaming_llm(agent_llm, "Dolphins are really intelligent") as patched_agent_llm:
        with patch.object(summarization_llm, "generate_async", mock_generate_summary):

            conv.execute()
            transformed_messages = [
                message
                for prompts, _ in patched_agent_llm.call_args_list
                for prompt in prompts
                for message in prompt.messages
            ]

            # long tool results should be summarized.
            assert transformed_messages[2].tool_result is not None
            assert summarized_message in transformed_messages[2].tool_result.content
            assert len(transformed_messages[2].tool_result.content) < toolres_len

            # contents should be summarized only if they are long
            if len("".join([c.content for c in toolres_message_contents])) > max_message_size:
                assert len(transformed_messages[2].content) < toolres_len
            else:
                assert transformed_messages[2].contents == toolres_message_contents


@pytest.mark.filterwarnings(f"ignore:{_SUMMARIZATION_WARNING_MESSAGE}:UserWarning")
@retry_test(max_attempts=4)
def test_summarization_transform_summarizes_images(remote_gemma_llm):
    """
    Failure rate:          0 out of 10
    Observed on:           2025-11-25
    Average success time:  9.15 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    transform = MessageSummarizationTransform(
        llm=remote_gemma_llm,
        datastore=None,
        cache_collection_name=MESSAGE_SUMMARIZATION_CACHE_COLLECTION_NAME,
        max_message_size=500,
    )
    messages = CONVERSATION_WITH_LONG_MESSAGES
    agent_llm = mock_llm()
    agent = Agent(llm=agent_llm, tools=[], transforms=[transform])

    conv = agent.start_conversation()
    for m in messages:
        conv.append_message(m)

    with patch_streaming_llm(agent_llm, "This is a mock llm generation.") as patched_agent_llm:
        conv.execute()
        transformed_messages = [
            message
            for prompts, _ in patched_agent_llm.call_args_list
            for prompt in prompts
            for message in prompt.messages
        ]
        assert "oracle" in transformed_messages[1].content.lower()
        assert "oracle" in transformed_messages[3].content.lower()
        assert IMAGE_CONTENT_PNG not in transformed_messages[1].contents
        assert IMAGE_CONTENT_JPEG not in transformed_messages[3].contents


@pytest.mark.filterwarnings(f"ignore:{_SUMMARIZATION_WARNING_MESSAGE}:UserWarning")
@retry_test(max_attempts=4)
def test_conversation_summarization_transform_summarizes_images(remote_gemma_llm):
    """
    Failure rate:          0 out of 10
    Observed on:           2025-11-25
    Average success time:  9.15 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    transform = ConversationSummarizationTransform(
        llm=remote_gemma_llm,
        datastore=None,
        cache_collection_name=CONVERSATION_SUMMARIZATION_CACHE_COLLECTION_NAME,
        max_num_messages=4,
        min_num_messages=1,
    )
    messages = LONG_CONVERSATION[:5]
    agent_llm = mock_llm()
    agent = Agent(llm=agent_llm, tools=[], transforms=[transform])

    conv = agent.start_conversation()
    for m in messages:
        conv.append_message(m)

    with patch_streaming_llm(agent_llm, "This is a mock llm generation.") as patched_agent_llm:
        conv.execute()
        transformed_messages = [
            message
            for prompts, _ in patched_agent_llm.call_args_list
            for prompt in prompts
            for message in prompt.messages
        ]
        assert "oracle" in transformed_messages[0].content.lower()


@retry_test(max_attempts=4)
@pytest.mark.filterwarnings(f"ignore:{_SUMMARIZATION_WARNING_MESSAGE}:UserWarning")
@pytest.mark.parametrize("messages", [CONVERSATION_WITH_LONG_MESSAGES, LONG_CONVERSATION])
def test_conversation_summarization_transformer_summarizes_long_conversations(
    messages, remote_gemma_llm
):
    """
    Failure rate:          0 out of 10
    Observed on:           2025-12-01
    Average success time:  4.33 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    transform = ConversationSummarizationTransform(
        llm=remote_gemma_llm, min_num_messages=5, max_num_messages=10
    )
    agent_llm = mock_llm()
    agent = Agent(llm=agent_llm, tools=[], transforms=[transform])
    check_conversation_summarization_transformer_summarizes_long_conversations(agent, messages)


@retry_test(max_attempts=4)
@pytest.mark.filterwarnings(f"ignore:{_INMEMORY_USER_WARNING}:UserWarning")
@pytest.mark.parametrize("messages", [CONVERSATION_WITH_LONG_MESSAGES, LONG_CONVERSATION])
def test_conversation_summarization_transformer_summarizes_long_conversations_from_agentspec(
    messages, converted_wayflow_agent_with_conversation_summarization_transform_from_agentspec
):
    """
    Failure rate:          0 out of 10
    Observed on:           2026-01-15
    Average success time:  4.33 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    agent = converted_wayflow_agent_with_conversation_summarization_transform_from_agentspec
    check_conversation_summarization_transformer_summarizes_long_conversations(agent, messages)


def conversation_summarization_transforms_setup(llm):
    datastore = InMemoryDatastore(
        {"test_conversation_cache": ConversationSummarizationTransform.get_entity_definition()}
    )
    summarization_llm = llm
    transform = ConversationSummarizationTransform(
        llm=summarization_llm,
        datastore=datastore,
        cache_collection_name="test_conversation_cache",
        max_num_messages=10,
        min_num_messages=5,
        summarized_conversation_template="Summarized conversation: {{summary}}",
    )
    return {
        "transforms": [transform],
        "datastore": datastore,
        "collection_name": "test_conversation_cache",
        "summarization_llm": summarization_llm,
    }


@pytest.mark.filterwarnings(f"ignore:{_INMEMORY_USER_WARNING}:UserWarning")
@pytest.mark.parametrize(
    "get_setup",
    [
        conversation_summarization_transforms_setup,
        message_and_conversation_summarization_transforms_setup,
    ],
)
def test_conversation_summarization_trigger_and_cache_incremental(get_setup):
    setup = get_setup(mock_llm())
    transforms = setup["transforms"]
    datastore = setup["datastore"]
    collection_name = setup["collection_name"]
    summarization_llm = setup["summarization_llm"]

    agent_llm = mock_llm()
    agent = Agent(llm=agent_llm, tools=[], transforms=transforms)

    # Mock summary generation
    summary = "Dolphins are the best."
    mock_generate_summary = AsyncMock(
        side_effect=lambda prompt: LlmCompletion(Message(summary), None)
    )

    conv = agent.start_conversation()

    # In total 10 messages (hello1 to hello5 and answers). We expect no summarization
    for i in range(5):
        conv.append_message(Message(message_type=MessageType.USER, content=f"hello {i+1}"))
        assert not execute_conversation_check_summarizer_ran(conv, summarization_llm, agent_llm)

    with patch.object(summarization_llm, "generate_async", mock_generate_summary):
        with patch_streaming_llm(agent_llm, "This is a mock llm generation.") as patched_agent_llm:

            # hello 6, message number 11.
            conv.append_message(Message(message_type=MessageType.USER, content=f"hello 6"))

            conv.execute()
            assert mock_generate_summary.call_count > 0
            transformed_messages = [
                message.content
                for prompts, _ in patched_agent_llm.call_args_list
                for prompt in prompts
                for message in prompt.messages
            ]

            assert len(transformed_messages) == 6
            assert transformed_messages[0] == "Summarized conversation: " + summary
            conversation_messsages_contents = [m.content for m in conv.get_messages()]
            assert transformed_messages[1:] == conversation_messsages_contents[6:11]

    for i in range(7, 9):
        conv.append_message(Message(message_type=MessageType.USER, content=f"hello {i}"))
        # conversation will have <= 10 messages and old summaries are cached.
        assert not execute_conversation_check_summarizer_ran(conv, summarization_llm, agent_llm)

    with patch.object(summarization_llm, "generate_async", mock_generate_summary):
        with patch_streaming_llm(agent_llm, "This is a mock llm generation.") as patched_agent_llm:

            # hello 9, message number 11.
            conv.append_message(Message(message_type=MessageType.USER, content=f"hello 9"))

            conv.execute()
            assert mock_generate_summary.call_count > 0
            transformed_messages = [
                message.content
                for prompts, _ in patched_agent_llm.call_args_list
                for prompt in prompts
                for message in prompt.messages
            ]
            assert len(transformed_messages) == 6
            # summary of message 0 to 11.
            assert transformed_messages[0] == "Summarized conversation: " + summary
            conversation_messsages_contents = [m.content for m in conv.get_messages()]
            # exclude last message which the agent just generated.
            assert transformed_messages[1:] == conversation_messsages_contents[-6:-1]

    datastore.delete(collection_name=collection_name, where={})

    conv.append_message(Message(message_type=MessageType.USER, content=f"hello 10"))
    # not cached, summarization should happen.
    assert execute_conversation_check_summarizer_ran(conv, summarization_llm, agent_llm)


@pytest.mark.filterwarnings(f"ignore:{_SUMMARIZATION_WARNING_MESSAGE}:UserWarning")
@pytest.mark.parametrize(
    "transform_type,params",
    [
        (MessageSummarizationTransform, {"max_message_size": 500}),
        (ConversationSummarizationTransform, {"max_num_messages": 10, "min_num_messages": 5}),
    ],
)
def test_summarization_transform_no_caching_when_datastore_none(transform_type, params):
    """Test that when datastore=None, no caching occurs for summarization transforms."""
    summarization_llm = mock_llm()
    agent_llm = mock_llm()

    transform = transform_type(llm=summarization_llm, datastore=None, **params)
    assert transform.cache is None

    agent = Agent(llm=agent_llm, tools=[], transforms=[transform])
    conversation = agent.start_conversation()

    # Add messages that trigger summarization
    if transform_type == MessageSummarizationTransform:
        messages = CONVERSATION_WITH_LONG_MESSAGES[:2]  # Include one short, one long message
    else:
        messages = LONG_CONVERSATION[:12]  # More than max_num_messages

    for m in messages:
        conversation.append_message(m)

    # First execution should run summarizer
    assert execute_conversation_check_summarizer_ran(conversation, summarization_llm, agent_llm)

    # Add another message and run again - should run summarizer again since no caching
    conversation.append_message(Message("This is another mock message."))
    assert execute_conversation_check_summarizer_ran(conversation, summarization_llm, agent_llm)


@pytest.mark.filterwarnings(f"ignore:{_SUMMARIZATION_WARNING_MESSAGE}:UserWarning")
def test_conversation_summarization_respects_tool_request_response_consistency():
    conversation = [
        Message(
            message_type=MessageType.USER,
            content="Hi! Can you tell me something interesting about dolphins and giraffes?",
        ),
        Message(
            contents=[],
            message_type=MessageType.TOOL_REQUEST,
            tool_requests=[
                ToolRequest(
                    name="retrieve_facts", args={"subject": "dolphin"}, tool_request_id="id1"
                )
            ],
        ),
        Message(
            contents=[],
            message_type=MessageType.TOOL_REQUEST,
            tool_requests=[
                ToolRequest(
                    name="retrieve_facts", args={"subject": "giraffe"}, tool_request_id="id2"
                )
            ],
        ),
        Message(
            contents=[],
            message_type=MessageType.TOOL_RESULT,
            tool_result=ToolResult(
                content=(
                    "Absolutely! Dolphins are fascinating creatures, famous for their intelligence and complex behavior. "
                ),
                tool_request_id="id1",
            ),
        ),
        Message(
            contents=[],
            message_type=MessageType.TOOL_RESULT,
            tool_result=ToolResult(
                content=(
                    "Absolutely! Giraffes are fascinating creatures, famous for their intelligence and complex behavior. "
                ),
                tool_request_id="id2",
            ),
        ),
    ]
    # even if min_num_messages = 2, we can't summarize the first 3 together because they lack tool results with id: id1.
    summarization_llm = mock_llm()
    transform = ConversationSummarizationTransform(
        llm=summarization_llm, max_num_messages=3, min_num_messages=2
    )
    agent_llm = mock_llm()
    agent = Agent(
        llm=agent_llm,
        tools=[],
        transforms=[transform],
    )

    conv = agent.start_conversation()
    for message in conversation:
        conv.append_message(message)

    summary = "Summarized early conversation with tool requests."
    mock_generate_summary = AsyncMock(
        side_effect=lambda prompt: LlmCompletion(Message(summary), None)
    )

    with patch.object(summarization_llm, "generate_async", mock_generate_summary):
        with patch_streaming_llm(agent_llm, "Mock agent response") as patched_agent_llm:
            conv.execute()

            transformed_messages = [
                message.content
                for prompts, _ in patched_agent_llm.call_args_list
                for prompt in prompts
                for message in prompt.messages
            ]

            assert len(transformed_messages) == 5


@pytest.mark.filterwarnings(f"ignore:{_SUMMARIZATION_WARNING_MESSAGE}:UserWarning")
def test_agent_transforms_should_run_before_canonicalization_with_gemma(remote_gemma_llm):

    main_content = (
        "Absolutely! Dolphins are fascinating creatures, famous for their intelligence and complex behavior. "
        "For example, they have been observed using tools, such as covering their snouts with sponges to protect themselves "
        "while foraging on the seafloor"
    )
    messages = [Message(role="user", content=main_content) for _ in range(4)]

    summarization_transform = ConversationSummarizationTransform(
        llm=remote_gemma_llm,
        max_num_messages=3,
        min_num_messages=1,
    )

    agent = Agent(llm=remote_gemma_llm, tools=[], transforms=[summarization_transform])

    conv = agent.start_conversation()
    for m in messages:
        conv.append_message(m)

    summary = "Summarized conversation"
    mock_generate_summary = AsyncMock(
        side_effect=lambda prompt: LlmCompletion(Message(summary), None)
    )

    with patch_llm(remote_gemma_llm, ["Mock Gemma response"]) as (_, patched_gemma_llm):
        with patch.object(remote_gemma_llm, "generate_async", mock_generate_summary):
            conv.execute()

            transformed_messages = [
                message
                for prompts, _ in patched_gemma_llm.call_args_list
                for prompt in prompts
                for message in prompt.messages
            ]

            # CanonicalizationMessageTransform should merge the summary and the last message into a single message.
            assert len(transformed_messages) == 1
            # If CanonicalizationMessageTransform runs AFTER ConversationSummarizationTransform
            # then summarization should happen.
            assert mock_generate_summary.call_count > 0
            # The messages received by the LLM were summarized.
            assert len(transformed_messages[0].content) <= len(main_content) * 2
