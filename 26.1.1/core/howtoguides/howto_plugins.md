<a id="top-howtoplugins"></a>

# How to Create New WayFlow Components![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[WayFlow plugins how-to script](../end_to_end_code_examples/howto_plugins.py)

#### Prerequisites
This guide assumes familiarity with:

- [LLM configuration](llm_from_different_providers.md)
- [Using agents](agents.md)

WayFlow Plugins are the expected mean that users can use to introduce new concepts and components, or extensions to existing ones,
such that they can be integrated seamlessly into the serialization, deserialization, and Agent Spec conversion processes
of WayFlow.

In this guide, you will learn how to build a WayFlow plugin to introduce a new custom component in WayFlow, and make sure
that it can be serialized, deserialized, and converted to Agent Spec.

You are going to build a specialized [ServerTool](../api/tools.md#servertool) that reads the content of a file given its path.
Then we are going to use this tool as part of an [Agent](../api/agent.md#agent), build the plugins, and show how to use them
for WayFlow’s serialization and Agent Spec conversion.

## Basic usage

As first step, we build our new tool extension. We call it `ReadFileTool`, and we give it an attribute
to specify which file extensions are allowed to be read. The tool implementation in this example is mocked,
and it just returns the content of two predefined filepaths.

```python
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

```

In this example we extended `Tool`, but a new component that does not inherit from existing concepts can be created,
and it can be connected to the serialization mechanism by simply extending the `SerializableObject` interface.
Note that there are also extensions of the `SerializableObject` class, like the `SerializableDataclass`,
which offers basic serialization implementation for `dataclass` annotated classes.

We can now build our agent: we select the LLM we want to use to orchestrate it, write custom instructions to
inform it about which files are available, and give it instructions to read them if needed.

```python
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
```

As already mentioned at the beginning of this guide, WayFlow plugins take also care of the Agent Spec conversion.
Therefore, in order to create complete WayFlow plugins, we have to create the new tool also in Agent Spec.
To do that, we extend the `ServerTool` implementation from `pyagentspec` and we add the `allowed_extensions` attribute.
Then we create the Agent Spec plugins that will take care of the serialization/deserialization to/from Agent Spec.

```python
from typing import Optional
from pydantic import Field
from pyagentspec.tools import ServerTool as AgentSpecServerTool

class AgentSpecReadFileTool(AgentSpecServerTool):
    allowed_extensions: Optional[list[str]] = Field(default_factory=lambda: [".txt"])

from pyagentspec.serialization.pydanticserializationplugin import PydanticComponentSerializationPlugin
from pyagentspec.serialization.pydanticdeserializationplugin import PydanticComponentDeserializationPlugin

agentspec_read_file_tool_serialization_plugin = PydanticComponentSerializationPlugin({"AgentSpecReadFileTool": AgentSpecReadFileTool})
agentspec_read_file_tool_deserialization_plugin = PydanticComponentDeserializationPlugin({"AgentSpecReadFileTool": AgentSpecReadFileTool})
```

Now that the Agent Spec plugins are ready, we can use them in our WayFlow plugins for the ReadFileTool.
We build the [WayflowSerializationPlugin](../api/serialization.md#wayflowserializationplugin) and the [WayflowDeserializationPlugin](../api/serialization.md#wayflowdeserializationplugin)
by specifying a plugin name, a version, the Agent Spec plugins (if any) that are required to serialize and deserialize
the new Tool, and implement the conversion logic for it.

```python
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
```

Now that we have built the plugins, we can use them in serialization and deserialization.

```python
from wayflowcore.serialization.serializer import serialize, autodeserialize

serialized_assistant = serialize(assistant, plugins=[WayflowReadFileToolSerializationPlugin()])
deserialized_assistant = autodeserialize(serialized_assistant, plugins=[WayflowReadFileToolDeserializationPlugin()])
```

Finally, we can try to run our agent and ask it some information contained in a file.

```python
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
```

## Agent Spec Exporting/Loading

You can export the assistant configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter(plugins=[WayflowReadFileToolSerializationPlugin()]).to_json(assistant)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "ExtendedAgent",
  "id": "9602dfd1-77aa-42c7-8ebb-097cbdf6eb29",
  "name": "agent_ed163a03__auto",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [],
  "outputs": [],
  "llm_config": {
    "component_type": "VllmConfig",
    "id": "c1cc758f-c022-4c9c-88d4-ac6cc027a897",
    "name": "llm_2609a7b7__auto",
    "description": null,
    "metadata": {
      "__metadata_info__": {}
    },
    "default_generation_parameters": null,
    "url": "MODEL-URL",
    "model_id": "MODEL-ID"
  },
  "system_prompt": "\nYou have the following files available:\n- movies.txt\n- videogames.txt\n\nRead the content of the right file - based on the user query - with the tool, and answer the user.\n",
  "tools": [
    {
      "component_type": "AgentSpecReadFileTool",
      "id": "f1097ec5-343d-434a-b599-39b8c8ec9c76",
      "name": "read_file_tool",
      "description": "Read the content of a file",
      "metadata": {},
      "inputs": [
        {
          "type": "string",
          "title": "file_path"
        }
      ],
      "outputs": [
        {
          "type": "string",
          "title": "file_content"
        }
      ],
      "allowed_extensions": [
        ".txt"
      ],
      "component_plugin_name": "PydanticComponentPlugin",
      "component_plugin_version": "26.1.0.dev0"
    }
  ],
  "toolboxes": [],
  "human_in_the_loop": true,
  "context_providers": null,
  "can_finish_conversation": false,
  "raise_exceptions": false,
  "max_iterations": 10,
  "initial_message": "Hi! How can I help you?",
  "caller_input_mode": "always",
  "agents": [],
  "flows": [],
  "agent_template": {
    "component_type": "PluginPromptTemplate",
    "id": "af4f8ec3-ac2c-43fc-852b-6be2f48f55cb",
    "name": "",
    "description": null,
    "metadata": {
      "__metadata_info__": {}
    },
    "messages": [
      {
        "role": "system",
        "contents": [
          {
            "type": "text",
            "content": "{%- if __TOOLS__ -%}\nEnvironment: ipython\nCutting Knowledge Date: December 2023\n\nYou are a helpful assistant with tool calling capabilities. Only reply with a tool call if the function exists in the library provided by the user. If it doesn't exist, just reply directly in natural language. When you receive a tool call response, use the output to format an answer to the original user question.\n\nYou have access to the following functions. To call a function, please respond with JSON for a function call.\nRespond in the format {\"name\": function name, \"parameters\": dictionary of argument name and its value}.\nDo not use variables.\n\n[{% for tool in __TOOLS__%}{{tool.to_openai_format() | tojson}}{{', ' if not loop.last}}{% endfor %}]\n{%- endif -%}\n"
          }
        ],
        "tool_requests": null,
        "tool_result": null,
        "display_only": false,
        "sender": null,
        "recipients": [],
        "time_created": "2025-11-18T18:54:31.910732+00:00",
        "time_updated": "2025-11-18T18:54:31.910732+00:00"
      },
      {
        "role": "system",
        "contents": [
          {
            "type": "text",
            "content": "{%- if custom_instruction -%}Additional instructions:\n{{custom_instruction}}{%- endif -%}"
          }
        ],
        "tool_requests": null,
        "tool_result": null,
        "display_only": false,
        "sender": null,
        "recipients": [],
        "time_created": "2025-11-18T18:54:31.910753+00:00",
        "time_updated": "2025-11-18T18:54:31.910753+00:00"
      },
      {
        "role": "system",
        "contents": [
          {
            "type": "text",
            "content": "$$__CHAT_HISTORY_PLACEHOLDER__$$"
          }
        ],
        "tool_requests": null,
        "tool_result": null,
        "display_only": false,
        "sender": null,
        "recipients": [],
        "time_created": "2025-11-18T18:54:31.908396+00:00",
        "time_updated": "2025-11-18T18:54:31.908397+00:00"
      },
      {
        "role": "system",
        "contents": [
          {
            "type": "text",
            "content": "{% if __PLAN__ %}The current plan you should follow is the following: \n{{__PLAN__}}{% endif %}"
          }
        ],
        "tool_requests": null,
        "tool_result": null,
        "display_only": false,
        "sender": null,
        "recipients": [],
        "time_created": "2025-11-18T18:54:31.910769+00:00",
        "time_updated": "2025-11-18T18:54:31.910769+00:00"
      }
    ],
    "output_parser": {
      "component_type": "PluginJsonToolOutputParser",
      "id": "9d783ae5-68db-4015-90cd-7becff0e1ad6",
      "name": "jsontool_outputparser",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "tools": null,
      "component_plugin_name": "OutputParserPlugin",
      "component_plugin_version": "26.1.0.dev0"
    },
    "inputs": [
      {
        "description": "\"__TOOLS__\" input variable for the template",
        "title": "__TOOLS__"
      },
      {
        "description": "\"custom_instruction\" input variable for the template",
        "type": "string",
        "title": "custom_instruction"
      },
      {
        "description": "\"__PLAN__\" input variable for the template",
        "type": "string",
        "title": "__PLAN__",
        "default": ""
      },
      {
        "type": "array",
        "items": {},
        "title": "__CHAT_HISTORY__"
      }
    ],
    "pre_rendering_transforms": null,
    "post_rendering_transforms": [
      {
        "component_type": "PluginRemoveEmptyNonUserMessageTransform",
        "id": "c1b5c055-4e6a-47a2-9a89-49b77132aff6",
        "name": "removeemptynonusermessage_messagetransform",
        "description": null,
        "metadata": {
          "__metadata_info__": {}
        },
        "component_plugin_name": "MessageTransformPlugin",
        "component_plugin_version": "26.1.0.dev0"
      },
      {
        "component_type": "PluginCoalesceSystemMessagesTransform",
        "id": "292f22e0-2b83-4a5c-9c99-0a9eb5d04639",
        "name": "coalescesystemmessage_messagetransform",
        "description": null,
        "metadata": {
          "__metadata_info__": {}
        },
        "component_plugin_name": "MessageTransformPlugin",
        "component_plugin_version": "26.1.0.dev0"
      },
      {
        "component_type": "PluginLlamaMergeToolRequestAndCallsTransform",
        "id": "199c50af-30f0-4d8d-a50c-86afdccaf089",
        "name": "llamamergetoolrequestandcalls_messagetransform",
        "description": null,
        "metadata": {
          "__metadata_info__": {}
        },
        "component_plugin_name": "MessageTransformPlugin",
        "component_plugin_version": "26.1.0.dev0"
      }
    ],
    "tools": null,
    "native_tool_calling": false,
    "response_format": null,
    "native_structured_generation": true,
    "generation_config": null,
    "component_plugin_name": "PromptTemplatePlugin",
    "component_plugin_version": "26.1.0.dev0"
  },
  "component_plugin_name": "AgentPlugin",
  "component_plugin_version": "26.1.0.dev0",
  "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: ExtendedAgent
id: a5b53483-10ab-48ff-bc1d-562c89ab89ab
name: agent_514df23e__auto
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs: []
llm_config:
  component_type: VllmConfig
  id: e67b1ce6-bd21-4a33-a407-8defa56c867e
  name: llm_f2262eaa__auto
  description: null
  metadata:
    __metadata_info__: {}
  default_generation_parameters: null
  url: MODEL-URL
  model_id: MODEL-ID
system_prompt: '

  You have the following files available:

  - movies.txt

  - videogames.txt


  Read the content of the right file - based on the user query - with the tool, and
  answer the user.

  '
tools:
- component_type: AgentSpecReadFileTool
  id: a8f4bd9d-ec84-4762-b063-b460cd6bd91e
  name: read_file_tool
  description: Read the content of a file
  metadata: {}
  inputs:
  - type: string
    title: file_path
  outputs:
  - type: string
    title: file_content
  allowed_extensions:
  - .txt
  component_plugin_name: PydanticComponentPlugin
  component_plugin_version: 26.1.0.dev0
toolboxes: []
human_in_the_loop: true
context_providers: null
can_finish_conversation: false
raise_exceptions: false
max_iterations: 10
initial_message: Hi! How can I help you?
caller_input_mode: always
agents: []
flows: []
agent_template:
  component_type: PluginPromptTemplate
  id: e3918256-4e22-4a94-bb73-6f530ac3a9bd
  name: ''
  description: null
  metadata:
    __metadata_info__: {}
  messages:
  - role: system
    contents:
    - type: text
      content: '{%- if __TOOLS__ -%}

        Environment: ipython

        Cutting Knowledge Date: December 2023


        You are a helpful assistant with tool calling capabilities. Only reply with
        a tool call if the function exists in the library provided by the user. If
        it doesn''t exist, just reply directly in natural language. When you receive
        a tool call response, use the output to format an answer to the original user
        question.


        You have access to the following functions. To call a function, please respond
        with JSON for a function call.

        Respond in the format {"name": function name, "parameters": dictionary of
        argument name and its value}.

        Do not use variables.


        [{% for tool in __TOOLS__%}{{tool.to_openai_format() | tojson}}{{'', '' if
        not loop.last}}{% endfor %}]

        {%- endif -%}

        '
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-11-18T18:55:16.416935+00:00'
    time_updated: '2025-11-18T18:55:16.416935+00:00'
  - role: system
    contents:
    - type: text
      content: '{%- if custom_instruction -%}Additional instructions:

        {{custom_instruction}}{%- endif -%}'
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-11-18T18:55:16.416954+00:00'
    time_updated: '2025-11-18T18:55:16.416954+00:00'
  - role: system
    contents:
    - type: text
      content: $$__CHAT_HISTORY_PLACEHOLDER__$$
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-11-18T18:55:16.414612+00:00'
    time_updated: '2025-11-18T18:55:16.414612+00:00'
  - role: system
    contents:
    - type: text
      content: "{% if __PLAN__ %}The current plan you should follow is the following:\
        \ \n{{__PLAN__}}{% endif %}"
    tool_requests: null
    tool_result: null
    display_only: false
    sender: null
    recipients: []
    time_created: '2025-11-18T18:55:16.416970+00:00'
    time_updated: '2025-11-18T18:55:16.416970+00:00'
  output_parser:
    component_type: PluginJsonToolOutputParser
    id: 58030d61-6b25-48e4-992d-556acfcbc6cd
    name: jsontool_outputparser
    description: null
    metadata:
      __metadata_info__: {}
    tools: null
    component_plugin_name: OutputParserPlugin
    component_plugin_version: 26.1.0.dev0
  inputs:
  - description: '"__TOOLS__" input variable for the template'
    title: __TOOLS__
  - description: '"custom_instruction" input variable for the template'
    type: string
    title: custom_instruction
  - description: '"__PLAN__" input variable for the template'
    type: string
    title: __PLAN__
    default: ''
  - type: array
    items: {}
    title: __CHAT_HISTORY__
  pre_rendering_transforms: null
  post_rendering_transforms:
  - component_type: PluginRemoveEmptyNonUserMessageTransform
    id: 3aef0150-1ea1-4b05-9074-92968f936306
    name: removeemptynonusermessage_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 26.1.0.dev0
  - component_type: PluginCoalesceSystemMessagesTransform
    id: edbc25ed-0543-4bf4-97cb-be4908ae8b98
    name: coalescesystemmessage_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 26.1.0.dev0
  - component_type: PluginLlamaMergeToolRequestAndCallsTransform
    id: cf79ec30-db91-4cef-92ba-e198c59e56dc
    name: llamamergetoolrequestandcalls_messagetransform
    description: null
    metadata:
      __metadata_info__: {}
    component_plugin_name: MessageTransformPlugin
    component_plugin_version: 26.1.0.dev0
  tools: null
  native_tool_calling: false
  response_format: null
  native_structured_generation: true
  generation_config: null
  component_plugin_name: PromptTemplatePlugin
  component_plugin_version: 26.1.0.dev0
component_plugin_name: AgentPlugin
component_plugin_version: 26.1.0.dev0
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

new_agent = AgentSpecLoader(plugins=[WayflowReadFileToolDeserializationPlugin()]).load_json(config)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `AgentPlugin`
- `MessageTransformPlugin`
- `PromptTemplatePlugin`
- `OutputParserPlugin`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Next steps

Now that you have learned how to build WayFlow plugins, you may proceed to
[Load and Execute an Agent Spec Configuration](howto_execute_agentspec_with_wayflowcore.md).

## Full code

Click on the card at the [top of this page](#top-howtoplugins) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Create New WayFlow Components
# ---------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_plugins.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import warnings

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.CRITICAL)


# %%[markdown]
## Create the new tool to read a file

# %%
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


# %%[markdown]
## Create the agent

# %%
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

# %%[markdown]
## Create Agent Spec components and plugins

# %%
from typing import Optional
from pydantic import Field
from pyagentspec.tools import ServerTool as AgentSpecServerTool

class AgentSpecReadFileTool(AgentSpecServerTool):
    allowed_extensions: Optional[list[str]] = Field(default_factory=lambda: [".txt"])

from pyagentspec.serialization.pydanticserializationplugin import PydanticComponentSerializationPlugin
from pyagentspec.serialization.pydanticdeserializationplugin import PydanticComponentDeserializationPlugin

agentspec_read_file_tool_serialization_plugin = PydanticComponentSerializationPlugin({"AgentSpecReadFileTool": AgentSpecReadFileTool})
agentspec_read_file_tool_deserialization_plugin = PydanticComponentDeserializationPlugin({"AgentSpecReadFileTool": AgentSpecReadFileTool})

# %%[markdown]
## Create Wayflow plugins for serialization and Agent Spec conversion

# %%
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

# %%[markdown]
## Serialize and deserialize the agent

# %%
from wayflowcore.serialization.serializer import serialize, autodeserialize

serialized_assistant = serialize(assistant, plugins=[WayflowReadFileToolSerializationPlugin()])
deserialized_assistant = autodeserialize(serialized_assistant, plugins=[WayflowReadFileToolDeserializationPlugin()])

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter(plugins=[WayflowReadFileToolSerializationPlugin()]).to_json(assistant)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

new_agent = AgentSpecLoader(plugins=[WayflowReadFileToolDeserializationPlugin()]).load_json(config)

# %%[markdown]
## Agent Execution

# %%
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
```
