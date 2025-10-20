# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import warnings
from typing import Dict, Optional, Tuple

from wayflowcore._metadata import MetadataType
from wayflowcore.messagelist import MessageType
from wayflowcore.steps.getchathistorystep import GetChatHistoryStep, MessageSlice

from .flowcontextprovider import FlowContextProvider

GET_CHAT_HISTORY_STEP_NAME = "get_chat_history_step"


class ChatHistoryContextProvider(FlowContextProvider):
    def __init__(
        self,
        n: int = 10,
        which_messages: MessageSlice = MessageSlice.LAST_MESSAGES,
        offset: int = 0,
        message_types: Optional[Tuple[MessageType, ...]] = (MessageType.USER, MessageType.AGENT),
        output_template: Optional[str] = None,
        output_name: Optional[str] = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        """
        Context provider to get messages from the messages list e.g. last 4 messages and return it as output.
        The following parameters will be passed to the underlying ``GetChatHistoryStep``.

        Parameters
        ----------
        n:
            Number of messages to retrieve.
        which_messages:
            Name of the strategy to use to collect messages. Either ``last_messages`` or ``first_messages``
        offset:
            Number of messages to ignore in the given order. Must be a non-negative integer.
        message_types:
            Tuple specification of the ``MessageType`` to keep from the list of messages.
            If ``None``, collects all the messages from the history.
        output_template:
            Template to format the chat history.
            If string, will format the chat history messages into the template using jinja2 syntax.
            Unlike ``GetChatHistoryStep``, the template should only contain the ``chat_history`` jinja variable.
            If ``None``, will use the default one from ``GetChatHistorySteps``.
        output_name:
            Name of the output for the context provider, to be used in the calling flow's I/O system.
            This is *not* a parameter of the underlying ``GetChatHistoryStep``
            If not given, the output name is ``chat_history``.
        name:
            The name of the context provider

        Examples
        -------
        >>> from wayflowcore.contextproviders import ChatHistoryContextProvider
        >>> from wayflowcore.flowhelpers import create_single_step_flow
        >>> from wayflowcore.messagelist import MessageList, Message
        >>> from wayflowcore.steps import OutputMessageStep
        >>> context_provider = ChatHistoryContextProvider(
        ...     n=2, # will retrieve the last 5 messages
        ...     output_name="history",
        ... )
        >>> flow = create_single_step_flow(
        ...     OutputMessageStep("Chat history number: {{history}}"),
        ...     context_providers=[context_provider]
        ... )
        >>> message_list = MessageList([Message(f"Message {i+1}") for i in range(5)])
        >>> conversation = flow.start_conversation(messages=message_list)
        >>> execution_status = conversation.execute()
        >>> last_message = conversation.get_last_message()
        >>> # print(last_message.content)
        >>> # Chat history number:
        >>> # USER >> Message 4
        >>> # USER >> Message 5

        """
        from wayflowcore.controlconnection import ControlFlowEdge
        from wayflowcore.flow import Flow

        warnings.warn(
            "Usage of `ChatHistoryContextProvider` is deprecated from 25.2, and will be removed in 25.4. Please use the `ChatHistoryStep` and the `FlowContextProvider` instead.",
            DeprecationWarning,
        )

        self._getchathistorystep = GetChatHistoryStep(
            n=n,
            which_messages=which_messages,
            offset=offset,
            message_types=message_types,
            output_template=output_template or GetChatHistoryStep.DEFAULT_OUTPUT_TEMPLATE,
            output_mapping=(
                {GetChatHistoryStep.CHAT_HISTORY: output_name} if output_name is not None else None
            ),
        )
        flow = Flow(
            begin_step=self._getchathistorystep,
            steps={GET_CHAT_HISTORY_STEP_NAME: self._getchathistorystep},
            control_flow_edges=[
                ControlFlowEdge(source_step=self._getchathistorystep, destination_step=None)
            ],
        )
        self.output_name = output_name
        super().__init__(
            name=name,
            flow=flow,
            __metadata_info__=__metadata_info__,
            id=id,
            description=description,
        )

    @property
    def n(self) -> int:
        return self._getchathistorystep.n

    @property
    def which_messages(self) -> MessageSlice:
        return self._getchathistorystep.which_messages

    @property
    def offset(self) -> int:
        return self._getchathistorystep.offset

    @property
    def message_types(self) -> Optional[Tuple[MessageType, ...]]:
        return (
            tuple(self._getchathistorystep.message_types)
            if self._getchathistorystep.message_types is not None
            else None
        )

    @property
    def output_template(self) -> Optional[str]:
        return self._getchathistorystep.output_template

    @classmethod
    def get_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:

        return {
            **GetChatHistoryStep._get_step_specific_static_configuration_descriptors(),
            "output_name": str,
        }
