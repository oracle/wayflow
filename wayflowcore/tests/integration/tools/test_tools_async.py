# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import time

import anyio

from wayflowcore import tool
from wayflowcore.tools import ServerTool


async def _check_server_tool_works_asynchronously(server_tool: ServerTool):
    start = time.time()
    async with anyio.create_task_group() as tg:
        for _ in range(100):
            tg.start_soon(server_tool.run_async)

    assert time.time() - start < 5  # if ran in main event loop, should be > 10


def _check_server_tool_works_synchronously(server_tool: ServerTool):
    assert server_tool.run() == ""


def test_can_create_server_tool_with_async_func():
    async def my_tool_func():
        await anyio.sleep(0.1)
        return ""

    my_tool = ServerTool(
        name="my_tool",
        description="description",
        input_descriptors=[],
        func=my_tool_func,
    )

    anyio.run(_check_server_tool_works_asynchronously, my_tool)
    _check_server_tool_works_synchronously(my_tool)


def test_can_create_async_server_tool_with_decorator():

    @tool(description_mode="only_docstring")
    async def my_tool() -> str:
        """description"""
        await anyio.sleep(0.1)
        return ""

    anyio.run(_check_server_tool_works_asynchronously, my_tool)
    _check_server_tool_works_synchronously(my_tool)


def test_synchronous_server_tool_is_ran_in_worker_thread():

    @tool(description_mode="only_docstring")
    def my_tool() -> str:
        """description"""
        time.sleep(0.1)
        return ""

    anyio.run(_check_server_tool_works_asynchronously, my_tool)
    _check_server_tool_works_synchronously(my_tool)
