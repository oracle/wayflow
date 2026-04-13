# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from concurrent.futures import ThreadPoolExecutor

import anyio
import pytest
from anyio import to_thread

from wayflowcore._utils.async_helpers import (
    AsyncContext,
    async_to_sync_iterator,
    get_execution_context,
    run_async_in_sync,
    sync_to_async_iterator,
    transform_async_into_sync,
    transform_sync_into_async,
)


def test_can_detect_non_async_context():
    assert get_execution_context() == AsyncContext.SYNC


def test_can_detect_threaded_context():
    result = None

    def _check():
        nonlocal result
        result = get_execution_context()

    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(_check)

    assert result == AsyncContext.SYNC


@pytest.mark.anyio
async def test_can_detect_async_context_in_main_event_loop():
    assert get_execution_context() == AsyncContext.ASYNC


@pytest.mark.anyio
async def test_can_detect_async_context_in_async_workers():
    result = None

    async def _detect_context():
        nonlocal result
        result = get_execution_context()

    async with anyio.create_task_group() as tg:
        tg.start_soon(_detect_context)

    assert result == AsyncContext.ASYNC


def test_can_detect_async_context_in_manual_main_event_loop():
    async def _detect_context():
        return get_execution_context()

    assert anyio.run(_detect_context) == AsyncContext.ASYNC


@pytest.mark.anyio
async def test_can_detect_async_context_in_sync_worker():
    assert await to_thread.run_sync(get_execution_context) == AsyncContext.SYNC_WORKER


async def async_work():
    return True


def test_can_run_synchronous_api_from_synchronous_context():
    result = run_async_in_sync(async_work)
    assert result is True


def test_can_run_synchronous_api_from_main_event_loop():
    async def execute():
        return run_async_in_sync(async_work)

    with pytest.warns(
        UserWarning, match="You are calling an asynchronous method in a synchronous method"
    ):
        result = anyio.run(execute)
        assert result is True


@pytest.mark.anyio
async def test_can_run_synchronous_api_from_sync_anyio_workers():
    def _worker():
        return run_async_in_sync(async_work)

    result = await to_thread.run_sync(_worker)

    assert result is True


@pytest.mark.anyio
async def test_can_run_synchronous_api_from_async_workers():
    result = None

    async def _worker():
        nonlocal result
        result = run_async_in_sync(async_work)

    with pytest.warns(
        UserWarning, match="You are calling an asynchronous method in a synchronous method"
    ):
        async with anyio.create_task_group() as tg:
            tg.start_soon(_worker)

    assert result is True


def test_can_run_synchronous_api_from_sync_threadpool_workers():
    result = None

    def _worker():
        nonlocal result
        result = run_async_in_sync(async_work)

    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(_worker)

    assert result is True


async def _async_iterator():
    for i in range(3):
        yield i


def _sync_iterator():
    for i in range(3):
        yield i


def _run_async_iterator_in_sync_context():
    cnt = 0
    for value in async_to_sync_iterator(_async_iterator()):
        assert value == cnt
        cnt += 1


def test_can_iterate_with_sync_iterator():
    _run_async_iterator_in_sync_context()


@pytest.mark.anyio
async def test_can_iterate_with_sync_iterator_in_sync_thread():
    await to_thread.run_sync(_run_async_iterator_in_sync_context)


@pytest.mark.anyio
async def test_can_iterate_with_async_iterator():
    cnt = 0
    async for value in sync_to_async_iterator(_sync_iterator()):
        assert value == cnt
        cnt += 1


def test_can_transform_sync_into_async():
    def _wrap():
        return "hello"

    assert _wrap() == "hello"

    _wrap_async = transform_sync_into_async(_wrap)
    assert anyio.run(_wrap_async) == "hello"


def test_can_transform_async_into_sync():
    async def _wrap_async():
        return "hi"

    assert anyio.run(_wrap_async) == "hi"

    _wrap = transform_async_into_sync(_wrap_async)
    assert _wrap() == "hi"


def test_can_transform_nested():
    def _wrap():
        return "hallo"

    assert _wrap() == "hallo"

    _wrap_async = transform_sync_into_async(_wrap)
    assert anyio.run(_wrap_async) == "hallo"

    _wrap = transform_async_into_sync(_wrap_async)
    assert _wrap() == "hallo"
