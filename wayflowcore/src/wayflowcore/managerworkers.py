# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union

from wayflowcore import Tool
from wayflowcore._metadata import MetadataType
from wayflowcore.agent import Agent
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.messagelist import MessageList
from wayflowcore.models import LlmModel
from wayflowcore.property import Property
from wayflowcore.serialization.serializer import SerializableDataclassMixin, SerializableObject
from wayflowcore.templates import PromptTemplate
from wayflowcore.templates._managerworkerstemplate import _DEFAULT_MANAGERWORKERS_CHAT_TEMPLATE

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.messagelist import Message

logger = logging.getLogger(__name__)


@dataclass(init=False)
class ManagerWorkers(ConversationalComponent, SerializableDataclassMixin, SerializableObject):
    group_manager: Union[LlmModel, Agent]
    workers: List[Agent]
    managerworkers_template: "PromptTemplate"
    input_descriptors: List["Property"]
    output_descriptors: List["Property"]

    name: str
    description: Optional[str]
    id: str

    def __init__(
        self,
        group_manager: Union[LlmModel, Agent],
        workers: List[Agent],
        managerworkers_template: Optional["PromptTemplate"] = None,
        input_descriptors: Optional[List["Property"]] = None,
        output_descriptors: Optional[List["Property"]] = None,
        name: Optional[str] = None,
        description: str = "",
        __metadata_info__: Optional[MetadataType] = None,
        id: Optional[str] = None,
    ) -> None:
        """
        Defines a ``ManagerWorkers`` conversational component.

        A ``ManagerWorkers`` is a multi-agent conversational component in which a group manager agent
        assigns tasks to worker agents.

        Parameters
        ---------
        workers:
            List of Agents that participate in the group. There should be at least one agent in the list.
        group_manager:
            Can either be an LLM or an agent that manages the group. If an LLM is passed, a manager agent
            will be created using that LLM.
        input_descriptors:
            Input descriptors of the ManagerWorkers. ``None`` means the ManagerWorks will resolve the input descriptors automatically in a best effort manner.

            .. note::

                In some cases, the static configuration might not be enough to infer them properly, so this argument allows to override them.

                If ``input_descriptors`` are specified, they will override the resolved descriptors but will be matched
                by ``name`` against them to check that types can be casted from one another, raising an error if they can't.
                If some expected descriptors are missing from the ``input_descriptors`` (i.e. you forgot to specify one),
                a warning will be raised and the ManagerWorkers is not guaranteed to work properly.
        output_descriptors:
            Output descriptors of the ManagerWorkers. ``None`` means the ManagerWorkers will resolve them automatically in a best effort manner.
            .. warning::

                Setting output descriptors for the Swarm is currently not supported.
        name:
            name of the ManagerWorkers, used for composition
        description:
            description of the ManagerWorkers, used for composition

        Example
        -------
        >>> from wayflowcore.agent import Agent
        >>> from wayflowcore.managerworkers import ManagerWorkers
        >>> addition_agent = Agent(name="addition_agent", description="Agent that can do additions", llm=llm, custom_instruction="You can do additions.")
        >>> multiplication_agent = Agent(name="multiplication_agent", description="Agent that can do multiplication", llm=llm, custom_instruction="You can do multiplication.")
        >>> division_agent = Agent(name="division_agent", description="Agent that can do division", llm=llm, custom_instruction="You can do division.")
        >>>
        >>> group = ManagerWorkers(
        ...     workers=[addition_agent, multiplication_agent, division_agent],
        ...     group_manager=llm,
        ... )
        >>> conversation = group.start_conversation()
        >>> conversation.append_user_message("Please compute 2*2 + 1")
        >>> status = conversation.execute()
        >>> answer = conversation.get_last_message().content
        >>> # The answer to 2*2 + 1 is 5.
        """

        from wayflowcore.executors._agenticpattern_helpers import _create_communication_tools
        from wayflowcore.executors._managerworkersconversation import ManagerWorkersConversation
        from wayflowcore.executors._managerworkersexecutor import (
            ManagerWorkersRunner,
            _create_manager_agent,
            _validate_agent_unicity,
        )

        if not (isinstance(group_manager, LlmModel) or isinstance(group_manager, Agent)):
            raise ValueError("Pass either an LLM model or an agent as the group manager.")

        if len(workers) == 0:
            raise ValueError("Cannot define a group with no worker agent.")

        if output_descriptors:
            raise ValueError(
                "`output_descriptors` is not supported yet for the ManagerWorkers pattern."
            )

        self.group_manager = group_manager
        self.manager_agent = _create_manager_agent(self.group_manager)

        self.workers = workers

        self._agent_by_name: Dict[str, "Agent"] = _validate_agent_unicity(
            self.workers + [self.manager_agent]
        )

        # Create send message tools for the group manager
        self._manager_communication_tools = _create_communication_tools()

        self.managerworkers_template = (
            managerworkers_template or _DEFAULT_MANAGERWORKERS_CHAT_TEMPLATE
        )

        super().__init__(
            name=IdGenerator.get_or_generate_name(name, prefix="managerworkers_", length=8),
            description=description,
            id=id,
            input_descriptors=input_descriptors or [],
            output_descriptors=output_descriptors or [],
            runner=ManagerWorkersRunner,
            conversation_class=ManagerWorkersConversation,
            __metadata_info__=__metadata_info__,
        )

    def start_conversation(
        self,
        inputs: Optional[Dict[str, Any]] = None,
        messages: Union[None, str, "Message", List["Message"], "MessageList"] = None,
        conversation_id: Optional[str] = None,
        conversation_name: Optional[str] = None,
    ) -> "Conversation":
        """
        Initializes a conversation with the managerworkers.

        Parameters
        ----------
        inputs:
            Dictionary of inputs. Keys are the variable identifiers and
            values are the actual inputs to start the main conversation.
        messages:
            Message list of the manager agent and the end-user.
        conversation_id:
            Conversation id of the main conversation.

        Returns
        -------
        Conversation:
            The conversation object of the managerworkers.
        """
        from wayflowcore.agentconversation import AgentConversation
        from wayflowcore.events.event import ConversationCreatedEvent
        from wayflowcore.events.eventlistener import record_event
        from wayflowcore.executors._managerworkersconversation import (
            ManagerWorkersConversation,
            ManagerWorkersConversationExecutionState,
        )

        if not isinstance(messages, MessageList):
            messages = MessageList.from_messages(messages=messages)

        if conversation_id is None:
            conversation_id = IdGenerator.get_or_generate_id(conversation_id)

        record_event(
            ConversationCreatedEvent(
                conversational_component=self,
                inputs=inputs or {},
                messages=messages,
                conversation_id=conversation_id,
                nesting_level=None,
            )
        )

        subconversations: Dict[str, AgentConversation] = {}
        subconversations[self.manager_agent.name] = self.manager_agent.start_conversation(
            inputs=inputs,
            messages=messages,
        )

        state = ManagerWorkersConversationExecutionState(
            current_agent_name=self.manager_agent.name,
            subconversations=subconversations,
        )

        return ManagerWorkersConversation(
            component=self,
            inputs={},
            message_list=messages,
            name=conversation_name or "managerworkers_conversation",
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
                self.manager_agent._referenced_tools_dict(recursive=True, visited_set=visited_set)
            )

            for agent in self.workers:
                all_tools.update(
                    agent._referenced_tools_dict(recursive=True, visited_set=visited_set)
                )

        return all_tools

    def _update_internal_state(self) -> None:
        # This method would need to be implemented if needed
        pass
