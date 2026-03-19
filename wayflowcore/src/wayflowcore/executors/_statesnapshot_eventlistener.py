# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, Optional, cast

from wayflowcore.conversation import Conversation, _get_active_conversations
from wayflowcore.events import Event, EventListener
from wayflowcore.events.event import (
    AgentExecutionFinishedEvent,
    AgentExecutionIterationFinishedEvent,
    AgentExecutionIterationStartedEvent,
    AgentExecutionStartedEvent,
    ExceptionRaisedEvent,
    FlowExecutionFinishedEvent,
    FlowExecutionIterationFinishedEvent,
    FlowExecutionIterationStartedEvent,
    FlowExecutionStartedEvent,
    StateSnapshotEvent,
    ToolExecutionResultEvent,
    ToolExecutionStartEvent,
)
from wayflowcore.events.eventlistener import (
    get_event_listeners,
    record_event,
    register_event_listeners,
)
from wayflowcore.executors._events.event import EventType as ExecutionEventType
from wayflowcore.executors._executor import ExecutionInterruptedException
from wayflowcore.executors.executionstatus import ExecutionStatus
from wayflowcore.executors.statesnapshotpolicy import StateSnapshotInterval, StateSnapshotPolicy
from wayflowcore.serialization.conversation import (
    _UNSET,
    _serialize_conversation_state_with_runtime_overrides,
    dump_conversation_state,
    dump_variable_state,
    serialize_conversation_state,
)
from wayflowcore.tracing.span import AgentExecutionSpan, FlowExecutionSpan, get_current_span

logger = logging.getLogger(__name__)

_STATE_SNAPSHOT_RUNTIME = "wayflow"
_STATE_SNAPSHOT_SCHEMA_VERSION = 1
_STATE_SNAPSHOT_INTERVALS_BY_POLICY = {
    StateSnapshotInterval.CONVERSATION_TURNS: {
        StateSnapshotInterval.CONVERSATION_TURNS,
    },
    StateSnapshotInterval.TOOL_TURNS: {
        StateSnapshotInterval.CONVERSATION_TURNS,
        StateSnapshotInterval.TOOL_TURNS,
    },
    StateSnapshotInterval.NODE_TURNS: {
        StateSnapshotInterval.CONVERSATION_TURNS,
        StateSnapshotInterval.NODE_TURNS,
    },
    StateSnapshotInterval.ALL_INTERNAL_TURNS: {
        StateSnapshotInterval.CONVERSATION_TURNS,
        StateSnapshotInterval.TOOL_TURNS,
        StateSnapshotInterval.NODE_TURNS,
    },
}


_STATE_SNAPSHOT_POLICIES: ContextVar[Dict[str, StateSnapshotPolicy]] = ContextVar(
    "_STATE_SNAPSHOT_POLICIES",
    default={},
)
"""Execution-local mapping of active conversations to their effective snapshot policy."""

_STATE_SNAPSHOT_EXECUTION_ROOT_CONVERSATION_ID: ContextVar[Optional[str]] = ContextVar(
    "_STATE_SNAPSHOT_EXECUTION_ROOT_CONVERSATION_ID",
    default=None,
)
"""Runtime conversation id for the root conversation of the current snapshot-enabled run."""


def _get_state_snapshot_policies(
    return_copy: bool = True,
) -> Dict[str, StateSnapshotPolicy]:
    state_snapshot_policies = _STATE_SNAPSHOT_POLICIES.get()
    return state_snapshot_policies.copy() if return_copy else state_snapshot_policies


def _get_parent_state_snapshot_policy(
    conversation: Conversation,
) -> Optional[StateSnapshotPolicy]:
    active_conversations = _get_active_conversations(return_copy=False)
    if not active_conversations or active_conversations[-1] is conversation:
        return None
    return _get_state_snapshot_policy(active_conversations[-1])


def get_effective_state_snapshot_policy_for_conversation(
    conversation: Conversation,
    state_snapshot_policy: Optional[StateSnapshotPolicy],
) -> Optional[StateSnapshotPolicy]:
    return (
        state_snapshot_policy
        if state_snapshot_policy is not None
        else _get_parent_state_snapshot_policy(conversation)
    )


def _is_state_snapshot_execution_root(conversation: Conversation) -> bool:
    return _STATE_SNAPSHOT_EXECUTION_ROOT_CONVERSATION_ID.get() == conversation.id


def _get_state_snapshot_policy(
    conversation: Conversation,
) -> Optional[StateSnapshotPolicy]:
    return _get_state_snapshot_policies(return_copy=False).get(conversation.id)


@contextmanager
def _use_state_snapshot_policy(
    conversation: Conversation,
    state_snapshot_policy: Optional[StateSnapshotPolicy],
) -> Iterator[None]:
    # Copy-on-write is needed here because child anyio tasks inherit the current
    # context, including references to mutable ContextVar values.
    state_snapshot_policies = _get_state_snapshot_policies(return_copy=True)
    if state_snapshot_policy is None:
        state_snapshot_policies.pop(conversation.id, None)
    else:
        state_snapshot_policies[conversation.id] = state_snapshot_policy

    token = _STATE_SNAPSHOT_POLICIES.set(state_snapshot_policies)
    try:
        yield
    finally:
        _STATE_SNAPSHOT_POLICIES.reset(token)


@contextmanager
def _use_state_snapshot_execution_root(
    conversation: Conversation,
) -> Iterator[None]:
    current_root_conversation_id = _STATE_SNAPSHOT_EXECUTION_ROOT_CONVERSATION_ID.get()
    if current_root_conversation_id is not None:
        yield
        return

    token = _STATE_SNAPSHOT_EXECUTION_ROOT_CONVERSATION_ID.set(conversation.id)
    try:
        yield
    finally:
        _STATE_SNAPSHOT_EXECUTION_ROOT_CONVERSATION_ID.reset(token)


def _build_extra_state(
    conversation: Conversation,
    state_snapshot_policy: StateSnapshotPolicy,
) -> Optional[Dict[str, Any]]:
    if state_snapshot_policy.extra_state_builder is None:
        return None

    try:
        extra_state = state_snapshot_policy.extra_state_builder(conversation)
    except Exception:
        logger.warning(
            "Failed to build extra snapshot state for conversation '%s'",
            conversation.conversation_id,
            exc_info=True,
        )
        return None

    if extra_state is None:
        return None
    if not isinstance(extra_state, dict):
        logger.warning(
            "Expected extra snapshot state to be a dictionary for conversation '%s'",
            conversation.conversation_id,
        )
        return None

    try:
        return cast(Dict[str, Any], json.loads(json.dumps(extra_state)))
    except Exception:
        logger.warning(
            "Extra snapshot state is not JSON serializable for conversation '%s'",
            conversation.conversation_id,
            exc_info=True,
        )
        return None


def _get_snapshot_policy_for_interval(
    conversation: Conversation,
    required_snapshot_interval: StateSnapshotInterval,
) -> Optional[StateSnapshotPolicy]:
    state_snapshot_policy = _get_state_snapshot_policy(conversation)
    if state_snapshot_policy is None:
        return None

    snapshot_interval = state_snapshot_policy.state_snapshot_interval
    if snapshot_interval == StateSnapshotInterval.OFF:
        return None

    if required_snapshot_interval in _STATE_SNAPSHOT_INTERVALS_BY_POLICY[snapshot_interval]:
        return state_snapshot_policy
    return None


def _build_variable_state(
    conversation: Conversation,
    state_snapshot_policy: StateSnapshotPolicy,
) -> Optional[dict[str, Any]]:
    if not state_snapshot_policy.include_variable_state:
        return None

    try:
        return dump_variable_state(conversation)
    except Exception:
        logger.warning(
            "Failed to dump variable state for conversation '%s'",
            conversation.conversation_id,
            exc_info=True,
        )
        return None


def _build_state_snapshot_payload(
    conversation: Conversation,
    *,
    include_conversation_state: bool,
    status: object = _UNSET,
    status_handled: object = _UNSET,
) -> dict[str, Any]:
    # The snapshot payload should match the intended runtime view at the
    # boundary where it is emitted. Opening/tool/node snapshots mask any
    # previous turn status, and turn-end snapshots can override the runtime
    # fields before the live conversation object commits that new status.
    dumped_state = dump_conversation_state(
        conversation,
        status=status,
        status_handled=status_handled,
    )
    payload = {
        "runtime": _STATE_SNAPSHOT_RUNTIME,
        "schema_version": _STATE_SNAPSHOT_SCHEMA_VERSION,
        "conversation": dumped_state["conversation"],
        "execution": dumped_state["execution"],
    }
    if include_conversation_state:
        payload["conversation_state"] = (
            serialize_conversation_state(conversation)
            if status is _UNSET and status_handled is _UNSET
            else _serialize_conversation_state_with_runtime_overrides(
                conversation,
                status=cast(
                    Optional[ExecutionStatus],
                    conversation.status if status is _UNSET else status,
                ),
                status_handled=cast(
                    bool,
                    conversation.status_handled if status_handled is _UNSET else status_handled,
                ),
            )
        )
    return payload


def _record_state_snapshot(
    conversation: Conversation,
    required_snapshot_interval: StateSnapshotInterval,
    *,
    status: object = _UNSET,
    status_handled: object = _UNSET,
) -> None:
    state_snapshot_policy = _get_snapshot_policy_for_interval(
        conversation, required_snapshot_interval
    )
    if state_snapshot_policy is None:
        return

    if (
        required_snapshot_interval == StateSnapshotInterval.CONVERSATION_TURNS
        and not _is_state_snapshot_execution_root(conversation)
    ):
        # The conversation passed to `execute()` / `execute_async()` owns the
        # resumable turn-level checkpoint stream. Nested child conversations may
        # still emit internal tracing snapshots, but they do not emit competing
        # conversation-turn checkpoints for the same run.
        return

    # Snapshot delivery is part of the execution contract: downstream listener
    # or storage failures must propagate to the caller instead of being silently
    # converted into best-effort behavior.
    record_event(
        StateSnapshotEvent(
            conversation_id=conversation.conversation_id,
            state_snapshot=_build_state_snapshot_payload(
                conversation,
                include_conversation_state=(
                    required_snapshot_interval == StateSnapshotInterval.CONVERSATION_TURNS
                ),
                status=status,
                status_handled=status_handled,
            ),
            extra_state=_build_extra_state(conversation, state_snapshot_policy),
            variable_state=_build_variable_state(conversation, state_snapshot_policy),
        )
    )


class StateSnapshotEventListener(EventListener):
    """Emit state snapshots for the active conversation."""

    def __init__(
        self,
        conversation: Conversation,
        post_interrupts: bool,
    ) -> None:
        self.conversation = conversation
        self.post_interrupts = post_interrupts

    def _record_snapshot(
        self,
        required_snapshot_interval: StateSnapshotInterval,
        *,
        status: object = None,
        status_handled: object = False,
    ) -> None:
        _record_state_snapshot(
            self.conversation,
            required_snapshot_interval,
            status=status,
            status_handled=status_handled,
        )

    def _handle_pre_interrupt_event(
        self,
        event: Event,
    ) -> None:
        # Agents do not expose node execution events, so NODE_TURNS maps to
        # flow iteration boundaries and agent iteration boundaries.
        match event:
            case AgentExecutionStartedEvent() | FlowExecutionStartedEvent():
                self._record_snapshot(StateSnapshotInterval.CONVERSATION_TURNS)
            case ToolExecutionStartEvent() | ToolExecutionResultEvent():
                self._record_snapshot(StateSnapshotInterval.TOOL_TURNS)
            case (
                FlowExecutionIterationStartedEvent()
                | FlowExecutionIterationFinishedEvent()
                | AgentExecutionIterationStartedEvent()
                | AgentExecutionIterationFinishedEvent()
            ):
                self._record_snapshot(StateSnapshotInterval.NODE_TURNS)

    def _should_record_interrupted_turn_end_snapshot(
        self,
    ) -> bool:
        return (
            bool(self.conversation.state.events)
            and (self.conversation.state.events[-1].type == ExecutionEventType.EXECUTION_END)
            and isinstance(get_current_span(), (FlowExecutionSpan, AgentExecutionSpan))
        )

    def _owns_current_conversation(self, current_conversation: Conversation) -> bool:
        # This is the intended extension point for future multi-agent snapshot
        # ownership rules. Today a listener only reacts for its own active
        # conversation. Follow-up PRs can widen this here to parent wrapper
        # conversations (for example swarms or manager-workers) without
        # changing the snapshot emission logic elsewhere in this listener.
        return current_conversation.id == self.conversation.id

    def _handle_post_interrupt_event(self, event: Event) -> None:
        match event:
            case FlowExecutionFinishedEvent(
                execution_status=execution_status
            ) | AgentExecutionFinishedEvent(execution_status=execution_status):
                self._record_snapshot(
                    StateSnapshotInterval.CONVERSATION_TURNS,
                    status=execution_status,
                    status_handled=False,
                )
            case ExceptionRaisedEvent(exception=ExecutionInterruptedException() as exception):
                if self._should_record_interrupted_turn_end_snapshot():
                    self._record_snapshot(
                        StateSnapshotInterval.CONVERSATION_TURNS,
                        status=exception.execution_status,
                        status_handled=False,
                    )

    def __call__(self, event: Event) -> None:
        if isinstance(event, StateSnapshotEvent):
            return

        active_conversations = _get_active_conversations(return_copy=False)
        if not active_conversations:
            return

        current_conversation = active_conversations[-1]
        if not self._owns_current_conversation(current_conversation):
            return

        if self.post_interrupts:
            self._handle_post_interrupt_event(event)
        else:
            self._handle_pre_interrupt_event(event)


@contextmanager
def get_state_snapshot_event_listener_context_for_conversation(
    conversation: Conversation,
    *,
    post_interrupts: bool,
) -> Iterator[StateSnapshotEventListener]:
    current_listener = next(
        (
            event_listener
            for event_listener in get_event_listeners()
            if isinstance(event_listener, StateSnapshotEventListener)
            and event_listener.conversation.id == conversation.id
            and event_listener.post_interrupts == post_interrupts
        ),
        None,
    )

    if current_listener is not None:
        yield current_listener
    else:
        listener = StateSnapshotEventListener(conversation, post_interrupts=post_interrupts)
        with register_event_listeners([listener]):
            yield listener


@contextmanager
def get_state_snapshot_execution_context_for_conversation(
    conversation: Conversation,
    state_snapshot_policy: Optional[StateSnapshotPolicy],
) -> Iterator[None]:
    """
    Activate the effective snapshot policy for one `conversation.execute(...)` turn.

    Child conversations inherit the currently active parent policy unless they
    explicitly override it. Only the conversation that started the current
    snapshot-enabled execution emits conversation-turn checkpoints; nested
    children may still emit internal snapshots that describe their own runtime
    state. When snapshots are enabled, listener registration happens here in the
    runtime order the execution model depends on:
    1. pre-interrupt snapshot listener
    2. interrupts listener
    3. post-interrupt snapshot listener
    """
    active_state_snapshot_policy = get_effective_state_snapshot_policy_for_conversation(
        conversation,
        state_snapshot_policy,
    )

    with _use_state_snapshot_policy(conversation, active_state_snapshot_policy):
        if active_state_snapshot_policy is None:
            yield
            return

        from wayflowcore.executors._interrupts_eventlistener import (
            get_interrupts_event_listener_context_for_conversation,
        )

        with (
            _use_state_snapshot_execution_root(conversation),
            get_state_snapshot_event_listener_context_for_conversation(
                conversation,
                post_interrupts=False,
            ),
            get_interrupts_event_listener_context_for_conversation(conversation),
            get_state_snapshot_event_listener_context_for_conversation(
                conversation,
                post_interrupts=True,
            ),
        ):
            yield
