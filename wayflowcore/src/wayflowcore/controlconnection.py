# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

from wayflowcore.component import FrozenDataclassComponent
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import (
    SerializableObject,
    deserialize_from_dict,
    serialize_to_dict,
)
from wayflowcore.steps.step import Step

if TYPE_CHECKING:
    from wayflowcore.steps.step import Step


@dataclass(frozen=True)
class ControlFlowEdge(FrozenDataclassComponent):
    """
    A control flow edge specifies how we transition from a step to another

    Parameters
    ----------
    source_step:
        Source ``Step`` to transition from.
    destination_step:
        Destination ``Step`` where the transition is directed to.
    source_branch:
       Name of the specific step branch to transition from.
       Defaults to ``Step.BRANCH_NEXT``.

    Example
    -------
    >>> from wayflowcore.controlconnection import ControlFlowEdge
    >>> from wayflowcore.flow import Flow
    >>> from wayflowcore.steps import OutputMessageStep
    >>> opening_step = OutputMessageStep("Opening session")
    >>> closing_step = OutputMessageStep('Closing session"')
    >>> flow = Flow(
    ...     begin_step_name="open_step",
    ...     steps={
    ...         "open_step": opening_step,
    ...         "close_step": closing_step,
    ...     },
    ...     control_flow_edges=[
    ...         ControlFlowEdge(source_step=opening_step, destination_step=closing_step),
    ...         ControlFlowEdge(source_step=closing_step, destination_step=None),
    ...     ],
    ... )
    >>> conversation = flow.start_conversation()
    >>> status = conversation.execute()
    >>> print(conversation.get_messages())  # doctest: +SKIP
    """

    source_step: "Step"
    destination_step: Optional["Step"]
    source_branch: str = Step.BRANCH_NEXT

    def __post_init__(self) -> None:
        from wayflowcore.steps.step import Step

        if not isinstance(self.source_step, Step):
            raise TypeError(
                f"The `source_step` of a control flow edge must be a `Step`, is {type(self.source_step)}"
            )
        if self.destination_step is not None and not isinstance(self.destination_step, Step):
            raise TypeError(
                f"The `destination_step` of a control flow edge must be a `Step`, is {type(self.destination_step)}"
            )

        # the branch should exist in the source step
        available_source_branches = self.source_step.get_branches()
        if self.source_branch not in available_source_branches:
            raise ValueError(
                f"The edge {self} is incorrect: the `source_step` does not have a branch named `{self.source_branch}` in its branches: {available_source_branches}"
            )

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        return {
            "source_step": serialize_to_dict(self.source_step, serialization_context),
            "destination_step": (
                serialize_to_dict(self.destination_step, serialization_context)
                if self.destination_step
                else None
            ),
            "source_branch": self.source_branch,
            "id": self.id,
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        from wayflowcore.steps.step import Step

        control_flow_edge_args = dict(
            source_step=deserialize_from_dict(
                Step, input_dict["source_step"], deserialization_context
            ),
            destination_step=(
                deserialize_from_dict(Step, input_dict["destination_step"], deserialization_context)
                if input_dict.get("destination_step", None)
                else None
            ),
            source_branch=input_dict["source_branch"],
            __metadata_info__=input_dict.get("__metadata_info__", {}),
        )
        if "id" in input_dict:
            control_flow_edge_args["id"] = input_dict["id"]
        return ControlFlowEdge(**control_flow_edge_args)
