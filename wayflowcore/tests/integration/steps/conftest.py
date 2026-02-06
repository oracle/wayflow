# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest

from wayflowcore.property import DictProperty, FloatProperty, ListProperty, StringProperty
from wayflowcore.variable import Variable


@pytest.fixture
def float_variable() -> Variable:
    return Variable(
        name="float_variable",
        type=FloatProperty(),
        description="a float variable",
        default_value=1.1,
    )


@pytest.fixture
def string_variable() -> Variable:
    return Variable(
        name="string variable",
        type=StringProperty(),
        description="my string variable",
    )


@pytest.fixture
def string_variable_with_default() -> Variable:
    return Variable(
        name="string variable",
        type=StringProperty(),
        description="my string variable",
        default_value="default",
    )


@pytest.fixture
def list_of_floats_variable() -> Variable:
    return Variable(
        name="list_of_floats_variable",
        type=ListProperty(item_type=FloatProperty()),
        description="list of floats variable",
        default_value=[4.0, 4.0, 3.0, 2.1423],
    )


@pytest.fixture
def dict_of_floats_variable() -> Variable:
    return Variable(
        name="dict_of_floats_variable",
        type=DictProperty(value_type=FloatProperty()),
        description="dict of floats variable",
        default_value={"my_str": 22.14},
    )


@pytest.fixture
def list_of_dicts_of_strings_variable() -> Variable:
    return Variable(
        name="list_of_dict_of_strings_variable",
        type=ListProperty(item_type=DictProperty(value_type=StringProperty())),
        description="list of dict of strings variable",
        default_value=[{"my_str": "my value"}],
    )
