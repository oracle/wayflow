# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors

"""
# .. oci-embedding-start
from wayflowcore.embeddingmodels import OCIGenAIEmbeddingModel
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey

if __name__ == "__main__":

    # Get the list of available embedding models from OCI documentation
    OCIGENAI_MODEL_ID = "cohere.embed-english-light-v3.0"
    # e.g. <oci region> can be "us-phoenix-1" and can also be found in your ~/.oci/config file
    OCIGENAI_ENDPOINT = "https://path.to.your.ocigenai.endpoint.com"
    # <compartment_id> can be obtained from your personal OCI account (not the key config file).
    # Please find it under "Identity > Compartments" on the OCI console website after logging in to your user account.
    COMPARTMENT_ID = "ocid1.compartment.oc1..example"

    oci_embedding_model = OCIGenAIEmbeddingModel(
        model_id=OCIGENAI_MODEL_ID,
        config=OCIClientConfigWithApiKey(
            service_endpoint=OCIGENAI_ENDPOINT,
            compartment_id=COMPARTMENT_ID,
        ),
    )

    # Generate embeddings
    text_list = [
        "WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants.",
    ]
    # embeddings = oci_embedding_model.embed(text_list)
    # print(f"OCI GenAI embeddings dimension: {len(embeddings[0])}")
# .. oci-embedding-end
"""

"""
# .. openai-embedding-start
from wayflowcore.embeddingmodels import OpenAIEmbeddingModel

if __name__ == "__main__":

    # For the sake of this example, we set the API key in the environment
    # In production, use a secure method to store and access the key
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "DUMMY_OPENAI_KEY")

    OPENAI_MODEL_ID = "text-embedding-3-small"

    openai_embedding_model = OpenAIEmbeddingModel(
        model_id=OPENAI_MODEL_ID,
    )

    # Generate embeddings
    text_list = [
        "WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants.",
    ]
    # embeddings = openai_embedding_model.embed(text_list)
    # print(f"OpenAI embeddings dimension: {len(embeddings[0])}")
# .. openai-embedding-end
"""
"""
# .. vllm-embedding-start
from wayflowcore.embeddingmodels import VllmEmbeddingModel

if __name__ == "__main__":

    VLLM_MODEL_ID = "mistralai/mistral-embed"
    VLLM_BASE_URL = "http://your.ip:port"

    vllm_embedding_model = VllmEmbeddingModel(
        base_url=VLLM_BASE_URL,
        model_id=VLLM_MODEL_ID,
    )

    # Generate embeddings
    text_list = [
        "WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants.",
    ]
    # embeddings = vllm_embedding_model.embed(text_list)
    # print(f"vLLM embeddings dimension: {len(embeddings[0])}")
# .. vllm-embedding-end
"""
"""
# .. ollama-embedding-start
from wayflowcore.embeddingmodels import OllamaEmbeddingModel

if __name__ == "__main__":

    OLLAMA_MODEL_ID = "nomic-embed-text"
    OLLAMA_BASE_URL = "http://your.ip:port"

    ollama_embedding_model = OllamaEmbeddingModel(
        base_url=OLLAMA_BASE_URL,
        model_id=OLLAMA_MODEL_ID,
    )

    # Generate embeddings
    text_list = [
        "WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants.",
    ]
    # embeddings = ollama_embedding_model.embed(text_list)
    # print(f"Ollama embeddings dimension: {len(embeddings[0])}")
# .. ollama-embedding-end
"""
"""
# .. recap:
from wayflowcore.embeddingmodels import (
    OCIGenAIEmbeddingModel,
    OllamaEmbeddingModel,
    OpenAIEmbeddingModel,
    VllmEmbeddingModel,
)
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey

if __name__ == "__main__":
    text_list = [
        "WayFlow is a powerful, intuitive Python library for building sophisticated AI-powered assistants.",
    ]

    # OCI GenAI Embedding Model
    OCIGENAI_MODEL_ID = "cohere.embed-english-light-v3.0"
    OCIGENAI_ENDPOINT = "https://path.to.your.ocigenai.endpoint.com"
    COMPARTMENT_ID = "ocid1.compartment.oc1..example"

    oci_embedding_model = OCIGenAIEmbeddingModel(
        model_id=OCIGENAI_MODEL_ID,
        config=OCIClientConfigWithApiKey(
            service_endpoint=OCIGENAI_ENDPOINT,
            compartment_id=COMPARTMENT_ID,
        ),
    )

    # oci_embeddings = oci_embedding_model.embed(text_list)
    # print(f"OCI GenAI embeddings dimension: {len(oci_embeddings[0])}")

    # OpenAI Embedding Model
    OPENAI_MODEL_ID = "text-embedding-3-small"

    openai_embedding_model = OpenAIEmbeddingModel(
        model_id=OPENAI_MODEL_ID,
    )

    # openai_embeddings = openai_embedding_model.embed(text_list)
    # print(f"OpenAI embeddings dimension: {len(openai_embeddings[0])}")

    # vLLM Embedding Model
    VLLM_MODEL_ID = "mistralai/mistral-embed"
    VLLM_BASE_URL = "http://your.ip:port"

    vllm_embedding_model = VllmEmbeddingModel(
        base_url=VLLM_BASE_URL,
        model_id=VLLM_MODEL_ID,
    )

    # vllm_embeddings = vllm_embedding_model.embed(text_list)
    # print(f"vLLM embeddings dimension: {len(vllm_embeddings[0])}")

    # Ollama Embedding Model
    OLLAMA_MODEL_ID = "nomic-embed-text"
    OLLAMA_BASE_URL = "http://your.ip:port"

    ollama_embedding_model = OllamaEmbeddingModel(
        base_url=OLLAMA_BASE_URL,
        model_id=OLLAMA_MODEL_ID,
    )

    # ollama_embeddings = ollama_embedding_model.embed(text_list)
    # print(f"Ollama embeddings dimension: {len(ollama_embeddings[0])}")
# .. end-recap
"""
