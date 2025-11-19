# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
import threading
import time
from typing import Any, Dict, List, Optional

import pytest

from wayflowcore import Message, MessageType
from wayflowcore._threading import initialize_threadpool, shutdown_threadpool
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import (
    create_single_step_flow,
    run_flow_and_return_outputs,
    run_single_step,
)
from wayflowcore.property import (
    AnyProperty,
    DictProperty,
    IntegerProperty,
    ListProperty,
    Property,
    StringProperty,
)
from wayflowcore.steps import (
    InputMessageStep,
    OutputMessageStep,
    ParallelMapStep,
    PromptExecutionStep,
    ToolExecutionStep,
)
from wayflowcore.tools import ServerTool, tool

from ...testhelpers.dummy import DummyModel

LIST_OF_STR_INPUTS = ["hello", "world", "!"]


def create_output_step_flow(template: str = "{{message_internal}}") -> Flow:
    return create_single_step_flow(
        step=OutputMessageStep(
            message_template=template,
            input_mapping={"message_internal": "message"},
            output_mapping={OutputMessageStep.OUTPUT: "printed_message"},
        ),
        step_name="add_to_conversation_step",
    )


def test_can_map_in_list_without_collecting() -> None:
    step = ParallelMapStep(
        unpack_input={"message": "."},
        flow=create_output_step_flow(),
    )
    conv, messages = run_single_step(
        step, inputs={ParallelMapStep.ITERATED_INPUT: LIST_OF_STR_INPUTS}
    )

    assert [m.content for m in messages] == LIST_OF_STR_INPUTS


@pytest.mark.parametrize(
    "input_descriptors, unpack_input, step_input, inside_template, expected_outputs",
    [
        (None, {"name": "."}, ["louis", "damien"], "-{{name}}", ["-louis", "-damien"]),
        (
            None,
            {"user": ".username", "email": ".email"},
            [
                {"username": "alex", "email": "a@oracle.com"},
                {"username": "jonas", "email": "j@oracle.com"},
            ],
            "{{user}}({{email}})",
            ["alex(a@oracle.com)", "jonas(j@oracle.com)"],
        ),
        (
            [DictProperty(name="names", value_type=AnyProperty())],
            {"user": "._key", "email": "._value.email"},
            {
                "alex": {"username": "alex", "email": "a@oracle.com"},
                "jonas": {"username": "jonas", "email": "j@oracle.com"},
            },
            "{{user}}({{email}})",
            ["alex(a@oracle.com)", "jonas(j@oracle.com)"],
        ),
        (
            [ListProperty(name="names", item_type=ListProperty(item_type=AnyProperty()))],
            {"user": ".[0]", "email": ".[1]"},
            [
                ["alex", "a@oracle.com"],
                ["jonas", "j@oracle.com"],
            ],
            "{{user}}({{email}})",
            ["alex(a@oracle.com)", "jonas(j@oracle.com)"],
        ),
        (
            None,
            {"content": "."},
            [
                {"username": "alex", "email": "a@oracle.com"},
                {"username": "jonas", "email": "j@oracle.com"},
            ],
            "{% for k,v in content.items() %}{{k}}:{{v}},{% endfor %}",
            ["username:alex,email:a@oracle.com,", "username:jonas,email:j@oracle.com,"],
        ),
    ],
)
def test_parallelmapstep_can_iterate_through_any_input_type(
    input_descriptors: Optional[List[Property]],
    unpack_input: Dict[str, str],
    step_input: Any,
    inside_template: str,
    expected_outputs: List[str],
) -> None:
    flow = Flow.from_steps(
        [
            ParallelMapStep(
                unpack_input=unpack_input,
                flow=Flow.from_steps(
                    steps=[
                        OutputMessageStep(message_template=inside_template),
                    ]
                ),
                input_descriptors=input_descriptors,
                output_descriptors=[ListProperty(name="outputs", item_type=AnyProperty())],
                input_mapping={ParallelMapStep.ITERATED_INPUT: "names"},
                output_mapping={OutputMessageStep.OUTPUT: "outputs"},
            ),
        ]
    )
    outputs = run_flow_and_return_outputs(flow, inputs={"names": step_input})
    assert outputs["outputs"] == expected_outputs


def test_parallelmapstep_can_iterate_with_inside_flow_without_inputs() -> None:
    assistant = create_single_step_flow(
        ParallelMapStep(
            flow=create_single_step_flow(OutputMessageStep(message_template="done")),
        )
    )
    conv = assistant.start_conversation(inputs={ParallelMapStep.ITERATED_INPUT: list(range(10))})
    conv.execute()
    messages = conv.get_messages()
    assert len(messages) == 10
    assert all(m.content == "done" for m in messages)


def test_parallelmapstep_has_correct_value_when_collecting_outputs_with_default_value():
    dummy_model = DummyModel()
    dummy_model.set_next_output(
        Message(
            content=json.dumps({"name": "agentspec"}),
            message_type=MessageType.AGENT,
        )
    )
    assistant = create_single_step_flow(
        ParallelMapStep(
            flow=create_single_step_flow(
                PromptExecutionStep(
                    llm=dummy_model,
                    prompt_template="what is the name of the project named agentspec?",
                    output_descriptors=[
                        StringProperty(
                            name="name",
                            description="name of the project",
                            default_value="none",
                        )
                    ],
                )
            ),
            output_descriptors=[ListProperty(name="name", item_type=AnyProperty())],
        )
    )
    conv = assistant.start_conversation(inputs={ParallelMapStep.ITERATED_INPUT: list(range(1))})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)


def test_parallelmapstep_with_tool_description_call_inside() -> None:

    def name_tool_func(i: int) -> str:
        match i % 3:
            case 0:
                return "damien"
            case 1:
                return "alex"
            case 2:
                return "jonas"
        return ""

    name_tool = ServerTool(
        name="name_tool",
        description="Tool that returns a name",
        func=name_tool_func,
        input_descriptors=[IntegerProperty(name="i")],
        output_descriptors=[StringProperty(name=ToolExecutionStep.TOOL_OUTPUT)],
    )

    assistant = Flow.from_steps(
        [
            ParallelMapStep(
                unpack_input={"i": "."},
                flow=Flow.from_steps(
                    steps=[
                        ToolExecutionStep(tool=name_tool),
                    ]
                ),
                output_descriptors=[
                    ListProperty(name=ToolExecutionStep.TOOL_OUTPUT, item_type=AnyProperty())
                ],
            ),
        ]
    )
    conv = assistant.start_conversation(inputs={ParallelMapStep.ITERATED_INPUT: list(range(3))})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values[ToolExecutionStep.TOOL_OUTPUT] == [
        "damien",
        "alex",
        "jonas",
    ]


def test_raises_when_iterated_input_type_is_dict_but_no_unpack_dict_is_passed() -> None:
    with pytest.raises(ValueError):
        ParallelMapStep(
            unpack_input=None,
            flow=Flow.from_steps(
                steps=[
                    OutputMessageStep(message_template="{{var}}"),  # inside type is str
                ]
            ),
            input_descriptors=[
                DictProperty(
                    name=ParallelMapStep.ITERATED_INPUT,
                    value_type=DictProperty(value_type=AnyProperty()),
                )
            ],
        )


def test_raises_when_iterated_input_type_is_of_wrong_type() -> None:
    with pytest.raises(ValueError):
        ParallelMapStep(
            unpack_input={"var": "."},
            flow=Flow.from_steps(
                steps=[
                    OutputMessageStep(message_template="{{var}}"),  # inside type is str
                ]
            ),
            input_descriptors=[StringProperty(name=ParallelMapStep.ITERATED_INPUT)],
        )


def test_raises_when_iterated_input_type_and_inside_flow_type_conflicts() -> None:
    with pytest.raises(ValueError):
        ParallelMapStep(
            unpack_input={"var": "."},
            flow=Flow.from_steps(
                steps=[
                    OutputMessageStep(message_template="{{var}}"),  # inside type is str
                ]
            ),
            input_descriptors=[
                ListProperty(
                    name=ParallelMapStep.ITERATED_INPUT,
                    item_type=DictProperty(value_type=AnyProperty()),
                )
            ],
        )


def test_raises_if_input_not_in_subflow() -> None:
    with pytest.raises(ValueError):
        _ = ParallelMapStep(
            unpack_input={"wrong_message": "."},
            output_descriptors=[ListProperty(name="printed_message", item_type=AnyProperty())],
            flow=create_output_step_flow(),
        )


def test_raises_if_some_input_not_in_subflow() -> None:
    with pytest.raises(ValueError):
        _ = ParallelMapStep(
            unpack_input={"message": "...", "wrong_message": "..."},
            output_descriptors=[ListProperty(name="printed_message", item_type=AnyProperty())],
            flow=create_output_step_flow(),
        )


def test_raises_if_output_not_in_subflow() -> None:
    with pytest.raises(ValueError):
        _ = ParallelMapStep(
            unpack_input={"message": "."},
            output_descriptors=[
                ListProperty(name="wrong_printed_message", item_type=AnyProperty())
            ],
            flow=create_output_step_flow(),
        )


def test_parallelmapstep_with_multiple_same_name_output_descriptors():
    @tool(description_mode="only_docstring")
    def create_list_from_str(string_input: str) -> List[str]:
        """
        Wraps a list around input string

        Parameters
        ----------
        string_input
            the input string
        """
        return [string_input]

    @tool(description_mode="only_docstring")
    def create_str_from_str_list(list_input: List[str]) -> str:
        """
        Converts a list of strings into string

        Parameters
        ----------
        list_input
            the input list
        """
        return str(list_input)

    def create_multi_step_tool_flow():
        multi_step_tool_flow = Flow.from_steps(
            [
                ToolExecutionStep(
                    tool=create_list_from_str,
                    input_mapping={"string_input": "var"},
                    output_mapping={ToolExecutionStep.TOOL_OUTPUT: "list_with_string"},
                ),
                ToolExecutionStep(
                    tool=create_str_from_str_list,
                    input_mapping={"list_input": "list_with_string"},
                    output_mapping={ToolExecutionStep.TOOL_OUTPUT: "output"},
                ),
            ]
        )
        return multi_step_tool_flow

    create_str_list_step = ParallelMapStep(
        flow=create_multi_step_tool_flow(),
        unpack_input={"var": "."},
        output_descriptors=[ListProperty(name="output", item_type=AnyProperty())],
        input_mapping={ParallelMapStep.ITERATED_INPUT: "list_of_str_inputs"},
    )
    flow = create_single_step_flow(create_str_list_step)
    outputs = run_flow_and_return_outputs(flow, inputs={"list_of_str_inputs": LIST_OF_STR_INPUTS})
    assert "['hello']" in outputs["output"]


@pytest.mark.parametrize(
    "flow,unpack_input,input_descriptors,output_name,expected_inputs,expected_outputs",
    [
        (
            create_single_step_flow(OutputMessageStep("What is your name, {{username}}?")),
            None,
            None,
            None,
            {"username", "iterated_input"},
            set(),
        ),
        (  # unpacking username
            create_single_step_flow(OutputMessageStep("What is your name, {{username}}?")),
            {"username": "."},
            None,
            None,
            {"iterated_input"},
            set(),
        ),
        (  # collecting an output
            create_single_step_flow(OutputMessageStep("What is your name, {{username}}?")),
            {"username": "."},
            None,
            [OutputMessageStep.OUTPUT],
            {"iterated_input"},
            {OutputMessageStep.OUTPUT},
        ),
    ],
)
def test_step_has_correct_input_and_output_descriptors(
    flow, unpack_input, input_descriptors, output_name, expected_inputs, expected_outputs
) -> None:

    # Check that the configuration description looks like what we need
    configuration = {
        "input_mapping": None,
        "output_mapping": None,
        "flow": flow,
        "unpack_input": unpack_input,
        "input_descriptors": input_descriptors,
        "output_descriptors": (
            [ListProperty(name=o, item_type=StringProperty()) for o in output_name]
            if output_name is not None
            else None
        ),
    }

    # set the static configuration
    step = ParallelMapStep(**configuration)

    # check that input descriptors can be created
    input_descriptors = step.input_descriptors
    assert {i.name for i in input_descriptors} == expected_inputs

    # check that output descriptors can be created
    output_descriptors = step.output_descriptors
    assert {o.name for o in output_descriptors} == expected_outputs

    # check that next steps can be retrieved
    next_step_names = step.get_branches()
    assert set(next_step_names) == {ParallelMapStep.BRANCH_NEXT}


def get_parallelmapstep(concurrent_workers: int) -> ParallelMapStep:
    pool = set()

    def thread_tool() -> int:
        """Returns the thread number"""
        thread_id = threading.get_ident()
        # nonlocal pool
        pool.add(thread_id)
        while len(pool) < concurrent_workers:
            time.sleep(0.2)  # make sure the first thread doesn't take everything
        return thread_id

    return ParallelMapStep(
        flow=create_single_step_flow(step=ToolExecutionStep(tool=tool(thread_tool))),
        output_descriptors=[
            ListProperty(name=ToolExecutionStep.TOOL_OUTPUT, item_type=AnyProperty())
        ],
    )


def run_parallelmapstep_with_thread_tools(
    expected_number_threads: Optional[int], run_in_parallel: bool = True
):
    flow = create_single_step_flow(
        get_parallelmapstep(concurrent_workers=expected_number_threads or 1)
    )
    conv = flow.start_conversation(inputs={ParallelMapStep.ITERATED_INPUT: list(range(50))})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    tool_outputs = status.output_values[ToolExecutionStep.TOOL_OUTPUT]
    number_of_threads_used = len(set(tool_outputs))
    if expected_number_threads is None and run_in_parallel:
        assert number_of_threads_used > 0
    else:
        assert number_of_threads_used == expected_number_threads


@pytest.mark.parametrize(
    "max_concurrent_threads,expected_number_threads",
    [
        (None, None),
        (1, 1),
        (4, 4),
        (8, 8),
    ],
)
def test_parallelmapstep_can_execute_in_parallel(
    max_concurrent_threads, expected_number_threads, shutdown_threadpool_fixture
):
    initialize_threadpool(max_concurrent_threads)
    run_parallelmapstep_with_thread_tools(expected_number_threads=expected_number_threads)
    shutdown_threadpool()


def test_parallelmapstep_leverages_the_right_number_of_threads(shutdown_threadpool_fixture):
    initialize_threadpool(1)
    run_parallelmapstep_with_thread_tools(expected_number_threads=1)
    shutdown_threadpool()
    initialize_threadpool(2)
    run_parallelmapstep_with_thread_tools(expected_number_threads=2)
    shutdown_threadpool()
    initialize_threadpool(3)
    run_parallelmapstep_with_thread_tools(expected_number_threads=3)
    shutdown_threadpool()
    initialize_threadpool(1)
    run_parallelmapstep_with_thread_tools(expected_number_threads=1)
    shutdown_threadpool()
    run_parallelmapstep_with_thread_tools(expected_number_threads=None)


def test_parallelmapstep_raises_when_given_flow_that_yields():
    with pytest.raises(ValueError):
        ParallelMapStep(
            flow=create_single_step_flow(step=InputMessageStep(message_template="Message")),
        )
