# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)

from .datastorecreatenode import PluginDatastoreCreateNode
from .datastoredeletenode import PluginDatastoreDeleteNode
from .datastorelistnode import PluginDatastoreListNode
from .datastorequerynode import PluginDatastoreQueryNode
from .datastoreupdatenode import PluginDatastoreUpdateNode

DATASTORE_NODES_PLUGIN_NAME = "DatastoreNodesPlugin"

datastore_nodes_serialization_plugin = PydanticComponentSerializationPlugin(
    name=DATASTORE_NODES_PLUGIN_NAME,
    component_types_and_models={
        PluginDatastoreCreateNode.__name__: PluginDatastoreCreateNode,
        PluginDatastoreDeleteNode.__name__: PluginDatastoreDeleteNode,
        PluginDatastoreListNode.__name__: PluginDatastoreListNode,
        PluginDatastoreQueryNode.__name__: PluginDatastoreQueryNode,
        PluginDatastoreUpdateNode.__name__: PluginDatastoreUpdateNode,
    },
)
datastore_nodes_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=DATASTORE_NODES_PLUGIN_NAME,
    component_types_and_models={
        PluginDatastoreCreateNode.__name__: PluginDatastoreCreateNode,
        PluginDatastoreDeleteNode.__name__: PluginDatastoreDeleteNode,
        PluginDatastoreListNode.__name__: PluginDatastoreListNode,
        PluginDatastoreQueryNode.__name__: PluginDatastoreQueryNode,
        PluginDatastoreUpdateNode.__name__: PluginDatastoreUpdateNode,
    },
)

__all__ = [
    "PluginDatastoreCreateNode",
    "PluginDatastoreDeleteNode",
    "PluginDatastoreListNode",
    "PluginDatastoreQueryNode",
    "PluginDatastoreUpdateNode",
    "datastore_nodes_serialization_plugin",
    "datastore_nodes_deserialization_plugin",
]
