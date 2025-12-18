# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import warnings
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypeGuard,
    Union,
)

from wayflowcore._metadata import MetadataType
from wayflowcore.contextproviders import ContextProvider
from wayflowcore.contextproviders.toolcontextprovider import (
    _convert_context_provider_dict_to_tool_provider,
)
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.messagelist import MessageList
from wayflowcore.property import (
    ObjectProperty,
    Property,
    _cast_value_into,
    _empty_default,
    _property_can_be_casted_into_property,
)
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.tools import Tool

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation
    from wayflowcore.executors._flowexecutor import _IoKeyType
    from wayflowcore.messagelist import Message
    from wayflowcore.models.llmmodel import LlmModel
    from wayflowcore.serialization.context import DeserializationContext, SerializationContext
    from wayflowcore.steps import CompleteStep, StartStep
    from wayflowcore.steps.step import Step
    from wayflowcore.tools import ClientTool, ServerTool
    from wayflowcore.variable import Variable

logger = logging.getLogger(__name__)

_EdgeDestinationType = Tuple[str, str]
"""Type for the destination object given a data flow edge"""


def _is_step_a_complete_step(step: "Step") -> TypeGuard["CompleteStep"]:
    from wayflowcore.steps import CompleteStep

    return isinstance(step, CompleteStep)


def _is_step_a_start_step(step: "Step") -> TypeGuard["StartStep"]:
    from wayflowcore.steps import StartStep

    return isinstance(step, StartStep)


def _get_step_name_from_step(step: Optional["Step"], steps: Dict[str, "Step"]) -> Optional[str]:
    if step is None:
        return None
    return next(
        (step_name for step_name, step_object in steps.items() if step == step_object), None
    )


def _resolve_inputs_and_outputs(
    begin_step_name: str,
    steps: Dict[str, "Step"],
    control_flow_edges: List[ControlFlowEdge],
    data_flow_edges: List[DataFlowEdge],
) -> Tuple[
    Dict[str, Property],
    Dict[str, List["_IoKeyType"]],
    Dict[str, Property],
    Dict[str, List[Property]],
]:
    """
    Method to resolve the list of expected flow inputs (that must be passed as inputs when
    creating a conversation) as well as the produced flow outputs.
    """
    from wayflowcore.executors._flowexecutor import FlowConversationExecutor
    from wayflowcore.steps.step import Step

    # The below list of tuples is used for traversing through the flow:
    # - current_step_name: str
    #    The name of the current step during the flow traversal
    # - produced_outputs_along_path: Set[_IoKeyType]
    #    All outputs that have been produced until this point in the flow traversal. Note that
    #    for this algorithm we care about the minimal sets of outputs (i.e. outputs that are
    #    guaranteed)
    # - produced_mapped_outputs_along_path: Dict[str, Property]
    #    All outputs renamed using the output mappings. This is kept for backward compatibility
    resolved_input_descriptors_dict: Dict[str, Property] = {}
    producing_step_by_input_descriptor_name: Dict[str, Step] = {}
    _input_mapping_to_io_value_keys: Dict[str, List["_IoKeyType"]] = {}
    queue: List[Tuple[str, Set["_IoKeyType"], Dict[str, Property]]] = [(begin_step_name, set(), {})]
    all_possible_produced_outputs_at_exit: Dict[str, Dict[str, Property]] = {}
    visited_steps_io_types: Dict[str, Tuple[Set["_IoKeyType"], Dict[str, Property]]] = {}
    conflicting_input_descriptors: Dict[str, List[Property]] = {}

    def _get_destination_from_edge(data_flow_edge: DataFlowEdge) -> _EdgeDestinationType:
        destination_step = data_flow_edge.destination_step
        try:
            destination_step_name = next(
                step_name
                for step_name, step_object in steps.items()
                if step_object is destination_step
            )
        except StopIteration:
            raise ValueError(
                f"The destination step `{destination_step.name}` present in the data flow edge (`{data_flow_edge})`"
                f" does not seem to exist in the flow. Make sure it is mentioned in at least one control flow edge and in the steps."
            )

        return destination_step_name, data_flow_edge.destination_input

    # We use this to remove the outputs of the start step only from the final output descriptors
    # This is needed to avoid that inputs of this flow appear also as outputs
    start_step_only_output_descriptors = {}
    if _is_step_a_start_step(steps[begin_step_name]):
        start_step = steps[begin_step_name]
        start_step_only_output_descriptors = {
            output_descriptor.name: output_descriptor
            for output_descriptor in start_step.output_descriptors
        }

    while len(queue) > 0:
        current_step_name, produced_outputs_along_path, produced_mapped_outputs_along_path = (
            queue.pop()
        )

        # not getting trapped in loops
        if current_step_name in visited_steps_io_types.keys():
            (
                previously_recorded_produced_outputs_along_path,
                previously_recorded_mapped_produced_outputs_along_path,
            ) = visited_steps_io_types[current_step_name]
            if all(
                io_key in produced_outputs_along_path
                for io_key in previously_recorded_produced_outputs_along_path
            ) and all(
                mapped_output_name in produced_mapped_outputs_along_path
                for mapped_output_name in previously_recorded_mapped_produced_outputs_along_path
            ):
                continue

            produced_outputs_along_path = {
                io_key
                for io_key in produced_outputs_along_path
                if io_key in previously_recorded_produced_outputs_along_path
            }
            produced_mapped_outputs_along_path = {
                mapped_output_name: value_type_description
                for mapped_output_name, value_type_description in produced_mapped_outputs_along_path.items()
                if mapped_output_name in previously_recorded_mapped_produced_outputs_along_path
            }

        visited_steps_io_types[current_step_name] = (
            produced_outputs_along_path,
            produced_mapped_outputs_along_path,
        )
        current_step = steps[current_step_name]

        # resolve step inputs
        for input_type in current_step.input_descriptors:
            input_name = input_type.name

            has_matching_contextprovider = (
                FlowConversationExecutor._get_context_provider_or_none_for_step(
                    destination_step=current_step,
                    destination_input=input_name,
                    data_flow_edges=data_flow_edges,
                )
            )
            io_key = (current_step_name, input_name)
            if not has_matching_contextprovider and io_key not in produced_outputs_along_path:
                if input_name in resolved_input_descriptors_dict:
                    if not data_flow_edges:
                        other_input_descriptor = resolved_input_descriptors_dict[input_name]
                        other_step = producing_step_by_input_descriptor_name[input_name]
                        base_message = (
                            "You did not specify any data edges, so they were created automatically based on a breath-first visit of the flow.\n"
                            "The input `%s` of step `%s` (of type `%s`) has the same name as \n"
                            "the input `%s` of step `%s` (of type `%s`), so they will appear as a single "
                            "input of the flow. \n"
                        )
                        if not _property_can_be_casted_into_property(
                            other_input_descriptor, input_type
                        ):
                            raise ValueError(
                                base_message.replace("%s", "{}").format(
                                    input_type.pretty_str(),
                                    current_step.name,
                                    type(current_step).__name__,
                                    other_input_descriptor.pretty_str(),
                                    other_step.name,
                                    type(other_step).__name__,
                                )
                                + "Their types are not compatible, please change one of the names."
                            )
                        else:
                            logger.warning(
                                base_message
                                + "Make sure that these refer to the same input or conflicts might happen",
                                input_type.pretty_str(),
                                current_step.name,
                                type(current_step).__name__,
                                other_input_descriptor.pretty_str(),
                                other_step.name,
                                type(other_step).__name__,
                            )
                    conflicting_input_descriptors[input_name] = conflicting_input_descriptors.get(
                        input_name, []
                    ) + [input_type]

                producing_step_by_input_descriptor_name[input_name] = current_step
                resolved_input_descriptors_dict[input_name] = input_type
                if input_name not in _input_mapping_to_io_value_keys:
                    _input_mapping_to_io_value_keys[input_name] = []
                _input_mapping_to_io_value_keys[input_name].append(io_key)

        # resolve step outputs
        for data_flow_edge in data_flow_edges:
            if data_flow_edge.source_step is current_step:
                produced_outputs_along_path.add(_get_destination_from_edge(data_flow_edge))

            source_step = data_flow_edge.source_step
            if isinstance(source_step, Step) and not any(
                step_object for step_object in steps.values() if step_object is source_step
            ):
                raise ValueError(
                    f"The source step `{source_step.name}` present in the data flow edge (`{data_flow_edge})`"
                    f" does not seem to exist in the flow. Make sure it is mentioned in at least one control flow edge"
                )

        for output_descriptor in current_step.output_descriptors:
            produced_mapped_outputs_along_path[output_descriptor.name] = output_descriptor
            if (
                not _is_step_a_start_step(current_step)
                and output_descriptor.name in start_step_only_output_descriptors
            ):
                del start_step_only_output_descriptors[output_descriptor.name]

        destination_steps = [
            control_flow_edge.destination_step
            for control_flow_edge in control_flow_edges
            if control_flow_edge.source_step is current_step
        ]
        next_step_name_list = [
            _get_step_name_from_step(destination_step, steps)
            for destination_step in destination_steps
        ]

        queue.extend(
            [
                (
                    next_step_name,
                    deepcopy(produced_outputs_along_path),
                    deepcopy(produced_mapped_outputs_along_path),
                )
                for next_step_name in next_step_name_list
                if next_step_name is not None
            ]
        )

        # if node is exit node, we write up the outputs
        if len(next_step_name_list) == 0 or any(
            next_step_name is None for next_step_name in next_step_name_list
        ):
            all_possible_produced_outputs_at_exit[current_step_name] = (
                produced_mapped_outputs_along_path
            )

    # we check that the input descriptors of the start step are a subset of the collected ones
    flow_input_descriptors_dict: Dict[str, Property]
    if _is_step_a_start_step(steps[begin_step_name]):
        start_step = steps[begin_step_name]
        start_step_input_descriptors = {
            input_descriptor.name: input_descriptor
            for input_descriptor in start_step.input_descriptors
        }
        for input_name, prop in resolved_input_descriptors_dict.items():
            if not prop.has_default and input_name not in start_step_input_descriptors:
                raise ValueError(
                    f"The flow requires the input descriptor `{prop.pretty_str()}` because some"
                    f" step requires it but "
                    f"that is not available in the StartStep. Please add it."
                )
        flow_input_descriptors_dict = start_step_input_descriptors
    else:
        flow_input_descriptors_dict = resolved_input_descriptors_dict

    # the flow doesn't finish
    if len(all_possible_produced_outputs_at_exit) == 0:
        return (
            flow_input_descriptors_dict,
            _input_mapping_to_io_value_keys,
            {},
            conflicting_input_descriptors,
        )

    # we only keep the outputs that are produced by all possible final nodes
    names_of_resolved_outputs = set.intersection(
        *[
            set(produced_mapped_outputs.keys())
            for produced_mapped_outputs in all_possible_produced_outputs_at_exit.values()
        ]
    )
    produced_outputs_along_any_path = next(iter(all_possible_produced_outputs_at_exit.values()))
    flow_output_descriptors_dict = {
        mapped_output_name: produced_outputs_along_any_path[mapped_output_name]
        for mapped_output_name in names_of_resolved_outputs
        if mapped_output_name not in start_step_only_output_descriptors
    }
    return (
        flow_input_descriptors_dict,
        _input_mapping_to_io_value_keys,
        flow_output_descriptors_dict,
        conflicting_input_descriptors,
    )


def _remap_input_to_io_value_keys_with_startstep(
    steps: Dict[str, "Step"],
    begin_step_name: str,
    input_mapping_to_io_value_keys: Dict[str, List["_IoKeyType"]],
    auto_start_step_input_resolution: bool,
) -> Tuple[List[DataFlowEdge], Dict[str, List["_IoKeyType"]]]:
    """
    Remaps the io value keys based on the start step.
    Used when the flow did not contain a StartStep natively.
    Return the list of new data edges to add, and the remapped dictionary of io value keys.
    """
    new_data_flow_edges: List[DataFlowEdge] = []
    remapped_io_value_keys: Dict[str, List["_IoKeyType"]] = dict()

    for mapped_input_key, io_keys in input_mapping_to_io_value_keys.items():
        remapped_io_value_keys[mapped_input_key] = []
        for destination_step_name, original_step_input_name in io_keys:

            # We check that if we have a step input that is not given in the start step,
            # then we have a default value for it that we can use instead
            source_step_output_names = {
                descriptor.name for descriptor in steps[begin_step_name].output_descriptors
            }
            if mapped_input_key not in source_step_output_names:
                destination_step_input = next(
                    (
                        descriptor
                        for descriptor in steps[destination_step_name].input_descriptors
                        if descriptor.name == original_step_input_name
                    ),
                    None,
                )
                if (
                    destination_step_input is not None
                    and destination_step_input.default_value is _empty_default
                ):
                    # No default given for the destination input, that's a problem
                    raise ValueError(
                        f"Step named `{destination_step_name}` requires an input called `{original_step_input_name}`, "
                        f"but no input with that name was given to the flow. Please check the input descriptors of this step,"
                        f" add a data flow edge or give it a default value."
                    )
                # We have a default, we can continue without adding the edge
                continue

            remapped_io_value_keys[mapped_input_key].append((begin_step_name, mapped_input_key))
            new_data_flow_edges.append(
                DataFlowEdge(
                    source_step=steps[begin_step_name],
                    source_output=mapped_input_key,
                    destination_step=steps[destination_step_name],
                    destination_input=original_step_input_name,
                )
            )
    return new_data_flow_edges, remapped_io_value_keys


def _handle_transitions_updates(
    step: "Step",
    step_name: str,
    old_transitions: Union[Sequence[Optional[str]], Dict[str, Optional[str]]],
    additional_transitions: Dict[str, Optional[str]],
) -> Dict[str, Optional[str]]:
    """
    Based on the previously gathered `additional_transitions` (during step building), we now modify the `transitions`
    dict to include these additional transitions, and fill potentially missing branches that are now mandatory
    (to avoid crashing on old configs)
    """
    if isinstance(old_transitions, Mapping):
        if not isinstance(old_transitions, dict):
            raise ValueError("Internal error")

        if len(additional_transitions) > 0:
            old_transitions.update(additional_transitions)
        return old_transitions

    from wayflowcore.steps import BranchingStep, ChoiceSelectionStep, RetryStep
    from wayflowcore.steps.step import Step

    transitions_dict = additional_transitions

    step_cls = step.__class__

    if step_cls in [BranchingStep, ChoiceSelectionStep, RetryStep]:
        if step_cls == BranchingStep:
            if BranchingStep.BRANCH_DEFAULT not in transitions_dict:
                transitions_dict[BranchingStep.BRANCH_DEFAULT] = None

        elif step_cls == ChoiceSelectionStep:
            if ChoiceSelectionStep.BRANCH_DEFAULT not in transitions_dict:
                transitions_dict[ChoiceSelectionStep.BRANCH_DEFAULT] = None

        elif step_cls == RetryStep:
            if RetryStep.BRANCH_NEXT not in transitions_dict:
                transitions_dict[RetryStep.BRANCH_NEXT] = None
            if RetryStep.BRANCH_FAILURE not in transitions_dict:
                transitions_dict[RetryStep.BRANCH_FAILURE] = None

        branches = step.get_branches()
        for old_transition in old_transitions:
            if old_transition in branches:
                transitions_dict[str(old_transition)] = old_transition

    else:
        if len(old_transitions) > 1 and step_name in old_transitions:
            old_transitions = [s for s in old_transitions if s != step_name]
        if len(old_transitions) == 1:
            transitions_dict = {Step.BRANCH_NEXT: old_transitions[0]}
        else:
            ValueError(
                f"Found several potential next steps and transitions is a list: {old_transitions}"
            )

    return transitions_dict


class Flow(ConversationalComponent, SerializableObject):
    """
    Represents a conversational assistant that defines the flow of a conversation.

    The flow consists of a set of steps (states) and possible transitions between steps.
    Transitions are validated to ensure compliance with expected scenarios.
    The flow can have arbitrary loops, and each step can indicate whether it should be followed by
    a direct execution of the next step or yielding back to the user.
    """

    _DEFAULT_STARTSTEP_NAME: ClassVar[str] = "__StartStep__"

    def __init__(
        self,
        steps: Optional[Union[Dict[str, "Step"], List["Step"]]] = None,
        begin_step: Optional["Step"] = None,
        data_flow_edges: Optional[List[DataFlowEdge]] = None,
        control_flow_edges: Optional[List[ControlFlowEdge]] = None,
        context_providers: Optional[List["ContextProvider"]] = None,
        variables: Optional[List["Variable"]] = None,
        name: Optional[str] = None,
        description: str = "",
        flow_id: Optional[str] = None,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        __metadata_info__: Optional[MetadataType] = None,
        # deprecated
        transitions: Optional[
            Mapping[str, Union[List[Optional[str]], Mapping[str, Optional[str]]]]
        ] = None,
        id: Optional[str] = None,
    ) -> None:
        """
        Note
        ----

        A flow has input and output descriptors, describing what values the flow requires to run and what values it produces.

        **Input descriptors**

        By default, when ``input_descriptors`` is set to ``None``, the input descriptors of the flow are resolved
        automatically based on the shape of the flow. This means that we consider an input descriptor of the flow
        all input descriptors that are defined in the ``StartStep``.

        If no ``StartStep`` is provided for the flow, the input descriptors of the step are resolved
        automatically based on the shape of the flow. They consist of all input descriptors of its steps that are
        not linked with a ``data_flow_edge`` to an output descriptor of another step in this flow.

        If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
        in particular using the new type instead of the detected one. If some of them are missing,
        they won't be exposed as inputs of the flow.

        When starting a conversation with a ``Flow``, you need to pass an input for each input_descriptor of
        the flow using ``flow.start_conversation(inputs=<INPUTS>)``.

        **Output descriptors**

        By default, when ``output_descriptors`` is set to ``None``, the flow will auto-detect all outputs that are
        produced in any path in this flow. This means that we consider an output descriptor of the flow all output
        descriptors that were produced when reaching any of the ``CompleteStep`` / steps transitioning to ``None``.

        If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
        in particular using the new type instead of the detected one. If some of them are missing,
        they won't be exposed as outputs of the flow.

        If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
        the flow will not work if they don't have default values.

        **Branches**

        Flows sometimes can have different paths, and finish in different ``CompleteStep``. Each name of a ``CompleteStep`` in the flow
        will be exposed as a different end of the flow (or branch).

        Parameters
        ----------
        steps:
            Dictionary of steps linking names with stateless instances of steps.
        begin_step:
            First step of the flow.
        data_flow_edges:
            Data flow edges indicate which outputs that step or context provider produce are passed
            to the next steps in the Flow.
        control_flow_edges:
            Control flow edges indicate transitions between each steps.
        context_providers:
            List of objects that add context to specific steps.
        variables:
            List of variables for the flow, whose values are visible per conversation.

            .. note::

                ``Variables`` defined in this list must have unique names. Whenever a flow starts
                a new conversation, a variable store is created with keys being the flow's
                variables and values being the variables' default values.
        name:
            name of the agent, used for composition
        description:
            description of the agent, used for composition
        input_descriptors:
            Input descriptors of the flow. ``None`` means the flow will resolve the input descriptors automatically in a best effort manner.
            .. note::

                If ``input_descriptors`` are specified, they will override the resolved descriptors but will be matched
                by ``name`` against them to check that types can be casted from one another, raising an error if they can't.
                If some expected descriptors are missing from the ``input_descriptors`` (i.e. you forgot to specify one),
                a warning will be raised and the flow is not guaranteed to work properly.
        output_descriptors:
            Output descriptors of the flow. ``None`` means the flow will resolve the output descriptors automatically in a best effort manner.

            .. note::

                If ``output_descriptors`` are specified, they will override the resolved descriptors but will be matched
                by ``name`` against them to check that types can be casted from one another, raising an error if they can't.
                If some expected descriptors are missing from the ``output_descriptors`` (i.e. you forgot to specify one),
                a warning will be raised and the flow is not guaranteed to work properly.

        Examples
        --------
        >>> from wayflowcore.flow import Flow
        >>> from wayflowcore.steps import OutputMessageStep, InputMessageStep, StartStep, CompleteStep
        >>> from wayflowcore.controlconnection import ControlFlowEdge
        >>> from wayflowcore.property import StringProperty
        >>> USER_NAME = "$message"
        >>> start_step = StartStep(name="start_step", input_descriptors=[StringProperty(name=USER_NAME)])
        >>> output_step = OutputMessageStep(
        ...     name="output_step",
        ...     message_template="Welcome, {{username}}",
        ...     input_mapping={"username": USER_NAME}
        ... )
        >>> complete_step = CompleteStep(name='complete_step')
        >>> flow = Flow(
        ...     begin_step=start_step,
        ...     steps=[start_step, output_step, complete_step],
        ...     control_flow_edges=[
        ...         ControlFlowEdge(source_step=start_step, destination_step=output_step),
        ...         ControlFlowEdge(source_step=output_step, destination_step=complete_step),
        ...     ],
        ... )
        >>> conversation = flow.start_conversation(inputs={USER_NAME: "User"})
        >>> status = conversation.execute()
        >>> status.output_values
        {'output_message': 'Welcome, User'}

        """
        from wayflowcore.executors._flowexecutor import FlowConversationExecutor

        if steps is None:
            if control_flow_edges is None:
                raise ValueError(
                    "Should always pass `control_flow_edges` when not passing `steps`, but was None."
                )

            all_steps = [
                step
                for control_flow_edge in control_flow_edges
                for step in [control_flow_edge.source_step, control_flow_edge.destination_step]
                if step is not None
            ]

            steps = {}
            for step in all_steps:
                if step.name is None:
                    raise ValueError(
                        f"Found step without name: `{step}`. Either set a name on each step, or pass a `steps` dict to the flow"
                    )
                elif step.name not in steps:
                    steps[step.name] = step
                elif steps[step.name] is not step:
                    raise ValueError(
                        f"Found 2 different steps with similar names: {steps[step.name]}, {step}. Please make sure step names are unique in the flow"
                    )
        elif isinstance(steps, list):
            step_names_to_steps_dict: Dict[str, Step] = {}
            for step in steps:
                if step.name in step_names_to_steps_dict:
                    raise ValueError(
                        f"Two steps have the same id: {step} and {step_names_to_steps_dict[step.name]}"
                    )
                step_names_to_steps_dict[step.name] = step
            steps = step_names_to_steps_dict
        elif isinstance(steps, dict):
            # we override the names
            for step_name, step in steps.items():
                if step.name is not None and IdGenerator.is_auto_generated(step.name):
                    step.name = step_name

        # Validate begin step name
        if begin_step is not None:
            if begin_step not in steps.values():
                raise ValueError(
                    f"Indicated begin step name `{begin_step}` is not present in the steps"
                )
            begin_step_name = next(
                step_name for step_name, step in steps.items() if step == begin_step
            )
        else:
            raise ValueError(
                "You should specify the starting step with the ``begin_step`` argument, but was None"
            )

        if _is_step_a_complete_step(steps[begin_step_name]):
            raise ValueError(
                "A flow cannot start with a CompleteStep. Please specify another ``begin_step``."
            )

        start_step_count = sum(_is_step_a_start_step(step) for step in steps.values())
        if start_step_count > 1:
            raise ValueError(
                f"A flow can have at most 1 StartStep instance, but {start_step_count} were given."
            )

        if not _is_step_a_start_step(steps[begin_step_name]):
            if start_step_count > 0:
                raise ValueError(
                    "A StartStep instance is given, but it does not correspond to the begin_step_name"
                )
            if self._DEFAULT_STARTSTEP_NAME in steps:
                raise ValueError(
                    f"A step with the default StartStep name `{self._DEFAULT_STARTSTEP_NAME}` is given, "
                    f"but it's not of type StartStep. Please use another name."
                )

        extended_end_steps: List[Optional[str]] = list(
            {
                None,
                *{step_name for step_name, step in steps.items() if _is_step_a_complete_step(step)},
            }
        )

        if control_flow_edges:
            if transitions is not None:
                raise ValueError(
                    "Cannot set both `control_flow_edges` and `transitions`. Please use `control_flow_edges`."
                )
            self._check_all_steps_are_mentioned(control_flow_edges, steps)
        elif transitions is not None:
            warnings.warn(
                "Usage of `transitions` is deprecated. Please use `control_flow_edges`.",
                DeprecationWarning,
            )
            control_flow_edges = self._convert_transition_mapping_into_control_flow_edges(
                transitions=transitions, steps=steps
            )
        else:
            raise ValueError("Should specify ``control_flow_edges`` parameter.")

        self._validate_all_steps_have_transitions_and_are_transitioned_to(
            steps, control_flow_edges, begin_step_name
        )

        if any(
            _is_step_a_start_step(control_flow_edge.destination_step)
            for control_flow_edge in control_flow_edges
            if control_flow_edge.destination_step is not None
        ):
            raise ValueError(
                "Found a control edge with the StartStep as destination. There should be a single StartStep per Flow"
                " and it should not be specified as a destination of a control flow edge."
            )

        # Specify the list of Context Providers, convert them if needed and validate their names
        if context_providers is None:
            context_providers = []

        self._validate_list_of_context_providers_has_unique_output_descriptor_names(
            context_providers
        )

        # Validating or inferring data edges from I/O mapping
        if data_flow_edges:
            # add context providers from the edges into the context providers list of the flow
            for data_flow_edge in data_flow_edges:
                if (
                    isinstance(data_flow_edge.source_step, ContextProvider)
                    and data_flow_edge.source_step not in context_providers
                ):
                    context_providers.append(data_flow_edge.source_step)

        else:
            data_flow_edges = self._create_data_edges_for_implicit_data_edges(
                steps=steps, context_providers=context_providers
            )

        # Resolve the input/outputs of the Flow
        (
            input_descriptors_dict,
            input_mapping_to_io_value_keys,
            output_descriptors_dict,
            conflicting_input_descriptors,
        ) = _resolve_inputs_and_outputs(
            begin_step_name=begin_step_name,
            steps=steps,
            control_flow_edges=control_flow_edges,
            data_flow_edges=data_flow_edges,
        )

        # We add the default StartStep if none is given, and we remap inputs
        if not _is_step_a_start_step(steps[begin_step_name]):
            from wayflowcore.steps import StartStep

            context_providers_output_descriptor_names = {
                output_descriptor.name
                for context_provider in context_providers
                for output_descriptor in context_provider.get_output_descriptors()
            }
            if input_descriptors is None:
                # we check no conflict in the inputs values
                resolved_input_descriptors = list(
                    input_property.copy(name=mapped_input_name)
                    for mapped_input_name, input_property in input_descriptors_dict.items()
                    if mapped_input_name not in context_providers_output_descriptor_names
                )
                for input_descriptor in resolved_input_descriptors:
                    if input_descriptor.name in conflicting_input_descriptors and not all(
                        descriptor == input_descriptor
                        for descriptor in conflicting_input_descriptors[input_descriptor.name]
                    ):
                        formatted_properties = (
                            "\n-"
                            + "\n -".join(
                                s.pretty_str()
                                for s in conflicting_input_descriptors[input_descriptor.name]
                            )
                            + "\n"
                        )
                        raise ValueError(
                            f"Some flow input descriptors have the same name but are different:\n"
                            f"{formatted_properties}"
                            f"Please make sure properties with a common name are identical, or change one of the names to avoid conflicts."
                        )

            else:
                resolved_input_descriptors = input_descriptors

            auto_start_step_input_resolution = input_descriptors is None

            logger.info(
                "No StartStep was given as part of the Flow, one will be added with the following detected inputs: %s",
                "\n -".join(i.pretty_str() for i in resolved_input_descriptors),
            )

            start_step = StartStep(input_descriptors=resolved_input_descriptors)
            control_flow_edges.append(
                ControlFlowEdge(source_step=start_step, destination_step=steps[begin_step_name])
            )
            begin_step_name = Flow._DEFAULT_STARTSTEP_NAME
            steps[begin_step_name] = start_step
            if len(start_step.input_descriptors) > 0:
                # only add data edges if the start step has inputs
                new_data_flow_edges, input_mapping_to_io_value_keys = (
                    _remap_input_to_io_value_keys_with_startstep(
                        steps=steps,
                        begin_step_name=begin_step_name,
                        input_mapping_to_io_value_keys=input_mapping_to_io_value_keys,
                        auto_start_step_input_resolution=auto_start_step_input_resolution,
                    )
                )
                data_flow_edges.extend(new_data_flow_edges)

        # Specifying flow attributes
        self.begin_step_name: str = begin_step_name
        self.begin_step = steps[begin_step_name]
        self.steps: Dict[str, "Step"] = steps
        self.control_flow_edges: List[ControlFlowEdge] = control_flow_edges
        self.data_flow_edges: List[DataFlowEdge] = data_flow_edges
        self.end_steps: List[Optional[str]] = extended_end_steps
        self.context_providers: List[ContextProvider] = context_providers
        self.input_descriptors_dict: Dict[str, Property] = input_descriptors_dict
        self.output_descriptors_dict: Dict[str, Property] = output_descriptors_dict
        self._input_mapping_to_io_value_keys: Dict[str, List["_IoKeyType"]] = (
            input_mapping_to_io_value_keys
        )

        # We are assuming the flow is static to be able to precompute this
        # if that ever changes, we would need to recompute it when it changes
        self._might_yield: bool = any(step.might_yield for step in self.steps.values())

        # Specify the list of Variables, validate their names and the associated read/write steps
        variables = variables if variables is not None else []
        self._validate_unique_variable_names(variables)
        self.variables = variables
        self._validate_readwrite_steps_refer_to_declared_variables(self.steps, self.variables)

        self._check_step_outputs_and_context_provider_collisions()

        self.executor = FlowConversationExecutor()
        # Dictionary of files available in this conversation
        self._files: Dict[str, Path] = {}

        default_input_descriptors = list(self.input_descriptors_dict.values())
        input_descriptors = self._resolve_input_descriptors(
            specified_descriptors=input_descriptors, default_descriptors=default_input_descriptors
        )
        default_output_descriptors = list(self.output_descriptors_dict.values())
        output_descriptors = self._resolve_output_descriptors(
            specified_descriptors=output_descriptors, default_descriptors=default_output_descriptors
        )

        # Inputs and outputs might be a subset of all those generated, if they are specified by the user.
        # We make sure that also descriptors dict contain only the inputs and outputs that are supposed to be
        # exposed by this flow, so that they are aligned with descriptors lists
        self.input_descriptors_dict = {
            descriptor.name: self.input_descriptors_dict[descriptor.name]
            for descriptor in input_descriptors
        }
        self.output_descriptors_dict = {
            descriptor.name: self.output_descriptors_dict[descriptor.name]
            for descriptor in output_descriptors
        }

        from wayflowcore.executors._flowconversation import FlowConversation

        super().__init__(
            name=IdGenerator.get_or_generate_name(name, prefix="flow_", length=8),
            description=description,
            id=id or flow_id,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            runner=FlowConversationExecutor,
            conversation_class=FlowConversation,
            __metadata_info__=__metadata_info__,
        )

    @property
    def flow_id(self) -> str:
        return self.id

    @staticmethod
    def _check_all_steps_are_mentioned(
        control_flow_edges: List[ControlFlowEdge], steps: Dict[str, "Step"]
    ) -> None:
        for control_flow_edge in control_flow_edges:
            source_step = control_flow_edge.source_step
            source_step_name = source_step.name
            if source_step_name not in steps:
                # we check maybe there is a name mismatch
                found_identical_step = next(
                    iter(s for s in steps.values() if source_step is s), None
                )
                if found_identical_step is None:
                    raise ValueError(
                        f"The source step in control flow edge `{control_flow_edge}` was not specified in the list of steps: {list(steps.keys())}\nPlease add it."
                    )
            elif source_step is not steps[source_step_name]:
                raise ValueError(
                    f"The source step in control flow edge `{control_flow_edge}` is not the one specified in the list of steps under the name `{source_step_name}`: {steps[source_step_name]}\nPlease ensure it is the same step"
                )

            destination_step = control_flow_edge.destination_step
            if destination_step is None:
                continue

            destination_step_name = destination_step.name
            if destination_step_name not in steps:
                # we check maybe there is a name mismatch
                found_identical_step = next(
                    iter(s for s in steps.values() if destination_step is s), None
                )
                if found_identical_step is None:
                    raise ValueError(
                        f"The destination step in control flow edge `{control_flow_edge}` was not specified in the list of steps: {list(steps.keys())}\nPlease add it."
                    )
            elif destination_step is not steps[destination_step_name]:
                raise ValueError(
                    f"The destination step in control flow edge `{control_flow_edge}` is not the one specified in the list of steps under the name `{source_step_name}`: {steps[source_step_name]}\nPlease ensure it is the same step",
                )

    @staticmethod
    def _convert_transition_mapping_into_control_flow_edges(
        transitions: Mapping[str, Union[List[Optional[str]], Mapping[str, Optional[str]]]],
        steps: Dict[str, "Step"],
    ) -> List[ControlFlowEdge]:
        logger.debug(
            f"Detected old transition mapping: %s.\nIt will be converted to control flow edges.",
            transitions,
        )

        control_flow_edges = []

        for source_step_name, mapping in transitions.items():
            if source_step_name not in steps:
                raise ValueError(
                    f"Source step {source_step_name} is not a step of the flow: {list(steps.keys())}"
                )

            source_step = steps[source_step_name]

            if isinstance(mapping, list):
                for destination_step_name in mapping:
                    if destination_step_name is not None and destination_step_name not in steps:
                        raise ValueError(
                            f"Destination step {destination_step_name} is not a step of the flow: {list(steps.keys())}"
                        )

                    if destination_step_name == source_step_name and len(mapping) > 1:
                        # unnecessary edge, we don't add it
                        continue

                    control_flow_edge = Flow._create_control_flow_edge(
                        source_step=source_step,
                        destination_step_name=destination_step_name,
                        steps=steps,
                    )
                    if control_flow_edge is not None:
                        control_flow_edges.append(control_flow_edge)

            elif isinstance(mapping, dict):
                for source_branch, destination_step_name in mapping.items():
                    if destination_step_name is not None and destination_step_name not in steps:
                        raise ValueError(
                            f"Destination step {destination_step_name} is not a step of the flow: {list(steps.keys())}"
                        )

                    control_flow_edge = Flow._create_control_flow_edge(
                        source_step=source_step,
                        destination_step_name=destination_step_name,
                        steps=steps,
                        source_branch=source_branch,
                    )
                    if control_flow_edge is not None:
                        control_flow_edges.append(control_flow_edge)
            else:
                raise NotImplementedError(
                    f"Transition mapping should be list or dict, but was {mapping.__class__.__name__}"
                )

        edges_to_str = "\n".join(str(control_flow_edge) for control_flow_edge in control_flow_edges)
        logger.debug(
            f"Legacy transition mapping was converted into control flow edges:\n{edges_to_str}"
        )

        return control_flow_edges

    @staticmethod
    def _create_control_flow_edge(
        source_step: "Step",
        destination_step_name: Optional[str],
        steps: Dict[str, "Step"],
        source_branch: Optional[str] = None,
    ) -> Optional[ControlFlowEdge]:
        from wayflowcore.steps import CompleteStep

        if isinstance(source_step, CompleteStep):
            # no transition from a Complete Step
            return None

        destination_step: Optional["Step"] = None
        if destination_step_name is not None:
            destination_step = steps[destination_step_name]

        available_branches = source_step.get_branches()
        if source_branch is not None and source_branch not in available_branches:
            logger.warning(
                f"Step `{source_step}` doesn't expose a transition named `{source_branch}`\nAvailable transitions: {available_branches}.\nThis transition will be ignored"
            )
            return None

        if source_branch is not None:
            return ControlFlowEdge(
                source_step=source_step,
                destination_step=destination_step,
                source_branch=source_branch,
            )

        return ControlFlowEdge(
            source_step=source_step,
            destination_step=destination_step,
        )

    @staticmethod
    def _validate_all_steps_have_transitions_and_are_transitioned_to(
        steps: Dict[str, "Step"], control_flow_edges: List[ControlFlowEdge], begin_step_name: str
    ) -> None:
        for step_name, step in steps.items():

            if any(step == step_ for step_name_, step_ in steps.items() if step_name_ != step_name):
                raise ValueError(
                    f"Found duplicate step in the flow. Make sure they are all unique: {steps}"
                )

            # Make sure that all non-begin step are being transitioned to
            if step_name != begin_step_name and not any(
                control_flow_edge
                for control_flow_edge in control_flow_edges
                if control_flow_edge.destination_step == step
            ):
                edges_to_str = "\n".join(
                    str(control_flow_edge) for control_flow_edge in control_flow_edges
                )
                raise ValueError(
                    f"No step is transitioning to step `{step_name}`. "
                    f"Except the begin step, all steps should be transitioned to.\n"
                    f"Steps: {list(steps.keys())}\n"
                    f"Control flow edges: {edges_to_str}"
                )

            # Make sure that all non-CompleteStep are transitioning to another step or None
            if not _is_step_a_complete_step(step):
                Flow._validate_step_has_correct_control_flow_edges(
                    step, control_flow_edges, step_name
                )

    @staticmethod
    def _validate_step_has_correct_control_flow_edges(
        step: "Step", control_flow_edges: List[ControlFlowEdge], step_name: str
    ) -> None:
        if not any(
            control_flow_edge
            for control_flow_edge in control_flow_edges
            if control_flow_edge.source_step is step
        ):
            raise ValueError(
                f"Transition is not specified for step `{step_name}`. "
                "All non-CompleteStep should transition to another step or `None`\n"
                f"Control flow edges: {[str(e) for e in control_flow_edges]}"
            )

        step_branches = step.get_branches()
        step_control_flow_edges = [
            control_flow_edge
            for control_flow_edge in control_flow_edges
            if control_flow_edge.source_step == step
        ]
        mentioned_branch_names = [edge.source_branch for edge in step_control_flow_edges]

        if len(set(mentioned_branch_names)) < len(mentioned_branch_names):
            raise ValueError(
                f"Found duplicate control flow edges with same `source_branch`: {step_control_flow_edges}.\nMake sure there is only one `control_flow_edge` per branch."
            )

        for branch in step_branches:
            if branch not in mentioned_branch_names:
                control_flow_edges_str = "\n".join(
                    f"[{step.name}]-({edge.source_branch})->[{edge.destination_step.name if edge.destination_step else None}]"
                    for edge in step_control_flow_edges
                )
                warnings.warn(
                    f"Missing a control flow edge for branch `{branch}` of step `{step.name}`. From this step, you only passed the following `control_flow_edges`:\n{control_flow_edges_str}\nThe flow will raise at runtime if this branch is taken."
                )

    def _create_data_edges_for_implicit_data_edges(
        self,
        steps: Dict[str, "Step"],
        context_providers: List[ContextProvider],
    ) -> List[DataFlowEdge]:
        """
        Automatically infers data edges between steps and context providers based
        on the source (``Step`` or ``ContextProvider``) output value names and the
        destination (``Step``) input value names.
        """
        data_edge_list: List[DataFlowEdge] = []
        for destination_step in steps.values():
            for source_step in steps.values():
                data_edge_list.extend(
                    self._infer_data_edges_between_steps(source_step, destination_step)
                )
            for context_provider in context_providers:
                data_edge_list.extend(
                    self._infer_data_edges_between_context_provider_and_step(
                        context_provider, destination_step
                    )
                )
        return data_edge_list

    @staticmethod
    def _infer_data_edges_between_steps(
        source_step: "Step",
        destination_step: "Step",
    ) -> List[DataFlowEdge]:
        """
        Previous I/O mapping are converted into data edges
        """
        data_edge_list: List[DataFlowEdge] = []
        for destination_input_descriptor in destination_step.input_descriptors:
            for source_output_descriptor in source_step.output_descriptors:
                if source_output_descriptor.name == destination_input_descriptor.name:
                    data_edge_list.append(
                        DataFlowEdge(
                            source_step=source_step,
                            source_output=source_output_descriptor.name,
                            destination_step=destination_step,
                            destination_input=destination_input_descriptor.name,
                        )
                    )
        return data_edge_list

    @staticmethod
    def _infer_data_edges_between_context_provider_and_step(
        source_contextprovider: "ContextProvider",
        destination_step: "Step",
    ) -> List[DataFlowEdge]:
        data_edge_list: List[DataFlowEdge] = []
        for destination_input_descriptor in destination_step.input_descriptors:
            for source_output_descriptor in source_contextprovider.get_output_descriptors():
                if source_output_descriptor.name == destination_input_descriptor.name:
                    data_edge_list.append(
                        DataFlowEdge(
                            source_step=source_contextprovider,
                            source_output=source_output_descriptor.name,
                            destination_step=destination_step,
                            destination_input=destination_input_descriptor.name,
                        )
                    )
        return data_edge_list

    def start_conversation(
        self,
        inputs: Optional[Dict[str, Any]] = None,
        messages: Union[None, str, "Message", List["Message"], "MessageList"] = None,
        conversation_id: Optional[str] = None,
        nesting_level: int = 0,
        context_providers_from_parent_flow: Optional[Set[str]] = None,
    ) -> "FlowConversation":
        """
        Start the conversation.

        Parameters
        ----------
        inputs:
            Dictionary of inputs. Keys are the variable identifiers and
            values are the actual inputs to start the conversation.
        conversation_id:
            Conversation id of the parent conversation.
        messages:
            List of messages (``MessageList`` object) before starting the conversation.
        context_providers_from_parent_flow:
            Context provider that don't need to be checked when validating existing inputs.
        nesting_level:
            Nesting level of the conversation.

        Returns
        -------
        Conversation:
            A Flow Conversation object.
        """
        from wayflowcore.events.event import ConversationCreatedEvent
        from wayflowcore.events.eventlistener import record_event
        from wayflowcore.executors._flowconversation import FlowConversation

        context_providers_from_parent_flow = context_providers_from_parent_flow or set()
        if inputs is None:
            inputs = {}

        if not isinstance(messages, MessageList):
            messages = MessageList.from_messages(messages=messages)

        # Check that there is no missing input value to start the flow execution
        for input_name, input_descriptor in self.input_descriptors_dict.items():
            context_providers_from_current_flow = {
                output_descriptor.name
                for context_provider in self.context_providers
                for output_descriptor in context_provider.get_output_descriptors()
            }
            available_inputs = (
                set(inputs)
                | context_providers_from_current_flow
                | context_providers_from_parent_flow
            )
            if input_name not in available_inputs and not input_descriptor.has_default:
                raise ValueError(
                    f'Cannot start conversation because of missing inputs "{input_name}" '
                    f"({input_descriptor}) in inputs: {inputs}"
                )

            if input_name in inputs and not input_descriptor.is_value_of_expected_type(
                inputs[input_name]
            ):
                try:
                    input_value = inputs[input_name]
                    casted_input_value = _cast_value_into(input_value, input_descriptor)
                    inputs[input_name] = casted_input_value
                    logger.warning(
                        "The input value named `%s` didn't have the right type (expected `%s`). It was casted from `%s` to `%s`",
                        input_name,
                        input_descriptor,
                        input_value,
                        casted_input_value,
                    )
                except Exception:
                    raise TypeError(
                        f"The input passed: `{inputs[input_name]}` of type `{inputs[input_name].__class__.__name__}` is not of the expected type `{input_descriptor.pretty_str()}`"
                    )

        record_event(
            ConversationCreatedEvent(
                conversational_component=self,
                inputs=inputs,
                messages=messages,
                conversation_id=conversation_id,
                nesting_level=nesting_level,
            )
        )

        from wayflowcore.executors._flowexecutor import FlowConversationExecutionState

        variable_store = {v.name: deepcopy(v.default_value) for v in self.variables}

        for input_key in inputs.keys():
            if input_key not in self.input_descriptors_dict:
                raise ValueError(
                    f"Input '{input_key}' passed to start conversation is not an expected input of the Flow"
                )

        input_output_key_values = {
            io_key: input_value
            for input_key, input_value in deepcopy(inputs).items()
            for io_key in self._input_mapping_to_io_value_keys.get(input_key, [])
        }
        state = FlowConversationExecutionState(
            flow=self,
            current_step_name=self.begin_step_name,
            input_output_key_values=input_output_key_values,
            variable_store=variable_store,
            context_providers=self.context_providers if self.context_providers is not None else [],
            nesting_level=nesting_level,
        )

        return FlowConversation(
            component=self,
            inputs=inputs,
            conversation_id=IdGenerator.get_or_generate_id(conversation_id),
            message_list=messages,
            __metadata_info__={},
            status=None,
            name="flow_conversation",
            state=state,
        )

    @property
    def llms(self) -> List["LlmModel"]:
        # recompute on the fly to have all llms
        flow_steps_llms = set(llm for step in self.steps.values() for llm in step.llms)
        if hasattr(self, "_configured_llms"):
            return list(flow_steps_llms | set(self._configured_llms))
        return list(flow_steps_llms)

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        """
        Converts a flow to a nested dict of standard types such that it can be easily serialized with
        either JSON or YAML
        """
        from wayflowcore.flow import Flow
        from wayflowcore.serialization.serializer import serialize_to_dict

        serialized_flow_dict = {
            "_component_type": Flow.__name__,
            "flow_id": self.flow_id,
            "begin_step_name": self.begin_step_name,
            "variables": [serialize_to_dict(v, serialization_context) for v in self.variables],
            "steps": {
                step_name: serialize_to_dict(step, serialization_context)
                for step_name, step in self.steps.items()
            },
            "control_flow_edges": [
                serialize_to_dict(edge, serialization_context) for edge in self.control_flow_edges
            ],
            "data_flow_edges": [
                serialize_to_dict(edge, serialization_context) for edge in self.data_flow_edges
            ],
            "end_steps": self.end_steps,
            "name": self.name,
            "description": self.description,
        }

        if len(self.context_providers) > 0:
            serialized_flow_dict["context_providers"] = [
                serialize_to_dict(context_prov, serialization_context)
                for context_prov in self.context_providers
            ]

        return serialized_flow_dict

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "Flow":
        from wayflowcore.contextproviders import ContextProvider
        from wayflowcore.serialization.serializer import deserialize_from_dict
        from wayflowcore.variable import Variable

        if (
            "context_key_values_providers" in input_dict
            and len(input_dict["context_key_values_providers"]) > 0
        ):
            context_providers_dict = [
                (
                    deserialize_from_dict(Property, property_dict, deserialization_context),
                    deserialize_from_dict(
                        ContextProvider, context_provider_dict, deserialization_context
                    ),
                )
                for property_dict, context_provider_dict in input_dict[
                    "context_key_values_providers"
                ]
            ]
            context_providers_list = _convert_context_provider_dict_to_tool_provider(
                {
                    property_.name: context_provider_
                    for property_, context_provider_ in context_providers_dict
                }
            )
        elif "context_providers" in input_dict:
            context_providers_list = [
                deserialize_from_dict(
                    ContextProvider, serialized_context_provider, deserialization_context
                )
                for serialized_context_provider in input_dict["context_providers"]
            ]
        else:
            context_providers_list = None

        variables = []
        for serialized_variable in input_dict.get("variables", []):
            variable = deserialize_from_dict(Variable, serialized_variable, deserialization_context)
            variables.append(variable)

        from wayflowcore.flow import Flow
        from wayflowcore.steps.step import Step

        steps = {}
        # trick to get some additional branches from the deprecated step input_dict
        additional_transitions = {}
        for step_name, step_as_dict in input_dict["steps"].items():
            steps[step_name] = deserialize_from_dict(Step, step_as_dict, deserialization_context)
            # retrieve additional transitions
            additional_transitions[step_name] = (
                deserialization_context._consume_additional_transitions()
            )

        transitions = input_dict.get("transitions", None)
        if transitions is not None:
            for src_step_name, new_transitions in additional_transitions.items():
                transitions[src_step_name] = _handle_transitions_updates(
                    step=steps[src_step_name],
                    step_name=src_step_name,
                    old_transitions=transitions[src_step_name],
                    additional_transitions=new_transitions,
                )

        control_flow_edges: Optional[List[ControlFlowEdge]] = None
        if input_dict.get("control_flow_edges", None):
            control_flow_edges = [
                deserialize_from_dict(ControlFlowEdge, control_flow_edge, deserialization_context)
                for control_flow_edge in input_dict["control_flow_edges"]
            ]

        data_flow_edges: Optional[List[DataFlowEdge]] = None
        if input_dict.get("data_flow_edges", None):
            data_flow_edges = [
                deserialize_from_dict(DataFlowEdge, data_flow_edge, deserialization_context)
                for data_flow_edge in input_dict["data_flow_edges"]
            ]

        return Flow(
            flow_id=input_dict.get("flow_id", None),
            begin_step=steps[input_dict["begin_step_name"]],
            steps=steps,
            transitions=transitions,
            context_providers=context_providers_list,
            variables=variables,
            control_flow_edges=control_flow_edges,
            data_flow_edges=data_flow_edges,
            name=input_dict.get("name", None),
            description=input_dict.get("description", ""),
            __metadata_info__=input_dict.get("__metadata_info__", None),
        )

    def _get_flow_id(self) -> str:
        return self.flow_id

    @staticmethod
    def _convert_transition_list_into_dict(
        next_steps: Union[Sequence[Optional[str]], Mapping[str, Optional[str]]],
        src_step_name: str,
    ) -> Mapping[str, Optional[str]]:
        from wayflowcore.steps.step import Step

        if isinstance(next_steps, list):
            # remove duplicates if any
            if len(set(next_steps)) != len(next_steps):
                logger.warning(
                    f"Transitions of `{src_step_name}` contains duplicate. They will be deduplicated."
                )
                next_steps = list(set(next_steps))

            if len(next_steps) > 1 and src_step_name in next_steps:
                next_steps = [step_name for step_name in next_steps if step_name != src_step_name]

            if len(next_steps) == 1:
                return {Step.BRANCH_NEXT: next_steps[0]}
            else:
                raise ValueError(
                    f"Step `{src_step_name}` has a list of several next steps ({next_steps}). Please used a dict instead to link branch names to possible next steps"
                )

        elif isinstance(next_steps, dict):
            return next_steps
        else:
            raise ValueError(
                f"Values of the `transitions` dict should be list or dict, was {type(next_steps)}"
            )

    def _get_final_step_names_from_flow(self) -> List[Optional[str]]:
        """
        Helper method to get the final step names from a Flow instance.
        Final steps are steps that transition to None or are of type CompleteStep.
        """
        from wayflowcore.steps.completestep import CompleteStep

        return list(
            {
                *{
                    next(
                        step_name
                        for step_name, step in self.steps.items()
                        if step is control_flow_edge.source_step
                    )
                    for control_flow_edge in self.control_flow_edges
                    if control_flow_edge.destination_step is None
                },  # Get steps that transition to None
                *{
                    step_name
                    for step_name, step in self.steps.items()
                    if isinstance(step, CompleteStep)
                },  # Steps of type CompleteStep
            }
        )

    def _check_step_outputs_and_context_provider_collisions(self) -> None:
        from wayflowcore.steps.step import Step

        all_destinations_from_steps = {
            (data_edge.destination_step, data_edge.destination_input)
            for data_edge in self.data_flow_edges
            if isinstance(data_edge.source_step, Step)
        }

        all_destinations_from_context_provider = [
            (data_edge.destination_step, data_edge.destination_input)
            for data_edge in self.data_flow_edges
            if isinstance(data_edge.source_step, ContextProvider)
        ]

        all_destinations_from_context_provider_counts = Counter(
            all_destinations_from_context_provider
        )
        repeated_context_provider_destination = [
            destination
            for destination, count in all_destinations_from_context_provider_counts.items()
            if count > 1
        ]
        if any(repeated_context_provider_destination):
            raise ValueError(
                f"Found multiple context providers targeting the same destinations: "
                f"'{repeated_context_provider_destination}'"
            )

        collisions = [
            destination
            for destination in all_destinations_from_context_provider_counts
            if destination in all_destinations_from_steps
        ]
        if collisions:
            raise ValueError(
                f"Found both a context provider and a step passing data to the same step input:"
                f"'{collisions[0]}'."
            )

    @staticmethod
    def _validate_unique_variable_names(variables: List["Variable"]) -> None:
        var_names = [v.name for v in variables]
        if len(variables) != len(set(var_names)):
            raise ValueError(
                f"The list of Variables contain duplicated names: {var_names}. Variable names should be unique."
            )

    @staticmethod
    def _validate_readwrite_steps_refer_to_declared_variables(
        steps: Dict[str, "Step"], variables: List["Variable"]
    ) -> None:
        from wayflowcore.steps import VariableReadStep, VariableWriteStep

        for step_name, step in steps.items():
            if isinstance(
                step, (VariableReadStep, VariableWriteStep)
            ) and step.variable.name not in {
                v.name for v in variables
            }:  # assumes variables is a list of variables whose names are unique
                raise ValueError(
                    f"The Read/Write step '{step_name}' refers to the Variable '{step.variable.name}' "
                    "but it was not passed into the flow constructor. Make sure to pass it as an argument when "
                    "creating the flow."
                )

    @staticmethod
    def _validate_list_of_context_providers_has_unique_output_descriptor_names(
        providers: List["ContextProvider"],
    ) -> None:
        all_context_provider_keys = [
            value_description.name
            for context_prov in providers
            for value_description in context_prov.get_output_descriptors()
        ]
        if len(set(all_context_provider_keys)) < len(all_context_provider_keys):
            raise ValueError(
                "The provided list of context providers contains "
                f"non-unique output description names: {all_context_provider_keys}"
            )

    def add_context_providers(self, providers: List["ContextProvider"]) -> None:
        """
        Adds context key value providers to the flow.

        Parameters
        ----------
        providers:
            Context providers to add to the flow.
        """
        self.context_providers += providers

    @property
    def might_yield(self) -> bool:
        """
        Indicates if the flow might yield back to the user.
        ``True`` if any of the steps in the flow might yield.
        """
        # We are assuming the flow is static to be able to precompute this
        # if that ever changes, we would need to recompute it when it changes
        return self._might_yield

    def _get_llms(self) -> List["LlmModel"]:
        return list(set(llm for step in self.steps.values() for llm in step.llms))

    def _get_end_steps(self) -> List[str]:
        return list(
            {step_name for step_name, step in self.steps.items() if _is_step_a_complete_step(step)},
        )

    def _get_outgoing_branches(self) -> List[str]:
        return list(
            {
                step.branch_name or step_name
                for step_name, step in self.steps.items()
                if _is_step_a_complete_step(step)
            }
        )

    def _has_transitions_to_none(self) -> bool:
        return any(
            control_flow_edge
            for control_flow_edge in self.control_flow_edges
            if control_flow_edge.destination_step is None
        )

    def _get_step(self, step_name: str) -> "Step":
        return self.steps[step_name]

    @staticmethod
    def from_steps(
        steps: List["Step"],
        data_flow_edges: Optional[List[DataFlowEdge]] = None,
        context_providers: Optional[list[ContextProvider]] = None,
        variables: Optional[List["Variable"]] = None,
        loop: bool = False,
        step_names: Optional[List[str]] = None,
        name: Optional[str] = None,
        description: str = "",
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
    ) -> "Flow":
        """Helper method to create a sequential flow from a list of steps. Each step will be executed in the order
        they are passed.

        Parameters
        ----------
        steps:
            the steps to create an assistant from
        data_flow_edges:
            list of data flow edges
        context_providers:
            list of context providers
        variables:
            list of variables
        loop:
            whether the flow should loop back the first step or finish after the last step.
        step_names:
            List of step names. Will default to "step_{idx}" if not passed.
        name:
            Name of the flow
        description:
            Description of the flow
        input_descriptors:
            Input descriptors of the flow
        output_descriptors:
            Output descriptors of the flow

        Examples
        --------

        Create a flow in one line using this function:

        >>> from wayflowcore.flow import Flow
        >>> from wayflowcore.steps import OutputMessageStep
        >>> flow = Flow.from_steps(
        ...     steps=[
        ...         OutputMessageStep('step 1 executes'),
        ...         OutputMessageStep('step 2 executes'),
        ...         OutputMessageStep('step 3 executes'),
        ...     ],
        ... )

        """
        if len(steps) == 0:
            raise ValueError("Should pass at least one step, but passed an empty list.")

        if step_names is None:
            for idx, step in enumerate(steps):
                if step.name is None or IdGenerator.is_auto_generated(step.name):
                    step.name = f"step_{idx}"
        else:
            if len(step_names) != len(steps):
                raise ValueError(
                    f"Should have the same amount of steps and step_names, but got {len(step_names)} steps and {len(steps)} step names"
                )
            for step_name, step in zip(step_names, steps):
                step.name = step_name

        return Flow(
            begin_step=steps[0],
            steps=steps,
            control_flow_edges=[
                ControlFlowEdge(
                    source_step=step,
                    source_branch=branch_name,
                    destination_step=steps[step_idx + 1],
                )
                for step_idx, step in enumerate(steps[:-1])
                for branch_name in step.get_branches()
            ]
            + [
                ControlFlowEdge(
                    source_step=steps[-1],
                    source_branch=branch_name,
                    destination_step=None if not loop else steps[0],
                )
                for branch_name in steps[-1].get_branches()
            ],
            data_flow_edges=data_flow_edges,
            context_providers=context_providers,
            variables=variables,
            name=name,
            description=description,
            output_descriptors=output_descriptors,
            input_descriptors=input_descriptors,
        )

    def clone(self, name: str, description: str) -> "Flow":
        """Clones a flow with a different name and description"""
        return Flow(
            begin_step=self.begin_step,
            steps=self.steps,
            control_flow_edges=self.control_flow_edges,
            data_flow_edges=self.data_flow_edges,
            context_providers=self.context_providers,
            variables=self.variables,
            name=name,
            description=description,
            flow_id=self.flow_id,
        )

    def as_client_tool(self) -> "ClientTool":
        """Converts this flow into a client tool"""
        from wayflowcore.tools import ClientTool
        from wayflowcore.tools.tools import _sanitize_tool_name

        return ClientTool(
            name=_sanitize_tool_name(self.name),
            description=self.description or "",
            input_descriptors=self.input_descriptors,
            output_descriptors=(
                self.output_descriptors
                if len(self.output_descriptors) == 1
                else [
                    ObjectProperty(
                        properties={
                            property_.name: property_ for property_ in self.output_descriptors
                        }
                    )
                ]
            ),  # TODO change when tools support several outputs
        )

    def as_server_tool(self) -> "ServerTool":
        """Converts this flow into a server tool. Can only convert non-yielding flows"""
        from wayflowcore.tools import ServerTool

        return ServerTool.from_flow(
            flow=self,
            flow_name=self.name,
            flow_description=self.description or "",
        )

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        all_tools = {}

        if recursive:
            for step in self.steps.values():
                all_tools.update(
                    step._referenced_tools_dict(recursive=True, visited_set=visited_set)
                )

            for context_provider in self.context_providers or []:
                all_tools.update(
                    context_provider._referenced_tools_dict(recursive=True, visited_set=visited_set)
                )

        return all_tools
