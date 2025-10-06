# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from wayflowcore.agentspec.components.datastores.nodes import PluginDatastoreCreateNode


def test_plugin_datastore_create_node_can_be_partially_constructed() -> None:
    partial_config = {
        "component_type": "PluginDatastoreCreateNode",
        "metadata": {"__studio__": {"expanded": True, "position_x": -1458.5, "position_y": -955.0}},
        "name": "fancy_name",
    }
    plugin_component = PluginDatastoreCreateNode.build_from_partial_config(partial_config)
    assert isinstance(plugin_component, PluginDatastoreCreateNode)
    assert plugin_component.name == "fancy_name"
