# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
from typing import List, Optional

from pyagentspec import Property
from pyagentspec.flows.flow import Flow
from pyagentspec.validation_helpers import model_validator_with_error_accumulation
from pydantic import Field, SerializeAsAny
from typing_extensions import Self

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)
from wayflowcore.agentspec.components.contextprovider import PluginContextProvider


class ExtendedFlow(Flow):
    """Extension of the basic Agent Spec Flow that supports context providers"""

    context_providers: Optional[List[SerializeAsAny[PluginContextProvider]]] = None
    """List of providers that add context to specific steps."""

    state: List[Property] = Field(default_factory=list)
    """The list of properties that compose the state of the Flow"""

    @model_validator_with_error_accumulation
    def _validate_data_edges_use_existing_nodes(self) -> Self:
        # we override the default flow validation to enable also using context providers as source
        node_ids = {
            node.id
            for node in (
                getattr(self, "nodes", []) + (getattr(self, "context_providers", []) or [])
            )
        }

        for data_edge in getattr(self, "data_flow_connections", []) or []:
            if data_edge.source_node.id not in node_ids:
                raise ValueError(
                    f"A data flow edge was defined, but the flow does not contain the"
                    f" source node '{data_edge.source_node.name}'"
                )
            if data_edge.destination_node.id not in node_ids:
                raise ValueError(
                    f"A data flow edge was defined, but the flow does not contain the"
                    f" destination node '{data_edge.destination_node.name}'"
                )
        return self


FLOW_PLUGIN_NAME = "FlowPlugin"

flow_serialization_plugin = PydanticComponentSerializationPlugin(
    name=FLOW_PLUGIN_NAME, component_types_and_models={ExtendedFlow.__name__: ExtendedFlow}
)
flow_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=FLOW_PLUGIN_NAME, component_types_and_models={ExtendedFlow.__name__: ExtendedFlow}
)
