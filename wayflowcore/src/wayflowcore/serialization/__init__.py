# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any

from .serializer import (
    autodeserialize,
    deserialize,
    deserialize_from_dict,
    serialize,
    serialize_to_dict,
)


def dump_conversation_state(*args: Any, **kwargs: Any) -> Any:
    from .conversation import dump_conversation_state as _dump_conversation_state

    return _dump_conversation_state(*args, **kwargs)


def serialize_conversation_state(*args: Any, **kwargs: Any) -> Any:
    from .conversation import serialize_conversation_state as _serialize_conversation_state

    return _serialize_conversation_state(*args, **kwargs)


def deserialize_conversation_state(*args: Any, **kwargs: Any) -> Any:
    from .conversation import deserialize_conversation_state as _deserialize_conversation_state

    return _deserialize_conversation_state(*args, **kwargs)


def dump_variable_state(*args: Any, **kwargs: Any) -> Any:
    from .conversation import dump_variable_state as _dump_variable_state

    return _dump_variable_state(*args, **kwargs)


__all__ = [
    "autodeserialize",
    "deserialize",
    "deserialize_conversation_state",
    "deserialize_from_dict",
    "dump_conversation_state",
    "dump_variable_state",
    "serialize",
    "serialize_conversation_state",
    "serialize_to_dict",
]
