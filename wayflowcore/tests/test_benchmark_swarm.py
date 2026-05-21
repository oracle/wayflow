# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Optional

import pytest

from wayflowcore.agent import CallerInputMode
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.models import LlmModel
from wayflowcore.property import IntegerProperty
from wayflowcore.swarm import HandoffMode, Swarm
from wayflowcore.templates import PromptTemplate
from wayflowcore.templates._swarmtemplate import (
    _DEFAULT_SWARM_CHAT_TEMPLATE,
    _DEFAULT_SWARM_NATIVE_CHAT_TEMPLATE,
)

from .test_swarm import (
    _get_bwip_agent,
    _get_fooza_agent,
    _get_zbuk_agent,
    bwip_tool,
    fooza_tool,
    get_debugger_agent,
    get_first_agent,
    get_fixer_agent,
    zbuk_tool,
)
from .testhelpers.testhelpers import retry_test


@pytest.fixture(
    params=[_DEFAULT_SWARM_CHAT_TEMPLATE, _DEFAULT_SWARM_NATIVE_CHAT_TEMPLATE],
    ids=["old_template", "native_tool_calling_template"],
)
def swarm_template(request: pytest.FixtureRequest) -> Optional[PromptTemplate]:
    return request.param


def _get_math_swarm(
    llm: LlmModel, handoff: HandoffMode, swarm_template: Optional[PromptTemplate]
) -> Swarm:
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)
    fooza_agent = _get_fooza_agent(llm)
    all_agents = (bwip_agent, zbuk_agent, fooza_agent)
    return Swarm(
        first_agent=fooza_agent,
        relationships=[(ag1, ag2) for ag1 in all_agents for ag2 in all_agents if ag1 is not ag2],
        handoff=handoff,
        swarm_template=swarm_template,
    )


@retry_test(max_attempts=3)
@pytest.mark.parametrize(
    argnames="handoff",
    argvalues=[HandoffMode.NEVER, HandoffMode.OPTIONAL],
    ids=["no_handoff", "with_handoff"],
)
def test_benchmark_swarm_can_complete_task_without_specialist(
    vllm_responses_llm: LlmModel,
    swarm_template: Optional[PromptTemplate],
    handoff: HandoffMode,
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.33 ** 3) ~= 3703.7 / 100'000
    """
    math_swarm = _get_math_swarm(vllm_responses_llm, handoff, swarm_template)
    conv = math_swarm.start_conversation()
    conv.append_user_message("compute the result the fooza operation of 4 and 5")
    conv.execute()

    last_message = conv.get_last_message()
    assert last_message is not None
    assert "22" in last_message.content


@retry_test(max_attempts=3)
@pytest.mark.parametrize(
    argnames="handoff",
    argvalues=[HandoffMode.NEVER, HandoffMode.OPTIONAL],
    ids=["no_handoff", "with_handoff"],
)
def test_benchmark_swarm_can_complete_routing_task(
    vllm_responses_llm: LlmModel,
    swarm_template: Optional[PromptTemplate],
    handoff: HandoffMode,
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.33 ** 3) ~= 3703.7 / 100'000
    """
    math_swarm = _get_math_swarm(vllm_responses_llm, handoff, swarm_template)
    conv = math_swarm.start_conversation()
    conv.append_user_message("compute the result the zbuk operation of 4 and 5")
    conv.execute()

    last_message = conv.get_last_message()
    assert last_message is not None
    assert "14" in last_message.content


@retry_test(max_attempts=5)
@pytest.mark.parametrize(
    argnames="handoff",
    argvalues=[HandoffMode.NEVER, HandoffMode.OPTIONAL],
    ids=["no_handoff", "with_handoff"],
)
def test_benchmark_swarm_can_complete_composition_task(
    vllm_responses_llm: LlmModel,
    swarm_template: Optional[PromptTemplate],
    handoff: HandoffMode,
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           5
    Justification:         (0.33 ** 5) ~= 411.5 / 100'000
    """
    math_swarm = _get_math_swarm(vllm_responses_llm, handoff, swarm_template)
    conv = math_swarm.start_conversation()
    conv.append_user_message("compute the result of the bwip(4, zbuk(5, 6))")
    conv.execute()

    last_message = conv.get_last_message()
    assert last_message is not None
    assert "-12" in last_message.content


@retry_test(max_attempts=6)
def test_benchmark_swarm_uses_handoff_tool_in_always_handoff_mode(
    vllm_responses_llm: LlmModel,
    swarm_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           6
    Justification:         (0.33 ** 6) ~= 137.2 / 100'000
    """
    main_agent = get_first_agent(vllm_responses_llm)
    debugger_agent = get_debugger_agent(vllm_responses_llm)
    fixer_agent = get_fixer_agent(vllm_responses_llm)

    swarm = Swarm(
        first_agent=main_agent,
        relationships=[
            (main_agent, debugger_agent),
            (debugger_agent, main_agent),
            (main_agent, fixer_agent),
            (fixer_agent, main_agent),
            (debugger_agent, fixer_agent),
        ],
        handoff=HandoffMode.ALWAYS,
        swarm_template=swarm_template,
    )

    conv = swarm.start_conversation(
        messages="Do we have any bugs on the `amazon` product? If yes, fix them."
    )
    conv.execute()

    expected_tool_requests = [
        ("handoff_conversation", {"recipient": "debugger_agent"}),
        ("get_bug", {}),
        ("handoff_conversation", {"recipient": "fixer_agent"}),
        ("fix_bug", {}),
    ]
    all_tool_requests = [
        tq for message in conv.get_messages() for tq in (message.tool_requests or [])
    ]

    assert len(all_tool_requests) > 0

    for tool_request, (expected_tool_name, expected_params) in zip(
        all_tool_requests,
        expected_tool_requests,
        strict=False,
    ):
        assert tool_request.name == expected_tool_name
        for k, v in expected_params.items():
            assert tool_request.args[k] == v


@retry_test(max_attempts=3)
def test_benchmark_swarm_uses_handoff_tool_when_sub_agent_can_take_over(
    vllm_responses_llm: LlmModel,
    swarm_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.33 ** 3) ~= 3703.7 / 100'000
    """
    main_agent = get_first_agent(vllm_responses_llm)
    debugger_agent = get_debugger_agent(vllm_responses_llm)
    swarm = Swarm(
        first_agent=main_agent,
        relationships=[
            (main_agent, debugger_agent),
            (debugger_agent, main_agent),
        ],
        handoff=HandoffMode.ALWAYS,
        swarm_template=swarm_template,
    )

    conv = swarm.start_conversation(messages="Do we have any bugs on the `amazon` product?")
    conv.execute()

    expected_tool_requests = [
        ("handoff_conversation", {"recipient": "debugger_agent"}),
        ("get_bug", {}),
    ]
    all_tool_requests = [
        tq for message in conv.get_messages() for tq in (message.tool_requests or [])
    ]
    for tool_request, (expected_tool_name, expected_params) in zip(
        all_tool_requests, expected_tool_requests, strict=True
    ):
        assert tool_request.name == expected_tool_name
        for k, v in expected_params.items():
            assert tool_request.args[k] == v


@retry_test(max_attempts=6)
def test_benchmark_swarm_uses_send_message_when_collaboration_needed(
    vllm_responses_llm: LlmModel,
    swarm_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           6
    Justification:         (0.33 ** 6) ~= 137.2 / 100'000
    """
    main_agent = get_first_agent(vllm_responses_llm)
    debugger_agent = get_debugger_agent(vllm_responses_llm)
    fixer_agent = get_fixer_agent(vllm_responses_llm)

    swarm = Swarm(
        first_agent=main_agent,
        relationships=[
            (main_agent, debugger_agent),
            (debugger_agent, main_agent),
            (main_agent, fixer_agent),
            (fixer_agent, main_agent),
            (debugger_agent, fixer_agent),
        ],
        handoff=HandoffMode.OPTIONAL,
        swarm_template=swarm_template,
    )

    conv = swarm.start_conversation(
        messages="Do we have any bugs on the `amazon` product? If yes, fix them."
    )
    conv.execute()

    expected_tool_requests = [
        ("send_message", {"recipient": "debugger_agent"}),
        ("send_message", {"recipient": "fixer_agent"}),
    ]

    all_tool_requests = [
        tq for message in conv.get_messages() for tq in (message.tool_requests or [])
    ]
    for tool_request, (expected_tool_name, expected_params) in zip(
        all_tool_requests, expected_tool_requests, strict=True
    ):
        assert tool_request.name == expected_tool_name
        for k, v in expected_params.items():
            assert tool_request.args[k] == v


def _setup_swarm_for_multiple_tool_calling(
    llm: LlmModel, raise_exceptions: bool, swarm_template: Optional[PromptTemplate]
):
    fooza_agent = _get_fooza_agent(
        llm, raise_exception_tool=True, raise_exceptions=raise_exceptions
    )
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)
    main_agent = get_first_agent(llm)
    main_agent.custom_instruction = (
        "You are the main agent. You SHOULD output all the tool calls at once when appropriate. "
        "If you are unable to obtain a complete result, return the partial result instead."
    )

    math_swarm = Swarm(
        first_agent=main_agent,
        relationships=[(main_agent, agent) for agent in [fooza_agent, bwip_agent, zbuk_agent]],
        swarm_template=swarm_template,
    )

    return math_swarm.start_conversation(
        messages="Compute the result of fooza(4, 2) + bwip(4, 5) + zbuk(5, 6)"
    )


@retry_test(max_attempts=3)
def test_benchmark_swarm_can_do_multiple_tool_calling_when_appropriate(
    vllm_responses_llm: LlmModel,
    swarm_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.33 ** 3) ~= 3703.7 / 100'000
    """
    fooza_agent = _get_fooza_agent(vllm_responses_llm)
    bwip_agent = _get_bwip_agent(vllm_responses_llm)
    zbuk_agent = _get_zbuk_agent(vllm_responses_llm)
    main_agent = get_first_agent(vllm_responses_llm)
    main_agent.custom_instruction = (
        "You are the main agent. You SHOULD output all the tool calls at once when appropriate."
    )

    math_swarm = Swarm(
        first_agent=main_agent,
        relationships=[(main_agent, agent) for agent in [fooza_agent, bwip_agent, zbuk_agent]],
        swarm_template=swarm_template,
    )

    conv = math_swarm.start_conversation(
        messages=(
            "Compute the result of fooza(4, 2) + bwip(4, 5) + zbuk(5, 6). "
            "You should call multiple tools at once for this task."
        )
    )
    conv.execute()

    expected_tool_requests = [
        ("send_message", {"recipient": "fooza_agent"}),
        ("send_message", {"recipient": "bwip_agent"}),
        ("send_message", {"recipient": "zbuk_agent"}),
    ]

    messages = conv.get_messages()
    second_message = messages[1]
    if not swarm_template.native_tool_calling:
        assert second_message.tool_requests is not None
        assert len(second_message.tool_requests) == 3
        actual_tool_requests = second_message.tool_requests
    else:
        actual_tool_requests = [
            tool_request
            for message in messages
            for tool_request in (message.tool_requests or [])
            if tool_request.name == "send_message"
        ]
        assert len(actual_tool_requests) == 3

    for tool_request, (expected_tool_name, expected_params) in zip(
        actual_tool_requests, expected_tool_requests, strict=True
    ):
        assert tool_request.name == expected_tool_name
        for k, v in expected_params.items():
            assert tool_request.args[k] == v

    result = fooza_tool.func(4, 2) + bwip_tool.func(4, 5) + zbuk_tool.func(5, 6)
    assert str(result) in conv.get_last_message().content


@retry_test(max_attempts=3)
def test_benchmark_swarm_multiple_tool_calling_exception_raises_error(
    vllm_responses_llm: LlmModel,
    swarm_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.33 ** 3) ~= 3703.7 / 100'000
    """
    conv = _setup_swarm_for_multiple_tool_calling(
        vllm_responses_llm, raise_exceptions=True, swarm_template=swarm_template
    )
    try:
        conv.execute()
    except ValueError as exc:
        assert "Cannot compute result using fooza tool." in str(exc)
    else:
        assert False, "Expected fooza tool exception to be raised."


@retry_test(max_attempts=5)
def test_benchmark_swarm_multiple_tool_calling_exception_does_not_raise_error(
    vllm_responses_llm: LlmModel,
    swarm_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           5
    Justification:         (0.33 ** 5) ~= 411.5 / 100'000
    """
    conv = _setup_swarm_for_multiple_tool_calling(
        vllm_responses_llm, raise_exceptions=False, swarm_template=swarm_template
    )
    conv.execute()
    result = bwip_tool.func(4, 5) + zbuk_tool.func(5, 6)
    assert str(result) in conv.get_last_message().content


@retry_test(max_attempts=4)
def test_benchmark_swarm_without_user_input_can_execute_as_expected(
    vllm_responses_llm: LlmModel,
    swarm_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.33 ** 4) ~= 1234.6 / 100'000
    """
    fooza_agent = _get_fooza_agent(vllm_responses_llm)
    bwip_agent = _get_bwip_agent(vllm_responses_llm)
    main_agent = get_first_agent(vllm_responses_llm)

    math_swarm = Swarm(
        first_agent=main_agent,
        relationships=[(main_agent, fooza_agent), (main_agent, bwip_agent)],
        output_descriptors=[
            IntegerProperty("result", description="The result of the user request")
        ],
        caller_input_mode=CallerInputMode.NEVER,
        swarm_template=swarm_template,
    )

    conv = math_swarm.start_conversation(messages="Compute the result of fooza(4, 2) + bwip(4, 5)")
    status = conv.execute()
    assert isinstance(status, FinishedStatus)

    result = fooza_tool.func(4, 2) + bwip_tool.func(4, 5)
    assert status.output_values["result"] == result
