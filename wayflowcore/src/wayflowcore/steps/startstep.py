# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.property import Property
from wayflowcore.steps.step import Step, StepResult

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation

logger = logging.getLogger(__name__)


class StartStep(Step):
    """Step to enter a ``Flow``."""

    _input_descriptors_change_step_behavior = True

    def __init__(
        self,
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

        By default, when ``input_descriptors`` is set to ``None``, the input descriptors of the step are empty.
        The user should set the ``input_descriptors`` to the list of inputs that are expected to be provided
        as inputs to the flow this step belongs to.

        **Output descriptors**

        The output descriptors of this step are equal to the input descriptors.

        Parameters
        ----------
        input_descriptors:
            The list of input descriptors that the flow containing this step takes as input.
            ``None`` means the step will not have any input descriptor.

        output_descriptors:
            Output descriptors of the step. ``None`` means the step will resolve them automatically using its static
            configuration in a best effort manner. The output descriptors should be a subset of the input_descriptors.
            This parameter should not be used in this step.

        name:
            Name of the step.

        input_mapping:
            Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.
            This parameter should not be used in this step.

        output_mapping:
            Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.

        Examples
        --------
        >>> from wayflowcore.property import StringProperty
        >>> from wayflowcore.dataconnection import DataFlowEdge
        >>> from wayflowcore.flow import Flow
        >>> from wayflowcore.steps import (
        ...     CompleteStep,
        ...     PromptExecutionStep,
        ...     StartStep,
        ... )
        >>> START_STEP = "start_step"
        >>> LLM_ANSWER_STEP = "llm_answer_step"
        >>> COMPLETE_STEP = "complete_step"
        >>> start_step = StartStep(
        ...     input_descriptors=[
        ...         StringProperty(
        ...             name="user_question",
        ...             description="The user question.",
        ...         )
        ...     ]
        ... )
        >>> llm_step = PromptExecutionStep(
        ...     prompt_template="Answer the user question: {{user_question}}",
        ...     llm=llm,
        ... )
        >>> steps = {
        ...     START_STEP: start_step,
        ...     LLM_ANSWER_STEP: llm_step,
        ...     COMPLETE_STEP: CompleteStep(),
        ... }
        >>> transitions = {
        ...     START_STEP: [LLM_ANSWER_STEP],
        ...     LLM_ANSWER_STEP: [COMPLETE_STEP],
        ... }
        >>> assistant = Flow(
        ...     begin_step_name=START_STEP,
        ...     steps=steps,
        ...     transitions=transitions,
        ... )
        >>> conversation = assistant.start_conversation(
        ...     inputs={"user_question": "Could you talk about the Oracle Cloud Infrastructure?"}
        ... )

        """
        # Non-empty input_mapping is only confusing for the StartStep, as it has no internal input names
        if input_mapping:
            logger.warning("The usage of input_mapping in the StartStep is discouraged")
        # Setting output_descriptors is only confusing for the StartStep
        if output_descriptors is not None and input_descriptors != output_descriptors:
            logger.warning("The usage of output_descriptors in the StartStep is discouraged")
        super().__init__(
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            step_static_configuration={},
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            name=name,
            __metadata_info__=__metadata_info__,
        )

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        return {}

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls, input_descriptors: Optional[List[Property]]
    ) -> List[Property]:
        return input_descriptors or []

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls, input_descriptors: Optional[List[Property]]
    ) -> List[Property]:
        return input_descriptors or []

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        # We just forward the given inputs
        return StepResult(outputs=inputs)
