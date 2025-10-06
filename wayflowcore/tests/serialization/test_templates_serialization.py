# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
from dataclasses import dataclass
from typing import Any, Dict

import pytest

from wayflowcore import Message
from wayflowcore.outputparser import (
    JsonOutputParser,
    JsonToolOutputParser,
    OutputParser,
    PythonToolOutputParser,
    RegexOutputParser,
    RegexPattern,
)
from wayflowcore.property import ObjectProperty, StringProperty
from wayflowcore.serialization import autodeserialize, serialize
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.templates import (
    LLAMA_AGENT_TEMPLATE,
    LLAMA_CHAT_TEMPLATE,
    NATIVE_AGENT_TEMPLATE,
    NATIVE_CHAT_TEMPLATE,
    PYTHON_CALL_AGENT_TEMPLATE,
    PYTHON_CALL_CHAT_TEMPLATE,
    REACT_AGENT_TEMPLATE,
    REACT_CHAT_TEMPLATE,
    PromptTemplate,
)


@pytest.mark.parametrize(
    "template",
    [
        REACT_AGENT_TEMPLATE,
        REACT_CHAT_TEMPLATE,
        LLAMA_CHAT_TEMPLATE,
        LLAMA_AGENT_TEMPLATE,
        NATIVE_CHAT_TEMPLATE,
        NATIVE_AGENT_TEMPLATE,
        PYTHON_CALL_AGENT_TEMPLATE,
        PYTHON_CALL_CHAT_TEMPLATE,
    ],
)
def test_all_default_templates_are_serializable(template):
    serialized_template = serialize(template)
    deserialized_template = autodeserialize(serialized_template)
    assert isinstance(deserialized_template, PromptTemplate)
    assert deserialized_template == template


def test_simple_custom_template_serialization():
    template = PromptTemplate(
        messages=[
            {"role": "system", "content": "system info"},
            PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
            {"role": "user", "content": "reminder"},
        ],
        response_format=ObjectProperty(
            name="some_object", properties={"content": StringProperty()}
        ),
    )
    serialized_template = serialize(template)
    deserialized_template = autodeserialize(serialized_template)
    assert isinstance(deserialized_template, PromptTemplate)
    assert deserialized_template == template


@pytest.mark.parametrize(
    "output_parser",
    [
        JsonOutputParser(),
        PythonToolOutputParser(),
        JsonToolOutputParser(),
        RegexOutputParser(regex_pattern=RegexPattern(".*")),
    ],
)
def test_output_parser_serialization(output_parser):
    serialized_output_parser = serialize(output_parser)
    deserialized_output_parser = autodeserialize(serialized_output_parser)
    assert deserialized_output_parser == output_parser


def test_serialization_of_template_with_custom_parser_works():
    class MyParser(OutputParser, SerializableObject):
        def _serialize_to_dict(
            self, serialization_context: "SerializationContext"
        ) -> Dict[str, Any]:
            return {}

        @classmethod
        def _deserialize_from_dict(
            cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
        ) -> "SerializableObject":
            return MyParser(__metadata_info__={})

        def parse_output(self, content: Message) -> Message:
            pass

        async def parse_output_streaming(self, content: Any) -> Any:
            pass

    parser = MyParser(__metadata_info__={})
    serialized_parser = serialize(parser)


def test_serialization_of_custom_parser_raises():
    @dataclass
    class MyParser(OutputParser):
        def parse_output(self, content: Message) -> Message:
            pass

        async def parse_output_streaming(self, content: Any) -> Any:
            pass

    parser = MyParser()
    with pytest.raises(ValueError, match="Serialization not implemented for MyParser"):
        serialized_parser = serialize(parser)


def test_serialization_of_template_with_custom_parser_raises():
    @dataclass
    class MyParser(OutputParser):
        def parse_output(self, content: Message) -> Message:
            pass

        async def parse_output_streaming(self, content: Any) -> Any:
            pass

    parser = MyParser()
    template = PromptTemplate.from_string("some text").with_output_parser(parser)
    with pytest.raises(ValueError, match="Serialization not implemented for MyParser"):
        serialized_parser = serialize(template)
