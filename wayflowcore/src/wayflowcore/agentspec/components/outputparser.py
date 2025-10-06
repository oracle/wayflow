# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import re
from typing import Any, Dict, List, Literal, Optional, Union

from pyagentspec.component import Component
from pyagentspec.tools import Tool
from pydantic import BaseModel, SerializeAsAny

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)


class PluginRegexPattern(BaseModel):
    """Represents a regex pattern and matching options for output parsing."""

    pattern: str
    """Regex pattern to match"""
    match: Literal["first", "last"] = "first"
    """Whether to take the first match or the last match"""
    flags: Optional[Union[re.RegexFlag, int]] = None
    """Potential regex flags to use (re.DOTALL for multiline matching for example)"""

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        # we want the flags as an int so that serialization works
        if hasattr(self, "flags") and self.flags is not None:
            self.flags = int(self.flags)

    @staticmethod
    def from_str(pattern: Union[str, "PluginRegexPattern"]) -> "PluginRegexPattern":
        if isinstance(pattern, PluginRegexPattern):
            return pattern
        return PluginRegexPattern(pattern=pattern, flags=int(re.DOTALL))


class PluginOutputParser(Component):
    """Abstract base class for output parsers that process LLM outputs."""


class PluginRegexOutputParser(PluginOutputParser):
    """Parses some text with Regex, potentially several regex to fill a dict"""

    regex_pattern: Union[Dict[str, Union[str, PluginRegexPattern]], PluginRegexPattern, str]
    """Regex pattern to use"""
    strict: bool = True
    """Whether to return empty string if no match is found or return the raw text"""

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if not hasattr(self, "regex_pattern"):
            # partial build
            return
        if isinstance(self.regex_pattern, str):
            self.regex_pattern = PluginRegexPattern.from_str(pattern=self.regex_pattern)
        elif isinstance(self.regex_pattern, dict):
            self.regex_pattern = {
                key: PluginRegexPattern.from_str(value) for key, value in self.regex_pattern.items()
            }


class PluginJsonOutputParser(PluginOutputParser):
    """Parses output as JSON, repairing and serializing as needed."""

    properties: Optional[Dict[str, str]] = None
    """Dictionary of property names and jq queries to manipulate the loaded JSON"""


class PluginToolOutputParser(PluginOutputParser):
    """Base parser for tool requests"""

    tools: Optional[List[SerializeAsAny[Tool]]] = None


class PluginJsonToolOutputParser(PluginToolOutputParser):
    """Parses tool requests from JSON-formatted strings."""


class PluginPythonToolOutputParser(PluginToolOutputParser):
    """Parses tool requests from Python function call syntax."""


class PluginReactToolOutputParser(PluginToolOutputParser):
    """Parses ReAct-style tool requests."""


OUTPUTPARSER_PLUGIN_NAME = "OutputParserPlugin"

outputparser_serialization_plugin = PydanticComponentSerializationPlugin(
    name=OUTPUTPARSER_PLUGIN_NAME,
    component_types_and_models={
        PluginRegexOutputParser.__name__: PluginRegexOutputParser,
        PluginJsonOutputParser.__name__: PluginJsonOutputParser,
        PluginToolOutputParser.__name__: PluginToolOutputParser,
        PluginJsonToolOutputParser.__name__: PluginJsonToolOutputParser,
        PluginPythonToolOutputParser.__name__: PluginPythonToolOutputParser,
        PluginReactToolOutputParser.__name__: PluginReactToolOutputParser,
    },
)

outputparser_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=OUTPUTPARSER_PLUGIN_NAME,
    component_types_and_models={
        PluginRegexOutputParser.__name__: PluginRegexOutputParser,
        PluginJsonOutputParser.__name__: PluginJsonOutputParser,
        PluginToolOutputParser.__name__: PluginToolOutputParser,
        PluginJsonToolOutputParser.__name__: PluginJsonToolOutputParser,
        PluginPythonToolOutputParser.__name__: PluginPythonToolOutputParser,
        PluginReactToolOutputParser.__name__: PluginReactToolOutputParser,
    },
)
