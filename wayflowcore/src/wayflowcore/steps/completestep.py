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


class CompleteStep(Step):
    """Step to exit a ``Flow``."""

    _input_descriptors_change_step_behavior = True

    def __init__(
        self,
        branch_name: Optional[str] = None,
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

        This step has no input descriptors.

        **Output descriptors**

        This step has no output descriptors.

        Parameters
        ----------
        branch_name:
            Name of the outgoing branch of this step when being used in a sub-flow (i.e. flows used in a ``FlowExecutionStep``).
            If ``None``, the step ``name`` is used.

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
        >>> from wayflowcore.controlconnection import ControlFlowEdge
        >>> from wayflowcore.dataconnection import DataFlowEdge
        >>> from wayflowcore.flow import Flow
        >>> from wayflowcore.property import StringProperty
        >>> from wayflowcore.steps import BranchingStep, OutputMessageStep, StartStep
        >>> BRANCHING_VAR_NAME = "my_branching_var"
        >>> branching_step = BranchingStep(
        ...     name="branching_step",
        ...     branch_name_mapping={
        ...         "[SUCCESS]": "success",
        ...         "[FAILURE]": "failure",
        ...     },
        ... )
        >>> start_step = StartStep(name="start_step", input_descriptors=[StringProperty(BRANCHING_VAR_NAME)])
        >>> success_step = OutputMessageStep(name="success_step", message_template="It was a success")
        >>> failure_step = OutputMessageStep(name="failure_step", message_template="It was a failure")
        >>> flow = Flow(
        ...     begin_step=start_step,
        ...     control_flow_edges=[
        ...         ControlFlowEdge(source_step=start_step, destination_step=branching_step),
        ...         ControlFlowEdge(
        ...             source_step=branching_step,
        ...             destination_step=success_step,
        ...             source_branch="success",
        ...         ),
        ...         ControlFlowEdge(
        ...             source_step=branching_step,
        ...             destination_step=failure_step,
        ...             source_branch="failure",
        ...         ),
        ...         ControlFlowEdge(
        ...             source_step=branching_step,
        ...             destination_step=failure_step,
        ...             source_branch=BranchingStep.BRANCH_DEFAULT,
        ...         ),
        ...         ControlFlowEdge(source_step=success_step, destination_step=None),
        ...         ControlFlowEdge(source_step=failure_step, destination_step=None),
        ...     ],
        ...     data_flow_edges=[
        ...         DataFlowEdge(start_step, BRANCHING_VAR_NAME, branching_step, BranchingStep.NEXT_BRANCH_NAME),
        ...     ],
        ... )
        >>> conversation = flow.start_conversation(inputs={BRANCHING_VAR_NAME: "[SUCCESS]"})
        >>> status = conversation.execute()
        >>> print(conversation.get_last_message().content)
        It was a success

        """
        self.branch_name = branch_name
        super().__init__(
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            step_static_configuration={"branch_name": branch_name},
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            name=name,
            __metadata_info__=__metadata_info__,
        )

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        return {
            "branch_name": Optional[str],  # type: ignore
        }

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        return StepResult(outputs=inputs)

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls, input_descriptors: Optional[List[Property]], branch_name: str
    ) -> List[Property]:
        return input_descriptors or []

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls, input_descriptors: Optional[List[Property]], branch_name: str
    ) -> List[Property]:
        return input_descriptors or []

    @classmethod
    def _compute_internal_branches_from_static_config(
        cls, input_descriptors: Optional[List[Property]], branch_name: str
    ) -> List[str]:
        # Note that branch_name is not used here because we don't want to connect anything after a CompleteStep
        return []
