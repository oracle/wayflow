# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import re
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Union, cast

import pytest
from pyagentspec.component import Component as AgentSpecComponent
from pyagentspec.serialization import ComponentDeserializationPlugin, ComponentSerializationPlugin
from pyagentspec.serialization.pydanticdeserializationplugin import (
    PydanticComponentDeserializationPlugin,
)
from pyagentspec.serialization.pydanticserializationplugin import (
    PydanticComponentSerializationPlugin,
)
from pyagentspec.tools import Tool as AgentSpecTool

from wayflowcore.agent import Agent as Agent
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.flow import Flow
from wayflowcore.models import VllmModel
from wayflowcore.serialization import autodeserialize, serialize
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.plugins import (
    _COMPONENT_PLUGIN_NAME_FIELD,
    _COMPONENT_PLUGIN_VERSION_FIELD,
    WayflowDeserializationPlugin,
    WayflowSerializationPlugin,
)
from wayflowcore.serialization.serializer import (
    SerializableObject,
    autodeserialize_any_from_dict,
    autodeserialize_from_dict,
    deserialize,
    deserialize_any_from_dict,
    deserialize_from_dict,
    serialize_to_dict,
)
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import ServerTool, Tool

if TYPE_CHECKING:
    from wayflowcore.agentspec._agentspecconverter import WayflowToAgentSpecConversionContext
    from wayflowcore.agentspec._runtimeconverter import AgentSpecToWayflowConversionContext

_PLUGIN_NAME = "MyCustomToolPlugin"
_PLUGIN_VERSION = "26.1.0.alpha"


@pytest.fixture(scope="module")
def custom_tool_class():

    class MyCustomTool(Tool):

        def __init__(self, custom_attribute: str) -> None:
            self.custom_attribute = custom_attribute
            super().__init__(
                name="customtool",
                description="",
                input_descriptors=[],
                output_descriptors=[],
                id="abc123",
                __metadata_info__=None,
                requires_confirmation=False,
            )

        def _serialize_to_dict(
            self, serialization_context: "SerializationContext"
        ) -> Dict[str, Any]:
            return {"custom_attribute": self.custom_attribute}

        @classmethod
        def _deserialize_from_dict(
            cls,
            input_dict: Dict[str, Any],
            deserialization_context: "DeserializationContext",
        ) -> "SerializableObject":
            return MyCustomTool(input_dict["custom_attribute"])

    try:
        yield MyCustomTool
    finally:
        # need to manually remove it from registry so that it doesn't appear in the registry of other tests
        SerializableObject._COMPONENT_REGISTRY.pop(MyCustomTool.__name__)


class AgentSpecMyCustomTool(AgentSpecTool):
    custom_attribute: str


@pytest.fixture(scope="module")
def my_custom_tool_serialization_plugin(custom_tool_class: type) -> WayflowSerializationPlugin:

    class MyCustomToolAgentSpecSerializationPlugin(PydanticComponentSerializationPlugin):

        def __init__(self) -> None:
            super().__init__(
                component_types_and_models={"AgentSpecMyCustomTool": AgentSpecMyCustomTool}
            )

        @property
        def plugin_name(self) -> str:
            return _PLUGIN_NAME

        @property
        def plugin_version(self) -> str:
            return _PLUGIN_VERSION

    class MyCustomToolSerializationPlugin(WayflowSerializationPlugin):

        @property
        def plugin_name(self) -> str:
            return _PLUGIN_NAME

        @property
        def plugin_version(self) -> str:
            return _PLUGIN_VERSION

        @property
        def supported_component_types(self) -> List[str]:
            return ["MyCustomTool"]

        @property
        def required_agentspec_serialization_plugins(self) -> List[ComponentSerializationPlugin]:
            return [MyCustomToolAgentSpecSerializationPlugin()]

        def convert_to_agentspec(
            self,
            conversion_context: "WayflowToAgentSpecConversionContext",
            runtime_component: "SerializableObject",
            referenced_objects: Dict[str, AgentSpecComponent],
        ) -> AgentSpecComponent:
            return AgentSpecMyCustomTool(
                id=runtime_component.id,
                name=runtime_component.name,
                description=runtime_component.description,
                custom_attribute=runtime_component.custom_attribute,
            )

    return MyCustomToolSerializationPlugin()


@pytest.fixture(scope="module")
def my_custom_tool_deserialization_plugin(custom_tool_class: type) -> WayflowDeserializationPlugin:

    class MyCustomToolAgentSpecDeserializationPlugin(PydanticComponentDeserializationPlugin):

        def __init__(self) -> None:
            super().__init__(
                component_types_and_models={"AgentSpecMyCustomTool": AgentSpecMyCustomTool}
            )

        @property
        def plugin_name(self) -> str:
            return _PLUGIN_NAME

        @property
        def plugin_version(self) -> str:
            return _PLUGIN_VERSION

    class MyCustomToolDeserializationPlugin(WayflowDeserializationPlugin):

        @property
        def plugin_name(self) -> str:
            return _PLUGIN_NAME

        @property
        def plugin_version(self) -> str:
            return _PLUGIN_VERSION

        @property
        def supported_component_types(self) -> List[str]:
            return ["MyCustomTool"]

        @property
        def required_agentspec_deserialization_plugins(
            self,
        ) -> List[ComponentDeserializationPlugin]:
            return [MyCustomToolAgentSpecDeserializationPlugin()]

        def convert_to_wayflow(
            self,
            conversion_context: "AgentSpecToWayflowConversionContext",
            agentspec_component: AgentSpecComponent,
            tool_registry: Dict[str, Union[ServerTool, Callable[..., Any]]],
            converted_components: Dict[str, Any],
        ) -> Any:
            return custom_tool_class(
                custom_attribute=agentspec_component.custom_attribute,
            )

    return MyCustomToolDeserializationPlugin()


@pytest.fixture
def agent(custom_tool_class: type[Tool]) -> Agent:
    return Agent(
        name="agent_with_custom_tool",
        llm=VllmModel(model_id="model-id", host_port="localhost"),
        custom_instruction="Do this task: {{task}}",
        tools=[custom_tool_class(custom_attribute="custom_value")],
    )


@pytest.fixture
def flow(custom_tool_class: type[Tool]) -> Flow:
    return Flow.from_steps(
        name="myflow",
        steps=[
            ToolExecutionStep(
                name="custom_tool_execution_step",
                tool=custom_tool_class(custom_attribute="custom_value"),
            ),
        ],
    )


def test_serialize_agent_with_custom_plugin(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
) -> None:
    serialized_component = serialize(agent, plugins=[my_custom_tool_serialization_plugin])
    assert _COMPONENT_PLUGIN_NAME_FIELD in serialized_component
    assert _COMPONENT_PLUGIN_VERSION_FIELD in serialized_component
    assert _PLUGIN_NAME in serialized_component
    assert _PLUGIN_VERSION in serialized_component
    assert custom_tool_class.__name__ in serialized_component
    assert "custom_value" in serialized_component


def test_serialize_flow_with_custom_plugin(
    custom_tool_class: type[Tool],
    flow: Flow,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
) -> None:
    serialized_component = serialize(flow, plugins=[my_custom_tool_serialization_plugin])
    assert _COMPONENT_PLUGIN_NAME_FIELD in serialized_component
    assert _COMPONENT_PLUGIN_VERSION_FIELD in serialized_component
    assert _PLUGIN_NAME in serialized_component
    assert _PLUGIN_VERSION in serialized_component
    assert custom_tool_class.__name__ in serialized_component
    assert "custom_value" in serialized_component


def test_serialize_agent_with_custom_plugin_passed_in_context(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
) -> None:
    context = SerializationContext(root=agent, plugins=[my_custom_tool_serialization_plugin])
    serialized_component = serialize(agent, serialization_context=context)
    assert _PLUGIN_NAME in serialized_component
    assert _PLUGIN_VERSION in serialized_component
    assert custom_tool_class.__name__ in serialized_component
    assert "custom_value" in serialized_component


def test_serialize_to_dict_agent_with_custom_plugin(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
) -> None:
    component_dict = serialize_to_dict(agent, plugins=[my_custom_tool_serialization_plugin])
    serialized_component = str(component_dict)
    assert _PLUGIN_NAME in serialized_component
    assert _PLUGIN_VERSION in serialized_component
    assert custom_tool_class.__name__ in serialized_component
    assert "custom_value" in serialized_component


def test_serialize_to_dict_agent_with_custom_plugin_passed_in_context(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
) -> None:
    context = SerializationContext(root=agent, plugins=[my_custom_tool_serialization_plugin])
    component_dict = serialize_to_dict(agent, serialization_context=context)
    serialized_component = str(component_dict)
    assert _PLUGIN_NAME in serialized_component
    assert _PLUGIN_VERSION in serialized_component
    assert custom_tool_class.__name__ in serialized_component
    assert "custom_value" in serialized_component


def test_serialize_agent_with_custom_tool_without_plugin_warns(
    custom_tool_class: type[Tool], agent: Agent
) -> None:
    warning_match = "Found no serialization plugin to serialize the object of type `MyCustomTool`. Trying using the builtins serialization plugin instead."
    with pytest.warns(UserWarning, match=warning_match):
        _ = serialize(agent)
    with pytest.warns(UserWarning, match=warning_match):
        _ = serialize_to_dict(agent)


def test_serialize_and_deserialize_agent_with_custom_plugin(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    serialized_component = serialize(agent, plugins=[my_custom_tool_serialization_plugin])
    deserialized_component = deserialize(
        Agent, serialized_component, plugins=[my_custom_tool_deserialization_plugin]
    )
    assert isinstance(deserialized_component, Agent)
    assert len(deserialized_component.tools) == 1
    assert isinstance(deserialized_component.tools[0], custom_tool_class)
    assert deserialized_component.tools[0].custom_attribute == "custom_value"


def test_serialize_and_deserialize_flow_with_custom_plugin(
    custom_tool_class: type[Tool],
    flow: Flow,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    serialized_component = serialize(flow, plugins=[my_custom_tool_serialization_plugin])
    deserialized_component = deserialize(
        Flow, serialized_component, plugins=[my_custom_tool_deserialization_plugin]
    )
    assert isinstance(deserialized_component, Flow)
    assert "custom_tool_execution_step" in deserialized_component.steps
    tool_execution_step = cast(
        ToolExecutionStep, deserialized_component.steps["custom_tool_execution_step"]
    )
    assert isinstance(tool_execution_step.tool, custom_tool_class)
    assert tool_execution_step.tool.custom_attribute == "custom_value"


def test_serialize_and_deserialize_from_dict_agent_with_custom_plugin(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    serialized_component = serialize_to_dict(agent, plugins=[my_custom_tool_serialization_plugin])
    deserialized_component = deserialize_from_dict(
        Agent, serialized_component, plugins=[my_custom_tool_deserialization_plugin]
    )
    assert isinstance(deserialized_component, Agent)
    assert len(deserialized_component.tools) == 1
    assert isinstance(deserialized_component.tools[0], custom_tool_class)
    assert deserialized_component.tools[0].custom_attribute == "custom_value"


def test_serialize_and_deserialize_any_from_dict_agent_with_custom_plugin(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    serialized_component = serialize_to_dict(agent, plugins=[my_custom_tool_serialization_plugin])
    deserialization_context = DeserializationContext(
        plugins=[my_custom_tool_deserialization_plugin]
    )
    deserialized_component = deserialize_any_from_dict(
        serialized_component, Agent, deserialization_context=deserialization_context
    )
    assert isinstance(deserialized_component, Agent)
    assert len(deserialized_component.tools) == 1
    assert isinstance(deserialized_component.tools[0], custom_tool_class)
    assert deserialized_component.tools[0].custom_attribute == "custom_value"


def test_serialize_and_autodeserialize_agent_with_custom_plugin(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    serialized_component = serialize(agent, plugins=[my_custom_tool_serialization_plugin])
    deserialized_component = autodeserialize(
        serialized_component, plugins=[my_custom_tool_deserialization_plugin]
    )
    assert isinstance(deserialized_component, Agent)
    assert len(deserialized_component.tools) == 1
    assert isinstance(deserialized_component.tools[0], custom_tool_class)
    assert deserialized_component.tools[0].custom_attribute == "custom_value"


def test_serialize_and_autodeserialize_agent_with_custom_plugin_in_context(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    serialized_component = serialize(agent, plugins=[my_custom_tool_serialization_plugin])
    deserialization_context = DeserializationContext(
        plugins=[my_custom_tool_deserialization_plugin]
    )
    deserialized_component = autodeserialize(
        serialized_component, deserialization_context=deserialization_context
    )
    assert isinstance(deserialized_component, Agent)
    assert len(deserialized_component.tools) == 1
    assert isinstance(deserialized_component.tools[0], custom_tool_class)
    assert deserialized_component.tools[0].custom_attribute == "custom_value"


def test_serialize_and_autodeserialize_from_dict_agent_with_custom_plugin(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    serialized_component = serialize_to_dict(agent, plugins=[my_custom_tool_serialization_plugin])
    deserialization_context = DeserializationContext(
        plugins=[my_custom_tool_deserialization_plugin]
    )
    deserialized_component = autodeserialize_from_dict(
        serialized_component, deserialization_context=deserialization_context
    )
    assert isinstance(deserialized_component, Agent)
    assert len(deserialized_component.tools) == 1
    assert isinstance(deserialized_component.tools[0], custom_tool_class)
    assert deserialized_component.tools[0].custom_attribute == "custom_value"


def test_serialize_and_autodeserialize_any_from_dict_agent_with_custom_plugin(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    serialized_component = serialize_to_dict(agent, plugins=[my_custom_tool_serialization_plugin])
    deserialization_context = DeserializationContext(
        plugins=[my_custom_tool_deserialization_plugin]
    )
    deserialized_component = autodeserialize_any_from_dict(
        serialized_component, deserialization_context=deserialization_context
    )
    assert isinstance(deserialized_component, Agent)
    assert len(deserialized_component.tools) == 1
    assert isinstance(deserialized_component.tools[0], custom_tool_class)
    assert deserialized_component.tools[0].custom_attribute == "custom_value"


def test_deserialize_agent_with_wrong_plugin_name_raises(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    serialized_component = serialize(agent, plugins=[my_custom_tool_serialization_plugin])
    serialized_component = serialized_component.replace(_PLUGIN_NAME, "WrongPluginName")
    with pytest.raises(
        ValueError,
        match="Invalid plugin name: expected `MyCustomToolPlugin` but found `WrongPluginName`.",
    ):
        _ = deserialize(
            Agent, serialized_component, plugins=[my_custom_tool_deserialization_plugin]
        )


def test_deserialize_agent_with_no_plugin_name_raises(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    serialized_component = serialize(agent, plugins=[my_custom_tool_serialization_plugin])
    serialized_component = re.sub(
        r"[ ]+" + f"{_COMPONENT_PLUGIN_NAME_FIELD}: {_PLUGIN_NAME}\n", "", serialized_component
    )
    with pytest.raises(
        ValueError, match="Invalid plugin name: expected `MyCustomToolPlugin` but found `None`."
    ):
        _ = deserialize(
            Agent, serialized_component, plugins=[my_custom_tool_deserialization_plugin]
        )


def test_deserialize_agent_with_no_plugin_version_raises(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    serialized_component = serialize(agent, plugins=[my_custom_tool_serialization_plugin])
    serialized_component = re.sub(
        r"[ ]+" + f"{_COMPONENT_PLUGIN_VERSION_FIELD}: {_PLUGIN_VERSION}\n",
        "",
        serialized_component,
    )
    with pytest.raises(ValueError, match="Plugin version not found."):
        _ = deserialize(
            Agent, serialized_component, plugins=[my_custom_tool_deserialization_plugin]
        )


def test_deserialize_agent_with_older_plugin_version_warns(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    serialized_component = serialize(agent, plugins=[my_custom_tool_serialization_plugin])
    serialized_component = re.sub(
        f"{_COMPONENT_PLUGIN_VERSION_FIELD}: {_PLUGIN_VERSION}\n",
        f"{_COMPONENT_PLUGIN_VERSION_FIELD}: 99.1.0\n",
        serialized_component,
    )
    with pytest.warns(UserWarning, match="is newer than the version of the Wayflow plugin"):
        _ = deserialize(
            Agent, serialized_component, plugins=[my_custom_tool_deserialization_plugin]
        )


def test_serialize_and_deserialize_agent_with_custom_tool_without_plugin_warns(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    serialized_component = serialize(agent, plugins=[my_custom_tool_serialization_plugin])
    serialized_component_dict = serialize_to_dict(
        agent, plugins=[my_custom_tool_serialization_plugin]
    )
    warning_match = "Found no deserialization plugin to deserialize the object of type `MyCustomTool`. Trying using the builtins deserialization plugin instead"
    with pytest.warns(UserWarning, match=warning_match):
        _ = deserialize(Agent, serialized_component)
    with pytest.warns(UserWarning, match=warning_match):
        _ = deserialize_from_dict(Agent, serialized_component_dict)
    with pytest.warns(UserWarning, match=warning_match):
        _ = deserialize_any_from_dict(
            serialized_component_dict, Agent, deserialization_context=DeserializationContext()
        )
    with pytest.warns(UserWarning, match=warning_match):
        _ = autodeserialize(serialized_component)
    with pytest.warns(UserWarning, match=warning_match):
        _ = autodeserialize_from_dict(
            serialized_component_dict, deserialization_context=DeserializationContext()
        )
    with pytest.warns(UserWarning, match=warning_match):
        _ = autodeserialize_any_from_dict(
            serialized_component_dict, deserialization_context=DeserializationContext()
        )


def test_serde_with_multiple_plugins_covering_same_component_raises(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:

    class MyCustomToolSecondSerializationPlugin(my_custom_tool_serialization_plugin.__class__):

        @property
        def plugin_name(self) -> str:
            return _PLUGIN_NAME + "Second"

        @property
        def plugin_version(self) -> str:
            return _PLUGIN_VERSION + "Second"

    class MyCustomToolSecondDeserializationPlugin(my_custom_tool_deserialization_plugin.__class__):

        @property
        def plugin_name(self) -> str:
            return _PLUGIN_NAME + "Second"

        @property
        def plugin_version(self) -> str:
            return _PLUGIN_VERSION + "Second"

    with pytest.raises(
        ValueError,
        match="Two plugins, `MyCustomToolPluginSecond` and `MyCustomToolPlugin`, have component types with the same name: `MyCustomTool`",
    ):
        _ = serialize(
            agent,
            plugins=[my_custom_tool_serialization_plugin, MyCustomToolSecondSerializationPlugin()],
        )

    with pytest.raises(
        ValueError,
        match="Two plugins, `MyCustomToolPluginSecond` and `MyCustomToolPlugin`, have component types with the same name: `MyCustomTool`",
    ):
        _ = deserialize(
            Agent,
            "_component_type: Agent",
            plugins=[
                my_custom_tool_deserialization_plugin,
                MyCustomToolSecondDeserializationPlugin(),
            ],
        )


def test_custom_serde_in_plugins_works(
    custom_tool_class: type[Tool],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:

    class MyCustomToolCustomSerializationPlugin(my_custom_tool_serialization_plugin.__class__):

        def serialize(
            self, obj: "SerializableObject", serialization_context: SerializationContext
        ) -> Dict[str, Any]:
            """Serialize a component that the plugin should support."""
            return {
                _COMPONENT_PLUGIN_NAME_FIELD: self.plugin_name,
                _COMPONENT_PLUGIN_VERSION_FIELD: self.plugin_version,
                "custom_attribute": "SERIALIZED_VALUE",
            }

    class MyCustomToolCustomDeserializationPlugin(my_custom_tool_deserialization_plugin.__class__):

        def deserialize(
            self,
            obj_type: type["SerializableObject"],
            input_dict: Dict[str, Any],
            deserialization_context: "DeserializationContext",
        ) -> "SerializableObject":
            return custom_tool_class("DESERIALIZED_VALUE")

    serialized_agent = serialize(agent, plugins=[MyCustomToolCustomSerializationPlugin()])
    assert "SERIALIZED_VALUE" in serialized_agent

    deserialized_agent = deserialize(
        Agent, serialized_agent, plugins=[MyCustomToolCustomDeserializationPlugin()]
    )
    assert len(deserialized_agent.tools) == 1
    assert isinstance(deserialized_agent.tools[0], custom_tool_class)
    assert "DESERIALIZED_VALUE" == deserialized_agent.tools[0].custom_attribute


def test_agentspec_agent_serde_with_wayflow_plugins_works(
    custom_tool_class: type[WayflowSerializationPlugin],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    exporter = AgentSpecExporter(plugins=[my_custom_tool_serialization_plugin])
    serialized_component = exporter.to_yaml(agent)
    assert my_custom_tool_serialization_plugin.plugin_name in serialized_component
    assert my_custom_tool_serialization_plugin.plugin_version in serialized_component
    assert custom_tool_class.__name__ in serialized_component
    assert "custom_value" in serialized_component

    loader = AgentSpecLoader(plugins=[my_custom_tool_deserialization_plugin])
    deserialized_component = loader.load_yaml(serialized_component)
    assert isinstance(deserialized_component, Agent)
    assert len(deserialized_component.tools) == 1
    assert isinstance(deserialized_component.tools[0], custom_tool_class)
    assert deserialized_component.tools[0].custom_attribute == "custom_value"


def test_agentspec_flow_serde_with_wayflow_plugins_works(
    custom_tool_class: type[WayflowSerializationPlugin],
    flow: Flow,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
    my_custom_tool_deserialization_plugin: WayflowDeserializationPlugin,
) -> None:
    exporter = AgentSpecExporter(plugins=[my_custom_tool_serialization_plugin])
    serialized_component = exporter.to_yaml(flow)
    assert my_custom_tool_serialization_plugin.plugin_name in serialized_component
    assert my_custom_tool_serialization_plugin.plugin_version in serialized_component
    assert custom_tool_class.__name__ in serialized_component
    assert "custom_value" in serialized_component

    loader = AgentSpecLoader(plugins=[my_custom_tool_deserialization_plugin])
    deserialized_component = loader.load_yaml(serialized_component)
    assert isinstance(deserialized_component, Flow)
    assert "custom_tool_execution_step" in deserialized_component.steps
    tool_execution_step = cast(
        ToolExecutionStep, deserialized_component.steps["custom_tool_execution_step"]
    )
    assert isinstance(tool_execution_step.tool, custom_tool_class)
    assert tool_execution_step.tool.custom_attribute == "custom_value"


def test_agentspec_serde_with_custom_components_without_wayflow_plugins_raises(
    custom_tool_class: type[WayflowSerializationPlugin],
    agent: Agent,
    my_custom_tool_serialization_plugin: WayflowSerializationPlugin,
) -> None:

    with pytest.raises(
        ValueError,
        match="There is no plugin to convert the component type MyCustomTool",
    ):
        _ = AgentSpecExporter().to_yaml(agent)

    exporter = AgentSpecExporter(plugins=[my_custom_tool_serialization_plugin])
    serialized_component = exporter.to_yaml(agent)

    with pytest.raises(
        ValueError,
        match="There is no plugin to load the component type AgentSpecMyCustomTool",
    ):
        # Note that this error is triggered by pyagentspec
        _ = AgentSpecLoader().load_yaml(serialized_component)
