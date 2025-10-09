# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import json
import logging
import re
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Literal, Optional, Tuple, Union

import jq
import json_repair

from wayflowcore._utils.formatting import (
    correct_arguments,
    parse_tool_call_using_ast,
    parse_tool_call_using_json,
)
from wayflowcore.messagelist import Message, TextContent
from wayflowcore.serialization.serializer import (
    SerializableDataclass,
    SerializableDataclassMixin,
    SerializableNeedToBeImplementedMixin,
    SerializableObject,
)
from wayflowcore.tools import Tool, ToolRequest

logger = logging.getLogger(__name__)


class OutputParser(SerializableNeedToBeImplementedMixin, SerializableObject, ABC):
    """Abstract base class for output parsers that process LLM outputs."""

    @abstractmethod
    def parse_output(self, content: Message) -> Message:
        """Parses the LLM raw output"""
        raise NotImplementedError()

    @abstractmethod
    async def parse_output_streaming(self, content: Any) -> Any:
        """
        Can parse the result returned by streaming
        By default does nothing until the message has been completely generated, but can implement specific stream methods if we want to stream something specific
        """
        raise NotImplementedError()


@dataclass
class RegexPattern(SerializableDataclassMixin, SerializableObject):
    """Represents a regex pattern and matching options for output parsing."""

    pattern: str
    """Regex pattern to match"""
    match: Literal["first", "last"] = "first"
    """Whether to take the first match or the last match"""
    flags: Optional[Union[int, re.RegexFlag]] = None
    """Potential regex flags to use (re.DOTALL for multiline matching for example)"""

    _can_be_referenced: ClassVar[bool] = False  # internal

    def __post_init__(self) -> None:
        # we want the flags as an int so that serialization works
        if self.flags is not None:
            self.flags = int(self.flags)

    @staticmethod
    def from_str(
        pattern: Union[str, "RegexPattern"], flags: Optional[Union[int, re.RegexFlag]] = re.DOTALL
    ) -> "RegexPattern":
        if isinstance(pattern, RegexPattern):
            return pattern
        return RegexPattern(pattern=pattern, flags=flags)


@dataclass
class RegexOutputParser(SerializableDataclass, OutputParser, SerializableObject):
    """
    Parses some text with Regex, potentially several regex to fill a dict

    Examples
    --------
    >>> import re
    >>> from wayflowcore.messagelist import Message
    >>> from wayflowcore.outputparser import RegexOutputParser, RegexPattern
    >>> RegexOutputParser(
    ...     regex_pattern=RegexPattern(pattern=r"Solution is: (.*)", flags=re.DOTALL)
    ... ).parse_output(Message(content="Solution is: Bern is the capital of Switzerland")).content
    'Bern is the capital of Switzerland'


    >>> RegexOutputParser(
    ...     regex_pattern={
    ...         'thought': "THOUGHT: (.*) ACTION:",
    ...         'action': "ACTION: (.*)",
    ...     }
    ... ).parse_output(Message("THOUGHT: blahblah ACTION: doing")).content
    '{"thought": "blahblah", "action": "doing"}'

    """

    regex_pattern: Union[str, RegexPattern, Dict[str, Union[str, RegexPattern]]]
    """Regex pattern to use"""
    strict: bool = True
    """Whether to return empty string if no match is found or return the raw text"""

    def __post_init__(self) -> None:
        if isinstance(self.regex_pattern, str):
            self.regex_pattern = RegexPattern.from_str(pattern=self.regex_pattern)
        elif isinstance(self.regex_pattern, dict):
            self.regex_pattern = {
                key: RegexPattern.from_str(value) for key, value in self.regex_pattern.items()
            }

    def parse_output(self, message: Message) -> Message:
        if any(not isinstance(content, TextContent) for content in message.contents):
            raise RuntimeError("Cannot use a Regex output parser with non message contents")
        if isinstance(self.regex_pattern, dict):
            content_dict = {
                key: self._parse_output(message.content, value)
                for key, value in self.regex_pattern.items()
            }
            content = json.dumps(content_dict)
        else:
            content = self._parse_output(message.content, self.regex_pattern)

        message = message.copy(content=content)
        return message

    def _parse_output(self, content: str, re_pattern: Union[RegexPattern, str]) -> str:
        if isinstance(re_pattern, str):
            re_pattern = RegexPattern.from_str(re_pattern)
        matches = re.findall(
            pattern=re_pattern.pattern, string=content, flags=re_pattern.flags or 0
        )
        if matches is None or len(matches) == 0:
            return "" if self.strict else content
        return str(matches[0 if re_pattern.match == "first" else -1])

    async def parse_output_streaming(self, content: Any) -> Any:
        raise NotImplementedError("RegexOutputParser does not support streaming outputs")


@dataclass
class JsonOutputParser(SerializableDataclass, OutputParser, SerializableObject):
    """Parses output as JSON, repairing and serializing as needed."""

    properties: Optional[Dict[str, str]] = None
    """Dictionary of property names and jq queries to manipulate the loaded JSON"""

    def parse_output(self, content: Message) -> Message:
        raw_text = content.content
        json_dict = json_repair.loads(raw_text)
        response_as_txt = json.dumps(json_dict)

        if self.properties is not None:
            response_as_dict = {}
            for output_name, output_jq_query in self.properties.items():
                try:
                    new_value = jq.compile(output_jq_query).input_text(response_as_txt).first()
                    response_as_dict[output_name] = new_value
                except Exception as e:
                    logger.debug("Could not parse: %s", e)
            response_as_txt = json.dumps(response_as_dict)

        return content.copy(content=response_as_txt)

    async def parse_output_streaming(self, content: Any) -> Any:
        raise NotImplementedError("JsonOutputParser does not support streaming outputs")


@dataclass
class ToolOutputParser(SerializableDataclass, OutputParser):
    """Base parser for tool requests"""

    tools: Optional[List[Tool]] = None

    def parse_output(self, message: Message) -> Message:
        """Separates the raw output into thoughts and calls, and then parses the calls into ToolRequests"""
        if message.tool_requests is not None:
            return message

        try:
            # 1. we parse the output into thoughts and tool calls
            thoughts, raw_tool_calls = self.parse_thoughts_and_calls(message.content)

            # 2. we parse tool calls
            tool_requests = self.parse_tool_request_from_str(raw_tool_calls)
        except Exception:
            logger.debug("Parsing of message content into tool failed.", exc_info=True)
            thoughts, tool_requests = "", []

        # 3. if found, we change the type of the message
        if len(tool_requests) > 0:
            message = message.copy(
                tool_requests=tool_requests,
                content=thoughts,
            )
            logger.debug("Raw tool call: %s, %s", tool_requests, self.tools)

        if message.tool_requests is None or self.tools is None:
            return message

        # correct types if necessary
        tools_by_name: Dict[str, Tool] = {tool.name: tool for tool in self.tools}

        tool_requests = []
        for tool_request in message.tool_requests:
            if tool_request.name not in tools_by_name:
                # model hallucinated a tool
                tool_requests.append(tool_request)
            else:
                tool_requests.append(
                    ToolRequest(
                        name=tool_request.name,
                        args=correct_arguments(
                            tool_request.args, tools_by_name[tool_request.name].parameters
                        ),
                        tool_request_id=tool_request.tool_request_id,
                    )
                )

        return message.copy(tool_requests=tool_requests)

    def with_tools(self, tools: Optional[List[Tool]]) -> "ToolOutputParser":
        """Enhances the tool parser with some validation of the parsed tool calls according to specific tools"""
        self_copy = deepcopy(self)
        self_copy.tools = tools
        return self_copy

    def parse_thoughts_and_calls(self, raw_txt: str) -> Tuple[str, str]:
        """Default function to separate thoughts and tool calls"""
        return "", raw_txt

    @abstractmethod
    def parse_tool_request_from_str(self, raw_txt: str) -> List[ToolRequest]:
        raise NotImplementedError()

    async def parse_output_streaming(self, content: Any) -> Any:
        raise NotImplementedError("ToolOutputParser does not support streaming outputs")


class JsonToolOutputParser(ToolOutputParser):
    """Parses tool requests from JSON-formatted strings."""

    def parse_tool_request_from_str(self, raw_txt: str) -> List[ToolRequest]:
        """Parses tool calls of the format '{"name":"some_tool", "parameters": {...}}'"""
        return parse_tool_call_using_json(raw_txt)


class PythonToolOutputParser(ToolOutputParser):
    """Parses tool requests from Python function call syntax."""

    def parse_tool_request_from_str(self, raw_txt: str) -> List[ToolRequest]:
        """Parses tool calls of the format 'some_tool(arg1=...)'"""
        return parse_tool_call_using_ast(raw_txt)
