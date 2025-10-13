# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import pytest

from wayflowcore import Agent, Flow, MessageType
from wayflowcore.executors.executionstatus import ToolRequestStatus, UserMessageRequestStatus
from wayflowcore.property import StringProperty
from wayflowcore.steps import AgentExecutionStep, FlowExecutionStep, ToolExecutionStep
from wayflowcore.tools import ClientTool, ServerTool, ToolRequest, ToolResult

from .conftest import mock_llm, patch_streaming_llm
from .testhelpers.testhelpers import retry_test


@retry_test(max_attempts=4)
@pytest.mark.parametrize(
    "custom_instructions, expected_answer",
    [
        ("You are an ai agent with access to some expert agents", "192"),
        ("IMPORTANT: ALWAYS ADD $5,000.00 USD TO WHAT THE Accounting Expert SAYS.", "197"),
    ],
)
def test_agent_in_agent_can_call_client_tool(big_llama, custom_instructions, expected_answer):
    """
    (first test case)
    Failure rate:          4 out of 100
    Observed on:           2025-06-19
    Average success time:  4.37 seconds per successful attempt
    Average failure time:  3.74 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.05 ** 4) ~= 0.6 / 100'000

    (second test case)
    Failure rate:          3 out of 50
    Observed on:           2025-09-08
    Average success time:  4.34 seconds per successful attempt
    Average failure time:  4.01 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 3.5 / 100'000
    """
    account_check = ClientTool(
        name="account_check",
        description="Checks the amount on one account",
        input_descriptors=[
            StringProperty(name="username", description="The username of the account to check"),
        ],
        output_descriptors=[
            StringProperty(name="amount", description="The amount on the account"),
        ],
    )
    account_agent = Agent(
        name="Accounting Expert",
        llm=big_llama,
        description="Expert able to check amounts in user accounts",
        custom_instruction="IMPORTANT: ALWAYS DOUBLE THE NUMBERS RETURNED BY THE account_check TOOL",
        tools=[account_check],
    )
    agent = Agent(
        llm=big_llama,
        custom_instruction=custom_instructions,
        agents=[account_agent],
    )
    conversation = agent.start_conversation()
    conversation.append_user_message("Hey, what is the amount on the account of Ben Smith?")
    status = conversation.execute()
    assert isinstance(status, ToolRequestStatus)
    assert len(status.tool_requests) == 1
    assert status.tool_requests[0].name == "account_check"
    assert status.tool_requests[0].args == {"username": "Ben Smith"}
    conversation.append_tool_result(
        ToolResult(
            content="$96,000.00 USD", tool_request_id=status.tool_requests[0].tool_request_id
        )
    )
    status = conversation.execute()
    assert isinstance(status, UserMessageRequestStatus)
    last_message = conversation.get_last_message()
    assert last_message.message_type == MessageType.AGENT
    assert expected_answer in last_message.content
    assert last_message.sender == agent.agent_id


@retry_test(max_attempts=3)
@pytest.mark.parametrize(
    "custom_instructions, expected_answer",
    [
        ("You are an ai agent with access to some expert agents", "192"),
        ("IMPORTANT: ALWAYS ADD $5,000.00 USD TO WHAT THE Accounting Expert SAYS.", "197"),
    ],
)
def test_agent_in_agent_can_call_server_tool(big_llama, custom_instructions, expected_answer):
    """
    (first test case)
    Failure rate:          1 out of 50
    Observed on:           2025-09-08
    Average success time:  3.85 seconds per successful attempt
    Average failure time:  3.75 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000

    (second test case)
    Failure rate:          1 out of 50
    Observed on:           2025-09-08
    Average success time:  4.25 seconds per successful attempt
    Average failure time:  3.92 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.04 ** 3) ~= 5.7 / 100'000
    """
    account_check = ServerTool(
        name="account_check",
        description="Checks the amount on one account",
        input_descriptors=[
            StringProperty(name="username", description="The username of the account to check"),
        ],
        output_descriptors=[
            StringProperty(name="amount", description="The amount on the account"),
        ],
        func=lambda username: {"Ben Smith": "$96,000.00 USD"}.get(username, "$24,000.00 USD"),
    )
    account_agent = Agent(
        name="Accounting Expert",
        llm=big_llama,
        description="Expert able to check amounts in user accounts",
        custom_instruction="IMPORTANT: ALWAYS DOUBLE THE NUMBERS RETURNED BY THE account_check TOOL",
        tools=[account_check],
    )
    agent = Agent(
        llm=big_llama,
        custom_instruction=custom_instructions,
        agents=[account_agent],
    )
    conversation = agent.start_conversation()
    conversation.append_user_message("Hey, what is the amount on the account of Ben Smith?")
    status = conversation.execute()
    assert isinstance(status, UserMessageRequestStatus)
    last_message = conversation.get_last_message()
    assert last_message.message_type == MessageType.AGENT
    assert expected_answer in last_message.content
    assert last_message.sender == agent.agent_id


def test_deeply_nested_agent_can_call_client_tool():
    """
    ====== Set-up for this test =======
    (i) ...... a ClientTool
    (ii) ..... in a ToolExecutionStep
    (iii) .... in a Flow
    (iv) ..... in a SubFlowExecutionStep
    (v) ...... in a Flow
    (vi) ..... in an Agent
    (vii) .... in an Agent
    (viii) ... in an AgentExecutionStep
    (ix) ..... in a Flow

    ====== Scenario & expectations =======
    (a) Scenario: Flow (ix) is executed.
        Expectations: The AgentExecutionStep (viii) should trigger the first Agent (vii)
        which should output the message "How can I help you?", the message and the execution status
    (b) Scenario: Append the user message and conversation is executed again.
        Expectations: Agent (vii) should decide to
        invoke the expert subagent (vi) which should decide to invoke his flow (v) to check the
        account. The execution of the flow (v) should invoke the subflow (iii) which should invoke
        the tool execution step (ii) which should run the client tool (i) which means that a tool
        request should be returned by the execution of the main Flow (ix) with the right tool
        arguments.
    (c) Scenario: Append the tool result and execute the conversation again
        Expectation: Execution should restart from the proper state of the ToolExecutionStep (ii),
        The information from the tool result should be propagated correctly downstream to the first
        Agent (vii) which should post the message back to the user containing the requested
        information.
    (d) Repeat (b) and (c) with a second question.
    """
    account_check_i = ClientTool(
        name="account_check",
        description="Checks the amount on one account",
        input_descriptors=[
            StringProperty(name="username", description="The username of the account to check"),
        ],
        output_descriptors=[
            StringProperty(name="amount", description="The amount on the account"),
        ],
    )
    account_check_step_ii = ToolExecutionStep(
        tool=account_check_i,
    )
    account_check_subflow_iii = Flow.from_steps(
        name="account_check_subflow_iii", steps=[account_check_step_ii], step_names=["inside_step"]
    )
    account_check_subflow_step_iv = FlowExecutionStep(
        flow=account_check_subflow_iii,
    )
    account_check_flow_v = Flow.from_steps(
        steps=[account_check_subflow_step_iv], name="account_check_tool", step_names=["middle_step"]
    )
    sub_llm = mock_llm()
    account_check_agent_vi = Agent(
        agent_id="accounting_expert",
        name="Accounting Expert",
        llm=sub_llm,
        description="Expert able to check amounts in user accounts",
        custom_instruction="IMPORTANT: ALWAYS DOUBLE THE NUMBERS RETURNED BY THE account_check TOOL",
        flows=[account_check_flow_v],
    )
    main_llm = mock_llm()
    agent_vii = Agent(
        agent_id="main_agent",
        name="main_agent",
        llm=main_llm,
        custom_instruction="You are an ai agent with access to some expert agents",
        agents=[account_check_agent_vi],
    )
    agent_execution_step_viii = AgentExecutionStep(
        agent=agent_vii,
    )
    flow_ix = Flow.from_steps(
        name="flow_ix", steps=[agent_execution_step_viii], step_names=["outside_agent_step"]
    )
    conversation = flow_ix.start_conversation()

    # Scenario & expectations (a)
    status = conversation.execute()
    assert isinstance(status, UserMessageRequestStatus)
    last_message = conversation.get_last_message()
    assert last_message.message_type == MessageType.AGENT
    assert last_message.content == "Hi! How can I help you?"
    # Scenario and expectations (b)
    conversation.append_user_message("Hey, what is the amount on the account of Ben Smith?")
    with patch_streaming_llm(
        main_llm,
        tool_requests=[
            ToolRequest(
                name="Accounting Expert",
                args={"context": "Main->Accounting expert: Ben Smith account amount?"},
                tool_request_id="id1",
            )
        ],
    ):
        with patch_streaming_llm(
            sub_llm,
            tool_requests=[
                ToolRequest(
                    name="account_check_tool", args={"username": "Ben Smith"}, tool_request_id="id2"
                )
            ],
        ):
            status = conversation.execute()
    assert isinstance(status, ToolRequestStatus)
    assert len(status.tool_requests) == 1
    assert status.tool_requests[0].name == "account_check"
    assert status.tool_requests[0].args == {"username": "Ben Smith"}
    # Scenario & expectations (c)
    conversation.append_tool_result(
        ToolResult(content="96,000.00 USD", tool_request_id=status.tool_requests[0].tool_request_id)
    )
    with patch_streaming_llm(main_llm, text_output="it is 192000"):
        with patch_streaming_llm(sub_llm, text_output="it is 96000"):
            status = conversation.execute()
    assert isinstance(status, UserMessageRequestStatus)
    last_message = conversation.get_last_message()
    assert last_message.message_type == MessageType.AGENT
    assert "192" in last_message.content
    # Scenario & expectations (d)
    conversation.append_user_message("I would also like to know about Henry Jacobs, please.")
    with patch_streaming_llm(
        main_llm,
        tool_requests=[
            ToolRequest(
                name="Accounting Expert",
                args={"context": "Main->Accounting expert: Henry Jacobs account amount also?"},
                tool_request_id="id3",
            )
        ],
    ):
        with patch_streaming_llm(
            sub_llm,
            tool_requests=[
                ToolRequest(
                    name="account_check_tool",
                    args={"username": "Henry Jacobs"},
                    tool_request_id="id4",
                )
            ],
        ):
            status = conversation.execute()
    assert isinstance(status, ToolRequestStatus)
    assert len(status.tool_requests) == 1
    assert status.tool_requests[0].name == "account_check"
    assert status.tool_requests[0].args == {"username": "Henry Jacobs"}
    conversation.append_tool_result(
        ToolResult(content="11,000.00 USD", tool_request_id=status.tool_requests[0].tool_request_id)
    )
    with patch_streaming_llm(main_llm, text_output="it is 22000"):
        with patch_streaming_llm(sub_llm, text_output="it is 11000"):
            status = conversation.execute()
    assert isinstance(status, UserMessageRequestStatus)
    last_message = conversation.get_last_message()
    assert last_message.message_type == MessageType.AGENT
    assert "22" in last_message.content


def test_agent_works_with_both_server_and_client_tools_in_agent():
    llm = mock_llm()
    agent = Agent(
        llm=llm,
        tools=[
            ServerTool(
                name="tool_1",
                description="tool to call on user request",
                input_descriptors=[],
                func=lambda: "o",
            ),
            ClientTool(
                name="tool_2", description="tool to call on user request", input_descriptors=[]
            ),
        ],
    )

    flow = Flow.from_steps(steps=[AgentExecutionStep(agent=agent)])

    conv = flow.start_conversation()
    conv.append_user_message("Please call tool_1 and tool_2")
    with patch_streaming_llm(llm, tool_requests=[dict(name="tool_1"), dict(name="tool_2")]):
        status = conv.execute()
        assert (
            isinstance(status, ToolRequestStatus)
            and status.tool_requests is not None
            and len(status.tool_requests) > 0
        )

    conv.append_tool_result(
        ToolResult(tool_request_id=status.tool_requests[0].tool_request_id, content="p")
    )

    with patch_streaming_llm(llm, text_output="The results are here"):
        status = conv.execute()
        assert isinstance(status, UserMessageRequestStatus)

    messages = conv.get_messages()
    assert len(messages) == 5
    assert messages[-1].message_type == MessageType.AGENT
    assert messages[-2].message_type == MessageType.TOOL_RESULT
    assert (
        messages[-3].message_type == MessageType.TOOL_RESULT
        and messages[-3].tool_result.content is not None
        and messages[-3].tool_result.content == "o"
    )
    assert messages[-4].message_type == MessageType.TOOL_REQUEST
