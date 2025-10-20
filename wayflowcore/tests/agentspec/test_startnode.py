# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging

from wayflowcore import Flow
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.property import IntegerProperty as RuntimeIntegerProperty
from wayflowcore.steps import StartStep


def test_start_step_can_be_exported_to_agentspec_then_imported(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        step = StartStep(
            input_descriptors=[
                RuntimeIntegerProperty(name="a", default_value=19),
            ],
        )
        flow = Flow.from_steps([step])
        agentspec_flow = AgentSpecExporter().to_json(flow)
        converted_back_flow = AgentSpecLoader().load_json(agentspec_flow)

    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
