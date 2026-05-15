# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, cast

import yaml

from wayflowcore.serialization import autodeserialize, serialize_to_dict
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import autodeserialize_from_dict

from ._componentidentity import (
    CHECKPOINT_COMPONENT_REFERENCES_KEY,
    build_checkpoint_component_references,
    iter_checkpoint_component_tree,
    iter_checkpoint_conversation_graph,
    normalize_restored_component_keyed_state,
    register_checkpoint_component_references,
)

if TYPE_CHECKING:
    from wayflowcore.component import Component
    from wayflowcore.conversation import Conversation


_CHECKPOINT_ENVELOPE_FORMAT = "wayflow-conversation-checkpoint"
_CHECKPOINT_ENVELOPE_VERSION = 1


def _iter_conversation_graph(root_conversation: "Conversation") -> Sequence["Conversation"]:
    return iter_checkpoint_conversation_graph(root_conversation)


def _ensure_checkpointing_supported(conversation: "Conversation") -> None:
    from wayflowcore.ociagent import OciAgent

    for sub_conversation in _iter_conversation_graph(conversation):
        if isinstance(sub_conversation.component, OciAgent):
            raise NotImplementedError(
                "Checkpointing conversations that contain `OciAgent` is not supported yet."
            )


def _iter_component_tree(component: "Component") -> Sequence["Component"]:
    return iter_checkpoint_component_tree(component)


def _build_checkpoint_serialization_context(conversation: "Conversation") -> SerializationContext:
    serialization_context = SerializationContext(root=conversation)
    for component in _iter_component_tree(conversation.component):
        serialization_context.register_external_reference(component)
    return serialization_context


def _serialize_conversation_checkpoint_state(
    conversation: "Conversation",
    *,
    root_component_id: Optional[str] = None,
) -> str:
    _ensure_checkpointing_supported(conversation)

    serialized_conversation = serialize_to_dict(
        conversation,
        serialization_context=_build_checkpoint_serialization_context(conversation),
    )

    envelope = {
        "checkpoint_format": _CHECKPOINT_ENVELOPE_FORMAT,
        "version": _CHECKPOINT_ENVELOPE_VERSION,
        "conversation": serialized_conversation,
        CHECKPOINT_COMPONENT_REFERENCES_KEY: build_checkpoint_component_references(
            conversation.component,
            root_component_id=root_component_id,
        ),
    }
    return yaml.safe_dump(envelope)


def _deserialize_conversation_checkpoint_state(
    serialized_state: str,
    *,
    tool_registry: Optional[Dict[str, Any]] = None,
    component: Optional["Component"] = None,
    root_component_id_aliases: Optional[Sequence[str]] = None,
) -> "Conversation":
    deserialization_context = DeserializationContext()
    deserialization_context.registered_tools = tool_registry.copy() if tool_registry else {}

    state_payload = yaml.safe_load(serialized_state)
    component_references = (
        state_payload.get(CHECKPOINT_COMPONENT_REFERENCES_KEY)
        if isinstance(state_payload, dict)
        else None
    )
    register_checkpoint_component_references(
        deserialization_context=deserialization_context,
        root_component=component,
        component_references=component_references,
        root_component_id_aliases=root_component_id_aliases,
    )
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

    restored_conversation = cast("Conversation", conversation)
    normalize_restored_component_keyed_state(restored_conversation)
    return restored_conversation
