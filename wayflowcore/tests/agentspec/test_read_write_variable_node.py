# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import pytest
from pyagentspec.property import ListProperty, StringProperty

from wayflowcore import Flow
from wayflowcore.agentspec._runtimeconverter import AgentSpecToRuntimeConverter
from wayflowcore.agentspec.components.nodes import PluginReadVariableNode, PluginWriteVariableNode
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.property import ListProperty as RuntimeListProperty
from wayflowcore.property import StringProperty as RuntimeStringProperty


def test_read_variable_node_executes_correctly():
    agentspec_variable = ListProperty(
        title="variable",
        description="variable example",
        item_type=StringProperty(),
        default=[],
    )

    plugin_node = PluginReadVariableNode(
        name="ReadNode",
        variable=agentspec_variable,
    )

    runtime_step = AgentSpecToRuntimeConverter().convert(plugin_node, {})
    runtime_variable = AgentSpecToRuntimeConverter()._convert_property_to_runtime_variable(
        agentspec_variable
    )

    assert runtime_step.input_descriptors == []
    assert runtime_step.output_descriptors == [
        RuntimeListProperty(
            name="value",
            description="variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        )
    ]

    runtime_flow = Flow.from_steps([runtime_step], variables=[runtime_variable])

    conversation = runtime_flow.start_conversation()
    status = conversation.execute()

    assert status.output_values == {"value": []}
    assert isinstance(status, FinishedStatus)


def test_read_variable_node_with_output_mapping_executes_correctly():
    agentspec_variable = ListProperty(
        title="variable",
        description="variable example",
        item_type=StringProperty(),
        default=[],
    )

    plugin_node = PluginReadVariableNode(
        name="ReadNode",
        variable=agentspec_variable,
        output_mapping={PluginReadVariableNode.VALUE: "read_variable_output"},
    )

    runtime_step = AgentSpecToRuntimeConverter().convert(plugin_node, {})
    runtime_variable = AgentSpecToRuntimeConverter()._convert_property_to_runtime_variable(
        agentspec_variable
    )

    assert runtime_step.input_descriptors == []
    assert runtime_step.output_descriptors == [
        RuntimeListProperty(
            name="read_variable_output",
            description="variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        )
    ]

    runtime_flow = Flow.from_steps([runtime_step], variables=[runtime_variable])

    conversation = runtime_flow.start_conversation()
    status = conversation.execute()

    assert status.output_values == {"read_variable_output": []}
    assert isinstance(status, FinishedStatus)


def test_write_variable_node_with_default_write_operator_executes_correctly():
    agentspec_variable = ListProperty(
        title="variable",
        description="variable example",
        item_type=StringProperty(),
        default=[],
    )

    plugin_node = PluginWriteVariableNode(
        name="WriteNode",
        variable=agentspec_variable,
    )  # default write operator is "overwrite"

    runtime_step = AgentSpecToRuntimeConverter().convert(plugin_node, {})
    runtime_variable = AgentSpecToRuntimeConverter()._convert_property_to_runtime_variable(
        agentspec_variable
    )

    assert runtime_step.input_descriptors == [
        RuntimeListProperty(
            name="value",
            description="variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        )
    ]
    assert runtime_step.output_descriptors == []

    runtime_flow = Flow.from_steps([runtime_step], variables=[runtime_variable])

    conversation = runtime_flow.start_conversation()
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    conversation = runtime_flow.start_conversation({"value": ["a", "b"]})
    status = conversation.execute()
    assert conversation._get_variable_value(runtime_variable) == ["a", "b"]
    assert isinstance(status, FinishedStatus)


def test_write_variable_node_with_write_operator_and_input_mapping_executes_correctly():
    agentspec_variable = ListProperty(
        title="variable",
        description="variable example",
        item_type=StringProperty(),
        default=[],
    )

    plugin_node = PluginWriteVariableNode(
        name="WriteNode",
        variable=agentspec_variable,
        operation="insert",
        input_mapping={PluginWriteVariableNode.VALUE: "write_value"},
    )

    runtime_step = AgentSpecToRuntimeConverter().convert(plugin_node, {})
    runtime_variable = AgentSpecToRuntimeConverter()._convert_property_to_runtime_variable(
        agentspec_variable
    )

    assert runtime_step.input_descriptors == [
        RuntimeStringProperty(
            name="write_value",
            description="variable example (single element)",
        )
    ]
    assert runtime_step.output_descriptors == []

    runtime_flow = Flow.from_steps([runtime_step], variables=[runtime_variable])

    with pytest.raises(
        ValueError, match='Cannot start conversation because of missing inputs "write_value"'
    ):
        conversation = runtime_flow.start_conversation()

    conversation = runtime_flow.start_conversation({"write_value": "a"})
    status = conversation.execute()
    assert conversation._get_variable_value(runtime_variable) == ["a"]
    assert isinstance(status, FinishedStatus)
