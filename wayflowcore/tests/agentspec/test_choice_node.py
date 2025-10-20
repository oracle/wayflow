# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import cast

from wayflowcore import Flow
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.property import StringProperty
from wayflowcore.steps import ChoiceSelectionStep, OutputMessageStep, StartStep

from ..testhelpers.testhelpers import retry_test


@retry_test(max_attempts=12)
def test_choice_step_can_be_exported_to_agentspec_then_imported(remotely_hosted_llm) -> None:
    """
    Failure rate:          22 out of 50
    Observed on:           2025-08-13
    Average success time:  0.69 seconds per successful attempt
    Average failure time:  0.70 seconds per failed attempt
    Max attempt:           12
    Justification:         (0.44 ** 12) ~= 5.6 / 100'000
    """
    choice_step = ChoiceSelectionStep(
        name="choice_step",
        llm=remotely_hosted_llm,
        next_steps=[
            ("success_branch", "in case the test passed successfully", "success"),
            ("failure_branch", "in case the test did not pass", "failure"),
        ],
    )
    success_step = OutputMessageStep("It was a success", name="success_step")
    failure_step = OutputMessageStep("It was a failure", name="failure_step")
    start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="start_step")
    flow = Flow(
        begin_step=start_step,
        control_flow_edges=[
            ControlFlowEdge(source_step=start_step, destination_step=choice_step),
            ControlFlowEdge(
                source_step=choice_step,
                destination_step=success_step,
                source_branch="success_branch",
            ),
            ControlFlowEdge(
                source_step=choice_step,
                destination_step=failure_step,
                source_branch="failure_branch",
            ),
            ControlFlowEdge(
                source_step=choice_step,
                destination_step=failure_step,
                source_branch=ChoiceSelectionStep.BRANCH_DEFAULT,
            ),
            ControlFlowEdge(source_step=success_step, destination_step=None),
            ControlFlowEdge(source_step=failure_step, destination_step=None),
        ],
        data_flow_edges=[
            DataFlowEdge(start_step, "my_var", choice_step, ChoiceSelectionStep.INPUT),
        ],
    )
    serialized_flow = AgentSpecExporter().to_yaml(flow)
    new_flow = cast(Flow, AgentSpecLoader().load_yaml(serialized_flow))
    conversation = new_flow.start_conversation(inputs={"my_var": "TEST IS SUCCESSFUL"})
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    last_message = conversation.get_last_message()
    assert last_message.content == "It was a success"
