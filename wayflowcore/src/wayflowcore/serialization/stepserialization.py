# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from typing import TYPE_CHECKING, Any, Dict, cast

from deprecated import deprecated

if TYPE_CHECKING:
    from wayflowcore.serialization.context import DeserializationContext, SerializationContext
    from wayflowcore.steps.step import Step

logger = logging.getLogger(__name__)


@deprecated(
    "`serialize_step_to_dict` is deprecated. Please use `serialize_to_dict(Step, ...)` instead."
)
def serialize_step_to_dict(
    step: "Step", serialization_context: "SerializationContext"
) -> Dict[str, Any]:
    """
    Converts a step to a nested dict of standard types such that it can be easily serialized with either JSON or YAML

    Parameters
    ----------
    step:
        The Step that is intended to be serialized
    serialization_context:
        Context for serialization operations.
    """
    return step._serialize_to_dict(serialization_context)


@deprecated(
    "`deserialize_step_from_dict` is deprecated. Please use `deserialize_from_dict(Step, ...)` instead."
)
def deserialize_step_from_dict(
    step_as_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
) -> "Step":
    return cast(Step, Step._deserialize_from_dict(step_as_dict, deserialization_context))
