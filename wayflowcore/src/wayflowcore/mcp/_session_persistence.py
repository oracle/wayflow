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
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

import anyio
from anyio import from_thread, to_thread
from anyio.streams import memory
from exceptiongroup import ExceptionGroup
from httpx import ConnectError
from mcp import ClientSession
from typing_extensions import TypeAlias

from wayflowcore._utils.singleton import Singleton

if TYPE_CHECKING:
    from wayflowcore.mcp.clienttransport import ClientTransport


T = TypeVar("T")
MemoryStreamTypeT: TypeAlias = Tuple[Any, Any]

logger = logging.getLogger(__name__)


_DEFAULT_MCP_SESSION_CONTEXT_ID = "DEFAULT_CONTEXT_ID"
"""Default key used to register a MCP session when not running under a conversation."""


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
        self._sessions: Dict[str, ClientSession] = {}
        # client session per conversation id
        self._memory_streams: List[MemoryStreamTypeT] = []
        self._cancel_events: List[anyio.Event] = []

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
        return self._portal.call(async_fn, *args, **kwargs)

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
        from wayflowcore.conversation import _get_current_conversation_id

        key = _get_current_conversation_id() or _DEFAULT_MCP_SESSION_CONTEXT_ID
        if key not in self._sessions:
            session = self._create_long_lived_session(client_transport)
            self._sessions[key] = session

        return self._sessions[key]

    def _create_long_lived_session(
        self,
        client_transport: "ClientTransport",
    ) -> ClientSession:
        """Creates a long lived MCP ClientSession in a background thread.

        This session is then reused between calls.
        """
        # The memory stream is used to collect the session object from the runner
        send, recv = anyio.create_memory_object_stream(1)  # type: ignore
        self._memory_streams.append((send, recv))

        # The runner will be keeping the MCP client session task alive until the
        # event flag is set (which is done when closing all sessions)
        cancel_event: anyio.Event = self.call(anyio.Event)  # type: ignore
        self._cancel_events.append(cancel_event)

        async def session_runner(
            send_chan: memory.MemoryObjectSendStream[Union[ClientSession, BaseException]],
            cancel_evt: anyio.Event,
        ) -> None:
            sent_first = False
            try:
                async with client_transport._get_client_transport_cm() as transport_tuple:
                    read_stream, write_stream = transport_tuple[0], transport_tuple[1]
                    async with ClientSession(
                        read_stream, write_stream, **client_transport.session_parameters.to_dict()
                    ) as session:
                        try:
                            await session.initialize()
                        except Exception as e:
                            raise e
                        await send_chan.send(session)
                        # keep task alive until asked to stop
                        await cancel_evt.wait()
            except Exception as e:
                if not sent_first:
                    # Shield sending the error so it isn’t cancelled
                    with anyio.CancelScope(shield=True):
                        await send_chan.send(e)
                # Re-raise to surface in logs/monitoring
                raise e

        # start the long-lived task
        if not self._portal:
            raise RuntimeError("Async runtime not started")

        self._portal.start_task_soon(session_runner, send, cancel_event)
        res = self._portal.call(recv.receive)

        if isinstance(res, ExceptionGroup):
            # in case the error is just about connect, we raise a meaningful error instead
            for sub_exception in res.exceptions:
                if isinstance(
                    sub_exception, ConnectError
                ) and "All connection attempts failed" in str(sub_exception):
                    raise ConnectionError(
                        "Could not connect to the remote MCP server. Make sure it is running and reachable."
                    ) from sub_exception
            raise res
        elif isinstance(res, BaseException):
            raise res

        session: ClientSession = res
        return session

    def _close_all_sessions(self) -> None:
        # Close memory streams
        for send, recv in self._memory_streams:
            send.close()
            recv.close()
        self._memory_streams.clear()
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
            self._exit_stack.close()
            self._sessions.clear()
            self._portal = None

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
