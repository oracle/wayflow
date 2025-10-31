# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union

from wayflowcore._metadata import MetadataType
from wayflowcore.componentwithio import ComponentWithInputsOutputs
from wayflowcore.property import Property

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.executors._executor import ConversationExecutor
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
        from wayflowcore.tools.tools import _validate_name

        # Dictionary of files available in this conversation
        self._files: Dict[str, Path] = {}
        self.runner = runner
        self.conversation_class = conversation_class

        # we want in the future to be able to use any conversational components
        # as an "agentic component", which might be used in multi-agent patterns
        # where we need their name to be used for making tool names (to talk between agentic components)
        # so we need to validate that the name is OK for such use
        _validate_name(name, allow_space=True, raise_on_invalid=False)

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
