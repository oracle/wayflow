# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import TYPE_CHECKING, Any, Callable, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.property import Property

from .contextprovider import ContextProvider

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation


ContextProviderType = Callable[["Conversation"], Any]


class ConstantContextProvider(ContextProvider):
    """Context provider to return constant value"""

    def __init__(
        self,
        value: Any,
        output_description: "Property",
        name: Optional[str] = None,
        id: Optional[str] = None,
        description: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        self._value = value
        self._output_description = output_description
        super().__init__(
            name=name, description=description, id=id, __metadata_info__=__metadata_info__
        )

    async def call_async(self, conversation: "Conversation") -> Any:
        from wayflowcore.tracing.span import ContextProviderExecutionSpan

        with ContextProviderExecutionSpan(context_provider=self) as span:
            value = self._value
            span.record_end_span_event(
                output=value,
            )
            return value

    @property
    def callable(self) -> ContextProviderType:
        return self.__call__

    def get_output_descriptors(self) -> List["Property"]:
        return [self._output_description]
