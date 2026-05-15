# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import TYPE_CHECKING, Any, Dict, Iterable, Iterator, List, Optional, Sequence

from wayflowcore.idgeneration import IdGenerator
from wayflowcore.serialization.context import DeserializationContext, SerializationContext

if TYPE_CHECKING:
    from wayflowcore.component import Component
    from wayflowcore.conversation import Conversation


CHECKPOINT_COMPONENT_REFERENCES_KEY = "component_references"

_COMPONENT_TYPE_KEY = "component_type"
_COMPONENT_NAME_KEY = "name"
_COMPONENT_STABLE_IDS_KEY = "stable_ids"


def iter_checkpoint_conversation_graph(
    root_conversation: "Conversation",
) -> Sequence["Conversation"]:
    visited_conversation_ids: set[str] = set()
    queue: List["Conversation"] = [root_conversation]
    ordered_conversations: List["Conversation"] = []

    while queue:
        conversation = queue.pop()
        if conversation.id in visited_conversation_ids:
            continue
        visited_conversation_ids.add(conversation.id)
        ordered_conversations.append(conversation)
        queue.extend(conversation._get_all_sub_conversations())

    return ordered_conversations


def _iter_checkpoint_child_components(component: "Component") -> Iterator["Component"]:
    from wayflowcore.agent import Agent
    from wayflowcore.component import Component
    from wayflowcore.flow import Flow
    from wayflowcore.managerworkers import ManagerWorkers
    from wayflowcore.steps.agentexecutionstep import AgentExecutionStep
    from wayflowcore.swarm import Swarm

    if isinstance(component, Agent):
        for agent_child_component in [*component.agents, *component.flows]:
            if isinstance(agent_child_component, Component):
                yield agent_child_component
        return
    elif isinstance(component, Flow):
        for step in component.steps.values():
            if isinstance(step, AgentExecutionStep) and isinstance(step.agent, Component):
                yield step.agent
            for sub_flow in step.sub_flows() or []:
                if isinstance(sub_flow, Component):
                    yield sub_flow
        return
    elif isinstance(component, ManagerWorkers):
        for manager_child_component in [component.manager_agent, *component.workers]:
            if isinstance(manager_child_component, Component):
                yield manager_child_component
        return
    elif isinstance(component, Swarm):
        for swarm_child_component in component._agent_by_name.values():
            if isinstance(swarm_child_component, Component):
                yield swarm_child_component


def iter_checkpoint_component_tree(component: "Component") -> Sequence["Component"]:
    visited_component_refs: set[str] = set()
    ordered_components: List["Component"] = []
    queue: List["Component"] = [component]

    while queue:
        current_component = queue.pop()
        current_component_ref = SerializationContext.get_reference(current_component)
        if current_component_ref in visited_component_refs:
            continue
        visited_component_refs.add(current_component_ref)
        ordered_components.append(current_component)
        queue.extend(_iter_checkpoint_child_components(current_component))

    return ordered_components


def _stable_component_name(component: "Component") -> Optional[str]:
    component_name = getattr(component, "name", None)
    if not isinstance(component_name, str) or IdGenerator.is_auto_generated(component_name):
        return None
    return component_name


def build_checkpoint_component_references(
    root_component: "Component",
    *,
    root_component_id: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    component_references: Dict[str, Dict[str, Any]] = {}
    for component in iter_checkpoint_component_tree(root_component):
        stable_ids = [component.id]
        if component is root_component and root_component_id is not None:
            stable_ids.append(root_component_id)

        descriptor: Dict[str, Any] = {
            _COMPONENT_TYPE_KEY: component.__class__.__name__,
            _COMPONENT_STABLE_IDS_KEY: sorted(set(stable_ids)),
        }
        component_name = _stable_component_name(component)
        if component_name is not None:
            descriptor[_COMPONENT_NAME_KEY] = component_name
        component_references[SerializationContext.get_reference(component)] = descriptor
    return component_references


def _component_reference_for_id(component: "Component", component_id: str) -> str:
    return f"{component.__class__.__name__.lower()}/{component_id}"


def _add_unique_index_value(
    index: Dict[tuple[str, str], Optional["Component"]],
    key: tuple[str, str],
    component: "Component",
) -> None:
    existing_component = index.get(key)
    if existing_component is component:
        return
    if key in index:
        index[key] = None
    else:
        index[key] = component


def _build_current_component_index(
    current_components: Sequence["Component"],
    *,
    root_component: "Component",
    root_component_id_aliases: Iterable[str],
) -> Dict[tuple[str, str], Optional["Component"]]:
    current_components_by_identity: Dict[tuple[str, str], Optional["Component"]] = {}
    for current_component in current_components:
        component_type = current_component.__class__.__name__
        _add_unique_index_value(
            current_components_by_identity,
            (component_type, current_component.id),
            current_component,
        )

        component_name = _stable_component_name(current_component)
        if component_name is not None:
            _add_unique_index_value(
                current_components_by_identity,
                (component_type, component_name),
                current_component,
            )

    root_component_type = root_component.__class__.__name__
    for root_component_id_alias in root_component_id_aliases:
        current_components_by_identity[(root_component_type, root_component_id_alias)] = (
            root_component
        )

    return current_components_by_identity


def register_checkpoint_component_references(
    *,
    deserialization_context: DeserializationContext,
    root_component: Optional["Component"],
    component_references: Any,
    root_component_id_aliases: Optional[Sequence[str]] = None,
) -> None:
    if root_component is None:
        return

    root_component_id_aliases = root_component_id_aliases or []
    current_components = iter_checkpoint_component_tree(root_component)
    for current_tree_component in current_components:
        deserialization_context.recorddeserialized_object(
            SerializationContext.get_reference(current_tree_component),
            current_tree_component,
        )
    for root_component_id_alias in root_component_id_aliases:
        deserialization_context.recorddeserialized_object(
            _component_reference_for_id(root_component, root_component_id_alias),
            root_component,
        )

    if not isinstance(component_references, dict):
        return

    current_components_by_identity = _build_current_component_index(
        current_components,
        root_component=root_component,
        root_component_id_aliases=root_component_id_aliases,
    )

    for serialized_reference, descriptor in component_references.items():
        if not isinstance(serialized_reference, str) or not isinstance(descriptor, dict):
            continue

        component_type = descriptor.get(_COMPONENT_TYPE_KEY)
        if not isinstance(component_type, str):
            continue

        matched_component: Optional["Component"] = None
        stable_ids = descriptor.get(_COMPONENT_STABLE_IDS_KEY)
        if isinstance(stable_ids, list):
            for stable_id in stable_ids:
                if not isinstance(stable_id, str):
                    continue
                matched_component = current_components_by_identity.get((component_type, stable_id))
                if matched_component is not None:
                    break

        if matched_component is None:
            component_name = descriptor.get(_COMPONENT_NAME_KEY)
            if isinstance(component_name, str):
                matched_component = current_components_by_identity.get(
                    (component_type, component_name)
                )

        if matched_component is not None:
            deserialization_context.recorddeserialized_object(
                serialized_reference,
                matched_component,
            )


def normalize_restored_component_keyed_state(conversation: "Conversation") -> None:
    for sub_conversation in iter_checkpoint_conversation_graph(conversation):
        state = getattr(sub_conversation, "state", None)
        if state is None:
            continue
        sub_component_conversations = getattr(
            state,
            "current_sub_component_conversations",
            None,
        )
        if not isinstance(sub_component_conversations, dict):
            continue

        rekeyed_sub_component_conversations: Dict[str, Any] = {}
        for child_conversation in sub_component_conversations.values():
            child_component = getattr(child_conversation, "component", None)
            child_component_id = getattr(child_component, "id", None)
            if not isinstance(child_component_id, str):
                break
            rekeyed_sub_component_conversations[child_component_id] = child_conversation
        else:
            setattr(
                state,
                "current_sub_component_conversations",
                rekeyed_sub_component_conversations,
            )
