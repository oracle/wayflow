# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict


class Singleton(type):
    """A metaclass that creates a Singleton base class when called."""

    # Taken from https://stackoverflow.com/questions/6760685/creating-a-singleton-in-python
    _instances: Dict[Any, Any] = {}

    def __call__(cls, *args: Any, **kwargs: Dict[str, Any]) -> Any:
        """
        Singleton class creation.

        Args:
            *args: arguments
            **kwargs: keyword arguments

        Returns:
            Singleton: object
        """
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
