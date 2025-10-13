# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, cast

from wayflowcore._metadata import MetadataType
from wayflowcore.executors._flowexecutor import FlowConversationExecutor
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.executors.interrupts.executioninterrupt import InterruptedExecutionStatus
from wayflowcore.property import Property
from wayflowcore.steps.step import Step, StepExecutionStatus, StepResult
from wayflowcore.tools import Tool

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation
    from wayflowcore.flow import Flow


logger = logging.getLogger(__name__)


class FlowExecutionStep(Step):
    """Executes a flow inside a step."""

    def __init__(
        self,
        flow: "Flow",
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Note
        ----

        A step has input and output descriptors, describing what values the step requires to run and what values it produces.

        **Input descriptors**

        By default, when ``input_descriptors`` is set to ``None``, the input_descriptors will be automatically inferred
        from the input descriptors of the ``flow`` that this step will run.
        See :ref:`Flow <Flow>` to learn more about how flow inputs are resolved.

        If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
        in particular using the new type instead of the detected one.
        If some of them are missing, an error will be thrown at instantiation of the step.

        If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
        they won't be used during the execution of the step.

        **Output descriptors**

        The outputs descriptors of this step are the same as the outputs descriptors of the ``flow`` that this step will run.
        See :ref:`Flow <Flow>` to learn more about how flow outputs are resolved.

        **Branches**

        This step can have several next steps and perform conditional branching depending on where the ``flow`` finishes.
        This step will have one branch per name of ``CompleteStep`` present in the ``flow``, plus an additional one named
        ``FlowExecutionStep.NEXT_STEP`` if the inside ``flow`` contains transitions to ``None``.

        Parameters
        ----------
        flow:
            ``Flow`` that the step needs to execute.
        input_descriptors:
            Input descriptors of the step. ``None`` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.

        output_descriptors:
            Output descriptors of the step. ``None`` means the step will resolve them automatically using its static
            configuration in a best effort manner.

        name:
            Name of the step.

        input_mapping:
            Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.

        output_mapping:
            Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.

        Example
        -------
        The ``FlowExecutionStep`` is particularly suitable when subflows can be reused inside a wayflowcore project.
        Let's see an example with a flow that estimates numerical value using the "wisdowm of the crowd" effect:

        >>> from typing import List
        >>> from wayflowcore.property import Property, StringProperty, ListProperty
        >>> from wayflowcore.flowhelpers import create_single_step_flow
        >>> from wayflowcore.flow import Flow
        >>> from wayflowcore.steps import MapStep, PromptExecutionStep, ToolExecutionStep
        >>> from wayflowcore.tools import ServerTool
        >>> def duplication_func(element: str, n: int) -> List[str]:
        ...     return [element for _ in range(n)]
        ...
        >>> duplication_tool = ServerTool(
        ...     name="duplication_tool", description="",
        ...     parameters={
        ...         "element": {"description": "", "type": "string"},
        ...         "n": {"description": "", "type": "integer"},
        ...     },
        ...     func=duplication_func, output={'type': 'array'},
        ... )
        >>> def reduce_func(elements: List[str]) -> str:
        ...     import re
        ...     extracted_elements = [re.search('-?\\d*\\.?\\d+', elt) for elt in elements]
        ...     extracted_numbers = [float(x.group(0)) for x in extracted_elements if x is not None] or [-1.]
        ...     return str(sum(extracted_numbers) / len(extracted_numbers))
        ...
        >>> reduce_tool = ServerTool(
        ...     name="reduce_tool", description="",
        ...     parameters={"elements": {"description": "", "type": "array"}},
        ...     func=reduce_func, output={'type': 'string'},
        ... )
        >>> # Defining step names
        >>> DUPLICATION_STEP = "DUPLICATION"
        >>> REASONING_STEP = "REASONING"
        >>> MAP_STEP = "MAP"
        >>> REDUCE_STEP = "REDUCE"
        >>> # Defining flow input/output variables
        >>> USER_QUERY_IO = "$user_query"
        >>> N_REPEAT_IO = "$n_repeat"
        >>> FLOW_ITERABLE_QUERIES_IO = "$flow_iterable_queries"
        >>> FLOW_PROCESSED_QUERIES_IO = "$flow_processed_queries"
        >>> FINAL_ANSWER_IO = "$answer_io"
        >>> # Defining a simple prompt
        >>> REASONING_PROMPT_TEMPLATE = '''Provide your best numerical estimate for: {{user_input}}
        ... Your answer should be a single number. Do not include any units, reasoning, or extra text.'''
        >>> # Defining the subflow
        >>> mapreduce_flow = Flow(
        ...     begin_step_name=DUPLICATION_STEP,
        ...     steps={
        ...         DUPLICATION_STEP: ToolExecutionStep(
        ...             tool=duplication_tool,
        ...             input_mapping={"element": USER_QUERY_IO, "n": N_REPEAT_IO},
        ...             output_mapping={ToolExecutionStep.TOOL_OUTPUT: FLOW_ITERABLE_QUERIES_IO},
        ...         ),
        ...         MAP_STEP: MapStep(
        ...             flow=create_single_step_flow(
        ...                 PromptExecutionStep(
        ...                     prompt_template=REASONING_PROMPT_TEMPLATE,
        ...                     llm=llm,
        ...                     output_mapping={PromptExecutionStep.OUTPUT: FLOW_PROCESSED_QUERIES_IO},
        ...                 ),
        ...                 step_name=REASONING_STEP
        ...             ),
        ...             unpack_input={"user_input": "."},
        ...             output_descriptors=[ListProperty(name=FLOW_PROCESSED_QUERIES_IO, item_type=StringProperty())],
        ...             input_mapping={MapStep.ITERATED_INPUT: FLOW_ITERABLE_QUERIES_IO},
        ...         ),
        ...         REDUCE_STEP: ToolExecutionStep(
        ...             tool=reduce_tool,
        ...             input_mapping={"elements": FLOW_PROCESSED_QUERIES_IO},
        ...             output_mapping={ToolExecutionStep.TOOL_OUTPUT: FINAL_ANSWER_IO},
        ...         )
        ...     },
        ...     transitions={DUPLICATION_STEP: [MAP_STEP], MAP_STEP: [REDUCE_STEP], REDUCE_STEP: [None]}
        ... )

        Once the subflow is created we can simply integrate it with the ``FlowExecutionStep``:

        >>> from wayflowcore.flow import Flow
        >>> from wayflowcore.steps import FlowExecutionStep, OutputMessageStep
        >>> MAPREDUCE_STEP = "MAPREDUCE"
        >>> OUTPUT_STEP = "OUTPUT"
        >>> assistant = Flow(
        ...     begin_step_name=MAPREDUCE_STEP,
        ...     steps={
        ...         MAPREDUCE_STEP: FlowExecutionStep(mapreduce_flow),
        ...         OUTPUT_STEP: OutputMessageStep("The estimation is {{value}}", input_mapping={"value": FINAL_ANSWER_IO})
        ...     },
        ...     transitions={MAPREDUCE_STEP: [OUTPUT_STEP], OUTPUT_STEP: [None]}
        ... )
        >>> conversation = assistant.start_conversation(inputs={
        ...     USER_QUERY_IO: "How many calories are in a typical slice of pepperoni pizza?",
        ...     N_REPEAT_IO: 2
        ... })
        >>> status = conversation.execute()
        >>> # print(conversation.get_last_message().content)
        >>> # The estimation is 285.5

        """
        super().__init__(
            llm=flow._get_llms()[0] if flow._get_llms() else None,
            step_static_configuration=dict(flow=flow),
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )

        self.flow: "Flow" = flow

    def sub_flow(self) -> "Flow":
        return self.flow

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        from wayflowcore.flow import Flow

        return {
            "flow": Flow,
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        flow: "Flow",
    ) -> List[Property]:
        input_descriptors = [v.copy(name=k) for k, v in flow.input_descriptors_dict.items()]
        return input_descriptors

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        flow: "Flow",
    ) -> List[Property]:
        output_descriptors = [v.copy(name=k) for k, v in flow.output_descriptors_dict.items()]
        return output_descriptors

    @classmethod
    def _compute_internal_branches_from_static_config(
        cls,
        flow: "Flow",
    ) -> List[str]:
        outgoing_branches = set(flow._get_outgoing_branches())
        if len(outgoing_branches) == 0 or flow._has_transitions_to_none():
            # transitions to None are a `NEXT` branch
            outgoing_branches.add(cls.BRANCH_NEXT)
        return list(outgoing_branches)

    # override
    @property
    def might_yield(self) -> bool:
        """
        Indicates if the step might yield back to the user.
        It depends on the subflow we are executing
        """
        return self.flow.might_yield

    async def _invoke_step_async(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        sub_conversation = conversation._get_or_create_current_sub_conversation(
            step=self,
            flow=self.flow,
            inputs=inputs,
        )
        status = await sub_conversation.execute_async()

        if isinstance(status, InterruptedExecutionStatus):
            return StepResult(
                # We return the status so that it can be propagated
                outputs={"__execution_status__": status},
                branch_name=self.BRANCH_SELF,
                step_type=StepExecutionStatus.INTERRUPTED,
            )
        if not isinstance(status, FinishedStatus):
            return StepResult(
                outputs={
                    "__execution_status__": status
                },  # yielding means it will come back to it, so no need to fill the outputs
                branch_name=self.BRANCH_SELF,
                step_type=StepExecutionStatus.YIELDING,
            )

        FlowConversationExecutor().cleanup_sub_conversation(
            conversation.state,
            self,
        )

        if status.complete_step_name is not None:
            # If the subflow ends by landing on a CompleteStep, the next step
            # depends on the complete step we landed on
            from wayflowcore.steps import CompleteStep

            complete_step: CompleteStep = cast(
                CompleteStep, self.flow.steps[status.complete_step_name]
            )
            next_branch_name: str = complete_step.branch_name or status.complete_step_name
        else:
            # Otherwise (if the subflow exits due to transition to None)
            # we get the next step from the conversation
            next_branch_name = self.BRANCH_NEXT

        return StepResult(outputs=status.output_values, branch_name=next_branch_name)

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        all_tools = {}

        if recursive:
            all_tools.update(
                self.flow._referenced_tools_dict(recursive=True, visited_set=visited_set)
            )

        return all_tools
