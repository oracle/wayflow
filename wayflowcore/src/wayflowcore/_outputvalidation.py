# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Validation for structured LLM outputs."""

from typing import Any

from wayflowcore.exceptions import StructuredOutputValidationError
from wayflowcore.property import Property


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
        else:
            value, value_violations = output._validate_strict_value(outputs[output_name])
            validated_outputs[output_name] = value
            violations.extend(
                f"{output_name}{location}: {message}" for location, message in value_violations
            )

    if violations:
        raise StructuredOutputValidationError(violations=violations)
    return validated_outputs
