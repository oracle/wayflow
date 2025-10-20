# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from dataclasses import dataclass
from typing import TYPE_CHECKING, List

from wayflowcore.conversation import Conversation
from wayflowcore.executors._ociagentexecutor import OciAgentState
from wayflowcore.ociagent import OciAgent

if TYPE_CHECKING:
    from wayflowcore.contextproviders import ContextProvider
    from wayflowcore.conversation import Conversation


@dataclass
class OciAgentConversation(Conversation):
    component: OciAgent
    state: OciAgentState

    @property
    def current_step_name(self) -> str:
        return "oci_agent"

    def _get_all_context_providers_from_parent_conversations(self) -> List["ContextProvider"]:
        return []

    def _get_all_sub_conversations(self) -> List[Conversation]:
        return []

    def __repr__(self) -> str:
        return f"OciAgentConversation({self.get_messages()})"

    def __str__(self) -> str:
        return f"OciAgentConversation({self.get_messages()})"
