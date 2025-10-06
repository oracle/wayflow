# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.async_helpers import run_async_in_sync
from wayflowcore.componentwithio import ComponentWithInputsOutputs
from wayflowcore.property import Property

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.executors._executor import ConversationExecutor
    from wayflowcore.executors.executionstatus import ExecutionStatus
    from wayflowcore.executors.interrupts.executioninterrupt import ExecutionInterrupt
    from wayflowcore.messagelist import Message, MessageList
    from wayflowcore.models.llmmodel import LlmModel
    from wayflowcore.tools import Tool

_HUMAN_ENTITY_ID = "human_user"


class ConversationalComponent(ComponentWithInputsOutputs, ABC):

    def __init__(
        self,
        name: str,
        description: Optional[str],
        input_descriptors: List["Property"],
        output_descriptors: List["Property"],
        runner: type["ConversationExecutor"],
        conversation_class: Any,
        id: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        # Dictionary of files available in this conversation
        self._files: Dict[str, Path] = {}
        self.runner = runner
        self.conversation_class = conversation_class

        super().__init__(
            id=id,
            name=name,
            description=description,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            __metadata_info__=__metadata_info__,
        )

    @abstractmethod
    def start_conversation(
        self,
        inputs: Optional[Dict[str, Any]] = None,
        messages: Optional[Union["MessageList", List["Message"]]] = None,
    ) -> "Conversation":
        pass

    @property
    def llms(self) -> List["LlmModel"]:
        raise NotImplementedError("to be implemented by child classes")

    def execute(
        self,
        conversation: "Conversation",
        execution_interrupts: Optional[List["ExecutionInterrupt"]] = None,
        _validate_same_component: bool = True,
    ) -> "ExecutionStatus":
        from wayflowcore.events.eventlistener import _record_exception

        warnings.warn(
            "Call to deprecated method execute. (Method was deprecated in 25.3.0 and will be removed in 25.4. Please use `conversation.execute()` instead.)",
            category=DeprecationWarning,
        )

        try:
            if not isinstance(conversation, self.conversation_class):
                raise ValueError(
                    f"the provided conversation to a {self.__class__} must be of type {self.conversation_class} but was {type(conversation).__name__}"
                )
            if _validate_same_component and conversation.component is not self:
                raise ValueError(
                    "You are trying to call the component on a conversation that was not created by it. Please use `conversation.execute()` instead."
                )

            return run_async_in_sync(
                self.runner.execute_async,
                conversation,
                execution_interrupts,
                method_name="conversation.execute_async",
            )

        except Exception as e:
            _record_exception(e)
            raise e

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
        """
        Returns a dictionary of all tools that are present in this component's configuration, including tools
        nested in subcomponents, with the keys being the tool IDs, and the values being the tools.
        """
        visited_set = set() if visited_set is None else visited_set

        if self.id in visited_set:
            # we are already visited, no need to return anything
            return {}

        # Mark ourself as visited to avoid repeated visits
        visited_set.add(self.id)

        return self._referenced_tools_dict_inner(recursive=recursive, visited_set=visited_set)

    @abstractmethod
    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        """
        Returns a dictionary of all tools that are present in this component's configuration, including tools
        nested in subcomponents, with the keys being the tool IDs, and the values being the tools.
        """
