# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import time
from pathlib import Path
from typing import List, Optional
from unittest.mock import AsyncMock, patch

import pytest

from wayflowcore.agent import Agent
from wayflowcore.conversation import Conversation
from wayflowcore.datastore.entity import Entity
from wayflowcore.datastore.inmemory import InMemoryDatastore
from wayflowcore.messagelist import ImageContent, Message, MessageType, TextContent
from wayflowcore.models.llmmodel import LlmCompletion, LlmModel
from wayflowcore.property import FloatProperty, IntegerProperty, StringProperty
from wayflowcore.templates.llamatemplates import _LlamaMergeToolRequestAndCallsTransform
from wayflowcore.templates.pythoncalltemplates import _PythonMergeToolRequestAndCallsTransform
from wayflowcore.tools import ToolRequest, ToolResult, tool
from wayflowcore.transforms import (
    CoalesceSystemMessagesTransform,
    MessageSummarizationTransform,
    RemoveEmptyNonUserMessageTransform,
    SplitPromptOnMarkerMessageTransform,
)

from .conftest import mock_llm, patch_streaming_llm
from .datastores.conftest import cleanup_oracle_datastore, get_oracle_datastore_with_schema
from .testhelpers.testhelpers import retry_test


def assert_messages_are_correct(messages: List[Message], expected_messages: List[Message]):
    assert len(messages) == len(expected_messages), messages
    for message, expected_message in zip(messages, expected_messages):
        assert message.message_type == expected_message.message_type
        assert message.content == expected_message.content


SYSTEM_MESSAGE = Message(message_type=MessageType.SYSTEM, content="You are a helpful assistant")
USER_MESSAGE = Message(message_type=MessageType.USER, content="What is the capital of Switzerland?")
TOOL_REQUEST_MESSAGE = Message(
    message_type=MessageType.TOOL_REQUEST,
    tool_requests=[ToolRequest(name="some_tool", args={}, tool_request_id="id1")],
)
TOOL_RESULT = Message(
    message_type=MessageType.TOOL_RESULT,
    tool_result=ToolResult(tool_request_id="id1", content="some_output"),
)
AGENT_MESSAGE = Message(
    message_type=MessageType.AGENT, content="The capital of Switzerland is Bern"
)

IMAGE_CONTENT_PNG = ImageContent.from_bytes(
    bytes_content=(Path(__file__).parent / "configs/test_data/oracle_logo.png").read_bytes(),
    format="png",
)
IMAGE_CONTENT_JPEG = ImageContent.from_bytes(
    bytes_content=(Path(__file__).parent / "configs/test_data/oracle_logo.jpeg").read_bytes(),
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


@pytest.mark.parametrize(
    "messages,expected_messages",
    [
        ([USER_MESSAGE], [USER_MESSAGE]),
        ([SYSTEM_MESSAGE], [SYSTEM_MESSAGE]),
        (
            [SYSTEM_MESSAGE, SYSTEM_MESSAGE],
            [
                Message(
                    content="You are a helpful assistant\n\nYou are a helpful assistant",
                    message_type=MessageType.SYSTEM,
                )
            ],
        ),
        (
            [SYSTEM_MESSAGE, AGENT_MESSAGE, SYSTEM_MESSAGE],
            [SYSTEM_MESSAGE, AGENT_MESSAGE, SYSTEM_MESSAGE],
        ),
        (
            [SYSTEM_MESSAGE, SYSTEM_MESSAGE, SYSTEM_MESSAGE, AGENT_MESSAGE, SYSTEM_MESSAGE],
            [
                Message(
                    content="You are a helpful assistant\n\nYou are a helpful assistant\n\nYou are a helpful assistant",
                    message_type=MessageType.SYSTEM,
                ),
                AGENT_MESSAGE,
                SYSTEM_MESSAGE,
            ],
        ),
    ],
)
def test_coalesce_system_message_transform(messages, expected_messages):
    transform = CoalesceSystemMessagesTransform()
    transformed_messages = transform(messages)
    assert_messages_are_correct(transformed_messages, expected_messages)


EMPTY_USER_MESSAGE = Message(content="")
EMPTY_SYSTEM_MESSAGE = Message(content="", message_type=MessageType.SYSTEM)


@pytest.mark.parametrize(
    "messages,expected_messages",
    [
        (
            [AGENT_MESSAGE, EMPTY_USER_MESSAGE, EMPTY_SYSTEM_MESSAGE],
            [AGENT_MESSAGE, EMPTY_USER_MESSAGE],
        ),
        ([AGENT_MESSAGE, EMPTY_SYSTEM_MESSAGE, USER_MESSAGE], [AGENT_MESSAGE, USER_MESSAGE]),
        ([EMPTY_SYSTEM_MESSAGE, EMPTY_USER_MESSAGE], [EMPTY_USER_MESSAGE]),
    ],
)
def test_remove_empty_non_user_message_transform(messages, expected_messages):
    transform = RemoveEmptyNonUserMessageTransform()
    transformed_messages = transform(messages)
    assert_messages_are_correct(transformed_messages, expected_messages)


@pytest.mark.parametrize(
    "messages,expected_messages",
    [
        (
            [SYSTEM_MESSAGE, USER_MESSAGE, TOOL_REQUEST_MESSAGE, TOOL_RESULT, AGENT_MESSAGE],
            [
                Message(message_type=MessageType.SYSTEM, content="You are a helpful assistant"),
                USER_MESSAGE,
                Message(
                    message_type=MessageType.AGENT,
                    content='{"name": "some_tool", "parameters": {}}',
                ),
                Message(
                    message_type=MessageType.USER,
                    content='<tool_response>"some_output"</tool_response>',
                ),
                AGENT_MESSAGE,
            ],
        ),
    ],
)
def test_llama_merge_tool_request(messages, expected_messages):
    transform = _LlamaMergeToolRequestAndCallsTransform()
    transformed_messages = transform(messages)
    assert_messages_are_correct(transformed_messages, expected_messages)


COMPLEX_TOOL_REQUEST = Message(
    message_type=MessageType.TOOL_REQUEST,
    tool_requests=[
        ToolRequest(
            name="some_tool", args={"a": [1, 2, 3], "b": {1: "1"}, "c": True}, tool_request_id="id1"
        )
    ],
)


@pytest.mark.parametrize(
    "messages,expected_messages",
    [
        (
            [SYSTEM_MESSAGE, USER_MESSAGE, TOOL_REQUEST_MESSAGE, TOOL_RESULT, AGENT_MESSAGE],
            [
                Message(message_type=MessageType.SYSTEM, content="You are a helpful assistant"),
                USER_MESSAGE,
                Message(
                    message_type=MessageType.AGENT,
                    content="[some_tool()]",
                ),
                Message(
                    message_type=MessageType.USER,
                    content='<tool_response>"some_output"</tool_response>',
                ),
                AGENT_MESSAGE,
            ],
        ),
        (
            [SYSTEM_MESSAGE, USER_MESSAGE, COMPLEX_TOOL_REQUEST, TOOL_RESULT, AGENT_MESSAGE],
            [
                Message(message_type=MessageType.SYSTEM, content="You are a helpful assistant"),
                USER_MESSAGE,
                Message(
                    message_type=MessageType.AGENT,
                    content="[some_tool(a=[1, 2, 3],b={1: '1'},c=True)]",
                ),
                Message(
                    message_type=MessageType.USER,
                    content='<tool_response>"some_output"</tool_response>',
                ),
                AGENT_MESSAGE,
            ],
        ),
    ],
)
def test_python_merge_tool_request(messages, expected_messages):
    transform = _PythonMergeToolRequestAndCallsTransform()
    transformed_messages = transform(messages)
    assert_messages_are_correct(transformed_messages, expected_messages)


@pytest.mark.parametrize(
    "messages,expected_messages",
    [
        (
            [Message(message_type=MessageType.USER, content="First part\n---\nSecond part")],
            [
                Message(message_type=MessageType.USER, content="First part"),
                Message(message_type=MessageType.USER, content="Second part"),
            ],
        ),
        (
            [Message(message_type=MessageType.USER, content="A\n---\nB\n---\nC")],
            [
                Message(message_type=MessageType.USER, content="A"),
                Message(message_type=MessageType.USER, content="B"),
                Message(message_type=MessageType.USER, content="C"),
            ],
        ),
    ],
)
def test_split_prompt_on_marker(messages, expected_messages):
    transform = SplitPromptOnMarkerMessageTransform()
    transformed_messages = transform(messages)
    assert_messages_are_correct(transformed_messages, expected_messages)


@retry_test(max_attempts=4)
@pytest.mark.parametrize(
    "messages, long_msgs_indices",
    [(CONVERSATION_WITH_LONG_MESSAGES, [1, 3]), (CONVERSATION_WITH_TOOL_REQUESTS, [2, 5])],
)
def test_transform_summarizes_long_messages_only(remote_gemma_llm, messages, long_msgs_indices):
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
    # We have this check because this test requires short and long messages.
    assert len(long_messages) == 2 and len(short_messages) >= 3
    # We used different llms for summarization and agent
    transform = MessageSummarizationTransform(
        llm=remote_gemma_llm, max_message_size=max_message_size
    )
    # We pass a mock_llm because we will not need the agent's generation.
    agent_llm = mock_llm()
    agent = Agent(llm=agent_llm, tools=[], transforms=[transform])
    conversation = agent.start_conversation()
    for m in messages:
        conversation.append_message(m)

    with patch_streaming_llm(agent_llm, "This is a mock llm generation.") as patched_agent_llm:
        conversation.execute()

        # We will check that the messages passed to the llm where summarized iff they were long.
        transformed_messages = [
            message
            for prompts, _ in patched_agent_llm.call_args_list
            for prompt in prompts
            for message in prompt.messages
        ]
        assert len(transformed_messages) == len(messages)

        # We do this check to ensure that some information from the long message is kept. Otherwise
        # returning "" would pass the tests.
        def at_east_one_keyword_present(keywords: List[str], message: str) -> bool:
            return any([keyword.lower() in message.lower() for keyword in keywords])

        # These tests are not strict on purpose to avoid flakiness.
        assert at_east_one_keyword_present(
            ["smart", "intelligent", "social", "information", "signature"],
            transformed_messages[long_msgs_indices[0]].content,
        )
        assert at_east_one_keyword_present(
            ["memory", "20 year", "cognitive", "memories", "migrate"],
            transformed_messages[long_msgs_indices[1]].content,
        )

        for original_message, transformed_message in zip(messages, transformed_messages):
            if original_message.content in short_messages:
                assert original_message.content == transformed_message.content
            else:
                assert len(transformed_message.content) < len(original_message.content)


# Executes the conversation and Checks if the summarization LLM ran or not.
def execute_conversation_check_summarizer_ran(
    conversation: Conversation, summarization_llm: LlmModel, agent_llm: LlmModel
) -> bool:
    mock_generate_summary = AsyncMock(
        side_effect=lambda prompt: LlmCompletion(Message("Summary: Dolphins are amazing."), None)
    )
    with patch.object(summarization_llm, "generate_async", mock_generate_summary):
        with patch_streaming_llm(agent_llm, "This is a mock generation"):
            # We expect the transform to do summarization
            conversation.execute()
            return mock_generate_summary.call_count > 0


@pytest.fixture
def testing_oracle_data_store(collection_name: Optional[str]):
    # if collection name is none, the user needs to choose the default
    if not collection_name:
        collection_name = "summarized_messages_cache"
    schema = {collection_name: MessageSummarizationTransform.get_entity_definition()}
    yield get_oracle_datastore_with_schema(get_ddl_from_one_entity_schema(schema), schema)
    cleanup_oracle_datastore()


@pytest.fixture
def testing_no_datastore(collection_name: Optional[str]):
    return None


@pytest.fixture
def testing_inmemory_data_store(collection_name: Optional[str]):
    # if collection name is none, the default one is chosen.
    if not collection_name:
        collection_name = "summarized_messages_cache"
    return InMemoryDatastore(
        {collection_name: MessageSummarizationTransform.get_entity_definition()}
    )


@pytest.fixture(
    scope="function",
    params=["testing_inmemory_data_store", "testing_oracle_data_store", "testing_no_datastore"],
)
def testing_data_store(request):
    # https://stackoverflow.com/questions/42014484/pytest-using-fixtures-as-arguments-in-parametrize
    return request.getfixturevalue(request.param)


def cache_collection_names() -> List[Optional[str]]:
    return ["cache_table", None]


@pytest.mark.parametrize(
    "messages,collection_name",
    [(CONVERSATION_WITH_LONG_MESSAGES, name) for name in cache_collection_names()],
)
def test_summarization_transform_caches_summarization(
    messages, collection_name, testing_data_store
):
    summarization_llm = mock_llm()
    max_message_size = 500
    params = {
        "llm": summarization_llm,
        "max_message_size": max_message_size,
        "datastore": testing_data_store,
    }
    if collection_name:
        params["cache_collection_name"] = collection_name

    transform = MessageSummarizationTransform(**params)
    # We pass a mock_llm because we will not need the agent's generation.
    agent_llm = mock_llm()
    agent = Agent(llm=agent_llm, tools=[], transforms=[transform])
    conversation = agent.start_conversation()
    assert len(messages[0].content) < max_message_size
    conversation.append_message(messages[0])
    assert len(messages[1].content) > max_message_size
    conversation.append_message(messages[1])

    # On first try the conversation should not be cached.
    assert execute_conversation_check_summarizer_ran(conversation, summarization_llm, agent_llm)

    # Now we expect that our long message has been cached and the summarizer did not run.
    conversation.append_message(Message("This is another mock message."))
    assert not execute_conversation_check_summarizer_ran(conversation, summarization_llm, agent_llm)


@pytest.mark.parametrize(
    "messages,collection_name",
    [(CONVERSATION_WITH_LONG_MESSAGES, name) for name in cache_collection_names()],
)
def test_summarization_transform_cache_evicts_lru(messages, collection_name, testing_data_store):
    summarization_llm = mock_llm()
    max_message_size = 500
    # It's better to have a small cache size in tests. Otherwise, tests with DB take too long
    max_cache_size = 6
    params = {
        "llm": summarization_llm,
        "max_message_size": max_message_size,
        "max_cache_size": max_cache_size,
        "datastore": testing_data_store,
    }
    if collection_name:
        params["cache_collection_name"] = collection_name
    transform = MessageSummarizationTransform(**params)
    # We pass a mock_llm because we will not need the agent's generation.
    agent_llm = mock_llm()
    agent = Agent(llm=agent_llm, tools=[], transforms=[transform])

    def run_many_conversations(n_convs):
        conversations = []
        for _ in range(n_convs):
            conv = agent.start_conversation()
            assert len(messages[0].content) < max_message_size
            conv.append_message(messages[0])
            assert len(messages[1].content) > max_message_size
            conv.append_message(messages[1])

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


def get_ddl_from_one_entity_schema(schema: dict[str, "Entity"]) -> list[str]:
    entity_name = next(iter(schema.keys()), None)
    if not entity_name:
        return [""]

    entity = schema[entity_name]
    prop_lines = []
    for prop_name, prop_type in entity.properties.items():
        if isinstance(prop_type, StringProperty):
            sql_type = "VARCHAR(200)"
        elif isinstance(prop_type, IntegerProperty) or isinstance(prop_type, FloatProperty):
            sql_type = "NUMBER"
        else:
            sql_type = "CLOB"
        prop_lines.append(f"    {prop_name} {sql_type}")
    props_str = ",\n".join(prop_lines)
    ddl = f"CREATE TABLE {entity_name} (\n{props_str}\n)"

    drop = f"DROP TABLE IF EXISTS {entity_name}"
    return [drop, ddl]


def get_wrong_schemas(collection_name):
    entity = MessageSummarizationTransform.get_entity_definition()
    prop_keys = list(entity.properties.keys())

    wrong_entities = []
    for i in range(len(prop_keys)):
        keys_to_include = prop_keys[:i] + prop_keys[i + 1 :]
        new_properties = {k: entity.properties[k] for k in keys_to_include}
        wrong_entity = Entity(properties=new_properties)
        wrong_entities.append(wrong_entity)
    wrong_entities.append(Entity(properties={"conversation_id": StringProperty()}))
    return [{collection_name: entity} for entity in wrong_entities]


@pytest.fixture
def bad_datastore(request):
    schema = request.param
    ds = get_oracle_datastore_with_schema(get_ddl_from_one_entity_schema(schema), schema)
    yield ds
    cleanup_oracle_datastore()


@pytest.fixture
def bad_inmemory_datastore(request):
    schema = request.param
    return InMemoryDatastore(schema)


@pytest.mark.parametrize(
    "bad_datastore",
    get_wrong_schemas(MessageSummarizationTransform.DEFAULT_CACHE_COLLECTION_NAME)
    + [
        # Use wrong table name but correct entity structure.
        {"wrong_table_name": MessageSummarizationTransform.get_entity_definition()}
    ],
    indirect=True,
)
def test_summarization_transform_raises_error_incorrect_oracle_ds_schema(bad_datastore):
    with pytest.raises(ValueError):
        MessageSummarizationTransform(
            llm=mock_llm(),
            datastore=bad_datastore,
            cache_collection_name=MessageSummarizationTransform.DEFAULT_CACHE_COLLECTION_NAME,
        )


@pytest.mark.parametrize(
    "bad_inmemory_datastore",
    # correct table name but wrong schema:
    get_wrong_schemas("summarized_messages_cache")
    # wrong table name but correct entity definition
    + [{"wrong_table_name": MessageSummarizationTransform.get_entity_definition()}],
    indirect=True,
)
def test_summarization_transform_raises_error_incorrect_inmemory_ds_schema(bad_inmemory_datastore):
    with pytest.raises(ValueError):
        MessageSummarizationTransform(
            llm=mock_llm(),
            datastore=bad_inmemory_datastore,
            cache_collection_name=MessageSummarizationTransform.DEFAULT_CACHE_COLLECTION_NAME,
        )


@pytest.mark.parametrize(
    "messages,collection_name", [(CONVERSATION_WITH_LONG_MESSAGES, "cache_table")]
)
def test_summarization_transform_removes_expired_messages(
    messages, collection_name, testing_data_store
):
    if not testing_data_store:
        return
    summarization_llm = mock_llm()
    max_message_size = 500
    max_cache_lifetime = 1
    transform = MessageSummarizationTransform(
        llm=summarization_llm,
        max_message_size=max_message_size,
        max_cache_lifetime=max_cache_lifetime,
        cache_collection_name=collection_name,
        datastore=testing_data_store,
    )
    agent_llm = mock_llm()
    agent = Agent(llm=agent_llm, tools=[], transforms=[transform])

    first_conv = agent.start_conversation()
    assert len(messages[0].content) < max_message_size
    first_conv.append_message(messages[0])
    assert len(messages[1].content) > max_message_size
    first_conv.append_message(messages[1])

    execute_conversation_check_summarizer_ran(first_conv, summarization_llm, agent_llm)

    assert (
        len(
            testing_data_store.list(
                collection_name,
                {"cache_key": str(first_conv.id) + "_1_content"},  # second message is the long one.
            )
        )
        == 1
    )
    time.sleep(max_cache_lifetime * 2)

    # we create another conversation because expired message at eliminated when running
    # the transform.
    second_conv = agent.start_conversation()
    second_conv.append_message(messages[0])
    second_conv.append_message(messages[1])
    execute_conversation_check_summarizer_ran(second_conv, summarization_llm, agent_llm)
    assert (
        len(
            testing_data_store.list(
                collection_name,
                {"cache_key": str(first_conv.id) + "_1_content"},  # second message is the long one.
            )
        )
        == 0
    )


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
    summarization_llm = remote_gemma_llm
    max_message_size = 500
    transform = MessageSummarizationTransform(
        llm=summarization_llm, max_message_size=max_message_size
    )
    agent_llm = mock_llm()
    agent = Agent(llm=agent_llm, tools=[], transforms=[transform])

    conv = agent.start_conversation()
    for m in CONVERSATION_WITH_LONG_MESSAGES:
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
        assert IMAGE_CONTENT_PNG not in transformed_messages[3].contents
