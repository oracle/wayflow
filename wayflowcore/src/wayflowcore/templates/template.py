# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import warnings
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Sequence, Union, cast

from wayflowcore._utils._templating_helpers import (
    MessageAsDictT,
    get_variables_names_and_types_from_template,
    render_template,
)
from wayflowcore._utils.formatting import render_message_dict_template
from wayflowcore.component import DataclassComponent
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.outputparser import OutputParser, ToolOutputParser
from wayflowcore.property import AnyProperty, ListProperty, Property
from wayflowcore.tools import Tool
from wayflowcore.transforms import MessageTransform

if TYPE_CHECKING:
    from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
    from wayflowcore.models.llmmodel import Prompt

logger = logging.getLogger(__name__)


_CHAT_HISTORY_PLACEHOLDER_MESSAGE_CONTENT = "$$__CHAT_HISTORY_PLACEHOLDER__$$"


@dataclass
class PromptTemplate(DataclassComponent):
    """
    Represents a flexible and extensible template for constructing prompts to be sent to large language models (LLMs).

    The PromptTemplate class enables the definition of prompt messages with variable placeholders, supports both
    native and custom tool calling, and allows for structured output generation.
    It manages input descriptors, message transforms (pre- and post chat_history rendering), and partial formatting
    for efficiency.
    The class also integrates with output parsers, tools and llm generation configurations.
    """

    messages: Sequence[Union[Message, MessageAsDictT]]
    """List of messages for the prompt."""
    output_parser: Optional[Union[OutputParser, List[OutputParser]]] = None
    """Post-processing applied on the raw output of the LLM."""
    input_descriptors: Optional[List[Property]] = None
    """Input descriptors that will be picked up by PromptExecutionStep or AgentExecutionStep.
    Resolved by default from the variables present in the messages."""

    # reserved placeholders & variable names
    CHAT_HISTORY_PLACEHOLDER: ClassVar[Message] = Message(
        content=_CHAT_HISTORY_PLACEHOLDER_MESSAGE_CONTENT, role="system"
    )  # singleton
    """Message placeholder in case the chat history is formatted as a chat."""
    CHAT_HISTORY_PLACEHOLDER_NAME: ClassVar[str] = "__CHAT_HISTORY__"
    """Reserved name of the placeholder for the chat history, if rendered in one message."""
    TOOL_PLACEHOLDER_NAME: ClassVar[str] = "__TOOLS__"
    """Reserved name of the placeholder for tools."""
    RESPONSE_FORMAT_PLACEHOLDER_NAME: ClassVar[str] = "__RESPONSE_FORMAT__"
    """Reserved name of the placeholder for the expected output format. Only used if non-native structured
    generation, to be able to specify the JSON format anywhere in the prompt."""

    # related to message formatting
    pre_rendering_transforms: Optional[List[MessageTransform]] = None
    """Message transform applied before rendering the list of messages into the template."""
    post_rendering_transforms: Optional[List[MessageTransform]] = None
    """Message transform applied on the rendered list of messages."""

    # related to using tools
    tools: Optional[List[Tool]] = None
    """Tools to use in the prompt."""
    native_tool_calling: bool = True
    """Whether to use the native tool calling of the model or not. All llm providers might not support it."""

    # related to structured generation
    response_format: Optional[Property] = None
    """Specific format the llm answer should follow."""
    native_structured_generation: bool = True
    """Whether to use native structured generation or not. All llm providers might not support it."""

    generation_config: Optional["LlmGenerationConfig"] = None
    """Parameters to configure the generation."""

    # internal attributes
    _partial_values: Dict[str, Any] = field(default_factory=dict)
    """Variables that are partially rendered."""

    def __post_init__(self) -> None:
        if not all(isinstance(m, Message) for m in self.messages):
            self.messages = [
                m if isinstance(m, Message) else render_message_dict_template(m)
                for m in self.messages
            ]

        if self.input_descriptors is None:
            self._resolve_inputs()

        self._validate_tool_calling()
        self._validate_structured_output()

    def _resolve_inputs(self) -> None:
        input_descriptors_per_name = {
            property_.name: property_
            for message in self.messages
            for property_ in get_variables_names_and_types_from_template(message)
        }
        if (
            PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME in input_descriptors_per_name
            and self._get_chat_history_placeholder_index() != -1
        ):
            raise ValueError(
                f"Input descriptor {PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME} is reserved for chat history, but you also used {PromptTemplate.CHAT_HISTORY_PLACEHOLDER}. Please only use one of the two"
            )
        if any(msg.content == self.CHAT_HISTORY_PLACEHOLDER.content for msg in self.messages):  # type: ignore
            input_descriptors_per_name[PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME] = ListProperty(
                name=PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME,
                item_type=AnyProperty(),
            )
        self.input_descriptors = [
            property_
            for property_ in input_descriptors_per_name.values()
            if property_.name not in self._partial_values
        ]

    def _validate_tool_calling(self) -> None:
        input_descriptors_names = {d.name for d in self.input_descriptors or []}
        if self.native_tool_calling:
            if self.TOOL_PLACEHOLDER_NAME in input_descriptors_names:
                warnings.warn(
                    f"You used the tool placeholder {self.TOOL_PLACEHOLDER_NAME} in the template, which reserved for tools, "
                    "but you configured the prompt to use native tool calling. Make sure "
                    "you know what you are doing.",
                )
        else:
            if self.TOOL_PLACEHOLDER_NAME not in input_descriptors_names:
                warnings.warn(
                    f"There is no tool placeholder {self.TOOL_PLACEHOLDER_NAME} in the template and it has been configured in non-FC mode. The model will not see any tools. Inputs are {self.input_descriptors}"
                )
            if self.output_parser is None:
                raise ValueError(
                    "Should configure an output parser if not using native tool calling"
                )

    def _validate_structured_output(self) -> None:
        input_descriptors_names = {d.name for d in self.input_descriptors or []}
        if self.native_structured_generation:
            if self.RESPONSE_FORMAT_PLACEHOLDER_NAME in input_descriptors_names:
                warnings.warn(
                    f"You used the structured output placeholder {self.RESPONSE_FORMAT_PLACEHOLDER_NAME} in the template, which reserved for structured output format, "
                    "but you configured the prompt to use native structure output format. Make sure "
                    "you know what you are doing.",
                )
        else:
            if self.RESPONSE_FORMAT_PLACEHOLDER_NAME not in input_descriptors_names:
                logger.debug(
                    f"There is no structured output placeholder {self.RESPONSE_FORMAT_PLACEHOLDER_NAME} in the template and it has been configured in non-native structured mode. Make sure the prompt contains the expected output format."
                )
            if self.output_parser is None:
                raise ValueError(
                    "Template was configured to non-native structured generation, but no output parser was configured"
                )

    def with_partial(self, inputs: Dict[str, Any]) -> "PromptTemplate":
        """
        Partially formats the prompt with the given inputs (to avoid formatting everything at each call, if some
        inputs do not change). These inputs are not rendered directly, but stored for a later call to `format()`.
        """
        new_template = self.copy()
        new_template._partial_values.update(inputs)
        new_template._resolve_inputs()
        return new_template

    def with_tools(self, tools: Optional[List[Tool]]) -> "PromptTemplate":
        """Returns a copy of the template equipped with the given tools."""
        new_template = self.copy()
        if tools is not None and not isinstance(tools, list):
            raise ValueError(f"Should pass a list of tools to PromptTemplate, but passed: {tools}")
        new_template.tools = tools
        return new_template

    def with_generation_config(
        self, generation_config: Optional[LlmGenerationConfig], override: bool = True
    ) -> "PromptTemplate":
        """Override: Whether the template config should be overridden or should overridden this config."""
        new_template = self.copy()
        if generation_config is not None:
            if new_template.generation_config is None:
                new_template.generation_config = generation_config
            elif override:
                new_template.generation_config = new_template.generation_config.merge_config(
                    generation_config
                )
            else:
                new_template.generation_config = generation_config.merge_config(
                    new_template.generation_config
                )
        return new_template

    def with_response_format(self, response_format: Optional[Property]) -> "PromptTemplate":
        """Returns a copy of the template equipped with a given response format."""
        new_template = self.copy()
        new_template.response_format = response_format
        return new_template

    def with_additional_post_rendering_transform(
        self, transform: MessageTransform
    ) -> "PromptTemplate":
        """Appends an additional post rendering transform to this template."""
        new_template = self.copy()
        new_template.post_rendering_transforms = (new_template.post_rendering_transforms or []) + [
            transform
        ]
        return new_template

    def with_output_parser(
        self, output_parser: Union[OutputParser, List[OutputParser]]
    ) -> "PromptTemplate":
        """Replaces the output parser of this template."""
        new_template = self.copy()
        new_template.output_parser = output_parser
        return new_template

    def copy(self) -> "PromptTemplate":
        """Returns a copy of the template."""
        template_dict = {k: v for k, v in self.__dict__.items()}
        template_dict["_partial_values"] = {
            k: v for k, v in template_dict["_partial_values"].items()
        }
        if template_dict["post_rendering_transforms"] is not None:
            template_dict["post_rendering_transforms"] = [
                *template_dict["post_rendering_transforms"]
            ]
        if template_dict["pre_rendering_transforms"] is not None:
            template_dict["pre_rendering_transforms"] = [*template_dict["pre_rendering_transforms"]]
        return PromptTemplate(**template_dict)

    @classmethod
    def from_string(
        cls,
        template: str,
        output_parser: Optional[OutputParser] = None,
        input_descriptors: Optional[List[Property]] = None,
        pre_rendering_transforms: Optional[List[MessageTransform]] = None,
        post_rendering_transforms: Optional[List[MessageTransform]] = None,
        tools: Optional[List[Tool]] = None,
        native_tool_calling: bool = True,
        response_format: Optional[Property] = None,
        native_structured_generation: bool = True,
        generation_config: Optional["LlmGenerationConfig"] = None,
    ) -> "PromptTemplate":
        """Creates a prompt template from a string."""
        return PromptTemplate(
            messages=[Message(message_type=MessageType.USER, content=template)],
            output_parser=output_parser,
            input_descriptors=input_descriptors,
            pre_rendering_transforms=pre_rendering_transforms,
            post_rendering_transforms=post_rendering_transforms,
            tools=tools,
            native_tool_calling=native_tool_calling,
            response_format=response_format,
            native_structured_generation=native_structured_generation,
            generation_config=generation_config,
        )

    def format(self, inputs: Optional[Dict[str, Any]] = None) -> "Prompt":
        """Formats the prompt into a list of messages to pass to the LLM"""
        from wayflowcore.models.llmmodel import Prompt

        inputs = deepcopy(inputs) or {}
        inputs.update(self._partial_values)

        if not self.native_tool_calling:
            inputs[self.TOOL_PLACEHOLDER_NAME] = [
                tool.to_openai_format() for tool in (self.tools or [])
            ]

        if (
            not self.native_structured_generation
            and self.response_format is not None
            and self.RESPONSE_FORMAT_PLACEHOLDER_NAME not in inputs
        ):
            inputs[self.RESPONSE_FORMAT_PLACEHOLDER_NAME] = self.response_format.to_json_schema()

        messages = self._prepare_messages(inputs)

        return Prompt(
            messages=messages,
            tools=self.tools if self.native_tool_calling else None,
            response_format=self.response_format if self.native_structured_generation else None,
            output_parser=(
                self.output_parser.with_tools(self.tools)
                if isinstance(self.output_parser, ToolOutputParser)
                else self.output_parser
            ),
            generation_config=self.generation_config,
        )

    def _prepare_messages(self, inputs: Dict[str, Any]) -> List[Message]:

        if (
            any(p.name == self.CHAT_HISTORY_PLACEHOLDER_NAME for p in self.input_descriptors or [])
            and self.CHAT_HISTORY_PLACEHOLDER_NAME not in inputs
        ):
            raise ValueError(
                f"Should pass the chat_history as input (with key `self.CHAT_HISTORY_PLACEHOLDER_NAME`), but only passed: {inputs}"
            )

        chat_history = inputs.pop(self.CHAT_HISTORY_PLACEHOLDER_NAME, [])
        for message_transform in self.pre_rendering_transforms or []:
            chat_history = message_transform(chat_history)

        chat_history_index = self._get_chat_history_placeholder_index()
        messages: List[Message] = cast(List[Message], list(self.messages))
        if chat_history_index != -1:
            messages = [
                *render_template(messages[:chat_history_index], inputs=inputs),
                *chat_history,
                *render_template(messages[chat_history_index + 1 :], inputs=inputs),
            ]
        else:
            serialized_chat_history = [
                {
                    "message_type": message.message_type.value,
                    "content": message.content,
                }
                for message in chat_history
            ]
            messages = render_template(
                messages,
                inputs={self.CHAT_HISTORY_PLACEHOLDER_NAME: serialized_chat_history, **inputs},
            )

        for message_transform in self.post_rendering_transforms or []:
            messages = message_transform(messages)

        return messages

    def _get_chat_history_placeholder_index(self) -> int:
        """Returns the index of the chat history placeholder in the list of messages. Returns -1 if None."""
        try:
            return next(
                idx
                for idx, msg in enumerate(self.messages)
                if (msg.content if isinstance(msg, Message) else msg["content"])
                == self.CHAT_HISTORY_PLACEHOLDER.content
            )
        except StopIteration:
            return -1
