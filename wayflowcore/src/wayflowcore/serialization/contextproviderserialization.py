# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, cast

from deprecated import deprecated

from wayflowcore.contextproviders import _SUPPORTED_CONTEXT_PROVIDER_TYPES, ContextProvider

from .context import DeserializationContext, SerializationContext


def register_supported_context_provider(
    name: str, context_provider_cls: type[ContextProvider]
) -> None:
    if name in _SUPPORTED_CONTEXT_PROVIDER_TYPES:
        raise ValueError(f"context provider already registered: {name}")
    _SUPPORTED_CONTEXT_PROVIDER_TYPES[name] = context_provider_cls


@deprecated(
    "`serialize_context_provider_to_dict` is deprecated. Please use `serialize_to_dict(ContextProvider, ...)` instead."
)
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
    return ContextProvider._serialize_to_dict(context_provider, serialization_context)


@deprecated(
    "`deserialize_context_provider_from_dict` is deprecated. Please use `deserialize_from_dict(ContextProvider, ...)` instead."
)
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
    return cast(
        ContextProvider,
        ContextProvider._deserialize_from_dict(context_provider_as_dict, deserialization_context),
    )
