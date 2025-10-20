# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: WayFlow Code Example - How to Catch Exceptions in Flows


# .. start-##_Define_Catch_Exception_Step
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import BooleanProperty
from wayflowcore.steps import (
    CatchExceptionStep,
    OutputMessageStep,
    PromptExecutionStep,
    StartStep,
    ToolExecutionStep,
)
from wayflowcore.tools import tool

@tool(description_mode="only_docstring")
def flaky_tool(raise_error: bool = False) -> str:
    """Will throw a ValueError"""
    if raise_error:
        raise ValueError("Raising an error.")
    return "execution successful"


FLAKY_TOOL_STEP = "flaky_tool_step"
VALUE_ERROR_BRANCH = ValueError.__name__
start_step_flaky = StartStep(input_descriptors=[BooleanProperty("raise_error")], name="start_step")
flaky_tool_step = ToolExecutionStep(tool=flaky_tool, raise_exceptions=True, name="flaky_step")
flaky_subflow = Flow.from_steps(steps=[start_step_flaky, flaky_tool_step])
ERROR_IO = "error_io"
catch_step = CatchExceptionStep(
    flow=flaky_subflow, except_on={ValueError.__name__: VALUE_ERROR_BRANCH}, name="catch_flow_step"
)
# .. end-##_Define_Catch_Exception_Step
# .. start-##_Build_Exception_Handling_Flow
main_start = StartStep(input_descriptors=[BooleanProperty("raise_error")], name="start_step")
success_step = OutputMessageStep("Success: No error was raised", name="success_step")
failure_step = OutputMessageStep("Failure: Did get an error: {{tool_error}}", name="failure_step")

flow = Flow(
    begin_step=main_start,
    control_flow_edges=[
        ControlFlowEdge(source_step=main_start, destination_step=catch_step),
        ControlFlowEdge(
            source_step=catch_step,
            destination_step=success_step,
            source_branch=CatchExceptionStep.BRANCH_NEXT,
        ),
        ControlFlowEdge(
            source_step=catch_step, destination_step=failure_step, source_branch=VALUE_ERROR_BRANCH
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(main_start, "raise_error", catch_step, "raise_error"),
        DataFlowEdge(
            catch_step, CatchExceptionStep.EXCEPTION_NAME_OUTPUT_NAME, failure_step, "tool_error"
        ),
    ],
)
# .. end-##_Build_Exception_Handling_Flow
from wayflowcore.agentspec import AgentSpecExporter # docs-skiprow
from wayflowcore.agentspec import AgentSpecLoader # docs-skiprow

config = AgentSpecExporter().to_json(flow) # docs-skiprow
new_flow = AgentSpecLoader(tool_registry={"flaky_tool": flaky_tool}).load_json(config) # docs-skiprow
flow = new_flow  # docs-skiprow # type: ignore
# .. start-##_Execute_Flow_With_Exceptions
conversation = flow.start_conversation(inputs={"raise_error": False})
conversation.execute()
# "Success: No error was raised"

conversation = flow.start_conversation(inputs={"raise_error": True})
conversation.execute()
# "Failure: Did get an error: ValueError"
# .. end-##_Execute_Flow_With_Exceptions
# .. start-##_Catch_All_Exceptions
main_start = StartStep(input_descriptors=[BooleanProperty("raise_error")], name="start_step")
catchall_step = CatchExceptionStep(
    flow=flaky_subflow,
    catch_all_exceptions=True,
    name="catch_flow_step",
)
success_step = OutputMessageStep("Success: No error was raised", name="success_step")
failure_step = OutputMessageStep("Failure: Did get an error: {{tool_error}}", name="failure_step")

flow = Flow(
    begin_step=main_start,
    control_flow_edges=[
        ControlFlowEdge(source_step=main_start, destination_step=catchall_step),
        ControlFlowEdge(
            source_step=catchall_step,
            destination_step=success_step,
            source_branch=CatchExceptionStep.BRANCH_NEXT,
        ),
        ControlFlowEdge(
            source_step=catchall_step,
            destination_step=failure_step,
            source_branch=CatchExceptionStep.DEFAULT_EXCEPTION_BRANCH,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(main_start, "raise_error", catchall_step, "raise_error"),
        DataFlowEdge(
            catchall_step, CatchExceptionStep.EXCEPTION_NAME_OUTPUT_NAME, failure_step, "tool_error"
        ),
    ],
)
# .. end-##_Catch_All_Exceptions
# .. start-##_Handle_OCI_Service_Error
from oci.exceptions import ServiceError
from wayflowcore.models import OCIGenAIModel
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey

oci_config = OCIClientConfigWithApiKey(service_endpoint="OCIGENAI_ENDPOINT")

llm = OCIGenAIModel(
    model_id="openai.model-id",
    client_config=oci_config,
    compartment_id="COMPARTMENT_ID",
)

robust_prompt_execution_step = CatchExceptionStep(
    flow=Flow.from_steps([PromptExecutionStep(prompt_template="{{prompt_template}}", llm=llm)]),
    except_on={ServiceError.__name__: "oci_service_error"},
)
# .. end-##_Handle_OCI_Service_Error
# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(flow)
# .. end-##_Export_config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {"flaky_tool": flaky_tool}
flow = AgentSpecLoader(tool_registry=tool_registry).load_json(serialized_flow)
# .. end-##_Load_Agent_Spec_config
