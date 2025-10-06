# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict, Set

import pytest

from wayflowcore._utils._templating_helpers import (
    get_variable_names_from_object,
    render_nested_object_template,
)


@pytest.fixture
def rendering_input() -> Dict[str, Any]:
    return {
        "username": "scott",
        "email": "great.scott@bttf.com",
        "name": "Great Scott",
        "street": "123 oak street",
        "city": "greendale",
    }


@pytest.mark.parametrize(
    "templated_value,expected_extracted_variables,expected_rendered_value",
    [
        ("{{ username }}", {"username"}, "scott"),
        (
            ["{{ username }}", "marty", "{{ name }}", "{{ username }}"],
            {"username", "name"},
            ["scott", "marty", "Great Scott", "scott"],
        ),
        (
            [["{{ username }}"], ["name", "{{ name }}"]],
            {"username", "name"},
            [["scott"], ["name", "Great Scott"]],
        ),
        ({"email": "{{ email }}"}, {"email"}, {"email": "great.scott@bttf.com"}),
        (
            {
                "person1": [{"name": "{{ name }}"}, {"{{ street }}": "main"}],
                "person2": {"city": ("{{ city }}",)},
            },
            {"name", "street", "city"},
            {
                "person1": [{"name": "Great Scott"}, {"123 oak street": "main"}],
                "person2": {"city": ("greendale",)},
            },
        ),
    ],
)
def test_variable_extraction_and_render(
    rendering_input: Dict[str, str],
    templated_value: Any,
    expected_extracted_variables: Set[str],
    expected_rendered_value: Any,
) -> None:
    assert set(get_variable_names_from_object(templated_value)) == set(expected_extracted_variables)
    assert (
        render_nested_object_template(templated_value, rendering_input) == expected_rendered_value
    )


def test_template_throw_on_duplicates_when_configured() -> None:
    with pytest.raises(ValueError):
        get_variable_names_from_object(["{{ a }}", "{{ a }}"], allow_duplicates=False)
