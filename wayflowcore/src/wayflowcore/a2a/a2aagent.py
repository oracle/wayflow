# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Set, Union
from warnings import warn

from wayflowcore._metadata import MetadataType
from wayflowcore.component import DataclassComponent
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.messagelist import Message, MessageList
from wayflowcore.serialization.serializer import SerializableDataclassMixin, SerializableObject
from wayflowcore.tools import Tool

if TYPE_CHECKING:
    from wayflowcore.executors._a2aagentconversation import A2AAgentConversation

logger = logging.getLogger(__name__)


@dataclass
class A2ASessionParameters(SerializableDataclassMixin, SerializableObject):
    """
    Configuration parameters for an A2A session, controlling polling timeout and retry behavior.

    This class defines the settings used during agent-to-agent communication sessions,
    particularly for polling and timeout behavior when waiting for responses from a remote server.

    Parameters
    ----------
    timeout:
        The maximum time in seconds to wait for a response before considering the session timed out.
        Defaults to 60.0 seconds.
    poll_interval:
        The time interval in seconds between polling attempts to check for a response from the server.
        Defaults to 2.0 seconds.
    max_retries:
        The maximum number of retry attempts to establish a connection or receive a response before
        giving up. Defaults to 5 retries.
    """

    _can_be_referenced: ClassVar[bool] = False
    timeout: float = 60.0
    poll_interval: float = 2.0
    max_retries: int = 5

    def __post_init__(self) -> None:
        if self.timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self.timeout}")
        if self.poll_interval <= 0:
            raise ValueError(f"poll_interval must be positive, got {self.poll_interval}")
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be non-negative, got {self.max_retries}")


@dataclass
class A2AConnectionConfig(DataclassComponent):
    """
    Configuration settings for establishing a connection in agent-to-agent (A2A) communication.

    This class encapsulates the necessary parameters to set up HTTP connections with a remote server,
    including timeout settings and security configurations for SSL/TLS.

    Parameters
    ----------
    timeout:
        The maximum time in seconds to wait for HTTP requests to complete before timing out.
        Defaults to 600.0 seconds.
    headers:
        A dictionary of HTTP headers to include in requests sent to the server.
        Defaults to None, meaning no additional headers are sent.
    verify:
        Determines whether the client verifies the server's SSL certificate, enabling HTTPS.
        If True, the client will verify the server's identity using the provided `ssl_ca_cert`.
        If False, disables SSL verification (not recommended for production environments).
    key_file:
        Path to the client's private key file in PEM format, used for mTLS authentication.
        If None, mTLS cannot be performed. Defaults to None.
    cert_file:
        Path to the client's certificate chain file in PEM format, used for mTLS authentication.
        If None, mTLS cannot be performed. Defaults to None.
    ssl_ca_cert:
        Path to the trusted CA certificate file in PEM format, used to verify the server's identity.
        If None, the system's certificate store is used. Defaults to None.
    """

    timeout: float = 600.0
    headers: Optional[Dict[str, str]] = None
    verify: bool = True
    key_file: Optional[str] = None
    cert_file: Optional[str] = None
    ssl_ca_cert: Optional[str] = None

    def __post_init__(self) -> None:
        import os

        if self.timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self.timeout}")
        if self.verify:
            if self.key_file and not os.path.isfile(self.key_file):
                raise ValueError(f"key_file path does not exist: {self.key_file}")
            if self.cert_file and not os.path.isfile(self.cert_file):
                raise ValueError(f"cert_file path does not exist: {self.cert_file}")
            if self.ssl_ca_cert and not os.path.isfile(self.ssl_ca_cert):
                raise ValueError(f"ssl_ca_cert path does not exist: {self.ssl_ca_cert}")
        else:
            warn(
                "SSL verification is disabled. This is not recommended for production environments."
            )


@dataclass
class A2AAgent(ConversationalComponent, SerializableDataclassMixin, SerializableObject):
    """
    An agent that facilitates agent-to-agent (A2A) communication with a remote server agent for conversational tasks.

    The ``A2AAgent`` serves as a client-side wrapper to establish and manage connections with a server-side agent
    through a specified URL. It handles the setup of HTTP connections, including security configurations for mutual
    TLS (mTLS), and manages conversational interactions with the remote agent.

    Parameters
    ----------
    id:
        A unique identifier for the agent.
    name:
        The name of the agent, often used for identification in conversational contexts.
    description:
        A brief description of the agent's purpose or functionality.
    agent_url:
        The URL of the remote server agent to connect to.
    connection_config:
        Configuration settings for establishing HTTP connections, including timeout and security parameters.
    session_parameters:
        Parameters controlling session behavior such as polling timeouts and retry logic.

    .. note::
        ``A2AAgent`` is specifically designed for agent-to-agent communication and requires a valid server
        endpoint to function properly. Ensure the provided URL and connection configurations are correct
        to avoid connection issues.
    """

    id: str
    name: str
    description: str
    agent_url: str
    connection_config: A2AConnectionConfig
    session_parameters: A2ASessionParameters
    __metadata_info__: MetadataType

    def __init__(
        self,
        agent_url: str,
        connection_config: A2AConnectionConfig,
        session_parameters: Optional[A2ASessionParameters] = None,
        name: Optional[str] = None,
        description: str = "",
        id: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Initializes an ``A2AAgent`` to connect with a remote server agent.

        This sets up the agent with the necessary connection details to interact with
        a server agent at the specified URL.

        Parameters
        ----------
        agent_url:
            The URL of the server agent to connect to. Must be a valid URL with scheme and netloc.
        connection_config:
            Configuration settings for establishing HTTP connections.
        session_parameters:
            Parameters controlling session behavior such as polling timeouts and retry logic.
            Defaults to an instance of `A2ASessionParameters` with default values.
        name:
            Optional name for the agent. If not provided, a default name with prefix
            ``a2a_agent_`` is generated. Defaults to None.
        description:
            Description of the agent's purpose or functionality. Defaults to an empty string.
        id:
            Optional unique identifier for the agent. If not provided, one is generated.

        Raises
        ------
        ValueError:
            If the provided ``agent_url`` is not a valid URL.
        TypeError:
            If the provided ``agent_url`` is not a string.
        """

        from urllib.parse import urlparse

        from wayflowcore.executors._a2aagentconversation import A2AAgentConversation
        from wayflowcore.executors._a2aagentexecutor import A2AAgentExecutor
        from wayflowcore.mcp.clienttransport import _HttpxClientFactory

        # Validate agent_url
        try:
            result = urlparse(agent_url)
            if not all([result.scheme, result.netloc]):
                raise ValueError(f"Invalid URL provided for agent_url: {agent_url}")
        except Exception as e:
            raise ValueError(f"Invalid URL provided for agent_url: {agent_url} - {str(e)}")
        self.agent_url = agent_url

        # Set connection_config
        self.connection_config = connection_config

        # Set session_parameters
        if session_parameters is None:
            session_parameters = A2ASessionParameters()
        self.session_parameters = session_parameters

        # Initialize HTTP client factory with validated configuration
        self._http_factory = _HttpxClientFactory(
            verify=connection_config.verify,
            key_file=connection_config.key_file,
            cert_file=connection_config.cert_file,
            ssl_ca_cert=connection_config.ssl_ca_cert,
        )

        # Initialize base class with provided or generated values
        super().__init__(
            name=IdGenerator.get_or_generate_name(name, length=8, prefix="a2a_agent_"),
            description=description,
            id=id,
            input_descriptors=[],
            output_descriptors=[],
            runner=A2AAgentExecutor,
            conversation_class=A2AAgentConversation,
            __metadata_info__=__metadata_info__,
        )

    def start_conversation(
        self,
        inputs: Optional[Dict[str, Any]] = None,
        messages: Union[None, str, Message, List[Message], MessageList] = None,
    ) -> "A2AAgentConversation":
        """
        Initiates a new conversation with the remote server agent.

        Creates and returns a conversation instance tied to this agent, optionally initialized
        with input data and a message history.

        Parameters
        ----------
        inputs:
            Optional dictionary of initial input data for the conversation. Defaults to an empty
            dictionary if not provided.
        messages:
            Optional initial message list for the conversation. Can be either a ``MessageList``
            or a list of ``Message`` objects. Defaults to an empty ``MessageList`` if not provided.

        Returns
        -------
        A2AAgentConversation:
            A new conversation object associated with this agent.
        """
        from wayflowcore.executors._a2aagentconversation import A2AAgentConversation
        from wayflowcore.executors._a2aagentexecutor import A2AAgentState

        if not isinstance(messages, MessageList):
            messages = MessageList.from_messages(messages=messages)

        return A2AAgentConversation(
            component=self,
            state=A2AAgentState(last_message_idx=-1),
            inputs=inputs or {},  # Inputs are ignored in execution
            message_list=messages,
            status=None,
            conversation_id=IdGenerator.get_or_generate_id(None),
            name="a2a_conversation",
            __metadata_info__={},
        )

    @property
    def agent_id(self) -> str:
        return self.id

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        return {}
