# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import importlib
import pkgutil
import warnings
from abc import ABC, abstractmethod
from dataclasses import FrozenInstanceError, dataclass, field, fields
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    ForwardRef,
    List,
    Optional,
    Type,
    TypeVar,
    cast,
    get_type_hints,
)

import yaml

from wayflowcore._metadata import METADATA_KEY, MetadataType, ObjectWithMetadata
from wayflowcore.exceptions import DataclassFieldDeserializationError
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.serialization._typingutils import (
    get_dict_inner_types,
    get_list_inner_type,
    get_optional_inner_type,
    get_set_inner_type,
    get_tuple_inner_types,
    get_union_types,
    is_any_type,
    is_dict_type,
    is_list_type,
    is_literal_type,
    is_optional_type,
    is_set_type,
    is_tuple_type,
    is_union_type,
    respects_literal,
)
from wayflowcore.serialization.context import DeserializationContext, SerializationContext

if TYPE_CHECKING:
    from wayflowcore.serialization.plugins import (
        WayflowDeserializationPlugin,
        WayflowSerializationPlugin,
    )


class SerializableObject(ObjectWithMetadata, ABC):
    """
    Abstract base class for WayFlow components that can be serialized and deserialized.

    This class provides a common interface for objects that need to be converted to and from a dictionary representation.
    """

    _COMPONENT_REGISTRY: ClassVar[Dict[str, Type["SerializableObject"]]] = {}
    # Cannot be `_REGISTRY` which is already used by `_StepRegistry`

    _can_be_referenced: ClassVar[bool] = True
    # whether the object can be referenced or will be entirely serialized where its needed

    def __init_subclass__(cls, **kwargs: Dict[str, Any]):
        super().__init_subclass__(**kwargs)
        if issubclass(cls, SerializableObject):
            SerializableObject._COMPONENT_REGISTRY[cls.__name__] = cls

    @classmethod
    def get_component(cls, component_type: str) -> Type["SerializableObject"]:
        if component_type not in cls._COMPONENT_REGISTRY:
            raise KeyError(f"Object of type {component_type} is not registered.")
        return cls._COMPONENT_REGISTRY[component_type]

    @abstractmethod
    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        """
        Serialize the component into a dictionary.

        Parameters
        ----------
        serialization_context:
            Context for serialization operations.

        Returns
        -------
            A dictionary representation of the component.
        """

    @classmethod
    @abstractmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        """
        Converts a dictionary into a component of the ``cls`` type.

        Parameters
        ----------
        input_dict:
            The dictionary to deserialize.
        deserialization_context:
            Context for deserialization operations.

        Returns
        -------
            The deserialized component, reconstructed from the input dictionary.
        """


class SerializableNeedToBeImplementedMixin:
    """Mixin to prevent from needing to always implement serde for specific custom classes that might be custom"""

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        raise ValueError(f"Serialization not implemented for {self.__class__.__name__}")

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        raise ValueError(f"Serialization not implemented for {cls.__class__.__name__}")


def get_field_type_mapping(cls: Any) -> Dict[str, type]:
    """
    This allows to have the types of the attributes of dataclass
    for both normally-typed attributes and the ones annotated with type-checking only type.

    class MyDataclass:
        type_1: str
        type_2: MyCustomAttr
        type_3: "MySecondCustomAttr"  <--- resolves the actual type of this kind of attribute
    """
    dataclass_fields = {param.name: param.type for param in fields(cls) if param.init}

    # we resolve the forwards references (e.g. dataclasses with type annotations specified "between quotes")
    if any(isinstance(t, str) for t in dataclass_fields.values()):
        try:
            dataclass_fields = get_type_hints(cls)
        except NameError as e:
            pass

    if hasattr(cls, "__orig_bases__"):
        # Get the base with concrete types (Box[int, str])
        orig_base = cls.__orig_bases__[0]
        # A tuple of type args (int, str)
        type_args = orig_base.__args__
        # The generic type vars (T, U)
        type_vars = orig_base.__origin__.__parameters__
        # Get field type hints as dict with type vars as values
        hints = get_type_hints(orig_base.__origin__)
        # Map field names to actual concrete classes
        return {
            fname: (
                type_args[type_vars.index(ftype)] if ftype in type_vars else dataclass_fields[fname]
            )
            for fname, ftype in hints.items()
            if ftype in type_vars or fname in dataclass_fields
        }
    else:
        return dataclass_fields


def _resolve_legacy_field_name(cls: type, field_name: str) -> str:
    """
    Some attributes of dataclasses have been modified, so we need to use resolve the old
    name to load old serialized flows/agents.
    """
    from wayflowcore.executors._agentconversation import AgentConversation
    from wayflowcore.executors._flowconversation import FlowConversation

    _CLS_TO_ATTRIBUTE_MAPPING: Dict[type, Dict[str, str]] = {
        AgentConversation: {"component": "agent"},
        FlowConversation: {"component": "flow"},
    }

    if cls in _CLS_TO_ATTRIBUTE_MAPPING:
        return _CLS_TO_ATTRIBUTE_MAPPING[cls].get(field_name, field_name)

    return field_name


class SerializableDataclassMixin:
    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return {
            k.name: serialize_any_to_dict(getattr(self, k.name), serialization_context)
            for k in fields(self)  # type: ignore
            if (
                (
                    not k.name.startswith("_")  # we don't serialize private fields
                    or k.name == "__metadata_info__"  # except the metadata
                )
                and k.init  # not part of the dataclass __init__ -> would fail at deserialization
            )
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        if "_referenced_objects" in input_dict:
            deserialization_context.add_referenced_objects(input_dict["_referenced_objects"])

        dataclass_fields: Dict[str, Any] = {}
        for field_name, field_type in get_field_type_mapping(cls).items():
            if field_name not in input_dict:
                # maybe an old name
                old_name = _resolve_legacy_field_name(cls, field_name)

                if old_name in input_dict:
                    field_value = input_dict[old_name]
                else:
                    continue
            else:
                field_value = input_dict[field_name]

            try:
                dataclass_fields[field_name] = deserialize_any_from_dict(
                    field_value, field_type, deserialization_context
                )
            except DataclassFieldDeserializationError as e:
                # throw exception as is
                raise e
            except Exception as e:
                raise DataclassFieldDeserializationError(
                    f"Error when deserializing field `{field_name}` of dataclass `{cls.__name__}`: {str(e)}"
                ) from e

        return cls(**dataclass_fields)  # type: ignore


M = TypeVar("M")


class _IncorrectDeserializedTypeException(ValueError):
    """Raised when the autodeserialized type is not correct"""


def deserialize_any_from_dict(
    obj: Any, expected_type: Type[M], deserialization_context: DeserializationContext
) -> M:

    _import_all_submodules("wayflowcore")

    if isinstance(expected_type, ForwardRef):
        # resolve forward type annotation
        expected_class_as_str = expected_type.__forward_arg__
        # resolve string type-checking annotation
        expected_type = SerializableObject._COMPONENT_REGISTRY.get(
            expected_class_as_str, expected_type
        )
    else:
        # resolve string type-checking annotation
        expected_type = SerializableObject._COMPONENT_REGISTRY.get(expected_type, expected_type)  # type: ignore

    try:
        if issubclass(expected_type, SerializableObject):
            # If the object is a string and the expected type is a subclass of tool
            # We proceed with its deserialization, as autodeserialize requires a dictionary
            from wayflowcore.tools import Tool

            if isinstance(obj, str) and issubclass(expected_type, Tool):
                deserialized_object = Tool._deserialize_from_dict(obj, deserialization_context)  # type: ignore
            else:
                deserialized_object = autodeserialize_from_dict(obj, deserialization_context)
            if not isinstance(deserialized_object, expected_type):
                raise _IncorrectDeserializedTypeException(
                    f"The expected deserialized type is {expected_type} but `{obj}` was passed (the deserialized type is {type(deserialized_object)})"
                )
            return cast(M, deserialized_object)
    except _IncorrectDeserializedTypeException as e:
        pass
    except TypeError as e:
        # We ignore the TypeError raised by the call to `issubclass` because
        # we don't want to break and can continue normally in this cases.
        if "issubclass" not in str(e):
            raise e

    if is_any_type(expected_type):
        return autodeserialize_any_from_dict(obj, deserialization_context)  # type: ignore

    if is_union_type(expected_type):
        if obj is None:
            return None  # type: ignore
        inner_types = get_union_types(expected_type)
        encountered_errors = []
        for inner_type in inner_types:
            try:
                return deserialize_any_from_dict(obj, inner_type, deserialization_context)
            except (TypeError, ValueError) as e:
                encountered_errors.append(e)
                continue
        raise ValueError(
            f"The expected deserialized type is {expected_type} but `{obj}` was passed: none of the union types was serializable. Encountered errors: {encountered_errors}"
        )

    if is_optional_type(expected_type):
        if obj is None:
            return None  # type: ignore
        expected_type = get_optional_inner_type(expected_type)

    if is_set_type(expected_type):
        if not isinstance(obj, set):
            raise ValueError(
                f"The expected deserialized type is {expected_type} but `{obj}` was passed (obj is not list)"
            )
        inner_type = get_set_inner_type(expected_type)
        return {deserialize_any_from_dict(v, inner_type, deserialization_context) for v in obj}  # type: ignore

    if is_tuple_type(expected_type):
        if not isinstance(obj, (tuple, list)):
            raise ValueError(
                f"The expected deserialized type is {expected_type} but `{obj}` was passed (obj is not tuple)"
            )
        inner_types = get_tuple_inner_types(expected_type)  # assuming single-type tuple
        if len(inner_types) != len(obj):
            raise ValueError(
                f"The expected deserialized type is {expected_type} but `{obj}` was passed (obj does not have the same length as tuple)"
            )
        return tuple(
            deserialize_any_from_dict(item, inner_type, deserialization_context)
            for inner_type, item in zip(inner_types, obj)
        )  # type: ignore

    if is_list_type(expected_type):
        if not isinstance(obj, list):
            raise ValueError(
                f"The expected deserialized type is {expected_type} but `{obj}` was passed (obj is not list)"
            )
        inner_type = get_list_inner_type(expected_type)
        return [
            deserialize_any_from_dict(item, inner_type, deserialization_context) for item in obj
        ]  # type: ignore

    if is_literal_type(expected_type):
        if not respects_literal(obj, expected_type):
            raise ValueError(
                f"The expected deserialized type is {expected_type} but `{obj}` was passed (obj is not such a literal)"
            )
        return obj  # type: ignore

    if is_dict_type(expected_type):
        if not (isinstance(obj, dict) and not any(x in obj for x in ["_component_type", "$ref"])):
            raise ValueError(
                f"The expected deserialized type is {expected_type} but `{obj}` was passed (obj is not dict)"
            )
        key_type, value_type = get_dict_inner_types(expected_type)
        return {
            deserialize_any_from_dict(
                k, key_type, deserialization_context
            ): deserialize_any_from_dict(v, value_type, deserialization_context)
            for k, v in obj.items()
        }  # type: ignore

    try:
        if issubclass(expected_type, Enum):
            return expected_type(obj)  # type: ignore
    except (TypeError, ValueError):
        # "ValueError: * is not a valid `expected_type`" or
        # "TypeError: issubclass() arg 1 must be a class"
        # We failed deserialization as enum, it's ok, we can continue
        pass

    # handle primitive types
    if any(
        [
            expected_type is int,
            expected_type is float,
        ]
    ):
        if not isinstance(obj, (int, float)):
            raise ValueError(
                f"The expected deserialized type is {expected_type} but `{obj}` was passed (obj is not int or float type)"
            )
        return expected_type(obj)  # type: ignore
    elif any(
        [
            expected_type is str,
            expected_type is bool,
            expected_type is bytes,
            expected_type is str,
        ]
    ):
        if not isinstance(obj, expected_type):
            raise ValueError(
                f"The expected deserialized type is {expected_type} but `{obj}` was passed (obj is not primitive type)"
            )
        return obj

    # Fallback
    raise ValueError(f"Deserialization of {obj} into {expected_type} is not supported")


@dataclass
class SerializableCallable(SerializableDataclassMixin, ABC):
    """Helper class to serialize a callable just by the name of its class"""

    _can_be_referenced: ClassVar[bool] = False

    def __init__(self) -> None:
        pass

    @abstractmethod
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


def serialize_to_dict(
    obj: SerializableObject,
    serialization_context: Optional[SerializationContext] = None,
    plugins: Optional[List["WayflowSerializationPlugin"]] = None,
) -> Dict[str, Any]:
    """
    Serializes an object into a dictionary representation.

    Parameters
    ----------
    obj:
        Object to serialize.
    serialization_context:
        Context for serialization operations. Keeps track of serialized objects to avoid serializing them several times.
        If not provided, a new ``SerializationContext`` will be created with the object as its root.
    plugins:
        List of plugins to be used in the SerializationContext.
        If a serialization context instance is provided, this list is ignored.

    Returns
    -------
        A dictionary representation of the object, which can be saved as text using YAML or JSON.

    Examples
    --------
    >>> import yaml
    >>> from wayflowcore.serialization.serializer import serialize_to_dict
    >>>
    >>> serialized_assistant = serialize_to_dict(assistant)
    >>> with open(config_file_path, 'w') as f:  # doctest: +SKIP
    ...     yaml.dump(serialized_assistant, f)

    """
    if (
        not isinstance(obj, SerializableObject)
        and SerializableObject._COMPONENT_REGISTRY.get(obj.__class__.__name__, None)
        is not obj.__class__
    ):
        raise ValueError(
            f"You are trying to serialize an object that is not `SerializableObject`. Please make sure this object extends it: {obj}"
        )

    # not using the common serialization context if object is not supposed to use references
    if serialization_context is None:
        serialization_context = SerializationContext(root=obj, plugins=plugins)
    elif plugins is not None:
        warnings.warn(
            "A list of plugins was provided together with a serialization context instance in `serialize_to_dict`. "
            "Do not pass the plugins to `serialize_to_dict`, but create the context instance passing the list of plugins instead.",
            UserWarning,
        )

    # returned reference object if already deserialized
    if serialization_context.check_obj_is_already_serialized(obj):
        return serialization_context.get_reference_dict(obj)

    # avoid self references
    if obj._can_be_referenced:
        serialization_context.start_serialization(obj)

    serialization_plugin = serialization_context.get_serialization_plugin_for_object(obj)
    obj_as_dict = serialization_plugin.serialize(obj, serialization_context)

    # fill with type and metadata fields
    metadata = obj.__metadata_info__ if hasattr(obj, "__metadata_info__") else {}
    if metadata is None:
        metadata = {}
    if len(metadata) > 0:
        obj_as_dict[METADATA_KEY] = metadata
    if "_component_type" not in obj_as_dict:
        obj_as_dict["_component_type"] = obj.__class__.__name__

    if serialization_context.is_root(obj):
        # 2. uses references and is root, so dict should contain referenced objects
        referenced_objects = serialization_context.get_all_referenced_objects()
        if referenced_objects:
            obj_as_dict["_referenced_objects"] = referenced_objects
        return obj_as_dict
    elif not obj._can_be_referenced:
        # 1. should not use reference, just return dict
        return obj_as_dict
    else:
        # 3. stores the serialized object in context and just return reference
        serialization_context.record_obj_dict(obj, obj_as_dict)
        return serialization_context.get_reference_dict(obj)


def serialize(
    obj: SerializableObject,
    serialization_context: Optional[SerializationContext] = None,
    plugins: Optional[List["WayflowSerializationPlugin"]] = None,
) -> str:
    """
    Serializes an object into a YAML string representation.

    Parameters
    ----------
    obj:
        Object to serialize.
    serialization_context:
        Context for serialization operations. Keeps track of serialized objects to avoid serializing them several times.
        If not provided, a new ``SerializationContext`` will be created with the object as its root.
    plugins:
        List of plugins to be used in the SerializationContext.
        If a serialization context instance is provided, this list is ignored.

    Returns
    -------
        A YAML string representation of the object.

    Examples
    --------
    >>> from wayflowcore.serialization.serializer import serialize
    >>>
    >>> serialized_assistant_as_str = serialize(assistant)

    """
    obj_as_dict = serialize_to_dict(obj, serialization_context, plugins)
    return yaml.dump(obj_as_dict)


T = TypeVar("T", bound=SerializableObject)


def deserialize_from_dict(
    deserialization_type: type[T],
    obj_as_dict: Dict[str, Any],
    deserialization_context: Optional[DeserializationContext] = None,
    plugins: Optional[List["WayflowDeserializationPlugin"]] = None,
) -> T:
    """
    Deserializes an object from its dictionary representation.

    Parameters
    ----------
    deserialization_type:
        The type of the object to be deserialized.
    obj_as_dict:
        The dictionary representation of the object to be deserialized.
    deserialization_context:
        Context for deserialization operations, to avoid deserializing the same object twice.
        If not provided, a new ``DeserializationContext`` will be created.
    plugins:
        List of plugins to be used in the DeserializationContext.
        If a deserialization context instance is provided, this list is ignored.

    Returns
    -------
        The deserialized object.

    Examples
    --------
    >>> import yaml
    >>> from wayflowcore.serialization.serializer import deserialize_from_dict
    >>> from wayflowcore.flow import Flow
    >>>
    >>> with open(config_file_path, 'r') as f:
    ...     serialized_assistant = yaml.safe_load(f.read())
    ...
    >>> new_assistant = deserialize_from_dict(Flow, serialized_assistant)

    """
    if deserialization_context is None:
        deserialization_context = DeserializationContext(plugins=plugins)
    elif plugins is not None:
        warnings.warn(
            "A list of plugins was provided together with a deserialization context instance in `deserialize_from_dict`. "
            "Do not pass the plugins to `deserialize_from_dict`, but create the context instance passing the list of plugins instead.",
            UserWarning,
        )

    if isinstance(obj_as_dict, dict) and "_referenced_objects" in obj_as_dict:
        deserialization_context.add_referenced_objects(obj_as_dict["_referenced_objects"])

    object_reference = obj_as_dict.get("$ref") if isinstance(obj_as_dict, dict) else None
    if object_reference:
        if deserialization_context.check_reference_is_already_deserialized(object_reference):
            deserialized_obj: SerializableObject = deserialization_context.get_deserialized_object(
                object_reference
            )
            if not isinstance(deserialized_obj, deserialization_type):
                raise ValueError(
                    f"A referenced objects found of type {deserialized_obj.__class__.__name__} "
                    f"which is not compatible with the expected deserialization type of "
                    f"{deserialization_type.__name__}"
                )
            return deserialized_obj
        else:
            deserialization_context.start_deserialization(object_reference)
            obj_as_dict = deserialization_context.get_referenced_dict(object_reference)

    deserialization_plugin = deserialization_context.get_deserialization_plugin_for_object(
        deserialization_type
    )
    deserialized_obj = deserialization_plugin.deserialize(
        deserialization_type, obj_as_dict, deserialization_context
    )
    if object_reference:
        deserialization_context.recorddeserialized_object(object_reference, deserialized_obj)
        _set_component_id(deserialized_obj, object_reference)
    return cast(T, deserialized_obj)


def _set_component_id(component: ObjectWithMetadata, reference: str) -> None:
    if "/" in reference:
        reference = reference.split("/", maxsplit=1)[-1]
    try:
        component.id = reference
    except FrozenInstanceError:
        # cannot set id of frozen dataclass, ID should be passed some other way
        pass


def deserialize(
    deserialization_type: type[T],
    obj: str,
    deserialization_context: Optional[DeserializationContext] = None,
    plugins: Optional[List["WayflowDeserializationPlugin"]] = None,
) -> T:
    """
    Deserializes an object from its text representation and its corresponding class.

    Parameters
    ----------
    deserialization_type:
        The type of the object to be deserialized.
    obj:
        The text representation of the object to be deserialized.
    deserialization_context:
        Context for deserialization operations, to avoid deserializing a same object twice.
        If not provided, a new ``DeserializationContext`` will be created.
    plugins:
        List of plugins to be used in the DeserializationContext.
        If a deserialization context instance is provided, this list is ignored.

    Returns
    -------
        The deserialized object.

    Examples
    --------
    >>> from wayflowcore.serialization.serializer import deserialize
    >>> from wayflowcore.flow import Flow
    >>>
    >>> new_assistant = deserialize(Flow, serialized_assistant_as_str)

    """
    if deserialization_context is None:
        deserialization_context = DeserializationContext(plugins=plugins)
    elif plugins is not None:
        warnings.warn(
            "A list of plugins was provided together with a deserialization context instance in `deserialize`. "
            "Do not pass the plugins to `deserialize`, but create the context instance passing the list of plugins instead.",
            UserWarning,
        )

    obj_as_dict: Dict[str, Any] = yaml.safe_load(obj)

    component_type: str = obj_as_dict["_component_type"]

    if component_type is not None and component_type != deserialization_type.__name__:
        raise ValueError(
            f"WayFlow type does not match deserialization type: "
            f"deserialization_type={deserialization_type.__name__}; _component_type={component_type}"
        )
    return deserialize_from_dict(deserialization_type, obj_as_dict, deserialization_context)


def autodeserialize(
    obj: str,
    deserialization_context: Optional[DeserializationContext] = None,
    plugins: Optional[List["WayflowDeserializationPlugin"]] = None,
) -> SerializableObject:
    """
    Deserializes an object from its text representation.

    Parameters
    ----------
    obj:
        The text representation of the object to be deserialized.
    deserialization_context:
        Context for deserialization operations, to avoid deserializing a same object twice.
        If not provided, a new ``DeserializationContext`` will be created.
    plugins:
        List of plugins to be used in the DeserializationContext.
        If a deserialization context instance is provided, this list is ignored.

    Returns
    -------
        The deserialized object.

    Examples
    --------
    >>> from wayflowcore.serialization.serializer import autodeserialize
    >>>
    >>> new_assistant = autodeserialize(serialized_assistant_as_str)

    """

    if deserialization_context is None:
        deserialization_context = DeserializationContext(plugins=plugins)
    elif plugins is not None:
        warnings.warn(
            "A list of plugins was provided together with a deserialization context instance in `autodeserialize`. "
            "Do not pass the plugins to `autodeserialize`, but create the context instance passing the list of plugins instead.",
            UserWarning,
        )

    obj_as_dict: Dict[str, Any] = yaml.safe_load(obj)
    return autodeserialize_from_dict(obj_as_dict, deserialization_context)


def autodeserialize_from_dict(
    obj_as_dict: Dict[str, Any], deserialization_context: DeserializationContext
) -> SerializableObject:
    # ensure all classes are registered
    _import_all_submodules("wayflowcore")

    # check if reference first
    object_reference = obj_as_dict.get("$ref", None) if isinstance(obj_as_dict, dict) else None
    if object_reference is not None:
        if deserialization_context.check_reference_is_already_deserialized(object_reference):
            deserialized_obj: SerializableObject = deserialization_context.get_deserialized_object(
                object_reference
            )
            return deserialized_obj
        else:
            deserialization_context.start_deserialization(object_reference)
            obj_as_dict = deserialization_context.get_referenced_dict(object_reference)

    component_type: str = obj_as_dict["_component_type"]

    if "_component_type" not in obj_as_dict or component_type is None:
        raise KeyError(
            "Failure to deserialize due to missing `_component_type`: The following object "
            f"does not seem to be a valid WayFlow component to deserialize:\n{obj_as_dict}"
        )
    deserialization_type = SerializableObject.get_component(component_type)

    if component_type is not None and component_type != deserialization_type.__name__:
        raise ValueError(
            f"WayFlow type does not match deserialization type: "
            f"deserialization_type={deserialization_type.__name__}; _component_type={component_type}"
        )
    deserialized_obj = deserialize_from_dict(
        deserialization_type=deserialization_type,
        obj_as_dict=obj_as_dict,
        deserialization_context=deserialization_context,
    )
    if object_reference:
        deserialization_context.recorddeserialized_object(object_reference, deserialized_obj)
        _set_component_id(deserialized_obj, reference=object_reference)
    return deserialized_obj


def serialize_any_to_dict(obj: Any, serialization_context: SerializationContext) -> Any:
    if isinstance(obj, (bool, int, float, bytes)):
        return obj
    elif obj is None:
        return None
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, set):
        return {serialize_any_to_dict(v, serialization_context) for v in obj}
    elif isinstance(obj, (tuple, list)):
        return [serialize_any_to_dict(s, serialization_context) for s in obj]
    elif isinstance(obj, dict) and "_component_type" not in obj:
        return {k: serialize_any_to_dict(v, serialization_context) for k, v in obj.items()}
    elif (
        isinstance(obj, SerializableObject)
        or obj.__class__.__name__ in SerializableObject._COMPONENT_REGISTRY
    ):
        return serialize_to_dict(obj, serialization_context)
    elif isinstance(obj, str):
        # we serialize as str after SerializableObject because a custom component might extend
        # from str (like enums) but we want to serialize it using the custom serialization and not just a string
        return obj
    elif callable(obj):
        raise ValueError(
            f"Callable are not serializable. ({obj}) Make it extend from `SerializableCallable` to make it serializable"
        )
    raise ValueError(
        f"Type {type(obj)} of {obj} is not supported for deserialization, because it is not extending `SerializableObject`. Please make sure this object extends it."
    )


def serialize_any_to_dict_or_stringify(
    obj: Any, serialization_context: SerializationContext
) -> Any:
    """
    Attempt to serialize any object using the standard serializer; fall back to ``str(obj)``
    when the object cannot be serialized, while preserving native container structures.
    """

    try:
        return serialize_any_to_dict(obj, serialization_context)
    except (TypeError, ValueError):
        if isinstance(obj, dict):
            return {
                k: serialize_any_to_dict_or_stringify(v, serialization_context)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [serialize_any_to_dict_or_stringify(v, serialization_context) for v in obj]
        if isinstance(obj, tuple):
            return tuple(serialize_any_to_dict_or_stringify(v, serialization_context) for v in obj)
        if isinstance(obj, set):
            return {serialize_any_to_dict_or_stringify(v, serialization_context) for v in obj}
        if isinstance(obj, (float, int, str, bool)):
            return obj
        return str(obj)


def autodeserialize_any_from_dict(obj: Any, deserialization_context: DeserializationContext) -> Any:
    # ensure all classes are registered
    _import_all_submodules("wayflowcore")
    if isinstance(obj, (str, bool, int, float, bytes)):
        return obj
    elif obj is None:
        return None
    elif isinstance(obj, set):
        return {autodeserialize_from_dict(v, deserialization_context) for v in obj}
    elif isinstance(obj, list):
        return [autodeserialize_any_from_dict(s, deserialization_context) for s in obj]
    elif isinstance(obj, tuple):
        return tuple(autodeserialize_any_from_dict(s, deserialization_context) for s in obj)
    elif isinstance(obj, dict) and not any(x in obj for x in ["_component_type", "$ref"]):
        return {
            k: autodeserialize_any_from_dict(v, deserialization_context) for k, v in obj.items()
        }
    return autodeserialize_from_dict(obj, deserialization_context)


def _import_all_submodules(package_name: str, recursive: bool = True) -> None:
    """Import all submodules to ensure all serializable classes are registered."""
    package = importlib.import_module(package_name)
    for _, name, is_pkg in pkgutil.walk_packages(
        package.__path__,
        prefix=package.__name__ + ".",
        # need this prefix to avoid looping in the tests, only the src/ files are prefixed with the package name
    ):
        full_name = name
        try:
            importlib.import_module(full_name)
        except ModuleNotFoundError:
            continue
        if recursive and is_pkg:
            _import_all_submodules(full_name)


@dataclass(kw_only=True)
class SerializableDataclass(SerializableDataclassMixin, SerializableObject, ABC):
    """
    Base class for dataclasses to be serializable and to have ID and metadata attributes
    """

    id: str = field(default_factory=IdGenerator.get_or_generate_id, compare=False, hash=False)
    __metadata_info__: MetadataType = field(default_factory=dict, hash=False)

    def __init_subclass__(cls, **kwargs: Dict[str, Any]):
        # we override so that any child classes are registered
        super().__init_subclass__(**kwargs)
        # always serialize if not abstract
        if ABC not in cls.__bases__:
            SerializableObject._COMPONENT_REGISTRY[cls.__name__] = cls


@dataclass(frozen=True, kw_only=True)
class FrozenSerializableDataclass(SerializableDataclassMixin, SerializableObject, ABC):
    """
    Base class for frozen dataclasses to be serializable and to have ID and metadata attributes
    """

    id: str = field(default_factory=IdGenerator.get_or_generate_id, compare=False, hash=False)
    __metadata_info__: MetadataType = field(default_factory=dict, hash=False)

    def __init_subclass__(cls, **kwargs: Dict[str, Any]):
        # we override so that any child classes are registered
        super().__init_subclass__(**kwargs)
        # always serialize if not abstract
        if ABC not in cls.__bases__:
            SerializableObject._COMPONENT_REGISTRY[cls.__name__] = cls
