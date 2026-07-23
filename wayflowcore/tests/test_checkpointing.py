# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from unittest.mock import AsyncMock

import pytest

from wayflowcore.agent import Agent
from wayflowcore.checkpointing import CheckpointingInterval, InMemoryCheckpointer
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.serialization import deserialize, serialize
from wayflowcore.steps import CompleteStep, ConstantValuesStep, OutputMessageStep, RetryStep
from wayflowcore.steps.promptexecutionstep import PromptExecutionStep
from wayflowcore.swarm import Swarm

from .testhelpers.dummy import DummyModel


def test_checkpointer_save_snapshots_a_live_conversation_with_custom_metadata() -> None:
    checkpointer = InMemoryCheckpointer()
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello from checkpointing."))
    conversation = flow.start_conversation(conversation_id="custom-checkpoint")

    saved_checkpoint = checkpointer.save(
        conversation,
        checkpoint_id="response_123",
        component_id="served-model",
        metadata={"response": "serialized response"},
    )

    assert saved_checkpoint is not None
    assert saved_checkpoint.checkpoint_id == "response_123"
    assert conversation.checkpoint_id == "response_123"
    checkpoint = checkpointer.load("custom-checkpoint", "response_123")
    assert checkpoint.component_id == "served-model"
    assert checkpoint.metadata["response"] == "serialized response"

    checkpointer.save(conversation, checkpoint_id="response_456")

    checkpoints = checkpointer.list_checkpoints("custom-checkpoint")
    assert [checkpoint.checkpoint_id for checkpoint in checkpoints] == [
        "response_123",
        "response_456",
    ]
    assert checkpoints[-1].metadata["save_sequence"] == 2
    assert checkpointer.load_latest("custom-checkpoint").checkpoint_id == "response_456"

    checkpointer.delete("custom-checkpoint", "response_456")

    assert checkpointer.load_latest("custom-checkpoint").checkpoint_id == "response_123"


def test_checkpoint_restore_requires_conversation_id_when_checkpoint_id_is_provided() -> None:
    checkpointer = InMemoryCheckpointer()
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello from checkpointing."))

    conversation = flow.start_conversation(
        conversation_id="checkpoint-missing-conversation-id",
        checkpointer=checkpointer,
    )
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)

    checkpoint = checkpointer.load_latest(conversation.conversation_id)
    assert checkpoint is not None

    with pytest.raises(ValueError, match="`checkpoint_id` requires a `conversation_id`\\."):
        flow.start_conversation(
            checkpointer=checkpointer,
            checkpoint_id=checkpoint.checkpoint_id,
        )


def test_checkpoint_restore_resumes_retry_flow() -> None:
    # An internal-turn checkpoint must preserve retry progress instead of
    # restarting the retry sequence when the conversation is restored.
    inner_flow = create_single_step_flow(
        ConstantValuesStep(constant_values={"success": False}, name="retry_result")
    )
    retry_step = RetryStep(
        flow=inner_flow,
        success_condition="success",
        max_num_trials=2,
        name="retry_step",
    )
    success_step = CompleteStep(name="success")
    failure_step = CompleteStep(name="failure")
    flow = Flow(
        begin_step=retry_step,
        steps={"retry_step": retry_step, "success": success_step, "failure": failure_step},
        control_flow_edges=[
            ControlFlowEdge(
                source_step=retry_step,
                source_branch=RetryStep.BRANCH_NEXT,
                destination_step=success_step,
            ),
            ControlFlowEdge(
                source_step=retry_step,
                source_branch=RetryStep.BRANCH_FAILURE,
                destination_step=failure_step,
            ),
        ],
    )
    checkpointer = InMemoryCheckpointer(
        checkpointing_interval=CheckpointingInterval.ALL_INTERNAL_TURNS
    )

    conversation = flow.start_conversation(
        conversation_id="checkpoint-retry-counter",
        checkpointer=checkpointer,
    )
    assert isinstance(conversation.execute(), FinishedStatus)

    # Restore from an in-progress checkpoint rather than the final checkpoint.
    checkpoint = next(
        checkpoint
        for checkpoint in checkpointer.list_checkpoints(conversation.conversation_id)
        if checkpoint.metadata["save_reason"] == "internal_turn_boundary"
    )

    reloaded_flow = deserialize(Flow, serialize(flow))
    restored_conversation = reloaded_flow.start_conversation(
        conversation_id=conversation.conversation_id,
        checkpoint_id=checkpoint.checkpoint_id,
        checkpointer=checkpointer,
    )

    restored_status = restored_conversation.execute()
    # The restored retry has exhausted its attempts and takes the failure branch.
    assert isinstance(restored_status, FinishedStatus)
    assert restored_status.complete_step_name == "failure"


@pytest.mark.parametrize(
    (
        "interval",
        "conversation_id",
        "step",
        "expected_reasons",
        "expected_event_types",
    ),
    [
        (
            CheckpointingInterval.CONVERSATION_TURNS,
            "conversation-turn",
            OutputMessageStep(message_template="Hello once."),
            ["conversation_turn"],
            [],
        ),
        (
            CheckpointingInterval.ALL_INTERNAL_TURNS,
            "all-internal-turns",
            OutputMessageStep(message_template="Hello internal turns."),
            ["internal_turn_boundary", "internal_turn_boundary", "conversation_turn"],
            ["FlowExecutionIterationStartedEvent", "FlowExecutionIterationStartedEvent"],
        ),
        (
            CheckpointingInterval.LLM_TURNS,
            "llm-turns",
            None,
            ["internal_turn_boundary", "conversation_turn"],
            ["FlowExecutionIterationStartedEvent"],
        ),
    ],
    ids=["conversation_turns", "all_internal_turns", "llm_turns"],
)
def test_checkpoint_intervals_save_expected_flow_checkpoints(
    interval: CheckpointingInterval,
    conversation_id: str,
    step,
    expected_reasons: list[str],
    expected_event_types: list[str],
) -> None:
    checkpointer = InMemoryCheckpointer(checkpointing_interval=interval)
    if step is None:
        llm = DummyModel()
        llm.set_next_output("Hello from the prompt step.")
        step = PromptExecutionStep(llm=llm, prompt_template="Say hello.")
    flow = create_single_step_flow(step)

    status = flow.start_conversation(
        conversation_id=conversation_id,
        checkpointer=checkpointer,
    ).execute()

    assert isinstance(status, FinishedStatus)
    checkpoints = checkpointer.list_checkpoints(conversation_id)
    assert [checkpoint.metadata["save_reason"] for checkpoint in checkpoints] == expected_reasons
    assert [checkpoint.metadata.get("event_type") for checkpoint in checkpoints[:-1]] == (
        expected_event_types
    )
    assert checkpoints[-1].metadata["status_type"] == "FinishedStatus"


@pytest.mark.parametrize(
    "interval",
    list(CheckpointingInterval),
    ids=["conversation_turns", "all_internal_turns", "llm_turns"],
)
def test_checkpoint_intervals_save_expected_agent_checkpoints(
    interval: CheckpointingInterval,
) -> None:
    checkpointer = InMemoryCheckpointer(checkpointing_interval=interval)
    conversation_id = f"agent-{interval.name.lower()}"
    agent = Agent(
        llm=DummyModel(),
        name="checkpoint_interval_agent",
        initial_message="Hello from the agent.",
    )

    status = agent.start_conversation(
        conversation_id=conversation_id,
        checkpointer=checkpointer,
    ).execute()

    assert isinstance(status, UserMessageRequestStatus)
    checkpoints = checkpointer.list_checkpoints(conversation_id)
    assert checkpoints[-1].metadata["save_reason"] == "conversation_turn"
    assert checkpoints[-1].metadata["status_type"] == "UserMessageRequestStatus"
    if interval is CheckpointingInterval.ALL_INTERNAL_TURNS:
        assert any(
            checkpoint.metadata.get("event_type") == "AgentExecutionIterationStartedEvent"
            for checkpoint in checkpoints
        )
        assert all(
            checkpoint.metadata.get("agent_iteration") is not None
            for checkpoint in checkpoints[:-1]
        )


def test_execute_async_does_not_save_final_checkpoint_when_execution_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpointer = InMemoryCheckpointer()
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello failure."))

    conversation = flow.start_conversation(
        conversation_id="checkpoint-final-exception",
        checkpointer=checkpointer,
    )
    monkeypatch.setattr(
        conversation.component.runner,
        "execute_async",
        AsyncMock(side_effect=RuntimeError("runner failed")),
    )

    with pytest.raises(RuntimeError, match="runner failed"):
        conversation.execute()

    assert checkpointer.list_checkpoints("checkpoint-final-exception") == []


def _checkpoint_restore_generated_agent_id_scenario(
    checkpointer: InMemoryCheckpointer,
):
    original_agent = Agent(
        llm=DummyModel(),
        name="generated_id_restart_agent",
        description="generated_id_restart_agent description",
        custom_instruction="Be helpful.",
        initial_message="Hello from the original generated-id agent.",
    )
    conversation = original_agent.start_conversation(
        conversation_id="agent-generated-id-restart",
        checkpointer=checkpointer,
    )
    assert isinstance(conversation.execute(), UserMessageRequestStatus)
    restarted_agent = Agent(
        llm=DummyModel(),
        name="generated_id_restart_agent",
        description="generated_id_restart_agent description",
        custom_instruction="Be helpful.",
        initial_message="Hello from the original generated-id agent.",
    )
    return conversation, restarted_agent


def _checkpoint_restore_generated_swarm_child_id_scenario(
    checkpointer: InMemoryCheckpointer,
):
    def build_swarm() -> Swarm:
        first_agent = Agent(
            llm=DummyModel(),
            name="checkpoint_swarm_first_agent",
            description="checkpoint_swarm_first_agent description",
            custom_instruction="Be helpful.",
            initial_message="Hello from the swarm.",
        )
        second_agent = Agent(
            llm=DummyModel(fails_if_not_set=False),
            name="checkpoint_swarm_second_agent",
            description="Swarm helper",
            custom_instruction="Help with delegated tasks.",
        )
        return Swarm(
            first_agent=first_agent,
            relationships=[(first_agent, second_agent)],
            name="checkpoint_swarm",
        )

    original_swarm = build_swarm()
    conversation = original_swarm.start_conversation(
        conversation_id="swarm-generated-child-id-restart",
        checkpointer=checkpointer,
    )
    assert isinstance(conversation.execute(), UserMessageRequestStatus)
    restarted_swarm = build_swarm()
    return conversation, restarted_swarm


@pytest.mark.parametrize(
    "scenario",
    [
        _checkpoint_restore_generated_agent_id_scenario,
        _checkpoint_restore_generated_swarm_child_id_scenario,
    ],
    ids=[
        "generated_agent_id",
        "generated_swarm_child_id",
    ],
)
def test_checkpoint_restore_requires_matching_component_ids(scenario) -> None:
    checkpointer = InMemoryCheckpointer()
    conversation, restarted_component = scenario(checkpointer)

    with pytest.raises(ValueError, match="stable component ids"):
        restarted_component.start_conversation(
            conversation_id=conversation.conversation_id,
            checkpointer=checkpointer,
        )
