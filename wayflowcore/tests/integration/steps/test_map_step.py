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

from wayflowcore import Agent, Message, MessageType
from wayflowcore._threading import initialize_threadpool, shutdown_threadpool
from wayflowcore.agent import CallerInputMode
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import (
    create_single_step_flow,
    run_flow_and_return_outputs,
    run_single_step,
)
from wayflowcore.property import AnyProperty, DictProperty, ListProperty, Property, StringProperty
from wayflowcore.steps import (
    AgentExecutionStep,
    InputMessageStep,
    MapStep,
    OutputMessageStep,
    PromptExecutionStep,
    RegexExtractionStep,
    ToolExecutionStep,
)
from wayflowcore.tools import ClientTool, ToolResult, tool

from ...testhelpers.dummy import DummyModel
from ...testhelpers.flowscriptrunner import (
    AnswerCheck,
    FlowScript,
    FlowScriptInteraction,
    FlowScriptRunner,
    IODictCheck,
)
from ...testhelpers.testhelpers import retry_test

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
    step = MapStep(
        unpack_input={"message": "."},
        flow=create_output_step_flow(),
    )
    conv, messages = run_single_step(step, inputs={MapStep.ITERATED_INPUT: LIST_OF_STR_INPUTS})

    assert [m.content for m in messages] == LIST_OF_STR_INPUTS


def test_can_map_and_use_properly_new_conversation_each_time() -> None:
    ask_location_flow = create_single_step_flow(
        step=InputMessageStep(
            message_template="Where is {{username}} located?",
            output_mapping={InputMessageStep.USER_PROVIDED_INPUT: "location"},
        ),
        step_name="add_to_conversation_step",
    )

    assistant = Flow.from_steps(
        [
            InputMessageStep(
                "Give me the names of the users, separated by a comma",
                output_mapping={InputMessageStep.USER_PROVIDED_INPUT: "raw_usernames"},
            ),
            RegexExtractionStep(
                regex_pattern=r"([^,]+)",
                return_first_match_only=False,
                input_mapping={RegexExtractionStep.TEXT: "raw_usernames"},
                output_mapping={RegexExtractionStep.OUTPUT: "usernames"},
            ),
            MapStep(
                unpack_input={"username": "."},
                output_descriptors=[ListProperty(name="locations", item_type=AnyProperty())],
                flow=ask_location_flow,
                input_mapping={MapStep.ITERATED_INPUT: "usernames"},
                output_mapping={"location": "locations"},
            ),
        ]
    )

    flow_script = FlowScript(
        interactions=[
            FlowScriptInteraction(user_input=None),
            FlowScriptInteraction(user_input="damien,jonas,alex"),
            FlowScriptInteraction(user_input="zurich"),
            FlowScriptInteraction(user_input="schlieren"),
            FlowScriptInteraction(
                user_input="zurich",
                checks=[
                    IODictCheck(lambda x: x == ["zurich", "schlieren", "zurich"], "locations"),
                    AnswerCheck("Where is damien located", -6),
                    AnswerCheck("zurich", -5),
                    AnswerCheck("Where is jonas located", -4),
                    AnswerCheck("schlieren", -3),
                    AnswerCheck("Where is alex located", -2),
                    AnswerCheck("zurich", -1),
                ],
            ),
        ]
    )

    runner = FlowScriptRunner(assistants=[assistant], flow_scripts=[flow_script])
    runner.execute(raise_exceptions=True)


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
            "{% for k in content %}{{k}}:{{content[k]}},{% endfor %}",
            ["username:alex,email:a@oracle.com,", "username:jonas,email:j@oracle.com,"],
        ),
    ],
)
def test_map_step_can_iterate_through_any_input_type(
    input_descriptors: Optional[List[Property]],
    unpack_input: Dict[str, str],
    step_input: Any,
    inside_template: str,
    expected_outputs: List[str],
) -> None:
    flow = Flow.from_steps(
        [
            MapStep(
                unpack_input=unpack_input,
                flow=Flow.from_steps(
                    steps=[
                        OutputMessageStep(message_template=inside_template),
                    ]
                ),
                input_descriptors=input_descriptors,
                output_descriptors=[ListProperty(name="outputs", item_type=AnyProperty())],
                input_mapping={MapStep.ITERATED_INPUT: "names"},
                output_mapping={OutputMessageStep.OUTPUT: "outputs"},
            ),
        ]
    )
    outputs = run_flow_and_return_outputs(flow, inputs={"names": step_input})
    assert outputs["outputs"] == expected_outputs


def test_map_step_can_iterate_with_inside_flow_without_inputs() -> None:
    assistant = create_single_step_flow(
        MapStep(
            flow=create_single_step_flow(OutputMessageStep(message_template="done")),
        )
    )
    conv = assistant.start_conversation(inputs={MapStep.ITERATED_INPUT: list(range(10))})
    conv.execute()
    messages = conv.get_messages()
    assert len(messages) == 10
    assert all(m.content == "done" for m in messages)


def test_map_step_has_correct_value_when_collecting_outputs_with_default_value():
    dummy_model = DummyModel()
    dummy_model.set_next_output(
        Message(
            content=json.dumps({"name": "agentspec"}),
            message_type=MessageType.AGENT,
        )
    )
    assistant = create_single_step_flow(
        MapStep(
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
    conv = assistant.start_conversation(inputs={MapStep.ITERATED_INPUT: list(range(1))})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)


def test_map_step_with_tool_description_call_inside() -> None:
    name_tool = ClientTool(
        name="name_tool",
        description="Ask the user for some name",
        parameters={},
    )
    assistant = Flow.from_steps(
        [
            MapStep(
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
    conv = assistant.start_conversation(inputs={MapStep.ITERATED_INPUT: list(range(3))})
    status = conv.execute()

    assert isinstance(status, ToolRequestStatus)
    conv.append_tool_result(
        ToolResult(tool_request_id=status.tool_requests[0].tool_request_id, content="damien")
    )
    status = conv.execute()
    assert isinstance(status, ToolRequestStatus)
    conv.append_tool_result(
        ToolResult(tool_request_id=status.tool_requests[0].tool_request_id, content="alex")
    )
    status = conv.execute()
    assert isinstance(status, ToolRequestStatus)
    conv.append_tool_result(
        ToolResult(tool_request_id=status.tool_requests[0].tool_request_id, content="jonas")
    )
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values[ToolExecutionStep.TOOL_OUTPUT] == [
        "damien",
        "alex",
        "jonas",
    ]


def test_raises_when_iterated_input_type_is_dict_but_no_unpack_dict_is_passed() -> None:
    with pytest.raises(ValueError):
        MapStep(
            unpack_input=None,
            flow=Flow.from_steps(
                steps=[
                    OutputMessageStep(message_template="{{var}}"),  # inside type is str
                ]
            ),
            input_descriptors=[
                DictProperty(
                    name=MapStep.ITERATED_INPUT, value_type=DictProperty(value_type=AnyProperty())
                )
            ],
        )


def test_raises_when_iterated_input_type_is_of_wrong_type() -> None:
    with pytest.raises(ValueError):
        MapStep(
            unpack_input={"var": "."},
            flow=Flow.from_steps(
                steps=[
                    OutputMessageStep(message_template="{{var}}"),  # inside type is str
                ]
            ),
            input_descriptors=[StringProperty(name=MapStep.ITERATED_INPUT)],
        )


def test_raises_when_iterated_input_type_and_inside_flow_type_conflicts() -> None:
    with pytest.raises(ValueError):
        MapStep(
            unpack_input={"var": "."},
            flow=Flow.from_steps(
                steps=[
                    OutputMessageStep(message_template="{{var}}"),  # inside type is str
                ]
            ),
            input_descriptors=[
                ListProperty(
                    name=MapStep.ITERATED_INPUT,
                    item_type=DictProperty(value_type=AnyProperty()),
                )
            ],
        )


def test_raises_if_input_not_in_subflow() -> None:
    with pytest.raises(ValueError):
        step = MapStep(
            unpack_input={"wrong_message": "."},
            output_descriptors=[ListProperty(name="printed_message", item_type=AnyProperty())],
            flow=create_output_step_flow(),
        )


def test_raises_if_some_input_not_in_subflow() -> None:
    with pytest.raises(ValueError):
        step = MapStep(
            unpack_input={"message": "...", "wrong_message": "..."},
            output_descriptors=[ListProperty(name="printed_message", item_type=AnyProperty())],
            flow=create_output_step_flow(),
        )


def test_raises_if_output_not_in_subflow() -> None:
    with pytest.raises(ValueError):
        step = MapStep(
            unpack_input={"message": "."},
            output_descriptors=[
                ListProperty(name="wrong_printed_message", item_type=AnyProperty())
            ],
            flow=create_output_step_flow(),
        )


def test_mapstep_with_multiple_same_name_output_descriptors():
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

    create_str_list_step = MapStep(
        flow=create_multi_step_tool_flow(),
        unpack_input={"var": "."},
        output_descriptors=[ListProperty(name="output", item_type=AnyProperty())],
        input_mapping={MapStep.ITERATED_INPUT: "list_of_str_inputs"},
    )
    flow = create_single_step_flow(create_str_list_step)
    outputs = run_flow_and_return_outputs(flow, inputs={"list_of_str_inputs": LIST_OF_STR_INPUTS})
    assert "['hello']" in outputs["output"]


@pytest.mark.parametrize(
    "flow,unpack_input,input_descriptors,output_name,expected_inputs,expected_outputs",
    [
        (
            create_single_step_flow(InputMessageStep("What is your name, {{username}}?")),
            None,
            None,
            None,
            {"username", "iterated_input"},
            set(),
        ),
        (  # unpacking username
            create_single_step_flow(InputMessageStep("What is your name, {{username}}?")),
            {"username": "."},
            None,
            None,
            {"iterated_input"},
            set(),
        ),
        (  # collecting an output
            create_single_step_flow(InputMessageStep("What is your name, {{username}}?")),
            {"username": "."},
            None,
            [InputMessageStep.USER_PROVIDED_INPUT],
            {"iterated_input"},
            {InputMessageStep.USER_PROVIDED_INPUT},
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
        "parallel_execution": False,
    }

    # set the static configuration
    step = MapStep(**configuration)

    # check that input descriptors can be created
    input_descriptors = step.input_descriptors
    assert {i.name for i in input_descriptors} == expected_inputs

    # check that output descriptors can be created
    output_descriptors = step.output_descriptors
    assert {o.name for o in output_descriptors} == expected_outputs

    # check that next steps can be retrieved
    next_step_names = step.get_branches()
    assert set(next_step_names) == {MapStep.BRANCH_NEXT}


def get_mapstep(run_in_parallel: bool, concurrent_workers: int) -> MapStep:
    pool = set()

    def thread_tool() -> int:
        """Returns the thread number"""
        thread_id = threading.get_ident()
        # nonlocal pool
        pool.add(thread_id)
        while len(pool) < concurrent_workers:
            time.sleep(0.2)  # make sure the first thread doesn't take everything
        return thread_id

    return MapStep(
        flow=create_single_step_flow(step=ToolExecutionStep(tool=tool(thread_tool))),
        parallel_execution=run_in_parallel,
        output_descriptors=[
            ListProperty(name=ToolExecutionStep.TOOL_OUTPUT, item_type=AnyProperty())
        ],
    )


def run_mapstep_with_thread_tools(
    expected_number_threads: Optional[int], run_in_parallel: bool = True
):
    flow = create_single_step_flow(
        get_mapstep(
            run_in_parallel=run_in_parallel, concurrent_workers=expected_number_threads or 1
        )
    )
    conv = flow.start_conversation(inputs={MapStep.ITERATED_INPUT: list(range(50))})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    tool_outputs = status.output_values[ToolExecutionStep.TOOL_OUTPUT]
    number_of_threads_used = len(set(tool_outputs))
    if expected_number_threads is None and run_in_parallel:
        assert number_of_threads_used > 0
    else:
        assert number_of_threads_used == expected_number_threads


@pytest.mark.parametrize(
    "run_in_parallel,max_concurrent_threads,expected_number_threads",
    [
        (True, None, None),
        (False, None, 1),
        (True, 1, 1),
        (True, 4, 4),
        (True, 8, 8),
    ],
)
def test_mapstep_can_execute_in_parallel(
    run_in_parallel, max_concurrent_threads, expected_number_threads, shutdown_threadpool_fixture
):
    initialize_threadpool(max_concurrent_threads)
    run_mapstep_with_thread_tools(
        expected_number_threads=expected_number_threads,
        run_in_parallel=run_in_parallel,
    )
    shutdown_threadpool()


def test_mapstep_leverages_the_right_number_of_threads(shutdown_threadpool_fixture):
    initialize_threadpool(1)
    run_mapstep_with_thread_tools(expected_number_threads=1)
    shutdown_threadpool()
    initialize_threadpool(2)
    run_mapstep_with_thread_tools(expected_number_threads=2)
    shutdown_threadpool()
    initialize_threadpool(3)
    run_mapstep_with_thread_tools(expected_number_threads=3)
    shutdown_threadpool()
    initialize_threadpool(1)
    run_mapstep_with_thread_tools(expected_number_threads=1)
    shutdown_threadpool()
    run_mapstep_with_thread_tools(expected_number_threads=None)


def test_map_step_parallel_raises_when_given_flow_that_yields():
    with pytest.raises(ValueError):
        MapStep(
            flow=create_single_step_flow(step=InputMessageStep(message_template="Message")),
            parallel_execution=True,
        )


def test_subflow_can_yield_and_sub_state_is_cleaned():
    step = MapStep(
        unpack_input={"username": "."},
        flow=create_single_step_flow(
            InputMessageStep("What is your name, {{username}}?"), step_name="substep"
        ),
    )

    flow = create_single_step_flow(step)
    conv = flow.start_conversation(inputs={MapStep.ITERATED_INPUT: ["d", "l"]})
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    assert conv.get_last_message().content == "What is your name, d?"
    conv.append_user_message("damien")
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    assert conv.get_last_message().content == "What is your name, l?"
    conv.append_user_message("louis")
    status = conv.execute()
    assert isinstance(status, FinishedStatus)


@retry_test(max_attempts=4)
def test_agent_execution_step_in_map_step(remotely_hosted_llm):
    """
    Failure rate:          1 out of 20
    Observed on:           2025-12-23
    Average success time:  1.19 seconds per successful attempt
    Average failure time:  1.10 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 6.8 / 100'000
    """

    @tool(description_mode="only_docstring")
    def get_email(name: str) -> str:
        """Get the work email address given an employee family name"""
        if "@oracle.com" in name:
            return name
        return name + "@oracle.com"

    agent = Agent(
        llm=remotely_hosted_llm,
        tools=[get_email],
        custom_instruction="Please figure out this employee email from the raw data:"
        "\n`{{person}}`.\n"
        "Only use the `get_email` tool if the email is not fully qualified."
        "Use the submit tool to submit your answer. Only use a single tool at a time",
        caller_input_mode=CallerInputMode.NEVER,
        output_descriptors=[
            StringProperty(name="email", description="work email address"),
        ],
    )

    agent_step = AgentExecutionStep(agent=agent, _share_conversation=False)

    map_step = MapStep(
        unpack_input={"person": "."},
        flow=Flow.from_steps(steps=[agent_step]),
        parallel_execution=True,
        output_descriptors=[ListProperty(name="email")],
    )

    flow = Flow.from_steps([map_step])

    conv = flow.start_conversation(
        inputs={
            MapStep.ITERATED_INPUT: [
                "work_email:marty@oracle.com",
                "family_name:lellison",
                "family_name:jdupont",
                "work_email:dupond@oracle.com",
            ]
        }
    )

    status = conv.execute()

    assert isinstance(status, FinishedStatus)

    assert set(s.lower() for s in status.output_values["email"]) == {
        "marty@oracle.com",
        "lellison@oracle.com",
        "jdupont@oracle.com",
        "dupond@oracle.com",
    }
