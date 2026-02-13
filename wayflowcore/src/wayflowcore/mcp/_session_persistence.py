# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import atexit
import logging
import threading
import weakref
from contextlib import ExitStack
from typing import TYPE_CHECKING, Any, Awaitable, Callable, List, Optional, Tuple, TypeVar, Union

import anyio
import httpx
from anyio import from_thread, to_thread
from anyio.streams import memory
from exceptiongroup import ExceptionGroup
from httpx import ConnectError
from mcp import ClientSession
from typing_extensions import TypeAlias

from wayflowcore._utils.singleton import Singleton
from wayflowcore.exceptions import AuthInterrupt
from wayflowcore.tracing.span import _ACTIVE_SPAN_STACK, Span, get_active_span_stack

if TYPE_CHECKING:
    from wayflowcore.auth.auth import AuthChallengeResult
    from wayflowcore.mcp._auth import OAuthFlowHandler
    from wayflowcore.mcp.clienttransport import ClientTransport


T = TypeVar("T")
MemoryStreamTypeT: TypeAlias = Tuple[Any, Any]

logger = logging.getLogger(__name__)


_DEFAULT_MCP_SESSION_CONTEXT_ID = "DEFAULT_CONTEXT_ID"
"""Default key used to register a MCP session when not running under a conversation."""


def get_current_conv_id_or_default() -> str:
    from wayflowcore.conversation import _get_current_conversation_id

    return _get_current_conversation_id() or _DEFAULT_MCP_SESSION_CONTEXT_ID


async def _call_with_parent_span(
    parent_span_stack: list[Span],
    async_fn: Callable[..., Awaitable[T]],
    /,
    *args: Any,
    **kwargs: Any,
) -> T | Awaitable[T]:
    token = _ACTIVE_SPAN_STACK.set(parent_span_stack)
    try:
        result = async_fn(*args, **kwargs)
        if hasattr(result, "__await__"):
            return await result
        return result
    finally:
        _ACTIVE_SPAN_STACK.reset(token)


class ConnectionCompletedStatus:
    """Maker used to indicate that a connection (potentially with auth)
    has been fully completed."""


class AsyncRuntime(metaclass=Singleton):
    """
    This class enable wayflow executor to reuse MCP sessions, even when running sync code.

    When doing a first call to a MCP server, a long-lived task is created in a background
    thread, which enables the executor to route MCP requests through the same ClientSession.
    The sessions live until the program is terminated.

    Upon program termination, this class automatically shuts down the background thread.

    In practice, users of this class:
    1. Create long lived sessions using `create_long_lived_session`
    2. Route subsequent calls to the MCP server using `call` (sync) and `call_async` (async).

    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._portal_cm: Optional[from_thread.BlockingPortal] = None
        self._portal: Optional[from_thread.BlockingPortal] = None
        self._closed = False
        self._exit_stack = ExitStack()
        # sessions/handlers are stored in dict[transport_id, dict[conv_id, ...]]
        self._client_sessions: dict[str, dict[str, ClientSession]] = {}
        self._oauth_handlers: dict[str, dict[str, "OAuthFlowHandler"]] = {}
        self._memory_streams: List[MemoryStreamTypeT] = []
        self._cancel_events: List[anyio.Event] = []
        # Cross-call portal state used by MCP progress callbacks.
        # This is a pragmatic workaround for contextvar propagation issues when the
        # portal task is created long before tool execution.
        self._portal_parent_span_stack: Dict[str, List[Span]] = {}

    def initialize(self) -> None:
        if self._portal is not None:
            logger.debug("MCP Async Portal already started")
            return
        with self._lock:
            if self._portal is not None:
                logger.debug("MCP Async Portal already present (after lock)")
                return
            logger.debug("Starting BlockingPortal background loop")
            self._portal_cm = from_thread.start_blocking_portal()  # type: ignore
            self._portal = self._exit_stack.enter_context(self._portal_cm)  # type: ignore

            # Ensure resource cleanup runs before portal closes
            self._exit_stack.callback(self._close)
            atexit.register(self._exit_stack.close)
            weakref.finalize(self, AsyncRuntime._finalize, weakref.proxy(self))
            # ^ used if the AsyncRuntime is garbage-collected before the
            # atexit callback is called

            logger.info("BlockingPortal loop started")

    @property
    def is_live(self) -> bool:
        """Whether the MCP async runtime is started or not."""
        return self._portal is not None

    def call(self, async_fn: Callable[..., Awaitable[T]], /, *args: Any, **kwargs: Any) -> T:
        """This method should be called to ensure that an async method is called from the portal when in a sync context."""
        if self._portal is None:
            raise RuntimeError("Async runtime not started")

        # contextvars.copy_context() does not propagate correctly through anyio's
        # BlockingPortal on all code paths (notably when toolboxes trigger MCP
        # schema fetches before tool execution). To ensure tool progress callbacks
        # can resolve the active ToolExecutionSpan, explicitly forward the current
        # WayFlow span stack + event listeners to the portal task.
        parent_span_stack = get_active_span_stack(return_copy=True)

        # Store the most recent caller context on the runtime so callbacks that are
        # invoked later (e.g., MCP progress callbacks inside a long-lived session
        # created earlier) can still access the correct span/listeners.
        conversation_id = get_current_conv_id_or_default()
        self._portal_parent_span_stack[conversation_id] = parent_span_stack

        return self._portal.call(  # type: ignore
            _call_with_parent_span,
            parent_span_stack,
            async_fn,
            *args,
            **kwargs,
        )

    async def call_async(
        self, async_fn: Callable[..., Awaitable[T]], /, *args: Any, **kwargs: Any
    ) -> T:
        """This method should be called to ensure that an async method is called from the portal when in an async context."""
        return await to_thread.run_sync(lambda: self.call(async_fn, *args, **kwargs))

    def get_or_create_session(self, client_transport: "ClientTransport") -> ClientSession:
        """
        If a session already exists for the currently running conversation, return it.
        Otherwise,
          1. create a new session through the portal
          2. register the session

        This method MUST NOT be called within a portal.call (for cancellation scope reasons).
        """
        conversation_id = get_current_conv_id_or_default()
        sessions_by_transport = self._client_sessions.setdefault(client_transport.id, {})
        if conversation_id in sessions_by_transport:
            # session already exists
            return sessions_by_transport[conversation_id]
        return self._create_long_lived_session(client_transport, conversation_id)

    def get_parent_span_stack(self) -> List[Span]:
        # called by the _mcp_progress_handler
        conversation_id = get_current_conv_id_or_default()
        return self._portal_parent_span_stack.get(conversation_id, [])

    def _create_long_lived_session(
        self,
        client_transport: "ClientTransport",
        conversation_id: str,
    ) -> ClientSession:
        """Creates a long lived MCP ClientSession in a background thread.

        This session is then reused between calls.
        """
        from wayflowcore.auth.auth import AuthChallengeRequest
        from wayflowcore.executors.executionstatus import AuthChallengeRequestStatus
        from wayflowcore.mcp._auth import OAuthCancelledError

        # The memory stream is used to collect the session object from the runner
        send, recv = anyio.create_memory_object_stream[
            Union[AuthChallengeRequest, ConnectionCompletedStatus, BaseException]
        ]()
        memory_stream = (send, recv)
        self._memory_streams.append(memory_stream)
        requires_oauth = _bind_portal_info_if_needed(
            client_transport,
            memory_stream,
            self,
            conversation_id,
        )

        # The runner will be keeping the MCP client session task alive until the
        # event flag is set (which is done when closing all sessions)
        cancel_event: anyio.Event = self.call(anyio.Event)  # type: ignore
        self._cancel_events.append(cancel_event)

        async def session_runner(
            send_chan: memory.MemoryObjectSendStream[
                Union[AuthChallengeRequest, ConnectionCompletedStatus, BaseException]
            ],
            cancel_evt: anyio.Event,
            transport_id: str,
            conversation_id: str,
        ) -> None:
            is_session_initialized = False
            try:
                async with client_transport._get_client_transport_cm() as transport_tuple:
                    read_stream, write_stream = transport_tuple[0], transport_tuple[1]
                    async with ClientSession(
                        read_stream, write_stream, **client_transport.session_parameters.to_dict()
                    ) as session:
                        try:
                            await session.initialize()
                            is_session_initialized = True
                        except Exception as e:
                            raise e
                        self._client_sessions.setdefault(transport_id, {})[
                            conversation_id
                        ] = session

                        if not requires_oauth:
                            await send_chan.send(ConnectionCompletedStatus())
                        else:
                            _signal_oauth_completion(self, transport_id, conversation_id)
                            # ^ AuthChallengeRequestStatus.submit_result waits on
                            # this signal to continue.

                        await cancel_evt.wait()  # keep task alive until asked to stop
            except BaseException as e:
                if isinstance(e, ExceptionGroup) and any(
                    isinstance(sub_exc, OAuthCancelledError) for sub_exc in e.exceptions
                ):
                    logger.debug(
                        "OAuth flow cancelled for transport '%s' and conversation '%s'",
                        transport_id,
                        conversation_id,
                    )
                    return
                elif not is_session_initialized:
                    # Shield sending the error so it isn’t cancelled
                    with anyio.CancelScope(shield=True):
                        await send_chan.send(e)
                # Re-raise to surface in logs/monitoring
                raise e

        # start the long-lived task
        if not self._portal:
            raise RuntimeError("Async runtime not started")

        transport_id = client_transport.id
        self._portal.start_task_soon(
            session_runner, send, cancel_event, transport_id, conversation_id
        )
        status = self._portal.call(recv.receive)
        if isinstance(status, ConnectionCompletedStatus):
            # sent by the `session_runner`
            session = self._client_sessions[transport_id][conversation_id]
            return session
        elif isinstance(status, AuthChallengeRequest):
            # sent by the `OAuthFlowHandler.redirect_handler`
            # called from the `mcp.ClientSession` context manager
            # upon auth flow completion, the session is then directly
            # populated in the self._client_sessions dict.
            auth_request = status
            auth_status = AuthChallengeRequestStatus(
                auth_request=auth_request,
                client_transport_id=transport_id,
                _conversation_id=conversation_id,
            )
            raise AuthInterrupt(auth_status)
        elif isinstance(status, ExceptionGroup):
            # in case the error is just about connect, we raise a meaningful error instead
            for sub_exception in status.exceptions:
                if isinstance(
                    sub_exception, ConnectError
                ) and "All connection attempts failed" in str(sub_exception):
                    raise ConnectionError(
                        "Could not connect to the remote MCP server. Make sure it is "
                        f"running and reachable. Full error: {str(sub_exception)}"
                    ) from sub_exception
                elif isinstance(sub_exception, httpx.HTTPStatusError) and "401 Unauthorized" in str(
                    sub_exception
                ):
                    request = sub_exception.request
                    raise httpx.HTTPStatusError(
                        (
                            f"Encountered Authorization error when connecting to the MCP server. "
                            f"Make sure that you are using the proper Authorization Config for the server. "
                            f"Full error: {str(sub_exception)}"
                        ),
                        request=request,
                        response=sub_exception.response,
                    ) from sub_exception
                elif isinstance(sub_exception, httpx.HTTPStatusError) and "404 Not Found" in str(
                    sub_exception
                ):
                    request = sub_exception.request
                    raise httpx.HTTPStatusError(
                        (
                            f"Successfully reached the MCP server but failed to find the endpoint for the given transport. "
                            f"Make sure that you are using the right url and transport. "
                            f"Full error: {str(sub_exception)}"
                        ),
                        request=request,
                        response=sub_exception.response,
                    ) from sub_exception
                elif isinstance(
                    sub_exception, httpx.HTTPStatusError
                ) and "405 Method Not Allowed" in str(sub_exception):
                    request = sub_exception.request
                    raise httpx.HTTPStatusError(
                        (
                            f"Successfully reached the MCP server but failed when establishing the connection. "
                            f"Make sure that you are using the right transport. "
                            f"Full error: {str(sub_exception)}"
                        ),
                        request=request,
                        response=sub_exception.response,
                    ) from sub_exception
            raise status
        elif isinstance(status, BaseException):
            raise status
        else:
            raise ValueError(f"Unrecognized status: {status}")

    def cancel_oauth_callback(
        self,
        client_transport_id: str,
        conversation_id: str | None,
    ) -> None:
        conv_key = conversation_id or _DEFAULT_MCP_SESSION_CONTEXT_ID
        handler = self._oauth_handlers.get(client_transport_id, {}).get(conv_key)
        if handler is None:
            raise ValueError("No OAuth handler registered for transport/conversation")

        handler._cancel_oauth_flow()

    def _cancel_all_oauth_flows(self) -> None:
        for handlers_by_conv in self._oauth_handlers.values():
            for handler in handlers_by_conv.values():
                try:
                    handler._cancel_oauth_flow()
                except RuntimeError as e:
                    logger.debug("Error when canceling OAuth Flow: %s", e)

    def submit_oauth_callback(
        self,
        client_transport_id: str,
        conversation_id: str | None,
        callback_result: "AuthChallengeResult",
        timeout: float,
    ) -> None:
        """Called by `AuthChallengeRequestStatus.submit_result`."""
        conv_key = conversation_id or _DEFAULT_MCP_SESSION_CONTEXT_ID
        handler = self._oauth_handlers.get(client_transport_id, {}).get(conv_key)
        if handler is None:
            raise ValueError("No OAuth handler registered for transport/conversation")

        handler._submit_oauth_callbackresult(callback_result, timeout)

    def _close_all_sessions(self) -> None:
        # Close memory streams
        for send, recv in self._memory_streams:
            send.close()
            recv.close()
        self._memory_streams.clear()
        # Cancel auth flows still opened (important otherwise would hang)
        self._cancel_all_oauth_flows()
        # Cancel sessions
        for event in self._cancel_events:
            self.call(event.set)  # type: ignore
        self._cancel_events.clear()

    def _close(self) -> None:
        """When the runtime is being shutdown, this method is called to properly
        close the MCP client sessions.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._close_all_sessions()
            # no need to close the portal, this is already handled by the ExitStack

    def shutdown(self) -> None:
        """Gracefully shuts down the MCP async runtime."""
        self._close()
        with self._lock:
            exit_stack = self._exit_stack
            self._exit_stack = ExitStack()
            self._client_sessions.clear()
            self._portal = None

        exit_stack.close()  # closing outside the lock

    @staticmethod
    def _finalize(self_ref: "AsyncRuntime") -> None:
        try:
            self_ref._close()
        except (
            Exception
        ):  # nosec0003 # finalizers must not raise; we ignore normal cleanup errors during shutdown/garbage collection on purpose
            pass


# need a reference here, otherwise weakref might delete the connection object
# once not use for a while
# async runtime is lazily initialized using `.initialize()`
_RUNTIME = AsyncRuntime()
_RUNTIME_INIT_LOCK = threading.Lock()


def get_mcp_async_runtime() -> AsyncRuntime:
    """Gets the current unique MCP Async Runtime."""
    if _RUNTIME.is_live:
        return _RUNTIME

    with _RUNTIME_INIT_LOCK:
        if not _RUNTIME.is_live:
            _RUNTIME.initialize()

    return _RUNTIME


def shutdown_mcp_async_runtime() -> None:
    """Shuts down the current unique MCP Async Runtime."""
    if not _RUNTIME.is_live:
        return  # nothing to shut down

    with _RUNTIME_INIT_LOCK:
        if _RUNTIME.is_live:
            _RUNTIME.shutdown()


def _get_oauth_flow_handler(client_transport: "ClientTransport") -> "OAuthFlowHandler":
    from wayflowcore.conversation import _get_current_conversation_id

    runtime = get_mcp_async_runtime()
    conversation_id = _get_current_conversation_id() or _DEFAULT_MCP_SESSION_CONTEXT_ID
    transport_id = client_transport.id

    handler = runtime._oauth_handlers.get(transport_id, {}).get(conversation_id)
    if handler is None:
        raise ValueError(
            f"No OAuth flow handler is registered for transport '{transport_id}' "
            f"and conversation {conversation_id}."
        )

    return handler


def _bind_portal_info_if_needed(
    client_transport: "ClientTransport",
    memory_stream: MemoryStreamTypeT,
    portal: AsyncRuntime,
    conversation_id: str,
) -> bool:
    """Done when creating a long-lived MCP Client Session."""
    from wayflowcore.auth.auth import OAuthConfig
    from wayflowcore.mcp._auth import OAuthFlowHandler
    from wayflowcore.mcp.clienttransport import RemoteBaseTransport

    transport_id = client_transport.id

    if not (
        isinstance(client_transport, RemoteBaseTransport)
        and isinstance(client_transport.auth, OAuthConfig)
    ):
        return False

    oauth_config = client_transport.auth

    # need to add some validation of the OAuth Config
    # (to raise on unsupported configs)
    handler = OAuthFlowHandler(
        mcp_url=client_transport.url,
        # scopes=oauth_config.scopes,
        # redirect_uri=oauth_config.redirect_uri,
        oauth_config=oauth_config,
    )
    handler.bind_runtime(
        portal=portal,
        memory_stream=memory_stream,
        transport_id=transport_id,
        conversation_id=conversation_id,
    )

    # register handler
    portal._oauth_handlers.setdefault(transport_id, {})[conversation_id] = handler
    return True


def _signal_oauth_completion(
    portal: AsyncRuntime,
    transport_id: str,
    conversation_id: str,
) -> None:
    handler = portal._oauth_handlers.get(transport_id, {}).get(conversation_id)
    if handler is None or handler.oauth_flow_completed_event is None:
        raise ValueError(
            f"No OAuth flow handler is registered for transport '{transport_id}' "
            f"and conversation {conversation_id}."
        )

    handler.oauth_flow_completed_event.set()
