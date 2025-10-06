# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from wayflowcore.embeddingmodels.openaicompatiblemodel import OpenAICompatibleEmbeddingModel
from wayflowcore.serialization.serializer import SerializableObject


class VllmEmbeddingModel(OpenAICompatibleEmbeddingModel, SerializableObject):
    """
    Embedding model for self-hosted models via vLLM.

    Parameters
    ----------
    base_url
        The complete URL of the vLLM server (e.g., "http://localhost:8000" or "https://secure-vllm.example.com").
        Both HTTP and HTTPS protocols are supported.
    model_id
        The name of the model to use on the server.

    Examples
    --------
    >>> from wayflowcore.embeddingmodels.vllmmodel import VllmEmbeddingModel  # doctest: +SKIP
    >>> # Using HTTP
    >>> model = VllmEmbeddingModel(url="http://localhost:8000", model_id="hosted-model-name")  # doctest: +SKIP
    >>> # Using HTTPS
    >>> secure_model = VllmEmbeddingModel(url="https://secure-vllm.example.com", model_id="hosted-model-name")  # doctest: +SKIP
    >>> embeddings = model.embed(["WayFlow is a framework to develop and run LLM-based assistants."])  # doctest: +SKIP

    Notes
    -----
    This provider makes HTTP/HTTPS POST requests to the /v1/embeddings endpoint of the specified URL.
    When using HTTPS, certificate verification is performed by default. For self-signed certificates,
    additional configuration may be needed at the application level.
    """
