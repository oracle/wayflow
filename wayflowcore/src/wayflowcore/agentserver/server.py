# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import secrets
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fasta2a.broker import InMemoryBroker
from fasta2a.schema import AgentCapabilities, AgentCard
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from wayflowcore.agentserver.serverstorageconfig import ServerStorageConfig
from wayflowcore.flow import Flow
from wayflowcore.steps import AgentExecutionStep, InputMessageStep

from ..conversationalcomponent import ConversationalComponent
from ..datastore import Datastore
from .a2a._app import A2AApp
from .a2a._storage import A2AStorage
from .a2a._task_manager import TaskNotifier
from .a2a._worker import A2AAgentWorker
from .openairesponses.routes import create_openai_responses_api_routes
from .openairesponses.services import OpenAIResponsesService, WayFlowOpenAIResponsesService


class A2AServer:
    def __init__(
        self,
        storage_config: Optional[ServerStorageConfig] = None,
    ) -> None:
        """
        A server for exposing a WayFlow conversational component via the A2A protocol.

        The `A2AServer` wraps around an internal `A2AApp` (a Starlette application)
        to handle HTTP-based communication between external A2A clients and an agent.
        It automatically serves the agent card and task endpoints.

        The assistant can be queried via the A2A protocol at the provided URL.

        This server supports **server** tools in the served assistant.
        In A2A, the WayFlow ToolRequest and ToolResult are represented as the `DataPart`
        object.

        A DataPart contains:
            - **metadata**: a dictionary with a `type` key indicating whether this
              part represents a `ToolRequest` or a `ToolResult`.
            - **data**: a dictionary with the actual fields of the `ToolRequest`
              or `ToolResult`.

        Parameters
        ----------

        storage_config:
            Config for the storage to save the conversations. If not provided, the default storage with `InMemoryDatastore` will be used.
        """

        self.storage_config = ServerStorageConfig()
        self._storage = A2AStorage(self.storage_config)
        self._broker = InMemoryBroker()

    def serve_agent(
        self,
        agent: ConversationalComponent,
        url: Optional[str] = None,
    ) -> None:
        """
        Specifies the agent to be served.

        Parameters
        ----------
        agent
            The agent to be served which can be any conversational component in WayFlow (e.g Agent, Flow, Swarm, etc.).
        url
            The public address the agent is hosted at.
        """
        if url and not is_valid_url(url):
            raise ValueError(f"Invalid URL")

        self.agent = agent
        if isinstance(self.agent, Flow) and not any(
            isinstance(step, (InputMessageStep, AgentExecutionStep))
            for step in self.agent.steps.values()
        ):
            raise ValueError(f"Only support Flow with ``InputMessageStep`` or ``AgentExecutionStep")

        self._task_notifier = TaskNotifier()
        self._worker = A2AAgentWorker(
            broker=self._broker,
            storage=self._storage,
            assistant=self.agent,
            notifier=self._task_notifier,
        )
        self.url = url

    def get_app(self, host: str = "127.0.0.1", port: int = 8000) -> A2AApp:
        @asynccontextmanager
        async def lifespan(app: A2AApp) -> AsyncIterator[None]:
            async with app.task_manager:
                async with self._worker.run():
                    yield

        if not self.url:
            url = f"http://{host}:{port}"
            self.url = url
        agent_card = _get_agent_card(self.agent, url=self.url)

        app = A2AApp(
            storage=self._storage,
            broker=self._broker,
            agent_card=agent_card,
            notifer=self._task_notifier,
            lifespan=lifespan,
        )

        return app

    def run(self, host: str = "127.0.0.1", port: int = 8000, api_key: Optional[str] = None) -> None:
        """
        Starts the server and serve the assistant.

        Parameters
        ----------
        host:
            Host to serve the server.
        port:
            Port to expose the server.
        api_key:
            A key that will be required to authenticate the requests. It needs to be provided as a bearer token.
        """
        import uvicorn

        # we log a warning since this server has no security implemented
        warn_server_is_not_secured()

        app = self.get_app(host, port)
        uvicorn.run(
            app=app,
            host=host,
            port=port,
            reload=False,  # need to be set to false for production
        )


class OpenAIResponsesServer:
    """FastAPI application for task management with AI agents."""

    def __init__(
        self,
        agents: Optional[Dict[str, ConversationalComponent]] = None,
        storage: Optional[Datastore] = None,
        storage_config: Optional[ServerStorageConfig] = None,
    ):
        """
        Public-facing server for exposing an Agent or Flow via the OpenAI Responses protocol.
        The assistant can be queried via the OpenAI Responses protocol at the provided URL.

        Parameters
        ----------
        agents:
            Dictionary storing the agent_ids and agents to serve. The `model_id` will be the one
            clients will have to mention in `request.model` to choose which agent to use for their request.
        storage:
            Datastore for server persistence. Needs to have the proper table and columns as specified
            in the `storage_config`.
        storage_config:
            Cch will not guarantee persistence of data across runs.
        """
        self.app = FastAPI(
            title="WayFlow Responses API",
            version="1.0.0",
            description="Serve WayFlow agents through OpenAI Responses-compatible endpoints.",
            servers=[{"description": "WayFlow Responses API Server"}],
        )
        agents = agents or {}
        # Initialize services
        self.agent_service: OpenAIResponsesService = WayFlowOpenAIResponsesService(
            agents=agents,
            storage=storage,
            storage_config=storage_config,
        )
        self._setup_middleware()
        self._setup_routes()

    def serve_agent(self, agent_id: str, agent: ConversationalComponent) -> None:
        """
        Adds an agent to the service.

        Parameters
        ----------
        agent_id:
            Name of the agent to serve.
        agent:
            The agent to serve.
        """
        self.agent_service._add_agent(agent_id, agent)

    def _setup_middleware(self) -> None:
        """Set up CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure as needed for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self) -> None:
        """Set up API routes and static file serving."""
        api_router = create_openai_responses_api_routes(
            agent_service=self.agent_service,
        )
        self.app.include_router(api_router, prefix="/v1")

    def get_app(self) -> FastAPI:
        """
        Get the FastAPI application instance.

        .. note::
           For production environments, you should use this function to get the FastAPI
           application that implements the OpenAI Responses endpoints, and then add your
           own security/authentication layer on top of it.

           Consider adding:

           - **HTTPS/TLS**: Terminate TLS at a reverse proxy or load balancer, or use
             ``uvicorn --ssl-keyfile`` and ``--ssl-certfile``.
           - **Rate limiting**: Use ``slowapi`` or an API gateway to prevent abuse.
           - **CORS**: Configure ``CORSMiddleware`` if serving browser-based clients.
           - **Request validation**: Add input size limits and content-type checks.

        Example
        -------
        Here is a very simple example of how to implement token-based authentication:

        >>> import os
        >>> import secrets
        >>> from fastapi import Request, status
        >>> from fastapi.responses import JSONResponse
        >>> API_TOKEN = os.environ.get("WAYFLOW_SERVER_TOKEN", "change-me")
        >>>
        >>> app = server.get_app()  # doctest: +SKIP
        >>>
        >>> @app.middleware("http")  # doctest: +SKIP
        ... async def require_bearer_token(request: Request, call_next):
        ...     auth_header = request.headers.get("authorization", "")
        ...     expected_header = f"Bearer {API_TOKEN}"
        ...     if not secrets.compare_digest(auth_header, expected_header):
        ...         return JSONResponse(
        ...             status_code=status.HTTP_401_UNAUTHORIZED,
        ...             content={"detail": "Missing or invalid bearer token"},
        ...         )
        ...     return await call_next(request)

        and then run ``uvicorn main:app --host 0.0.0.0 --port 8000``.

        Returns
        -------
        server:
            A FastAPI application that implements the OpenAI Responses endpoints.
        """
        return self.app

    def run(self, host: str = "127.0.0.1", port: int = 8000, api_key: Optional[str] = None) -> None:
        """
        Starts the server and serves all the registered agents in a blocking way.

        Parameters
        ----------
        host:
            Host to serve the server.
        port:
            Port to expose the server.
        api_key:
            A key that will be required to authenticate the requests. It needs to be provided as a bearer token.
        """
        import uvicorn

        # we log a warning since this server has no security implemented
        warn_server_is_not_secured()

        app = self.get_app()
        if api_key is not None:
            _add_token_authentication_auth(app=app, api_key=api_key)

        uvicorn.run(
            app=app,
            host=host,
            port=port,
            reload=False,  # need to be set to false for production
        )


def _add_token_authentication_auth(app: FastAPI, api_key: str) -> None:
    @app.middleware("http")
    async def require_bearer_token(request: Request, call_next: Any) -> Any:
        auth_header = request.headers.get("authorization", "")
        expected_header = f"Bearer {api_key}"
        if not secrets.compare_digest(auth_header, expected_header):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid bearer token"},
            )
        return await call_next(request)


_WARNING_MESSAGE = r"""

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                           ⚠️  SECURITY WARNING                                                 ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                                                                ┃
┃   This server has NO built-in authentication or encryption.                                    ┃
┃   Anyone with network access can invoke your agent.                                            ┃
┃                                                                                                ┃
┃   For production, either:                                                                      ┃
┃     • Deploy behind an authenticated gateway (e.g., OCI Agent Hub)                             ┃
┃     • Add auth middleware via `OpenAIResponsesServer.get_app()`                                ┃
┃                                                                                                ┃
┃   See: https://oracle.github.io/wayflow/development/core/howtoguides/howto_serve_agents.html   ┃
┃                                                                                                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
"""


def warn_server_is_not_secured() -> None:
    warnings.warn(_WARNING_MESSAGE)


def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return all([parsed.scheme, parsed.netloc])


def _get_agent_card(agent: ConversationalComponent, url: str) -> AgentCard:
    return AgentCard(
        name=agent.name,
        description=agent.description,
        url=url,
        version="0.0.1",
        skills=[],
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(
            streaming=False,
            push_notifications=False,
            state_transition_history=False,
        ),
    )
