# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import uuid
from typing import Optional

import numpy as np

AUTO_GENERATED_SUFFIX = "__auto"


class IdGenerator:
    @staticmethod
    def _generate_id() -> str:
        id = uuid.uuid4()
        return str(id)

    @staticmethod
    def get_or_generate_id(id: Optional[str] = None) -> str:
        if id is not None:
            return id
        return IdGenerator._generate_id()

    @staticmethod
    def get_or_generate_name(
        name: Optional[str] = None, prefix: Optional[str] = None, length: Optional[int] = None
    ) -> str:
        """
        If needed, generates a name automatically of the form:
        >>> f"{prefix}_{random_string_of_size_length}__auto"  # doctest: +SKIP

        Parameters
        ----------
        name:
            The current name. A name will be auto-generated if this is `None`.
        prefix:
            Prefix for the auto-generated name.
        length:
            Number of random characters [1234567890abcdef] to include in the name.

        """
        if name is not None:
            return name
        name = "".join(np.random.choice(list("1234567890abcdef"), size=length))
        if length is not None:
            name = name[: min(len(name), length)]
        if prefix is not None:
            name = prefix + name
        return f"{name}{AUTO_GENERATED_SUFFIX}"

    @staticmethod
    def is_auto_generated(value: str) -> bool:
        return value.endswith(AUTO_GENERATED_SUFFIX)
