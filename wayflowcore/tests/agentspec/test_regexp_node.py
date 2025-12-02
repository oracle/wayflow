# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import cast

import pytest
from pyagentspec.property import Property, StringProperty

from wayflowcore import Flow
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.agentspec._runtimeconverter import AgentSpecToWayflowConversionContext
from wayflowcore.agentspec.components.nodes import PluginRegexNode
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.property import ListProperty as RuntimeListProperty
from wayflowcore.property import StringProperty as RuntimeStringProperty
from wayflowcore.steps import RegexExtractionStep


def test_regexp_extraction_step_can_be_exported_to_agentspec_then_imported() -> None:
    step = RegexExtractionStep(regex_pattern=r"\b\w+@\w+\.\w+")
    flow = Flow.from_steps([step])
    serialized_flow = AgentSpecExporter().to_yaml(flow)
    new_flow = cast(Flow, AgentSpecLoader().load_yaml(serialized_flow))
    conversation = new_flow.start_conversation(
        {RegexExtractionStep.TEXT: "My email is john@example.com"}
    )
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {RegexExtractionStep.OUTPUT: "john@example.com"}


def test_regex_node_with_mapped_ios_executes_correctly():
    plugin_node = PluginRegexNode(
        name="MyNumberExtractionNode",
        regex_pattern=r"\d+",
        return_first_match_only=False,
        input_mapping={PluginRegexNode.DEFAULT_INPUT_KEY: "MyTextFullOfNumbers"},
        output_mapping={PluginRegexNode.DEFAULT_OUTPUT_KEY: "AllMyExtractedNumbers"},
    )
    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    assert runtime_step.input_descriptors == [RuntimeStringProperty(name="MyTextFullOfNumbers")]
    assert runtime_step.output_descriptors == [
        RuntimeListProperty(
            name="AllMyExtractedNumbers", item_type=RuntimeStringProperty(name="output_item")
        )
    ]
    runtime_flow = Flow.from_steps([runtime_step])
    with pytest.raises(
        ValueError,
        match='Cannot start conversation because of missing inputs "MyTextFullOfNumbers"',
    ):
        # Starting without the renamed input should raise
        runtime_flow.start_conversation({PluginRegexNode.DEFAULT_INPUT_KEY: "xyz"})

    conversation = runtime_flow.start_conversation({"MyTextFullOfNumbers": "xyz"})
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {"AllMyExtractedNumbers": []}

    conversation = runtime_flow.start_conversation(
        {"MyTextFullOfNumbers": "This 123 text 45 contains 678 numbers 9"}
    )
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {"AllMyExtractedNumbers": ["123", "45", "678", "9"]}


def test_regex_node_with_default_properties_correctly_executes():
    plugin_node = PluginRegexNode(
        name="MyNumberExtractionNode",
        regex_pattern=r"\d+",
        inputs=[
            Property(
                json_schema={
                    "title": PluginRegexNode.DEFAULT_INPUT_KEY,
                    "type": "string",
                    "default": "My password: ABCD",
                }
            )
        ],
        outputs=[StringProperty(title=PluginRegexNode.DEFAULT_OUTPUT_KEY, default="1234")],
    )
    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_flow = Flow.from_steps([runtime_step])

    conversation = runtime_flow.start_conversation(
        {PluginRegexNode.DEFAULT_INPUT_KEY: "My password: 5678"}
    )
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {PluginRegexNode.DEFAULT_OUTPUT_KEY: "5678"}

    conversation = runtime_flow.start_conversation()
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {PluginRegexNode.DEFAULT_OUTPUT_KEY: "1234"}

    conversation = runtime_flow.start_conversation(
        {PluginRegexNode.DEFAULT_INPUT_KEY: "My password: wxyz"}
    )
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {PluginRegexNode.DEFAULT_OUTPUT_KEY: "1234"}
