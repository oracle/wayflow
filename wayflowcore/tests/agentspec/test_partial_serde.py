# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import pytest
from pyagentspec.serialization import AgentSpecDeserializer, AgentSpecSerializer

from wayflowcore.agentspec.components import all_deserialization_plugin, all_serialization_plugin
from wayflowcore.agentspec.components.flow import ExtendedFlow


def test_serde_of_partially_configured_components_works_with_wayflow_plugins():
    incomplete_extended_flow_dict = {"component_type": "ExtendedFlow", "name": "Foo"}

    deserializer = AgentSpecDeserializer(plugins=all_deserialization_plugin)
    with pytest.warns(
        UserWarning, match="Missing `agentspec_version` field at the top level of the configuration"
    ):
        component, errors = deserializer.from_partial_dict(incomplete_extended_flow_dict)
    assert isinstance(component, ExtendedFlow)
    assert component.name == "Foo"

    serializer = AgentSpecSerializer(
        _allow_partial_model_serialization=True, plugins=all_serialization_plugin
    )
    partial_component_yaml = serializer.to_yaml(component)
    assert "component_type: ExtendedFlow" in partial_component_yaml
    assert "component_plugin_name: FlowPlugin" in partial_component_yaml
    assert "name: Foo" in partial_component_yaml
