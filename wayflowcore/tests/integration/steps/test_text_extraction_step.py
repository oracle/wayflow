# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import re
from typing import Union

import pytest
from _pytest.logging import LogCaptureFixture

from wayflowcore.conversation import Conversation
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.outputparser import RegexPattern
from wayflowcore.property import ListProperty, Property, StringProperty
from wayflowcore.steps import ExtractValueFromJsonStep, OutputMessageStep, RegexExtractionStep

from ...testhelpers.teststeps import _AddCustomValuesToContextStep

logger = logging.getLogger(__name__)

WEATHER_DOCUMENTS = [
    ("France", "in France it is currently raining"),
    ("Switzerland", "in Switzerland it is currently snowing"),
    ("Spain", "in Spain it is currently sunny"),
    ("Italy", "in Italy it is currently stormy"),
]


@pytest.fixture
def text_extraction_step():
    try:
        from langchain_community.embeddings.huggingface import HuggingFaceEmbeddings
        from langchain_community.vectorstores.faiss import FAISS
        from langchain_core.documents import Document
    except ImportError:
        pytest.skip("Langchain is not installed, skipping the test")

    docs = [Document(page_content=content) for _, content in WEATHER_DOCUMENTS]
    # text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    # split_documents = text_splitter.split_documents(docs)
    texts = [doc.page_content for doc in docs]

    embedding_model = HuggingFaceEmbeddings(model_kwargs={"device": "cpu"})
    vector_store = FAISS.from_texts(texts, embedding_model)
    return vector_store.as_retriever(search_kwargs={"k": 1})


JSON_ANSWER = """
{
    "response_type": "action_response",
    "thought": "I think I should do blah",
    "data": {
     "function_name": "blah",
     "irrelevant_stuff": "bluh"
    }
}
"""

EXPECTED_MESSAGE = """The LLM thought: I think I should do blah, and executed the function blah"""


@pytest.mark.parametrize(
    "llm_txt,expected_message",
    [
        (f"```{JSON_ANSWER}```", EXPECTED_MESSAGE),
        (f"```json{JSON_ANSWER}```", EXPECTED_MESSAGE),
        (f"```json{JSON_ANSWER}", EXPECTED_MESSAGE),
        (f"```{JSON_ANSWER}", EXPECTED_MESSAGE),
        (f"{JSON_ANSWER}```", EXPECTED_MESSAGE),
        (JSON_ANSWER, EXPECTED_MESSAGE),
    ],
)
def test_extract_value_from_json_step(llm_txt: str, expected_message: str) -> None:
    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({ExtractValueFromJsonStep.TEXT: llm_txt}),
            ExtractValueFromJsonStep(
                output_values={
                    "thought": ".thought",
                    "response_type": ".response_type",
                    "function_name": ".data.function_name",
                },
            ),
            OutputMessageStep(
                message_template="""The LLM thought: {{thought}}, and executed the function {{function_name}}"""
            ),
        ]
    )

    conversation: Conversation = assistant.start_conversation({})
    assistant.execute(conversation)

    assert conversation.get_last_message().content == expected_message


@pytest.mark.parametrize(
    "output_description",
    [
        "thought",
        StringProperty(name="thought"),
    ],
)
def test_extract_json_raises_on_not_found_required_value(output_description):
    with pytest.raises(ValueError):
        run_json_extraction_with_assistant(output_description, ".wrong_thought")


def test_extract_json_raises_on_not_found_required_value() -> None:
    with pytest.raises(ValueError):
        run_json_extraction_with_assistant("thought", ".wrong_thought")


def test_extract_json_does_not_raises_when_value_is_optional() -> None:
    run_json_extraction_with_assistant(
        StringProperty(name="thought", default_value=""),
        ".wrong_thought",
    )


def test_extract_value_from_json_step_produces_expected_outputs() -> None:
    run_json_extraction_with_assistant("thought", ".thought")


def run_json_extraction_with_assistant(
    output_description: Union[Property, str], jq_query: str
) -> None:
    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({ExtractValueFromJsonStep.TEXT: JSON_ANSWER}),
            ExtractValueFromJsonStep(
                output_values={
                    output_description: jq_query,
                },
            ),
        ]
    )
    conversation: Conversation = assistant.start_conversation({})
    assistant.execute(conversation)


def test_optional_output_in_extract_value_from_json_step() -> None:
    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({ExtractValueFromJsonStep.TEXT: JSON_ANSWER}),
            ExtractValueFromJsonStep(
                output_values={
                    "thought": ".thought",
                    StringProperty(name="duration", default_value=""): ".duration",  # doesn't exist
                },
            ),
        ]
    )

    conversation: Conversation = assistant.start_conversation({})
    assistant.execute(conversation)


@pytest.mark.parametrize(
    "llm_txt,pattern,expected_message",
    [
        ("The cat sat on the mat", r"c\w+", "cat"),
        ("My email is john@example.com", r"\b\w+@\w+\.\w+", "john@example.com"),
        ("The price is $199.99", r"\$\d+\.\d{2}", "$199.99"),
        ("Some input", r"ahahah", ""),
    ],
)
def test_regex_text_extraction_step(llm_txt: str, pattern: str, expected_message: str) -> None:
    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({RegexExtractionStep.TEXT: llm_txt}),
            RegexExtractionStep(
                regex_pattern=pattern,
            ),
            OutputMessageStep(message_template="""{{output}}"""),
        ]
    )

    conversation: Conversation = assistant.start_conversation({})
    assistant.execute(conversation)

    assert conversation.get_last_message().content == expected_message


REAL_VALUE = """
{
    "value": "real_value"
}
"""

WRONG_VALUE = """
{
    "value": "wrong_value"
}
"""


@pytest.mark.parametrize(
    "llm_txt",
    [
        f"```json\n{REAL_VALUE}```\n```json{WRONG_VALUE}```",
        f"```json\n{REAL_VALUE}```\n```{WRONG_VALUE}```",
        f"```\n{REAL_VALUE}```\n```{WRONG_VALUE}```",
        f"```\n{REAL_VALUE}```\n```json{WRONG_VALUE}```",
        f"```\n{REAL_VALUE}```\n```{WRONG_VALUE}",
        f"```json\n{REAL_VALUE}```\n```{WRONG_VALUE}",
    ],
)
def test_extract_from_json_step_matches_first_json(llm_txt: str) -> None:
    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({ExtractValueFromJsonStep.TEXT: llm_txt}),
            ExtractValueFromJsonStep(
                output_values={
                    "v": ".value",
                },
            ),
            OutputMessageStep(message_template="""{{v}}"""),
        ]
    )

    conversation: Conversation = assistant.start_conversation({})
    assistant.execute(conversation)

    assert conversation.get_last_message().content == "real_value"


def test_regex_and_json_extraction() -> None:

    llm_text = """
Thought: blahblah
Action:
```json
{
  "plan": {
      "name": "cook_pasta"
  }
}
```
"""

    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({ExtractValueFromJsonStep.TEXT: llm_text}),
            RegexExtractionStep(
                regex_pattern=r"Thought: (.*)\nAction:",
                output_mapping={RegexExtractionStep.OUTPUT: "llm_thought"},
            ),
            RegexExtractionStep(
                regex_pattern=r"Thought:.*\nAction:([\s\S]*)",
                output_mapping={RegexExtractionStep.OUTPUT: "llm_action"},
            ),
            ExtractValueFromJsonStep(
                output_values={
                    "title": ".plan.name",
                },
                input_mapping={ExtractValueFromJsonStep.TEXT: "llm_action"},
            ),
            OutputMessageStep(
                message_template="""The LLM thought {{llm_thought}} and will execute the plan {{title}}"""
            ),
        ]
    )

    conversation: Conversation = assistant.start_conversation({})
    assistant.execute(conversation)

    assert (
        conversation.get_last_message().content
        == """The LLM thought blahblah and will execute the plan cook_pasta"""
    )


def test_list_extraction_from_json() -> None:

    llm_text = """
```json
{
  "plan": {
      "name": "cook_pasta",
      "steps": [
          "step1",
          "step2",
          "step3",
          "step4"
      ]
  }
}
```
"""
    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({ExtractValueFromJsonStep.TEXT: llm_text}),
            ExtractValueFromJsonStep(
                output_values={
                    ListProperty(name="steps", item_type=StringProperty("step")): ".plan.steps",
                },
            ),
            OutputMessageStep(message_template="""{% for step in steps -%}{{step}}{% endfor -%}"""),
        ]
    )

    conversation: Conversation = assistant.start_conversation({})
    assistant.execute(conversation)

    assert conversation.get_last_message().content == """step1step2step3step4"""


def run_regex_extraction(
    return_first_match_only: bool, message_template: str, expected_output: str, text_input: str
) -> None:

    assistant = Flow.from_steps(
        [
            _AddCustomValuesToContextStep({ExtractValueFromJsonStep.TEXT: text_input}),
            RegexExtractionStep(
                regex_pattern=r"Thought: .*\nAction: (.*)\n",
                return_first_match_only=return_first_match_only,
                output_mapping={RegexExtractionStep.OUTPUT: "steps"},
            ),
            OutputMessageStep(message_template=message_template),
        ]
    )

    conversation: Conversation = assistant.start_conversation({})
    assistant.execute(conversation)
    assert conversation.get_last_message().content == expected_output


def test_list_extraction_from_json_returns_single_str(caplog: LogCaptureFixture) -> None:
    logger.propagate = True  # necessary so that the caplog handler can capture logging messages
    caplog.set_level(
        logging.WARNING
    )  # setting pytest to capture log messages of level WARNING or above
    llm_text = """Thought: blahblah1\nAction: action1\nThought: blahblah2\nAction: action2\n"""
    run_regex_extraction(
        return_first_match_only=True,
        message_template="{{steps}}",
        expected_output="action1",
        text_input=llm_text,
    )
    assert "The RegexExtractionStep found more than one match" in caplog.text


@pytest.mark.parametrize(
    "text_input,expected_output",
    [
        (
            """Thought: blahblah1\nAction: action1\nThought: blahblah2\nAction: action2\n""",
            """action1action2""",
        ),
        ("""""", ""),
    ],
)
def test_list_extraction_from_json_returns_list(text_input, expected_output) -> None:
    run_regex_extraction(
        return_first_match_only=False,
        message_template="""{% for step in steps -%}{{step}}{% endfor -%}""",
        expected_output=expected_output,
        text_input=text_input,
    )


def test_text_extraction_step_might_not_yield() -> None:
    step = RegexExtractionStep(regex_pattern="abc%*")
    assert not step.might_yield


@pytest.mark.parametrize(
    "pattern,text_input,expected_output",
    [
        (
            RegexPattern(pattern=".*", flags=re.DOTALL),
            "hello\nhow\nare\nyou",
            "hello\nhow\nare\nyou",
        ),
        (
            RegexPattern(pattern=".*"),
            "hello\nhow\nare\nyou",
            "hello",
        ),
        (
            RegexPattern(pattern=".*", match="last"),
            "hello\nhow\nare\nyou",
            "you",
        ),
    ],
)
def test_regex_extraction_step_with_pattern(pattern, text_input, expected_output):

    step = RegexExtractionStep(regex_pattern=pattern)
    flow = Flow.from_steps(steps=[step])
    conv = flow.start_conversation(inputs={RegexExtractionStep.TEXT: text_input})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values[RegexExtractionStep.OUTPUT] == expected_output
