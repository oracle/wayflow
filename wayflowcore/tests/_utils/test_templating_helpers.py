# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import List

import pytest

from wayflowcore._utils._templating_helpers import get_variable_names_from_str_template


@pytest.mark.parametrize(
    "template, expected",
    [
        ("{{ foo }}", ["foo"]),
        ("{{ foo }} {{ foo }} ", ["foo"]),
        ("{{ foo }} {{ bar }}", ["foo", "bar"]),
        ("{{ bar }} {{ foo }}", ["bar", "foo"]),
        ("{{ a }} {{ b }} {{ c }} {{ d }}", ["a", "b", "c", "d"]),
        ("{{ a }} {{ b }} {{ c }} {{ a }}", ["a", "b", "c"]),
        (
            "{{ apple }} {{ orange }} {{ apple }} {{ pear }} {{ orange }} {{ banana }}",
            ["apple", "orange", "pear", "banana"],
        ),
        ("orange {{ apple }} {{ banana }} {{ orange }}", ["apple", "banana", "orange"]),
        ("Hello World!", []),
        ("", []),
    ],
)
def test_get_variable_names_from_str_template(template: str, expected: List[str]):
    assert expected == get_variable_names_from_str_template(template)


@pytest.mark.parametrize(
    "template, expected",
    [
        # Complex expressions maintaining order
        ("{{ data['key1'] }} {{ data.key2 }}", ["data"]),
        ("{{ list[0] }} and {{ list[1] }} and {{ list2[0] }}", ["list", "list2"]),
        # Variables in loops (order appears as in the loop body)
        ("{% for item in items %}{{ item }}{% endfor %}", ["items"]),
        ("{% for user in users %}{{ user.id }}: {{ user.name }}{% endfor %}", ["users"]),
        # Variables with filters (only variable name should be extracted)
        ("{{ name|capitalize }} {{ age|default('unknown', true) }}", ["name", "age"]),
        # Mixed static text, HTML, and variables
        ("Welcome, {{ user }}!", ["user"]),
        ("<div>{{ header }}</div><p>{{ content }}</p>", ["header", "content"]),
        # Whitespace variations
        ("{{     spaced    }}", ["spaced"]),
        ("{{tight}}", ["tight"]),
        # Control Structures: enforce correct context usage
        (
            "{% if condition %}{{ outcome1 }}{% elif x == 2 %}{{outcome2}}{% else %}{{ outcome3 }}{% endif %}",
            ["condition", "outcome1", "x", "outcome2", "outcome3"],
        ),
        (
            "{% for book in books %} Title: {{ book.title }} Author: {{ book.author }} {% endfor %}",
            ["books"],
        ),
        # Special cases and edge cases
        ("{{ user }} <{{ user2.id }}>", ["user", "user2"]),
        # Test with blocks and extends
        (
            "{% block header %}{{ title }} {% endblock %}{% block content %}{{ body }}{% endblock %}",
            ["title", "body"],
        ),
        # condition with expression
        ("{% if x == 2 %}{{bar}}{% endif %}", ["x", "bar"]),
        # nested list and condition
        (
            "{{hello}} {% for i in mylist %}{{i}}{{array}}{% endfor %}{% if x == 2 %}{% endif %}",
            ["hello", "mylist", "array", "x"],
        ),
        ("{% for v, k in my_dict.items() %}{{v}}:{{k}},{% endfor %}", ["my_dict"]),
    ],
)
def test_get_variable_names_from_str_template_complex(template: str, expected: List[str]):
    assert get_variable_names_from_str_template(template) == expected
