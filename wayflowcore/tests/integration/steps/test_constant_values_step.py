# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from datetime import datetime

import pytest

from wayflowcore.flowhelpers import run_step_and_return_outputs
from wayflowcore.property import IntegerProperty
from wayflowcore.steps import ConstantValuesStep


@pytest.mark.parametrize(
    "constant_values",
    [
        {"int_number": 3},
        {"int_number_1": 3, "int_number_2": 4},
        {"float_number": 3.13, "int_number": 4, "bool_value": True, "string_value": "string"},
    ],
)
def test_different_constant_values(constant_values):
    step = ConstantValuesStep(constant_values)
    output = run_step_and_return_outputs(step, inputs={})
    assert output == constant_values


@pytest.mark.parametrize(
    "constant_values",
    [
        {"list": [1, 2, 3]},
        {"datetime": datetime(year=2025, month=1, day=1)},
        {"dict": {"a": 1, "b": 1}},
    ],
)
def test_constant_values_negative(constant_values):
    with pytest.raises(ValueError):
        step = ConstantValuesStep(constant_values)


def test_override_output_descriptors():
    constant_values = {
        "value": True,
    }
    step = ConstantValuesStep(
        constant_values=constant_values, output_descriptors=[IntegerProperty(name="value")]
    )
    output = run_step_and_return_outputs(step, inputs={})
    assert isinstance(output["value"], int)
    assert output["value"] == 1
