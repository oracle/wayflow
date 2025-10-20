# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Callable


def _required_attribute(attribute_name: str, attribute_type: Any) -> Callable[[], Any]:
    # Generic factory used to ensure that a field in a dataclass is provided
    def _inner_required_attribute() -> None:
        raise ValueError(
            f"An attribute named `{attribute_name}` of type `{attribute_type}` is required"
        )

    return _inner_required_attribute
