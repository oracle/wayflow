# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import os
from textwrap import dedent
from typing import List

import pytest

from wayflowcore import Message, MessageType
from wayflowcore.executors._agentexecutor import _DISABLE_STREAMING
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import (
    _run_single_step_and_return_conv_and_status,
    _run_single_step_to_finish,
    run_step_and_return_outputs,
)
from wayflowcore.models import LlmCompletion
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.llmmodel import Prompt
from wayflowcore.property import IntegerProperty, ObjectProperty, StringProperty
from wayflowcore.serialization import autodeserialize, serialize
from wayflowcore.steps import (
    GetChatHistoryStep,
    InputMessageStep,
    OutputMessageStep,
    PromptExecutionStep,
)
from wayflowcore.steps.promptexecutionstep import StructuredGenerationMode
from wayflowcore.templates import PromptTemplate
from wayflowcore.templates.structuredgeneration import (
    adapt_prompt_template_for_json_structured_generation,
)

from ...testhelpers.dummy import DummyModel
from ...testhelpers.flowscriptrunner import FlowScript, FlowScriptInteraction, FlowScriptRunner
from ...testhelpers.patching import patch_llm
from ...testhelpers.testhelpers import retry_test
from ...testhelpers.teststeps import _AddCustomValuesToContextStep


def run_conversation(assistant: Flow, user_inputs: List[str]) -> None:
    script = FlowScript(
        "generation",
        [
            FlowScriptInteraction(user_input=inp)
            for inp in user_inputs
            # the recent changes of userinputstep forces us to have this for the first if case of userinputstep
        ],
    )
    runner = FlowScriptRunner(assistants=[assistant], flow_scripts=[script])
    runner.execute(raise_exceptions=True)


def test_basic_generation() -> None:
    dummy_model = DummyModel()
    dummy_model.set_next_output(
        {"Here is the request of the user. Please execute it:\ncode review": "generated text"}
    )

    assistant = Flow.from_steps(
        [
            InputMessageStep("Give me a request"),
            PromptExecutionStep(
                """Here is the request of the user. Please execute it:
{{ user_provided_input }}""",
                llm=dummy_model,
            ),
            OutputMessageStep("{{output}}"),
        ]
    )
    run_conversation(
        assistant, ["", "code review"]
    )  # initial empty interaction is needed for the input step


def test_several_input_generation() -> None:
    dummy_model = DummyModel()
    dummy_model.set_next_output({"valueA - valueB - valueC": "generated text"})

    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({"A": "valueA", "B_B": "valueB", "C": "valueC"}),
            PromptExecutionStep(
                """{{ A }} - {{ B_B }} - {{ C }}""",
                llm=dummy_model,
            ),
            OutputMessageStep("{{output}}"),
        ]
    )
    run_conversation(assistant, ["code review"])


def test_one_additional_input_generation() -> None:
    dummy_model = DummyModel()
    dummy_model.set_next_output({"valueA - valueB - valueC": "generated text"})

    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep(
                {"A": "valueA", "B_B": "valueB", "C": "valueC", "D": "valueD"}
            ),
            PromptExecutionStep(
                """{{ A }} - {{ B_B }} - {{ C }}""",
                llm=dummy_model,
            ),
            OutputMessageStep("{{output}}"),
        ]
    )
    run_conversation(assistant, ["code review"])


def test_prompt_execution_raises_when_missing_input() -> None:
    with pytest.raises(ValueError, match='Cannot start conversation because of missing inputs "D"'):
        assistant = Flow.from_steps(
            [
                _AddCustomValuesToContextStep({"A": "valueA", "B_B": "valueB", "C": "valueC"}),
                PromptExecutionStep(
                    """{{ A }} - {{ B_B }} - {{ C }} - {{ D }}""",
                    llm=DummyModel(),
                ),
                OutputMessageStep("{{output}}"),
            ]
        )
        run_conversation(assistant, ["code review"])


def test_prompt_execution_step_might_not_yield() -> None:
    step = PromptExecutionStep(
        llm=DummyModel(),
        prompt_template="prompt {{var1}}",
    )
    assert not step.might_yield


@pytest.mark.parametrize(
    "prompt,outputs,expected_inputs,expected_outputs",
    [
        ("prompt {{var1}}", None, {"var1"}, {"output"}),
        ("prompt {{var2}} {%for i in items %}{% endfor %}", None, {"var2", "items"}, {"output"}),
        (
            "",
            [StringProperty(name="o1")],
            set(),
            {"o1"},
        ),
        (
            "{{var3}}",
            [
                StringProperty(name="o2"),
                StringProperty(name="o3"),
            ],
            {"var3"},
            {"o2", "o3"},
        ),
    ],
)
def test_step_has_correct_input_and_output_descriptors(
    prompt, outputs, expected_inputs, expected_outputs
) -> None:
    # Check that the configuration description looks like what we need
    configuration = {
        "input_mapping": None,
        "output_mapping": None,
        "input_descriptors": None,
        "output_descriptors": outputs,
        "prompt_template": prompt,
        "generation_config": LlmGenerationConfig(max_tokens=10),
        "llm": DummyModel(),
        "send_message": False,
    }

    step = PromptExecutionStep(**configuration)

    # check that input descriptors can be created
    input_descriptors = step.input_descriptors
    assert {i.name for i in input_descriptors} == expected_inputs

    # check that output descriptors can be created
    output_descriptors = step.output_descriptors
    assert {o.name for o in output_descriptors} == expected_outputs

    # check that next steps can be retrieved
    next_step_names = step.get_branches()
    assert set(next_step_names) == {PromptExecutionStep.BRANCH_NEXT}


def test_empty_template(remotely_hosted_llm):
    step = PromptExecutionStep(prompt_template="", llm=remotely_hosted_llm)
    outputs = _run_single_step_to_finish(step)
    assert "output" in outputs and len(outputs["output"]) > 0


def test_does_not_use_structured_generation_when_list_is_empty(remotely_hosted_llm):
    step = PromptExecutionStep(
        prompt_template="What is the last name of Safra A. Catz? Just answer with the last name",
        llm=remotely_hosted_llm,
        output_descriptors=[],
    )
    outputs = _run_single_step_to_finish(step)
    assert len(outputs) == 0


def test_structured_generation(remotely_hosted_llm):
    name_output = StringProperty(
        name="last_name",
        description="last name of the person",
    )
    step = PromptExecutionStep(
        prompt_template="What is the last name of Safra A. Catz?",
        llm=remotely_hosted_llm,
        output_descriptors=[name_output],
    )
    outputs = _run_single_step_to_finish(step)
    assert "last_name" in outputs


@retry_test(max_attempts=4)
def test_structured_generation_with_non_str_outputs(remotely_hosted_llm):
    """
    Failure rate:          9 out of 100
    Observed on:           2025-02-21
    Average success time:  1.16 seconds per successful attempt
    Average failure time:  0.86 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.10 ** 4) ~= 9.2 / 100'000
    """
    name_output = IntegerProperty(
        name="age",
        description="age of the person",
    )
    step = PromptExecutionStep(
        prompt_template="Answer with the age of Anna. Here are the information we have on her: 'Name: Anna, Age: 28'",
        llm=remotely_hosted_llm,
        output_descriptors=[name_output],
    )
    outputs = _run_single_step_to_finish(step)
    assert "age" in outputs
    assert outputs["age"] == 28


@pytest.mark.parametrize(
    "structured_generation_mode",
    [
        StructuredGenerationMode.JSON_GENERATION,
        StructuredGenerationMode.TOOL_GENERATION,
        StructuredGenerationMode.CONSTRAINED_GENERATION,
    ],
)
@retry_test(max_attempts=3)
def test_structured_generation_with_multiple_outputs(
    remotely_hosted_llm, structured_generation_mode
):
    """
    [StructuredGenerationMode.JSON_GENERATION]
    Failure rate:          0 out of 50
    Observed on:           2025-05-06
    Average success time:  0.63 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000

    [StructuredGenerationMode.TOOL_GENERATION]
    Failure rate:          0 out of 50
    Observed on:           2025-05-06
    Average success time:  0.32 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000

    [StructuredGenerationMode.CONSTRAINED_GENERATION]
    Failure rate:          0 out of 50
    Observed on:           2025-05-06
    Average success time:  0.33 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    last_name_output = StringProperty(
        name="last_name",
        description="last name of the person",
    )
    first_name_output = StringProperty(
        name="first_name",
        description="first name of the person",
    )
    step = PromptExecutionStep(
        prompt_template="What are the first and last names of Safra Catz?",
        llm=remotely_hosted_llm,
        output_descriptors=[last_name_output, first_name_output],
        _structured_generation_mode=structured_generation_mode,
    )
    outputs = _run_single_step_to_finish(step)
    assert "last_name" in outputs
    assert outputs["last_name"]
    assert "first_name" in outputs
    assert outputs["first_name"]


@retry_test(max_attempts=11)
def test_structured_generation_with_reasoning(remotely_hosted_llm):
    """
    Failure rate:          8 out of 20
    Observed on:           2025-01-28
    Average success time:  4.30 seconds per successful attempt
    Average failure time:  4.65 seconds per failed attempt
    Max attempt:           11
    Justification:         (0.27 ** 8) ~= 3.1 / 100'000
    """
    name_output = IntegerProperty(
        name="result",
        description="result of the calculus",
    )
    step = PromptExecutionStep(
        prompt_template="What is the result of 32*32*7+81? Please think step by step, first reason and then generate the expected output",
        llm=remotely_hosted_llm,
        output_descriptors=[name_output],
        _structured_generation_mode=StructuredGenerationMode.JSON_GENERATION,
    )
    outputs = _run_single_step_to_finish(step)
    assert "result" in outputs
    assert outputs["result"] == 7249


COMPLEX_OBJECT_DESCRIPTOR = ObjectProperty(
    name="conversation_info",
    description="info about the conversation",
    properties={
        "name_1": ObjectProperty(
            description="name of the first person",
            properties={"name": StringProperty()},
        ),
        "name_2": ObjectProperty(
            description="name of the second person",
            properties={"name": StringProperty()},
        ),
    },
)


@retry_test(max_attempts=4)
def test_structured_generation_with_complex_structure(remotely_hosted_llm):
    """
    Failure rate:          1 out of 20
    Observed on:           2025-02-12
    Average success time:  1.14 seconds per successful attempt
    Average failure time:  0.99 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 6.8 / 100'000
    """

    step = PromptExecutionStep(
        prompt_template="A discussion takes place between 2 people, Anna and Bob. What people are talking? Just output the expected json",
        llm=remotely_hosted_llm,
        output_descriptors=[COMPLEX_OBJECT_DESCRIPTOR],
        _structured_generation_mode=StructuredGenerationMode.JSON_GENERATION,
    )
    outputs = _run_single_step_to_finish(step)
    assert "conversation_info" in outputs
    assert outputs["conversation_info"]["name_1"]["name"].lower() == "anna"
    assert outputs["conversation_info"]["name_2"]["name"].lower() == "bob"


def test_structured_generation_returns_wrong_type(remotely_hosted_llm):
    last_name_output = IntegerProperty(name="last_name")
    first_name_output = StringProperty(name="first_name")
    step = PromptExecutionStep(
        prompt_template="What is the last name of Safra A. Catz?",
        llm=remotely_hosted_llm,
        output_descriptors=[last_name_output, first_name_output],
    )
    llm_answer = """{"first_name": "safra", "last_name": "catz"}"""
    with patch_llm(remotely_hosted_llm, outputs=[llm_answer]):
        outputs = _run_single_step_to_finish(step)
    assert "last_name" in outputs
    assert "first_name" in outputs
    assert outputs["last_name"] == 0
    assert outputs["first_name"] == "safra"


def test_check_token_consumption(remotely_hosted_llm):
    step = PromptExecutionStep(
        prompt_template="Count to 50",
        llm=remotely_hosted_llm,
        generation_config=LlmGenerationConfig(max_tokens=10),
    )
    conv, status = _run_single_step_and_return_conv_and_status(step)
    assert isinstance(status, FinishedStatus)
    assert PromptExecutionStep.OUTPUT in status.output_values
    assert isinstance(status.output_values[PromptExecutionStep.OUTPUT], str)
    token_consumption = remotely_hosted_llm.get_total_token_consumption(conv.conversation_id)
    assert token_consumption.input_tokens == 39
    assert token_consumption.output_tokens == 10


def run_simple_generation(llm):
    step = PromptExecutionStep(llm=llm, prompt_template="""what is the capital of Switzerland?""")
    outputs = run_step_and_return_outputs(step)
    assert step.OUTPUT in outputs and isinstance(outputs[step.OUTPUT], str)


def test_prompt_execution_step_ocigenai(llama_oci_llm):
    run_simple_generation(llama_oci_llm)


def test_prompt_execution_step_llama(remotely_hosted_llm):
    run_simple_generation(remotely_hosted_llm)


def test_prompt_execution_step_cohere(cohere_llm):
    run_simple_generation(cohere_llm)


def test_prompt_execution_step_openai(gpt_llm):
    run_simple_generation(gpt_llm)


def _test_can_publish_message_to_conversation(llm):
    step = PromptExecutionStep(
        llm=llm,
        prompt_template="Is the following sentence positive? 'Wow this Agentic library is so good!'. Simply output '1' (if positive) or '0' (if negative).",
        generation_config=LlmGenerationConfig(max_tokens=20),
        send_message=True,  #  TO PUBLISH CONTENT TO MESSAGE LIST
    )
    conv, status = _run_single_step_and_return_conv_and_status(step)
    assert isinstance(status, FinishedStatus)
    last_message = conv.get_last_message()
    assert last_message is not None
    assert last_message.message_type == MessageType.AGENT


def test_can_publish_message_to_conversation_no_streaming(remotely_hosted_llm, cleanup_env):
    try:
        os.environ[_DISABLE_STREAMING] = "true"
        _test_can_publish_message_to_conversation(remotely_hosted_llm)
    finally:
        os.environ.pop(_DISABLE_STREAMING)


def test_can_publish_message_to_conversation_with_streaming(remotely_hosted_llm, cleanup_env):
    _test_can_publish_message_to_conversation(remotely_hosted_llm)


def test_cannot_publish_message_with_constrained_generation(remotely_hosted_llm):
    with pytest.raises(ValueError, match="Cannot generate some output"):
        PromptExecutionStep(
            llm=remotely_hosted_llm,
            prompt_template="Some template",
            send_message=True,
            output_descriptors=[
                ObjectProperty(name="my_obj", properties={"param1": StringProperty()})
            ],
        )


def test_can_use_specific_template_in_prompt_execution_step(remotely_hosted_llm):
    step = PromptExecutionStep(
        llm=remotely_hosted_llm,
        prompt_template=PromptTemplate(
            messages=[{"role": "user", "content": "what is the capital of Switzerland?"}]
        ),
        generation_config=LlmGenerationConfig(max_tokens=20),
    )
    outputs = run_step_and_return_outputs(step)
    assert PromptExecutionStep.OUTPUT in outputs
    assert isinstance(outputs[PromptExecutionStep.OUTPUT], str)
    assert len(outputs[PromptExecutionStep.OUTPUT]) > 0


@retry_test(max_attempts=3)
def test_can_use_specific_template_in_prompt_execution_step_with_chat_history(remotely_hosted_llm):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-05-21
    Average success time:  0.38 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    step = PromptExecutionStep(
        llm=remotely_hosted_llm,
        prompt_template=PromptTemplate(
            messages=[
                PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
                {
                    "role": "system",
                    "content": "what 2 cities are mentioned in the previous discussion with the user? Only answer with the 2 cities names",
                },
            ]
        ),
        generation_config=LlmGenerationConfig(max_tokens=20),
    )
    flow = Flow.from_steps(
        [
            InputMessageStep("What is your question?"),
            InputMessageStep("It is Bern"),
            GetChatHistoryStep(
                output_template=None,
                output_mapping={
                    GetChatHistoryStep.CHAT_HISTORY: PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME
                },
            ),
            step,
        ]
    )
    conv = flow.start_conversation()
    flow.execute(conv)
    conv.append_user_message("What is the capital of Switzerland?")
    flow.execute(conv)
    conv.append_user_message("Really? I thought it is Zurich")
    status = flow.execute(conv)
    assert isinstance(status, FinishedStatus)
    outputs = status.output_values
    assert PromptExecutionStep.OUTPUT in outputs
    assert isinstance(outputs[PromptExecutionStep.OUTPUT], str)
    text = outputs[PromptExecutionStep.OUTPUT].lower()
    assert "zurich" in text and "bern" in text


def test_prompt_template_response_format_and_no_output_descriptors(remotely_hosted_llm):
    with patch_llm(remotely_hosted_llm, outputs=["hi"]):
        step = PromptExecutionStep(
            llm=remotely_hosted_llm,
            prompt_template=PromptTemplate.from_string(
                template="hello", response_format=StringProperty("name")
            ),
            output_descriptors=None,
        )
        outputs = run_step_and_return_outputs(step)
        assert outputs["name"] == "hi"


def test_prompt_template_response_format_oci_json_generation(llama_oci_llm):
    prompt_template = adapt_prompt_template_for_json_structured_generation(
        PromptTemplate.from_string(
            template="Please state your name",
            response_format=ObjectProperty(
                "response",
                description="Your response to the task",
                properties={"name": StringProperty(description="Your name")},
            ),
        )
    )
    step = PromptExecutionStep(
        llm=llama_oci_llm,
        prompt_template=prompt_template,
        _structured_generation_mode=StructuredGenerationMode.JSON_GENERATION,
    )
    outputs = run_step_and_return_outputs(step)
    assert outputs["response"]["name"]  # Non-empty


@pytest.mark.parametrize(
    "structured_generation_mode",
    [
        StructuredGenerationMode.CONSTRAINED_GENERATION,
        StructuredGenerationMode.JSON_GENERATION,
        StructuredGenerationMode.TOOL_GENERATION,
    ],
)
def test_prompt_template_response_format_oci_constrained_generation_works(
    structured_generation_mode, llama_oci_llm
):
    prompt_template = PromptTemplate.from_string(
        template="Please state your name",
        response_format=ObjectProperty(
            "response",
            description="Your response to the question",
            properties={"name": StringProperty()},
        ),
    )
    step = PromptExecutionStep(
        llm=llama_oci_llm,
        prompt_template=prompt_template,
        _structured_generation_mode=structured_generation_mode,
    )
    outputs = run_step_and_return_outputs(step)
    assert "response" in outputs
    assert "name" in outputs["response"]


def test_prompt_template_response_format_matches_step_output_descriptors(remotely_hosted_llm):
    output_format = StringProperty("name")
    with patch_llm(remotely_hosted_llm, outputs=["hi"]):
        step = PromptExecutionStep(
            llm=remotely_hosted_llm,
            prompt_template=PromptTemplate.from_string(
                template="hello", response_format=output_format
            ),
            output_descriptors=[output_format],
        )
        outputs = run_step_and_return_outputs(step)
        assert outputs["name"] == "hi"


def test_prompt_template_response_raises_when_does_not_format_matches_prompt_execution_step_outputs(
    remotely_hosted_llm,
):
    with pytest.raises(
        ValueError, match="The output descriptors of the step and the prompt template do not match"
    ):
        with patch_llm(remotely_hosted_llm, outputs=["hi"]):
            step = PromptExecutionStep(
                llm=remotely_hosted_llm,
                prompt_template=PromptTemplate.from_string(
                    template="hello", response_format=StringProperty("name")
                ),
                output_descriptors=[IntegerProperty("name")],
            )
            outputs = run_step_and_return_outputs(step)
            assert outputs["name"] == "hi"


def test_prompt_template_response_works_when_format_matches_prompt_execution_step_outputs(
    remotely_hosted_llm,
):
    output_format = ObjectProperty("object", properties={"name": StringProperty()})
    with patch_llm(remotely_hosted_llm, outputs=['{"name":"hi"}']):
        step = PromptExecutionStep(
            llm=remotely_hosted_llm,
            prompt_template=PromptTemplate.from_string(
                template="hello", response_format=output_format
            ),
            output_descriptors=[output_format],
        )
        outputs = run_step_and_return_outputs(step)
        assert outputs["object"]["name"] == "hi"


def test_prompt_template_with_template_and_output_descriptors_correctly_sets_response_format_on_template(
    remotely_hosted_llm,
):
    with patch_llm(remotely_hosted_llm, outputs=['{"name":"hi"}']):
        step = PromptExecutionStep(
            llm=remotely_hosted_llm,
            prompt_template=PromptTemplate.from_string(
                template="hello",
            ),
            output_descriptors=[StringProperty(name="name")],
        )
        outputs = run_step_and_return_outputs(step)
        assert outputs["name"] == "hi"


def test_step_with_custom_template_can_be_properly_serialized(remotely_hosted_llm):
    output_format = ObjectProperty("object", properties={"name": StringProperty()})
    step = PromptExecutionStep(
        llm=remotely_hosted_llm,
        prompt_template=PromptTemplate.from_string(template="hello", response_format=output_format),
        output_descriptors=[output_format],
    )
    serialized_step = serialize(step)
    deserialized_step = autodeserialize(serialized_step)
    assert isinstance(deserialized_step, PromptExecutionStep)
    assert deserialized_step.prompt_template == step.prompt_template


def test_prompt_execution_step_replaces_chat_history_placeholder(monkeypatch, remotely_hosted_llm):
    """
    Verifies that PromptExecutionStep injects CHAT_HISTORY_PLACEHOLDER with the FlowConversation's history.
    """

    def generate_with_check(prompt, _conversation):
        assert isinstance(prompt, Prompt)
        assert len(prompt.messages) == 4
        assert prompt.messages[0].content == "A"
        assert prompt.messages[1].content == "B"
        assert prompt.messages[2].content == "C"
        assert prompt.messages[3].content == "Summarize the conversation."
        return LlmCompletion(
            message=Message(
                content="ABC",
                message_type=(MessageType.AGENT),
            ),
            token_usage=None,
        )

    with monkeypatch.context() as m:
        m.setattr(remotely_hosted_llm, "generate", generate_with_check)

        prompt_template = PromptTemplate(
            messages=[
                PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
                {"role": "system", "content": "Summarize the conversation."},
            ]
        )
        chat_messages = [
            Message(content="A", message_type=MessageType.USER),
            Message(content="Hidden content", message_type=MessageType.THOUGHT),
            Message(content="B", message_type=MessageType.AGENT),
            Message(content="C", message_type=MessageType.USER),
            Message(content="Hidden content", message_type=MessageType.INTERNAL),
        ]

        step = PromptExecutionStep(prompt_template=prompt_template, llm=remotely_hosted_llm)
        assert PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME not in set(
            [input_desc.name for input_desc in step.input_descriptors]
        )
        flow = Flow.from_steps([step])
        conversation = flow.start_conversation()
        for message in chat_messages:
            conversation.append_message(message)

        status = flow.execute(conversation)
        assert isinstance(status, FinishedStatus)


def test_prompt_execution_step_can_generate_enum_value_when_llm_fails(remotely_hosted_llm):
    text = "Sea turtles are animals living most of their lives in the ocean. They are in danger, and are lonely animals"
    habitat_enum = ("WATER", "FOREST", "DESERT", "MOUNTAINS")
    state_enum = ("NA", "IN_DANGER", "EXTINCTION")
    life_enum = ("ALONE", "FAMILY", "HERD")
    step = PromptExecutionStep(
        llm=remotely_hosted_llm,
        prompt_template="Here is some text, extract some information about it: {{text}}",
        output_descriptors=[
            ObjectProperty(
                name="animal",
                properties={
                    "name": StringProperty(description="name of the animal in lower letters"),
                    "habitat": StringProperty(enum=habitat_enum),
                    "state": StringProperty(enum=state_enum),
                    "life": StringProperty(enum=life_enum),
                },
            )
        ],
    )
    with patch_llm(remotely_hosted_llm, outputs=['{"habitat": "OCEAN", "state": "IN_DANGER"}']):
        # some values are not numeration accepted values, they are replaced by defaults of the enumeration type
        outputs = run_step_and_return_outputs(step, inputs={"text": text})
        assert outputs["animal"] == {
            "name": "",
            "habitat": "WATER",
            "state": "IN_DANGER",
            "life": "ALONE",
        }


def test_structured_generation_with_enum_str_fail(remotely_hosted_llm):
    text = dedent(
        """
        Here is some text, extract some information about it:
        Sea turtles are animals living most of their lives in the ocean, in the deep waters. They are in danger, and are lonely animals.
        """
    )
    habitat_enum = ("WATER", "FOREST", "DESERT", "MOUNTAINS")
    step = PromptExecutionStep(
        llm=remotely_hosted_llm,
        prompt_template="Here is some text, extract some information about it: {{text}}",
        output_descriptors=[StringProperty(name="habitat", enum=habitat_enum)],
    )
    outputs = run_step_and_return_outputs(step, inputs={"text": text})
    content = outputs["habitat"]
    assert content in habitat_enum
