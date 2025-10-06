# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import inspect
from typing import Any, Dict

import pytest

from wayflowcore import Agent, Flow, Message, Step, Tool
from wayflowcore.component import Component
from wayflowcore.contextproviders import ContextProvider
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.datastore import Entity, InMemoryDatastore, nullable
from wayflowcore.embeddingmodels import EmbeddingModel
from wayflowcore.mcp import SSETransport
from wayflowcore.models import LlmModel, VllmModel
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey
from wayflowcore.outputparser import RegexPattern
from wayflowcore.property import (
    FloatProperty,
    IntegerProperty,
    ListProperty,
    Property,
    StringProperty,
)
from wayflowcore.serialization.serializer import SerializableObject, serialize_to_dict
from wayflowcore.steps import CompleteStep, InputMessageStep, MapStep, OutputMessageStep, StartStep
from wayflowcore.tools import ServerTool
from wayflowcore.variable import Variable

from ..serialization.test_serializableobject import ALL_SERIALIZABLE_CLASSES

EXCLUDED_COMPONENTS = {
    # not supported
    "TlsOracleDatabaseConnectionConfig",
    "MTlsOracleDatabaseConnectionConfig",
    "StepDescription",
    "DescribedFlow",
    "DescribedAgent",
    "ClientTransport",
    "SSEmTLSTransport",
    "StreamableHTTPmTLSTransport",
    "OracleDatabaseDatastore",
    # abstract classes
    "Component",
    "Event",
    "OutputParser",
    # abstract classes
    "ContextProvider",
    "EmbeddingModel",
    "LlmModel",
    "Step",
    "Tool",
    "Property",
    "OracleDatabaseConnectionConfig",
    "FrozenSerializableDataclass",
    "Message",
    "MessageList",
    # Runtime objects
    "_TokenConsumptionEvent",
    "Conversation",
    "ExecutionStatus",
    "AgentConversation",
    "InterruptedExecutionStatus",
    "LlmCompletion",
    "SwarmThread",
    "UserMessageRequestStatus",
    "ToolRequestStatus",
    "FlowConversation",
    "ExecutionInterrupt",
    "SwarmConversation",
    "OciAgentConversation",
    "ManagerWorkersConversation",
    "SoftTokenLimitExecutionInterrupt",
    "ToolRequest",
    "FinishedStatus",
    "SwarmConversationExecutionState",
    "AgentConversationExecutionState",
    "FlowConversationExecutionState",
    "ManagerWorkersConversationExecutionState",
    "OciAgentState",
    "PromptBenchmarkerPlaceholder",
    # test classes
    "DummyModel",
    "SleepStep",
    "DoNothingStep",
    # TODO: Support these in the future
    "DatastoreQueryStep",  # requires a relational datastore, we only have oracledb and it requires a connection to create the object
    "MapStep",  # names are not equivalent, need some complex logic
    "ConstantContextProvider",  # is not serializable in wayflowcore so we can't test last step
    "Flow",
    "FlowExecutionStep",
    "FlowContextProvider",
    "RetryStep",
    "CatchExceptionStep",
    "BranchingStep",
    # the variable, stored as a agentspec property, doesn't keep the same id
    "Variable",
    "VariableReadStep",
    "VariableWriteStep",
}

ALL_ADDITIONAL_SUBCLASSES = list(
    component_class
    for component_class in {
        *Step.__subclasses__(),
        *ContextProvider.__subclasses__(),
        *LlmModel.__subclasses__(),
        *EmbeddingModel.__subclasses__(),
        *Tool.__subclasses__(),
        *Property.__subclasses__(),
    }
    if component_class.__name__ not in EXCLUDED_COMPONENTS
)

ALL_AGENTSPEC_EXPORTABLE_CLASS = [
    SerializableObject._COMPONENT_REGISTRY[component_class_name]
    for component_class_name in ALL_SERIALIZABLE_CLASSES
    if component_class_name not in EXCLUDED_COMPONENTS
]

llm = VllmModel(model_id="model_name", host_port="some/port")
main_agent = Agent(llm=llm, name="main")

start_step = StartStep(name="start_step", input_descriptors=[StringProperty(name="output")])
source_step = InputMessageStep(name="input_step", message_template="")
destination_step = OutputMessageStep(name="output_step", message_template="{{output}}")

schema = {
    "products": Entity(
        properties={
            "ID": IntegerProperty(description="Unique product identifier"),
            # Descriptions can be helpful if an LLM needs to fill these fields,
            # or generally disambiguate non-obvious property names
            "title": StringProperty(description="Brief summary of the product"),
            "description": StringProperty(),
            "price": FloatProperty(default_value=0.1),
            # Use nullable to define optional properties
            "category": nullable(StringProperty()),
        },
    )
}

control_flow_edges = [
    ControlFlowEdge(source_step=start_step, destination_step=destination_step),
    ControlFlowEdge(source_step=destination_step, destination_step=CompleteStep(name="end_step")),
]

INIT_PARAMETER_DEFAULT_VALUES = {
    "messages": [Message(content="message content", role="user")],
    "session_id": "some_id",
    "_client": None,
    "url": "/some/url",
    "agent_endpoint_id": "some_id",
    "client_config": OCIClientConfigWithApiKey(service_endpoint="service_endpoint"),
    "config": OCIClientConfigWithApiKey(
        service_endpoint="service_endpoint"
    ),  # for oci embedding models
    "pattern": RegexPattern(".*"),
    "regex_pattern": RegexPattern(".*"),
    "control_flow_edges": control_flow_edges,
    "model_id": "some_model",
    "base_url": "/some/url",
    "begin_step": start_step,
    "name": "some_tool",
    "description": "some description",
    "content": "message content",
    "tool_request_id": "some_id",
    "schema": schema,
    "client_transport": SSETransport(url="some_url"),
    "_validate_tool_exist_on_server": False,  # should not require connection for conversion
    "_validate_server_exists": False,  # should not require connection for conversion # TODO
    "source_step": source_step,
    "source_output": InputMessageStep.USER_PROVIDED_INPUT,
    "destination_step": destination_step,
    "destination_input": "output",
    "base64_content": "some_content".encode(),
    "type": StringProperty(),
    "command": "pwd",
    # swarm
    "first_agent": main_agent,
    "relationships": [
        (main_agent, Agent(llm=llm, name="sub_agent", description="some description"))
    ],
    # manager/worker
    "group_manager": main_agent,
    "workers": [Agent(llm=llm, name="sub_agent", description="some description")],
    "llm": llm,
    "_validate_api_key": False,
    "input_descriptors": [],
    "method": "POST",
    "compartment_id": "some_compartment_id",
    "func": lambda: "",
    "agent": main_agent,
    # properties
    "any_of": [StringProperty()],
    "flow": Flow(begin_step=start_step, control_flow_edges=control_flow_edges),
    "template": "",
    "message_template": "",
    "prompt_template": "",
    # 'template': '',
    "tool": ServerTool(
        name="some_tool", description="some_description", input_descriptors=[], func=lambda: ""
    ),
    # steps
    "constant_values": {"value": "constant_value_x"},
    "variable": Variable(
        name="var",
        description="some description",
        type=StringProperty(name="var", description="some description"),
    ),
    "success_condition": "output_message",
    "output_values": {"output_value": "."},
    "next_steps": [],
    "value": "some_value",
    "output_description": StringProperty(),
    "datastore": InMemoryDatastore(schema=schema),
    "collection_name": "products",
    "where": {"title": "{{user_requested_product}}"},
    "query": "SELECT *",
}

CLASS_SPECIFIC_INPUTS = {
    MapStep: {"input_descriptors": [ListProperty(name=MapStep.ITERATED_INPUT)]}
}


SKIP_ELEMENTS: Dict[str, Dict[str, Any]] = {
    "ApiCallStep": {
        "step_args": {"output_values_json": None}  # this is filled by default, we don't care
    },
}


def prune_dict_inplace(d1: dict, d2: dict, checks_equality: bool = True) -> dict:
    """
    Recursively remove keys from d1 if they exist in d2.
    - If checks_equality=True, prune only if values are equal.
    - If checks_equality=False, prune whenever the key exists in d2.

    Modifies d1 in place and returns the subset of d2 that was pruned.
    """
    if not isinstance(d1, dict) or not isinstance(d2, dict):
        return {}

    pruned = {}
    keys_to_delete = []

    for key, value in d1.items():
        if key in d2:
            if isinstance(value, dict) and isinstance(d2[key], dict):
                nested_pruned = prune_dict_inplace(value, d2[key], checks_equality)
                if nested_pruned:
                    pruned[key] = nested_pruned
                if not value:  # d1[key] became empty
                    keys_to_delete.append(key)
            else:
                if (checks_equality and value == d2[key]) or (not checks_equality):
                    keys_to_delete.append(key)
                    pruned[key] = value

    # Apply deletions
    for key in keys_to_delete:
        del d1[key]

    return pruned


def _check_component_equality(comp1: SerializableObject, comp2: SerializableObject):
    dict_1 = serialize_to_dict(comp1)
    dict_2 = serialize_to_dict(comp2)

    assert comp1.__class__ == comp2.__class__
    if comp1.__class__.__name__ in SKIP_ELEMENTS:
        elements_to_skip = SKIP_ELEMENTS[comp1.__class__.__name__]

        pruned = prune_dict_inplace(dict_2, elements_to_skip)
        if pruned:
            prune_dict_inplace(dict_1, pruned, checks_equality=False)

    # # un-comment for easier debugging
    # print(dict_1)
    # print(dict_2)

    assert dict_1 == dict_2


def _validate_compatibility(obj):
    from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader

    serialized_version = AgentSpecExporter().to_yaml(obj)

    tool_registry = {}
    if hasattr(obj, "_referenced_tools"):
        tool_registry.update({tool.name: tool for tool in obj._referenced_tools()})
    if isinstance(obj, ServerTool):
        tool_registry.update({obj.name: obj})

    deserialized_version = AgentSpecLoader(tool_registry=tool_registry).load_yaml(
        serialized_version
    )
    _check_component_equality(deserialized_version, obj)


CLASSES_TO_RUN = list(
    sorted(ALL_AGENTSPEC_EXPORTABLE_CLASS + ALL_ADDITIONAL_SUBCLASSES, key=lambda x: x.__name__)
)


@pytest.mark.parametrize("component_class", CLASSES_TO_RUN)
def test_coverage(component_class, with_mcp_enabled):

    if not issubclass(component_class, Component):
        pytest.skip()

    # Get constructor signature
    sig = inspect.signature(component_class.__init__)
    kwargs = {}

    for name, param in sig.parameters.items():
        if name == "self":
            continue

        # First check explicit defaults dictionary
        if name in INIT_PARAMETER_DEFAULT_VALUES:
            kwargs[name] = INIT_PARAMETER_DEFAULT_VALUES[name]
            continue

    if component_class in CLASS_SPECIFIC_INPUTS:
        kwargs.update(**CLASS_SPECIFIC_INPUTS[component_class])

    obj = component_class(**kwargs)
    _validate_compatibility(obj)
