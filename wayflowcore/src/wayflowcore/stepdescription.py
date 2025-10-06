# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

from wayflowcore.serialization.serializer import SerializableDataclassMixin, SerializableObject


@dataclass
class StepDescription(SerializableDataclassMixin, SerializableObject):
    """
    Data class that contains all the information needed to describe a step.
    This is used by Steps in order to identify steps inside LLM prompts.
    """

    step_name: str
    description: str
    displayed_step_name: str = None  # type: ignore

    def __post_init__(self) -> None:
        if self.displayed_step_name is None:
            self.displayed_step_name = self.step_name


# Tuple[step_name,step_description,Optional[step_displayed_name]]
StepDescriptionInput = Union[Tuple[str, str], Tuple[str, str, str], StepDescription]


def make_steps_descriptions(
    next_steps: Union[List[StepDescriptionInput], Dict[str, str]],
) -> List[StepDescription]:
    step_descriptions = (
        [
            StepDescription(*next_step) if not isinstance(next_step, StepDescription) else next_step
            for next_step in next_steps
        ]
        if not isinstance(next_steps, dict)
        else [
            StepDescription(step_name=step_name, description=description)
            for step_name, description in next_steps.items()
        ]
    )
    if len(step_descriptions) != len(
        set([step_description.displayed_step_name for step_description in step_descriptions])
    ):
        raise ValueError(
            f"Two next steps seem to have the same displayed names. This will make it impossible for the LLM to differenciate them: {step_descriptions}"
        )
    return step_descriptions
