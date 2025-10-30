# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import cast

from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.flow import Flow
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import CompleteStep, MapStep, OutputMessageStep, StartStep

from ..testhelpers.testhelpers import assert_flows_are_copies


def test_mapstep_with_non_iterable_input_can_be_serialized_and_deserialized() -> None:

    message_incipit_property = StringProperty(name="message_incipit")
    i_property = StringProperty(name="i")
    iterated_input_property = ListProperty(name=MapStep.ITERATED_INPUT, item_type=i_property)

    output_step = OutputMessageStep(
        name="outputstep",
        message_template="{{message_incipit}}: {{i}}",
    )

    start_step = StartStep(name="start", input_descriptors=[message_incipit_property, i_property])
    map_step = MapStep(
        name="mapstep",
        flow=Flow.from_steps([start_step, output_step, CompleteStep("end")]),
        unpack_input={"i": "."},
        input_descriptors=[iterated_input_property, message_incipit_property],
    )

    outer_start_step = StartStep(
        name="start", input_descriptors=[message_incipit_property, iterated_input_property]
    )
    flow = Flow.from_steps([outer_start_step, map_step, CompleteStep("end")])
    agentspec_flow = AgentSpecExporter().to_json(flow)
    loaded_flow = cast(Flow, AgentSpecLoader().load_json(agentspec_flow))

    assert_flows_are_copies(flow, loaded_flow)
