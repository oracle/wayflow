# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import warnings
from copy import deepcopy
from functools import cached_property
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, Union, cast

if TYPE_CHECKING:
    from wayflowcore.serialization.plugins import (
        WayflowDeserializationPlugin,
        WayflowSerializationPlugin,
    )
    from wayflowcore.serialization.serializer import SerializableObject


def _create_component_type_to_plugin_mapping(
    plugins: Union[List["WayflowDeserializationPlugin"], List["WayflowSerializationPlugin"]],
) -> Union[Dict[str, "WayflowDeserializationPlugin"], Dict[str, "WayflowSerializationPlugin"]]:
    """Creates mapping from component types name to the plugin that should be used to (de)serialize it"""
    component_types_to_plugins: Union[
        Dict[str, "WayflowDeserializationPlugin"], Dict[str, "WayflowSerializationPlugin"]
    ] = {}
    for plugin in plugins:
        for component_type in plugin.supported_component_types:
            if component_type not in component_types_to_plugins:
                component_types_to_plugins[component_type] = plugin  # type: ignore
            else:
                raise ValueError(
                    f"Two plugins, `{plugin.plugin_name}` and "
                    f"`{component_types_to_plugins[component_type].plugin_name}`, have "
                    f"component types with the same name: `{component_type}`"
                )
    return component_types_to_plugins


class SerializationContext:

    def __init__(self, root: Any, plugins: Optional[List["WayflowSerializationPlugin"]] = None):
        """
        SerializationContext helps ensure that duplicated objects
        (e.g. reused steps in a nested Flow) are serialized only once.
        """
        self.root = root
        self._serialized_objects: Dict[str, Any] = {}
        self._started_serialization: Dict[str, bool] = {}
        self.plugins = plugins or []

        from wayflowcore.serialization._builtins_serialization_plugin import (
            WayflowBuiltinsSerializationPlugin,
        )

        # If none of the given plugins is the builtins one, we automatically add it
        if not any(
            isinstance(plugin, WayflowBuiltinsSerializationPlugin) for plugin in self.plugins
        ):
            self.plugins.append(self._builtins_serialization_plugin)

        # Create a mapping cache of component_type -> plugin mappings
        # to know what plugin to use to convert a given component
        self.component_types_to_plugins: Dict[str, "WayflowSerializationPlugin"] = cast(
            Dict[str, "WayflowSerializationPlugin"],
            _create_component_type_to_plugin_mapping(self.plugins),
        )

    def get_serialization_plugin_for_object(
        self, obj: "SerializableObject"
    ) -> "WayflowSerializationPlugin":
        component_type = obj.__class__.__name__
        if component_type not in self.component_types_to_plugins:
            # For backward compatibility, we rely on the builtin serialization if no plugin is given, but we warn the user
            warnings.warn(
                f"Found no serialization plugin to serialize the object of type `{type(obj).__name__}`. "
                f"Trying using the builtins serialization plugin instead. "
                f"Note that since 26.1.0 Wayflow Plugins are required to support serialization of custom components."
            )
            return self._builtins_serialization_plugin
        return self.component_types_to_plugins[component_type]

    def start_serialization(self, obj: Any) -> None:
        """
        Records that the serialization of an object will start. If the object has already been
        serialized, then it should do nothing, but if the serialization has started and not
        completed, then an error is raised because one object is referencing itself, which we do
        not support.

        Parameters
        ----------
        obj:
          The original, non-serialized object
        """
        obj_ref = self.get_reference(obj)
        if self._started_serialization.get(obj_ref) and not self._serialized_objects.get(obj_ref):
            raise ValueError(
                f"Serialization of objects containing themselves is a mathematical impossibility. {obj_ref, obj, self._serialized_objects}"
            )
        self._started_serialization[obj_ref] = True

    def record_obj_dict(self, obj: Any, obj_as_dict: Dict[Any, Any]) -> None:
        """
        Records the serialization-as-dict of a serialized object

        Parameters
        ----------
        obj:
          The original, non-serialized object
        obj_as_dict:
          The object serialized as a dict
        """
        self._serialized_objects[self.get_reference(obj)] = obj_as_dict

    def check_obj_is_already_serialized(self, obj: Any) -> bool:
        """
        Returns True if the object has already been serialized

        Parameters
        ----------
        obj:
          The original, non-serialized object
        """
        return self._serialized_objects.get(self.get_reference(obj)) is not None

    def get_reference_dict(self, obj: Any) -> Dict[str, str]:
        """
        Returns a dict that contains a single entry "$ref"

        Parameters
        ----------
        obj:
          The original, non-serialized object
        """
        return {"$ref": self.get_reference(obj)}

    def get_reference(self, obj: Any) -> str:
        """
        Returns the formatted string that is used by the serialization context to reference the
        object

        Parameters
        ----------
        obj:
          The original, non-serialized object
        """
        obj_id = getattr(obj, "id", id(obj))
        return f"{obj.__class__.__name__.lower()}/{obj_id}"

    def is_root(self, obj: Any) -> bool:
        """
        Check if one object is the root of the ongoing serialization process

        Parameters
        ----------
        obj:
          The original, non-serialized object
        """
        return obj is self.root

    def get_all_referenced_objects(self) -> Dict[str, Any]:
        """
        Returns the dict containing all referenced objects
        """
        return self._serialized_objects

    @cached_property
    def _builtins_serialization_plugin(cls) -> "WayflowSerializationPlugin":
        from wayflowcore.serialization._builtins_serialization_plugin import (
            WayflowBuiltinsSerializationPlugin,
        )

        return WayflowBuiltinsSerializationPlugin()


class DeserializationContext:

    def __init__(self, plugins: Optional[List["WayflowDeserializationPlugin"]] = None) -> None:
        self._referenced_objects: Dict[str, Dict[Any, Any]] = {}
        self._deserialized_objects: Dict[str, Any] = {}
        self._started_deserialization: Dict[str, bool] = {}
        self.registered_tools: Dict[str, Any] = {}
        self._current_additional_transitions: Dict[str, Optional[str]] = {}
        self.plugins = plugins or []

        from wayflowcore.serialization._builtins_deserialization_plugin import (
            WayflowBuiltinsDeserializationPlugin,
        )

        # If none of the given plugins is the builtins one, we automatically add it
        if not any(
            isinstance(plugin, WayflowBuiltinsDeserializationPlugin) for plugin in self.plugins
        ):
            self.plugins.append(self._builtins_deserialization_plugin)

        # Create a mapping cache of component_type -> plugin mappings
        # to know what plugin to use to convert a given component
        self.component_types_to_plugins: Dict[str, "WayflowDeserializationPlugin"] = cast(
            Dict[str, "WayflowDeserializationPlugin"],
            _create_component_type_to_plugin_mapping(self.plugins),
        )

    def get_deserialization_plugin_for_object(
        self, obj_type: Type["SerializableObject"]
    ) -> "WayflowDeserializationPlugin":
        component_type = obj_type.__name__
        if component_type not in self.component_types_to_plugins:
            # For backward compatibility, we rely on the builtin serialization if no plugin is given, but we warn the user
            warnings.warn(
                f"Found no deserialization plugin to deserialize the object of type `{component_type}`. "
                f"Trying using the builtins deserialization plugin instead. "
                f"Note that since 26.1.0 Wayflow Plugins are required to support deserialization of custom components."
            )
            return self._builtins_deserialization_plugin
        return self.component_types_to_plugins[component_type]

    def add_referenced_objects(self, new_referenced_objects: Dict[str, Dict[Any, Any]]) -> None:
        self._referenced_objects.update(new_referenced_objects)

    def get_referenced_dict(self, object_reference: str) -> Dict[Any, Any]:
        """
        Returns the object object_as_dict for a given object reference

        Parameters
        ----------
        object_reference:
          The reference of the object being deserialized
        """
        if object_reference not in self._referenced_objects:
            raise ValueError(
                f"During deserialization, encountered reference {object_reference} that is missing "
                f"in the _referenced_objects of the serialized root object."
            )
        return self._referenced_objects[object_reference]

    def recorddeserialized_object(self, object_reference: str, deserialized_object: Any) -> None:
        """
        Records the object deserialized, such that it may be reused during the deserialization
        process

        Parameters
        ----------
        object_reference:
          The reference of the object being deserialized
        """
        self._deserialized_objects[object_reference] = deserialized_object

    def check_reference_is_already_deserialized(self, object_reference: str) -> bool:
        """
        Returns True if the object is already deserialized

        Parameters
        ----------
        object_reference:
          The reference of the object being deserialized
        """
        return object_reference in self._deserialized_objects

    def get_deserialized_object(self, object_reference: str) -> Any:
        """
        Returns the object already deserialized

        Parameters
        ----------
        object_reference:
          The reference of the object being deserialized
        """
        return self._deserialized_objects[object_reference]

    def start_deserialization(self, object_reference: str) -> None:
        """
        Records that the deserialization of an object will start. If the object has already been
        deserialized, then it should do nothing, but if the deserialization has started and not
        completed, then an error is raised because one object is referencing itself, which we do
        not support.

        Parameters
        ----------
        object_reference:
          The reference of the object being deserialized
        """
        if self._started_deserialization.get(
            object_reference
        ) and not self._deserialized_objects.get(object_reference):
            raise ValueError(
                "Deserialization of objects containing themselves is a mathematical impossibility."
            )
        self._started_deserialization[object_reference] = True

    def _register_additional_transitions(self, transitions: Dict[str, Optional[str]]) -> None:
        self._current_additional_transitions = deepcopy(transitions)

    def _consume_additional_transitions(self) -> Dict[str, Optional[str]]:
        additional_transitions = self._current_additional_transitions
        self._current_additional_transitions = {}  # reset
        return additional_transitions

    @cached_property
    def _builtins_deserialization_plugin(cls) -> "WayflowDeserializationPlugin":
        from wayflowcore.serialization._builtins_deserialization_plugin import (
            WayflowBuiltinsDeserializationPlugin,
        )

        return WayflowBuiltinsDeserializationPlugin()
