# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import threading
import time

import pytest

from wayflowcore._threading import get_threadpool, initialize_threadpool, shutdown_threadpool


def thread_tool_func(x: int) -> int:
    """Will sleep for some time"""
    time.sleep(0.01)  # make sure all threads will be used
    return threading.get_ident()


def execute_parallel_operations() -> int:
    pool_executor = get_threadpool()
    outputs = pool_executor.execute(thread_tool_func, range(50))
    pool_executor.shutdown()
    return len(set(outputs))


@pytest.mark.parametrize(
    "max_workers",
    [1, 2, 3],
)
def test_pool_uses_proper_amount_of_threads(max_workers, shutdown_threadpool_fixture):
    shutdown_threadpool()
    initialize_threadpool(max_workers)
    num_thread_used = execute_parallel_operations()
    assert num_thread_used == max_workers
    shutdown_threadpool()
    # TODO proper shutdown if it crashes


def test_pool_can_be_started_and_shutdown_and_restarted(shutdown_threadpool_fixture):
    shutdown_threadpool()
    initialize_threadpool(1)
    num_thread_used = execute_parallel_operations()
    assert num_thread_used == 1
    shutdown_threadpool()
    initialize_threadpool(2)
    num_thread_used = execute_parallel_operations()
    assert num_thread_used == 2
    shutdown_threadpool()
    initialize_threadpool(3)
    num_thread_used = execute_parallel_operations()
    assert num_thread_used == 3
    shutdown_threadpool()


def test_pool_is_automatically_started(shutdown_threadpool_fixture):
    execute_parallel_operations()
    shutdown_threadpool()


def test_pool_can_be_shutdown_several_times(shutdown_threadpool_fixture):
    initialize_threadpool()
    shutdown_threadpool()
    shutdown_threadpool()


def test_pool_can_be_initialized_several_times(shutdown_threadpool_fixture):
    with pytest.warns(
        match="The WayFlow threadpool is already started. Please make sure to shut it down before re-starting it"
    ):
        initialize_threadpool()
        initialize_threadpool()
        shutdown_threadpool()
