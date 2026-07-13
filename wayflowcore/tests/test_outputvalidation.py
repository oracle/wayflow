# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest

from wayflowcore._outputvalidation import validate_strict_outputs
from wayflowcore.exceptions import StructuredOutputValidationError
from wayflowcore.property import (
    DictProperty,
    IntegerProperty,
    ListProperty,
    ObjectProperty,
    StringProperty,
)


@pytest.mark.parametrize(
    ("outputs", "descriptors"),
    [
        ({"description": ["condition"]}, [StringProperty(name="description")]),
        ({"count": "one"}, [IntegerProperty(name="count")]),
        ({"answer": "maybe"}, [StringProperty(name="answer", enum=("yes", "no"))]),
        ({"findings": ["valid", 1]}, [ListProperty(name="findings", item_type=StringProperty())]),
        ({"scores": {"first": "mid"}}, [DictProperty(name="scores", value_type=IntegerProperty())]),
        (
            {"details": {"reason": "valid", "unexpected": "value"}},
            [ObjectProperty(name="details", properties={"reason": StringProperty(name="reason")})],
        ),
        (
            {"report": {"findings": [{"description": ["condition"]}]}},
            [
                ObjectProperty(
                    name="report",
                    properties={
                        "findings": ListProperty(
                            name="findings",
                            item_type=ObjectProperty(properties={"description": StringProperty()}),
                        )
                    },
                )
            ],
        ),
        ({"extra": "value"}, [StringProperty(name="required")]),
    ],
    ids=[
        "string-receives-list",
        "integer-receives-string",
        "enum-value-is-invalid",
        "list-item-has-wrong-type",
        "dict-value-has-wrong-type",
        "object-has-unexpected-field",
        "nested-object-has-wrong-type",
        "missing-and-unexpected-top-level-fields",
    ],
)
def test_strict_validation_rejects_invalid_outputs(outputs, descriptors):
    with pytest.raises(StructuredOutputValidationError):
        validate_strict_outputs(outputs, descriptors)


def test_strict_validation_uses_explicit_defaults():
    descriptors = [
        StringProperty(name="description"),
        ObjectProperty(
            name="details",
            properties={"reason": StringProperty(name="reason", default_value="unknown")},
        ),
        StringProperty(name="optional", default_value="default"),
    ]

    assert validate_strict_outputs({"description": "condition", "details": {}}, descriptors) == {
        "description": "condition",
        "details": {"reason": "unknown"},
        "optional": "default",
    }
