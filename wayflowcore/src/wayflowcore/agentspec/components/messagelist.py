# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator
from typing_extensions import Self

from wayflowcore.agentspec.components.tools import PluginToolRequest, PluginToolResult
from wayflowcore.messagelist import MessageType as PluginMessageType  # noqa: F401

logger = logging.getLogger(__name__)


class PluginMessageContent(BaseModel):
    """
    Abstract base class for message content chunks.

    All message content types (such as text and images) should derive from this class
    and specify a class-level 'type' field to distinguish content variant.
    Subclasses may also add additional fields for content-specific data.
    """

    type: str


class PluginTextContent(PluginMessageContent):
    """Represents the content of a text message."""

    content: str = ""
    """The textual content of the message."""
    type: Literal["text"] = "text"

    @model_validator(mode="after")
    def validate_text_content_type(self) -> Self:
        if not isinstance(self.content, str):
            logger.warning(
                "Message.content should be of type `str` but is of type `%s`. Make sure that the "
                "message content can be cast to a string",
                type(self.content).__name__,
            )
            self.content = str(self.content)
        return self


class PluginImageContent(PluginMessageContent):
    """
    Represents the content of an image message, storing image data as a base64-encoded string.
    """

    base64_content: str
    """A base64-encoded string representing the image data."""
    type: Literal["image"] = "image"


PluginAnyContent = Annotated[
    Union[PluginTextContent, PluginImageContent],
    Field(discriminator="type"),
]
"""
Discriminated union to ensure proper ser/deser of MessageContent

Note: This is a temporary workaround until the handling of plugin `BaseModel`
Agent Spec classes is improved
"""


class PluginMessage(BaseModel):
    """
    Messages are an exchange medium between the user, LLM agent, and controller logic.
    This helps determining who provided what information.
    """

    role: Literal["user", "assistant", "system"]
    """Role of the sender of the message. Can be `user`, `system` or `assistant`"""
    contents: List[PluginAnyContent] = Field(default_factory=list)
    """Message content. Is a list of chunks with potentially different types"""
    tool_requests: Optional[List[PluginToolRequest]] = None
    """
    A list of ``ToolRequest`` objects representing the tools invoked as part
    of this message. Each request includes the tool's name, arguments,
    and a unique identifier.
    """
    tool_result: Optional[PluginToolResult] = None
    """
    A ``ToolResult`` object representing the outcome of a tool invocation.
    It includes the returned content and a reference to the related tool request ID.
    """
    display_only: bool = False
    """If True, the message is excluded from any context. Its only purpose is to be displayed
    in the chat UI (e.g debugging message)"""
    sender: Optional[str] = None
    """Sender of the message in str format."""
    recipients: List[str] = Field(default_factory=list)
    """Recipients of the message in str format."""
    time_created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), repr=False)
    """Creation timestamp of the message."""
    time_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), repr=False)
    """Update timestamp of the message."""

    @field_serializer("time_created", mode="plain")
    def serialize_time_created(self, value: Any) -> Any:
        return value.isoformat()

    @field_validator("time_created", mode="before")
    @classmethod
    def deserialize_time_created(cls, v: Any) -> Any:
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v

    @field_serializer("time_updated", mode="plain")
    def serialize_time_updated(self, value: Any) -> Any:
        return value.isoformat()

    @field_validator("time_updated", mode="before")
    @classmethod
    def deserialize_time_updated(cls, v: Any) -> Any:
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v
