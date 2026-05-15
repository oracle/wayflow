# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import warnings
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock

import pytest

import wayflowcore.checkpointing.datastorecheckpointer as checkpoint_datastore
import wayflowcore.checkpointing.serialization as checkpoint_serialization
from wayflowcore.a2a.a2aagent import A2AAgent, A2AConnectionConfig
from wayflowcore.agent import Agent
from wayflowcore.checkpointing import (
    CheckpointingInterval,
    ConversationCheckpoint,
    DatastoreCheckpointer,
    InMemoryCheckpointer,
    StorageConfig,
)
from wayflowcore.checkpointing.checkpointeventlistener import _save_conversation_checkpoint
from wayflowcore.datastore._relational import RelationalDatastore
from wayflowcore.exceptions import DatastoreEntityError
from wayflowcore.executors._agentexecutor import AgentConversationExecutor
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey
from wayflowcore.ociagent import OciAgent
from wayflowcore.serialization.serializer import _resolve_legacy_field_name
from wayflowcore.steps import OutputMessageStep, PromptExecutionStep
from wayflowcore.swarm import Swarm
from wayflowcore.tools import ToolResult

from ..testhelpers.dummy import DummyModel
from ..testhelpers.testhelpers import retry_test
from .test_assistant_serialization import create_flow


class RecordingCheckpointer:
    def __init__(self, *, fail_first_save: bool = False) -> None:
        self.checkpointing_interval = CheckpointingInterval.CONVERSATION_TURNS
        self.should_fail_next_save = fail_first_save
        self.saved_checkpoints: Dict[tuple[str, str], Dict[str, Any]] = {}

    def save_conversation(
        self,
        conversation,
        *,
        checkpoint_id: Optional[str] = None,
        component_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        if self.should_fail_next_save:
            self.should_fail_next_save = False
            raise RuntimeError("checkpoint save failed")
        resolved_checkpoint_id = checkpoint_id or "generated-checkpoint-id"
        self.saved_checkpoints[(conversation.id, resolved_checkpoint_id)] = dict(metadata or {})
        conversation.checkpoint_id = resolved_checkpoint_id
        return SimpleNamespace(
            checkpoint_id=resolved_checkpoint_id,
            metadata=dict(metadata or {}),
        )

    def load(self, conversation_id: str, checkpoint_id: str) -> Any:
        return SimpleNamespace(metadata=self.saved_checkpoints[(conversation_id, checkpoint_id)])

    def load_latest(self, conversation_id: str) -> Any:
        return None


class StaticLoadCheckpointer:
    def __init__(self, checkpoint: ConversationCheckpoint) -> None:
        self.checkpointing_interval = CheckpointingInterval.CONVERSATION_TURNS
        self.checkpoint = checkpoint

    def load(self, conversation_id: str, checkpoint_id: str) -> ConversationCheckpoint:
        return self.checkpoint

    def load_latest(self, conversation_id: str) -> Optional[ConversationCheckpoint]:
        if conversation_id != self.checkpoint.conversation_id:
            return None
        return self.checkpoint


class FakeRelationalDatastore(RelationalDatastore):
    def __init__(self) -> None:
        pass

    def _serialize_to_dict(self, serialization_context: Any) -> Dict[str, Any]:
        raise NotImplementedError()

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: Any
    ) -> Any:
        raise NotImplementedError()


class IntegrityRetryCheckpointer(DatastoreCheckpointer):
    def __init__(self) -> None:
        super().__init__(
            datastore=FakeRelationalDatastore(),
            storage_config=StorageConfig(),
        )
        self.relational_save_attempts = 0

    def _save_checkpoint_relational_once(self, checkpoint: ConversationCheckpoint) -> None:
        from sqlalchemy.exc import IntegrityError

        self.relational_save_attempts += 1
        if self.relational_save_attempts == 1:
            raise IntegrityError("statement", {}, Exception("duplicate latest row"))


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


def test_postgres_checkpoint_setup_creates_latest_turn_unique_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries: list[str] = []

    def record_query(connection_config: Any, query: str) -> None:
        queries.append(query)

    monkeypatch.setattr(
        checkpoint_datastore,
        "_execute_query_on_postgres_db",
        record_query,
    )

    connection_config: Any = object()
    checkpoint_datastore._prepare_postgres_checkpoint_datastore(connection_config, StorageConfig())

    assert len(queries) == 2
    assert "CREATE TABLE conversations" in queries[0]
    assert "CREATE UNIQUE INDEX conversations_last_turn_idx" in queries[1]
    assert "ON conversations (conversation_id)" in queries[1]
    assert "WHERE is_last_turn = 1" in queries[1]


def test_oracle_checkpoint_setup_creates_latest_turn_unique_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries: list[str] = []

    def record_query(connection_config: Any, query: str) -> None:
        queries.append(query)

    monkeypatch.setattr(
        checkpoint_datastore,
        "_execute_query_on_oracle_db",
        record_query,
    )

    connection_config: Any = object()
    checkpoint_datastore._prepare_oracle_checkpoint_datastore(connection_config, StorageConfig())

    assert len(queries) == 2
    assert "CREATE TABLE conversations" in queries[0]
    assert "CREATE UNIQUE INDEX conversations_last_turn_idx" in queries[1]
    assert "CASE WHEN is_last_turn = 1" in queries[1]
    assert "THEN conversation_id END" in queries[1]


def test_relational_checkpoint_save_retries_integrity_errors() -> None:
    checkpointer = IntegrityRetryCheckpointer()

    checkpointer.save(
        ConversationCheckpoint(
            checkpoint_id="checkpoint-1",
            conversation_id="conversation-1",
            component_id="component-1",
            created_at=0,
            state="state",
            metadata={},
        )
    )

    assert checkpointer.relational_save_attempts == 2


def test_checkpoint_serializes_exception_tool_result_content_as_text() -> None:
    agent = Agent(
        llm=DummyModel(),
        agent_id="checkpoint-exception-agent",
        name="checkpoint_exception_agent",
        description="Checkpoint exception agent.",
    )
    conversation = agent.start_conversation(conversation_id="checkpoint-exception-tool-result")
    conversation.message_list.append_message(
        Message(
            tool_result=ToolResult(
                content=DatastoreEntityError("datastore create failed"),
                tool_request_id="tool-call-1",
            ),
            message_type=MessageType.TOOL_RESULT,
        )
    )

    serialized_state = checkpoint_serialization._serialize_conversation_checkpoint_state(
        conversation
    )
    restored_conversation = checkpoint_serialization._deserialize_conversation_checkpoint_state(
        serialized_state,
        component=agent,
    )

    restored_tool_result = restored_conversation.get_last_message().tool_result
    assert restored_tool_result is not None
    assert restored_tool_result.content == "datastore create failed"


def test_agent_tool_response_messages_stringify_exception_content() -> None:
    message = AgentConversationExecutor._get_tool_response_message(
        content=DatastoreEntityError("datastore create failed"),
        tool_request_id="tool-call-1",
        agent_id="agent-1",
    )

    assert message.tool_result is not None
    assert message.tool_result.content == "datastore create failed"


def test_inmemory_checkpointer_can_save_load_list_and_delete_checkpoints() -> None:
    checkpointer = InMemoryCheckpointer()
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello from checkpointing."))

    conversation = flow.start_conversation(
        conversation_id="checkpoint-lifecycle", checkpointer=checkpointer
    )
    assert conversation.checkpointer is checkpointer

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
    assert restored_conversation.checkpointer is checkpointer
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


def test_checkpoint_restore_handles_messages_validation_without_runtime_name_error() -> None:
    checkpointer = InMemoryCheckpointer()
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello from checkpointing."))

    conversation = flow.start_conversation(
        conversation_id="checkpoint-messages-validation",
        checkpointer=checkpointer,
    )
    status = conversation.execute()
    assert isinstance(status, FinishedStatus)
    checkpoint_id = conversation.checkpoint_id
    assert checkpoint_id is not None

    restored_conversation = flow.start_conversation(
        conversation_id="checkpoint-messages-validation",
        checkpointer=checkpointer,
        messages=[],
    )
    assert restored_conversation.checkpoint_id == checkpoint_id

    with pytest.raises(ValueError, match="Cannot restore a checkpoint"):
        flow.start_conversation(
            conversation_id="checkpoint-messages-validation",
            checkpointer=checkpointer,
            messages=Message("new input"),
        )


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


def test_execute_can_skip_final_checkpoint_while_preserving_internal_checkpoints() -> None:
    checkpointer = InMemoryCheckpointer(
        checkpointing_interval=CheckpointingInterval.ALL_INTERNAL_TURNS
    )
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello internal only."))

    status = flow.start_conversation(
        conversation_id="skip-final-checkpoint",
        checkpointer=checkpointer,
    ).execute(_save_final_checkpoint=False)

    assert isinstance(status, FinishedStatus)
    checkpoints = checkpointer.list_checkpoints("skip-final-checkpoint")
    assert len(checkpoints) == 2
    assert [checkpoint.metadata["save_reason"] for checkpoint in checkpoints] == [
        "internal_turn_boundary",
        "internal_turn_boundary",
    ]


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


def test_checkpoint_serialization_context_registers_component_tree_as_external_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeSerializationContext:
        def __init__(self, root: Any) -> None:
            self.root = root
            self.external_refs: set[str] = set()
            self.recorded_refs: Dict[str, Dict[str, Any]] = {}

        @staticmethod
        def get_reference(obj: Any) -> str:
            obj_id = getattr(obj, "id", id(obj))
            return f"{obj.__class__.__name__.lower()}/{obj_id}"

        def register_external_reference(self, obj: Any) -> None:
            self.external_refs.add(self.get_reference(obj))

        def record_obj_dict(self, obj: Any, obj_as_dict: Dict[str, Any]) -> None:
            self.recorded_refs[self.get_reference(obj)] = obj_as_dict

    monkeypatch.setattr(
        checkpoint_serialization,
        "SerializationContext",
        _FakeSerializationContext,
    )

    flow = create_single_step_flow(OutputMessageStep(message_template="Hello external refs."))
    conversation = flow.start_conversation(conversation_id="checkpoint-external-refs")
    serialization_context = checkpoint_serialization._build_checkpoint_serialization_context(
        conversation
    )

    expected_component_refs = {
        _FakeSerializationContext.get_reference(component)
        for component in checkpoint_serialization._iter_component_tree(conversation.component)
    }

    assert serialization_context.external_refs == expected_component_refs
    assert serialization_context.recorded_refs == {}


def test_explicit_final_checkpoint_parameters_can_be_retried_after_save_fails() -> None:
    checkpointer = RecordingCheckpointer(fail_first_save=True)
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello overrides."))

    conversation = flow.start_conversation(
        conversation_id="checkpoint-final-overrides", checkpointer=checkpointer
    )

    with pytest.raises(RuntimeError, match="checkpoint save failed"):
        _save_conversation_checkpoint(
            conversation,
            save_reason="conversation_turn",
            checkpoint_id="final-checkpoint-id",
            metadata={"response_id": "resp-123"},
        )

    _save_conversation_checkpoint(
        conversation,
        save_reason="conversation_turn",
        checkpoint_id="final-checkpoint-id",
        metadata={"response_id": "resp-123"},
    )

    assert conversation.checkpoint_id == "final-checkpoint-id"
    checkpoint = checkpointer.load("checkpoint-final-overrides", "final-checkpoint-id")
    assert checkpoint.metadata["response_id"] == "resp-123"


def test_execute_final_checkpoint_parameters_are_applied_to_final_save() -> None:
    checkpointer = RecordingCheckpointer()
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello execute."))

    conversation = flow.start_conversation(
        conversation_id="checkpoint-final-execute",
        checkpointer=checkpointer,
    )
    status = conversation.execute(
        _final_checkpoint_id="final-checkpoint-id",
        _final_checkpoint_metadata={"response_id": "resp-123"},
    )

    assert isinstance(status, FinishedStatus)
    assert conversation.checkpoint_id == "final-checkpoint-id"
    checkpoint = checkpointer.load("checkpoint-final-execute", "final-checkpoint-id")
    assert checkpoint.metadata["response_id"] == "resp-123"
    assert checkpoint.metadata["save_reason"] == "conversation_turn"


def test_execute_async_does_not_save_final_checkpoint_when_execution_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpointer = RecordingCheckpointer()
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

    assert conversation.checkpoint_id is None
    assert checkpointer.saved_checkpoints == {}


def test_checkpoint_restore_rejects_conversations_from_other_components() -> None:
    original_flow = create_single_step_flow(OutputMessageStep(message_template="Hello original."))
    other_flow = create_single_step_flow(OutputMessageStep(message_template="Hello other."))
    checkpointer = StaticLoadCheckpointer(
        ConversationCheckpoint(
            checkpoint_id="checkpoint-1",
            conversation_id="checkpoint-other-component",
            component_id=original_flow.id,
            created_at=0,
            state="unused-because-component-mismatch-is-checked-first",
            metadata={},
        )
    )

    with pytest.raises(ValueError, match="started with another component"):
        other_flow.start_conversation(
            conversation_id="checkpoint-other-component",
            checkpointer=checkpointer,
        )


def test_checkpoint_restore_supports_fresh_component_with_same_stable_id() -> None:
    checkpointer = InMemoryCheckpointer()
    original_agent = Agent(
        llm=DummyModel(),
        agent_id="stable-checkpoint-agent",
        name="stable_checkpoint_agent",
        description="Stable checkpoint agent.",
        initial_message="Hello from the original agent.",
    )

    conversation = original_agent.start_conversation(
        conversation_id="checkpoint-stable-component",
        checkpointer=checkpointer,
    )
    first_status = conversation.execute()

    assert isinstance(first_status, UserMessageRequestStatus)
    first_checkpoint_id = conversation.checkpoint_id
    assert first_checkpoint_id is not None

    restarted_agent = Agent(
        llm=DummyModel(),
        agent_id="stable-checkpoint-agent",
        name="stable_checkpoint_agent",
        description="Stable checkpoint agent.",
        initial_message="Hello from the restarted agent.",
    )
    restored_conversation = restarted_agent.start_conversation(
        conversation_id="checkpoint-stable-component",
        checkpointer=checkpointer,
    )

    assert restored_conversation.component is restarted_agent
    assert restored_conversation.checkpoint_id == first_checkpoint_id
    assert isinstance(restored_conversation.status, UserMessageRequestStatus)


def test_checkpoint_restore_remaps_nested_agent_refs_after_restart() -> None:
    def build_parent_agent() -> tuple[Agent, Agent]:
        sub_agent = Agent(
            llm=DummyModel(fails_if_not_set=False),
            name="checkpoint_sub_agent",
            description="Checkpoint sub-agent.",
            initial_message="Hello from sub-agent.",
        )
        parent_agent = Agent(
            llm=DummyModel(fails_if_not_set=False),
            agent_id="stable-parent-agent",
            name="checkpoint_parent_agent",
            description="Checkpoint parent agent.",
            agents=[sub_agent],
            initial_message="Hello from parent.",
        )
        return parent_agent, sub_agent

    checkpointer = InMemoryCheckpointer()
    original_parent, original_sub_agent = build_parent_agent()
    original_conversation = original_parent.start_conversation(
        conversation_id="agent-nested-restart",
        checkpointer=checkpointer,
    )
    original_sub_conversation = original_sub_agent.start_conversation(
        conversation_id="agent-nested-restart-sub",
        _root_conversation_id=original_conversation.root_conversation_id,
    )
    original_conversation.state.current_sub_component_conversations[original_sub_agent.id] = (
        original_sub_conversation
    )
    checkpointer.save_conversation(original_conversation)

    restarted_parent, restarted_sub_agent = build_parent_agent()
    restored_conversation = restarted_parent.start_conversation(
        conversation_id="agent-nested-restart",
        checkpointer=checkpointer,
    )

    restored_sub_conversation = restored_conversation._get_sub_component_conversation(
        restarted_sub_agent
    )
    assert restored_sub_conversation is not None
    assert restored_sub_conversation.component is restarted_sub_agent
    assert list(restored_conversation.state.current_sub_component_conversations) == [
        restarted_sub_agent.id
    ]


def test_checkpoint_restore_remaps_managerworkers_nested_refs_after_restart() -> None:
    def build_managerworkers() -> tuple[ManagerWorkers, DummyModel]:
        manager_llm = DummyModel()
        manager_agent = Agent(
            llm=manager_llm,
            name="checkpoint_restart_manager_agent",
            description="Checkpoint restart manager.",
            initial_message="Hello from the manager.",
        )
        worker_agent = Agent(
            llm=DummyModel(fails_if_not_set=False),
            name="checkpoint_restart_worker_agent",
            description="Checkpoint restart worker.",
            custom_instruction="Help the manager.",
        )
        managerworkers = ManagerWorkers(
            group_manager=manager_agent,
            workers=[worker_agent],
            name="checkpoint_restart_managerworkers",
            id="stable-managerworkers",
        )
        return managerworkers, manager_llm

    checkpointer = InMemoryCheckpointer()
    original_managerworkers, _ = build_managerworkers()
    original_conversation = original_managerworkers.start_conversation(
        conversation_id="managerworkers-nested-restart",
        checkpointer=checkpointer,
    )
    first_status = original_conversation.execute()
    assert isinstance(first_status, UserMessageRequestStatus)

    restarted_managerworkers, restarted_manager_llm = build_managerworkers()
    restored_conversation = restarted_managerworkers.start_conversation(
        conversation_id="managerworkers-nested-restart",
        checkpointer=checkpointer,
    )

    main_subconversation = restored_conversation._get_main_subconversation()
    assert restored_conversation.component is restarted_managerworkers
    assert main_subconversation.component is restarted_managerworkers.manager_agent

    restarted_manager_llm.set_next_output("ManagerWorkers resumed successfully.")
    restored_conversation.append_user_message("Please continue.")
    restored_status = restored_conversation.execute()

    assert isinstance(restored_status, UserMessageRequestStatus)
    assert restored_conversation.get_last_message().content == (
        "ManagerWorkers resumed successfully."
    )


def test_checkpoint_restore_remaps_swarm_nested_refs_after_restart() -> None:
    def build_swarm() -> tuple[Swarm, DummyModel]:
        first_llm = DummyModel()
        first_agent = Agent(
            llm=first_llm,
            name="checkpoint_restart_swarm_first_agent",
            description="Checkpoint restart first swarm agent.",
            initial_message="Hello from the swarm.",
        )
        second_agent = Agent(
            llm=DummyModel(fails_if_not_set=False),
            name="checkpoint_restart_swarm_second_agent",
            description="Checkpoint restart second swarm agent.",
            custom_instruction="Help with delegated tasks.",
        )
        swarm = Swarm(
            first_agent=first_agent,
            relationships=[(first_agent, second_agent)],
            name="checkpoint_restart_swarm",
            id="stable-swarm",
        )
        return swarm, first_llm

    checkpointer = InMemoryCheckpointer()
    original_swarm, _ = build_swarm()
    original_conversation = original_swarm.start_conversation(
        conversation_id="swarm-nested-restart",
        checkpointer=checkpointer,
    )
    first_status = original_conversation.execute()
    assert isinstance(first_status, UserMessageRequestStatus)

    restarted_swarm, restarted_first_llm = build_swarm()
    restored_conversation = restarted_swarm.start_conversation(
        conversation_id="swarm-nested-restart",
        checkpointer=checkpointer,
    )

    main_thread_conversation = restored_conversation._get_main_thread_conversation()
    assert restored_conversation.component is restarted_swarm
    assert main_thread_conversation.component is restarted_swarm.first_agent

    restarted_first_llm.set_next_output("Swarm resumed successfully.")
    restored_conversation.append_user_message("Please continue.")
    restored_status = restored_conversation.execute()

    assert isinstance(restored_status, UserMessageRequestStatus)
    assert restored_conversation.get_last_message().content == "Swarm resumed successfully."


def test_restore_can_skip_attaching_live_checkpointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flow = create_single_step_flow(OutputMessageStep(message_template="Hello restore."))
    checkpoint_id = "checkpoint-no-attach-id"
    checkpointer = StaticLoadCheckpointer(
        ConversationCheckpoint(
            checkpoint_id=checkpoint_id,
            conversation_id="checkpoint-no-attach",
            component_id=flow.id,
            created_at=0,
            state="unused-because-deserialization-is-mocked",
            metadata={},
        )
    )

    monkeypatch.setattr(
        checkpoint_serialization,
        "_deserialize_conversation_checkpoint_state",
        lambda *args, **kwargs: flow.start_conversation(conversation_id="checkpoint-no-attach"),
    )

    restored_conversation = flow.start_conversation(
        conversation_id="checkpoint-no-attach",
        checkpoint_id=checkpoint_id,
        checkpointer=checkpointer,
        _attach_checkpointer=False,
    )

    assert restored_conversation.checkpointer is None
    assert restored_conversation.checkpoint_id == checkpoint_id


def test_legacy_serialized_conversation_id_restores_root_conversation_id() -> None:
    agent, _ = _build_checkpointable_agent(
        name="legacy_checkpoint_agent",
        initial_message="Hello from the past.",
    )
    conversation = agent.start_conversation(_root_conversation_id="legacy-root-conversation")

    assert conversation.root_conversation_id == "legacy-root-conversation"
    assert (
        _resolve_legacy_field_name(type(conversation), "root_conversation_id") == "conversation_id"
    )
    assert not hasattr(conversation, "conversation_id")


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
