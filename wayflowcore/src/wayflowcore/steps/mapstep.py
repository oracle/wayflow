# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

import jq

from wayflowcore._metadata import MetadataType
from wayflowcore._threading import get_threadpool
from wayflowcore._utils.async_helpers import run_async_function_in_parallel
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.executors.interrupts.executioninterrupt import InterruptedExecutionStatus
from wayflowcore.property import AnyProperty, DictProperty, ListProperty, Property
from wayflowcore.steps.step import Step, StepExecutionStatus, StepResult
from wayflowcore.tools import Tool

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation
    from wayflowcore.flow import Flow


logger = logging.getLogger(__name__)

_MAX_NUM_WORKERS: int = 20
"""Maximal number of concurrent flows ran in the MapStep"""


class MapStep(Step):
    _input_descriptors_change_step_behavior = True
    # it changes how the map step iterates, either on a dict or on a list
    _output_descriptors_change_step_behavior = (
        True  # it changes what outputs are collected from the inside flow
    )

    _CURRENT_ITEM_KEY = "map_item_currently_processing_key"
    _ALL_OUTPUTS_KEY = "map_outputs_key"
    ITERATED_INPUT = "iterated_input"
    """str: Input key for the iterable to use the ``MapStep`` on."""

    def __init__(
        self,
        flow: "Flow",
        unpack_input: Optional[Dict[str, str]] = None,
        parallel_execution: bool = False,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Step to execute an inside flow on all the elements of an iterable. Order in the iterable is guaranteed the same
        as order of execution.

        Note
        ----

        A step has input and output descriptors, describing what values the step requires to run and what values it produces.

        **Input descriptors**

        By default, when ``input_descriptors`` is set to ``None``, this step will have several inputs descriptors.
        One will be named ``MapStep.ITERATED_INPUT`` of type ``ListProperty`` will be the iterable on which the step
        will iterate. The step will also expose all input descriptors of the ``flow`` it runs if their names
        are not in the ``unpack_input`` mapping (if they are, these values are extracted from ``MapStep.ITERATED_INPUT``).
        See :ref:`Flow <Flow>` to learn more about how flow input descriptors are resolved.

        If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
        in particular using the new type instead of the detected one. In particular, the type of
        ``MapStep.ITERATED_INPUT`` will impact the way the step iterates on the iterable (see ``unpack_input``
        parameter for more details).

        If some of them are missing, an error will be thrown at instantiation of the step.

        If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
        they won't be used during the execution of the step.

        **Output descriptors**

        By default, when ``output_descriptors`` is set to ``None``, this step will not have any output descriptor.

        If you provide a list of output descriptors, their names much match with the names of the output
        descriptors of the inside ``flow`` and their type should be ``ListProperty``.
        This way. the step will collect the output of each iteration of the inside ``flow`` into these outputs.

        Parameters
        ----------
        flow:
            Flow that is being executed with each iteration of the input.
        unpack_input:
            Mapping to specify how to unpack when each iter item is a ``dict`` and we need to map its element to the inside flow inputs.

            .. note::
                Keys are names of input variables of the inside flow, while values are jq queries to extract a specific part of each iterated item (see https://jqlang.github.io/jq/ for more information on jq queries). Using the item as-is can be done with the ``.`` query.
                If the iterated input type is ``dict``, then the iterated items will be key/value pairs and you can access both using ``._key`` and ``._value`` as jq queries.
        parallel_execution:
            Executes the mapping operation in parallel. Cannot be set to true if the internal flow can yield. This feature is
            in beta, be aware that flows might have side effects on one another. Each thread will use a different IO dict, but they will all share
            the same message list.
        input_descriptors:
            Input descriptors of the step. ``None`` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.

            .. warning::
                Setting this value to something else than ``None`` will change the behavior of the step. The step will
                iterate differently depending on the type of the ``MapStep.ITERATED_INPUT`` descriptor and the
                value of ``unpack_inputs``

        output_descriptors:
            Output descriptors of the step. ``None`` means the step will resolve them automatically using its static
            configuration in a best effort manner.

            .. warning::
                Setting this value to something else than ``None`` will change the behavior of the step. It will try to collect
                these output descriptors values from the outputs of each run of the inside ``flow``.

        name:
            Name of the step.

        input_mapping:
            Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.

        output_mapping:
            Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.

        Notes
        -----
        If the mapping between iterated items and the inside
        flow input is 1 to 1 (``unpack_input`` is a ``str``), then the ``iterated_input_type`` subtype will be inferred from the inside flow's input type.
        Otherwise, it will be set to ``AnyType``.

        Examples
        --------
        >>> from wayflowcore.steps import MapStep, OutputMessageStep
        >>> from wayflowcore.flowhelpers import create_single_step_flow
        >>> from wayflowcore.property import DictProperty, AnyProperty, Property

        You can iterate in simple lists:

        >>> sub_flow = create_single_step_flow(OutputMessageStep(message_template="username={{user}}"), step_name='step')
        >>> step = MapStep(
        ...     flow=sub_flow,
        ...     unpack_input={'user': '.'},
        ...     output_descriptors=[AnyProperty(name=OutputMessageStep.OUTPUT)],
        ... )
        >>> iterable = ["a", "b"]
        >>> assistant = create_single_step_flow(step, 'step')
        >>> conversation = assistant.start_conversation(inputs={MapStep.ITERATED_INPUT: iterable})
        >>> status = conversation.execute()
        >>> status.output_values
        {'output_message': ['username=a', 'username=b']}

        You can also extract from list of elements:

        >>> sub_flow=create_single_step_flow(OutputMessageStep(message_template="{{user}}:{{email}}"), step_name='step')
        >>> step = MapStep(
        ...     flow=sub_flow,
        ...     unpack_input={
        ...        'user': '.username',
        ...        'email': '.email',
        ...     },
        ...     output_descriptors=[AnyProperty(name=OutputMessageStep.OUTPUT)],
        ... )
        >>> iterable = [
        ...     {"username": "a", "email": "a@oracle.com"},
        ...     {"username": "b", "email": "b@oracle.com"},
        ... ]
        >>> assistant = create_single_step_flow(step, 'step')
        >>> conversation = assistant.start_conversation(inputs={MapStep.ITERATED_INPUT: iterable})
        >>> status = conversation.execute()
        >>> status.output_values
        {'output_message': ['a:a@oracle.com', 'b:b@oracle.com']}

        You can also iterate through dictionaries:

        >>> sub_flow=create_single_step_flow(OutputMessageStep(message_template="{{user}}:{{email}}"), step_name='step')
        >>> step = MapStep(
        ...     flow=sub_flow,
        ...     unpack_input={
        ...        'user': '._key',
        ...        'email': '._value.email',
        ...     },
        ...     input_descriptors=[DictProperty(name=MapStep.ITERATED_INPUT, value_type=AnyProperty('inner_value'))],
        ...     output_descriptors=[AnyProperty(name=OutputMessageStep.OUTPUT)],
        ... )
        >>> iterable = {
        ...     'a': {"username": "a", "email": "a@oracle.com"},
        ...     'b': {"username": "b", "email": "b@oracle.com"},
        ... }
        >>> assistant = create_single_step_flow(step, 'step')
        >>> conversation = assistant.start_conversation(inputs={MapStep.ITERATED_INPUT: iterable})
        >>> status = conversation.execute()
        >>> status.output_values
        {'output_message': ['a:a@oracle.com', 'b:b@oracle.com']}

        """
        if isinstance(output_descriptors, list) and len(output_descriptors) > 0:
            output_descriptors = [
                (
                    ListProperty(
                        name=(
                            output_mapping.get(output, output)
                            if output_mapping is not None
                            else output
                        ),
                        item_type=AnyProperty(),
                    )
                    if isinstance(output, str)
                    else output
                )
                for output in output_descriptors
            ]

        super().__init__(
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            step_static_configuration=dict(
                flow=flow,
                unpack_input=unpack_input,
                parallel_execution=parallel_execution,
            ),
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )

        self.flow = flow
        self.unpack_input = unpack_input or {}
        self.unpack_jq_processors = {
            var_name: jq.compile(query) for var_name, query in self.unpack_input.items()
        }
        self.parallel_execution = parallel_execution

    @staticmethod
    def _extract_iterated_descriptor(
        input_descriptors: Optional[List[Property]],
    ) -> Optional[Property]:
        if input_descriptors is None:
            # can be resolved automatically
            return None

        for input_descriptor in input_descriptors:
            if input_descriptor.name == MapStep.ITERATED_INPUT:
                if not isinstance(input_descriptor, (DictProperty, ListProperty, AnyProperty)):
                    raise ValueError(
                        "Can't iterate through another type than ListProperty or DictProperty"
                    )
                return input_descriptor

        raise ValueError(
            "Input descriptors of the MapStep should contain ``MapStep.ITERATED_INPUT``"
        )

    @staticmethod
    def _validate_inputs(
        flow: "Flow",
        unpack_input: Optional[Dict[str, str]],
        input_descriptors: Optional[List[Property]],
        output_descriptors: Optional[List[Property]],
        parallel_execution: bool,
    ) -> None:
        if parallel_execution and flow.might_yield:
            raise ValueError("MapStep does not support parallelism on flows that might yield")
        elif parallel_execution:
            logger.info(
                """Parallel execution with MapStep is a beta feature. It does not support flow
that can yield, and is prone to side effects. We recommend not using sub-flows with side effects, and be aware that
messages may be posted in the order they are produced, in this case not deterministically."""
            )

        iterated_descriptor = MapStep._extract_iterated_descriptor(input_descriptors)

        if unpack_input is None:
            if isinstance(iterated_descriptor, DictProperty):
                raise ValueError("To iterate in a dict or any, we need an `unpack_input` mapping")
            else:
                # we just iterate
                pass
        elif not isinstance(unpack_input, dict):
            raise ValueError(
                f"unpack_input should be either None or a dict, but was: {unpack_input.__class__.__name__}"
            )
        elif len(unpack_input) == 1:
            # 1:1 mapping
            inside_var_name = next(iter(unpack_input.keys()))
            if inside_var_name not in flow.input_descriptors_dict:
                raise ValueError(
                    f'Inside flow does not contain an input named "{inside_var_name}", flow_inputs={list(flow.input_descriptors_dict.keys())}"'
                )
            inside_var_flow_type = flow.input_descriptors_dict[inside_var_name]
            if (
                isinstance(iterated_descriptor, ListProperty)
                and not inside_var_flow_type._match_type_of(iterated_descriptor.item_type)
                and not (
                    isinstance(inside_var_flow_type, AnyProperty)
                    or isinstance(iterated_descriptor, AnyProperty)
                )
                and next(iter(unpack_input.values())) == "."
            ):
                raise ValueError(
                    f"Given {iterated_descriptor.item_type} is not compatible for 1:1 mapping with inside flow variable {inside_var_flow_type}"
                )
        else:
            # 1:N mapping
            for input_name in unpack_input:
                if input_name not in flow.input_descriptors_dict:
                    raise ValueError(
                        f'Inside flow does not contain an input named "{input_name}", flow_inputs={list(flow.input_descriptors_dict.keys())}"'
                    )

        for o in output_descriptors or []:
            if o.name not in flow.output_descriptors_dict:
                raise ValueError(
                    f'Inside flow does not contain an output named "{o.name}" ({o}), flow_outputs={list(flow.output_descriptors_dict.keys())}"'
                )
            if not isinstance(o, (ListProperty, AnyProperty)):
                raise ValueError(f"Collected output {o} should be of type {ListProperty.__name__}")

    def sub_flow(self) -> Optional["Flow"]:
        return self.flow

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, Any]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        from wayflowcore.flow import Flow

        return {
            "flow": Flow,
            "unpack_input": Optional[Dict[str, str]],
            "parallel_execution": bool,
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        flow: "Flow",
        unpack_input: Optional[Dict[str, str]],
        input_descriptors: Optional[List[Property]],
        output_descriptors: Optional[List[Property]],
        parallel_execution: bool,
    ) -> List[Property]:
        MapStep._validate_inputs(
            flow, unpack_input, input_descriptors, output_descriptors, parallel_execution
        )

        iterated_input_names = set(unpack_input.keys()) if unpack_input else {}

        iterated_descriptor = MapStep._extract_iterated_descriptor(input_descriptors)

        if input_descriptors is not None and iterated_descriptor is not None:
            # already all specified in the input descriptors
            return input_descriptors

        # inputs that are not iterated
        resolved_input_descriptors = {
            k: v.copy(name=k)
            for k, v in flow.input_descriptors_dict.items()
            if k not in iterated_input_names
        }

        # we try to detect it automatically
        if (
            unpack_input is None
            or len(unpack_input) != 1
            or next(iter(unpack_input.values())) != "."
        ):
            # cannot detect the type -> fallback to AnyProperty
            item_value_type: Property = AnyProperty()
        else:
            # can take the inside flow var type
            inside_var_name = next(iter(unpack_input))
            item_value_type = flow.input_descriptors_dict[inside_var_name]

        resolved_input_descriptors[cls.ITERATED_INPUT] = ListProperty(
            name=cls.ITERATED_INPUT,
            description="iterated input for the map step",
            item_type=item_value_type,
        )
        return list(resolved_input_descriptors.values())

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        flow: "Flow",
        unpack_input: Optional[Dict[str, str]],
        input_descriptors: Optional[List[Property]],
        output_descriptors: Optional[List[Property]],
        parallel_execution: bool,
    ) -> List[Property]:
        return output_descriptors or []

    # override
    @property
    def might_yield(self) -> bool:
        # the internal flow might yield
        return self.flow.might_yield

    def _get_iter(self, conversation: "FlowConversation") -> Any:
        return (
            conversation._get_internal_context_value_for_step(self, MapStep._CURRENT_ITEM_KEY) or 0
        )

    def _prepare_inputs(self, inputs: Dict[str, Any], iter_idx: int) -> Dict[str, Any]:
        sub_step_input = deepcopy(inputs)

        input_iterable = sub_step_input.pop(self.ITERATED_INPUT)

        if isinstance(input_iterable, list) and len(self.unpack_input) > 0:
            # case #2, list of Any to extract
            element_to_explode = input_iterable[iter_idx]
            for var_name, j_query in self.unpack_input.items():
                sub_step_input[var_name] = jq.compile(j_query).input(element_to_explode).first()
        elif isinstance(input_iterable, dict):
            # case #3, dict to loop on
            input_iterable = [
                {"_key": key, "_value": value} for key, value in input_iterable.items()
            ]
            element_to_explode = input_iterable[iter_idx]
            for var_name, jq_processor in self.unpack_jq_processors.items():
                sub_step_input[var_name] = jq_processor.input(element_to_explode).first()

        return sub_step_input

    async def _compute_one_iteration_no_yielding(
        self,
        inputs: Dict[str, Any],
        idx: int,
        conversation: "FlowConversation",
    ) -> Dict[str, Any]:
        sub_step_input = self._prepare_inputs(inputs=inputs, iter_idx=idx)

        sub_conversation = conversation._create_sub_conversation(
            inputs=sub_step_input,
            flow=self.flow,
            step=self,
        )

        status = await sub_conversation.execute_async()

        if not isinstance(status, FinishedStatus):
            raise ValueError("Internal error, flows in parallel should not yield")

        # extract the outputs
        return self._extract_iteration_outputs(status)

    async def _invoke_step_async(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        max_num_iter = len(inputs[self.ITERATED_INPUT])

        if self.parallel_execution:

            async def execute_one_branch(idx: int) -> Dict[str, Any]:
                return await self._compute_one_iteration_no_yielding(
                    inputs=inputs,
                    idx=idx,
                    conversation=conversation,
                )

            # for backward compatibility, we check whether a threadpool
            # was started manually, otherwise we use a default number of workers
            max_workers = get_threadpool(start_threadpool=False).max_workers or _MAX_NUM_WORKERS

            all_outputs = await run_async_function_in_parallel(
                func_async=execute_one_branch,
                input_list=list(range(max_num_iter)),
                max_workers=max_workers,
            )

            output_names = {v.name for v in self._internal_output_descriptors}
            return StepResult(
                # from list of dicts to dict of lists
                outputs={v: [output[v] for output in all_outputs] for v in output_names},
                branch_name=self.BRANCH_NEXT,
                step_type=StepExecutionStatus.PASSTHROUGH,
            )

        while self._get_iter(conversation) < max_num_iter:

            sub_step_input = self._prepare_inputs(
                inputs=inputs,
                iter_idx=self._get_iter(conversation),
            )

            sub_conversation = conversation._get_or_create_current_sub_conversation(
                step=self,
                flow=self.flow,
                inputs=sub_step_input,
            )

            logger.debug(
                f"Executing iteration ({self._get_iter(conversation)+1}/{max_num_iter}) on: {sub_step_input}"
            )
            status = await sub_conversation.execute_async()

            if isinstance(status, InterruptedExecutionStatus):
                return StepResult(
                    # We return the status so that it can be propagated
                    outputs={"__execution_status__": status},
                    branch_name=self.BRANCH_SELF,
                    step_type=StepExecutionStatus.INTERRUPTED,
                )

            if status._requires_yielding:
                return StepResult(
                    outputs={
                        "__execution_status__": status
                    },  # yielding means it will come back to it, so no need to fill the outputs
                    branch_name=self.BRANCH_SELF,
                    step_type=StepExecutionStatus.YIELDING,
                )
            elif not isinstance(status, FinishedStatus):
                raise ValueError(f"Unsupported execution status: {status}")

            conversation._cleanup_sub_conversation(step=self)

            conversation._put_internal_context_key_value_for_step(
                self,
                MapStep._CURRENT_ITEM_KEY,
                self._get_iter(conversation) + 1,
            )

            outputs = self._extract_iteration_outputs(status)

            conversation._put_internal_context_key_value_for_step(
                self,
                MapStep._ALL_OUTPUTS_KEY,
                (
                    conversation._get_internal_context_value_for_step(
                        self, MapStep._ALL_OUTPUTS_KEY
                    )
                    or []
                )
                + [outputs],
            )

        conversation._put_internal_context_key_value_for_step(self, MapStep._CURRENT_ITEM_KEY, None)
        all_outputs = (
            conversation._get_internal_context_value_for_step(self, MapStep._ALL_OUTPUTS_KEY) or []
        )
        conversation._put_internal_context_key_value_for_step(self, MapStep._ALL_OUTPUTS_KEY, None)

        if len(self._internal_output_descriptors) > 0:
            final_outputs = {
                v.name: [s[v.name] for s in all_outputs] for v in self._internal_output_descriptors
            }
        else:
            final_outputs = {}

        return StepResult(outputs=final_outputs)

    def _extract_iteration_outputs(self, status: FinishedStatus) -> Dict[str, type]:
        outputs = status.output_values
        output_names = {v.name for v in self._internal_output_descriptors}
        outputs = {k: v for k, v in outputs.items() if k in output_names}
        return outputs

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        all_tools = {}

        if recursive:
            all_tools.update(
                self.flow._referenced_tools_dict(recursive=True, visited_set=visited_set)
            )

        return all_tools
