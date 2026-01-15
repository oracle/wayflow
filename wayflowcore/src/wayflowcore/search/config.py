# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

from wayflowcore.embeddingmodels import EmbeddingModel
from wayflowcore.search.metrics import SimilarityMetric
from wayflowcore.serialization.serializer import SerializableDataclass


@dataclass
class VectorConfig(SerializableDataclass):
    """Configuration for how to generate and store embeddings/vectors for a collection of entities in a ``Datastore``.

    Parameters
    ----------
    model
        Embedding model to use for encoding queries.
        If there is no embedding model given, then the embedding model needs to be given in ``VectorRetrieverConfig``.
    collection_name
        Name of the collection for which the VectorConfig belongs to.
        If no collection_name is given, the VectorConfig is usable for any collection.
    vector_property
        The document field/property name where generated vectors are stored.
        If None, the vector column will be inferred during search.
    serializer
        Serializer to concatenate or preprocess text before embedding, by default None.
        If None, a default Serializer will be used depending on the ``VectorGenerator`` class.
        It will be ignored if used for OracleDatabaseDatastore,
        because embeddings can only be generated for InMemoryDatastore.
    name
        Identifier for this vector configuration. If None, a name is inferred during instantiating a ``Datastore``.
    """

    model: Optional[EmbeddingModel] = None
    collection_name: Optional[str] = None
    vector_property: Optional[str] = None
    serializer: Optional["SerializerConfig"] = None
    name: Optional[str] = None


class RetrieverConfig(ABC):
    """Base configuration for search retrievers.

    Defines the interface for retriever configurations that can be used
    in search pipelines.
    """

    @abstractmethod
    def get_index_config(self) -> Dict[str, Any]:
        """Get configuration parameters for the index.

        Returns
        -------
        dict[str, Any]
            Configuration parameters for the index.
        """


@dataclass
class VectorRetrieverConfig(SerializableDataclass, RetrieverConfig):
    """Configuration for vector-based retrievers.

    Uses semantic embeddings to find similar entities.

    Parameters
    ----------

    vectors
        Name of the vector config present in the datastore or the VectorConfig itself to use, by default None.
        If None, the vector column will be inferred during search.
    model
        Embedding model to use for encoding queries. By default, it uses the embedding model from VectorConfig.
        If there is no embedding model given in the VectorConfig, then the embedding model needs to be given.
    collection_name
        Name of the collection to retrieve from. If None, applies to all collections.
    distance_metric
        Distance metric to use, by default cosine_distance (SimilarityMetric.COSINE).

        Metrics currently supported:
            - l2_distance (SimilarityMetric.EUCLIDEAN)
            - cosine_distance (SimilarityMetric.COSINE)
            - inner_product (SimilarityMetric.DOT)
    **index_params
        Additional parameters for the index configuration.
    """

    vectors: Optional[Union[str, "VectorConfig"]] = None
    model: Optional[EmbeddingModel] = None
    collection_name: Optional[str] = None
    distance_metric: SimilarityMetric = SimilarityMetric.COSINE
    index_params: Dict[str, Any] = field(default_factory=dict)

    def get_index_config(self) -> Dict[str, Any]:
        """Get configuration parameters for the vector index.

        Returns
        -------
        dict[str, Any]
            Configuration parameters for the vector index.
        """
        config = {
            "type": "vector",
            "collection_name": self.collection_name,
            "vector_field": self.vectors,
            "distance_metric": self.distance_metric,
            **self.index_params,
        }
        return config


@dataclass
class SearchConfig(SerializableDataclass):
    """Configuration for a search pipeline.

    A search pipeline defines how to retrieve and process entities for search.

    Parameters
    ----------
    retriever
        Retriever configuration for the search pipeline.
    name
        Name of the search pipeline.
        If None, a name is inferred and assigned during instantiating a ``Datastore``.
    """

    retriever: VectorRetrieverConfig
    name: Optional[str] = None


@dataclass
class SerializerConfig(ABC):
    """Base configuration for serializing entity properties into a single string.

    Use this for generating input text for embedding models or
    any string-based search/pruning steps.
    """

    @abstractmethod
    def serialize(self, entity: Dict[str, Any]) -> str:
        """Serialize entity to string by concatenating property values. Must be implemented by subclasses

        Parameters
        ----------
        entity
            Entity to serialize.

        Returns
        -------
        str
            Serialized string representation.
        """


@dataclass
class ConcatSerializerConfig(SerializerConfig):
    """
    Serializer that concatenates property values with optional pre- and post-processing steps.

    Parameters
    ----------
    separator : str
        String used to separate concatenated property values. Default is '\\n'.
    pre_processors : Optional[List[Callable[[str], str]]]
        List of callables to apply sequentially to each property value before formatting. Default is None.
    post_processors : Optional[List[Callable[[str], str]]]
        List of callables to apply sequentially to the entire result after concatenation. Default is None.
    include_property_names : bool
        Whether to include property names in the formatted output. Default is True.
    skip_hidden_properties : bool
        If True, skip properties whose names begin with an underscore. Default is True.
    property_name_format : str
        String format applied when including property names, with placeholders for property key and value. Default is '{key}: {value}'.
    columns_to_exclude: List[str]
        Columns to exclude while performing serialization. Default is None.
    """

    separator: str = "\n"
    pre_processors: Optional[List[Callable[[str], str]]] = None
    post_processors: Optional[List[Callable[[str], str]]] = None
    include_property_names: bool = True
    skip_hidden_properties: bool = True
    property_name_format: str = "{key}: {value}"
    columns_to_exclude: Optional[List[str]] = None

    def serialize(self, entity: Dict[str, Any]) -> str:
        """Serialize entity to string by concatenating property values.

        Parameters
        ----------
        entity
            Entity to serialize.

        Returns
        -------
        str
            Serialized string representation.
        """
        text_parts = []

        for key, value in entity.items():
            # Skip hidden properties if configured
            if self.skip_hidden_properties and key.startswith("_"):
                continue
            # Skip columns to exclude for serialization
            if self.columns_to_exclude and key in self.columns_to_exclude:
                continue

            # Convert value to string
            if isinstance(value, str):
                text_value = value
            elif isinstance(value, (int, float, bool)):
                text_value = str(value)
            elif isinstance(value, list):
                # Handle list values by joining them
                text_value = ", ".join(
                    str(item) for item in value if not isinstance(item, (dict, list))
                )
            elif isinstance(value, dict):
                text_value = json.dumps(value)
            else:
                # Convert other types to string
                text_value = str(value)

            # Apply pre-processors if configured
            if self.pre_processors:
                for processor in self.pre_processors:
                    text_value = processor(text_value)

            # Format the property
            if self.include_property_names:
                formatted_text = self.property_name_format.format(key=key, value=text_value)
            else:
                formatted_text = text_value

            text_parts.append(formatted_text)

        # Join all parts
        result = self.separator.join(text_parts)

        # Apply post-processors if configured
        if self.post_processors:
            for processor in self.post_processors:
                result = processor(result)

        return result
