# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import cast

from wayflowcore import Flow
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.property import IntegerProperty as RuntimeIntegerProperty
from wayflowcore.steps import TemplateRenderingStep


def test_template_step_can_be_exported_to_agentspec_then_imported() -> None:
    step = TemplateRenderingStep(
        template="{{a}} + {{b}} = {{c}}",
        input_descriptors=[
            RuntimeIntegerProperty(name="a", default_value=19),
            RuntimeIntegerProperty(name="b", default_value=23),
            RuntimeIntegerProperty(name="c"),
        ],
        output_mapping={TemplateRenderingStep.OUTPUT: "equation"},
    )
    flow = Flow.from_steps([step])
    serialized_flow = AgentSpecExporter().to_yaml(flow)
    new_flow = cast(Flow, AgentSpecLoader().load_yaml(serialized_flow))
    conversation = new_flow.start_conversation({"c": 43})
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {"equation": "19 + 23 = 43"}
