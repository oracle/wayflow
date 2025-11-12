# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from wayflowcore.agentspec.components import ExtendedMapNode, all_deserialization_plugin


def test_extended_map_node_can_be_partially_constructed() -> None:
    partial_config = {
        "component_type": "ExtendedMapNode",
        "metadata": {"__studio__": {"expanded": True, "position_x": -77.0, "position_y": -443.5}},
        "name": "fancy_name",
    }
    plugin_component = ExtendedMapNode.build_from_partial_config(
        partial_config, plugins=all_deserialization_plugin
    )
    assert isinstance(plugin_component, ExtendedMapNode)
    assert plugin_component.name == "fancy_name"
