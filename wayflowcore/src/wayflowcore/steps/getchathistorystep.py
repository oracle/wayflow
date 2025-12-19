# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from wayflowcore._metadata import MetadataType
from wayflowcore._utils._templating_helpers import (
    get_variables_names_and_types_from_template,
    render_template,
)
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.property import AnyProperty, ListProperty, Property, StringProperty
from wayflowcore.steps.step import Step, StepResult

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation


class MessageSlice(Enum):
    LAST_MESSAGES = "last"
    FIRST_MESSAGES = "first"


_DEFAULT_OUTPUT_TEMPLATE = """{% for m in chat_history -%}
{{m.message_type}} >> {{m.content}}{{ "
" if not loop.last }}
{%- endfor %}"""

_DEFAULT_MESSAGE_TYPES = (MessageType.USER, MessageType.AGENT)


class GetChatHistoryStep(Step):

    CHAT_HISTORY = "chat_history"
    """str: Output key for the chat history collected by the ``GetChatHistoryStep``."""
    DEFAULT_OUTPUT_TEMPLATE = _DEFAULT_OUTPUT_TEMPLATE
    """str: Default output template to be used to format the chat history."""

    def __init__(
        self,
        n: int = 10,
        which_messages: MessageSlice = MessageSlice.LAST_MESSAGES,
        offset: int = 0,
        message_types: Optional[Tuple[MessageType, ...]] = _DEFAULT_MESSAGE_TYPES,
        output_template: Optional[str] = "",
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Step to get messages from the messages list e.g. last 4 messages and return it as output.

        Note
        ----

        A step has input and output descriptors, describing what values the step requires to run and what values it produces.

        **Input descriptors**

        This step has no input descriptors.

        **Output descriptors**

        This step has a single output descriptor:

        * ``GetChatHistoryStep.CHAT_HISTORY``: the chat history extract from the conversation, type is either ``StringProperty()`` or ``ListProperty(item_type=AnyProperty())`` if ``output_template`` is ``None``.

        Parameters
        ----------
        n:
            Number of messages to retrieve.
        which_messages:
            Strategy for which messages to collect. Either ``last_messages`` or ``first_messages``.
        offset:
            Number of messages to ignore in the given order. Needs to be a non-negative integer.
        message_types:
            Optional filter to select specific messages. ``None`` means take all the messages from the history.
        output_template:
            Template to format the chat history. If None, this step will return the list of messages. If string,
            it will format the ``chat_history`` messages into this template using jinja2 syntax.
        input_descriptors:
            Input descriptors of the step. ``None`` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.
        output_descriptors:
            Output descriptors of the step. ``None`` means the step will resolve them automatically using its static
            configuration in a best effort manner.
        name:
            Name of the step.
        input_mapping:
            Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
        output_mapping:
            Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.

        Examples
        --------

        This step can be used to format the conversation into a string that can be used in a prompt.
        For example, if the conversation is:

        >>> from wayflowcore.messagelist import Message, MessageType, MessageList
        >>> from wayflowcore.steps import GetChatHistoryStep
        >>> from wayflowcore.flowhelpers import create_single_step_flow
        >>> messages = [
        ...     Message(content='How can I help you?', message_type=MessageType.AGENT),
        ...     Message(content='What is the capital of Switzerland?', message_type=MessageType.AGENT),
        ...     Message(content='The capital of Switzerland is Bern?', message_type=MessageType.AGENT),
        ... ]

        If we want to format the chat history into a string directly in the step:

        >>> step = GetChatHistoryStep(n=10)
        >>> assistant = create_single_step_flow(step, 'step')
        >>> conversation = assistant.start_conversation(inputs={}, messages=messages)
        >>> status = conversation.execute()
        >>> status.output_values[GetChatHistoryStep.CHAT_HISTORY]  # doctest: +SKIP
        AGENT>>>How can I help you?
        USER>>>What is the capital of Switzerland?
        AGENT>>>The capital of Switzerland is Bern?

        If we want to use the chat history in a later step (``PromptExecutionStep`` for example), we can set the template
        of the ``GetChatHistoryStep`` to None and use the object returned by this step in a later template, similarly to
        how it's used in the default ``GetChatHistoryStep`` template.

        >>> from wayflowcore.steps import PromptExecutionStep
        >>> step = GetChatHistoryStep(n=10, output_template=None)
        >>> prompt_execution_step = PromptExecutionStep(
        ...     llm=llm,
        ...     prompt_template='{% for m in chat_history -%}>>>{{m.content}}{% endfor %}',
        ...     input_mapping={'chat_history': GetChatHistoryStep.CHAT_HISTORY}
        ... )

        """
        if n < 0:
            raise ValueError("`n` should be >= 0")
        self.output_template = (
            output_template if output_template != "" else self.DEFAULT_OUTPUT_TEMPLATE
        )
        super().__init__(
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            step_static_configuration=dict(
                n=n,
                which_messages=which_messages,
                offset=offset,
                message_types=message_types,
                output_template=self.output_template,
            ),
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )
        self.n = n
        self.which_messages = which_messages
        self.message_types = message_types
        if offset < 0:
            raise ValueError(f"Offset should be a non-negative integer but was {offset}")
        self.offset = offset

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        return {
            "n": int,
            "which_messages": MessageSlice,
            "offset": int,
            "message_types": List[MessageType],
            "output_template": Optional[str],  # type: ignore
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        n: Optional[int],
        which_messages: MessageSlice,
        offset: int,
        message_types: Optional[Tuple[MessageType, ...]],
        output_template: Optional[str],
    ) -> List[Property]:
        if output_template is None:
            return []

        input_descriptors = [
            var_info
            for var_info in get_variables_names_and_types_from_template(output_template)
            if var_info.name != "chat_history"
        ]
        return input_descriptors

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        n: Optional[int],
        which_messages: MessageSlice,
        offset: int,
        message_types: Optional[Tuple[MessageType, ...]],
        output_template: Optional[str],
    ) -> List[Property]:
        output_descriptor: Property
        if output_template is None:
            output_descriptor = ListProperty(
                name=cls.CHAT_HISTORY,
                description="the list of chat messages extracted from the messages list",
                item_type=AnyProperty("item"),
            )
        else:
            output_descriptor = StringProperty(
                name=cls.CHAT_HISTORY,
                description="the chat history extracted from the messages list, formatted as a string",
            )
        return [output_descriptor]

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        chat_history = conversation.get_messages()

        if self.message_types is not None:
            chat_history = [m for m in chat_history if m.message_type in self.message_types]

        if self.which_messages == MessageSlice.LAST_MESSAGES:
            # swap the order to filter correctly, and will be swapped back afterwards
            chat_history = chat_history[::-1]

        if self.offset > 0:
            if self.offset >= len(chat_history):
                chat_history = []
            else:
                chat_history = chat_history[self.offset :]

        if self.n is not None:
            chat_history = chat_history[: min(self.n, len(chat_history))]

        if self.which_messages == MessageSlice.LAST_MESSAGES:
            chat_history = chat_history[::-1]

        formatted_chat_history: Union[str, List[Message]] = chat_history
        if self.output_template is not None:
            serialized_chat_history = [
                {
                    "message_type": message.message_type.value,
                    "content": message.content,
                }
                for message in chat_history
            ]
            formatted_chat_history = render_template(
                template=self.output_template,
                inputs=dict(chat_history=serialized_chat_history, **inputs),
            )

        return StepResult(
            outputs={self.CHAT_HISTORY: formatted_chat_history},
        )
