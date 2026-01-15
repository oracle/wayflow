# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from wayflowcore.embeddingmodels import EmbeddingModel
from wayflowcore.search.config import ConcatSerializerConfig, VectorConfig


class VectorGenerator(ABC):
    """Abstract base class for generating embeddings from entities."""

    @abstractmethod
    def generate_vectors(
        self,
        entities: List[Dict[str, Any]],
    ) -> List[List[float]]:
        """Generate vectors for a list of entities.

        Parameters
        ----------
        entities
            List of entities to generate vectors for.

        Returns
        -------
        List[List[float]]
            List of vectors, one per entity.
        """


class SimpleVectorGenerator(VectorGenerator):
    """Vector generator for simple vector generation.
    No chunking is supported with this one.
    """

    def __init__(self, vector_config: VectorConfig, embedding_model: EmbeddingModel):
        """Initialize the vector generator.

        Parameters
        ----------
        vector_config
            Configuration for vector generation.
        embedding_model
            Model to use for generating embeddings.
        """
        self.vector_config = vector_config
        self.embedding_model = embedding_model

        serializer = vector_config.serializer
        if serializer is None:
            serializer = ConcatSerializerConfig(
                separator=",",
                include_property_names=True,
                skip_hidden_properties=True,
                property_name_format="{key}: {value}",
            )
        self.serializer = serializer

    def generate_vectors(self, entities: List[Dict[str, Any]]) -> List[List[float]]:
        """Generate vectors for a list of entities.

        Parameters
        ----------
        entities
            List of entities to generate vectors for.

        Returns
        -------
        List[List[float]]
            List of vectors, one per entity.
        """

        texts = [self.serializer.serialize(entity) for entity in entities]
        vectors = self.embedding_model.embed(texts)

        return vectors
