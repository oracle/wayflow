# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import Any, Mapping

import pytest
from pyagentspec.llms.ocigenaiconfig import ModelProvider, ServingMode

from wayflowcore import Agent
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.models import (
    LlmGenerationConfig,
    OCIGenAIModel,
    OllamaModel,
    OpenAICompatibleModel,
    OpenAIModel,
    VllmModel,
)
from wayflowcore.models.ociclientconfig import (
    OCIClientConfigWithApiKey,
    OCIClientConfigWithInstancePrincipal,
    OCIClientConfigWithResourcePrincipal,
    OCIClientConfigWithSecurityToken,
)


def _deserialize_agent(
    serialized_agent: str,
    components_registry: Mapping[str, Any] | None = None,
) -> Agent:
    deserialized_component = AgentSpecLoader().load_json(
        serialized_agent,
        components_registry=components_registry,
    )
    assert isinstance(deserialized_component, Agent)
    return deserialized_component


@pytest.mark.parametrize(
    "llm_model",
    [
        VllmModel(model_id="my.model-id", host_port="my.url"),
        OllamaModel(model_id="my.model-id", host_port="my.url"),
        OpenAICompatibleModel(model_id="my.model-id", base_url="my.url"),
        OpenAIModel(model_id="my.model-id", api_key="something"),
        OCIGenAIModel(
            model_id="my.model-id",
            compartment_id="cid",
            client_config=OCIClientConfigWithApiKey(
                service_endpoint="http://sid.url", auth_profile="NOTDEFAULT"
            ),
        ),
        OCIGenAIModel(
            model_id="my.model-id2",
            compartment_id="cid2",
            client_config=OCIClientConfigWithSecurityToken(
                service_endpoint="http://sid.url", auth_profile="NOTDEFAULT"
            ),
        ),
        OCIGenAIModel(
            model_id="my.model-id3",
            compartment_id="cid3",
            client_config=OCIClientConfigWithResourcePrincipal(service_endpoint="http://sid.url"),
        ),
        OCIGenAIModel(
            model_id="my.model-id4",
            compartment_id="cid4",
            client_config=OCIClientConfigWithInstancePrincipal(service_endpoint="http://sid.url"),
        ),
        OCIGenAIModel(
            model_id="my.model-id4",
            compartment_id="cid4",
            provider=ModelProvider.GROK,
            serving_mode=ServingMode.DEDICATED,
            client_config=OCIClientConfigWithInstancePrincipal(service_endpoint="http://sid.url"),
        ),
    ],
)
def test_llm_model_serde_works_and_is_equal(llm_model) -> None:
    agent = Agent(llm=llm_model, custom_instruction="Be nice.")
    deserialized_agent = _deserialize_agent(
        AgentSpecExporter().to_json(agent),
        components_registry={f"{llm_model.id}.api_key": "something"},
    )
    deserialized_llm_model = deserialized_agent.llm
    assert type(deserialized_llm_model) is type(llm_model)
    for param_name in [
        "model_id",
        "host_port",
        "base_url",
        "compartment_id",
        "client_config",
        "provider",
        "serving_mode",
    ]:
        if hasattr(llm_model, param_name):
            assert getattr(llm_model, param_name) == getattr(deserialized_llm_model, param_name)


@pytest.mark.parametrize(
    "llm_generation_config",
    [
        LlmGenerationConfig(),
        LlmGenerationConfig(top_p=0.3, max_tokens=45, stop=["end", "exit"]),
        LlmGenerationConfig(top_p=0.9, extra_args={"seed": 1}),
    ],
)
def test_llm_generation_config_serde_works_and_is_equal(llm_generation_config) -> None:
    llm_model = VllmModel(
        model_id="my.model-id", host_port="http://my.url", generation_config=llm_generation_config
    )
    agent = Agent(llm=llm_model, custom_instruction="Be nice.")
    deserialized_agent = _deserialize_agent(AgentSpecExporter().to_json(agent))
    deserialized_llm_generation_config = deserialized_agent.llm.generation_config
    assert llm_generation_config == deserialized_llm_generation_config


@pytest.mark.parametrize("llm_cls", [OpenAICompatibleModel, VllmModel, OllamaModel])
def test_llm_model_serde_restores_tls_sensitive_fields_from_components_registry(
    tls_material_factory, llm_cls
) -> None:
    tls_material = tls_material_factory("llm-serde")
    constructor_kwargs = dict(
        model_id="my.model-id",
        key_file=tls_material.client_key_path,
        cert_file=tls_material.client_cert_path,
        ca_file=tls_material.ca_cert_path,
    )
    if llm_cls is OpenAICompatibleModel:
        constructor_kwargs["base_url"] = "https://example.test"
    else:
        constructor_kwargs["host_port"] = "https://example.test"

    llm_model = llm_cls(**constructor_kwargs)
    agent = Agent(llm=llm_model, custom_instruction="Be nice.")
    components_registry = {
        f"{llm_model.id}.key_file": tls_material.client_key_path,
        f"{llm_model.id}.cert_file": tls_material.client_cert_path,
        f"{llm_model.id}.ca_file": tls_material.ca_cert_path,
    }

    deserialized_agent = _deserialize_agent(
        AgentSpecExporter().to_json(agent),
        components_registry=components_registry,
    )
    deserialized_llm_model = deserialized_agent.llm

    assert deserialized_llm_model.key_file == tls_material.client_key_path
    assert deserialized_llm_model.cert_file == tls_material.client_cert_path
    assert deserialized_llm_model.ca_file == tls_material.ca_cert_path
