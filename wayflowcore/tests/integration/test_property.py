# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from typing import Any, List, Tuple

import pytest

from wayflowcore.property import (
    AnyProperty,
    BooleanProperty,
    DictProperty,
    FloatProperty,
    IntegerProperty,
    ListProperty,
    NullProperty,
    ObjectProperty,
    Property,
    StringProperty,
    UnionProperty,
    _property_can_be_casted_into_property,
)

DESCRIPTIONS_AND_SCHEMAS = [
    (StringProperty(), {"type": "string"}),  # 0
    (IntegerProperty(), {"type": "integer"}),  # 1
    (FloatProperty(), {"type": "number"}),  # 2
    (BooleanProperty(), {"type": "boolean"}),  # 3
    (  # 4
        DictProperty(value_type=FloatProperty()),
        {
            "type": "object",
            "additionalProperties": {"type": "number"},
            "key_type": {"type": "string"},
        },
    ),
    (
        ListProperty(item_type=IntegerProperty()),
        {"type": "array", "items": {"type": "integer"}},
    ),  # 5
    (AnyProperty(), {}),  # 6
    (  # 7
        ObjectProperty(properties={"some_field": IntegerProperty(description="some_description")}),
        {
            "type": "object",
            "properties": {
                "some_field": {
                    "type": "integer",
                    "description": "some_description",
                }
            },
        },
    ),
    (  # 8
        StringProperty(name="some_name", description="some_description"),
        {"type": "string", "title": "some_name", "description": "some_description"},
    ),
    (  # 9
        IntegerProperty(name="some_int", description="some_description"),
        {"type": "integer", "title": "some_int", "description": "some_description"},
    ),
    (  # 10
        FloatProperty(name="some_float", description="some_description"),
        {"type": "number", "title": "some_float", "description": "some_description"},
    ),
    (  # 11
        BooleanProperty(
            name="some_bool",
            description="some_description",
        ),
        {"type": "boolean", "title": "some_bool", "description": "some_description"},
    ),
    (  # 12
        DictProperty(
            name="some_dict",
            description="some_description",
            value_type=FloatProperty(),
            key_type=AnyProperty(),
        ),
        {
            "type": "object",
            "title": "some_dict",
            "description": "some_description",
            "additionalProperties": {"type": "number"},
        },
    ),
    (  # 13
        ListProperty(name="some_list", description="some_description", item_type=FloatProperty()),
        {
            "type": "array",
            "title": "some_list",
            "description": "some_description",
            "items": {"type": "number"},
        },
    ),
    (  # 14
        AnyProperty(name="some_any", description="some_description"),
        {"title": "some_any", "description": "some_description"},
    ),
    (  # 15
        ObjectProperty(
            name="some_struct",
            description="some_description",
            properties={"some_field": IntegerProperty(description="some_description")},
        ),
        {
            "title": "some_struct",
            "description": "some_description",
            "type": "object",
            "properties": {
                "some_field": {
                    "type": "integer",
                    "description": "some_description",
                }
            },
        },
    ),
    (NullProperty(name="null_property"), {"title": "null_property", "type": "null"}),  # 16
    (  # 17
        UnionProperty(name="union_property", any_of=[NullProperty(), IntegerProperty()]),
        {
            "title": "union_property",
            "anyOf": [
                {"type": "null"},
                {"type": "integer"},
            ],
        },
    ),
]
SCHEMAS_AND_DESCRIPTIONS = [(y, x) for x, y in DESCRIPTIONS_AND_SCHEMAS]


@pytest.mark.parametrize("value_type_description,expected_json_schema", DESCRIPTIONS_AND_SCHEMAS)
def test_convert_value_type_description_into_json_schema(
    value_type_description, expected_json_schema
):
    schema = value_type_description.to_json_schema()
    assert schema == expected_json_schema


@pytest.mark.parametrize("json_schema,expected_value_type", SCHEMAS_AND_DESCRIPTIONS)
def test_convert_json_schema_into_value_type_description(json_schema, expected_value_type):
    value_type = Property.from_json_schema(json_schema)
    assert value_type == expected_value_type


def test_list_of_types_can_be_decoded_in_union_property():
    json_schema = {
        "title": "union_property",
        "type": ["null", "integer"],
    }
    expected_property = UnionProperty(
        name="union_property", any_of=[NullProperty(), IntegerProperty()]
    )
    assert Property.from_json_schema(json_schema) == expected_property


def test_union_raises_when_no_types():
    with pytest.raises(ValueError):
        UnionProperty()


@dataclass
class MyCustomObject:
    some_other_field: int


TYPES_AND_VALUES: List[Tuple[Property, Any]] = [
    (StringProperty(), "some_string"),  # 0
    (IntegerProperty(), 1),  # 1
    (FloatProperty(), 2.0),  # 2
    (BooleanProperty(), True),  # 3
    (  # 4
        DictProperty(key_type=AnyProperty(), value_type=StringProperty()),
        {"some_key": "some_value", 1: "some_int_key_value"},
    ),
    (ListProperty(item_type=IntegerProperty()), [1, 4, 5, 6]),  # 5
    (ListProperty(item_type=StringProperty()), ["", "fe2", "f32"]),  # 6
    (  # 7
        ObjectProperty(properties={"some_field": IntegerProperty(description="some_description")}),
        {"some_field": 1},
    ),
    (  # 8
        ObjectProperty(
            properties={"some_other_field": IntegerProperty(description="some_description")}
        ),
        MyCustomObject(2),
    ),
    (NullProperty(), None),
]


@pytest.mark.parametrize("value_type,value", TYPES_AND_VALUES)
def test_check_type_is_correctly_checked(value_type, value):
    # check expected type is validated
    assert value_type.is_value_of_expected_type(value)

    # check other types are not validated
    for _, other_value in TYPES_AND_VALUES:
        if other_value != value:
            assert not value_type.is_value_of_expected_type(other_value)


@pytest.mark.parametrize(
    "value_type,value",
    [
        (UnionProperty(any_of=[IntegerProperty(), FloatProperty()]), 1),
        (UnionProperty(any_of=[IntegerProperty(), FloatProperty()]), 1.0),
        (UnionProperty(any_of=[IntegerProperty(), NullProperty()]), 1),
        (UnionProperty(any_of=[IntegerProperty(), NullProperty()]), None),
    ],
)
def test_union_type_validations(value_type, value):
    # check expected type is validated
    assert value_type.is_value_of_expected_type(value)


@pytest.mark.parametrize(
    "property_cls,enum",
    [
        (StringProperty, ("a", "b", "c")),
        (IntegerProperty, (1, 2, 3)),
        (BooleanProperty, (True, False)),
        (FloatProperty, (1.2, 1.3, 1.4)),
    ],
)
def test_property_can_have_enum_values(property_cls, enum):
    prop_ = property_cls(enum=enum)  # type: ignore
    for e in enum:
        assert prop_.is_value_of_expected_type(e) is True
    assert prop_.is_value_of_expected_type(["something"]) is False


def test_mixed_enum_type_is_supported_nested():
    property_ = UnionProperty(
        any_of=[
            IntegerProperty(enum=(1, 2, 3)),
            StringProperty(enum=("1", "2", "3")),
        ]
    )
    assert property_.is_value_of_expected_type("3") is True
    assert property_.is_value_of_expected_type(1) is True
    assert property_.is_value_of_expected_type(4) is False


def test_mixed_enum_type_is_supported():
    property_ = UnionProperty(
        any_of=[IntegerProperty(), StringProperty()], enum=("1", "2", "3", 1, 2, 3)
    )
    assert property_.is_value_of_expected_type("3") is True
    assert property_.is_value_of_expected_type(1) is True
    assert property_.is_value_of_expected_type(4) is False


def test_enum_with_non_primitive_types_raises():
    with pytest.raises(ValueError, match="Property only support primitive type in enums"):
        ListProperty(enum=([],))


@pytest.mark.parametrize(
    "property_cls,enum",
    [
        (StringProperty, ["a", "b", 1]),
        (IntegerProperty, [1, 2, "d"]),
    ],
)
def test_property_with_wrong_type_enum_raises(property_cls, enum):
    with pytest.raises(ValueError, match="Enum value .* does not have the type"):
        prop_ = property_cls(enum=enum)  # type: ignore


def test_enum_can_be_casted_in_its_type():
    source_property = StringProperty(enum=("1", "2", "3"))
    destination_property = StringProperty()
    assert _property_can_be_casted_into_property(source_property, destination_property) is True


def test_property_cannot_be_casted_in_an_enum():
    source_property = StringProperty()
    destination_property = StringProperty(enum=("1", "2", "3"))
    assert _property_can_be_casted_into_property(source_property, destination_property) is False


def test_enum_cannot_be_casted_into_other_enum():
    source_property = StringProperty(enum=("1", "2", "3"))
    destination_property = StringProperty(enum=("1", "2"))
    assert _property_can_be_casted_into_property(source_property, destination_property) is False


def test_enum_can_be_casted_into_larger_enum():
    source_property = StringProperty(enum=("1", "2"))
    destination_property = StringProperty(enum=("1", "2", "3"))
    assert _property_can_be_casted_into_property(source_property, destination_property) is True
