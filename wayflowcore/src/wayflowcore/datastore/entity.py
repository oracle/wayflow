# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass, field, fields
from typing import Any, Dict

from wayflowcore.property import (
    NullProperty,
    ObjectProperty,
    Property,
    UnionProperty,
    VectorProperty,
)
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject, deserialize_from_dict

# This is how we represent the data described by an `Entity`
EntityAsDictT = Dict[str, Any]


@dataclass(frozen=True)
class Entity(ObjectProperty, SerializableObject):
    """An ``Entity`` defines the properties of an object in a collection
    manipulated by a datastore.

    Entities can be used to model relational entities, where their
    properties are the columns of the tables, as well as any
    other kind of entity. For example, a text file on OCI Object Storage
    can be represented as an entity with properties file name and content.

    Parameters
    ----------
    name:
        Optional name of the entities described by this object.

        .. note::

            In a datastore, the relevant name is the one provided as the
            dictionary key of the ``schema`` parameter for the corresponding
            ``Entity``.

    description:
        Optional description of the entity type.

        .. important::

            It can be helpful to put a description in the following cases:

            * to help users know what this entity is about, and simplify the usage of a ``Step`` using it
            * to help a LLM if it needs to generate values for this entity (e.g. in ``DatastoreCreateStep``)
            * to help an agent when tools are generated from the Datastore operations,
              to automatically provide a comprehensive docstring for that tool

    default_value:
        Optional default value.
    properties:
        Mapping of property names and their types. Defaults to no properties.

        .. important::
            If a property is not required (but doesn't have a default value conforming to its type),
            use the ``nullable`` helper function to create a new property that can be set to `None`.

    Examples
    --------
    >>> from wayflowcore.datastore import Entity, nullable
    >>> from wayflowcore.property import StringProperty, IntegerProperty

    You can define an entity representing documents with metadata as follows:

    >>> documents = Entity(
    ...     description="Documents in object store, including category metadata",
    ...     properties={
    ...         "id": IntegerProperty(),
    ...         # By default, documents are created empty
    ...         "content": StringProperty(default_value=""),
    ...         # Category is empty by default
    ...         "category": nullable(StringProperty()),
    ...     }
    ... )

    """

    _has_vector_properties: bool = field(init=False)

    def __post_init__(self) -> None:
        # Need to set _has_vector_properties as it is a frozen dataclass
        object.__setattr__(
            self,
            "_has_vector_properties",
            any(isinstance(prop, VectorProperty) for prop in self.properties.values()),
        )

    def _serialize_to_dict(self, serialization_context: SerializationContext) -> Dict[str, Any]:
        # We just need to distinguish the exact types of Entity and ObjectProperty
        object_property_dict = super()._serialize_to_dict(serialization_context)
        object_property_dict["_component_type"] = "Entity"
        return object_property_dict

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: DeserializationContext
    ) -> "Entity":
        entity_as_obj_property = deserialize_from_dict(
            ObjectProperty, input_dict, deserialization_context
        )
        return Entity(
            **{
                f.name: getattr(entity_as_obj_property, f.name)
                for f in fields(entity_as_obj_property)
            }
        )

    def get_entity_defaults(self) -> Dict[str, Any]:
        """Construct a dictionary of default values for properties that
        have them.

        This method can be helpful to supplement default values in an
        entity object. Note that datastores already provide this
        functionality on creation of an object.

        Returns
        -------
        dict[str, Any]
            A dictionary mapping each property name in the dictionary to its
            default value (if it has one, otherwise it will not be part of
            this dictionary)
        """
        return {p_name: p.default_value for p_name, p in self.properties.items() if p.has_default}


def nullable(property: Property) -> UnionProperty:
    """Makes a property nullable.

    Parameters
    ----------
    property : Property
        Property that can be null. If a default value is set on this
        property the resulting nullable property will have the same
        default value. If no default value is set, the default of the
        resulting property is ``None``.

    Returns
    -------
    UnionProperty
        A new property descriptor that is equivalent to the original one,
        but that can also be ``None``.
    """
    default_value = (
        property.default_value if property.default_value != Property.empty_default else None
    )
    return UnionProperty(
        property.name,
        description=property.description,
        default_value=default_value,
        any_of=[NullProperty(), property],
    )
