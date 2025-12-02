# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from wayflowcore._metadata import METADATA_KEY, MetadataType
from wayflowcore._utils.async_helpers import run_async_in_sync, run_sync_in_thread
from wayflowcore.component import Component
from wayflowcore.conversation import Conversation
from wayflowcore.property import Property
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import (
    SerializableObject,
    autodeserialize_any_from_dict,
    serialize_any_to_dict,
)
from wayflowcore.tools import Tool

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.property import Property


# It is not recommended to write a custom ContextProvider, you should rather use
# the ToolContextProvider to maximize portability.
# If you still decide to do it, you either need to implement `__call__` for CPU-bounded
# workloads or `call_async` for IO-bounded workloads


class ContextProvider(Component, SerializableObject, ABC):
    """Context providers are callable components that are used to provide dynamic contextual information to
    WayFlow assistants. They are useful to connect external datasources to an assistant.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        id: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            id=id,
            __metadata_info__=__metadata_info__,
        )
        self._validate_single_output_description()

    def _serialize_to_dict(self, serialization_context: SerializationContext) -> Dict[str, Any]:
        from wayflowcore.contextproviders import _SUPPORTED_CONTEXT_PROVIDER_TYPES

        context_provider_types = {
            context_provider_cls: context_provider_type
            for context_provider_type, context_provider_cls in _SUPPORTED_CONTEXT_PROVIDER_TYPES.items()
        }

        if self.__class__ not in context_provider_types:
            raise ValueError(
                f"The context provider class {self.__class__.__name__} is not supported for serialization"
            )

        serialized_context_provider_dict: Dict[str, Any] = {
            "_component_type": ContextProvider.__name__,
            "context_provider_type": context_provider_types[self.__class__],
            "name": self.name,
            "id": self.id,
            "description": self.description,
        }

        context_provider_args = {}
        context_provider_config = self.get_static_configuration_descriptors()
        for config_name, config_type_descriptor in context_provider_config.items():
            if not hasattr(self, config_name):
                raise ValueError(
                    f"The ContextProvider {self.__class__.__name__} cannot be serialized "
                    f"because it has a config named {config_name} but is missing the attribute "
                    f"of the same name."
                )
            context_provider_args[config_name] = serialize_any_to_dict(
                getattr(self, config_name), serialization_context
            )

        serialized_context_provider_dict["context_provider_args"] = context_provider_args

        return serialized_context_provider_dict

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: DeserializationContext
    ) -> "SerializableObject":
        from wayflowcore.contextproviders import _SUPPORTED_CONTEXT_PROVIDER_TYPES

        context_provider_type = input_dict["context_provider_type"]
        if context_provider_type not in _SUPPORTED_CONTEXT_PROVIDER_TYPES:
            raise ValueError(
                f"The context provider type {context_provider_type} is not supported for deserialization."
                f" Supported types are: {list(_SUPPORTED_CONTEXT_PROVIDER_TYPES.keys())}"
            )
        context_provider_cls = _SUPPORTED_CONTEXT_PROVIDER_TYPES[context_provider_type]

        context_provider_arguments = {
            arg_name: autodeserialize_any_from_dict(arg_prepared_value, deserialization_context)
            for arg_name, arg_prepared_value in input_dict["context_provider_args"].items()
        }

        deserialized_context_provider = context_provider_cls(
            **context_provider_arguments,
            name=input_dict.get("name", None),
            description=input_dict.get("description", None),
            id=input_dict.get("id", None),
            __metadata_info__=context_provider_arguments.get(METADATA_KEY, None),
        )

        return deserialized_context_provider

    def _has_async_implemented(self) -> bool:
        return "call_async" in self.__class__.__dict__

    def __call__(self, conversation: "Conversation") -> Any:
        if self._has_async_implemented():
            return run_async_in_sync(self.call_async, conversation, method_name="call_async")
        raise NotImplementedError("Abstract method must be implemented")

    async def call_async(self, conversation: "Conversation") -> Any:
        """Default sync callable of the context provider"""
        return await run_sync_in_thread(self.__call__, conversation)

    @classmethod
    def get_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are the expected type.
        """
        raise NotImplementedError(
            f"The ContextProvider type {cls.__name__} does not support serialization"
        )

    def _validate_single_output_description(self) -> None:
        # TODO: to be removed
        try:
            output_descriptors = self.get_output_descriptors()
        except NotImplementedError:
            return
        if len(output_descriptors) > 1:
            raise NotImplementedError(
                "Context providers that return more than one output are not yet supported"
            )
        elif len(output_descriptors) == 0:
            raise ValueError(
                "Context provider must return something, but its list of output descriptors is empty."
            )

    @abstractmethod
    def get_output_descriptors(self) -> List["Property"]:
        raise NotImplementedError("Must be implemented by an appropriate subclass")

    @property
    def output_descriptors(self) -> List["Property"]:
        return self.get_output_descriptors()

    def _referenced_tools(self, recursive: bool = True) -> List["Tool"]:
        """
        Returns a list of all tools that are present in this component's configuration, including tools
        nested in subcomponents
        """
        visited_set: Set[str] = set()
        all_tools_dict = self._referenced_tools_dict(recursive=recursive, visited_set=visited_set)
        return list(all_tools_dict.values())

    def _referenced_tools_dict(
        self, recursive: bool = True, visited_set: Optional[Set[str]] = None
    ) -> Dict[str, "Tool"]:
        visited_set = set() if visited_set is None else visited_set

        if self.id in visited_set:
            # we are already visited, no need to return anything
            return {}

        # Mark ourself as visited to avoid repeated visits
        visited_set.add(self.id)

        return self._referenced_tools_dict_inner(recursive=recursive, visited_set=visited_set)

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        return {}
