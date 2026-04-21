# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, cast

import yaml

from wayflowcore.serialization import autodeserialize, serialize_to_dict
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import autodeserialize_from_dict

if TYPE_CHECKING:
    from wayflowcore.component import Component
    from wayflowcore.conversation import Conversation


_CHECKPOINT_ENVELOPE_FORMAT = "wayflow-conversation-checkpoint"
_CHECKPOINT_ENVELOPE_VERSION = 1


def _iter_conversation_graph(root_conversation: "Conversation") -> Sequence["Conversation"]:
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


def _ensure_checkpointing_supported(conversation: "Conversation") -> None:
    from wayflowcore.ociagent import OciAgent

    for sub_conversation in _iter_conversation_graph(conversation):
        if isinstance(sub_conversation.component, OciAgent):
            raise NotImplementedError(
                "Checkpointing conversations that contain `OciAgent` is not supported yet."
            )


def _iter_component_tree(component: "Component") -> Sequence["Component"]:
    from wayflowcore.component import Component

    def _iter_nested_components(value: Any) -> List["Component"]:
        if isinstance(value, Component):
            return [value]
        if isinstance(value, dict):
            nested_components: List["Component"] = []
            for nested_value in value.values():
                nested_components.extend(_iter_nested_components(nested_value))
            return nested_components
        if isinstance(value, (list, tuple, set)):
            nested_components = []
            for nested_value in value:
                nested_components.extend(_iter_nested_components(nested_value))
            return nested_components
        return []

    visited_component_ids: set[str] = set()
    ordered_components: List["Component"] = []
    queue: List["Component"] = [component]

    while queue:
        current_component = queue.pop()
        current_component_ref = SerializationContext.get_reference(current_component)
        if current_component_ref in visited_component_ids:
            continue
        visited_component_ids.add(current_component_ref)
        ordered_components.append(current_component)

        all_public_attrs = {
            name: value
            for name, value in vars(current_component).items()
            if not name.startswith("_")
        }
        for attr in all_public_attrs.values():
            queue.extend(_iter_nested_components(attr))

    return ordered_components


def _build_checkpoint_serialization_context(conversation: "Conversation") -> SerializationContext:
    serialization_context = SerializationContext(root=conversation)
    for component in _iter_component_tree(conversation.component):
        serialization_context.register_external_reference(component)
    return serialization_context


def _serialize_conversation_checkpoint_state(conversation: "Conversation") -> str:
    _ensure_checkpointing_supported(conversation)

    serialized_conversation = serialize_to_dict(
        conversation,
        serialization_context=_build_checkpoint_serialization_context(conversation),
    )

    envelope = {
        "checkpoint_format": _CHECKPOINT_ENVELOPE_FORMAT,
        "version": _CHECKPOINT_ENVELOPE_VERSION,
        "conversation": serialized_conversation,
    }
    return yaml.safe_dump(envelope)


def _deserialize_conversation_checkpoint_state(
    serialized_state: str,
    *,
    tool_registry: Optional[Dict[str, Any]] = None,
    component: Optional["Component"] = None,
) -> "Conversation":
    deserialization_context = DeserializationContext()
    deserialization_context.registered_tools = tool_registry.copy() if tool_registry else {}

    if component is not None:
        deserialization_context._add_component_to_context(component)

    state_payload = yaml.safe_load(serialized_state)
    if (
        isinstance(state_payload, dict)
        and state_payload.get("checkpoint_format") == _CHECKPOINT_ENVELOPE_FORMAT
        and state_payload.get("version") == _CHECKPOINT_ENVELOPE_VERSION
        and "conversation" in state_payload
    ):
        conversation = autodeserialize_from_dict(
            state_payload["conversation"],
            deserialization_context=deserialization_context,
        )
    else:
        conversation = autodeserialize(
            serialized_state,
            deserialization_context=deserialization_context,
        )

    return cast("Conversation", conversation)
