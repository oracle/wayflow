# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict, Type

from wayflowcore.contextproviders import (
    ChatHistoryContextProvider,
    ContextProvider,
    FlowContextProvider,
    ToolContextProvider,
)

from .._metadata import METADATA_KEY
from .context import DeserializationContext, SerializationContext
from .serializer import autodeserialize_any_from_dict, serialize_any_to_dict

SUPPORTED_CONTEXT_PROVIDER_TYPES: Dict[str, Type[ContextProvider]] = {
    "chat-history": ChatHistoryContextProvider,
    "flow": FlowContextProvider,
    "tool": ToolContextProvider,
}


def register_supported_context_provider(
    name: str, context_provider_cls: Type[ContextProvider]
) -> None:
    if name in SUPPORTED_CONTEXT_PROVIDER_TYPES:
        raise ValueError(f"context provider already registered: {name}")
    SUPPORTED_CONTEXT_PROVIDER_TYPES[name] = context_provider_cls


def serialize_context_provider_to_dict(
    context_provider: ContextProvider, serialization_context: SerializationContext
) -> Dict[str, Any]:
    """
    Converts a ContextProvider to a nested dict of standard types such that it can be easily
    serialized with either JSON or YAML.

    The serialized dict contains:
    ```
    {
        "_component_type": "ContextProvider",
        "context_provider_type": str,
        "context_provider_args": dict,
    }
    ```
    The args will depend on the type of context providers. For example for a
    DatastoreContextProvider the args will contain the corresponding Datastore.

    Parameters
    ----------
    context_provider:
      The ContextProvider that is intended to be serialized
    serialization_context:
      The serialization context used to store serialization of wayflowcore objects and store their
      references
    """
    context_provider_types = {
        context_provider_cls: context_provider_type
        for context_provider_type, context_provider_cls in SUPPORTED_CONTEXT_PROVIDER_TYPES.items()
    }

    if context_provider.__class__ not in context_provider_types:
        raise ValueError(
            f"The context provider class {context_provider.__class__.__name__} is not supported for serialization"
        )

    serialized_context_provider_dict: Dict[str, Any] = {
        "_component_type": ContextProvider.__name__,
        "context_provider_type": context_provider_types[context_provider.__class__],
        "name": context_provider.name,
        "id": context_provider.id,
        "description": context_provider.description,
    }

    context_provider_args = {}
    context_provider_config = context_provider.get_static_configuration_descriptors()
    for config_name, config_type_descriptor in context_provider_config.items():
        if not hasattr(context_provider, config_name):
            raise ValueError(
                f"The ContextProvider {context_provider.__class__.__name__} cannot be serialized "
                f"because it has a config named {config_name} but is missing the attribute "
                f"of the same name."
            )
        context_provider_args[config_name] = serialize_any_to_dict(
            getattr(context_provider, config_name), serialization_context
        )

    serialized_context_provider_dict["context_provider_args"] = context_provider_args

    return serialized_context_provider_dict


def deserialize_context_provider_from_dict(
    context_provider_as_dict: Dict[str, Any], deserialization_context: DeserializationContext
) -> ContextProvider:
    """
    Builds an instance of Context Provider from its representation as a dict.

    Parameters
    ----------
    context_provider_as_dict:
      The representation as a dict of a ContextProvider
    deserialization_context:
      The context of the deserialization. It contains tools and the deserialization of referenced_objects
    """
    context_provider_type = context_provider_as_dict["context_provider_type"]
    if context_provider_type not in SUPPORTED_CONTEXT_PROVIDER_TYPES:
        raise ValueError(
            f"The context provider type {context_provider_type} is not supported for deserialization."
            f" Supported types are: {list(SUPPORTED_CONTEXT_PROVIDER_TYPES.keys())}"
        )
    context_provider_cls = SUPPORTED_CONTEXT_PROVIDER_TYPES[context_provider_type]

    context_provider_arguments = {
        arg_name: autodeserialize_any_from_dict(arg_prepared_value, deserialization_context)
        for arg_name, arg_prepared_value in context_provider_as_dict[
            "context_provider_args"
        ].items()
    }

    deserialized_context_provider = context_provider_cls(
        **context_provider_arguments,
        name=context_provider_as_dict.get("name", None),
        description=context_provider_as_dict.get("description", None),
        id=context_provider_as_dict.get("id", None),
        __metadata_info__=context_provider_arguments.get(METADATA_KEY, None),
    )

    return deserialized_context_provider
