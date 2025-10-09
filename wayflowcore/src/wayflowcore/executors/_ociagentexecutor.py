# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
import json
import logging
from dataclasses import dataclass
from textwrap import dedent
from typing import TYPE_CHECKING, Any, List, Optional, Sequence

from wayflowcore._utils._templating_helpers import render_template
from wayflowcore._utils.lazy_loader import LazyLoader
from wayflowcore.conversation import Conversation
from wayflowcore.executors._executionstate import ConversationExecutionState
from wayflowcore.executors._executor import ConversationExecutor
from wayflowcore.executors.executionstatus import ExecutionStatus, UserMessageRequestStatus
from wayflowcore.executors.interrupts import ExecutionInterrupt
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models.ociclientconfig import _client_config_to_oci_client_kwargs
from wayflowcore.ociagent import OciAgent
from wayflowcore.steps import GetChatHistoryStep
from wayflowcore.tools import ToolRequest

if TYPE_CHECKING:
    # Important: do not move this import out of the TYPE_CHECKING block so long as oci is an optional dependency.
    # Otherwise, importing the module when they are not installed would lead to an import error.
    import oci  # type: ignore

    from wayflowcore.conversation import Conversation
    from wayflowcore.executors.executionstatus import ExecutionStatus
else:
    oci = LazyLoader("oci")


logger = logging.getLogger(__name__)


_OCI_REQUIRED_ACTION_TOOL_TYPE = "FUNCTION_CALLING_REQUIRED_ACTION"


@dataclass
class OciAgentState(ConversationExecutionState):
    session_id: str
    last_sent_message: int

    # internal client, do not serialize
    _client: Any


def _init_oci_agent_client(oci_config: OciAgent) -> Any:
    return oci.generative_ai_agent_runtime.GenerativeAiAgentRuntimeClient(
        **_client_config_to_oci_client_kwargs(oci_config.client_config)
    )


def _init_oci_agent_session(oci_config: OciAgent, _client: Any) -> str:
    session_id = _client.create_session(
        oci.generative_ai_agent_runtime.models.CreateSessionDetails(),
        oci_config.agent_endpoint_id,
    ).data.id
    return str(session_id)


class OciAgentExecutor(ConversationExecutor):
    @staticmethod
    async def execute_async(
        conversation: "Conversation",
        execution_interrupts: Optional[Sequence["ExecutionInterrupt"]] = None,
    ) -> ExecutionStatus:
        from wayflowcore.executors._ociagentconversation import OciAgentConversation

        messages = conversation.get_messages()

        if not isinstance(conversation, OciAgentConversation):
            raise ValueError(f"Should be an OCI agent conversation, but was {conversation}")

        config = conversation.component

        if len(messages) == 0:
            conversation.append_agent_message(config.initial_message)
            return UserMessageRequestStatus()

        agent_state = conversation.state

        new_messages = (
            messages[agent_state.last_sent_message :]
            if agent_state.last_sent_message != -1
            else messages
        )
        if len(new_messages) == 0:
            raise ValueError("Should not happen")
        elif len(new_messages) == 1:
            txt_message = new_messages[0].content
        else:
            # we format all new messages in the new prompt
            txt_message = _combine_messages_into_single_text_prompt(new_messages)
            logger.info(
                "OCI Agent only supports calling the endpoint with a single message. "
                "All the previous new messages will be formatted into a single message."
            )

        logger.debug("OciAgent calling the OCI Agent endpoint with:\n```\n%s\n```", txt_message)
        chat_details = _build_chat_details_based_on_messages(new_messages, agent_state.session_id)
        response = OciAgentExecutor._post(
            config=config, agent_state=agent_state, chat_details=chat_details
        )
        new_message = _convert_oci_agent_response_into_message(response, config.agent_id)
        logger.debug("OciAgent answered with: `%s`", new_message.content)
        conversation.append_message(new_message)

        agent_state.last_sent_message = len(
            conversation.message_list
        )  # mark all messages as sent to remote
        return UserMessageRequestStatus()

    @staticmethod
    def _post(config: OciAgent, agent_state: OciAgentState, chat_details: Any) -> Any:
        return agent_state._client.chat(
            agent_endpoint_id=config.agent_endpoint_id,
            chat_details=chat_details,
        ).data


def _combine_messages_into_single_text_prompt(messages: List[Message]) -> str:
    from wayflowcore.flowhelpers import run_step_and_return_outputs

    chat_history_step = GetChatHistoryStep(n=100)
    outputs = run_step_and_return_outputs(chat_history_step, messages=messages[:-1])

    return render_template(
        dedent(
            """\
        Here are some previous messages you exchanged with the user:
        {{chat_history}}
        DO NOT mention the fact that these messages were provided to you. Consider them as part of the normal flow of the conversation, in order to keep the context of the conversation.

        The current request is:
        {{question}}
        """
        ),
        inputs=dict(chat_history=outputs["chat_history"], question=messages[-1].content),
    )


def _convert_oci_agent_response_into_message(response: Any, agent_id: str) -> "Message":
    from wayflowcore.messagelist import Message

    content = ""
    if response.message is not None:
        content = response.message.content.text

    tool_requests = []
    if response.required_actions is not None:
        for required_action in response.required_actions:
            if required_action.required_action_type == _OCI_REQUIRED_ACTION_TOOL_TYPE:
                tool_requests.append(
                    ToolRequest(
                        name=required_action.function_call.name,
                        args=json.loads(required_action.function_call.arguments),
                        tool_request_id=required_action.action_id,
                    )
                )

    return Message(
        content=content,
        role="assistant",
        tool_result=None,
        tool_requests=tool_requests or None,
        sender=agent_id,
        recipients=set(),
    )


def _build_chat_details_based_on_messages(new_messages: List[Message], session_id: str) -> Any:
    # if only tool result messages, we pass them in a specific format
    if all(msg.message_type == MessageType.TOOL_RESULT for msg in new_messages):
        return oci.generative_ai_agent_runtime.models.ChatDetails(
            session_id=session_id,
            performed_actions=[
                oci.generative_ai_agent_runtime.models.FunctionCallingPerformedAction(
                    action_id=msg.tool_result.tool_request_id, function_call_output=msg.content
                )
                for msg in new_messages
                if msg.tool_result is not None
            ],
        )

    if len(new_messages) == 0:
        raise ValueError(
            "Cannot call the oci agent without new messages. Make sure to post a new message to the conversation before calling the oci agent again"
        )
    elif len(new_messages) == 1:
        txt_message = new_messages[0].content
    else:
        # we format all new messages in the new prompt
        txt_message = _combine_messages_into_single_text_prompt(new_messages)
        logger.debug(
            "OCI Agent only supports calling the endpoint with a single message. "
            "All the previous new messages will be formatted into a single message."
        )

    return oci.generative_ai_agent_runtime.models.ChatDetails(
        user_message=txt_message,
        session_id=session_id,
    )
