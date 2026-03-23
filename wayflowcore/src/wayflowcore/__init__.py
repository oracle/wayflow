# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from importlib.metadata import version

from .agent import Agent
from .checkpointing import (
    Checkpointer,
    CheckpointingInterval,
    ConversationCheckpoint,
    DatastoreCheckpointer,
    InMemoryCheckpointer,
    OracleDatabaseCheckpointer,
    PostgresCheckpointer,
    StorageConfig,
)
from .conversation import Conversation
from .flow import Flow
from .messagelist import Message, MessageList, MessageType
from .steps.step import Step
from .swarm import Swarm
from .tools import Tool, tool

__all__ = [
    "Agent",
    "CheckpointingInterval",
    "Checkpointer",
    "Conversation",
    "ConversationCheckpoint",
    "DatastoreCheckpointer",
    "Flow",
    "InMemoryCheckpointer",
    "Message",
    "MessageList",
    "MessageType",
    "OracleDatabaseCheckpointer",
    "PostgresCheckpointer",
    "Step",
    "StorageConfig",
    "Swarm",
    "tool",
    "Tool",
]

# Get the version from the information set in the setup of this package
__version__ = version("wayflowcore")
