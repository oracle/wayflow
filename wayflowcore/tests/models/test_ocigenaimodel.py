# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import os
import re
import unittest
from copy import deepcopy
from typing import Any
from unittest.mock import patch

import pytest

from wayflowcore import Flow
from wayflowcore.messagelist import ImageContent, Message, MessageContent, TextContent
from wayflowcore.models import LlmGenerationConfig, LlmModelFactory, OCIGenAIModel, Prompt
from wayflowcore.models.ociclientconfig import OCIClientConfig, _OCIAuthType
from wayflowcore.models.ocigenaimodel import ModelProvider, ServingMode
from wayflowcore.templates import PromptTemplate
from wayflowcore.tools.tools import ToolRequest

from ..conftest import (
    COHERE_OCI_API_KEY_CONFIG,
    COHERE_OCI_INSTANCE_PRINCIPAL_CONFIG,
    DUMMY_OCI_USER_CONFIG_DICT,
    LLAMA_OCI_API_KEY_CONFIG,
    LLAMA_OCI_INSTANCE_PRINCIPAL_CONFIG,
    compartment_id,
)
from .test_models import CHAT_TEXT_PROMPT


class UnsupportedContent(MessageContent):
    def __hash__(self) -> Any:
        pass


@pytest.fixture(scope="function")
def flow_with_oci_cohere(monkeypatch) -> Flow:  # type: ignore
    """
    Temporarily patches the environment variables to include proxies
    in order to block ocigenai (and make it time out)
    """
    from wayflowcore.flowhelpers import create_single_step_flow
    from wayflowcore.steps import PromptExecutionStep

    oracle_http_proxy = os.environ.get("ORACLE_HTTP_PROXY")
    if not oracle_http_proxy:
        raise Exception("ORACLE_HTTP_PROXY is not set in the environment")
    # no type hints for monkeypatch https://github.com/pytest-dev/pytest/issues/2712
    proxies = {
        "HTTP_PROXY": oracle_http_proxy,
        "http_proxy": oracle_http_proxy,
    }
    for proxy_var_name, proxy_value in proxies.items():
        monkeypatch.setenv(proxy_var_name, proxy_value)
    return create_single_step_flow(
        PromptExecutionStep(
            "Repeat the word Banana",
            llm=LlmModelFactory.from_config(COHERE_OCI_INSTANCE_PRINCIPAL_CONFIG),
        )
    )


def parametrize_with_oci_configs():
    all_oci_model_configs = [
        COHERE_OCI_INSTANCE_PRINCIPAL_CONFIG,
        COHERE_OCI_API_KEY_CONFIG,
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
    oci_cohere_config_using_user_auth = {
        "model_type": "ocigenai",
        "model_id": COHERE_OCI_API_KEY_CONFIG["model_id"],
        "client_config": oci_user_authentication_config,
    }
    llm = LlmModelFactory.from_config(oci_cohere_config_using_user_auth)
    res = llm.generate(prompt=Prompt(CHAT_TEXT_PROMPT)).message
    assert len(res.contents) > 0
    assert isinstance(res.contents[0], TextContent)
    assert len(res.contents[0].content) > 0


def test_ocigenai_model_throws_exception_when_wrongly_configured(
    flow_with_oci_cohere: Flow,
) -> None:
    with pytest.raises(
        Exception,
        match="Instance principals authentication can only be used on OCI compute instances",
    ):
        conversation = flow_with_oci_cohere.start_conversation()
        conversation.execute()


def test_cohere_warning_on_max_tokens():

    class FakeGeneration(ValueError):
        pass

    def fake_generation(*args, **kwargs):
        raise FakeGeneration

    cohere_config = deepcopy(COHERE_OCI_API_KEY_CONFIG)
    cohere_config["generation_config"] = {"max_tokens": 99}
    model_from_factory = LlmModelFactory.from_config(cohere_config)
    assert model_from_factory.generation_config.max_tokens == 99
    cohere_config.pop("generation_config")
    with pytest.warns(UserWarning, match="Setting `max_tokens` to 512 for cohere"):
        model_from_factory = LlmModelFactory.from_config(cohere_config)
        with unittest.mock.patch(
            "oci.generative_ai_inference.models.ChatDetails", side_effect=fake_generation
        ) as patch:
            with pytest.raises(FakeGeneration):
                model_from_factory.generate("hello")
            chat_request = patch.call_args[1]["chat_request"]
            assert chat_request.max_tokens == 512

    cohere_config.pop("model_type")
    client_config = cohere_config.pop("client_config")
    with pytest.warns(UserWarning, match="Setting `max_tokens` to 512 for cohere"):
        initialized_model = OCIGenAIModel(
            **cohere_config, client_config=OCIClientConfig.from_dict(client_config)
        )
        with unittest.mock.patch(
            "oci.generative_ai_inference.models.ChatDetails", side_effect=fake_generation
        ) as patch:
            with pytest.raises(FakeGeneration):
                initialized_model.generate("hello")
            chat_request = patch.call_args[1]["chat_request"]
            assert chat_request.max_tokens == 512


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


def run_generate_and_expect_error(llm, prompt, match):
    with pytest.raises(RuntimeError, match=match):
        llm.generate(prompt)


@pytest.mark.parametrize(
    "messages,match",
    [
        # Case: Image content as user
        (
            [
                Message(
                    role="user",
                    contents=[ImageContent.from_bytes(bytes_content=b"1234", format="png")],
                )
            ],
            r"Cohere models only support text messages as input",
        ),
        # Case: Image content as assistant with tool requests and conversation
        (
            [
                Message(role="user", contents=[TextContent("Hi")]),
                Message(
                    role="assistant",
                    contents=[ImageContent.from_bytes(bytes_content=b"1234", format="png")],
                    tool_requests=[
                        ToolRequest(
                            name="test-tool", tool_request_id="tool-id-1", args={"param": "value"}
                        )
                    ],
                ),
                Message(role="assistant", contents=[TextContent("Hi")]),
                Message(role="user", contents=[TextContent("Hi")]),
            ],
            r"Cohere models only support text messages as input",
        ),
        # Case: Unsupported content object type
        (
            [Message(role="user", contents=[UnsupportedContent()])],
            r"Cohere models only support text messages as input",
        ),
    ],
    ids=["user-image-content", "assistant-image-content-with-tools", "unsupported-content-type"],
)
def test_oci_cohere_invalid_content_and_unsupported_types(messages, match):
    """
    Test that invalid or unsupported content types/messages raise a RuntimeError in OCI Cohere formatter.
    """
    llm = LlmModelFactory.from_config(COHERE_OCI_INSTANCE_PRINCIPAL_CONFIG)
    prompt = Prompt(messages)
    run_generate_and_expect_error(llm, prompt, match)


def test_oci_model_raises_warning_when_parameters_are_not_supported(grok_oci_llm, caplog):
    with caplog.at_level(logging.WARNING):
        grok_oci_llm.generate(
            prompt=Prompt(
                messages=[Message(content="2+2=", role="user")],
                generation_config=LlmGenerationConfig(
                    stop=["4"],
                ),
            )
        )
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
