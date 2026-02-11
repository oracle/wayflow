# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import List

from pyagentspec.datastores import OracleDatabaseDatastore
from pydantic import Field

from wayflowcore.agentspec.components.search import PluginSearchConfig, PluginVectorConfig


class PluginOracleDatabaseDatastore(OracleDatabaseDatastore):
    """
    Datastore that uses Oracle Database as the storage mechanism with
    additional configurations for search."""

    search_configs: List[PluginSearchConfig] = Field(default_factory=list)
    vector_configs: List[PluginVectorConfig] = Field(default_factory=list)
