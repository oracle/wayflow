# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, overload

from wayflowcore.datastore.entity import EntityAsDictT


class Datatable(ABC):
    """Store and perform basic manipulations on a uniform collection of entities.

    Provides an interface for listing, creating, deleting, updating entities.
    """

    @abstractmethod
    def list(
        self, where: Optional[Dict[str, Any]] = None, limit: Optional[int] = None
    ) -> List[EntityAsDictT]:
        """Retrieve a list of entities based on the specified criteria.

        Parameters
        ----------
        where :
            Filter criteria for the entities to list (default is ``None``).
            The dictionary is composed of property name and value pairs
            to filter by with exact matches. Only entities matching all
            conditions in the dictionary will be listed. For example,
            ``{"name": "Fido", "breed": "Golden Retriever"}`` will match
            all ``Golden Retriever`` dogs named ``Fido``.
        limit :
            Maximum number of entities to retrieve (default is ``None``,
            retrieve all entities).

        Returns
        -------
        list[dict]
            A list of entities matching the specified criteria.
        """

    @overload
    def create(self, entities: EntityAsDictT) -> EntityAsDictT: ...

    @overload
    def create(self, entities: List[EntityAsDictT]) -> List[EntityAsDictT]: ...

    @abstractmethod
    def create(
        self, entities: Union[EntityAsDictT, List[EntityAsDictT]]
    ) -> Union[EntityAsDictT, List[EntityAsDictT]]:
        """Create new entities in the data table.

        Parameters
        ----------
        entities :
            One or more entities to create. Creating multiple entities
            at once may be beneficial for performance compared to
            executing multiple calls to create.

        Returns
        -------
        list[dict] or dict
            The newly created entities, including any defaults not provided
            in the original entity. If the input entities were multiples,
            they will be returned as a list. Otherwise, a single dictionary
            with the newly created entity will be returned.
        """

    @abstractmethod
    def delete(self, where: Dict[str, Any]) -> None:
        """Delete entities based on the specified criteria.

        Parameters
        ----------
        where :
            Filter criteria for the entities to delete.
            The dictionary is composed of property name and value pairs
            to filter by with exact matches. Only entities matching all
            conditions in the dictionary will be deleted. For example,
            ``{"name": "Fido", "breed": "Golden Retriever"}`` will match
            all ``Golden Retriever`` dogs named ``Fido``.
        """

    @abstractmethod
    def update(self, where: Dict[str, Any], update: EntityAsDictT) -> List[EntityAsDictT]:
        """Update existing entities that match the provided conditions.

        Parameters
        ----------
        where :
            Filter criteria for the entities to update.
            The dictionary is composed of property name and value pairs
            to filter by with exact matches. Only entities matching all
            conditions in the dictionary will be updated. For example,
            ``{"name": "Fido", "breed": "Golden Retriever"}`` will match
            all ``Golden Retriever`` dogs named ``Fido``.
        update :
            The data to update the entities.

        Returns
        -------
        The updated entities, including any defaults not set in the
        original entity.
        """
