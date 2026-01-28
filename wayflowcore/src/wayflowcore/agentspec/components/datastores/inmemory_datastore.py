# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Dict, List

from pydantic import Field

from wayflowcore.agentspec.components.datastores.datastore import PluginDatastore
from wayflowcore.agentspec.components.datastores.entity import PluginEntity
from wayflowcore.agentspec.components.search import PluginSearchConfig, PluginVectorConfig


class PluginInMemoryDatastore(PluginDatastore):
    """In-memory datastore for testing and development purposes."""

    # "schema" is a special field for Pydantic, so use the prefix "datastore_" to avoid clashes
    datastore_schema: Dict[str, PluginEntity]
    """Mapping of collection names to entity definitions used by this datastore."""
    search_configs: List[PluginSearchConfig] = Field(default_factory=list)
    vector_configs: List[PluginVectorConfig] = Field(default_factory=list)
