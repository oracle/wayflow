# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.async_helpers import run_async_in_sync, run_sync_in_thread
from wayflowcore.component import Component
from wayflowcore.conversation import Conversation
from wayflowcore.property import Property
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableObject
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
        from wayflowcore.serialization.contextproviderserialization import (
            serialize_context_provider_to_dict,
        )

        return serialize_context_provider_to_dict(self, serialization_context)

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: DeserializationContext
    ) -> "SerializableObject":
        from wayflowcore.serialization.contextproviderserialization import (
            deserialize_context_provider_from_dict,
        )

        return deserialize_context_provider_from_dict(input_dict, deserialization_context)

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
