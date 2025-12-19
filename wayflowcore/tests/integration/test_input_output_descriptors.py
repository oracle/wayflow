# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
import inspect
from typing import Any, Dict, List, Optional, Type

import pytest

from wayflowcore import Agent, Flow, Step
from wayflowcore.componentwithio import ComponentWithInputsOutputs
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.flowhelpers import (
    create_single_step_flow,
    run_flow_and_return_outputs,
    run_step_and_return_outputs,
)
from wayflowcore.models import LlmModelFactory
from wayflowcore.property import (
    AnyProperty,
    IntegerProperty,
    ListProperty,
    Property,
    StringProperty,
)
from wayflowcore.steps import ApiCallStep, OutputMessageStep, PromptExecutionStep
from wayflowcore.steps.step import _StepRegistry
from wayflowcore.tools import ClientTool

from ..conftest import VLLM_MODEL_CONFIG
from .test_descriptors import create_init_arguments, steps_to_check


def create_step(
    input_descriptors: Optional[List[Property]] = None,
    output_descriptors: Optional[List[Property]] = None,
) -> Step:
    return OutputMessageStep(
        "{{query}}", input_descriptors=input_descriptors, output_descriptors=output_descriptors
    )


def create_flow(
    input_descriptors: Optional[List[Property]] = None,
    output_descriptors: Optional[List[Property]] = None,
) -> Flow:
    step = create_step()
    return Flow(
        begin_step=step,
        steps={"": step},
        control_flow_edges=[ControlFlowEdge(source_step=step, destination_step=None)],
        input_descriptors=input_descriptors,
        output_descriptors=output_descriptors,
    )


def create_agent(
    llm,
    input_descriptors: Optional[List[Property]] = None,
    output_descriptors: Optional[List[Property]] = None,
):
    return Agent(
        llm=llm,
        custom_instruction="{{query}}",
        output_descriptors=output_descriptors
        or [
            StringProperty(
                name=OutputMessageStep.OUTPUT,
                default_value="",
            )
        ],
        input_descriptors=input_descriptors,
    )


def create_tool(
    input_descriptors: Optional[List[Property]] = None,
    output_descriptors: Optional[List[Property]] = None,
):
    return ClientTool(
        name="some_tool",
        description="",
        parameters={"query": {"type": "string"}},
        output={"type": "string"},
        input_descriptors=input_descriptors,
        output_descriptors=output_descriptors,
    )


def check_input_and_output_descriptors(
    component: Any,
    input_type: Type[Property] = StringProperty,
    output_type: Type[Property] = StringProperty,
    output_name: str = OutputMessageStep.OUTPUT,
    num_input_descriptors: int = 1,
    num_output_descriptors: int = 1,
):
    assert isinstance(component, ComponentWithInputsOutputs)
    assert len(component.input_descriptors) == num_input_descriptors
    assert component.input_descriptors[0].name == "query"
    assert isinstance(component.input_descriptors[0], input_type)
    assert len(component.output_descriptors) == num_output_descriptors
    assert component.output_descriptors[0].name == output_name
    assert isinstance(component.output_descriptors[0], output_type)


@pytest.fixture
def default_class_parameter_values(datastore) -> Dict[str, Dict[str, object]]:
    return {
        ApiCallStep.__name__: {},
        OutputMessageStep.__name__: {},
        PromptExecutionStep.__name__: {},
    }


# import all wayflowcoresteps
from wayflowcore.steps import __all__ as all_wayflowcore_step_names

steps_to_check = [
    cls
    for cls in _StepRegistry._REGISTRY.values()
    if not inspect.isabstract(cls) and cls.__name__ in all_wayflowcore_step_names
    # and cls != SearchStep  # required searchable datastore
]


def run_step_descriptors_test(init_arguments, step_cls):
    auto_detected_input_descriptors = step_cls._compute_input_descriptors_from_static_config(
        **init_arguments
    )
    auto_detected_output_descriptors = step_cls._compute_output_descriptors_from_static_config(
        **init_arguments
    )

    DESCRIPTION = "some_very_special_description"

    modified_auto_detected_input_descriptors = [
        vtd.copy(description=DESCRIPTION) for vtd in auto_detected_input_descriptors
    ]
    modified_auto_detected_output_descriptors = [
        vtd.copy(description=DESCRIPTION) for vtd in auto_detected_output_descriptors
    ]

    init_arguments.update(
        dict(
            input_descriptors=modified_auto_detected_input_descriptors,
            output_descriptors=modified_auto_detected_output_descriptors,
        )
    )

    initialized_step: Step = step_cls(
        **init_arguments,
    )
    # only check when the list was not empty
    if len(auto_detected_input_descriptors) > 0:
        assert set(vtd.description for vtd in initialized_step.input_descriptors) == {DESCRIPTION}
    if len(auto_detected_output_descriptors) > 0:
        assert set(vtd.description for vtd in initialized_step.output_descriptors) == {DESCRIPTION}


@pytest.mark.parametrize("step_cls", steps_to_check)
def test_all_steps_can_override_auto_detected_io_descriptors(
    step_cls: Any, default_class_parameter_values
) -> None:
    init_arguments = create_init_arguments(step_cls, default_class_parameter_values)
    run_step_descriptors_test(init_arguments, step_cls)


def test_step_has_input_and_output_descriptors():
    step = create_step()
    check_input_and_output_descriptors(step)


def test_flow_has_input_and_output_descriptors():
    flow = create_flow()
    check_input_and_output_descriptors(flow)


def test_agent_has_input_and_output_descriptors(remotely_hosted_llm):
    agent = create_agent(remotely_hosted_llm)
    check_input_and_output_descriptors(agent)


def test_tool_has_input_and_output_descriptors():
    # cannot change the name of the output descriptor of a tool
    component = create_tool()
    check_input_and_output_descriptors(component, output_name="tool_output")


new_input_descriptor = IntegerProperty(
    name="query",
)
new_output_descriptor = IntegerProperty(name=OutputMessageStep.OUTPUT, default_value=1)


@pytest.mark.parametrize(
    "component",
    [
        create_step(
            input_descriptors=[new_input_descriptor],
            output_descriptors=[new_output_descriptor],
        ),
        create_flow(
            input_descriptors=[new_input_descriptor],
            output_descriptors=[new_output_descriptor],
        ),
        create_agent(
            llm=LlmModelFactory.from_config(VLLM_MODEL_CONFIG),
            input_descriptors=[new_input_descriptor],
            output_descriptors=[new_output_descriptor],
        ),
    ],
)
def test_can_override_input_descriptors_of_component(component):
    check_input_and_output_descriptors(
        component, input_type=IntegerProperty, output_type=IntegerProperty
    )


def test_can_override_input_descriptors_of_tool():
    component = create_tool(
        input_descriptors=[new_input_descriptor],
        output_descriptors=[IntegerProperty(name="tool_output", default_value=1)],
    )
    check_input_and_output_descriptors(
        component,
        input_type=IntegerProperty,
        output_type=IntegerProperty,
        output_name="tool_output",
    )


other_input_descriptor = IntegerProperty(name="some_other_input")
other_output_descriptor = IntegerProperty(name="some_other_output", default_value=1)


def test_additional_input_descriptor_step_raises():
    with pytest.raises(ValueError):
        step = create_step(
            input_descriptors=[new_input_descriptor, other_input_descriptor],
        )
        check_input_and_output_descriptors(component=step)


def test_additional_output_descriptor_step_raises():
    with pytest.raises(ValueError):
        step = create_step(
            output_descriptors=[new_output_descriptor, other_output_descriptor],
        )
        check_input_and_output_descriptors(component=step)


def test_additional_output_descriptor_step_that_has_output_descriptors_in_static_config_works(
    remotely_hosted_llm,
):
    step = PromptExecutionStep(
        llm=remotely_hosted_llm,
        prompt_template="{{query}}",
        output_descriptors=[new_output_descriptor, other_output_descriptor],
    )
    check_input_and_output_descriptors(
        component=step, num_output_descriptors=2, output_type=IntegerProperty
    )


def test_conflicting_input_descriptors_names_step_raises():
    with pytest.raises(ValueError):
        create_step(
            input_descriptors=[new_input_descriptor, new_input_descriptor],
        )


def test_conflicting_output_descriptors_names_step_raises():
    with pytest.raises(ValueError):
        create_step(
            output_descriptors=[new_output_descriptor, new_output_descriptor],
        )


def test_additional_input_descriptor_flow_raises():
    with pytest.raises(ValueError):
        flow = create_flow(
            input_descriptors=[new_input_descriptor, other_input_descriptor],
        )
        check_input_and_output_descriptors(component=flow)


def test_additional_output_descriptor_flow_raises():
    with pytest.raises(ValueError):
        flow = create_flow(
            output_descriptors=[new_output_descriptor, other_output_descriptor],
        )
        check_input_and_output_descriptors(component=flow)


def test_conflicting_input_descriptors_names_flow_raises():
    with pytest.raises(ValueError):
        create_flow(
            input_descriptors=[new_input_descriptor, new_input_descriptor],
        )


def test_conflicting_output_descriptors_names_flow_raises():
    with pytest.raises(ValueError):
        create_flow(
            output_descriptors=[new_output_descriptor, new_output_descriptor],
        )


def test_additional_input_descriptor_agent_raises():
    with pytest.raises(ValueError):
        agent = create_agent(
            llm=LlmModelFactory.from_config(VLLM_MODEL_CONFIG),
            input_descriptors=[new_input_descriptor, other_input_descriptor],
        )
        check_input_and_output_descriptors(component=agent)


def test_additional_output_descriptor_agent_doesnt_raise_since_it_changes_agent_behavior():
    agent = create_agent(
        llm=LlmModelFactory.from_config(VLLM_MODEL_CONFIG),
        output_descriptors=[new_output_descriptor, other_output_descriptor],
    )
    check_input_and_output_descriptors(
        component=agent,
        input_type=StringProperty,
        output_type=IntegerProperty,
        num_input_descriptors=1,
        num_output_descriptors=2,
    )


def test_conflicting_input_descriptors_names_agent_raises():
    with pytest.raises(ValueError):
        create_agent(
            llm=LlmModelFactory.from_config(VLLM_MODEL_CONFIG),
            input_descriptors=[new_input_descriptor, new_input_descriptor],
        )


def test_conflicting_output_descriptors_names_agent_raises():
    with pytest.raises(ValueError):
        create_agent(
            llm=LlmModelFactory.from_config(VLLM_MODEL_CONFIG),
            output_descriptors=[new_output_descriptor, new_output_descriptor],
        )


def test_type_can_be_precised_from_any_to_some_specific_type():
    step = OutputMessageStep("{% for s in inputs %}{{s}},{% endfor %}")
    outputs = run_step_and_return_outputs(step, inputs={"inputs": ["h", "e", "l", "l", "o"]})
    assert outputs[OutputMessageStep.OUTPUT] == "h,e,l,l,o,"
    assert len(step.input_descriptors) == 1
    assert isinstance(step.input_descriptors[0], AnyProperty)

    # runtime crash, since type is Any so no IO type checking
    with pytest.raises(TypeError):
        step = OutputMessageStep("{% for s in inputs %}{{s}},{% endfor %}")
        outputs = run_step_and_return_outputs(step, inputs={"inputs": 2})

    # crash at start because it's not the expected type
    with pytest.raises(TypeError):
        step = OutputMessageStep(
            message_template="{% for s in inputs %}{{s[0]}},{% endfor %}",
            input_descriptors=[ListProperty(name="inputs", item_type=StringProperty())],
        )
        outputs = run_step_and_return_outputs(step, inputs={"inputs": 2})


@pytest.mark.parametrize("step_cls", steps_to_check)
def test_all_steps_can_override_auto_detected_io_descriptors(step_cls: Any) -> None:
    init_arguments = create_init_arguments(step_cls)

    auto_detected_input_descriptors = step_cls._compute_input_descriptors_from_static_config(
        **init_arguments
    )
    auto_detected_output_descriptors = step_cls._compute_output_descriptors_from_static_config(
        **init_arguments
    )

    DESCRIPTION = "some_very_special_description"

    modified_auto_detected_input_descriptors = [
        vtd.copy(description=DESCRIPTION) for vtd in auto_detected_input_descriptors
    ]
    modified_auto_detected_output_descriptors = [
        vtd.copy(description=DESCRIPTION) for vtd in auto_detected_output_descriptors
    ]

    init_arguments.update(
        dict(
            input_descriptors=modified_auto_detected_input_descriptors,
            output_descriptors=modified_auto_detected_output_descriptors,
        )
    )

    initialized_step: Step = step_cls(
        **init_arguments,
    )
    # only check when the list was not empty
    if len(auto_detected_input_descriptors) > 0:
        assert set(vtd.description for vtd in initialized_step.input_descriptors) == {DESCRIPTION}
    if len(auto_detected_output_descriptors) > 0:
        assert set(vtd.description for vtd in initialized_step.output_descriptors) == {DESCRIPTION}


@pytest.mark.parametrize(
    "object_builder",
    [
        create_step,
        create_flow,
        lambda **kwargs: create_agent(**kwargs, llm=LlmModelFactory.from_config(VLLM_MODEL_CONFIG)),
    ],
)
def test_component_uses_default_input_descriptors_when_missing_expected_input_descriptor(
    object_builder,
):
    object_builder(input_descriptors=[])


def test_step_works_when_missing_expected_output_descriptor():
    step = OutputMessageStep(
        "{{query}}",
    )
    outputs = run_step_and_return_outputs(step, inputs={"query": "hello"})
    assert OutputMessageStep.OUTPUT in outputs
    assert outputs[OutputMessageStep.OUTPUT] == "hello"

    step = OutputMessageStep("{{query}}", output_descriptors=[])
    outputs = run_step_and_return_outputs(step, inputs={"query": "hello"})
    assert len(outputs) == 0


def check_descriptors_names_and_types_equality(
    descriptors: List[Property], expected_descriptors: List[Property]
):
    expected_descriptors_by_name = {
        descriptor.name: descriptor for descriptor in expected_descriptors
    }
    for descriptor in descriptors:
        assert descriptor.name in expected_descriptors_by_name
        assert descriptor._match_type_of(expected_descriptors_by_name[descriptor.name])

    new_descriptors_by_name = {descriptor.name: descriptor for descriptor in descriptors}
    for descriptor in expected_descriptors:
        assert descriptor.name in new_descriptors_by_name
        assert descriptor._match_type_of(new_descriptors_by_name[descriptor.name])


def test_e2e_step_input_descriptors_work_as_expected():
    # taking default
    step = OutputMessageStep("{{query}}", input_descriptors=None)
    check_descriptors_names_and_types_equality(
        step.input_descriptors, [StringProperty(name="query")]
    )
    # correctly passed
    step = OutputMessageStep("{{query}}", input_descriptors=[IntegerProperty(name="query")])
    check_descriptors_names_and_types_equality(
        step.input_descriptors, [IntegerProperty(name="query")]
    )

    with pytest.raises(ValueError):
        # misspelled descriptor
        OutputMessageStep("{{query}}", input_descriptors=[StringProperty(name="queryy")])

    with pytest.raises(ValueError):
        # one additional descriptor
        OutputMessageStep(
            "{{query}}",
            input_descriptors=[StringProperty(name="query"), IntegerProperty(name="unknown")],
        )

    # several descriptors
    step = OutputMessageStep("{{query}}{{query2}}", input_descriptors=None)
    check_descriptors_names_and_types_equality(
        step.input_descriptors, [StringProperty(name="query"), StringProperty(name="query2")]
    )

    # only override one descriptor
    step = OutputMessageStep(
        "{{query}}{{query2}}", input_descriptors=[IntegerProperty(name="query")]
    )
    check_descriptors_names_and_types_equality(
        step.input_descriptors, [IntegerProperty(name="query"), StringProperty(name="query2")]
    )

    # input names collide
    with pytest.raises(ValueError):
        OutputMessageStep(
            "{{query}}{{query2}}",
            input_descriptors=[IntegerProperty(name="query"), StringProperty(name="query")],
        )

    # input mapping collides input descriptors with proper types
    step = OutputMessageStep("{{query}}{{query2}}", input_mapping={"query2": "query"})
    check_descriptors_names_and_types_equality(
        step.input_descriptors, [StringProperty(name="query")]
    )

    # input mapping collides input descriptors with proper types
    step = OutputMessageStep(
        "{{query}}{{query2}}",
        input_descriptors=[IntegerProperty(name="query")],
        input_mapping={"query2": "query"},
    )
    check_descriptors_names_and_types_equality(
        step.input_descriptors, [IntegerProperty(name="query")]
    )


def test_e2e_step_output_descriptors_work_as_expected(remotely_hosted_llm):
    # taking default
    step = OutputMessageStep(output_descriptors=None)
    check_descriptors_names_and_types_equality(
        step.output_descriptors, [StringProperty(name="output_message")]
    )
    # correctly passed
    step = OutputMessageStep(output_descriptors=[IntegerProperty(name="output_message")])
    check_descriptors_names_and_types_equality(
        step.output_descriptors, [IntegerProperty(name="output_message")]
    )

    with pytest.raises(ValueError):
        # misspelled descriptor
        OutputMessageStep(output_descriptors=[StringProperty(name="ooutput_message")])

    with pytest.raises(ValueError):
        # one additional descriptor
        OutputMessageStep(
            output_descriptors=[
                StringProperty(name="output_message"),
                IntegerProperty(name="unknown"),
            ]
        )

    # output mapping is not properly setup
    with pytest.raises(ValueError):
        OutputMessageStep(
            output_descriptors=[IntegerProperty(name="output_message")],
            output_mapping={"output_message": "some_new_name"},
        )

    # output_mapping can be used to rename
    step = OutputMessageStep(
        output_descriptors=[IntegerProperty(name="some_new_name")],
        output_mapping={"output_message": "some_new_name"},
    )
    check_descriptors_names_and_types_equality(
        step.output_descriptors, [IntegerProperty(name="some_new_name")]
    )

    # removes an output descriptor
    step = OutputMessageStep(output_descriptors=[])
    check_descriptors_names_and_types_equality(step.output_descriptors, [])

    # output names collide
    with pytest.raises(ValueError):
        OutputMessageStep(
            output_descriptors=[IntegerProperty(name="output"), StringProperty(name="output")],
        )


def test_e2e_step_output_descriptors_that_changes_step_behavior(remotely_hosted_llm):
    # output changes step behavior
    step = PromptExecutionStep(llm=remotely_hosted_llm, prompt_template="", output_descriptors=None)
    check_descriptors_names_and_types_equality(
        step.output_descriptors, [StringProperty(name="output")]
    )

    # output changes step behavior
    step = PromptExecutionStep(llm=remotely_hosted_llm, prompt_template="", output_descriptors=[])
    check_descriptors_names_and_types_equality(step.output_descriptors, [])

    # output changes step behavior
    step = PromptExecutionStep(
        llm=remotely_hosted_llm,
        prompt_template="",
        output_descriptors=[IntegerProperty(name="integer_output")],
    )
    check_descriptors_names_and_types_equality(
        step.output_descriptors, [IntegerProperty(name="integer_output")]
    )


def create_single_step_flow_with_descriptors(
    input_descriptors: Optional[List[Property]] = None,
    output_descriptors: Optional[List[Property]] = None,
) -> Flow:
    step = OutputMessageStep()
    return Flow(
        begin_step=step,
        steps={"": step},
        control_flow_edges=[ControlFlowEdge(source_step=step, destination_step=None)],
        input_descriptors=input_descriptors,
        output_descriptors=output_descriptors,
    )


def test_e2e_flow_output_descriptors_work_as_expected(remotely_hosted_llm):
    # taking default
    flow = create_single_step_flow_with_descriptors(output_descriptors=None)
    check_descriptors_names_and_types_equality(
        flow.output_descriptors, [StringProperty(name="output_message")]
    )
    # correctly passed
    flow = create_single_step_flow_with_descriptors(
        output_descriptors=[IntegerProperty(name="output_message")]
    )
    check_descriptors_names_and_types_equality(
        flow.output_descriptors, [IntegerProperty(name="output_message")]
    )

    with pytest.raises(ValueError):
        # misspelled descriptor
        create_single_step_flow_with_descriptors(
            output_descriptors=[StringProperty(name="ooutput_message")]
        )

    with pytest.raises(ValueError):
        # one additional descriptor
        create_single_step_flow_with_descriptors(
            output_descriptors=[
                StringProperty(name="output_message"),
                IntegerProperty(name="unknown"),
            ]
        )

    # removes an output descriptor
    flow = create_single_step_flow_with_descriptors(output_descriptors=[])
    check_descriptors_names_and_types_equality(flow.output_descriptors, [])


def test_flow_has_steps_with_conflicting_input_names_works():
    output_1_step = OutputMessageStep("{{input_1}}")
    output_2_step = OutputMessageStep("{{input_1}}")
    flow = Flow(
        begin_step_name="step1",
        steps={
            "step1": output_1_step,
            "step2": output_2_step,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=output_1_step, destination_step=output_2_step),
            ControlFlowEdge(source_step=output_2_step, destination_step=None),
        ],
        data_flow_edges=[],
    )
    assert len(flow.input_descriptors_dict) == 1


def test_input_mapping_can_collide_inputs_but_step_still_works():
    step = OutputMessageStep(
        "{{query}}{{query2}}",
        input_descriptors=[IntegerProperty(name="query")],
        input_mapping={"query2": "query"},
    )
    flow = create_single_step_flow(step=step)
    outputs = run_flow_and_return_outputs(flow, inputs={"query": 3})
    assert outputs[OutputMessageStep.OUTPUT] == "33"
