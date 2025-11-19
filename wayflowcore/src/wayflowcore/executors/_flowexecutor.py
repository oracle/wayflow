# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

import dataclasses
import logging
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple, cast

from wayflowcore._utils.async_helpers import run_async_in_sync
from wayflowcore.conversation import Conversation
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.events import record_event
from wayflowcore.events.event import (
    FlowExecutionIterationFinishedEvent,
    FlowExecutionIterationStartedEvent,
)
from wayflowcore.events.eventlistener import _record_exception
from wayflowcore.executors._events.event import Event, EventType
from wayflowcore.executors._executionstate import ConversationExecutionState
from wayflowcore.executors._executor import ConversationExecutor, ExecutionInterruptedException
from wayflowcore.executors.executionstatus import (
    ExecutionStatus,
    FinishedStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.property import (
    Property,
    _cast_value_into,
    _get_python_type_str,
    _try_cast_str_value_to_type,
)
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.steps import CompleteStep
from wayflowcore.steps.step import Step, StepExecutionStatus
from wayflowcore.tracing.span import FlowExecutionSpan

if TYPE_CHECKING:
    from wayflowcore.contextproviders import ContextProvider
    from wayflowcore.controlconnection import ControlFlowEdge
    from wayflowcore.executors._flowconversation import FlowConversation
    from wayflowcore.executors.interrupts.executioninterrupt import ExecutionInterrupt
    from wayflowcore.flow import Flow
    from wayflowcore.serialization.context import DeserializationContext, SerializationContext

logger = logging.getLogger(__name__)


_IoKeyType = Tuple[str, str]
"""This is the type for keys in the flow state I/O dictionary"""

_IO_KEY_SEP = "#$#$#$"


@dataclass
class FlowConversationExecutionState(ConversationExecutionState):
    """Contains the states for a flow conversation, including the flow, internal context values and
    the dictionary for the input/output system."""

    flow: "Flow"
    current_step_name: Optional[str]

    # dictionary of input / output values that is passed as input to steps and updated given the outputs of steps.
    # This is useful in situations where the execution flow is looping or has cycles : the assistant can read the
    # (possibly-updated) inputs of previous steps on following iterations.
    input_output_key_values: Dict[_IoKeyType, Any]
    # The normal i-o dict contains what is expected to be inputs of upcoming node and is different from what
    # gets generated as output of the flow.
    # For example: if step a, b, and c generate outputs A, B, C and take no input, the outputs of flow a->b->c are A, B, C,
    # but the io dict stays empty because the flow has no edge & no node needing any inputs.
    _flow_output_value_dict: Dict[str, Any] = dataclasses.field(default_factory=dict)

    # variable kv store, scoped at the conversation level
    variable_store: Dict[str, Any] = dataclasses.field(default_factory=dict)

    # Key-value context store for context providers and computed context values.
    #
    # Examples of context providers are:
    # - current date,
    # - current user,
    # - latest messages in the conversation
    # - the content of a datastore or external database
    # The context are passed as inputs to steps and are recomputed on demand before the step
    # invocation such that they provide up-to-date info
    context_key_values: Dict[str, Any] = dataclasses.field(default_factory=dict)
    context_providers: List["ContextProvider"] = dataclasses.field(default_factory=list)

    step_history: List[Optional[str]] = dataclasses.field(default_factory=list)

    # conversation key-value context store (e.g. to store execution information for steps)
    # This should not be made global and need to stay (sub)flow specific!
    # This is quite internal, and should not be used to put information like
    # current date and so on
    internal_context_key_values: Dict[str, Any] = dataclasses.field(default_factory=dict)

    nesting_level: int = 0

    def _set_execution_interrupts(self, interrupts: Optional[Sequence[ExecutionInterrupt]]) -> None:
        # We might be in a sub conversation, in that case we inherit the interrupts from the parent conversation
        parent_conversation = self.get_parent_conversation()

        if parent_conversation is not None:
            interrupts = parent_conversation._get_interrupts()

        self.interrupts = self._resolve_execution_interrupts(interrupts)

    def get_parent_conversation(self) -> Optional[Conversation]:
        parent_conv = self.internal_context_key_values.get(
            FlowConversationExecutor._SUPER_CONVERSATION_KEY, None
        )
        return cast(Conversation, parent_conv) if parent_conv else None

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        from wayflowcore.serialization.serializer import serialize_to_dict

        internal_context_key_values = {}
        for k, v in self.internal_context_key_values.items():
            if k == FlowConversationExecutor._SUPER_CONVERSATION_KEY:
                pass
            elif isinstance(v, SerializableObject):
                internal_context_key_values[k] = serialize_to_dict(v, serialization_context)
            else:
                internal_context_key_values[k] = v

        return {
            "flow": serialize_to_dict(self.flow, serialization_context=serialization_context),
            "current_step_name": self.current_step_name,
            "input_output_key_values": {
                f"{step_name}{_IO_KEY_SEP}{output_name}": value
                for (step_name, output_name), value in self.input_output_key_values.items()
            },
            "_flow_output_value_dict": self._flow_output_value_dict,
            "variable_store": self.variable_store,
            "context_key_values": self.context_key_values,
            "context_providers": [
                serialize_to_dict(context_provider, serialization_context)
                for context_provider in self.context_providers
            ],
            "step_history": self.step_history,
            "internal_context_key_values": {
                context_key: self._serialize_context_value(
                    context_key, context_value, serialization_context
                )
                for context_key, context_value in self.internal_context_key_values.items()
            },
            "nesting_level": self.nesting_level,
            "events": [serialize_to_dict(event) for event in self.events],
            "_component_type": FlowConversationExecutionState.__name__,
        }

    @staticmethod
    def _serialize_context_value(
        context_key: str, context_value: Any, serialization_context: "SerializationContext"
    ) -> Any:
        from wayflowcore.serialization.serializer import serialize_to_dict

        if context_key == FlowConversationExecutor._SUPER_CONVERSATION_KEY:
            # we don't serialize super conversation, link will be put back by deserialization
            return None
        elif isinstance(context_value, SerializableObject):
            # we serialize wayflowcore objects
            return serialize_to_dict(context_value, serialization_context)
        else:
            # it's just a basic str or int
            return context_value

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        from wayflowcore.flow import Flow
        from wayflowcore.serialization.serializer import deserialize_from_dict

        state = FlowConversationExecutionState(
            flow=deserialize_from_dict(
                Flow, input_dict["flow"], deserialization_context=deserialization_context
            ),
            current_step_name=input_dict.get("current_step_name"),
            input_output_key_values={
                tuple(io_key_str.split(_IO_KEY_SEP)): value
                for io_key_str, value in input_dict.get("input_output_key_values", {}).items()
            },
            _flow_output_value_dict=input_dict.get("_flow_output_value_dict", {}),
            variable_store=input_dict.get("variable_store", {}),
            context_key_values=input_dict.get("context_key_values", {}),
            context_providers=input_dict.get("context_providers", []),
            step_history=input_dict.get("step_history", []),
            internal_context_key_values={
                k: cls._deserialize_context_value_from_dict(v, deserialization_context)
                for k, v in input_dict.get("internal_context_key_values", {}).items()
            },
            nesting_level=input_dict.get("nesting_level", 0),
        )
        # not init arg
        state.events = [
            deserialize_from_dict(Event, event_dict, deserialization_context)
            for event_dict in input_dict["events"]
        ]
        return state

    @classmethod
    def _deserialize_context_value_from_dict(
        cls, context_value: Any, deserialization_context: "DeserializationContext"
    ) -> Any:
        from wayflowcore.serialization.serializer import autodeserialize_from_dict

        if isinstance(context_value, dict) and (
            "_component_type" in context_value or "$ref" in context_value
        ):
            return autodeserialize_from_dict(context_value, deserialization_context)
        else:
            return context_value

    def _register_super_conversation(self, conversation: Conversation) -> None:
        """Need to register super conversation for double pointers"""
        for context_key in self.internal_context_key_values.keys():
            if context_key == FlowConversationExecutor._SUPER_CONVERSATION_KEY:
                # should register this conversation as super conversation
                self.internal_context_key_values[context_key] = conversation


class FlowConversationExecutor(ConversationExecutor):
    """
    Class for conversations between the user and the assistant.
    It basically executes the steps of the flow, keeps track of the execution
    state.
    If needed, it also generates a conversation ID so that we can uniquely identify different conversations.

    It holds a map of the "app context" and functions that can provide contextual values.
    The context map is refreshed before every step call, in case the values change that frequently
    """

    _SUPER_CONVERSATION_KEY = "super_conversation_key"
    _SUB_CONVERSATION_KEY = "sub_conversation_key"

    @staticmethod
    def make_key_for_step(assistant_step: Step, key: str) -> str:
        return str(assistant_step.id) + "_" + key

    @staticmethod
    def get_parent_conversation(state: FlowConversationExecutionState) -> Optional[Conversation]:
        return state.get_parent_conversation()

    @staticmethod
    def create_sub_conversation(
        conversation: FlowConversation,
        inputs: Dict[str, Any],
        flow: "Flow",
        step: Step,
        sub_conversation_id: Optional[str] = None,
    ) -> "FlowConversation":
        """
        Create a sub conversation for a given step.

        Arguments:
            conversation: FlowConversation
                Current flow conversation
            inputs: Dict[str, Any]
                inputs for the new conversation
            flow: Flow
                Flow on which to start the sub-conversation
            step: Step
                Step that is creating the sub-conversation. Needed so that step can find its own sub-conversation later
            sub_conversation_id: str
                A custom id to use for the sub-conversation. If None, a default suffix is used.
        """
        all_context_providers = conversation._get_all_context_providers_from_parent_conversations()
        all_context_provider_keys = {
            value_description.name
            for context_prov in all_context_providers
            for value_description in context_prov.get_output_descriptors()
        }

        inputs_not_from_context_providers = {
            k: v for k, v in inputs.items() if k not in all_context_provider_keys
        }

        sub_conversation = flow.start_conversation(
            inputs_not_from_context_providers,
            conversation_id=conversation.conversation_id,
            messages=conversation.message_list,
            nesting_level=conversation.state.nesting_level + 1,
            context_providers_from_parent_flow=all_context_provider_keys,
        )

        key = FlowConversationExecutor.make_key_for_step(
            step, sub_conversation_id or FlowConversationExecutor._SUB_CONVERSATION_KEY
        )
        conversation.state.internal_context_key_values[key] = sub_conversation
        sub_conversation._put_internal_context_key_value(
            FlowConversationExecutor._SUPER_CONVERSATION_KEY, conversation
        )

        return sub_conversation

    @staticmethod
    def cleanup_sub_conversation(
        state: FlowConversationExecutionState,
        step: Step,
    ) -> None:
        """
        Remove a subconversation saved in the internal context of the flow execution state, to cleanup the state after the subconversation is finished.
        """
        key = FlowConversationExecutor.make_key_for_step(
            step, FlowConversationExecutor._SUB_CONVERSATION_KEY
        )
        # We have to pop finished sub-conversations from the context store as other methods assume the conversation
        # (dict value) is not `None`.
        state.internal_context_key_values.pop(key, None)

    @staticmethod
    def get_current_sub_conversation(
        state: FlowConversationExecutionState,
        step: Step,
    ) -> Optional[Conversation]:
        """Get the current sub conversation of a given step"""
        key1 = FlowConversationExecutor.make_key_for_step(
            step, FlowConversationExecutor._SUB_CONVERSATION_KEY
        )
        sub_conv = state.internal_context_key_values.get(key1, None)
        return cast(Conversation, sub_conv) if sub_conv is not None else None

    @staticmethod
    def _get_context_provider_or_none_for_step(
        destination_step: Optional["Step"],
        destination_input: str,
        data_flow_edges: List[DataFlowEdge],
    ) -> Optional["ContextProvider"]:
        from wayflowcore.contextproviders import ContextProvider

        if destination_step is None:
            return None

        for data_edge in data_flow_edges:
            if (
                isinstance(data_edge.source_step, ContextProvider)
                and data_edge.destination_step is destination_step
                and data_edge.destination_input == destination_input
            ):
                return data_edge.source_step
        return None

    @staticmethod
    def _push_step_output_values_to_io_dict(
        io_value_dict: Dict[_IoKeyType, Any],
        source_step_name: str,
        data_flow_edges: List[DataFlowEdge],
        steps: Dict[str, "Step"],
        outputs: Dict[str, Any],
    ) -> None:
        """
        Given a source step name and step outputs, pushes the outputs to the destination
        steps using the list of data flow edges.
        """
        for data_flow_edge in data_flow_edges:
            if data_flow_edge.source_step is steps[source_step_name]:
                destination_step_name = next(
                    (
                        step_name
                        for step_name, s in steps.items()
                        if s is data_flow_edge.destination_step
                    ),
                    None,
                )
                if destination_step_name is None:
                    raise ValueError(
                        f"Could not find a name for the step '{data_flow_edge.destination_step}'"
                    )
                io_key = (destination_step_name, data_flow_edge.destination_input)
                io_value_dict[io_key] = outputs.get(data_flow_edge.source_output)

    @staticmethod
    def _push_step_outputs_to_flow_outputs(
        state: FlowConversationExecutionState,
        outputs: Dict[str, Any],
    ) -> None:
        """
        This method saves all outputs of steps and saves them in the execution state
        `_flow_output_value_dict`. Note that in the method `gather_flow_outputs` these outputs are
        filtered to include only the outputs of the flow.
        """
        if state.current_step_name is None:
            return
        for mapped_output_name, output_value in outputs.items():
            state._flow_output_value_dict[mapped_output_name] = output_value

    @staticmethod
    async def _get_input_value_or_default(
        conversation: FlowConversation,
        state: FlowConversationExecutionState,
        current_step_name: Optional[str],
        value_descriptor: Property,
        value_name: str,
    ) -> Any:
        """
        Attempt to get the desired value:
        1. Collect the value from a Context Provider, the I/O dict (checking for collisions) or a default value
        2. Cast the value to a desired type if necessary
        3. Validate the value type against the expected value type
        """
        if current_step_name is None:
            raise ValueError("Can't get value for `None` step")

        # 1. Collect the value from a Context Provider, I/O dict or default value
        context_provider = FlowConversationExecutor._get_context_provider_or_none_for_step(
            state.flow.steps[current_step_name], value_name, state.flow.data_flow_edges
        )
        if context_provider is None:
            context_provider = FlowConversationExecutor._find_context_provider_from_conversation(
                conversation, value_descriptor.name
            )
        io_value_key = (
            current_step_name,
            value_descriptor.name,
        )  # When IO dict of type Dict[_IoKeyType, Any]
        if context_provider is not None and io_value_key in state.input_output_key_values:
            # The following section is a workaround due to the fact that some input values of a sub-flow
            # might be filled by the dynamic value of a context provider from an outer flow.
            # With the introduction of the StartStep, that output is going to appear also as part of the
            # StartStep outputs, making the two collide.
            # As a temporary solution, we check that the output is coming from the StartStep
            # (i.e., it's an input of the flow), and if that's the case, we do not raise the exception,
            # but we will give precedence to the context provider output value instead.
            _start_step = state.flow.steps[state.flow.begin_step_name]
            _current_step = state.flow.steps[current_step_name]
            data_flow_edges_connecting_start_step_to_current_step = list(
                data_flow_edge
                for data_flow_edge in state.flow.data_flow_edges
                if _start_step is data_flow_edge.source_step
                and _current_step is data_flow_edge.destination_step
            )
            input_names_connected_to_start_steps = {
                data_flow_edge.destination_input
                for data_flow_edge in data_flow_edges_connecting_start_step_to_current_step
            }
            if value_descriptor.name not in input_names_connected_to_start_steps:
                raise ValueError(
                    f"Found the name: '{value_descriptor.name}' corresponding to both a context provider "
                    f"and a step output. You must change the name of the step output or of the context "
                    f"provider."
                )
        if context_provider is not None:
            value = await context_provider.call_async(conversation)
            state.context_key_values[value_name] = value
        elif io_value_key in state.input_output_key_values:
            value = state.input_output_key_values[io_value_key]
        else:
            if not value_descriptor.has_default:
                raise ValueError(
                    f"Step {current_step_name} with field {value_name} is not required but it does not have a default value"
                )
            value = value_descriptor.default_value

        # 2. Cast the value to a desired type if necessary
        if value is not None:
            value = _try_cast_str_value_to_type(value, value_descriptor)
        if value is not None and not value_descriptor.is_value_of_expected_type(value):
            # we cast, data edges should have checked types
            return _cast_value_into(value, value_descriptor)
        return value

    @staticmethod
    def _find_context_provider_from_conversation(
        conversation: Conversation, field_name: str
    ) -> Optional["ContextProvider"]:
        from wayflowcore.executors._flowconversation import FlowConversation

        # the subflow is allowed to have context providers with same output names as those in the parent flow
        # see test_output_message_step_correctly_uses_context_in_a_subflow
        current_conversation: Optional[Conversation] = conversation
        while current_conversation is not None:
            if not isinstance(current_conversation, FlowConversation):
                raise ValueError(
                    f"Illegal, found parent conversation that is not a flow conversation, {current_conversation}"
                )
            all_context_provider_output_names = {
                value_desc.name: context_prov
                for context_prov in current_conversation.state.context_providers
                for value_desc in context_prov.get_output_descriptors()
            }
            if field_name in all_context_provider_output_names:
                return all_context_provider_output_names[field_name]
            current_conversation = current_conversation._get_parent_conversation()
        return None

    @staticmethod
    def _gather_step_inputs(
        conversation: FlowConversation, state: FlowConversationExecutionState, current_step: Step
    ) -> Dict[str, Any]:
        return run_async_in_sync(
            FlowConversationExecutor._gather_step_inputs_async, conversation, state, current_step
        )

    @staticmethod
    async def _gather_step_inputs_async(
        conversation: FlowConversation, state: FlowConversationExecutionState, current_step: Step
    ) -> Dict[str, Any]:
        return {
            input_descriptor.name: await FlowConversationExecutor._get_input_value_or_default(
                conversation=conversation,
                state=state,
                current_step_name=state.current_step_name,
                value_descriptor=input_descriptor,
                value_name=input_descriptor.name,
            )
            for input_descriptor in current_step.input_descriptors
        }

    @staticmethod
    def gather_flow_outputs(
        state: FlowConversationExecutionState,
        outputs_descriptions: Dict[str, Property],
        fail_on_missing_value: bool = True,
    ) -> Dict[str, Any]:
        output_values = {}
        for output_name, output_descriptor in outputs_descriptions.items():
            try:
                value = state._flow_output_value_dict[output_name]
            except KeyError:
                if fail_on_missing_value:
                    raise KeyError(
                        f"Output flow value with name {output_name} is missing from the "
                        f"flow output value dictionary:\n{state._flow_output_value_dict}"
                    )
                value = None
            if value is not None:
                # Cast the value to expected type if necessary and validate type
                value = _try_cast_str_value_to_type(value, output_descriptor)

                if not output_descriptor.is_value_of_expected_type(value):
                    raise ValueError(
                        f"Found incorrect flow output value type for output with name '{output_name}'. "
                        f"Expected type: {output_descriptor.get_type_str()}\nbut got value of type: "
                        f"{_get_python_type_str(value)}. Please check the input value and ensure it "
                        "matches the expected type."
                    )

                output_values[output_name] = value
            elif (
                output_descriptor.default_value != None
                and output_descriptor.default_value is not Property.empty_default
            ):
                output_values[output_name] = output_descriptor.default_value
        return output_values

    @staticmethod
    def _writeback_step_outputs(
        step_outputs: Dict[str, Any],
        current_step: Step,
        yielding: bool,
        current_step_name: str,
    ) -> Dict[str, Any]:
        """
        Sanitize the step outputs before they are added to the I/O dict.

        For every expected step output:
        1. Attempt to use default value if missing from step outputs
        2. For non-yielding flows, validate output existence and type

        Returns
        -------
            The dictionary of sanitized step outputs.
        """
        sanitized_outputs = {}
        for output_descriptor in current_step.output_descriptors:
            if yielding and output_descriptor.name not in step_outputs:
                # We do not enforce all outputs to be present when a step yields, because it
                # self-loops
                continue
            if output_descriptor.name not in step_outputs:
                if not output_descriptor.has_default:
                    raise ValueError(
                        f"Field {output_descriptor.name} of current step {current_step_name} is required but has no default value"
                    )
                step_outputs[output_descriptor.name] = output_descriptor.default_value
                logger.debug(
                    f"Step `{current_step_name}` outputs did not contain a value for `{output_descriptor.name}`, filling it with default value: `{output_descriptor.default_value}`"
                )

            output_value = step_outputs[output_descriptor.name]

            # If the flow is not yielding, validate the output value type.
            # (if we are yielding, we might not be done with creating the final outputs)
            if (
                (not yielding)
                and output_value is not None
                and (not output_descriptor.is_value_of_expected_type(output_value))
            ):
                try:
                    output_value = _cast_value_into(output_value, output_descriptor)
                except Exception:
                    raise ValueError(
                        f"Expected a value of type {output_descriptor} but the output value "
                        f"named `{output_descriptor.name}` --> {output_value} has type {type(output_value)}. "
                        f"(step `{current_step_name}` outputs: {step_outputs})"
                    )

            sanitized_outputs[output_descriptor.name] = output_value

        additional_step_outputs = set(step_outputs.keys()).difference(sanitized_outputs.keys())
        if len(additional_step_outputs) > 0:
            warnings.warn(
                f"Found additional values ({additional_step_outputs}) that are not specified "
                f"in step `{current_step_name}` outputs ({current_step.output_descriptors}",
            )

        return sanitized_outputs

    @staticmethod
    def flow_state_or_throw(conversation: Conversation) -> FlowConversationExecutionState:
        from wayflowcore.executors._flowconversation import FlowConversation

        if not isinstance(conversation, FlowConversation):
            raise ValueError(
                f"Cannot run flow executor with non FlowConversation, {conversation}, {conversation.__class__.__name__}"
            )
        return conversation.state

    @staticmethod
    def get_next_step_name_from_branch(
        control_flow_edges: List["ControlFlowEdge"],
        current_step_name: str,
        steps: Dict[str, Step],
        branch_taken: str,
    ) -> Optional[str]:
        from wayflowcore.flow import _get_step_name_from_step

        if branch_taken == Step.BRANCH_SELF:
            return current_step_name

        step = steps[current_step_name]

        control_flow_edges_of_step = [
            control_flow_edge
            for control_flow_edge in control_flow_edges
            if control_flow_edge.source_step is step
        ]

        # There's no control flow edge going out of the current step
        # Since we assume the Flow to be valid, this must be a CompleteStep
        if len(control_flow_edges_of_step) == 0:
            return None

        for control_flow_edge in control_flow_edges_of_step:
            if control_flow_edge.source_branch == branch_taken:
                if control_flow_edge.destination_step is None:
                    return None

                return _get_step_name_from_step(control_flow_edge.destination_step, steps)

        configured_edges = [e.source_branch for e in control_flow_edges_of_step]
        raise ValueError(
            f"Step '{current_step_name}' completed with branch '{branch_taken}' which is not part"
            f" of the configured control flow edges: {configured_edges}"
        )

    @staticmethod
    async def execute_async(
        conversation: Conversation,
        execution_interrupts: Optional[Sequence[ExecutionInterrupt]] = None,
    ) -> ExecutionStatus:
        """
        Main logic for the Flow execution.

        Logic for conducting the next iteration of Step execution:
        1. Get the current step (to be executed during this iteration)
        2. Gather the step inputs, using the default value if there is one and it does not exist yet
        3. Invoke the step with the step inputs
        4. Determine the next step to transition to based on the next branch and the transition dictionary
        5. Sanitize the step outputs i.e.
            - Check for existence and type correctness when needed, using the default value if necessary
            - Map the keys using the step input_mapping if specified
        6. Update the I/O dict with the sanitized step outputs
        7. Update the current step with the next step to execute

        Logic for gathering flow outputs upon flow completion:
        For all expected flow outputs, attempt to collect the output value from:
        1. I/O dict or Context Providers
        2. Default value from value descriptor
        """
        from wayflowcore.executors._flowconversation import FlowConversation

        if not isinstance(conversation, FlowConversation):
            raise ValueError(
                f"the provided conversation to a flow must be of type FlowConversation but was {type(conversation).__name__}"
            )

        with FlowExecutionSpan(conversational_component=conversation.component) as span:
            execution_status = await FlowConversationExecutor._execute_flow(
                conversation, execution_interrupts
            )
            span.record_end_span_event(execution_status=execution_status)
        return execution_status

    @staticmethod
    async def _execute_flow(
        conversation: "FlowConversation",
        execution_interrupts: Optional[Sequence[ExecutionInterrupt]] = None,
    ) -> ExecutionStatus:
        """
        Main logic for the Flow execution.

        Logic for conducting the next iteration of Step execution:
        1. Get the current step (to be executed during this iteration)
        2. Gather the step inputs, using the default value if there is one and it does not exist yet
        3. Invoke the step with the step inputs
        4. Determine the next step to transition to based on the next branch and the transition dictionary
        5. Sanitize the step outputs i.e.
            - Check for existence and type correctness when needed, using the default value if necessary
            - Map the keys using the step input_mapping if specified
        6. Update the I/O dict with the sanitized step outputs
        7. Update the current step with the next step to execute

        Logic for gathering flow outputs upon flow completion:
        For all expected flow outputs, attempt to collect the output value from:
        1. I/O dict or Context Providers
        2. Default value from value descriptor
        """
        logger.debug("Interrupts received: %s", execution_interrupts)
        flow_state = conversation.state
        flow_state._set_execution_interrupts(execution_interrupts)
        last_complete_step_name_executed = None

        try:
            FlowConversationExecutor._register_event(
                state=flow_state,
                conversation=conversation,
                event_type=EventType.EXECUTION_START,
            )

            while flow_state.current_step_name is not None:

                FlowConversationExecutor._register_event(
                    state=flow_state,
                    conversation=conversation,
                    event_type=EventType.EXECUTION_LOOP_ITERATION_START,
                )

                record_event(
                    FlowExecutionIterationStartedEvent(
                        execution_state=conversation.state,
                    )
                )

                flow_state.step_history.append(flow_state.current_step_name)

                if not (flow_state.current_step_name in flow_state.flow.steps):
                    raise ValueError(
                        f"Current step {flow_state.current_step_name} is not among the known steps"
                    )

                current_step = flow_state.flow.steps[flow_state.current_step_name]
                if isinstance(current_step, CompleteStep):
                    last_complete_step_name_executed = flow_state.current_step_name

                # we extract the inputs from the conversation input/output dict
                # and pass only the needed ones to the step
                step_inputs = await FlowConversationExecutor._gather_step_inputs_async(
                    conversation, flow_state, current_step
                )

                if logger.isEnabledFor(logging.DEBUG):
                    logger.info(
                        'Invoking "%s" (%s) - inputs %s',
                        flow_state.current_step_name,
                        current_step,
                        step_inputs,
                    )

                FlowConversationExecutor._register_event(
                    state=flow_state,
                    conversation=conversation,
                    event_type=EventType.STEP_EXECUTION_START,
                )

                step_result = await current_step.invoke_async(
                    inputs=step_inputs,
                    conversation=conversation,
                )

                step_outputs = step_result.outputs
                branch_name = step_result.branch_name
                current_step_type = step_result.step_type

                if logger.isEnabledFor(logging.DEBUG):
                    logger.info(
                        'Returned from "%s" - outputs %s - branch: %s',
                        flow_state.current_step_name,
                        step_outputs,
                        branch_name,
                    )

                yielding = current_step_type == StepExecutionStatus.YIELDING
                interrupted = current_step_type == StepExecutionStatus.INTERRUPTED

                # We extract the last status from the step outputs, in case an inner interrupt was triggered
                last_status: Optional[ExecutionStatus] = None
                if interrupted:
                    if "__execution_status__" not in step_outputs:
                        raise ValueError(
                            f'The Step "{flow_state.current_step_name}" was interrupted, but it did not report any status. Please check the implementation of the step.'
                        )
                    last_status = step_outputs.pop("__execution_status__")

                if yielding:
                    # check that if we are yielding, it was declared possible by the step
                    if not current_step.might_yield:
                        raise ValueError(
                            f'The step "{flow_state.current_step_name}" yielded contrarily to what might_yield reported. The step was implemented wrongly, and should be changed to indicate that it might yield.'
                        )

                    # workaround: if the status was passed inside the steps outputs, we propagate it directly
                    if "__execution_status__" in step_outputs:
                        last_status = step_outputs["__execution_status__"]
                        if not isinstance(last_status, ExecutionStatus):
                            raise ValueError(
                                f"Content of `__execution_status__` should be an execution status, but was: {last_status}"
                            )
                        # Do not return for ToolExecutionConfirmationStatus, because we need to prepare for the next step
                        if not isinstance(last_status, ToolExecutionConfirmationStatus):
                            conversation.status = last_status
                            return last_status

                next_step_name = FlowConversationExecutor.get_next_step_name_from_branch(
                    control_flow_edges=flow_state.flow.control_flow_edges,
                    current_step_name=flow_state.current_step_name,
                    steps=flow_state.flow.steps,
                    branch_taken=branch_name,
                )

                # make sure that after yielding or being interrupted we will come back to same step
                if (yielding or interrupted) and next_step_name != flow_state.current_step_name:
                    raise ValueError(
                        f'The step "{flow_state.current_step_name}" yielded but indicated that the next step should be {next_step_name} instead of itself, which is not allowed.'
                    )

                # we rename the outputs from the step as needed by the mapping before placing
                # them in the conversation input/output dict
                sanitized_outputs = FlowConversationExecutor._writeback_step_outputs(
                    step_outputs,
                    current_step,
                    yielding or interrupted,
                    flow_state.current_step_name,
                )

                FlowConversationExecutor._push_step_output_values_to_io_dict(
                    io_value_dict=flow_state.input_output_key_values,
                    source_step_name=flow_state.current_step_name,
                    data_flow_edges=flow_state.flow.data_flow_edges,
                    steps=flow_state.flow.steps,
                    outputs=sanitized_outputs,
                )

                FlowConversationExecutor._push_step_outputs_to_flow_outputs(
                    state=flow_state,
                    outputs=sanitized_outputs,
                )

                logger.debug("Next step `%s`", next_step_name)

                # prepare for next iteration if needed
                flow_state.current_step_name = next_step_name

                if interrupted and last_status is not None:
                    logger.info("%s is being interrupted", flow_state.current_step_name)
                    return last_status

                if yielding:
                    logger.info("%s is yielding", flow_state.current_step_name)

                    # TODO when supporting client tool execution in other steps, design a
                    # better mechanism for the flow executor to know whether to yield for a user
                    # message or for a tool request
                    next_tool_request_message: Optional[Message] = conversation.get_last_message()

                    if (
                        next_tool_request_message is not None
                        and next_tool_request_message.message_type == MessageType.TOOL_REQUEST
                        and next_tool_request_message.tool_requests is not None
                    ):
                        return ToolRequestStatus(
                            tool_requests=next_tool_request_message.tool_requests,
                            _conversation_id=conversation.id,
                        )

                    elif isinstance(last_status, ToolExecutionConfirmationStatus):
                        last_status._conversation_id = conversation.id
                        return last_status

                    last_message = conversation.get_last_message()
                    if last_message is None:
                        last_message = Message(
                            content="**The flow yielded without posting any message to the conversation**",
                            role="assistant",
                        )

                    return UserMessageRequestStatus(
                        message=last_message, _conversation_id=conversation.id
                    )

                FlowConversationExecutor._register_event(
                    state=flow_state,
                    conversation=conversation,
                    event_type=EventType.STEP_EXECUTION_END,
                )

                FlowConversationExecutor._register_event(
                    state=flow_state,
                    conversation=conversation,
                    event_type=EventType.EXECUTION_LOOP_ITERATION_END,
                )

                record_event(
                    FlowExecutionIterationFinishedEvent(
                        execution_state=conversation.state,
                    )
                )

            outputs = FlowConversationExecutor.gather_flow_outputs(
                state=flow_state,
                outputs_descriptions=flow_state.flow.output_descriptors_dict,
                fail_on_missing_value=False,  # TODO fix required values
            )

            FlowConversationExecutor._register_event(
                state=flow_state,
                conversation=conversation,
                event_type=EventType.EXECUTION_END,
            )
        except ExecutionInterruptedException as e:
            return e.execution_status
        except Exception as e:
            _record_exception(e)
            raise e

        return FinishedStatus(
            output_values=outputs,
            complete_step_name=last_complete_step_name_executed,
            _conversation_id=conversation.id,
        )

    @staticmethod
    def get_all_sub_conversations(
        state: FlowConversationExecutionState,
    ) -> List["Conversation"]:
        return [
            conv
            for k, conv in state.internal_context_key_values.items()
            if FlowConversationExecutor._SUB_CONVERSATION_KEY in k
        ]
