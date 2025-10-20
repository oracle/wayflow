# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Dict, List, Optional, TypedDict

from wayflowcore import Step
from wayflowcore.contextproviders import ContextProvider
from wayflowcore.controlconnection import ControlFlowEdge

FlowConfigT = TypedDict(
    "FlowConfigT",
    {
        "begin_step": Step,
        "steps": Dict[str, Step],
        "control_flow_edges": List[ControlFlowEdge],
        "context_providers": Optional[List[ContextProvider]],
    },
    total=False,
)


def _single_step_flow_dict(
    step: Step,
    step_name: str = "single_step",
    context_providers: Optional[List[ContextProvider]] = None,
) -> FlowConfigT:
    return dict(
        begin_step=step,
        steps={step_name: step},
        control_flow_edges=[
            ControlFlowEdge(
                source_step=step,
                source_branch=str(branch_name),
                destination_step=None,
            )
            for branch_name in step.get_branches()
        ],
        context_providers=context_providers,
    )
