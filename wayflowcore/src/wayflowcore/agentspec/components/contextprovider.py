# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, List, Optional

from pyagentspec.flows.flow import Flow
from pyagentspec.flows.node import Node
from pyagentspec.tools import ServerTool
from pyagentspec.validation_helpers import model_validator_with_error_accumulation
from pydantic import SerializeAsAny
from typing_extensions import Self

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)


class PluginContextProvider(Node):
    """Context providers are callable components that are used to provide dynamic contextual information to
    WayFlow assistants. They are useful to connect external datasources to an assistant."""

    @model_validator_with_error_accumulation
    def _validate_no_inputs(self) -> Self:
        if self.inputs:
            raise ValueError(
                f"Context providers should not have any inputs, but got: {self.inputs}"
            )
        return self


class PluginConstantContextProvider(PluginContextProvider):
    """Context provider that returns a constant value"""

    value: Any
    """The value that this context provider should always return"""


class PluginToolContextProvider(PluginContextProvider):
    """Context provider that returns the output of a Server Tool"""

    tool: SerializeAsAny[ServerTool]
    """Server tool to execute to get the context provider value"""
    output_name: str
    """Name of the output of the context provider"""


class PluginFlowContextProvider(PluginContextProvider):
    """Context provider that uses a flow to compute some values"""

    flow: SerializeAsAny[Flow]
    """Flow to execute to get the value of the context provider"""
    output_names: Optional[List[str]] = None
    """Names of the flow outputs to return"""


CONTEXTPROVIDER_PLUGIN_NAME = "ContextProviderPlugin"

contextprovider_serialization_plugin = PydanticComponentSerializationPlugin(
    name=CONTEXTPROVIDER_PLUGIN_NAME,
    component_types_and_models={
        PluginConstantContextProvider.__name__: PluginConstantContextProvider,
        PluginToolContextProvider.__name__: PluginToolContextProvider,
        PluginFlowContextProvider.__name__: PluginFlowContextProvider,
    },
)
contextprovider_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=CONTEXTPROVIDER_PLUGIN_NAME,
    component_types_and_models={
        PluginConstantContextProvider.__name__: PluginConstantContextProvider,
        PluginToolContextProvider.__name__: PluginToolContextProvider,
        PluginFlowContextProvider.__name__: PluginFlowContextProvider,
    },
)
