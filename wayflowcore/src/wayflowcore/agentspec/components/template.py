# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import warnings
from typing import Any, ClassVar, Dict, List, Optional, Union

from pyagentspec.component import Component
from pyagentspec.llms import LlmGenerationConfig
from pyagentspec.property import ListProperty, Property
from pyagentspec.tools import Tool
from pyagentspec.validation_helpers import model_validator_with_error_accumulation
from pydantic import SerializeAsAny
from typing_extensions import Self

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)
from wayflowcore.agentspec.components._utils import (
    get_placeholder_properties_from_string_with_jinja_loops,
)
from wayflowcore.agentspec.components.messagelist import PluginMessage, PluginTextContent
from wayflowcore.agentspec.components.outputparser import PluginOutputParser
from wayflowcore.agentspec.components.transforms import PluginMessageTransform

logger = logging.getLogger(__name__)


class PluginPromptTemplate(Component):
    """
    Represents a flexible and extensible template for constructing prompts to be sent to large language models (LLMs).

    The PromptTemplate class enables the definition of prompt messages with variable placeholders, supports both
    native and custom tool calling, and allows for structured output generation.
    It manages input descriptors, message transforms (pre- and post chat_history rendering), and partial formatting
    for efficiency.
    The class also integrates with output parsers, tools and llm generation configurations.
    """

    messages: List[PluginMessage]
    """List of messages for the prompt."""
    output_parser: Optional[
        Union[List[SerializeAsAny[PluginOutputParser]], SerializeAsAny[PluginOutputParser]]
    ] = None
    """Post-processing applied on the raw output of the LLM."""
    inputs: Optional[List[SerializeAsAny[Property]]] = None
    """Input descriptors that will be picked up by PromptExecutionStep or AgentExecutionStep.
    Resolved by default from the variables present in the messages."""

    # related to message formatting
    pre_rendering_transforms: Optional[List[SerializeAsAny[PluginMessageTransform]]] = None
    """Message transform applied before rendering the list of messages into the template."""
    post_rendering_transforms: Optional[List[SerializeAsAny[PluginMessageTransform]]] = None
    """Message transform applied on the rendered list of messages."""

    # related to using tools
    tools: Optional[List[SerializeAsAny[Tool]]] = None
    """Tools to use in the prompt."""
    native_tool_calling: bool = True
    """Whether to use the native tool calling of the model or not. All llm providers might not support it."""

    # related to structured generation
    response_format: Optional[SerializeAsAny[Property]] = None
    """Specific format the llm answer should follow."""
    native_structured_generation: bool = True
    """Whether to use native structured generation or not. All llm providers might not support it."""

    generation_config: Optional[LlmGenerationConfig] = None
    """Parameters to configure the generation."""

    # reserved placeholders & variable names
    CHAT_HISTORY_PLACEHOLDER: ClassVar[PluginMessage] = PluginMessage(role="user")  # singleton
    """Message placeholder in case the chat history is formatted as a chat."""
    CHAT_HISTORY_PLACEHOLDER_NAME: ClassVar[str] = "__CHAT_HISTORY__"
    """Reserved name of the placeholder for the chat history, if rendered in one message."""
    TOOL_PLACEHOLDER_NAME: ClassVar[str] = "__TOOLS__"
    """Reserved name of the placeholder for tools."""
    RESPONSE_FORMAT_PLACEHOLDER_NAME: ClassVar[str] = "__RESPONSE_FORMAT__"
    """Reserved name of the placeholder for the expected output format. Only used if non-native structured
    generation, to be able to specify the JSON format anywhere in the prompt."""

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if not hasattr(self, "messages") or (  # partial build
            hasattr(self, "inputs") and self.inputs
        ):  # already resolved
            return None
        inputs_per_name = self._get_input_per_name()
        self.inputs = [property_ for property_ in inputs_per_name.values()]

    def _get_input_per_name(self) -> Dict[str, Property]:
        if not hasattr(self, "messages"):
            raise RuntimeError(
                "Method `_get_input_per_name` should not be "
                "called when field `messages` is missing."
            )
        return {
            property_.title: property_
            for message in self.messages
            for property_ in get_placeholder_properties_from_string_with_jinja_loops(
                "\n".join(c.content for c in message.contents if isinstance(c, PluginTextContent))
            )
        }

    @model_validator_with_error_accumulation
    def _resolve_and_validate_inputs(self) -> Self:
        if self.inputs:
            return self
        inputs_per_name = self._get_input_per_name()
        if (
            PluginPromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME in inputs_per_name
            and self._get_chat_history_placeholder_index() != -1
        ):
            raise ValueError(
                f"Input descriptor {PluginPromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME} is reserved "
                f"for chat history, but you also used {PluginPromptTemplate.CHAT_HISTORY_PLACEHOLDER}. "
                "Please only use one of the two."
            )
        if PluginPromptTemplate.CHAT_HISTORY_PLACEHOLDER in self.messages:
            inputs_per_name[PluginPromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME] = ListProperty(
                title=PluginPromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME,
                item_type=Property(json_schema={}),
            )
        return self

    @model_validator_with_error_accumulation
    def _validate_tool_calling(self) -> Self:
        inputs_names = {property_.title for property_ in self.inputs or []}
        if self.native_tool_calling:
            if self.TOOL_PLACEHOLDER_NAME in inputs_names:
                warnings.warn(
                    f"You used the tool placeholder {self.TOOL_PLACEHOLDER_NAME} in the template, which reserved for tools, "
                    "but you configured the prompt to use native tool calling. Make sure "
                    "you know what you are doing.",
                )
        else:
            if self.TOOL_PLACEHOLDER_NAME not in inputs_names:
                warnings.warn(
                    f"There is no tool placeholder {self.TOOL_PLACEHOLDER_NAME} in the template and it has been configured in non-function-calling mode. The model will not see any tools. Inputs are {self.inputs}"
                )
            if self.output_parser is None:
                raise ValueError(
                    "Should configure an output parser if not using native tool calling"
                )
        return self

    @model_validator_with_error_accumulation
    def _validate_structured_output(self) -> Self:
        inputs_names = {property_.title for property_ in self.inputs or []}
        if self.native_structured_generation:
            if self.RESPONSE_FORMAT_PLACEHOLDER_NAME in inputs_names:
                warnings.warn(
                    f"You used the structured output placeholder {self.RESPONSE_FORMAT_PLACEHOLDER_NAME} in the template, which reserved for structured output format, "
                    "but you configured the prompt to use native structure output format. Make sure "
                    "you know what you are doing.",
                )
        else:
            if self.RESPONSE_FORMAT_PLACEHOLDER_NAME not in inputs_names:
                logger.debug(
                    f"There is no structured output placeholder {self.RESPONSE_FORMAT_PLACEHOLDER_NAME} in the template and it has been configured in non-native structured mode. Make sure the prompt contains the expected output format."
                )
            if self.output_parser is None:
                raise ValueError(
                    "Template was configured to non-native structured generation, but no output parser was configured"
                )
        return self

    def _get_chat_history_placeholder_index(self) -> int:
        """Returns the index of the chat history placeholder in the list of messages. Returns -1 if None."""
        try:
            return self.messages.index(self.CHAT_HISTORY_PLACEHOLDER)
        except ValueError:
            return -1


PROMPTTEMPLATE_PLUGIN_NAME = "PromptTemplatePlugin"

prompttemplate_serialization_plugin = PydanticComponentSerializationPlugin(
    name=PROMPTTEMPLATE_PLUGIN_NAME,
    component_types_and_models={
        PluginPromptTemplate.__name__: PluginPromptTemplate,
    },
)

prompttemplate_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=PROMPTTEMPLATE_PLUGIN_NAME,
    component_types_and_models={
        PluginPromptTemplate.__name__: PluginPromptTemplate,
    },
)
