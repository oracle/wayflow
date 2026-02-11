# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List, Optional, Union

from pyagentspec import Component
from pyagentspec.datastores import Datastore
from pydantic import Field

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)
from wayflowcore.agentspec.components.embeddingmodels import PluginEmbeddingConfig
from wayflowcore.agentspec.components.tools import PluginToolBox


class PluginSearchToolBox(PluginToolBox):
    collection_names: Optional[List[str]]
    k: int
    datastore: Datastore
    search_configs: Optional[List[str]]


class PluginVectorRetrieverConfig(Component):
    vectors: Optional[Union[str, "PluginVectorConfig"]]
    model: Optional[PluginEmbeddingConfig]
    collection_name: Optional[str]
    distance_metric: str
    index_params: Dict[str, Any] = Field(default_factory=dict)


class PluginSearchConfig(Component):
    retriever: PluginVectorRetrieverConfig
    name: str


class PluginVectorConfig(Component):
    model: Optional[PluginEmbeddingConfig]
    collection_name: Optional[str]
    vector_property: Optional[str]
    name: str


SEARCH_PLUGIN_NAME = "SearchPlugin"

search_serialization_plugin = PydanticComponentSerializationPlugin(
    name=SEARCH_PLUGIN_NAME,
    component_types_and_models={
        PluginSearchToolBox.__name__: PluginSearchToolBox,
        PluginSearchConfig.__name__: PluginSearchConfig,
        PluginVectorRetrieverConfig.__name__: PluginVectorRetrieverConfig,
        PluginVectorConfig.__name__: PluginVectorConfig,
    },
)
search_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=SEARCH_PLUGIN_NAME,
    component_types_and_models={
        PluginSearchToolBox.__name__: PluginSearchToolBox,
        PluginSearchConfig.__name__: PluginSearchConfig,
        PluginVectorRetrieverConfig.__name__: PluginVectorRetrieverConfig,
        PluginVectorConfig.__name__: PluginVectorConfig,
    },
)
