# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import os
from unittest.mock import MagicMock, patch

import pytest

from wayflowcore.models import OpenAICompatibleModel
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.llmmodel import LlmModel
from wayflowcore.models.llmmodelfactory import LlmModelFactory
from wayflowcore.models.ociclientconfig import (
    OCIClientConfigWithApiKey,
    OCIClientConfigWithUserAuthentication,
)
from wayflowcore.models.ocigenaimodel import ModelProvider, OCIGenAIModel, ServingMode
from wayflowcore.models.openaimodel import OpenAIModel
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.serialization import autodeserialize, deserialize, serialize, serialize_to_dict
from wayflowcore.warnings import SecurityWarning

from ..conftest import COHERE_OCI_API_KEY_CONFIG, DUMMY_OCI_USER_CONFIG_DICT

llama_api_url = os.environ.get("LLAMA_API_URL")
if not llama_api_url:
    raise Exception("LLAMA_API_URL is not set in the environment")

compartment_id = os.environ.get("COMPARTMENT_ID")
if not compartment_id:
    raise Exception("COMPARTMENT_ID is not set in the environment")
# Note: These look like JSON format, but is YAML format, don't be confused!
OPEN_AI_MODEL = '{model_type: openai, model_id: "gpt-3.5-turbo", _component_type: LlmModel}'
VLLM_MODEL = (
    '{"model_type" : "vllm", "host_port" : "'
    + llama_api_url
    + '", "model_id" : "meta-llama/Meta-Llama-3.1-8B-Instruct", "__metadata_info__":{"ui_name":"VLLM_NAME"}'
    + ", _component_type: LlmModel}"
)
COHERE_MODEL = (
    '{"model_type" : "ocigenai", "model_id" : "cohere.command-r-plus", "service_endpoint": "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com", "compartment_id": "'
    + compartment_id
    + '", "auth_type": "INSTANCE_PRINCIPAL"'
    + ", _component_type: LlmModel}"
)


def test_can_deserialize_vllm() -> None:
    assistant_llm_model = deserialize(LlmModel, VLLM_MODEL)
    assert isinstance(assistant_llm_model, LlmModel)
    assert isinstance(assistant_llm_model, VllmModel)
    assert "ui_name" in assistant_llm_model.__metadata_info__
    assert assistant_llm_model.__metadata_info__["ui_name"] == "VLLM_NAME"


@patch.dict(os.environ, {"OPENAI_API_KEY": "dummykey"})
def test_serialized_openai_model_matches_original_config() -> None:
    assistant_llm_model = deserialize(LlmModel, OPEN_AI_MODEL)
    assert isinstance(assistant_llm_model, LlmModel)
    assert isinstance(assistant_llm_model, OpenAIModel)


def test_can_deserialize_ocigenai() -> None:
    assistant_llm_model = deserialize(LlmModel, COHERE_MODEL)
    assert isinstance(assistant_llm_model, LlmModel)
    assert isinstance(assistant_llm_model, OCIGenAIModel)


@patch.dict(os.environ, {"OPENAI_API_KEY": "dummykey"})
def test_serialized_openai_model_matches_original_config() -> None:
    new_serialized_model = serialize(deserialize(LlmModel, OPEN_AI_MODEL))
    assert "openai" in new_serialized_model
    assert "gpt-3.5-turbo" in new_serialized_model


def test_serialized_vllm_model_matches_original_config() -> None:
    new_serialized_model = serialize(deserialize(LlmModel, VLLM_MODEL))
    assert "vllm" in new_serialized_model
    assert llama_api_url in new_serialized_model


def test_serialized_ocigenai_model_matches_original_config() -> None:
    new_serialized_model = serialize(deserialize(LlmModel, COHERE_MODEL))
    assert "cohere" in new_serialized_model
    assert "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com" in new_serialized_model


def _check_deserialized_vllm_model_validity(old_model: VllmModel, new_model: VllmModel):
    assert isinstance(new_model, VllmModel)
    assert new_model.host_port == old_model.host_port
    assert new_model.model_id == old_model.model_id
    assert new_model.generation_config.max_tokens == old_model.generation_config.max_tokens
    assert new_model.__metadata_info__ == old_model.__metadata_info__


def test_deserialized_vllm_model_matches_original() -> None:
    model_id, host_port = "zephyr-7b-beta", "LLAMA_API_ENDPOINT"
    llm_assistant_model = VllmModel(
        host_port=host_port,
        model_id=model_id,
        generation_config=LlmGenerationConfig(
            max_tokens=1234,
        ),
        __metadata_info__={"llm_ui_name": "ZEPHYR"},
    )
    new_llm_assistant_model = deserialize(LlmModel, serialize(llm_assistant_model))
    _check_deserialized_vllm_model_validity(llm_assistant_model, new_llm_assistant_model)


def test_autodeserialized_vllm_model_matches_original() -> None:
    model_id, host_port = "zephyr-7b-beta", "LLAMA_API_ENDPOINT"
    llm_assistant_model = VllmModel(
        host_port=host_port,
        model_id=model_id,
        generation_config=LlmGenerationConfig(
            max_tokens=1234,
        ),
        __metadata_info__={"llm_ui_name": "ZEPHYR"},
    )
    new_llm_assistant_model = autodeserialize(serialize(llm_assistant_model))
    _check_deserialized_vllm_model_validity(llm_assistant_model, new_llm_assistant_model)


def test_deserialized_ocigenai_model_matches_original_deprecated() -> None:
    model_id = COHERE_OCI_API_KEY_CONFIG["model_id"]
    service_endpoint = COHERE_OCI_API_KEY_CONFIG["client_config"]["service_endpoint"]
    compartment_id = COHERE_OCI_API_KEY_CONFIG["client_config"]["compartment_id"]
    auth_type = COHERE_OCI_API_KEY_CONFIG["client_config"]["auth_type"]

    # passing individual parameters directly to OCIGenAIModel is deprecated
    # should use client_config instead
    with pytest.warns(DeprecationWarning):
        llm_assistant_model = OCIGenAIModel(
            model_id=model_id,
            service_endpoint=service_endpoint,
            compartment_id=compartment_id,
            auth_type=auth_type,
            generation_config=LlmGenerationConfig(
                max_tokens=4321,
            ),
        )

    new_llm_assistant_model = deserialize(LlmModel, serialize(llm_assistant_model))
    assert isinstance(new_llm_assistant_model, OCIGenAIModel)
    assert new_llm_assistant_model.model_id == model_id
    assert new_llm_assistant_model.client_config.service_endpoint == service_endpoint
    assert new_llm_assistant_model.compartment_id == compartment_id
    assert new_llm_assistant_model.client_config.auth_type.name == auth_type
    assert new_llm_assistant_model.generation_config.max_tokens == 4321
    assert new_llm_assistant_model.serving_mode == ServingMode.ON_DEMAND


def test_deserialized_ocigenai_model_matches_original() -> None:
    client_config = OCIClientConfigWithApiKey(
        service_endpoint=COHERE_OCI_API_KEY_CONFIG["client_config"]["service_endpoint"],
        compartment_id=COHERE_OCI_API_KEY_CONFIG["client_config"]["compartment_id"],
    )
    llm_assistant_model = OCIGenAIModel(
        model_id=COHERE_OCI_API_KEY_CONFIG["model_id"],
        client_config=client_config,
        generation_config=LlmGenerationConfig(
            max_tokens=4321,
        ),
        serving_mode=ServingMode.DEDICATED,
        provider=ModelProvider.META,
    )
    serialized_model = serialize(llm_assistant_model)
    new_llm_assistant_model = deserialize(LlmModel, serialized_model)
    assert isinstance(new_llm_assistant_model, OCIGenAIModel)
    assert new_llm_assistant_model.model_id == COHERE_OCI_API_KEY_CONFIG["model_id"]
    assert new_llm_assistant_model.client_config == client_config
    assert new_llm_assistant_model.generation_config.max_tokens == 4321
    assert new_llm_assistant_model.serving_mode == ServingMode.DEDICATED


def test_oci_user_authentication_does_not_accept_dict():
    error_string = "'user_config' must be an OCIUserAuthenticationConfig object."
    with pytest.raises(TypeError, match=error_string):
        OCIClientConfigWithUserAuthentication(
            service_endpoint=COHERE_OCI_API_KEY_CONFIG["client_config"]["service_endpoint"],
            compartment_id=COHERE_OCI_API_KEY_CONFIG["client_config"]["compartment_id"],
            user_config=DUMMY_OCI_USER_CONFIG_DICT,  # dictionary object
        )


def test_oci_user_authentication_does_not_deserialize():
    ocigenai_model_config_using_user_auth = {
        "model_type": "ocigenai",
        "model_id": COHERE_OCI_API_KEY_CONFIG["model_id"],
        "client_config": {
            "auth_type": "API_KEY",
            "service_endpoint": COHERE_OCI_API_KEY_CONFIG["client_config"]["service_endpoint"],
            "compartment_id": COHERE_OCI_API_KEY_CONFIG["client_config"]["compartment_id"],
            "user_config": DUMMY_OCI_USER_CONFIG_DICT,  # dictionary object
        },
    }

    error_string = (
        "OCIUserAuthenticationConfig is a security sensitive configuration object, "
        "and cannot be deserialized."
    )
    with pytest.raises(ValueError, match=error_string):
        llm = LlmModelFactory.from_config(ocigenai_model_config_using_user_auth)


@patch("wayflowcore.models.ocigenaimodel.OCIGenAIModel._init_client")
def test_ocigenai_model_with_user_authentication_serialize_to_empty_dict(
    patched_langchain_chat_model: MagicMock, dummy_oci_client_config_with_user_authentication
) -> None:
    llm_assistant_model = OCIGenAIModel(
        model_id=COHERE_OCI_API_KEY_CONFIG["model_id"],
        client_config=dummy_oci_client_config_with_user_authentication,
        generation_config=LlmGenerationConfig(
            max_tokens=4321,
        ),
    )

    with pytest.warns(
        SecurityWarning,
        match="OCIUserAuthenticationConfig is a security sensitive configuration object, and cannot be serialized.",
    ):
        serialized_model = serialize(llm_assistant_model)
        assert "user_config: {}" in serialized_model


def assert_llms_are_equal(llm_1: LlmModel, ref_llm: OpenAICompatibleModel) -> None:
    assert isinstance(llm_1, OpenAICompatibleModel)
    assert llm_1.model_id == ref_llm.model_id
    assert llm_1.base_url == ref_llm.base_url
    assert llm_1.proxy == ref_llm.proxy
    assert llm_1.generation_config == ref_llm.generation_config
    assert llm_1.id == ref_llm.id


def test_openai_compatible_llm_serde():
    llm = OpenAICompatibleModel(model_id="some_model", base_url="some_url", proxy="some_proxy")
    serialized_llm = serialize(llm)
    deserialized_llm = deserialize(LlmModel, serialized_llm)
    assert_llms_are_equal(deserialized_llm, llm)
    deserialized_llm_with_factory = LlmModelFactory.from_config(serialize_to_dict(llm))
    assert_llms_are_equal(deserialized_llm_with_factory, llm)
