# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Optional

import pytest

from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.models import LlmModel
from wayflowcore.property import IntegerProperty
from wayflowcore.templates import PromptTemplate
from wayflowcore.templates._managerworkerstemplate import (
    _DEFAULT_MANAGERWORKERS_CHAT_TEMPLATE,
    _DEFAULT_MANAGERWORKERS_NATIVE_CHAT_TEMPLATE,
)

from .test_swarm import (
    _get_bwip_agent,
    _get_fooza_agent,
    _get_zbuk_agent,
    bwip_tool,
    fooza_tool,
    zbuk_tool,
)
from .testhelpers.testhelpers import retry_test


@pytest.fixture(
    params=[_DEFAULT_MANAGERWORKERS_CHAT_TEMPLATE, _DEFAULT_MANAGERWORKERS_NATIVE_CHAT_TEMPLATE],
    ids=["old_template", "native_tool_calling_template"],
)
def managerworkers_template(request: pytest.FixtureRequest) -> Optional[PromptTemplate]:
    return request.param


@retry_test(max_attempts=4)
def test_benchmark_managerworkers_can_do_multiple_tool_calling_when_appropriate(
    vllm_responses_llm: LlmModel,
    managerworkers_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.33 ** 4) ~= 1234.6 / 100'000
    """
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)

    group = ManagerWorkers(
        group_manager=llm,
        workers=[fooza_agent, bwip_agent, zbuk_agent],
        managerworkers_template=managerworkers_template,
    )

    conv = group.start_conversation(
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
    if not managerworkers_template.native_tool_calling:
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
        actual_tool_requests,
        expected_tool_requests,
        strict=True,
    ):
        assert tool_request.name == expected_tool_name
        for k, v in expected_params.items():
            assert tool_request.args[k] == v

    assert "30" in conv.get_last_message().content


def _setup_managerworkers_for_multiple_tool_calling(
    llm: LlmModel,
    raise_exceptions: bool,
    managerworkers_template: Optional[PromptTemplate],
):
    fooza_agent = _get_fooza_agent(
        llm, raise_exception_tool=True, raise_exceptions=raise_exceptions
    )
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)

    group = ManagerWorkers(
        group_manager=fooza_agent,
        workers=[bwip_agent, zbuk_agent],
        managerworkers_template=managerworkers_template,
    )

    return group.start_conversation(
        messages=(
            "Compute the result of fooza(4, 2) + bwip(4, 5) + zbuk(5, 6). "
            "You should call multiple tools at once for this task. "
            "If you are unable to obtain a complete result, return the partial result instead."
        )
    )


@retry_test(max_attempts=3)
def test_benchmark_managerworkers_multiple_tool_calling_exception_raises_error(
    vllm_responses_llm: LlmModel,
    managerworkers_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.33 ** 3) ~= 3703.7 / 100'000
    """
    conv = _setup_managerworkers_for_multiple_tool_calling(
        vllm_responses_llm,
        raise_exceptions=True,
        managerworkers_template=managerworkers_template,
    )
    try:
        conv.execute()
    except ValueError as exc:
        assert "Cannot compute result using fooza tool." in str(exc)
    else:
        assert False, "Expected fooza tool exception to be raised."


@retry_test(max_attempts=6)
def test_benchmark_managerworkers_multiple_tool_calling_exception_does_not_raise_error(
    vllm_responses_llm: LlmModel,
    managerworkers_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           6
    Justification:         (0.33 ** 6) ~= 137.2 / 100'000
    """
    conv = _setup_managerworkers_for_multiple_tool_calling(
        vllm_responses_llm,
        raise_exceptions=False,
        managerworkers_template=managerworkers_template,
    )
    conv.execute()
    result = bwip_tool.func(4, 5) + zbuk_tool.func(5, 6)
    assert str(result) in conv.get_last_message().content


@retry_test(max_attempts=4)
def test_benchmark_managerworkers_without_user_input_can_execute_as_expected(
    vllm_responses_llm: LlmModel,
    managerworkers_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.33 ** 4) ~= 1234.6 / 100'000
    """
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)

    group = ManagerWorkers(
        group_manager=llm,
        workers=[fooza_agent, bwip_agent],
        output_descriptors=[
            IntegerProperty("result", description="The result of the user request")
        ],
        caller_input_mode=CallerInputMode.NEVER,
        managerworkers_template=managerworkers_template,
    )

    conv = group.start_conversation(messages="Compute the result of fooza(4, 2) + bwip(4, 5)")
    status = conv.execute()
    assert isinstance(status, FinishedStatus)

    assert status.output_values["result"] == 13


@retry_test(max_attempts=4)
def test_benchmark_two_level_managerworkers_with_llms(
    vllm_responses_llm: LlmModel,
    managerworkers_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.33 ** 4) ~= 1234.6 / 100'000
    """
    llm = vllm_responses_llm

    worker_1 = _get_bwip_agent(llm)

    sub_worker = _get_fooza_agent(llm)
    worker_2 = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction=(
                "You are a second-level manager. Use your worker fooza for related work."
            ),
        ),
        workers=[sub_worker],
        name="worker_2",
        description="worker 2",
        managerworkers_template=managerworkers_template,
    )

    group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction=(
                "You are a first-level manager. Use your workers for fooza and bwip "
                "for related computations."
            ),
        ),
        workers=[worker_1, worker_2],
        name="first_level_group",
        description="First level group",
        managerworkers_template=managerworkers_template,
    )

    conv = group.start_conversation(
        messages="Compute the result of fooza(4, 2) and add it with bwip(4,5)"
    )
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    ans = fooza_tool.func(4, 2) + bwip_tool.func(4, 5)
    assert str(ans) in conv.get_last_message().content


@retry_test(max_attempts=3)
def test_benchmark_three_level_managerworkers_with_llms(
    vllm_responses_llm: LlmModel,
    managerworkers_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.33 ** 3) ~= 3703.7 / 100'000
    """
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)

    third_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction=(
                "You are a third-level manager. Use your worker fooza for related work."
            ),
        ),
        workers=[fooza_agent],
        name="third_level_group",
        description="Third level group",
        managerworkers_template=managerworkers_template,
    )
    second_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction=(
                "You are a second-level manager. Use your third-level group for "
                "fooza related work."
            ),
        ),
        workers=[third_level_group],
        name="second_level_group",
        description="Second level group",
        managerworkers_template=managerworkers_template,
    )
    first_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction=(
                "You are a first-level manager. Use your workers for fooza, bwip, "
                "zbuk related computations."
            ),
        ),
        workers=[second_level_group, bwip_agent, zbuk_agent],
        name="first_level_group",
        description="First level group",
        managerworkers_template=managerworkers_template,
    )

    conv = first_level_group.start_conversation(
        messages="Compute the result of fooza(4, 2) and add it with bwip(4,5) and zbuk(5,6)"
    )
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    ans = fooza_tool.func(4, 2) + bwip_tool.func(4, 5) + zbuk_tool.func(5, 6)
    assert str(ans) in conv.get_last_message().content


@retry_test(max_attempts=5)
def test_benchmark_linear_chain_managerworkers_with_llms(
    vllm_responses_llm: LlmModel,
    managerworkers_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           5
    Justification:         (0.33 ** 5) ~= 411.5 / 100'000
    """
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)

    third_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction=(
                "You are a third-level manager. Use your worker fooza for related work."
            ),
        ),
        workers=[fooza_agent],
        name="third_level_group",
        description="Third level group",
        managerworkers_template=managerworkers_template,
    )
    second_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction=(
                "You are a second-level manager. Use your workers for fooza and "
                "zbuk related computations."
            ),
        ),
        workers=[third_level_group, zbuk_agent],
        name="second_level_group",
        description="Second level group",
        managerworkers_template=managerworkers_template,
    )
    first_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction=(
                "You are a first-level manager. Use your workers for fooza, bwip, "
                "zbuk related computations."
            ),
        ),
        workers=[second_level_group, bwip_agent],
        name="first_level_group",
        description="First level group",
        managerworkers_template=managerworkers_template,
    )

    conv = first_level_group.start_conversation(
        messages="Compute the result of fooza(4, 2) and add it with bwip(4,5) and zbuk(5,6)"
    )
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    ans = fooza_tool.func(4, 2) + bwip_tool.func(4, 5) + zbuk_tool.func(5, 6)
    assert str(ans) in conv.get_last_message().content


@retry_test(max_attempts=5)
def test_benchmark_multi_managers_with_llms(
    vllm_responses_llm: LlmModel,
    managerworkers_template: Optional[PromptTemplate],
):
    """
    Failure rate:          0 out of 1
    Observed on:           2026-05-20
    Average success time:  No time measurement
    Average failure time:  No time measurement
    Max attempt:           5
    Justification:         (0.33 ** 5) ~= 411.5 / 100'000
    """
    llm = vllm_responses_llm

    fooza_agent = _get_fooza_agent(llm)
    bwip_agent = _get_bwip_agent(llm)
    zbuk_agent = _get_zbuk_agent(llm)

    second_level_group_1 = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction=(
                "You are second level group 1 manager. Use your worker fooza " "for related work."
            ),
        ),
        workers=[fooza_agent],
        name="second_level_group_1",
        description="Second level group 1",
        managerworkers_template=managerworkers_template,
    )
    second_level_group_2 = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction=(
                "You are second level group 2 manager. Use your workers bwip "
                "and zbuk for related work."
            ),
        ),
        workers=[bwip_agent, zbuk_agent],
        name="second_level_group_2",
        description="Second level group 2",
        managerworkers_template=managerworkers_template,
    )
    first_level_group = ManagerWorkers(
        group_manager=Agent(
            llm=llm,
            custom_instruction=(
                "You are first level group manager. Use your workers second level "
                "group 1 for fooza and group 2 managers for bwip and zbuk related work."
            ),
        ),
        workers=[second_level_group_1, second_level_group_2],
        name="first_level_group",
        description="First level group",
        managerworkers_template=managerworkers_template,
    )

    conv = first_level_group.start_conversation(
        messages="Compute the result of fooza(4, 2) and add it with bwip(4,5) and zbuk(5,6)"
    )
    status = conv.execute()
    assert isinstance(status, UserMessageRequestStatus)
    ans = fooza_tool.func(4, 2) + bwip_tool.func(4, 5) + zbuk_tool.func(5, 6)
    assert str(ans) in conv.get_last_message().content
