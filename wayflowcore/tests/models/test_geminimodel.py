# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import os
from typing import Annotated

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm
import pytest
from litellm.types.utils import ChatCompletionDeltaToolCall, Choices, Delta, Function
from litellm.types.utils import Message as LiteLLMMessage
from litellm.types.utils import ModelResponse, ModelResponseStream, StreamingChoices

from tests.testhelpers import litellm_testhelpers
from tests.testhelpers.testhelpers import retry_test
from wayflowcore.messagelist import Message
from wayflowcore.models._requesthelpers import StreamChunkType
from wayflowcore.models.geminimodel import GeminiApiKeyAuth, GeminiCloudAuth, GeminiModel
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.llmmodel import Prompt
from wayflowcore.models.llmmodelfactory import LlmModelFactory
from wayflowcore.serialization.serializer import serialize_to_dict
from wayflowcore.tools import ToolResult, tool

_ADC_CREDENTIALS_PATH = litellm_testhelpers.ADC_CREDENTIALS_PATH
_VERTEX_CREDENTIALS_PROJECT_ID = litellm_testhelpers.VERTEX_CREDENTIALS_PROJECT_ID
_VERTEX_ADC_PROJECT_ID = litellm_testhelpers.VERTEX_ADC_PROJECT_ID
_VERTEX_ADC_LOCATION = litellm_testhelpers.VERTEX_ADC_LOCATION
litellm_anyio_cleanup = litellm_testhelpers.litellm_anyio_cleanup
litellm_thread_cleanup = litellm_testhelpers.litellm_thread_cleanup


def _stream_and_collect_sync(llm: GeminiModel, prompt: Prompt) -> tuple[str, Message]:
    streamed_text = ""
    final_message: Message | None = None

    for chunk_type, message in llm.stream_generate(prompt):
        if chunk_type == StreamChunkType.TEXT_CHUNK:
            streamed_text += message.content
        elif chunk_type == StreamChunkType.END_CHUNK:
            final_message = message

    assert final_message is not None
    return streamed_text, final_message


async def _stream_and_collect_async(llm: GeminiModel, prompt: Prompt) -> tuple[str, Message]:
    streamed_text = ""
    final_message: Message | None = None

    async for chunk_type, message in llm.stream_generate_async(prompt):
        if chunk_type == StreamChunkType.TEXT_CHUNK:
            streamed_text += message.content
        elif chunk_type == StreamChunkType.END_CHUNK:
            final_message = message

    assert final_message is not None
    return streamed_text, final_message


@pytest.fixture
def vertex_gemini_model():
    llm = GeminiModel(
        model_id="gemini-2.0-flash-lite",
        auth=GeminiCloudAuth(
            project_id=_VERTEX_CREDENTIALS_PROJECT_ID,
            location=_VERTEX_ADC_LOCATION,
            vertex_credentials=os.environ["VERTEX_CREDENTIALS"],
        ),
    )
    return llm


@pytest.fixture
def vertex_gemini_model_without_explicit_credentials():
    llm = GeminiModel(
        model_id="gemini-2.0-flash-lite",
        auth=GeminiCloudAuth(project_id=_VERTEX_ADC_PROJECT_ID, location=_VERTEX_ADC_LOCATION),
    )
    return llm


@pytest.fixture
def prompt_with_tool():
    @tool
    def tool_greet(echo_text: Annotated[str, "text to echo back"]) -> str:
        """Return the provided text verbatim."""
        return echo_text

    return Prompt(
        messages=[
            Message(role="system", content="You are an efficient assistant."),
            Message(role="user", content="Call tool_greet with echo_text='hello'"),
        ],
        tools=[tool_greet],
    )


@pytest.fixture
def prompt_without_tool():
    return Prompt(
        messages=[
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Tell me a 2 sentence fun fact about Bern."),
        ]
    )


@pytest.fixture
def prompt_with_tool_replay(prompt_with_tool: Prompt) -> Prompt:
    return Prompt(
        messages=[
            Message(role="system", content="You are an efficient assistant."),
            Message(
                role="user",
                content=(
                    "You MUST call tool_greet with echo_text='hello'. "
                    "DO NOT reply to the user until after you receive the tool result. "
                    "After receiving the tool result, reply with exactly: echoed: hello"
                ),
            ),
        ],
        tools=prompt_with_tool.tools,
    )


def test_geminimodel_factory_supports_gemini_configs() -> None:
    llm = LlmModelFactory.from_config(
        {
            "model_type": "gemini",
            "model_id": "gemini-2.5-flash",
            "auth": {"type": "api_key"},
        }
    )

    assert isinstance(llm, GeminiModel)
    assert isinstance(llm.auth, GeminiApiKeyAuth)
    assert llm.model_id == "gemini-2.5-flash"

    request = llm._build_litellm_request(
        Prompt(messages=[Message(role="user", content="Hello")]),
        stream=False,
    )
    assert request["model"] == "gemini/gemini-2.5-flash"


def test_geminimodel_requires_explicit_auth() -> None:
    with pytest.raises(TypeError, match="auth"):
        GeminiModel(model_id="gemini-2.5-flash")  # type: ignore[call-arg]


def test_geminimodel_factory_requires_auth() -> None:
    with pytest.raises(ValueError, match="non-null 'auth' configuration"):
        LlmModelFactory.from_config(
            {
                "model_type": "gemini",
                "model_id": "gemini-2.5-flash",
            }
        )


def test_geminimodel_factory_requires_explicit_auth_type() -> None:
    with pytest.raises(ValueError, match="include a 'type' field"):
        LlmModelFactory.from_config(
            {
                "model_type": "gemini",
                "model_id": "gemini-2.5-flash",
                "auth": {},
            }
        )


def test_geminimodel_build_request_accepts_vertex_credentials_dict() -> None:
    llm = GeminiModel(
        model_id="gemini-2.0-flash-lite",
        auth=GeminiCloudAuth(
            project_id="project-id",
            location="global",
            vertex_credentials={
                "type": "service_account",
                "private_key": "line1\\nline2",
            },
        ),
    )

    request = llm._build_litellm_request(
        Prompt(messages=[Message(role="user", content="Hello")]),
        stream=False,
    )

    assert request["vertex_project"] == "project-id"
    assert request["vertex_location"] == "global"
    assert request["model"] == "vertex_ai/gemini-2.0-flash-lite"
    assert request["vertex_credentials"]["private_key"] == "line1\nline2"


def test_geminimodel_build_request_accepts_vertex_credentials_json_string() -> None:
    llm = GeminiModel(
        model_id="gemini-2.0-flash-lite",
        auth=GeminiCloudAuth(
            project_id="project-id",
            location="global",
            vertex_credentials=json.dumps(
                {
                    "type": "service_account",
                    "private_key": "line1\\nline2",
                }
            ),
        ),
    )

    request = llm._build_litellm_request(
        Prompt(messages=[Message(role="user", content="Hello")]),
        stream=False,
    )

    assert request["vertex_project"] == "project-id"
    assert request["vertex_location"] == "global"
    assert request["model"] == "vertex_ai/gemini-2.0-flash-lite"
    assert request["vertex_credentials"]["private_key"] == "line1\nline2"


def test_litellm_testhelpers_read_vertex_project_id_from_inline_json(monkeypatch) -> None:
    monkeypatch.setenv("VERTEX_CREDENTIALS", json.dumps({"project_id": "project-id"}))

    assert litellm_testhelpers.get_vertex_credentials_dict() == {"project_id": "project-id"}
    assert litellm_testhelpers._get_vertex_project_id_from_service_account_credentials() == (
        "project-id"
    )


def test_geminicloudauth_defaults_to_global_location() -> None:
    assert GeminiCloudAuth().location == "global"


def test_geminimodel_runtime_config_roundtrip_omits_secret_vertex_credentials() -> None:
    llm = GeminiModel(
        model_id="gemini-2.0-flash-lite",
        auth=GeminiCloudAuth(
            project_id="project-id",
            location="global",
            vertex_credentials={
                "type": "service_account",
                "private_key": "line1\\nline2",
            },
        ),
        supports_structured_generation=False,
        supports_tool_calling=False,
    )

    serialized_llm = serialize_to_dict(llm)

    assert serialized_llm["auth"] == {
        "type": "cloud",
        "project_id": "project-id",
        "location": "global",
    }
    assert serialized_llm["supports_structured_generation"] is False
    assert serialized_llm["supports_tool_calling"] is False

    deserialized_llm = LlmModelFactory.from_config(serialized_llm)

    assert isinstance(deserialized_llm, GeminiModel)
    assert deserialized_llm.auth == GeminiCloudAuth(project_id="project-id", location="global")
    assert deserialized_llm.supports_structured_generation is False
    assert deserialized_llm.supports_tool_calling is False

    request = deserialized_llm._build_litellm_request(
        Prompt(messages=[Message(role="user", content="Hello")]),
        stream=False,
    )
    assert request["vertex_project"] == "project-id"
    assert request["vertex_location"] == "global"
    assert "vertex_credentials" not in request


def test_geminimodel_preserves_message_extra_content_without_wrapping() -> None:
    llm = GeminiModel(model_id="gemini-2.5-flash", auth=GeminiApiKeyAuth())
    response = ModelResponse(
        model="gemini/gemini-2.5-flash",
        choices=[
            Choices(
                index=0,
                finish_reason="stop",
                message=LiteLLMMessage(
                    role="assistant",
                    content="hello",
                    provider_specific_fields={"foo": "bar"},
                ),
            )
        ],
    )

    message = llm._litellm_adapter.litellm_response_to_wayflow_message(response)

    assert message.content == "hello"
    assert message._extra_content == {"foo": "bar"}


def test_geminimodel_streaming_reconstructs_partial_tool_call_deltas() -> None:
    llm = GeminiModel(model_id="gemini-2.5-flash", auth=GeminiApiKeyAuth())
    stream_state = llm._litellm_adapter.new_stream_state()
    first_function = Function(name="tool_g", arguments='{"echo')
    second_function = Function(name="reet", arguments='_text": "hello"}')

    first_chunk = ModelResponseStream(
        choices=[
            StreamingChoices(
                delta=Delta(
                    tool_calls=[
                        ChatCompletionDeltaToolCall(
                            index=0,
                            id="call_1",
                            type="function",
                            function=first_function,
                        )
                    ]
                )
            )
        ]
    )
    second_chunk = ModelResponseStream(
        choices=[
            StreamingChoices(
                delta=Delta(
                    tool_calls=[
                        ChatCompletionDeltaToolCall(
                            index=0,
                            type="function",
                            function=second_function,
                        )
                    ]
                )
            )
        ]
    )

    llm._litellm_adapter.ingest_litellm_stream_chunk(stream_state, first_chunk)
    llm._litellm_adapter.ingest_litellm_stream_chunk(stream_state, second_chunk)
    message = llm._litellm_adapter.stream_state_to_wayflow_message(stream_state)

    assert message.tool_requests is not None
    assert len(message.tool_requests) == 1
    assert message.tool_requests[0].name == "tool_greet"
    assert message.tool_requests[0].args == {"echo_text": "hello"}
    assert message.tool_requests[0].tool_request_id == "call_1"


@pytest.mark.anyio
async def test_geminimodel_sync_generate_uses_async_bridge_outside_plain_sync(monkeypatch) -> None:
    llm = GeminiModel(model_id="gemini-2.5-flash", auth=GeminiApiKeyAuth(api_key="test-key"))
    prompt = Prompt(messages=[Message(role="user", content="Hello")])
    call_counts = {"async": 0, "sync": 0}

    async def fake_acompletion(**_kwargs):
        call_counts["async"] += 1
        return {
            "choices": [{"message": {"role": "assistant", "content": "hello"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    def fake_completion(**_kwargs):
        call_counts["sync"] += 1
        pytest.fail("Gemini sync generate should use litellm.acompletion outside plain sync")

    monkeypatch.setattr("wayflowcore.models.geminimodel.litellm.acompletion", fake_acompletion)
    monkeypatch.setattr("wayflowcore.models.geminimodel.litellm.completion", fake_completion)

    with pytest.warns(
        UserWarning,
        match="Please use the asynchronous method equivalent: generate_async",
    ):
        completion = llm.generate(prompt)

    assert completion.message.content == "hello"
    assert call_counts == {"async": 1, "sync": 0}


@pytest.mark.skipif(
    not os.getenv("VERTEX_CREDENTIALS") or not _VERTEX_CREDENTIALS_PROJECT_ID,
    reason="Gemini Vertex-auth test credentials not set up",
)
def test_geminimodel_vertex_sync(
    vertex_gemini_model: GeminiModel,
    prompt_with_tool: Prompt,
    litellm_thread_cleanup,
) -> None:
    completion = vertex_gemini_model.generate(prompt_with_tool)
    assert completion.message.tool_requests is not None
    assert completion.message.tool_requests[0].name == "tool_greet"


@pytest.mark.skipif(
    not _ADC_CREDENTIALS_PATH.exists() or not _VERTEX_ADC_PROJECT_ID,
    reason="Gemini ADC-backed Vertex auth not set up",
)
@pytest.mark.filterwarnings(
    "ignore:Your application has authenticated using end user credentials from Google Cloud SDK without a quota project.*:UserWarning"
)
def test_geminimodel_vertex_sync_without_vertex_credentials(
    vertex_gemini_model_without_explicit_credentials: GeminiModel,
    prompt_with_tool: Prompt,
    litellm_thread_cleanup,
) -> None:
    completion = vertex_gemini_model_without_explicit_credentials.generate(prompt_with_tool)
    assert completion.message.tool_requests is not None
    assert completion.message.tool_requests[0].name == "tool_greet"


@pytest.mark.skipif(
    not _ADC_CREDENTIALS_PATH.exists() or not _VERTEX_ADC_PROJECT_ID,
    reason="Gemini ADC-backed Vertex auth not set up",
)
@pytest.mark.filterwarnings(
    "ignore:Your application has authenticated using end user credentials from Google Cloud SDK without a quota project.*:UserWarning"
)
def test_geminimodel_vertex_e2e_can_continue_after_tool_call_with_replayed_history(
    vertex_gemini_model_without_explicit_credentials: GeminiModel,
    prompt_with_tool_replay: Prompt,
    litellm_thread_cleanup,
) -> None:
    prompt = prompt_with_tool_replay.copy()
    completion = vertex_gemini_model_without_explicit_credentials.generate(prompt)
    assert completion.message.tool_requests is not None

    first_tool_request = completion.message.tool_requests[0]
    prompt.messages.append(completion.message)
    prompt.messages.append(
        Message(tool_result=ToolResult("hello", first_tool_request.tool_request_id))
    )

    follow_up_completion = vertex_gemini_model_without_explicit_credentials.generate(prompt)
    assert follow_up_completion.message is not None
    assert "echoed: hello" in follow_up_completion.message.content.lower()


@pytest.mark.skipif(
    not os.getenv("VERTEX_CREDENTIALS") or not _VERTEX_CREDENTIALS_PROJECT_ID,
    reason="Gemini Vertex-auth test credentials not set up",
)
@pytest.mark.anyio
async def test_geminimodel_vertex_async(
    vertex_gemini_model: GeminiModel,
    prompt_with_tool: Prompt,
    litellm_thread_cleanup,
) -> None:
    completion = await vertex_gemini_model.generate_async(prompt_with_tool)
    assert completion.message.tool_requests is not None
    assert completion.message.tool_requests[0].name == "tool_greet"


@pytest.mark.skipif(
    not os.getenv("VERTEX_CREDENTIALS") or not _VERTEX_CREDENTIALS_PROJECT_ID,
    reason="Gemini Vertex-auth test credentials not set up",
)
def test_litellm_works_properly(litellm_thread_cleanup) -> None:
    vertex_credentials = litellm_testhelpers.get_vertex_credentials_dict()
    assert vertex_credentials is not None
    vertex_credentials_json = json.dumps(vertex_credentials)
    response = litellm.completion(
        model="vertex_ai/gemini-2.0-flash-lite",
        messages=[{"content": "Hello, how are you?", "role": "user"}],
        vertex_credentials=vertex_credentials_json,
    )
    assert response.choices


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="Gemini LLM auth not set up")
@retry_test(max_attempts=9)
def test_geminimodel_aistudio_gemini3_pro_preview_thought_signature(
    prompt_with_tool_replay,
    litellm_thread_cleanup,
) -> None:
    """
    Failure rate:          3 out of 10
    Observed on:           2026-03-10
    Average success time:  8.16 seconds per successful attempt
    Average failure time:  10.29 seconds per failed attempt
    Max attempt:           9
    Justification:         (0.33 ** 9) ~= 5.1 / 100'000
    """
    llm = GeminiModel(
        model_id="gemini-3-pro-preview",
        auth=GeminiApiKeyAuth(api_key=os.environ["GEMINI_API_KEY"]),
        generation_config=LlmGenerationConfig(extra_args={"reasoning_effort": "low"}),
    )
    prompt = prompt_with_tool_replay.copy()
    completion = llm.generate(prompt)
    assert completion.message is not None
    tool_requests = completion.message.tool_requests
    assert tool_requests is not None
    first_tool_request = tool_requests[0]
    assert isinstance(first_tool_request._extra_content, dict)
    thought_signature = first_tool_request._extra_content.get("thought_signature")
    assert isinstance(thought_signature, str)
    assert thought_signature

    prompt.messages.append(completion.message)
    prompt.messages.append(
        Message(tool_result=ToolResult("hello", first_tool_request.tool_request_id))
    )

    follow_up_completion = llm.generate(prompt)
    assert follow_up_completion.message is not None
    assert "echoed: hello" in follow_up_completion.message.content.lower()


@pytest.mark.skipif(
    not os.getenv("VERTEX_CREDENTIALS") or not _VERTEX_CREDENTIALS_PROJECT_ID,
    reason="Gemini Vertex-auth test credentials not set up",
)
def test_geminimodel_vertex_streaming_text_matches_final_sync(
    vertex_gemini_model: GeminiModel,
    prompt_without_tool,
    litellm_thread_cleanup,
) -> None:
    streamed_text, final_message = _stream_and_collect_sync(
        vertex_gemini_model, prompt_without_tool
    )
    assert final_message.content
    assert final_message.content in streamed_text


@pytest.mark.skipif(
    not os.getenv("VERTEX_CREDENTIALS") or not _VERTEX_CREDENTIALS_PROJECT_ID,
    reason="Gemini Vertex-auth test credentials not set up",
)
@pytest.mark.anyio
async def test_geminimodel_vertex_streaming_text_matches_final_async(
    vertex_gemini_model: GeminiModel,
    prompt_without_tool,
    litellm_thread_cleanup,
) -> None:
    streamed_text, final_message = await _stream_and_collect_async(
        vertex_gemini_model, prompt_without_tool
    )
    assert final_message.content
    assert final_message.content in streamed_text


@pytest.mark.skipif(
    not os.getenv("VERTEX_CREDENTIALS") or not _VERTEX_CREDENTIALS_PROJECT_ID,
    reason="Gemini Vertex-auth test credentials not set up",
)
def test_geminimodel_vertex_streaming_tool_call_sync(
    vertex_gemini_model: GeminiModel,
    prompt_with_tool: Prompt,
    litellm_thread_cleanup,
) -> None:
    _streamed_text, final_message = _stream_and_collect_sync(vertex_gemini_model, prompt_with_tool)
    assert final_message.tool_requests is not None
    assert final_message.tool_requests[0].name == "tool_greet"


@pytest.mark.skipif(
    not os.getenv("VERTEX_CREDENTIALS") or not _VERTEX_CREDENTIALS_PROJECT_ID,
    reason="Gemini Vertex-auth test credentials not set up",
)
@pytest.mark.anyio
async def test_geminimodel_vertex_streaming_tool_call_async(
    vertex_gemini_model: GeminiModel,
    prompt_with_tool: Prompt,
    litellm_thread_cleanup,
) -> None:
    _streamed_text, final_message = await _stream_and_collect_async(
        vertex_gemini_model, prompt_with_tool
    )
    assert final_message.tool_requests is not None
    assert final_message.tool_requests[0].name == "tool_greet"


@pytest.mark.skipif(
    not os.getenv("VERTEX_CREDENTIALS") or not _VERTEX_CREDENTIALS_PROJECT_ID,
    reason="Gemini Vertex-auth test credentials not set up",
)
def test_geminimodel_vertex_counts_tokens_sync(
    vertex_gemini_model: GeminiModel,
    prompt_without_tool: Prompt,
    litellm_thread_cleanup,
) -> None:
    prompt = prompt_without_tool.copy(generation_config=LlmGenerationConfig(max_tokens=32))
    completion = vertex_gemini_model.generate(prompt)
    assert completion.token_usage is not None
    assert completion.token_usage.exact_count
    assert completion.token_usage.input_tokens > 0
    assert completion.token_usage.output_tokens > 0
    assert completion.token_usage.total_tokens == (
        completion.token_usage.input_tokens + completion.token_usage.output_tokens
    )
