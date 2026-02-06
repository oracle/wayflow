# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import warnings
from abc import ABC, abstractmethod
from logging import getLogger
from typing import Any, Dict, List, Optional, Sequence, Union, overload

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.async_helpers import run_async_in_sync
from wayflowcore.component import Component
from wayflowcore.datastore.entity import Entity, EntityAsDictT
from wayflowcore.embeddingmodels import EmbeddingModel
from wayflowcore.search import SearchConfig, VectorConfig, VectorRetrieverConfig
from wayflowcore.search.metrics import SimilarityMetric
from wayflowcore.tools import Tool, ToolBox

logger = getLogger(__name__)

_DEFAULT_K = 3


class Datastore(Component, ABC):
    """Store and perform basic manipulations on collections of entities
    of various types.

    Provides an interface for listing, creating, deleting and updating
    collections. It also provides a way of describing the entities in
    this datastore.
    """

    def __init__(
        self,
        schema: Dict[str, Entity],
        search_configs: Optional[List["SearchConfig"]] = None,
        vector_configs: Optional[List["VectorConfig"]] = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Initialize a ``Datastore``.

        Parameters
        ----------
        schema : dict[str, Entity]
            Mapping of collection names to entity definitions used by this datastore.
        search_configs :
            List of search configurations for vector search capabilities.
            By default, it's set as None.
            If no search config is given, the datastore will not support Search functionality.
        vector_configs :
            List of vector configurations for vector generation and storage.
            By default, it's set as None.
            If None, a vector config will be inferred for each vector property found in the schema.
        id : Optional[str]
            Optional unique identifier for this datastore instance. Default is None.
        name : Optional[str]
            Optional name to help identify this datastore. Default is None.
        description : Optional[str]
            Optional human-readable description of the datastore. Default is None.
        """

        self.schema = schema

        # Search config resolution priority:
        # 1. Explicit collection match (config.collection_name == requested)
        # 2. Universal config (config.collection_name is None/empty)
        self.search_configs = search_configs or []
        self.vector_configs = vector_configs or []

        # Build configuration maps for efficient lookup
        # _search_config_map: Maps search config names to SearchConfig objects for O(1) lookup
        # Auto-generates names like "search_<collection>" if not explicitly provided
        # _vector_config_map: Maps vector config names to VectorConfig objects
        # Auto-generates names like "vector_<collection>" if not explicitly provided
        self._search_config_map: Dict[str, SearchConfig] = {}
        self._vector_config_map: Dict[str, VectorConfig] = {}
        self._build_config_maps()

        super().__init__(
            name=name,
            id=id,
            description=description,
        )

    def search(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Search for entities matching a query in an synchronous manner. See the `search_async` method to get details about the parameters.

        Note: While performing search, at least one of search_config or collection_name must be specified.
        """

        # need to wrap because we can't pass named arguments to anyio
        async def inside_wrapped() -> Any:
            return await self.search_async(*args, **kwargs)

        return run_async_in_sync(inside_wrapped)

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
        Subclass hook for actual execution of search over the chosen backend/index.
        Should be implemented by concrete datastore subclasses.
        """
        raise NotImplementedError()

    async def search_async(
        self,
        query: str,
        collection_name: Optional[str] = None,
        search_config: Optional[str] = None,
        k: int = 3,
        where: Optional[Dict[str, Any]] = None,
        columns_to_exclude: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for entities matching a query in an asynchronous manner.

        Note: While performing search, at least one of search_config or collection_name must be specified.

        Parameters
        ----------
        query : str
            Search query string to find matching entities.
        collection_name : Optional[str]
            Optional name of the collection to search within.
        search_config : Optional[str]
            Optional search configuration name to use; if None, infers config from collection name.
        k : int
            Number of results to return (default: 3).
        where : Optional[Dict[str, Any]]
            Optional filters to apply to search results.
            The dictionary keys are column names, and the values are specific the values in that column
            If given, returns results only matching the filters
        columns_to_exclude : Optional[List[str]]
            Optional list of columns to exclude from the search results. The vector embedding column is excluded by default

        Returns
        -------
        List[Dict[str, Any]]
            List of matching entities ordered by relevance.
        """
        from wayflowcore.datastore._utils import check_collection_name

        if search_config:
            config = self._search_config_map.get(search_config)
            if config is None:
                raise ValueError(f"Search config '{search_config}' not found")

            if not collection_name:
                collection_name = config.retriever.collection_name
                if not collection_name:
                    raise ValueError(
                        "Given search_config does not have a collection_name configured."
                    )
            else:
                if (
                    config.retriever.collection_name
                    and config.retriever.collection_name != collection_name
                ):
                    raise ValueError(
                        "collection name inside SearchConfig and collection name passed in the search function do not match"
                    )
        elif collection_name and not search_config:
            config = self._find_default_search_config(collection_name)
            if not config:
                raise ValueError(f"No search config found for collection '{collection_name}'")
        else:
            raise ValueError(
                "Expected one of search_config or collection_name to be passed in search()"
            )

        check_collection_name(self.schema, collection_name)

        retriever = config.retriever
        vector_config_name = self._find_vector_config_name_for_search(retriever, collection_name)
        vector_config = self._find_vector_config_from_name(vector_config_name, collection_name)

        model = self._get_first_embedding_model(
            collection_name, vector_config=vector_config, search_config=config
        )
        if model:
            _query_embedding = await model.embed_async([query])
            query_embedding = _query_embedding[0]
        else:
            raise ValueError(
                f"Could not find any embedding model for collection_name: {collection_name}"
            )

        results = self._search_backend(
            collection_name=collection_name,
            query_embedding=query_embedding,
            k=k,
            metric=retriever.distance_metric,
            where=where,
            columns_to_exclude=columns_to_exclude,
            vector_config=vector_config,
        )
        return results[:k]

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

    def get_search_toolbox(
        self,
        collection_names: Optional[List[str]] = None,
        search_configs: Optional[List[str]] = None,
        k: int = _DEFAULT_K,
        requires_confirmation: Optional[bool] = None,
    ) -> ToolBox:
        """Get search toolbox for entities to pass into an Agent.

        Parameters
        ----------
        collection_names
            Which collection names to expose tools for; None => all.
        search_configs
            Names of the search_configs to expose. If set to None, all search_configs are exposed as tools.
        k
            Number of results to return for search tools (will be fixed, not changeable by Agent).
            It is only configurable by the user as `k` heavily impacts speed and cost: searching for more leads to more being put in the context of the next LLM call.
        requires_confirmation:
            Flag to ask for user confirmation whenever executing any of this toolbox's tools, yields ``ToolExecutionConfirmationStatus`` if True or if the ``Tool`` from the ``ToolBox`` requires confirmation.

        Returns
        -------
        ToolBox
            A toolbox containing search tools for the specified collections.
        """
        from wayflowcore.search.toolbox import SearchToolBox

        return SearchToolBox(
            datastore=self,
            collection_names=collection_names,
            search_configs=search_configs,
            k=k,
            requires_confirmation=requires_confirmation,
        )

    def get_search_tools(
        self,
        collection_names: Optional[List[str]] = None,
        search_configs: Optional[List[str]] = None,
        k: int = _DEFAULT_K,
        requires_confirmation: Optional[bool] = None,
    ) -> Sequence[Tool]:
        """Get search tools for entities to pass into an Agent.

        Parameters
        ----------
        collection_names
            Which collection names to expose tools for; None => all.
        k
            Number of results to return for search tools (will be fixed, not changeable by Agent).
            It is only configurable by the user as `k` heavily impacts speed and cost: searching for more leads to more being put in the context of the next LLM call.
        requires_confirmation:
            Flag to ask for user confirmation whenever executing any of this toolbox's tools, yields ``ToolExecutionConfirmationStatus`` if True or if the ``Tool`` from the ``ToolBox`` requires confirmation.

        Returns
        -------
        List[Tool]
            A list containing search tools for the specified collections.
        """
        toolbox = self.get_search_toolbox(
            collection_names, search_configs, k, requires_confirmation
        )
        return toolbox.get_tools()

    def _build_config_maps(self) -> None:
        """Build lookup maps for search and vector configurations.

        Creates lookup dictionaries for search and vector configs by name.
        Auto-generates names for configs without explicit names based on their
        target collections.
        """
        # Build search config map
        for i, search_config in enumerate(self.search_configs):
            if not search_config.name:
                # Auto-generate name based on collection if possible
                if search_config.retriever.collection_name:
                    # Specific collection
                    search_config.name = f"search_{search_config.retriever.collection_name}"
                else:
                    # Applies to all collections. Uses first collection name if only one exists
                    if len(self.schema) == 1:
                        collection_name = list(self.schema.keys())[0]
                        search_config.name = f"search_{collection_name}"
                    else:
                        search_config.name = f"search_config_{i}"

            if search_config.name in self._search_config_map:
                raise ValueError(f"Duplicate Search Config name given: {search_config.name}")
            self._search_config_map[search_config.name] = search_config

        # Build vector config map
        for i, vector_config in enumerate(self.vector_configs):
            if not vector_config.name:
                # Auto-generate name based on collection
                if vector_config.collection_name:
                    vector_config.name = f"vector_{vector_config.collection_name}_{i}"
                else:
                    vector_config.name = f"vector_config_{i}"

            if vector_config.name in self._vector_config_map:
                raise ValueError(f"Duplicate Vector Config name given: {vector_config.name}")
            self._vector_config_map[vector_config.name] = vector_config

    def _find_default_search_config(self, collection_name: str) -> Optional[SearchConfig]:
        """Find the default search configuration for a collection.

        The default search configuration is determined by the following priority order:

        1. **Explicit collection match**: A SearchConfig where the retriever's
        collection_name exactly matches the requested collection_name.

        2. **Universal config**: A SearchConfig where the retriever's collection_name
        is empty or None, indicating it applies to all collections.

        """
        matching_configs = []
        # Look for configs that explicitly target this collection
        for config in self.search_configs:
            if config.retriever.collection_name:
                if config.retriever.collection_name == collection_name:
                    matching_configs.append(config)

        if len(matching_configs) >= 1:
            if len(matching_configs) > 1:
                logger.warning(
                    f"Found multiple search configs for collection {collection_name}, returning one out of these."
                    f"This can lead to unexpected behaviour, specify the search_config to use if you want a fixed behaviour."
                )

            # Try to return the best "default", by returning a config which has vector column mentioned.
            for config in matching_configs:
                if config.retriever.vectors:
                    return config
            return matching_configs[0]

        # Look for configs without specific collection (apply to all)
        for config in self.search_configs:
            if not config.retriever.collection_name:
                return config

        return None

    def _get_first_vector_property_name(self, collection_name: str) -> str:
        """
        Shared logic for retrieving the vector property name for a collection.
        Calls a subclass hook if not found.
        """
        for config in self.vector_configs:
            if config.collection_name and config.collection_name == collection_name:
                if config.vector_property:
                    return config.vector_property
        entity = self.schema[collection_name]
        for prop_name, prop in entity.properties.items():
            from wayflowcore.property import VectorProperty

            if isinstance(prop, VectorProperty):
                return prop_name
        return self._handle_vector_property_name_not_found(collection_name)

    def _handle_vector_property_name_not_found(self, collection_name: str) -> str:
        """
        Subclass hook for when no vector property is found.
        Should be overridden by Datastore implementations.
        """
        raise NotImplementedError()

    def _find_vector_config_name_for_search(
        self, retriever: "VectorRetrieverConfig", collection_name: str
    ) -> Optional[str]:
        """
        Shared logic for finding the vector configuration to use for search.
        Calls a subclass hook if no config is found.
        """
        if retriever.vectors:
            if isinstance(retriever.vectors, VectorConfig):
                return retriever.vectors.name

        matching_configs = []
        for config in self.vector_configs:
            if config.collection_name and config.collection_name == collection_name:
                if not (
                    config.vector_property
                    and retriever.vectors
                    and config.vector_property != retriever.vectors
                ):
                    matching_configs.append(config)
            elif (
                config.vector_property
                and retriever.vectors
                and (not config.collection_name)
                and config.vector_property == retriever.vectors
            ):
                matching_configs.append(config)
        if len(matching_configs) == 1:
            return matching_configs[0].name
        elif len(matching_configs) == 0:
            implicit_name = f"vector_{collection_name}"
            if implicit_name in self._vector_config_map:
                return implicit_name
            return self._handle_no_matching_vector_config(collection_name, retriever)
        else:
            raise ValueError(
                f"Multiple vector configs found for collection '{collection_name}', please specify which to use"
            )

    def _handle_no_matching_vector_config(
        self, collection_name: str, retriever: "VectorRetrieverConfig"
    ) -> Optional[str]:
        """
        Subclass hook for when there are no matching vector configs for a collection.
        Should be overridden by Datastore implementations.
        """
        raise NotImplementedError()

    def _find_vector_config_from_name(
        self, vector_config_name: Optional[str], collection_name: Optional[str] = None
    ) -> Optional[VectorConfig]:
        """
        Subclass hook for finding VectorConfig from a vector config name.
        Should be overridden by Datastore implementations.
        """
        raise NotImplementedError()

    def _get_first_embedding_model(
        self,
        collection_name: str,
        vector_config: Optional[VectorConfig] = None,
        search_config: Optional[SearchConfig] = None,
    ) -> Optional[EmbeddingModel]:
        """Get the embedding model for a collection from search configurations."""

        if (
            vector_config
            and vector_config.model
            and search_config
            and search_config.retriever.model
        ):
            if vector_config.model != search_config.retriever.model:
                warnings.warn(
                    "Different Embedding Models found in Vector and Search configs."
                    f"Found model {vector_config.model} in Vector Config {vector_config} and"
                    f"found model {search_config.retriever.model} in Search Config {search_config}."
                    f"Using model provided in Vector Config: {vector_config.model}."
                )

            return vector_config.model

        if vector_config and vector_config.model:
            return vector_config.model

        if search_config and search_config.retriever.model:
            return search_config.retriever.model

        for config in self.search_configs:
            if config.retriever.model:
                retriever = config.retriever
                if not retriever.collection_name or retriever.collection_name == collection_name:
                    return retriever.model

        return None
