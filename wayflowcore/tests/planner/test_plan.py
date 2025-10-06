# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, List, Union

import pytest

from wayflowcore.planning import ExecutionPlan, Task, TaskStatus


@pytest.mark.parametrize(
    "raw_text,expected",
    [
        (
            "- (id:0, status:PENDING): zero",
            [Task(id="0", description="zero", tool=None, status=TaskStatus.PENDING)],
        ),
        (
            "- (id:1, status:PENDING): one",
            [Task(id="1", description="one", tool=None, status=TaskStatus.PENDING)],
        ),
        ("HALLUCINATION", []),
        ("- (): two", []),
        (
            "- (id:2, status:IN_PROGRESS, tool:tool_2): two",
            [Task(id="2", description="two", tool="tool_2", status=TaskStatus.IN_PROGRESS)],
        ),
        ("- (id:2, tool:tool_2): misses the status", []),
        ("- (status:IN_PROGRESS, tool:tool_2): misses the id", []),
        (
            "- (id:3, status:SUCCESS, tool:tool_3): three",
            [Task(id="3", description="three", tool="tool_3", status=TaskStatus.SUCCESS)],
        ),
    ],
)
def test_str_task_can_be_parsed_into_task(raw_text: str, expected: List[Union[Task, Any]]) -> None:
    plan = ExecutionPlan.from_str(raw_text)
    assert plan == ExecutionPlan(expected)


list_of_tasks = [
    Task(id="0", description="zero", tool=None, status=TaskStatus.PENDING),
    Task(id="1", description="one"),
    Task(id="2", description="two", tool="tool_2", status=TaskStatus.IN_PROGRESS),
    Task(id="3", description="three", tool="tool_3", status=TaskStatus.SUCCESS),
]

expected_str_plan = """- (id:0, status:PENDING): zero
- (id:1, status:PENDING): one
- (id:2, status:IN_PROGRESS, tool:tool_2): two
- (id:3, status:SUCCESS, tool:tool_3): three"""


def test_plan_is_serialized_correctly_for_llm() -> None:
    plan = ExecutionPlan(list_of_tasks)
    plan_str = plan.to_str()
    assert expected_str_plan == plan_str


def test_str_plan_can_be_parsed_into_execution_plan() -> None:
    plan = ExecutionPlan.from_str(expected_str_plan)
    assert plan == ExecutionPlan(list_of_tasks)


def test_plan_to_str_and_from_str_is_the_same() -> None:
    initial_plan = ExecutionPlan(list_of_tasks)
    plan_str = initial_plan.to_str()
    plan_from_str = ExecutionPlan.from_str(plan_str)
    assert plan_from_str == initial_plan
