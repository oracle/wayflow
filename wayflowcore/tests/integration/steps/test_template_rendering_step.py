# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest

from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.steps import TemplateRenderingStep
from wayflowcore.steps.outputmessagestep import OutputMessageStep

from ...testhelpers.flowscriptrunner import (
    FlowScript,
    FlowScriptInteraction,
    FlowScriptRunner,
    IODictCheck,
)
from ...testhelpers.teststeps import _AddCustomValuesToContextStep


def check_output(assistant, expected_message):
    script = FlowScript(
        "generation",
        [
            FlowScriptInteraction(
                user_input="anything",
                checks=[
                    IODictCheck(
                        lambda content: content == expected_message, TemplateRenderingStep.OUTPUT
                    )
                ],
            ),
        ],
    )

    runner = FlowScriptRunner(assistants=[assistant], flow_scripts=[script])
    runner.execute(raise_exceptions=True)


def test_pure_text_output_message():
    message = "Hi, I'm a OLab agent!"
    assistant = Flow.from_steps([TemplateRenderingStep(message)])
    check_output(assistant, message)


def test_output_message_with_variables():
    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({"username": "Damien"}),
            TemplateRenderingStep("Welcome {{username}}, I'm a OLab agent"),
        ]
    )
    check_output(assistant, "Welcome Damien, I'm a OLab agent")


@pytest.mark.parametrize(
    "template,expected_match",
    [
        ("""{% for step in steps -%}{{step}}{% endfor -%}""", """step1step2"""),
        ("""{%for step in steps%}{{step}}-{% endfor -%}""", """step1-step2-"""),
        ("""{%- for s in steps -%}{{s}}\n{% endfor -%}""", """step1\nstep2\n"""),
        (
            """{%- for s in steps%}{{s}}\n{% endfor -%}{{some_other_value}}""",
            """step1\nstep2\nahah""",
        ),
    ],
)
def test_output_can_use_lists(template, expected_match):
    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep(
                {"steps": ["step1", "step2"], "some_other_value": "ahah"}
            ),
            TemplateRenderingStep(template=template),
        ]
    )

    conv = assistant.start_conversation()
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values[TemplateRenderingStep.OUTPUT] == expected_match


def test_output_can_use_dicts():
    template = """{% for k in my_dict %}{{k}}:{{my_dict[k]}},{% endfor %}"""
    assistant = Flow.from_steps(
        [
            TemplateRenderingStep(template=template),
        ]
    )

    conv = assistant.start_conversation(inputs={"my_dict": {"k1": "v1", "k2": "v2"}})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values[TemplateRenderingStep.OUTPUT] == "k1:v1,k2:v2,"


def test_output_can_use_arbitrary_complex_structures():
    template = """{% for k in my_dict %}\
[{%for vv in my_dict[k] %}\
{%for kvv in vv %}\
{{kvv}}:{{vv[kvv]}},\
{% endfor %}\
{% endfor %}]\
{% endfor %}"""
    assistant = Flow.from_steps([TemplateRenderingStep(template=template)])
    conv = assistant.start_conversation(
        inputs={"my_dict": {"N1": [{"k1": "v1"}, {"k2": "v2"}], "N2": [{"k3": "v3"}, {"k4": "v4"}]}}
    )
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values[TemplateRenderingStep.OUTPUT] == "[k1:v1,k2:v2,][k3:v3,k4:v4,]"


def test_does_not_raises_when_jinja_detected_variable_is_str_but_list_is_passed():
    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({"steps": ["step1", "step2"]}),
            TemplateRenderingStep(template="{{steps}}"),
        ]
    )

    conv = assistant.start_conversation()
    conv.execute()


def test_raises_when_missing_input():
    with pytest.raises(ValueError):
        assistant = Flow.from_steps(
            [
                TemplateRenderingStep(template="{{step}}"),
            ]
        )

        conv = assistant.start_conversation()
        conv.execute()


@pytest.mark.parametrize(
    "template",
    [
        "{% if step is none %}{{step}}{% endif %}",
        "{% if step is not none %}{{step}}{% endif %}",
        "{% if   step  is    not   none  %}{{step}}{% endif %}",
        "{% if step %}{{step}}{% endif %}",
        "{% if   step    %}{{step}}{% endif %}",
        "{% if not step  %}{{step}}{% endif %}",
        "{% if not not step  %}{{step}}{% endif %}",
    ],
)
def test_correctly_detects_optional_value(template):
    assistant = Flow.from_steps(
        [
            TemplateRenderingStep(template=template),
        ]
    )
    conv = assistant.start_conversation()
    conv.execute()


def test_assistant_output_step_might_not_yield():
    step = TemplateRenderingStep("Example output")
    assert not step.might_yield


def test_can_wire_template_formatting_step_to_other_step():
    welcome_message = "welcome_message"
    assistant = Flow.from_steps(
        [
            TemplateRenderingStep(
                "My name is {{name}}",
                output_mapping={TemplateRenderingStep.OUTPUT: welcome_message},
            ),
            OutputMessageStep(
                message_template="{{my_template}}", input_mapping={"my_template": welcome_message}
            ),
        ]
    )

    conv = assistant.start_conversation({"name": "Son"})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values[OutputMessageStep.OUTPUT] == "My name is Son"


def test_no_conflict_when_variable_is_named_template():
    assistant = Flow.from_steps(
        [
            TemplateRenderingStep("{{template}}"),
        ]
    )

    conv = assistant.start_conversation({"template": "anything"})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values[TemplateRenderingStep.OUTPUT] == "anything"
