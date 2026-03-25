# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import AsyncGenerator

import pytest

from wayflowcore.events.event import Event, ToolExecutionResultEvent
from wayflowcore.events.eventlistener import EventListener, register_event_listeners
from wayflowcore.flowhelpers import run_step_and_return_outputs
from wayflowcore.messagelist import Message, MessageList, MessageType
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import (
    ReturnArtifact,
    ServerTool,
    ToolOutputArtifact,
    ToolOutputType,
    ToolResult,
    tool,
)
from wayflowcore.tools.tools import (
    reset_max_tool_artifact_size_bytes,
    set_max_tool_artifact_size_bytes,
)


class ToolResultListener(EventListener):
    def __init__(self) -> None:
        self.result_events: list[ToolExecutionResultEvent] = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ToolExecutionResultEvent):
            self.result_events.append(event)


@pytest.fixture(autouse=True)
def reset_tool_artifact_size_limit():
    reset_max_tool_artifact_size_bytes()
    yield
    reset_max_tool_artifact_size_bytes()


def _make_server_tool(
    func=lambda: None,
    output_type: ToolOutputType = ToolOutputType.CONTENT_AND_ARTIFACT,
) -> ServerTool:
    return ServerTool(
        name="artifact_tool",
        description="Tool used to test artifact outputs.",
        parameters={},
        output={"type": "string"},
        func=func,
        output_type=output_type,
    )


def _execute_tool_and_get_result(
    server_tool: ServerTool,
    *,
    inputs: dict[str, object] | None = None,
) -> tuple[dict[str, object], ToolExecutionResultEvent]:
    step = ToolExecutionStep(tool=server_tool)
    listener = ToolResultListener()

    with register_event_listeners([listener]):
        outputs = run_step_and_return_outputs(step, inputs=inputs or {})

    assert len(listener.result_events) == 1
    return outputs, listener.result_events[0]


def test_content_only_tool_has_no_artifacts():
    server_tool = _make_server_tool(func=lambda: "summary", output_type=ToolOutputType.CONTENT_ONLY)

    outputs, result_event = _execute_tool_and_get_result(server_tool)

    assert outputs == {ToolExecutionStep.TOOL_OUTPUT: "summary"}
    assert result_event.tool_result.artifacts == ()


@pytest.mark.parametrize(
    "artifacts_input, expected_name, expected_mime_type, expected_data",
    [
        ("full log text", None, "text/plain", "full log text"),
        (b"\x00\x01", None, "application/octet-stream", b"\x00\x01"),
        (
            ToolOutputArtifact(name="a.txt", mime_type="text/plain", data="x"),
            "a.txt",
            "text/plain",
            "x",
        ),
        (
            {"name": "b.txt", "mime_type": "text/plain", "data": "y"},
            "b.txt",
            "text/plain",
            "y",
        ),
    ],
)
def test_artifact_outputs_are_normalized(
    artifacts_input,
    expected_name: str | None,
    expected_mime_type: str,
    expected_data: str | bytes,
):
    server_tool = _make_server_tool(func=lambda: ("summary", artifacts_input))

    outputs, result_event = _execute_tool_and_get_result(server_tool)

    artifacts = result_event.tool_result.artifacts
    assert outputs == {ToolExecutionStep.TOOL_OUTPUT: "summary"}
    assert len(artifacts) == 1
    assert artifacts[0].mime_type == expected_mime_type
    assert artifacts[0].data == expected_data
    if expected_name is None:
        assert artifacts[0].name is not None
        assert artifacts[0].name.startswith("artifact_")
    else:
        assert artifacts[0].name == expected_name


def test_server_tool_preserves_multiple_mapped_artifacts_and_warns_on_name_mismatch(caplog):
    server_tool = _make_server_tool(
        func=lambda: (
            "summary",
            {
                "outer.txt": ToolOutputArtifact(
                    name="inner.txt", mime_type="text/plain", data="payload"
                ),
                "blob.bin": b"\x00\x01",
                "report.json": {
                    "name": "inner-report.json",
                    "mime_type": "application/json",
                    "data": '{"ok": true}',
                },
            },
        )
    )

    with caplog.at_level("WARNING"):
        outputs, result_event = _execute_tool_and_get_result(server_tool)

    artifacts = result_event.tool_result.artifacts
    assert outputs == {ToolExecutionStep.TOOL_OUTPUT: "summary"}
    assert [artifact.name for artifact in artifacts] == ["outer.txt", "blob.bin", "report.json"]
    assert [artifact.mime_type for artifact in artifacts] == [
        "text/plain",
        "application/octet-stream",
        "application/json",
    ]
    assert artifacts[0].data == "payload"
    assert artifacts[1].data == b"\x00\x01"
    assert artifacts[2].data == '{"ok": true}'
    assert "overrides nested artifact name" in caplog.text
    assert "inner.txt" in caplog.text
    assert "inner-report.json" in caplog.text


def test_tuple_artifact_shapes_are_rejected_for_server_tools():
    server_tool = _make_server_tool(
        func=lambda: (
            "summary",
            (
                ToolOutputArtifact(name="first.txt", mime_type="text/plain", data="first"),
                "second",
            ),
        )
    )

    outputs, result_event = _execute_tool_and_get_result(server_tool)

    assert outputs == {ToolExecutionStep.TOOL_OUTPUT: "summary"}
    assert result_event.tool_result.artifacts == ()


@pytest.mark.parametrize(
    "raw_output",
    [
        "summary",
        ("summary", None),
        ("summary", 123),
        ("summary", {"data": "x"}),
        ("summary", ()),
        ("summary", ("chunk 1", "chunk 2")),
    ],
)
def test_invalid_artifact_shapes_are_dropped_with_warning(caplog, raw_output):
    server_tool = _make_server_tool(func=lambda: raw_output)

    with caplog.at_level("WARNING"):
        outputs, result_event = _execute_tool_and_get_result(server_tool)

    assert outputs == {ToolExecutionStep.TOOL_OUTPUT: "summary"}
    assert result_event.tool_result.artifacts == ()
    assert "artifacts" in caplog.text.lower() or "output_type" in caplog.text.lower()


def test_binary_artifact_data_is_preserved_exactly():
    server_tool = _make_server_tool(
        func=lambda: (
            "summary",
            ToolOutputArtifact(
                name="blob.bin", mime_type="application/octet-stream", data=b"\x00\x01\x02"
            ),
        )
    )
    payload = b"\x00\x01\x02"

    _, result_event = _execute_tool_and_get_result(server_tool)

    artifacts = result_event.tool_result.artifacts
    assert artifacts[0].mime_type == "application/octet-stream"
    assert artifacts[0].data == payload


def test_server_tool_preserves_explicit_mapping_keys():
    server_tool = _make_server_tool(
        func=lambda: (
            "summary",
            {
                "first.txt": ToolOutputArtifact(data="one"),
                "second.txt": ToolOutputArtifact(data="two"),
            },
        )
    )

    outputs, result_event = _execute_tool_and_get_result(server_tool)

    artifacts = result_event.tool_result.artifacts
    assert outputs == {ToolExecutionStep.TOOL_OUTPUT: "summary"}
    assert artifacts[0].name is not None
    assert artifacts[1].name is not None
    assert artifacts[0].name == "first.txt"
    assert artifacts[1].name == "second.txt"
    assert artifacts[0].name != artifacts[1].name


def test_artifact_size_limit_truncates_and_warns(caplog):
    server_tool = _make_server_tool(func=lambda: ("summary", "abcdef"))
    set_max_tool_artifact_size_bytes(4)

    with caplog.at_level("WARNING"):
        _, result_event = _execute_tool_and_get_result(server_tool)

    artifacts = result_event.tool_result.artifacts
    assert artifacts[0].data == "abcd"
    assert "soft size limit" in caplog.text


def test_message_list_copy_keeps_same_artifact_objects():
    artifact = ToolOutputArtifact(name="artifact.txt", mime_type="text/plain", data="payload")
    message_list = MessageList(
        [
            Message(
                message_type=MessageType.TOOL_RESULT,
                tool_result=ToolResult(
                    content="summary",
                    tool_request_id="tool_call_1",
                    artifacts=(artifact,),
                ),
            )
        ]
    )

    copied = message_list.copy()

    assert copied.messages[0].tool_result is not None
    assert copied.messages[0].tool_result is not message_list.messages[0].tool_result
    assert copied.messages[0].tool_result.artifacts[0] is artifact


def test_content_only_tool_warns_when_tuple_looks_like_artifact(caplog):
    server_tool = _make_server_tool(
        func=lambda: ("summary", "full log"),
        output_type=ToolOutputType.CONTENT_ONLY,
    )

    with caplog.at_level("WARNING"):
        outputs, result_event = _execute_tool_and_get_result(server_tool)

    assert outputs
    assert result_event.tool_result.content == ("summary", "full log")
    assert result_event.tool_result.artifacts == ()
    assert "potential artifact payload" in caplog.text


def test_tool_decorator_infers_content_schema_for_artifact_tools():
    @tool(description_mode="only_docstring", output_type=ToolOutputType.CONTENT_AND_ARTIFACT)
    def summarize_logs(path: str) -> ReturnArtifact[str]:
        """Summarize a log file and attach the full contents."""

        return "summary", "full log"

    assert summarize_logs.output_type == ToolOutputType.CONTENT_AND_ARTIFACT
    assert summarize_logs.output["type"] == "string"


def test_server_tool_execution_uses_raw_output_hook_before_calling_func():
    async def should_not_be_called() -> str:
        raise RuntimeError("should not be called")

    class HookedServerTool(ServerTool):
        async def _execute_raw_tool_outputs_async(self, *args, **kwargs):
            return "summary", "full log"

    server_tool = HookedServerTool(
        name="hooked_tool",
        description="Tool used to test the raw output hook.",
        parameters={},
        output={"type": "string"},
        func=should_not_be_called,
        output_type=ToolOutputType.CONTENT_AND_ARTIFACT,
    )

    outputs, result_event = _execute_tool_and_get_result(server_tool)

    artifacts = result_event.tool_result.artifacts
    assert outputs == {ToolExecutionStep.TOOL_OUTPUT: "summary"}
    assert len(artifacts) == 1
    assert artifacts[0].data == "full log"


def test_tool_decorator_infers_content_schema_for_streaming_artifact_tools():
    @tool(description_mode="only_docstring", output_type=ToolOutputType.CONTENT_AND_ARTIFACT)
    async def stream_logs(topic: str) -> AsyncGenerator[ReturnArtifact[str], None]:
        """Stream log lines and attach the full log at the end."""

        yield topic
        yield "summary", "full log"

    assert stream_logs.output_type == ToolOutputType.CONTENT_AND_ARTIFACT
    assert stream_logs.output["type"] == "string"


def test_streaming_tool_with_artifacts_returns_content_and_artifacts():
    @tool(description_mode="only_docstring", output_type=ToolOutputType.CONTENT_AND_ARTIFACT)
    async def stream_logs() -> AsyncGenerator[ReturnArtifact[str], None]:
        """Stream log lines and attach the full log at the end."""

        yield "chunk 1"
        yield "chunk 2"
        yield "summary", {"full_log.txt": "full log"}

    outputs, result_event = _execute_tool_and_get_result(stream_logs)

    artifacts = result_event.tool_result.artifacts
    assert outputs == {ToolExecutionStep.TOOL_OUTPUT: "summary"}
    assert len(artifacts) == 1
    assert artifacts[0].name == "full_log.txt"
    assert artifacts[0].data == "full log"
