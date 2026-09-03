# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from wayflowcore.agentserver.a2a._worker import _flow_yields_at_input_step_before_any_real_message
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import BranchingStep, CompleteStep, InputMessageStep, OutputMessageStep


def test_reaches_input_step_immediately() -> None:
    """The flow's only real step is the InputMessageStep (the implicit StartStep
    leads directly to it), so pre-executing would swallow the caller's first
    message as the answer to a question never actually surfaced."""
    input_step = InputMessageStep(name="input_step", message_template="")
    complete_step = CompleteStep(name="complete_step")

    flow = Flow(
        begin_step=input_step,
        control_flow_edges=[
            ControlFlowEdge(input_step, complete_step),
        ],
    )

    assert _flow_yields_at_input_step_before_any_real_message(flow) is True


def test_non_yielding_step_before_input_step_still_reaches_immediately() -> None:
    """A non-yielding step (e.g. one with only a static message) running before
    the InputMessageStep does not make pre-execution safe: pre-execute always
    runs before any real message has been appended, so it would still reach
    and yield at the InputMessageStep on its very first pass, swallowing the
    caller's first message as the answer. The path is unambiguous (single
    edge at each hop), so this must still be detected as "reached with no
    prior work that depends on the caller's message"."""
    output_step = OutputMessageStep(name="output_step", message_template="hello")
    input_step = InputMessageStep(name="input_step", message_template="")
    complete_step = CompleteStep(name="complete_step")

    flow = Flow(
        begin_step=output_step,
        control_flow_edges=[
            ControlFlowEdge(output_step, input_step),
            ControlFlowEdge(input_step, complete_step),
        ],
    )

    assert _flow_yields_at_input_step_before_any_real_message(flow) is True


def test_no_input_step_in_flow() -> None:
    """A flow with no InputMessageStep at all never needs the pre-execute
    guard; the original pre-execute condition already filters this out before
    calling the helper, but the helper itself should not claim otherwise."""
    output_step = OutputMessageStep(name="output_step", message_template="hello")
    complete_step = CompleteStep(name="complete_step")

    flow = Flow(
        begin_step=output_step,
        control_flow_edges=[
            ControlFlowEdge(output_step, complete_step),
        ],
    )

    assert _flow_yields_at_input_step_before_any_real_message(flow) is False


def test_branching_before_input_step_is_treated_as_unknown() -> None:
    """When the step before a potential InputMessageStep has more than one
    distinct outgoing destination, we can't cheaply tell whether the
    InputMessageStep is reached with or without prior work, so we
    conservatively keep the existing pre-execute behaviour."""
    input_step_a = InputMessageStep(name="input_step_a", message_template="")
    output_step_b = OutputMessageStep(name="output_step_b", message_template="hello")
    complete_step = CompleteStep(name="complete_step")

    branching_step = BranchingStep(
        name="branching_step",
        branch_name_mapping={"go_to_input": "to_input", "go_to_output": "to_output"},
    )

    flow = Flow(
        begin_step=branching_step,
        control_flow_edges=[
            ControlFlowEdge(branching_step, input_step_a, source_branch="to_input"),
            ControlFlowEdge(branching_step, output_step_b, source_branch="to_output"),
            ControlFlowEdge(
                branching_step, output_step_b, source_branch=BranchingStep.BRANCH_DEFAULT
            ),
            ControlFlowEdge(input_step_a, complete_step),
            ControlFlowEdge(output_step_b, complete_step),
        ],
    )

    assert _flow_yields_at_input_step_before_any_real_message(flow) is False
