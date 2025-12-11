# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, AsyncIterable, List, Optional, Union

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..models.openairesponsespydanticmodels import (
    CreateResponse,
    ListModelsResponse,
    Order,
    Response,
    ResponseAdditionalContent,
    ResponseCompletedEvent,
    ResponseError,
    ResponseFailedEvent,
    ResponseIncompleteEvent,
    ResponseStreamEvent,
)
from ..services.service import OpenAIResponsesService


def create_openai_responses_api_routes(
    agent_service: OpenAIResponsesService,
) -> APIRouter:
    """
    Create API router with task CRUD endpoints and chat agent routes.

    Routes:
    - GET    /models                            : Retrieves all available models
    - POST   /responses                         : Creates a new task
    - GET    /responses/{response_id}           : Retrieves a response by its ID
    - DELETE /responses/{response_id}           : Removes a response by its ID
    - POST   /responses/{response_id}/cancel    : Deletes a task by its ID
    """
    router = APIRouter()

    @router.get("/models", response_model=ListModelsResponse, tags=["Models"])
    async def list_models(
        limit: Optional[int] = 20,
        order: Optional[Order] = "desc",
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> ListModelsResponse:
        """
        List models
        """
        return await agent_service.list_models(limit, order, after, before)

    @router.post("/responses", response_model=Response, tags=["Responses"])
    async def create_response(body: CreateResponse) -> Any:
        """
        Create a model response
        """
        event_stream = agent_service.create_response(body)
        if body.stream:
            sse_stream = iterate_and_yield_sse_event(event_stream)
            return StreamingResponse(sse_stream, media_type="text/event-stream")
        return await iterate_and_return_finalized_event(event_stream)

    @router.get("/responses/{response_id}", response_model=Response, tags=["Responses"])
    async def get_response(
        response_id: str,
        include: Optional[List[ResponseAdditionalContent]] = None,
        stream: Optional[bool] = None,
        starting_after: Optional[int] = None,
        include_obfuscation: Optional[bool] = None,
    ) -> Response:
        """
        Get a model response
        """
        return await agent_service.get_response(
            response_id, include, stream, starting_after, include_obfuscation
        )

    @router.delete(
        "/responses/{response_id}",
        response_model=None,
        responses={"404": {"model": ResponseError}},
        tags=["Responses"],
    )
    async def delete_response(response_id: str) -> Optional[ResponseError]:
        """
        Delete a model response
        """
        return await agent_service.delete_response(response_id)

    @router.post(
        "/responses/{response_id}/cancel",
        response_model=Response,
        responses={"404": {"model": ResponseError}},
        tags=["Responses"],
    )
    async def cancel_response(response_id: str) -> Union[Response, ResponseError]:
        """
        Cancel a response
        """
        return await agent_service.cancel_response(response_id)

    return router


async def iterate_and_return_finalized_event(
    async_iterable: AsyncIterable[ResponseStreamEvent],
) -> Response:
    async for c in async_iterable:
        if isinstance(
            c,
            (
                ResponseCompletedEvent,
                ResponseFailedEvent,
                ResponseIncompleteEvent,
            ),
        ):
            return c.response
    raise ValueError("No final event streamed")


async def iterate_and_yield_sse_event(
    async_iterable: AsyncIterable[ResponseStreamEvent],
) -> AsyncIterable[str]:
    counter = 0
    async for event in async_iterable:
        event.sequence_number = counter
        counter += 1
        event_json = event.model_dump_json()
        yield f"data: {event_json}\n\n"
    yield "data: [DONE]\n\n"
