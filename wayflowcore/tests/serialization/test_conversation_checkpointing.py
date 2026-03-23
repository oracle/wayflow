# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import warnings
from typing import Any, Dict, Optional

import pytest

from wayflowcore.a2a.a2aagent import A2AAgent, A2AConnectionConfig
from wayflowcore.agent import Agent
from wayflowcore.checkpointing import CheckpointingInterval, InMemoryCheckpointer
from wayflowcore.checkpointing.runtime import (
    _save_conversation_checkpoint,
    _set_conversation_final_checkpoint_overrides,
)
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey
from wayflowcore.ociagent import OciAgent
from wayflowcore.steps import OutputMessageStep, PromptExecutionStep
from wayflowcore.swarm import Swarm

from ..testhelpers.dummy import DummyModel
from ..testhelpers.testhelpers import retry_test
from .test_assistant_serialization import create_flow


class FailingOnceInMemoryCheckpointer(InMemoryCheckpointer):
    def __init__(self) -> None:
        super().__init__()
        self.should_fail_next_save = True

    def save_conversation(
        self,
        conversation,
        *,
        checkpoint_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        if self.should_fail_next_save:
            self.should_fail_next_save = False
            raise RuntimeError("checkpoint save failed")
        return super().save_conversation(
            conversation,
            checkpoint_id=checkpoint_id,
            metadata=metadata,
        )


def _build_checkpointable_agent(
    *,
    name: str,
    initial_message: str,
) -> tuple[Agent, DummyModel]:
    llm = DummyModel()
    agent = Agent(
        llm=llm,
        name=name,
        description=f"{name} description",
        custom_instruction="Be helpful.",
        initial_message=initial_message,
    )
    return agent, llm


def _build_checkpointable_swarm() -> tuple[Swarm, DummyModel]:
    first_agent, first_agent_llm = _build_checkpointable_agent(
        name="checkpoint_swarm_first_agent",
        initial_message="Hello from the swarm.",
    )
    second_agent = Agent(
        llm=DummyModel(fails_if_not_set=False),
        name="checkpoint_swarm_second_agent",
        description="Swarm helper",
        custom_instruction="Help with delegated tasks.",
    )
    swarm = Swarm(
        first_agent=first_agent,
        relationships=[(first_agent, second_agent)],
        name="checkpoint_swarm",
    )
    return swarm, first_agent_llm


def _build_checkpointable_managerworkers() -> tuple[ManagerWorkers, DummyModel]:
    manager_agent, manager_llm = _build_checkpointable_agent(
        name="checkpoint_manager_agent",
        initial_message="Hello from the manager.",
    )
    worker_agent = Agent(
        llm=DummyModel(fails_if_not_set=False),
        name="checkpoint_worker_agent",
        description="Worker agent",
        custom_instruction="Help the manager.",
    )
    managerworkers = ManagerWorkers(
        group_manager=manager_agent,
        workers=[worker_agent],
        name="checkpoint_managerworkers",
    )
    return managerworkers, manager_llm


@pytest.fixture(scope="session")
def connection_config_no_verify():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return A2AConnectionConfig(verify=False)


@pytest.fixture
def a2a_agent(a2a_server, connection_config_no_verify):
    return A2AAgent(
        name="Checkpoint A2A Agent",
        agent_url=a2a_server,
        connection_config=connection_config_no_verify,
    )


def test_inmemory_checkpointer_can_save_load_list_and_delete_checkpoints() -> None:
    checkpointer = InMemoryCheckpointer()
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello from checkpointing."))

    conversation = flow.start_conversation(
        conversation_id="checkpoint-lifecycle", checkpointer=checkpointer
    )
    status = conversation.execute()

    assert isinstance(status, FinishedStatus)
    first_checkpoint_id = conversation.checkpoint_id
    assert first_checkpoint_id is not None

    checkpointer.save(conversation)
    second_checkpoint_id = conversation.checkpoint_id
    assert second_checkpoint_id is not None
    assert second_checkpoint_id != first_checkpoint_id

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
    assert restored_conversation.checkpoint_id == first_checkpoint_id
    assert restored_conversation.get_last_message().content == "Hello from checkpointing."

    checkpointer.delete("checkpoint-lifecycle", second_checkpoint_id)
    promoted_checkpoint = checkpointer.load_latest("checkpoint-lifecycle")
    assert promoted_checkpoint is not None
    assert promoted_checkpoint.checkpoint_id == first_checkpoint_id
    assert [
        checkpoint.checkpoint_id
        for checkpoint in checkpointer.list_checkpoints("checkpoint-lifecycle")
    ] == [first_checkpoint_id]


def test_conversation_turns_checkpoint_interval_saves_once_after_outer_execute() -> None:
    checkpointer = InMemoryCheckpointer(
        checkpointing_interval=CheckpointingInterval.CONVERSATION_TURNS
    )
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello once."))

    status = flow.start_conversation(
        conversation_id="conversation-turn", checkpointer=checkpointer
    ).execute()

    assert isinstance(status, FinishedStatus)
    checkpoints = checkpointer.list_checkpoints("conversation-turn")
    assert len(checkpoints) == 1
    assert checkpoints[0].metadata["save_reason"] == "conversation_turn"
    assert checkpoints[0].metadata["status_type"] == "FinishedStatus"


def test_all_internal_turns_checkpoint_interval_saves_before_each_flow_turn() -> None:
    checkpointer = InMemoryCheckpointer(
        checkpointing_interval=CheckpointingInterval.ALL_INTERNAL_TURNS
    )
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello internal turns."))

    status = flow.start_conversation(
        conversation_id="all-internal-turns", checkpointer=checkpointer
    ).execute()

    assert isinstance(status, FinishedStatus)
    checkpoints = checkpointer.list_checkpoints("all-internal-turns")
    assert len(checkpoints) == 3
    assert [checkpoint.metadata["save_reason"] for checkpoint in checkpoints] == [
        "internal_turn_boundary",
        "internal_turn_boundary",
        "conversation_turn",
    ]
    assert [checkpoint.metadata.get("event_type") for checkpoint in checkpoints[:-1]] == [
        "FlowExecutionIterationStartedEvent",
        "FlowExecutionIterationStartedEvent",
    ]
    assert checkpoints[-1].metadata["status_type"] == "FinishedStatus"


def test_llm_turns_checkpoint_interval_saves_only_after_llm_backed_turns() -> None:
    checkpointer = InMemoryCheckpointer(checkpointing_interval=CheckpointingInterval.LLM_TURNS)
    dummy_llm = DummyModel()
    dummy_llm.set_next_output("Hello from the prompt step.")
    flow = create_single_step_flow(
        PromptExecutionStep(
            llm=dummy_llm,
            prompt_template="Say hello.",
        )
    )

    status = flow.start_conversation(
        conversation_id="llm-turns", checkpointer=checkpointer
    ).execute()

    assert isinstance(status, FinishedStatus)
    checkpoints = checkpointer.list_checkpoints("llm-turns")
    assert len(checkpoints) == 2
    assert checkpoints[0].metadata["save_reason"] == "internal_turn_boundary"
    assert checkpoints[0].metadata["event_type"] == "FlowExecutionIterationStartedEvent"
    assert checkpoints[0].metadata["llm_used_in_previous_turn"] is True
    assert checkpoints[1].metadata["save_reason"] == "conversation_turn"


def test_final_checkpoint_save_overrides_are_preserved_when_save_fails() -> None:
    checkpointer = FailingOnceInMemoryCheckpointer()
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello overrides."))

    conversation = flow.start_conversation(
        conversation_id="checkpoint-final-overrides", checkpointer=checkpointer
    )
    _set_conversation_final_checkpoint_overrides(
        conversation,
        checkpoint_id="final-checkpoint-id",
        metadata={"response_id": "resp-123"},
    )

    with pytest.raises(RuntimeError, match="checkpoint save failed"):
        _save_conversation_checkpoint(
            conversation,
            save_reason="conversation_turn",
            use_final_save_overrides=True,
        )

    _save_conversation_checkpoint(
        conversation,
        save_reason="conversation_turn",
        use_final_save_overrides=True,
    )

    assert conversation.checkpoint_id == "final-checkpoint-id"
    checkpoint = checkpointer.load("checkpoint-final-overrides", "final-checkpoint-id")
    assert checkpoint.metadata["response_id"] == "resp-123"


def test_flow_checkpointing_supports_resume_and_time_travel() -> None:
    checkpointer = InMemoryCheckpointer()
    flow = create_flow()

    conversation = flow.start_conversation(
        conversation_id="flow-checkpoint", checkpointer=checkpointer
    )
    first_status = conversation.execute()

    assert isinstance(first_status, UserMessageRequestStatus)
    first_checkpoint_id = conversation.checkpoint_id
    assert first_checkpoint_id is not None

    restored_conversation = flow.start_conversation(
        conversation_id=conversation.id,
        checkpointer=checkpointer,
    )
    assert restored_conversation.checkpoint_id == first_checkpoint_id
    assert isinstance(restored_conversation.status, UserMessageRequestStatus)

    restored_conversation.append_user_message("continue")
    restored_status = restored_conversation.execute()
    assert isinstance(restored_status, FinishedStatus)

    rewound_conversation = flow.start_conversation(
        conversation_id=conversation.id,
        checkpointer=checkpointer,
        checkpoint_id=first_checkpoint_id,
    )
    assert len(rewound_conversation.get_messages()) < len(restored_conversation.get_messages())
    rewound_conversation.append_user_message("rewind")
    rewound_status = rewound_conversation.execute()
    assert isinstance(rewound_status, FinishedStatus)


def test_agent_checkpointing_supports_resume_and_time_travel() -> None:
    checkpointer = InMemoryCheckpointer()
    agent, llm = _build_checkpointable_agent(
        name="checkpoint_agent",
        initial_message="Hello from the agent.",
    )

    conversation = agent.start_conversation(
        conversation_id="agent-checkpoint", checkpointer=checkpointer
    )
    first_status = conversation.execute()

    assert isinstance(first_status, UserMessageRequestStatus)
    first_checkpoint_id = conversation.checkpoint_id
    assert first_checkpoint_id is not None

    restored_conversation = agent.start_conversation(
        conversation_id=conversation.id,
        checkpointer=checkpointer,
    )
    llm.set_next_output("Agent resumed successfully.")
    restored_conversation.append_user_message("Please continue.")
    restored_status = restored_conversation.execute()
    assert isinstance(restored_status, UserMessageRequestStatus)
    assert restored_conversation.get_last_message().content == "Agent resumed successfully."

    rewound_conversation = agent.start_conversation(
        conversation_id=conversation.id,
        checkpointer=checkpointer,
        checkpoint_id=first_checkpoint_id,
    )
    llm.set_next_output("Agent rewound successfully.")
    rewound_conversation.append_user_message("Try again.")
    rewound_status = rewound_conversation.execute()
    assert isinstance(rewound_status, UserMessageRequestStatus)
    assert rewound_conversation.get_last_message().content == "Agent rewound successfully."


def test_swarm_checkpointing_supports_resume_and_time_travel() -> None:
    checkpointer = InMemoryCheckpointer()
    swarm, llm = _build_checkpointable_swarm()

    conversation = swarm.start_conversation(
        conversation_id="swarm-checkpoint", checkpointer=checkpointer
    )
    first_status = conversation.execute()

    assert isinstance(first_status, UserMessageRequestStatus)
    first_checkpoint_id = conversation.checkpoint_id
    assert first_checkpoint_id is not None

    restored_conversation = swarm.start_conversation(
        conversation_id=conversation.id,
        checkpointer=checkpointer,
    )
    llm.set_next_output("Swarm resumed successfully.")
    restored_conversation.append_user_message("Continue the swarm conversation.")
    restored_status = restored_conversation.execute()
    assert isinstance(restored_status, UserMessageRequestStatus)
    assert restored_conversation.get_last_message().content == "Swarm resumed successfully."

    rewound_conversation = swarm.start_conversation(
        conversation_id=conversation.id,
        checkpointer=checkpointer,
        checkpoint_id=first_checkpoint_id,
    )
    llm.set_next_output("Swarm rewound successfully.")
    rewound_conversation.append_user_message("Try the swarm again.")
    rewound_status = rewound_conversation.execute()
    assert isinstance(rewound_status, UserMessageRequestStatus)
    assert rewound_conversation.get_last_message().content == "Swarm rewound successfully."


def test_managerworkers_checkpointing_supports_resume_and_time_travel() -> None:
    checkpointer = InMemoryCheckpointer()
    managerworkers, llm = _build_checkpointable_managerworkers()

    conversation = managerworkers.start_conversation(
        conversation_id="managerworkers-checkpoint",
        checkpointer=checkpointer,
    )
    first_status = conversation.execute()

    assert isinstance(first_status, UserMessageRequestStatus)
    first_checkpoint_id = conversation.checkpoint_id
    assert first_checkpoint_id is not None

    restored_conversation = managerworkers.start_conversation(
        conversation_id=conversation.id,
        checkpointer=checkpointer,
    )
    llm.set_next_output("Manager resumed successfully.")
    restored_conversation.append_user_message("Continue the manager workflow.")
    restored_status = restored_conversation.execute()
    assert isinstance(restored_status, UserMessageRequestStatus)
    assert restored_conversation.get_last_message().content == "Manager resumed successfully."

    rewound_conversation = managerworkers.start_conversation(
        conversation_id=conversation.id,
        checkpointer=checkpointer,
        checkpoint_id=first_checkpoint_id,
    )
    llm.set_next_output("Manager rewound successfully.")
    rewound_conversation.append_user_message("Try the manager workflow again.")
    rewound_status = rewound_conversation.execute()
    assert isinstance(rewound_status, UserMessageRequestStatus)
    assert rewound_conversation.get_last_message().content == "Manager rewound successfully."


@retry_test(max_attempts=4)
def test_a2aagent_checkpointing_supports_resume_and_time_travel(a2a_agent: A2AAgent) -> None:
    """
    Failure rate:          0 out of 20
    Observed on:           2026-03-23
    Average success time:  0.00 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.05 ** 4) ~= 0.6 / 100'000
    """
    checkpointer = InMemoryCheckpointer()

    conversation = a2a_agent.start_conversation(
        conversation_id="a2a-checkpoint", checkpointer=checkpointer
    )
    conversation.append_user_message("What is 5+5? Just output the answer.")
    first_status = conversation.execute()

    assert isinstance(first_status, UserMessageRequestStatus)
    first_checkpoint_id = conversation.checkpoint_id
    assert first_checkpoint_id is not None
    first_message_count = len(conversation.get_messages())

    restored_conversation = a2a_agent.start_conversation(
        conversation_id=conversation.id,
        checkpointer=checkpointer,
    )
    assert restored_conversation.checkpoint_id == first_checkpoint_id
    assert len(restored_conversation.get_messages()) == first_message_count
    restored_conversation.append_user_message(
        "What if you replace 5 by 10? Just output the answer."
    )
    restored_status = restored_conversation.execute()

    assert isinstance(restored_status, UserMessageRequestStatus)
    assert len(restored_conversation.get_messages()) > first_message_count
    assert restored_conversation.get_last_message() is not None
    assert checkpointer.load_latest(conversation.id) is not None

    rewound_conversation = a2a_agent.start_conversation(
        conversation_id=conversation.id,
        checkpointer=checkpointer,
        checkpoint_id=first_checkpoint_id,
    )
    assert len(rewound_conversation.get_messages()) == first_message_count
    assert len(rewound_conversation.get_messages()) < len(restored_conversation.get_messages())
    rewound_conversation.append_user_message("What if you replace 5 by 7? Just output the answer.")
    rewound_status = rewound_conversation.execute()

    assert isinstance(rewound_status, UserMessageRequestStatus)
    assert len(rewound_conversation.get_messages()) > first_message_count
    assert rewound_conversation.get_last_message() is not None


def test_ociagent_explicitly_rejects_checkpoint_restore_arguments() -> None:
    oci_agent = OciAgent(
        agent_endpoint_id="ocid1.test.oc1..example",
        client_config=OCIClientConfigWithApiKey(service_endpoint="https://example.com"),
        name="checkpoint_oci_agent",
    )

    with pytest.raises(NotImplementedError, match="checkpoint restore"):
        oci_agent.start_conversation(checkpointer=InMemoryCheckpointer())
