# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import contextlib
import contextvars
import inspect
import warnings
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import (
    Any,
    AsyncContextManager,
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    TypeVar,
)

import anyio
from anyio import from_thread
from exceptiongroup import BaseExceptionGroup
from sniffio import AsyncLibraryNotFoundError
from typing_extensions import Self

T = TypeVar("T")


AsyncFuncType = Callable[..., Awaitable[Any]]
FuncType = Callable[..., Any]


class AsyncContext(Enum):
    ASYNC = "async"
    SYNC = "sync"
    SYNC_WORKER = "sync_worker"


def _no_event_loop_exc_types() -> tuple[type[BaseException], ...]:
    exc_types: list[type[BaseException]] = []

    # anyio < 4.12.0
    exc_types.append(AsyncLibraryNotFoundError)

    # anyio == 4.12.0
    try:
        from anyio._core._eventloop import NoCurrentAsyncBackend  # type: ignore
    except ImportError:
        pass
    else:
        exc_types.append(NoCurrentAsyncBackend)

    # anyio > 4.12.0
    t = getattr(anyio, "NoEventLoopError", None)
    if isinstance(t, type) and issubclass(t, BaseException):
        exc_types.append(t)

    return tuple(exc_types)


_NO_EVENT_LOOP_EXCS = _no_event_loop_exc_types()


def get_execution_context() -> AsyncContext:
    """
    Return one of:
    - 'sync'         → plain synchronous context (no loop, no worker thread)
    - 'sync_worker'  → synchronous worker thread (spawned by to_thread.run_sync)
    - 'async'        → running inside the event loop
    """
    try:
        anyio.get_current_task()
        return AsyncContext.ASYNC
    except _NO_EVENT_LOOP_EXCS:
        # 1. if no backend is installed
        # 2. if no event loop is running
        current_thread = from_thread.current_thread()  # type: ignore
        worker_name = current_thread.name.lower()
        if "worker" in worker_name and "anyio" in worker_name:
            # for anyio workers, we can use specific methods to
            # handle back asynchronous code to the main loop
            return AsyncContext.SYNC_WORKER
        else:
            # otherwise, consider it as a synchronous thread
            return AsyncContext.SYNC


def run_async_in_sync(
    async_function: Callable[..., Awaitable[T]], *args: Any, method_name: str = ""
) -> T:
    """
    Runs an asynchronous function in any context, choosing the most efficient way to do so
    """
    match get_execution_context():
        case AsyncContext.SYNC:
            # case 1: synchronous context
            return anyio.run(async_function, *args)
        case AsyncContext.SYNC_WORKER:
            # case 2: from worker thread get back to existing async event loop
            return from_thread.run(async_function, *args)
        case AsyncContext.ASYNC:
            # case 3: from async main context
            # this is highly discouraged since it synchronises work that could
            # be just run async
            warnings.warn(
                "You are calling an asynchronous method in a synchronous method from an asynchronous context. "
                "This is highly discouraged because it can lead to deadlocks. "
                f"Please use the asynchronous method equivalent: {method_name}",
                UserWarning,
            )

            # workaround: anyio does not have any API run asynchronous code in a
            # synchronous method that was not started with anyio.to_thread
            # instead, we spawn a thread to execute it in a completely new event loop
            def thread_target() -> T:
                return anyio.run(async_function, *args)

            future = ThreadPoolExecutor(max_workers=1).submit(thread_target)
            return future.result()
        case unsupported_context:
            raise NotImplementedError(f"Unsupported async context: {unsupported_context}")


class SyncAsyncIterable(Generic[T], Iterable[T]):
    """
    Sync iterable over async iterator.
    All asynchronous tasks will share the same context variables
    through a `shared_ctx` mutable dictionary.
    """

    def __init__(self, async_iterable: AsyncIterator[T]) -> None:
        self.async_iterable = async_iterable
        self.shared_ctx = {k: v for k, v in contextvars.copy_context().items()}
        self.portal_cm = None
        # We use an AnyIO portal because it lets sync code safely call into an existing
        # async event loop. Unlike `anyio.run` or `to_thread.run_sync`, the portal keeps
        # the loop alive across multiple calls. This is essential for driving an async
        # iterator step-by-step from synchronous iteration.
        self.portal = None
        self.ait = None
        self.closed = False

    def __iter__(self) -> "SyncAsyncIterable[T]":
        return self

    def run_iteration(self, mutable_state: Dict[contextvars.ContextVar[Any], Any]) -> AsyncFuncType:
        async def _run() -> T:
            # set the context vars based on the content of the shared mutable dict
            for var, val in mutable_state.items():
                var.set(val)
            # execute the workload
            result = await self.async_iterable.__anext__()
            # transmit the context variables updates to the shared mutable dict
            for var in mutable_state:
                mutable_state[var] = var.get()
            return result

        return _run

    def _lazy_init(self) -> None:
        if self.portal is None:
            self.portal_cm = from_thread.start_blocking_portal()  # type: ignore
            self.portal = self.portal_cm.__enter__()  # type: ignore
            self.ait = self.portal.call(self.async_iterable.__aiter__)  # type: ignore

    def __next__(self) -> T:
        if self.closed:
            raise StopIteration

        self._lazy_init()
        if self.portal is None:
            raise RuntimeError("Something went wrong, could not start the portal")

        try:
            result = self.portal.call(self.run_iteration(self.shared_ctx))
            return result
        except StopAsyncIteration:
            self.close()
            raise StopIteration
        except Exception as e:
            # we catch all types of exception, close the portal, and then raise
            self.close()
            raise e

    def close(self) -> None:
        if self.closed:
            return

        if self.portal is not None:
            try:
                self.portal.call(self.ait.aclose)
            finally:
                self.portal_cm.__exit__(None, None, None)
        self.closed = True


def async_to_sync_iterator(async_iterable: AsyncIterable[T]) -> Iterable[T]:
    """Transforms an asynchronous iterator into a synchronous iterable"""
    if not isinstance(async_iterable, AsyncIterator):
        raise ValueError(
            f"AsyncIterable {async_iterable} should be an AsyncIterator to be able to "
            f"transform it into a synchronous Iterable, but was not."
        )
    return SyncAsyncIterable(async_iterable)


class AsyncSyncIterable(Generic[T], AsyncIterable[T]):
    """
    Async iterable over a sync iterator.
    """

    def __init__(self, sync_iterable: Iterable[T]) -> None:
        self.sync_iterable = sync_iterable

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> T:
        try:
            return self.sync_iterable.__next__()  # type: ignore
        except StopIteration:
            raise StopAsyncIteration()


def sync_to_async_iterator(sync_iterable: Iterable[T]) -> AsyncIterable[T]:
    """Transforms an synchronous iterable into a asynchronous iterable"""
    return AsyncSyncIterable(sync_iterable)


FuncRetType = TypeVar("FuncRetType")


async def run_sync_in_thread(func: Callable[..., FuncRetType], *args: Any) -> FuncRetType:
    """Runs a synchronous function in another thread"""
    return await anyio.to_thread.run_sync(func, *args)


async def run_sync_in_process(func: Callable[..., FuncRetType], *args: Any) -> FuncRetType:
    """Runs a synchronous function in another process"""
    return await anyio.to_process.run_sync(func, *args)  # type: ignore


def transform_sync_into_async(func: FuncType) -> AsyncFuncType:
    """
    Transforms a sync function into an async function that delegates the synchronous
    work to an anyio worker
    """

    async def _wrapped(*args: Any, **kwargs: Any) -> Any:
        # need to wrap because anyio can't use named arguments
        def tool_callable_without_inputs() -> Any:
            return func(*args, **kwargs)

        return await anyio.to_thread.run_sync(tool_callable_without_inputs)

    return _wrapped


def transform_async_into_sync(func_async: AsyncFuncType) -> FuncType:
    """
    Transforms an async function into a synchronous function.
    """

    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        # need to wrap because we can't pass named arguments to anyio
        async def inside_wrapped() -> Any:
            return await func_async(*args, **kwargs)

        return run_async_in_sync(inside_wrapped)

    return _wrapped


TInput = TypeVar("TInput")
TResult = TypeVar("TResult")


async def run_async_function_in_parallel(
    func_async: Callable[[TInput], Awaitable[TResult]],
    input_list: List[TInput],
    max_workers: Optional[int] = None,
) -> List[TResult]:
    """
    Run a given asynchronous function in parallel with all the
    passed inputs, with a given max number of workers
    """
    max_workers_semaphore: AsyncContextManager[Any] = (
        anyio.Semaphore(initial_value=max_workers)  # type: ignore
        if max_workers is not None
        else contextlib.nullcontext()
    )

    all_outputs: Dict[int, TResult] = {}

    # wrap with the semaphore
    async def run_and_collect(
        func_inputs: TInput, index: int, semaphore: AsyncContextManager[Any]
    ) -> None:
        async with semaphore:
            result = await func_async(func_inputs)
            all_outputs[index] = result

    try:
        async with anyio.create_task_group() as tg:
            for idx, f_input in enumerate(input_list):
                tg.start_soon(run_and_collect, f_input, idx, max_workers_semaphore)
    except BaseExceptionGroup as eg:
        # raise the first exception encountered
        for e in eg.exceptions:
            raise e

    return list(all_outputs[i] for i in range(len(input_list)))


def is_coroutine_function(obj: Any) -> bool:
    """
    Checks whether the object is a coroutine function or not.
    Also detects objects with an async __call__
    """
    if inspect.iscoroutinefunction(obj):
        return True
    return hasattr(obj, "__call__") and inspect.iscoroutinefunction(obj.__call__)
