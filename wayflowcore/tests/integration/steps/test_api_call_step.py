# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from multiprocessing import Process
from typing import Any, Dict, List, Tuple, Union
from urllib.parse import urlparse

import httpx
import pytest

from wayflowcore.flowhelpers import (
    create_single_step_flow,
    run_single_step,
    run_step_and_return_outputs,
)
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.serialization.serializer import deserialize
from wayflowcore.steps.apicallstep import ApiCallStep
from wayflowcore.steps.step import Step

from ...utils import get_available_port

URL_TEMPLATE_VALUE = "a/b/c?param=baram&rama=bu77er"
ENCODED_URL_TEMPLATE_VALUE = "a%2Fb%2Fc%3Fparam%3Dbaram%26rama%3Dbu77er"


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


@dataclass
class AsyncRequestFaker:
    requests: List[Tuple[tuple, dict]] = field(default_factory=list)
    response: httpx.Response = field(default_factory=MockResponse.from_object)

    def overwrite_status_code(self, code: int):
        self.response.status_code = code

    async def __call__(self, *args: Any, **kwds: Any) -> Any:
        self.requests.append((args, kwds))
        return self.response


@pytest.fixture
def faked_request(monkeypatch):
    request_faker = AsyncRequestFaker()
    monkeypatch.setattr(httpx.AsyncClient, "request", request_faker)
    return request_faker


def test_mock_api_call_very_basic(faked_request) -> None:

    step = ApiCallStep(
        url="https://example.com/endpoint",
        method="GET",
    )

    assert len(step.input_descriptors) == 0

    outputs = run_step_and_return_outputs(step, inputs={})
    assert outputs == {ApiCallStep.HTTP_STATUS_CODE: 200}


def test_mock_api_call_io(faked_request) -> None:

    faked_request.response = MockResponse.from_object(
        {
            "value1": "test",
            "values": [{"n": "a", "list": []}, {"n": "b", "list": ["a", "b", "c"]}],
        }
    )

    step = ApiCallStep(
        url="https://example.com/endpoint",
        method="POST",
        json_body={"value": "{{ v1 }}", "listofvalues": ["a", "{{ v2 }}", "c"]},
        params={"param": "{{ p1 }}"},
        headers={"header1": "{{ h1 }}"},
        sensitive_headers={"sensitive_header1": "{{ sh1 }}"},
        output_values_json={
            "v1": ".value1",
            ListProperty(name="v2list", item_type=StringProperty("inner_str")): ".values[1].list",
        },
    )

    assert len(step.input_descriptors) == 5
    input_descriptor_names = set(
        input_descriptor.name for input_descriptor in step.input_descriptors
    )
    assert input_descriptor_names == {"v1", "v2", "p1", "h1", "sh1"}

    inputs = {
        "v1": "test1",
        "v2": "test2",
        "p1": "test3",
        "h1": "test4",
        "sh1": "test5",
    }
    outputs = run_step_and_return_outputs(step, inputs=inputs)
    assert outputs == {
        ApiCallStep.HTTP_STATUS_CODE: 200,
        "v1": "test",
        "v2list": ["a", "b", "c"],
    }

    output_descriptor_keys = {key.name for key in step.output_descriptors}
    assert output_descriptor_keys == outputs.keys()

    assert faked_request.requests == [
        (
            (),
            {
                "url": step.url,
                "method": step.method,
                "json": {"value": "test1", "listofvalues": ["a", "test2", "c"]},
                "params": {"param": "test3"},
                "headers": {"header1": "test4", "sensitive_header1": "test5"},
            },
        )
    ]


def test_url_param_encoding(faked_request) -> None:

    step = ApiCallStep(
        url="https://example.com/endpoint/{{ url_template }}",
        method="GET",
    )

    inputs = {"url_template": URL_TEMPLATE_VALUE}
    _ = run_step_and_return_outputs(step, inputs=inputs)

    assert faked_request.requests == [
        (
            (),
            {
                "url": f"https://example.com/endpoint/{ENCODED_URL_TEMPLATE_VALUE}",
                "method": "GET",
            },
        )
    ]


def deploy_test_webapp(hostname: str, port: int):
    class RequestHandler(BaseHTTPRequestHandler):

        def create_content(self):
            path = urlparse(self.path)
            query = {k.split("=", 2)[0]: k.split("=", 2)[1] for k in path.query.split("&", 2)}
            body_values = {}

            if "Content-Length" in self.headers:
                length = int(self.headers["Content-Length"])
                body_values = json.loads(self.rfile.read(length))

            return {
                "test": "test",
                "__full_path": self.path,
                "__parsed_path": path.path,
                **dict(self.headers.items()),
                **query,
                **body_values,
            }

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self, content=None):
            content = content or self.create_content()
            content_text = json.dumps(content).encode()
            if content.get("fail"):
                self.send_response(HTTPStatus.IM_A_TEAPOT)
            else:
                self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(content_text))
            self.end_headers()
            self.wfile.write(content_text)

    server = HTTPServer((hostname, port), RequestHandler)
    server.serve_forever()


def check_server_is_up(base_url: str) -> bool:
    try:
        response = httpx.get(f"{base_url}?q=3")
        return response.status_code == 200
    except httpx.ConnectError as e:
        return False


@pytest.fixture(scope="module")
def test_webapp(session_tmp_path: str):
    hostname = "localhost"
    port = get_available_port(session_tmp_path)
    process = Process(target=deploy_test_webapp, kwargs={"hostname": hostname, "port": port})
    process.start()

    try:
        base_url = f"http://{hostname}:{port}"

        server_up = False
        remaining_attempts = 10

        while remaining_attempts > 0 and not server_up:
            remaining_attempts -= 1
            server_up = check_server_is_up(base_url)
            if server_up:
                break
            else:
                time.sleep(1)

        if remaining_attempts <= 0 and not server_up:
            raise ValueError("Server did not start")

        yield base_url

    finally:
        process.terminate()


def test_api_call_step_actual_endpoint(test_webapp: str) -> None:

    step = ApiCallStep(
        url=test_webapp + "/api/{{ u1 }}",
        method="POST",
        json_body={"value": "{{ v1 }}", "listofvalues": ["a", "{{ v2 }}", "c"]},
        params={"param": "{{ p1 }}"},
        headers={"header1": "{{ h1 }}"},
        sensitive_headers={"sensitive_header1": "{{ sh1 }}"},
        output_values_json={
            "v2": ".listofvalues[1]",
            "vl": ".listofvalues[-1]",
            "p": ".param",
            "h": ".header1",
            "sh": ".sensitive_header1",
            "test": ".test",
            "path": ".__parsed_path",
            ListProperty(name="v2list", item_type=StringProperty("inner_str")): ".listofvalues",
        },
        allow_insecure_http=True,
    )

    inputs_dict = {
        "v1": "test1",
        "v2": "test2",
        "p1": "test3",
        "h1": "test4",
        "sh1": "test5",
        "u1": URL_TEMPLATE_VALUE,
    }

    outputs = run_step_and_return_outputs(step, inputs=inputs_dict)

    assert outputs == {
        "v2": "test2",
        "vl": "c",
        "p": "test3",
        "h": "test4",
        "sh": "test5",
        "test": "test",
        "v2list": ["a", "test2", "c"],
        ApiCallStep.HTTP_STATUS_CODE: 200,
        "path": f"/api/{ENCODED_URL_TEMPLATE_VALUE}",
    }


def test_load_api_call_step_from_yaml(test_webapp: str) -> None:
    step = deserialize(
        Step,
        """
            _component_type: Step
            step_args:
                url: \""""
        + test_webapp
        + """/v1/{{ input_id }}"
                method: POST
                json_body: >
                    {
                        "param": "{{ input_param }}"
                    }
                params:
                    query_param: "{{ input_param }}"
                headers:
                    header_param: "{{ input_param }}"
                output_values_json:
                    body_param: .param
                    query_param:  .query_param
                    header_param: .header_param
                    path: .__parsed_path
                allow_insecure_http: true
            step_cls: ApiCallStep
            """,
    )

    inputs_dict = {
        "input_id": URL_TEMPLATE_VALUE,
        "input_param": "return_param",
    }

    outputs = run_step_and_return_outputs(step, inputs=inputs_dict)

    assert outputs == {
        ApiCallStep.HTTP_STATUS_CODE: 200,
        "body_param": "return_param",
        "query_param": "return_param",
        "header_param": "return_param",
        "path": f"/v1/{ENCODED_URL_TEMPLATE_VALUE}",
    }


def test_api_call_step_kwargs_arguments() -> None:
    config = {
        k: None
        for k in [
            "url",
            "method",
            "data",
            "json_body",
            "params",
            "headers",
            "sensitive_headers",
            "cookies",
            "output_values_json",
            "store_response",
        ]
    }

    # just make sure it doesn't throw
    ApiCallStep._compute_step_specific_input_descriptors_from_static_config(**config)
    ApiCallStep._compute_step_specific_output_descriptors_from_static_config(**config)


def test_api_call_step_in_flow():
    create_single_step_flow(step=ApiCallStep(url="fakeurl", method="GET"))


def test_api_call_step_disallow_http_by_default_instantiation():
    # Test exception thrown at initialization
    with pytest.raises(ValueError):
        step = ApiCallStep(
            url="http://example.com/endpoint",
            method="GET",
        )


def test_api_call_step_disallow_http_by_default_runstep(faked_request):
    # Test exception thrown at request
    with pytest.raises(ValueError):
        step = ApiCallStep(
            url="{{scheme}}://example.com/endpoint",
            method="GET",
        )

        inputs_dict = {
            "scheme": "http",
        }
        run_single_step(step, inputs_dict)


def test_api_call_step_disallow_http_by_default_allowed(faked_request):
    # Test explicitly allowing http
    step = ApiCallStep(
        url="https://example.com/endpoint",
        method="GET",
        allow_insecure_http=True,
    )

    run_single_step(step)


def test_api_call_step_may_contain_http(faked_request):
    # Testing whether other parts of the url containing the string http works correctly.
    step = ApiCallStep(url="https://example.com/http", method="GET")

    run_single_step(step)


def test_api_call_step_does_not_throw_if_allow_list_none(faked_request):
    step = ApiCallStep(
        url="https://someurl.example.com/endpoint",
        method="GET",
    )

    run_single_step(step)


def test_api_call_step_throws_if_disallowed_credentials(faked_request):
    with pytest.raises(ValueError):
        step = ApiCallStep(
            url="https://user:pass@someurl.example.com/endpoint",
            method="GET",
            allow_credentials=False,
        )
        run_single_step(step)


def test_api_call_step_does_not_throw_if_allowed_credentials(faked_request):
    step = ApiCallStep(
        url="https://user:pass@someurl.example.com/endpoint", method="GET", allow_credentials=True
    )
    run_single_step(step)


def test_api_call_step_does_not_throw_if_allowed_fragments(faked_request):
    step = ApiCallStep(
        url="https://someurl.example.com/endpoint#fragment", method="GET", allow_fragments=True
    )
    run_single_step(step)


def test_api_call_step_throws_if_disallowed_fragments(faked_request):
    with pytest.raises(ValueError):
        step = ApiCallStep(
            url="https://someurl.example.com/endpoint#fragment",
            method="GET",
            allow_fragments=False,
        )
        run_single_step(step)


def test_api_call_step_headers_and_sensitive_headers_cannot_overlap():
    with pytest.raises(
        ValueError,
        match="Some headers have been specified in both `headers` and `sensitive_headers`",
    ):
        _ = ApiCallStep(
            name="get_example_tool",
            url="https://example.com/endpoint",
            method="GET",
            headers={"exclusive_key_1": "value", "shared_key": 1},
            sensitive_headers={"exclusive_key_2": "value", "shared_key": 1},
        )


def _create_step_and_run(url, method, url_allow_list):
    step = ApiCallStep(url=url, method=method, url_allow_list=url_allow_list)
    return run_single_step(step)


@pytest.mark.parametrize(
    "url, method, url_allow_list",
    [
        ("https://example.com/page", "GET", ["https://example.com/page"]),
        ("https://subdomain.trusted-domain.com", "GET", ["https://subdomain.trusted-domain.com"]),
        ("https://specific.com/path/and/more", "GET", ["https://specific.com/path"]),
        ("https://user:pass@example.com/", "GET", ["https://user:pass@example.com"]),
        (
            "https://example.com/script%20%3Cscript%3Ealert(1)%3C/script%3E",
            "GET",
            ["https://example.com/script%20%3Cscript%3Ealert(1)%3C/script%3E"],
        ),
        ("https://xn--n3h.com/", "GET", ["https://xn--n3h.com/"]),
        ("https://127.0.0.1/metadata", "GET", ["https://127.0.0.1/metadata"]),
    ],
)
def test_api_call_step_does_not_throw_if_in_allow_list_parameter_url(
    faked_request, url, method, url_allow_list
):
    _create_step_and_run(url, method, url_allow_list)


@pytest.mark.parametrize(
    "url, method, url_allow_list, expected_error_message",
    [
        (
            "https://someurl.example.com",  # Not in list
            "GET",
            ["https://test.example.com", "https://other.example.com"],
            "Requested URL is not in allowed list",
        ),
        (
            "https://someurl.example.com",  # Wrong scheme
            "GET",
            ["http://someurl.example.com"],
            "Requested URL is not in allowed list",
        ),
        (
            "https://someurl.example.com/path",  # Paths dont match
            "GET",
            ["https://someurl.example.com/differentpath"],
            "Requested URL is not in allowed list",
        ),
        (
            "https://someurl.example.com/endpoint",
            "GET",
            ["https://"],
            "validation error for",
        ),
        (
            "https://someurl.example.com/endpoint",
            "GET",
            [""],
            "validation error for",
        ),
        (
            "https://example.com/%00",
            "GET",
            ["https://example.com/"],
            "An error occurred when normalizing the URL.",
        ),
        (
            "https://example.com/",
            "GET",
            ["https://example.com/%00"],
            "An error occurred when normalizing the URL.",
        ),
        (
            "https://user:pass@example.com/",
            "GET",
            ["https://example.com/"],
            "Requested URL is not in allowed list.",
        ),
        (
            "https://example.com/",
            "GET",
            ["https://user:pass@example.com/"],
            "Requested URL is not in allowed list.",
        ),
        (
            "javascript:alert(1)",
            "GET",
            ["javascript:alert(1)"],
            "An error occurred when normalizing the URL.",
        ),
        (
            "https://example.com:99999/",  # invalid port
            "GET",
            ["https://example.com"],
            "validation error for",
        ),
        (
            "https://example..com/",  # invalid url
            "GET",
            ["https://example.com"],
            "An error occurred when normalizing the URL.",
        ),
        (
            "https://example.com/%invalid",  # invalid encoding
            "GET",
            ["https://example.com"],
            "An error occurred when normalizing the URL.",
        ),
        (
            "https://％77％77％77％2E％65％78％61％6D％70％6C％65％2E％63％6F％6D/",  # invalid encoding
            "GET",
            ["https://example.com"],
            "validation error for",
        ),
    ],
)
def test_api_call_step_throws_if_not_in_allow_list_netloc_overlap(
    faked_request, url, method, url_allow_list, expected_error_message
):
    with pytest.raises(ValueError):
        _create_step_and_run(url, method, url_allow_list)
