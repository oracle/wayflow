# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from abc import ABC, abstractmethod
from typing import Any, AsyncIterable, List, Optional, Union

from ..models.openairesponsespydanticmodels import (
    CreateResponse,
    ListModelsResponse,
    Order,
    Response,
    ResponseAdditionalContent,
    ResponseError,
    ResponseStreamEvent,
)


class OpenAIResponsesService(ABC):

    @abstractmethod
    async def list_models(
        self,
        limit: Optional[int] = 20,
        order: Optional[Order] = "desc",
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> ListModelsResponse:
        """
        List models
        """

    @abstractmethod
    async def create_response(self, body: CreateResponse) -> AsyncIterable[ResponseStreamEvent]:
        """
        Create a model response
        """
        # fake implementation for IDE typechecker to work
        yield ResponseStreamEvent()  # type: ignore

    @abstractmethod
    async def get_response(
        self,
        response_id: str,
        include: Optional[List[ResponseAdditionalContent]] = None,
        stream: Optional[bool] = None,
        starting_after: Optional[int] = None,
        include_obfuscation: Optional[bool] = None,
    ) -> Response:
        """
        Get a model response
        """
        ...

    @abstractmethod
    async def delete_response(self, response_id: str) -> Optional[ResponseError]:
        """
        Delete a model response
        """

    @abstractmethod
    async def cancel_response(self, response_id: str) -> Union[Response, ResponseError]:
        """
        Cancel a response
        """

    @abstractmethod
    def _add_agent(self, agent_id: str, agent: Any) -> None:
        pass
