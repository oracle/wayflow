# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

"""Marker types for optional values whose absence is meaningful."""

from typing import Literal


class NotGiven:
    """Marker for a value that was not supplied."""

    def __bool__(self) -> Literal[False]:
        """Evaluate the marker as false."""
        return False


NOT_GIVEN = NotGiven()
