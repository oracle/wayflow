# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import warnings
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

from wayflowcore._metadata import MetadataType
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.conversationalcomponent import (
    ConversationalComponent,
    T,
    _MutatedConversationalComponent,
)
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.messagelist import MessageList
from wayflowcore.property import Property
from wayflowcore.serialization.serializer import SerializableDataclassMixin, SerializableObject
from wayflowcore.templates import PromptTemplate
from wayflowcore.templates._swarmtemplate import _DEFAULT_SWARM_CHAT_TEMPLATE
from wayflowcore.tools import ClientTool, Tool

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.messagelist import Message

logger = logging.getLogger(__name__)


class HandoffMode(Enum):
    """
    Controls how agents in a Swarm may delegate work to one another.
    This setting determines whether an agent is equipped with:

    * *send_message* — a tool for asking another agent to perform a sub-task and reply back.
    * *handoff_conversation* — a tool for transferring the full user–agent conversation to another agent.

    Depending on the selected mode, agents have different capabilities for delegation and collaboration.
    """

    NEVER = "never"
    """
    Agent is not equipped with the *handoff_conversation* tool.
    Delegation is limited to message-passing:

    * Agents *can* use *send_message* to request a sub-task from another agent.
    * Agents *cannot* transfer the user conversation to another agent.

    As a consequence, the ``first_agent`` always remains the primary point of contact with the user.
    """

    OPTIONAL = "optional"
    """
    Agents receive **both** *handoff_conversation* and *send_message* tool.
    This gives agents full flexibility:

    * They may pass a message to another agent and wait for a reply.
    * Or they may fully hand off the user conversation to another agent.

    Use this mode when you want agents to intelligently choose the most natural delegation strategy.
    """

    ALWAYS = "always"
    """
    Agents receive **only** the *handoff_conversation* tool.
    Message-passing is disabled:

    * Agents *must* hand off the user conversation when delegating work.
    * They cannot simply send a message and receive a response.

    This mode enforces a strict chain-of-ownership: whenever an agent involves another agent,
    it must transfer the full dialogue context. The next agent can either respond directly to the user
    or continue handing off the conversation to another agent.
    """


@dataclass(init=False)
class Swarm(ConversationalComponent, SerializableDataclassMixin, SerializableObject):

    first_agent: Agent
    relationships: List[Tuple[Agent, Agent]]
    handoff: Union[HandoffMode, bool]
    caller_input_mode: CallerInputMode
    swarm_template: "PromptTemplate"
    input_descriptors: List["Property"]
    output_descriptors: List["Property"]

    name: str
    description: Optional[str]
    id: str

    def __init__(
        self,
        first_agent: Agent,
        relationships: List[Tuple[Agent, Agent]],
        handoff: Union[HandoffMode, bool] = HandoffMode.OPTIONAL,
        caller_input_mode: CallerInputMode = CallerInputMode.ALWAYS,
        swarm_template: Optional[PromptTemplate] = None,
        input_descriptors: Optional[List["Property"]] = None,
        output_descriptors: Optional[List["Property"]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
        id: Optional[str] = None,
    ) -> None:
        """
        Defines a ``Swarm`` conversational component.

        A ``Swarm`` is a multi-agent conversational component in which each agent determines
        the next agent to be executed, based on a list of pre-defined relationships.

        Parameters
        ----------
        first_agent:
            The first ``Agent`` to interact with the human user.
        relationships:
            Determine the list of allowed interactions in the ``Swarm``.
            Each element in the list is a tuple ``(caller_agent, recipient_agent)``
            specifying that the ``caller_agent`` can query the ``recipient_agent``.

            Agents can delegate in two ways, depending on the ``handoff`` mode:

            * **Message passing** via *send_message* tool — the caller requests a sub-task and waits for the recipient to reply. Note the the recipient does *not* need to have a reverse relatiship (i.e (recipient_agent, caller_agent)) in order to send a response back to the caller.
            * **Conversation handoff** via *handoff_conversation* tool — the caller transfers the entire conversation history with the user to the recipient, who then becomes the new active agent speaking to the user.
        handoff:
            Specifies how agents are allowed to delegate work. See ``HandoffMode`` for full details.

            * ``HandoffMode.NEVER``: Agents can only use *send_message*. The ``first_agent`` is the only agent that can interact with the user.
            * ``HandoffMode.OPTIONAL``: Agents may either send messages or fully hand off the conversation. This provides the most flexibility and often results in natural delegation.
            * ``HandoffMode.ALWAYS``: Agents cannot send messages to other agents. Any delegation must be performed through *handoff_conversation*.

            .. note::

                A key benefit of using Handoff is the reduced response latency: While talking to other agents increases the "distance"
                between the human user and the current agent, transferring a conversation to another agent keeps this distance unchanged
                (i.e. the agent interacting with the user is different but the user is still the same). However, transferring the full conversation might increase the token usage.
        input_descriptors:
            Input descriptors of the swarm. ``None`` means the swarm will resolve the input descriptors automatically in a best effort manner.

            .. note::

                In some cases, the static configuration might not be enough to infer them properly, so this argument allows to override them.

                If ``input_descriptors`` are specified, they will override the resolved descriptors but will be matched
                by ``name`` against them to check that types can be casted from one another, raising an error if they can't.
                If some expected descriptors are missing from the ``input_descriptors`` (i.e. you forgot to specify one),
                a warning will be raised and the swarm is not guaranteed to work properly.
        output_descriptors:
            Output descriptors of the swarm. ``None`` means the swarm will resolve them automatically in a best effort manner.
        caller_input_mode:
            Whether the agent in swarm can ask the user for additional information or needs to handle the task internally within the swarm.
        name:
            name of the swarm, used for composition
        description:
            description of the swarm, used for composition
        id:
            ID of the Swarm

        Example
        -------
        >>> from wayflowcore.agent import Agent
        >>> from wayflowcore.swarm import Swarm
        >>> addition_agent = Agent(name="addition_agent", description="Agent that can do additions", llm=llm, custom_instruction="You can do additions.")
        >>> multiplication_agent = Agent(name="multiplication_agent", description="Agent that can do multiplication", llm=llm, custom_instruction="You can do multiplication.")
        >>> division_agent = Agent(name="division_agent", description="Agent that can do division", llm=llm, custom_instruction="You can do division.")
        >>>
        >>> swarm = Swarm(
        ...     first_agent=addition_agent,
        ...     relationships=[
        ...         (addition_agent, multiplication_agent),
        ...         (addition_agent, division_agent),
        ...         (multiplication_agent, division_agent),
        ...     ]
        ... )
        >>> conversation = swarm.start_conversation()
        >>> conversation.append_user_message("Please compute 2*2+1")
        >>> status = conversation.execute()
        >>> swarm_answer = conversation.get_last_message().content
        >>> # The answer to 2*2+1 is 5.
        """

        from wayflowcore.executors._agenticpattern_helpers import _create_communication_tools
        from wayflowcore.executors._swarmconversation import SwarmConversation
        from wayflowcore.executors._swarmexecutor import (
            SwarmRunner,
            _get_all_recipients_for_agent,
            _validate_agent_unicity,
            _validate_relationships_unicity,
        )

        if not relationships:
            raise ValueError(
                "Cannot define an `Swarm` with no relationships between the agents. Use an `Agent` instead."
            )

        self._agent_by_name: Dict[str, "Agent"] = _validate_agent_unicity(
            first_agent, relationships
        )
        _validate_relationships_unicity(relationships)

        if isinstance(handoff, bool):
            warnings.warn(
                "Passing a boolean to configure handoff is deprecated. "
                "Use a `HandoffMode` value instead. Booleans will be removed in a future release."
            )
            self.handoff = HandoffMode.OPTIONAL if handoff else HandoffMode.NEVER
        else:
            self.handoff = handoff

        # Creating send message tools for each agent
        self._communication_tools: Dict[str, List[ClientTool]] = {}
        for agent_name, agent in self._agent_by_name.items():
            self._communication_tools[agent_name] = []
            agent_recipients = _get_all_recipients_for_agent(relationships, agent)
            if not agent_recipients:
                logger.debug("Agent '%s' does not have any recipient", agent_name)
                continue

            send_message_tools = _create_communication_tools(self.handoff)
            self._communication_tools[agent_name].extend(send_message_tools)

        self.first_agent = first_agent
        self.relationships = relationships or []
        self.swarm_template = swarm_template or _DEFAULT_SWARM_CHAT_TEMPLATE
        self.caller_input_mode = caller_input_mode

        super().__init__(
            name=IdGenerator.get_or_generate_name(name, prefix="swarm_", length=8),
            description=description,
            id=id,
            input_descriptors=input_descriptors or [],
            output_descriptors=output_descriptors or [],
            runner=SwarmRunner,
            conversation_class=SwarmConversation,
            __metadata_info__=__metadata_info__,
        )

    def start_conversation(
        self,
        inputs: Optional[Dict[str, Any]] = None,
        messages: Union[None, str, "Message", List["Message"], MessageList] = None,
        conversation_id: Optional[str] = None,
        conversation_name: Optional[str] = None,
    ) -> "Conversation":
        from wayflowcore.executors._swarmconversation import (
            SwarmConversation,
            SwarmConversationExecutionState,
            SwarmThread,
            SwarmUser,
        )

        if not isinstance(messages, MessageList):
            messages = MessageList.from_messages(messages=messages)

        if conversation_id is None:
            conversation_id = IdGenerator.get_or_generate_id(conversation_id)

        main_thread = SwarmThread(
            caller=SwarmUser(), recipient_agent=self.first_agent, is_main_thread=True
        )
        agents_and_threads: Dict[str, Dict[str, SwarmThread]] = {}
        for caller_agent, recipient_agent in self.relationships:
            if caller_agent.name not in agents_and_threads:
                agents_and_threads[caller_agent.name] = {}

            agents_and_threads[caller_agent.name][recipient_agent.name] = SwarmThread(
                caller=caller_agent,
                recipient_agent=recipient_agent,
            )
        state = SwarmConversationExecutionState(
            main_thread=main_thread,
            agents_and_threads=agents_and_threads,
            context_providers=[],
            inputs=inputs,
            messages=messages,
        )
        return SwarmConversation(
            component=self,
            inputs=inputs or {},
            message_list=messages,
            name=conversation_name or "swarm_conversation",
            state=state,
            status=None,
            conversation_id=conversation_id,
            __metadata_info__={},
        )

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        all_tools = {}

        if recursive:
            all_tools.update(
                self.first_agent._referenced_tools_dict(recursive=True, visited_set=visited_set)
            )

            for agents in self.relationships:
                for agent in agents:
                    all_tools.update(
                        agent._referenced_tools_dict(recursive=True, visited_set=visited_set)
                    )

        return all_tools


class _MutatedSwarm(_MutatedConversationalComponent[T]):
    pass
