# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pytest
from pyagentspec.property import ListProperty, StringProperty

from wayflowcore import Flow
from wayflowcore.agentspec._runtimeconverter import AgentSpecToWayflowConversionContext
from wayflowcore.agentspec.components.nodes import (
    PluginReadVariableNode,
    PluginVariableNode,
    PluginVariableWriteOperation,
    PluginWriteVariableNode,
)
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

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_variable = runtime_step.variable

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

    assert isinstance(status, FinishedStatus)
    assert status.output_values == {"value": []}


def test_variable_node_for_read_executes_correctly():
    var_name = "variable_name"

    agentspec_variable = ListProperty(
        title=var_name,
        description="variable example",
        item_type=StringProperty(),
        default=[],
    )

    plugin_node = PluginVariableNode(
        name="VarNodeForRead",
        read_variables=[agentspec_variable],
    )

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_variables = runtime_step.read_variables
    assert len(runtime_variables) == 1

    assert runtime_step.input_descriptors == []
    assert runtime_step.output_descriptors == [
        RuntimeListProperty(
            name=var_name,
            description="variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        )
    ]

    runtime_flow = Flow.from_steps([runtime_step], variables=runtime_variables)

    conversation = runtime_flow.start_conversation()
    status = conversation.execute()

    assert isinstance(status, FinishedStatus)
    assert status.output_values == {var_name: []}


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

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_variable = runtime_step.variable

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

    assert isinstance(status, FinishedStatus)
    assert status.output_values == {"read_variable_output": []}


def test_variable_node_for_read_with_output_mapping_executes_correctly():
    var_name = "variable_name"

    agentspec_variable = ListProperty(
        title=var_name,
        description="variable example",
        item_type=StringProperty(),
        default=["hello"],
    )

    plugin_node = PluginVariableNode(
        name="VarNodeForRead",
        read_variables=[agentspec_variable],
        output_mapping={var_name: "read_variable_output"},
    )

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_variables = runtime_step.read_variables
    assert len(runtime_variables) == 1

    assert runtime_step.input_descriptors == []
    assert runtime_step.output_descriptors == [
        RuntimeListProperty(
            name="read_variable_output",
            description="variable example",
            item_type=RuntimeStringProperty(),
            default_value=["hello"],
        )
    ]

    runtime_flow = Flow.from_steps([runtime_step], variables=runtime_variables)

    conversation = runtime_flow.start_conversation()
    status = conversation.execute()

    assert isinstance(status, FinishedStatus)
    assert status.output_values == {"read_variable_output": ["hello"]}


def test_write_variable_node_executes_correctly():
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

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_variable = runtime_step.variable

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


def test_variable_node_for_write_executes_correctly():
    var_name = "variable_name"

    agentspec_variable = ListProperty(
        title=var_name,
        description="variable example",
        item_type=StringProperty(),
        default=[],
    )

    plugin_node = PluginVariableNode(
        name="VarNodeForWrite",
        write_variables=[agentspec_variable],
        write_operations={var_name: PluginVariableWriteOperation.OVERWRITE},
    )

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_variables = runtime_step.write_variables
    assert len(runtime_variables) == 1
    runtime_variable = runtime_variables[0]

    assert runtime_step.input_descriptors == [
        RuntimeListProperty(
            name=var_name,
            description="variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        )
    ]
    assert runtime_step.output_descriptors == []

    runtime_flow = Flow.from_steps([runtime_step], variables=runtime_variables)

    conversation = runtime_flow.start_conversation()
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    conversation = runtime_flow.start_conversation({var_name: ["a", "b"]})
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
        operation=PluginVariableWriteOperation.INSERT,
        input_mapping={PluginWriteVariableNode.VALUE: "write_value"},
    )

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_variable = runtime_step.variable

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


def test_variable_node_for_write_with_write_operator_and_input_mapping_executes_correctly():
    var_name = "variable_name"

    agentspec_variable = ListProperty(
        title=var_name,
        description="variable example",
        item_type=StringProperty(),
        default=[],
    )

    plugin_node = PluginVariableNode(
        name="VarNodeForWrite",
        write_variables=[agentspec_variable],
        write_operations={var_name: PluginVariableWriteOperation.INSERT},
        input_mapping={var_name: "write_value"},
    )

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_variables = runtime_step.write_variables
    assert len(runtime_variables) == 1
    runtime_variable = runtime_variables[0]

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


def test_variable_node_for_read_and_write_executes_correctly():
    var_name = "variable_name"

    agentspec_variable = ListProperty(
        title=var_name,
        description="variable example",
        item_type=StringProperty(),
        default=[],
    )

    plugin_node = PluginVariableNode(
        name="VarNodeForReadWrite",
        read_variables=[agentspec_variable],
        write_variables=[agentspec_variable],
        write_operations={var_name: PluginVariableWriteOperation.OVERWRITE},
    )

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    assert len(runtime_step.read_variables) == len(runtime_step.write_variables) == 1
    runtime_variables = runtime_step.write_variables
    runtime_variable = runtime_variables[0]

    assert runtime_step.input_descriptors == [
        RuntimeListProperty(
            name=var_name,
            description="variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        )
    ]
    assert runtime_step.output_descriptors == [
        RuntimeListProperty(
            name=var_name,
            description="variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        )
    ]

    runtime_flow = Flow.from_steps([runtime_step], variables=runtime_variables)

    conversation = runtime_flow.start_conversation()
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    conversation = runtime_flow.start_conversation({var_name: ["a", "b"]})
    status = conversation.execute()
    assert conversation._get_variable_value(runtime_variable) == ["a", "b"]
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {var_name: ["a", "b"]}


def test_variable_node_for_read_and_write_with_write_operator_and_mapping_with_same_names_executes_correctly():
    var_name = "variable_name"

    agentspec_variable = ListProperty(
        title=var_name,
        description="variable example",
        item_type=StringProperty(),
        default=[],
    )

    plugin_node = PluginVariableNode(
        name="VarNodeForReadWrite",
        read_variables=[agentspec_variable],
        write_variables=[agentspec_variable],
        write_operations={var_name: PluginVariableWriteOperation.OVERWRITE},
        input_mapping={var_name: "val"},
        output_mapping={var_name: "val"},
    )

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_variables = runtime_step.write_variables
    assert len(runtime_step.read_variables) == len(runtime_step.write_variables) == 1
    runtime_variable = runtime_variables[0]

    assert runtime_step.input_descriptors == [
        RuntimeListProperty(
            name="val",
            description="variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        )
    ]
    assert runtime_step.output_descriptors == [
        RuntimeListProperty(
            name="val",
            description="variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        )
    ]

    runtime_flow = Flow.from_steps([runtime_step], variables=runtime_variables)

    conversation = runtime_flow.start_conversation()
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    conversation = runtime_flow.start_conversation({"val": ["a", "b"]})
    status = conversation.execute()
    assert conversation._get_variable_value(runtime_variable) == ["a", "b"]
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {"val": ["a", "b"]}


def test_variable_node_for_read_and_write_with_write_operator_and_mapping_with_different_names_executes_correctly():
    var_name = "variable_name"

    agentspec_variable = ListProperty(
        title=var_name,
        description="variable example",
        item_type=StringProperty(),
        default=[],
    )

    plugin_node = PluginVariableNode(
        name="VarNodeForReadWrite",
        read_variables=[agentspec_variable],
        write_variables=[agentspec_variable],
        write_operations={var_name: PluginVariableWriteOperation.OVERWRITE},
        input_mapping={var_name: "input-val"},
        output_mapping={var_name: "output-val"},
    )

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_variables = runtime_step.write_variables
    assert len(runtime_step.read_variables) == len(runtime_step.write_variables) == 1
    runtime_variable = runtime_variables[0]

    assert runtime_step.input_descriptors == [
        RuntimeListProperty(
            name="input-val",
            description="variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        )
    ]
    assert runtime_step.output_descriptors == [
        RuntimeListProperty(
            name="output-val",
            description="variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        )
    ]

    runtime_flow = Flow.from_steps([runtime_step], variables=runtime_variables)

    conversation = runtime_flow.start_conversation()
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    conversation = runtime_flow.start_conversation({"input-val": ["a", "b"]})
    status = conversation.execute()
    assert conversation._get_variable_value(runtime_variable) == ["a", "b"]
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {"output-val": ["a", "b"]}


def test_variable_node_for_read_and_write_for_two_vars_executes_correctly():
    var_name_1 = "variable_name_1"
    var_name_2 = "variable_name_2"

    agentspec_variable_1 = ListProperty(
        title=var_name_1,
        description="list variable example",
        item_type=StringProperty(),
        default=[],
    )
    agentspec_variable_2 = StringProperty(
        title=var_name_2,
        description="string variable example",
        default="hello",
    )

    plugin_node = PluginVariableNode(
        name="VarNodeForReadWrite",
        read_variables=[agentspec_variable_1, agentspec_variable_2],
        write_variables=[agentspec_variable_1, agentspec_variable_2],
        write_operations={
            var_name_1: PluginVariableWriteOperation.OVERWRITE,
            var_name_2: PluginVariableWriteOperation.OVERWRITE,
        },
    )

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_variables = runtime_step.write_variables
    assert len(runtime_step.read_variables) == len(runtime_step.write_variables) == 2
    runtime_variable_1 = runtime_variables[0]
    runtime_variable_2 = runtime_variables[1]

    assert runtime_step.input_descriptors == [
        RuntimeListProperty(
            name=var_name_1,
            description="list variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        ),
        RuntimeStringProperty(
            name=var_name_2,
            description="string variable example",
            default_value="hello",
        ),
    ]
    assert runtime_step.output_descriptors == [
        RuntimeListProperty(
            name=var_name_1,
            description="list variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        ),
        RuntimeStringProperty(
            name=var_name_2,
            description="string variable example",
            default_value="hello",
        ),
    ]

    runtime_flow = Flow.from_steps([runtime_step], variables=runtime_variables)

    conversation = runtime_flow.start_conversation()
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    conversation = runtime_flow.start_conversation(
        {
            var_name_1: ["a", "b"],
            var_name_2: "bye",
        }
    )
    status = conversation.execute()
    assert conversation._get_variable_value(runtime_variable_1) == ["a", "b"]
    assert conversation._get_variable_value(runtime_variable_2) == "bye"
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {
        var_name_1: ["a", "b"],
        var_name_2: "bye",
    }


def test_variable_node_for_read_and_write_for_two_vars_with_write_operator_and_mapping_with_same_names_executes_correctly():
    var_name_1 = "variable_name_1"
    var_name_2 = "variable_name_2"

    agentspec_variable_1 = ListProperty(
        title=var_name_1,
        description="list variable example",
        item_type=StringProperty(),
        default=[],
    )
    agentspec_variable_2 = StringProperty(
        title=var_name_2,
        description="string variable example",
        default="hello",
    )

    plugin_node = PluginVariableNode(
        name="VarNodeForReadWrite",
        read_variables=[agentspec_variable_1, agentspec_variable_2],
        write_variables=[agentspec_variable_1, agentspec_variable_2],
        write_operations={
            var_name_1: PluginVariableWriteOperation.OVERWRITE,
            var_name_2: PluginVariableWriteOperation.OVERWRITE,
        },
        input_mapping={
            var_name_1: "val-1",
            var_name_2: "val-2",
        },
        output_mapping={
            var_name_1: "val-1",
            var_name_2: "val-2",
        },
    )

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_variables = runtime_step.write_variables
    assert len(runtime_step.read_variables) == len(runtime_step.write_variables) == 2
    runtime_variable_1 = runtime_variables[0]
    runtime_variable_2 = runtime_variables[1]

    assert runtime_step.input_descriptors == [
        RuntimeListProperty(
            name="val-1",
            description="list variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        ),
        RuntimeStringProperty(
            name="val-2",
            description="string variable example",
            default_value="hello",
        ),
    ]
    assert runtime_step.output_descriptors == [
        RuntimeListProperty(
            name="val-1",
            description="list variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        ),
        RuntimeStringProperty(
            name="val-2",
            description="string variable example",
            default_value="hello",
        ),
    ]

    runtime_flow = Flow.from_steps([runtime_step], variables=runtime_variables)

    conversation = runtime_flow.start_conversation()
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    conversation = runtime_flow.start_conversation(
        {
            "val-1": ["a", "b"],
            "val-2": "bye",
        }
    )
    status = conversation.execute()
    assert conversation._get_variable_value(runtime_variable_1) == ["a", "b"]
    assert conversation._get_variable_value(runtime_variable_2) == "bye"
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {
        "val-1": ["a", "b"],
        "val-2": "bye",
    }


def test_variable_node_for_read_and_write_for_two_vars_with_write_operator_and_mapping_with_different_names_executes_correctly():
    var_name_1 = "variable_name_1"
    var_name_2 = "variable_name_2"

    agentspec_variable_1 = ListProperty(
        title=var_name_1,
        description="list variable example",
        item_type=StringProperty(),
        default=[],
    )
    agentspec_variable_2 = StringProperty(
        title=var_name_2,
        description="string variable example",
        default="hello",
    )

    plugin_node = PluginVariableNode(
        name="VarNodeForReadWrite",
        read_variables=[agentspec_variable_1, agentspec_variable_2],
        write_variables=[agentspec_variable_1, agentspec_variable_2],
        write_operations={
            var_name_1: PluginVariableWriteOperation.OVERWRITE,
            var_name_2: PluginVariableWriteOperation.OVERWRITE,
        },
        input_mapping={
            var_name_1: "input-val-1",
            var_name_2: "input-val-2",
        },
        output_mapping={
            var_name_1: "output-val-1",
            var_name_2: "output-val-2",
        },
    )

    runtime_step = AgentSpecToWayflowConversionContext().convert(plugin_node, {})
    runtime_variables = runtime_step.write_variables
    assert len(runtime_step.read_variables) == len(runtime_step.write_variables) == 2
    runtime_variable_1 = runtime_variables[0]
    runtime_variable_2 = runtime_variables[1]

    assert runtime_step.input_descriptors == [
        RuntimeListProperty(
            name="input-val-1",
            description="list variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        ),
        RuntimeStringProperty(
            name="input-val-2",
            description="string variable example",
            default_value="hello",
        ),
    ]
    assert runtime_step.output_descriptors == [
        RuntimeListProperty(
            name="output-val-1",
            description="list variable example",
            item_type=RuntimeStringProperty(),
            default_value=[],
        ),
        RuntimeStringProperty(
            name="output-val-2",
            description="string variable example",
            default_value="hello",
        ),
    ]

    runtime_flow = Flow.from_steps([runtime_step], variables=runtime_variables)

    conversation = runtime_flow.start_conversation()
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    conversation = runtime_flow.start_conversation(
        {
            "input-val-1": ["a", "b"],
            "input-val-2": "bye",
        }
    )
    status = conversation.execute()
    assert conversation._get_variable_value(runtime_variable_1) == ["a", "b"]
    assert conversation._get_variable_value(runtime_variable_2) == "bye"
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {
        "output-val-1": ["a", "b"],
        "output-val-2": "bye",
    }
