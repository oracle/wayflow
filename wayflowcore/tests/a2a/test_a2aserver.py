# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import base64
import time
from pathlib import Path
from typing import Optional

import httpx
import pytest
from fasta2a.schema import FileWithBytes
from httpx import Response

from ..testhelpers.testhelpers import retry_test
from .start_a2a_server import AgentType


def rpc_call(base_url: str, method: str, params: dict, id="test") -> Response:
    return httpx.post(
        url=base_url,
        json={
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
            "params": params,
        },
    )


def send_text_message(
    base_url: str,
    text: str,
    context_id: Optional[str] = None,
    task_id: Optional[str] = None,
    blocking: Optional[bool] = None,
) -> Response:
    method = "message/send"
    params = {
        "message": {
            "messageId": "test",
            "role": "user",
            "kind": "message",
            "parts": [
                {
                    "text": text,
                    "kind": "text",
                }
            ],
        }
    }

    if context_id:
        params["message"]["contextId"] = context_id
    if task_id:
        params["message"]["taskId"] = task_id
    if blocking:
        params["configuration"] = {"blocking": blocking, "acceptedOutputModes": ["text"]}

    response = rpc_call(base_url, method, params)
    assert response.status_code == 200

    return response


def wait_for_task(base_url, task_id, timeout=20) -> Response:
    start = time.time()
    while time.time() - start < timeout:
        resp = rpc_call(base_url, "tasks/get", {"id": task_id})
        state = resp.json()["result"]["status"]["state"]
        if state in ["completed", "input-required"]:
            return resp
        if state == "failed":
            raise RuntimeError("Task failed")
        time.sleep(0.1)
    raise TimeoutError(f"Task {task_id} not completed in time")


@retry_test(max_attempts=4)
@pytest.mark.parametrize(
    "a2a_server",
    [
        AgentType.AGENT_WITH_SERVER_TOOL,
        AgentType.AGENT_WITHOUT_TOOL,
        AgentType.FLOW_WITH_AGENT_STEP,
        AgentType.MANAGER_WORKERS,
        AgentType.SWARM,
    ],
    indirect=True,
)
def test_all_conversational_components_can_be_served(a2a_server):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-11-20
    Average success time:  0.85 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    base_url = a2a_server

    # Send the initial message
    resp1 = send_text_message(base_url, "Hi! My name is John")
    assert resp1.json()["result"]["status"]["state"] == "submitted"

    # Wait for the task to finish processing and its state should be either "completed" or "input-required"
    task_id = resp1.json()["result"]["id"]
    wait_for_task(base_url, task_id)


@retry_test(max_attempts=4)
def test_conversation_can_be_continued_by_sending_same_context_id(a2a_server):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-12-02
    Average success time:  3.63 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    base_url = a2a_server

    # Send the initial message and wait for the task to finish
    resp1 = send_text_message(base_url, "Hi! My name is John")
    wait_for_task(base_url, resp1.json()["result"]["id"])

    # Send follow-up message in the same context
    context_id = resp1.json()["result"]["contextId"]
    resp2 = send_text_message(base_url, "What is my name?", context_id=context_id)

    resp3 = wait_for_task(base_url, resp2.json()["result"]["id"])
    output = resp3.json()["result"]["history"][-1]["parts"][-1]["text"]

    assert "John" in output


@retry_test(max_attempts=4)
@pytest.mark.parametrize(
    "a2a_server",
    [
        AgentType.FLOW_WITH_AGENT_STEP_THAT_YIELDS_ONCE,
    ],
    indirect=True,
)
def test_conversation_can_be_continued_when_latest_task_completed_by_sending_same_context_id(
    a2a_server,
):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-12-02
    Average success time:  3.41 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    """
    To continue a conversation with context_id we take the conversation of the latest task which might be finished.
    This test is to guaranteed the "context conversation" can be continued in such case.
    """
    base_url = a2a_server

    # Send the initial message and wait for the task to finish
    resp1 = send_text_message(base_url, "Hi! My name is John")
    resp2 = wait_for_task(base_url, resp1.json()["result"]["id"])

    # This task is completed
    assert resp2.json()["result"]["status"]["state"] == "completed"

    # Send follow-up message in the same context
    context_id = resp1.json()["result"]["contextId"]
    resp3 = send_text_message(base_url, "What is my name?", context_id=context_id)

    resp4 = wait_for_task(base_url, resp3.json()["result"]["id"])
    output = resp4.json()["result"]["history"][-1]["parts"][-1]["text"]

    assert "John" in output


@retry_test(max_attempts=6)
def test_conversation_can_be_continued_for_context_with_multiple_tasks(a2a_server):
    """
    Failure rate:          4 out of 25
    Observed on:           2025-12-03
    Average success time:  5.42 seconds per successful attempt
    Average failure time:  5.38 seconds per failed attempt
    Max attempt:           6
    Justification:         (0.19 ** 6) ~= 4.0 / 100'000
    """
    """
    When there are multiple tasks in the context, the newly created task (within the context) should be aware of them all.
    The test also shows that server can handle multiple requests with same context_id.
    """
    base_url = a2a_server

    resp1 = send_text_message(base_url, "Hi! My name is John")
    resp2 = send_text_message(
        base_url, "My dog's name is Tom", context_id=resp1.json()["result"]["contextId"]
    )

    resp3 = send_text_message(
        base_url,
        "What is my name and my dog's name?",
        context_id=resp1.json()["result"]["contextId"],
    )

    resp4 = wait_for_task(base_url, resp3.json()["result"]["id"])
    output = resp4.json()["result"]["history"][-1]["parts"][-1]["text"]

    assert "john" in output.lower()
    assert "tom" in output.lower()


@retry_test(max_attempts=4)
def test_conversation_can_be_continued_by_sending_same_task_id(a2a_server):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-12-02
    Average success time:  3.49 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    base_url = a2a_server

    # Send the initial message and wait for the task to finish
    resp1 = send_text_message(base_url, "Hi! My name is John")
    wait_for_task(base_url, resp1.json()["result"]["id"])

    # Send follow-up message in the same task
    task_id = resp1.json()["result"]["id"]
    resp2 = send_text_message(base_url, "What is my name?", task_id=task_id)

    resp3 = wait_for_task(base_url, resp2.json()["result"]["id"])
    output = resp3.json()["result"]["history"][-1]["parts"][-1]["text"]

    assert "John" in output


@retry_test(max_attempts=4)
@pytest.mark.filterwarnings("ignore::UserWarning")  # Ignore warnings from google adk itself.
@pytest.mark.filterwarnings("ignore::DeprecationWarning")  # Ignore warnings from google adk itself.
@pytest.mark.filterwarnings("ignore::FutureWarning")  # Ignore warnings from google adk itself.
def test_server_can_be_accessed_with_google_adk_a2aagent(a2a_server):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-12-02
    Average success time:  1.60 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    # Skip test automatically if google-adk is not installed
    pytest.importorskip(
        "google.adk.agents.remote_a2a_agent",
        reason="Skipping because the google-adk[a2a] package is not installed.",
    )

    from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    base_url = a2a_server

    remote_agent = RemoteA2aAgent(
        name="math_agent",
        description="Agent that can do math",
        agent_card=f"{base_url}/.well-known/agent-card.json",
    )

    session_service = InMemorySessionService()
    session_service.create_session_sync(
        app_name="app", user_id="test_user", session_id="test_session"
    )
    runner = Runner(agent=remote_agent, app_name="app", session_service=session_service)
    user_input = "What is 13 x 15?"
    content = types.Content(parts=[types.Part.from_text(text=user_input)])

    response = ""
    for event in runner.run(user_id="test_user", session_id="test_session", new_message=content):
        if event.is_final_response() and event.content and event.content.parts:
            response = event.content.parts[0].text

    assert "195" in response


@retry_test(max_attempts=4)
@pytest.mark.parametrize("a2a_server", [AgentType.AGENT_WITH_VISION_CAPABILITY], indirect=True)
def test_server_can_handle_vision_input(a2a_server):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-12-02
    Average success time:  1.02 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    base_url = a2a_server

    image_path = Path(__file__).parent.parent / "configs/test_data/image.png"
    image_bytes = Path(image_path).read_bytes()
    base64_str = base64.b64encode(image_bytes).decode("utf-8")
    base64_str = f"data:image/png;base64,{base64_str}"

    resp1 = rpc_call(
        base_url,
        method="message/send",
        params={
            "message": {
                "messageId": "test",
                "role": "user",
                "kind": "message",
                "parts": [
                    {
                        "file": FileWithBytes(bytes=base64_str),
                        "kind": "file",
                    },
                    {
                        "text": "Which color is this logo?",
                        "kind": "text",
                    },
                ],
            }
        },
    )

    resp1.status_code == 200
    resp2 = wait_for_task(base_url, task_id=resp1.json()["result"]["id"])

    output = resp2.json()["result"]["history"][-1]["parts"][-1]["text"].lower()
    assert "yellow" in output or "gold" in output


@retry_test(max_attempts=4)
def test_server_returns_final_result_when_setting_blocking_true(a2a_server):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-12-02
    Average success time:  0.87 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    base_url = a2a_server

    resp = send_text_message(base_url, "Hi! My name is John", blocking=True)
    task_state = resp.json()["result"]["status"]["state"]
    assert task_state == "input-required"

    task_history = resp.json()["result"]["history"]
    assert len(task_history) == 2


@retry_test(max_attempts=4)
def test_server_returns_error_when_sending_non_existing_task(a2a_server):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-12-02
    Average success time:  0.00 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    base_url = a2a_server

    resp = send_text_message(base_url, "Hello", task_id="wrong_id")
    task_error = resp.json()["error"]
    assert task_error == {
        "code": -32602,
        "message": "Invalid parameters",
        "data": {
            "parameter": "task_id",
            "value": "wrong_id",
            "reason": "Task id not found",
        },
    }


@retry_test(max_attempts=4)
@pytest.mark.parametrize(
    "a2a_server",
    [
        AgentType.FLOW_THAT_WITH_INPUT_STEP_YIELDS_ONCE,
    ],
    indirect=True,
)
def test_server_returns_error_when_sending_completed_task(a2a_server):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-12-02
    Average success time:  0.05 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    base_url = a2a_server

    # Create a completed task
    resp1 = send_text_message(base_url, text="John", blocking=True)
    assert resp1.json()["result"]["status"]["state"] == "completed"

    task_id = resp1.json()["result"]["id"]
    resp2 = send_text_message(base_url, text="Johb", task_id=task_id)
    task_error = resp2.json()["error"]
    assert task_error == {
        "code": -32602,
        "message": "Invalid parameters",
        "data": {
            "parameter": "task_id",
            "value": task_id,
            "reason": "Cannot continue a completed task",
        },
    }


@retry_test(max_attempts=4)
def test_agent_card_is_accessible(a2a_server):
    """
    Failure rate:          0 out of 15
    Observed on:           2025-12-02
    Average success time:  0.00 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    base_url = a2a_server
    resp = httpx.get(
        f"{base_url}/.well-known/agent-card.json"  # This is the standard endpoint specified by A2A protocol
    )
    assert resp.status_code == 200


@retry_test(max_attempts=4)
def test_server_can_handle_multiple_requests(a2a_server):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-12-18
    Average success time:  2.47 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    base_url = a2a_server

    resp1 = send_text_message(base_url, "What is 2 x 3")
    resp2 = send_text_message(base_url, "What is 3 x 4")

    resp3 = wait_for_task(base_url, resp1.json()["result"]["id"])
    assert "6" in resp3.json()["result"]["history"][-1]["parts"][-1]["text"]

    resp4 = wait_for_task(base_url, resp2.json()["result"]["id"])
    assert "12" in resp4.json()["result"]["history"][-1]["parts"][-1]["text"]
