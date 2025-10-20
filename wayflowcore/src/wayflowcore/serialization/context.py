# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from copy import deepcopy
from typing import Any, Dict, Optional


class SerializationContext:
    def __init__(self, root: Any):
        """
        SerializationContext helps ensure that duplicated objects (e.g. reused steps in a nested
        Flow) are serialized only once.
        """
        self._serialized_objects: Dict[str, Any] = {}
        self._started_serialization: Dict[str, bool] = {}
        self.root = root

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


class DeserializationContext:

    def __init__(self) -> None:
        self._referenced_objects: Dict[str, Dict[Any, Any]] = {}
        self._deserialized_objects: Dict[str, Any] = {}
        self._started_deserialization: Dict[str, bool] = {}
        self.registered_tools: Dict[str, Any] = {}

        self._current_additional_transitions: Dict[str, Optional[str]] = {}

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
