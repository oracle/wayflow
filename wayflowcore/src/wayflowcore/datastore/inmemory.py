# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from logging import getLogger
from typing import Any, Dict, List, Optional, Union, cast, overload
from warnings import warn

import numpy as np
import pandas as pd

from wayflowcore.component import Component
from wayflowcore.datastore._datatable import Datatable
from wayflowcore.datastore._utils import (
    check_collection_name,
    validate_entities,
    validate_partial_entity,
)
from wayflowcore.datastore.datastore import Datastore
from wayflowcore.datastore.entity import Entity, EntityAsDictT
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import serialize_to_dict

logger = getLogger(__name__)

_INMEMORY_USER_WARNING = "InMemoryDatastore is for DEVELOPMENT and PROOF-OF-CONCEPT ONLY!"

_USER_WARNING_MESSAGE_INTERNAL = (
    "InMemoryDatastore is for DEVELOPMENT and PROOF-OF-CONCEPT ONLY!\n"
    + "DO NOT use InMemoryDatastore in production environments.\n"
    + "\n"
    + "Limitations:\n"
    + "- Data is NOT persisted between sessions\n"
    + "- Limited scalability (all data must fit in memory)\n"
    + "- No concurrent access support\n"
    + "- No enterprise features (backup, recovery, security)\n"
    + "\n"
    + "For production use, switch to OracleDatabaseDatastore.\n"
    + "=" * 80
)


class _InMemoryDatatable(Datatable):
    def __init__(self, entity_description: Entity):
        self.entity_description = entity_description
        column_names = [p_name for p_name in entity_description.properties]
        self._data = pd.DataFrame(columns=column_names)

    def _convert_where_to_filter(
        self, where: Dict[str, Any]
    ) -> np.ndarray[Any, np.dtype[np.bool_]]:
        if not where:
            return np.zeros((len(self._data),), dtype=bool)
        where_clauses = [
            self._data[where_col] == where_val for where_col, where_val in where.items()
        ]
        # np.all returns Any, for some reason
        return cast(np.ndarray[Any, np.dtype[np.bool_]], np.all(where_clauses, axis=0))

    def _add_defaults(self, entities: List[EntityAsDictT]) -> List[EntityAsDictT]:
        default_values_dict = self.entity_description.get_entity_defaults()
        entities_with_defaults = [default_values_dict | entity for entity in entities]
        validate_entities(self.entity_description, entities_with_defaults)
        return entities_with_defaults

    def list(
        self, where: Optional[Dict[str, Any]] = None, limit: Optional[int] = None
    ) -> List[EntityAsDictT]:
        if len(self._data) == 0:
            return []

        data = self._data
        if where is not None:
            validate_partial_entity(self.entity_description, where)
            where_filter = self._convert_where_to_filter(where)
            data = self._data.loc[where_filter]
        if limit is not None:
            data = data.iloc[:limit, :]
        # We can cast here, because we create the data ourselves and ensure column names
        # are str (stricter than hashable returned by DataFrame.to_dict)
        return cast(List[EntityAsDictT], data.to_dict("records"))

    def update(self, where: Dict[str, Any], update: EntityAsDictT) -> List[EntityAsDictT]:
        validate_partial_entity(self.entity_description, where)
        validate_partial_entity(self.entity_description, update)
        where_filter = self._convert_where_to_filter(where)
        for column, new_value in update.items():
            self._data.loc[where_filter, column] = new_value
        # We can cast here, because we create the data ourselves and ensure column names
        # are str (stricter than hashable returned by DataFrame.to_dict)
        return cast(List[EntityAsDictT], self._data[where_filter].to_dict("records"))

    @overload
    def create(self, entities: EntityAsDictT) -> EntityAsDictT: ...

    @overload
    def create(self, entities: List[EntityAsDictT]) -> List[EntityAsDictT]: ...

    def create(
        self, entities: Union[EntityAsDictT, List[EntityAsDictT]]
    ) -> Union[EntityAsDictT, List[EntityAsDictT]]:
        unpack_list = False
        if not isinstance(entities, list):
            entities = [entities]
            unpack_list = True
        new_data = self._add_defaults(entities)
        if len(self._data) > 0:
            self._data = pd.concat([self._data, pd.DataFrame(new_data)])
        else:
            # Pandas throws a FutureWarning on concatenation when self._data is empty:
            # The behavior of DataFrame concatenation with empty or all-NA entries is deprecated.
            # In a future version, this will no longer exclude empty or all-NA columns when
            # determining the result dtypes. To retain the old behavior, exclude the relevant
            # entries before the concat operation.
            self._data = pd.DataFrame(new_data)
        return new_data[0] if unpack_list else new_data

    def delete(self, where: Dict[str, Any]) -> None:
        validate_partial_entity(self.entity_description, where)
        where_filter = self._convert_where_to_filter(where)
        if not any(where_filter):
            logger.warning(
                "Found no matching %s records on delete, skipping...", self.entity_description.name
            )
        self._data = self._data.loc[~where_filter]


class InMemoryDatastore(Datastore, Component):
    """In-memory datastore for testing and development purposes.

    This datastore implements basic functionalities of datastores, with
    the following properties:

    * All schema objects manipulated by the datastore must be fully defined
      using the ``Entity`` property. These entities are not persisted
      across instances of ``InMemoryDatastore`` or Python processes;
    * The underlying data cannot be shared across instances of this ``Datastore``.

    .. important::
        This ``Datastore`` is meant only for testing and development
        purposes. Switch to a production-grade datastore (e.g.,
        ``OracleDatabaseDatastore``) before deploying an assistant.

    .. note::
        When this ``Datastore`` is serialized, only its configuration
        will be serialized, without any of the stored data.

    """

    def __init__(
        self,
        schema: Dict[str, Entity],
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Initialize an ``InMemoryDatastore``.

        Parameters
        ----------
        schema :
            Mapping of collection names to entity definitions used by this
            datastore.

        Example
        -------
        >>> from wayflowcore.datastore import Entity
        >>> from wayflowcore.datastore.inmemory import InMemoryDatastore
        >>> from wayflowcore.property import StringProperty, IntegerProperty

        You can define one or more entities for your datastore and initialize it

        >>> document = Entity(
        ...     properties={ "id": IntegerProperty(), "content": StringProperty(default_value="") }
        ... )
        >>> datastore = InMemoryDatastore({"documents": document})

        The ``InMemoryDatastore`` can create, list, update and delete entities.
        Creation can happen for single entities as well as multiples:

        >>> datastore.create("documents", {"id": 1, "content": "The quick brown fox jumps over the lazy dog"})
        {'content': 'The quick brown fox jumps over the lazy dog', 'id': 1}
        >>> bulk_insert_docs = [
        ...     {"id": 2, "content": "The rat the cat the dog bit chased escaped."},
        ...     {"id": 3, "content": "More people have been to Russia than I have."}
        ... ]
        >>> datastore.create("documents", bulk_insert_docs)
        [{'content': 'The rat the cat the dog bit chased escaped.', 'id': 2}, {'content': 'More people have been to Russia than I have.', 'id': 3}]

        Use ``where`` parameters to filter results when listing entities. When no matches are found, an empty list is returned
        Note that if multiple properties are set in the ``where`` dictionary, all of the values must match:

        >>> datastore.list("documents", where={"id": 3})
        [{'content': 'More people have been to Russia than I have.', 'id': 3}]
        >>> datastore.list("documents", where={"id": 1, "content": "Not the content of document 1"})
        []

        Use the limit parameter to reduce the size of the result set:

        >>> datastore.list("documents", limit=1)
        [{'content': 'The quick brown fox jumps over the lazy dog', 'id': 1}]

        The same `where` parameter can be used to determine which entities should be updated or deleted:

        >>> datastore.update("documents", where={"id": 1}, update={"content": "Will, will Will will Will Will's will?"})
        [{'content': "Will, will Will will Will Will's will?", 'id': 1}]
        >>> datastore.delete("documents", where={"id": 3})

        """
        warn(_USER_WARNING_MESSAGE_INTERNAL, UserWarning)

        super().__init__(
            name=IdGenerator.get_or_generate_name(name, prefix="inmemory_datastore", length=8),
            id=id,
            description=description,
        )
        self._validate_schema(schema)
        self.schema = schema
        self._datatables = {name: _InMemoryDatatable(e) for name, e in self.schema.items()}

    def _validate_schema(self, schema: Dict[str, Entity]) -> None:
        for collection_name, entity in schema.items():
            if entity.name != "" and collection_name != entity.name:
                warn(
                    f"Entity name {entity.name} does not match collection name {collection_name} "
                    "provided to the datastore. Only the collection name will be used to reference "
                    "the Entity. To remove this warning, remove the entity name or set it to match "
                    "the collection name.",
                    UserWarning,
                )

    def _serialize_to_dict(self, serialization_context: SerializationContext) -> Dict[str, Any]:
        return {
            "schema": {
                name: serialize_to_dict(entity, serialization_context)
                for name, entity in self.schema.items()
            }
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: DeserializationContext
    ) -> "InMemoryDatastore":
        from wayflowcore.serialization.serializer import autodeserialize_from_dict

        schema = {
            name: cast(Entity, autodeserialize_from_dict(entity, deserialization_context))
            for name, entity in input_dict["schema"].items()
        }

        return InMemoryDatastore(schema)

    def list(
        self,
        collection_name: str,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> List[EntityAsDictT]:
        check_collection_name(self.schema, collection_name)
        return self._datatables[collection_name].list(where, limit)

    def update(
        self, collection_name: str, where: Dict[str, Any], update: EntityAsDictT
    ) -> List[EntityAsDictT]:
        check_collection_name(self.schema, collection_name)
        return self._datatables[collection_name].update(where, update)

    @overload
    def create(self, collection_name: str, entities: EntityAsDictT) -> EntityAsDictT: ...

    @overload
    def create(
        self, collection_name: str, entities: List[EntityAsDictT]
    ) -> List[EntityAsDictT]: ...

    def create(
        self, collection_name: str, entities: Union[EntityAsDictT, List[EntityAsDictT]]
    ) -> Union[EntityAsDictT, List[EntityAsDictT]]:
        check_collection_name(self.schema, collection_name)
        return self._datatables[collection_name].create(entities)

    def delete(self, collection_name: str, where: Dict[str, Any]) -> None:
        check_collection_name(self.schema, collection_name)
        return self._datatables[collection_name].delete(where)

    def describe(self) -> Dict[str, Entity]:
        return self.schema
