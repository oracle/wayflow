# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import List, Union

from pyagentspec.agent import Agent
from pyagentspec.component import ComponentWithIO
from pyagentspec.llms import LlmConfig
from pyagentspec.validation_helpers import model_validator_with_error_accumulation
from pydantic import Field, SerializeAsAny
from typing_extensions import Self

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)


class PluginManagerWorkers(ComponentWithIO):
    """
    Defines a ``ManagerWorkers`` conversaton component.
    A ``ManagerWorkers`` is a multi-agent conversational component in which a group manager agent
        assign tasks to worker agents.

    Parameters
    ----------
    group_manager:
        Can either be an LLM or an agent that is used as the group manager. If an LLM is passed, a manager agent
        will be created using that LLM.
    workers:
        List of Agents that participate in the group. There should be at least one agent in the list.
    """

    group_manager: SerializeAsAny[Union[Agent, LlmConfig]]
    workers: List[SerializeAsAny[Agent]] = Field(default_factory=list)

    @model_validator_with_error_accumulation
    def _validate_one_or_more_workers(self) -> Self:
        if len(self.workers) == 0:
            raise ValueError(
                "Cannot define a `ManagerWorkers` with no worker agent." "Use an `Agent` instead."
            )

        return self


MANAGER_WORKERS_PLUGIN_NAME = "ManagerWorkersPlugin"

managerworkers_serialization_plugin = PydanticComponentSerializationPlugin(
    name=MANAGER_WORKERS_PLUGIN_NAME,
    component_types_and_models={PluginManagerWorkers.__name__: PluginManagerWorkers},
)

managerworkers_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=MANAGER_WORKERS_PLUGIN_NAME,
    component_types_and_models={PluginManagerWorkers.__name__: PluginManagerWorkers},
)
