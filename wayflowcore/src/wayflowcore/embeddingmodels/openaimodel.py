# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import os
from typing import Any, Dict, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.embeddingmodels.openaicompatiblemodel import OpenAICompatibleEmbeddingModel
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject


class OpenAIEmbeddingModel(OpenAICompatibleEmbeddingModel, SerializableObject):
    """
    Embedding model for OpenAI's embedding API using the requests library.

    Parameters
    ----------
    model_id:
        The name of the OpenAI model to use for generating embeddings.
    api_key:
        The API key for the service. If not provided, the value of the
        OPENAI_API_KEY environment variable will be used, if set.

    Examples
    --------
    >>> from wayflowcore.embeddingmodels.openaimodel import OpenAIEmbeddingModel  # doctest: +SKIP
    >>> model = OpenAIEmbeddingModel(model_id="text-embedding-3-small", api_key="<your API key>")  # doctest: +SKIP
    >>> embeddings = model.embed(["WayFlow is a framework to develop and run LLM-based assistants."])  # doctest: +SKIP
    >>> # Update API key after initialization
    >>> model.api_key = "<your new API key>"  # doctest: +SKIP
    >>> # If no key is provided, it will try to use the OPENAI_API_KEY environment variable
    >>> model.api_key = None  # Will use environment variable if available  # doctest: +SKIP

    Notes
    -----
    `OPENAI_API_KEY` is the default API key used for authentication with the embedding service when ``api_key`` is not explicitly provided.
    If the API key is not provided and the environment variable `OPENAI_API_KEY` is not set, a ValueError is raised.

    Available embedding models: https://platform.openai.com/docs/guides/embeddings#embedding-models
    """

    def __init__(
        self,
        model_id: str,
        api_key: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        _validate_api_key: bool = True,
    ):
        base_url = "https://api.openai.com"
        super().__init__(
            model_id=model_id,
            base_url=base_url,
            __metadata_info__=__metadata_info__,
            id=id,
            name=name,
            description=description,
        )

        if api_key:
            self._api_key = api_key
        else:
            self._api_key = os.getenv("OPENAI_API_KEY", "")

        if not self._api_key and _validate_api_key:
            raise ValueError(
                "API key must be provided either through the api_key parameter or the OPENAI_API_KEY environment variable"
            )

    def _get_headers(self) -> Dict[str, str]:
        # has additional authorization field for the API key
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

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

        if not model_id:
            raise ValueError(f"Missing required field 'model_id' for {cls.__name__}")

        id = input_dict.get("id")
        name = input_dict.get("name")
        description = input_dict.get("description")

        return cls(
            model_id=model_id, name=name, description=description, id=id, _validate_api_key=False
        )
