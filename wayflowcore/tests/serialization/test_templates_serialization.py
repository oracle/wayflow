# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import Any, Dict

import pytest

from wayflowcore import Message, __version__
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
from wayflowcore.serialization.plugins import WayflowSerializationPlugin
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

from ..testhelpers.serialization import make_serialization_plugin


@pytest.fixture
def my_parser_with_serde_class():

    class MyParser(OutputParser):

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

    try:
        yield MyParser
    finally:
        # need to manually remove it from registry so that it doesn't appear in the registry of other tests
        SerializableObject._COMPONENT_REGISTRY.pop(MyParser.__name__)


@pytest.fixture
def my_parser_without_serde_class():

    class MyParserNoSerde(OutputParser):

        def parse_output(self, content: Message) -> Message:
            pass

        async def parse_output_streaming(self, content: Any) -> Any:
            pass

    try:
        yield MyParserNoSerde
    finally:
        # need to manually remove it from registry so that it doesn't appear in the registry of other tests
        SerializableObject._COMPONENT_REGISTRY.pop(MyParserNoSerde.__name__)


@pytest.fixture
def my_parser_serialization_plugin(my_parser_with_serde_class: type[SerializableObject]):
    return make_serialization_plugin(
        [my_parser_with_serde_class], name="MyParserPlugin", version=__version__
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


def test_serialization_of_template_with_custom_parser_works(
    my_parser_with_serde_class: type, my_parser_serialization_plugin: WayflowSerializationPlugin
):
    parser = my_parser_with_serde_class()
    serialized_parser = serialize(parser, plugins=[my_parser_serialization_plugin])
    assert "MyParser" in serialized_parser


def test_serialization_of_template_with_custom_parser_without_plugin_works(
    my_parser_with_serde_class: type,
):
    parser = my_parser_with_serde_class(__metadata_info__={})
    with pytest.warns(
        UserWarning,
        match="Found no serialization plugin to serialize the object of type `MyParser`. Trying using the builtins serialization plugin instead.",
    ):
        serialized_parser = serialize(parser)
    assert "MyParser" in serialized_parser


def test_serialization_of_custom_parser_raises(
    my_parser_without_serde_class: type, my_parser_serialization_plugin: WayflowSerializationPlugin
):
    parser = my_parser_without_serde_class()
    with pytest.raises(ValueError, match="Serialization not implemented for MyParserNoSerde"):
        _ = serialize(parser, plugins=[my_parser_serialization_plugin])


def test_serialization_of_template_with_custom_parser_raises(
    my_parser_without_serde_class: type, my_parser_serialization_plugin: WayflowSerializationPlugin
):
    parser = my_parser_without_serde_class()
    template = PromptTemplate.from_string("some text").with_output_parser(parser)
    with pytest.raises(ValueError, match="Serialization not implemented for MyParserNoSerde"):
        _ = serialize(template, plugins=[my_parser_serialization_plugin])
