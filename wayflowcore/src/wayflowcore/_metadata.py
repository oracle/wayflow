# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, Optional

from wayflowcore.idgeneration import IdGenerator

METADATA_KEY = "__metadata_info__"
MetadataType = Dict[str, Any]

METADATA_ID_KEY = "$$ID$$"


class ObjectWithMetadata:
    def __init__(self, __metadata_info__: Optional[MetadataType] = None, id: Optional[str] = None):
        self.__metadata_info__ = dict(__metadata_info__) if __metadata_info__ is not None else {}
        # workaround to set the ID of any component without init argument
        default_id = id
        if METADATA_ID_KEY in self.__metadata_info__:
            default_id = self.__metadata_info__.pop(METADATA_ID_KEY)
        if not hasattr(self, "id"):
            self.id = IdGenerator.get_or_generate_id(default_id)

        if self.id is None:
            self.id = IdGenerator.get_or_generate_id(self.id)
