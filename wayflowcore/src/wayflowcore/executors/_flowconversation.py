# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from wayflowcore.contextproviders import ContextProvider
from wayflowcore.conversation import Conversation
from wayflowcore.executors._flowexecutor import FlowConversationExecutionState
from wayflowcore.flow import Flow
from wayflowcore.variable import Variable

if TYPE_CHECKING:
    from wayflowcore.executors._flowexecutor import FlowConversationExecutor
    from wayflowcore.steps.step import Step


@dataclass
class FlowConversation(Conversation):
    component: Flow
    state: FlowConversationExecutionState

    def _gather_flow_outputs(self) -> Dict[str, Any]:
        return FlowConversationExecutor.gather_flow_outputs(
            state=self.state,
            outputs_descriptions=self.component.output_descriptors_dict,
        )

    def _get_internal_context_value_for_step(self, assistant_step: "Step", key: str) -> Any:
        from wayflowcore.executors._flowexecutor import FlowConversationExecutor

        key = FlowConversationExecutor().make_key_for_step(assistant_step, key)
        return self.state.internal_context_key_values.get(key, None)

    def _put_internal_context_key_value(self, key: str, value: Any) -> None:
        self.state.internal_context_key_values[key] = value

    def _put_internal_context_key_value_for_step(
        self, assistant_step: "Step", key: str, value: Any
    ) -> None:
        from wayflowcore.executors._flowexecutor import FlowConversationExecutor

        key = FlowConversationExecutor().make_key_for_step(assistant_step, key)
        self.state.internal_context_key_values[key] = value

    def _get_current_context(self) -> Dict[str, Any]:
        return self.state.context_key_values

    def _put_current_context_key_value(self, key: str, value: Any) -> None:
        self.state.context_key_values[key] = value

    def _get_variable_value(self, variable: Variable) -> Any:
        if variable.name in self.state.variable_store:
            return self.state.variable_store[variable.name]
        raise ValueError(
            f"Variable {variable.name} does not exist in this conversation's variable store, "
            f"which contains the following variables: {list(self.state.variable_store.keys())}."
        )

    def _get_parent_conversation(self) -> Optional["Conversation"]:
        from wayflowcore.executors._flowexecutor import FlowConversationExecutor

        return FlowConversationExecutor().get_parent_conversation(self.state)

    def _get_step(self, step_name: str) -> "Step":
        return self.state.flow.steps[step_name]

    def _get_current_sub_conversation(
        self, step: "Step", sub_conversation_id: Optional[str] = None
    ) -> Optional["Conversation"]:
        from wayflowcore.executors._flowexecutor import FlowConversationExecutor

        key = FlowConversationExecutor().make_key_for_step(
            step, sub_conversation_id or FlowConversationExecutor._SUB_CONVERSATION_KEY
        )
        value = self.state.internal_context_key_values.get(key, None)
        return cast(Optional["Conversation"], value)

    def _update_sub_conversation(
        self,
        step: "Step",
        sub_conversation: "Conversation",
        sub_conversation_id: Optional[str] = None,
    ) -> None:
        from wayflowcore.executors._flowexecutor import FlowConversationExecutor

        key = FlowConversationExecutor().make_key_for_step(
            step, sub_conversation_id or FlowConversationExecutor._SUB_CONVERSATION_KEY
        )
        self._put_internal_context_key_value(key, sub_conversation)

    def _get_or_create_current_sub_conversation(
        self, step: "Step", flow: "Flow", inputs: Dict[str, Any]
    ) -> "FlowConversation":
        sub_conversation = self._get_current_sub_conversation(step)
        if sub_conversation is None:
            sub_conversation = self._create_sub_conversation(
                inputs=inputs,
                flow=flow,
                step=step,
            )

        if not isinstance(sub_conversation, FlowConversation):
            raise ValueError(
                f"Expected the sub_conversation to be a FlowConversation, but it is {sub_conversation.__class__.__name__}"
            )

        return sub_conversation

    def _create_sub_conversation(
        self,
        inputs: Dict[str, Any],
        flow: "Flow",
        step: "Step",
    ) -> "FlowConversation":
        from wayflowcore.executors._flowexecutor import FlowConversationExecutor

        return FlowConversationExecutor().create_sub_conversation(
            self,
            inputs,
            flow,
            step,
        )

    def _cleanup_sub_conversation(
        self, step: "Step", sub_conversation_id: Optional[str] = None
    ) -> None:
        from wayflowcore.executors._flowexecutor import FlowConversationExecutor

        key = FlowConversationExecutor().make_key_for_step(
            step, sub_conversation_id or FlowConversationExecutor._SUB_CONVERSATION_KEY
        )
        self.state.internal_context_key_values.pop(key, None)

    def _get_all_context_providers_from_parent_conversations(
        self,
    ) -> List["ContextProvider"]:
        from wayflowcore.flow import Flow

        all_context_providers: List["ContextProvider"] = []
        current_conversation: Optional[Conversation] = self
        while current_conversation:
            if not isinstance(current_conversation, FlowConversation):
                raise ValueError(
                    f"Illegal, found a non-flow parent conversation: {current_conversation}"
                )
            Flow._validate_list_of_context_providers_has_unique_output_descriptor_names(
                all_context_providers + current_conversation.state.context_providers
            )
            all_context_providers.extend(current_conversation.state.context_providers)
            current_conversation = current_conversation._get_parent_conversation()
        return all_context_providers

    def _get_all_sub_conversations(self) -> List[Conversation]:
        from wayflowcore.executors._flowexecutor import FlowConversationExecutor

        return FlowConversationExecutor.get_all_sub_conversations(self.state)

    @property
    def current_step_name(self) -> str:
        return self.state.current_step_name or "None"

    @property
    def _step_history(self) -> List[Optional[str]]:
        return self.state.step_history

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message_list={repr(self.message_list)}, state={repr(self.state)})"

    def __str__(self) -> str:
        result = f"State: {self.state}\nList of messages:\n"

        for i, message in enumerate(self.message_list.messages):
            message_str = dedent(
                f"""
            Message #{i}
            Message type: {message.message_type}
            Message content:\n
            {message.content}\n
            tool_requests: {message.tool_requests}
            tool_results: {message.tool_result}
            """
            )

            result += message_str
        return result

    @property
    def flow(self) -> "Flow":
        # backward compatibility
        return self.component

    @property
    def nesting_level(self) -> int:
        # backward compatibility
        return self.state.nesting_level
