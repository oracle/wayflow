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
from wayflowcore.executors._flowexecutor import FlowConversationExecutor
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.serialization import deserialize, serialize
from wayflowcore.steps import CompleteStep, ConstantValuesStep, OutputMessageStep, RetryStep
from wayflowcore.steps.promptexecutionstep import PromptExecutionStep
from wayflowcore.swarm import Swarm

from .serialization.test_assistant_serialization import create_flow
from .test_managerworkers import _send_message
from .testhelpers.dummy import DummyModel


def _checkpoint_restore_wrong_component_type_scenario(
    checkpointer: InMemoryCheckpointer,
):
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello original."))
    agent = Agent(
        llm=DummyModel(),
        name="checkpoint_wrong_type_agent",
        description="checkpoint_wrong_type_agent description",
        custom_instruction="Be helpful.",
        initial_message="Hello from the wrong component type.",
        agent_id="checkpoint_wrong_type_agent",
    )
    conversation = flow.start_conversation(
        conversation_id="checkpoint-other-component-type",
        checkpointer=checkpointer,
    )
    assert isinstance(conversation.execute(), FinishedStatus)
    return conversation, agent


def _checkpoint_restore_wrong_component_identity_scenario(
    checkpointer: InMemoryCheckpointer,
):
    original_agent = Agent(
        llm=DummyModel(),
        name="checkpoint_owner_agent",
        agent_id="checkpoint-owner-agent-a",
        description="Original checkpoint owner",
        custom_instruction="Be helpful.",
        initial_message="Hello from checkpoint owner A.",
    )
    other_agent = Agent(
        llm=DummyModel(),
        name="checkpoint_owner_agent",
        agent_id="checkpoint-owner-agent-b",
        description="Other checkpoint owner",
        custom_instruction="Be helpful.",
        initial_message="Hello from checkpoint owner B.",
    )
    conversation = original_agent.start_conversation(
        conversation_id="checkpoint-explicit-owner",
        checkpointer=checkpointer,
    )
    assert isinstance(conversation.execute(), UserMessageRequestStatus)
    return conversation, other_agent


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


def test_inmemory_checkpointer_can_save_load_list_and_delete_checkpoints() -> None:
    checkpointer = InMemoryCheckpointer()
    flow = create_flow()

    conversation = flow.start_conversation(
        conversation_id="checkpoint-lifecycle", checkpointer=checkpointer
    )
    assert conversation.checkpointer is checkpointer

    first_status = conversation.execute()
    assert isinstance(first_status, UserMessageRequestStatus)
    first_checkpoint = checkpointer.load_latest(conversation.conversation_id)
    assert first_checkpoint is not None
    first_checkpoint_id = first_checkpoint.checkpoint_id
    assert conversation.checkpoint_id == first_checkpoint_id

    conversation.append_user_message("continue")
    second_status = conversation.execute()
    assert isinstance(second_status, FinishedStatus)
    second_checkpoint = checkpointer.load_latest(conversation.conversation_id)
    assert second_checkpoint is not None
    second_checkpoint_id = second_checkpoint.checkpoint_id
    assert second_checkpoint_id != first_checkpoint_id
    assert conversation.checkpoint_id == second_checkpoint_id

    checkpoints = checkpointer.list_checkpoints("checkpoint-lifecycle")
    assert [checkpoint.checkpoint_id for checkpoint in checkpoints] == [
        first_checkpoint_id,
        second_checkpoint_id,
    ]
    assert checkpoints[-1].metadata["save_sequence"] == 2

    latest_checkpoint = checkpointer.load_latest("checkpoint-lifecycle")
    assert latest_checkpoint is not None
    assert latest_checkpoint.checkpoint_id == second_checkpoint_id

    restored_conversation = flow.start_conversation(
        conversation_id="checkpoint-lifecycle",
        checkpoint_id=first_checkpoint_id,
        checkpointer=checkpointer,
    )
    assert restored_conversation.checkpointer is checkpointer
    assert restored_conversation.checkpoint_id == first_checkpoint_id
    assert isinstance(restored_conversation.status, UserMessageRequestStatus)

    checkpointer.delete("checkpoint-lifecycle", second_checkpoint_id)
    promoted_checkpoint = checkpointer.load_latest("checkpoint-lifecycle")
    assert promoted_checkpoint is not None
    assert promoted_checkpoint.checkpoint_id == first_checkpoint_id
    assert [
        checkpoint.checkpoint_id
        for checkpoint in checkpointer.list_checkpoints("checkpoint-lifecycle")
    ] == [first_checkpoint_id]


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


def test_checkpoint_restore_with_serialized_component_graph() -> None:
    checkpointer = InMemoryCheckpointer()
    original_flow = create_flow()

    conversation = original_flow.start_conversation(
        conversation_id="checkpoint-serialized-component-graph",
        checkpointer=checkpointer,
    )
    first_status = conversation.execute()
    assert isinstance(first_status, UserMessageRequestStatus)

    serialized_flow = serialize(original_flow)
    reloaded_flow = deserialize(Flow, serialized_flow)
    assert reloaded_flow.id == original_flow.id
    assert {name: step.id for name, step in reloaded_flow.steps.items()} == {
        name: step.id for name, step in original_flow.steps.items()
    }

    restored_conversation = reloaded_flow.start_conversation(
        conversation_id=conversation.conversation_id,
        checkpointer=checkpointer,
    )
    assert isinstance(restored_conversation.status, UserMessageRequestStatus)

    restored_conversation.append_user_message("continue")
    assert isinstance(restored_conversation.execute(), FinishedStatus)


def test_checkpoint_restore_preserves_retry_counter_with_recreated_step() -> None:
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

    counter_key = FlowConversationExecutor.make_key_for_step(
        retry_step, RetryStep._RETRY_COUNTER_KEY
    )
    checkpoint = next(
        checkpoint
        for checkpoint in checkpointer.list_checkpoints(conversation.conversation_id)
        if f"{counter_key}: 1" in checkpoint.state
    )

    reloaded_flow = deserialize(Flow, serialize(flow))
    reloaded_retry_step = reloaded_flow.steps["retry_step"]
    reloaded_retry_step.name = "renamed_retry_step"
    restored_conversation = reloaded_flow.start_conversation(
        conversation_id=conversation.conversation_id,
        checkpoint_id=checkpoint.checkpoint_id,
        checkpointer=checkpointer,
    )

    restored_counter_key = FlowConversationExecutor.make_key_for_step(
        reloaded_retry_step, RetryStep._RETRY_COUNTER_KEY
    )
    assert restored_counter_key == counter_key
    assert restored_conversation.state.internal_context_key_values[restored_counter_key] == 1
    restored_status = restored_conversation.execute()
    assert isinstance(restored_status, FinishedStatus)
    assert restored_status.complete_step_name == "failure"


def test_managerworkers_checkpoint_restore_preserves_worker_subconversation() -> None:
    manager_llm = DummyModel()
    worker = Agent(
        llm=DummyModel(fails_if_not_set=False),
        name="checkpoint_worker",
        description="Checkpoint worker",
        initial_message="Worker ready.",
    )
    group = ManagerWorkers(
        group_manager=manager_llm,
        workers=[worker],
        name="checkpoint_managerworkers",
        id="checkpoint-managerworkers",
    )
    checkpointer = InMemoryCheckpointer(
        checkpointing_interval=CheckpointingInterval.ALL_INTERNAL_TURNS
    )

    conversation = group.start_conversation(
        conversation_id="checkpoint-managerworkers",
        checkpointer=checkpointer,
    )
    conversation.append_user_message("Delegate this task.")
    manager_llm.set_next_output([_send_message(worker, message="Please help."), "All done."])

    status = conversation.execute()
    assert isinstance(status, UserMessageRequestStatus)
    assert worker.id in conversation.subconversations

    checkpoint = checkpointer.load_latest(conversation.conversation_id)
    assert checkpoint is not None
    restored_conversation = group.start_conversation(
        conversation_id=conversation.conversation_id,
        checkpoint_id=checkpoint.checkpoint_id,
        checkpointer=checkpointer,
    )

    assert worker.id in restored_conversation.subconversations
    assert restored_conversation.subconversations[worker.id].component is worker


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
def test_checkpoint_intervals_save_expected_checkpoints(
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


@pytest.mark.parametrize(
    "scenario",
    [
        _checkpoint_restore_wrong_component_type_scenario,
        _checkpoint_restore_wrong_component_identity_scenario,
        _checkpoint_restore_generated_agent_id_scenario,
        _checkpoint_restore_generated_swarm_child_id_scenario,
    ],
    ids=[
        "wrong_component_type",
        "wrong_component_identity",
        "generated_agent_id",
        "generated_swarm_child_id",
    ],
)
def test_checkpoint_restore_rejects_component_id_mismatches(scenario) -> None:
    checkpointer = InMemoryCheckpointer()
    conversation, restarted_component = scenario(checkpointer)

    with pytest.raises(ValueError, match="stable component ids"):
        restarted_component.start_conversation(
            conversation_id=conversation.conversation_id,
            checkpointer=checkpointer,
        )
