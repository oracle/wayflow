# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from typing import Any, Callable, Dict, List, Optional, Sequence, TypeVar

from wayflowcore._utils.singleton import Singleton

logger = logging.getLogger(__name__)


T = TypeVar("T")
M = TypeVar("M")


class WayFlowThreadPoolExecutor(metaclass=Singleton):
    def __init__(self) -> None:
        """
        Singleton class for the single wayflowcore thread pool executor. This single object
        manages all threads started in WayFlow (using parallel MapStep).
        """
        self.pool: Optional[ThreadPoolExecutor] = None
        self.max_workers: Optional[int] = None

    def __del__(self) -> None:
        self.shutdown()

    def start(self, max_workers: Optional[int] = None) -> None:
        """
        Starts the thread pool.

        Parameters
        ----------
        max_workers:
            Amount of workers to start.
        """
        if self.pool is not None:
            if self.max_workers != max_workers:
                logger.warning(
                    "The executor is already running. Make sure to shut it down before re-starting it",
                )
            return

        self.max_workers = max_workers
        self.pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="wayflowcore_thread"
        )

    @property
    def is_live(self) -> bool:
        """Whether the thread pool is started or not"""
        return self.pool is not None

    def shutdown(self) -> None:
        """
        Stops the thread pool and cancels all the pending tasks.
        """
        if self.pool is not None:
            self.pool.shutdown(cancel_futures=True)
        self.pool = None
        self.max_workers = None

    def execute(self, func: Callable[[T], M], items: Sequence[T]) -> List[M]:
        """
        Executes a callable on each element of an iterator using all available threads in the pool.

        Parameters
        ----------
        func:
            Function to run
        items:
            Iterable of items to run the function on

        """
        self.start()
        if self.pool is None:
            raise ValueError("Thread pool could not be started")

        # Ensures that Tracing works with Parallel Execution
        global_context_var = copy_context()

        def _run_func(x: Any) -> M:
            return global_context_var.copy().run(func, x)

        futures = {self.pool.submit(_run_func, item): idx for idx, item in enumerate(items)}
        results: Dict[int, M] = {}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()  # ensures completion
            except Exception as exc:
                raise RuntimeError(f"Thread {idx} generated an exception: {exc}")

        if len(results) != len(futures):
            raise ValueError("Some thread went wrong and didn't return anything")

        return [results[i] for i in range(len(futures))]


def initialize_threadpool(num_threads: Optional[int] = None) -> None:
    """Initializes the unique wayflowcore threadpool for parallel operations"""
    thread_pool = WayFlowThreadPoolExecutor()
    if thread_pool.is_live:
        warnings.warn(
            "The WayFlow threadpool is already started. Please make sure to shut it down before re-starting it"
        )
    thread_pool.start(num_threads)


def get_threadpool(start_threadpool: bool = True) -> WayFlowThreadPoolExecutor:
    """Gets the current unique wayflowcore threadpool"""
    thread_pool = WayFlowThreadPoolExecutor()
    if start_threadpool and not thread_pool.is_live:
        thread_pool.start()
    return thread_pool


def shutdown_threadpool() -> None:
    """Shutdowns the wayflowcore unique threadpool"""
    thread_pool = WayFlowThreadPoolExecutor()
    thread_pool.shutdown()
