# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Optional, Set, Type, TypeVar, Union

from wayflowcore._metadata import MetadataType
from wayflowcore.checkpointing.runtime import _attach_checkpointer_to_conversation
from wayflowcore.checkpointing.serialization import _deserialize_conversation_checkpoint_state
from wayflowcore.componentwithio import ComponentWithInputsOutputs
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.property import Property

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from wayflowcore.checkpointing import Checkpointer
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
        runner: Type["ConversationExecutor"],
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
        messages: Union[None, str, "Message", List["Message"], "MessageList"] = None,
        conversation_id: Optional[str] = None,
        *,
        root_conversation_id: Optional[str] = None,
        checkpointer: Optional["Checkpointer"] = None,
        checkpoint_id: Optional[str] = None,
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

    @abstractmethod
    def _update_internal_state(self) -> None:
        """
        Method to update the attributes inside.
        """

    @staticmethod
    def _messages_or_inputs_were_passed(
        inputs: Optional[Dict[str, Any]],
        messages: Union[None, str, "Message", List["Message"], "MessageList"],
    ) -> bool:
        if inputs:
            return True
        if messages is None:
            return False
        if isinstance(messages, str):
            return len(messages) > 0
        if hasattr(messages, "__len__"):
            return len(messages) > 0
        return True

    def _restore_or_prepare_checkpoint_conversation(
        self,
        *,
        inputs: Optional[Dict[str, Any]],
        messages: Union[None, str, "Message", List["Message"], "MessageList"],
        conversation_id: Optional[str],
        root_conversation_id: Optional[str],
        checkpointer: Optional["Checkpointer"],
        checkpoint_id: Optional[str],
    ) -> tuple[Optional["Conversation"], Optional[str]]:
        if checkpointer is None:
            if checkpoint_id is not None:
                raise ValueError("`checkpoint_id` requires a `checkpointer`.")
            return None, conversation_id

        if (
            root_conversation_id is not None
            and conversation_id is not None
            and root_conversation_id != conversation_id
        ):
            raise ValueError(
                "`root_conversation_id` and `conversation_id` cannot differ when checkpointing is enabled."
            )

        resolved_conversation_id = conversation_id or root_conversation_id
        if resolved_conversation_id is None and checkpoint_id is not None:
            raise ValueError("`checkpoint_id` requires a `conversation_id`.")
        if resolved_conversation_id is None:
            resolved_conversation_id = IdGenerator.get_or_generate_id()

        checkpoint = (
            checkpointer.load(resolved_conversation_id, checkpoint_id)
            if checkpoint_id is not None
            else checkpointer.load_latest(resolved_conversation_id)
        )
        if checkpoint is None:
            return None, resolved_conversation_id

        if self._messages_or_inputs_were_passed(inputs=inputs, messages=messages):
            raise ValueError(
                "Cannot restore a checkpoint while also passing new `inputs` or `messages`. "
                "Load the conversation first, then append new user input explicitly."
            )

        conversation = _deserialize_conversation_checkpoint_state(
            checkpoint.state,
            tool_registry={tool.name: tool for tool in self._referenced_tools()},
            component=self,
        )
        return (
            _attach_checkpointer_to_conversation(
                conversation,
                checkpointer=checkpointer,
                checkpoint_id=checkpoint.checkpoint_id,
            ),
            resolved_conversation_id,
        )

    @staticmethod
    def _resolve_runtime_and_root_conversation_ids(
        *,
        conversation_id: Optional[str],
        root_conversation_id: Optional[str],
        checkpointer: Optional["Checkpointer"],
        restored_conversation_id: Optional[str],
    ) -> tuple[str, str]:
        if checkpointer is not None:
            runtime_conversation_id = restored_conversation_id or IdGenerator.get_or_generate_id(
                conversation_id or root_conversation_id
            )
            resolved_root_conversation_id = root_conversation_id or runtime_conversation_id
            if resolved_root_conversation_id != runtime_conversation_id:
                raise ValueError(
                    "`root_conversation_id` and `conversation_id` cannot differ when checkpointing is enabled."
                )
            return runtime_conversation_id, runtime_conversation_id

        runtime_conversation_id = IdGenerator.get_or_generate_id(conversation_id)
        return runtime_conversation_id, root_conversation_id or runtime_conversation_id


# Define a TypeVar that represents the component's type
ConversationalComponentTypeT = TypeVar(
    "ConversationalComponentTypeT", bound="ConversationalComponent"
)


class _MutatedConversationalComponent(Generic[ConversationalComponentTypeT]):
    def __init__(self, component: ConversationalComponentTypeT, attributes: Dict[str, Any]):
        self.component = component
        self.attributes = attributes
        self.old_config: Dict[str, Any] = {}

    def __enter__(self) -> ConversationalComponentTypeT:
        self.old_config.clear()
        for attr, value in self.attributes.items():
            self.old_config[attr] = getattr(self.component, attr)
            setattr(self.component, attr, value)
        self.component._update_internal_state()
        return self.component

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        for attr, value in self.old_config.items():
            setattr(self.component, attr, value)
        self.old_config.clear()
        self.component._update_internal_state()


def _mutate(
    component: ConversationalComponentTypeT, attributes: Dict[str, Any]
) -> _MutatedConversationalComponent[ConversationalComponentTypeT]:
    """
    Returns a context manager for mutating the component with the provided attributes.
    Selects the appropriate mutator class based on the component type.
    """
    return _MutatedConversationalComponent(component, attributes)
