# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from wayflowcore.embeddingmodels.openaicompatiblemodel import OpenAICompatibleEmbeddingModel
from wayflowcore.serialization.serializer import SerializableObject


class OllamaEmbeddingModel(OpenAICompatibleEmbeddingModel, SerializableObject):
    """
    Embedding model for self-hosted models via Ollama.

    Parameters
    ----------
    base_url
        The complete URL of the Ollama server (e.g., "http://localhost:11434" or "https://ollama.example.com").
        Both HTTP and HTTPS protocols are supported.
    model_id
        The name of the model to use on the Ollama server.

    Examples
    --------
    >>> from wayflowcore.embeddingmodels.ollamamodel import OllamaEmbeddingModel  # doctest: +SKIP
    >>> # Using HTTP
    >>> model = OllamaEmbeddingModel(url="http://localhost:11434", model_id="nomic-embed-text")  # doctest: +SKIP
    >>> # Using HTTPS
    >>> secure_model = OllamaEmbeddingModel(url="https://ollama.example.com", model_id="nomic-embed-text")  # doctest: +SKIP
    >>> embeddings = model.embed(["WayFlow is a framework to develop and run LLM-based assistants."])  # doctest: +SKIP

    Notes
    -----
    This provider makes HTTP/HTTPS POST requests to the /v1/embeddings endpoint of the specified URL.
    When using HTTPS, certificate verification is performed by default. For self-signed certificates,
    additional configuration may be needed at the application level.
    """
