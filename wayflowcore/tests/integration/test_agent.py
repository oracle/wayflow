# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Annotated, Dict, List, Optional, Tuple, Union
from unittest.mock import Mock

import pytest
from _pytest.logging import LogCaptureFixture

from wayflowcore import Conversation
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.contextproviders import ContextProvider, ToolContextProvider
from wayflowcore.contextproviders.constantcontextprovider import ConstantContextProvider
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors._agentexecutor import _SUBMIT_TOOL_NAME
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.flow import Flow
from wayflowcore.messagelist import ImageContent, Message, MessageType
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.llmmodel import LlmModel
from wayflowcore.models.llmmodelfactory import LlmModelFactory
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.property import BooleanProperty, IntegerProperty, StringProperty
from wayflowcore.steps import (
    AgentExecutionStep,
    InputMessageStep,
    OutputMessageStep,
    ToolExecutionStep,
)
from wayflowcore.steps.step import Step
from wayflowcore.templates import PromptTemplate
from wayflowcore.tools import ClientTool, DescribedFlow, ServerTool, ToolRequest, ToolResult, tool

from ..conftest import VLLM_MODEL_CONFIG, with_all_llm_configs
from ..testhelpers.dummy import DummyModel
from ..testhelpers.flowscriptrunner import (
    AnswerCheck,
    FlowScript,
    FlowScriptInteraction,
    FlowScriptRunner,
)
from ..testhelpers.patching import patch_llm, patch_openai_compatible_llm
from ..testhelpers.testhelpers import retry_test
from ..testhelpers.teststeps import create_forecasting_flow

logger = logging.getLogger(__name__)


def create_dashboard_tool() -> ServerTool:

    @tool(description_mode="only_docstring")
    def create_dashboard(name: str, forecasted_data: str) -> str:
        """Creates a dashboard given a name and the forecasted data in string form"""
        return f"""Dashboard successfully created!
        {name}
        {'-'*len(name)}

        Forecasted data
        ---------------
        {forecasted_data}
        """

    return create_dashboard


@tool
def zinimo_tool(
    a: Annotated[int, "first required integer"], b: Annotated[int, "second required integer"]
) -> int:
    """Return the result of the zinimo operation between numbers a and b. This operation is secret and result is not predictable. Both inputs are required."""
    return a - b + 1


def create_agent(llm: LlmModel, **kwargs) -> Agent:
    dsa_described_flow = create_forecasting_flow([llm])
    dashboard_tool = create_dashboard_tool()

    return Agent(
        tools=[dashboard_tool],
        flows=[dsa_described_flow],
        llm=llm,
        **kwargs,
    )


def create_two_dashboards(successive_llm_calls: bool) -> FlowScriptInteraction:
    return FlowScriptInteraction(
        user_input="help me create 2 dashboards (one after the other): 1 named D1 with forecasted data [1,1,1] and one named D2 with forecasted data [2,2,2]",
        checks=[
            AnswerCheck("D1", -3 - int(successive_llm_calls)),
            AnswerCheck("D2", -2),
        ],
    )


def create_basic_agent(llm: LlmModel, **kwargs) -> Agent:
    return create_agent(
        llm=llm,
        custom_instruction="You are a helpful dashboard developer agent. Your goal is to help the user design data analysis dashboards",
        **kwargs,
    )


@pytest.fixture
def agent_with_yielding_subflow(remotely_hosted_llm: LlmModel) -> Agent:
    llm = remotely_hosted_llm
    input_step = InputMessageStep("What is the weather in Morocco")
    output_step = OutputMessageStep("The weather in Morocco {{ user_input }}")
    example_flow = Flow(
        name="get_weather",
        description="Flow to get the weather in Morocco",
        begin_step=input_step,
        steps={
            "input_step": input_step,
            "output_step": output_step,
        },
        control_flow_edges=[
            ControlFlowEdge(input_step, output_step),
            ControlFlowEdge(output_step, None),
        ],
        data_flow_edges=[
            DataFlowEdge(
                input_step, InputMessageStep.USER_PROVIDED_INPUT, output_step, "user_input"
            )
        ],
    )

    return Agent(llm=llm, flows=[example_flow])


@pytest.fixture
def what_time_is_it_context_provider() -> ToolContextProvider:
    tool_ = ServerTool(
        name="get_current_time",
        description="Tool that returns the current time",
        func=lambda: datetime.now().strftime("%d, %B %Y, %I:%M %p"),
        parameters={},
        output={"type": "string"},
    )
    return ToolContextProvider(
        tool=tool_,
        output_name="date_and_time",
    )


@retry_test(max_attempts=4, wait_between_tries=0)
@with_all_llm_configs
def test_agent_can_call_one_tool_vllm(llm_config: Dict[str, str]) -> None:
    """
    Failure rate:          3 out of 50
    Observed on:           2024-11-28
    Average success time:  3.51 seconds per successful attempt
    Average failure time:  3.44 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 3.5 / 100'000
    """
    llm = LlmModelFactory.from_config(llm_config)
    flow_script = FlowScript(
        interactions=[
            FlowScriptInteraction(
                user_input="help me create a dashboard named D1 with forecasted data [1,1,1]]",
                checks=[AnswerCheck("D1", -2)],
            )
        ]
    )
    agent = create_basic_agent(llm)
    runner = FlowScriptRunner([agent], [flow_script])
    runner.execute(raise_exceptions=True)


@retry_test(max_attempts=4, wait_between_tries=0)
def test_flexible_dont_use_tools_on_last_iteration(remotely_hosted_llm: LlmModel) -> None:
    """
    Failure rate:  2 out of 50
    Observed on:   2024-10-02
    Average success time:  3.63 seconds per successful attempt
    Average failure time:  TODO
    Max attempt:   4
    Justification: (0.06 ** 4) ~= 1.1 / 100'000
    """

    agent = Agent(
        llm=remotely_hosted_llm,
        max_iterations=2,
        tools=[zinimo_tool],
    )

    conv = agent.start_conversation()
    conv.append_user_message(
        "compute the result of the zinimo operation between zinimo(2,1) and 4)"
    )

    status = conv.execute()


@retry_test(max_attempts=5, wait_between_tries=0)
def test_agent_can_call_one_tool_two_times_in_a_row_vllm(remotely_hosted_llm: LlmModel) -> None:
    """
    Failure rate:          7 out of 50
    Observed on:           2024-12-17
    Average success time:  2.91 seconds per successful attempt
    Average failure time:  2.40 seconds per failed attempt
    Max attempt:           5
    Justification:         (0.15 ** 5) ~= 8.6 / 100'000
    """
    agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="You are a helpful agent",
        tools=[zinimo_tool],
    )

    conv = agent.start_conversation()
    conv.append_user_message("what is the result of zinimo(41,5) and zinimo(56,10)?")
    status = conv.execute()

    assert isinstance(status, UserMessageRequestStatus)
    agent_answer = conv.get_last_message().content
    assert "37" in agent_answer
    assert "47" in agent_answer


@retry_test(max_attempts=3, wait_between_tries=0)
def test_agent_can_call_two_tools_in_one_llm_call_gpt(gpt_llm):
    """
    Failure rate:  0 out of 50
    Observed on:   2024-10-02
    Average success time:  6.72 seconds per successful attempt
    Average failure time:  TODO
    Max attempt:   3
    Justification: (0.02 ** 3) ~= 0.7 / 100'000
    """
    flow_script = FlowScript(interactions=[create_two_dashboards(successive_llm_calls=False)])
    agent = create_basic_agent(gpt_llm)
    runner = FlowScriptRunner([agent], [flow_script])
    runner.execute(raise_exceptions=True)


@retry_test(max_attempts=3, wait_between_tries=0)
@with_all_llm_configs
def test_agent_can_call_one_flow_that_yields_vllm(llm_config: Dict[str, str]) -> None:
    """
    Failure rate:          0 out of 50
    Observed on:           2024-12-17
    Average success time:  1.77 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    llm = LlmModelFactory.from_config(llm_config)
    flow_script = FlowScript(
        interactions=[
            FlowScriptInteraction(user_input="forecast some data for my dashboard"),
            FlowScriptInteraction(
                user_input="4",
                checks=[AnswerCheck("[27, 28, 24, 21]", index=-2)],
            ),
        ]
    )
    agent = create_basic_agent(llm)
    runner = FlowScriptRunner([agent], [flow_script])
    runner.execute(raise_exceptions=True)


@retry_test(max_attempts=3, wait_between_tries=0)
@with_all_llm_configs
def test_agent_can_use_flows_and_tools_vllm(llm_config: Dict[str, str]) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2025-01-16
    Average success time:  5.28 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    llm = LlmModelFactory.from_config(llm_config)

    dsa_described_flow = create_forecasting_flow(None)

    described_flow = DescribedFlow(
        name="compute_forecast",
        description="computes the forecast data required to create a dashboard",
        flow=dsa_described_flow.flow,
        output=dsa_described_flow.output,
    )

    dashboard_called = [False]

    @tool
    def create_dashboard(
        name: Annotated[str, "name of the dashboard"],
        forecasted_data: Annotated[List[int], "forecasted data. Cannot be empty list"],
    ) -> str:
        """Creates a dashboard"""
        assert name == "my_dash"
        assert forecasted_data == [27, 28, 24, 21, 25]
        dashboard_called[0] = True
        return "Dashboard successfully created!"

    agent = Agent(
        tools=[create_dashboard],
        flows=[described_flow],
        llm=llm,
        custom_instruction="""Your ask is to help the user create a dashboard. IMPORTANT: use only one tool at a time""",
    )

    conv: Conversation = agent.start_conversation()
    conv.append_user_message(
        'help me create a dashboard. The name will be "my_dash". Compute the forecast data using your tool'
    )
    conv.execute()
    assert (
        conv.get_last_message().content
        == "Please choose a forecasting horizon (in weeks, between 1 and 7)"
    )  # message posted by the flow
    conv.append_user_message("5")
    conv.execute()
    if not dashboard_called[0]:
        # might need confirmation to continue
        conv.append_user_message('go ahead to create the dashboard named "my_dash"')
        conv.execute()
    assert dashboard_called[0]


def make_described_flow_with_single_step_with_input(step: Step, output: str):
    return DescribedFlow(
        flow=Flow(
            begin_step=step,
            steps={"single_step": step},
            control_flow_edges=[ControlFlowEdge(source_step=step, destination_step=None)],
        ),
        name="Search_Tool",
        description=(
            "A tool to search our company's internal documents. "
            "You must access our company's internal information by calling this tool with appropriate parameters."
        ),
        output=output,
    )


def run_test_agent_can_call_one_flow_with_one_input(
    remotely_hosted_llm: LlmModel, exec_step_name: str
) -> None:
    from wayflowcore.steps import PromptExecutionStep

    @tool
    def mock_tool(search_query: Annotated[str, "The search query to be performed."]) -> str:
        """A tool to search our knowledge base."""
        # make sure required inputs are required
        return "The science advisor of our company is George."

    mock_step = (
        PromptExecutionStep(
            (
                "The roles are as follow:\n"
                "- John is sales consultant\n"
                "- Lucie is head of strategy\n"
                "- George is the science advisor\n"
                "- Camille is the technical expert\n"
                "Answer with the correct name the following query: {{search_query}}"
            ),
            llm=remotely_hosted_llm,
            output_mapping={PromptExecutionStep.OUTPUT: "flow_output"},
        )
        if exec_step_name == "prompt_exec"
        else ToolExecutionStep(
            tool=mock_tool, output_mapping={ToolExecutionStep.TOOL_OUTPUT: "flow_output"}
        )
    )

    agent = Agent(
        llm=remotely_hosted_llm,
        flows=[
            make_described_flow_with_single_step_with_input(mock_step, output="flow_output")
        ],  # , output='flow_output')],
        custom_instruction="You are a helpful agent",
    )

    flow_script = FlowScript(
        interactions=[
            FlowScriptInteraction(
                user_input="Who is the science advisor of our company? Use the Search_Tool for this, with a suitable search_query.",
                checks=[AnswerCheck("George")],
            ),
        ],
    )

    runner = FlowScriptRunner([agent], [flow_script])
    runner.execute(raise_exceptions=True)


@retry_test(max_attempts=2, wait_between_tries=0)
def test_agent_can_call_one_flow_with_one_input_tool_execution_step(
    remotely_hosted_llm: LlmModel,
) -> None:
    """
    Failure rate:          0 out of 100
    Observed on:           2024-12-17
    Average success time:  2.40 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           2
    Justification:         (0.01 ** 2) ~= 9.6 / 100'000
    """
    run_test_agent_can_call_one_flow_with_one_input(remotely_hosted_llm, "tool_exec")


@retry_test(max_attempts=2, wait_between_tries=0)
def test_agent_can_call_one_flow_with_one_input_prompt_execution_step(
    remotely_hosted_llm: LlmModel,
) -> None:
    """
    Failure rate:          0 out of 100
    Observed on:           2025-11-05
    Average success time:  1.28 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           2
    Justification:         (0.01 ** 2) ~= 9.6 / 100'000
    """
    run_test_agent_can_call_one_flow_with_one_input(remotely_hosted_llm, "prompt_exec")


@retry_test(max_attempts=2, wait_between_tries=0)
@with_all_llm_configs
def test_agent_without_tools(llm_config: Dict[str, str]) -> None:
    """
    Failure rate:          0 out of 100
    Observed on:           2024-12-18
    Average success time:  0.28 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           2
    Justification:         (0.01 ** 2) ~= 9.6 / 100'000
    """
    llm = LlmModelFactory.from_config(llm_config)
    agent = Agent(llm=llm)
    flow_script = FlowScript(
        interactions=[
            FlowScriptInteraction(
                user_input="what is the capital of Switzerland?",
                checks=[AnswerCheck("bern")],
            ),
        ],
    )

    runner = FlowScriptRunner([agent], [flow_script])
    runner.execute(raise_exceptions=True)


def run_agent_with_context(
    llm_config: Dict[str, str], instruction: str, providers: Optional[List[ContextProvider]]
) -> None:
    llm = LlmModelFactory.from_config(llm_config)
    agent = Agent(
        llm=llm,
        custom_instruction=instruction,
        context_providers=providers,
    )
    flow_script = FlowScript(
        interactions=[
            FlowScriptInteraction(
                user_input="what is the capital of my country?",
                checks=[AnswerCheck("bern")],
            ),
        ],
    )
    runner = FlowScriptRunner([agent], [flow_script])
    runner.execute(raise_exceptions=True)


@with_all_llm_configs
def test_agent_fails_if_missing_needed_custom_instructions(llm_config: Dict[str, str]) -> None:
    with pytest.raises(ValueError):
        run_agent_with_context(llm_config, """""", providers=None)


@retry_test(max_attempts=2, wait_between_tries=0)
@with_all_llm_configs
def test_agent_succeeds_with_context_provider(llm_config: Dict[str, str]) -> None:
    """
    Failure rate:          0 out of 100
    Observed on:           2024-12-18
    Average success time:  0.28 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           2
    Justification:         (0.01 ** 2) ~= 9.6 / 100'000
    """
    run_agent_with_context(
        llm_config,
        """My country is: {{ country }}""",
        providers=[
            ConstantContextProvider(
                value="switzerland", output_description=StringProperty(name="country")
            )
        ],
    )


def create_spluk_gliif_tools() -> Tuple[Mock, Mock, ServerTool, ClientTool]:
    mock_spluk_operation = Mock(wraps=lambda a, b: 1 + 2 * a + 3 * b)
    mock_gliif_operation = Mock(wraps=lambda a, b: a * b // 2 - 12)

    def spluk_tool(a: int = 0, b: int = 0) -> int:
        """Computes the result of the spluk operation between numbers a and b"""
        return mock_spluk_operation(a=a, b=b)

    gliif_tool = ClientTool(
        name="gliif_tool",
        description="Computes the result of the gliif operation between numbers a and b",
        parameters={
            "a": {"type": "integer", "default": 0},
            "b": {"type": "integer", "default": 0},
        },
        output={"type": "integer"},
    )

    return (
        mock_spluk_operation,
        mock_gliif_operation,
        tool(spluk_tool, description_mode="only_docstring"),
        gliif_tool,
    )


def run_test_assistant_can_request_at_once_client_and_server_tools(
    assistant: Union[Flow, Agent],
    mock_spluk_operation: Mock,
    mock_gliif_operation: Mock,
) -> None:
    conversation = assistant.start_conversation()
    conversation.append_user_message(
        "I want to know the result of the spluk and the gliif operations with a=11 and b=6. Tell me both results at the same time."
    )
    execution_status = conversation.execute()

    # We expect that the first invocation has ToolRequestStatus because the
    # agent should try calling both tools before replying to the user and the
    # gliif tool is a client tool.
    assert isinstance(execution_status, ToolRequestStatus)
    assert len(execution_status.tool_requests) == 1
    client_tool_request = execution_status.tool_requests[0]
    assert client_tool_request.name == "gliif_tool"
    assert client_tool_request.args == {"a": 11, "b": 6}

    client_tool_result = ToolResult(
        content=mock_gliif_operation(**client_tool_request.args),
        tool_request_id=client_tool_request.tool_request_id,
    )
    conversation.append_message(
        Message(
            message_type=MessageType.TOOL_RESULT,
            tool_result=client_tool_result,
        )
    )

    execution_status = conversation.execute()
    assert isinstance(execution_status, UserMessageRequestStatus)
    last_agent_message = conversation.get_last_message()

    mock_gliif_operation.assert_called_once()
    assert mock_gliif_operation.call_args.kwargs == {"a": 11, "b": 6}
    assert "21" in last_agent_message.content
    mock_spluk_operation.assert_called_once()
    assert mock_spluk_operation.call_args.kwargs == {"a": 11, "b": 6}
    assert "41" in last_agent_message.content


@retry_test(max_attempts=10, wait_between_tries=1)  # TODO
def test_agent_can_request_at_once_client_and_server_tools(
    remotely_hosted_llm: LlmModel,
) -> None:
    """
    Failure rate:          2 out of 100
    Observed on:           2024-12-17
    Average success time:  3.00 seconds per successful attempt
    Average failure time:  2.89 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 2.5 / 100'000
    """
    mock_spluk_operation, mock_gliif_operation, spluk_tool, gliif_tool = create_spluk_gliif_tools()

    agent = Agent(
        tools=[spluk_tool, gliif_tool],
        llm=remotely_hosted_llm,
        custom_instruction="You are an expert of the spluk and gliif operations. These are highly complex operations for which you have tools, never make up any result and always use the tool results.",
    )
    run_test_assistant_can_request_at_once_client_and_server_tools(
        agent, mock_spluk_operation, mock_gliif_operation
    )


@pytest.fixture
def measure_room_temp_tool():
    tool = ClientTool(
        name="measure_room_temp",
        description="Return the value of the temperature in the room",
        parameters={},
    )
    return tool


@pytest.fixture
def measure_room_temp_tool_with_confirmation():
    tool = ClientTool(
        name="measure_room_temp",
        description="Return the value of the temperature in the room",
        parameters={},
        requires_confirmation=True,
    )
    return tool


@pytest.fixture
def dummy_check_name_in_db_tool():
    tool_func = lambda name: "This name is present in the database"
    tool = ServerTool(
        func=tool_func,
        name="dummy_check_name_in_db_tool",
        description="Check if a name is present in the database",
        parameters={"name": {"type": "string"}},
        requires_confirmation=True,
    )
    return tool


def run_test_agent_can_call_client_tool_with_no_parameter(assistant: Union[Flow, Agent]) -> None:
    conversation = assistant.start_conversation()
    conversation.append_user_message("What is the temperature in the room? Use your tool if needed")
    execution_status = conversation.execute()
    assert isinstance(execution_status, ToolRequestStatus)
    assert len(execution_status.tool_requests) == 1
    client_tool_request = execution_status.tool_requests[0]
    assert client_tool_request.name == "measure_room_temp"
    assert not client_tool_request.args  # because the tool has no arguments


@retry_test(max_attempts=3, wait_between_tries=1)
def test_agent_can_call_client_tool_with_no_parameter(
    remotely_hosted_llm: LlmModel,
    measure_room_temp_tool: ClientTool,
) -> None:
    """
    Failure rate:          1 out of 50
    Observed on:           2025-05-20
    Average success time:  0.43 seconds per successful attempt
    Average failure time:  0.50 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000
    """
    agent = Agent(
        tools=[measure_room_temp_tool],
        llm=remotely_hosted_llm,
        custom_instruction="You are a helpful agent that has access to some tools.",
    )
    run_test_agent_can_call_client_tool_with_no_parameter(agent)


def run_test_agent_can_call_client_tool_with_confirmation_with_no_parameter(
    assistant: Union[Flow, Agent],
) -> None:
    conversation = assistant.start_conversation()
    conversation.append_user_message("What is the temperature in the room? Use your tool if needed")
    execution_status = conversation.execute()
    assert isinstance(execution_status, ToolExecutionConfirmationStatus)
    execution_status.confirm_tool_execution(tool_request=execution_status.tool_requests[0])
    execution_status = conversation.execute()
    assert isinstance(execution_status, ToolRequestStatus)
    assert len(execution_status.tool_requests) == 1
    client_tool_request = execution_status.tool_requests[0]
    assert client_tool_request.name == "measure_room_temp"
    assert not client_tool_request.args  # because the tool has no arguments


def run_test_agent_can_call_client_tool_with_rejection_with_no_parameter(
    assistant: Union[Flow, Agent],
) -> None:
    conversation = assistant.start_conversation()
    conversation.append_user_message("What is the temperature in the room? Use your tool if needed")
    execution_status = conversation.execute()
    assert isinstance(execution_status, ToolExecutionConfirmationStatus)
    execution_status.reject_tool_execution(
        tool_request=execution_status.tool_requests[0], reason="Simply Call the tool again"
    )
    execution_status = conversation.execute()
    assert isinstance(execution_status, ToolExecutionConfirmationStatus)
    execution_status.reject_tool_execution(
        tool_request=execution_status.tool_requests[0],
        reason="You can never access this tool. Do not call the tool again. DO NOT TRY AGAIN!",
    )
    execution_status = conversation.execute()
    assert isinstance(execution_status, UserMessageRequestStatus)


@retry_test(max_attempts=3)
def test_agent_can_call_client_tool_with_confirmation_with_no_parameter(
    remotely_hosted_llm: LlmModel,
    measure_room_temp_tool_with_confirmation: ClientTool,
) -> None:
    """
    Failure rate:          0 out of 50
    Observed on:           2025-10-20
    Average success time:  0.57 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    agent = Agent(
        tools=[measure_room_temp_tool_with_confirmation],
        llm=remotely_hosted_llm,
        custom_instruction="You are a helpful agent that has access to some tools.",
    )
    run_test_agent_can_call_client_tool_with_confirmation_with_no_parameter(agent)


@retry_test(max_attempts=3)
def test_agent_can_call_client_tool_with_rejection_with_no_parameter(
    remotely_hosted_llm: LlmModel,
    measure_room_temp_tool_with_confirmation: ClientTool,
) -> None:
    """
    Failure rate:          2 out of 50
    Observed on:           2025-10-20
    Average success time:  1.93 seconds per successful attempt
    Average failure time:  1.16 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.1 / 100'000
    """
    agent = Agent(
        tools=[measure_room_temp_tool_with_confirmation],
        llm=remotely_hosted_llm,
        custom_instruction="You are a helpful agent that has access to some tools.",
    )
    run_test_agent_can_call_client_tool_with_rejection_with_no_parameter(agent)


@pytest.fixture
def agent_with_db_tool(
    remotely_hosted_llm: LlmModel,
    dummy_check_name_in_db_tool: ServerTool,
):
    agent = Agent(
        tools=[dummy_check_name_in_db_tool],
        llm=remotely_hosted_llm,
        custom_instruction="You are a helpful agent that has access to some tools which check if a person is present in database.",
    )
    return agent


@retry_test(max_attempts=3)
def test_agent_can_call_server_tool_with_confirmation(
    agent_with_db_tool: Agent,
) -> None:
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-23
    Average success time:  1.88 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    conversation = agent_with_db_tool.start_conversation()
    conversation.append_user_message(
        "Is name Jack present in the database? Use your tool if needed"
    )
    execution_status = conversation.execute()
    assert isinstance(execution_status, ToolExecutionConfirmationStatus)
    assert len(execution_status.tool_requests) == 1
    server_tool_request = execution_status.tool_requests[0]
    assert server_tool_request.name == "dummy_check_name_in_db_tool"
    execution_status.confirm_tool_execution(tool_request=server_tool_request)
    execution_status = conversation.execute()
    assert isinstance(execution_status, UserMessageRequestStatus)

    conversation = agent_with_db_tool.start_conversation()
    conversation.append_user_message(
        "Is name Jack present in the database? Use your tool if needed"
    )
    execution_status = conversation.execute()
    assert isinstance(execution_status, ToolExecutionConfirmationStatus)
    execution_status.confirm_tool_execution(tool_request=execution_status.tool_requests[0])
    execution_status = conversation.execute()
    assert isinstance(execution_status, UserMessageRequestStatus)


@retry_test(max_attempts=3, wait_between_tries=1)
def test_agent_can_handle_server_tool_rejection_multiple_times(agent_with_db_tool: Agent) -> None:
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-29
    Average success time:  1.60 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    conversation = agent_with_db_tool.start_conversation()
    conversation.append_user_message(
        "Is name Jack present in the database? Use your tool if needed"
    )
    execution_status = conversation.execute()
    assert isinstance(execution_status, ToolExecutionConfirmationStatus)
    server_tool_request = execution_status.tool_requests[0]
    execution_status.reject_tool_execution(
        tool_request=server_tool_request, reason="Simply Call the tool again"
    )
    execution_status = conversation.execute()
    assert isinstance(execution_status, ToolExecutionConfirmationStatus)
    execution_status.reject_tool_execution(
        tool_request=execution_status.tool_requests[0],
        reason="This database cannot be accessed. Do not try again",
    )
    execution_status = conversation.execute()
    assert isinstance(execution_status, UserMessageRequestStatus) or isinstance(
        execution_status, FinishedStatus
    )


@retry_test(max_attempts=3, wait_between_tries=1)
def test_agent_can_handle_server_tool_rejection_once(agent_with_db_tool: Agent) -> None:
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-29
    Average success time:  1.16 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """

    conversation = agent_with_db_tool.start_conversation()
    conversation.append_user_message(
        "Is name Jack present in the database? Use your tool if needed"
    )
    execution_status = conversation.execute()
    assert isinstance(execution_status, ToolExecutionConfirmationStatus)
    execution_status.reject_tool_execution(
        tool_request=execution_status.tool_requests[0],
        reason="This database cannot be accessed. Do not try again",
    )
    execution_status = conversation.execute()
    assert isinstance(execution_status, UserMessageRequestStatus) or isinstance(
        execution_status, FinishedStatus
    )


@retry_test(max_attempts=3)
def test_server_tool_raises_error_when_not_confirmed(agent_with_db_tool: Agent) -> None:
    """
    Failure rate:          0 out of 50
    Observed on:           2025-09-29
    Average success time:  0.50 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """

    conversation = agent_with_db_tool.start_conversation()
    conversation.append_user_message(
        "Is name Jack present in the database? Use your tool if needed"
    )
    execution_status = conversation.execute()
    assert isinstance(execution_status, ToolExecutionConfirmationStatus)
    with pytest.raises(
        ValueError,
        match="Missing tool confirmation, "
        "please make sure to either confirm or reject the tool execution before resuming the conversation.",
    ):
        execution_status = conversation.execute()


@pytest.fixture
def measure_room_temp_described_flow():
    measure_room_temp_tool = ClientTool(
        name="_inner_measure_room_temp",
        description="Return the value of the temperature in the room",
        parameters={},
    )
    tool_step = ToolExecutionStep(tool=measure_room_temp_tool)
    flow = Flow(
        begin_step=tool_step,
        steps={"execute_tool": tool_step},
        control_flow_edges=[ControlFlowEdge(source_step=tool_step, destination_step=None)],
    )
    described_flow = DescribedFlow(
        flow=flow,
        name="measure_room_temp",
        description="Return the value of the temperature in the room",
    )
    return described_flow


@retry_test(max_attempts=3, wait_between_tries=1)
def test_agent_returns_tool_request_status_when_using_client_tool_execution_step(
    remotely_hosted_llm: LlmModel,
    measure_room_temp_described_flow: DescribedFlow,
) -> None:
    """
    Failure rate:          0 out of 50
    Observed on:           2024-12-17
    Average success time:  1.14 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 0.7 / 100'000
    """
    agent = Agent(
        flows=[measure_room_temp_described_flow],
        llm=remotely_hosted_llm,
        custom_instruction="You are a helpful agent that has access to some tools.",
    )
    conversation = agent.start_conversation()
    conversation.append_user_message("What is the temperature in the room?")
    execution_status = conversation.execute()
    assert isinstance(execution_status, ToolRequestStatus)
    assert len(execution_status.tool_requests) == 1
    client_tool_request = execution_status.tool_requests[0]
    assert client_tool_request.name == "_inner_measure_room_temp"
    assert not client_tool_request.args  # because the tool has no arguments


def test_agent_raises_if_names_of_tools_agent_or_flows_overlap(
    remotely_hosted_llm: LlmModel,
    measure_room_temp_described_flow: DescribedFlow,
    measure_room_temp_tool: ClientTool,
) -> None:
    with pytest.raises(ValueError):
        Agent(
            tools=[measure_room_temp_tool],
            flows=[measure_room_temp_described_flow],
            llm=remotely_hosted_llm,
            custom_instruction="You are a helpful agent that has access to some tools.",
        )


def create_spuor_roowl_tools():
    spuor_tool = ClientTool(
        name="spuor_tool",
        description="Return the result of the spuor operation",
        parameters={
            "a": {"description": "Any number", "type": "number", "default": 0},
        },
    )
    roowl_tool = ClientTool(
        name="roowl_tool",
        description="Return the result of the roowl operation",
        parameters={
            "a": {"description": "Any number", "type": "number", "default": 0},
        },
    )
    return [spuor_tool, roowl_tool]


def run_test_agent_can_return_multiple_tool_requests(assistant: Union[Flow, Agent]):
    client_tools = {
        "roowl_tool": lambda a: a * a - 7,
        "spuor_tool": lambda a: 1 + 2 * a,
    }

    conversation = assistant.start_conversation()
    conversation.append_user_message(
        "I want to know the result of the roowl operation for a=5 and for a=6, and also the result of the spuor operation for a=7.  Tell me the three results at the same time."
    )
    execution_status = conversation.execute()
    assert isinstance(execution_status, ToolRequestStatus)
    assert len(execution_status.tool_requests) == 3
    for tool_request in execution_status.tool_requests:
        client_tool = client_tools[tool_request.name]
        client_tool_result = ToolResult(
            content=str(client_tool(**tool_request.args)),
            tool_request_id=tool_request.tool_request_id,
        )
        conversation.append_message(
            Message(
                message_type=MessageType.TOOL_RESULT,
                tool_result=client_tool_result,
            )
        )
    execution_status = conversation.execute()
    assert isinstance(execution_status, UserMessageRequestStatus)
    last_agent_message = conversation.get_last_message()

    assert "18" in last_agent_message.content  # roowl(a=5) == 18
    assert "29" in last_agent_message.content  # roowl(a=6) == 29
    assert "15" in last_agent_message.content  # spuor(a=7) == 15


@retry_test(max_attempts=4, wait_between_tries=1)
def test_agent_can_return_multiple_tool_requests(gpt_llm):
    """
    Failure rate:          0 out of 10
    Observed on:           2024-10-07
    Average success time:  7.80 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """

    agent = Agent(
        tools=create_spuor_roowl_tools(),
        llm=gpt_llm,
        custom_instruction="You are a helpful agent that has access to some tools.",
    )

    run_test_agent_can_return_multiple_tool_requests(agent)


# marked as integration test because it fails otherwise
# TODO investigate this
def test_agent_dummy_model(test_with_llm_fixture):
    human_question = "call some_tool with var=5"
    tool_result = "some result"
    rephrased_tool_output = "here is the result of some tool: some result"

    llm = DummyModel()
    llm.set_next_output(
        {
            human_question: Message(
                message_type=MessageType.TOOL_REQUEST,
                tool_requests=[
                    ToolRequest(name="some_tool", args={"var": 5}, tool_request_id="id1")
                ],
            ),
            tool_result: Message(message_type=MessageType.AGENT, content=rephrased_tool_output),
        }
    )

    @tool(description_mode="only_docstring")
    def some_tool(var: int) -> str:
        """Some tool description"""
        assert var == 5
        return tool_result

    agent = Agent(llm=llm, tools=[some_tool])

    conv = agent.start_conversation()

    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    assert conv.get_last_message().content == Agent.DEFAULT_INITIAL_MESSAGE

    conv.append_user_message(human_question)
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)

    messages = conv.get_messages()
    assert messages[-3].message_type == MessageType.TOOL_REQUEST
    assert messages[-2].tool_result == ToolResult(content=tool_result, tool_request_id="id1")
    assert messages[-1].content == rephrased_tool_output


@retry_test(max_attempts=3, wait_between_tries=1)
def test_agent_without_custom_instruction(remotely_hosted_llm):
    """
    Failure rate:          0 out of 40
    Observed on:           2025-01-10
    Average success time:  2.91 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 1.3 / 100'000
    """
    mock1, mock2, spluk_tool, gliif_tool = create_spluk_gliif_tools()

    agent = Agent(
        llm=remotely_hosted_llm,
        tools=[spluk_tool],
        max_iterations=3,
    )

    conv = agent.start_conversation()
    conv.append_user_message("What is the result of spluk of 2 and 3? ")
    status = conv.execute()
    response = conv.get_last_message().content
    assert "14" in response


@retry_test(max_attempts=3, wait_between_tries=1)
def test_agent_without_custom_instruction_openai(gpt_llm):
    """
    Failure rate:          0 out of 40
    Observed on:           2025-08-27
    Average success time:  2.79 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 1.3 / 100'000
    """
    mock1, mock2, spluk_tool, gliif_tool = create_spluk_gliif_tools()

    agent = Agent(
        llm=gpt_llm,
        tools=[spluk_tool],
        max_iterations=3,
    )

    conv = agent.start_conversation()
    conv.append_user_message("What is the result of spluk of 2 and 3? ")
    status = conv.execute()
    response = conv.get_last_message().content
    assert "14" in response


def run_initial_interaction_agent(agent: Agent) -> str:
    conv = agent.start_conversation()
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    assert conv.get_last_message().message_type == MessageType.AGENT
    return conv.get_last_message().content


def test_agent_uses_initial_message_default(remotely_hosted_llm):
    # will not generate, so not flaky
    agent = Agent(llm=remotely_hosted_llm)
    initial_message_content = run_initial_interaction_agent(agent)
    assert initial_message_content == Agent.DEFAULT_INITIAL_MESSAGE


@pytest.mark.parametrize(
    "initial_message", [Agent.DEFAULT_INITIAL_MESSAGE, "Hi, how are you doing today?"]
)
def test_agent_uses_initial_message(remotely_hosted_llm, initial_message):
    agent = Agent(llm=remotely_hosted_llm, initial_message=initial_message)
    initial_message_content = run_initial_interaction_agent(agent)
    assert initial_message_content == initial_message


def test_agent_can_generate_initial_message_if_custom_instruction(remotely_hosted_llm):
    # will not generate, so not flaky
    agent = Agent(
        llm=remotely_hosted_llm, custom_instruction="You are a helper agent.", initial_message=None
    )
    initial_message_content = run_initial_interaction_agent(agent)
    assert initial_message_content != Agent.DEFAULT_INITIAL_MESSAGE


def test_agent_cannot_generate_initial_message_without_custom_instructions(remotely_hosted_llm):
    with pytest.raises(ValueError):
        Agent(llm=remotely_hosted_llm, initial_message=None)


def test_agent_throws_if_required_inputs_are_not_passed(remotely_hosted_llm):
    with pytest.raises(ValueError):
        my_agent = Agent(
            llm=remotely_hosted_llm,
            custom_instruction="You are an agent named {{agent_name}}",
            initial_message=None,
        )
        my_agent.start_conversation()


def test_agent_with_context_provider_and_required_inputs_throws_if_inputs_are_missing(
    remotely_hosted_llm, what_time_is_it_context_provider
):
    my_agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="You are an agent named {{agent_name}}. Today's date and time is {{date_and_time}}",
        initial_message=None,
        context_providers=[what_time_is_it_context_provider],
    )
    with pytest.raises(ValueError):
        my_agent.start_conversation()


def test_agent_throws_if_requires_inputs_and_wrong_input_is_passed(remotely_hosted_llm):
    with pytest.raises(ValueError):
        my_agent = Agent(
            llm=remotely_hosted_llm,
            custom_instruction="You are an agent named {{agent_name}}",
            initial_message=None,
        )
        my_agent.start_conversation(inputs={"some_var": "hello"})


def test_agent_with_context_provider_and_required_inputs_successfully_conversation_with_required_inputs(
    remotely_hosted_llm, what_time_is_it_context_provider
):

    my_agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="You are an agent named {{agent_name}}. Today's date and time is {{date_and_time}}",
        initial_message=None,
        context_providers=[what_time_is_it_context_provider],
    )
    conversation = my_agent.start_conversation(inputs={"agent_name": "R0B0T"})
    assert conversation


@retry_test(max_attempts=3)
def test_agent_uses_inputs_if_passed(remotely_hosted_llm):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-01-24
    Average success time:  2.55 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    my_agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="You are an agent named {{agent_name}}",
        initial_message=None,
    )

    for name in ["Larry", "Jenny"]:
        conversation = my_agent.start_conversation(inputs={"agent_name": name})
        conversation.append_user_message("Please just tell me your name?")
        conversation.execute()
        last_message = conversation.get_last_message()
        assert last_message is not None
        assert name.lower() in last_message.content.lower()


def test_input_of_agents_are_casted_to_proper_type(remotely_hosted_llm):
    agent = Agent(llm=remotely_hosted_llm, custom_instruction="{{some_input}}")
    agent.start_conversation(inputs={"some_input": 7382783})


@retry_test(max_attempts=6)
@pytest.mark.parametrize(
    "user_question, expected_answer",
    [
        ("What is the result of the multiplication 13 x 4?", "52"),
        ("What is a regular polygon with 6 equal sides called?", "hexagon"),
        ("How much is a right angle in degrees?", "90"),
        ("What are all the countries around Switzerland?", "germany"),
    ],
)
def test_agent_without_tool_helpfully_answers_basic_questions_when_it_can_finish(
    remotely_hosted_llm, user_question, expected_answer
):
    """
    (Test case 1)
    Failure rate:          16 out of 100
    Observed on:           2025-02-25
    Average success time:  1.62 seconds per successful attempt
    Average failure time:  1.67 seconds per failed attempt
    Max attempt:           6
    Justification:         (0.17 ** 6) ~= 2.1 / 100'000

    (Test case 2)
    Failure rate:          0 out of 100
    Observed on:           2025-02-25
    Average success time:  1.58 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           2
    Justification:         (0.01 ** 2) ~= 9.6 / 100'000

    (Test case 3)
    Failure rate:          0 out of 100
    Observed on:           2025-02-25
    Average success time:  1.52 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           2
    Justification:         (0.01 ** 2) ~= 9.6 / 100'000

    (Test case 4)
    Failure rate:          2 out of 100
    Observed on:           2025-02-25
    Average success time:  1.52 seconds per successful attempt
    Average failure time:  1.61 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 2.5 / 100'000

    (Test case 5)
    Failure rate:          3 out of 100
    Observed on:           2025-02-25
    Average success time:  1.76 seconds per successful attempt
    Average failure time:  1.73 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 6.0 / 100'000
    """
    agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="Helpfully answer the user questions about maths and geography.",
        can_finish_conversation=True,
    )
    conversation = agent.start_conversation()
    conversation.append_user_message(user_question)
    conversation.execute()
    assert expected_answer in conversation.get_last_message().content.lower()


@retry_test(max_attempts=4)
def test_agent_with_multi_outputs_tool(remotely_hosted_llm):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-03-14
    Average success time:  2.84 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """

    @tool(output_descriptors=[StringProperty(name="name"), IntegerProperty(name="id")])
    def get_user_username() -> Dict[str, Union[str, int]]:
        """A tool returning several outputs"""
        return {"name": "larry", "id": 123}

    agent = Agent(
        llm=remotely_hosted_llm,
        tools=[get_user_username],
    )

    conversation = agent.start_conversation()
    conversation.append_user_message("what are my name and id?")
    status = conversation.execute()
    last_message_content = conversation.get_last_message().content.lower()
    assert "larry" in last_message_content
    assert "123" in last_message_content


@retry_test(max_attempts=3)
def test_agent_with_multi_outputs_tool_with_default(remotely_hosted_llm):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-04
    Average success time:  0.88 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """

    get_user_username = ClientTool(
        name="get_user_username",
        description="A tool returning several outputs",
        input_descriptors=[],
        output_descriptors=[
            StringProperty(name="name"),
            IntegerProperty(name="id", default_value=123),
        ],
    )

    agent = Agent(
        llm=remotely_hosted_llm,
        tools=[get_user_username],
    )

    conversation = agent.start_conversation()
    conversation.append_user_message("what are my name and id?")
    status = conversation.execute()
    assert isinstance(status, ToolRequestStatus)
    assert len(status.tool_requests) == 1
    conversation.append_tool_result(
        ToolResult(
            tool_request_id=status.tool_requests[0].tool_request_id, content={"name": "larry"}
        )
    )
    status = conversation.execute()
    last_message_content = conversation.get_last_message().content.lower()
    assert "larry" in last_message_content
    assert "123" in last_message_content


@retry_test(max_attempts=3)
def test_agent_given_tool_result_with_missing_output_raises(remotely_hosted_llm):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-04
    Average success time:  0.79 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """

    get_user_username = ClientTool(
        name="get_user_username",
        description="A tool returning several outputs",
        input_descriptors=[],
        output_descriptors=[
            StringProperty(name="name"),
            IntegerProperty(name="id", default_value=123),
        ],
    )

    agent = Agent(
        llm=remotely_hosted_llm,
        tools=[get_user_username],
    )

    conversation = agent.start_conversation()
    conversation.append_user_message("what are my name and id?")
    status = conversation.execute()
    assert isinstance(status, ToolRequestStatus)
    assert len(status.tool_requests) == 1
    conversation.append_tool_result(
        ToolResult(
            tool_request_id=status.tool_requests[0].tool_request_id, content={"wrong_key": "larry"}
        )
    )
    with pytest.raises(
        ValueError, match="The tool `get_user_username` did not return all expected outputs."
    ):
        _ = conversation.execute()


def test_agent_has_default_name(remotely_hosted_llm):
    agent = Agent(llm=remotely_hosted_llm)
    assert "agent_" in agent.name and len(agent.name) == 20
    assert agent.description == ""


def test_agent_name_and_description_can_be_changed(remotely_hosted_llm):
    agent = Agent(llm=remotely_hosted_llm, name="agent_1", description="description_1")
    assert agent.name == "agent_1"
    assert agent.description == "description_1"
    agent_2 = agent.clone(
        name="agent_2",
        description="description_2",
    )
    assert agent.name == "agent_1"
    assert agent.description == "description_1"
    assert agent_2.name == "agent_2"
    assert agent_2.description == "description_2"


def test_agent_raises_warning_when_sub_agent_description_is_empty(remotely_hosted_llm):
    with pytest.warns(Warning):
        agent = Agent(
            llm=remotely_hosted_llm, agents=[Agent(llm=remotely_hosted_llm, name="some_name")]
        )


def test_agent_raises_error_when_sub_agent_name_is_auto_generated(remotely_hosted_llm):
    with pytest.raises(ValueError):
        agent = Agent(llm=remotely_hosted_llm, agents=[Agent(llm=remotely_hosted_llm)])


def test_agent_raises_warning_when_sub_flow_description_is_empty(remotely_hosted_llm):
    with pytest.warns(Warning):
        agent = Agent(
            llm=remotely_hosted_llm,
            flows=[Flow.from_steps([OutputMessageStep("")], name="some_flow")],
        )


def test_agent_raises_error_when_sub_flow_name_is_auto_generated(remotely_hosted_llm):
    with pytest.raises(ValueError):
        agent = Agent(llm=remotely_hosted_llm, flows=[Flow.from_steps([OutputMessageStep("")])])


@tool(description_mode="only_docstring")
def search_hr_database(query: str) -> str:
    """Function that searches the HR database for employee benefits.

    Parameters
    ----------
    query:
        type of benefit to look up

    Returns
    -------
        a JSON response

    """
    return '{"benefits": "Unlimited PTO"}'


@retry_test(max_attempts=6)
def test_ocigenai_agent_can_use_tools(llama_oci_llm):
    """
    Failure rate:          3 out of 20
    Observed on:           2025-04-10
    Average success time:  2.46 seconds per successful attempt
    Average failure time:  2.33 seconds per failed attempt
    Max attempt:           6
    Justification:         (0.18 ** 6) ~= 3.6 / 100'000
    """
    HRASSISTANT_GENERATION_INSTRUCTIONS = dedent(
        """
        You are a knowledgeable, factual, and helpful HR assistant that can answer simple \
        HR-related questions like salary and benefits.
        You are given a tool to look up the HR database.
        Your task:
            - Ask the user if they need assistance
            - Use the provided tool below to retrieve HR data
            - Based on the data you retrieved, answer the user's question
        Important:
            - Be helpful and concise in your messages
            - Do not tell the user any details not mentioned in the tool response, let's be factual.
        """
    )

    agent = Agent(
        custom_instruction=HRASSISTANT_GENERATION_INSTRUCTIONS,
        tools=[search_hr_database],
        llm=llama_oci_llm,
        can_finish_conversation=True,
    )

    conv = agent.start_conversation()
    conv.append_user_message("Based on a query on the HR DB, how many vacation days do I have?")
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    tool_calls = [tc for m in conv.get_messages() for tc in (m.tool_requests or [])]
    assert len(tool_calls) == 1
    assert tool_calls[0].name == "search_hr_database"
    assert "unlimited" in conv.get_last_message().content.lower()


@retry_test(max_attempts=3)
def test_flow_as_tool_calling_with_user_response_inside_only_agent(agent_with_yielding_subflow):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-04-16
    Average success time:  2.95 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    Test that an agent correctly executes a yielding flow as a tool
    Verifies that:
    1. A TOOL_REQUEST is generated for weather queries
    2. Subsequent USER messages (windy) are properly processed
    3. The flow completes with expected output formatting
    """

    agent = agent_with_yielding_subflow
    conversation = agent.start_conversation()
    conversation.append_user_message("How is the weather in Morocco?")
    conversation.execute()
    conversation.append_user_message("windy")
    conversation.execute()

    messages = [m for m in conversation.get_messages() if m.message_type != MessageType.INTERNAL]

    assert messages[0].content == "How is the weather in Morocco?"
    assert messages[0].message_type == MessageType.USER

    assert messages[1].message_type == MessageType.TOOL_REQUEST

    assert messages[2].content == "What is the weather in Morocco"
    assert messages[2].message_type == MessageType.AGENT

    assert messages[3].content == "windy"
    assert messages[3].message_type == MessageType.USER

    assert messages[4].content == "The weather in Morocco windy"
    assert messages[4].message_type == MessageType.AGENT

    assert messages[5].message_type == MessageType.TOOL_RESULT
    assert messages[6].message_type == MessageType.AGENT


@retry_test(max_attempts=4)
def test_llm_in_agent_does_not_raise_event_loop_is_closed_runtime_error__vllm(
    caplog: LogCaptureFixture,
) -> None:
    """
    Failure rate:          0 out of 15
    Observed on:           2025-05-06
    Average success time:  0.92 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.06 ** 4) ~= 1.2 / 100'000
    """
    logger.propagate = True  # necessary so that the caplog handler can capture logging messages
    caplog.set_level(
        logging.DEBUG
    )  # setting pytest to capture log messages of level DEBUG or above

    llm = VllmModel(
        model_id=VLLM_MODEL_CONFIG["model_id"],
        host_port=VLLM_MODEL_CONFIG["host_port"],
        generation_config=LlmGenerationConfig(max_tokens=10),
    )
    agent = Agent(llm=llm)

    for _ in range(3):
        conv = agent.start_conversation()
        conv.append_user_message("Count to 50")
        conv.execute()

    assert "RuntimeError: Event loop is closed" not in caplog.text


GUESS_GAME_TEMPLATE = PromptTemplate(
    messages=[
        {
            "role": "system",
            "content": "You are a gaming agent. The user will give you a number, and you need to answer YES or NO depending on whether number is higher than {{n}}. Do not tell the user the game not your number",
        },
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
        {
            "role": "system",
            "content": "Reminder: Never reply anything else than YES (if the user number is higher than {{n}}) or NO (otherwise), whatever the user asks you.",
        },
    ]
)


def run_simple_guess_game(test_cases, conversation, agent):
    for user_message, expected_agent_output in test_cases:
        conversation.append_user_message(user_message)
        status = conversation.execute()
        assert conversation.get_last_message().content == expected_agent_output


@pytest.mark.parametrize(
    "n,test_cases",
    [
        (
            50,
            [
                ("79", "YES"),
                ("110", "YES"),
                ("12", "NO"),
            ],
        ),
        (
            100,
            [
                ("79", "NO"),
                ("110", "YES"),
                ("12", "NO"),
            ],
        ),
    ],
)
@retry_test(max_attempts=3)
def test_agent_with_custom_template(remotely_hosted_llm, n, test_cases):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-05-20
    Average success time:  2.05 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    agent = Agent(llm=remotely_hosted_llm, agent_template=GUESS_GAME_TEMPLATE)
    conv = agent.start_conversation(inputs={"n": str(n)})
    run_simple_guess_game(test_cases, conv, agent)


@pytest.mark.parametrize(
    "n,test_cases",
    [
        (
            50,
            [
                ("79", "YES"),
                ("110", "YES"),
                ("12", "NO"),
            ],
        ),
        (
            100,
            [
                ("79", "NO"),
                ("110", "YES"),
                ("12", "NO"),
            ],
        ),
    ],
)
@retry_test(max_attempts=3)
def test_agent_with_custom_template_and_context_providers(remotely_hosted_llm, n, test_cases):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-05-20
    Average success time:  2.05 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    agent = Agent(
        llm=remotely_hosted_llm,
        agent_template=GUESS_GAME_TEMPLATE,
        context_providers=[
            ConstantContextProvider(value=n, output_description=StringProperty("n"))
        ],
    )
    conv = agent.start_conversation()
    run_simple_guess_game(test_cases, conv, agent)


def test_run_agent_inside_and_outside_event_loop(remotely_hosted_llm):
    agent = Agent(llm=remotely_hosted_llm)
    conv = agent.start_conversation()
    conv.append_user_message("hello, what is your name")

    # outside event loop
    conv.execute()
    conv.append_user_message("my name is Damien")

    # inside event loop
    async def run_agent():
        conv.execute()

    with pytest.warns(
        UserWarning, match="You are calling an asynchronous method in a synchronous method"
    ):
        asyncio.run(run_agent())


def test_agent_doesnt_raise_warning_about_wrong_parsing_when_outputting_code(
    remotely_hosted_llm, caplog
):
    code = """right]

         while product >= k and left <= right:
             product //= nums[left]
             left += 1"""
    agent = Agent(llm=remotely_hosted_llm)
    conv = agent.start_conversation()
    conv.append_user_message("generate some code")

    with caplog.at_level(logging.WARNING):
        with patch_openai_compatible_llm(remotely_hosted_llm, code):
            conv.execute()

    assert len(caplog.records) == 0


def test_agent_raise_warning_about_wrong_parsing_when_outputting_wrongly_formatted_tool_call(
    remotely_hosted_llm, caplog
):
    with caplog.at_level(logging.WARNING):
        code = """{"name": "my_func", "param": {}}"""  # missing s at param
        agent = Agent(llm=remotely_hosted_llm)
        conv = agent.start_conversation()
        conv.append_user_message("generate a tool call")
        with patch_openai_compatible_llm(remotely_hosted_llm, code):
            conv.execute()

    assert len(caplog.records) == 1
    assert "Couldn't parse tool request" in caplog.text


def test_execute_agent_with_non_str_outputs(gpt_llm):
    @tool(description_mode="only_docstring")
    def generate_name() -> Dict[str, str]:
        """Generates a good name"""
        return {"good_name": "son"}

    agent = Agent(llm=gpt_llm, tools=[generate_name])

    conv = agent.start_conversation()
    conv.append_user_message("Generate a good name please")
    status = conv.execute()

    assert isinstance(status, UserMessageRequestStatus)


@retry_test(max_attempts=4)
def test_agent_handles_image_content_in_user_message(remote_gemma_llm: LlmModel):
    """
    Test that an agent can process a user message containing image content.
    The agent should acknowledge the image content in its response.

    Failure rate:          0 out of 10
    Observed on:           2025-07-11
    Average success time:  0.69 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    agent = Agent(
        llm=remote_gemma_llm,
        custom_instruction="You are a helpful agent capable of processing image content in messages. When an image is provided, acknowledge its content.",
    )

    conversation = agent.start_conversation()
    # Simulate a user message with image content
    image_path = Path(__file__).parent.parent / "configs/test_data/image.png"
    conversation.append_message(
        Message(
            contents=[
                ImageContent.from_bytes(bytes_content=Path(image_path).read_bytes(), format="png")
            ]
        )
    )

    # Execute the agent to process the message
    _ = conversation.execute()

    # Verify the agent processed the message correctly
    last_message = conversation.get_last_message()
    assert last_message.role == "assistant"
    result_string = last_message.content.lower()
    assert ("yellow" in result_string) or ("gold" in result_string)


def test_agent_works_with_two_mandatory_outputs(remotely_hosted_llm):
    agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="You can provide to the user a random number or a random word",
        output_descriptors=[
            IntegerProperty(name="a"),
            StringProperty(name="b"),
        ],
        caller_input_mode=CallerInputMode.NEVER,
        initial_message=None,
    )

    # 1. missing the random_word output
    # 2. missing the random_number output
    # 3. all outputs are present
    with patch_llm(
        llm=remotely_hosted_llm,
        outputs=[
            [ToolRequest(name=_SUBMIT_TOOL_NAME, args={"a": 1})],
            [ToolRequest(name=_SUBMIT_TOOL_NAME, args={"b": "word"})],
            [ToolRequest(name=_SUBMIT_TOOL_NAME, args={"b": "word", "a": 1})],
        ],
    ):
        conv = agent.start_conversation()
        status = conv.execute()
        assert isinstance(status, FinishedStatus)
        assert status.output_values == {"a": 1, "b": "word"}


def test_agent_works_with_one_mandatory_output_and_one_optional(remotely_hosted_llm):
    agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="You can provide to the user a random number or a random word",
        output_descriptors=[
            IntegerProperty(name="a"),
            StringProperty(name="b", default_value="nothing"),
        ],
        caller_input_mode=CallerInputMode.NEVER,
        initial_message=None,
    )

    # 1. missing an optional output, it's fine
    with patch_llm(
        llm=remotely_hosted_llm,
        outputs=[
            [ToolRequest(name=_SUBMIT_TOOL_NAME, args={"a": 1})],
        ],
    ):
        conv = agent.start_conversation()
        status = conv.execute()
        assert isinstance(status, FinishedStatus)
        assert status.output_values == {"a": 1, "b": "nothing"}

    # 2. missing a mandatory output, will re-ask
    with patch_llm(
        llm=remotely_hosted_llm,
        outputs=[
            [ToolRequest(name=_SUBMIT_TOOL_NAME, args={"b": "something"})],
            [ToolRequest(name=_SUBMIT_TOOL_NAME, args={"b": "something", "a": 1})],
        ],
    ):
        conv = agent.start_conversation()
        status = conv.execute()
        assert isinstance(status, FinishedStatus)
        assert status.output_values == {"a": 1, "b": "something"}


def test_agent_works_with_two_optional_outputs(remotely_hosted_llm):
    agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="You can provide to the user a random number or a random word",
        output_descriptors=[
            IntegerProperty(name="a", default_value=0),
            StringProperty(name="b", default_value="nothing"),
        ],
        caller_input_mode=CallerInputMode.NEVER,
        initial_message=None,
    )

    # 1. missing both optional output, we fill with defaults
    with patch_llm(
        llm=remotely_hosted_llm,
        outputs=[
            [ToolRequest(name=_SUBMIT_TOOL_NAME, args={})],
        ],
    ):
        conv = agent.start_conversation()
        status = conv.execute()
        assert isinstance(status, FinishedStatus)
        assert status.output_values == {"a": 0, "b": "nothing"}

    # 2. missing none optional output, it's fine
    with patch_llm(
        llm=remotely_hosted_llm,
        outputs=[
            [ToolRequest(name=_SUBMIT_TOOL_NAME, args={"a": 1, "b": "something"})],
        ],
    ):
        conv = agent.start_conversation()
        status = conv.execute()
        assert isinstance(status, FinishedStatus)
        assert status.output_values == {"a": 1, "b": "something"}


def test_can_continue_conversation_after_submitting_outputs(remotely_hosted_llm):
    agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="return an answer",
        initial_message=None,
    )
    flow = Flow.from_steps(
        steps=[
            AgentExecutionStep(
                agent=agent,
                output_descriptors=[StringProperty(name="answer")],
            ),
            InputMessageStep(""),
            AgentExecutionStep(
                agent=agent,
            ),
        ]
    )
    conversation = flow.start_conversation()
    with patch_openai_compatible_llm(
        llm=remotely_hosted_llm, txt='{"name": "submit_result", "parameters": {"answer": "hello"}}'
    ):
        conversation.execute()
    conversation.append_user_message("")
    with patch_openai_compatible_llm(llm=remotely_hosted_llm, txt="hello"):
        conversation.execute()


def test_agent_with_cohere(cohere_llm):
    agent = Agent(
        llm=cohere_llm,
    )
    conv = agent.start_conversation()
    conv.execute()
    conv.append_user_message("my wifi is not working")
    conv.execute()
    assert len(conv.get_messages()) == 3


@pytest.mark.anyio
async def test_agent_can_run_async(remotely_hosted_llm):
    agent = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="who is the CEO of Oracle?",
        initial_message=None,
    )
    conversation = agent.start_conversation()
    status = await conversation.execute_async()
    assert isinstance(status, UserMessageRequestStatus)


def test_error_on_caller_input_mode_never_with_initial_message(big_llama):
    with pytest.raises(
        ValueError, match="The caller input mode for the agent is set to `CallerInputMode.NEVER`"
    ):
        Agent(
            llm=big_llama,
            caller_input_mode=CallerInputMode.NEVER,
            initial_message="Hi, what's your name?",
        )


def _get_haiku_tool(
    submitted_haikus: List[str],
    success_message: str = "Haiku Submitted Successfully.",
):
    @tool(description_mode="only_docstring")
    def submit_haiku(haiku: str) -> str:
        """Submit your haiku.

        Parameters
        ----------
        haiku :
            the full haiku (all three verses of it)

        Returns
        -------
        A status code
        """
        submitted_haikus.append(haiku)
        return success_message

    return submit_haiku


@retry_test(max_attempts=3)
@pytest.mark.parametrize("can_finish_conversation", [True])
def test_caller_input_mode_never(big_llama, can_finish_conversation):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-07-28
    Average success time:  4.20 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """

    submitted_haikus = []

    agent = Agent(
        llm=big_llama,
        tools=[_get_haiku_tool(submitted_haikus)],
        caller_input_mode=CallerInputMode.NEVER,
        custom_instruction="You are a helpful assistant, who always uses the appropriate tool to submit a single Haiku, and then finishes the conversation.",
        initial_message=None,
        can_finish_conversation=can_finish_conversation,
        max_iterations=5,
    )

    conv = agent.start_conversation()
    conv.execute()
    assert len(submitted_haikus) == 1


@retry_test(max_attempts=3)
@pytest.mark.parametrize("can_finish_conversation", [True, False])
def test_caller_input_mode_never_with_agent_template(big_llama, can_finish_conversation):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-07-28
    Average success time:  4.20 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    submitted_haikus = []

    agent = Agent(
        llm=big_llama,
        tools=[_get_haiku_tool(submitted_haikus)],
        caller_input_mode=CallerInputMode.NEVER,
        initial_message=None,
        custom_instruction="You are a helpful assistant, who always uses the appropriate tool to submit a single Haiku, and then finishes the conversation.",
        agent_template=PromptTemplate(
            messages=[
                Message("{{user_input}}", MessageType.USER),
                PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
            ],
        ),
        output_descriptors=[
            BooleanProperty(
                "haiku_submitted",
                description="true if the haiku was successfully submitted",
                default_value=False,
            )
        ],
        can_finish_conversation=can_finish_conversation,
        max_iterations=5,
    )

    conv = agent.start_conversation(inputs={"user_input": "I want my haiku to be about trees"})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values["haiku_submitted"]
    assert len(submitted_haikus) == 1


@retry_test(max_attempts=3)
def test_caller_input_mode_never_with_single_iteration(big_llama):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-07-28
    Average success time:  0.87 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    submitted_haikus = []

    with pytest.warns(
        UserWarning, match="Maximum number of iterations is set to one for the Agent.*"
    ):
        agent = Agent(
            llm=big_llama,
            tools=[_get_haiku_tool(submitted_haikus)],
            caller_input_mode=CallerInputMode.NEVER,
            custom_instruction="You are a helpful assistant, who always uses the appropriate tool to submit a single Haiku, and then finishes the conversation.",
            output_descriptors=[
                BooleanProperty(
                    "haiku_submitted", "true if the haiku was submitted", default_value=False
                )
            ],
            initial_message=None,
            can_finish_conversation=False,
            max_iterations=1,
        )

    conv = agent.start_conversation()
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert not status.output_values["haiku_submitted"]


@retry_test(max_attempts=3)
def test_agent_with_default_input_values_works(big_llama):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-11-19
    Average success time:  2.81 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    agent = Agent(
        llm=big_llama,
        custom_instruction="You are a helpful agent. Here's what you know: {{context}}. Answer the user `{{username}}`.",
        input_descriptors=[
            StringProperty(name="context", default_value="Videogames"),
            StringProperty(name="username"),
        ],
    )
    conv = agent.start_conversation({"username": "john"})
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    status.submit_user_response("Who is the user?")
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    last_message = status.message
    assert "john" in last_message.content.lower()
    status.submit_user_response("What do you know?")
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    last_message = status.message
    assert "videogame" in last_message.content.lower()


def test_agent_with_missing_input_values_raises(big_llama):
    agent = Agent(
        llm=big_llama,
        custom_instruction="You are a helpful agent. Here's what you know: {{context}}. But also {{additional_context}}. Answer the user.",
        input_descriptors=[
            StringProperty(name="context", default_value="Videogames"),
            StringProperty(name="additional_context"),
        ],
    )
    with pytest.raises(
        ValueError,
        match=r"Agent requires inputs \(`\['additional_context'\]`\), but you did not pass any.",
    ):
        _ = agent.start_conversation()
    with pytest.raises(
        ValueError,
        match="The agent requires an input `additional_context`, but it was not passed in the input dictionary",
    ):
        _ = agent.start_conversation({})


def test_agent_template_with_no_custom_instructions(big_llama):
    agent = Agent(
        llm=big_llama,
        initial_message=None,
        custom_instruction=None,
        agent_template=PromptTemplate(
            messages=[Message("Hi, how can I help you?")],
        ),
    )

    conv = agent.start_conversation()
    conversation_length_before = len(conv.get_messages())
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    assert len(conv.get_messages()) == conversation_length_before + 1


@tool
def success_tool() -> str:
    """some tool"""
    return "Success tool completed."


@tool
def failing_tool() -> str:
    """some tool"""
    raise RuntimeError("Simulated tool failure - this tool intentionally fails")


def _check_each_tool_request_is_followed_by_single_matching_tool_result(
    messages: List[Message],
) -> None:
    call_ids = set()
    for message in messages:
        if message.tool_requests:
            for tr in message.tool_requests:
                tr_id = tr.tool_request_id
                assert tr_id not in call_ids
                call_ids.add(tr_id)
        if message.tool_result:
            call_ids.remove(message.tool_result.tool_request_id)


def test_exception_during_parallel_tool_calls(remotely_hosted_llm):
    agent = Agent(
        tools=[success_tool, failing_tool],
        llm=remotely_hosted_llm,
        custom_instruction="some instructions",
        can_finish_conversation=False,
        max_iterations=40,
        raise_exceptions=True,  # need to raise exceptions
    )

    conversation = agent.start_conversation(messages="do something")

    with pytest.raises(
        RuntimeError, match="Simulated tool failure - this tool intentionally fails"
    ):
        with patch_llm(
            remotely_hosted_llm,
            outputs=[
                [
                    ToolRequest(name="success_tool", args={}, tool_request_id="id1"),
                    ToolRequest(name="success_tool", args={}, tool_request_id="id2"),
                    ToolRequest(name="failing_tool", args={}, tool_request_id="id3"),
                    ToolRequest(name="failing_tool", args={}, tool_request_id="id4"),
                    ToolRequest(name="success_tool", args={}, tool_request_id="id5"),
                ]
            ],
        ):
            status = conversation.execute()

    _check_each_tool_request_is_followed_by_single_matching_tool_result(conversation.get_messages())

    with patch_llm(
        remotely_hosted_llm,
        outputs=[
            [
                ToolRequest(name="success_tool", args={}, tool_request_id="id7"),
                ToolRequest(name="success_tool", args={}, tool_request_id="id8"),
            ],
            "done",
        ],
    ):
        status = conversation.execute()

    _check_each_tool_request_is_followed_by_single_matching_tool_result(conversation.get_messages())


def test_exception_during_parallel_tool_calls_with_agent(remotely_hosted_llm):
    sub_agent = Agent(
        llm=remotely_hosted_llm,
        tools=[success_tool, failing_tool],
        name="sub_agent",
        description="some description",
        raise_exceptions=True,
    )
    sub_agent.start_conversation(messages="do something")
    agent = Agent(
        agents=[sub_agent],
        llm=remotely_hosted_llm,
        custom_instruction="some instructions",
        can_finish_conversation=False,
        max_iterations=40,
        raise_exceptions=True,  # need to raise exceptions
    )

    conversation = agent.start_conversation(messages="do something")

    with pytest.raises(
        RuntimeError, match="Simulated tool failure - this tool intentionally fails"
    ):
        with patch_llm(
            remotely_hosted_llm,
            outputs=[
                [ToolRequest(name="sub_agent", args={"context": ""}, tool_request_id="id100")],
                [
                    ToolRequest(name="failing_tool", args={}, tool_request_id="id3"),
                ],
            ],
        ):
            status = conversation.execute()

    _check_each_tool_request_is_followed_by_single_matching_tool_result(conversation.get_messages())

    with patch_llm(remotely_hosted_llm, outputs=["done"]):
        status = conversation.execute()

    _check_each_tool_request_is_followed_by_single_matching_tool_result(conversation.get_messages())


def test_exception_during_parallel_tool_calls_with_flow(remotely_hosted_llm):
    sub_flow = Flow.from_steps(
        steps=[ToolExecutionStep(tool=failing_tool, raise_exceptions=True)],
        name="sub_flow",
        description="some description",
    )
    agent = Agent(
        flows=[sub_flow],
        llm=remotely_hosted_llm,
        custom_instruction="some instructions",
        can_finish_conversation=False,
        max_iterations=40,
        raise_exceptions=True,  # need to raise exceptions
    )

    conversation = agent.start_conversation(messages="do something")

    with pytest.raises(
        RuntimeError, match="Simulated tool failure - this tool intentionally fails"
    ):
        with patch_llm(
            remotely_hosted_llm,
            outputs=[
                [ToolRequest(name="sub_flow", args={}, tool_request_id="id100")],
                [
                    ToolRequest(name="failing_tool", args={}, tool_request_id="id3"),
                ],
            ],
        ):
            status = conversation.execute()

    _check_each_tool_request_is_followed_by_single_matching_tool_result(conversation.get_messages())

    with patch_llm(remotely_hosted_llm, outputs=["done"]):
        status = conversation.execute()

    _check_each_tool_request_is_followed_by_single_matching_tool_result(conversation.get_messages())


def test_agent_does_not_loop_until_max_iterations(remotely_hosted_llm):
    # when caller_input_mode == NEVER, can_finish_conversation=False and no outputs,
    # the agent does not have the exit conversation nor the submit tool
    # we still need it to be able to exit
    agent = Agent(
        llm=remotely_hosted_llm,
        can_finish_conversation=False,
        caller_input_mode=CallerInputMode.NEVER,
        custom_instruction="do something",
    )
    conv = agent.start_conversation()
    status = conv.execute()
    # it should not have exited because of max_iter
    assert conv.state.curr_iter != agent.max_iterations
