# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import functools
import inspect
from logging import getLogger
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.async_helpers import run_async_in_sync
from wayflowcore.component import Component
from wayflowcore.datastore._utils import check_collection_name
from wayflowcore.datastore.datastore import _DEFAULT_K
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.property import Property
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject, serialize_to_dict
from wayflowcore.tools import Tool, ToolBox
from wayflowcore.tools.servertools import ServerTool
from wayflowcore.tools.toolfromtoolbox import ToolFromToolBox

if TYPE_CHECKING:
    from wayflowcore.datastore.datastore import Datastore
    from wayflowcore.search.config import SearchConfig

logger = getLogger(__name__)

_TOOL_DESCRIPTION_TEMPLATE = """Search for {entity_desc} in the database using semantic similarity.

This tool searches the {name} collection for entities that match the given query.
It returns exactly {k} matching records with their properties and similarity scores.
Use this tool when you need to find information about {entity_desc}.

Parameters
----------
query : str
    The search query string to find relevant {entity_desc}.
"""


class SearchToolBox(ToolBox, Component, SerializableObject):
    """ToolBox implementation for In-Memory and Oracle Database Datastore search tools.

    All generated search tools are named with the prefix "search_" followed by the collection
    name and the search config name if given (for example, "search_users_config2").
    """

    def __init__(
        self,
        datastore: "Datastore",
        collection_names: Optional[List[str]] = None,
        search_configs: Optional[List[str]] = None,
        k: int = _DEFAULT_K,
        requires_confirmation: Optional[bool] = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """Initialize with datastore reference and search parameters.

        Parameters
        ----------
        datastore
            The datastore instance to create search tools from.
        collection_names
            Which collection names to expose tools for; None => all.
        search_configs
            Search Configs to make tools for.
            If a search config is linked to a collection name, that search config will be used for the collection.
            If two search configs are given for a collection name, both of them are made into tools.
            If a search config is not linked to any collection, all collections in ``collection_names`` get this search config.
            If no search config is given for a collection, a default search configuration is inferred for that collection.
        k
            Number of results to return for search tools.
        requires_confirmation:
            Flag to ask for user confirmation whenever executing any of this toolbox's tools, yields ``ToolExecutionConfirmationStatus`` if True or if the ``Tool`` from the ``ToolBox`` requires confirmation.
        """
        self._datastore = datastore
        self._collection_names = collection_names
        self._search_configs = search_configs
        self._k = k
        self._tool_name_prefix = "search_"
        self._tool_name_sep = "_"
        self._tool_registry: Dict[str, Tuple[str, Optional[str]]] = dict()
        super().__init__(requires_confirmation=requires_confirmation)
        Component.__init__(
            self,
            id=id,
            name=IdGenerator.get_or_generate_name(
                name, prefix=self._tool_name_prefix + "toolbox", length=8
            ),
            description=description,
            __metadata_info__=__metadata_info__,
        )
        self.get_tools()  # Run once to populate tool registry. Will rebuild tools for each call so this does not change behaviour.

    async def _get_tools_inner_async(self) -> Sequence[Tool]:
        # Regenerate tools on each call to support dynamic behavior
        collection_names = self._collection_names or list(self._datastore.schema.keys())
        search_configs = self._search_configs or []
        tools = []
        collection_names_found = set()
        for config_name in search_configs:
            search_config = self._datastore._search_config_map.get(config_name, None)
            if not search_config:
                logger.warning(
                    f"No Search Config found with name: {config_name}, skipping this Search Config"
                )
                continue

            if search_config.retriever.collection_name:
                if search_config.retriever.collection_name not in collection_names:
                    raise ValueError(
                        f"Invalid collection name given for creating ToolFromToolBox: {search_config.retriever.collection_name}"
                    )

                check_collection_name(
                    self._datastore.schema, search_config.retriever.collection_name
                )
                collection_names_found.add(search_config.retriever.collection_name)

                tool_name = (
                    self._tool_name_prefix
                    + search_config.retriever.collection_name
                    + self._tool_name_sep
                    + config_name
                )
                self._tool_registry[tool_name] = (
                    search_config.retriever.collection_name,
                    config_name,
                )
                tools.append(ToolFromToolBox(tool_name=tool_name, toolbox=self))
            else:
                # No collection name for search config means that it is applicable to all collections
                for collection_name in collection_names:
                    if collection_name not in list(self._datastore.schema.keys()):
                        logger.warning(
                            f"Did not find collection_name {collection_name} in Datastore, skipping search tools for this collection name"
                        )
                        continue
                    check_collection_name(self._datastore.schema, collection_name)
                    collection_names_found.add(collection_name)
                    tool_name = (
                        self._tool_name_prefix + collection_name + self._tool_name_sep + config_name
                    )
                    self._tool_registry[tool_name] = (collection_name, config_name)
                    tools.append(ToolFromToolBox(tool_name=tool_name, toolbox=self))

        for name in collection_names:
            if name in collection_names_found:
                continue

            if name not in list(self._datastore.schema.keys()):
                logger.warning(
                    f"Did not find collection_name {name} in Datastore, skipping search tools for this collection name"
                )
                continue

            check_collection_name(self._datastore.schema, name)
            search_config = self._find_search_config(name, None)

            tool_name = self._tool_name_prefix + name
            if search_config.name:
                self._tool_registry[tool_name + self._tool_name_sep + search_config.name] = (
                    name,
                    search_config.name,
                )
                tools.append(
                    ToolFromToolBox(
                        tool_name=tool_name + self._tool_name_sep + search_config.name, toolbox=self
                    )
                )
            else:
                self._tool_registry[tool_name] = (name, None)
                tools.append(ToolFromToolBox(tool_name=tool_name, toolbox=self))

        return tools

    def _get_tools_inner(self) -> Sequence[Tool]:
        """Return the list of search tools.

        This method dynamically generates tools on each call, allowing
        the toolbox to adapt to datastore changes.

        Returns
        -------
        Sequence of search tools exposed by this toolbox.
        """
        return run_async_in_sync(self.get_tools_async)

    def _find_search_config(
        self, collection_name: str, search_config_name: Optional[str]
    ) -> "SearchConfig":
        if search_config_name:
            search_config = self._datastore._search_config_map.get(search_config_name, None)
            if not search_config:
                raise ValueError(
                    f"No Search Config found for Search Config name: {search_config_name}"
                )
            return search_config
        else:
            search_config = self._datastore._find_default_search_config(collection_name)
            if not search_config:
                raise ValueError(
                    f"No Search Config found for given collection_name: {collection_name}"
                )
            return search_config

    def _get_concrete_tool(self, tool_name: str) -> ServerTool:
        collection_name, config_name = self._tool_registry[tool_name]
        collection_names = self._collection_names or list(self._datastore.schema.keys())
        search_configs = self._search_configs or []
        if config_name not in search_configs and collection_name not in collection_names:
            raise ValueError(
                f"Invalid SearchConfig and collection name given for creating ToolFromToolBox: {config_name, collection_name}"
            )

        check_collection_name(self._datastore.schema, collection_name)
        search_config = self._find_search_config(collection_name, config_name)

        # Get entity description
        entity = self._datastore.schema[collection_name]
        entity_desc = entity.description or collection_name

        # Create search function for this collection
        search_func = self._create_search_function(
            collection_name,
            search_config.name if search_config else None,
            self._k,
        )
        # Use only_docstring mode to avoid issues with Any type in return annotation
        tool_name = tool_name or (
            f"search_{collection_name}{self._tool_name_sep}{config_name}"
            if config_name
            else f"search_{collection_name}"
        )
        tool_description = _TOOL_DESCRIPTION_TEMPLATE.format(
            entity_desc=entity_desc, name=collection_name, k=self._k
        )

        concrete_search_tool = self._make_tool(
            search_func, tool_name=tool_name, tool_description=tool_description
        )
        return concrete_search_tool

    def _make_tool(
        self,
        func: Callable[..., Any],
        tool_name: str,
        tool_description: str,
        output_descriptors: Optional[List[Property]] = None,
    ) -> ServerTool:
        from wayflowcore.tools.toolhelpers import _get_tool_schema_no_parsing

        if inspect.isclass(func) or not hasattr(func, "__name__"):
            raise TypeError(
                f"Input callable type is not supported, callable is of of type `{func.__class__.__name__}`"
            )

        signature = inspect.signature(func)
        # Exclude the 'datastore' parameter
        new_signature = signature.replace(
            parameters=[p for p in signature.parameters.values() if p.name != "datastore"]
        )

        args_schema, output_schema = _get_tool_schema_no_parsing(
            new_signature, tool_description, tool_name
        )

        copy_func = functools.partial(func, self._datastore)
        functools.update_wrapper(copy_func, func)

        return ServerTool(
            name=tool_name,
            description=tool_description,
            parameters=args_schema,
            output_descriptors=output_descriptors,
            output=output_schema if output_descriptors is None else None,
            func=copy_func,
        )

    def _create_search_function(
        self,
        coll_name: str,
        config_name: Optional[str] = None,
        return_results_k: int = _DEFAULT_K,
    ) -> Callable[..., Any]:
        """Create a search function for a specific collection."""

        def search_collection(
            datastore: "Datastore",
            query: str,
            columns_to_exclude: Optional[List[str]] = None,
        ) -> List[Dict[str, str]]:
            """
            Search function to retrieve results for a query from a Datastore
            """

            # Get raw results from datastore
            results = datastore.search(
                collection_name=coll_name,
                query=query,
                search_config=config_name,
                k=return_results_k,
                columns_to_exclude=columns_to_exclude,
            )

            return results

        return search_collection

    def _serialize_to_dict(self, serialization_context: SerializationContext) -> Dict[str, Any]:
        """Serialize the SearchToolBox to a dictionary.

        Note: We serialize the configuration, not the actual tools or datastore.
        """
        return {
            "_component_type": "SearchToolBox",
            "collection_names": self._collection_names,
            "k": self._k,
            "datastore": serialize_to_dict(self._datastore, serialization_context),
            "search_configs": self._search_configs,
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: DeserializationContext
    ) -> "SearchToolBox":
        """Deserialize a SearchToolBox from a dictionary."""
        from wayflowcore.serialization.serializer import autodeserialize_any_from_dict

        instance = cls.__new__(cls)
        instance._collection_names = input_dict.get("collection_names", None)
        instance._search_configs = input_dict.get("search_configs", None)
        instance._k = input_dict.get("k", _DEFAULT_K)
        datastore: "Datastore"
        datastore = autodeserialize_any_from_dict(
            input_dict.get("datastore"), deserialization_context
        )
        instance._datastore = datastore
        SerializableObject.__init__(instance, None)

        return instance
