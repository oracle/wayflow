# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import logging
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple, Type, TypedDict, Union, cast

from wayflowcore._metadata import MetadataType
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject

logger = logging.getLogger(__name__)


class _empty_default:
    """Marker object for Property.empty_default"""


JsonSchemaParam = TypedDict(
    "JsonSchemaParam",
    {
        "title": str,
        "type": Union[str, List[str]],
        "default": Any,
        "description": Optional[str],
        "enum": List[Any],
        "items": "JsonSchemaParam",
        "additionalProperties": Union["JsonSchemaParam", bool],
        "properties": Dict[str, "JsonSchemaParam"],
        "anyOf": List["JsonSchemaParam"],
        "key_type": "JsonSchemaParam",  # added by us, to support types of key in dicts
        "required": List[str],
    },
    total=False,
)


# just a SerializableObject since it has a custom serialization
@dataclass(frozen=True)
class Property(SerializableObject, ABC):
    """
    Base class to describe an input/output value for a component (flow or agent).

    Parameters
    ----------
    name:
        Name of the property. Optional when the property is nested (e.g. ``StringProperty`` in a ``ListProperty``)
    description:
        Optional description of the variable.

        .. important::

            It can be helpful to put a description in two cases:

            * to help potential users to know what this property is about, and simplify the usage of a potential ``Step`` using it
            * to help an LLM if it needs to generate values for this property (e.g. in ``PromptExecutionStep`` or ``AgentExecutionStep``).
    default_value:
        Optional default value. By default, there is no default value (``Property.empty_default``), meaning that if a component has this property
        as input, the value will need to be produced or passed before (it will appear as an input of an
        ``Agent``/``Flow`` OR it needs to be produced by a previous ``Step`` in a ``Flow``).

        .. important::

            Setting a default value might be needed in several cases:

            * when **generating a value for a property** (e.g. ``PromptExecutionStep`` or ``AgentExecutionStep``), it is
              possible that the LLM is not able to generate the value. In this case, the default value of the given property
              type will be used, but you can specify your own ``default_value``.
            * when **a value might not be yet produced / not passed as input** in a ``Flow`` (e.g. caught exception, some other branch execution, ...),
              but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
              the flow can always execute properly with some defaults if needed.
    enum:
        Restricted accepted values of this property (in the case of an enumeration).
        In case of validation, the first value in this tuple as default of the property.
    """

    name: str = ""
    description: str = ""
    default_value: Any = _empty_default
    enum: Optional[Tuple[Any, ...]] = None
    _validate_default_type: bool = field(default=False, hash=False, repr=False, compare=False)
    __metadata_info__: MetadataType = field(default_factory=dict, hash=False, repr=False)

    empty_default: ClassVar[Any] = _empty_default
    """Any: Marker for no default value"""

    # don't use references for properties, its a simple descriptive dataclass
    _can_be_referenced: ClassVar[bool] = False

    @property
    def has_default(self) -> bool:
        """Whether this property has a default value or not"""
        return self.default_value is not Property.empty_default

    def is_value_of_expected_type(self, value: Any) -> bool:
        """
        Check whether a value corresponds to this property's type.

        Parameters
        ----------
        value:
            value for which to check the type
        """
        if self.enum is not None and value not in self.enum:
            return False
        return self._is_value_of_expected_type(value)

    @abstractmethod
    def _is_value_of_expected_type(self, value: Any) -> bool:
        """For classes override"""
        raise NotImplementedError()

    @property
    @abstractmethod
    def _type_default_value(self) -> Any:
        raise NotImplementedError()

    def _validate_or_return_default_value(self, value: Any) -> Any:
        if self.is_value_of_expected_type(value):
            return value
        try:
            return _cast_value_into(value, self)
        except Exception as e:
            logger.debug("Tried to cast `%s` into `%s`, got an error: %s", value, self, e)
        if self.enum is not None and len(self.enum) > 0:
            # when the property is an enumeration, we consider the first value
            # in the enumeration as the default value of the property
            return self.enum[0]
        return self._type_default_value

    def __post_init__(self) -> None:
        if (
            self.has_default
            and self._validate_default_type
            and not self.is_value_of_expected_type(self.default_value)
        ):
            raise ValueError(
                f"Error when initializing: {self}\n"
                f"Default value `{self.default_value}` is not of type `{self.__class__}`"
            )

        if self.enum is None:
            return
        for enum_val in self.enum:
            if not isinstance(
                self,
                (BooleanProperty, IntegerProperty, FloatProperty, StringProperty, NullProperty),
            ):
                raise ValueError(
                    f"Property only support primitive type in enums (BooleanProperty, IntegerProperty, FloatProperty, StringProperty, NullProperty) but got: {enum_val}"
                )

            if not self._is_value_of_expected_type(enum_val):
                raise ValueError(
                    f"Enum value {enum_val!r} does not have the type: {self.__class__.__name__}"
                )

    def __hash__(self) -> int:
        return hash(self.name)

    def pretty_str(self) -> str:
        return (
            str(self)
            .replace(", description=''", "")
            .replace(", default_value=<class 'wayflowcore.property._empty_default'>", "")
            .replace(", enum=None", "")
        )

    def _serialize_to_dict(self, serialization_context: SerializationContext) -> Dict[str, Any]:
        json_schema_dict: Dict[str, Any] = dict(self.to_json_schema())
        json_schema_dict["_component_type"] = Property.__name__
        return json_schema_dict

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: DeserializationContext
    ) -> "SerializableObject":
        return Property.from_json_schema(cast(JsonSchemaParam, input_dict))

    def to_json_schema(self, openai_compatible: bool = False) -> JsonSchemaParam:
        """Convert this ``Property`` object into a corresponding JSON Schema.

        Parameters
        ----------
        openai_compatible
            Adds additional properties into the JSON schema to ensure valid
            requests are made
        """
        json_schema = self._type_to_json_schema(openai_compatible=openai_compatible)
        if self.name != "":
            json_schema["title"] = self.name
        if self.description != "":
            json_schema["description"] = self.description
        if self.has_default:
            json_schema["default"] = self.default_value
        if self.enum is not None:
            json_schema["enum"] = list(self.enum)
        return json_schema

    @staticmethod
    def from_json_schema(
        schema: JsonSchemaParam,
        name: Optional[str] = None,
        description: Optional[str] = None,
        default_value: Optional[Any] = None,
        enum: Optional[Tuple[Any, ...]] = None,
        validate_default_type: bool = True,
    ) -> "Property":
        """
        Convert a JSON Schema into a ``Property`` object.

        Parameters
        ----------
        schema:
            JSON Schema to convert.
        name:
            Optional name to override the ``title`` that might exist in the JSON Schema.
        description:
            Optional description to override the ``description`` that might exist in the JSON Schema.
        default_value:
            Optional default_value to override the ``default`` that might exist in the JSON Schema
        enum:
            Potential values for a enumeration
        validate_default_type:
            Whether to ensure that any default_value has the correct type.
        """
        name = name or schema.get("title", "")
        description = description or schema.get("description", "")
        default_value = default_value or schema.get("default", Property.empty_default)
        enum_list = schema.get("enum", None)
        enum = enum or (tuple(enum_list) if enum_list is not None else None)
        kwargs = dict(
            name=name,
            description=description,
            default_value=default_value,
            enum=enum,
            _validate_default_type=validate_default_type,
        )

        # detection of type
        json_type_as_string = schema.get("type", None)
        if json_type_as_string is None and "anyOf" in schema:
            # first possibility of union
            types = [
                Property.from_json_schema(
                    schema=sub_schema,
                    validate_default_type=validate_default_type,
                )
                for sub_schema in schema["anyOf"]
            ]
            # we add an optional to the union if None default
            if default_value is None and not any(isinstance(p, NullProperty) for p in types):
                types.append(NullProperty())

            return UnionProperty(**kwargs, any_of=types)
        elif isinstance(json_type_as_string, list):
            # second possibility of union
            schema_without_name_and_description = deepcopy(schema)
            schema_without_name_and_description.pop("title", None)
            schema_without_name_and_description.pop("description", None)
            schema_without_name_and_description.pop("default", None)
            types = [
                Property.from_json_schema(
                    schema={**schema_without_name_and_description, "type": sub_type},
                    validate_default_type=validate_default_type,
                )
                for sub_type in json_type_as_string
            ]
            # we add an optional to the union if None default
            if default_value is None and not any(isinstance(p, NullProperty) for p in types):
                types.append(NullProperty())

            return UnionProperty(**kwargs, any_of=types)
        elif json_type_as_string is None:
            return AnyProperty(**kwargs)

        # we add an optional to the union if None default
        if default_value is None and json_type_as_string != "null":
            schema_without_name_and_description = deepcopy(schema)
            schema_without_name_and_description.pop("title", None)
            schema_without_name_and_description.pop("description", None)
            schema_without_name_and_description.pop("default", None)
            return UnionProperty(
                **kwargs,
                any_of=[
                    Property.from_json_schema(
                        schema=schema_without_name_and_description,
                        validate_default_type=validate_default_type,
                    ),
                    NullProperty(),
                ],
            )

        if json_type_as_string in _JSON_TYPES_TO_SIMPLE_VALUE_TYPES:
            return _JSON_TYPES_TO_SIMPLE_VALUE_TYPES[json_type_as_string](**kwargs)

        if json_type_as_string == "array":
            item_type = Property.from_json_schema(
                schema=schema.get("items", {}),
                validate_default_type=validate_default_type,
            )
            return ListProperty(**kwargs, item_type=item_type)

        if not json_type_as_string == "object":
            return AnyProperty(**kwargs)

        if "properties" in schema:
            return ObjectProperty(
                **kwargs,
                properties={
                    param_name: Property.from_json_schema(
                        schema=param_schema,
                        validate_default_type=validate_default_type,
                    )
                    for param_name, param_schema in schema["properties"].items()
                },
            )

        if "additionalProperties" in schema:
            if "key_type" in schema:
                key_type = Property.from_json_schema(
                    schema=schema["key_type"],
                    validate_default_type=validate_default_type,
                )
            else:
                key_type = AnyProperty()

            if isinstance(schema["additionalProperties"], dict):
                value_type = Property.from_json_schema(
                    schema=schema["additionalProperties"],
                    validate_default_type=validate_default_type,
                )
            else:
                value_type = AnyProperty()
                # sometimes, `additionalProperties` can be `True`/`False`,
                # in which case we don't want to assume anything on the type
                # of the value, otherwise further type checking might fail

            return DictProperty(
                **kwargs,
                key_type=key_type,
                value_type=value_type,
            )

        return AnyProperty(**kwargs)

    @abstractmethod
    def _type_to_json_schema(self, openai_compatible: bool = False) -> JsonSchemaParam:
        raise NotImplementedError()

    def copy(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        default_value: Optional[Any] = None,
        enum: Optional[Tuple[Any, ...]] = None,
    ) -> "Property":
        """
        Copy a ``Property`` with potentially some new attributes.

        Parameters
        ----------
        name:
            Optional name to override this property's name. By default uses the same name.
        description:
            Optional description to override this property's description. By default uses the same description.
        default_value:
            Optional default_value to override this property's default_value. By default uses the same default_value.
        enum:
            Values for an enumeration.
        """
        other_args = {
            arg_name: deepcopy(arg_value)
            for arg_name, arg_value in self.__dict__.items()
            if arg_name not in ["name", "description", "default_value", "enum"]
        }
        return self.__class__(
            name=name if name is not None else self.name,
            description=description if description is not None else self.description,
            default_value=default_value if default_value is not None else self.default_value,
            enum=enum,
            **other_args,
        )

    def _match_type_of(self, other: "Property") -> bool:
        return other.__class__ == self.__class__

    def get_type_str(self) -> str:
        return self.__class__.__name__

    def get_python_type_str(self) -> str:
        property_type_str = self.get_type_str()
        for old, new in [
            ("AnyProperty", "Any"),
            ("StringProperty", "str"),
            ("BooleanProperty", "bool"),
            ("FloatProperty", "float"),
            ("IntegerProperty", "int"),
            ("ListProperty", "List"),
            ("DictProperty", "Dict"),
            ("UnionProperty", "Union"),
        ]:
            property_type_str = property_type_str.replace(old, new)
        return property_type_str


@dataclass(frozen=True)
class BooleanProperty(Property):
    """
    Class to describe a boolean input/output value for a component (flow or agent).
    Its JSON type equivalent is ``boolean``.

    Parameters
    ----------
    name:
        Name of the property. Optional when the property is nested (e.g. ``StringProperty`` in a ``ListProperty``)
    description:
        Optional description of the variable.

        .. important::

            It can be helpful to put a description in two cases:

            * to help potential users to know what this property is about, and simplify the usage of a potential ``Step`` using it
            * to help an LLM if it needs to generate values for this property (e.g. in ``PromptExecutionStep`` or ``AgentExecutionStep``).
    default_value:
        Optional default value. By default, there is no default value (``Property.empty_default``), meaning that if a component has this property
        as input, the value will need to be produced or passed before (it will appear as an input of an
        ``Agent``/``Flow`` OR it needs to be produced by a previous ``Step`` in a ``Flow``).

        .. important::

            Setting a default value might be needed in several cases:

            * when **generating a value for a property** (e.g. ``PromptExecutionStep`` or ``AgentExecutionStep``), it is
              possible that the LLM is not able to generate the value. In this case, the default value of the given property
              type will be used, but you can specify your own ``default_value``.
            * when **a value might not be yet produced / not passed as input** in a ``Flow`` (e.g. caught exception, some other branch execution, ...),
              but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
              the flow can always execute properly with some defaults if needed.
    """

    def _is_value_of_expected_type(self, value: Any) -> bool:
        return isinstance(value, bool)

    @property
    def _type_default_value(self) -> Any:
        return False

    def _type_to_json_schema(self, openai_compatible: bool = False) -> JsonSchemaParam:
        return {"type": "boolean"}


@dataclass(frozen=True)
class FloatProperty(Property):
    """
    Class to describe a float input/output value for a component (flow or agent).
    Its JSON type equivalent is ``number``.

    Parameters
    ----------
    name:
        Name of the property. Optional when the property is nested (e.g. ``StringProperty`` in a ``ListProperty``)
    description:
        Optional description of the variable.

        .. important::

            It can be helpful to put a description in two cases:

            * to help potential users to know what this property is about, and simplify the usage of a potential ``Step`` using it
            * to help an LLM if it needs to generate values for this property (e.g. in ``PromptExecutionStep`` or ``AgentExecutionStep``).
    default_value:
        Optional default value. By default, there is no default value (``Property.empty_default``), meaning that if a component has this property
        as input, the value will need to be produced or passed before (it will appear as an input of an
        ``Agent``/``Flow`` OR it needs to be produced by a previous ``Step`` in a ``Flow``).

        .. important::

            Setting a default value might be needed in several cases:

            * when **generating a value for a property** (e.g. ``PromptExecutionStep`` or ``AgentExecutionStep``), it is
              possible that the LLM is not able to generate the value. In this case, the default value of the given property
              type will be used, but you can specify your own ``default_value``.
            * when **a value might not be yet produced / not passed as input** in a ``Flow`` (e.g. caught exception, some other branch execution, ...),
              but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
              the flow can always execute properly with some defaults if needed.
    """

    def _is_value_of_expected_type(self, value: Any) -> bool:
        return isinstance(value, float)

    @property
    def _type_default_value(self) -> Any:
        return 0.0

    def _type_to_json_schema(self, openai_compatible: bool = False) -> JsonSchemaParam:
        return {"type": "number"}


@dataclass(frozen=True)
class MessageProperty(Property):
    """
    Class to describe a message input/output value for a component (flow or agent).

    Parameters
    ----------
    name:
        Name of the property. Optional when the property is nested (e.g. ``StringProperty`` in a ``ListProperty``)
    description:
        Optional description of the variable.

        .. important::

            It can be helpful to put a description in two cases:

            * to help potential users to know what this property is about, and simplify the usage of a potential ``Step`` using it
            * to help an LLM if it needs to generate values for this property (e.g. in ``PromptExecutionStep`` or ``AgentExecutionStep``).
    default_value:
        Optional default value. By default, there is no default value (``Property.empty_default``), meaning that if a component has this property
        as input, the value will need to be produced or passed before (it will appear as an input of an
        ``Agent``/``Flow`` OR it needs to be produced by a previous ``Step`` in a ``Flow``).

        .. important::

            Setting a default value might be needed in several cases:

            * when **generating a value for a property** (e.g. ``PromptExecutionStep`` or ``AgentExecutionStep``), it is
              possible that the LLM is not able to generate the value. In this case, the default value of the given property
              type will be used, but you can specify your own ``default_value``.
            * when **a value might not be yet produced / not passed as input** in a ``Flow`` (e.g. caught exception, some other branch execution, ...),
              but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
              the flow can always execute properly with some defaults if needed.
    """

    def _is_value_of_expected_type(self, value: Any) -> bool:
        from wayflowcore.messagelist import Message

        return isinstance(value, Message)

    @property
    def _type_default_value(self) -> Any:
        from wayflowcore.messagelist import Message, MessageType

        return Message(content="", message_type=MessageType.AGENT)

    def _type_to_json_schema(self, openai_compatible: bool = False) -> JsonSchemaParam:
        return {"type": "object"}


@dataclass(frozen=True)
class IntegerProperty(Property):
    """
    Class to describe an integer input/output value for a component (flow or agent).
    Its JSON type equivalent is ``integer``.

    Parameters
    ----------
    name:
        Name of the property. Optional when the property is nested (e.g. ``StringProperty`` in a ``ListProperty``)
    description:
        Optional description of the variable.

        .. important::

            It can be helpful to put a description in two cases:

            * to help potential users to know what this property is about, and simplify the usage of a potential ``Step`` using it
            * to help an LLM if it needs to generate values for this property (e.g. in ``PromptExecutionStep`` or ``AgentExecutionStep``).
    default_value:
        Optional default value. By default, there is no default value (``Property.empty_default``), meaning that if a component has this property
        as input, the value will need to be produced or passed before (it will appear as an input of an
        ``Agent``/``Flow`` OR it needs to be produced by a previous ``Step`` in a ``Flow``).

        .. important::

            Setting a default value might be needed in several cases:

            * when **generating a value for a property** (e.g. ``PromptExecutionStep`` or ``AgentExecutionStep``), it is
              possible that the LLM is not able to generate the value. In this case, the default value of the given property
              type will be used, but you can specify your own ``default_value``.
            * when **a value might not be yet produced / not passed as input** in a ``Flow`` (e.g. caught exception, some other branch execution, ...),
              but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
              the flow can always execute properly with some defaults if needed.
    """

    def _is_value_of_expected_type(self, value: Any) -> bool:
        return isinstance(value, int)

    @property
    def _type_default_value(self) -> Any:
        return 0

    def _type_to_json_schema(self, openai_compatible: bool = False) -> JsonSchemaParam:
        return {"type": "integer"}


@dataclass(frozen=True)
class StringProperty(Property):
    """
    Class to describe a string input/output value for a component (flow or agent).
    Its JSON type equivalent is ``string``.

    Parameters
    ----------
    name:
        Name of the property. Optional when the property is nested (e.g. ``StringProperty`` in a ``ListProperty``)
    description:
        Optional description of the variable.

        .. important::

            It can be helpful to put a description in two cases:

            * to help potential users to know what this property is about, and simplify the usage of a potential ``Step`` using it
            * to help an LLM if it needs to generate values for this property (e.g. in ``PromptExecutionStep`` or ``AgentExecutionStep``).
    default_value:
        Optional default value. By default, there is no default value (``Property.empty_default``), meaning that if a component has this property
        as input, the value will need to be produced or passed before (it will appear as an input of an
        ``Agent``/``Flow`` OR it needs to be produced by a previous ``Step`` in a ``Flow``).

        .. important::

            Setting a default value might be needed in several cases:

            * when **generating a value for a property** (e.g. ``PromptExecutionStep`` or ``AgentExecutionStep``), it is
              possible that the LLM is not able to generate the value. In this case, the default value of the given property
              type will be used, but you can specify your own ``default_value``.
            * when **a value might not be yet produced / not passed as input** in a ``Flow`` (e.g. caught exception, some other branch execution, ...),
              but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
              the flow can always execute properly with some defaults if needed.
    """

    def _is_value_of_expected_type(self, value: Any) -> bool:
        return isinstance(value, str)

    @property
    def _type_default_value(self) -> Any:
        return ""

    def _type_to_json_schema(self, openai_compatible: bool = False) -> JsonSchemaParam:
        return {"type": "string"}


@dataclass(frozen=True)
class AnyProperty(Property):
    """
    Class to describe any input/output value for a component (flow or agent).

    Parameters
    ----------
    name:
        Name of the property. Optional when the property is nested (e.g. ``StringProperty`` in a ``ListProperty``)
    description:
        Optional description of the variable.

        .. important::

            It can be helpful to put a description in two cases:

            * to help potential users to know what this property is about, and simplify the usage of a potential ``Step`` using it
            * to help an LLM if it needs to generate values for this property (e.g. in ``PromptExecutionStep`` or ``AgentExecutionStep``).
    default_value:
        Optional default value. By default, there is no default value (``Property.empty_default``), meaning that if a component has this property
        as input, the value will need to be produced or passed before (it will appear as an input of an
        ``Agent``/``Flow`` OR it needs to be produced by a previous ``Step`` in a ``Flow``).

        .. important::

            Setting a default value might be needed in several cases:

            * when **generating a value for a property** (e.g. ``PromptExecutionStep`` or ``AgentExecutionStep``), it is
              possible that the LLM is not able to generate the value. In this case, the default value of the given property
              type will be used, but you can specify your own ``default_value``.
            * when **a value might not be yet produced / not passed as input** in a ``Flow`` (e.g. caught exception, some other branch execution, ...),
              but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
              the flow can always execute properly with some defaults if needed.
    """

    def _is_value_of_expected_type(self, value: Any) -> bool:
        return True

    @property
    def _type_default_value(self) -> Any:
        return None

    def _type_to_json_schema(self, openai_compatible: bool = False) -> JsonSchemaParam:
        return {}


@dataclass(frozen=True)
class ListProperty(Property):
    """
    Class to describe a list input/output value for a component (flow or agent). It also contains the type
    of its items.
    Its JSON type equivalent is ``array``.

    Parameters
    ----------
    name:
        Name of the property. Optional when the property is nested (e.g. ``StringProperty`` in a ``ListProperty``)
    description:
        Optional description of the variable.

        .. important::

            It can be helpful to put a description in two cases:

            * to help potential users to know what this property is about, and simplify the usage of a potential ``Step`` using it
            * to help an LLM if it needs to generate values for this property (e.g. in ``PromptExecutionStep`` or ``AgentExecutionStep``).
    default_value:
        Optional default value. By default, there is no default value (``Property.empty_default``), meaning that if a component has this property
        as input, the value will need to be produced or passed before (it will appear as an input of an
        ``Agent``/``Flow`` OR it needs to be produced by a previous ``Step`` in a ``Flow``).

        .. important::

            Setting a default value might be needed in several cases:

            * when **generating a value for a property** (e.g. ``PromptExecutionStep`` or ``AgentExecutionStep``), it is
              possible that the LLM is not able to generate the value. In this case, the default value of the given property
              type will be used, but you can specify your own ``default_value``.
            * when **a value might not be yet produced / not passed as input** in a ``Flow`` (e.g. caught exception, some other branch execution, ...),
              but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
              the flow can always execute properly with some defaults if needed.
    item_type:
        Type of the items of the list. Defaults to ``StringProperty``.
    """

    item_type: Property = field(default_factory=StringProperty)
    __hash__ = Property.__hash__  # Explicitly inherit (helps avoid surprises)

    def _is_value_of_expected_type(self, value: Any) -> bool:
        return isinstance(value, list) and (
            all(self.item_type.is_value_of_expected_type(v) for v in value)
        )

    @property
    def _type_default_value(self) -> Any:
        return []

    def _type_to_json_schema(self, openai_compatible: bool = False) -> JsonSchemaParam:
        return {
            "type": "array",
            "items": self.item_type.to_json_schema(openai_compatible=openai_compatible),
        }

    def get_type_str(self) -> str:
        return f"{self.__class__.__name__}[{self.item_type.get_type_str()}]"


@dataclass(frozen=True)
class DictProperty(Property):
    """
    Class to describe a dictionary input/output value for a component (flow or agent). It also contains the type
    if its keys and its values.
    Its JSON type equivalent is ``object`` with ``additionalProperties``.

    Parameters
    ----------
    name:
        Name of the property. Optional when the property is nested (e.g. ``StringProperty`` in a ``ListProperty``)
    description:
        Optional description of the variable.

        .. important::

            It can be helpful to put a description in two cases:

            * to help potential users to know what this property is about, and simplify the usage of a potential ``Step`` using it
            * to help an LLM if it needs to generate values for this property (e.g. in ``PromptExecutionStep`` or ``AgentExecutionStep``).
    default_value:
        Optional default value. By default, there is no default value (``Property.empty_default``), meaning that if a component has this property
        as input, the value will need to be produced or passed before (it will appear as an input of an
        ``Agent``/``Flow`` OR it needs to be produced by a previous ``Step`` in a ``Flow``).

        .. important::

            Setting a default value might be needed in several cases:

            * when **generating a value for a property** (e.g. ``PromptExecutionStep`` or ``AgentExecutionStep``), it is
              possible that the LLM is not able to generate the value. In this case, the default value of the given property
              type will be used, but you can specify your own ``default_value``.
            * when **a value might not be yet produced / not passed as input** in a ``Flow`` (e.g. caught exception, some other branch execution, ...),
              but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
              the flow can always execute properly with some defaults if needed.
    value_type:
        Type of the values of the dict. Defaults to ``StringProperty``.
    key_type:
        Type of the keys of the dict. Defaults to ``StringProperty``.
    """

    value_type: Property = field(default_factory=StringProperty)
    key_type: Property = field(default_factory=StringProperty)

    def _is_value_of_expected_type(self, value: Any) -> bool:
        return (
            isinstance(value, dict)
            and all(self.key_type.is_value_of_expected_type(k) for k in value.keys())
            and all(self.value_type.is_value_of_expected_type(v) for v in value.values())
        )

    @property
    def _type_default_value(self) -> Any:
        return dict()

    def _type_to_json_schema(self, openai_compatible: bool = False) -> JsonSchemaParam:
        # does not support non string keys
        if not isinstance(self.key_type, (StringProperty, AnyProperty)):
            raise ValueError(
                "Cannot convert string key dict descriptor into json_schema because json_schema only supports string keys"
            )

        return {
            "type": "object",
            "additionalProperties": self.value_type.to_json_schema(
                openai_compatible=openai_compatible
            ),
            **(
                {"key_type": self.key_type.to_json_schema(openai_compatible=openai_compatible)}
                if not self.key_type == AnyProperty()
                else {}
            ),
        }

    def get_type_str(self) -> str:
        return f"{self.__class__.__name__}[{self.key_type.get_type_str()}, {self.value_type.get_type_str()}]"


@dataclass(frozen=True)
class ObjectProperty(Property):
    """
    Class to describe an object input/output value for a component (flow or agent). It contains the names of its
    properties and their associated types. It supports both dictionaries with specific keys & types and objects with
    specific attributes & types.
    Its JSON type equivalent is ``object`` with ``properties``.

    Parameters
    ----------
    name:
        Name of the property. Optional when the property is nested (e.g. ``StringProperty`` in a ``ListProperty``)
    description:
        Optional description of the variable.

        .. important::

            It can be helpful to put a description in two cases:

            * to help potential users to know what this property is about, and simplify the usage of a potential ``Step`` using it
            * to help an LLM if it needs to generate values for this property (e.g. in ``PromptExecutionStep`` or ``AgentExecutionStep``).
    default_value:
        Optional default value. By default, there is no default value (``Property.empty_default``), meaning that if a component has this property
        as input, the value will need to be produced or passed before (it will appear as an input of an
        ``Agent``/``Flow`` OR it needs to be produced by a previous ``Step`` in a ``Flow``).

        .. important::

            Setting a default value might be needed in several cases:

            * when **generating a value for a property** (e.g. ``PromptExecutionStep`` or ``AgentExecutionStep``), it is
              possible that the LLM is not able to generate the value. In this case, the default value of the given property
              type will be used, but you can specify your own ``default_value``.
            * when **a value might not be yet produced / not passed as input** in a ``Flow`` (e.g. caught exception, some other branch execution, ...),
              but you still want the flow to execute. Putting a default value helps ensuring that whatever happens before,
              the flow can always execute properly with some defaults if needed.
    properties:
        Dictionary of property names and their types. Defaults without any property.
    """

    properties: Dict[str, "Property"] = field(default_factory=dict)

    def _is_value_of_expected_type(self, value: Any) -> bool:
        return all(
            (
                self._check_dict_has_correct_entry(value, prop_name, property_)
                if isinstance(value, dict)
                else self._check_object_has_correct_attribute(value, prop_name, property_)
            )
            for prop_name, property_ in self.properties.items()
        )

    @staticmethod
    def _check_dict_has_correct_entry(
        value: Dict[str, Any], name: str, property_: Property
    ) -> bool:
        return name in value and property_.is_value_of_expected_type(value[name])

    @staticmethod
    def _check_object_has_correct_attribute(value: Any, name: str, value_type: Property) -> bool:
        return hasattr(value, name) and value_type.is_value_of_expected_type(getattr(value, name))

    @property
    def _type_default_value(self) -> Any:
        return {
            prop_name: prop_value._type_default_value
            for prop_name, prop_value in self.properties.items()
        }

    def _validate_or_return_default_value(self, value: Any) -> Any:
        if not isinstance(value, dict):
            # just check or return default object
            return value if self.is_value_of_expected_type(value) else self._type_default_value

        # if dict, we can try to validate or default each element
        new_dict = {}
        for prop_name, property_ in self.properties.items():
            new_dict[prop_name] = property_._validate_or_return_default_value(
                value.get(prop_name, None)
            )
        return new_dict

    def _type_to_json_schema(self, openai_compatible: bool = False) -> JsonSchemaParam:
        json_schema: JsonSchemaParam = {
            "type": "object",
            "properties": {
                prop_name: property_.to_json_schema(openai_compatible=openai_compatible)
                for prop_name, property_ in self.properties.items()
            },
        }
        if openai_compatible:
            json_schema["additionalProperties"] = False
            json_schema["required"] = list(json_schema["properties"].keys())
            for property_name, property_ in json_schema["properties"].items():
                if "default" in property_:
                    logger.info(
                        "The LLM cannot access the default value of the property `%s=%s`. "
                        "If you need to preserve this behavior, define the property as a union "
                        "with `NullProperty` and handle the default manually.",
                        property_name,
                        property_["default"],
                    )
        return json_schema

    def get_type_str(self) -> str:
        field_types_str = "\n".join(
            f"    {name}: {property_.get_type_str()}" for name, property_ in self.properties.items()
        )
        return f"{self.__class__.__name__}[\n{field_types_str}\n]"


@dataclass(frozen=True)
class NullProperty(Property):

    def _is_value_of_expected_type(self, value: Any) -> bool:
        return value is None

    @property
    def _type_default_value(self) -> Any:
        return None

    def _type_to_json_schema(self, openai_compatible: bool = False) -> JsonSchemaParam:
        return {"type": "null"}


@dataclass(frozen=True)
class UnionProperty(Property):
    any_of: List[Property] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.any_of) == 0:
            raise ValueError("`UnionProperty` should contain at least one type")

    def _is_value_of_expected_type(self, value: Any) -> bool:
        return any(property_.is_value_of_expected_type(value) for property_ in self.any_of)

    @property
    def _type_default_value(self) -> Any:
        return self.any_of[0]._type_default_value

    def _type_to_json_schema(self, openai_compatible: bool = False) -> JsonSchemaParam:
        return {
            "anyOf": [
                property_.to_json_schema(openai_compatible=openai_compatible)
                for property_ in self.any_of
            ]
        }

    def get_type_str(self) -> str:
        union_types_str = ", ".join(property_.get_type_str() for property_ in self.any_of)
        return f"{self.__class__.__name__}[{union_types_str}]"


_JSON_TYPES_TO_SIMPLE_VALUE_TYPES: Dict[Optional[str], Type[Property]] = {
    "boolean": BooleanProperty,
    "integer": IntegerProperty,
    "number": FloatProperty,
    "string": StringProperty,
    "null": NullProperty,
}

_SIMPLE_PROPERTY_CLASSES: Set[Type[Property]] = set(_JSON_TYPES_TO_SIMPLE_VALUE_TYPES.values())


def _try_cast_str_value_to_type(value: str, value_type: Property) -> Any:
    """Get type to cast to if supported. We only support the following casting:
    From `str` to
    - int
    - bool
    - float
    """
    if not isinstance(value, str):
        return value
    try:
        converted_value: Any
        if isinstance(value_type, BooleanProperty):
            converted_value = bool(value)
        elif isinstance(value_type, IntegerProperty):
            converted_value = int(value)
        elif isinstance(value_type, FloatProperty):
            converted_value = float(value)
        else:
            return value
        logger.debug(
            "Successfully casted value %s to type %s (value type is now %s)",
            value,
            value_type,
            type(converted_value),
        )
        return converted_value
    except:
        logger.debug(
            "Failed to cast value %s to type %s (value type will remain %s)",
            value,
            value_type,
            type(value),
        )
        return value


def string_to_property(description: Union[str, Property]) -> Property:
    if isinstance(description, Property):
        return description
    elif isinstance(description, str):
        return StringProperty(
            name=description,
            description=f'The "{description}" extracted value from the raw json text',
        )
    else:
        raise ValueError(
            "Input description should be of type `str` or `Property`, "
            f"was {description!r} of type ({type(description)})"
        )


def _format_default_value(property_: Property) -> Any:
    default_value = property_.default_value
    if default_value is not Property.empty_default:
        return default_value
    return property_._type_default_value


def _convert_list_of_properties_to_json_schema(properties: List[Property]) -> JsonSchemaParam:
    if len(properties) == 1 and isinstance(properties[0], ObjectProperty):
        json_schema: JsonSchemaParam = properties[0].to_json_schema()
        # add `required` field to help LLMs
        json_schema["required"] = [
            property_name
            for property_name, property_json_schema in json_schema["properties"].items()
            if "default" not in property_json_schema
        ]
        # don't put the title because the name already appears as a key
        # in the object properties Dict[str, JSONSchema]
        json_schema.pop("title", None)
        return json_schema
    return {
        "title": "expected_output",
        "description": "the expected output of the generation",
        "type": "object",  # required in an json_schema
        "properties": {prop_value.name: prop_value.to_json_schema() for prop_value in properties},
        "required": [
            prop_value.name
            for prop_value in properties
            if prop_value.default_value is Property.empty_default
        ],
    }


def _property_can_be_casted_into_property(from_type: Property, to_type: Property) -> bool:
    """Casting rules"""
    if to_type.enum is not None and (
        # from_type is not limited to a finite set of values
        from_type.enum is None
        # some value from the from_type allowed values is not accepted in to_type
        or any(val_ not in to_type.enum for val_ in from_type.enum)
    ):
        return False
    return (
        (
            type(from_type) == type(to_type)
            and type(from_type) in _SIMPLE_PROPERTY_CLASSES  # simple type
        )
        or (isinstance(to_type, AnyProperty))
        or (isinstance(to_type, StringProperty))
        or (isinstance(from_type, IntegerProperty) and isinstance(to_type, FloatProperty))
        or (isinstance(from_type, FloatProperty) and isinstance(to_type, IntegerProperty))
        or (
            isinstance(from_type, (FloatProperty, IntegerProperty))
            and isinstance(to_type, BooleanProperty)
        )
        or (
            isinstance(from_type, BooleanProperty)
            and isinstance(to_type, (FloatProperty, IntegerProperty))
        )
        or (
            isinstance(from_type, ListProperty)
            and isinstance(to_type, ListProperty)
            and _property_can_be_casted_into_property(from_type.item_type, to_type.item_type)
        )
        or (
            isinstance(from_type, DictProperty)
            and isinstance(to_type, DictProperty)
            and _property_can_be_casted_into_property(from_type.key_type, to_type.key_type)
            and _property_can_be_casted_into_property(from_type.value_type, to_type.value_type)
        )
        or (
            isinstance(from_type, ObjectProperty)
            and isinstance(to_type, DictProperty)
            and all(
                _property_can_be_casted_into_property(source_property_, to_type.value_type)
                for source_property_name, source_property_ in from_type.properties.items()
            )
            and _property_can_be_casted_into_property(StringProperty(), to_type.key_type)
        )
        or (
            isinstance(from_type, ObjectProperty)
            and (
                (
                    isinstance(to_type, ObjectProperty)
                    and all(
                        source_property_name in to_type.properties
                        for source_property_name, source_property_ in from_type.properties.items()
                    )
                    and all(
                        _property_can_be_casted_into_property(
                            source_property_, to_type.properties[source_property_name]
                        )
                        for source_property_name, source_property_ in from_type.properties.items()
                    )
                )
                or (  # object can be casted into dict if properties have proper types
                    isinstance(to_type, DictProperty)
                    and _property_can_be_casted_into_property(StringProperty(), to_type.key_type)
                    and all(
                        _property_can_be_casted_into_property(source_property_, to_type.value_type)
                        for source_property_name, source_property_ in from_type.properties.items()
                    )
                )
            )
        )
        or (
            isinstance(to_type, UnionProperty)
            # for all from_type, it needs to be cast-able to at least one of the to_type
            and all(
                any(
                    _property_can_be_casted_into_property(from_type, property_)
                    for property_ in to_type.any_of
                )
                for from_type in (
                    from_type.any_of if isinstance(from_type, UnionProperty) else [from_type]
                )
            )
        )
    )


def _cast_value_into(value: Any, target_type: Property) -> Any:
    casted_value = _try_cast_value_into(value, target_type)
    if target_type.enum is None:
        return casted_value

    if casted_value not in target_type.enum:
        raise TypeError(
            f"Casted value {casted_value} does not respect the enum target type: {target_type}"
        )
    return casted_value


def _try_cast_value_into(value: Any, target_type: Property) -> Any:
    """Casting rules"""
    if target_type.is_value_of_expected_type(value) or isinstance(target_type, AnyProperty):
        # no changes to do
        return value

    if isinstance(target_type, StringProperty):
        if value is None:
            # for None, we prefer returning empty string than `null`
            return ""
        try:
            # try json serialization
            return json.dumps(value)
        except TypeError as e:
            # resolve on __str__ if object is not serializable
            return str(e)
    elif isinstance(value, int) and isinstance(target_type, FloatProperty):
        return float(value)
    elif isinstance(value, float) and isinstance(target_type, IntegerProperty):
        return int(value)
    elif isinstance(value, (float, int)) and isinstance(target_type, BooleanProperty):
        return value != 0
    elif isinstance(value, bool) and isinstance(target_type, FloatProperty):
        return 1.0 if value else 0.0
    elif isinstance(value, bool) and isinstance(target_type, IntegerProperty):
        return 1 if value else 0

    # nested types
    elif isinstance(value, list) and isinstance(target_type, ListProperty):
        return [_cast_value_into(single_value, target_type.item_type) for single_value in value]

    elif isinstance(value, dict) and isinstance(target_type, DictProperty):
        return {
            _cast_value_into(key, target_type.key_type): _cast_value_into(
                value, target_type.value_type
            )
            for key, value in value.items()
        }
    elif isinstance(target_type, ObjectProperty):
        if not isinstance(value, dict):
            logger.warning(
                "Cannot convert non dict object types: %s to %s", value, str(target_type)
            )
            return {
                prop_name: _cast_value_into(getattr(value, prop_name), property_)
                for prop_name, property_ in target_type.properties.items()
            }
        return {
            prop_name: _cast_value_into(value[prop_name], property_)
            for prop_name, property_ in target_type.properties.items()
        }
    elif isinstance(target_type, UnionProperty):
        if any(property_.is_value_of_expected_type(value) for property_ in target_type.any_of):
            # value already has one of the types of the union
            return value
        else:
            for property_ in target_type.any_of:
                try:
                    return _cast_value_into(value, property_)
                except ValueError as e:
                    pass
            raise ValueError(
                f"Value {value} cannot be cast into any of the types of the Union: {target_type}"
            )
    else:
        raise ValueError(f"Type casting is not implemented for case: {value=}, {target_type=}")


def _get_python_type_str(value: Any) -> str:
    """
    Generates a string representation of the type of the given value.

    Parameter
    ---------
    value:
        The value to generate the type string for.

    Returns
    -------
    A string representation of the type of the given value.
    """
    if value is None:
        return "NoneType"
    if isinstance(value, list):
        if not value:
            return "List[Any]"

        item_types = [_get_python_type_str(item) for item in value]
        if len(set(item_types)) == 1:
            return f"List[{item_types[0]}]"
        else:
            return f"List[Union[{', '.join(item_types)}]]"

    elif isinstance(value, dict):
        if not value:
            return "Dict[Any, Any]"

        key_types = [_get_python_type_str(key) for key in value.keys()]
        value_types = [_get_python_type_str(value[key]) for key in value.keys()]

        if len(set(key_types)) == 1 and len(set(value_types)) == 1:
            return f"Dict[{key_types[0]}, {value_types[0]}]"
        elif len(set(key_types)) == 1 and len(set(value_types)) != 1:
            return f"Dict[{key_types[0]}, Union[{', '.join(value_types)}]]"
        elif len(set(key_types)) != 1 and len(set(value_types)) == 1:
            return f"Dict[Union[{', '.join(key_types)}], {value_types[0]}]"
        else:
            return f"Dict[Union[{', '.join(key_types)}], Union[{', '.join(value_types)}]]"

    elif hasattr(value, "__dict__"):
        fields = [
            (key, value_) for key, value_ in value.__dict__.items() if not key.startswith("__")
        ]

        field_types_str = "\n".join(
            f"    {name}: {_get_python_type_str(field)}" for name, field in fields
        )
        return f"{type(value).__name__}[\n{field_types_str}\n]"

    else:
        return type(value).__name__


def _output_properties_to_response_format_property(outputs: List[Property]) -> Property:
    if len(outputs) == 1 and isinstance(outputs[0], (ListProperty, ObjectProperty, DictProperty)):
        return outputs[0]
    return ObjectProperty(
        name="expected_output",
        description="the expected output of the generation",
        properties={property_.name: property_ for property_ in outputs},
    )
