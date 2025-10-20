# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import pytest

from wayflowcore.property import (
    AnyProperty,
    BooleanProperty,
    DictProperty,
    FloatProperty,
    ListProperty,
    Property,
    StringProperty,
)
from wayflowcore.serialization import autodeserialize, deserialize, serialize
from wayflowcore.serialization.context import DeserializationContext

from ..conftest import assert_str_equal_ignoring_white_space


def test_serde_nested_value_type_description_of_list_of_dict_of_float() -> None:
    vtd = ListProperty(
        name="dummy name",
        description="dummy description",
        default_value=[{"zero": 0.0}, {}],
        item_type=DictProperty(value_type=FloatProperty(), key_type=AnyProperty()),
    )
    serialized_vtd = serialize(vtd)
    expected_string = """
        _component_type: Property
        default:
          - zero: 0.0
          - {}
        description: dummy description
        items:
            additionalProperties:
              type: number
            type: object
        title: dummy name
        type: array
    """
    assert_str_equal_ignoring_white_space(serialized_vtd, expected_string)
    # since it's a dataclass, we can compare if they are the same object (meaning all fields are the same)
    assert vtd == deserialize(Property, serialized_vtd)


def test_serde_value_type_description_of_float() -> None:
    vtd = FloatProperty(
        name="dummy name",
        description="dummy description",
        default_value=0.3,
    )
    serialized_vtd = serialize(vtd)
    expected_string = """
        _component_type: Property
        default: 0.3
        description: dummy description
        title: dummy name
        type: number
    """
    assert_str_equal_ignoring_white_space(serialized_vtd, expected_string)
    assert vtd == deserialize(Property, serialized_vtd)


def test_autoserde_value_type_description_of_float() -> None:
    vtd = FloatProperty(
        name="dummy name",
        description="dummy description",
        default_value=0.0,
    )
    assert vtd == autodeserialize(serialize(vtd))


@pytest.mark.parametrize(
    "serialized_type, expected_value_type",
    [
        ({"type": "number", "_component_type": "Property"}, FloatProperty()),
        ({"type": "string", "_component_type": "Property"}, StringProperty()),
        (
            {"type": "array", "items": {"type": "string"}, "_component_type": "Property"},
            ListProperty(item_type=StringProperty()),
        ),
        (
            {
                "type": "object",
                "additionalProperties": {"type": "boolean"},
                "_component_type": "Property",
            },
            DictProperty(value_type=BooleanProperty(), key_type=AnyProperty()),
        ),
        ({}, AnyProperty()),
    ],
)
def test_value_type_deserialization(serialized_type, expected_value_type):
    value_type = Property._deserialize_from_dict(
        serialized_type, deserialization_context=DeserializationContext()
    )

    assert value_type == expected_value_type
