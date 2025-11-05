# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import cast

from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import FlowExecutionStep, MapStep, OutputMessageStep, StartStep


def test_flow_execution_step_with_map_step_can_be_exported_to_agentspec_then_imported():
    sub_start_step = StartStep(input_descriptors=[ListProperty(name="output_message")])
    map_step = MapStep(
        unpack_input={"output_message": "."},
        flow=create_single_step_flow(
            step=OutputMessageStep(
                message_template="{{ output_message }}",
                output_descriptors={StringProperty(name="output_message")},
            ),
        ),
        output_descriptors=[ListProperty(name="output_message")],
    )
    output_message_step = OutputMessageStep(
        message_template="Hello {% for l in output_message %}{{ l }}{% endfor %}"
    )
    sub_data_edges = [
        DataFlowEdge(sub_start_step, "output_message", map_step, MapStep.ITERATED_INPUT),
        DataFlowEdge(map_step, "output_message", output_message_step, "output_message"),
    ]
    sub_flow_step = FlowExecutionStep(
        flow=Flow.from_steps(
            [sub_start_step, map_step, output_message_step], data_flow_edges=sub_data_edges
        )
    )

    start_step = StartStep(input_descriptors=[ListProperty(name="output_message")])
    main_data_edges = [DataFlowEdge(start_step, "output_message", sub_flow_step, "output_message")]
    main_flow = Flow.from_steps([start_step, sub_flow_step], data_flow_edges=main_data_edges)

    serialized_flow = AgentSpecExporter().to_yaml(main_flow)
    assert isinstance(serialized_flow, str)
    assert "ExtendedMapNode" not in serialized_flow
    assert "Hello" in serialized_flow

    new_flow = cast(Flow, AgentSpecLoader().load_yaml(serialized_flow))
    conversation = new_flow.start_conversation(
        inputs={"output_message": ["w", "a", "y", "f", "l", "o", "w"]}
    )
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {"output_message": "Hello wayflow"}
