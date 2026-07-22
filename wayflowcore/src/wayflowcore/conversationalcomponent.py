# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
    cast,
)

from wayflowcore._metadata import MetadataType
from wayflowcore.componentwithio import ComponentWithInputsOutputs
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.messagelist import Message
from wayflowcore.property import Property

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from wayflowcore.checkpointing import Checkpointer
    from wayflowcore.conversation import Conversation
    from wayflowcore.executors._executor import ConversationExecutor
    from wayflowcore.messagelist import MessageList
    from wayflowcore.models.llmmodel import LlmModel
    from wayflowcore.tools import Tool

_HUMAN_ENTITY_ID = "human_user"
ConversationTypeT = TypeVar("ConversationTypeT", bound="Conversation")


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
        checkpointer: Optional["Checkpointer"] = None,
        checkpoint_id: Optional[str] = None,
    ) -> "Conversation":
        pass

    def _start_conversation_impl(
        self,
        inputs: Optional[Dict[str, Any]],
        messages: Union[None, str, "Message", List["Message"], "MessageList"],
        conversation_id: Optional[str],
        checkpointer: Optional["Checkpointer"],
        checkpoint_id: Optional[str],
        parent_conversation: Optional["Conversation"] = None,
    ) -> "Conversation":
        """Create a concrete conversation for internal root/child entry points."""
        raise NotImplementedError

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
        if isinstance(messages, Message):
            return True
        return len(messages) > 0

    def _prepare_conversation_start(
        self,
        inputs: Optional[Dict[str, Any]],
        messages: Union[None, str, "Message", List["Message"], "MessageList"],
        conversation_id: Optional[str],
        checkpointer: Optional["Checkpointer"],
        checkpoint_id: Optional[str],
        expected_conversation_type: Type[ConversationTypeT],
        parent_conversation: Optional["Conversation"],
    ) -> tuple[Optional[ConversationTypeT], str, str]:
        """Resolve whether start_conversation creates a fresh or restored conversation.

        Returns a tuple of:
        - an already restored conversation, or ``None`` for a fresh start
        - the generated id to assign to the concrete ``Conversation`` object
        - the conversation thread id shared by nested conversations

        ``expected_conversation_type`` keeps the restored conversation typed for static typing;
        runtime validation uses it too.
        """
        if parent_conversation is not None:
            if checkpoint_id is not None:
                raise ValueError("Cannot restore a checkpoint as a subconversation.")
            return None, IdGenerator.get_or_generate_id(), parent_conversation.conversation_id

        # No checkpointer means this is a fresh root conversation; just resolve ids.
        if checkpointer is None:
            if checkpoint_id is not None:
                raise ValueError("`checkpoint_id` requires a `checkpointer`.")

            # A root conversation is the first instance in its thread, so one ID serves both roles.
            conversation_id = conversation_id or IdGenerator.get_or_generate_id()
            return None, conversation_id, conversation_id

        # Checkpoint restore uses the thread id to locate stored state.
        resolved_conversation_id = conversation_id
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
            return None, resolved_conversation_id, resolved_conversation_id

        # Restoring and starting with new input are separate operations.
        if self._messages_or_inputs_were_passed(inputs=inputs, messages=messages):
            raise ValueError(
                "Cannot restore a checkpoint while also passing new `inputs` or `messages`. "
                "Load the conversation first, then append new user input explicitly."
            )

        from wayflowcore.checkpointing.checkpoint_state import _load_checkpointed_conversation

        # Rehydrate the stored conversation against this live component tree.
        conversation = _load_checkpointed_conversation(
            checkpoint,
            component=self,
            expected_conversation_type=expected_conversation_type,
            tool_registry={tool.name: tool for tool in self._referenced_tools()},
            checkpointer=checkpointer,
            attach_checkpointer=True,
        )
        return (
            cast(ConversationTypeT, conversation),
            resolved_conversation_id,
            resolved_conversation_id,
        )

    def _start_subconversation(
        self,
        parent_conversation: "Conversation",
        inputs: Optional[Dict[str, Any]] = None,
        messages: Union[None, str, "Message", List["Message"], "MessageList"] = None,
    ) -> "Conversation":
        """Start a child that inherits its parent's conversation thread."""
        return self._start_conversation_impl(
            inputs=inputs,
            messages=messages,
            conversation_id=None,
            checkpointer=None,
            checkpoint_id=None,
            parent_conversation=parent_conversation,
        )


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
