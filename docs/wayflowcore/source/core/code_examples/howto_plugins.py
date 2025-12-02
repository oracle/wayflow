# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Code Example - How to Create New WayFlow Components
import logging
import warnings

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.CRITICAL)

# .. start-##_Create_the_new_tool_to_read_a_file
from typing import Any, Callable, Dict
from wayflowcore.property import StringProperty
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.tools import ServerTool

class ReadFileTool(ServerTool):

    def __init__(self, allowed_extensions: list[str] | None = None):
        self.allowed_extensions = allowed_extensions or [".txt"]
        super().__init__(
            name="read_file_tool",
            description="Read the content of a file",
            func=self._get_read_file_function(),
            input_descriptors=[StringProperty(name="file_path")],
            output_descriptors=[StringProperty(name="file_content")],
        )

    def _get_read_file_function(self) -> Callable[[str], Any]:
        def read_file(file_path: str) -> Any:
            # We mock the implementation for this example
            if not any(file_path.endswith(allowed_extension) for allowed_extension in self.allowed_extensions):
                return "Unsupported file extension"
            return {
                "movies.txt": "According to IMDB, the best movie of all time is `The Shawshank Redemption`",
                "videogames.txt": "According to IGN, the best videogame of all time is `The Legend of Zelda: Breath of the Wild.`",
            }.get(file_path, "File not found")
        return read_file

    def _serialize_to_dict(self, serialization_context: SerializationContext) -> Dict[str, Any]:
        # We return the dictionary of all the elements that we need in order to reconstruct the same exact instance
        # once we deserialize back. The dictionary values should be only serialized attributes, it should not contain
        # instances of objects that are not serializable. Developers can use serialization methods exposed by the
        # wayflowcore.serialization.serializer module to serialize complex objects.
        return {"allowed_extensions": self.allowed_extensions}

    @classmethod
    def _deserialize_from_dict(cls, input_dict: Dict[str, Any], deserialization_context: DeserializationContext) -> SerializableObject:
        # We return an instance of this class built with the information we serialized. Developers can use deserialization
        # methods exposed by the wayflowcore.serialization.serializer module to deserialize attributes having complex classes.
        return ReadFileTool(input_dict.get("allowed_extensions", None))

# .. end-##_Create_the_new_tool_to_read_a_file
# .. start-##_Create_the_agent
from wayflowcore import Agent
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

custom_instructions = """
You have the following files available:
- movies.txt
- videogames.txt

Read the content of the right file - based on the user query - with the tool, and answer the user.
"""

assistant = Agent(
    custom_instruction=custom_instructions,
    tools=[ReadFileTool()],
    llm=llm,
)
# .. end-##_Create_the_agent
(assistant.llm,) = _update_globals(["llm_big"])  # docs-skiprow # type: ignore
# .. start-##_Create_Agent_Spec_components_and_plugins
from typing import Optional
from pydantic import Field
from pyagentspec.tools import ServerTool as AgentSpecServerTool

class AgentSpecReadFileTool(AgentSpecServerTool):
    allowed_extensions: Optional[list[str]] = Field(default_factory=lambda: [".txt"])

from pyagentspec.serialization.pydanticserializationplugin import PydanticComponentSerializationPlugin
from pyagentspec.serialization.pydanticdeserializationplugin import PydanticComponentDeserializationPlugin

agentspec_read_file_tool_serialization_plugin = PydanticComponentSerializationPlugin({"AgentSpecReadFileTool": AgentSpecReadFileTool})
agentspec_read_file_tool_deserialization_plugin = PydanticComponentDeserializationPlugin({"AgentSpecReadFileTool": AgentSpecReadFileTool})
# .. end-##_Create_Agent_Spec_components_and_plugins
# .. start-##_Create_Wayflow_plugins_for_serialization_and_Agent_Spec_conversion
from pyagentspec import Component as AgentSpecComponent
from pyagentspec.property import Property as AgentSpecProperty
from pyagentspec.serialization import ComponentSerializationPlugin, ComponentDeserializationPlugin
from wayflowcore.agentspec._agentspecconverter import WayflowToAgentSpecConversionContext
from wayflowcore.agentspec._runtimeconverter import AgentSpecToWayflowConversionContext
from wayflowcore.serialization.plugins import ToolRegistryT, WayflowSerializationPlugin, WayflowDeserializationPlugin
from wayflowcore.serialization.serializer import SerializableObject

plugin_name = "WayflowReadFileTool"
plugin_version = "1.0.0"

class WayflowReadFileToolSerializationPlugin(WayflowSerializationPlugin):

    @property
    def plugin_name(self) -> str:
        return plugin_name

    @property
    def plugin_version(self) -> str:
        return plugin_version

    @property
    def supported_component_types(self) -> list[str]:
        return ["ReadFileTool"]

    @property
    def required_agentspec_serialization_plugins(self) -> list[ComponentSerializationPlugin]:
        return [agentspec_read_file_tool_serialization_plugin]

    def convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_component: SerializableObject,
        referenced_objects: dict[str, AgentSpecComponent],
    ) -> AgentSpecComponent:
        return AgentSpecReadFileTool(
            id=runtime_component.id,
            name=runtime_component.name,
            description=runtime_component.description,
            allowed_extensions=runtime_component.allowed_extensions,
            metadata=runtime_component.__metadata_info__,
            inputs=[AgentSpecProperty(json_schema=p.to_json_schema()) for p in runtime_component.input_descriptors],
            outputs=[AgentSpecProperty(json_schema=p.to_json_schema()) for p in runtime_component.output_descriptors],
        )


class WayflowReadFileToolDeserializationPlugin(WayflowDeserializationPlugin):
    @property
    def plugin_name(self) -> str:
        return plugin_name

    @property
    def plugin_version(self) -> str:
        return plugin_version

    @property
    def supported_component_types(self) -> list[str]:
        return ["ReadFileTool"]

    @property
    def required_agentspec_deserialization_plugins(self) -> list[ComponentDeserializationPlugin]:
        return [agentspec_read_file_tool_deserialization_plugin]

    def convert_to_wayflow(
        self,
        conversion_context: "AgentSpecToWayflowConversionContext",
        agentspec_component: AgentSpecComponent,
        tool_registry: ToolRegistryT,
        converted_components: dict[str, Any],
    ) -> Any:
        return ReadFileTool(agentspec_component.allowed_extensions)
# .. end-##_Create_Wayflow_plugins_for_serialization_and_Agent_Spec_conversion
# .. start-##_Serialize_and_deserialize_the_agent
from wayflowcore.serialization.serializer import serialize, autodeserialize

serialized_assistant = serialize(assistant, plugins=[WayflowReadFileToolSerializationPlugin()])
deserialized_assistant = autodeserialize(serialized_assistant, plugins=[WayflowReadFileToolDeserializationPlugin()])
# .. end-##_Serialize_and_deserialize_the_agent
# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter(plugins=[WayflowReadFileToolSerializationPlugin()]).to_json(assistant)
# .. end-##_Export_config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

new_agent = AgentSpecLoader(plugins=[WayflowReadFileToolDeserializationPlugin()]).load_json(config)
# .. end-##_Load_Agent_Spec_config
# .. start-##_Agent_Execution
conversation = assistant.start_conversation()

status = conversation.execute()
assistant_reply = conversation.get_last_message()
print("\nAssistant >>>", assistant_reply.content)
conversation.append_user_message("What's the best movie")
status = conversation.execute()
assistant_reply = conversation.get_last_message()
print("\nAssistant >>>", assistant_reply.content)

# Example of conversation:
# Assistant >>> Hi! How can I help you?
# User >>> What's the best movie
# Assistant >>> According to IMDB, the best movie of all time is The Shawshank Redemption
# .. end-##_Agent_Execution
