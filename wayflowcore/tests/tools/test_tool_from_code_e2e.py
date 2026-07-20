# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""End-to-end tests for tools backed by a CodeExecutor."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

pytest_plugins = ("tests.tools.codeexecutors.conftest",)

from wayflowcore import Agent, Flow
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.property import IntegerProperty
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import ToolRequest
from wayflowcore.tools.codeexecutors import (
    CodeExecutor,
    EndpointCodeExecutor,
    SubProcessCodeExecutor,
    subprocess_execution_enabled,
)
from wayflowcore.tools.toolfromcode import ToolFromCode

from ..testhelpers.dummy import DummyModel
from ..testhelpers.patching import patch_llm


@dataclass(frozen=True)
class ToolFromCodeExecutorConfig:
    """Configuration used to instantiate one ToolFromCode E2E executor."""

    name: str
    executor_type: type[CodeExecutor]
    kwargs: dict[str, Any]


ALL_TOOL_FROM_CODE_EXECUTORS = [
    ToolFromCodeExecutorConfig(
        name="subprocess",
        executor_type=SubProcessCodeExecutor,
        kwargs={"timeout_seconds": 2.0, "max_code_chars": 50_000},
    ),
    ToolFromCodeExecutorConfig(
        name="endpoint",
        executor_type=EndpointCodeExecutor,
        kwargs={"timeout_seconds": 2.0, "max_code_chars": 50_000},
    ),
]

with_all_tool_from_code_executors = pytest.mark.parametrize(
    "executor_config",
    argvalues=ALL_TOOL_FROM_CODE_EXECUTORS,
    ids=[config.name for config in ALL_TOOL_FROM_CODE_EXECUTORS],
)


@pytest.fixture
def code_executor(
    executor_config: ToolFromCodeExecutorConfig,
    request: pytest.FixtureRequest,
) -> Iterator[CodeExecutor]:
    """Yield one CodeExecutor configuration for ToolFromCode tests."""
    kwargs = dict(executor_config.kwargs)
    if executor_config.executor_type is EndpointCodeExecutor:
        kwargs["url"] = request.getfixturevalue("code_executor_url")
    executor = executor_config.executor_type(**kwargs)
    try:
        if isinstance(executor, SubProcessCodeExecutor):
            with subprocess_execution_enabled():
                yield executor
        else:
            yield executor
    finally:
        close = getattr(executor, "close", None)
        if callable(close):
            close()


@pytest.fixture
def multiply_tool_from_code(code_executor: CodeExecutor) -> ToolFromCode:
    """Create a simple function-backed multiplication tool."""
    return ToolFromCode(
        name="multiply",
        description="Multiply two integers.",
        language="python",
        code="""
def multiply(a, b):
    print(f"multiplying {a} and {b}")
    return a * b
""",
        code_executor=code_executor,
        input_descriptors=[
            IntegerProperty(name="a", description="First integer."),
            IntegerProperty(name="b", description="Second integer."),
        ],
        output_descriptors=[
            IntegerProperty(name="product", description="Product of a and b."),
        ],
    )


@with_all_tool_from_code_executors
def test_tool_from_code_runs_directly(
    multiply_tool_from_code: ToolFromCode,
) -> None:
    """Runs a code-backed tool directly and returns its structured result."""
    assert multiply_tool_from_code.run(a=6, b=7) == 42


@with_all_tool_from_code_executors
def test_tool_from_code_runs_in_agent(
    multiply_tool_from_code: ToolFromCode,
) -> None:
    """Runs a code-backed tool from an agent tool request."""
    llm = DummyModel()
    agent = Agent(
        llm=llm,
        name="tools_from_code_agent",
        description="Agent using a code-backed tool.",
        tools=[multiply_tool_from_code],
    )
    tool_request = ToolRequest(
        name="multiply",
        args={"a": 6, "b": 7},
        tool_request_id="req_multiply_001",
    )

    conversation = agent.start_conversation(messages="Multiply 6 by 7.")
    with patch_llm(llm, outputs=[[tool_request], "done"]):
        status = conversation.execute()

    assert isinstance(status, (FinishedStatus, UserMessageRequestStatus))
    tool_results = [
        message.tool_result
        for message in conversation.message_list.messages
        if message.tool_result is not None
    ]
    assert len(tool_results) == 1
    assert tool_results[0].tool_request_id == "req_multiply_001"
    assert tool_results[0].content == 42


@with_all_tool_from_code_executors
def test_tool_from_code_runs_in_flow(
    multiply_tool_from_code: ToolFromCode,
) -> None:
    """Runs a code-backed tool from a flow and returns its named output."""
    flow = Flow.from_steps(
        steps=[ToolExecutionStep(tool=multiply_tool_from_code)],
        input_descriptors=[
            IntegerProperty(name="a", description="First integer."),
            IntegerProperty(name="b", description="Second integer."),
        ],
    )

    conversation = flow.start_conversation(inputs={"a": 8, "b": 9})
    status = conversation.execute()

    assert isinstance(status, FinishedStatus)
    assert status.output_values == {"product": 72}


@with_all_tool_from_code_executors
def test_tool_from_code_raises_for_failed_execution(
    code_executor: CodeExecutor,
) -> None:
    """Converts a failed code execution into a tool failure."""
    tool = ToolFromCode(
        name="failing_tool",
        description="A tool that fails.",
        language="python",
        code="def failing_tool():\n    raise ValueError('boom')",
        code_executor=code_executor,
        input_descriptors=[],
        output_descriptors=[IntegerProperty(name="result", description="Result.")],
    )

    with pytest.raises(RuntimeError, match="boom"):
        tool.run()


def test_tool_from_code_serializes_endpoint_executor() -> None:
    """Serializes a ToolFromCode and its endpoint executor configuration."""
    tool = ToolFromCode(
        name="multiply",
        description="Multiply two integers.",
        language="python",
        code="def multiply(a, b):\n    return a * b",
        code_executor=EndpointCodeExecutor(
            url="https://executor.example.com",
        ),
        input_descriptors=[
            IntegerProperty(name="a", description="First integer."),
            IntegerProperty(name="b", description="Second integer."),
        ],
        output_descriptors=[
            IntegerProperty(name="product", description="Product of a and b."),
        ],
    )

    from wayflowcore.serialization.serializer import serialize_to_dict

    serialized = serialize_to_dict(tool)

    assert serialized["tool_type"] == "toolfromcode"
    assert serialized["code"] == tool.code
    assert "code_executor" in serialized
    assert "$ref" in serialized["code_executor"]
