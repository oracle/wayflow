# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import os
from pathlib import Path
from typing import cast

import pytest

from wayflowcore.contextproviders.flowcontextprovider import FlowContextProvider
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.models.ociclientconfig import OCIClientConfigWithInstancePrincipal
from wayflowcore.models.ocigenaimodel import OCIGenAIModel
from wayflowcore.serialization import autodeserialize, deserialize, serialize
from wayflowcore.steps import (
    BranchingStep,
    CompleteStep,
    FlowExecutionStep,
    InputMessageStep,
    OutputMessageStep,
    StartStep,
)

from ..conftest import COHERE_OCI_INSTANCE_PRINCIPAL_CONFIG

CONFIGS_DIR = Path(os.path.dirname(__file__)).parent / "configs"


@pytest.fixture
def flow_with_output_and_input_steps():
    step_a = OutputMessageStep(message_template="Hello!")
    step_b = OutputMessageStep(message_template="How")
    step_c = OutputMessageStep(message_template="are")
    step_d = InputMessageStep(message_template="you?")
    return Flow(
        begin_step_name="STEP_A",
        steps={
            "STEP_A": step_a,
            "STEP_B": step_b,
            "STEP_C": step_c,
            "STEP_D": step_d,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=step_a, destination_step=step_b),
            ControlFlowEdge(source_step=step_b, destination_step=step_c),
            ControlFlowEdge(source_step=step_c, destination_step=step_d),
            ControlFlowEdge(source_step=step_d, destination_step=step_a),
        ],
        __metadata_info__={"workflow_name": "my_workflow"},
    )


@pytest.fixture
def flow_with_subflow_step(flow_with_output_and_input_steps):
    step_alpha = OutputMessageStep(
        message_template="Prepare yourself for entering a subconversation!"
    )
    step_beta = FlowExecutionStep(flow=flow_with_output_and_input_steps)
    return Flow(
        begin_step_name="STEP_ALPHA",
        steps={
            "STEP_ALPHA": step_alpha,
            "STEP_BETA": step_beta,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=step_alpha, destination_step=step_beta),
            ControlFlowEdge(source_step=step_beta, destination_step=None),
        ],
    )


@pytest.fixture
def xkcd_serialized_flow():
    with open(CONFIGS_DIR / "xkcd_tech_support_flow_chart.yaml") as config_file:
        serialized_flow = config_file.read()
    return serialized_flow


@pytest.fixture
def flow_with_component_referenced_several_times():
    with open(CONFIGS_DIR / "flow_with_multiple_references_of_same_component.yaml") as config_file:
        serialized_flow = config_file.read()
    return serialized_flow


def test_can_serialize_simple_flow(flow_with_output_and_input_steps: Flow) -> None:
    serialized_flow = serialize(flow_with_output_and_input_steps)
    assert isinstance(serialized_flow, str)
    assert serialized_flow.count(" Flow") == 1
    assert serialized_flow.count(" Step") == 5
    assert "InputMessageStep" in serialized_flow
    assert "you?" in serialized_flow
    assert "my_workflow" in serialized_flow


def test_can_serialize_flow_with_subflow(flow_with_subflow_step: Flow) -> None:
    serialized_flow = serialize(flow_with_subflow_step)
    assert isinstance(serialized_flow, str)
    assert serialized_flow.count("_component_type: Flow") == 2
    assert serialized_flow.count(" Step") == 8
    assert "FlowExecutionStep" in serialized_flow
    assert "STEP_C" in serialized_flow
    assert "Hello!" in serialized_flow


def _check_deserialized_flow_validity(old_flow: Flow, new_flow: Flow):
    assert set(new_flow.steps) == set(old_flow.steps)
    assert new_flow.__metadata_info__ == old_flow.__metadata_info__
    assert new_flow.id == old_flow.id


def test_can_deserialize_a_serialized_flow(
    flow_with_output_and_input_steps: Flow,
) -> None:
    new_flow = deserialize(Flow, serialize(flow_with_output_and_input_steps))
    _check_deserialized_flow_validity(flow_with_output_and_input_steps, new_flow)


def test_can_autodeserialize_a_serialized_flow(
    flow_with_output_and_input_steps: Flow,
) -> None:
    new_flow = autodeserialize(serialize(flow_with_output_and_input_steps))
    _check_deserialized_flow_validity(flow_with_output_and_input_steps, new_flow)


def test_can_deserialize_a_serialized_flow_with_subflow(
    flow_with_subflow_step: Flow,
) -> None:
    new_flow = deserialize(Flow, serialize(flow_with_subflow_step))
    assert set(new_flow.steps) == set(flow_with_subflow_step.steps)
    subflow_step = new_flow.steps["STEP_BETA"]
    assert isinstance(subflow_step, FlowExecutionStep)


def test_serialization_of_twice_the_same_subflow_is_not_duplicated(
    flow_with_output_and_input_steps: Flow,
) -> None:
    flow_with_twice_same_subflow = Flow.from_steps(
        steps=[
            FlowExecutionStep(flow=flow_with_output_and_input_steps),
            FlowExecutionStep(flow=flow_with_output_and_input_steps),
        ],
        step_names=["STEP_ALPHA", "STEP_BETA"],
        loop=True,
    )
    serialized_flow = serialize(flow_with_twice_same_subflow)
    assert isinstance(serialized_flow, str)
    assert "_referenced_objects" in serialized_flow
    assert serialized_flow.count("Hello!") == 1  # Would be a count of 2 if there was duplication


def test_serialization_of_twice_the_same_step_is_not_duplicated(
    flow_with_output_and_input_steps: Flow,
) -> None:
    step = FlowExecutionStep(flow=flow_with_output_and_input_steps)
    flow_with_twice_same_subflow = Flow(
        begin_step_name="STEP_ALPHA",
        steps={
            "STEP_ALPHA": step,
        },
        control_flow_edges=[ControlFlowEdge(source_step=step, destination_step=None)],
    )
    serialized_flow = serialize(flow_with_twice_same_subflow)
    assert isinstance(serialized_flow, str)
    assert "_referenced_objects" in serialized_flow
    assert serialized_flow.count("Hello!") == 1  # Would be a count of 2 if there was duplication


def test_serialization_raises_if_flow_contains_itself() -> None:
    step = OutputMessageStep(message_template="ω")
    strange_loop_flow = Flow(
        begin_step_name="ω",
        steps={"ω": step},
        control_flow_edges=[ControlFlowEdge(source_step=step, destination_step=step)],
    )
    strange_loop_flow.steps["ω"] = FlowExecutionStep(flow=strange_loop_flow)
    with pytest.raises(
        ValueError,
        match="Serialization of objects containing themselves is a mathematical impossibility",
    ):
        serialize(strange_loop_flow)


def test_referenced_objects_are_not_created_twice_on_deserialization(
    flow_with_component_referenced_several_times,
) -> None:
    serialized_flow = flow_with_component_referenced_several_times
    flow = cast(Flow, deserialize(Flow, serialized_flow))
    assert flow.steps["STEP_ALPHA"] is flow.control_flow_edges[0].source_step


def test_deserialization_raises_on_self_referenced_objects() -> None:
    self_referential_serialized_flow = """
      _component_type: Flow
      _referenced_objects:
        flow/ωωω:
          _component_type: Flow
          begin_step_name: ω
          end_steps:
          - null
          steps:
            ω:
              $ref: flowexecutionstep/ωωω
          transitions:
            ω:
            - ω
        flowexecutionstep/ωωω:
          _component_type: Step
          step_args:
            flow:
              $ref: flow/ωωω
          step_cls: FlowExecutionStep
      $ref: flow/ωωω
    """
    with pytest.raises(
        ValueError,
        match="Deserialization of objects containing themselves is a mathematical impossibility",
    ):
        _ = deserialize(Flow, self_referential_serialized_flow)


def test_can_deserialize_flow_with_referenced_llm_model(xkcd_serialized_flow: str) -> None:
    flow = deserialize(Flow, xkcd_serialized_flow)
    assert isinstance(flow, Flow)


def test_expected_llm_model_is_in_flow_serialization(xkcd_serialized_flow: str) -> None:
    new_serialized_flow = serialize(deserialize(Flow, xkcd_serialized_flow))
    assert isinstance(new_serialized_flow, str)
    assert "model_type: vllm" in new_serialized_flow
    assert "max_tokens: 250" in new_serialized_flow
    assert "host_port: LLAMA_API_ENDPOINT" in new_serialized_flow
    assert "meta-llama/Meta-Llama-3.1-8B-Instruct" in new_serialized_flow


def test_expected_io_mappings_are_in_flow_serialization(xkcd_serialized_flow: str) -> None:
    new_serialized_flow = serialize(deserialize(Flow, xkcd_serialized_flow))
    assert isinstance(new_serialized_flow, str)
    assert "input_mapping" in new_serialized_flow
    assert "output_mapping" in new_serialized_flow


def test_can_serde_flow_with_variable_readwrite_steps():
    from wayflowcore.property import FloatProperty, ListProperty
    from wayflowcore.variable import Variable

    list_variable = Variable(
        name="list_of_floats_variable",
        type=ListProperty(item_type=FloatProperty()),
        description="list of floats variable",
        default_value=[],
    )

    float_variable = Variable(
        name="float_variable",
        type=FloatProperty(),
        description="a float variable",
    )

    variables = [list_variable, float_variable]

    serialized_flow = """
        _component_type: Flow
        _referenced_objects:
          variable/140438685963696:
            _component_type: Variable
            default_value: []
            description: list of floats variable
            name: list_of_floats_variable
            type:
              _component_type: Property
              items:
                type: number
              type: array
          variable/140438685964896:
            _component_type: Variable
            default_value: null
            description: a float variable
            name: float_variable
            type:
              _component_type: Property
              type: number
          variablereadstep/140438685964704:
            _component_type: Step
            input_mapping: {}
            output_mapping: {}
            step_args:
              variable:
                $ref: variable/140438685963696
            step_cls: VariableReadStep
          variablewritestep/140438685963936:
            _component_type: Step
            input_mapping: {}
            output_mapping: {}
            step_args:
              operation: overwrite
              variable:
                $ref: variable/140438685963696
            step_cls: VariableWriteStep
        begin_step_name: read_step
        context_key_values_providers: []
        end_steps:
        - null
        steps:
          read_step:
            $ref: variablereadstep/140438685964704
          write_step:
            $ref: variablewritestep/140438685963936
        transitions:
          read_step:
          - write_step
          write_step:
          - null
        variables:
        - $ref: variable/140438685963696
        - $ref: variable/140438685964896
    """

    deserialized_flow = deserialize(Flow, serialized_flow)

    assert len(deserialized_flow.variables) == 2
    assert deserialized_flow.variables == variables
    assert deserialized_flow.steps["read_step"].variable == list_variable
    assert deserialized_flow.steps["write_step"].variable == list_variable

    serialized_flow = serialize(deserialized_flow)

    assert "variables:" in serialized_flow
    assert "$ref: variablereadstep" in serialized_flow
    assert "$ref: variablewritestep" in serialized_flow
    assert serialized_flow.count("_component_type: Variable\n") == 2


def test_can_serialize_and_deserialize_control_flow_edge():
    control_flow_edge = ControlFlowEdge(
        source_step=BranchingStep(branch_name_mapping={"": "branch1"}),
        destination_step=CompleteStep(),
        source_branch="branch1",
    )

    serialized_edge = serialize(control_flow_edge)
    deserialized_edge = cast(ControlFlowEdge, deserialize(ControlFlowEdge, serialized_edge))

    assert isinstance(deserialized_edge.source_step, BranchingStep)
    assert isinstance(deserialized_edge.destination_step, CompleteStep)
    assert deserialized_edge.source_branch == "branch1"


def test_serialization_and_deserialization_of_control_flow_edge_uses_references():
    step1 = OutputMessageStep("")
    control_flow_edge = ControlFlowEdge(source_step=step1, destination_step=step1)

    serialized_edge = serialize(control_flow_edge)
    deserialized_edge = cast(ControlFlowEdge, deserialize(ControlFlowEdge, serialized_edge))

    assert isinstance(deserialized_edge.source_step, OutputMessageStep)
    assert deserialized_edge.source_step is deserialized_edge.destination_step


def test_can_serialize_and_deserialize_data_flow_edge():
    input_step = InputMessageStep("hi {{username}}, how are you doing today?")
    output_step = OutputMessageStep("You said you were: {{mood}}")
    data_flow_edge = DataFlowEdge(
        source_step=input_step,
        source_output=input_step.USER_PROVIDED_INPUT,
        destination_step=output_step,
        destination_input="mood",
    )

    serialized_edge = serialize(data_flow_edge)
    deserialized_edge = cast(DataFlowEdge, deserialize(DataFlowEdge, serialized_edge))

    assert isinstance(deserialized_edge.source_step, InputMessageStep)
    assert isinstance(deserialized_edge.destination_step, OutputMessageStep)
    assert deserialized_edge.source_output == data_flow_edge.source_output
    assert deserialized_edge.destination_input == data_flow_edge.destination_input


def test_can_serialize_and_deserialize_data_flow_edge_with_context_provider():
    start_step = StartStep()
    step = OutputMessageStep("good")
    context_provider = FlowContextProvider(
        flow=Flow(
            begin_step_name="start",
            steps={"start": start_step, "my_step": step},
            control_flow_edges=[
                ControlFlowEdge(source_step=start_step, destination_step=step),
                ControlFlowEdge(source_step=step, destination_step=None),
            ],
        )
    )
    output_step = OutputMessageStep("You said you were: {{mood}}")
    data_flow_edge = DataFlowEdge(
        source_step=context_provider,
        source_output=OutputMessageStep.OUTPUT,
        destination_step=output_step,
        destination_input="mood",
    )

    serialized_edge = serialize(data_flow_edge)
    deserialized_edge = cast(DataFlowEdge, deserialize(DataFlowEdge, serialized_edge))

    assert isinstance(deserialized_edge.source_step, FlowContextProvider)
    assert set(deserialized_edge.source_step.flow.steps.keys()) == {"start", "my_step"}
    assert isinstance(deserialized_edge.destination_step, OutputMessageStep)
    assert deserialized_edge.source_output == data_flow_edge.source_output
    assert deserialized_edge.destination_input == data_flow_edge.destination_input


def check_data_edges_equality(flow_1: Flow, flow_2: Flow):
    for data_edge_1, data_edge_2 in zip(flow_1.data_flow_edges, flow_2.data_flow_edges):
        assert data_edge_1.source_output == data_edge_2.source_output
        assert data_edge_1.destination_input == data_edge_2.destination_input
        assert data_edge_1.source_step.__class__ == data_edge_2.source_step.__class__
        assert data_edge_1.destination_step.__class__ == data_edge_2.destination_step.__class__
        assert data_edge_1.id == data_edge_2.id


def test_data_edges_are_correctly_serde_with_input_outputs(flow_with_output_and_input_steps):
    serialized_flow = serialize(flow_with_output_and_input_steps)
    deserialized_flow = cast(Flow, autodeserialize(serialized_flow))
    check_data_edges_equality(flow_with_output_and_input_steps, deserialized_flow)


def test_data_edges_are_correctly_serde_(flow_with_subflow_step):
    serialized_flow = serialize(flow_with_subflow_step)
    deserialized_flow = cast(Flow, autodeserialize(serialized_flow))
    check_data_edges_equality(flow_with_subflow_step, deserialized_flow)


def test_data_edges_are_serialized_with_input_output_mapping():
    input_step = InputMessageStep(
        "What's your name?",
        output_mapping={
            InputMessageStep.USER_PROVIDED_INPUT: "username",
        },
    )
    output_step = OutputMessageStep("hi {{username}}")
    flow = Flow(
        begin_step_name="input",
        steps={"input": input_step, "output": output_step},
        control_flow_edges=[
            ControlFlowEdge(source_step=input_step, destination_step=output_step),
            ControlFlowEdge(source_step=output_step, destination_step=None),
        ],
    )

    serialized_flow = serialize(flow)
    deserialized_flow = cast(Flow, autodeserialize(serialized_flow))


def test_ocigenai_deserialization_from_deprecated_yaml_file() -> None:
    # passing individual parameters directly to OCIGenAIModel is deprecated, should use client_config instead
    # in the given serialized flow, note that the authentication parameters are directly below ocigenaimodel object
    serialized_flow = f"""
        _component_type: Flow
        _referenced_objects:
          controlflowedge/139943756284640:
            destination_step: null
            source_branch: next
            source_step:
              $ref: promptexecutionstep/139943754279472
          ocigenaimodel/139943756346320:
            _component_type: LlmModel
            auth_profile: DEFAULT
            auth_type: {COHERE_OCI_INSTANCE_PRINCIPAL_CONFIG["client_config"]["auth_type"]}
            compartment_id: {COHERE_OCI_INSTANCE_PRINCIPAL_CONFIG["client_config"]["compartment_id"]}
            generation_config:
              max_tokens: 512
            model_id: {COHERE_OCI_INSTANCE_PRINCIPAL_CONFIG["model_id"]}
            model_type: ocigenai
            service_endpoint: {COHERE_OCI_INSTANCE_PRINCIPAL_CONFIG["client_config"]["service_endpoint"]}
          promptexecutionstep/139943754279472:
            __metadata_info__: {{}}
            _component_type: Step
            input_mapping: {{}}
            output_mapping: {{}}
            step_args:
              generation_config: null
              llm:
                $ref: ocigenaimodel/139943756346320
              output_descriptors: null
              prompt_template: 'something'
            step_cls: PromptExecutionStep
        begin_step_name: Prompt Execution
        control_flow_edges:
        - $ref: controlflowedge/139943756284640
        end_steps:
        - null
        steps:
          Prompt Execution:
            $ref: promptexecutionstep/139943754279472
        variables: []
    """

    deserialized_flow = cast(Flow, autodeserialize(serialized_flow))
    oci_model_obj = deserialized_flow.steps["Prompt Execution"].llm
    assert isinstance(oci_model_obj, OCIGenAIModel)
    assert isinstance(oci_model_obj.client_config, OCIClientConfigWithInstancePrincipal)
    assert (
        oci_model_obj.client_config.service_endpoint
        == COHERE_OCI_INSTANCE_PRINCIPAL_CONFIG["client_config"]["service_endpoint"]
    )
    assert (
        oci_model_obj.client_config.compartment_id
        == COHERE_OCI_INSTANCE_PRINCIPAL_CONFIG["client_config"]["compartment_id"]
    )
    assert oci_model_obj.model_id == COHERE_OCI_INSTANCE_PRINCIPAL_CONFIG["model_id"]
