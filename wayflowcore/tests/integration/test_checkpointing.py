# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, Optional

import pytest

from wayflowcore.agent import Agent
from wayflowcore.checkpointing import InMemoryCheckpointer
from wayflowcore.checkpointing.checkpoint_state import _save_live_conversation_checkpoint
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.conversation import Conversation
from wayflowcore.executors._events.event import Event, EventType
from wayflowcore.executors._executionstate import ConversationExecutionState
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.executors.interrupts.executioninterrupt import (
    FlexibleExecutionInterrupt,
    FlowExecutionInterrupt,
    InterruptedExecutionStatus,
    _AllEventsInterruptMixin,
)
from wayflowcore.flow import Flow
from wayflowcore.flowbuilder import FlowBuilder
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.managerworkers import ManagerWorkers
from wayflowcore.steps import FlowExecutionStep, OutputMessageStep
from wayflowcore.swarm import Swarm

from ..serialization.test_assistant_serialization import create_flow
from ..testhelpers.dummy import DoNothingStep, DummyModel


def _build_nested_flow(
    *,
    child_first_step_name: str,
    child_second_step_name: str,
    child_flow_name: str,
    parent_step_name: str,
    parent_flow_name: str,
) -> Flow:
    first_step = DoNothingStep(name=child_first_step_name)
    second_step = DoNothingStep(name=child_second_step_name)
    child_flow = FlowBuilder.build_linear_flow(
        [first_step, second_step],
        name=child_flow_name,
        flow_id=child_flow_name,
    )
    parent_step = FlowExecutionStep(child_flow, name=parent_step_name)
    return FlowBuilder.build_linear_flow(
        [parent_step],
        flow_id=parent_flow_name,
        name=parent_flow_name,
    )


def _start_interrupted_flow_conversation(
    flow: Flow,
    *,
    conversation_id: str,
    interrupt_step_name: str,
    checkpointer: InMemoryCheckpointer | None = None,
):
    conversation = flow.start_conversation(
        conversation_id=conversation_id,
        checkpointer=checkpointer,
    )
    status = conversation.execute(
        execution_interrupts=[_OnStepStartExecutionInterrupt(interrupt_step_name)]
    )
    assert isinstance(status, InterruptedExecutionStatus)
    return conversation


class _OnStepStartExecutionInterrupt(
    _AllEventsInterruptMixin, FlexibleExecutionInterrupt, FlowExecutionInterrupt
):
    def __init__(self, step_name: str) -> None:
        self.step_name = step_name
        self.triggered = False
        self.current_event: Optional[Event] = None
        super().__init__()

    def _return_status_if_condition_is_met(
        self, state: ConversationExecutionState, conversation: Conversation
    ) -> Optional[InterruptedExecutionStatus]:
        if (
            self.current_event is not None
            and self.current_event.type == EventType.STEP_EXECUTION_START
            and self.step_name == conversation.current_step_name
            and not self.triggered
        ):
            self.triggered = True
            return InterruptedExecutionStatus(
                interrupter=self,
                reason=f"Start {self.step_name}",
                _conversation_id=conversation.id,
            )
        return None

    def on_event(
        self, event: Event, state: ConversationExecutionState, conversation: Conversation
    ) -> Optional[InterruptedExecutionStatus]:
        self.current_event = event
        return super().on_event(event, state, conversation)

    def _serialize_to_dict(self, serialization_context) -> Dict[str, Any]:
        return {"step_name": self.step_name}

    @classmethod
    def _deserialize_from_dict(cls, input_dict: Dict[str, Any], deserialization_context):
        return cls(step_name=input_dict["step_name"])


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
        agent_id=name,
    )
    return agent, llm


def _build_checkpointable_agent_component() -> tuple[Agent, DummyModel]:
    return _build_checkpointable_agent(
        name="checkpoint_agent",
        initial_message="Hello from the agent.",
    )


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
        agent_id="checkpoint_swarm_second_agent",
    )
    swarm = Swarm(
        first_agent=first_agent,
        relationships=[(first_agent, second_agent)],
        name="checkpoint_swarm",
        id="checkpoint_swarm",
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
        agent_id="checkpoint_worker_agent",
    )
    managerworkers = ManagerWorkers(
        group_manager=manager_agent,
        workers=[worker_agent],
        name="checkpoint_managerworkers",
        id="checkpoint_managerworkers",
    )
    return managerworkers, manager_llm


def test_flow_checkpoint_restore_rejects_generated_step_name_reinstantiation() -> None:
    checkpointer = InMemoryCheckpointer()

    def build_flow() -> tuple[Flow, OutputMessageStep]:
        first_step = DoNothingStep()
        second_step = OutputMessageStep(message_template="Generated step resumed.")
        first_step.id = "generated_step_restore_flow_first_step"
        second_step.id = "generated_step_restore_flow_second_step"
        return (
            Flow(
                begin_step=first_step,
                steps=[first_step, second_step],
                control_flow_edges=[
                    ControlFlowEdge(source_step=first_step, destination_step=second_step),
                    ControlFlowEdge(source_step=second_step, destination_step=None),
                ],
                name="generated_step_restore_flow",
                flow_id="generated_step_restore_flow",
            ),
            second_step,
        )

    original_flow, original_second_step = build_flow()
    assert IdGenerator.is_auto_generated(original_second_step.name)
    conversation = original_flow.start_conversation(
        conversation_id="generated-step-name-restore",
        checkpointer=checkpointer,
    )
    first_status = conversation.execute(
        execution_interrupts=[_OnStepStartExecutionInterrupt(original_second_step.name)]
    )

    assert isinstance(first_status, InterruptedExecutionStatus)
    assert checkpointer.load_latest(conversation.conversation_id) is not None

    restarted_flow, _ = build_flow()

    with pytest.raises(ValueError, match="stable step names"):
        restarted_flow.start_conversation(
            conversation_id=conversation.conversation_id,
            checkpointer=checkpointer,
        )


def test_flow_checkpoint_restore_relinks_nested_flow_parent_for_interrupt_inheritance() -> None:
    checkpointer = InMemoryCheckpointer()

    def build_flow() -> Flow:
        return _build_nested_flow(
            child_first_step_name="child_first_step",
            child_second_step_name="child_second_step",
            child_flow_name="checkpoint_child_flow",
            parent_step_name="parent_flow_step",
            parent_flow_name="checkpoint_parent_flow",
        )

    original_flow = build_flow()
    conversation = _start_interrupted_flow_conversation(
        original_flow,
        conversation_id="flow-parent-link-restore",
        interrupt_step_name="child_first_step",
        checkpointer=checkpointer,
    )
    assert checkpointer.load_latest(conversation.conversation_id) is not None

    restarted_flow = build_flow()
    restored_conversation = restarted_flow.start_conversation(
        conversation_id=conversation.conversation_id,
        checkpointer=checkpointer,
    )
    restored_child_conversation = restored_conversation._get_current_sub_conversation(
        restarted_flow.steps["parent_flow_step"]
    )
    assert restored_child_conversation is not None
    assert restored_child_conversation._get_parent_conversation() is restored_conversation
    assert restored_conversation.id == restored_conversation.conversation_id
    assert restored_child_conversation.id != restored_conversation.id
    assert restored_child_conversation.conversation_id == restored_conversation.conversation_id

    restored_status = restored_conversation.execute(
        execution_interrupts=[_OnStepStartExecutionInterrupt("child_second_step")]
    )

    assert isinstance(restored_status, InterruptedExecutionStatus)
    assert restored_status.reason == "Start child_second_step"


def test_flow_checkpointing_supports_resume_and_time_travel() -> None:
    checkpointer = InMemoryCheckpointer()
    flow = create_flow()

    conversation = flow.start_conversation(
        conversation_id="flow-checkpoint", checkpointer=checkpointer
    )
    first_status = conversation.execute()

    assert isinstance(first_status, UserMessageRequestStatus)
    first_checkpoint = checkpointer.load_latest(conversation.conversation_id)
    assert first_checkpoint is not None
    first_checkpoint_id = first_checkpoint.checkpoint_id
    assert conversation.checkpoint_id == first_checkpoint_id

    restored_conversation = flow.start_conversation(
        conversation_id=conversation.conversation_id,
        checkpointer=checkpointer,
    )
    assert restored_conversation.checkpoint_id == first_checkpoint_id
    assert isinstance(restored_conversation.status, UserMessageRequestStatus)

    restored_conversation.append_user_message("continue")
    restored_status = restored_conversation.execute()
    assert isinstance(restored_status, FinishedStatus)

    rewound_conversation = flow.start_conversation(
        conversation_id=conversation.conversation_id,
        checkpointer=checkpointer,
        checkpoint_id=first_checkpoint_id,
    )
    assert len(rewound_conversation.get_messages()) < len(restored_conversation.get_messages())
    rewound_conversation.append_user_message("rewind")
    rewound_status = rewound_conversation.execute()
    assert isinstance(rewound_status, FinishedStatus)


@pytest.mark.parametrize(
    ("builder", "conversation_id"),
    [
        (_build_checkpointable_agent_component, "agent-checkpoint"),
        (_build_checkpointable_swarm, "swarm-checkpoint"),
        (_build_checkpointable_managerworkers, "managerworkers-checkpoint"),
    ],
)
def test_multi_agent_checkpointing_supports_resume_and_time_travel(
    builder,
    conversation_id: str,
) -> None:
    checkpointer = InMemoryCheckpointer()
    component, llm = builder()
    resumed_output = "Checkpoint resumed successfully."
    rewound_output = "Checkpoint rewound successfully."

    conversation = component.start_conversation(
        conversation_id=conversation_id,
        checkpointer=checkpointer,
    )
    first_status = conversation.execute()

    assert isinstance(first_status, UserMessageRequestStatus)
    first_checkpoint = checkpointer.load_latest(conversation.conversation_id)
    assert first_checkpoint is not None
    first_checkpoint_id = first_checkpoint.checkpoint_id
    assert conversation.checkpoint_id == first_checkpoint_id

    restored_conversation = component.start_conversation(
        conversation_id=conversation.conversation_id,
        checkpointer=checkpointer,
    )
    assert restored_conversation.checkpoint_id == first_checkpoint_id
    llm.set_next_output(resumed_output)
    restored_conversation.append_user_message("Please continue.")
    restored_status = restored_conversation.execute()
    assert isinstance(restored_status, UserMessageRequestStatus)
    assert restored_conversation.get_last_message().content == resumed_output

    rewound_conversation = component.start_conversation(
        conversation_id=conversation.conversation_id,
        checkpointer=checkpointer,
        checkpoint_id=first_checkpoint_id,
    )
    assert rewound_conversation.checkpoint_id == first_checkpoint_id
    llm.set_next_output(rewound_output)
    rewound_conversation.append_user_message("Try again.")
    rewound_status = rewound_conversation.execute()
    assert isinstance(rewound_status, UserMessageRequestStatus)
    assert rewound_conversation.get_last_message().content == rewound_output


def test_swarm_checkpoint_restore_rebuilds_generated_agent_name_threads() -> None:
    checkpointer = InMemoryCheckpointer()

    def build_swarm() -> tuple[Swarm, Agent, Agent]:
        first_agent = Agent(
            llm=DummyModel(fails_if_not_set=False),
            description="Swarm first agent",
            custom_instruction="Route work to another agent.",
            agent_id="checkpoint_generated_name_swarm_first_agent",
        )
        second_agent = Agent(
            llm=DummyModel(fails_if_not_set=False),
            description="Swarm second agent",
            custom_instruction="Handle delegated work.",
            agent_id="checkpoint_generated_name_swarm_second_agent",
        )
        return (
            Swarm(
                first_agent=first_agent,
                relationships=[(first_agent, second_agent)],
                name="checkpoint_generated_name_swarm",
                id="checkpoint_generated_name_swarm",
            ),
            first_agent,
            second_agent,
        )

    original_swarm, original_first_agent, original_second_agent = build_swarm()
    conversation = original_swarm.start_conversation(
        conversation_id="swarm-generated-agent-name-restart",
        checkpointer=checkpointer,
    )
    original_thread = conversation.state.agents_and_threads[original_first_agent.name][
        original_second_agent.name
    ]
    conversation.state._create_subconversation_for_thread(original_thread)
    conversation.state.current_thread = original_thread
    _save_live_conversation_checkpoint(checkpointer, conversation)

    restarted_swarm, restarted_first_agent, restarted_second_agent = build_swarm()

    restored_conversation = restarted_swarm.start_conversation(
        conversation_id=conversation.conversation_id, checkpointer=checkpointer
    )
    assert restored_conversation.state.current_thread is not None
    assert restored_conversation.state.current_thread.identifier == (
        f"{restarted_first_agent.name}#{restarted_second_agent.name}"
    )


def test_agent_checkpoint_restore_relinks_current_flow_parent() -> None:
    checkpointer = InMemoryCheckpointer()

    def build_agent() -> tuple[Agent, Flow]:
        parent_flow = _build_nested_flow(
            child_first_step_name="agent_child_first_step",
            child_second_step_name="agent_child_second_step",
            child_flow_name="checkpoint_agent_child_flow",
            parent_step_name="agent_parent_flow_step",
            parent_flow_name="checkpoint_agent_parent_flow",
        )
        agent = Agent(
            llm=DummyModel(fails_if_not_set=False),
            name="checkpoint_flow_agent",
            description="Agent with a nested flow",
            custom_instruction="Use the nested flow.",
            flows=[parent_flow],
            initial_message=None,
            agent_id="checkpoint_flow_agent",
        )
        return agent, parent_flow

    original_agent, original_parent_flow = build_agent()
    conversation = original_agent.start_conversation(
        conversation_id="agent-current-flow-restore",
        checkpointer=checkpointer,
    )
    parent_flow_conversation = _start_interrupted_flow_conversation(
        original_parent_flow,
        conversation_id=conversation.conversation_id,
        interrupt_step_name="agent_child_first_step",
    )
    conversation.state.current_flow_conversation = parent_flow_conversation
    _save_live_conversation_checkpoint(checkpointer, conversation)

    restarted_agent, restarted_parent_flow = build_agent()
    restored_conversation = restarted_agent.start_conversation(
        conversation_id=conversation.conversation_id,
        checkpointer=checkpointer,
    )

    restored_parent_flow_conversation = restored_conversation.state.current_flow_conversation
    assert restored_parent_flow_conversation is not None
    restored_child_conversation = restored_parent_flow_conversation._get_current_sub_conversation(
        restarted_parent_flow.steps["agent_parent_flow_step"]
    )
    assert restored_child_conversation is not None
    assert (
        restored_child_conversation._get_parent_conversation() is restored_parent_flow_conversation
    )


def test_managerworkers_checkpoint_restore_rejects_nested_generated_agent_names() -> None:
    checkpointer = InMemoryCheckpointer()

    def build_managerworkers() -> tuple[ManagerWorkers, Agent, ManagerWorkers, Agent, Agent]:
        nested_manager_agent = Agent(
            llm=DummyModel(fails_if_not_set=False),
            description="Nested generated manager agent",
            custom_instruction="Assign nested work to worker agents.",
            agent_id="checkpoint_nested_generated_name_manager_agent",
        )
        nested_worker_agent = Agent(
            llm=DummyModel(fails_if_not_set=False),
            description="Nested generated worker agent",
            custom_instruction="Handle nested delegated work.",
            agent_id="checkpoint_nested_generated_name_worker_agent",
        )
        nested_managerworkers = ManagerWorkers(
            group_manager=nested_manager_agent,
            workers=[nested_worker_agent],
            name="checkpoint_nested_generated_name_managerworkers",
            id="checkpoint_nested_generated_name_managerworkers",
        )
        outer_manager_agent = Agent(
            llm=DummyModel(fails_if_not_set=False),
            description="Outer generated manager agent",
            custom_instruction="Assign work to nested manager-workers.",
            agent_id="checkpoint_outer_generated_name_manager_agent",
        )
        return (
            ManagerWorkers(
                group_manager=outer_manager_agent,
                workers=[nested_managerworkers],
                name="checkpoint_outer_generated_name_managerworkers",
                id="checkpoint_outer_generated_name_managerworkers",
            ),
            outer_manager_agent,
            nested_managerworkers,
            nested_manager_agent,
            nested_worker_agent,
        )

    (
        original_managerworkers,
        original_outer_manager_agent,
        original_nested_managerworkers,
        original_nested_manager_agent,
        original_nested_worker_agent,
    ) = build_managerworkers()
    conversation = original_managerworkers.start_conversation(
        conversation_id="managerworkers-nested-generated-agent-name-restart",
        checkpointer=checkpointer,
    )
    nested_conversation = conversation.state._create_subconversation_for_agent(
        original_nested_managerworkers
    )
    nested_conversation.state._create_subconversation_for_agent(original_nested_worker_agent)
    conversation.state.current_agent_name = original_nested_managerworkers.name
    nested_conversation.state.current_agent_name = original_nested_worker_agent.name
    _save_live_conversation_checkpoint(checkpointer, conversation)

    restarted_managerworkers, *_ = build_managerworkers()

    with pytest.raises(ValueError, match="stable agent names"):
        restarted_managerworkers.start_conversation(
            conversation_id=conversation.conversation_id,
            checkpointer=checkpointer,
        )
