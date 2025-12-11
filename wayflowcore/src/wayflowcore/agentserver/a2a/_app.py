# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations as _annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Optional, Sequence

from fasta2a.broker import Broker
from fasta2a.schema import AgentCard, a2a_request_ta, a2a_response_ta, agent_card_ta
from fasta2a.storage import Storage
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.types import ExceptionHandler, Lifespan, Receive, Scope, Send

from ._task_manager import TaskManager, TaskNotifier


@asynccontextmanager
async def _default_lifespan(app: A2AApp) -> AsyncIterator[None]:
    async with app.task_manager:
        yield


class A2AApp(Starlette):
    def __init__(
        self,
        storage: Storage,
        broker: Broker,
        notifer: TaskNotifier,
        agent_card: AgentCard,
        # Starlette
        debug: bool = False,
        routes: Sequence[Route] | None = None,
        middleware: Sequence[Middleware] | None = None,
        exception_handlers: dict[Any, ExceptionHandler] | None = None,
        lifespan: Lifespan[A2AApp] | None = None,
    ):
        if lifespan is None:
            lifespan = _default_lifespan

        super().__init__(
            debug=debug,
            routes=routes,
            middleware=middleware,
            exception_handlers=exception_handlers,
            lifespan=lifespan,
        )

        self.agent_card = agent_card
        self._agent_card_json: Optional[bytes] = None

        self.task_manager = TaskManager(broker=broker, storage=storage, notifier=notifer)

        # Routes
        self.router.add_route("/", self._agent_execution_endpoint, methods=["POST"])
        self.router.add_route(
            "/.well-known/agent-card.json",  # This the standard endpoint specified by A2A protocol
            self._agent_card_endpoint,
            methods=["HEAD", "GET", "OPTIONS"],
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
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
