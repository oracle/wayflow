# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)
from wayflowcore.agentspec.components.datastores import *
from wayflowcore.agentspec.components.datastores.nodes import *

DATASTORE_PLUGIN_NAME = "DatastorePlugin"

wayflowcore_datastore_serialization_plugin = PydanticComponentSerializationPlugin(
    name=DATASTORE_PLUGIN_NAME,
    component_types_and_models={
        PluginEntity.__name__: PluginEntity,
        PluginDatastore.__name__: PluginDatastore,
        PluginInMemoryDatastore.__name__: PluginInMemoryDatastore,
        PluginOracleDatabaseDatastore.__name__: PluginOracleDatabaseDatastore,
        PluginTlsOracleDatabaseConnectionConfig.__name__: PluginTlsOracleDatabaseConnectionConfig,
        PluginMTlsOracleDatabaseConnectionConfig.__name__: PluginMTlsOracleDatabaseConnectionConfig,
        PluginPostgresDatabaseDatastore.__name__: PluginPostgresDatabaseDatastore,
        PluginTlsPostgresDatabaseConnectionConfig.__name__: PluginTlsPostgresDatabaseConnectionConfig,
        PluginDatastoreCreateNode.__name__: PluginDatastoreCreateNode,
        PluginDatastoreDeleteNode.__name__: PluginDatastoreDeleteNode,
        PluginDatastoreListNode.__name__: PluginDatastoreListNode,
        PluginDatastoreQueryNode.__name__: PluginDatastoreQueryNode,
        PluginDatastoreUpdateNode.__name__: PluginDatastoreUpdateNode,
    },
)


wayflowcore_datastore_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=DATASTORE_PLUGIN_NAME,
    component_types_and_models={
        PluginEntity.__name__: PluginEntity,
        PluginDatastore.__name__: PluginDatastore,
        PluginInMemoryDatastore.__name__: PluginInMemoryDatastore,
        PluginOracleDatabaseDatastore.__name__: PluginOracleDatabaseDatastore,
        PluginTlsOracleDatabaseConnectionConfig.__name__: PluginTlsOracleDatabaseConnectionConfig,
        PluginMTlsOracleDatabaseConnectionConfig.__name__: PluginMTlsOracleDatabaseConnectionConfig,
        PluginPostgresDatabaseDatastore.__name__: PluginPostgresDatabaseDatastore,
        PluginTlsPostgresDatabaseConnectionConfig.__name__: PluginTlsPostgresDatabaseConnectionConfig,
        PluginDatastoreCreateNode.__name__: PluginDatastoreCreateNode,
        PluginDatastoreDeleteNode.__name__: PluginDatastoreDeleteNode,
        PluginDatastoreListNode.__name__: PluginDatastoreListNode,
        PluginDatastoreQueryNode.__name__: PluginDatastoreQueryNode,
        PluginDatastoreUpdateNode.__name__: PluginDatastoreUpdateNode,
    },
)
