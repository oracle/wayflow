# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.property import Property, StringProperty
from wayflowcore.steps.step import Step, StepResult

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation


class BranchingStep(Step):
    """
    This step impacts the control flow of the assistant by deciding what step to go next based on the input passed to it.
    This step does not involve the use of LLMs, as it simply uses the given input step name and an optional mapping.
    As a consequence, exact match in the step names is required for this step.
    For more flexibility please use the ``ChoiceSelectionStep`` where the next step is determined by an LLM.
    """

    NEXT_BRANCH_NAME = "next_step_name"
    """str: Input key for the name to transition to next."""

    BRANCH_DEFAULT = "default"
    """str: Name of the branch taken if none of the `branch_name_mapping` transitions match"""

    def __init__(
        self,
        branch_name_mapping: Optional[Dict[str, str]] = None,
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

        By default, when ``input_descriptors`` is set to ``None``, this step has a single input descriptor, named
        ``BranchingStep.NEXT_BRANCH_NAME``, of type ``StringProperty()``, that represents the value that will be
        mapped against ``branch_name_mapping`` to determine the next branch.

        **Output descriptors**

        By default, this step has no output descriptor.

        **Branches**

        This step can have several next steps and perform conditional branching based on the value of its inputs. It has one
        possible branch per value in the ``branch_name_mapping`` dictionary, plus ``BRANCH_DEFAULT`` which is chosen
        in case the value passed as input does not appear in the ``branch_name_mapping`` mapping.

        Parameters
        ----------
        branch_name_mapping:
            Mapping between input values of this step and particular branches. Used to branch out based on the input value.
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


        See Also
        --------
        :class:`~wayflowcore.steps.choiceselectionstep.ChoiceSelectionStep` : Flexible version of the ``BranchingStep`` using an LLM to select the next step.

        Examples
        --------
        >>> from wayflowcore.flow import Flow
        >>> from wayflowcore.steps import BranchingStep, OutputMessageStep
        >>> BRANCHING_STEP = "BRANCHING"
        >>> OUTPUT_ACCESS_GRANTED_STEP = "ACCESS_GRANTED"
        >>> OUTPUT_ACCESS_DENIED_STEP = "ACCESS_DENIED"
        >>> NEXT_STEP_NAME_IO = "$next_step_name"
        >>> branching_step = BranchingStep(
        ...         branch_name_mapping={"yes": "access_is_granted", "no": "access_is_denied"},
        ...         input_mapping={BranchingStep.NEXT_BRANCH_NAME: NEXT_STEP_NAME_IO},
        ...    )
        >>> assistant = Flow(
        ...     begin_step=branching_step,
        ...     steps={
        ...         BRANCHING_STEP: branching_step,
        ...         OUTPUT_ACCESS_GRANTED_STEP: OutputMessageStep("Access granted. Press any key to continue..."),
        ...         OUTPUT_ACCESS_DENIED_STEP: OutputMessageStep("Access denied. Please exit the conversation."),
        ...     },
        ...     transitions={
        ...         BRANCHING_STEP: {
        ...             'access_is_granted': OUTPUT_ACCESS_GRANTED_STEP,
        ...             'access_is_denied': OUTPUT_ACCESS_DENIED_STEP,
        ...             BranchingStep.BRANCH_DEFAULT: OUTPUT_ACCESS_DENIED_STEP,
        ...         },
        ...         OUTPUT_ACCESS_GRANTED_STEP: [None],
        ...         OUTPUT_ACCESS_DENIED_STEP: [None],
        ...     }
        ... )
        >>> conversation = assistant.start_conversation(inputs={NEXT_STEP_NAME_IO: "yes"})
        >>> status = conversation.execute()
        >>> # conversation.get_last_message().content
        >>> # Access granted. Press any key to continue...

        """
        super().__init__(
            step_static_configuration=dict(branch_name_mapping=branch_name_mapping),
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            name=name,
            __metadata_info__=__metadata_info__,
        )
        self.branch_name_mapping = branch_name_mapping or {}

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        return {"branch_name_mapping": Optional[Dict[str, str]]}  # type: ignore

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        branch_name_mapping: Optional[Dict[str, str]],
    ) -> List[Property]:
        return [
            StringProperty(
                name=cls.NEXT_BRANCH_NAME,
                description="Next branch name in the flow",
                default_value=cls.BRANCH_DEFAULT,
            )
        ]

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        branch_name_mapping: Optional[Dict[str, str]],
    ) -> List[Property]:
        return []

    @classmethod
    def _compute_internal_branches_from_static_config(
        cls,
        branch_name_mapping: Optional[Dict[str, str]],
    ) -> List[str]:
        branches: List[str] = [cls.BRANCH_DEFAULT]
        if branch_name_mapping is not None:
            branches_names = list(branch_name_mapping.values())
            if cls.BRANCH_DEFAULT in branches_names:
                logger.warning(
                    f"Branching step already has a branch named {cls.BRANCH_DEFAULT}. Please choose another name in the `branch_name_mapping` values"
                )
            branches.extend(branches_names)
        return list(set(branches))

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        if (
            self.NEXT_BRANCH_NAME not in inputs
            or inputs[self.NEXT_BRANCH_NAME] not in self.branch_name_mapping
        ):
            logger.info(
                "Branching step got `%s` which does not appear in possible branches: %s. Will default to `BranchingStep.BRANCH_DEFAULT`",
                inputs[self.NEXT_BRANCH_NAME],
                self.branch_name_mapping,
            )
            branch_name = self.BRANCH_DEFAULT
        else:
            branch_name = self.branch_name_mapping[inputs[self.NEXT_BRANCH_NAME]]

        logger.info(
            'Branching step got "%s" will transition to %s branch',
            inputs.get(self.NEXT_BRANCH_NAME, "no value"),
            branch_name,
        )

        return StepResult(outputs={}, branch_name=branch_name)
