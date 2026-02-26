# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import os
import threading
from typing import Annotated

import litellm
import pytest
import pytest_asyncio

from wayflowcore.messagelist import Message
from wayflowcore.models._requesthelpers import StreamChunkType
from wayflowcore.models.geminimodel import GeminiApiKeyAuth, GeminiCloudAuth, GeminiModel
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.llmmodel import Prompt
from wayflowcore.tools import tool


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


def _cleanup_litellm_threads(*, threads_before: set[int]) -> None:
    """Shutdown threads spawned by LiteLLM/httpx during a test.

    LiteLLM/httpx may start a `ThreadPoolExecutor` worker thread that can linger
    past the test, and WayFlow's `pytest_sessionfinish` hook treats this as an
    error.

    This cleanup is intentionally narrow: it only shuts down threads that were
    *not* present before the test began, and only for threads which match the
    `ThreadPoolExecutor-*` naming pattern.
    """
    import gc
    import threading
    from concurrent.futures import ThreadPoolExecutor

    threads_after = {
        t.ident
        for t in threading.enumerate()
        if t is not threading.main_thread() and t.ident is not None
    }
    spawned_thread_idents = threads_after - threads_before

    if not spawned_thread_idents:
        return

    for executor in [o for o in gc.get_objects() if isinstance(o, ThreadPoolExecutor)]:
        for thread in getattr(executor, "_threads", set()):
            if thread.ident in spawned_thread_idents and thread.name.startswith(
                "ThreadPoolExecutor-"
            ):
                executor.shutdown(wait=True, cancel_futures=True)
                break


@pytest.fixture(scope="session")
def litellm_thread_cleanup():
    threads_before = {t.ident for t in threading.enumerate() if t.ident is not None}
    yield
    litellm.module_level_client.close()
    _cleanup_litellm_threads(threads_before=threads_before)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def litellm_async_client_cleanup():
    yield
    await litellm.close_litellm_async_clients()
    await litellm.module_level_aclient.close()


@pytest.fixture
def vertex_gemini_model():
    llm = GeminiModel(
        model_id="vertex_ai/gemini-2.0-flash-lite",
        auth=GeminiCloudAuth(vertex_credentials=os.environ["VERTEX_CREDENTIALS"]),
    )
    try:
        yield llm
    finally:
        pass
        # _asyncio_run_and_cleanup(llm.aclose())


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


@pytest.mark.skipif(not os.getenv("VERTEX_CREDENTIALS"), reason="Gemini LLM auth not set up")
def test_geminimodel_vertex_sync(
    vertex_gemini_model: GeminiModel,
    prompt_with_tool: Prompt,
    litellm_thread_cleanup,
) -> None:
    completion = vertex_gemini_model.generate(prompt_with_tool)
    assert completion.message.tool_requests is not None
    assert completion.message.tool_requests[0].name == "tool_greet"


@pytest.mark.skipif(not os.getenv("VERTEX_CREDENTIALS"), reason="Gemini LLM auth not set up")
@pytest.mark.asyncio(loop_scope="session")
async def test_geminimodel_vertex_async(
    vertex_gemini_model: GeminiModel,
    prompt_with_tool: Prompt,
    litellm_async_client_cleanup,
    litellm_thread_cleanup,
) -> None:
    completion = await vertex_gemini_model.generate_async(prompt_with_tool)
    assert completion.message.tool_requests is not None
    assert completion.message.tool_requests[0].name == "tool_greet"


@pytest.mark.skipif(not os.getenv("VERTEX_CREDENTIALS"), reason="Gemini LLM auth not set up")
def test_litellm_works_properly(litellm_thread_cleanup) -> None:
    with open(os.environ["VERTEX_CREDENTIALS"], "r") as file:
        vertex_credentials = json.load(file)
    vertex_credentials_json = json.dumps(vertex_credentials)
    response = litellm.completion(
        model="vertex_ai/gemini-2.0-flash-lite",
        messages=[{"content": "Hello, how are you?", "role": "user"}],
        vertex_credentials=vertex_credentials_json,
    )
    assert response.choices


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="Gemini LLM auth not set up")
def test_geminimodel_aistudio_gemini3_pro_preview_thought_signature(
    prompt_with_tool,
    litellm_thread_cleanup,
) -> None:
    llm = GeminiModel(
        model_id="gemini/gemini-3-pro-preview",
        auth=GeminiApiKeyAuth(api_key=os.environ["GEMINI_API_KEY"]),
        generation_config=LlmGenerationConfig(extra_args={"reasoning_effort": "low"}),
    )
    completion = llm.generate(prompt_with_tool)
    assert completion.message is not None
    thought_signatures = completion.message._extra_content["provider_specific_fields"][
        "thought_signatures"
    ]
    assert isinstance(thought_signatures, list)
    assert thought_signatures


@pytest.mark.skipif(not os.getenv("VERTEX_CREDENTIALS"), reason="Gemini LLM auth not set up")
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


@pytest.mark.skipif(not os.getenv("VERTEX_CREDENTIALS"), reason="Gemini LLM auth not set up")
@pytest.mark.asyncio(loop_scope="session")
async def test_geminimodel_vertex_streaming_text_matches_final_async(
    vertex_gemini_model: GeminiModel,
    prompt_without_tool,
    litellm_async_client_cleanup,
    litellm_thread_cleanup,
) -> None:
    streamed_text, final_message = await _stream_and_collect_async(
        vertex_gemini_model, prompt_without_tool
    )
    assert final_message.content
    assert final_message.content in streamed_text


@pytest.mark.skipif(not os.getenv("VERTEX_CREDENTIALS"), reason="Gemini LLM auth not set up")
def test_geminimodel_vertex_streaming_tool_call_sync(
    vertex_gemini_model: GeminiModel,
    prompt_with_tool: Prompt,
    litellm_thread_cleanup,
) -> None:
    _streamed_text, final_message = _stream_and_collect_sync(vertex_gemini_model, prompt_with_tool)
    assert final_message.tool_requests is not None
    assert final_message.tool_requests[0].name == "tool_greet"


@pytest.mark.skipif(not os.getenv("VERTEX_CREDENTIALS"), reason="Gemini LLM auth not set up")
@pytest.mark.asyncio(loop_scope="session")
async def test_geminimodel_vertex_streaming_tool_call_async(
    vertex_gemini_model: GeminiModel,
    prompt_with_tool: Prompt,
    litellm_async_client_cleanup,
    litellm_thread_cleanup,
) -> None:
    _streamed_text, final_message = await _stream_and_collect_async(
        vertex_gemini_model, prompt_with_tool
    )
    assert final_message.tool_requests is not None
    assert final_message.tool_requests[0].name == "tool_greet"


@pytest.mark.skipif(not os.getenv("VERTEX_CREDENTIALS"), reason="Gemini LLM auth not set up")
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
