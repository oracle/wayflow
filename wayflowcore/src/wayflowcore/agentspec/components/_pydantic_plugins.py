# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, Mapping, Optional, Type, cast

from pyagentspec.component import Component
from pyagentspec.serialization import DeserializationContext
from pyagentspec.serialization.pydanticdeserializationplugin import (
    PydanticComponentDeserializationPlugin as BasePydanticComponentDeserializationPlugin,
)
from pyagentspec.serialization.pydanticserializationplugin import (
    PydanticComponentSerializationPlugin as BasePydanticComponentSerializationPlugin,
)
from pydantic import BaseModel


class PydanticComponentSerializationPlugin(BasePydanticComponentSerializationPlugin):
    """Serialization plugin for Pydantic Components."""

    def __init__(
        self,
        component_types_and_models: Mapping[str, Type[BaseModel]],
        name: str,
        version: Optional[str] = None,
        _allow_partial_model_serialization: bool = True,
    ) -> None:
        super().__init__(
            component_types_and_models=component_types_and_models,
            _allow_partial_model_serialization=_allow_partial_model_serialization,
        )
        self._name = name
        self._version = version

    @property
    def plugin_name(self) -> str:
        """Return the plugin name."""
        return self._name or "PydanticComponentPlugin"

    @property
    def plugin_version(self) -> str:
        """Return the plugin version."""
        from pyagentspec import __version__

        return self._version or __version__


class PydanticComponentDeserializationPlugin(BasePydanticComponentDeserializationPlugin):
    """Deserialization plugin for Pydantic Components."""

    def __init__(
        self,
        component_types_and_models: Mapping[str, Type[BaseModel]],
        name: str,
        version: Optional[str] = None,
    ) -> None:
        super().__init__(
            component_types_and_models=component_types_and_models,
        )
        self._name = name
        self._version = version

    @property
    def plugin_name(self) -> str:
        """Return the plugin name."""
        return self._name or "PydanticComponentPlugin"

    @property
    def plugin_version(self) -> str:
        """Return the plugin version."""
        from pyagentspec import __version__

        return self._version or __version__

    def deserialize(
        self, serialized_component: Dict[str, Any], deserialization_context: DeserializationContext
    ) -> Component:
        """Deserialize a serialized Pydantic model. Same as `pyagentspec` version but also loads aliases"""
        component_type = deserialization_context.get_component_type(serialized_component)
        model_class = self.component_types_and_models[component_type]

        # resolve the content leveraging the pydantic annotations
        resolved_content: Dict[str, Any] = {}
        for field_name, field_info in model_class.model_fields.items():
            annotation = field_info.annotation
            if field_name in serialized_component:
                resolved_content[field_name] = deserialization_context.load_field(
                    serialized_component[field_name], annotation
                )
            elif field_info.alias is not None and field_info.alias in serialized_component:
                resolved_content[field_info.alias] = deserialization_context.load_field(
                    serialized_component[field_info.alias], annotation
                )

        # create the component
        component = model_class(**resolved_content)
        return cast(Component, component)
