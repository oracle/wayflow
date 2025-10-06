# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
from typing import Any, Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.async_helpers import run_async_in_sync
from wayflowcore.embeddingmodels.embeddingmodel import EmbeddingModel
from wayflowcore.models._requesthelpers import _RetryStrategy, request_post_with_retries
from wayflowcore.models.openaicompatiblemodel import _add_leading_http_if_needed
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject


class OpenAICompatibleEmbeddingModel(EmbeddingModel, SerializableObject):
    """
    Base class for OpenAI-compatible embedding models.

    Parameters
    ----------
    model_id
        The name of the model to use for generating embeddings.
    base_url
        The base URL for the embedding API. Both HTTP and HTTPS protocols are supported.
    """

    def __init__(
        self,
        model_id: str,
        base_url: str,
        __metadata_info__: Optional[MetadataType] = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        super().__init__(
            __metadata_info__=__metadata_info__,
            id=id,
            name=name,
            description=description,
        )
        self._model_id = model_id
        self._base_url = _add_leading_http_if_needed(base_url).rstrip("/")
        self._retry_strategy = _RetryStrategy()

    def _get_headers(self) -> Dict[str, str]:
        """
        Get the headers for API requests with a default implementation.
        Child classes can override this method to provide custom headers.

        Returns
        -------
        Dict[str, str]
            Default headers for API requests
        """
        return {"Content-Type": "application/json"}

    def embed(self, data: List[str]) -> List[List[float]]:
        return run_async_in_sync(self.embed_async, data, method_name="embed_async")

    async def embed_async(self, data: List[str]) -> List[List[float]]:
        url = self._base_url if self._base_url.endswith("embeddings") else f"{self._base_url}/v1/embeddings"
        payload = {"model": self._model_id, "input": data}

        headers = self._get_headers()
        response_data = await request_post_with_retries(
            request_params=dict(url=url, headers=headers, json=payload),
            retry_strategy=self._retry_strategy,
        )

        return [item["embedding"] for item in response_data["data"]]

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return {
            "model_id": self._model_id,
            "base_url": self._base_url,
            "name": self.name,
            "id": self.id,
            "description": self.description,
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        model_id = input_dict.get("model_id")
        base_url = input_dict.get("base_url")

        if not model_id:
            raise ValueError(f"Missing required field 'model_id' for {cls.__name__}")
        if not base_url:
            raise ValueError(f"Missing required field 'base_url' for {cls.__name__}")

        id = input_dict.get("id")
        name = input_dict.get("name")
        description = input_dict.get("description")

        return cls(model_id=model_id, base_url=base_url, name=name, description=description, id=id)
