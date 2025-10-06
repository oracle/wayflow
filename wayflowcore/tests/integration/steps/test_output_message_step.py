# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import pytest

from wayflowcore.flow import Flow
from wayflowcore.messagelist import MessageType
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.steps import InputMessageStep, OutputMessageStep
from wayflowcore.steps.outputmessagestep import EXCLUDED_VALUES

from ...testhelpers.flowscriptrunner import (
    FlowScript,
    FlowScriptInteraction,
    FlowScriptRunner,
    MessageCheck,
)
from ...testhelpers.testhelpers import retry_test
from ...testhelpers.teststeps import _AddCustomValuesToContextStep


def check_message(assistant: Flow, expected_message: str) -> None:
    script = FlowScript(
        "generation",
        [
            FlowScriptInteraction(
                user_input="anything",
                checks=[MessageCheck(lambda messages: messages[-1].content == expected_message)],
            ),
        ],
    )

    runner = FlowScriptRunner(assistants=[assistant], flow_scripts=[script])
    runner.execute(raise_exceptions=True)


def test_pure_text_output_message() -> None:
    message = "Hi, I'm a OLab agent!"
    output_message_step = OutputMessageStep(message)
    assert len(output_message_step.output_descriptors) == 1
    assistant = Flow.from_steps([OutputMessageStep(message)])
    check_message(assistant, message)


def test_output_message_without_output() -> None:
    message = "Hi, I'm a OLab agent!"
    output_message_step = OutputMessageStep(message, expose_message_as_output=False)
    assert len(output_message_step.output_descriptors) == 0
    assistant = Flow.from_steps([output_message_step])
    check_message(assistant, message)


def test_output_message_with_variables() -> None:
    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({"username": "Damien"}),
            OutputMessageStep("Welcome {{username}}, I'm a OLab agent"),
        ]
    )
    check_message(assistant, "Welcome Damien, I'm a OLab agent")


def check_asked_message(assistant: Flow, expected_question: str, expected_answer: str) -> None:
    script = FlowScript(
        "generation",
        [
            FlowScriptInteraction(user_input=""),
            FlowScriptInteraction(
                user_input=expected_answer,
                checks=[
                    MessageCheck(lambda messages: messages[-3].content == expected_question),
                    MessageCheck(lambda messages: messages[-2].content == expected_answer),
                ],
            ),
        ],
    )

    runner = FlowScriptRunner(assistants=[assistant], flow_scripts=[script])
    runner.execute(raise_exceptions=True)


def test_another_pure_text_output_message() -> None:
    question = "Hi, what do you want to do today?"
    assistant = Flow.from_steps(
        [
            InputMessageStep(question),
            OutputMessageStep("Let's do it"),
        ]
    )
    check_asked_message(assistant, question, "laundry")


default_intro_laundry = "Welcome Damien. What do you want to do today?"


def test_another_output_message_with_variables() -> None:
    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({"username": "Damien"}),
            InputMessageStep("Welcome {{username}}. What do you want to do today?"),
            OutputMessageStep("Let's do it"),
        ]
    )
    check_asked_message(assistant, default_intro_laundry, "laundry")


@retry_test(max_attempts=4)
def test_input_and_output_messages_with_rephrasing(remotely_hosted_llm: VllmModel) -> None:
    """
    Failure rate:          1 out of 30
    Observed on:           2024-10-30
    Average success time:  0.78 seconds per successful attempt
    Average failure time:  0.65 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.5 / 100'000
    """
    default_end_message = "OK, I'll start doing the laundry"

    name = "Damien"

    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({"username": name}),
            InputMessageStep(
                "Welcome {{username}}, nice to meet you. What do you want to do today?",
                rephrase=True,
                llm=remotely_hosted_llm,
            ),
            OutputMessageStep(default_end_message, rephrase=True, llm=remotely_hosted_llm),
        ]
    )

    def extract_message(messages, idx):
        return messages[idx].content.lower()

    script = FlowScript(
        "generation",
        [
            FlowScriptInteraction(user_input=""),
            FlowScriptInteraction(
                user_input="laundry",
                checks=[
                    MessageCheck(
                        # We just check that it is not the exact intro message we wanted to rephrase
                        lambda messages: extract_message(messages, 1)
                        != default_intro_laundry.lower()
                    ),
                    MessageCheck(
                        # We just check that it is not the exact end message we wanted to rephrase
                        lambda messages: extract_message(messages, 3)
                        != default_end_message.lower()
                    ),
                ],
            ),
        ],
    )

    runner = FlowScriptRunner(assistants=[assistant], flow_scripts=[script])
    runner.execute(raise_exceptions=True)


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
def test_output_can_use_lists(template: str, expected_match: str) -> None:
    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep(
                {"steps": ["step1", "step2"], "some_other_value": "ahah"}
            ),
            OutputMessageStep(message_template=template),
        ]
    )

    conv = assistant.start_conversation()
    assistant.execute(conv)
    assert conv.get_last_message().content == expected_match


def test_output_can_use_dicts() -> None:
    template = """{% for v, k in my_dict.items() %}{{v}}:{{k}},{% endfor %}"""
    assistant = Flow.from_steps(
        [
            OutputMessageStep(message_template=template),
        ]
    )

    conv = assistant.start_conversation(inputs={"my_dict": {"k1": "v1", "k2": "v2"}})
    assistant.execute(conv)
    assert conv.get_last_message().content == "k1:v1,k2:v2,"


def test_output_step_with_display_only_mode() -> None:
    assistant = Flow.from_steps(
        [
            OutputMessageStep(
                message_template="Test Message", message_type=MessageType.DISPLAY_ONLY
            ),
        ]
    )

    conv = assistant.start_conversation()
    assistant.execute(conv)
    assert conv.get_last_message().content == "Test Message"
    assert conv.get_last_message().message_type == MessageType.DISPLAY_ONLY
    assert len(conv.get_messages()) == 1


def test_output_can_use_arbitrary_complex_structures() -> None:
    template = """{% for k, v in my_dict.items() %}\
[{%for vv in v %}\
{%for kvv, vvv in vv.items() %}\
{{kvv}}:{{vvv}},\
{% endfor %}\
{% endfor %}]\
{% endfor %}"""
    assistant = Flow.from_steps([OutputMessageStep(message_template=template)])
    conv = assistant.start_conversation(
        inputs={"my_dict": {"N1": [{"k1": "v1"}, {"k2": "v2"}], "N2": [{"k3": "v3"}, {"k4": "v4"}]}}
    )
    assistant.execute(conv)
    assert conv.get_last_message().content == "[k1:v1,k2:v2,][k3:v3,k4:v4,]"


def test_output_doesnt_match_wrongly_formatted_lists() -> None:
    with pytest.raises(ValueError):
        assistant = Flow.from_steps(
            [
                _AddCustomValuesToContextStep({"steps": ["step1", "step2"]}),
                OutputMessageStep(message_template="""for step in steps {{step}}"""),
            ]
        )

        conv = assistant.start_conversation()
        assistant.execute(conv)


def test_assistant_output_step_might_not_yield() -> None:
    step = OutputMessageStep("Example output")
    assert not step.might_yield


@pytest.mark.parametrize("message_type", sorted(list(EXCLUDED_VALUES)))
def test_excluded_message_type(message_type: MessageType) -> None:
    with pytest.raises(ValueError):
        OutputMessageStep(message_template="", message_type=message_type)


@pytest.mark.parametrize(
    "message_type",
    [message_type for message_type in MessageType if message_type not in EXCLUDED_VALUES],
)
def test_included_message_type(message_type: MessageType) -> None:
    OutputMessageStep(message_template="", message_type=message_type)


def test_output_message_is_not_empty_by_default():
    step = OutputMessageStep()
    assert step.message_template != ""


def test_output_message_expects_input_named_message_by_default():
    step = OutputMessageStep()
    assert len(step.input_descriptors) == 1
    assert step.input_descriptors[0].name == "message"
