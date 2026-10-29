# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import asyncio
import json
import logging
import os
import re
from copy import deepcopy
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest

from wayflowcore.messagelist import Message, MessageContent, TextContent
from wayflowcore.models import LlmGenerationConfig, LlmModelFactory, OCIGenAIModel, Prompt
from wayflowcore.models._requesthelpers import StreamChunkType
from wayflowcore.models.ociclientconfig import OCIClientConfig, _OCIAuthType
from wayflowcore.models.ocigenaimodel import (
    _MODEL_PROVIDER_TO_FORMATTER,
    ModelProvider,
    OciAPIType,
    ServingMode,
    _detect_provider_from_model_id,
    _GenericOciApiFormatter,
    _OpenAIOciApiFormatter,
)
from wayflowcore.property import ListProperty, ObjectProperty, StringProperty
from wayflowcore.retrypolicy import RetryPolicy
from wayflowcore.templates import PromptTemplate
from wayflowcore.tools import ClientTool, ToolRequest

from ..conftest import (
    DUMMY_OCI_USER_CONFIG_DICT,
    GROK_OCI_RESPONSE_API_KEY_CONFIG,
    LLAMA_OCI_API_KEY_CONFIG,
    LLAMA_OCI_INSTANCE_PRINCIPAL_CONFIG,
    OCI_REASONING_MODEL_API_KEY_CONFIG,
    compartment_id,
)
from ..testhelpers.testhelpers import retry_test
from .test_models import CHAT_TEXT_PROMPT, REQUIRES_REASONING_PROMPT
from .test_openaicompatiblemodel import run_responses_tool_call_replay_e2e


class UnsupportedContent(MessageContent):
    def __hash__(self) -> Any:
        pass


def parametrize_with_oci_configs():
    all_oci_model_configs = [
        LLAMA_OCI_INSTANCE_PRINCIPAL_CONFIG,
        LLAMA_OCI_API_KEY_CONFIG,
    ]
    return pytest.mark.parametrize("oci_model_config", all_oci_model_configs)


@parametrize_with_oci_configs()
def test_ocigenai_model_creation_with_client_config_dict(oci_model_config):
    llm = LlmModelFactory.from_config(oci_model_config)
    assert isinstance(llm, OCIGenAIModel)
    assert llm.client_config.auth_type == oci_model_config["client_config"]["auth_type"]
    assert llm.client_config.compartment_id == oci_model_config["client_config"]["compartment_id"]
    assert (
        llm.client_config.service_endpoint == oci_model_config["client_config"]["service_endpoint"]
    )


@parametrize_with_oci_configs()
def test_ocigenai_model_creation_with_client_config_obj(oci_model_config):
    oci_model_config_ = deepcopy(oci_model_config)
    oci_model_config_["client_config"] = OCIClientConfig.from_dict(
        oci_model_config_["client_config"]
    )
    llm = LlmModelFactory.from_config(oci_model_config_)
    assert isinstance(llm, OCIGenAIModel)
    assert llm.client_config == oci_model_config_["client_config"]


def test_ocigenai_model_creation_with_user_authentication(
    dummy_oci_client_config_with_user_authentication,
):
    oci_llama_config_using_user_auth = {
        "model_type": "ocigenai",
        "model_id": LLAMA_OCI_API_KEY_CONFIG["model_id"],
        "client_config": dummy_oci_client_config_with_user_authentication,
    }
    llm = LlmModelFactory.from_config(oci_llama_config_using_user_auth)

    assert isinstance(llm, OCIGenAIModel)
    assert llm.client_config.auth_type == _OCIAuthType.API_KEY
    assert llm.client_config == dummy_oci_client_config_with_user_authentication


def test_oci_user_authentication_config_does_not_print_content(
    dummy_oci_client_config_with_user_authentication,
):
    # cannot print the content of user config; it instead prints something like below
    user_config = dummy_oci_client_config_with_user_authentication.user_config
    user_config_regex = re.compile(
        "<wayflowcore.models.ociclientconfig.OCIUserAuthenticationConfig object at (.*)>"
    )
    assert user_config_regex.match(str(user_config)) is not None
    assert user_config_regex.match(repr(user_config)) is not None

    assert DUMMY_OCI_USER_CONFIG_DICT["key_content"] not in str(user_config)
    assert DUMMY_OCI_USER_CONFIG_DICT["key_content"] not in repr(user_config)

    assert DUMMY_OCI_USER_CONFIG_DICT["fingerprint"] not in str(user_config)
    assert DUMMY_OCI_USER_CONFIG_DICT["fingerprint"] not in repr(user_config)

    # user_config is not exposed at the client_config level either
    assert "user_config" not in str(dummy_oci_client_config_with_user_authentication)
    assert "key_content" not in str(dummy_oci_client_config_with_user_authentication)
    assert str(DUMMY_OCI_USER_CONFIG_DICT) not in str(
        dummy_oci_client_config_with_user_authentication
    )
    assert repr(DUMMY_OCI_USER_CONFIG_DICT) not in repr(
        dummy_oci_client_config_with_user_authentication
    )
    assert DUMMY_OCI_USER_CONFIG_DICT["key_content"] not in str(
        dummy_oci_client_config_with_user_authentication
    )
    assert DUMMY_OCI_USER_CONFIG_DICT["key_content"] not in repr(
        dummy_oci_client_config_with_user_authentication
    )


def test_ocigenai_using_user_authentication(oci_user_authentication_config):
    oci_llama_config_using_user_auth = {
        "model_type": "ocigenai",
        "model_id": LLAMA_OCI_API_KEY_CONFIG["model_id"],
        "client_config": oci_user_authentication_config,
    }
    llm = LlmModelFactory.from_config(oci_llama_config_using_user_auth)
    res = llm.generate(prompt=Prompt(CHAT_TEXT_PROMPT)).message
    assert len(res.contents) > 0
    assert isinstance(res.contents[0], TextContent)
    assert len(res.contents[0].content) > 0


@pytest.mark.skipif(
    not ("OCI_GENAI_API_KEY_CONFIG" in os.environ and "OCI_GENAI_API_KEY_PEM" in os.environ),
    reason="OCI GENAI models not configured",
)
@pytest.mark.skipif(
    not os.path.exists(os.path.expanduser("~/.oci/config")),
    reason="Missing OCI config file (~/.oci/config) for API_KEY auth",
)
@retry_test(max_attempts=4)
def test_oci_responses_e2e_can_continue_after_tool_call_with_replayed_history() -> None:
    """
    Failure rate:          0 out of 10
    Observed on:           2026-03-03
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    pytest.importorskip("oci_openai")

    oci_responses_config = deepcopy(GROK_OCI_RESPONSE_API_KEY_CONFIG)
    oci_responses_config["generation_config"] = {"max_tokens": 64}
    llm = LlmModelFactory.from_config(oci_responses_config)
    assert isinstance(llm, OCIGenAIModel)
    run_responses_tool_call_replay_e2e(llm)


@pytest.mark.parametrize(
    "api_type,max_tokens_key",
    [
        (OciAPIType.OPENAI_CHAT_COMPLETIONS, "max_completion_tokens"),
        (OciAPIType.OPENAI_RESPONSES, "max_output_tokens"),
    ],
)
def test_oci_openai_api_generation_config_reaches_sdk_create(api_type, max_tokens_key):
    captured_create_kwargs = {}

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def model_dump(self):
            return self.payload

    class FakeResponses:
        async def create(self, **kwargs):
            captured_create_kwargs.update(kwargs)
            return FakeResponse(
                {
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "ok"}],
                        }
                    ]
                }
            )

    class FakeChatCompletions:
        async def create(self, **kwargs):
            captured_create_kwargs.update(kwargs)
            return FakeResponse({"choices": [{"message": {"role": "assistant", "content": "ok"}}]})

    class FakeChat:
        completions = FakeChatCompletions()

    class FakeOciOpenAIClient:
        responses = FakeResponses()
        chat = FakeChat()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            pass

    llm = OCIGenAIModel(
        model_id="openai.gpt-oss-120b",
        compartment_id="compartment-id",
        client_config=OCIClientConfig.from_dict(
            {
                "service_endpoint": "https://example.com",
                "auth_type": "API_KEY",
            }
        ),
        api_type=api_type,
        generation_config=LlmGenerationConfig(
            max_tokens=13,
            temperature=0.2,
            top_p=0.9,
            extra_args={"reasoning": {"effort": "low"}},
        ),
    )

    with patch.object(llm, "_init_client_if_needed", side_effect=llm._init_client), patch.object(
        llm, "_create_openai_client", return_value=FakeOciOpenAIClient()
    ):
        llm.generate(Prompt(messages=[Message(role="user", content="hello")]))

    assert captured_create_kwargs["model"] == "openai.gpt-oss-120b"
    assert captured_create_kwargs["store"] is False
    assert captured_create_kwargs["temperature"] == 0.2
    assert captured_create_kwargs["top_p"] == 0.9
    assert captured_create_kwargs[max_tokens_key] == 13
    assert captured_create_kwargs["reasoning"]["effort"] == "low"
    assert "prompt_cache_key" not in captured_create_kwargs

    if api_type == OciAPIType.OPENAI_RESPONSES:
        assert captured_create_kwargs["reasoning"]["summary"] == "auto"
        assert "reasoning.encrypted_content" in captured_create_kwargs["include"]


@pytest.mark.skipif(
    not os.path.exists(os.path.expanduser("~/.oci/config")), reason="Missing OCI config file"
)
@pytest.mark.filterwarnings(
    "ignore:Model .* is switching to the Responses API because Chat Completions does not support "
    "tools with non-none reasoning effort\\.:UserWarning"
)
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("api_type", [OciAPIType.OCI, OciAPIType.OPENAI_CHAT_COMPLETIONS])
def test_oci_reasoning_tools_use_responses_without_changing_config(api_type, stream):
    pytest.importorskip("oci_openai")
    config = deepcopy(OCI_REASONING_MODEL_API_KEY_CONFIG)
    config.update(model_id="openai.gpt-5.6-luna", api_type=api_type)
    config["generation_config"] = {"max_tokens": 1024, "reasoning_effort": "LOW"}
    llm = LlmModelFactory.from_config(config)
    prompt = Prompt(
        messages=[Message(role="user", content="Call test_tool now.")],
        tools=[ClientTool(name="test_tool", description="A no-op tool.", input_descriptors=[])],
    )
    message = list(llm.stream_generate(prompt))[-1][1] if stream else llm.generate(prompt).message
    assert message.tool_requests and message.tool_requests[0].name == "test_tool"
    assert llm.api_type == api_type and prompt.generation_config is None
    assert llm.generation_config.extra_args == {"reasoning_effort": "LOW"}


@pytest.mark.skip("Skip because we do not have any custom dedicated model on our tenancy")
def test_using_dedicated_model_on_oci():
    model = OCIGenAIModel(
        model_id="SOME_ENDPOINT_MODEL",
        service_endpoint="some_endpoint",
        serving_mode=ServingMode.DEDICATED,
        auth_type="INSTANCE_PRINCIPAL",
    )
    completion = model.generate("count to 5")


def test_dedicated_model_with_arbitrary_model_id_works():
    OCIGenAIModel(
        model_id="ANY_NAME_I_WANT",
        serving_mode=ServingMode.DEDICATED,
        service_endpoint="some_endpoint",
        compartment_id="comp_id",
        provider=ModelProvider.META,
        auth_type="INSTANCE_PRINCIPAL",
    )


def test_oci_generic_unsupported_content_type():
    """Test that an unsupported content type raises a RuntimeError in OCI Generic formatter."""
    llm = LlmModelFactory.from_config(LLAMA_OCI_INSTANCE_PRINCIPAL_CONFIG)

    message = Message(
        role="user",
        contents=[UnsupportedContent()],
    )

    with pytest.raises(RuntimeError, match="Unsupported content of type"):
        llm.generate(Prompt([message]))


def test_oci_model_raises_warning_when_parameters_are_not_supported(grok_oci_llm, caplog):
    # The shared live-model retry policy disables HTTP retries. This test needs one
    # retry so Wayflow can handle OCI's unsupported-parameter error by removing
    # `stop` from the generation config and resubmitting the request.
    grok_oci_llm.retry_policy = RetryPolicy(max_attempts=1, request_timeout=30.0)

    with caplog.at_level(logging.WARNING):
        completion = grok_oci_llm.generate(
            prompt=Prompt(
                messages=[Message(content="Reply with a short greeting.", role="user")],
                generation_config=LlmGenerationConfig(max_tokens=32, stop=["unused_stop"]),
            )
        )

    assert len(completion.message.contents) > 0
    assert isinstance(completion.message.contents[0], TextContent)
    assert len(completion.message.contents[0].content) > 0
    assert "Parameter `stop` is not supported by the OCI GenAI endpoint" in caplog.text


@pytest.mark.parametrize(
    "model_id,serving_mode,provider,expected_api_format,expected_max_tokens",
    [
        # auto-resolution of the provider
        ("meta.model_name", ServingMode.ON_DEMAND, None, "GENERIC", True),
        ("grok.model_name", ServingMode.ON_DEMAND, None, "GENERIC", False),
        ("cohere.model_name", ServingMode.ON_DEMAND, None, "COHERE", True),
        # when using some name
        ("meta.model_name", ServingMode.ON_DEMAND, ModelProvider.META, "GENERIC", True),
        ("grok.model_name", ServingMode.ON_DEMAND, ModelProvider.OTHER, "GENERIC", False),
        ("cohere.model_name", ServingMode.ON_DEMAND, ModelProvider.COHERE, "COHERE", True),
        # override the provider
        ("meta.model_name", ServingMode.ON_DEMAND, ModelProvider.COHERE, "COHERE", True),
        ("grok.model_name", ServingMode.ON_DEMAND, ModelProvider.META, "GENERIC", True),
        ("cohere.model_name", ServingMode.ON_DEMAND, ModelProvider.OTHER, "GENERIC", False),
        # specify the right provider with dedicated
        ("meta.model_name", ServingMode.DEDICATED, ModelProvider.META, "GENERIC", True),
        ("grok.model_name", ServingMode.DEDICATED, ModelProvider.OTHER, "GENERIC", False),
        ("cohere.model_name", ServingMode.DEDICATED, ModelProvider.COHERE, "COHERE", True),
        # auto-detect serving mode
        ("meta.model_name", None, ModelProvider.META, "GENERIC", True),
        (
            "ocid1.generativeaimodel.oc1.us-chicago-1.aaaaaaa",
            None,
            ModelProvider.META,
            "GENERIC",
            True,
        ),
        (
            "ocid2.generativeaiendpoint.oc1.us-chicago-1.aaaaaaa",
            None,
            ModelProvider.META,
            "GENERIC",
            True,
        ),
    ],
)
def test_model_uses_proper_provider(
    model_id,
    serving_mode,
    provider,
    expected_api_format,
    expected_max_tokens,
    oci_agent_client_config,
):
    llm = OCIGenAIModel(
        model_id=model_id,
        client_config=oci_agent_client_config,
        compartment_id=compartment_id,
        serving_mode=serving_mode,
        provider=provider,
    )

    should_be_dedicated = serving_mode == ServingMode.DEDICATED or "generativeai" in model_id

    class StopAtMock(ValueError):
        pass

    def raise_exception(**kwargs: Any) -> None:
        raise StopAtMock()

    with patch(
        "oci.generative_ai_inference.GenerativeAiInferenceClient.chat", side_effect=raise_exception
    ) as mock:
        try:
            prompt = PromptTemplate.from_string(
                "hello", generation_config=LlmGenerationConfig(max_tokens=100)
            ).format()
            llm.generate(prompt)
        except StopAtMock:
            pass

        assert mock.call_count == 1
        _, kwargs = mock.call_args
        chat_details = kwargs["chat_details"]
        assert (
            chat_details.serving_mode.serving_type == "DEDICATED"
            if should_be_dedicated
            else "ON_DEMAND"
        )
        if should_be_dedicated:
            assert chat_details.serving_mode.endpoint_id == model_id
        else:
            assert chat_details.serving_mode.model_id == model_id
        assert chat_details.chat_request.api_format == expected_api_format
        if expected_max_tokens:
            assert chat_details.chat_request.max_tokens == 100
        else:
            assert chat_details.chat_request.max_completion_tokens == 100


def test_dedicated_model_forces_to_specify_provider(oci_agent_client_config):
    with pytest.raises(
        ValueError,
        match="When using dedicated mode, please pass the provider of your dedicated model",
    ):
        OCIGenAIModel(
            model_id="any-model-name",
            client_config=oci_agent_client_config,
            compartment_id="fake-compartment-id",
            serving_mode=ServingMode.DEDICATED,
        )


@retry_test(max_attempts=3)
def test_oci_model_has_exact_count_and_reasoning_tokens():
    """
    Failure rate:          0 out of 50
    Observed on:           2025-12-08
    Average success time:  3.85 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    llm = LlmModelFactory.from_config(OCI_REASONING_MODEL_API_KEY_CONFIG)

    token_usage = llm.generate(prompt=REQUIRES_REASONING_PROMPT).token_usage
    assert token_usage.exact_count
    assert token_usage.reasoning_tokens > 0


@retry_test(max_attempts=4)
@pytest.mark.parametrize(
    "model_config",
    [OCI_REASONING_MODEL_API_KEY_CONFIG],
)
def test_oci_stream_has_exact_token_count(model_config):
    """
    Failure rate:          0 out of 10
    Observed on:           2026-06-30
    Average success time:  6.02 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    llm = LlmModelFactory.from_config(model_config)

    for _ in llm.stream_generate(Prompt(messages=CHAT_TEXT_PROMPT)):
        pass

    token_usage = llm.token_usage_standalone
    assert token_usage.exact_count
    assert token_usage.input_tokens > 0
    assert token_usage.output_tokens > 0


def test_oci_generic_stream_ignores_done_sentinel():
    chunks = list(
        _GenericOciApiFormatter.convert_oci_chunk_iterator_into_tagged_chunk_iterator(
            iter(
                [
                    SimpleNamespace(
                        data='{"message": {"content": [{"type": "TEXT", "text": "Hi"}]}}'
                    ),
                    SimpleNamespace(data="[DONE]"),
                ]
            )
        )
    )

    assert chunks[-1][1].content == "Hi"


@pytest.mark.parametrize("value", [[], ["one"], ["one", "two"]])
@pytest.mark.parametrize("use_subclass", [False, True])
def test_oci_openai_stream_exposes_only_unwrapped_root_list(monkeypatch, value, use_subclass):
    if use_subclass:

        class CustomOpenAIFormatter(_OpenAIOciApiFormatter):
            pass

        monkeypatch.setitem(
            _MODEL_PROVIDER_TO_FORMATTER, ModelProvider.OPENAI, CustomOpenAIFormatter
        )

    prompt = Prompt(
        messages=[Message(content="List items", role="user")],
        response_format=ListProperty(name="results"),
    )
    model = object.__new__(OCIGenAIModel)
    model.provider = ModelProvider.OPENAI
    model._client = object()
    model._oci_serving_mode = object()
    monkeypatch.setattr(model, "_init_client_if_needed", lambda: None)
    events = [
        SimpleNamespace(data=json.dumps({"message": {"content": [{"type": "TEXT", "text": part}]}}))
        for part in ['{"items": ', json.dumps(value), "}"]
    ]
    events.append(
        SimpleNamespace(
            data=json.dumps(
                {"usage": {"promptTokens": 5, "completionTokens": 8, "totalTokens": 13}}
            )
        )
    )
    events.append(SimpleNamespace(data="[DONE]"))
    response = SimpleNamespace(data=SimpleNamespace(events=lambda: iter(events)))
    monkeypatch.setattr(model, "_post_stream_with_retry", lambda provider, prompt: response)

    async def collect():
        return [chunk async for chunk in model._stream_generate_impl_oci_sdk(prompt)]

    chunks = asyncio.run(collect())
    assert [chunk[0] for chunk in chunks] == [
        StreamChunkType.START_CHUNK,
        StreamChunkType.TEXT_CHUNK,
        StreamChunkType.END_CHUNK,
    ]
    assert json.loads(chunks[1][1].content) == value
    assert json.loads(chunks[2][1].content) == value
    assert chunks[-1][2].total_tokens == 13


@pytest.mark.parametrize("model_id", ["openai.gpt-4.1-mini", "openai.gpt-6-sol"])
def test_oci_openai_root_list_request(model_id):
    provider = _detect_provider_from_model_id(model_id)
    assert provider == ModelProvider.OPENAI
    formatter = _MODEL_PROVIDER_TO_FORMATTER[provider]
    assert formatter is _OpenAIOciApiFormatter
    response_format = ListProperty(
        name="results",
        item_type=ObjectProperty(
            properties={"label": StringProperty()}, additional_properties=False
        ),
    )
    prompt = Prompt(
        messages=[Message(content="List items", role="user")], response_format=response_format
    )
    original_schema = response_format.to_json_schema(openai_compatible=True)
    request = formatter.convert_prompt_into_request(prompt, model_id)
    schema = request.response_format.json_schema.schema
    assert schema["type"] == "object"
    assert schema["required"] == ["items"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["items"] == original_schema
    assert prompt.response_format is response_format
    assert response_format.to_json_schema(openai_compatible=True) == original_schema


@pytest.mark.parametrize(
    "response_format",
    [
        None,
        ObjectProperty(
            name="result", properties={"items": ListProperty()}, additional_properties=False
        ),
    ],
)
def test_oci_openai_non_list_request_unchanged(response_format):
    prompt = Prompt(
        messages=[Message(content="Hello", role="user")], response_format=response_format
    )
    actual = _OpenAIOciApiFormatter.convert_prompt_into_request(prompt, "openai.gpt")
    expected = _GenericOciApiFormatter.convert_prompt_into_request(prompt, "openai.gpt")
    assert actual == expected
    message = Message(content='{"items": ["one"]}', role="assistant")
    assert _OpenAIOciApiFormatter.unwrap_response_message(message, prompt) is message


@pytest.mark.parametrize("model_id", ["meta.llama", "google.gemini", "xai.grok", "other.model"])
def test_oci_other_providers_keep_root_list_schema(model_id):
    provider = _detect_provider_from_model_id(model_id)
    formatter = _MODEL_PROVIDER_TO_FORMATTER.get(provider, _GenericOciApiFormatter)
    prompt = Prompt(
        messages=[Message(content="List items", role="user")],
        response_format=ListProperty(name="results"),
    )
    request = formatter.convert_prompt_into_request(prompt, model_id)
    assert request.response_format.json_schema.schema["type"] == "array"


@pytest.mark.parametrize("value", [[], ["one"], [{"label": "one"}], [["one"]]])
def test_oci_openai_complete_list_unwrapped_before_parser(monkeypatch, value):
    parser = Mock()
    parser.parse_output.side_effect = lambda message: message
    prompt = Prompt(messages=[], response_format=ListProperty(name="results"), output_parser=parser)
    response = SimpleNamespace(
        data=SimpleNamespace(
            chat_response=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=[
                                SimpleNamespace(type="TEXT", text=json.dumps({"items": value}))
                            ],
                            tool_calls=None,
                        )
                    )
                ]
            )
        )
    )
    model = object.__new__(OCIGenAIModel)
    model.provider = ModelProvider.OPENAI
    monkeypatch.setattr(model, "_post_with_retry", lambda provider, prompt: response)
    completion = asyncio.run(model._generate_impl_oci_sdk(prompt))
    assert json.loads(completion.message.content) == value
    parser.parse_output.assert_called_once()
    assert json.loads(parser.parse_output.call_args.args[0].content) == value


@pytest.mark.parametrize("content", ["", "incomplete {", '{"other": []}', '{"items": null}'])
def test_oci_openai_unwrap_preserves_unexpected_response(content):
    prompt = Prompt(messages=[], response_format=ListProperty(name="results"))
    message = Message(content=content, role="assistant")
    assert _OpenAIOciApiFormatter.unwrap_response_message(message, prompt) is message


def test_oci_openai_unwrap_preserves_tool_calls():
    prompt = Prompt(messages=[], response_format=ListProperty(name="results"))
    message = Message(
        content="",
        role="assistant",
        tool_requests=[ToolRequest(name="lookup", args={}, tool_request_id="call-1")],
    )
    assert _OpenAIOciApiFormatter.unwrap_response_message(message, prompt) is message


@pytest.mark.parametrize("provider", [ModelProvider.OPENAI, ModelProvider.META, ModelProvider.XAI])
@pytest.mark.parametrize("response_format", [None, ObjectProperty(name="result")])
def test_oci_normal_stream_returns_message_and_preserves_deltas(
    monkeypatch, provider, response_format
):
    model = object.__new__(OCIGenAIModel)
    model.provider = provider
    model._client = object()
    model._oci_serving_mode = object()
    monkeypatch.setattr(model, "_init_client_if_needed", lambda: None)
    events = [
        SimpleNamespace(data=json.dumps({"message": {"content": [{"type": "TEXT", "text": part}]}}))
        for part in ['{"items": ', '["one"]}']
    ]
    response = SimpleNamespace(data=SimpleNamespace(events=lambda: iter(events)))
    monkeypatch.setattr(model, "_post_stream_with_retry", lambda provider, prompt: response)
    parser = Mock()
    parser.parse_output.side_effect = lambda message: message.copy(content=message.content.upper())
    prompt = Prompt(messages=[], output_parser=parser, response_format=response_format)

    async def collect():
        return [chunk async for chunk in model._stream_generate_impl_oci_sdk(prompt)]

    chunks = asyncio.run(collect())
    assert [chunk[1].content for chunk in chunks] == [
        "",
        '{"items": ',
        '["one"]}',
        '{"ITEMS": ["ONE"]}',
    ]
    parser.parse_output.assert_called_once()


def test_oci_openai_responses_generation_config_reaches_service(oci_reasoning_model):
    pytest.importorskip("oci_openai")

    assert isinstance(oci_reasoning_model, OCIGenAIModel)
    oci_reasoning_model.api_type = OciAPIType.OPENAI_RESPONSES
    oci_reasoning_model.generation_config = LlmGenerationConfig(
        max_tokens=32,
        extra_args={"reasoning": {"effort": "invalid-effort"}},
    )

    with pytest.raises(Exception, match="invalid-effort|Invalid value|reasoning.effort"):
        oci_reasoning_model.generate("How do you optimize the TSP problem?")


def test_oci_openai_responses_generation_config_supports_reasoning(oci_reasoning_model):
    pytest.importorskip("oci_openai")

    assert isinstance(oci_reasoning_model, OCIGenAIModel)
    oci_reasoning_model.api_type = OciAPIType.OPENAI_RESPONSES
    oci_reasoning_model.generation_config = LlmGenerationConfig(
        max_tokens=64,
        extra_args={"reasoning": {"effort": "low"}},
    )

    completion = oci_reasoning_model.generate("Reply with a short greeting.")

    assert len(completion.message.contents) > 0
    assert completion.token_usage is None or completion.token_usage.exact_count
