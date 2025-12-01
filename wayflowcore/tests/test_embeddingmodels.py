# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import os
import random
from unittest.mock import MagicMock, patch

import pytest
import yaml

from wayflowcore.embeddingmodels.ocigenaimodel import OCIGenAIEmbeddingModel
from wayflowcore.embeddingmodels.ollamamodel import OllamaEmbeddingModel
from wayflowcore.embeddingmodels.openaicompatiblemodel import _add_leading_http_if_needed
from wayflowcore.embeddingmodels.openaimodel import OpenAIEmbeddingModel
from wayflowcore.embeddingmodels.vllmmodel import VllmEmbeddingModel
from wayflowcore.serialization.serializer import autodeserialize, serialize, serialize_to_dict

from .conftest import e5large_api_url, ollama_embedding_api_url


@pytest.fixture
def vllm_endpoint():
    """Endpoint for a hosted VllmEmbeddingModel."""
    return "E5LARGEV2_API_ENDPOINT"


@pytest.fixture
def ollama_endpoint():
    """Endpoint for a hosted OllamaEmbeddingModel."""
    return "OLLAMA_EMBEDDING_API_URL"


class MockResponse:
    """Mock response object that mimics requests.Response.
    Used to test embedding models such as the OpenAIEmbeddingModel.
    """

    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
        self.text = str(json_data)

    def json(self):
        return self.json_data


@pytest.fixture
def mock_openai_compatible_api(request):
    """
    Fixture to mock OpenAI API calls with successful responses.
    """
    # Apply mocking for normal tests
    with patch("httpx.AsyncClient.post") as mock_post:

        async def create_successful_response(*args, **kwargs):
            payload = kwargs.get("json", {})
            input_texts = payload.get("input", [])
            if isinstance(input_texts, str):
                input_texts = [input_texts]

            embedding_dim = 1536  # Standard for OpenAI embeddings
            embeddings_data = []

            for i in range(len(input_texts)):
                fake_embedding = [random.uniform(-1, 1) for _ in range(embedding_dim)]
                embeddings_data.append({"embedding": fake_embedding, "index": i})

            # Mock response
            mock_data = {
                "object": "list",
                "data": embeddings_data,
                "model": payload.get("model", "text-embedding-3-small"),
                "usage": {
                    "prompt_tokens": len("".join(input_texts)),
                    "total_tokens": len("".join(input_texts)),
                },
            }

            return MockResponse(mock_data)

        mock_post.side_effect = create_successful_response
        yield mock_post


@pytest.fixture
def mock_oci_modules(monkeypatch):
    """Mock the OCI modules needed for OCIGenAIEmbeddingModel."""

    # Create a mock client that returns proper embeddings
    class MockEmbeddingResponse:
        def __init__(self, inputs):
            self.data = type(
                "obj",
                (object,),
                {
                    "embeddings": [
                        [random.uniform(-1, 1) for _ in range(768)]  # 768-dim embeddings
                        for _ in range(len(inputs))
                    ]
                },
            )

    # Create a mock client class
    class MockGenAIClient:
        def __init__(self, *args, **kwargs):
            self.base_client = type(
                "obj",
                (object,),
                {"endpoint": kwargs.get("service_endpoint", "https://mock-endpoint")},
            )

        def embed_text(self, embed_text_details):
            # Return mock embeddings based on the input
            return MockEmbeddingResponse(embed_text_details.inputs)

    # Create mock for EmbedTextDetails
    class MockEmbedTextDetails:
        def __init__(self, inputs, compartment_id, serving_mode):
            self.inputs = inputs
            self.compartment_id = compartment_id
            self.serving_mode = serving_mode

    # Create mock for OnDemandServingMode
    class MockOnDemandServingMode:
        def __init__(self, model_id):
            self.model_id = model_id

    # Apply all the patches
    monkeypatch.setattr("oci.generative_ai_inference.GenerativeAiInferenceClient", MockGenAIClient)
    monkeypatch.setattr("oci.generative_ai_inference.models.EmbedTextDetails", MockEmbedTextDetails)
    monkeypatch.setattr(
        "oci.generative_ai_inference.models.OnDemandServingMode", MockOnDemandServingMode
    )

    # Mock oci.config.from_file to return a dict with the compartment_id
    monkeypatch.setattr(
        "oci.config.from_file", lambda *args, **kwargs: {"compartment_id": "test_compartment"}
    )

    # Mock oci.config.validate_config to do nothing
    monkeypatch.setattr("oci.config.validate_config", lambda *args, **kwargs: None)

    # Create a mock retry strategy
    mock_retry = MagicMock()
    monkeypatch.setattr("oci.retry.DEFAULT_RETRY_STRATEGY", mock_retry)

    # Mock instance principal signer if needed
    mock_instance_signer = MagicMock()
    monkeypatch.setattr(
        "oci.auth.signers.InstancePrincipalsSecurityTokenSigner", lambda: mock_instance_signer
    )

    return {
        "client_class": MockGenAIClient,
        "embed_text_details_class": MockEmbedTextDetails,
        "on_demand_mode_class": MockOnDemandServingMode,
    }


@pytest.fixture
def oci_client_config():
    """Create an OCIClientConfigWithApiKey instance for testing."""
    # Import here to avoid issues if OCI is not installed
    from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey

    return OCIClientConfigWithApiKey(
        service_endpoint="https://inference.generativeai.us-phoenix-1.oci.oraclecloud.com",
    )


def create_oci_embedding_model(request, model_id):
    """Factory function to create OCIGenAIEmbeddingModel instances."""
    config = request.getfixturevalue("oci_client_config")
    return OCIGenAIEmbeddingModel(
        model_id=model_id, config=config, compartment_id="test_compartment"
    )


@pytest.mark.parametrize(
    "model_cls, constructor_kwargs",
    [
        (
            OpenAIEmbeddingModel,
            {"model_id": "text-embedding-3-small", "api_key": "fake-api-key"},
        ),
    ],
)
def test_embedding_model_single_embed_openai(
    request,
    model_cls,
    constructor_kwargs,
    mock_openai_compatible_api,
):
    """Test type and shape of a generated embedding of a single sample for OpenAIEmbeddingModel (mocked)"""
    updated_kwargs = constructor_kwargs.copy()
    for key, value in constructor_kwargs.items():
        if isinstance(value, str) and value in request.fixturenames:
            updated_kwargs[key] = request.getfixturevalue(value)
    embedding_model = model_cls(**updated_kwargs)

    embedding = embedding_model.embed(["hello world"])

    assert isinstance(embedding, list)
    assert all(isinstance(sublist, list) for sublist in embedding)
    assert all(all(isinstance(item, float) for item in sublist) for sublist in embedding)
    assert len(embedding) == 1


@pytest.mark.parametrize(
    "model_cls, constructor_kwargs",
    [
        (
            VllmEmbeddingModel,
            {"base_url": e5large_api_url, "model_id": "intfloat/e5-large-v2"},
        ),
        (
            OllamaEmbeddingModel,
            {"base_url": ollama_embedding_api_url, "model_id": "nomic-embed-text"},
        ),
    ],
)
def test_embedding_model_single_embed_vllm_ollama(
    request,
    model_cls,
    constructor_kwargs,
):
    """Test type and shape of a generated embedding of a single sample for VllmEmbeddingModel and OllamaEmbeddingModel (NOT mocked)"""
    updated_kwargs = constructor_kwargs.copy()
    for key, value in constructor_kwargs.items():
        if isinstance(value, str) and value in request.fixturenames:
            updated_kwargs[key] = request.getfixturevalue(value)
    embedding_model = model_cls(**updated_kwargs)

    embedding = embedding_model.embed(["hello world"])

    assert isinstance(embedding, list)
    assert all(isinstance(sublist, list) for sublist in embedding)
    assert all(all(isinstance(item, float) for item in sublist) for sublist in embedding)
    assert len(embedding) == 1


def test_embedding_model_single_embed_oci(
    request,
    mock_oci_modules,
):
    """Test type and shape of a generated embedding for OCI model"""
    model_id = "cohere.embed-english-light-v3.0"
    embedding_model = create_oci_embedding_model(request, model_id)

    embedding = embedding_model.embed(["hello world"])

    assert isinstance(embedding, list)
    assert all(isinstance(sublist, list) for sublist in embedding)
    assert all(all(isinstance(item, float) for item in sublist) for sublist in embedding)
    assert len(embedding) == 1


@pytest.mark.parametrize(
    "model_cls, constructor_kwargs",
    [
        (
            OpenAIEmbeddingModel,
            {"model_id": "text-embedding-3-small", "api_key": "fake-api-key"},
        ),
    ],
)
def test_embedding_model_multiple_embeds_openai(
    request,
    model_cls,
    constructor_kwargs,
    mock_openai_compatible_api,
):
    """Test type and shape of generated embeddings for a random number of samples (2-10) for OpenAIEmbeddingModel (mocked)"""
    updated_kwargs = constructor_kwargs.copy()
    for key, value in constructor_kwargs.items():
        if isinstance(value, str) and value in request.fixturenames:
            updated_kwargs[key] = request.getfixturevalue(value)
    embedding_model = model_cls(**updated_kwargs)

    num_samples = random.randint(2, 10)
    sample_texts = [f"sample text {i}" for i in range(num_samples)]
    embeddings = embedding_model.embed(sample_texts)

    assert isinstance(embeddings, list)
    assert all(isinstance(embedding, list) for embedding in embeddings)
    assert all(all(isinstance(value, float) for value in embedding) for embedding in embeddings)
    assert len(embeddings) == num_samples

    embedding_dim = len(embeddings[0])
    assert all(len(embedding) == embedding_dim for embedding in embeddings)


@pytest.mark.parametrize(
    "model_cls, constructor_kwargs",
    [
        (
            VllmEmbeddingModel,
            {"base_url": e5large_api_url, "model_id": "intfloat/e5-large-v2"},
        ),
        (
            OllamaEmbeddingModel,
            {"base_url": ollama_embedding_api_url, "model_id": "nomic-embed-text"},
        ),
    ],
)
def test_embedding_model_multiple_embeds_vllm_ollama(
    request,
    model_cls,
    constructor_kwargs,
):
    """Test type and shape of generated embeddings for a random number of samples (2-10) for VllmEmbeddingModel and OllamaEmbeddingModel (NOT mocked)"""
    updated_kwargs = constructor_kwargs.copy()
    for key, value in constructor_kwargs.items():
        if isinstance(value, str) and value in request.fixturenames:
            updated_kwargs[key] = request.getfixturevalue(value)
    embedding_model = model_cls(**updated_kwargs)

    num_samples = random.randint(2, 10)
    sample_texts = [f"sample text {i}" for i in range(num_samples)]
    embeddings = embedding_model.embed(sample_texts)

    assert isinstance(embeddings, list)
    assert all(isinstance(embedding, list) for embedding in embeddings)
    assert all(all(isinstance(value, float) for value in embedding) for embedding in embeddings)
    assert len(embeddings) == num_samples

    embedding_dim = len(embeddings[0])
    assert all(len(embedding) == embedding_dim for embedding in embeddings)


def test_embedding_model_multiple_embeds_oci(
    request,
    mock_oci_modules,
):
    """Test type and shape of generated embeddings for a random number of samples (2-10) for OCI model"""
    model_id = "cohere.embed-english-light-v3.0"
    embedding_model = create_oci_embedding_model(request, model_id)

    num_samples = random.randint(2, 10)
    sample_texts = [f"sample text {i}" for i in range(num_samples)]
    embeddings = embedding_model.embed(sample_texts)

    assert isinstance(embeddings, list)
    assert all(isinstance(embedding, list) for embedding in embeddings)
    assert all(all(isinstance(value, float) for value in embedding) for embedding in embeddings)
    assert len(embeddings) == num_samples

    embedding_dim = len(embeddings[0])
    assert all(len(embedding) == embedding_dim for embedding in embeddings)


def test_missing_open_api_key():
    """Test behavior when no API key is provided and not available in environment"""
    try:
        original_api_key = os.environ.get("OPENAI_API_KEY")
        # Just in case the key is set on linux
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        with pytest.raises(ValueError) as e:
            model = OpenAIEmbeddingModel(model_id="text-embedding-3-small")

        error_message = str(e.value).lower()
        assert (
            "api key" in error_message
        ), f"Expected error about missing API key, but got: {error_message}"
    finally:
        # Restore the original API key if it existed
        if original_api_key is not None:
            os.environ["OPENAI_API_KEY"] = original_api_key


def test_invalid_open_api_key():
    """Test behavior when an invalid API key is provided"""

    try:
        original_api_key = os.environ.get("OPENAI_API_KEY")
        # Just in case the key is set on linux
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

        invalid_api_key = "invalid_key_12345"
        os.environ["OPENAI_API_KEY"] = invalid_api_key

        model = OpenAIEmbeddingModel(model_id="text-embedding-3-small")
        with pytest.raises(Exception) as e:
            model.embed(["WayFlow is a framework to develop and run LLM-based assistants."])

        error_message = str(e.value).lower()
        assert "401" in error_message, f"Expected 401 error, but got: {error_message}"

    finally:
        # Restore the original API key if it existed
        if original_api_key is not None:
            os.environ["OPENAI_API_KEY"] = original_api_key
        else:
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]


@pytest.mark.parametrize(
    "model_cls, constructor_kwargs",
    [
        (
            VllmEmbeddingModel,
            {"base_url": e5large_api_url, "model_id": "intfloat/e5-large-v2"},
        ),
        (
            OllamaEmbeddingModel,
            {"base_url": ollama_embedding_api_url, "model_id": "nomic-embed-text"},
        ),
        (
            OpenAIEmbeddingModel,
            {"model_id": "text-embedding-3-small", "api_key": "fake-api-key"},
        ),
    ],
)
def test_base_embedding_model_serialization(request, model_cls, constructor_kwargs):
    """Test serialization and deserialization of standard embedding models."""
    updated_kwargs = constructor_kwargs.copy()
    for key, value in constructor_kwargs.items():
        if isinstance(value, str) and value in request.fixturenames:
            updated_kwargs[key] = request.getfixturevalue(value)
    original_model = model_cls(**updated_kwargs)

    # Test serialization
    serialized_dict = serialize_to_dict(original_model)

    assert serialized_dict["_component_type"] == model_cls.__name__
    assert serialized_dict["model_id"] == constructor_kwargs["model_id"]

    # API key should never be serialized
    if "api_key" in constructor_kwargs:
        assert "api_key" not in serialized_dict

    # URL-specific assertions
    if model_cls in [VllmEmbeddingModel, OllamaEmbeddingModel]:
        assert "base_url" in serialized_dict
        assert serialized_dict["base_url"] == _add_leading_http_if_needed(
            constructor_kwargs["base_url"]
        )

    # Test YAML serialization
    yaml_str = serialize(original_model)
    assert f"model_id: {constructor_kwargs['model_id']}" in yaml_str

    # Test deserialization
    deserialized_model = autodeserialize(yaml_str)
    assert isinstance(deserialized_model, model_cls)
    assert deserialized_model._model_id == constructor_kwargs["model_id"]

    # Check base_url based on model type
    assert deserialized_model._base_url == (
        "https://api.openai.com"
        if model_cls == OpenAIEmbeddingModel
        else _add_leading_http_if_needed(constructor_kwargs["base_url"])
    )

    assert deserialized_model.id == original_model.id
    assert deserialized_model.name == original_model.name
    assert deserialized_model.description == original_model.description


def test_ocigenai_embedding_model_serialization(request, mock_oci_modules):
    """Test serialization and deserialization of OCI GenAI embedding models."""
    model_id = "cohere.embed-english-light-v3.0"

    # Create the OCI model using the factory function
    original_model = create_oci_embedding_model(request, model_id)

    # Test serialization
    serialized_dict = serialize_to_dict(original_model)

    assert serialized_dict["_component_type"] == "OCIGenAIEmbeddingModel"
    assert serialized_dict["model_id"] == model_id
    assert "service_endpoint" in serialized_dict
    assert "compartment_id" in serialized_dict

    # Test YAML serialization
    yaml_str = serialize(original_model)
    assert f"model_id: {model_id}" in yaml_str

    # Note: We skip deserialization for OCI as mentioned in the original test
    # as it requires special handling


@pytest.mark.parametrize(
    "model_cls, constructor_kwargs",
    [
        (
            VllmEmbeddingModel,
            {"base_url": e5large_api_url, "model_id": "intfloat/e5-large-v2"},
        ),
        (
            OllamaEmbeddingModel,
            {"base_url": ollama_embedding_api_url, "model_id": "nomic-embed-text"},
        ),
        (
            OpenAIEmbeddingModel,
            {"model_id": "text-embedding-3-small", "api_key": "fake-api-key"},
        ),
    ],
)
def test_embedding_model_file_serialization(request, model_cls, constructor_kwargs, tmp_path):
    """Test serialization to file and deserialization from file"""
    updated_kwargs = constructor_kwargs.copy()
    for key, value in constructor_kwargs.items():
        if isinstance(value, str) and value in request.fixturenames:
            updated_kwargs[key] = request.getfixturevalue(value)
    original_model = model_cls(**updated_kwargs)

    yaml_str = serialize(original_model)

    # Create temporary file path (leveraging pytest's tmp_path fixture)
    test_file = tmp_path / f"test_{model_cls.__name__.lower()}.yaml"

    with open(test_file, "w") as f:
        f.write(yaml_str)

    with open(test_file, "r") as f:
        loaded_yaml = f.read()

    deserialized_model = autodeserialize(loaded_yaml)
    assert isinstance(deserialized_model, model_cls)
    assert deserialized_model._model_id == constructor_kwargs["model_id"]

    # Check base_url based on model type
    if model_cls == OpenAIEmbeddingModel:
        assert deserialized_model._base_url == "https://api.openai.com"
    elif model_cls in [VllmEmbeddingModel, OllamaEmbeddingModel]:
        assert deserialized_model._base_url == _add_leading_http_if_needed(
            constructor_kwargs["base_url"]
        )


def test_embedding_model_file_serialization_oci(request, tmp_path, mock_oci_modules):
    """Test serialization to file for OCI model."""
    model_id = "cohere.embed-english-light-v3.0"
    original_model = create_oci_embedding_model(request, model_id)

    yaml_str = serialize(original_model)

    # Create temporary file path
    test_file = tmp_path / "test_ocigenaiembeddingmodel.yaml"

    with open(test_file, "w") as f:
        f.write(yaml_str)

    with open(test_file, "r") as f:
        loaded_yaml = f.read()

    # Verify the serialized content for OCIGenAIEmbeddingModel
    loaded_dict = yaml.safe_load(loaded_yaml)
    assert loaded_dict["_component_type"] == "OCIGenAIEmbeddingModel"
    assert loaded_dict["model_id"] == model_id
    assert "service_endpoint" in loaded_dict
    assert "compartment_id" in loaded_dict


@pytest.mark.parametrize(
    "model_cls, constructor_kwargs, missing_field",
    [
        (VllmEmbeddingModel, {"base_url": e5large_api_url}, "model_id"),
        (VllmEmbeddingModel, {"model_id": "intfloat/e5-large-v2"}, "base_url"),
        (OllamaEmbeddingModel, {"base_url": ollama_embedding_api_url}, "model_id"),
        (OllamaEmbeddingModel, {"model_id": "nomic-embed-text"}, "base_url"),
        (OpenAIEmbeddingModel, {}, "model_id"),
        (OCIGenAIEmbeddingModel, {"model_id": "cohere.embed-english-light-v3.0"}, "config"),
        (OCIGenAIEmbeddingModel, {}, "model_id"),
    ],
)
def test_embedding_model_missing_fields(request, model_cls, constructor_kwargs, missing_field):
    """Test error handling when deserializing with missing required fields."""
    updated_kwargs = constructor_kwargs.copy()
    # Replace fixture references with actual fixture values
    for key, value in constructor_kwargs.items():
        if isinstance(value, str) and value in request.fixturenames:
            updated_kwargs[key] = request.getfixturevalue(value)

    serialized_dict = {"_component_type": model_cls.__name__, **updated_kwargs}

    # Convert to YAML string for autodeserialize
    serialized_yaml = yaml.dump(serialized_dict)

    with pytest.raises(ValueError) as excinfo:
        autodeserialize(serialized_yaml)

    assert "Missing required field" in str(excinfo.value) or missing_field in str(excinfo.value)


def test_oci_genai_embedding_model_different_config_types(request, mock_oci_modules):
    """Test OCIGenAIEmbeddingModel with different config types."""
    from wayflowcore.embeddingmodels.ocigenaimodel import OCIGenAIEmbeddingModel
    from wayflowcore.models.ociclientconfig import (
        OCIClientConfigWithApiKey,
        OCIClientConfigWithInstancePrincipal,
    )

    # Test with ApiKey config
    api_key_config = OCIClientConfigWithApiKey(
        service_endpoint="https://inference.generativeai.us-phoenix-1.oci.oraclecloud.com",
    )

    api_key_model = OCIGenAIEmbeddingModel(
        model_id="cohere.embed-english-light-v3.0",
        config=api_key_config,
        compartment_id="test_compartment",
    )

    # Test with InstancePrincipal config
    instance_principal_config = OCIClientConfigWithInstancePrincipal(
        service_endpoint="https://inference.generativeai.us-phoenix-1.oci.oraclecloud.com",
    )

    instance_principal_model = OCIGenAIEmbeddingModel(
        model_id="cohere.embed-english-light-v3.0",
        config=instance_principal_config,
        compartment_id="test_compartment",
    )

    # Test serialization with different configs
    from wayflowcore.serialization.serializer import serialize_to_dict

    api_key_serialized = serialize_to_dict(api_key_model)
    instance_principal_serialized = serialize_to_dict(instance_principal_model)

    assert "config_type" in api_key_serialized
    assert "config_type" in instance_principal_serialized

    assert api_key_serialized["model_id"] == "cohere.embed-english-light-v3.0"
    assert instance_principal_serialized["model_id"] == "cohere.embed-english-light-v3.0"

    assert (
        api_key_serialized["service_endpoint"]
        == "https://inference.generativeai.us-phoenix-1.oci.oraclecloud.com"
    )
    assert (
        instance_principal_serialized["service_endpoint"]
        == "https://inference.generativeai.us-phoenix-1.oci.oraclecloud.com"
    )


def remove_leading_http(url: str) -> str:
    if url.startswith("http://"):
        url = url.replace("http://", "", 1)
    elif url.startswith("https://"):
        url = url.replace("https://", "", 1)

    return url


@pytest.mark.parametrize(
    "model_cls, url, model_id",
    [
        (
            VllmEmbeddingModel,
            e5large_api_url,
            "intfloat/e5-large-v2",
        ),
        (
            OllamaEmbeddingModel,
            ollama_embedding_api_url,
            "nomic-embed-text",
        ),
    ],
)
def test_embedding_model_works_without_http(request, model_cls, url, model_id):
    """Test serialization and deserialization of standard embedding models."""

    url = remove_leading_http(url)
    embedding_model = model_cls(base_url=url, model_id=model_id)
    embedding = embedding_model.embed(["hello world"])

    assert isinstance(embedding, list)
    assert all(isinstance(sublist, list) for sublist in embedding)
    assert all(all(isinstance(item, float) for item in sublist) for sublist in embedding)
    assert len(embedding) == 1
