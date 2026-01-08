# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Optional

from pyagentspec.component import Component

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)


class PluginMessageTransform(Component, abstract=True):
    """
    Abstract base class for message transforms.

    Subclasses should implement the __call__ method to transform a list of Message objects
    and return a new list of Message objects, typically for preprocessing or postprocessing
    message flows in the system.
    """


class PluginCoalesceSystemMessagesTransform(PluginMessageTransform):
    """
    Transform that merges consecutive system messages at the start of a message list
    into a single system message. This is useful for reducing redundancy and ensuring
    that only one system message appears at the beginning of the conversation.
    """


class PluginRemoveEmptyNonUserMessageTransform(PluginMessageTransform):
    """
    Transform that removes messages which are empty and not from the user.

    Any message with empty content and no tool requests, except for user messages,
    will be filtered out from the message list.

    This is useful in case the template contains optional messages, which will be discarded if their
    content is empty (with a string template such as "{% if __PLAN__ %}{{ __PLAN__ }}{% endif %}").
    """


class PluginAppendTrailingSystemMessageToUserMessageTransform(PluginMessageTransform):
    """
    Transform that appends the content of a trailing system message to the previous user message.

    If the last message in the list is a system message and the one before it is a user message,
    this transform merges the system message content into the user message, reducing message clutter.

    This is useful if the underlying LLM does not support system messages at the end.
    """


class PluginLlamaMergeToolRequestAndCallsTransform(PluginMessageTransform):
    """Llama-specific message transform"""


class PluginReactMergeToolRequestAndCallsTransform(PluginMessageTransform):
    """Simple message processor that joins tool requests and calls into a python-like message"""


class PluginSwarmToolRequestAndCallsTransform(PluginMessageTransform):
    """Format Tool requests as Agent messages and Tool results as User messages to have a simple User/Agent
    sequence of messages."""


class PluginCanonicalizationMessageTransform(PluginMessageTransform):
    """
    Produce a conversation shaped like:

        System   (optional, at most one, always first if present)
        User
        Assistant
        User
        Assistant
        ...

    This is useful because some models (like Gemma) require such formatting of the messages.

    * several system messages are merged
    * consecutive assistant (resp. user) messages are merged, unless there are several tool calls,
    in which case they are split and their responses are interleaving the requests.
    """


class PluginSplitPromptOnMarkerMessageTransform(PluginMessageTransform):
    """
    Split prompts on a marker into multiple messages with the same role. Only apply to the messages without
    tool_requests and tool_result.

    This transform is useful for script-based execution flows, where a single prompt script can be converted
    into multiple conversation turns for step-by-step reasoning.
    """

    marker: Optional[str] = None


messagetransform_serialization_plugin = PydanticComponentSerializationPlugin(
    name="MessageTransformPlugin",
    component_types_and_models={
        PluginCoalesceSystemMessagesTransform.__name__: PluginCoalesceSystemMessagesTransform,
        PluginRemoveEmptyNonUserMessageTransform.__name__: PluginRemoveEmptyNonUserMessageTransform,
        PluginAppendTrailingSystemMessageToUserMessageTransform.__name__: PluginAppendTrailingSystemMessageToUserMessageTransform,
        PluginLlamaMergeToolRequestAndCallsTransform.__name__: PluginLlamaMergeToolRequestAndCallsTransform,
        PluginReactMergeToolRequestAndCallsTransform.__name__: PluginReactMergeToolRequestAndCallsTransform,
        PluginSwarmToolRequestAndCallsTransform.__name__: PluginSwarmToolRequestAndCallsTransform,
        PluginCanonicalizationMessageTransform.__name__: PluginCanonicalizationMessageTransform,
        PluginSplitPromptOnMarkerMessageTransform.__name__: PluginSplitPromptOnMarkerMessageTransform,
    },
)
messagetransform_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name="MessageTransformPlugin",
    component_types_and_models={
        PluginCoalesceSystemMessagesTransform.__name__: PluginCoalesceSystemMessagesTransform,
        PluginRemoveEmptyNonUserMessageTransform.__name__: PluginRemoveEmptyNonUserMessageTransform,
        PluginAppendTrailingSystemMessageToUserMessageTransform.__name__: PluginAppendTrailingSystemMessageToUserMessageTransform,
        PluginLlamaMergeToolRequestAndCallsTransform.__name__: PluginLlamaMergeToolRequestAndCallsTransform,
        PluginReactMergeToolRequestAndCallsTransform.__name__: PluginReactMergeToolRequestAndCallsTransform,
        PluginSwarmToolRequestAndCallsTransform.__name__: PluginSwarmToolRequestAndCallsTransform,
        PluginCanonicalizationMessageTransform.__name__: PluginCanonicalizationMessageTransform,
        PluginSplitPromptOnMarkerMessageTransform.__name__: PluginSplitPromptOnMarkerMessageTransform,
    },
)
