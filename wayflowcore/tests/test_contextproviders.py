# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Callable, Dict, List, Optional, Union
from unittest.mock import Mock

import pytest

from wayflowcore.agent import Agent
from wayflowcore.contextproviders import (
    ChatHistoryContextProvider,
    ContextProvider,
    FlowContextProvider,
    ToolContextProvider,
    get_default_context_providers,
)
from wayflowcore.contextproviders.constantcontextprovider import ConstantContextProvider
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors._flowexecutor import FlowConversationExecutionState
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow, run_single_step
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.property import Property, StringProperty
from wayflowcore.steps import FlowExecutionStep, OutputMessageStep, RegexExtractionStep
from wayflowcore.tools import ServerTool

from .testhelpers.dummy import SleepStep
from .testhelpers.testhelpers import retry_test


def run_single_output_message_step_with_context(
    template: str,
    context_providers: Optional[List[ContextProvider]],
    inputs: Optional[Dict[str, str]] = None,
) -> str:
    flow = create_single_step_flow(
        OutputMessageStep(message_template=template), context_providers=context_providers
    )
    conv = flow.start_conversation(inputs=inputs)
    flow.execute(conv)
    return conv.get_last_message().content


def create_value_type_description(name, value):
    return [
        ConstantContextProvider(
            value=value,
            output_description=StringProperty(
                name=name,
                description="the index of the next step in the plan",
                default_value="",
            ),
        )
    ]


@pytest.mark.parametrize(
    "template,context_providers,expected_answer",
    [
        (
            "Context: {{user_context}}",
            create_value_type_description("user_context", "user_name"),
            "Context: user_name",
        ),
        (
            "Context: {{plan}}",
            create_value_type_description("plan", "super_plan"),
            "Context: super_plan",
        ),
        ("Context", create_value_type_description("plan", "super_plan"), "Context"),
    ],
)
def test_output_message_step_correctly_uses_context(
    template: str, context_providers: List[ContextProvider], expected_answer: str
) -> None:
    message = run_single_output_message_step_with_context(template, context_providers)
    assert message == expected_answer


@pytest.mark.parametrize(
    "template, context_providers",
    [
        (
            "Context: {{ context_provider_4 }}",
            None,
        ),
        (
            "Context: {{ context_provider_1 }} and {{ context_provider_4 }}",
            create_value_type_description("context_provider_1", "super_plan")
            + create_value_type_description("context_provider_2", "super_plan")
            + create_value_type_description("context_provider_3", "super_plan"),
        ),
    ],
)
def test_missing_contextual_variable(
    template: str, context_providers: Optional[Dict[Property, Callable]]
) -> None:
    with pytest.raises(
        ValueError,
        match='Cannot start conversation because of missing inputs "context_provider_4',
    ):
        run_single_output_message_step_with_context(template, context_providers)


def run_single_output_message_step_with_context_within_subflow(
    template: str,
    top_flow_context_providers: Dict[Property, Callable],
    sub_flow_context_providers: Optional[Dict[Property, Callable]],
) -> str:
    sub_flow_step = FlowExecutionStep(
        flow=create_single_step_flow(
            OutputMessageStep(message_template=template),
            context_providers=sub_flow_context_providers,
        )
    )
    flow = create_single_step_flow(sub_flow_step, context_providers=top_flow_context_providers)
    conv = flow.start_conversation()
    flow.execute(conv)
    return conv.get_last_message().content


@pytest.mark.parametrize(
    "template,top_flow_context_providers,sub_flow_context_providers,expected_answer",
    [
        (
            "Context: {{ context_provider_1 }}",
            create_value_type_description("context_provider_1", "context_value_1"),
            None,
            "Context: context_value_1",
        ),
        (
            "Context: {{ context_provider_1 }}",
            {},
            create_value_type_description("context_provider_1", "context_value_1"),
            "Context: context_value_1",
        ),
        # The subflow overwrites the context provided by the top flow
        (
            "Context: {{ context_provider_1 }}",
            create_value_type_description("context_provider_1", "context_value_1"),
            create_value_type_description("context_provider_1", "context_value_1_sub_flow"),
            "Context: context_value_1_sub_flow",
        ),
        # Mixing context providers from subflow and top flow
        (
            "Context: {{ context_provider_1 }} and {{ context_provider_4 }}",
            create_value_type_description("context_provider_1", "context_value_1")
            + create_value_type_description("context_provider_2", "context_value_2")
            + create_value_type_description("context_provider_3", "context_value_3"),
            create_value_type_description("context_provider_4", "context_value_4"),
            "Context: context_value_1 and context_value_4",
        ),
    ],
)
def test_output_message_step_correctly_uses_context_in_a_subflow(
    template: str,
    top_flow_context_providers: Dict[Property, Callable],
    sub_flow_context_providers: Optional[Dict[Property, Callable]],
    expected_answer: str,
) -> None:
    message = run_single_output_message_step_with_context_within_subflow(
        template, top_flow_context_providers, sub_flow_context_providers
    )
    assert message == expected_answer


@pytest.mark.parametrize(
    "max_count, messages, user_input, expected_history",
    [
        # # Support empty history
        (5, [], "Hello world!", "USER >> Hello world!"),
        (101, [Message("a", MessageType.AGENT)] * 100, "b", "AGENT >> a\n" * 100 + "USER >> b"),
        (1, [], "b" * 1000, "USER >> " + "b" * 1000),
        (
            2,
            [Message("a" * 123, MessageType.AGENT)],
            "b" * 123,
            "AGENT >> " + "a" * 123 + "\nUSER >> " + "b" * 123,
        ),
        # Filters out non user or agent messages
        (5, [Message("a", MessageType.INTERNAL)], "Hello world!", "USER >> Hello world!"),
        (5, [Message("a", MessageType.THOUGHT)], "Hello world!", "USER >> Hello world!"),
        (5, [Message("a", MessageType.SYSTEM)], "Hello world!", "USER >> Hello world!"),
    ],
)
def test_load_history_returns_expected_result(
    max_count: int,
    messages: List[Message],
    user_input: str,
    expected_history: str,
) -> None:
    output_message_step = OutputMessageStep("{{ history }}")
    conversation, messages = run_single_step(
        output_message_step,
        messages=messages,
        user_input=user_input,
        context_providers=[
            ChatHistoryContextProvider(
                n=max_count,
                output_name="history",
            )
        ],
    )
    assert isinstance(conversation.state, FlowConversationExecutionState)
    assert "history" not in conversation.state.input_output_key_values
    assert messages[-1].content == expected_history


@pytest.mark.parametrize(
    "offset, expected_history",
    [
        (0, "AGENT >> Message Idx 98\nAGENT >> Message Idx 99\nUSER >> Message Idx 100"),
        (3, "AGENT >> Message Idx 95\nAGENT >> Message Idx 96\nAGENT >> Message Idx 97"),
        (99, "AGENT >> Message Idx 0\nAGENT >> Message Idx 1"),
        (123, ""),
    ],
)
def test_load_history_can_offset_messages(offset: int, expected_history: str) -> None:
    output_message_step = OutputMessageStep("{{ history }}")
    conversation, messages = run_single_step(
        output_message_step,
        messages=[Message(f"Message Idx {idx}", MessageType.AGENT) for idx in range(100)],
        user_input="Message Idx 100",
        context_providers=[
            ChatHistoryContextProvider(
                n=3,
                offset=offset,
                output_name="history",
            )
        ],
    )
    assert isinstance(conversation.state, FlowConversationExecutionState)
    assert "history" not in conversation.state.input_output_key_values
    assert messages[-1].content == expected_history


def run_two_output_message_step_with_context(
    template: str, context_providers: List[ContextProvider]
) -> str:
    flow = Flow.from_steps(
        [
            OutputMessageStep(message_template=template),
            OutputMessageStep(message_template=template),
        ],
        context_providers=context_providers,
    )

    conv = flow.start_conversation()
    flow.execute(conv)
    return conv.get_last_message().content


def make_context_provider_from_callable(
    function: Callable, output: Union[str, Property]
) -> ContextProvider:
    return ToolContextProvider(
        tool=ServerTool(
            name="mocked_cp",
            description="",
            func=function,
            input_descriptors=[],
            output_descriptors=[output] if isinstance(output, Property) else None,
        ),
        output_name=output if isinstance(output, str) else None,
    )


def test_context_provider_is_invoked_twice_when_it_is_used_twice() -> None:
    template = "Context: {{ context_provider }}"
    mocked_cp = Mock(return_value="Some interesting context")
    mocked_cp_unused = Mock(return_value="Some uninteresting context")
    run_two_output_message_step_with_context(
        template,
        [
            make_context_provider_from_callable(mocked_cp, output="context_provider"),
            make_context_provider_from_callable(mocked_cp_unused, output="context_provider_unused"),
        ],
    )
    assert mocked_cp.call_count == 2
    mocked_cp_unused.assert_not_called()


def test_invocation_raises_when_starting_conversation_with_unnecessary_inputs() -> None:
    mocked_cp = Mock(return_value="Some interesting context")
    with pytest.raises(
        ValueError,
        match="Input 'context_provider' passed to start conversation is not an expected input",
    ):
        run_single_output_message_step_with_context(
            "Context: {{ context_provider }}",
            [
                ConstantContextProvider(
                    value="Some interesting context",
                    output_description=StringProperty(name="context_provider"),
                )
            ],
            inputs={"context_provider": "Some interesting input"},
        )
    mocked_cp.assert_not_called()


def test_instantiating_flow_with_outputs_and_context_collisions_raises() -> None:
    with pytest.raises(
        ValueError,
        match="Found both a context provider and a step passing data to the same step input",
    ):
        regex_step = RegexExtractionStep(regex_pattern=".*")
        message_step = OutputMessageStep(message_template="{{output}}")
        flow = Flow(
            begin_step=regex_step,
            steps={
                "step": regex_step,
                "message_step": message_step,
            },
            control_flow_edges=[
                ControlFlowEdge(source_step=regex_step, destination_step=message_step),
                ControlFlowEdge(source_step=message_step, destination_step=None),
            ],
            context_providers=[
                ConstantContextProvider(
                    value="", output_description=StringProperty(name=RegexExtractionStep.OUTPUT)
                )
            ],
        )


def test_can_compute_default_context_providers() -> None:
    default_cp = get_default_context_providers()
    assert isinstance(default_cp, dict)
    assert len(default_cp) > 0
    assert all(callable(cp) for cp in default_cp.values())
    assert all(isinstance(vd, Property) for vd in default_cp.keys())


def test_context_provider_output_description_names_collision_when_init_flow() -> None:
    context_prov = create_value_type_description("my_context_provider", "main called")[0]
    assert isinstance(context_prov, ConstantContextProvider)
    context_value_desc, context_callable = (
        context_prov.get_output_descriptors()[0],
        lambda: context_prov._value,
    )
    mock_step = OutputMessageStep(message_template="{{my_context_provider}}")
    with pytest.raises(
        ValueError,
        match="The provided list of context providers contains those with non-unique output description names",
    ):
        Flow(
            begin_step=mock_step,
            steps={"mock_step": mock_step},
            control_flow_edges=[ControlFlowEdge(source_step=mock_step, destination_step=None)],
            context_providers=[
                make_context_provider_from_callable(
                    function=context_callable, output=context_value_desc
                )
                for _ in range(2)
            ],
        )


@pytest.fixture
def contextual_flow():
    time_output_step = OutputMessageStep(
        message_template="The current time is 2pm.",
        output_mapping={OutputMessageStep.OUTPUT: "time_output_io"},
        message_type=MessageType.SYSTEM,
    )
    place_output_step = OutputMessageStep(
        message_template="Your current location is Zurich.",
        message_type=MessageType.SYSTEM,
    )
    return Flow.from_steps([time_output_step, place_output_step])


def test_flow_context_provider_has_correct_output_description(contextual_flow: Flow):
    import dataclasses

    for flow_output_names in [
        ["time_output_io"],
        [OutputMessageStep.OUTPUT],
    ]:
        gcp = FlowContextProvider(
            flow=contextual_flow,  # None here means all outputs
            flow_output_names=flow_output_names if len(flow_output_names) == 1 else None,
        )
        output_descriptions = {
            value_desc.name: value_desc for value_desc in gcp.get_output_descriptors()
        }
        ordered_output_description_names = sorted(list(output_descriptions.keys()))
        output_descriptions = [
            output_descriptions[name] for name in ordered_output_description_names
        ]
        assert ordered_output_description_names == sorted(flow_output_names)
        assert output_descriptions == [
            dataclasses.replace(
                contextual_flow.output_descriptors_dict[output_name], name=output_name
            )
            for output_name in sorted(flow_output_names)
        ]


def test_flow_context_provider_with_mistmached_output_names_throws(
    contextual_flow: Flow,
):
    with pytest.raises(
        ValueError,
        match="If flow_output_names is specified, it must be a subset of the context flow's outputs.",
    ):
        FlowContextProvider(flow=contextual_flow, flow_output_names=["invalid_name_1"])


def test_flow_with_flow_context_provider_with_one_output_correctly_executes(
    contextual_flow: Flow,
):
    from wayflowcore.executors.executionstatus import FinishedStatus

    display_text_step = OutputMessageStep(
        message_template="Context Time: {{ time_output_io }}",
        output_mapping={OutputMessageStep.OUTPUT: "$display_io"},
    )
    flow = create_single_step_flow(
        display_text_step,
        context_providers=[
            FlowContextProvider(contextual_flow, flow_output_names=["time_output_io"])
        ],
    )

    conversation = flow.start_conversation()
    outputs = flow.execute(conversation)
    assert isinstance(outputs, FinishedStatus)

    assert outputs.output_values["$display_io"] == "Context Time: The current time is 2pm."


@retry_test(max_attempts=4, wait_between_tries=0)
def test_flexassistant_with_flow_context_provider_can_execute(
    contextual_flow: Flow, remotely_hosted_llm: VllmModel
) -> None:
    """
    Failure rate:          0 out of 10
    Observed on:           2024-11-13
    Average success time:  1.82 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """

    flow_cp = FlowContextProvider(contextual_flow, flow_output_names=["time_output_io"])
    assistant = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="Context: {{ time_output_io }} -- Today's date is April 20. First, say hello to the user and tell them the current date. Tell them the current location if asked to.",
        context_providers=[flow_cp],
        initial_message=None,
    )
    conversation = assistant.start_conversation()
    assistant.execute(conversation)

    assert "April" in conversation.get_last_message().content


@retry_test(max_attempts=2, wait_between_tries=0)
@pytest.mark.parametrize("context_provider_type", ["short_history", "full_history"])
def test_flexassistant_with_builtin_context_provider_can_execute(
    remotely_hosted_llm: VllmModel,
    context_provider_type: str,
) -> None:
    """
    Failure rate:          0 out of 100
    Observed on:           2024-12-04
    Average success time:  1.04 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           2
    Justification:         (0.01 ** 2) ~= 9.6 / 100'000
    """

    context_providers = {
        value_desc.name: context_prov
        for value_desc, context_prov in get_default_context_providers().items()
    }
    context_provider = context_providers[context_provider_type]
    assistant = Agent(
        llm=remotely_hosted_llm,
        custom_instruction=f"When asked, repeat the following secret word: {{% if 'Task' in {context_provider_type} %}}Task{{% else %}}Banana{{% endif %}}",
        context_providers=[context_provider],
    )
    conversation = assistant.start_conversation()
    conversation.append_user_message("What is the secret word?")
    assistant.execute(conversation)
    last_message = conversation.get_last_message().content
    if "history" in context_provider_type:
        assert "Banana" in last_message
    else:
        assert "Task" in last_message


def test_tool_context_provider_correctly_executes() -> None:
    from time import time

    from wayflowcore.steps import OutputMessageStep
    from wayflowcore.tools import ServerTool

    def current_time() -> str:
        from time import time

        return str(time())

    tool = ServerTool(
        name="Current time",
        description="Tool that returns time",
        parameters={},
        output={"type": "string"},
        func=current_time,
    )

    context_provider = ToolContextProvider(tool=tool, output_name="time_output_io")

    display_first_step = OutputMessageStep(
        message_template="{{ time_output_io }}",
    )
    sleep_step = SleepStep(sleep_time=0.2)
    display_second_step = OutputMessageStep(
        message_template="{{ time_output_io }}",
    )

    flow = Flow.from_steps(
        [display_first_step, sleep_step, display_second_step], context_providers=[context_provider]
    )

    before_time = time()
    conversation = flow.start_conversation()
    flow.execute(conversation)
    after_time = time()
    messages = conversation.get_messages()
    assert before_time < float(messages[-2].content) < float(messages[-1].content) < after_time


def test_tool_context_provider_works_with_tool_with_parameters_with_default() -> None:
    from wayflowcore.tools import ServerTool

    def current_time(a: str) -> str:
        from time import time

        return str(time())

    tool = ServerTool(
        name="Current time",
        description="Tool that returns time",
        parameters={"param_a": {"type": "string", "default": "hello!"}},
        output={"type": "string"},
        func=current_time,
    )

    _ = ToolContextProvider(tool=tool)


def test_tool_context_provider_fails_with_client_tool() -> None:
    from wayflowcore.tools import ClientTool

    tool = ClientTool(
        name="Current time",
        description="Tool that returns time",
        parameters={},
        output={"type": "string"},
    )

    with pytest.raises(ValueError, match="Only ServerTools are supported"):
        _ = ToolContextProvider(tool=tool)


def test_tool_context_provider_fails_with_tool_with_parameters_without_default() -> None:
    from wayflowcore.tools import ServerTool

    def current_time() -> str:
        from time import time

        return str(time())

    tool = ServerTool(
        name="Current time",
        description="Tool that returns time",
        parameters={"param_a": {"type": "string"}},
        output={"type": "string"},
        func=current_time,
    )

    with pytest.raises(
        ValueError, match="Only ServerTools that do not have parameters without default"
    ):
        _ = ToolContextProvider(tool=tool)
