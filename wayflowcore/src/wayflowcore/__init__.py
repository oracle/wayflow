# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from importlib.metadata import version

from .agent import Agent
from .conversation import Conversation
from .flow import Flow
from .messagelist import Message, MessageList, MessageType
from .steps.step import Step
from .tools import Tool, tool

__all__ = [
    "Agent",
    "Conversation",
    "Flow",
    "Message",
    "MessageList",
    "MessageType",
    "Step",
    "tool",
    "Tool",
]

# Get the version from the information set in the setup of this package
__version__ = version("wayflowcore")
