# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any

from pyagentspec.component import Component as AgentSpecComponent
from pyagentspec.serialization import ComponentDeserializationPlugin, ComponentSerializationPlugin

from wayflowcore.serialization.plugins import (
    ToolRegistryT,
    WayflowDeserializationPlugin,
    WayflowSerializationPlugin,
)
from wayflowcore.serialization.serializer import SerializableObject


def make_serialization_plugin(
    classes: list[type[SerializableObject]],
    name: str = "MyDeserializationPlugin",
    version: str = "1.0.0",
) -> WayflowSerializationPlugin:

    class MySerializationPlugin(WayflowSerializationPlugin):

        @property
        def plugin_name(self) -> str:
            return name

        @property
        def plugin_version(self) -> str:
            return version

        @property
        def supported_component_types(self) -> list[str]:
            return [class_.__name__ for class_ in classes]

        @property
        def required_agentspec_serialization_plugins(self) -> list[ComponentSerializationPlugin]:
            raise NotImplementedError()

        def convert_to_agentspec(
            self,
            conversion_context: "WayflowToAgentSpecConversionContext",
            runtime_component: "SerializableObject",
            referenced_objects: dict[str, AgentSpecComponent],
        ) -> AgentSpecComponent:
            raise NotImplementedError()

    return MySerializationPlugin()


def make_deserialization_plugin(
    classes: list[type[SerializableObject]],
    name: str = "MyDeserializationPlugin",
    version: str = "1.0.0",
) -> WayflowDeserializationPlugin:

    class MyDeserializationPlugin(WayflowDeserializationPlugin):

        @property
        def plugin_name(self) -> str:
            return name

        @property
        def plugin_version(self) -> str:
            return version

        @property
        def supported_component_types(self) -> list[str]:
            return [class_.__name__ for class_ in classes]

        @property
        def required_agentspec_deserialization_plugins(
            self,
        ) -> list[ComponentDeserializationPlugin]:
            raise NotImplementedError()

        def convert_to_wayflow(
            self,
            conversion_context: "AgentSpecToWayflowConversionContext",
            agentspec_component: AgentSpecComponent,
            tool_registry: ToolRegistryT,
            converted_components: dict[str, Any],
        ) -> Any:
            raise NotImplementedError()

    return MyDeserializationPlugin()
