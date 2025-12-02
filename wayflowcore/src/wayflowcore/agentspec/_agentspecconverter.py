# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from pyagentspec.component import Component as AgentSpecComponent

from wayflowcore.component import Component

if TYPE_CHECKING:
    from wayflowcore.serialization.plugins import WayflowSerializationPlugin
    from wayflowcore.serialization.serializer import SerializableObject


def _get_obj_reference(obj: Any) -> str:
    return f"{obj.__class__.__name__.lower()}/{obj.id}"


class WayflowToAgentSpecConversionContext:

    def __init__(self, plugins: Optional[List["WayflowSerializationPlugin"]] = None):
        from wayflowcore.serialization._builtins_serialization_plugin import (
            WayflowBuiltinsSerializationPlugin,
        )
        from wayflowcore.serialization.context import _create_component_type_to_plugin_mapping

        self.plugins = plugins or []
        # If none of the given plugins is the builtins one, we automatically add it
        if not any(
            isinstance(plugin, WayflowBuiltinsSerializationPlugin) for plugin in self.plugins
        ):
            self.plugins.append(WayflowBuiltinsSerializationPlugin())

        # Create a mapping cache of component_type -> plugin mappings
        # to know what plugin to use to convert a given component
        self.component_types_to_plugins: Dict[str, "WayflowSerializationPlugin"] = cast(
            Dict[str, "WayflowSerializationPlugin"],
            _create_component_type_to_plugin_mapping(self.plugins),
        )

    def convert(
        self,
        runtime_component: "SerializableObject",
        referenced_objects: Optional[Dict[str, AgentSpecComponent]] = None,
    ) -> AgentSpecComponent:
        """Convert the given WayFlow component object into the corresponding PyAgentSpec component"""

        if referenced_objects is None:
            referenced_objects = dict()

        # Reuse the same object multiple times in order to exploit the referencing system
        # If it is not a component, referencing will not be used
        object_reference = (
            _get_obj_reference(runtime_component)
            if isinstance(runtime_component, Component)
            else None
        )
        if not object_reference or object_reference not in referenced_objects:
            # Get the plugin to use for loading if there is one
            component_type = runtime_component.__class__.__name__
            plugin: Optional[WayflowSerializationPlugin] = self.component_types_to_plugins.get(
                component_type, None
            )

            # Load with a plugin if there is one, otherwise raise an error
            if plugin is not None:
                converted_component = plugin.convert_to_agentspec(
                    conversion_context=self,
                    runtime_component=runtime_component,
                    referenced_objects=referenced_objects,
                )
            else:
                raise ValueError(
                    f"There is no plugin to convert the component type {component_type}"
                )

            if not object_reference:
                return converted_component

            referenced_objects[object_reference] = converted_component

        return referenced_objects[object_reference]
