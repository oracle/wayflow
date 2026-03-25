# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations as _annotations

from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping
from contextlib import asynccontextmanager
from typing import Any, Optional, Sequence

from fasta2a.broker import Broker
from fasta2a.schema import AgentCard, a2a_request_ta, a2a_response_ta, agent_card_ta
from fasta2a.storage import Storage
from fastapi import FastAPI, Request
from fastapi.responses import Response

from ._task_manager import TaskManager, TaskNotifier

# ``FastAPI`` instances are regular ASGI applications, so ``__call__`` receives the
# standard ``(scope, receive, send)`` trio from the server.

# Connection metadata for the current request, for example the protocol type,
# path, headers, and server/client information.
ASGIScope = MutableMapping[str, Any]
# Awaitable that yields the next inbound ASGI event, such as the incoming HTTP request body.
ASGIReceive = Callable[[], Awaitable[MutableMapping[str, Any]]]
# Awaitable used to emit outbound ASGI events back to the server, such as response start/body messages.
ASGISend = Callable[[MutableMapping[str, Any]], Awaitable[None]]


@asynccontextmanager
async def _default_lifespan(app: A2AApp) -> AsyncIterator[None]:
    async with app.task_manager:
        yield


class A2AApp(FastAPI):
    def __init__(
        self,
        storage: Storage,
        broker: Broker,
        notifer: TaskNotifier,
        agent_card: AgentCard,
        debug: bool = False,
        routes: Sequence[Any] | None = None,
        middleware: Sequence[Any] | None = None,
        exception_handlers: dict[Any, Any] | None = None,
        lifespan: Any | None = None,
    ):
        if lifespan is None:
            lifespan = _default_lifespan

        super().__init__(
            debug=debug,
            routes=list(routes) if routes is not None else None,
            middleware=list(middleware) if middleware is not None else None,
            exception_handlers=exception_handlers,
            lifespan=lifespan,
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
        )

        self.agent_card = agent_card
        self._agent_card_json: Optional[bytes] = None

        self.task_manager = TaskManager(broker=broker, storage=storage, notifier=notifer)

        # Routes
        self.add_api_route(
            "/",
            self._agent_execution_endpoint,
            methods=["POST"],
            include_in_schema=False,
        )
        self.add_api_route(
            "/.well-known/agent-card.json",  # This the standard endpoint specified by A2A protocol
            self._agent_card_endpoint,
            methods=["HEAD", "GET", "OPTIONS"],
            include_in_schema=False,
        )

    async def __call__(self, scope: ASGIScope, receive: ASGIReceive, send: ASGISend) -> None:
        if scope["type"] == "http" and not self.task_manager.is_running:
            raise RuntimeError("TaskManager was not properly initialized.")
        await super().__call__(scope, receive, send)

    async def _agent_execution_endpoint(self, request: Request) -> Response:
        """This is the main endpoint of A2A server"""
        data = await request.body()
        a2a_request = a2a_request_ta.validate_json(data)

        if a2a_request["method"] == "message/send":
            jsonrpc_response = await self.task_manager.send_message(a2a_request)
        elif a2a_request["method"] == "tasks/get":
            jsonrpc_response = await self.task_manager.get_task(a2a_request)
        elif a2a_request["method"] == "tasks/cancel":
            jsonrpc_response = await self.task_manager.cancel_task(a2a_request)
        else:
            raise NotImplementedError(f'Method {a2a_request["method"]} not implemented.')
        return Response(
            content=a2a_response_ta.dump_json(jsonrpc_response, by_alias=True),
            media_type="application/json",
        )

    async def _agent_card_endpoint(self, request: Request) -> Response:
        if not self._agent_card_json:
            self._agent_card_json = agent_card_ta.dump_json(self.agent_card, by_alias=True)
        return Response(content=self._agent_card_json, media_type="application/json")
