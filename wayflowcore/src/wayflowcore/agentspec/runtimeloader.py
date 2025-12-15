# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import warnings
from typing import Any, Callable, Dict, List, Literal, Mapping, Optional, Tuple, Union, overload

from pyagentspec.component import Component as AgentSpecComponent
from pyagentspec.serialization import AgentSpecDeserializer, ComponentDeserializationPlugin
from pyagentspec.serialization.types import ComponentsRegistryT as AgentSpecComponentsRegistryT
from typing_extensions import TypeAlias

from wayflowcore.component import Component as RuntimeComponent
from wayflowcore.serialization.plugins import WayflowDeserializationPlugin
from wayflowcore.tools import ServerTool as RuntimeServerTool

FieldName: TypeAlias = str
RuntimeComponentsRegistryT: TypeAlias = Mapping[
    str, Union[RuntimeComponent, Tuple[RuntimeComponent, FieldName]]
]


class AgentSpecLoader:
    """Helper class to convert Agent Spec configurations to WayFlow objects."""

    def __init__(
        self,
        tool_registry: Optional[Dict[str, Union[RuntimeServerTool, Callable[..., Any]]]] = None,
        plugins: Optional[
            List[Union[WayflowDeserializationPlugin, ComponentDeserializationPlugin]]
        ] = None,
    ):
        """
        Parameters
        ----------

        tool_registry:
            Optional dictionary to enable converting/loading assistant configurations involving the
            use of tools. Keys must be the tool names as specified in the serialized configuration, and
            the values are the ServerTool objects or callables that will be used to create ServerTools.
        plugins:
            List of additional wayflow plugins to use. By default, uses the latest supported builtin plugins only.

            .. note:

              Passing a list of ``ComponentDeserializationPlugin`` from ``pyagentspec`` is deprecated
              since wayflowcore==26.1.0.

        """
        self.tool_registry = tool_registry or {}
        self.plugins: List[WayflowDeserializationPlugin] = (
            [plugin for plugin in plugins if isinstance(plugin, WayflowDeserializationPlugin)]
            if plugins
            else []
        )

        from wayflowcore.serialization._builtins_deserialization_plugin import (
            WayflowBuiltinsDeserializationPlugin,
        )

        # If none of the given plugins is the builtins one, we automatically add it
        if not any(
            isinstance(plugin, WayflowBuiltinsDeserializationPlugin) for plugin in self.plugins
        ):
            self.plugins.append(WayflowBuiltinsDeserializationPlugin())

        self.agentspec_plugins: List[ComponentDeserializationPlugin] = (
            [plugin for plugin in plugins if isinstance(plugin, ComponentDeserializationPlugin)]
            if plugins
            else []
        )
        if self.agentspec_plugins:
            warnings.warn(
                "Passing plugins of type `ComponentDeserializationPlugin` is deprecated since wayflowcore==26.1.0. "
                "Please pass only plugins of type `WayflowDeserializationPlugin` instead.",
                DeprecationWarning,
            )

    def _get_all_plugins(self) -> List[WayflowDeserializationPlugin]:
        # We group all plugins that are manually passed here to allow passing
        # specific plugins (e.g., plugin associated with a specific version).
        # This is possible if:
        # 1. All plugins are given a unique name
        # 2. There is a single plugin that can deserialize each custom component
        all_plugins_by_name: Dict[str, WayflowDeserializationPlugin] = {
            plugin_.plugin_name: plugin_ for plugin_ in self.plugins
        }
        return list(all_plugins_by_name.values())

    def _get_all_agentspec_plugins(self) -> List[ComponentDeserializationPlugin]:
        # We group all plugins that are manually passed here to allow passing
        # specific plugins (e.g., plugin associated with a specific version).
        # This is possible if:
        # 1. All plugins are given a unique name
        # 2. There is a single plugin that can deserialize each custom component
        all_plugins_by_name: Dict[str, ComponentDeserializationPlugin] = {
            agentspec_plugin.plugin_name: agentspec_plugin
            for plugin_ in self._get_all_plugins()
            for agentspec_plugin in plugin_.required_agentspec_deserialization_plugins
        }
        for agentspec_plugin in self.agentspec_plugins:
            all_plugins_by_name[agentspec_plugin.plugin_name] = agentspec_plugin
        return list(all_plugins_by_name.values())

    @overload
    def load_json(self, serialized_assistant: str) -> RuntimeComponent: ...

    @overload
    def load_json(
        self,
        serialized_assistant: str,
        components_registry: Optional[RuntimeComponentsRegistryT],
    ) -> RuntimeComponent: ...

    @overload
    def load_json(
        self,
        serialized_assistant: str,
        *,
        import_only_referenced_components: Literal[False],
    ) -> RuntimeComponent: ...

    @overload
    def load_json(
        self,
        serialized_assistant: str,
        *,
        import_only_referenced_components: Literal[True],
    ) -> Dict[str, RuntimeComponent]: ...

    @overload
    def load_json(
        self,
        serialized_assistant: str,
        *,
        import_only_referenced_components: bool,
    ) -> Union[RuntimeComponent, Dict[str, RuntimeComponent]]: ...

    @overload
    def load_json(
        self,
        serialized_assistant: str,
        components_registry: Optional[RuntimeComponentsRegistryT],
        import_only_referenced_components: Literal[False],
    ) -> RuntimeComponent: ...

    @overload
    def load_json(
        self,
        serialized_assistant: str,
        components_registry: Optional[RuntimeComponentsRegistryT],
        import_only_referenced_components: Literal[True],
    ) -> Dict[str, RuntimeComponent]: ...

    @overload
    def load_json(
        self,
        serialized_assistant: str,
        components_registry: Optional[RuntimeComponentsRegistryT],
        import_only_referenced_components: bool,
    ) -> Union[RuntimeComponent, Dict[str, RuntimeComponent]]: ...

    def load_json(
        self,
        serialized_assistant: str,
        components_registry: Optional[RuntimeComponentsRegistryT] = None,
        import_only_referenced_components: bool = False,
    ) -> Union[RuntimeComponent, Dict[str, RuntimeComponent]]:
        """
        Transform the given Agent Spec JSON representation into the respective WayFlow Component

        Parameters
        ----------
        serialized_assistant:
            Serialized Agent Spec configuration to be converted to a WayFlow Component.
        components_registry:
            A dictionary of loaded WayFlow components to use when deserializing the
            main component.
        import_only_referenced_components:
            When ``True``, loads the referenced/disaggregated components
            into a dictionary to be used as the ``components_registry``
            when deserializing the main component. Otherwise, loads the
            main component. Defaults to ``False``

        Returns
        -------
        If ``import_only_referenced_components`` is ``False``

        Component
            The deserialized component.

        If ``import_only_referenced_components`` is ``False``

        Dict[str, Component]
            A dictionary containing the loaded referenced components.

        Examples
        --------
        Basic deserialization is done as follows. First, serialize a component (here an ``Agent``).

        >>> from wayflowcore.agent import Agent
        >>> from wayflowcore.agentspec import AgentSpecExporter
        >>> from wayflowcore.models import VllmModel
        >>> from wayflowcore.tools import tool
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

        Then deserialize using the ``AgentSpecLoader``.

        >>> from wayflowcore.agentspec import AgentSpecLoader
        >>> TOOL_REGISTRY = {"say_hello_tool": say_hello_tool}
        >>> loader = AgentSpecLoader(tool_registry=TOOL_REGISTRY)
        >>> deser_agent = loader.load_json(config)

        When using disaggregated components, the deserialization must be done
        in several phases, as follows.

        >>> main_config, disag_config = AgentSpecExporter().to_json(
        ...     agent,
        ...     disaggregated_components=[(llm, "custom_llm_id")],
        ...     export_disaggregated_components=True
        ... )
        >>> TOOL_REGISTRY = {"say_hello_tool": say_hello_tool}
        >>> loader = AgentSpecLoader(tool_registry=TOOL_REGISTRY)
        >>> disag_components = loader.load_json(
        ...     disag_config, import_only_referenced_components=True
        ... )
        >>> deser_agent = loader.load_json(
        ...     main_config,
        ...     components_registry=disag_components
        ... )

        """
        deserializer = AgentSpecDeserializer(plugins=self._get_all_agentspec_plugins())
        converted_registry = (
            self._convert_component_registry(components_registry)
            if components_registry is not None
            else None
        )
        if import_only_referenced_components:
            # Loading the disaggregated components
            agentspec_referenced_components = deserializer.from_json(
                serialized_assistant,
                components_registry=converted_registry,
                import_only_referenced_components=True,
            )
            # Agent Spec component with wayflow component
            # Currently plugins can be used to perform Serialization/Deserialization between AgentSpec YAML/JSON representations
            # and the pyagentspec Components (native or custom), but does not support passing the logic to handle the conversion
            # between pyagentspec and wayflowcore components (this logic is currently hardcoded in the pyagentspec<>wayflowcore
            # conversion layers).
            # As a consequence we currently do not support passing user-defined plugins.

            return {
                component_id: self.load_component(agentspec_component_)
                for component_id, agentspec_component_ in agentspec_referenced_components.items()
            }

        # Else, loading the Main Component
        agentspec_assistant = deserializer.from_json(
            serialized_assistant,
            components_registry=converted_registry,
            import_only_referenced_components=False,
        )
        return self.load_component(agentspec_assistant)

    @overload
    def load_yaml(self, serialized_assistant: str) -> RuntimeComponent: ...

    @overload
    def load_yaml(
        self,
        serialized_assistant: str,
        components_registry: Optional[RuntimeComponentsRegistryT],
    ) -> RuntimeComponent: ...

    @overload
    def load_yaml(
        self,
        serialized_assistant: str,
        *,
        import_only_referenced_components: Literal[False],
    ) -> RuntimeComponent: ...

    @overload
    def load_yaml(
        self,
        serialized_assistant: str,
        *,
        import_only_referenced_components: Literal[True],
    ) -> Dict[str, RuntimeComponent]: ...

    @overload
    def load_yaml(
        self,
        serialized_assistant: str,
        *,
        import_only_referenced_components: bool,
    ) -> Union[RuntimeComponent, Dict[str, RuntimeComponent]]: ...

    @overload
    def load_yaml(
        self,
        serialized_assistant: str,
        components_registry: Optional[RuntimeComponentsRegistryT],
        import_only_referenced_components: Literal[False],
    ) -> RuntimeComponent: ...

    @overload
    def load_yaml(
        self,
        serialized_assistant: str,
        components_registry: Optional[RuntimeComponentsRegistryT],
        import_only_referenced_components: Literal[True],
    ) -> Dict[str, RuntimeComponent]: ...

    @overload
    def load_yaml(
        self,
        serialized_assistant: str,
        components_registry: Optional[RuntimeComponentsRegistryT],
        import_only_referenced_components: bool,
    ) -> Union[RuntimeComponent, Dict[str, RuntimeComponent]]: ...

    def load_yaml(
        self,
        serialized_assistant: str,
        components_registry: Optional[RuntimeComponentsRegistryT] = None,
        import_only_referenced_components: bool = False,
    ) -> Union[RuntimeComponent, Dict[str, RuntimeComponent]]:
        """
        Transform the given Agent Spec YAML representation into the respective WayFlow Component

        Parameters
        ----------
        serialized_assistant:
            Serialized Agent Spec configuration to be converted to a WayFlow Component.
        components_registry:
            A dictionary of loaded WayFlow components to use when deserializing the
            main component.
        import_only_referenced_components:
            When ``True``, loads the referenced/disaggregated components
            into a dictionary to be used as the ``components_registry``
            when deserializing the main component. Otherwise, loads the
            main component. Defaults to ``False``

        Returns
        -------
        If ``import_only_referenced_components`` is ``False``

        Component
            The deserialized component.

        If ``import_only_referenced_components`` is ``False``

        Dict[str, Component]
            A dictionary containing the loaded referenced components.

        Examples
        --------
        Basic deserialization is done as follows. First, serialize a component (here an ``Agent``).

        >>> from wayflowcore.agent import Agent
        >>> from wayflowcore.agentspec import AgentSpecExporter
        >>> from wayflowcore.models import VllmModel
        >>> from wayflowcore.tools import tool
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

        Then deserialize using the ``AgentSpecLoader``.

        >>> from wayflowcore.agentspec import AgentSpecLoader
        >>> TOOL_REGISTRY = {"say_hello_tool": say_hello_tool}
        >>> loader = AgentSpecLoader(tool_registry=TOOL_REGISTRY)
        >>> deser_agent = loader.load_yaml(config)

        When using disaggregated components, the deserialization must be done
        in several phases, as follows.

        >>> main_config, disag_config = AgentSpecExporter().to_yaml(
        ...     agent,
        ...     disaggregated_components=[(llm, "custom_llm_id")],
        ...     export_disaggregated_components=True
        ... )
        >>> TOOL_REGISTRY = {"say_hello_tool": say_hello_tool}
        >>> loader = AgentSpecLoader(tool_registry=TOOL_REGISTRY)
        >>> disag_components = loader.load_yaml(
        ...     disag_config, import_only_referenced_components=True
        ... )
        >>> deser_agent = loader.load_yaml(
        ...     main_config,
        ...     components_registry=disag_components
        ... )

        """
        deserializer = AgentSpecDeserializer(plugins=self._get_all_agentspec_plugins())
        converted_registry = (
            self._convert_component_registry(components_registry)
            if components_registry is not None
            else None
        )

        if import_only_referenced_components:
            # Loading the disaggregated components
            agentspec_referenced_components = deserializer.from_yaml(
                serialized_assistant,
                components_registry=converted_registry,
                import_only_referenced_components=True,
            )
            # Agent Spec component with wayflow component
            # Currently plugins can be used to perform Serialization/Deserialization between AgentSpec YAML/JSON representations
            # and the pyagentspec Components (native or custom), but does not support passing the logic to handle the conversion
            # between pyagentspec and wayflowcore components (this logic is currently hardcoded in the pyagentspec<>wayflowcore
            # conversion layers).
            # As a consequence we currently do not support passing user-defined plugins.

            return {
                component_id: self.load_component(agentspec_component_)
                for component_id, agentspec_component_ in agentspec_referenced_components.items()
            }

        # Else, loading the Main Component
        agentspec_assistant = deserializer.from_yaml(
            serialized_assistant,
            components_registry=converted_registry,
            import_only_referenced_components=False,
        )
        return self.load_component(agentspec_assistant)

    def _convert_component_registry(
        self,
        runtime_component_registry: RuntimeComponentsRegistryT,
    ) -> AgentSpecComponentsRegistryT:
        from wayflowcore.agentspec import AgentSpecExporter

        exporter = AgentSpecExporter()
        return {
            custom_id: exporter.to_component(runtime_component)
            for custom_id, runtime_component in runtime_component_registry.items()
            if not isinstance(runtime_component, tuple)
        }

    def load_component(self, agentspec_component: AgentSpecComponent) -> RuntimeComponent:
        """
        Transform the given PyAgentSpec Component into the respective WayFlow Component

        Parameters
        ----------

        agentspec_component:
            PyAgentSpec Component to be converted to a WayFlow Component.
        """
        from wayflowcore.agentspec._runtimeconverter import AgentSpecToWayflowConversionContext

        runtime_assistant = AgentSpecToWayflowConversionContext(plugins=self.plugins).convert(
            agentspec_component, self.tool_registry
        )
        if not isinstance(runtime_assistant, RuntimeComponent):
            raise TypeError(
                f"Expected an Agent or a Flow, but got '{type(runtime_assistant)}' instead"
            )
        return runtime_assistant
