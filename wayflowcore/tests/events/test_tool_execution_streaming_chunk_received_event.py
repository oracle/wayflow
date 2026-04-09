# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
from typing import Any, Dict

import pytest

from wayflowcore.events.event import _PII_TEXT_MASK, ToolExecutionStreamingChunkReceivedEvent
from wayflowcore.tools.tools import ToolOutputArtifact, ToolRequest

from .conftest import GET_LOCATION_CLIENT_TOOL


@pytest.mark.parametrize("missing_attribute", ["tool", "tool_request", "content"])
def test_event_creation_with_missing_arguments_fails(missing_attribute: str) -> None:
    all_attributes = {
        "tool": GET_LOCATION_CLIENT_TOOL,
        "tool_request": ToolRequest(
            name=GET_LOCATION_CLIENT_TOOL.name,
            tool_request_id="abc123",
            args={},
        ),
        "content": "chunk 1",
    }
    del all_attributes[missing_attribute]
    with pytest.raises(ValueError, match=f"An attribute named `{missing_attribute}`"):
        ToolExecutionStreamingChunkReceivedEvent(**all_attributes)


@pytest.mark.parametrize(
    "event_info",
    [
        {
            "name": "My event test",
            "event_id": "abc123",
            "timestamp": 12,
            "tool_request": ToolRequest(
                name=GET_LOCATION_CLIENT_TOOL.name,
                tool_request_id="abc123",
                args={"path": "/tmp/app.log"},
            ),
            "content": "chunk 1",
            "artifacts": (
                ToolOutputArtifact(name="chunk.txt", mime_type="text/plain", data="payload"),
                ToolOutputArtifact(
                    name="chunk.bin",
                    mime_type="application/octet-stream",
                    data=b"\x00\x01",
                ),
            ),
        },
    ],
)
@pytest.mark.parametrize("mask_sensitive_information", [True, False])
def test_correct_event_serialization_to_tracing_format(
    event_info: Dict[str, Any], mask_sensitive_information: bool
) -> None:
    event = ToolExecutionStreamingChunkReceivedEvent(tool=GET_LOCATION_CLIENT_TOOL, **event_info)
    serialized_event = event.to_tracing_info(mask_sensitive_information=mask_sensitive_information)

    assert serialized_event["event_type"] == str(event.__class__.__name__)
    assert event.tool_request.tool_request_id == serialized_event["tool_request.tool_request_id"]
    if mask_sensitive_information:
        assert _PII_TEXT_MASK == serialized_event["tool_request.inputs"]
        assert _PII_TEXT_MASK == serialized_event["content"]
        assert _PII_TEXT_MASK == serialized_event["artifacts"]
    else:
        assert event.tool_request.args == serialized_event["tool_request.inputs"]
        assert event.content == serialized_event["content"]
        assert serialized_event["artifacts"] == [
            {
                "name": "chunk.txt",
                "mime_type": "text/plain",
                "data": "payload",
                "data_encoding": "text",
            },
            {
                "name": "chunk.bin",
                "mime_type": "application/octet-stream",
                "data": "AAE=",
                "data_encoding": "base64",
            },
        ]


def test_event_tracing_info_is_json_serializable_when_chunk_artifacts_include_bytes() -> None:
    event = ToolExecutionStreamingChunkReceivedEvent(
        tool=GET_LOCATION_CLIENT_TOOL,
        tool_request=ToolRequest(
            name=GET_LOCATION_CLIENT_TOOL.name,
            tool_request_id="abc123",
            args={"path": "/tmp/app.log"},
        ),
        content="chunk 1",
        artifacts=(
            ToolOutputArtifact(
                name="chunk.bin", mime_type="application/octet-stream", data=b"\x00"
            ),
        ),
    )

    serialized_event = event.to_tracing_info(mask_sensitive_information=False)

    assert json.loads(json.dumps(serialized_event))["artifacts"][0]["data"] == "AA=="
