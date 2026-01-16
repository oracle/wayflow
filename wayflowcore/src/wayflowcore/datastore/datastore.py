# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, overload

from wayflowcore._metadata import MetadataType
from wayflowcore.component import Component
from wayflowcore.datastore.entity import Entity, EntityAsDictT


class Datastore(Component, ABC):
    """Store and perform basic manipulations on collections of entities
    of various types.

    Provides an interface for listing, creating, deleting and updating
    collections. It also provides a way of describing the entities in
    this datastore.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        id: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        super().__init__(
            name=name, description=description, id=id, __metadata_info__=__metadata_info__
        )

    @abstractmethod
    def list(
        self,
        collection_name: str,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> List[EntityAsDictT]:
        """Retrieve a list of entities in a collection based on the
        given criteria.

        Parameters
        ----------
        collection_name :
            Name of the collection to list.
        where :
            Filter criteria for the collection to list.
            The dictionary is composed of property name and value pairs
            to filter by with exact matches. Only entities matching all
            conditions in the dictionary will be listed. For example,
            ``{"name": "Fido", "breed": "Golden Retriever"}`` will match
            all ``Golden Retriever`` dogs named ``Fido``.
        limit :
            Maximum number of entities to retrieve, by default ``None``
            (retrieve all entities).

        Returns
        -------
        list[dict]
            A list of entities matching the specified criteria.
        """

    @overload
    def create(self, collection_name: str, entities: EntityAsDictT) -> EntityAsDictT: ...

    @overload
    def create(
        self, collection_name: str, entities: List[EntityAsDictT]
    ) -> List[EntityAsDictT]: ...

    @abstractmethod
    def create(
        self, collection_name: str, entities: Union[EntityAsDictT, List[EntityAsDictT]]
    ) -> Union[EntityAsDictT, List[EntityAsDictT]]:
        """Create new entities of the specified type.

        Parameters
        ----------
        collection_name :
            Name of the collection to create the new entities in.
        entities :
            One or more entities to create. Creating multiple entities
            at once may be beneficial for performance compared to
            executing multiple calls to create.

            .. important::
                When bulk-creating entities, all entities must contain the same set of properties.
                For example, if the ``Entity`` "employees" has ``properties`` "name" (required) and
                "salary" (optional), either all entities to create define only the name, or all
                define both name and salary. Some entities defining the salary and others relying on
                its default value is not supported.)

        Returns
        -------
        list[dict] or dict
            The newly created entities, including any defaults not provided
            in the original entity. If the input entities were multiples,
            they will be returned as a list. Otherwise, a single dictionary
            with the newly created entity will be returned.
        """

    @abstractmethod
    def delete(self, collection_name: str, where: Dict[str, Any]) -> None:
        """Delete entities based on the specified criteria.

        Parameters
        ----------
        collection_name :
            Name of the collection in which entities will be deleted.
        where :
            Filter criteria for the entities to delete.
            The dictionary is composed of property name and value pairs
            to filter by with exact matches. Only entities matching all
            conditions in the dictionary will be deleted. For example,
            ``{"name": "Fido", "breed": "Golden Retriever"}`` will match
            all ``Golden Retriever`` dogs named ``Fido``.
        """

    @abstractmethod
    def update(
        self, collection_name: str, where: Dict[str, Any], update: EntityAsDictT
    ) -> List[EntityAsDictT]:
        """Update existing entities that match the provided conditions.

        Parameters
        ----------
        collection_name :
            Name of the collection to be updated.
        where :
            Filter criteria for the collection to update.
            The dictionary is composed of property name and value pairs
            to filter by with exact matches. Only entities matching all
            conditions in the dictionary will be updated. For example,
            ``{"name": "Fido", "breed": "Golden Retriever"}`` will match
            all ``Golden Retriever`` dogs named ``Fido``.
        update :
            The update to apply to the matching entities in the collection.

        Returns
        -------
        list[dict]
            The updated entities, including any defaults or values not set in the update.
        """

    @abstractmethod
    def describe(self) -> Dict[str, Entity]:
        """Get the descriptions of the schema associated with this
        ``Datastore``.

        Returns
        -------
        dict[str, Entity]
            The description of the schema for the ``Datastore``.
        """
