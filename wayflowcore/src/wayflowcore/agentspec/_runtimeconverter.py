# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

from pyagentspec.component import Component as AgentSpecComponent
from pyagentspec.serialization.builtinsdeserializationplugin import (
    BuiltinsComponentDeserializationPlugin,
)

from wayflowcore.tools import ServerTool as RuntimeServerTool

if TYPE_CHECKING:
    from wayflowcore.serialization.plugins import WayflowDeserializationPlugin


class AgentSpecToWayflowConversionContext:

    def __init__(self, plugins: Optional[List["WayflowDeserializationPlugin"]] = None):
        from wayflowcore.serialization._builtins_deserialization_plugin import (
            WayflowBuiltinsDeserializationPlugin,
        )

        self.plugins = plugins or []
        # If none of the given plugins is the builtins one, we automatically add it
        if not any(
            isinstance(plugin, WayflowBuiltinsDeserializationPlugin) for plugin in self.plugins
        ):
            self.plugins.append(WayflowBuiltinsDeserializationPlugin())

        # Create a mapping cache of component_type -> plugin mappings
        # to know what plugin to use to convert a given component
        self.component_types_to_plugins: Dict[str, "WayflowDeserializationPlugin"] = {}
        for plugin in self.plugins:
            agentspec_supported_component_types = [
                supported_component_type
                for agentspec_plugin in plugin.required_agentspec_deserialization_plugins
                for supported_component_type in agentspec_plugin.supported_component_types()
            ]
            # The builtins plugin also handles all the builtins components of agentspec
            if plugin.plugin_name == "WayflowBuiltins":
                agentspec_supported_component_types.extend(
                    BuiltinsComponentDeserializationPlugin().supported_component_types()
                )
            for component_type in agentspec_supported_component_types:
                if component_type not in self.component_types_to_plugins:
                    self.component_types_to_plugins[component_type] = plugin
                else:
                    raise ValueError(
                        f"Two plugins, `{plugin.plugin_name}` and "
                        f"`{self.component_types_to_plugins[component_type].plugin_name}`, have "
                        f"component types with the same name: `{component_type}`"
                    )

    def convert(
        self,
        agentspec_component: AgentSpecComponent,
        tool_registry: Dict[str, Union[RuntimeServerTool, Callable[..., Any]]],
        converted_components: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Convert the given PyAgentSpec component object into the corresponding Runtime component"""
        if converted_components is None:
            converted_components = {}

        if agentspec_component.id not in converted_components:

            # Get the plugin to use for loading if there is one
            component_type = agentspec_component.component_type
            plugin: Optional[WayflowDeserializationPlugin] = self.component_types_to_plugins.get(  # type: ignore
                component_type, None
            )

            # Load with a plugin if there is one, otherwise raise an error
            if plugin is not None:
                converted_components[agentspec_component.id] = plugin.convert_to_wayflow(
                    conversion_context=self,
                    agentspec_component=agentspec_component,
                    tool_registry=tool_registry,
                    converted_components=converted_components,
                )
            else:
                raise ValueError(
                    f"There is no plugin to convert the component type {component_type}"
                )

        return converted_components[agentspec_component.id]
