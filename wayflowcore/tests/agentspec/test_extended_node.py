# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List, Type

import pytest
from pyagentspec import AgentSpecSerializer
from pyagentspec.datastores import OracleDatabaseDatastore, TlsOracleDatabaseConnectionConfig
from pyagentspec.flows.edges import ControlFlowEdge, DataFlowEdge
from pyagentspec.flows.flow import Flow
from pyagentspec.flows.nodes import EndNode, StartNode
from pyagentspec.property import (
    FloatProperty,
    IntegerProperty,
    ListProperty,
    ObjectProperty,
    StringProperty,
)
from pyagentspec.tools import ClientTool

from wayflowcore import MessageType
from wayflowcore.agentspec.components import (
    ExtendedMapNode,
    ExtendedToolNode,
    PluginCatchExceptionNode,
    PluginExtractNode,
    PluginInputMessageNode,
    PluginOutputMessageNode,
    PluginReadVariableNode,
    PluginWriteVariableNode,
    all_deserialization_plugin,
    all_serialization_plugin,
)
from wayflowcore.agentspec.components.datastores.nodes import (
    PluginDatastoreCreateNode,
    PluginDatastoreDeleteNode,
    PluginDatastoreListNode,
    PluginDatastoreQueryNode,
    PluginDatastoreUpdateNode,
)
from wayflowcore.agentspec.components.node import ExtendedNode

city_input = StringProperty(title="city_as_input", default="zurich")
city_output = StringProperty(title="city_as_output")
start_node = StartNode(inputs=[city_input], name="start_node")
end_node = EndNode(outputs=[city_output], name="end_node")

example_flow = Flow(
    name="Flow",
    start_node=start_node,
    nodes=[start_node, end_node],
    control_flow_connections=[ControlFlowEdge(name="edge", from_node=start_node, to_node=end_node)],
    data_flow_connections=[
        DataFlowEdge(
            name="edge",
            source_node=start_node,
            source_output="city_as_input",
            destination_node=end_node,
            destination_input="city_as_output",
        ),
    ],
)

example_datastore = OracleDatabaseDatastore(
    name="ds",
    datastore_schema={
        "my_table": ObjectProperty(
            properties={
                "column_1": IntegerProperty(title="some_integer"),
                "column_2": FloatProperty(title="some_number"),
            }
        )
    },
    connection_config=TlsOracleDatabaseConnectionConfig(
        name="connection_config",
        user="SENSITIVE_FIELD",
        password="SENSITIVE_FIELD",
        dsn="SENSITIVE_FIELD",
    ),
)

example_tool = ClientTool(name="example_tool", inputs=[city_input], outputs=[city_output])

example_variable = ListProperty(
    title="variable",
    description="example variable",
    item_type=StringProperty(),
)

test_cases = [
    (
        PluginDatastoreQueryNode,
        dict(
            name="node",
            datastore=example_datastore,
            query="SELECT * FROM my_table",
            input_mapping={"bind_variables": "awesome_values"},
            output_mapping={"result": "awesome_result"},
        ),
        [
            {
                "type": "object",
                "additionalProperties": {},
                "key_type": {"type": "string"},
                "title": "awesome_values",
            }
        ],
        [
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": {},
                    "key_type": {"type": "string"},
                },
                "title": "awesome_result",
            }
        ],
    ),
    (
        PluginDatastoreCreateNode,
        dict(
            name="node",
            datastore=example_datastore,
            collection_name="my_table",
            input_mapping={"entity": "OBJECT"},
            output_mapping={"created_entity": "new_object"},
        ),
        [
            {
                "type": "object",
                "additionalProperties": {},
                "key_type": {"type": "string"},
                "title": "OBJECT",
            }
        ],
        [
            {
                "type": "object",
                "additionalProperties": {},
                "key_type": {"type": "string"},
                "title": "new_object",
            }
        ],
    ),
    (
        PluginDatastoreDeleteNode,
        dict(
            name="node",
            datastore=example_datastore,
            collection_name="{{pick_the_table}}",
            where={"column_1": "{{pick_the_value}}"},
            input_mapping={"pick_the_value": "XYZ"},
        ),
        [
            {
                "type": "string",
                "title": "pick_the_table",
                "description": '"pick_the_table" input variable for the template',
            },
            {
                "type": "string",
                "title": "XYZ",
                "description": '"pick_the_value" input variable for the template',
            },
        ],
        [],
    ),
    (
        PluginDatastoreListNode,
        dict(
            name="node",
            datastore=example_datastore,
            collection_name="{{pick_the_table}}",
            where={},
            input_mapping={"pick_the_table": "any_table"},
            limit=None,
            unpack_single_entity_from_list=None,
            output_mapping={"entities": "objects"},
        ),
        [
            {
                "type": "string",
                "title": "any_table",
                "description": '"pick_the_table" input variable for the template',
            }
        ],
        [
            {
                "title": "objects",
                "items": {
                    "type": "object",
                    "additionalProperties": {},
                    "key_type": {"type": "string"},
                },
                "type": "array",
            }
        ],
    ),
    (
        PluginDatastoreUpdateNode,
        dict(
            name="node",
            datastore=example_datastore,
            collection_name="my_table",
            where={},
            input_mapping={"update": "improvements"},
            output_mapping={"entities": "improved_objects"},
        ),
        [
            {
                "type": "object",
                "additionalProperties": {},
                "key_type": {"type": "string"},
                "title": "improvements",
            }
        ],
        [
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": {},
                    "key_type": {"type": "string"},
                },
                "title": "improved_objects",
            }
        ],
    ),
    (
        PluginOutputMessageNode,
        dict(
            name="node",
            input_mapping={"A": "C"},
            message="{{A}}",
            message_type=MessageType.AGENT,
            rephrase=False,
            llm_config=None,
            output_mapping={"output_message": "MESSAGE"},
        ),
        [{"title": "C", "type": "string"}],
        [{"title": "MESSAGE", "type": "string"}],
    ),
    (
        PluginExtractNode,
        dict(
            name="node",
            output_values={"some_value": "."},
            input_mapping={"text": "text_as_json"},
            output_mapping={"some_value": "my_value"},
        ),
        [{"title": "text_as_json", "type": "string"}],
        [{"title": "my_value"}],
    ),
    (
        PluginCatchExceptionNode,
        dict(
            name="node",
            flow=example_flow,
            except_on=None,
            catch_all_exceptions=True,
            input_mapping={"city_as_input": "MY_INPUT"},
            output_mapping={"exception_payload_name": "PAYLOAD"},
        ),
        [{"title": "MY_INPUT", "default": "zurich", "type": "string"}],
        [
            {"title": "city_as_output", "type": "string"},
            {"title": "exception_name", "type": "string", "default": ""},
            {"title": "PAYLOAD", "type": "string", "default": ""},
        ],
    ),
    (
        PluginInputMessageNode,
        dict(
            name="node",
            message_template="{{a}}{{b}}",
            rephrase=False,
            llm_config=None,
            input_mapping={"b": "c"},
            output_mapping={"user_provided_input": "request"},
        ),
        [{"title": "a", "type": "string"}, {"title": "c", "type": "string"}],
        [{"title": "request", "type": "string"}],
    ),
    (
        ExtendedMapNode,
        dict(
            name="node",
            flow=example_flow,
            unpack_input={"city_as_input": "."},
            parallel_execution=False,
            input_mapping={"iterated_input": "CITY_LIST"},
        ),
        [
            {
                "title": "CITY_LIST",
                "description": "iterated input for the map step",
                "items": {"title": "city_as_input", "default": "zurich", "type": "string"},
                "type": "array",
            }
        ],
        [],  # ExtendedMapNode relies on specifying outputs explicitly which is not compatible with using io mappings
    ),
    (
        ExtendedToolNode,
        dict(
            name="node",
            tool=example_tool,
            raise_exceptions=True,
            input_mapping={"city_as_input": "MY_INPUT"},
            output_mapping={"city_as_output": "MY_OUTPUT"},
        ),
        [{"default": "zurich", "title": "MY_INPUT", "type": "string"}],
        [{"title": "MY_OUTPUT", "type": "string"}],
    ),
    (
        PluginReadVariableNode,
        dict(
            name="node",
            variable=example_variable,
            output_mapping={"value": "MY_OUTPUT"},
        ),
        [],
        [
            {
                "title": "MY_OUTPUT",
                "description": "example variable",
                "items": {"type": "string"},
                "type": "array",
            }
        ],
    ),
    (
        PluginWriteVariableNode,
        dict(
            name="node",
            variable=example_variable,
            input_mapping={"value": "MY_INPUT"},
        ),
        [
            {
                "title": "MY_INPUT",
                "description": "example variable",
                "items": {"type": "string"},
                "type": "array",
            }
        ],
        [],
    ),
    (
        PluginWriteVariableNode,
        dict(
            name="node",
            variable=example_variable,
            operation="insert",
            input_mapping={"value": "MY_INPUT"},
        ),
        [
            {
                "title": "MY_INPUT",
                "description": "example variable (single element)",
                "type": "string",
            }
        ],
        [],
    ),
]


@pytest.mark.parametrize(
    "node_cls, node_args, expected_schemas",
    [(node_cls, node_args, input_schemas) for node_cls, node_args, input_schemas, _ in test_cases],
)
def test_extended_node_using_io_mapping_has_correct_inputs(
    node_cls: Type[ExtendedNode], node_args: Dict[str, Any], expected_schemas: List[Dict[str, Any]]
) -> None:
    node = node_cls(**node_args)
    assert len(node.inputs) == len(expected_schemas)
    for input_property in node.inputs:
        assert input_property.json_schema in expected_schemas


@pytest.mark.parametrize(
    "node_cls, node_args, expected_schemas",
    [
        (node_cls, node_args, output_schemas)
        for node_cls, node_args, _, output_schemas in test_cases
    ],
)
def test_extended_node_using_io_mapping_has_correct_outputs(
    node_cls: Type[ExtendedNode], node_args: Dict[str, Any], expected_schemas: List[Dict[str, Any]]
) -> None:
    node = node_cls(**node_args)
    assert len(node.outputs) == len(expected_schemas)
    for output_property in node.outputs:
        assert output_property.json_schema in expected_schemas


# list need to be sorted so the order of registered classes is deterministic
ALL_NODE_SUBCLASSES = sorted(list(ExtendedNode._get_all_subclasses()), key=lambda x: x.__name__)


@pytest.mark.parametrize(
    "extended_node_cls",
    [
        extended_node_cls
        for extended_node_cls in ALL_NODE_SUBCLASSES
        if not extended_node_cls._is_abstract
    ],
)
def test_extended_node_can_be_partially_constructed_out_of_nothing(extended_node_cls) -> None:
    partially_constructed_node = extended_node_cls.build_from_partial_config(
        {"name": "node"}, plugins=all_deserialization_plugin
    )
    assert isinstance(partially_constructed_node, extended_node_cls)


@pytest.mark.parametrize(
    "node_cls, node_args, expected_schemas",
    [(node_cls, node_args, input_schemas) for node_cls, node_args, input_schemas, _ in test_cases],
)
def test_nodes_do_not_contain_sensitive_info(
    node_cls: Type[ExtendedNode], node_args: Dict[str, Any], expected_schemas: List[Dict[str, Any]]
) -> None:
    node = node_cls(**node_args)
    flow = Flow(
        name="some-flow",
        start_node=start_node,
        nodes=[start_node, node, end_node],
        control_flow_connections=[
            ControlFlowEdge(name="start_to_llm", from_node=start_node, to_node=node),
            ControlFlowEdge(name="llm_to_end", from_node=node, to_node=end_node),
        ],
    )
    serialized_node = AgentSpecSerializer(plugins=all_serialization_plugin).to_json(flow)
    assert "SENSITIVE_FIELD" not in serialized_node
