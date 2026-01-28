# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Set, Union

from wayflowcore._metadata import MetadataType
from wayflowcore.conversation import Conversation
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.messagelist import Message, MessageList
from wayflowcore.models.ociclientconfig import OCIClientConfig
from wayflowcore.serialization.serializer import SerializableDataclassMixin, SerializableObject
from wayflowcore.tools import Tool

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation


logger = logging.getLogger(__name__)


@dataclass
class OciAgent(ConversationalComponent, SerializableDataclassMixin, SerializableObject):
    """
    An agent is a component that can do several rounds of conversation to solve a task.

    The agent is defined on the OCI console and this is only a wrapper to connect to it.
    It can be executed by itself, or be executed in a flow using an AgentNode, or used as a sub-agent of
    another WayFlow `Agent`.

    .. warning::
        ``OciAgent`` is currently in beta and may undergo significant changes.
        The API and behaviour are not guaranteed to be stable and may change in future versions.
    """

    DEFAULT_INITIAL_MESSAGE: ClassVar[str] = "Hi! How can I help you?"
    """str: Message the agent will post if no previous user message to welcome them."""

    agent_endpoint_id: str
    client_config: OCIClientConfig
    initial_message: str
    name: str
    description: str
    id: str
    __metadata_info__: MetadataType

    def __init__(
        self,
        agent_endpoint_id: str,
        client_config: OCIClientConfig,
        initial_message: str = DEFAULT_INITIAL_MESSAGE,
        name: Optional[str] = None,
        description: str = "",
        agent_id: Optional[str] = None,
        id: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Connects to a remote ``OciAgent``. The remote agent needs to be first created on the OCI console, this class
        only connects to existing remote agents.

        Parameters
        ----------
        agent_endpoint_id:
            A unique ID for the endpoint.
        client_config:
            oci client config to authenticate the OCI service
        initial_message:
            Initial message the agent will post if no previous user message.
            Default to ``OciGenAIAgent.DEFAULT_INITIAL_MESSAGE``.
        name:
            Name of the OCI agent.
        description:
            Description of the OCI agent. Is needed when the agent is used as the sub-agent of another agent.
        agent_id:
            Unique ID to define the agent
        """
        from wayflowcore.executors._ociagentconversation import OciAgentConversation
        from wayflowcore.executors._ociagentexecutor import OciAgentExecutor

        self.agent_endpoint_id = agent_endpoint_id
        self.client_config = client_config
        self.initial_message = initial_message

        super().__init__(
            name=IdGenerator.get_or_generate_name(name, length=8, prefix="oci_agent_"),
            description=description,
            id=id or agent_id,
            input_descriptors=[],
            output_descriptors=[],
            runner=OciAgentExecutor,
            conversation_class=OciAgentConversation,
            __metadata_info__=__metadata_info__,
        )

    def start_conversation(
        self,
        inputs: Optional[Dict[str, Any]] = None,
        messages: Union[None, str, Message, List[Message], MessageList] = None,
    ) -> "Conversation":
        """
        Initializes a conversation with the agent.

        Parameters
        ----------
        inputs:
            This argument is not used.
            It is included for compatibility with the Flow class.
        messages:
            Message list to which the agent will participate

        Returns
        -------
        Conversation:
            The conversation object of the agent.
        """
        from wayflowcore.executors._ociagentconversation import OciAgentConversation
        from wayflowcore.executors._ociagentexecutor import (
            OciAgentState,
            _init_oci_agent_client,
            _init_oci_agent_session,
        )

        if not isinstance(messages, MessageList):
            messages = MessageList.from_messages(messages=messages)

        _client = _init_oci_agent_client(self)

        return OciAgentConversation(
            component=self,
            state=OciAgentState(
                session_id=_init_oci_agent_session(self, _client),
                last_sent_message=-1,
                _client=_client,
            ),
            inputs=inputs or {},
            message_list=messages,
            status=None,
            conversation_id=IdGenerator.get_or_generate_id(None),
            name="oci_conversation",
            __metadata_info__={},
        )

    @property
    def agent_id(self) -> str:
        return self.id

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        return {}

    def _update_internal_state(self) -> None:
        # This method would need to be implemented if needed
        pass
