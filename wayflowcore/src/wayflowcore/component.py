# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from abc import ABC
from dataclasses import dataclass
from typing import ClassVar, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.serialization.serializer import (
    FrozenSerializableDataclass,
    SerializableDataclass,
    SerializableObject,
)


class Component(SerializableObject, ABC):
    """Class for all components present in the intermediate representation"""

    def __init__(
        self,
        name: Optional[str],
        description: Optional[str],
        id: Optional[str],
        __metadata_info__: Optional[MetadataType] = None,
    ):
        # all arguments are mandatory to avoid missing them in implementations
        super().__init__(id=id, __metadata_info__=__metadata_info__)
        self.name = name or self.id
        self.description = description


@dataclass(kw_only=True)
class DataclassComponent(SerializableDataclass, Component, ABC):
    """
    Base class for dataclasses to be serializable and to have ID and metadata attributes
    """

    name: str = ""
    description: Optional[str] = None

    _can_be_referenced: ClassVar[bool] = True


@dataclass(frozen=True, kw_only=True)
class FrozenDataclassComponent(FrozenSerializableDataclass, Component, ABC):
    """
    Base class for frozen dataclasses to be serializable and to have ID and metadata attributes
    """

    name: str = ""
    description: Optional[str] = None

    _can_be_referenced: ClassVar[bool] = True
