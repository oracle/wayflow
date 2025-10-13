# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Dict, List, Literal, Optional, Sequence, Tuple, Union, overload

from pyagentspec.component import Component as AgentSpecComponent
from pyagentspec.serialization import AgentSpecSerializer as PyAgentSpecSerializer
from pyagentspec.serialization import ComponentSerializationPlugin
from pyagentspec.serialization.types import (
    DisaggregatedComponentsConfigT as AgentSpecDisaggregatedComponentsConfigT,
)
from pyagentspec.versioning import AgentSpecVersionEnum
from typing_extensions import TypeAlias

from wayflowcore.agentspec._agentspecconverter import RuntimeToAgentSpecConverter
from wayflowcore.agentspec.components import all_serialization_plugin
from wayflowcore.component import Component as RuntimeComponent

FieldID: TypeAlias = str
RuntimeDisaggregatedComponentsConfigT: TypeAlias = Sequence[
    Union[RuntimeComponent, Tuple[RuntimeComponent, FieldID]]
]
"""Configuration list of components and fields to disaggregated upon serialization."""


class AgentSpecExporter:
    """Helper class to convert WayFlow objects to Agent Spec configurations."""

    def __init__(
        self,
        plugins: Optional[List[ComponentSerializationPlugin]] = None,
    ):
        """
        Parameters
        ----------
        plugins: List[ComponentSerializationPlugin]
            List of plugins to override existing plugins. By default, uses the latest supported plugins.
        """
        self.plugins = plugins

    def _get_all_plugins(self) -> List[ComponentSerializationPlugin]:
        # We group all plugins that are manually passed here to allow passing
        # specific plugins (e.g., plugin associated with a specific version).
        # This is possible if:
        # 1. All plugins are given a unique name
        # 2. There is a single plugin that can serialize each custom component
        all_plugins_by_name: Dict[str, ComponentSerializationPlugin] = {
            plugin_.plugin_name: plugin_ for plugin_ in all_serialization_plugin
        }
        for plugin_ in self.plugins or []:
            all_plugins_by_name[plugin_.plugin_name] = plugin_
        return list(all_plugins_by_name.values())

    @overload
    def to_json(
        self,
        runtime_component: RuntimeComponent,
    ) -> str: ...

    @overload
    def to_json(
        self,
        runtime_component: RuntimeComponent,
        agentspec_version: Optional[AgentSpecVersionEnum],
    ) -> str: ...

    @overload
    def to_json(
        self,
        runtime_component: RuntimeComponent,
        *,
        disaggregated_components: RuntimeDisaggregatedComponentsConfigT,
        export_disaggregated_components: Literal[True],
    ) -> Tuple[str, str]: ...

    @overload
    def to_json(
        self,
        runtime_component: RuntimeComponent,
        *,
        disaggregated_components: Optional[RuntimeDisaggregatedComponentsConfigT],
        export_disaggregated_components: Literal[False],
    ) -> str: ...

    @overload
    def to_json(
        self,
        runtime_component: RuntimeComponent,
        *,
        disaggregated_components: Optional[RuntimeDisaggregatedComponentsConfigT],
        export_disaggregated_components: bool,
    ) -> Union[str, Tuple[str, str]]: ...

    @overload
    def to_json(
        self,
        runtime_component: RuntimeComponent,
        agentspec_version: Optional[AgentSpecVersionEnum],
        disaggregated_components: Optional[RuntimeDisaggregatedComponentsConfigT],
        export_disaggregated_components: bool,
    ) -> Union[str, Tuple[str, str]]: ...

    def to_json(
        self,
        runtime_component: RuntimeComponent,
        agentspec_version: Optional[AgentSpecVersionEnum] = None,
        disaggregated_components: Optional[RuntimeDisaggregatedComponentsConfigT] = None,
        export_disaggregated_components: bool = False,
    ) -> Union[str, Tuple[str, str]]:
        """
        Transform the given WayFlow component into the respective Agent Spec JSON representation.

        Parameters
        ----------
        runtime_component:
            WayFlow component to serialize to an Agent Spec configuration.
        agentspec_version:
            The Agent Spec version of the component.
        disaggregated_components:
            Configuration specifying the components/fields to disaggregate upon serialization.
            Each item can be:

            - A ``Component``: to disaggregate the component using its id
            - A tuple ``(Component, str)``: to disaggregate the component using
              a custom id.

            .. note::

                Components in ``disaggregated_components`` are disaggregated
                even if ``export_disaggregated_components`` is ``False``.
        export_disaggregated_components:
            Whether to export the disaggregated components or not. Defaults to ``False``.

        Returns
        -------
        If ``export_disaggregated_components`` is ``True``:

        str
            The JSON serialization of the root component.
        str
            The JSON serialization of the disaggregated components.

        If ``export_disaggregated_components`` is ``False``:

        str
            The JSON serialization of the root component.

        Examples
        --------
        Basic serialization is done as follows.

        >>> from wayflowcore.agent import Agent
        >>> from wayflowcore.agentspec import AgentSpecExporter
        >>> from wayflowcore.models import VllmModel
        >>> from wayflowcore.tools import tool
        >>>
        >>> llm = VllmModel(
        ...     model_id="model-id",
        ...     host_port="VLLM_HOST_PORT",
        ... )
        >>> @tool
        ... def say_hello_tool() -> str:
        ...     '''This tool returns "hello"'''
        ...     return "hello"
        ...
        >>> agent = Agent(
        ...     name="Simple Agent",
        ...     llm=llm,
        ...     tools=[say_hello_tool]
        ... )
        >>> config = AgentSpecExporter().to_json(agent)

        To use component disaggregation, specify the component(s) to disaggregate
        in the ``disaggregated_components`` parameter, and ensure that
        ``export_disaggregated_components`` is set to ``True``.

        >>> main_config, disag_config = AgentSpecExporter().to_json(
        ...     agent,
        ...     disaggregated_components=[llm],
        ...     export_disaggregated_components=True
        ... )

        Finally, you can specify custom ids for the disaggregated components.

        >>> main_config, disag_config = AgentSpecExporter().to_json(
        ...     agent,
        ...     disaggregated_components=[(llm, "custom_llm_id")],
        ...     export_disaggregated_components=True
        ... )

        """
        agentspec_assistant = self.to_component(runtime_component)
        converted_disag_config = (
            self._convert_disaggregated_config(disaggregated_components)
            if disaggregated_components is not None
            else None
        )

        serializer = PyAgentSpecSerializer(plugins=self._get_all_plugins())
        return serializer.to_json(
            agentspec_assistant,
            agentspec_version=agentspec_version,
            disaggregated_components=converted_disag_config,
            export_disaggregated_components=export_disaggregated_components,
        )

    @overload
    def to_yaml(
        self,
        runtime_component: RuntimeComponent,
    ) -> str: ...

    @overload
    def to_yaml(
        self,
        runtime_component: RuntimeComponent,
        agentspec_version: Optional[AgentSpecVersionEnum],
    ) -> str: ...

    @overload
    def to_yaml(
        self,
        runtime_component: RuntimeComponent,
        *,
        disaggregated_components: RuntimeDisaggregatedComponentsConfigT,
        export_disaggregated_components: Literal[True],
    ) -> Tuple[str, str]: ...

    @overload
    def to_yaml(
        self,
        runtime_component: RuntimeComponent,
        *,
        disaggregated_components: Optional[RuntimeDisaggregatedComponentsConfigT],
        export_disaggregated_components: Literal[False],
    ) -> str: ...

    @overload
    def to_yaml(
        self,
        runtime_component: RuntimeComponent,
        *,
        disaggregated_components: Optional[RuntimeDisaggregatedComponentsConfigT],
        export_disaggregated_components: bool,
    ) -> Union[str, Tuple[str, str]]: ...

    @overload
    def to_yaml(
        self,
        runtime_component: RuntimeComponent,
        agentspec_version: Optional[AgentSpecVersionEnum],
        disaggregated_components: Optional[RuntimeDisaggregatedComponentsConfigT],
        export_disaggregated_components: bool,
    ) -> Union[str, Tuple[str, str]]: ...

    def to_yaml(
        self,
        runtime_component: RuntimeComponent,
        agentspec_version: Optional[AgentSpecVersionEnum] = None,
        disaggregated_components: Optional[RuntimeDisaggregatedComponentsConfigT] = None,
        export_disaggregated_components: bool = False,
    ) -> Union[str, Tuple[str, str]]:
        """
        Transform the given WayFlow component into the respective Agent Spec YAML representation.

        Parameters
        ----------
        runtime_component:
            WayFlow component to serialize to an Agent Spec configuration.
        agentspec_version:
            The Agent Spec version of the component.
        disaggregated_components:
            Configuration specifying the components/fields to disaggregate upon serialization.
            Each item can be:

            - A ``Component``: to disaggregate the component using its id
            - A tuple ``(Component, str)``: to disaggregate the component using
              a custom id.

            .. note::

                Components in ``disaggregated_components`` are disaggregated
                even if ``export_disaggregated_components`` is ``False``.
        export_disaggregated_components:
            Whether to export the disaggregated components or not. Defaults to ``False``.

        Returns
        -------
        If ``export_disaggregated_components`` is ``True``:

        str
            The YAML serialization of the root component.
        str
            The YAML serialization of the disaggregated components.

        If ``export_disaggregated_components`` is ``False``:

        str
            The YAML serialization of the root component.

        Examples
        --------
        Basic serialization is done as follows.

        >>> from wayflowcore.agent import Agent
        >>> from wayflowcore.agentspec import AgentSpecExporter
        >>> from wayflowcore.models import VllmModel
        >>> from wayflowcore.tools import tool
        >>>
        >>> llm = VllmModel(
        ...     model_id="model-id",
        ...     host_port="VLLM_HOST_PORT",
        ... )
        >>> @tool
        ... def say_hello_tool() -> str:
        ...     '''This tool returns "hello"'''
        ...     return "hello"
        ...
        >>> agent = Agent(
        ...     name="Simple Agent",
        ...     llm=llm,
        ...     tools=[say_hello_tool]
        ... )
        >>> config = AgentSpecExporter().to_yaml(agent)

        To use component disaggregation, specify the component(s) to disaggregate
        in the ``disaggregated_components`` parameter, and ensure that
        ``export_disaggregated_components`` is set to ``True``.

        >>> main_config, disag_config = AgentSpecExporter().to_yaml(
        ...     agent,
        ...     disaggregated_components=[llm],
        ...     export_disaggregated_components=True
        ... )

        Finally, you can specify custom ids for the disaggregated components.

        >>> main_config, disag_config = AgentSpecExporter().to_yaml(
        ...     agent,
        ...     disaggregated_components=[(llm, "custom_llm_id")],
        ...     export_disaggregated_components=True
        ... )

        """
        agentspec_assistant = self.to_component(runtime_component)
        converted_disag_config = (
            self._convert_disaggregated_config(disaggregated_components)
            if disaggregated_components is not None
            else None
        )

        serializer = PyAgentSpecSerializer(plugins=self._get_all_plugins())
        return serializer.to_yaml(
            agentspec_assistant,
            agentspec_version=agentspec_version,
            disaggregated_components=converted_disag_config,
            export_disaggregated_components=export_disaggregated_components,
        )

    def _convert_disaggregated_config(
        self, runtime_disag_config: RuntimeDisaggregatedComponentsConfigT
    ) -> AgentSpecDisaggregatedComponentsConfigT:
        return [  # type: ignore
            (agentspec_component, custom_id) if is_pair else agentspec_component  # type: ignore
            for disag_config in runtime_disag_config
            for is_pair in (isinstance(disag_config, tuple),)
            for runtime_component, custom_id in (
                (disag_config if is_pair else (disag_config, None)),
            )
            for agentspec_component in (self.to_component(runtime_component),)  # type: ignore
        ]

    def to_component(self, runtime_component: RuntimeComponent) -> AgentSpecComponent:
        """
        Transform the given WayFlow component into the respective PyAgentSpec Component.

        Parameters
        ----------

        runtime_component:
            WayFlow Component to serialize to a corresponding PyAgentSpec Component.
        """
        if not isinstance(runtime_component, RuntimeComponent):
            raise TypeError(
                f"Expected an Agent or a Flow, but got '{type(runtime_component)}' instead"
            )
        return RuntimeToAgentSpecConverter().convert(runtime_component)
