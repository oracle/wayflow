# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Tests for host-mediated callback interactions."""

import pytest

from wayflowcore.codeserver.models import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_INPUT_REQUIRED,
    CodeExecutionRequest,
    CreateSessionRequest,
    HostCallbackRequest,
    HostCallbackResponse,
    ScriptInput,
)
from wayflowcore.codeserver.service import CodeExecutionService


def test_service_with_python_backend_returns_callback_host_request(
    python_service: CodeExecutionService,
) -> None:
    """Returns a callback host request when Python code invokes a host function."""
    session = python_service.create_session(CreateSessionRequest(language_id="python"))
    source_code = """
result = lookup_weather(city="Paris")
print(result)
"""
    # The syntax used to create a callback host request may be backend-dependent.
    request = CodeExecutionRequest(
        language_id="python",
        session_id=session.id,
        input=[ScriptInput(type="script", source_code=source_code)],
    )

    response = python_service.execute(request)

    assert response.status == TASK_STATUS_INPUT_REQUIRED
    assert isinstance(response.output[0], HostCallbackRequest)
    assert response.output[0].request_type == "tool_execution"
    assert response.output[0].name == "lookup_weather"
    assert response.output[0].arguments == {"city": "Paris"}


def test_service_waits_for_callback_host_response(
    python_service: CodeExecutionService,
) -> None:
    """Leaves an execution waiting while a callback host request is pending."""
    session = python_service.create_session(CreateSessionRequest(language_id="python"))
    request = CodeExecutionRequest(
        language_id="python",
        session_id=session.id,
        input=[
            ScriptInput(
                type="script",
                source_code='result = lookup_weather(city="Paris")',
            )
        ],
    )

    response = python_service.execute(request)

    assert response.status == TASK_STATUS_INPUT_REQUIRED
    assert response.completed_at is None
    assert isinstance(response.output[0], HostCallbackRequest)
    assert response.output[0].request_id


def test_service_resumes_execution_after_callback_host_response(
    python_service: CodeExecutionService,
) -> None:
    """Resumes a callback execution with a response in the same session."""
    session = python_service.create_session(CreateSessionRequest(language_id="python"))
    request = CodeExecutionRequest(
        language_id="python",
        session_id=session.id,
        input=[
            ScriptInput(
                type="script",
                source_code=('result = lookup_weather(city="Paris")\n' "print(result)"),
            )
        ],
    )

    waiting_response = python_service.execute(request)
    host_request = waiting_response.output[0]
    assert isinstance(host_request, HostCallbackRequest)

    continuation_request = CodeExecutionRequest(
        language_id="python",
        session_id=session.id,
        input=[
            HostCallbackResponse(
                type="host_response",
                request_id=host_request.request_id,
                result={"temperature": 21},
            )
        ],
    )

    response = python_service.execute(continuation_request)

    assert response.status == TASK_STATUS_COMPLETED


def test_service_rejects_unknown_callback_host_request_id(
    python_service: CodeExecutionService,
) -> None:
    """Rejects a callback response without a matching pending host request."""
    session = python_service.create_session(CreateSessionRequest(language_id="python"))
    request = CodeExecutionRequest(
        language_id="python",
        session_id=session.id,
        input=[
            HostCallbackResponse(
                type="host_response",
                request_id="req_does_not_exist",
                result={"temperature": 21},
            )
        ],
    )

    with pytest.raises(ValueError, match="host request"):
        python_service.execute(request)
