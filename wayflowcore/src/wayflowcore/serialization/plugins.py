# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import re
import warnings
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, List

from pyagentspec.component import Component as AgentSpecComponent
from pyagentspec.serialization import ComponentDeserializationPlugin, ComponentSerializationPlugin
from pyagentspec.versioning import _version_lt
from typing_extensions import TypeAlias

from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.tools import ServerTool as RuntimeServerTool

if TYPE_CHECKING:
    from wayflowcore.agentspec._agentspecconverter import WayflowToAgentSpecConversionContext
    from wayflowcore.agentspec._runtimeconverter import AgentSpecToWayflowConversionContext
    from wayflowcore.serialization.serializer import SerializableObject


_COMPONENT_PLUGIN_NAME_FIELD = "component_plugin_name"
_COMPONENT_PLUGIN_VERSION_FIELD = "component_plugin_version"


ToolRegistryT: TypeAlias = dict[str, RuntimeServerTool | Callable[..., Any]]


class WayflowSerializationPlugin(ABC):
    """Base class for a Wayflow Plugin."""

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """Return the plugin name."""

    @property
    @abstractmethod
    def plugin_version(self) -> str:
        """Return the plugin version."""

    @property
    @abstractmethod
    def required_agentspec_serialization_plugins(self) -> List[ComponentSerializationPlugin]:
        """Indicate what Agent Spec serialization plugins are required for this WayFlow converter"""

    @property
    @abstractmethod
    def supported_component_types(self) -> List[str]:
        """Indicate what component types the plugin supports."""

    def serialize(
        self, obj: "SerializableObject", serialization_context: SerializationContext
    ) -> Dict[str, Any]:
        """Serialize a component that the plugin should support."""
        obj_dict = obj._serialize_to_dict(serialization_context)
        obj_dict[_COMPONENT_PLUGIN_NAME_FIELD] = self.plugin_name
        obj_dict[_COMPONENT_PLUGIN_VERSION_FIELD] = self.plugin_version
        return obj_dict

    @abstractmethod
    def convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_component: "SerializableObject",
        referenced_objects: Dict[str, AgentSpecComponent],
    ) -> AgentSpecComponent:
        """Convert a Wayflow component to Agent Spec"""

    def __str__(self) -> str:
        """Return the serialization plugin name and version."""
        return f"{self.plugin_name} (version: {self.plugin_version})"


class WayflowDeserializationPlugin(ABC):
    """Base class for a Wayflow Plugin."""

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """Return the plugin name."""

    @property
    @abstractmethod
    def plugin_version(self) -> str:
        """Return the plugin version."""

    @property
    @abstractmethod
    def supported_component_types(self) -> List[str]:
        """Indicate what component types the plugin supports."""

    @property
    @abstractmethod
    def required_agentspec_deserialization_plugins(self) -> List[ComponentDeserializationPlugin]:
        """Indicate what Agent Spec deserialization plugins are required for this WayFlow converter"""

    def deserialize(
        self,
        obj_type: type["SerializableObject"],
        input_dict: Dict[str, Any],
        deserialization_context: "DeserializationContext",
    ) -> "SerializableObject":
        if (plugin_name := input_dict.pop(_COMPONENT_PLUGIN_NAME_FIELD, None)) != self.plugin_name:
            raise ValueError(
                f"Invalid plugin name: expected `{self.plugin_name}` but found `{plugin_name}`."
            )
        if (
            plugin_version := input_dict.pop(_COMPONENT_PLUGIN_VERSION_FIELD, None)
        ) != self.plugin_version:
            if plugin_version is None:
                raise ValueError(f"Plugin version not found.")
            # We compare the (numeric part of) versions, if the plugin one is lower we might not be able to deserialize
            if _version_lt(
                re.sub(r"\D", "", self.plugin_version), re.sub(r"\D", "", plugin_version)
            ):
                warnings.warn(
                    f"The plugin version being deserialized ({plugin_version}) is newer than the version "
                    f"of the Wayflow plugin ({self.plugin_version}). Deserialization will be attempted anyway."
                )
        return obj_type._deserialize_from_dict(input_dict, deserialization_context)

    @abstractmethod
    def convert_to_wayflow(
        self,
        conversion_context: "AgentSpecToWayflowConversionContext",
        agentspec_component: AgentSpecComponent,
        tool_registry: ToolRegistryT,
        converted_components: Dict[str, Any],
    ) -> Any:
        """Convert an Agent Spec component to Wayflow"""

    def __str__(self) -> str:
        """Return the serialization plugin name and version."""
        return f"{self.plugin_name} (version: {self.plugin_version})"
