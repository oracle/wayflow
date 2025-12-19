# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, Set

import jinja2
import pytest

from wayflowcore._utils._templating_helpers import (
    check_template_validity,
    get_variable_names_from_object,
    render_nested_object_template,
    render_template_partially,
)
from wayflowcore.exceptions import SecurityException
from wayflowcore.messagelist import Message


@pytest.fixture
def rendering_input() -> Dict[str, Any]:
    return {
        "username": "scott",
        "email": "great.scott@bttf.com",
        "name": "Great Scott",
        "street": "123 oak street",
        "city": "greendale",
        "dictionary": {"a": 1, "b": "2"},
        "list": [1, 2, 3, 4],
    }


@pytest.mark.parametrize(
    "templated_value,expected_extracted_variables,expected_rendered_value",
    [
        ("{{ username }}", {"username"}, "scott"),
        ({"test": "{{ 7*7 }}"}, {}, {"test": "49"}),
        ({"greeting": "Hello {{ name }}"}, {"name"}, {"greeting": "Hello Great Scott"}),
        (
            {
                "allvals": "{% for k in dictionary %}{{k}}: {{dictionary[k]}}{{ ', ' if not loop.last }}{% endfor %}"
            },
            {"dictionary"},
            {"allvals": "a: 1, b: 2"},
        ),
        (
            {"allvals": "{% for e in list %}{{e}}{{ ', ' if not loop.last }}{% endfor %}"},
            {"list"},
            {"allvals": "1, 2, 3, 4"},
        ),
        ({"allvals": "{{list | length}}"}, {"list"}, {"allvals": "4"}),
        (
            {"iseven": "{% if list[1] % 2 == 0 %}even{% else %}odd{% endif %}"},
            {"list"},
            {"iseven": "even"},
        ),
        ({"allvals": "{{'%.2f' | format(0.123456789)}}"}, {}, {"allvals": "0.12"}),
        (
            {
                "customtest": "{% for e in [1,2] %}{{loop.last}},{{loop.first}},{{loop.index0}},{{loop.index}},{{loop.length}};{% endfor %}"
            },
            {},
            {"customtest": "False,True,0,1,2;True,False,1,2,2;"},
        ),
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


@pytest.mark.parametrize(
    "malicious_payload,inputs,description",
    [
        (
            "{{ f }}",
            {"f": lambda x: x},
            "Non-basic attributes in inputs (function)",
        ),
        (
            "{{ m.content }}",
            {"m": Message(content="Hello!")},
            "Non-basic attributes in inputs (class)",
        ),
        (
            "{{ m.a[0][1] }}",
            {"m": {"a": [(Message(content="Hello!"), "b")]}},
            "Non-basic attributes in inputs (class in nested object)",
        ),
        (
            "{{ f.__globals__ }}",
            {"f": lambda x: x},
            "Access to attributes of functions",
        ),
    ],
)
def test_ssti_attacks_in_template_renderer_inputs_are_blocked(
    malicious_payload: str, inputs: dict, description: str
) -> None:
    with pytest.raises(SecurityException, match=r"Rendering type"):
        render_nested_object_template({"exploit": malicious_payload}, inputs)


@pytest.mark.parametrize(
    "malicious_payload,inputs,description",
    [
        (
            "{{ lipsum.__globals__['os'].popen('id').read() }}",
            {},
            "Lipsum __globals__ access",
        ),
        (
            "{{ cycler.__init__.__globals__.os.popen('whoami').read() }}",
            {},
            "Cycler __init__ access",
        ),
        (
            "{{ joiner.__init__.__globals__.os.popen('uname -a').read() }}",
            {},
            "Joiner __init__ access",
        ),
        (
            "{{''.__class__.__mro__[1].__subclasses__()}}",
            {},
            "Class traversal via __class__.__mro__",
        ),
        (
            "{{ config.__class__.__init__.__globals__ }}",
            {},
            "Config __globals__ access",
        ),
        (
            "{{ self.__class__.__mro__ }}",
            {},
            "Self class traversal",
        ),
        (
            "{{ d.__init__ }}",
            {"d": {"a": 1, "b": 2}},
            "Access to attributes that are not dict keys",
        ),
        (
            "{{ len(d) }}",
            {"d": [1, 2, 3]},
            "Calling method on accepted type",
        ),
        (
            "{{ str(d) }}",
            {"d": [1, 2, 3]},
            "Calling method on accepted type",
        ),
        (
            "{{ d['__init__'] }}",
            {"d": {"a": 1, "b": 2}},
            "Access to attributes (with getitem) that are not dict keys",
        ),
        (
            "{{ d[('a', 'a')] }}",
            {"d": {("a", "a"): 1, ("b", "b"): 2}},
            "Access to attributes (with getitem) with complex type dict keys",
        ),
        (
            "{{ d['__init__'] }}",
            {"d": [1, 2, 3]},
            "Access to attributes (with getitem) that are not list indices",
        ),
        (
            "{{ d['d2']['__init__'] }}",
            {"d": {"d2": [1, 2, 3]}},
            "Access to nested attributes (with getitem) that are not list indices",
        ),
        (
            "{% for k, v in d.items() %}{{k}}:{{v}}, {% endfor %}",
            {"d": {"a": 1, "b": 2}},
            "Access to dict methods",
        ),
        (
            "{{ ''.__class__ }}",
            {},
            "Basic example",
        ),
        (
            "{{ {}.__class__ }}",
            {},
            "Basic example",
        ),
        (
            "{{ ().__class__ }}",
            {},
            "Basic example",
        ),
        (
            "{{ [].__class__ }}",
            {},
            "Basic example",
        ),
        (
            "{{ lipsum.__globals__ }}",
            {},
            "Basic example",
        ),
        (
            """
            {% for item in items %}
              {{ loop.index }}
              {{ loop.__class__ }}  {# Will this work? #}
            {% endfor %}
            """,
            {"items": [1, 2, 3]},
            "Loop context internals access",
        ),
    ],
)
def test_ssti_attacks_in_template_renderer_are_blocked_with_security(
    malicious_payload: str, inputs: dict, description: str
) -> None:
    with pytest.raises(SecurityException, match="is not safe and raised a security error"):
        print(render_nested_object_template({"exploit": malicious_payload}, inputs))
    with pytest.raises(SecurityException, match="is not safe and raised a security error"):
        print(render_template_partially(malicious_payload, inputs))


@pytest.mark.parametrize(
    "malicious_payload,inputs,description",
    [
        (
            "{{ cycler }}",
            {},
            "Basic example",
        ),
        (
            "{{ lipsum }}",
            {},
            "Basic example",
        ),
        (
            "{{ config }}",
            {},
            "Basic example",
        ),
    ],
)
def test_ssti_attacks_in_template_renderer_are_blocked_with_undefined(
    malicious_payload: str, inputs: dict, description: str
) -> None:
    with pytest.raises(
        jinja2.exceptions.UndefinedError,
        match="The template is expecting a variable but it was not passed:",
    ):
        print(render_nested_object_template({"exploit": malicious_payload}, inputs))


@pytest.mark.parametrize(
    "obj,inputs,expected_obj,failing_max_recursion_depth",
    [
        (
            [([[[{("{{v}}",)}]]],)],
            {"v": "value!"},
            [([[[{("value!",)}]]],)],
            3,
        ),
        (
            {"{{v}}": {"{{v}}": {"{{v}}": {"{{v}}": {"{{v}}": {"{{v}}": "{{v}}"}}}}}},
            {"v": "a"},
            {"a": {"a": {"a": {"a": {"a": {"a": "a"}}}}}},
            2,
        ),
        (
            [{"a": ("a", [{"a": ("a", [[{"a": "{{v}}"}]])}])}],
            {"v": "value!"},
            [{"a": ("a", [{"a": ("a", [[{"a": "value!"}]])}])}],
            5,
        ),
    ],
)
def test_max_recursion_depth_in_nested_template_rendering_is_triggered_correctly(
    obj: Any, inputs: Any, expected_obj: Any, failing_max_recursion_depth: int
) -> None:

    with pytest.raises(
        ValueError, match="Max recursion depth exceeded in method render_nested_object_template."
    ):
        _ = render_nested_object_template(
            obj, inputs, max_recursion_depth=failing_max_recursion_depth
        )

    rendered_template_obj = render_nested_object_template(obj, inputs)

    assert rendered_template_obj == expected_obj


@pytest.mark.parametrize(
    "template", ["{{ hello }}", "{% for elem in elements %}{{ element }}{% endfor %}"]
)
def test_check_template_validity_works_on_correct_templates(template):
    check_template_validity(template)


@pytest.mark.parametrize("template", ["{{ hello }", "{% for elem in elements %}{{ element }}{% en"])
def test_check_template_validity_raises_on_incorrect_templates(template):
    with pytest.raises(jinja2.exceptions.TemplateSyntaxError):
        check_template_validity(template)
