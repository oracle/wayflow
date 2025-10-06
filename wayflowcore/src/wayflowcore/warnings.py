# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import warnings
from functools import lru_cache
from typing import Type


class SecurityWarning(Warning):
    """Warning category for security related warnings."""


@lru_cache(maxsize=None)
def warn_once(message: str, category: Type[Warning] = DeprecationWarning) -> None:
    warnings.warn(message, category=category, stacklevel=2)
