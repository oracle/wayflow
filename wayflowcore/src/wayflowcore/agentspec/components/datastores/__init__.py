# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)

from .inmemory_datastore import PluginInMemoryDatastore
from .oracle_datastore import PluginOracleDatabaseDatastore

SEARCH_DATASTORE_PLUGIN_NAME = "SearchDatastorePlugin"

search_datastore_serialization_plugin = PydanticComponentSerializationPlugin(
    name=SEARCH_DATASTORE_PLUGIN_NAME,
    component_types_and_models={
        PluginInMemoryDatastore.__name__: PluginInMemoryDatastore,
        PluginOracleDatabaseDatastore.__name__: PluginOracleDatabaseDatastore,
    },
)
search_datastore_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=SEARCH_DATASTORE_PLUGIN_NAME,
    component_types_and_models={
        PluginInMemoryDatastore.__name__: PluginInMemoryDatastore,
        PluginOracleDatabaseDatastore.__name__: PluginOracleDatabaseDatastore,
    },
)

__all__ = [
    "PluginInMemoryDatastore",
    "PluginOracleDatabaseDatastore",
    "search_datastore_serialization_plugin",
    "search_datastore_deserialization_plugin",
]
