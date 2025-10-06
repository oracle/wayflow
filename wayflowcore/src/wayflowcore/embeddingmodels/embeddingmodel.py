# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
from abc import ABC, abstractmethod
from typing import List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.component import Component
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.serialization.serializer import SerializableObject


class EmbeddingModel(Component, SerializableObject, ABC):
    """
    Abstract base class for embedding models.

    Implementations should define the 'embed' method which returns a list of
    vector embeddings (each embedding is a list of floats) given a list of text strings.
    """

    def __init__(
        self,
        __metadata_info__: Optional[MetadataType],
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        super().__init__(
            name=IdGenerator.get_or_generate_name(name, prefix="embedding_model", length=8),
            id=id,
            description=description,
            __metadata_info__=__metadata_info__,
        )

    @abstractmethod
    def embed(self, data: List[str]) -> List[List[float]]:
        """
        Generate embeddings for the given list of text strings.

        Parameters
        ----------
        data
            A list of text strings for which to generate embeddings.

        Returns
        -------
        List[List[float]]
            A list where each element is a list of floats representing the embedding
            of the corresponding text.
        """
