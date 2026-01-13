# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import List, Tuple

import pytest

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.messagelist import MessageType
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.property import FloatProperty, ListProperty
from wayflowcore.serialization import autodeserialize, deserialize, serialize
from wayflowcore.serialization.context import DeserializationContext
from wayflowcore.steps import (
    AgentExecutionStep,
    ApiCallStep,
    FlowExecutionStep,
    MapStep,
    OutputMessageStep,
    PromptExecutionStep,
    ToolExecutionStep,
    VariableReadStep,
    VariableStep,
    VariableWriteStep,
)
from wayflowcore.steps.getchathistorystep import GetChatHistoryStep
from wayflowcore.steps.step import Step
from wayflowcore.tools import ServerTool, register_server_tool, tool
from wayflowcore.variable import Variable, VariableWriteOperation


@pytest.fixture
def example_flow():
    step_A = OutputMessageStep(message_template="Hello!")
    step_B = OutputMessageStep(message_template="How")
    step_C = OutputMessageStep(message_template="are")
    step_D = OutputMessageStep(message_template="you?")
    return Flow(
        begin_step=step_A,
        steps={
            "STEP_A": step_A,
            "STEP_B": step_B,
            "STEP_C": step_C,
            "STEP_D": step_D,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=step_A, destination_step=step_B),
            ControlFlowEdge(source_step=step_B, destination_step=step_C),
            ControlFlowEdge(source_step=step_C, destination_step=step_D),
            ControlFlowEdge(source_step=step_D, destination_step=None),
        ],
    )


def test_can_serialize_output_message_step() -> None:
    step = OutputMessageStep(
        message_template="Hello! How are you?", __metadata_info__={"x_position": 123}
    )
    serialized_step = serialize(step)
    assert isinstance(serialized_step, str)
    assert "Hello! How are you?" in serialized_step
    assert "x_position: 123" in serialized_step


def test_can_serialize_output_message_step_w_display() -> None:
    step = OutputMessageStep(
        message_template="Hello! How are you?",
        __metadata_info__={"x_position": 123},
        message_type=MessageType.DISPLAY_ONLY,
    )
    serialized_step = serialize(step)
    assert isinstance(serialized_step, str)
    assert "Hello! How are you?" in serialized_step
    assert "x_position: 123" in serialized_step
    assert "DISPLAY_ONLY" in serialized_step


def test_can_serialize_sub_flow_execution_step(example_flow: Flow) -> None:
    step = FlowExecutionStep(flow=example_flow)
    serialized_step = serialize(step)
    assert isinstance(serialized_step, str)
    assert "flow" in serialized_step
    assert "STEP_C" in serialized_step
    assert "Hello!" in serialized_step


def test_can_serialize_and_deserialize_map_step() -> None:
    step = MapStep(
        unpack_input={"message": "."},
        flow=create_single_step_flow(
            step=OutputMessageStep(
                message_template="{{message_internal}}",
                input_mapping={"message_internal": "message"},
                output_mapping={OutputMessageStep.OUTPUT: "printed_message"},
            ),
            step_name="add_to_conversation_step",
        ),
        input_mapping={MapStep.ITERATED_INPUT: "messages"},
    )
    serialized_step = serialize(step)
    assert isinstance(serialized_step, str)
    assert "{{message_internal}}" in serialized_step
    assert "add_to_conversation_step" in serialized_step

    deserialized_step = deserialize(Step, serialized_step)
    assert isinstance(deserialized_step, MapStep)
    assert deserialized_step.input_descriptors == step.input_descriptors
    assert deserialized_step.unpack_input == step.unpack_input
    assert deserialized_step.output_descriptors == step.output_descriptors
    assert set(deserialized_step.flow.steps) == set(step.flow.steps)


def test_can_deserialise_output_message_step() -> None:
    step = deserialize(
        Step,
        """
        _component_type: Step
        step_args:
            message_template: Hello! How are you?
            message_type: AGENT
            rephrase: false
        step_cls: OutputMessageStep
    """,
    )
    assert isinstance(step, Step)
    assert isinstance(step, OutputMessageStep)
    assert step.message_template == "Hello! How are you?"
    assert isinstance(step.message_type, MessageType)


def test_step_deserialization_raises_when_message_type_does_not_exist() -> None:
    with pytest.raises(
        ValueError,
        match="Error during deserialization of enum. Found value NOT_A_MESSAGE_TYPE.",
    ):
        step = deserialize(
            Step,
            """
            _component_type: Step
            step_args:
                message_template: Hello! How are you?
                message_type: NOT_A_MESSAGE_TYPE
                rephrase: false
            step_cls: OutputMessageStep
        """,
        )


def test_can_deserialise_subflow_execution_step() -> None:
    with pytest.warns(DeprecationWarning, match="Usage of `transitions` is deprecated"):
        step = deserialize(
            Step,
            """
            _component_type: Step
            step_args:
                flow:
                    _component_type: Flow
                    begin_step_name: STEP_A
                    end_steps:
                    - null
                    steps:
                        STEP_A:
                            _component_type: Step
                            step_args:
                                message_template: Hello!
                                message_type: AGENT
                                rephrase: false
                            step_cls: OutputMessageStep
                        STEP_B:
                            _component_type: Step
                            step_args:
                                message_template: How
                                message_type: AGENT
                                rephrase: false
                            step_cls: OutputMessageStep
                        STEP_C:
                            _component_type: Step
                            step_args:
                                message_template: are
                                message_type: AGENT
                                rephrase: false
                            step_cls: OutputMessageStep
                        STEP_D:
                            _component_type: Step
                            step_args:
                                message_template: you?
                                message_type: AGENT
                                rephrase: false
                            step_cls: OutputMessageStep
                    transitions:
                        STEP_A:
                        - STEP_B
                        STEP_B:
                        - STEP_C
                        STEP_C:
                        - STEP_D
                        STEP_D:
                        - null
            step_cls: FlowExecutionStep
        """,
        )
    assert isinstance(step, Step)
    assert isinstance(step, FlowExecutionStep)
    assert isinstance(step.flow, Flow)
    assert len(step.flow.steps) == 5


def test_can_deserialize_step_that_is_a_reference() -> None:
    serialized_step = """
      _component_type: Step
      _referenced_objects:
        here_is_my_reference_it_can_be_any_string:
          _component_type: Step
          step_args:
            message_template: 'How can I help you today?'
            message_type: AGENT
            rephrase: false
          step_cls: OutputMessageStep
      $ref: here_is_my_reference_it_can_be_any_string
    """
    step = deserialize(Step, serialized_step)
    assert isinstance(step, Step)
    assert isinstance(step, OutputMessageStep)
    assert step.message_template == "How can I help you today?"


@pytest.fixture
def testing_tools() -> List[ServerTool]:
    @tool(description_mode="only_docstring")
    def get_weather(location: str) -> str:
        """returns the state of the weather at the selected location"""
        return "windy"

    @tool(description_mode="only_docstring")
    def add_numbers(a: int, b: int) -> int:
        """adds the two numbers"""
        return a + b

    return [get_weather, add_numbers]


def test_tool_deserialization_raises_when_tools_are_not_registered() -> None:
    serialized_creative_step = """
      _component_type: Step
      _referenced_objects:
        agent/923891028:
          _component_type: Agent
          llm: {$ref: my_own_remote_llm}
          tools:
          - get_weather
          - add_numbers
          context_providers: []
          flows: []
          input_descriptors: []
          agents: []
          output_descriptors: []
          custom_instruction: null
          max_iterations: 10
          can_finish_conversation: True
        my_own_remote_llm:
          _component_type: LlmModel
          host_port: LLAMA_API_ENDPOINT
          model_id: meta-llama/Meta-Llama-3.1-8B-Instruct
          model_type: vllm
      step_args:
        agent:
            $ref: agent/923891028
      step_cls: AgentExecutionStep
    """
    with pytest.raises(
        ValueError,
        match="While trying to deserialize tool named 'get_weather', found no such tool registered",
    ):
        step = deserialize(Step, serialized_creative_step)


def test_agent_execution_step_deserialization_succeeds_when_tools_are_registered(
    testing_tools: List[ServerTool],
) -> None:
    serialized_agent_execution_step = """
      _component_type: Step
      _referenced_objects:
        my_own_remote_llm:
          _component_type: LlmModel
          host_port: LLAMA_API_ENDPOINT
          model_id: meta-llama/Meta-Llama-3.1-8B-Instruct
          model_type: vllm
        agent/923891023:
          _component_type: Agent
          llm: {$ref: my_own_remote_llm}
          tools:
          - get_weather
          - add_numbers
          context_providers: []
          flows: []
          input_descriptors: []
          agents: []
          output_descriptors: []
          custom_instruction: null
          max_iterations: 10
          can_finish_conversation: True
      step_args:
        agent: {$ref: agent/923891023}
      step_cls: AgentExecutionStep
    """
    deserialization_context = DeserializationContext()
    for t in testing_tools:
        deserialization_context.registered_tools[t.name] = t
    step = deserialize(Step, serialized_agent_execution_step, deserialization_context)
    assert isinstance(step, AgentExecutionStep)
    assert {t.name for t in step._referenced_tools()} == {"add_numbers", "get_weather"}


@pytest.fixture
def add_number_tool_with_context():
    deserialization_context = DeserializationContext()

    @tool(description_mode="only_docstring")
    def add_numbers(a: int, b: int) -> int:
        """adds the two numbers"""
        return a + b

    register_server_tool(add_numbers, deserialization_context.registered_tools)

    add_number_tool = deserialization_context.registered_tools["add_numbers"]
    return add_number_tool, deserialization_context


def test_can_serialize_tool_execution_step(
    add_number_tool_with_context: Tuple[
        ServerTool,
        DeserializationContext,
    ],
) -> None:
    add_number_tool, _ = add_number_tool_with_context
    step = ToolExecutionStep(tool=add_number_tool)
    serialized_step = serialize(step)
    assert "add_numbers" in serialized_step


def test_can_deserialize_serialized_tool_execution_step(
    add_number_tool_with_context: Tuple[
        ServerTool,
        DeserializationContext,
    ],
) -> None:
    add_number_tool, deserialization_context = add_number_tool_with_context
    step = ToolExecutionStep(tool=add_number_tool)
    deserialized_step = deserialize(Step, serialize(step), deserialization_context)
    assert isinstance(deserialized_step.tool, type(add_number_tool))


def test_can_autodeserialize_serialized_tool_execution_step(
    add_number_tool_with_context: Tuple[
        ServerTool,
        DeserializationContext,
    ],
) -> None:
    add_number_tool, deserialization_context = add_number_tool_with_context
    step = ToolExecutionStep(tool=add_number_tool)
    deserialized_step = autodeserialize(serialize(step), deserialization_context)
    assert isinstance(deserialized_step.tool, type(add_number_tool))


def test_prompt_execution_step_can_be_serde(remotely_hosted_llm: VllmModel) -> None:
    step = PromptExecutionStep(
        prompt_template="What is the capital of Switzerland?", llm=remotely_hosted_llm
    )

    serialized_step = serialize(step)

    assert "{}" in serialized_step  # empty generation kwargs are serialized as {}

    new_step: PromptExecutionStep = deserialize(Step, serialized_step)


@pytest.fixture
def list_variable():
    return Variable(
        name="list_of_floats_variable",
        type=ListProperty(item_type=FloatProperty()),
        description="list of floats variable",
        default_value=[],
    )


@pytest.fixture
def float_variable():
    return Variable(
        name="floats_variable",
        type=FloatProperty(),
        description=" variable",
        default_value=1.2,
    )


def test_variable_read_step_can_be_serde(list_variable: Variable) -> None:
    step = VariableReadStep(list_variable)
    serialized_step = serialize(step)

    assert "step_cls: VariableReadStep" in serialized_step
    assert "_referenced_objects:" in serialized_step
    assert "_component_type: Variable" in serialized_step
    assert "$ref: variable/" in serialized_step

    deserialized_step = deserialize(Step, serialized_step)

    assert isinstance(deserialized_step, VariableReadStep)
    assert deserialized_step.variable == list_variable


def test_variable_write_step_can_be_serde(list_variable: Variable) -> None:
    step = VariableWriteStep(list_variable)
    serialized_step = serialize(step)

    assert "step_cls: VariableWriteStep" in serialized_step
    assert "_referenced_objects:" in serialized_step
    assert "_component_type: Variable" in serialized_step
    assert "$ref: variable/" in serialized_step

    deserialized_step = deserialize(Step, serialized_step)

    assert isinstance(deserialized_step, VariableWriteStep)
    assert deserialized_step.variable == list_variable


def test_variable_step_can_be_serde_with_read_var(list_variable: Variable) -> None:
    step = VariableStep(read_variables=[list_variable])
    serialized_step = serialize(step)

    assert "step_cls: VariableStep" in serialized_step
    assert "_referenced_objects:" in serialized_step
    assert "_component_type: Variable" in serialized_step
    assert "$ref: variable/" in serialized_step

    deserialized_step = deserialize(Step, serialized_step)

    assert isinstance(deserialized_step, VariableStep)
    assert isinstance(deserialized_step.read_variables, list)
    assert isinstance(deserialized_step.write_variables, list)
    assert isinstance(deserialized_step.operations, dict)
    assert len(deserialized_step.read_variables) == 1
    assert len(deserialized_step.write_variables) == 0
    assert len(deserialized_step.operations) == 0
    assert deserialized_step.read_variables[0] == list_variable
    assert deserialized_step.read_variables[0].default_value == []


def test_variable_step_can_be_serde_with_read_vars(
    list_variable: Variable, float_variable: Variable
) -> None:
    step = VariableStep(
        read_variables=[
            list_variable,
            float_variable,
        ]
    )
    serialized_step = serialize(step)

    assert "step_cls: VariableStep" in serialized_step
    assert "_referenced_objects:" in serialized_step
    assert "_component_type: Variable" in serialized_step
    assert "$ref: variable/" in serialized_step

    deserialized_step = deserialize(Step, serialized_step)

    assert isinstance(deserialized_step, VariableStep)
    assert isinstance(deserialized_step.read_variables, list)
    assert isinstance(deserialized_step.write_variables, list)
    assert isinstance(deserialized_step.operations, dict)
    assert len(deserialized_step.read_variables) == 2
    assert len(deserialized_step.write_variables) == 0
    assert len(deserialized_step.operations) == 0
    assert deserialized_step.read_variables[0] == list_variable
    assert deserialized_step.read_variables[1] == float_variable
    assert deserialized_step.read_variables[0].default_value == []
    assert deserialized_step.read_variables[1].default_value == 1.2


def test_variable_step_can_be_serde_with_write_var(list_variable: Variable) -> None:
    step = VariableStep(
        write_variables=[list_variable], operations=VariableWriteOperation.OVERWRITE
    )
    serialized_step = serialize(step)

    assert "step_cls: VariableStep" in serialized_step
    assert "_referenced_objects:" in serialized_step
    assert "_component_type: Variable" in serialized_step
    assert "$ref: variable/" in serialized_step

    deserialized_step = deserialize(Step, serialized_step)

    assert isinstance(deserialized_step, VariableStep)
    assert isinstance(deserialized_step.read_variables, list)
    assert isinstance(deserialized_step.write_variables, list)
    assert isinstance(deserialized_step.operations, dict)
    assert len(deserialized_step.read_variables) == 0
    assert len(deserialized_step.write_variables) == 1
    assert len(deserialized_step.operations) == 1
    assert deserialized_step.write_variables[0] == list_variable
    assert list_variable.name in deserialized_step.operations
    assert deserialized_step.operations[list_variable.name] == VariableWriteOperation.OVERWRITE
    assert deserialized_step.write_variables[0].default_value == []


def test_variable_step_can_be_serde_with_write_vars(
    list_variable: Variable, float_variable: Variable
) -> None:
    step = VariableStep(
        write_variables=[list_variable, float_variable],
        operations={
            list_variable.name: VariableWriteOperation.INSERT,
            float_variable.name: VariableWriteOperation.OVERWRITE,
        },
    )
    serialized_step = serialize(step)

    assert "step_cls: VariableStep" in serialized_step
    assert "_referenced_objects:" in serialized_step
    assert "_component_type: Variable" in serialized_step
    assert "$ref: variable/" in serialized_step

    deserialized_step = deserialize(Step, serialized_step)

    assert isinstance(deserialized_step, VariableStep)
    assert isinstance(deserialized_step.read_variables, list)
    assert isinstance(deserialized_step.write_variables, list)
    assert isinstance(deserialized_step.operations, dict)
    assert len(deserialized_step.read_variables) == 0
    assert len(deserialized_step.write_variables) == 2
    assert len(deserialized_step.operations) == 2
    assert deserialized_step.write_variables[0] == list_variable
    assert deserialized_step.write_variables[1] == float_variable
    assert list_variable.name in deserialized_step.operations
    assert float_variable.name in deserialized_step.operations
    assert deserialized_step.operations[list_variable.name] == VariableWriteOperation.INSERT
    assert deserialized_step.operations[float_variable.name] == VariableWriteOperation.OVERWRITE
    assert deserialized_step.write_variables[0].default_value == []
    assert deserialized_step.write_variables[1].default_value == 1.2


def test_variable_step_can_be_serde_with_same_read_write_var(list_variable: Variable) -> None:
    step = VariableStep(
        read_variables=[list_variable],
        write_variables=[list_variable],
        operations=VariableWriteOperation.OVERWRITE,
    )
    serialized_step = serialize(step)

    assert "step_cls: VariableStep" in serialized_step
    assert "_referenced_objects:" in serialized_step
    assert "_component_type: Variable" in serialized_step
    assert "$ref: variable/" in serialized_step

    deserialized_step = deserialize(Step, serialized_step)

    assert isinstance(deserialized_step, VariableStep)
    assert isinstance(deserialized_step.read_variables, list)
    assert isinstance(deserialized_step.write_variables, list)
    assert isinstance(deserialized_step.operations, dict)
    assert len(deserialized_step.read_variables) == 1
    assert len(deserialized_step.write_variables) == 1
    assert len(deserialized_step.operations) == 1
    assert deserialized_step.read_variables[0] == list_variable
    assert deserialized_step.write_variables[0] == list_variable
    assert list_variable.name in deserialized_step.operations
    assert deserialized_step.operations[list_variable.name] == VariableWriteOperation.OVERWRITE
    assert deserialized_step.read_variables[0].default_value == []
    assert deserialized_step.write_variables[0].default_value == []


def test_variable_step_can_be_serde_with_different_read_write_var(
    list_variable: Variable, float_variable: Variable
) -> None:
    step = VariableStep(
        read_variables=[list_variable],
        write_variables=[float_variable],
        operations=VariableWriteOperation.OVERWRITE,
    )
    serialized_step = serialize(step)

    assert "step_cls: VariableStep" in serialized_step
    assert "_referenced_objects:" in serialized_step
    assert "_component_type: Variable" in serialized_step
    assert "$ref: variable/" in serialized_step

    deserialized_step = deserialize(Step, serialized_step)

    assert isinstance(deserialized_step, VariableStep)
    assert isinstance(deserialized_step.read_variables, list)
    assert isinstance(deserialized_step.write_variables, list)
    assert isinstance(deserialized_step.operations, dict)
    assert len(deserialized_step.read_variables) == 1
    assert len(deserialized_step.write_variables) == 1
    assert len(deserialized_step.operations) == 1
    assert deserialized_step.read_variables[0] == list_variable
    assert deserialized_step.write_variables[0] == float_variable
    assert float_variable.name in deserialized_step.operations
    assert deserialized_step.operations[float_variable.name] == VariableWriteOperation.OVERWRITE
    assert deserialized_step.read_variables[0].default_value == []
    assert deserialized_step.write_variables[0].default_value == 1.2


def test_variable_step_can_be_serde_with_read_write_vars(
    list_variable: Variable, float_variable: Variable
) -> None:
    step = VariableStep(
        read_variables=[list_variable, float_variable],
        write_variables=[float_variable, list_variable],
        operations={
            list_variable.name: VariableWriteOperation.INSERT,
            float_variable.name: VariableWriteOperation.OVERWRITE,
        },
    )
    serialized_step = serialize(step)

    assert "step_cls: VariableStep" in serialized_step
    assert "_referenced_objects:" in serialized_step
    assert "_component_type: Variable" in serialized_step
    assert "$ref: variable/" in serialized_step

    deserialized_step = deserialize(Step, serialized_step)

    assert isinstance(deserialized_step, VariableStep)
    assert isinstance(deserialized_step.read_variables, list)
    assert isinstance(deserialized_step.write_variables, list)
    assert isinstance(deserialized_step.operations, dict)
    assert len(deserialized_step.read_variables) == 2
    assert len(deserialized_step.write_variables) == 2
    assert len(deserialized_step.operations) == 2
    assert deserialized_step.read_variables[0] == list_variable
    assert deserialized_step.read_variables[1] == float_variable
    assert deserialized_step.write_variables[0] == float_variable
    assert deserialized_step.write_variables[1] == list_variable
    assert list_variable.name in deserialized_step.operations
    assert float_variable.name in deserialized_step.operations
    assert deserialized_step.operations[list_variable.name] == VariableWriteOperation.INSERT
    assert deserialized_step.operations[float_variable.name] == VariableWriteOperation.OVERWRITE
    assert deserialized_step.write_variables[0].default_value == 1.2
    assert deserialized_step.write_variables[1].default_value == []


def test_get_chat_history_with_default_arguments_can_be_serialized():
    step = GetChatHistoryStep(n=10)
    serialized_step = serialize(step)
    # Check that both default message types are in the serialization
    assert "AGENT" in serialized_step and "USER" in serialized_step


def test_get_chat_history_with_default_config_can_be_deserialized():
    serialized_step = serialize(GetChatHistoryStep())
    deserialized_step = deserialize(Step, serialized_step)
    assert deserialized_step.n == 10
    assert deserialized_step.message_types == [MessageType.USER, MessageType.AGENT]


def test_get_chat_history_with_custom_config_can_be_deserialized():
    serialized_step = serialize(
        GetChatHistoryStep(n=14, message_types=(MessageType.TOOL_REQUEST, MessageType.TOOL_RESULT))
    )
    deserialized_step = deserialize(Step, serialized_step)
    assert deserialized_step.n == 14
    assert deserialized_step.message_types == [MessageType.TOOL_REQUEST, MessageType.TOOL_RESULT]


def test_api_call_step_can_be_serde() -> None:
    step = ApiCallStep(
        url="https://example.com/orders/{{ order_id }}",
        method="POST",
        json_body={
            "topic_id": 12345,
            "item_id": "{{ item_id }}",
        },
        params={
            "store_id": "{{ store_id }}",
        },
        headers={
            "session_id": "{{ session_id }}",
        },
        sensitive_headers={"my_secret": "abc123"},
        output_values_json={
            "first_order_status": ".orders[0].status",
        },
    )

    serialized_step = serialize(step)
    assert "sensitive_headers" not in serialized_step
    assert "my_secret" not in serialized_step

    new_step: ApiCallStep = deserialize(Step, serialized_step)

    assert "first_order_status" in new_step.output_values_json
    assert new_step.output_values_json["first_order_status"] == ".orders[0].status"
