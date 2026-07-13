# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Validation for structured LLM outputs."""

from typing import Any

from wayflowcore.exceptions import StructuredOutputValidationError
from wayflowcore.property import (
    DictProperty,
    ListProperty,
    ObjectProperty,
    Property,
    UnionProperty,
)


def validate_strict_outputs(
    outputs: dict[str, Any], expected_outputs: list[Property]
) -> dict[str, Any]:
    """Validate outputs without coercion or implicit defaults.

    Explicit descriptor defaults make fields optional and are materialized in the
    returned mapping. All other descriptor mismatches are reported together.
    """
    validated_outputs: dict[str, Any] = {}
    violations: list[str] = []
    expected_by_name = {output.name: output for output in expected_outputs}

    for output_name in outputs:
        if output_name not in expected_by_name:
            violations.append(f"{output_name}: unexpected field")

    for output_name, output in expected_by_name.items():
        if output_name not in outputs:
            if output.has_default:
                validated_outputs[output_name] = output.default_value
            else:
                violations.append(f"{output_name}: missing required field")
            continue

        value, value_violations = _validate_output(
            value=outputs[output_name], output=output, field_name=output_name
        )
        validated_outputs[output_name] = value
        violations.extend(value_violations)

    if violations:
        raise StructuredOutputValidationError(violations=violations)
    return validated_outputs


def _validate_output(value: Any, output: Property, field_name: str) -> tuple[Any, list[str]]:
    validated_value: Any
    violations: list[str] = []

    if isinstance(output, ObjectProperty):
        if not isinstance(value, dict):
            return value, [_type_violation(field_name, output, value)]

        validated_value = {}
        for key in value:
            if key not in output.properties:
                violations.append(f"{field_name}.{key}: unexpected field")
        for name, nested_property in output.properties.items():
            nested_field_name = f"{field_name}.{name}"
            if name not in value:
                if nested_property.has_default:
                    validated_value[name] = nested_property.default_value
                else:
                    violations.append(f"{nested_field_name}: missing required field")
                continue
            nested_value, nested_violations = _validate_output(
                value[name], nested_property, nested_field_name
            )
            validated_value[name] = nested_value
            violations.extend(nested_violations)
        return validated_value, violations

    if isinstance(output, ListProperty):
        if not isinstance(value, list):
            return value, [_type_violation(field_name, output, value)]
        validated_value = []
        for index, item in enumerate(value):
            nested_value, nested_violations = _validate_output(
                item, output.item_type, f"{field_name}[{index}]"
            )
            validated_value.append(nested_value)
            violations.extend(nested_violations)
        return validated_value, violations

    if isinstance(output, DictProperty):
        if not isinstance(value, dict):
            return value, [_type_violation(field_name, output, value)]
        validated_value = {}
        for key, item in value.items():
            _, key_violations = _validate_output(key, output.key_type, f"{field_name}.<key>")
            nested_value, nested_violations = _validate_output(
                item, output.value_type, f"{field_name}.{key}"
            )
            validated_value[key] = nested_value
            violations.extend(key_violations)
            violations.extend(nested_violations)
        return validated_value, violations

    if isinstance(output, UnionProperty):
        for nested_property in output.any_of:
            nested_value, nested_violations = _validate_output(value, nested_property, field_name)
            if not nested_violations:
                return nested_value, []
        return value, [_type_violation(field_name, output, value)]

    if output.is_value_of_expected_type(value):
        return value, []
    return value, [_type_violation(field_name, output, value)]


def _type_violation(field_name: str, output: Property, value: Any) -> str:
    return f"{field_name}: expected {output.get_type_str()}, got {type(value).__name__}"
