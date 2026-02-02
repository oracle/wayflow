# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import time
from typing import Any, AsyncGenerator

import anyio
import pytest

from wayflowcore.agent import Agent
from wayflowcore.events.event import Event, ToolExecutionStreamingChunkReceivedEvent
from wayflowcore.events.eventlistener import EventListener, register_event_listeners
from wayflowcore.flowhelpers import run_step_and_return_outputs, run_step_and_return_outputs_async
from wayflowcore.property import IntegerProperty, StringProperty
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import ServerTool, tool
from wayflowcore.tools.servertools import (
    _get_max_tool_stream_chunks,
    reset_max_tool_stream_chunks,
    set_max_tool_stream_chunks,
)
from wayflowcore.tools.tools import ToolRequest

from ..testhelpers.patching import patch_llm


class ServerToolStreamingListener(EventListener):
    def __init__(self) -> None:
        self.chunks: list[tuple[Any, float]] = []
        self.events: list[ToolExecutionStreamingChunkReceivedEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ToolExecutionStreamingChunkReceivedEvent):
            self.chunks.append((event.content, time.time()))
            self.events.append(event)


async def _streaming_tool_impl() -> AsyncGenerator[str, None]:
    """This is a streaming tool"""
    contents = []
    for i in range(5):
        chunk = f"chunk {i}"
        contents.append(chunk)
        await anyio.sleep(0)
        yield chunk
    yield ". ".join(contents)


@pytest.mark.anyio
async def test_server_tool_in_flow_streams_chunks_and_returns_final_result() -> None:
    decorated = tool("streaming_tool", _streaming_tool_impl)
    step = ToolExecutionStep(tool=decorated)
    listener = ServerToolStreamingListener()
    with register_event_listeners([listener]):
        outputs = await run_step_and_return_outputs_async(step)

    assert outputs == {ToolExecutionStep.TOOL_OUTPUT: "chunk 0. chunk 1. chunk 2. chunk 3. chunk 4"}
    assert [c for (c, _) in listener.chunks] == [
        "chunk 0",
        "chunk 1",
        "chunk 2",
        "chunk 3",
        "chunk 4",
    ]


def _sync_gen_tool_impl():
    yield "part"
    yield "final"


def test_server_tool_rejects_sync_generators() -> None:
    tool = ServerTool(
        name="sync_gen",
        description="sync generator",
        input_descriptors=[],
        output_descriptors=[StringProperty(name=ToolExecutionStep.TOOL_OUTPUT)],
        func=_sync_gen_tool_impl,
    )
    step = ToolExecutionStep(tool=tool)

    with pytest.raises(TypeError, match="Synchronous generator tool callable is not supported"):
        _ = step.tool.run()  # direct call


def test_server_tool_infinite_stream_stops_with_clear_error() -> None:
    async def infinite_tool() -> AsyncGenerator[str, None]:
        i = 0
        while True:
            i += 1
            # no final yield on purpose
            yield f"chunk {i}"

    tool = ServerTool(
        name="infinite",
        description="infinite stream",
        input_descriptors=[],
        output_descriptors=[StringProperty(name=ToolExecutionStep.TOOL_OUTPUT)],
        func=infinite_tool,
    )
    step = ToolExecutionStep(tool=tool)

    with pytest.raises(
        ValueError, match="Reached max iteration number when running streaming tool"
    ):
        _ = run_step_and_return_outputs(step)


def test_server_tool_can_stream_unlimited_when_max_chunks_is_minus_one() -> None:
    MAX_CHUNKS_ALLOWED = _get_max_tool_stream_chunks()

    async def finite_many_tool() -> AsyncGenerator[str, None]:
        # generate more than the default cap, but still finite to keep test fast
        for i in range(0, MAX_CHUNKS_ALLOWED + 5):
            yield f"c{i}"
        yield "done"

    try:
        set_max_tool_stream_chunks(-1)
        tool_ = ServerTool(
            name="finite_many",
            description="many chunks",
            input_descriptors=[],
            output_descriptors=[StringProperty(name=ToolExecutionStep.TOOL_OUTPUT)],
            func=finite_many_tool,
        )
        step = ToolExecutionStep(tool=tool_)
        listener = ServerToolStreamingListener()
        with register_event_listeners([listener]):
            outputs = run_step_and_return_outputs(step)
        assert outputs[ToolExecutionStep.TOOL_OUTPUT] == "done"
        assert len(listener.chunks) == MAX_CHUNKS_ALLOWED + 5
        # ^ Should have received all MAX_CHUNKS_ALLOWED + 5 chunk events
    finally:
        reset_max_tool_stream_chunks()


def test_server_tool_streams_chunks_sync_path_and_event_fields() -> None:
    @tool(description_mode="only_docstring")
    async def streaming_tool(prefix: str, count: int = 3) -> AsyncGenerator[str, None]:
        """This is a streaming tool"""
        parts: list[str] = []
        for i in range(count):
            s = f"{prefix}{i}"
            parts.append(s)
            yield s
        yield ". ".join(parts)

    step = ToolExecutionStep(tool=streaming_tool)
    listener = ServerToolStreamingListener()
    with register_event_listeners([listener]):
        outputs = run_step_and_return_outputs(step, inputs={"prefix": "Hello-", "count": 3})

    assert outputs == {ToolExecutionStep.TOOL_OUTPUT: "Hello-0. Hello-1. Hello-2"}
    chunks = listener.chunks
    assert [c for (c, _) in chunks] == ["Hello-0", "Hello-1", "Hello-2"]
    # ^ We should have exactly 3 chunk events before the final result

    field_listener = ServerToolStreamingListener()  # fresh listener
    with register_event_listeners([field_listener]):
        _ = run_step_and_return_outputs(step, inputs={"prefix": "Hello-", "count": 3})

    events = field_listener.events
    assert len(events) == 3
    # All events should reference a ServerTool instance and same tool_request_id
    assert all(isinstance(e.tool, ServerTool) for e in events)
    request_ids = {e.tool_request.tool_request_id for e in events}
    assert len(request_ids) == 1
    # Inputs should match
    assert all(e.tool_request.name == streaming_tool.name for e in events)
    assert all(e.tool_request.args == {"prefix": "Hello-", "count": 3} for e in events)


@pytest.mark.anyio
async def test_streaming_tool_yields_no_items_async() -> None:
    @tool(description_mode="only_docstring")
    async def zero_stream() -> AsyncGenerator[str, None]:
        """Async generator that yields no items"""
        if False:
            yield "never"

    step = ToolExecutionStep(tool=zero_stream)
    listener = ServerToolStreamingListener()

    with register_event_listeners([listener]):
        with pytest.raises(ValueError, match="produced no items; expected at least one yield"):
            _ = await run_step_and_return_outputs_async(step)

    assert len(listener.chunks) == 0
    # ^ No streaming chunk should have been emitted


def test_streaming_tool_yields_no_items_sync() -> None:
    @tool(output_descriptors=[StringProperty(name=ToolExecutionStep.TOOL_OUTPUT)])
    async def zero_stream_sync() -> AsyncGenerator[str, None]:
        """Async generator that yields no items (sync path)"""
        if False:
            yield "never"

    step = ToolExecutionStep(tool=zero_stream_sync)
    listener = ServerToolStreamingListener()

    with register_event_listeners([listener]):
        with pytest.raises(ValueError, match="produced no items; expected at least one yield"):
            _ = run_step_and_return_outputs(step)

    assert len(listener.chunks) == 0


@tool(
    output_descriptors=[
        StringProperty(name="first"),
        IntegerProperty(name="second"),
    ],
    description_mode="only_docstring",
)
async def bad_final_output() -> AsyncGenerator[str, None]:
    """Streams chunks then returns wrong final type (list instead of dict)."""
    yield "part-1"
    yield "part-2"
    # Wrong final type for multi-output (should be dict with keys 'first' and 'second')
    yield ["foo", 2]


def test_streaming_tool_final_output_type_mismatch_still_streams_chunks() -> None:
    step = ToolExecutionStep(tool=bad_final_output)
    listener = ServerToolStreamingListener()

    with register_event_listeners([listener]):
        with pytest.raises(ValueError, match="Expected multiple outputs in a dictionary"):
            _ = run_step_and_return_outputs(step)

    assert [c for (c, _) in listener.chunks] == ["part-1", "part-2"]


def test_agent_with_streaming_tool_emits_tool_chunks(big_llama) -> None:
    @tool(description_mode="only_docstring")
    async def my_stream_tool() -> AsyncGenerator[str, None]:
        """Tool that streams"""
        yield "first"
        yield "second"
        yield "final"

    llm = big_llama
    agent = Agent(llm=llm, name="agent", description="agent", tools=[my_stream_tool])

    tool_request = ToolRequest("my_stream_tool", {}, "req_123")
    with patch_llm(llm, outputs=[[tool_request], "done"]):
        listener = ServerToolStreamingListener()
        with register_event_listeners([listener]):
            conv = agent.start_conversation()
            conv.append_user_message("go")
            _ = conv.execute()

    assert all(event.tool is my_stream_tool for event in listener.events)
    assert all(event.tool_request is tool_request for event in listener.events)
    assert [c for (c, _) in listener.chunks] == ["first", "second"]
