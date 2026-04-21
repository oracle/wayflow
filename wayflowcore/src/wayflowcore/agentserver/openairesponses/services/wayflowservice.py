# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import time
from typing import Any, AsyncIterable, Dict, List, Optional, Union, cast

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from fastapi import HTTPException
from fastapi import status as http_status_code

from wayflowcore.agentserver.serverstorageconfig import ServerStorageConfig
from wayflowcore.checkpointing import ConversationCheckpoint, DatastoreCheckpointer
from wayflowcore.conversation import Conversation
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.datastore import Datastore, InMemoryDatastore
from wayflowcore.events import register_event_listeners
from wayflowcore.executors.executionstatus import ExecutionStatus, ToolRequestStatus
from wayflowcore.idgeneration import IdGenerator

from ..models.openairesponsespydanticmodels import (
    Conversation2,
    CreateResponse,
    ListModelsResponse,
    Model,
    Order,
    Response,
    ResponseAdditionalContent,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseError,
    ResponseFailedEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseStreamEvent,
    ToolChoiceOptions,
)
from ._wayflowconversion import (
    _convert_tool_request_status_into_function_tool_call_items,
    _convert_wayflow_token_usage_into_oai_token_usage,
    _create_response_args_from_wayflow_status,
    _get_conversation_new_input_messages,
    _TextStreamingListener,
    _TokenCounterListener,
)
from .service import OpenAIResponsesService

logger = logging.getLogger(__name__)


class WayFlowOpenAIResponsesService(OpenAIResponsesService):
    def __init__(
        self,
        agents: Dict[str, ConversationalComponent],
        storage: Optional[Datastore] = None,
        storage_config: Optional[ServerStorageConfig] = None,
    ):
        self.agents = agents
        self.storage_config = storage_config or ServerStorageConfig()
        self.storage = storage or InMemoryDatastore(schema=self.storage_config.to_schema())
        self.checkpointer = DatastoreCheckpointer(
            datastore=self.storage,
            storage_config=self.storage_config,
        )
        self.created_at = int(time.time())
        self._response_conversation_ids: Dict[str, str] = {}
        self.tool_registries = {
            agent_name: {t.name: t for t in agent._referenced_tools()}
            for agent_name, agent in self.agents.items()
        }

    def _add_agent(self, agent_id: str, agent: ConversationalComponent) -> None:
        if agent_id in self.agents:
            raise ValueError(
                f"An agent named `{agent_id}` already exist in the service. Please use another name."
            )
        self.agents[agent_id] = agent
        self.tool_registries[agent_id] = {t.name: t for t in agent._referenced_tools()}

    # ROUTER APIS

    async def list_models(
        self,
        limit: Optional[int] = 20,
        order: Optional[Order] = "desc",
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> ListModelsResponse:
        all_models = [
            Model(
                id=agent_name,
                created=self.created_at,
                owned_by="wayflow-server",
                object="model",
            )
            for agent_name, agent in self.agents.items()
        ]
        return ListModelsResponse(
            **self._select_only(
                items=all_models,
                limit=limit,
                order=order,
                after=after,
            )
        )

    async def get_response(
        self,
        response_id: str,
        include: Optional[List[ResponseAdditionalContent]] = None,
        stream: Optional[bool] = None,
        starting_after: Optional[int] = None,
        include_obfuscation: Optional[bool] = None,
    ) -> Response:
        if stream is True or starting_after is not None:
            raise HTTPException(
                status_code=http_status_code.HTTP_501_NOT_IMPLEMENTED,
                detail="Get endpoint for wayflow server only supports non-streaming requests",
            )

        checkpoint = self._lookup_checkpoint_by_response_id(response_id)
        if checkpoint is None:
            raise HTTPException(
                status_code=http_status_code.HTTP_404_NOT_FOUND, detail="Response not found"
            )
        response_as_txt = checkpoint.metadata.get("response")
        if not isinstance(response_as_txt, str):
            raise HTTPException(
                status_code=http_status_code.HTTP_404_NOT_FOUND, detail="Response not found"
            )
        return Response.model_validate_json(response_as_txt)

    async def delete_response(self, response_id: str) -> Optional[ResponseError]:
        checkpoint = self._lookup_checkpoint_by_response_id(response_id)
        if checkpoint is not None:
            self.checkpointer.delete(checkpoint.conversation_id, checkpoint.checkpoint_id)
            self._response_conversation_ids.pop(response_id, None)
        return None

    async def cancel_response(self, response_id: str) -> Union[Response, ResponseError]:
        raise HTTPException(
            status_code=http_status_code.HTTP_501_NOT_IMPLEMENTED,
            detail="Cancelling response is not supported in the WayFlow server",
        )

    async def create_response(self, body: CreateResponse) -> AsyncIterable[ResponseStreamEvent]:
        unsupported_options: Dict[str, str] = {
            "max_tool_calls": "`max_tool_calls` is not supported yet",
            "parallel_tool_calls": "`parallel_tool_calls` is not supported yet",
            "prompt": "`prompt` is not supported yet",
            "reasoning": "`reasoning` is not supported yet",
            "safety_identifier": "`safety_identifier` is not supported yet",
            "service_tier": "`service_tier` is not supported yet",
            "text": "`text` is not supported yet",
            "tool_choice": "`tool_choice` is not supported yet",
            "tools": "`tools` is not supported yet",
            "top_logprobs": "`top_logprobs` is not supported yet",
            "top_p": "`top_p` is not supported yet",
            "truncation": "`truncation` is not supported yet",
        }
        for option, message in unsupported_options.items():
            if getattr(body, option):
                logger.warning('Getting a request with unsupported option: "%s"', option)
                raise HTTPException(
                    status_code=http_status_code.HTTP_501_NOT_IMPLEMENTED, detail=message
                )

        model = body.model
        if model is None:
            raise HTTPException(
                status_code=http_status_code.HTTP_404_NOT_FOUND,
                detail=f"No agent specified. Please specify an agent. Agents available: {list(self.agents.keys())}",
            )
        elif model not in self.agents:
            raise HTTPException(
                status_code=http_status_code.HTTP_404_NOT_FOUND,
                detail=f"No assistant named `{model}`",
            )
        else:
            agent = self.agents[model]

        previous_response_id = body.previous_response_id
        conversation_id = body.conversation
        if conversation_id is not None and not isinstance(conversation_id, str):
            conversation_id = conversation_id.id

        should_store_response = body.store is None or body.store is True

        state = self._load_state(
            previous_response_id=previous_response_id,
            conversation_id=conversation_id,
            agent_id=model,
            attach_checkpointer=should_store_response,
        )

        response_id = IdGenerator.get_or_generate_id()
        state = await self._create_state(
            agent=agent,
            state=state,
            request=body,
        )

        current_response = Response(
            id=response_id,
            created_at=int(time.time()),
            error=None,
            incomplete_details=None,
            instructions=body.instructions,
            metadata=None,
            model=model,
            object="response",
            output=[],
            parallel_tool_calls=body.parallel_tool_calls or True,
            temperature=body.temperature,
            tool_choice=cast(ToolChoiceOptions, body.tool_choice or "auto"),
            tools=body.tools or [],
            top_p=body.top_p,
            background=body.background,
            conversation=Conversation2(id=state.id),
            max_output_tokens=body.max_output_tokens,
            max_tool_calls=body.max_tool_calls,
            previous_response_id=body.previous_response_id,
            prompt=body.prompt,
            prompt_cache_key=body.prompt_cache_key,
            reasoning=body.reasoning,
            safety_identifier=body.safety_identifier,
            service_tier=body.service_tier,
            status="in_progress",
            text=body.text,
            top_logprobs=body.top_logprobs,
            truncation=body.truncation,
            usage=None,
            user=body.user,
        )

        yield ResponseCreatedEvent(
            type="response.created", response=current_response, sequence_number=0
        )

        token_usage_listener = _TokenCounterListener()

        send_stream: MemoryObjectSendStream[ResponseStreamEvent]
        receive_stream: MemoryObjectReceiveStream[ResponseStreamEvent]
        send_stream, receive_stream = anyio.create_memory_object_stream(100)

        yielding_listener = _TextStreamingListener(queue=send_stream)

        status: Optional[ExecutionStatus] = None
        raised_exception: Optional[Exception] = None

        async def runner(conversation: Conversation) -> None:
            nonlocal status
            try:
                with register_event_listeners([token_usage_listener, yielding_listener]):
                    status = await conversation.execute_async(
                        _final_checkpoint_id=response_id if should_store_response else None,
                    )
            except Exception as e:
                nonlocal raised_exception
                raised_exception = e
            finally:
                # close the send side so the receiver side's async for terminates
                await send_stream.aclose()

        async with anyio.create_task_group() as tg:
            tg.start_soon(runner, state)

            async for ev in receive_stream:
                # These events come from the synchronous callback
                yield ev

        if raised_exception:
            if "not a multimodal model" in str(raised_exception):
                raise HTTPException(
                    status_code=http_status_code.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="The underlying model does not support multimodal inputs",
                )
            raise raised_exception

        outputs, error = _create_response_args_from_wayflow_status(status)

        if isinstance(status, ToolRequestStatus):
            for idx, item in enumerate(
                _convert_tool_request_status_into_function_tool_call_items(status.tool_requests)
            ):
                yield ResponseOutputItemAddedEvent(
                    item=item, output_index=0, sequence_number=0, type="response.output_item.added"
                )
                yield ResponseOutputItemDoneEvent(
                    item=item, output_index=0, sequence_number=0, type="response.output_item.done"
                )

        current_response.output = outputs
        current_response.error = error
        current_response.created_at = time.time()
        current_response.status = "completed"
        current_response.usage = _convert_wayflow_token_usage_into_oai_token_usage(
            token_usage_listener.usage
        )

        if should_store_response and state.checkpointer is not None:
            self.checkpointer.save_conversation(
                state,
                checkpoint_id=current_response.id,
                metadata={"response": current_response.model_dump_json()},
            )
            self._response_conversation_ids[current_response.id] = state.id

        if current_response.error is not None:
            yield ResponseFailedEvent(
                response=current_response, type="response.failed", sequence_number=0
            )
        else:
            yield ResponseCompletedEvent(
                type="response.completed",
                response=current_response,
                sequence_number=0,
            )

    # PRIVATE METHODS
    @staticmethod
    def _select_only(
        items: List[Any],
        limit: Optional[int] = 20,
        order: Optional[Order] = None,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:

        if order == "asc":
            items.sort(key=lambda i: i.created)
        elif order == "desc":
            items.sort(key=lambda i: -i.created)

        if after is not None:
            selected_items = []
            found_first = False
            for item in items:
                if found_first:
                    selected_items.append(item)
                if item.id == after:
                    found_first = True
            items = selected_items

        has_more = limit is not None and (len(items) > limit)
        if has_more:
            items = items[:limit]

        return dict(
            object="list",
            data=items,
            has_more=has_more,
            first_id=items[0].id if len(items) > 0 else "",
            last_id=items[-1].id if len(items) > 0 else "",
        )

    def _load_state(
        self,
        previous_response_id: Optional[str],
        conversation_id: Optional[str],
        agent_id: str,
        attach_checkpointer: bool = True,
    ) -> Optional[Conversation]:
        if previous_response_id:
            checkpoint = self._lookup_checkpoint_by_response_id(previous_response_id)
            if checkpoint is None:
                raise HTTPException(
                    status_code=http_status_code.HTTP_404_NOT_FOUND,
                    detail=f"No previous response with id `{previous_response_id}` was found",
                )
            self._response_conversation_ids[checkpoint.checkpoint_id] = checkpoint.conversation_id
            try:
                return self.agents[agent_id].start_conversation(
                    conversation_id=checkpoint.conversation_id,
                    checkpoint_id=checkpoint.checkpoint_id,
                    checkpointer=self.checkpointer,
                    _attach_checkpointer=attach_checkpointer,
                )
            except (TypeError, ValueError) as e:
                raise HTTPException(
                    status_code=http_status_code.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Conversation state is corrupted, it cannot be de-serialized: {e}",
                ) from e
        elif conversation_id:
            checkpoint = self.checkpointer.load_latest(conversation_id)
            if checkpoint is None:
                raise HTTPException(
                    status_code=http_status_code.HTTP_404_NOT_FOUND,
                    detail=f"No conversation with id `{conversation_id}` was found",
                )
            self._response_conversation_ids[checkpoint.checkpoint_id] = checkpoint.conversation_id
            try:
                return self.agents[agent_id].start_conversation(
                    conversation_id=conversation_id,
                    checkpointer=self.checkpointer,
                    _attach_checkpointer=attach_checkpointer,
                )
            except (TypeError, ValueError) as e:
                raise HTTPException(
                    status_code=http_status_code.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Conversation state is corrupted, it cannot be de-serialized: {e}",
                ) from e
        else:
            return None

    def _lookup_checkpoint_by_response_id(
        self, response_id: str
    ) -> Optional[ConversationCheckpoint]:
        conversation_id = self._response_conversation_ids.get(response_id)
        if conversation_id is not None:
            try:
                return self.checkpointer.load(conversation_id, response_id)
            except ValueError:
                self._response_conversation_ids.pop(response_id, None)
        checkpoint = self.checkpointer._find_checkpoint_by_id(response_id)
        if checkpoint is not None:
            self._response_conversation_ids[response_id] = checkpoint.conversation_id
        return checkpoint

    async def _create_state(
        self,
        agent: ConversationalComponent,
        state: Optional[Conversation],
        request: CreateResponse,
    ) -> Conversation:
        # get the new input messages
        # if we didn't have a conversation, we just feed them as starting messages
        # if we had a conversation, we need to add them to the right place
        if request.input is None:
            new_messages = []
        else:
            new_messages = _get_conversation_new_input_messages(state, request.input)

        instructions = request.instructions
        if state is None:
            # create a new conversation
            inputs = {}
            if instructions is not None:
                if not any(p.name == "instructions" for p in agent.input_descriptors):
                    raise HTTPException(
                        status_code=http_status_code.HTTP_406_NOT_ACCEPTABLE,
                        detail="Agent should have an `instructions` input descriptor to be able to take instructions as input",
                    )
                inputs = {"instructions": instructions}
            if request.store is None or request.store is True:
                state = agent.start_conversation(
                    inputs=inputs,
                    messages=new_messages,
                    checkpointer=self.checkpointer,
                )
            else:
                state = agent.start_conversation(inputs=inputs, messages=new_messages)
        else:
            # later: implement context provider for custom instructions
            if instructions is not None:
                raise NotImplementedError(
                    "Instructions are only supported when creating a conversation"
                )
            # Add the new messages to the conversation
            for message in new_messages:
                state.append_message(message)

        return state
