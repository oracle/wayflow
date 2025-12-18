# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import base64
import json
from pathlib import Path
from typing import Any, Dict, Union

import httpx
import pytest

from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import OpenAIAPIType, OpenAICompatibleModel, StreamChunkType
from wayflowcore.models.llmmodel import LlmCompletion, Prompt
from wayflowcore.tools import ToolResult

from ..testhelpers.testhelpers import retry_test
from .conftest import _get_api_key_headers, get_all_server_fixtures_name

all_available_servers = pytest.mark.parametrize(
    "server_fixture_name", get_all_server_fixtures_name()
)


def _create_response(
    base_url: str,
    input_value: Any,
    model: str = "hr-assistant",
    headers: Dict[str, str] = None,
    **payload_fields: Any,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "input": input_value,
        **payload_fields,
    }
    response = httpx.post(f"{base_url}/v1/responses", json=payload, timeout=120.0, headers=headers)
    response.raise_for_status()
    return response.json()


@pytest.fixture
def official_openai_client(server_url):
    try:
        from openai import OpenAI
    except ImportError:
        pytest.skip("Skipping because openai is not installed", allow_module_level=False)

    return OpenAI(base_url=server_url + "/v1", api_key="SOME_FAKE_SECRET")


@pytest.fixture
def multi_agent_openai_client(multi_agent_inmemory_server):
    try:
        from openai import OpenAI
    except ImportError:
        pytest.skip("Skipping because openai is not installed", allow_module_level=False)

    return OpenAI(base_url=multi_agent_inmemory_server + "/v1", api_key="SOME_FAKE_SECRET")


def _openai_stream_content(client, messages, model="hr-assistant"):
    stream = client.responses.create(
        model=model,
        input=messages,
        stream=True,
    )
    content = ""
    for chunk in stream:
        try:
            content += chunk.delta if chunk.delta else ""
        except:
            pass
    return content


# TEST GET /models


@all_available_servers
def test_list_models_endpoint(server_url) -> None:
    resp = httpx.get(f"{server_url}/v1/models", timeout=30.0)
    resp.raise_for_status()
    payload = resp.json()
    assert payload["object"] == "list"
    model_ids = [model["id"] for model in payload["data"]]
    assert len(model_ids) == 2
    assert "hr-assistant" in model_ids
    assert "simple-flow" in model_ids


@all_available_servers
def test_list_models_limit_and_ordering(server_url) -> None:
    params = {"limit": 1, "order": "asc"}
    resp = httpx.get(f"{server_url}/v1/models", params=params, timeout=30.0)
    resp.raise_for_status()
    payload = resp.json()
    print(payload)
    assert payload["object"] == "list"
    assert payload["has_more"] is True
    assert len(payload["data"]) == 1
    assert payload["first_id"] == payload["last_id"] == payload["data"][0]["id"]


@all_available_servers
def test_list_models_with_limit_to_0(server_url) -> None:

    params = {"limit": 0, "order": "asc"}
    resp = httpx.get(f"{server_url}/v1/models", params=params, timeout=30.0)
    resp.raise_for_status()
    payload = resp.json()
    assert payload["object"] == "list"
    assert payload["has_more"] is True
    assert len(payload["data"]) == 0


@all_available_servers
def test_list_models_with_after(server_url) -> None:
    params = {"after": "simple-flow"}
    resp = httpx.get(f"{server_url}/v1/models", params=params, timeout=30.0)
    resp.raise_for_status()
    payload = resp.json()
    assert payload["object"] == "list"
    assert payload["has_more"] is False
    assert len(payload["data"]) == 0


@all_available_servers
def test_list_models_official_openai(official_openai_client) -> None:
    models = official_openai_client.models.list()
    assert models.object == "list"
    model_ids = [m.id for m in models.data]
    assert "hr-assistant" in model_ids


# TEST GET /responses/{response_id}


@pytest.fixture
def response_id_exist_on_server(server_url):
    response = _create_response(
        base_url=server_url,
        input_value="Provide PTO details for Mary.",
        store=True,
    )
    response_id = response["id"]
    assert response["status"] == "completed"

    yield response_id


@all_available_servers
def test_get_response(server_url, response_id_exist_on_server) -> None:
    fetch_resp = httpx.get(f"{server_url}/v1/responses/{response_id_exist_on_server}", timeout=60.0)
    fetch_resp.raise_for_status()


@all_available_servers
def test_delete_response_official_client(
    official_openai_client, response_id_exist_on_server
) -> None:
    response = official_openai_client.responses.retrieve(response_id_exist_on_server)
    assert response.id == response_id_exist_on_server


@all_available_servers
def test_get_unknow_response_fails(server_url, response_id_exist_on_server) -> None:
    missing_resp = httpx.get(
        f"{server_url}/v1/responses/{response_id_exist_on_server}_unknown", timeout=30.0
    )
    assert missing_resp.status_code == 404


@all_available_servers
def test_get_streaming_response_fails(server_url, response_id_exist_on_server) -> None:
    not_supported_rsp = httpx.get(
        f"{server_url}/v1/responses/{response_id_exist_on_server}",
        timeout=30.0,
        params=dict(stream=True),
    )
    assert not_supported_rsp.status_code == 501


# TEST DELETE /responses/{response_id}


@all_available_servers
def test_delete_response(server_url, response_id_exist_on_server) -> None:
    delete_resp = httpx.delete(
        f"{server_url}/v1/responses/{response_id_exist_on_server}", timeout=30.0
    )
    delete_resp.raise_for_status()

    # after deletion, it's not there anymore
    missing_resp = httpx.get(
        f"{server_url}/v1/responses/{response_id_exist_on_server}", timeout=30.0
    )
    assert missing_resp.status_code >= 400


@all_available_servers
def test_delete_response_official_client(
    official_openai_client, response_id_exist_on_server
) -> None:
    from openai import NotFoundError

    official_openai_client.responses.delete(response_id_exist_on_server)

    with pytest.raises(NotFoundError):
        response = official_openai_client.responses.retrieve(response_id_exist_on_server)


@all_available_servers
def test_delete_unexisting_response(server_url, response_id_exist_on_server) -> None:
    delete_resp = httpx.delete(
        f"{server_url}/v1/responses/{response_id_exist_on_server}_unknown", timeout=30.0
    )
    delete_resp.raise_for_status()


# TEST POST /responses/{response_id}/cancel


@all_available_servers
def test_cancel_response_not_implemented(server_url, response_id_exist_on_server) -> None:
    cancel = httpx.post(
        f"{server_url}/v1/responses/{response_id_exist_on_server}/cancel", timeout=30.0
    )
    assert cancel.status_code == 501


# TEST POST   /responses


@all_available_servers
def test_create_response_unknown_model_returns_404(server_url) -> None:

    payload = {"model": "does-not-exist", "input": "hi"}
    resp = httpx.post(f"{server_url}/v1/responses", json=payload, timeout=30.0)
    assert resp.status_code == 404
    detail = resp.json().get("detail")
    assert "assistant" in detail.lower()


@all_available_servers
def test_create_response_no_model_returns_404(server_url) -> None:

    payload = {"input": "hi"}
    resp = httpx.post(f"{server_url}/v1/responses", json=payload, timeout=30.0)
    assert resp.status_code == 404
    detail = resp.json().get("detail")
    assert "assistant" in detail.lower()


@all_available_servers
def test_create_response_unknown_conversation(server_url) -> None:

    payload = {"model": "hr-assistant", "input": "hi", "conversation": "1"}
    resp = httpx.post(f"{server_url}/v1/responses", json=payload, timeout=30.0)
    assert resp.status_code == 404
    detail = resp.json().get("detail")
    assert "conversation" in detail.lower()


@all_available_servers
def test_create_response_unknown_response(server_url) -> None:

    payload = {"model": "hr-assistant", "input": "hi", "previous_response_id": "1"}
    resp = httpx.post(f"{server_url}/v1/responses", json=payload, timeout=30.0)
    assert resp.status_code == 404
    detail = resp.json().get("detail")
    assert "previous response" in detail.lower()


@all_available_servers
def test_create_response_with_instructions_when_agent_does_not_support_it(server_url) -> None:

    payload = {"model": "hr-assistant", "input": "hi", "instructions": "be polite"}
    resp = httpx.post(f"{server_url}/v1/responses", json=payload, timeout=30.0)
    assert resp.status_code == 406
    detail = resp.json().get("detail")
    assert "Agent should have an `instructions` input" in detail


@all_available_servers
def test_create_response_respects_store_flag(server_url) -> None:
    created = _create_response(
        server_url,
        "Create a short summary for Alex.",
        store=False,
    )
    response_id = created["id"]

    reuse_attempt = httpx.post(
        f"{server_url}/v1/responses",
        json={
            "model": "hr-assistant",
            "previous_response_id": response_id,
            "input": "Continue the conversation.",
        },
        timeout=120.0,
    )
    assert reuse_attempt.status_code >= 400

    lookup = httpx.get(f"{server_url}/v1/responses/{response_id}", timeout=30.0)
    assert lookup.status_code >= 400


@retry_test(max_attempts=3)
@all_available_servers
def test_previous_response_id_reuses_conversation(server_url) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    first_body = _create_response(
        base_url=server_url,
        input_value="Please greet the new hire Jeremy.",
        store=True,
    )
    follow_up_body = _create_response(
        base_url=server_url,
        input_value="Now provide onboarding next steps and cite the name of the new hire",
        conversation={"id": first_body["conversation"]["id"]},
    )
    assert follow_up_body["conversation"]["id"] == first_body["conversation"]["id"]
    assert "jeremy" in follow_up_body["output"][0]["content"][0]["text"].lower()


@retry_test(max_attempts=3)
@all_available_servers
def test_no_previous_response_id_does_not_reuse_conversation(server_url) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    first_body = _create_response(
        base_url=server_url,
        input_value="Please greet the new hire Jeremy.",
        store=True,
    )
    follow_up_body = _create_response(
        base_url=server_url,
        input_value="Now provide onboarding next steps and cite the name of the new hire",
    )
    assert follow_up_body["conversation"]["id"] != first_body["conversation"]["id"]
    assert "jeremy" not in follow_up_body["output"][0]["content"][0]["text"].lower()


@all_available_servers
@pytest.mark.parametrize(
    "arg_name,arg_value",
    [
        ("max_tool_calls", 1),
        ("parallel_tool_calls", True),
        ("prompt", {"id": "1"}),
        ("reasoning", {"effort": "minimal"}),
        ("safety_identifier", "something"),
        ("service_tier", "flex"),
        ("text", {"format": {"type": "text"}}),
        ("tool_choice", "none"),
        (
            "tools",
            [{"name": "get_weather", "parameters": {}, "strict": True, "type": "function"}],
        ),
        ("top_p", 0.95),
        ("truncation", "disabled"),
    ],
)
def test_unsupported_arguments_raise(server_url, arg_name, arg_value):
    payload: Dict[str, Any] = {
        "model": "hr-assistant",
        "input": "hi",
        arg_name: arg_value,
    }
    response = httpx.post(
        f"{server_url}/v1/responses",
        json=payload,
        timeout=120.0,
    )
    print(response.content)
    assert response.status_code == 501


@pytest.mark.parametrize(
    ["argument", "value"],
    [
        ("max_tool_calls", 5),
        ("parallel_tool_calls", True),
        ("prompt", {"id": "random_id"}),
        ("reasoning", {"effort": "high"}),
        ("safety_identifier", "none"),
        ("service_tier", "auto"),
        ("text", {"verbosity": "medium"}),
        ("tool_choice", "none"),
        ("tools", [{"name": "get_weather", "parameters": {}, "strict": True, "type": "function"}]),
        ("top_logprobs", 4),
        ("top_p", 1),
        ("truncation", "auto"),
    ],
)
@all_available_servers
def test_unsupported_argument_raises_with_official_openai(
    official_openai_client, argument, value
) -> None:
    from openai import InternalServerError

    messages = [
        {"role": "user", "content": "List employee benefits for John Smith."},
    ]
    with pytest.raises(
        InternalServerError,
        match=f"Error code: 501 - {{'detail': '`{argument}` is not supported yet'}}",
    ):
        response = official_openai_client.responses.create(
            model="hr-assistant", input=messages, **{f"{argument}": value}
        )


# we first test with our openai compatible LLM to ensure the stateless
# (the state is maintained by the client)
# works correctly with:
# - text
# - tool calls
# - tool responses
# - image
# both without and with streaming

with_and_without_streaming = pytest.mark.parametrize("streaming", [False, True])


@pytest.fixture
def openai_client_with_server(server_url):
    client_llm = OpenAICompatibleModel(
        model_id="hr-assistant",
        base_url=server_url,
        api_type=OpenAIAPIType.RESPONSES,
    )
    return client_llm


def _stream_and_return_output(
    client_llm: OpenAICompatibleModel, prompt: Union[str, Prompt]
) -> LlmCompletion:
    text = ""
    completion = None
    for chunk_type, chunk in client_llm.stream_generate(prompt):
        if chunk_type == StreamChunkType.TEXT_CHUNK:
            text += chunk.content
        if chunk_type == StreamChunkType.END_CHUNK:
            if chunk.content not in text:
                continue
            completion = LlmCompletion(message=chunk, token_usage=None)
    assert chunk.content in text
    assert completion is not None
    return completion


@retry_test(max_attempts=3)
@all_available_servers
@with_and_without_streaming
def test_create_response_via_openai_compatible_llm(openai_client_with_server, streaming) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.81 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    prompt = "List employee benefits for John Smith."
    if streaming:
        completion = _stream_and_return_output(openai_client_with_server, prompt)
    else:
        completion = openai_client_with_server.generate(prompt)
    assert "unlimited" in completion.message.content.lower(), "Expected LLM completion content."


@retry_test(max_attempts=3)
@all_available_servers
@with_and_without_streaming
def test_create_response_via_openai_compatible_llm_handles_tool_requests_and_responses(
    openai_client_with_server, streaming
) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    messages = [
        Message(
            content="What is the weather in Zurich?",
            message_type=MessageType.USER,
        )
    ]
    if streaming:
        completion = _stream_and_return_output(openai_client_with_server, Prompt(messages=messages))
    else:
        completion = openai_client_with_server.generate(Prompt(messages=messages))
    tool_requests = completion.message.tool_requests or []
    assert tool_requests, "Expected the assistant to request a tool call."
    assert tool_requests[0].name == "get_weather"
    assert tool_requests[0].args["city"].lower() == "zurich"

    messages.append(completion.message)

    tool_result_message = Message(
        tool_result=ToolResult(
            content="sunny",
            tool_request_id=tool_requests[0].tool_request_id,
        ),
    )
    messages.append(tool_result_message)

    follow_up_prompt = Prompt(messages=messages)
    if streaming:
        completion = _stream_and_return_output(openai_client_with_server, follow_up_prompt)
    else:
        completion = openai_client_with_server.generate(follow_up_prompt)
    assert completion.message.tool_requests is None
    assert "sunny" in completion.message.content.lower()


# we then test in stateful mode
# (the state is maintained by the server)
# works correctly with:
# - text
# - tool calls
# - tool responses
# - image
# both without and with streaming


@pytest.fixture
def server_url(server_fixture_name, request):
    return request.getfixturevalue(server_fixture_name)


def _stream_request_and_return_output(
    server_url: str, input_value: Any, **kwargs
) -> Dict[str, Any]:
    sse_events = []
    streaming_payload = {
        "model": "hr-assistant",
        "input": input_value,
        "stream": True,
        **kwargs,
    }
    with httpx.stream(
        "POST",
        f"{server_url}/v1/responses",
        json=streaming_payload,
        timeout=120.0,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith("data:"):
                sse_events.append(line[len("data:") :].strip())
            if line.strip() == "data: [DONE]":
                break
    non_empty_events = [
        json.loads(event) for event in sse_events if event and "[DONE]" not in event
    ]

    assert any(non_empty_events)

    response_completed = [e for e in non_empty_events if e.get("type") == "response.completed"]
    assert len(response_completed) == 1

    response = response_completed[0].get("response")

    deltas = [
        e.get("delta") for e in response_completed if e.get("type") == "response.output_text.delta"
    ]
    assert all(d in str(response) for d in deltas)
    return response


@retry_test(max_attempts=3)
@all_available_servers
@with_and_without_streaming
def test_create_response_stateful(server_url, streaming) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.81 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    prompt = "What the name of the employee starting in M?"
    if streaming:
        response = _stream_request_and_return_output(server_url, prompt)
    else:
        response = _create_response(
            base_url=server_url,
            input_value=prompt,
        )
    assert "mary" in response["output"][0]["content"][0]["text"].lower()
    prompt = "What's the name of the person you just talked about?"
    if streaming:
        response = _stream_request_and_return_output(
            server_url=server_url, input_value=prompt, previous_response_id=response["id"]
        )
    else:
        response = _create_response(
            base_url=server_url, input_value=prompt, previous_response_id=response["id"]
        )
    text_response = response["output"][0]["content"][0]["text"].lower()
    assert "mary" in text_response


@retry_test(max_attempts=3)
@all_available_servers
@with_and_without_streaming
def test_create_response_with_tool_request_and_tools_stateful(server_url, streaming) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    prompt = "What is the weather in Zurich?"
    if streaming:
        response = _stream_request_and_return_output(
            server_url=server_url,
            input_value=prompt,
        )
    else:
        response = _create_response(
            base_url=server_url,
            input_value=prompt,
        )

    output = response["output"]
    assert len(output) == 1
    tool_request = output[0]
    assert all(k in tool_request for k in ["arguments", "call_id", "name"])
    assert tool_request["name"] == "get_weather"

    tool_result = {
        "call_id": tool_request["call_id"],
        "output": "sunny",
        "type": "function_call_output",
    }

    prompt = [tool_result]
    if streaming:
        response = _stream_request_and_return_output(
            server_url=server_url,
            input_value=prompt,
            previous_response_id=response["id"],
        )
    else:
        response = _create_response(
            base_url=server_url,
            input_value=prompt,
            previous_response_id=response["id"],
        )
    output = response["output"][0]["content"][0]["text"]
    assert "sunny" in output


@retry_test(max_attempts=3)
def test_agent_with_mcp_tools_is_supported(multi_agent_inmemory_server):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    response = _create_response(
        base_url=multi_agent_inmemory_server,
        input_value="What is the capital of France?",
        model="mcp-assistant",
        headers=_get_api_key_headers(),
    )
    output = response["output"][0]["content"][0]["text"]
    assert "paris" in output.lower()
    follow_up = _create_response(
        base_url=multi_agent_inmemory_server,
        input_value="and the biggest city?",
        model="mcp-assistant",
        previous_response_id=response["id"],
        headers=_get_api_key_headers(),
    )
    output = follow_up["output"][0]["content"][0]["text"]
    assert "paris" in output.lower()


@retry_test(max_attempts=3)
def test_agent_with_datastore_is_supported(datastore_agent_inmemory_server):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    response = _create_response(
        base_url=datastore_agent_inmemory_server,
        input_value="What is the capital of France?",
        model="datastore-swarm",
    )
    output = response["output"][0]["content"][0]["text"]
    assert "paris" in output.lower()
    follow_up = _create_response(
        base_url=datastore_agent_inmemory_server,
        input_value="and the biggest city?",
        model="datastore-assistant",
        previous_response_id=response["id"],
    )
    output = follow_up["output"][0]["content"][0]["text"]
    assert "paris" in output.lower()


@retry_test(max_attempts=3)
@all_available_servers
@with_and_without_streaming
def test_create_response_official_openai(official_openai_client, streaming) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    messages = [{"role": "user", "content": "List employee benefits for John Smith."}]
    if streaming:
        content = _openai_stream_content(official_openai_client, messages)
    else:
        response = official_openai_client.responses.create(model="hr-assistant", input=messages)
        content = response.output_text
    assert "unlimited" in content.lower()


@retry_test(max_attempts=3)
@all_available_servers
def test_create_response_handles_tool_requests_and_calls_official_openai(
    official_openai_client,
) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    messages = [{"role": "user", "content": "What is the weather in Zurich?"}]
    response = official_openai_client.responses.create(
        model="hr-assistant",
        input=messages,
    )
    tool_call = response.output[0]
    assert tool_call.type == "function_call"
    assert tool_call.name == "get_weather"
    arguments = json.loads(tool_call.arguments)
    assert arguments["city"].lower() == "zurich"
    # Provide tool result
    messages.append(
        {
            "arguments": tool_call.arguments,
            "call_id": tool_call.call_id,
            "name": tool_call.name,
            "type": tool_call.type,
        }
    )
    messages.append(
        {
            "output": "sunny",
            "call_id": tool_call.call_id,
            "type": "function_call_output",
        }
    )
    response = official_openai_client.responses.create(
        model="hr-assistant",
        input=messages,
    )
    content = response.output_text
    assert "sunny" in content.lower()


@retry_test(max_attempts=3)
@all_available_servers
@with_and_without_streaming
def test_create_response_with_string_input_official_openai(
    official_openai_client, streaming
) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    input_message = "List employee benefits for John Smith."
    if streaming:
        content = _openai_stream_content(official_openai_client, input_message)
    else:
        response = official_openai_client.responses.create(
            model="hr-assistant", input=input_message
        )
        content = response.output_text
    assert "unlimited" in content.lower()


@retry_test(max_attempts=3)
@all_available_servers
@with_and_without_streaming
def test_multiple_inputs_official_openai(official_openai_client, streaming) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    messages = [
        {
            "role": "system",
            "content": "Answer all questions asked by the user in your role as a HR assistant",
        },
        {"role": "user", "content": "Hi how are you doing today?"},
        {
            "role": "assistant",
            "content": "I am doing great! Thanks for asking! How can I help you today?",
        },
        {"role": "user", "content": "List employee benefits for John Smith."},
    ]
    if streaming:
        content = _openai_stream_content(official_openai_client, messages)
    else:
        response = official_openai_client.responses.create(model="hr-assistant", input=messages)
        content = response.output_text
    assert "unlimited" in content.lower()


@all_available_servers
def test_create_can_resume_from_given_turn_or_conversation(server_url) -> None:

    def _make_request(**kwargs: Any) -> Dict[str, Any]:
        return _create_response(
            base_url=server_url, model="simple-flow", input_value="whatever", **kwargs
        )

    response_0 = _make_request()
    conversation_id = response_0["conversation"]["id"]
    assert "0" in response_0["output"][0]["content"][0]["text"]

    def _check_answer_is_correct(request: Dict[str, Any], idx: str):
        assert idx in request["output"][0]["content"][0]["text"]
        assert request["conversation"]["id"] == conversation_id

    # one follow up
    response_1 = _make_request(
        previous_response_id=response_0["id"],
    )
    _check_answer_is_correct(response_1, "1")

    # using the conversation id mid-conversation
    response_intermediate = _make_request(
        conversation=conversation_id,
    )
    _check_answer_is_correct(response_intermediate, "2")

    # second follow-up
    response_2 = _make_request(
        previous_response_id=response_1["id"],
    )
    _check_answer_is_correct(response_2, "2")

    # using the conversation id again
    response_final = _make_request(
        conversation=conversation_id,
    )
    _check_answer_is_correct(response_final, "3")

    # restart from a given turn
    response_0_followup = _make_request(
        previous_response_id=response_0["id"],
    )
    _check_answer_is_correct(response_0_followup, "1")
    response_1_followup = _make_request(
        previous_response_id=response_1["id"],
    )
    _check_answer_is_correct(response_1_followup, "2")
    response_2_followup = _make_request(
        previous_response_id=response_2["id"],
    )
    _check_answer_is_correct(response_2_followup, "3")


@retry_test(max_attempts=3)
@all_available_servers
@with_and_without_streaming
def test_invalid_role_raises_with_official_openai(official_openai_client, streaming) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    from openai import UnprocessableEntityError

    messages = [
        {"role": "users", "content": "List employee benefits for John Smith."},
    ]

    with pytest.raises(UnprocessableEntityError, match="Error code: 422 -"):
        if streaming:
            content = _openai_stream_content(official_openai_client, messages)
        else:
            response = official_openai_client.responses.create(model="hr-assistant", input=messages)


def test_create_request_with_image_raises_when_llm_does_not_support_it_with_official_openai(
    multi_agent_openai_client,
):
    import openai

    image_path = Path(__file__).parent.parent / "configs/test_data/image.png"
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    with pytest.raises(
        openai.APIStatusError, match="The underlying model does not support multimodal inputs"
    ):
        input_message = {
            "role": "user",
            "content": [
                {"text": "what is the color of this logo?", "type": "input_text"},
                {"type": "input_image", "image_url": image_b64, "detail": "low"},
            ],
        }
        response = multi_agent_openai_client.responses.create(
            model="image-assistant", input=[input_message]
        )


@all_available_servers
def test_agent_can_be_given_instructions_when_agent_does_not_support_it(server_url):
    response = httpx.post(
        f"{server_url}/v1/responses",
        json=dict(
            input="What is the capital of Switzerland?",
            model="hr-assistant",
            instructions="The user is actually mixing up Sweden and Switzerland, so take that into account when he asks about countries",
        ),
        timeout=120.0,
    )
    assert response.status_code == 406
    assert "Agent should have an `instructions` input descriptor" in str(response.content)


@retry_test(max_attempts=3)
def test_agent_cant_be_given_instructions(multi_agent_inmemory_server):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    response = httpx.post(
        f"{multi_agent_inmemory_server}/v1/responses",
        json=dict(
            input="What is the capital of Switzerland?",
            model="mcp-assistant",
            instructions="The capital of Switzerland has changed, it's ZURICH now. Zurich is the new capital of Switzerland",
        ),
        headers=_get_api_key_headers(),
        timeout=120.0,
    )
    response.raise_for_status()
    assert "zurich" in str(response.content).lower()


@retry_test(max_attempts=3)
def test_tool_confirmation_is_not_implemented(multi_agent_inmemory_server):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-24
    Average success time:  1.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    response = httpx.post(
        f"{multi_agent_inmemory_server}/v1/responses",
        json=dict(
            input="What are Maria's benefits?",
            model="tool-confirmation-assistant",
        ),
        headers=_get_api_key_headers(),
        timeout=120.0,
    )
    assert response.status_code == 501
    assert "Unhandled wayflow status: ToolExecutionConfirmationStatus" in str(response.content)


def test_missing_api_token_in_request(multi_agent_inmemory_server):
    response = httpx.post(
        f"{multi_agent_inmemory_server}/v1/responses",
        json=dict(
            input="what is the capital of Switzerland?",
            model="mcp-assistant",
        ),
        timeout=120.0,
    )
    assert response.status_code == 401
    assert "Missing or invalid bearer token" in str(response.content)
