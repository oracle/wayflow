# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, cast

from wayflowcore._metadata import MetadataType
from wayflowcore.executors._flowexecutor import (
    FlowConversationExecutionState,
    FlowConversationExecutor,
)
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.property import BooleanProperty, IntegerProperty, Property
from wayflowcore.steps import FlowExecutionStep
from wayflowcore.steps.step import Step, StepExecutionStatus, StepResult
from wayflowcore.tools import Tool

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation
    from wayflowcore.flow import Flow

logger = logging.getLogger(__name__)

_MAX_RETRY = 20


class RetryStep(Step):

    NUM_RETRIES_VAR = "retry_step_num_retries"
    """str: Output key for the number of retries the retry step took to succeed or exit."""
    SUCCESS_VAR = "retry_step_success"
    """str: Output key for whether the retry step succeeded in the end or not."""
    MAX_RETRY = _MAX_RETRY
    """int: Global upper limit on the number of retries for the ``RetryStep``."""

    BRANCH_FAILURE = "failure"
    """Name of the branch taken in case the condition is still not met after the maximum number of trials"""

    def __init__(
        self,
        flow: "Flow",
        success_condition: str,
        max_num_trials: int = 5,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Step that can be used to execute a given ``Flow`` and retries if a success condition
        is not met.

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

        By default, when ``output_descriptors`` is set to ``None``, the outputs descriptors of this step will be
        the same as the outputs descriptors of the ``flow`` that this step will run.
        See :ref:`Flow <Flow>` to learn more about how flow outputs are resolved.

        It also has two additional descriptors:

        * ``RetryStep.SUCCESS_VAR``: ``BooleanProperty()``, whether the step succeeded or not.
        * ``RetryStep.NUM_RETRIES_VAR``: ``IntegerProperty()``, the number of trials the step used to succeed.

        **Branches**

        This step can have several next steps and perform conditional branching based on how the execution went. It has all the
        branches exposed by the ``flow`` it runs (see :ref:`FlowExecutionStep <flowexecutionstep>` to learn more about how flow branches are resolved).

        It has an additional branch, named ``RetryStep.BRANCH_FAILURE``, that is taken in case the step runs out of ``max_num_trials``.


        Parameters
        ----------
        flow:
            Flow to be executed inside the ``RetryStep``.
        success_condition:
            Name of the variable in the flow that defines success. The success is evaluated
            with ``bool(flow_output[success_condition])``
        max_num_trials:
            Maximum number of times to retry the flow execution. Defaults to 5.

            .. warning::
                ``max_num_trials`` should not exceed ``MAX_RETRY`` retries.
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

        Examples
        --------
        >>> from wayflowcore.steps import ExtractValueFromJsonStep, PromptExecutionStep, RetryStep
        >>> from wayflowcore.property import Property, BooleanProperty

        >>> prompt_step = PromptExecutionStep(llm=llm, prompt_template=(
        ...     "Please answer whether the following user query is a relevant HR question."
        ...     "User query: {{user_query}}"
        ...     'Answer with a json containing: {"in_domain": "false/true as string", "reason": "text explaining why its classified this way"}'
        ... ), output_mapping={PromptExecutionStep.OUTPUT: ExtractValueFromJsonStep.TEXT})
        >>> json_step = ExtractValueFromJsonStep(
        ...     output_values = {
        ...         'in_domain': '.in_domain',
        ...         'reason': '.reason',
        ...         BooleanProperty(name='success'): ' has("reason")'}
        ... )
        >>> from wayflowcore.flow import Flow
        >>> from wayflowcore.flowhelpers import run_single_step
        >>> retry_step = RetryStep(
        ...     flow = Flow.from_steps([prompt_step, json_step]),
        ...     success_condition="success",
        ... )
        >>> conv, messages = run_single_step(retry_step, inputs={'user_query': 'how many vacation days to I have left?'})

        """

        if success_condition not in flow.output_descriptors_dict:
            raise ValueError(
                f"Inside flow should produce the success_condition output: `{success_condition}`,"
                f" but outputs are: {list(flow.output_descriptors_dict.keys())}",
            )

        if max_num_trials < 0:
            raise ValueError(
                f"Negative value not permitted for `max_num_trials` argument ({max_num_trials})"
            )
        elif max_num_trials > self.MAX_RETRY:
            raise ValueError(
                f"The number of retries should not exceed {self.MAX_RETRY}, but was {max_num_trials}"
            )

        super().__init__(
            llm=flow._get_llms()[0] if flow._get_llms() else None,
            step_static_configuration=dict(
                flow=flow,
                success_condition=success_condition,
                max_num_trials=max_num_trials,
            ),
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            name=name,
            __metadata_info__=__metadata_info__,
        )

        self.flow = flow
        self.success_condition = success_condition
        self.max_num_trials = max_num_trials

        self.executor = FlowConversationExecutor()

    def sub_flow(self) -> Optional["Flow"]:
        return self.flow

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        from wayflowcore.flow import Flow

        return {
            "flow": Flow,
            "success_condition": str,
            "max_num_trials": int,
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        flow: "Flow",
        success_condition: str,
        max_num_trials: int,
    ) -> List[Property]:
        return FlowExecutionStep._compute_step_specific_input_descriptors_from_static_config(
            flow=flow,
        )

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        flow: "Flow",
        success_condition: str,
        max_num_trials: int,
    ) -> List[Property]:
        return [
            value_type_description
            for value_type_description in FlowExecutionStep._compute_step_specific_output_descriptors_from_static_config(
                flow=flow,
            )
            if value_type_description.name != success_condition
        ] + [
            IntegerProperty(
                name=cls.NUM_RETRIES_VAR,
                description="Number of retries the retry step took to succeed or exit",
            ),
            BooleanProperty(
                name=cls.SUCCESS_VAR,
                description="Whether the retry step succeeded in the end or not",
            ),
        ]

    @classmethod
    def _compute_internal_branches_from_static_config(
        cls,
        flow: "Flow",
        success_condition: str,
        max_num_trials: int,
    ) -> List[str]:
        return FlowExecutionStep._compute_internal_branches_from_static_config(flow=flow) + [
            RetryStep.BRANCH_FAILURE
        ]

    # override
    @property
    def might_yield(self) -> bool:
        """
        Indicates that this step might yield if the subflow might.
        """
        return self.flow.might_yield

    def _retry_count(self, state: FlowConversationExecutionState) -> int:
        return cast(int, state.internal_context_key_values.get(f"retry_counter_{id(self)}", 0))

    def _set_counter(self, state: FlowConversationExecutionState, value: int) -> None:
        state.internal_context_key_values[f"retry_counter_{id(self)}"] = value

    async def _invoke_step_async(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        logger.debug(
            "Starting execution of inside flow: %d/%d",
            self._retry_count(conversation.state) + 1,
            self.max_num_trials,
        )

        sub_conversation = conversation._get_or_create_current_sub_conversation(
            step=self,
            flow=self.flow,
            inputs=inputs,
        )
        status = await sub_conversation.execute_async()

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

        output_values = status.output_values
        success_value = output_values.pop(self.success_condition)
        success = bool(success_value)
        num_retries = self._retry_count(conversation.state) + 1

        logger.debug("Inside flow returned: %s. Success=%s", success_value, success)

        if success:
            self._set_counter(conversation.state, 0)  # reset the internal counter
            next_step_name = status.complete_step_name or self.BRANCH_NEXT

            logger.debug("RetryStep succeeded. Next step will be %s", next_step_name)
        elif num_retries < self.max_num_trials:
            self._set_counter(conversation.state, num_retries)
            next_step_name = self.BRANCH_SELF  # self loop, we will retry
            logger.debug("RetryStep failed. Retrying")
        else:
            next_step_name = self.BRANCH_FAILURE
            logger.debug("RetryStep failed. Next step will be %s", next_step_name)

            # num retries exceeded, we will fail
            self._set_counter(conversation.state, 0)  # reset the internal counter

        return StepResult(
            outputs={
                self.SUCCESS_VAR: success,
                self.NUM_RETRIES_VAR: num_retries,
                **output_values,
            },
            branch_name=next_step_name,
        )

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        all_tools = {}

        if recursive:
            all_tools.update(
                self.flow._referenced_tools_dict(recursive=True, visited_set=visited_set)
            )

        return all_tools
