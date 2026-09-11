# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Union
from unittest.mock import patch

import httpx
import pytest

from wayflowcore.agent import Agent
from wayflowcore.executors.executionstatus import ToolExecutionConfirmationStatus
from wayflowcore.property import AnyProperty, FloatProperty, IntegerProperty, StringProperty
from wayflowcore.tools import RemoteTool

from ...testhelpers.testhelpers import retry_test


@dataclass
class MockResponse:
    json_value: Any
    content: bytes
    status_code: int

    @property
    def is_success(self) -> bool:
        return self.status_code < 400

    def json(
        self,
    ) -> Dict[str, Union[str, List[Union[Dict[str, str], Dict[str, Union[str, List[str]]]]]]]:
        return self.json_value

    @staticmethod
    def from_object(obj: Any = {}) -> "MockResponse":
        return MockResponse(json_value=obj, content=json.dumps(obj).encode(), status_code=200)


def test_remote_tool_can_be_instantiated():
    tool = RemoteTool(
        name="get_example_tool",
        description="does a GET request to the example domain",
        url="https://example.com/endpoint",
        method="GET",
    )
    assert len(tool.parameters) == 0


def test_remote_tool_headers_and_sensitive_headers_cannot_overlap():
    with pytest.raises(
        ValueError,
        match="Some headers have been specified in both `headers` and `sensitive_headers`",
    ):
        _ = RemoteTool(
            name="get_example_tool",
            description="does a GET request to the example domain",
            url="https://example.com/endpoint",
            method="GET",
            headers={"exclusive_key_1": "value", "shared_key": 1},
            sensitive_headers={"exclusive_key_2": "value", "shared_key": 1},
        )


def test_remote_tool_has_correct_input_arguments():
    tool = RemoteTool(
        name="get_example_tool",
        description="does a GET request to the example domain",
        url="https://example.com/version/{{version}}/documents/{{ document_id }}",
        method="{{method}}",
    )
    assert len(tool.parameters) == 3
    assert "version" in tool.parameters
    assert "document_id" in tool.parameters
    assert "method" in tool.parameters


@patch.object(
    httpx.AsyncClient, "request", return_value=MockResponse.from_object({"full": "response"})
)
def test_remote_tool_returns_whole_response_by_default(patched_request):
    tool = RemoteTool(
        name="get_example_tool",
        description="does a GET request to the example domain",
        url="https://example.com/endpoint",
        method="GET",
    )
    tool_result = tool.run()
    assert tool_result == '{"full": "response"}'


@patch.object(
    httpx.AsyncClient,
    "request",
    return_value=MockResponse.from_object({"a": "b", "c": ["d", {"e": "f", "g": ["h", "i"]}]}),
)
def test_remote_tool_uses_the_jq_query(patched_request):
    tool = RemoteTool(
        name="get_example_tool",
        description="does a GET request to the example domain",
        url="https://example.com/endpoint",
        method="GET",
        output_jq_query=".c[1].g[1]",
    )
    tool_result = tool.run()
    assert tool_result == "i"


@retry_test(max_attempts=3, wait_between_tries=1)
@patch.object(
    httpx.AsyncClient,
    "request",
    return_value=MockResponse.from_object({"weather": "strong winds at 45 km/h"}),
)
def test_agent_can_use_remote_tool_with_confirmation(patched_request, remotely_hosted_llm):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-10-10
    Average success time:  0.98 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    weather_tool = RemoteTool(
        name="forecast_weather",
        description="Returns a forecast of the weather for the chosen city",
        url="https://weatherforecast.com/city/{{ city }}",
        method="GET",
        output_jq_query=".weather",
        requires_confirmation=True,
    )
    agent = Agent(
        llm=remotely_hosted_llm,
        tools=[weather_tool],
        max_iterations=3,
    )

    conversation = agent.start_conversation()
    conversation.append_user_message("What is the speed of the winds in Zurich?")
    status = conversation.execute()
    assert isinstance(status, ToolExecutionConfirmationStatus)
    status.confirm_tool_execution(tool_request=status.tool_requests[0])
    conversation.execute()
    patched_request.assert_called_once()
    assert (
        patched_request.call_args.kwargs["url"].lower() == "https://weatherforecast.com/city/zurich"
    )
    agent_message = conversation.get_last_message().content
    assert "45" in agent_message  # The speed of the winds


@patch.object(httpx.AsyncClient, "request", return_value=MockResponse.from_object({}))
def test_remote_tool_correctly_parametrizes_requests(patched_request):
    tool = RemoteTool(
        name="get_example_tool",
        description="does a GET request to the example domain",
        url="https://example.com/version/{{version}}/documents/{{ document_id }}",
        method="{{method}}",
    )
    tool.run(
        version="v2",
        document_id="42",
        method="POST",
    )
    patched_request.assert_called_once_with(
        url="https://example.com/version/v2/documents/42",
        method="POST",
    )


@retry_test(max_attempts=3, wait_between_tries=1)
@patch.object(
    httpx.AsyncClient,
    "request",
    return_value=MockResponse.from_object({"weather": "strong winds at 45 km/h"}),
)
def test_agent_can_use_a_simple_remote_tool(patched_request, remotely_hosted_llm):
    """
    Failure rate:          0 out of 50
    Observed on:           2025-01-27
    Average success time:  4.21 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    weather_tool = RemoteTool(
        name="forecast_weather",
        description="Returns a forecast of the weather for the chosen city",
        url="https://weatherforecast.com/city/{{ city }}",
        method="GET",
        output_jq_query=".weather",
    )

    agent = Agent(
        llm=remotely_hosted_llm,
        tools=[weather_tool],
        max_iterations=3,
    )

    conversation = agent.start_conversation()
    conversation.append_user_message("What is the speed of the winds in Zurich?")
    conversation.execute()
    patched_request.assert_called_once()
    assert (
        patched_request.call_args.kwargs["url"].lower() == "https://weatherforecast.com/city/zurich"
    )
    agent_message = conversation.get_last_message().content
    assert "45" in agent_message  # The speed of the winds


def test_remote_tool_warns_with_json_body():
    with pytest.warns(
        DeprecationWarning, match="Usage of `json_body` parameter in RemoteTool is Deprecated"
    ):
        remote_tool = RemoteTool(
            name="get_example_tool",
            description="does a GET request to the example domain",
            url="https://example.com/version/{{version}}/documents/{{ document_id }}",
            json_body="{{param1}}",
            method="GET",
        )


@patch.object(
    httpx.AsyncClient, "request", return_value=MockResponse.from_object({"sum": 9, "product": 18})
)
def test_remote_tool_with_multiple_outputs_maps_json_response_keys(patched_request):
    # The endpoint returns the JSON object expected by the declared outputs; the tool used to
    # return the raw body as a string and fail the multiple-outputs check.
    tool = RemoteTool(
        name="sum_multiply_tool",
        description="sums and multiplies two numbers",
        url="https://example.com/compute",
        method="POST",
        data={"a": "{{a}}", "b": "{{b}}"},
        output_descriptors=[FloatProperty(name="sum"), FloatProperty(name="product")],
    )
    assert tool.run(a=3, b=6) == {"sum": 9, "product": 18}


@patch.object(
    httpx.AsyncClient,
    "request",
    return_value=MockResponse.from_object({"result": {"sum": 9, "product": 18}, "status": "ok"}),
)
def test_remote_tool_with_multiple_outputs_applies_jq_query_first(patched_request):
    tool = RemoteTool(
        name="sum_multiply_tool",
        description="sums and multiplies two numbers",
        url="https://example.com/compute",
        method="GET",
        output_jq_query=".result",
        output_descriptors=[FloatProperty(name="sum"), FloatProperty(name="product")],
    )
    assert tool.run() == {"sum": 9, "product": 18}


@patch.object(
    httpx.AsyncClient, "request", return_value=MockResponse.from_object({"sum": 9, "other": 1})
)
def test_remote_tool_with_multiple_outputs_uses_default_for_missing_key(patched_request):
    tool = RemoteTool(
        name="sum_multiply_tool",
        description="sums and multiplies two numbers",
        url="https://example.com/compute",
        method="GET",
        output_descriptors=[
            FloatProperty(name="sum"),
            FloatProperty(name="product", default_value=0.0),
        ],
    )
    # jq yields null for a missing key, which is replaced by the output default
    assert tool.run() == {"sum": 9, "product": 0.0}


@patch.object(httpx.AsyncClient, "request", return_value=MockResponse.from_object(42))
def test_remote_tool_with_single_typed_output_parses_json_response(patched_request):
    tool = RemoteTool(
        name="count_tool",
        description="counts things",
        url="https://example.com/count",
        method="GET",
        output_descriptors=[IntegerProperty(name="count")],
    )
    assert tool.run() == 42


@pytest.mark.parametrize(
    "output_descriptor", [StringProperty(name="body"), AnyProperty(name="body")]
)
@patch.object(
    httpx.AsyncClient, "request", return_value=MockResponse.from_object({"full": "response"})
)
def test_remote_tool_with_single_text_output_keeps_raw_response(patched_request, output_descriptor):
    tool = RemoteTool(
        name="get_example_tool",
        description="does a GET request to the example domain",
        url="https://example.com/endpoint",
        method="GET",
        output_descriptors=[output_descriptor],
    )
    assert tool.run() == '{"full": "response"}'
