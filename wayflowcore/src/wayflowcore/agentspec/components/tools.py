# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict

from pyagentspec.component import Component
from pydantic import BaseModel

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)


class PluginToolBox(Component):
    """
    Class to expose a list of tools to agentic components.

    ToolBox is dynamic which means that agentic components equipped
    with a toolbox can may see its tools to evolve throughout its
    execution.
    """


class PluginToolRequest(BaseModel):
    name: str
    args: Dict[str, Any]
    tool_request_id: str


class PluginToolResult(BaseModel):
    content: Any
    tool_request_id: str


TOOLS_PLUGIN_NAME = "ToolPlugin"

tools_serialization_plugin = PydanticComponentSerializationPlugin(
    name=TOOLS_PLUGIN_NAME,
    component_types_and_models={
        PluginToolBox.__name__: PluginToolBox,
    },
)
tools_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=TOOLS_PLUGIN_NAME,
    component_types_and_models={
        PluginToolBox.__name__: PluginToolBox,
    },
)
