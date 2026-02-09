# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import warnings
from logging import getLogger
from typing import Any, Dict, List, Optional, Union, cast, overload

import numpy as np
import pandas as pd

from wayflowcore.datastore._datatable import Datatable
from wayflowcore.datastore._utils import (
    check_collection_name,
    validate_entities,
    validate_partial_entity,
)
from wayflowcore.datastore.datastore import Datastore
from wayflowcore.datastore.entity import Entity, EntityAsDictT
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.property import VectorProperty
from wayflowcore.search import (
    BaseInMemoryVectorIndex,
    EntityVectorIndex,
    SearchConfig,
    SimilarityMetric,
    SimpleVectorGenerator,
    VectorConfig,
    VectorGenerator,
    VectorRetrieverConfig,
)
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


class InMemoryDatastore(Datastore):
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
        search_configs: Optional[List["SearchConfig"]] = None,
        vector_configs: Optional[List["VectorConfig"]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        __metadata_info__: Optional["MetadataType"] = None,
    ):
        """Initialize an ``InMemoryDatastore``.

        Vector Config resolution Priority:
            1. VectorRetrieverConfig has a vectors attribute defined
            2. One of vector_configs' collection name matches with input collection_name
            3. Vector column is inferred from Schema

        Parameters
        ----------
        schema
            Mapping of collection names to entity definitions used by this
            datastore.
        search_configs
            List of search configurations for vector search capabilities.
            By default, it's set as None.
            If no search config is given, the datastore will not support Search functionality.
        vector_configs
            List of vector configurations for vector generation and storage.
            By default, it's set as None.
            If None, an implicit vector config will be created.
            Any operation on the Datastore might trigger the vector indices for these vector configs to be rebuilt again.

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
        warnings.warn(_USER_WARNING_MESSAGE_INTERNAL)


        self._validate_schema(schema)
        self.schema = schema
        super().__init__(
            schema=schema,
            search_configs=search_configs,
            vector_configs=vector_configs,
            id=id,
            name=IdGenerator.get_or_generate_name(name, prefix="inmemory_datastore", length=8),
            description=description,
            __metadata_info__=__metadata_info__,
        )
        self._validate_schema(schema)
        self.schema = schema
        self._datatables = {name: _InMemoryDatatable(e) for name, e in self.schema.items()}

        self._implicit_vector_property_name = "_embedding"  # Only used when the user has not defined a vector property name and wants to use search
        # Initialize vector infrastructure
        # Vector infrastructure maps:
        # - Outer dict: collection_name -> inner dict
        # - Inner dict: vector_config_name -> actual index
        # This allows multiple vector configs per collection (e.g., different serializers)
        self._vector_indices: Dict[str, Dict[str, BaseInMemoryVectorIndex]] = {}
        self._vector_generators: Dict[str, VectorGenerator] = {}

        # Create implicit vector properties where needed
        self._create_implicit_vector_properties()

        # Initialize datatables after schema modification
        self._datatables = {name: _InMemoryDatatable(e) for name, e in self.schema.items()}

        # Initialize vector infrastructure for each collection
        self._initialize_vector_infrastructure()

    def _create_implicit_vector_properties(self) -> None:
        """Create implicit vector properties for entities that need them.

        Examines search configurations to determine which collections require
        vector properties. For collections without explicit vector properties,
        creates an implicit '_embedding' property.
        """
        # Check which collections need vector properties based on search configs
        collections_needing_vectors = set()

        for search_config in self.search_configs:
            collection_name = search_config.retriever.collection_name
            if collection_name and collection_name in self.schema:
                collections_needing_vectors.add(collection_name)
            elif not collection_name:
                # If no collection specified, all collections need vectors
                collections_needing_vectors.update(self.schema.keys())

        # Create implicit vector properties for collections that don't have any
        for collection_name in collections_needing_vectors:
            entity = self.schema[collection_name]
            if not entity._has_vector_properties:
                # Create a new entity with the implicit vector property
                # Implicit vector properties:
                # When a collection needs vectors but has none defined, we auto-create
                # a hidden "_embedding" VectorProperty to store generated embeddings

                new_properties = entity.properties.copy()

                vector_config = self._find_or_create_vector_config(collection_name)
                if vector_config.vector_property:
                    vector_property = vector_config.vector_property
                else:
                    raise ValueError(
                        f"No Vector Property found for collection name {collection_name}. "
                        "Please specify a Vector Property in the Vector Config if you want to implicitly generate the vector column"
                    )

                new_properties[vector_property] = VectorProperty(
                    name=vector_property,
                    hidden=True,
                    description="Auto-generated embedding vector",
                    default_value=[],
                )
                # Replace the entity in the schema
                self.schema[collection_name] = Entity(
                    name=entity.name,
                    description=entity.description,
                    default_value=entity.default_value,
                    properties=new_properties,
                )

    def _initialize_vector_infrastructure(self) -> None:
        """Initialize vector indices and generators for collections.

        Sets up the vector search infrastructure for each collection that has
        vector properties, including vector generators for embedding generation.
        """
        for collection_name, entity in self.schema.items():
            self._vector_indices[collection_name] = {}

            # Create vector generators for collections with vector properties
            if entity._has_vector_properties:
                # Find or create vector config for this collection
                vector_config = self._find_or_create_vector_config(collection_name)

                # Get embedding model from search configs
                embedding_model = self._get_first_embedding_model(collection_name)
                if embedding_model:
                    # Use SimpleVectorGenerator
                    self._vector_generators[collection_name] = SimpleVectorGenerator(
                        vector_config, embedding_model
                    )

    def _find_or_create_vector_config(self, collection_name: str) -> VectorConfig:
        """Find existing vector config or create an implicit one for a collection."""
        # Look for existing vector config for this collection
        for config in self.vector_configs:
            if config.collection_name and config.collection_name == collection_name:
                return config

        # Check if implicit config already exists in map
        implicit_name = f"vector_{collection_name}"
        if implicit_name in self._vector_config_map:
            return self._vector_config_map[implicit_name]

        # Create implicit vector config
        implicit_config = VectorConfig(
            name=implicit_name,
            collection_name=collection_name,
            vector_property=self._get_first_vector_property_name(
                collection_name
            ),  # Use the vector property or the implicit vector name
        )
        self.vector_configs.append(implicit_config)
        self._vector_config_map[implicit_name] = implicit_config
        return implicit_config

    def _validate_schema(self, schema: Dict[str, Entity]) -> None:
        for collection_name, entity in schema.items():
            if entity.name != "" and collection_name != entity.name:
                warnings.warn(
                    f"Entity name {entity.name} does not match collection name {collection_name} "
                    "provided to the datastore. Only the collection name will be used to reference "
                    "the Entity. To remove this warning, remove the entity name or set it to match "
                    "the collection name.",
                    UserWarning,
                )

    def _serialize_to_dict(self, serialization_context: SerializationContext) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "schema": {
                name: serialize_to_dict(entity, serialization_context)
                for name, entity in self.schema.items()
            },
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }

        if self.search_configs is not None:
            result["search_configs"] = [
                serialize_to_dict(config, serialization_context) for config in self.search_configs
            ]

        if self.vector_configs is not None:
            result["vector_configs"] = [
                serialize_to_dict(config, serialization_context) for config in self.vector_configs
            ]

        return result

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: DeserializationContext
    ) -> "InMemoryDatastore":
        from wayflowcore.serialization.serializer import (
            autodeserialize_from_dict,
            deserialize_any_from_dict,
        )

        schema = {
            name: cast(Entity, autodeserialize_from_dict(entity, deserialization_context))
            for name, entity in input_dict["schema"].items()
        }

        id = input_dict["id"]
        name = input_dict["name"]
        description = input_dict["description"]

        search_configs = None
        if "search_configs" in input_dict:
            search_configs = [
                deserialize_any_from_dict(config, SearchConfig, deserialization_context)
                for config in input_dict["search_configs"]
            ]

        vector_configs = None
        if "vector_configs" in input_dict:
            vector_configs = [
                deserialize_any_from_dict(config, VectorConfig, deserialization_context)
                for config in input_dict["vector_configs"]
            ]

        return InMemoryDatastore(
            schema=schema,
            id=id,
            search_configs=search_configs,
            vector_configs=vector_configs,
            name=name,
            description=description,
        )

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
        updated = self._datatables[collection_name].update(where, update)

        if self._affects_vectors(collection_name, update):
            self._process_vectors_for_entities(collection_name, updated)
            self._rebuild_affected_indices(collection_name)

        return updated

    def _check_normalized_entities(
        self,
        entities: Union[EntityAsDictT, List[EntityAsDictT]],
    ) -> List[EntityAsDictT]:
        if isinstance(entities, dict):
            return [entities]
        elif isinstance(entities, list):
            for x in entities:
                if isinstance(x, dict):
                    continue
                elif isinstance(x, (list, tuple, set)):
                    raise TypeError(
                        f"Nested collection detected (collection of collections) inside entities list."
                        f"Did you mean to provide a list of dicts? Got: {x}"
                    )
                else:
                    raise TypeError(f"Invalid entity type inside list: {type(x)}")
            return entities
        else:
            raise TypeError(f"Invalid entity type for creation: {type(entities)}")

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

        entities_list = self._check_normalized_entities(entities)
        is_single = isinstance(entities, dict)

        # Generate vectors before creating if we have a vector generator
        if collection_name in self._vector_generators:
            # First ensure entities have the default empty vectors
            entity_schema = self.schema[collection_name]

            defaults = entity_schema.get_entity_defaults()
            for entity in entities_list:
                for key, value in defaults.items():
                    if key not in entity:
                        entity[key] = value
            self._process_vectors_for_entities(collection_name, entities_list)

        result: Union[EntityAsDictT, List[EntityAsDictT]]
        # Create entities with vectors already included
        if is_single:
            result = self._datatables[collection_name].create(entities_list[0])

        else:
            result = self._datatables[collection_name].create(entities_list)

        if collection_name in self._vector_generators:
            self._rebuild_affected_indices(collection_name)

        return result

    def _process_vectors_for_entities(
        self, collection_name: str, entities: List[EntityAsDictT]
    ) -> None:
        """Generate and store vectors for entities.

        Generates entity-level vectors.
        """
        # Safeguard: ensure entities is a flat list of dicts
        if not isinstance(entities, list) or not all(isinstance(x, dict) for x in entities):
            raise TypeError("entities must be a list of dicts (EntityAsDictT)")

        vector_generator = self._vector_generators.get(collection_name)
        if not vector_generator:
            return

        vector_property = self._get_first_vector_property_name(collection_name)

        if vector_property not in self.schema[collection_name].properties:
            raise ValueError(
                f"Given vector column name is not present in the table: {vector_property}"
            )

        if vector_property in entities[0] and entities[0][vector_property]:
            return

        vectors = vector_generator.generate_vectors(entities)
        for entity, vector in zip(entities, vectors):
            entity[vector_property] = vector

    def _handle_vector_property_name_not_found(self, collection_name: str) -> str:
        return self._implicit_vector_property_name

    def _rebuild_affected_indices(self, collection_name: str) -> None:
        """Rebuild vector indices after entity changes.

        Rebuilds entity-level indices based on the collection's vector configurations.
        """
        entities = self._datatables[collection_name].list()

        relevant_configs = []
        for config in self.vector_configs:
            if config.collection_name and config.collection_name == collection_name:
                relevant_configs.append(config)
        if not relevant_configs and collection_name in self._vector_generators:
            implicit_config = self._find_or_create_vector_config(collection_name)
            relevant_configs.append(implicit_config)

        for vector_config in relevant_configs:
            vector_property = vector_config.vector_property or self._get_first_vector_property_name(
                collection_name
            )

            # Build entity index using EntityVectorIndex
            dimension = None
            for entity in entities:
                if vector_property in entity and entity[vector_property]:
                    dimension = len(entity[vector_property])
                    break
            if dimension is not None:
                index = EntityVectorIndex(dimension, SimilarityMetric.COSINE)
                index.build(entities, vector_property)
                if not vector_config.name:
                    raise ValueError("Vector Config name is not configured properly")
                self._vector_indices[collection_name][vector_config.name] = index

    def _affects_vectors(self, collection_name: str, update: EntityAsDictT) -> bool:
        """Check if an update affects vector generation for a collection."""
        if collection_name not in self._vector_generators:
            return False

        vector_property = self._get_first_vector_property_name(collection_name)

        if vector_property in update:
            return True

        # Check if any string property is updated (used in text extraction)
        # The current ConcatSerializerConfig assumes that all columns are being used for generating vectors
        # Thus, if any non-hidden property is present in the update, it will affect the vectors
        for key, value in update.items():
            if isinstance(value, str) and not key.startswith("_"):
                return True

        return False

    def delete(self, collection_name: str, where: Dict[str, Any]) -> None:
        check_collection_name(self.schema, collection_name)
        self._datatables[collection_name].delete(where)

        if collection_name in self._vector_generators:
            self._rebuild_affected_indices(collection_name)

    def describe(self) -> Dict[str, Entity]:
        return self.schema

    def _search_backend(
        self,
        collection_name: str,
        query_embedding: List[float],
        k: int,
        metric: SimilarityMetric,
        where: Optional[Dict[str, Any]],
        columns_to_exclude: Optional[List[str]],
        vector_config: Optional[VectorConfig],
    ) -> List[Dict[str, Any]]:
        """
        Backend execution for in-memory search: retrieves (or rebuilds) in-memory vector index and searches.
        """
        if vector_config:
            vector_config_name = vector_config.name
        else:
            vector_config_name = None
        # Find correct vector config name (handles migration from old behavior)
        if not isinstance(vector_config_name, str):
            raise ValueError(
                f"Expected Vector Config name to be a string, but got a config of type: {type(vector_config_name)}"
            )
        index = self._vector_indices[collection_name][vector_config_name]
        results = index.search(
            query_embedding, k, metric=metric, where=where, columns_to_exclude=columns_to_exclude
        )

        return results

    def _find_vector_config_from_name(
        self,
        vector_config_name: Optional[str],
        collection_name: Optional[str] = None,
    ) -> Optional[VectorConfig]:
        if not isinstance(vector_config_name, str):
            raise ValueError(
                f"Expected Vector Config name to be a string, but got a config of type: {type(vector_config_name)}"
            )
        if collection_name not in self._vector_indices:
            raise ValueError(f"No vector index found for collection '{collection_name}'")
        if vector_config_name not in self._vector_indices[collection_name]:
            self._rebuild_affected_indices(collection_name)
            if vector_config_name not in self._vector_indices[collection_name]:
                raise ValueError(f"No vector index found for config '{vector_config_name}'")

        implicit_config = self._find_or_create_vector_config(collection_name)
        if implicit_config.name != vector_config_name:
            raise ValueError(
                f"Expected a to find a Vector Config for collection_name: {collection_name} and vector config name: {vector_config_name}"
            )
        else:
            return implicit_config

    def _handle_no_matching_vector_config(
        self, collection_name: str, retriever: VectorRetrieverConfig
    ) -> str:
        # Create implicit config if needed and return its name
        implicit_config = self._find_or_create_vector_config(collection_name)
        if implicit_config.name is None:
            raise ValueError(f"Expected Vector Config name to not be of type: {None}")
        return implicit_config.name
