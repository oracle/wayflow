# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Wire models for the Code Executor Protocol."""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import TypeAliasType

from wayflowcore._utils.notgiven import NOT_GIVEN, NotGiven

JsonValue = TypeAliasType(
    "JsonValue",
    "None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]",
)
"""A JSON-compatible value."""

TaskStatus: TypeAlias = Literal[
    "working", "input_required", "completed", "failed", "cancelled", "timed_out"
]

TASK_STATUS_WORKING: Final[Literal["working"]] = "working"
TASK_STATUS_INPUT_REQUIRED: Final[Literal["input_required"]] = "input_required"
TASK_STATUS_COMPLETED: Final[Literal["completed"]] = "completed"
TASK_STATUS_FAILED: Final[Literal["failed"]] = "failed"
TASK_STATUS_CANCELLED: Final[Literal["cancelled"]] = "cancelled"
TASK_STATUS_TIMED_OUT: Final[Literal["timed_out"]] = "timed_out"


class CodeExecutorModel(BaseModel):
    """Base model with strict protocol fields."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ScriptInput(CodeExecutorModel):
    """Source code executed as a program."""

    type: Literal["script"]
    source_code: str


class FunctionInput(CodeExecutorModel):
    """Source code containing one named function to invoke."""

    type: Literal["function"]
    source_code: str
    function_name: str
    arguments: dict[str, JsonValue]
    """Named JSON-compatible arguments passed to the function."""


class HostCallbackResponse(CodeExecutorModel):
    """A host response supplied to a prior host interaction request."""

    type: Literal["host_response"]
    request_id: str
    result: JsonValue = None
    """JSON-compatible result returned by the host."""


class TextContent(CodeExecutorModel):
    """Text content produced by an execution."""

    type: Literal["text"]
    text: str
    stream: Literal["stdout", "stderr"] | None = None
    """Originating process stream when the text was captured from execution."""


ExecutionInputItem: TypeAlias = ScriptInput | FunctionInput | HostCallbackResponse
"""Input item accepted by an execution, including a host response."""


class CodeExecutionRequest(CodeExecutorModel):
    """Request body for creating a code execution."""

    language_id: str
    input: list[ExecutionInputItem]

    dependencies: list[str] = Field(default_factory=list)
    """Dependencies expected to be available in the execution environment."""

    session_id: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    wait: bool = True

    @model_validator(mode="after")
    def _validate_input_count(self) -> CodeExecutionRequest:
        if len(self.input) != 1:
            raise ValueError("input must contain exactly one executable item")
        return self


class ExecutionResult(CodeExecutorModel):
    """Output item returned by an execution."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    type: Literal["output"]
    content: list[TextContent] = Field(default_factory=list)
    """Content blocks such as captured text output."""

    structured_content: JsonValue | NotGiven = Field(
        default=NOT_GIVEN,
        alias="structuredContent",
        exclude_if=lambda value: value is NOT_GIVEN,
    )
    """Optional JSON-compatible structured result, including an explicit null."""

    is_error: bool = Field(default=False, alias="isError")
    """Whether the output describes an execution error."""


class HostCallbackRequest(CodeExecutorModel):
    """A request for the host to perform an interaction on behalf of code."""

    type: Literal["host_request"]
    request_id: str
    request_type: Literal["tool_execution"]
    name: str
    arguments: dict[str, JsonValue]


ExecutionOutputItem: TypeAlias = ExecutionResult | HostCallbackRequest
"""Output item returned by an execution: a result or host callback request."""


class ExecutionResponse(CodeExecutorModel):
    """Snapshot returned for a code execution."""

    id: str
    object: Literal["response"]
    created_at: datetime
    status: TaskStatus
    completed_at: datetime | None = None
    language_id: str
    output: list[ExecutionOutputItem] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class HostInteractions(CodeExecutorModel):
    """Session configuration for host-initiated interaction requests."""

    enabled: bool
    allowed_request_types: list[Literal["tool_execution"]] = Field(default_factory=list)


class CreateSessionRequest(CodeExecutorModel):
    """Request body for creating a stateful execution session."""

    language_id: str
    host_interactions: HostInteractions | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class SessionSnapshot(CodeExecutorModel):
    """Snapshot of a stateful execution session."""

    id: str
    object: Literal["session"]
    status: Literal["active", "closing", "closed", "expired"]
    language_id: str
    host_interactions: HostInteractions | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class CodeExecutorCapabilities(CodeExecutorModel):
    """Public capabilities advertised by a Code Executor server."""

    view: Literal["public"] = "public"
    protocol_version: str
    server_name: str
    capabilities: dict[str, JsonValue] = Field(default_factory=dict)
